# -*- coding: utf-8 -*-
"""
s01_state_reducer.py —— StateGraph 与 reducer：状态 schema 怎么变成通道

LangGraph 的第一性设计：节点之间从不共享内存、也从不互相调用，
它们只"各自读一份状态、各交一份增量补丁"。于是两个问题决定一切：

  1) 增量补丁写到哪？—— 每个状态键一个**通道**（channel，状态的运行时载体）
  2) 同一个键收到多份补丁怎么合？—— 键上挂的 **reducer**（归并函数）

真实源码里这件事分两层：
  · 建图层 graph/state.py:143 的 StateGraph：类 docstring 就是规范——
    "节点签名 State -> Partial<State>"(:146)、"reducer 签名 (Value,Value)->Value"(:148-150)
  · 运行层 channels/base.py:19 的 BaseChannel 协议（7 个方法，:49-112），
    默认实现 channels/last_value.py:20 的 LastValue（一拍只收一个值），
    带 reducer 的键编译成 channels/binop.py:65 的 BinaryOperatorAggregate（逐值折叠 :143）

本文件用纯标准库实现这两层的 mini 版：

    State(TypedDict)                     channels/ 运行时
    +---------------------------+        +--------------------------------+
    | count: int                |  编译  | "count"  -> LastValue          |
    | logs:  list               | -----> | "logs"   -> LastValue          |
    | msgs:  Annotated[list,    |        | "msgs"   -> ReducerChannel     |
    |           add_messages]   |        |            (add_messages)      |
    +---------------------------+        +--------------------------------+
         schema 声明（Annotated 元数据）        每键一通道，合并语义在通道内部

运行：python code.py            （零依赖，离线）
对照真实源码：libs/langgraph/langgraph/graph/state.py、
             libs/langgraph/langgraph/channels/{base,last_value,binop}.py
"""

from __future__ import annotations

import operator
import sys
from pathlib import Path
from typing import Annotated, TypedDict, get_args, get_origin, get_type_hints

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 允许 python code.py 直跑
from shared.mini_util import banner, expect_error, fmt_state


# ---------------------------------------------------------------
# 第 1 部分：通道 —— 状态键的运行时载体
# ---------------------------------------------------------------
# 真实协议 channels/base.py:49-112 定义 7 个方法；教学版取最核心的 4 个。
class LastValue:
    """默认通道：只记住"本拍最后写入的那个值"。

    对应 channels/last_value.py:20。docstring 原话：
    "Stores the last value received, can receive at most one value per step."
    """

    def __init__(self, key: str):
        self.key = key
        self.value = None

    def update(self, values: list) -> bool:
        """批量写入：一拍收到 0 个值返回 False；>1 个值直接报错。

        对应 last_value.py:56-66：这正是新手最常见的
        INVALID_CONCURRENT_GRAPH_UPDATE 报错的出处——报错信息原样照抄
        真实源码 :61："Can receive only one value per step. Use an
        Annotated key to handle multiple values."
        """
        if not values:
            return False
        if len(values) != 1:
            raise InvalidUpdateError(
                f"At key '{self.key}': Can receive only one value per step. "
                "Use an Annotated key to handle multiple values."
            )
        self.value = values[-1]  # 一拍一个值，直接覆盖（后写覆盖前写）
        return True

    def get(self):
        return self.value


class InvalidUpdateError(Exception):
    """真实源码 types.py 的 InvalidUpdateError 教学版。"""


class ReducerChannel:
    """reducer 通道：一拍收到 N 个值，就用二元函数折叠 N 次。

    对应 channels/binop.py:65 的 BinaryOperatorAggregate——
    `Annotated[list, operator.add]` 这类键编译成它，折叠发生在 :143。
    """

    def __init__(self, key: str, reducer):
        self.key = key
        self.reducer = reducer  # (Value, Value) -> Value
        self.value = None

    def update(self, values: list) -> bool:
        if not values:
            return False
        if self.value is None:
            self.value, values = values[0], values[1:]  # 首值直接落位
        for v in values:
            self.value = self.reducer(self.value, v)  # ★ reducer 的最终执行处
        return True

    def get(self):
        return self.value


def add_messages(left: list, right: list) -> list:
    """LangGraph 最著名的 reducer：按消息 id 去重追加 / 原位替换。

    真实实现在 libs/langgraph/langgraph/_messages.py 一带（消息 id 相同
    视为同一条：新的替换旧的，新的追加到尾部）。mini 版保留语义主干。
    """
    merged = {m["id"]: m for m in left}
    for m in right:
        merged[m["id"]] = m  # 同 id = 替换，新 id = 追加
    return list(merged.values())


# ---------------------------------------------------------------
# 第 2 部分：schema → 通道（compile 做的第一件事）
# ---------------------------------------------------------------
# 真实编译逻辑在 graph/state.py 的 _get_channels 一带：从 Annotated 元数据
# 里提取 reducer（:1906），校验签名必须是二元函数，否则构造期就报错（:1934）
# ——错误左移到建图阶段，是值得学的工程习惯。
def build_channels(schema) -> dict:
    """把 TypedDict schema 翻译成 {键: 通道}。含编译期 reducer 校验。"""
    hints = get_type_hints(schema, include_extras=True)
    channels = {}
    for key, typ in hints.items():
        if get_origin(typ) is Annotated:  # Annotated[list, add_messages] 这类
            base, *meta = get_args(typ)
            reducer = meta[-1]
            if reducer is operator.add:  # 二元运算符直接可用
                channels[key] = ReducerChannel(key, reducer)
                continue
            n_params = reducer.__code__.co_argcount
            if n_params != 2:
                # 真实报错（state.py:1934）：
                # "Invalid reducer signature. Expected (a, b) -> c. Got ..."
                raise ValueError(
                    f"Invalid reducer signature. Expected (a, b) -> c. "
                    f"Got {n_params}-arg {getattr(reducer, '__name__', reducer)}"
                )
            channels[key] = ReducerChannel(key, reducer)
        else:  # 普通类型注解 → 默认 LastValue
            channels[key] = LastValue(key)
    return channels


# ---------------------------------------------------------------
# 第 3 部分：演示
# ---------------------------------------------------------------
class AgentState(TypedDict):
    count: int
    logs: list
    msgs: Annotated[list, add_messages]  # 挂 reducer 的键


def main() -> None:
    banner("场景 1：schema → 通道（compile 的第一件事）")
    channels = build_channels(AgentState)
    for name, ch in channels.items():
        kind = type(ch).__name__
        extra = f" reducer={ch.reducer.__name__}" if isinstance(ch, ReducerChannel) else ""
        print(f"  {name:6s} -> {kind}{extra}")
    print("  → 声明（Annotated 元数据）决定运行时合并语义，引擎对通道种类无感知")

    banner("场景 2：LastValue 的铁律——一拍只收一个值")
    logs = channels["logs"]
    logs.update(["第 1 拍写入"])
    print(f"  一拍一值：logs={fmt_state({'logs': logs.get()})}")
    expect_error(
        "同一拍写两个值",
        lambda: logs.update(["A 节点写的", "B 节点写的"]),
        InvalidUpdateError,
    )
    print("  → 并发节点写同一 LastValue 键 = INVALID_CONCURRENT_GRAPH_UPDATE；")
    print("    解法只有一个：给键挂 reducer（报错信息里官方也在指这条路）")

    banner("场景 3：reducer 通道——同一拍 3 个值，折叠合并")
    msgs = channels["msgs"]
    ok = msgs.update([
        [{"id": "m1", "role": "user", "text": "问题"}],
        [{"id": "m2", "role": "ai", "text": "回答A"}],   # 同拍三个节点各交一份补丁
        [{"id": "m3", "role": "ai", "text": "回答B"}],
    ])
    print(f"  update 返回 {ok}，合并结果 {len(msgs.get())} 条：")
    for m in msgs.get():
        print(f"    {m['id']}: {m['text']}")

    banner("场景 4：add_messages 的两条语义——替换与追加")
    msgs.update([[{"id": "m2", "role": "ai", "text": "回答A(修正版)"}]])  # 同 id 替换
    for m in msgs.get():
        print(f"    {m['id']}: {m['text']}")
    print("  → m2 被原位替换而非重复追加；消息历史'只增不改'的表象，")
    print("    其实是 reducer 在键级别裁决的结果")

    banner("场景 5：错误左移——坏 reducer 在编译期就被拒收")
    class BadState(TypedDict):
        x: Annotated[list, lambda a, b, c: a + b + c]  # 三参：签名非法
    expect_error("三参 reducer", lambda: build_channels(BadState), ValueError)
    print("  → 校验发生在建图（compile）期而不是跑到一半才炸——")
    print("    真实源码同样在 state.py:1934 构造期拦截")


if __name__ == "__main__":
    main()
