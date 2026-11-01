#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s09_streaming.py —— streaming：token 流与事件流的双通道

流式的本质：**把"等完整答案"变成"看答案长出来"**。LangChain 的流式有两
条并行通道：

  · 数据通道（chunk 流）：AIMessageChunk 分片逐段到达，分片相加（__add__，
    messages/ai.py:642）恢复成完整 AIMessage——**分段到达，合并无损**。
  · 事件通道（生命周期事件）：on_chat_model_start → on_llm_new_token×N →
    on_llm_end，与 chunk 时间线交错但职责分离（回调体系，s02 的回调树）。

  invoke():  [────────── 一次性完整回复 ──────────]
  stream():  [c1][c2][c3]…[cN]   ← 数据通道：逐段
              │   │   │       └─ on_llm_end          ← 事件通道：交错
              └── on_llm_new_token …

两个真实工程要点：
  · 假流式（chat_models.py:735）：模型没实现 _stream 时，基类把整段 invoke
    包成单个 chunk 吐出——接口统一，体验降级但不崩。判定在 _should_stream(:549)。
  · agent 流式的坑：tool_calls 要到流的**末尾**才拼装完整——中途不能下判断，
    必须攒完整个流再做路由（本轮要不要执行工具）。

运行：python code.py          （零依赖，离线；模型由脚本化 Mock 扮演）
对照真实源码（快照 80b7409，行号以源码为准）：
    libs/core/langchain_core/language_models/chat_models.py
        :284  class BaseChatModel             :475 def invoke
        :549  def _should_stream              判定走不走真流式
        :727  def stream                      :735 假流式分支（整段 invoke 包单 chunk）
        :2255 def _stream                     第 3 层默认实现：抛 NotImplementedError
    libs/core/langchain_core/messages/ai.py
        :418  class AIMessageChunk            :446 content_blocks
        :642  def __add__                     分片合并（__add__ 重载）
    libs/core/langchain_core/runnables/base.py     :3844 RunnableSequence.stream
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from mini_util import EventLog, banner  # noqa: E402

# ---------------------------------------------------------------
# 第 1 部分：AIMessageChunk —— 分片可加（__add__ 合并）
# ---------------------------------------------------------------
@dataclass
class Chunk:
    """消息分片（AIMessageChunk，ai.py:418 的 mini 版）。"""

    content: str = ""
    tool_call: dict | None = None   # 完整 tool_call 通常出现在流末（真实是 tool_call_chunks 渐进拼装）

    def __add__(self, other: "Chunk") -> "Chunk":
        """分片合并（ai.py:642 __add__ 的 mini 版）：content 相加、tool_call 取先到者。"""
        return Chunk(content=self.content + other.content,
                     tool_call=self.tool_call if self.tool_call else other.tool_call)


def merge(chunks: list[Chunk]) -> Chunk:
    out = Chunk()
    for c in chunks:
        out = out + c
    return out


# ---------------------------------------------------------------
# 第 2 部分：流式模型 —— 数据通道 + 事件通道
# ---------------------------------------------------------------
class BaseStreamModel:
    """mini 基类：stream() 统一入口，_stream() 由子类按需实现。

    对应 BaseChatModel（chat_models.py:284）的三层结构：stream(:727) 是壳，
    _should_stream(:549) 判定，_stream(:2255) 是子类唯一必做（或可不做的）事。
    """

    name = "model"

    def _stream(self, messages: list[dict]):
        raise NotImplementedError  # 真实基类同样默认抛错（:2255）

    def _should_stream(self) -> bool:
        """mini 判定（:549 的简化）：子类没覆写 _stream 就别走真流式。"""
        return type(self)._stream is not BaseStreamModel._stream

    def invoke(self, messages: list[dict]) -> Chunk:
        """非流式调用：整段返回（:475 的 mini 版）。"""
        return merge(list(self._stream(messages))) if self._should_stream() else self.fallback_chunk()

    def fallback_chunk(self) -> Chunk:
        return Chunk(content="（此模型不支持流式）")

    def stream(self, messages: list[dict], events: EventLog | None = None):
        """统一入口：走不了真流式就假流式（:735 分支——整段 invoke 包成单 chunk）。"""
        if not self._should_stream():
            events and events.log("on_chat_model_start", model=self.name, mode="fake")
            whole = self.fallback_chunk()
            events and events.log("on_llm_new_token", tokens=1, mode="fake")
            events and events.log("on_llm_end", model=self.name)
            yield whole
            return
        events and events.log("on_chat_model_start", model=self.name, mode="real")
        for chunk in self._stream(messages):
            events and events.log("on_llm_new_token", token=chunk.content or "<tool_call>")
            yield chunk
        events and events.log("on_llm_end", model=self.name)


class StreamingMock(BaseStreamModel):
    """脚本化流式模型：把 Chunk 剧本逐段吐出。"""

    def __init__(self, name: str, script: list[list[Chunk]]) -> None:
        self.name = name
        self.script = list(script)

    def _stream(self, messages: list[dict]):
        return iter(self.script.pop(0) if self.script else [Chunk(content="（剧本耗尽）")])


class NoStreamMock(BaseStreamModel):
    """不实现 _stream 的模型——触发基类的假流式分支。"""

    def __init__(self, text: str) -> None:
        self.text = text
        self.name = "no-stream-model"

    def fallback_chunk(self) -> Chunk:
        return Chunk(content=self.text)


# ---------------------------------------------------------------
# 第 3 部分：agent 流式循环 —— 攒完流再做路由判断
# ---------------------------------------------------------------
def stream_agent_loop(model: StreamingMock, tools: dict, user_input: str,
                      max_rounds: int = 4) -> str:
    """流式 agent 环：每轮边吐 token 边攒，流末才判 tool_calls。"""
    messages = [{"role": "user", "content": user_input}]
    for round_ in range(1, max_rounds + 1):
        events = EventLog()
        chunks: list[Chunk] = []
        print(f"  ── 第 {round_} 轮（数据通道） ──")
        for chunk in model.stream(messages, events):
            chunks.append(chunk)
            if chunk.content:
                print(f"    token: {chunk.content!r}")
            if chunk.tool_call:
                print(f"    token: <流末拼出 tool_call: {chunk.tool_call['name']}>")
        merged = merge(chunks)
        events.dump("    ")
        if merged.tool_call:
            call = merged.tool_call
            observation = tools[call["name"]](call["args"])
            print(f"    [tool] 执行 {call['name']}({call['args']}) → {observation}")
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": observation})
            continue
        print(f"  最终回答: {merged.content}")
        return merged.content
    return "（轮数上限）"


# ---------------------------------------------------------------
# 演示
# ---------------------------------------------------------------
def main() -> None:
    banner("场景 1：token 流 + 事件流双通道", "数据逐段到达，事件交错记录")
    model = StreamingMock("mock-gpt", [[
        Chunk(content="北京"), Chunk(content="今天"), Chunk(content="晴"),
        Chunk(content="，"), Chunk(content="26°C"), Chunk(content="。"),
    ]])
    events = EventLog()
    for chunk in model.stream([{"role": "user", "content": "北京天气"}], events):
        print(f"  数据通道收到: {chunk.content!r}")
    print("  事件通道（同一时间线）：")
    events.dump("    ")

    banner("场景 2：分片合并无损", "sum(chunks) == invoke() —— 流式不变量")
    tokens = [Chunk(content="北京"), Chunk(content="今天"), Chunk(content="晴"),
              Chunk(content="，"), Chunk(content="26°C"), Chunk(content="。")]
    fresh = StreamingMock("mock-gpt", [list(tokens), list(tokens)])  # 同一副本给两种调用
    streamed = merge(list(fresh.stream([])))   # 弹出剧本第 1 份
    invoked = fresh.invoke([])                 # 弹出剧本第 2 份
    print(f"  流式合并结果: {streamed.content!r}")
    print(f"  一次性调用结果: {invoked.content!r}")
    print(f"  完全一致: {streamed.content == invoked.content and streamed.tool_call is None}")

    banner("场景 3：假流式", "没实现 _stream 的模型 → 整段 invoke 包成单 chunk（chat_models.py:735）")
    nostream = NoStreamMock("这是一段不支持流式的完整回答。")
    events2 = EventLog()
    pieces = list(nostream.stream([], events2))
    print(f"  chunk 数: {len(pieces)}（=1 即假流式）；内容: {pieces[0].content!r}")
    events2.dump("  ")

    banner("场景 4：agent 流式 + 多轮", "tool_calls 在流末才完整——攒完流才能路由")
    agent_model = StreamingMock("mock-gpt", [
        [Chunk(content="我查一下天气。"), Chunk(tool_call={"name": "get_weather", "args": {"city": "北京"}, "id": "c1"})],
        [Chunk(content="北京"), Chunk(content="晴，"), Chunk(content="26°C。")],
    ])
    stream_agent_loop(agent_model, {"get_weather": lambda a: f"{a['city']}：晴，26°C"}, "北京天气如何？")

    print("\n结论：流式 = 数据通道（chunk 相加无损）+ 事件通道（生命周期交错）。")
    print("接口统一意味着没有 _stream 也能 stream（假流式）；agent 流式的纪律是攒完流再做路由。")


if __name__ == "__main__":
    main()
