# -*- coding: utf-8 -*-
"""
shared/mini_util.py —— 课程共享小工具（对应 codex-rs 里的 utils/、async-utils/ 这类
"被所有 crate 引用的小件"）。各课 `from shared.mini_util import ...`（从课程根跑）
或 `sys.path` 注入后独立运行。

约定：
- 本文件与全部课程代码只用 Python 标准库（零 pip 依赖）；
- Rust ↔ Python 对应物一律在注释里标注（如 tokio mpsc ↔ asyncio.Queue）；
- 模型一律脚本化 Mock（离线可跑）。
"""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional


def force_utf8_stdout() -> None:
    """Windows 控制台默认 GBK，中文输出可能炸掉 UnicodeEncodeError。
    统一重配为 UTF-8（Git Bash / run.bat 的 chcp 65001 都吃 UTF-8）。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


@dataclass
class TurnInput:
    """一次喂给模型的输入。

    对应 codex-rs/core/src/session/turn_input.rs 的 `TurnInput`：
    Rust 侧是 tagged enum（Text / Image / LocalImage…），
    Python 教学版退化为 kind + text 两个字段（serde tagged enum ↔ kind 判别字段）。
    """

    kind: str = "text"  # "text" | "interupt"（用户插话/steering）| ...
    text: str = ""


@dataclass
class ToolCall:
    """模型发出的一次工具调用（OpenAI 风格 function call 的最小面）。

    对应 codex-rs/protocol 里的 `ResponseItem::FunctionCall`：id/name/arguments。
    """

    id: str
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class TurnOutput:
    """模型一次采样的产出：要么是文本（终稿或中间叙述），要么是工具调用。

    对应 codex 采样循环里的 `SamplingRequestResult`：
    真实实现是流式 delta 组装（run_sampling_request，turn.rs），这里整块给出。
    """

    text: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)


class MockModel:
    """脚本化模型：按剧本逐幕返回。

    剧本 = list[TurnOutput | Callable[[List[Any]], TurnOutput]]。
    真实模型在 codex-rs/model-provider/（OpenAI / Bedrock / Ollama … 多 provider），
    课程里永远用 Mock：**离线、确定、可断言**——教学关心的是 harness 行为，
    不是模型的聪明程度。

    call_histories 记录每次采样的上下文长度，供课程演示"上下文随回合增长"。
    """

    def __init__(self, script: List[Any], delay_ms: float = 0.0):
        self.script = list(script)
        self.delay_ms = delay_ms  # 每次采样的虚拟网络耗时（教学用，让出事件循环）
        self.cursor = 0
        self.sample_count = 0
        self.call_histories: List[int] = []

    async def sample(self, context: List[Any]) -> TurnOutput:
        """一次采样：整块返回（真实实现是 SSE 流式，见 s01 注释）。"""
        self.sample_count += 1
        self.call_histories.append(len(context))
        await asyncio.sleep(self.delay_ms / 1000.0)  # tokio::time::sleep ↔ asyncio.sleep
        if self.cursor >= len(self.script):
            # 剧本演完还来要：教学场景里这属于 harness bug（或忘了回填工具结果）
            raise RuntimeError("MockModel 剧本耗尽：harness 是否漏了工具结果回填？")
        item = self.script[self.cursor]
        self.cursor += 1
        if callable(item):
            return item(context)
        return item


def logged(name: str) -> Callable[[str], None]:
    """返回一个带课程名前缀的打印函数，输出对齐更像一段日志。"""
    def _log(line: str) -> None:
        print(f"  [{name}] {line}")
    return _log


class Clock:
    """极简单调时钟：教学版替代 tokio::time::Instant，可手推进，方便断言耗时。"""

    def __init__(self) -> None:
        self._t = 0.0

    def now(self) -> float:
        return self._t

    def advance(self, ms: float) -> None:
        self._t += ms / 1000.0


async def sleep_ms(ms: float) -> None:
    """asyncio.sleep 的语义化包装。tokio::time::sleep ↔ asyncio.sleep。"""
    await asyncio.sleep(ms / 1000.0)


def banner(title: str) -> None:
    print(f"\n== {title} ==")


def _selfcheck() -> None:
    """`python mini_util.py` 自检：不依赖任何课程代码。"""
    force_utf8_stdout()
    m = MockModel([TurnOutput(text="hi"), TurnOutput(tool_calls=[ToolCall("1", "ls")])])
    out1 = asyncio.run(m.sample([]))
    out2 = asyncio.run(m.sample([]))
    assert out1.text == "hi" and out2.tool_calls[0].name == "ls"
    try:
        asyncio.run(m.sample([]))
    except RuntimeError:
        print("mini_util selfcheck OK：剧本耗尽按预期抛错")
        return
    raise AssertionError("剧本耗尽应当抛错")


if __name__ == "__main__":
    _selfcheck()
