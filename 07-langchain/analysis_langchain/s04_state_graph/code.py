#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s04_state_graph.py —— StateGraph 底座：节点、边与条件边

LangChain 1.x 的 agent 之所以是"编译产物"，是因为底下有 LangGraph 的
StateGraph（状态图）：**把控制流从代码搬进数据结构**——

    图 = 节点（node：吃 state、吐 state 增量）+ 边（edge：固定跳转）
         + 条件边（conditional edge：运行时由路由函数决定去哪）
    编译产物 = 沿边行走的状态机，state（状态字典）贯穿全程

s01 见过 agent 图的最终形态（model/tools 两节点两条件边）；本课把支撑它的
图引擎本身实现出来——这正是"声明式"三字的硬件层：

    START ──▶ [model] ──(route: 要工具?)──▶ [tools] ──▶ [model]   ← 环
                 │                                        │
                 └──(route: 不用了)──▶ END ◀──────────────┘   ← 出口

  · 节点是纯函数：state 进、增量 dict 出——**节点不改变历史，只提交补丁**。
  · 条件边是路由函数：读 state 返回下一个节点名——while/if 变成了数据。
  · 编译期校验：边的两端必须存在；运行期守卫：recursion_limit 防死环。

StateGraph 本体在 langgraph 包（独立仓库），LangChain 只是使用者
（factory.py:45 `from langgraph.graph.state import StateGraph`）——
但"怎么用"全部写在 factory.py 里，本课的对照锚点就用这些使用现场。

运行：python code.py          （零依赖，离线；模型由脚本化 Mock 扮演）
对照真实源码（快照 80b7409，行号以源码为准）：
    libs/langchain_v1/langchain/agents/factory.py（StateGraph 的使用现场）
        :45   from langgraph.graph.state import StateGraph    引擎来自 langgraph 包
        :1249 graph: StateGraph[...]                          建图起点
        :1623 graph.add_node("model", ...) / :1627 add_node("tools", ...)
        :1755 graph.add_edge(START, entry_node)               固定边
        :1770 graph.add_conditional_edges("tools", ...)       条件边：tools→model
        :1790 graph.add_conditional_edges(loop_exit_node,...) 条件边：model→tools
        :1926 return graph.compile(checkpointer=..., ...)     编译出口
    libs/langchain_v1/langchain/agents/middleware/types.py
        :349  class AgentState（messages 字段挂 add_messages reducer）
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from mini_util import banner  # noqa: E402

START, END = "__start__", "__end__"


# ---------------------------------------------------------------
# 第 1 部分：mini StateGraph —— 图是数据，不是代码
# ---------------------------------------------------------------
class GraphCompileError(Exception):
    """编译期错误：边的两端必须存在。"""


@dataclass
class _CondEdge:
    source: str
    router: Callable[[dict], str]
    destinations: list[str]


class StateGraph:
    """mini 状态图：nodes / edges / conditional_edges 三张表就是图的全部。"""

    def __init__(self) -> None:
        self.nodes: dict[str, Callable[[dict], dict]] = {}
        self.edges: dict[str, str] = {}               # 固定边：source → target
        self.cond_edges: dict[str, _CondEdge] = {}    # 条件边：source → 路由函数
        self.entry: str | None = None

    def add_node(self, name: str, fn: Callable[[dict], dict]) -> "StateGraph":
        if name in (START, END):
            raise GraphCompileError(f"节点名 {name} 是保留字")
        self.nodes[name] = fn
        return self

    def add_edge(self, source: str, target: str) -> "StateGraph":
        self.edges[source] = target
        return self

    def add_conditional_edges(self, source: str, router: Callable[[dict], str],
                              destinations: list[str]) -> "StateGraph":
        self.cond_edges[source] = _CondEdge(source, router, destinations)
        return self

    def set_entry_point(self, name: str) -> "StateGraph":
        self.entry = name
        return self

    def compile(self) -> "CompiledGraph":
        """编译期校验：所有边的端点必须已注册（fail-fast，同 s01 的纪律）。"""
        if self.entry is None:
            raise GraphCompileError("未设置入口节点（START）")
        for src, dst in self.edges.items():
            for endpoint in (src, dst):
                if endpoint not in (START, END) and endpoint not in self.nodes:
                    raise GraphCompileError(f"固定边引用了不存在的节点: {endpoint}")
        for cond in self.cond_edges.values():
            if cond.source not in self.nodes:
                raise GraphCompileError(f"条件边挂在不存在的节点上: {cond.source}")
            for dst in cond.destinations:
                if dst not in self.nodes and dst != END:
                    raise GraphCompileError(f"条件边目的地不存在: {dst}")
        return CompiledGraph(self)


@dataclass
class CompiledGraph:
    """编译产物：可 invoke 的状态机（真实对应 langgraph 的 CompiledStateGraph）。"""

    graph: StateGraph
    recursion_limit: int = 8  # mini 版把默认 25 调小，方便演示守卫触发

    def invoke(self, state: dict) -> dict:
        current: str = self.graph.entry
        path: list[str] = []
        steps = 0
        while current != END:
            steps += 1
            if steps > self.recursion_limit:
                raise RecursionLimitError(
                    f"recursion_limit={self.recursion_limit} 触发：图在 {path[-3:]} 处打转")
            path.append(current)
            patch = self.graph.nodes[current](state)  # 节点只提交增量补丁
            state = {**state, **patch}                # mini 合并策略：浅覆盖
            print(f"  [walk] {current} → patch={patch}")
            current = self.next_of(current, state)
        print(f"  [walk] 到达 END，路径: {' → '.join(path)}")
        return state

    def next_of(self, node: str, state: dict) -> str:
        """下一个节点：先看条件边（运行时路由），再看固定边。"""
        cond = self.graph.cond_edges.get(node)
        if cond is not None:
            target = cond.router(state)
            if target not in cond.destinations:
                raise GraphCompileError(f"路由返回 {target}，不在声明目的地 {cond.destinations} 内")
            return target
        if node in self.graph.edges:
            return self.graph.edges[node]
        return END  # 无边可走：自然出口（真实 langgraph 要求显式声明，此处宽容）


class RecursionLimitError(Exception):
    """运行期守卫：真实 langgraph 抛 GraphRecursionError。"""


# ---------------------------------------------------------------
# 第 2 部分：用 mini 引擎搭出 s01 的 agent 图（model/tools 环）
# ---------------------------------------------------------------
@dataclass
class ScriptedReply:
    content: str = ""
    tool_call: dict | None = None  # {"name","args","id"}


class ScriptedModel:
    def __init__(self, script: list[ScriptedReply]) -> None:
        self.script = list(script)

    def reply(self, messages: list[dict]) -> ScriptedReply:
        return self.script.pop(0) if self.script else ScriptedReply(content="（剧本耗尽）")


def build_react_graph(model: ScriptedModel, tools: dict[str, Callable[[dict], str]]) -> CompiledGraph:
    """两节点 + 两条件边 = ReAct 环（factory.py:1623/1627/1770/1790 的 mini 对应）。"""
    builder = StateGraph()

    def model_node(state: dict) -> dict:
        reply = model.reply(state["messages"])
        # mini 版返回"整个新列表"当补丁；真实框架在 AgentState.messages 字段上
        # 挂 add_messages reducer（middleware/types.py:349）——节点只返回**新增**
        # 的消息，由引擎按 id 追加/覆盖。语义细节在 s06 展开。
        if reply.tool_call:
            return {"messages": state["messages"] + [
                {"role": "assistant", "tool_call": reply.tool_call}]}
        return {"messages": state["messages"] + [{"role": "assistant", "content": reply.content}]}

    def tools_node(state: dict) -> dict:
        last = state["messages"][-1]
        call = last["tool_call"]
        observation = tools[call["name"]](call["args"])
        return {"messages": state["messages"] + [
            {"role": "tool", "tool_call_id": call["id"], "content": observation}]}

    def route_after_model(state: dict) -> str:
        """model → tools?（factory.py:1790 _make_model_to_tools_edge 的 mini 版）"""
        last = state["messages"][-1]
        return "tools" if last.get("tool_call") else END

    builder.add_node("model", model_node)
    builder.add_node("tools", tools_node)
    builder.set_entry_point("model")
    # 环的两条边：tools 恒回 model（:1770），model 条件去 tools 或 END（:1790）
    builder.add_edge("tools", "model")
    builder.add_conditional_edges("model", route_after_model, ["tools", END])
    return builder.compile()


# ---------------------------------------------------------------
# 第 3 部分：演示
# ---------------------------------------------------------------
def main() -> None:
    banner("场景 1：线性图", "节点是纯函数：state 进、增量补丁出")
    g = StateGraph()
    g.add_node("clean", lambda s: {"text": s["text"].strip()})
    g.add_node("upper", lambda s: {"text": s["text"].upper()})
    g.set_entry_point("clean")
    g.add_edge("clean", "upper")
    out = g.compile().invoke({"text": "  hello graph  "})
    print(f"  最终 state: {out}")

    banner("场景 2：条件边", "路由函数读 state 决定去哪——if/else 变成了数据")
    g2 = StateGraph()
    g2.add_node("classify", lambda s: {"label": "长文" if len(s["text"]) > 10 else "短文"})
    g2.add_node("deep_read", lambda s: {"plan": "逐段精读"})
    g2.add_node("quick_read", lambda s: {"plan": "扫一眼"})
    g2.set_entry_point("classify")
    g2.add_conditional_edges(
        "classify",
        lambda s: "deep_read" if s["label"] == "长文" else "quick_read",
        ["deep_read", "quick_read"],
    )
    for text in ("这是一条长长长长长长的输入文本", "短输入"):
        print(f"  输入={text!r}")
        g2.compile().invoke({"text": text})

    banner("场景 3：ReAct 环", "两节点两条件边——s01 的 agent 图这次跑在图引擎上")
    model = ScriptedModel([
        ScriptedReply(tool_call={"name": "get_weather", "args": {"city": "北京"}, "id": "c1"}),
        ScriptedReply(content="北京晴，26°C。"),
    ])
    agent = build_react_graph(model, {"get_weather": lambda a: f"{a['city']}：晴，26°C"})
    final = agent.invoke({"messages": [{"role": "user", "content": "北京天气?"}]})
    print(f"  最终回答: {final['messages'][-1]['content']}")
    print(f"  （注意 model 节点返回的是增量补丁，引擎负责合并——消息历史只增不改）")

    banner("场景 4（边界）：编译期校验", "边指向不存在的节点 → 编译即报错")
    bad = StateGraph()
    bad.add_node("a", lambda s: {})
    bad.set_entry_point("a")
    bad.add_edge("a", "不存在的节点")
    try:
        bad.compile()
    except GraphCompileError as e:
        print(f"  GraphCompileError: {e}")

    banner("场景 5（边界）：recursion_limit 守卫", "永不收敛的环被强制打断")
    loop = StateGraph()
    loop.add_node("a", lambda s: {"n": s.get("n", 0) + 1})
    loop.add_node("b", lambda s: {})
    loop.set_entry_point("a")
    loop.add_edge("a", "b")
    loop.add_edge("b", "a")  # 死环
    try:
        loop.compile().invoke({"n": 0})
    except RecursionLimitError as e:
        print(f"  RecursionLimitError: {e}")

    print("\n结论：图引擎 = 三张表（节点/固定边/条件边）+ 一个行走器。")
    print("控制流从代码搬进数据后，'改流程'变成'改声明'——中间件（s05）才有地方织入。")


if __name__ == "__main__":
    main()
