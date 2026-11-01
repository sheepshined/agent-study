#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s03_tool_system.py —— @tool 装饰器与工具调用循环

工具（Tool）是 agent 的手和脚：**带参数 schema（模式）的可调用函数，
模型可以按名字点名调用**。LangChain 的招牌手法是 `@tool` 装饰器——
普通函数只要带上类型注解和 docstring，schema 就被自动反射出来：

    @tool
    def get_weather(city: str) -> str:
        '''查询城市天气。'''          ← docstring 成为工具描述
        ...

反射链路（真实代码 tools/convert.py:89 → tools/base.py:263）：
    函数签名 inspect.signature → 参数注解 → JSON Schema → 呈现给模型
被过滤的参数（FILTERED_ARGS，tools/base.py:74：run_manager/callbacks）
和运行时注入参数（InjectedToolArg，tools/base.py:1726）**模型永远看不见**。

工具调用循环（tool calling loop）三拍闭合：
    ① 模型回复带 tool_calls（AIMessage.tool_calls 是一等字段，messages/ai.py:170）
    ② 应用执行工具，把结果包成 ToolMessage 回填（tool_call_id 与请求配对，messages/tool.py:67）
    ③ 带着工具结果再问模型，直到给出不含 tool_calls 的最终回答

本文件用纯标准库实现 mini 版：装饰器反射 schema + 消息类 + 闭合循环，
并演示三条边界路径（未知工具 / 注入参数 / return_direct 短路）。

运行：python code.py          （零依赖，离线；模型由脚本化 Mock 扮演）
对照真实源码（快照 80b7409，行号以源码为准）：
    libs/core/langchain_core/tools/convert.py
        :89  def tool(...)                装饰器实现（:29/:43/:59/:74 为四种重载）
        :294 def _tool_factory(...)       三种用法汇入同一工厂
    libs/core/langchain_core/tools/base.py
        :74  FILTERED_ARGS                被剔除出 schema 的参数名
        :263 def create_schema_from_function   签名 → schema 的钥匙
        :433 class BaseTool(RunnableSerializable, ...)   工具本身也是 Runnable
        :757 invoke → :778 _parse_input → :909 _run      三段式执行
        :1726 class InjectedToolArg       运行时注入、模型不可见
    libs/core/langchain_core/tools/structured.py  :93 StructuredTool
    libs/core/langchain_core/messages/ai.py        :160 AIMessage  :170 tool_calls
    libs/core/langchain_core/messages/tool.py      :26 ToolMessage  :67 tool_call_id
                                                   :81 status       :206 ToolCall
"""

from __future__ import annotations

import inspect
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, get_type_hints

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from mini_util import banner, show  # noqa: E402

# ---------------------------------------------------------------
# 第 1 部分：消息类（mini 版消息体系）
# ---------------------------------------------------------------
@dataclass
class ToolCall:
    """工具调用请求（tool.py:206 的 TypedDict）：name/args/id 三键。"""

    name: str
    args: dict
    id: str


@dataclass
class Message:
    role: str                       # "user" / "assistant" / "tool"
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)  # ai.py:170 一等字段
    tool_call_id: str | None = None  # tool.py:67 与请求配对的钥匙
    status: str = "success"          # tool.py:81 "success" | "error"

    def brief(self) -> str:
        if self.role == "assistant" and self.tool_calls:
            calls = ", ".join(f"{c.name}({c.args})" for c in self.tool_calls)
            return f"assistant[要点工具: {calls}]"
        return f"{self.role}: {self.content}"


# ---------------------------------------------------------------
# 第 2 部分：@tool 装饰器 —— 签名反射出 schema
# ---------------------------------------------------------------
PY_TO_JSON_TYPE = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array"}


class MiniTool:
    """mini 工具对象（StructuredTool，structured.py:93 的影子）。"""

    def __init__(self, name: str, description: str, schema: dict,
                 func: Callable, return_direct: bool = False) -> None:
        self.name = name
        self.description = description
        self.schema = schema
        self.func = func
        self.return_direct = return_direct  # True 时结果直接当最终回答（短路出环）

    def invoke(self, args: dict) -> str:
        """三段式执行的极简版：BaseTool.invoke(:757) → _parse_input(:778) → _run(:909)。"""
        return self.func(**args)

    def as_provider_dict(self) -> dict:
        """呈现给模型的形态：name/description/parameters（发给厂商 API 的 tools 字段）。"""
        return {"name": self.name, "description": self.description, "parameters": self.schema}


def tool(func: Callable | None = None, *, return_direct: bool = False):
    """mini @tool：裸装饰用法（convert.py:89 的极简版）。

    schema 反射的钥匙（base.py:263 create_schema_from_function 的思路）：
    inspect.signature 拿签名 → 类型注解映射 JSON 类型 → docstring 当描述。
    """
    def decorate(fn: Callable) -> MiniTool:
        sig = inspect.signature(fn)
        hints = get_type_hints(fn)
        properties: dict[str, Any] = {}
        required: list[str] = []
        for pname, param in sig.parameters.items():
            if pname in ("run_manager", "callbacks"):  # FILTERED_ARGS（base.py:74）
                continue
            if getattr(hints.get(pname, None), "__name__", "") == "Injected":
                continue  # InjectedToolArg（base.py:1726）：运行时注入，模型不可见
            ann = hints.get(pname, str)
            properties[pname] = {"type": PY_TO_JSON_TYPE.get(ann, "string")}
            if param.default is inspect.Parameter.empty:
                required.append(pname)
        description = (fn.__doc__ or "").strip() or "（无描述）"
        return MiniTool(
            name=fn.__name__,
            description=description,
            schema={"type": "object", "properties": properties, "required": required},
            func=fn,
            return_direct=return_direct,
        )

    return decorate(func) if func is not None else decorate


# 运行时注入参数的标记（base.py:1726 InjectedToolArg 的 mini 影子）
class Injected:
    """标注某参数由运行时注入（如当前用户身份），不进 schema、模型不可见。"""


# ---------------------------------------------------------------
# 第 3 部分：脚本化 Mock 模型 + 工具调用循环
# ---------------------------------------------------------------
class MockModel:
    """按剧本回复：每轮要么要点工具，要么给最终回答。"""

    def __init__(self, script: list[Message]) -> None:
        self.script = list(script)

    def invoke(self, messages: list[Message], tools: list[dict]) -> Message:
        if not self.script:
            return Message(role="assistant", content="（剧本耗尽）")
        return self.script.pop(0)


def render_tools_prompt(tools: list[MiniTool]) -> str:
    """把工具 schema 渲染进系统提示（真实框架里走厂商 API 的 tools 参数）。"""
    return "可用工具：\n" + "\n".join(json.dumps(t.as_provider_dict(), ensure_ascii=False) for t in tools)


def run_tool_loop(model: MockModel, tools: list[MiniTool], user_input: str,
                  max_steps: int = 5) -> str:
    """闭合循环：模型 → 执行 → 回填 → 再问（agent 的心脏，就这几行）。"""
    registry = {t.name: t for t in tools}
    messages = [Message(role="user", content=user_input)]
    for step in range(1, max_steps + 1):
        reply = model.invoke(messages, [t.as_provider_dict() for t in tools])
        print(f"  [step {step}] 模型回复: {reply.brief()}")
        if not reply.tool_calls:
            return reply.content  # 不带 tool_calls → 最终回答
        for call in reply.tool_calls:
            t = registry.get(call.name)
            if t is None:
                # 未知工具也要有配对回执：status="error" 的 ToolMessage，循环不崩
                messages.append(Message(role="tool", tool_call_id=call.id,
                                        content=f"未知工具: {call.name}", status="error"))
                continue
            try:
                observation = t.invoke(call.args)
            except Exception as e:  # 工具内部异常同样包装成 error 回执
                observation = f"执行失败: {e}"
                messages.append(Message(role="tool", tool_call_id=call.id,
                                        content=observation, status="error"))
                continue
            messages.append(Message(role="tool", tool_call_id=call.id, content=observation))
            print(f"  [step {step}] 回填 tool_call_id={call.id}: {observation}")
    return "（步数上限，强制出环）"


# ---------------------------------------------------------------
# 第 4 部分：演示
# ---------------------------------------------------------------
@tool
def get_weather(city: str, days: int = 1) -> str:
    """查询指定城市未来几天的天气。"""
    return f"{city} 未来 {days} 天：晴转多云，22~28°C"


@tool
def read_file(path: str, user: Injected) -> str:
    """读取文件内容（user 参数由运行时注入，模型看不见）。"""
    return f"（以 {user} 身份读了 {path}）"


@tool(return_direct=True)
def shout(text: str) -> str:
    """把文本大写后直接作为最终回答（return_direct 短路）。"""
    return text.upper()


def main() -> None:
    banner("场景 1：@tool 反射", "函数签名 → JSON Schema（模型看见什么）")
    show("get_weather.schema", get_weather.schema)
    show("read_file.schema", read_file.schema)
    print("  ↑ user 参数没进 schema：InjectedToolArg 运行时注入，模型不可见")
    print(f"  ↑ days 有默认值 → 不在 required 里（required={get_weather.schema['required']}）")

    banner("场景 2：工具调用循环闭合", "tool_calls → 执行 → ToolMessage(tool_call_id) 回填 → 再问")
    model = MockModel([
        Message(role="assistant",
                tool_calls=[ToolCall("get_weather", {"city": "上海", "days": 3}, "call_a")]),
        Message(role="assistant", content="上海未来 3 天：晴转多云，22~28°C，适合出行。"),
    ])
    answer = run_tool_loop(model, [get_weather], "上海这三天天气如何？")
    print(f"  最终回答: {answer}")

    banner("场景 3（边界）：未知工具", "循环不崩：回执 status=error，模型看到错误后收尾")
    model2 = MockModel([
        Message(role="assistant", tool_calls=[ToolCall("book_flight", {"to": "月球"}, "call_b")]),
        Message(role="assistant", content="抱歉，我没有订票工具，无法完成该请求。"),
    ])
    print(f"  最终回答: {run_tool_loop(model2, [get_weather], '帮我订去月球的票')}")

    banner("场景 4（边界）：工具内部抛错", "异常被包装成 error 回执而不是打断循环")
    @tool
    def divide(a: int, b: int) -> str:
        """两数相除。"""
        return str(a / b)

    model3 = MockModel([
        Message(role="assistant", tool_calls=[ToolCall("divide", {"a": 1, "b": 0}, "call_c")]),
        Message(role="assistant", content="除数不能为零，请换一组数字。"),
    ])
    print(f"  最终回答: {run_tool_loop(model3, [divide], '1 除以 0 等于几？')}")

    banner("场景 5：return_direct 短路", "工具结果直接当最终回答，省一轮模型调用")
    print(f"  shout.invoke → {shout.invoke({'text': 'hello langchain'})}（return_direct={shout.return_direct}）")

    print("\n结论：@tool = 签名反射 + docstring 描述；循环 = tool_calls 与 ToolMessage 按 id 配对闭合。")
    print("模型看得见的只有 schema——注入参数与框架参数永远不进上下文。")
    print("下一课把'环'正式化：mini StateGraph 图引擎，节点、边与条件边。")


if __name__ == "__main__":
    main()
