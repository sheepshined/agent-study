#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
s05_escalation/code.py —— mini 升级重试：escalation（升级提权）的完整语义

s03 留了第④段占位，s04 给了两根轴。本课把最精妙的一段补齐：命令在沙箱里
被挡下来之后，发生什么？Codex 的答案写在 orchestrator.rs 里（:300-:540
的决策链）：

    沙箱拒绝（SandboxErr::Denied，:352）
      ├─ 工具声明 escalate_on_failure == false？→ 不重试（:376）
      ├─ 审批策略是 Never / OnRequest？→ 不"出沙箱重跑"（wants_no_sandbox_approval，:389）
      ├─ 环境带 denied-read？→ 不能裸跑，降级为沙箱内重试（sandboxing.rs :275/:286）
      ├─ 请求升级审批（问一次用户，结果进缓存——免重审批）
      └─ 原样重跑（同一命令、同一参数，只是沙箱档位变了）

  两次执行，一道闸：
    attempt#1 ──沙箱──✗ denied（violation 事件记录在案）
        │ 只有"策略挡了"才走升级；命令自己报错 → 直接回模型，不重试
        ▼
    升级判定（三个门：escalate_on_failure / 策略 / denied-read）
        │ 全过 → 问一次用户
        ▼
    attempt#2 ──出沙箱（或沙箱内降级重试）──✓/✗

  为什么"免重审批"是安全的？因为升级的只是沙箱档位，审批缓存记的是
  "这个命令用户批过"；真实代码里 strict auto-review 还会进一步区分
  "沙箱内批准"与"沙箱外重跑"的授权边界（orchestrator.rs :412 一带）。

Rust ↔ Python：多级 if/else 决策链 ↔ 同样的顺序判断（语义等价即可）；
Instant 计时 ↔ time.perf_counter；otel.sandbox_outcome 遥测 ↔ events 列表。

运行：python code.py    （零依赖，离线）
对照真实源码：core/src/tools/orchestrator.rs（run :135 的决策链 :300-:540）、
             core/src/tools/sandboxing.rs（:194/:238/:275）
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.mini_util import ToolCall, force_utf8_stdout

force_utf8_stdout()

# ---------------------------------------------------------------
# 第 1 部分：环境与沙箱裁决（s04 结论的最小复用，本课自包含）
# ---------------------------------------------------------------


@dataclass
class Env:
    """一次执行的环境：审批档 + 沙箱档 + 可写根 + 是否带拒读限制。"""

    policy: str                      # "untrusted" | "on_request" | "never"
    sandbox: str                     # "workspace_write" | "read_only" | ...
    writable_roots: Tuple[str, ...] = ("workspace",)
    denied_reads: bool = False       # 环境是否声明了 denied-read 路径


class SandboxDenied(Exception):
    """沙箱拒绝：只表示"策略挡了"。对应 SandboxErr::Denied。"""


class ToolFailure(Exception):
    """命令自己的失败（非沙箱拒绝）。对应普通 ToolError——不该触发升级。"""


def sandbox_run(env: Env, command: str) -> str:
    """模拟"在给定沙箱档位下执行命令"。真实实施在 seatbelt/landlock/windows 后端。

    命令剧本（教学约定）：
      npm test               → 成功（不碰工作区外）
      python build.py        → 要写 /usr/lib/pkg → 工作区外 → 沙箱拒绝
      grep key /var/secrets  → 读 denied-read 路径 → 沙箱拒绝（有拒读的环境）
      flaky-deploy           → 命令自己崩（ToolFailure，与沙箱无关）
    """
    if command == "python build.py":
        raise SandboxDenied("写目标 /usr/lib/pkg 在工作区外")
    if command.startswith("grep") and env.denied_reads:
        raise SandboxDenied("目标 /var/secrets 在 denied-read 列表")
    if command == "flaky-deploy":
        raise ToolFailure("deploy 脚本 exit code 1")
    return f"(模拟) {command} 执行成功"


def unsandboxed_run(command: str) -> str:
    """裸跑（无沙箱）：只用于通过全部升级门之后的第二次尝试。"""
    if command == "flaky-deploy":
        raise ToolFailure("deploy 脚本 exit code 1")
    return f"(模拟) {command} 执行成功（无沙箱）"


# ---------------------------------------------------------------
# 第 2 部分：审批人（弹窗的剧本替身）
# ---------------------------------------------------------------


@dataclass
class Approver:
    """记录"被问了几次"，验证缓存语义。真实实现在 tui/app-server 的审批通道。"""

    answers: List[bool]
    asked: int = 0
    log: List[str] = field(default_factory=list)

    def ask(self, question: str) -> bool:
        self.asked += 1
        self.log.append(question)
        return self.answers[min(self.asked - 1, len(self.answers) - 1)]


# ---------------------------------------------------------------
# 第 3 部分：orchestrator 完整四段（本课主角）
# ---------------------------------------------------------------


@dataclass
class RunResult:
    output: str
    attempts: int
    escalated: bool
    timeline: List[str] = field(default_factory=list)


async def orchestrated_run(env: Env, call: ToolCall, *,
                           escalate_on_failure: bool = True,
                           approver: Optional[Approver] = None,
                           approval_cache: Dict[str, bool]) -> RunResult:
    """对应 orchestrator.rs run(:135) 决策链(:300-:540)的 mini 版。逐门注释真实锚点。"""
    t = {"n": 0}

    def mark(line: str) -> None:
        t["n"] += 1
        print(f"      {t['n']}. {line}")

    res = RunResult(output="", attempts=0, escalated=False)
    fp = f"{call.name}:{call.arguments.get('command', '')}"

    # ---- 段①：审批判定（命令执行前，s04 矩阵；本课聚焦拒绝后的世界，恒放行）----
    mark(f"段① 审批判定：{fp} → 放行（策略 {env.policy}）")

    # ---- 段②：选沙箱 —— 第一次尝试恒在沙箱内（除非首枪旁路，s04 :238）----
    mark(f"段② 选沙箱：first_attempt = {env.sandbox}")

    # ---- 段③：attempt #1 ----
    res.attempts += 1
    mark(f"段③ attempt#1：在 {env.sandbox} 内执行 …")
    try:
        out = sandbox_run(env, call.arguments["command"])
        mark(f"attempt#1 成功 → {out}")
        res.output = out
        return res
    except SandboxDenied as e:
        mark(f"attempt#1 被沙箱拒绝：{e}（SandboxErr::Denied，:352；违规已记录 violation.rs）")
        denial: SandboxDenied = e
    except ToolFailure as e:
        mark(f"attempt#1 命令自身失败：{e} → 不升级（失败归因是'命令错了'，:352 的 else 分支）")
        res.output = f"错误：{e}"
        return res

    # ---- 段④：升级重试决策链 ----
    if not escalate_on_failure:
        mark("段④ 工具声明 escalate_on_failure=false → 不重试（:376）")
        res.output = f"沙箱拒绝：{denial}"
        return res
    if env.policy in ("never", "on_request"):
        # Never/OnRequest 明确不出沙箱重跑：用户没给过"沙箱外执行"的授权
        mark(f"段④ 审批策略 {env.policy} → 不出沙箱重跑（wants_no_sandbox_approval，:389）")
        mark("      → 把简明的沙箱拒绝信息回给模型（保留原始输出）")
        res.output = f"沙箱拒绝：{denial}"
        return res
    if env.denied_reads:
        # 拒读只存在于沙箱内：裸跑等于白送拒读 → 降级为沙箱内重试（:275/:286）
        mark("段④ 环境带 denied-read → 禁止裸跑，降级为沙箱内重试（sandboxing.rs :275）")
        res.attempts += 1
        try:
            sandbox_run(env, call.arguments["command"])
            mark("attempt#2（沙箱内）成功")
            res.output = "（沙箱内重试成功）"
        except SandboxDenied as e2:
            mark(f"attempt#2（沙箱内）同样被拒：{e2} → 放弃，错误回模型")
            res.output = f"沙箱拒绝：{e2}"
        return res

    # ---- 升级审批：问一次，缓存 forever ----
    if approval_cache.get(fp):
        mark("段④ 升级审批：缓存命中，不再弹窗（no re-approval thanks to caching）")
    else:
        assert approver is not None
        granted = approver.ask(f"命令被沙箱拒绝，允许脱离沙箱重跑吗？[{fp}]")
        approval_cache[fp] = granted
        mark(f"段④ 升级审批：询问用户 → {'批准' if granted else '拒绝'}（结果已入缓存）")
        if not granted:
            res.output = f"沙箱拒绝：{denial}（用户否决升级）"
            return res

    # ---- attempt #2：原样重跑（同命令同参数，只换沙箱档位）----
    res.escalated = True
    res.attempts += 1
    mark("段④ attempt#2：原样重跑（unrestricted）…")
    try:
        out = unsandboxed_run(call.arguments["command"])
        mark(f"attempt#2 成功 → {out}")
        res.output = out
    except SandboxDenied as e2:  # 裸跑理论上不再有沙箱拒绝；防御性保留
        res.output = f"错误：{e2}"
    except ToolFailure as e2:
        mark(f"attempt#2 命令自身失败：{e2.message} → 错误回模型（不无限重试）")
        res.output = f"错误：{e2.message}"
    return res


# ---------------------------------------------------------------
# 第 4 部分：演示 —— 四条路径
# ---------------------------------------------------------------


async def main() -> None:
    approval_cache: Dict[str, bool] = {}

    print("== 场景 1：标准升级 —— 沙箱拒绝 → 问一次 → 原样重跑成功 ==")
    env1 = Env(policy="untrusted", sandbox="workspace_write")
    print(f"    环境：policy={env1.policy} sandbox={env1.sandbox}；命令：python build.py（要写工作区外）")
    ap = Approver(answers=[True])
    r = await orchestrated_run(env1, ToolCall("c1", "shell", {"command": "python build.py"}),
                               approver=ap, approval_cache=approval_cache)
    print(f"    结果：attempts={r.attempts} escalated={r.escalated} output={r.output}")
    print(f"    用户被问 {ap.asked} 次\n")

    print("== 场景 2：同命令再来 —— 升级审批走缓存，零弹窗 ==")
    ap2 = Approver(answers=[True])
    r = await orchestrated_run(env1, ToolCall("c2", "shell", {"command": "python build.py"}),
                               approver=ap2, approval_cache=approval_cache)
    print(f"    结果：attempts={r.attempts} escalated={r.escalated}；用户被问 {ap2.asked} 次")
    print("    → 批准过一次的决策有记忆：升级不再骚扰用户\n")

    print("== 场景 3：never 策略 —— 拒绝就是拒绝，不出沙箱重跑（失败路径） ==")
    env3 = Env(policy="never", sandbox="workspace_write")
    ap3 = Approver(answers=[True])
    r = await orchestrated_run(env3, ToolCall("c3", "shell", {"command": "python build.py"}),
                               approver=ap3, approval_cache=approval_cache)
    print(f"    结果：attempts={r.attempts} escalated={r.escalated} output={r.output}")
    print(f"    用户被问 {ap3.asked} 次 → 自动化场景零打扰，失败直接回给模型自己想办法\n")

    print("== 场景 4：denied-read 环境 —— 升级也不许裸跑（安全边界） ==")
    env4 = Env(policy="untrusted", sandbox="workspace_write", denied_reads=True)
    ap4 = Approver(answers=[True])
    r = await orchestrated_run(env4, ToolCall("c4", "shell", {"command": "grep key /var/secrets"}),
                               approver=ap4, approval_cache=approval_cache)
    print(f"    结果：attempts={r.attempts} escalated={r.escalated} output={r.output}")
    print("    → 拒读只存在于沙箱内，脱离沙箱 = 白送拒读；降级为沙箱内重试\n")

    print("== 场景 5：命令自己崩 —— 不升级（失败归因不属沙箱） ==")
    ap5 = Approver(answers=[True])
    r = await orchestrated_run(env1, ToolCall("c5", "shell", {"command": "flaky-deploy"}),
                               approver=ap5, approval_cache=approval_cache)
    print(f"    结果：attempts={r.attempts} escalated={r.escalated} output={r.output}")
    print("    → '沙箱把命令拦了'和'命令自己错了'是两回事：只有前者才值得升级\n")

    print("结论：escalation = 三个门（工具声明 / 审批策略 / 拒读约束）+ 一次升级审批 + 原样重跑。")
    print("升级的只是沙箱档位——命令、参数、审批缓存全都不变。")


if __name__ == "__main__":
    asyncio.run(main())
