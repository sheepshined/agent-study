#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s02_runnable_lcel.py —— Runnable 协议与 LCEL：`a | b` 到底发生了什么

LangChain 的第二块招牌：**一切组件都是 Runnable（可运行单元）**——
模型、提示词、解析器、工具甚至普通函数，全都能 invoke，全都能用 `|` 串成链
（LCEL，LangChain Expression Language，LangChain 表达式语言）。

而 LCEL 的全部魔法只有一行 Python 运算符重载：

    a | b   →   RunnableSequence(a, coerce_to_runnable(b))    # runnables/base.py:688

本文件用纯标准库实现 mini-LCEL，走读五个机制：

    prompt ──|──▶ model ──|──▶ parser          （书写视角：一条链）
       ▲           ▲           ▲
       └── coerce_to_runnable 归一化 ──┘         （真相视角：全被规整成 Runnable）
                     │
        RunnableSequence（拍平 + 逐步 invoke + 子回调）
          ├── invoke()   串行管道
          ├── batch()    线程池并发（max_concurrency 控流）
          └── stream()   逐段吐出

  · 拍平：(a|b)|c 与 a|(b|c) 的 steps 都是 [a,b,c] 一层——链不会越拼越深。
  · 子回调：每步 invoke 前 patch_config 挂上 child 回调（runnables/base.py:3465），
    整棵回调树（LangSmith 追踪的基础）就是这样一层层长出来的。
  · batch 的并发没有黑魔法：线程池 executor.map + 每个输入独立 config
    （base.py:994），跨线程保回调不断链靠 copy_context（config.py:639）。

运行：python code.py          （零依赖，离线；模型由脚本化 Mock 扮演）
对照真实源码（快照 80b7409，行号以源码为准）：
    libs/core/langchain_core/runnables/base.py
        :145  class Runnable(ABC, Generic[Input, Output])            协议本体
        :640  def __or__ / :688 return RunnableSequence(self, ...)   管道符实现
        :691 def __ror__                                             反向版本
        :3092 class RunnableSequence  :3186 __init__（拍平）  :3447 invoke
        :946  def batch（:994 executor.map 并发）
        :3881 class RunnableParallel  :4156 invoke（fan-out）
        :4720 class RunnableLambda    :5180 生成器函数 → 流式累积
        :6640 def coerce_to_runnable                                 归一化入口
    libs/core/langchain_core/runnables/config.py
        :183 DEFAULT_RECURSION_LIMIT = 25      :267 ensure_config
        :369 patch_config                      :619 ContextThreadPoolExecutor（:639 copy_context）
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from collections.abc import Generator, Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from mini_util import EventLog, banner  # noqa: E402

# ---------------------------------------------------------------
# 第 1 部分：Runnable 协议 + config（回调树与并发度的载体）
# ---------------------------------------------------------------
Config = dict  # mini 版 RunnableConfig：{"callbacks": [fn], "max_concurrency": int, ...}


def child_callbacks(config: Config, tag: str) -> list:
    """mini patch_config：给子调用挂上带命名空间的回调。

    真实实现 patch_config（config.py:369）替换 callbacks 为
    run_manager.get_child(f"seq:step:{i}")——回调树因此逐层生长，
    LangSmith 的追踪树形就是这里的 tag 前缀。
    """
    return [f"{tag}·{cb}" for cb in config.get("callbacks", [])]


class Runnable(ABC):
    """协议本体（base.py:145 的 mini 版）：invoke / batch / stream 三件套。

    学会这一个协议，等于学会全部组件——模型、提示词、解析器、工具
    都实现它，所以都能进链、都能被 `|` 串。
    """

    name: str = "Runnable"

    def __or__(self, other: Any) -> "RunnableSequence":
        """LCEL 的全部魔法就这一行（base.py:640 定义在协议上、:688 实现）：
        左操作数与"被规整成 Runnable 的右操作数"装进 RunnableSequence。
        真实代码还有对称的 __ror__（:691），处理 `dict | runnable` 的写法。
        """
        return RunnableSequence(self, coerce_to_runnable(other))

    @abstractmethod
    def invoke(self, input_: Any, config: Config | None = None) -> Any: ...

    def batch(self, inputs: list, config: Config | None = None) -> list:
        """批量并发（base.py:946 的 mini 版）：线程池 map，max_concurrency 控流。"""
        config = config or {}
        workers = config.get("max_concurrency") or len(inputs)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            return list(ex.map(lambda x: self.invoke(x, config), inputs))

    def stream(self, input_: Any, config: Config | None = None) -> Generator[Any, None, None]:
        """默认流式实现：整体 invoke 后单段吐出（假流式，chat_models.py:735 同款思路）。"""
        yield self.invoke(input_, config)


# ---------------------------------------------------------------
# 第 2 部分：coerce_to_runnable —— LCEL 的规整层
# ---------------------------------------------------------------
def coerce_to_runnable(thing: Any) -> Runnable:
    """把"长得像组件的东西"统一规整成 Runnable（base.py:6640）。

    Runnable → 原样；函数 → RunnableLambda；字典 → RunnableParallel；
    其余 → TypeError。语法糖越甜，规整层越厚。
    """
    if isinstance(thing, Runnable):
        return thing
    if callable(thing):
        return RunnableLambda(thing)
    if isinstance(thing, dict):
        return RunnableParallel(thing)
    raise TypeError(f"无法把 {type(thing).__name__} 规整成 Runnable：实现 Runnable / 可调用 / 是字典")


class RunnableLambda(Runnable):
    """普通函数的包装（base.py:4720）。

    彩蛋（:5180）：函数是生成器函数时，输出被逐段相加——这就是
    "为什么 lambda 里 yield 能参与流式"。
    """

    def __init__(self, func: Callable, name: str | None = None) -> None:
        self.func = func
        self.name = name or f"lambda:{getattr(func, '__name__', 'anon')}"

    def invoke(self, input_: Any, config: Config | None = None) -> Any:
        return self.func(input_)

    def stream(self, input_: Any, config: Config | None = None) -> Generator[Any, None, None]:
        out = self.func(input_)
        if isinstance(out, Iterable) and not isinstance(out, (str, bytes, dict)):
            for chunk in out:
                yield chunk
        else:
            yield out


class RunnableParallel(Runnable):
    """fan-out 并行（base.py:3881）：一个输入同时喂给多个分支。

    真实实现用 executor.submit 每个分支、子 run 命名 map:key:{key}；
    mini 版用线程池 map 语义等价。
    """

    def __init__(self, branches: dict[str, Any]) -> None:
        self.branches = {k: coerce_to_runnable(v) for k, v in branches.items()}
        self.name = "RunnableParallel"

    def invoke(self, input_: Any, config: Config | None = None) -> dict:
        keys = list(self.branches)
        with ThreadPoolExecutor(max_workers=len(keys)) as ex:
            values = list(ex.map(lambda k: self.branches[k].invoke(input_, config), keys))
        return dict(zip(keys, values))


# ---------------------------------------------------------------
# 第 3 部分：RunnableSequence —— 串行管道与回调树
# ---------------------------------------------------------------
class RunnableSequence(Runnable):
    """串行管道（base.py:3092）。

    __init__（:3186）把嵌套的 RunnableSequence 拍平成一级 steps 列表，
    所以 (a|b)|c 和 a|(b|c) 拼出来都是 [a,b,c]——链不会越拼越深。
    """

    def __init__(self, *steps: Any) -> None:
        flat: list[Runnable] = []
        for step in steps:
            if isinstance(step, RunnableSequence):
                flat.extend(step.steps)  # 拍平：嵌套序列展开（对应 :3208-3212）
            else:
                flat.append(coerce_to_runnable(step))
        self.steps = flat
        self.name = "RunnableSequence"

    def invoke(self, input_: Any, config: Config | None = None) -> Any:
        config = config or {}
        log: EventLog | None = config.get("event_log")
        current = input_
        for i, step in enumerate(self.steps, 1):
            if log is not None:
                log.log("on_chain_start", run=f"seq:step:{i}", name=step.name)
            # 子回调：真实代码在每步前 patch_config（:3465-3469），mini 用 tag 前缀示意
            step_config = {**config, "callbacks": child_callbacks(config, f"seq:step:{i}")}
            current = step.invoke(current, step_config)
            if log is not None:
                log.log("on_chain_end", run=f"seq:step:{i}", name=step.name)
        return current

    def stream(self, input_: Any, config: Config | None = None) -> Generator[Any, None, None]:
        """管道流式（简化自 :3844）：前 n-1 步逐段流式累积，最后一步的段吐给调用方。"""
        current = input_
        for step in self.steps[:-1]:
            acc: Any = None
            for chunk in step.stream(current, config):
                acc = chunk if acc is None else acc + chunk
            current = acc
        yield from self.steps[-1].stream(current, config)

    def __repr__(self) -> str:
        return f"RunnableSequence({[s.name for s in self.steps]})"


def make_operator_or() -> None:
    """教学注脚：真实的 `|` 定义在 Runnable 上（base.py:640）：

        def __or__(self, other): return RunnableSequence(self, coerce_to_runnable(other))

    Python 运算符重载而已——不是 DSL（Domain-Specific Language，领域专用语言）。
    本文件的 RunnableSequence.__or__ 复刻了同一行为。
    """


# ---------------------------------------------------------------
# 第 4 部分：脚本化 Mock 组件（prompt / model / parser 都是 Runnable）
# ---------------------------------------------------------------
class MockPrompt(Runnable):
    """提示词模板：渲染 {question}（真实对应 prompts/prompt.py:24 的 PromptTemplate）。"""

    name = "MockPrompt"

    def __init__(self, template: str) -> None:
        self.template = template

    def invoke(self, input_: dict, config: Config | None = None) -> str:
        return self.template.format(**input_)


class MockModel(Runnable):
    """脚本化模型：输入 str，输出固定回复（真实对应 chat_models.py:284 BaseChatModel）。"""

    name = "MockModel"

    def __init__(self, reply: str, stream_tokens: list[str] | None = None) -> None:
        self.reply = reply
        self.stream_tokens = stream_tokens or [c + "|" for c in reply]

    def invoke(self, input_: str, config: Config | None = None) -> str:
        return self.reply

    def stream(self, input_: str, config: Config | None = None):
        yield from self.stream_tokens


class MockParser(Runnable):
    """解析器：取前 8 个字符做"摘要"（真实对应 output_parsers/base.py:140）。"""

    name = "MockParser"

    def invoke(self, input_: str, config: Config | None = None) -> str:
        return input_[:8]


# ---------------------------------------------------------------
# 第 5 部分：演示
# ---------------------------------------------------------------
def main() -> None:
    banner("场景 1：prompt | model | parser", "三次 __or__，一个 RunnableSequence；拍平保证一层")
    chain = MockPrompt("问题：{question}") | MockModel("LCEL 就是运算符重载，没有魔法。") | MockParser()
    print(f"  链结构: {chain!r}")
    alt = MockPrompt("问题：{question}") | (MockModel("LCEL 就是运算符重载，没有魔法。") | MockParser())
    names = lambda c: [s.name for s in c.steps]
    print(f"  结合律: (p|m)|parser 与 p|(m|parser) 的 steps 相同？ {names(chain) == names(alt)}")
    print(f"  invoke 结果: {chain.invoke({'question': '什么是LCEL'})}")

    banner("场景 2：回调树", "每步 invoke 前挂子回调——追踪树逐层生长")
    log = EventLog()
    chain.invoke({"question": "什么是LCEL"}, {"callbacks": ["tracer"], "event_log": log})
    log.dump()

    banner("场景 3：batch 并发", "线程池 map；max_concurrency 控流（真实靠 copy_context 保回调）")
    answers = MockModel(reply="x").batch(["q1", "q2", "q3"], {"max_concurrency": 2})
    print(f"  3 个输入、并发 2 → {len(answers)} 个输出（并发度受 config 控制）")

    banner("场景 4：字典自动成 RunnableParallel", "fan-out：同一输入喂给两个分支")
    both = MockPrompt("{question}") | {"raw": lambda s: s.upper(), "length": lambda s: len(s)}
    print(f"  fan-out 结果: {both.invoke({'question': 'abc'})}")

    banner("场景 5：生成器函数 → 流式累积", "RunnableLambda 的 yield 彩蛋（base.py:5180）")
    to_words = RunnableLambda(lambda s: (w + " " for w in s.split()))
    print(f"  逐段: {list(to_words.stream('one two three'))}")
    streamer = MockModel("ABC", ["A", "B", "C"]) | RunnableLambda(lambda s: (f"[{c}]" for c in s))
    for chunk in streamer.stream("ignored"):
        print(f"  管道流式 chunk: {chunk}")

    banner("场景 6（边界）：规整失败", "coerce_to_runnable 拒绝不认识的东西")
    try:
        MockPrompt("x") | 42
    except TypeError as e:
        print(f"  TypeError: {e}")

    print("\n结论：LCEL 不是 DSL，就是运算符重载 + 归一化 + 串行管道。")
    print("组件层永远不知道编排层的存在——换任何一步，链照跑（s01 的 agent 也会在 s10 回来当链的一步）。")


if __name__ == "__main__":
    main()
