#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s05_middleware.py —— 中间件：拦截链与洋葱模型

图（s04）解决了"流程怎么走"，中间件（middleware，拦截链）解决
"每一步前后还能插什么"。LangChain 1.x 把 agent 的每个关键位都开成钩子：

    before_agent ──▶ ┌ before_model ──▶ wrap_model_call(洋葱) ──▶ after_model ┐
                     │                  （模型调用被层层包裹）                │  × N 轮
                     └──────── 工具调用走 wrap_tool_call(洋葱) ◀─────────────┘
    after_agent

七个钩子（middleware/types.py 实测：before_agent:431 / before_model:455 /
after_model:479 / wrap_model_call:503 / awrap_model_call:598 / after_agent:650 /
wrap_tool_call:674），两类形态：

  · 观察型（before/after）：读 state、返回增量补丁，可改写消息——"进去之前把事办了"。
  · 包裹型（wrap_*）：拿到 (request, handler)，洋葱一层——**可以决定不调用 handler**，
    即"拦下这次调用"；也可以前后各做一点事，最后把 handler 的结果交出去。

编译期这些钩子被"织入"图：factory.py:1648-1726 的成排 add_node 就是
middleware 的 before_model/after_model 等钩子各占一个节点，:2131 的
_add_middleware_edge 把它们串进环——**钩子在图里是显式节点，不是隐藏补丁**。

运行：python code.py          （零依赖，离线；模型由脚本化 Mock 扮演）
对照真实源码（快照 80b7409，行号以源码为准）：
    libs/langchain_v1/langchain/agents/middleware/types.py
        :349  class AgentState                状态模式（messages + add_messages）
        :431  before_agent / :455 before_model / :479 after_model
        :503  wrap_model_call / :650 after_agent / :674 wrap_tool_call
    libs/langchain_v1/langchain/agents/factory.py
        :1648-1726  中间件钩子成排 add_node（织入图结构）
        :2131  def _add_middleware_edge        钩子节点串进环
    libs/langchain_v1/langchain/agents/middleware/summarization.py
        :232  class SummarizationMiddleware   官方中间件：超预算先摘要
        :398  def before_model                观察型钩子的真实示范
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from mini_util import banner, estimate_tokens  # noqa: E402

Request = dict  # ModelRequest mini 版：{"messages": [...], "system_prompt": str}
Handler = Callable[[Request], str]


# ---------------------------------------------------------------
# 第 1 部分：中间件基类 —— 七个钩子，默认全部放行
# ---------------------------------------------------------------
class AgentMiddleware:
    """mini 中间件（types.py 的影子）。子类按需覆写钩子，其余自动放行。

    命名沿用真实 API：用户一看真实代码就能对上号——这是"教学实现
    向真实 API 收敛"的刻意选择。
    """

    name: str = "middleware"

    def before_agent(self, state: dict) -> dict | None:  # 整个 agent 运行前跑一次
        return None

    def before_model(self, state: dict) -> dict | None:  # 每轮模型调用前（观察型）
        return None

    def wrap_model_call(self, request: Request, handler: Handler) -> str:  # 包裹型
        return handler(request)

    def after_model(self, state: dict) -> dict | None:   # 每轮模型调用后
        return None

    def wrap_tool_call(self, call: dict, handler: Callable[[dict], str]) -> str:  # 包裹型
        return handler(call)

    def after_agent(self, state: dict) -> dict | None:   # 整个 agent 运行后跑一次
        return None


class StopAgent(Exception):
    """观察型钩子要求终止 agent（真实实现：after_model 返回 jump_to 跳到 END）。"""


# ---------------------------------------------------------------
# 第 2 部分：洋葱模型 —— wrap 钩子按注册顺序层层嵌套
# ---------------------------------------------------------------
def onion(hooks: list, core: Callable, make_wrap: Callable) -> Callable:
    """洋葱组装：hooks[0] 最外层（先进入、后返回），hooks[-1] 最内层。

    对应真实实现把多个 wrap_model_call 链成 async_handlers（factory.py:1230-1237）。
    返回顺序与进入顺序严格相反——这就是"洋葱"。
    """
    handler = core
    for h in reversed(hooks):
        handler = make_wrap(h, handler)
    return handler


# ---------------------------------------------------------------
# 第 3 部分：带中间件的 mini agent 运行器
# ---------------------------------------------------------------
class MockModel:
    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)

    def invoke(self, request: Request) -> str:
        return self.replies.pop(0) if self.replies else "（剧本耗尽）"


@dataclass
class MiniAgent:
    model: MockModel
    tools: dict[str, Callable[[dict], str]] = field(default_factory=dict)
    middlewares: list[AgentMiddleware] = field(default_factory=list)
    max_model_calls: int = 6

    def invoke(self, user_input: str) -> str:
        state: dict = {"messages": [f"user: {user_input}"], "tool_calls_used": 0}
        # ---- before_agent：整个会话一次（types.py:431）----
        for m in self.middlewares:
            patch = m.before_agent(state) or {}
            state |= patch
        try:
            for round_ in range(1, self.max_model_calls + 1):
                # ---- before_model 链（观察型，types.py:455）----
                for m in self.middlewares:
                    patch = m.before_model(state) or {}
                    state |= patch
                # ---- wrap_model_call 洋葱（包裹型，types.py:503）----
                def core(req: Request) -> str:
                    return self.model.invoke(req)

                def make(m: AgentMiddleware, nxt: Handler) -> Handler:
                    return lambda req: m.wrap_model_call(req, nxt)

                reply = onion(self.middlewares, core, make)({"messages": state["messages"]})
                state["messages"].append(f"assistant: {reply}")
                for m in self.middlewares:
                    state |= m.after_model(state) or {}
                # ---- 模型要工具？走 wrap_tool_call 洋葱 ----
                if reply.startswith("TOOL:"):
                    _, name, args_raw = reply.split(":", 2)
                    call = {"name": name, "args": {"raw": args_raw}, "id": f"c{round_}"}

                    def tool_core(c: dict) -> str:
                        obs = self.tools[c["name"]](c["args"])
                        state["messages"].append(f"tool({c['id']}): {obs}")
                        return obs

                    def tool_make(m: AgentMiddleware, nxt: Callable[[dict], str]) -> Callable[[dict], str]:
                        return lambda c: m.wrap_tool_call(c, nxt)

                    onion(self.middlewares, tool_core, tool_make)(call)
                    continue  # 工具结果已入历史，回 model
                return reply  # 纯文本 → 最终回答
            return "（模型调用上限，安全终止）"
        except StopAgent as e:
            print(f"  [agent] 被中间件终止: {e}")
            return f"（安全终止：{e}）"
        finally:
            for m in self.middlewares:
                state |= m.after_agent(state) or {}


# ---------------------------------------------------------------
# 第 4 部分：四个示范中间件
# ---------------------------------------------------------------
class PiiMaskMiddleware(AgentMiddleware):
    """包裹型：在把 request 交给下一层之前脱敏（真实范式：middleware/pii.py）。

    特意选包裹型而非 before_model：包裹型参与洋葱分层——**只有它在外层时，
    内层（含审计）才看不到明文**。这正是"注册顺序有语义"的教学点。
    """

    name = "pii_mask"

    def wrap_model_call(self, request: Request, handler: Handler) -> str:
        masked = [m.replace("138-0000-0000", "***MASKED***") for m in request["messages"]]
        if masked != request["messages"]:
            n = sum(a != b for a, b in zip(masked, request["messages"]))
            print(f"  [pii_mask] wrap_model_call：已脱敏 {n} 条消息")
            request = {**request, "messages": masked}
        return handler(request)


class AuditMiddleware(AgentMiddleware):
    """包裹型：wrap_model_call 进出各记一笔（真实范式：LangSmith 追踪钩子）。"""

    name = "audit"

    def __init__(self) -> None:
        self.log: list[str] = []

    def wrap_model_call(self, request: Request, handler: Handler) -> str:
        first = str(request["messages"][0])[:28] if request.get("messages") else ""
        self.log.append(f"enter model, 看到的第一条消息: {first}")
        reply = handler(request)
        self.log.append(f"exit  model(reply={reply[:12]!r}...)")
        return reply


class ToolGuardMiddleware(AgentMiddleware):
    """包裹型：wrap_tool_call 可以**不调用 handler**——拦下这次工具调用。"""

    name = "tool_guard"
    blocked: set[str] = {"deploy"}

    def wrap_tool_call(self, call: dict, handler: Callable[[dict], str]) -> str:
        if call["name"] in self.blocked:
            obs = "错误：deploy 需要人工审批（被 tool_guard 拦截）"
            print(f"  [tool_guard] 拦截 {call['name']} → 合成错误回执")
            return obs
        return handler(call)


class ModelCallLimitMiddleware(AgentMiddleware):
    """观察型：计数超限时要求终止（真实范式 model_call_limit.py：after_model 返回
    jump_to 跳出循环——mini 版用 StopAgent 异常表达同一意图）。"""

    name = "call_limit"

    def __init__(self, limit: int = 3) -> None:
        self.limit = limit
        self.count = 0

    def after_model(self, state: dict) -> dict | None:
        self.count += 1
        print(f"  [call_limit] 模型已调用 {self.count} 次")
        if self.count >= self.limit:
            raise StopAgent(f"达到模型调用上限 {self.limit}")
        return None


# ---------------------------------------------------------------
# 第 5 部分：演示
# ---------------------------------------------------------------
def main() -> None:
    banner("场景 1：洋葱模型的进入/返回顺序", "外层先进后出——注册顺序即洋葱层级")

    class Wrap(AgentMiddleware):
        def __init__(self, tag: str) -> None:
            self.tag = tag

        def wrap_model_call(self, request: Request, handler: Handler) -> str:
            print(f"  [→] 进入 {self.tag}")
            reply = handler(request)
            print(f"  [←] 返回 {self.tag}")
            return reply

    def core(req: Request) -> str:
        print("  [core] 模型真正被调用（洋葱最里层）")
        return "ok"

    chain = onion([Wrap("外层 A"), Wrap("内层 B")], core,
                  lambda m, nxt: lambda req: m.wrap_model_call(req, nxt))
    chain({"messages": []})
    print("  进入顺序 A→B→core，返回顺序 core→B→A —— 严格相反")

    banner("场景 2：完整 agent 挂三个中间件", "脱敏 + 审计 + 工具拦截同环共舞")
    model = MockModel([
        "TOOL:deploy:版本 v2",                       # 要点被拦截的工具
        "TOOL:check:健康检查",
        "一切正常，可以发布流程走完（需审批另说）。",
    ])
    agent = MiniAgent(
        model=model,
        tools={"deploy": lambda a: "已部署", "check": lambda a: "healthy"},
        middlewares=[PiiMaskMiddleware(), AuditMiddleware(), ToolGuardMiddleware()],
    )
    answer = agent.invoke("用户 138-0000-0000 想发布新版本并做健康检查")
    print(f"  最终回答: {answer}")

    banner("场景 3（边界）：模型调用上限", "永不收尾的模型被计数器拦停")
    loop_model = MockModel(["TOOL:check:1", "TOOL:check:2", "TOOL:check:3", "TOOL:check:4"])
    agent2 = MiniAgent(model=loop_model, tools={"check": lambda a: a["raw"]},
                       middlewares=[ModelCallLimitMiddleware(limit=2)], max_model_calls=6)
    print(f"  结果: {agent2.invoke('循环检查')}")

    banner("场景 4（安全教训）：中间件顺序有语义", "审计在脱敏之前 → 审计看到明文 PII")
    leaky_audit = AuditMiddleware()
    leaky = MiniAgent(
        model=MockModel(["收到，已记录。"]),
        middlewares=[leaky_audit, PiiMaskMiddleware()],  # 交换顺序！
    )
    leaky.invoke("用户 138-0000-0000 提交了反馈")
    print(f"  audit 实际看到的: {leaky_audit.log[0]}")
    print("  audit 在外层 → request 里手机号仍是明文（审计日志泄漏 PII）")
    print("  对比场景 2：pii_mask 在外层，审计只看到 ***MASKED*** ——顺序即安全边界")

    print("\n结论：中间件 = 图上预留的钩子位 + 洋葱链。观察型改 state，包裹型拦调用。")
    print("注册顺序不是风格问题，是语义与安全的一部分。")


if __name__ == "__main__":
    main()
