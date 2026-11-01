#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s07_structured_output.py —— 结构化输出：schema 进提示词、输出再校验、失败带原文重试

模型天然只会吐文本；程序需要的是**数据**。LangChain 把"文本 → 结构化"做成
三条互相咬合的机制：

    ① schema 进提示词：把"请只输出如下 JSON"的格式指令拼进 prompt
       （PydanticOutputParser.get_format_instructions，output_parsers/pydantic.py:95）
    ② 输出再校验：剥 markdown 围栏 → json.loads → 按字段校验
       （parse_json_markdown，utils/json.py:142；OutputParserException 失败时带原文）
    ③ 失败带原文重试：把解析错误 + 原始输出塞回消息再问模型——模型自己修自己
       （真实框架的 retry parser / fixed schema retry 同思路）

    ① prompt ──▶ 模型 ──▶ ② 解析+校验 ──▶ ✅ dict
                              │ ❌（错误 + 原文）
                              ▼
                        错误塞回消息 ──▶ 再问模型（最多 N 次）──▶ 仍失败 → 抛异常（带原文）

LangChain 1.x 的 agent 还有第二条路：**ToolStrategy**——把 schema 包装成一个
`final_answer` 工具，模型"调用工具"的那一刻 args 就已经是结构化数据
（agents/structured_output.py:196 ToolStrategy；解析 :77 _parse_with_schema），
甚至可要求强制工具调用（tool_choice）。

运行：python code.py          （零依赖，离线；模型由脚本化 Mock 扮演）
对照真实源码（快照 80b7409，行号以源码为准）：
    libs/core/langchain_core/output_parsers/pydantic.py
        :19  class PydanticOutputParser    先 JSON 解析，再按模型校验
        :95  def get_format_instructions   schema 拼 prompt 的最短实现
    libs/core/langchain_core/output_parsers/json.py
        :31  class JsonOutputParser        :93 def parse
    libs/core/langchain_core/utils/json.py         :142 parse_json_markdown（剥围栏）
    libs/core/langchain_core/exceptions.py         :15 OutputParserException（带 llm_output）
    libs/core/langchain_core/language_models/chat_models.py  :2385 with_structured_output
    libs/langchain_v1/langchain/agents/structured_output.py
        :77  def _parse_with_schema        按 schema 解析模型回复
        :196 class ToolStrategy            工具即 schema 的路线
    libs/langchain_v1/langchain/agents/factory.py  :888 response_format 参数
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from mini_util import banner, show  # noqa: E402

JSON_TYPE = {"str": "string", "int": "integer", "float": "number", "bool": "boolean"}


# ---------------------------------------------------------------
# 第 1 部分：mini schema —— 字段声明、格式指令、校验器
# ---------------------------------------------------------------
@dataclass
class Field:
    name: str
    type: str            # "str" | "int" | "float" | "bool"
    required: bool = True


@dataclass
class Schema:
    fields: list[Field]
    description: str = ""

    def shape(self) -> dict:
        """给模型看的形状（而不是真实 JSON Schema 的完整格式——教学从简）。"""
        return {f.name: JSON_TYPE[f.type] for f in self.fields}

    def get_format_instructions(self) -> str:
        """① schema 进提示词（pydantic.py:95 的最短实现）。

        真实实现把 Pydantic 模型的 model_json_schema() 拼进提示词；
        mini 版直接给字段形状——语义一致：**模型只认得文本化的 schema**。
        """
        return (
            f"请只输出一个 JSON 对象，不要输出任何其他文字。{self.description}\n"
            f"字段要求：{json.dumps(self.shape(), ensure_ascii=False)}\n"
            f"必填字段：{[f.name for f in self.fields if f.required]}"
        )

    def validate(self, obj: Any) -> list[str]:
        """② 校验：返回错误列表（空列表 = 通过）。"""
        errors: list[str] = []
        if not isinstance(obj, dict):
            return [f"期望 JSON 对象，得到 {type(obj).__name__}"]
        for f in self.fields:
            if f.name not in obj:
                if f.required:
                    errors.append(f"缺少必填字段 {f.name}")
                continue
            py_type = {"str": str, "int": int, "float": (int, float), "bool": bool}[f.type]
            if not isinstance(obj[f.name], py_type) or (f.type == "bool" and isinstance(obj[f.name], int)):
                errors.append(f"字段 {f.name} 类型应为 {f.type}，得到 {type(obj[f.name]).__name__}")
        return errors


# ---------------------------------------------------------------
# 第 2 部分：剥围栏解析 + 异常带原文
# ---------------------------------------------------------------
class OutputParserException(Exception):
    """解析失败（exceptions.py:15）：带 llm_output 原文，方便重试链把它塞回去。"""

    def __init__(self, msg: str, llm_output: str) -> None:
        super().__init__(msg)
        self.llm_output = llm_output


def parse_json_markdown(text: str) -> Any:
    """剥 markdown 代码围栏 + 解析 JSON（utils/json.py:142 的 mini 版）。"""
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    payload = fence.group(1) if fence else text
    try:
        return json.loads(payload)
    except json.JSONDecodeError as e:
        raise OutputParserException(f"Invalid json output: {e}", llm_output=text) from e


# ---------------------------------------------------------------
# ③ 重试链：模型 → 解析校验 → 失败带原文塞回 → 再问
# ---------------------------------------------------------------
def parse_with_retry(model, schema: Schema, question: str, max_retries: int = 2) -> dict:
    """结构化输出主循环：每次失败都把"错误 + 原文"作为反馈再问模型。"""
    messages: list[dict] = [{"role": "user", "content": question + "\n" + schema.get_format_instructions()}]
    for attempt in range(1, max_retries + 2):
        text = model(messages)
        print(f"  [attempt {attempt}] 模型输出: {text[:48]}{'...' if len(text) > 48 else ''}")
        try:
            obj = parse_json_markdown(text)
        except OutputParserException as e:
            feedback = f"你的上一条输出不是合法 JSON（错误：{e}）。原始输出：\n{e.llm_output}\n请修正后重新只输出 JSON。"
            messages.append({"role": "user", "content": feedback})
            continue
        errors = schema.validate(obj)
        if not errors:
            print(f"  [attempt {attempt}] 校验通过 ✓")
            return obj
        feedback = f"你的 JSON 没通过校验：{errors}。原始输出：\n{text}\n请修正后重新只输出 JSON。"
        messages.append({"role": "user", "content": feedback})
    raise OutputParserException(f"重试 {max_retries} 次后仍无法解析", llm_output=text)


# ---------------------------------------------------------------
# 第二条路：ToolStrategy —— 把 schema 包装成 final_answer 工具
# ---------------------------------------------------------------
@dataclass
class MockToolCallModel:
    """脚本化模型：直接"调用" final_answer 工具（args 即结构化数据）。"""

    calls: list[dict]

    def __call__(self, messages: list[dict]) -> dict:
        return self.calls.pop(0) if self.calls else {"name": "final_answer", "args": {}}


def parse_tool_strategy(call: dict, schema: Schema) -> dict:
    """ToolStrategy 的解析语义（structured_output.py:77 _parse_with_schema 的 mini 版）：
    模型调用 final_answer 工具的那一刻，args 已经是 JSON——只需按 schema 校验。
    """
    if call.get("name") != "final_answer":
        raise OutputParserException(f"模型没有调用 final_answer 工具（调了 {call.get('name')}）", llm_output=str(call))
    errors = schema.validate(call.get("args", {}))
    if errors:
        raise OutputParserException(f"tool args 校验失败: {errors}", llm_output=str(call))
    return call["args"]


# ---------------------------------------------------------------
# 演示
# ---------------------------------------------------------------
def main() -> None:
    ticket_schema = Schema(
        fields=[Field("category", "str"), Field("priority", "str"), Field("days_open", "int")],
        description="工单分类结果。",
    )

    banner("场景 1：schema 进提示词", "get_format_instructions 的渲染结果")
    print("  " + ticket_schema.get_format_instructions().replace("\n", "\n  "))

    banner("场景 2：坏 JSON → 带原文重试 → 成功", "剥围栏也救不了尾逗号，但模型能自己修")
    replies = [
        '好的！这是分类结果：```json\n{"category": "网络故障", "priority": "高", "days_open": 3,}\n```',  # 尾逗号
        '{"category": "网络故障", "priority": "高", "days_open": 3}',                                       # 修正后
    ]
    result = parse_with_retry(lambda msgs: replies.pop(0), ticket_schema, "对工单分类")
    show("结构化结果", result)

    banner("场景 3：schema 校验失败 → 重试", "JSON 合法但字段类型错了，同样要修")
    replies2 = [
        '{"category": "计费问题", "priority": "中", "days_open": "5"}',   # days_open 是字符串
        '{"category": "计费问题", "priority": "中", "days_open": 5}',
    ]
    result2 = parse_with_retry(lambda msgs: replies2.pop(0), ticket_schema, "再分类一个")
    show("结构化结果", result2)

    banner("场景 4：ToolStrategy 路线", "final_answer 工具的 args 即结构化数据")
    model = MockToolCallModel([
        {"name": "final_answer", "args": {"category": "账号问题", "priority": "低", "days_open": 12}},
    ])
    result3 = parse_tool_strategy(model([]), ticket_schema)
    show("工具 args 结果", result3)
    print("  ↑ 模型'调用工具'天然是 JSON：结构化输出借了工具调用的壳")

    banner("场景 5（边界）：重试用尽 → 异常带原文", "失败也要带着证据走")
    stubborn = ["我不是 JSON，我偏要用自然语言回答。"] * 3
    try:
        parse_with_retry(lambda msgs: stubborn.pop(0), ticket_schema, "顽固模型", max_retries=1)
    except OutputParserException as e:
        print(f"  OutputParserException: {e}")
        print(f"  llm_output 原文保留: {e.llm_output[:30]}...")

    print("\n结论：结构化输出 = schema 进 prompt + 输出再校验 + 失败带原文重试；")
    print("第二条路 ToolStrategy 借工具调用的壳拿原生 JSON。程序拿到的永远是校验过的数据。")


if __name__ == "__main__":
    main()
