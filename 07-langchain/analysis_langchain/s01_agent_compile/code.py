#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s01_agent_compile.py —— mini create_agent：一个 agent 如何被"编译"出来

LangChain 1.x 的招牌设计：**"做一个 agent"不是写一个 while 循环，
而是"声明一份配置，再把它编译成一张可运行的图"**。create_agent(model, tools)
内部组装 LangGraph 的 StateGraph——model/tools 两个节点、两条条件边成环——
最后 compile() 产出一个 Runnable（可 invoke/batch/stream 的统一可运行对象）。

本文件用纯标准库实现一个 mini 编译器，演示同一思想的最小骨架：

    AgentSpec（声明式配置：模型名 / 系统提示 / 工具清单）
        │  compile()：校验 → 装配 → 生成装配报告
        ▼
    +------------------------ CompiledAgent ------------------------+
    |  START ──▶ [model 节点] ──▶(发起工具调用?)──▶ [tools 节点] ──┐ |
    |               ▲                                            │ |
    |               └─────────────(工具结果回填)◀─────────────────┘ |
    |               └──(不带工具调用)──▶ END                        |
    +---------------------------------------------------------------+

  · 编译期：spec 只是数据。工具重名、模型未注册这类错误在这里 fail-fast，
    而不是留到第一次运行才炸——"把运行时错误提前到编译期"是声明式框架的
    第一红利。
  · 运行期：CompiledAgent.invoke() 沿环走：模型 → (要工具?) → 执行 → 回填
    → 再问模型 → …直到给出不带工具调用的最终回答，或触发迭代上限守卫。

运行：python code.py          （零依赖，离线；模型由脚本化 Mock 扮演）
对照真实源码（快照 80b7409，行号以源码为准）：
    libs/langchain_v1/langchain/agents/factory.py
        :882  def create_agent(model, tools, *, system_prompt, ...)   工厂入口
        :1249 graph: StateGraph[...]                                  图的组装起点
        :1623 graph.add_node("model", ...)                            模型节点
        :1627 graph.add_node("tools", tool_node)                      工具节点
        :1755 graph.add_edge(START, entry_node)                       入口边
        :1770 graph.add_conditional_edges("tools", ...)               条件边：tools→model
        :1790 graph.add_conditional_edges(loop_exit_node, ...)        条件边：model→tools
        :1926 return graph.compile(checkpointer=..., ...)             编译出口
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from mini_util import banner  # noqa: E402


# ---------------------------------------------------------------
# 第 1 部分：声明式配置 AgentSpec —— 只说"是什么"，不说"怎么跑"
# ---------------------------------------------------------------
@dataclass
class MiniTool:
    """mini 工具：真实框架里是 BaseTool（tools/base.py:433，本身就是 Runnable）。

    schema 会在编译期被反射生成并呈现给模型（s03 的主题），本课先用
    "手写 schema"占位，聚焦编译这件事本身。
    """

    name: str
    description: str
    run: Callable[[dict], str]


@dataclass
class AgentSpec:
    """声明式 agent 配置：对应 create_agent 的参数表（factory.py:882-901）。

    注意它和"命令式"的区别：这里没有任何流程代码，没有 while、没有 if——
    只有"用哪个模型、挂哪些工具、提示词是什么"这些**事实陈述**。
    流程（环怎么转）是编译器的事，不是配置的事。
    """

    model_name: str
    system_prompt: str
    tools: list[MiniTool] = field(default_factory=list)
    max_iterations: int = 4  # 迭代上限：真实框架里叫 recursion_limit（config.py:183，默认 25）


# ---------------------------------------------------------------
# 第 2 部分：脚本化 Mock 模型（离线）——按剧本逐轮返回
# ---------------------------------------------------------------
@dataclass
class MockReply:
    """一轮模型回复：content + 可选的工具调用请求。"""

    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)  # [{"name", "args", "id"}]


class MockModel:
    """脚本化模型：构造时传入回复剧本，每被调用一次弹出一轮。

    真实框架里模型是 BaseChatModel 子类（chat_models.py:284）；本课程全程
    用 Mock，把注意力留给 harness（框架）本身的机制。
    """

    def __init__(self, name: str, script: list[MockReply]) -> None:
        self.name = name
        self.script = list(script)
        self.calls = 0

    def invoke(self, messages: list[dict]) -> MockReply:
        self.calls += 1
        if not self.script:
            return MockReply(content="（剧本耗尽：模型表示无话可说）")
        return self.script.pop(0)


# ---------------------------------------------------------------
# 第 3 部分：编译器 —— 校验、装配、生成装配报告
# ---------------------------------------------------------------
class CompileError(Exception):
    """编译期错误：宁可在这里拒绝编译，也不把炸弹留给运行期。"""


@dataclass
class BuildReport:
    """装配报告：编译产物"长什么样"的白盒清单（教具化的 get_graph()）。"""

    nodes: list[str]
    edges: list[str]
    conditional_edges: list[str]
    tools: list[str]
    warnings: list[str]


class CompiledAgent:
    """编译产物：一个可 invoke 的 agent（对应 LangGraph 的 CompiledStateGraph）。

    关键认识：**编译产物是 Runnable**——create_agent 的返回值可以继续被
    `|` 组合（s02），也可以 stream（s09）。环在这里只是数据结构，
    invoke 只是沿环走。
    """

    def __init__(self, model: MockModel, tools: dict[str, MiniTool],
                 system_prompt: str, max_iterations: int,
                 report: BuildReport) -> None:
        self.model = model
        self.tools = tools
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.report = report

    def describe(self) -> str:
        r = self.report
        return (
            f"nodes={r.nodes}  edges={r.edges}  conditional={r.conditional_edges}\n"
            f"tools={r.tools}  warnings={r.warnings}"
        )

    def invoke(self, user_input: str) -> str:
        """沿环走一圈：模型 → (要工具?) → 执行 → 回填 → 再问模型。"""
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]
        for iteration in range(1, self.max_iterations + 1):
            reply = self.model.invoke(messages)
            if not reply.tool_calls:  # 不带工具调用 → 最终回答，出环
                print(f"  [环] 第 {iteration} 轮：模型给出最终回答，出环")
                return reply.content
            # 模型发起工具调用：逐个执行并回填 ToolMessage（配对 id 不变）
            for call in reply.tool_calls:
                tool = self.tools.get(call["name"])
                if tool is None:
                    observation = f"错误：工具 {call['name']} 不存在"
                else:
                    observation = tool.run(call.get("args", {}))
                print(f"  [环] 第 {iteration} 轮：执行 {call['name']}({call.get('args')}) → {observation}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": observation,
                })
        return "（迭代上限守卫触发：强制出环）"


def compile_agent(spec: AgentSpec, model_registry: dict[str, MockModel]) -> CompiledAgent:
    """mini 编译器：spec（数据）→ CompiledAgent（可运行对象）。

    对应 factory.py 的组装段：校验 schema（:482 _resolve_schemas 的精神）、
    注册节点（:1623/:1627）、连边（:1755/:1770/:1790）、compile（:1926）。
    """
    # ---- 编译期校验 1：模型必须在注册表里（对应 init_chat_model 按名解析）----
    if spec.model_name not in model_registry:
        raise CompileError(f"模型未注册: {spec.model_name}（已知: {sorted(model_registry)}）")

    # ---- 编译期校验 2：工具不可重名（模型按名字点名工具，重名即歧义）----
    names = [t.name for t in spec.tools]
    if len(names) != len(set(names)):
        dup = sorted({n for n in names if names.count(n) > 1})
        raise CompileError(f"工具重名: {dup}")

    # ---- 装配：节点 / 边 / 条件边。工具为空则 tools 节点不装（纯聊天图）----
    nodes = ["model"] + (["tools"] if spec.tools else [])
    conditional = (["model→tools?  tools→model"] if spec.tools else [])
    report = BuildReport(
        nodes=nodes,
        edges=["START→model"],
        conditional_edges=conditional,
        tools=names,
        warnings=[f"工具为空：退化为单节点链" for _ in [] if not spec.tools],
    )
    if not spec.tools:
        report.warnings.append("未挂任何工具：图中没有 tools 节点，也不会有环")

    tools_map = {t.name: t for t in spec.tools}
    return CompiledAgent(
        model=model_registry[spec.model_name],
        tools=tools_map,
        system_prompt=spec.system_prompt,
        max_iterations=spec.max_iterations,
        report=report,
    )


# ---------------------------------------------------------------
# 第 4 部分：演示
# ---------------------------------------------------------------
def main() -> None:
    weather_tool = MiniTool(
        name="get_weather",
        description="查询城市天气",
        run=lambda args: f"{args.get('city', '未知')}：晴，26°C",
    )

    banner("场景 1：声明 → 编译 → 打印装配报告", "spec 是数据，图是编译产物")
    registry = {"mock-gpt": MockModel("mock-gpt", script=[])}
    spec = AgentSpec(
        model_name="mock-gpt",
        system_prompt="你是天气助手。",
        tools=[weather_tool],
    )
    agent = compile_agent(spec, registry)
    print(agent.describe())

    banner("场景 2：invoke 走一圈环", "模型要点工具 → 执行 → 回填 → 再问")
    scripted = MockModel("mock-gpt", script=[
        MockReply(tool_calls=[{"name": "get_weather", "args": {"city": "北京"}, "id": "call_1"}]),
        MockReply(content="北京今天晴，26°C。"),
    ])
    agent2 = compile_agent(AgentSpec("mock-gpt", "你是天气助手。", [weather_tool]),
                           {"mock-gpt": scripted})
    answer = agent2.invoke("北京天气怎么样？")
    print(f"  最终回答: {answer}")
    print(f"  （模型共被调用 {scripted.calls} 次：一次要点工具，一次收尾）")

    banner("场景 3：编译期 fail-fast", "重名工具在 compile() 就报错，不留给运行期")
    try:
        compile_agent(AgentSpec("mock-gpt", "s", [weather_tool, weather_tool]), registry)
    except CompileError as e:
        print(f"  CompileError: {e}")

    banner("场景 4：迭代上限守卫", "模型永远只要工具时，环必须能被强制终止")
    loop_model = MockModel("mock-gpt", script=[
        MockReply(tool_calls=[{"name": "get_weather", "args": {"city": f"城市{i}"}, "id": f"c{i}"}])
        for i in range(10)
    ])
    agent3 = compile_agent(
        AgentSpec("mock-gpt", "你是天气助手。", [weather_tool], max_iterations=3),
        {"mock-gpt": loop_model},
    )
    print(f"  {agent3.invoke('把全国天气都查一遍')}")

    banner("场景 5：未注册模型", "编译期校验：宁可现在炸，不要运行时炸")
    try:
        compile_agent(AgentSpec("gpt-999", "s", []), registry)
    except CompileError as e:
        print(f"  CompileError: {e}")

    print("\n结论：agent = 声明式配置经编译器变成的图。")
    print("换配置 = 重新编译；查产物 = 看装配报告；防失控 = 编译期校验 + 迭代上限。")
    print("下一课把'图'先放一放，看支撑整座框架的统一协议：Runnable 与 LCEL 的 a|b。")


if __name__ == "__main__":
    main()
