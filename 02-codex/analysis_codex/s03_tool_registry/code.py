#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
s03_tool_registry/code.py —— mini ToolRegistry + orchestrator：工具总闸

s01 的 step 循环里有一行 `dispatch_tool(call)` 的占位。本课把它正式化——
Codex 对"模型点了工具名之后"的答案分两层：

  注册表层（codex-rs/core/src/tools/registry.rs）
    · ToolRegistry（:302）：所有工具的唯一登记处——内置、MCP、多智能体、
      插件工具都在同一张表里；带命名空间（如 multi_agent_v1），扁平名
      "ns.tool" 与 (namespace, name) 二元组互查
    · CoreToolRuntime（:55 trait）：本地工具的统一运行时契约——执行能力
      （ToolExecutor，在 codex-tools crate）+ 内核切面（hooks/遥测/调度追踪）

  编排层（codex-rs/core/src/tools/orchestrator.rs，文件头注释即设计文档）
    "Central place for approvals + sandbox selection + retry semantics:
     approval → select sandbox → attempt → retry with an escalated sandbox
     strategy on denial (no re-approval thanks to caching)."
    四段：审批判定 → 选沙箱 → 尝试执行 → 被沙箱拒绝则升级重试。
    本课实现前三段 + 审批缓存；第四段（escalation）留给 s05 专讲。

  模型 tool_call
       │
       ▼
  ┌─────────────┐   查找（命名空间/扁平名）
  │ ToolRegistry ├──────────────┐
  └─────────────┘              ▼
                     ┌───────────────────────────────┐
                     │ orchestrator 总闸              │
                     │ ① 审批（缓存命中免弹窗）        │
                     │ ② 选沙箱（s04 展开为双轴矩阵）  │
                     │ ③ attempt：start→执行→finish   │
                     │ ④ 拒绝→升级重试（s05）          │
                     └──────────────┬────────────────┘
                                    ▼
                          工具结果（成功或合成错误）
   铁律：每次执行必过总闸，没有旁路；被拒的调用也必有配对结果。

Rust ↔ Python：trait + 泛型（ToolExecutor<ToolInvocation>）↔ Protocol/可调用对象；
遥测（otel.sandbox_outcome）↔ 本地 events 列表；Arc 共享 ↔ 单线程 asyncio 直接共享。

运行：python code.py    （零依赖，离线）
对照真实源码：core/src/tools/registry.rs、core/src/tools/orchestrator.rs、
             core/src/tools/lifecycle.rs
"""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.mini_util import ToolCall, force_utf8_stdout

force_utf8_stdout()

MULTI_AGENT_V1_NAMESPACE = "multi_agent_v1"  # 对应 handlers/multi_agents_spec.rs 的同名常量

# ---------------------------------------------------------------
# 第 1 部分：ToolRegistry —— 唯一登记处
# ---------------------------------------------------------------


@dataclass
class ToolSpec:
    """工具登记项。真实版是 `*_spec.rs`（声明）与 handler（实现）分离的成对文件，
    例如 handlers/apply_patch.rs + apply_patch_spec.rs。"""

    name: str
    description: str
    run: Callable[[Dict[str, Any]], "ToolOutput"]          # ToolExecutor 的执行面
    namespace: Optional[str] = None                        # 命名空间：多智能体/扩展工具隔离用
    escalate_on_failure: bool = False                      # 沙箱拒绝后是否允许升级重试（s05）


@dataclass
class ToolOutput:
    """工具输出。对应 ToolOutput trait object：永远有结构化内容，供模型回读。"""

    ok: bool
    content: str


def flat_name(spec: ToolSpec) -> str:
    """扁平名："ns.tool" 或裸 "tool"。真实实现见 tools/registry.rs 的 flat_tool_name。"""
    return f"{spec.namespace}.{spec.name}" if spec.namespace else spec.name


class ToolRegistry:
    """对应 core/src/tools/registry.rs :302 `ToolRegistry`。

    设计要点：一张表管所有来源（内置/MCP/多智能体/插件），可见性与隔离
    靠命名空间，不靠"各自建表"——可见性审查因此有了单点。
    """

    def __init__(self) -> None:
        self._tools: Dict[Tuple[Optional[str], str], ToolSpec] = {}

    def register(self, spec: ToolSpec) -> Callable[[], None]:
        key = (spec.namespace, spec.name)
        if key in self._tools:
            raise ValueError(f"工具重复注册：{flat_name(spec)}")
        self._tools[key] = spec
        return lambda: self._tools.pop(key, None)  # 注销函数：注册即可逆（s01 纪律）

    def lookup(self, name: str, namespace: Optional[str] = None) -> Optional[ToolSpec]:
        if namespace:
            return self._tools.get((namespace, name))
        # 无命名空间的裸名：查全局表；带点的扁平名自动拆分
        if "." in name:
            ns, _, bare = name.partition(".")
            return self._tools.get((ns, bare))
        return self._tools.get((None, name))

    def visible(self, namespaces: List[Optional[str]]) -> List[str]:
        """当前上下文可见的工具面（真实实现还要算 ToolExposure / tool_search）。"""
        out = [flat_name(s) for (ns, _), s in self._tools.items() if ns is None or ns in namespaces]
        return sorted(out)


# ---------------------------------------------------------------
# 第 2 部分：orchestrator —— 审批 → 选沙箱 → attempt（→ 升级重试，s05）
# ---------------------------------------------------------------


class SandboxDenied(Exception):
    """沙箱拒绝。对应 core/src/tools/orchestrator.rs 里的 SandboxErr::Denied——
    注意它只表示"策略挡了"，与"命令自己报错"是两回事（s05 的分水岭）。"""


@dataclass
class ApprovalDecision:
    granted: bool
    reason: str


class Orchestrator:
    """对应 orchestrator.rs :135 `ToolOrchestrator::run` 的 mini 版（前三段）。

    审批缓存的语义：同一个 (工具, 命令指纹) 一旦获批，后续相同请求不再弹窗
    ——"no re-approval thanks to caching"。真实实现还有 execpolicy 规则表
    （Allow/Prompt/Forbidden 三值，execpolicy/src/decision.rs :9）参与判定。
    """

    def __init__(self, approver: Callable[[ToolCall, ToolSpec], ApprovalDecision],
                 events: List[Dict[str, Any]]):
        self.approver = approver
        self.events = events          # 遥测/调度追踪（对应 otel + ToolDispatchTrace）
        self.approval_cache: Dict[str, ApprovalDecision] = {}

    def _fingerprint(self, call: ToolCall) -> str:
        arg = call.arguments.get("command") or call.arguments.get("path") or ""
        return f"{call.name}:{arg}"

    async def run(self, call: ToolCall, registry: ToolRegistry) -> ToolOutput:
        t0 = time.perf_counter()
        spec = registry.lookup(call.name)
        if spec is None:
            # 未知工具：合成错误结果而非抛异常——模型的调用也要有配对结果
            out = ToolOutput(False, f"错误：未知工具 {call.name}")
            self.events.append({"phase": "dispatch", "tool": call.name, "ok": False,
                                "ms": self._ms(t0)})
            return out

        # ---- 段①：审批判定（orchestrator 的 default_exec_approval_requirement 语义）----
        fp = self._fingerprint(call)
        if fp in self.approval_cache:
            decision = self.approval_cache[fp]
            self.events.append({"phase": "approval", "tool": call.name, "cached": True,
                                "granted": decision.granted})
        else:
            decision = self.approver(call, spec)
            self.approval_cache[fp] = decision
            self.events.append({"phase": "approval", "tool": call.name, "cached": False,
                                "granted": decision.granted, "reason": decision.reason})
        if not decision.granted:
            out = ToolOutput(False, f"用户拒绝执行 {call.name}：{decision.reason}")
            self.events.append({"phase": "denied", "tool": call.name, "ms": self._ms(t0)})
            return out

        # ---- 段②：选沙箱（本课恒为"无沙箱"；s04 展开为双轴矩阵，s05 升级重试）----
        sandbox = "none"  # 真实实现：sandbox_override_for_first_attempt（tools/sandboxing.rs :238）

        # ---- 段③：attempt —— start → 执行 → finish（lifecycle.rs 的 notify_tool_start/finish）----
        self.events.append({"phase": "tool_start", "tool": call.name, "sandbox": sandbox})
        try:
            out = await spec.run(call.arguments)
        except SandboxDenied as e:
            # ---- 段④：升级重试的入口（mini 版只记录，语义展开在 s05）----
            self.events.append({"phase": "sandbox_denied", "tool": call.name, "detail": str(e)})
            out = ToolOutput(False, f"沙箱拒绝：{e}（升级重试见 s05）")
        self.events.append({"phase": "tool_finish", "tool": call.name, "ok": out.ok,
                            "ms": self._ms(t0)})
        return out

    def _ms(self, t0: float) -> float:
        return round((time.perf_counter() - t0) * 1000, 1)


# ---------------------------------------------------------------
# 第 3 部分：演示工具与剧本审批人
# ---------------------------------------------------------------


async def run_read_file(args: Dict[str, Any]) -> ToolOutput:
    await asyncio.sleep(0)  # 模拟 IO 让出
    return ToolOutput(True, f"(模拟) {args['path']} 共 42 行：def login(): ...")


async def run_shell(args: Dict[str, Any]) -> ToolOutput:
    """shell 工具：如果命令想写工作区外，教学版抛 SandboxDenied（真实由沙箱实施）。"""
    await asyncio.sleep(0)
    if args.get("command", "").startswith("rm -rf /"):
        raise SandboxDenied("目标路径在工作区外，写保护")
    return ToolOutput(True, f"(模拟) 已执行：{args['command']}")


def scripted_approver(script: List[ApprovalDecision], calls: List[str]):
    """剧本审批人：按序吐决定，并记录"被问了几次"（供缓存断言）。"""
    state = {"cursor": 0}

    def approve(call: ToolCall, spec: ToolSpec) -> ApprovalDecision:
        calls.append(f"{call.name}({call.arguments.get('command', call.arguments.get('path', ''))})")
        d = script[min(state["cursor"], len(script) - 1)]
        state["cursor"] += 1
        return d
    return approve


# ---------------------------------------------------------------
# 第 4 部分：演示
# ---------------------------------------------------------------


async def main() -> None:
    events: List[Dict[str, Any]] = []

    print("== 场景 1：注册表与命名空间 —— 一张表管所有来源 ==")
    registry = ToolRegistry()
    registry.register(ToolSpec("read_file", "读文件", run_read_file))
    registry.register(ToolSpec("shell", "执行命令", run_shell, escalate_on_failure=True))
    registry.register(ToolSpec("spawn", "派生子代理", run_read_file,
                               namespace=MULTI_AGENT_V1_NAMESPACE))
    print(f"    全局面: {registry.visible([None])}")
    print(f"    多智能体上下文可见: {registry.visible([None, MULTI_AGENT_V1_NAMESPACE])}")
    print(f"    扁平名解析 'multi_agent_v1.spawn' → "
          f"{registry.lookup('multi_agent_v1.spawn') is not None}")
    try:
        registry.register(ToolSpec("shell", "重复注册", run_shell))
    except ValueError as e:
        print(f"    重复注册被拒：{e}")

    approver_calls: List[str] = []
    orch = Orchestrator(scripted_approver([
        ApprovalDecision(True, "策略允许只读工具"),
        ApprovalDecision(True, "用户批准 npm test"),
        ApprovalDecision(False, "用户拒绝强推"),
        ApprovalDecision(True, "用户批准清理（但沙箱另说，见场景 5）"),
    ], approver_calls), events)

    print("\n== 场景 2：快乐路径 —— 四段总闸走一遍 ==")
    out = await orch.run(ToolCall("c1", "read_file", {"path": "login.py"}), registry)
    print(f"    结果 ok={out.ok}: {out.content[:30]}…")

    print("\n== 场景 3：审批缓存 —— 同一命令第二次不再弹窗 ==")
    await orch.run(ToolCall("c2", "shell", {"command": "npm test"}), registry)
    await orch.run(ToolCall("c3", "shell", {"command": "npm test"}), registry)
    npm_asked = sum(1 for c in approver_calls if "npm test" in c)
    print(f"    'npm test' 被问 {npm_asked} 次（第 1 次弹窗，第 2 次命中缓存）")

    print("\n== 场景 4：拒绝与未知工具 —— 都有配对结果，没有悬空调用 ==")
    out = await orch.run(ToolCall("c4", "shell", {"command": "git push --force"}), registry)
    print(f"    被拒: ok={out.ok}, {out.content}")
    out = await orch.run(ToolCall("c5", "not_a_tool", {}), registry)
    print(f"    未知工具: ok={out.ok}, {out.content}")

    print("\n== 场景 5：沙箱拒绝 —— 用户批了，沙箱说不（第④段入口，展开在 s05） ==")
    out = await orch.run(ToolCall("c6", "shell", {"command": "rm -rf /system"}), registry)
    print(f"    ok={out.ok}, {out.content}")
    print("    → 审批与沙箱是两道独立的闸：批的是'可以做'，沙箱裁决'这个环境能不能'")

    print("\n调度追踪（ToolDispatchTrace 的 mini 版）：")
    for e in events:
        if e["phase"] in ("approval", "tool_start", "tool_finish", "sandbox_denied", "denied"):
            print(f"    {e['phase']:<14} {e['tool']:<12} cached={e.get('cached', '-')}"
                  f" granted={e.get('granted', '-')} {('ms=' + str(e['ms'])) if 'ms' in e else ''}")
    print("\n结论：注册表是一张表，总闸只有一道；被拒的调用也必有配对结果。")


if __name__ == "__main__":
    asyncio.run(main())
