#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s10_classic_vs_v1.py —— 两个时代的 agent：langchain-classic 怎么包，v1 凭什么取代

仓库地图里最重要的认知（见课程 README）：pip install langchain 装的是
libs/langchain_v1（pyproject name = "langchain"）；0.x 那套 AgentExecutor /
LLMChain / ConversationBufferMemory 整体搬进了 libs/langchain（pyproject
name = "langchain-classic"）——**包名没变、体系已换代**，这就是网上 0.x
教程对不上 1.x 现状的根源。

    0.x（classic 命令式）                  1.x（v1 声明式编译）
    ┌──────────────────────────┐          ┌──────────────────────────────┐
    │ AgentExecutor(Chain)     │          │ create_agent(model, tools,   │
    │   自己持有 while 循环     │          │   middleware, checkpointer)  │
    │ memory.save_context(...) │   ───▶   │   └─ 编译成 StateGraph       │
    │ LLMChain 手工串接         │          │   └─ compile() → Runnable    │
    │ Agent._plan 决定下一步    │          │ 记忆=checkpointer 拦截=中间件 │
    └──────────────────────────┘          └──────────────────────────────┘

本课把同一个"天气问答"任务用两种风格各实现一遍，逐项对照迁移差异；
最后用 v1 mini 总装前九课的全部机制（工具 / 中间件 / 检查点 / 结构化输出 /
检索工具）跑一个收官场景。

运行：python code.py          （零依赖，离线；模型由脚本化 Mock 扮演）
对照真实源码（快照 80b7409，行号以源码为准）：
    libs/langchain/pyproject.toml                    :6  name = "langchain-classic"
    libs/langchain_v1/pyproject.toml                 :6  name = "langchain"
    libs/langchain/langchain_classic/
        chains/base.py                               :52 class Chain(RunnableSerializable, ABC)
        agents/agent.py                              :1012 class AgentExecutor(Chain)   :1570 _call
        memory/buffer.py                             :24 class ConversationBufferMemory
        agents/__init__.py                           :46/:56 导出 create_react_agent / create_tool_calling_agent
    libs/langchain_v1/langchain/agents/__init__.py   :3  from langchain.agents.factory import create_agent
    libs/langchain_v1/langchain/agents/factory.py    :882 def create_agent  :1926 graph.compile
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from mini_util import banner  # noqa: E402


# ===============================================================
# 第 1 部分：classic 风格（0.x 命令式）—— 每个零件都手工持有
# ===============================================================
class ConversationBufferMemory:
    """mini ConversationBufferMemory（memory/buffer.py:24 的影子）：
    记忆是独立对象，把历史攒成字符串，prompt 自己负责留位置。"""

    def __init__(self) -> None:
        self.buffer: list[str] = []

    def save_context(self, human: str, ai: str) -> None:
        self.buffer += [f"Human: {human}", f"AI: {ai}"]

    def load_memory_string(self) -> str:
        return "\n".join(self.buffer)


class LLMChain:
    """mini LLMChain（0.x chains 的代表）：prompt 模板 + 模型调用，手工串。

    真实 Chain 继承 RunnableSerializable（chains/base.py:52），但串接方式
    是"类套类"，不是 v1 的 `|` 运算符。
    """

    def __init__(self, mock_model, template: str) -> None:
        self.mock_model = mock_model
        self.template = template

    def run(self, **variables: str) -> str:
        prompt = self.template.format(**variables)
        return self.mock_model(prompt)


class AgentExecutor:
    """mini AgentExecutor（agents/agent.py:1012 的影子）：类自己持有 while 循环。

    0.x 的 agent 由两部分组成：Agent（决定下一步）+ AgentExecutor（驱动循环，
    _call 在 agent.py:1570）。想定制循环行为？子类化并覆写方法——命令式定制。
    """

    def __init__(self, chain: LLMChain, tools: dict, memory: ConversationBufferMemory,
                 plan) -> None:
        self.chain = chain
        self.tools = tools
        self.memory = memory
        self.plan = plan  # Agent 的"思考"：脚本化决策函数（真实是 LLM 输出解析）

    def run(self, question: str) -> str:
        history = self.memory.load_memory_string()
        for _ in range(5):
            action = self.plan(question, history, self.tools)
            if action[0] == "tool":
                _, name, args = action
                observation = self.tools[name](**args)
                print(f"  [classic] 工具 {name}({args}) → {observation}")
                history = f"{history}\nObservation: {observation}".strip()
                continue
            answer = self.chain.run(question=question, history=history, observation=action[1])
            self.memory.save_context(question, answer)  # 记忆要手动存
            print(f"  [classic] 最终回答: {answer}")
            return answer
        return "（AgentExecutor 循环上限）"


# ===============================================================
# 第 2 部分：v1 风格（声明式编译）—— spec 进、图出
# ===============================================================
def create_agent_mini(script: list, tools: dict, system_prompt: str,
                      middlewares: list | None = None, checkpointer: dict | None = None):
    """mini create_agent（factory.py:882 的影子）：声明式参数 → 编译 → 可运行对象。

    对比 AgentExecutor：没有手写 while——循环是编译进图的（s04）；
    记忆不靠 memory 对象而靠 checkpointer（s06）；拦截不靠子类化而靠中间件（s05）。
    final_answer 是保留工具名：模型"调用"它的 args 即结构化结论（s07 ToolStrategy）。
    """
    middlewares = middlewares or []
    checkpointer = checkpointer if checkpointer is not None else {}
    for name in tools:
        assert callable(tools[name]), f"工具 {name} 必须可调用"

    def invoke(user_input: str, thread_id: str = "t1") -> str:
        history = checkpointer.get(thread_id, [])
        messages = history + [f"user: {user_input}"]
        for m in middlewares:  # 拦截链（s05）：进"模型"之前
            messages = m(messages)
        for round_ in range(1, 6):
            reply = script.pop(0) if script else "（剧本耗尽）"
            if isinstance(reply, dict) and reply.get("name") == "final_answer":
                print(f"  [v1] 结构化输出（final_answer args）: {reply['args']}")
                return reply["args"]["answer"]
            if isinstance(reply, dict):  # 模型节点 → 条件边 → 工具节点
                observation = tools[reply["name"]](**reply["args"])
                print(f"  [v1] 节点 tools 执行 {reply['name']}({reply['args']}) → {observation}")
                messages.append(f"observation: {observation}")
                continue
            print(f"  [v1] 节点 model 给出最终回答: {reply}")
            checkpointer.setdefault(thread_id, []).append(f"user: {user_input}")
            checkpointer.setdefault(thread_id, []).append(f"assistant: {reply}")
            return reply
        return "（recursion_limit）"

    return invoke


# ===============================================================
# 第 3 部分：演示
# ===============================================================
def pii_mask(messages: list[str]) -> list[str]:
    """中间件（s05）：进"模型"前脱敏。"""
    return [m.replace("138-0000-0000", "***MASKED***") for m in messages]


def main() -> None:
    weather_tools = {"get_weather": lambda city: f"{city}：晴，26°C"}

    banner("场景 1：classic 风格跑通", "命令式：executor 持有循环、memory 手动存")

    def classic_plan(question: str, history: str, tools: dict):
        """脚本化 Agent：本轮还没观察结果就先查天气，有结果就收尾。"""
        if "Observation" not in history:
            return ("tool", "get_weather", {"city": "上海" if "上海" in question else "北京"})
        return ("finish", "（按 Observation 回答）")

    def weather_model(prompt: str) -> str:
        city = "上海" if "上海" in prompt else "北京"
        return f"{city}今天晴，26°C。"

    memory = ConversationBufferMemory()
    classic = AgentExecutor(
        chain=LLMChain(weather_model, "{history}\n{observation}\n回答：{question}"),
        tools=weather_tools,
        memory=memory,
        plan=classic_plan,
    )
    classic.run("北京天气怎么样？")
    classic.run("那上海呢？")  # 第二问：memory 里已有一问一答，历史被拼进 prompt
    print(f"  memory.buffer 现状: {memory.buffer}")

    banner("场景 2：v1 风格跑同一问题", "声明式：spec 编译成图，环在编译产物里")
    checkpointer: dict = {}
    agent_v1 = create_agent_mini(
        script=[{"name": "get_weather", "args": {"city": "北京"}}, "北京今天晴，26°C。"],
        tools=weather_tools,
        system_prompt="你是天气助手",
        checkpointer=checkpointer,
    )
    agent_v1("北京天气怎么样？")
    print(f"  checkpointer['t1'] 现状: {checkpointer.get('t1')}")
    print("  对照：memory.save_context（手动存）→ checkpointer 自动快照；")
    print("        AgentExecutor.run（循环在类里）→ 环在编译产物里")

    banner("场景 3：迁移对照清单", "同一能力、两个时代的写法")
    rows = [
        ("编排", "AgentExecutor(Chain) 自己写 while（agent.py:1012/:1570）", "create_agent 编译成 StateGraph（factory.py:1249/:1926）"),
        ("串接", "LLMChain 一个个手工连（chains/base.py:52）", "LCEL：prompt | model | parser（base.py:688）"),
        ("记忆", "ConversationBufferMemory 拼字符串（buffer.py:24）", "checkpointer 按 thread_id 快照（factory.py:891）"),
        ("定制", "子类化 Agent / Executor 覆写方法", "middleware 钩子织入图（types.py:455/503）"),
        ("工具", "create_tool_calling_agent（classic agents/__init__.py:56）", "tools 参数直接挂 BaseTool（factory.py:883）"),
        ("入口", "from langchain import ...（0.x 教程写法）", "from langchain.agents import create_agent（v1 agents/__init__.py:3）"),
    ]
    for name, old, new in rows:
        print(f"  {name}：{old}")
        print(f"      ↳ {new}")

    banner("场景 4：收官总装", "工具 + 中间件 + 检查点 + 检索 + 结构化输出，一个不缺")
    store = {
        "chunks": [
            "报销标准：市内交通实报实销，每日餐补 100 元。",
            "agent 的状态快照由 checkpointer 按 thread_id 保存。",
        ]
    }

    def search_docs(query: str) -> str:  # s08：检索工具（关键词版模拟）
        hits = [c for c in store["chunks"] if any(w in c for w in query.split())]
        return "\n".join(f"[内部文档·片段{i+1}] {h}" for i, h in enumerate(hits)) or "（无相关资料）"

    def no_deploy(messages: list[str]) -> list[str]:  # s05：拦截链再来一层
        return [m for m in messages if "deploy" not in m] or ["（本会话禁止 deploy）"]

    assembled = create_agent_mini(
        script=[
            {"name": "search_docs", "args": {"query": "报销 餐补 标准"}},
            {"name": "final_answer",
             "args": {"answer": "市内交通实报实销，每日餐补 100 元。", "cited": "内部文档·片段1"}},
        ],
        tools={**weather_tools, "search_docs": search_docs},
        system_prompt="你是企业助手",
        middlewares=[pii_mask, no_deploy],
        checkpointer={},
    )
    answer = assembled("用户 138-0000-0000 问：差旅报销标准是什么？（不需要 deploy）")
    print(f"  结构化结论: {answer}")
    print("  总装清单：search_docs 检索工具（s08）+ pii/no_deploy 中间件（s05）+ "
          "checkpointer（s06）+ final_answer 结构化（s07）+ 声明式编译（s01/s04）")

    print("\n学完之后去哪？")
    print("  · 按 ../源码解析与学习路线.md 的阶段 4 精读 factory.py 全文（本课行号可直接定位）")
    print("  · 图引擎下沉：08-langgraph 的源码解析文档讲'图到底怎么执行'（工作区 08 号材料）")
    print("  · 横向对照：03-deepseek-harness 教材（插件树路线）——两家把'可组装'做成了不同形状")


if __name__ == "__main__":
    main()
