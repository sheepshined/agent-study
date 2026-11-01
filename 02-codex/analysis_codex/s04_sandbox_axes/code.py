#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
s04_sandbox_axes/code.py —— mini 沙箱双轴：AskForApproval × SandboxPolicy

s03 的总闸里，"审批"与"选沙箱"两段只各占几行。本课展开 Codex 安全模型
的核心世界观：**两根正交的轴**（protocol/src/protocol.rs :1004 / :1090）：

  轴一 AskForApproval（审批策略：问不问人，问什么）        :1004
    UnlessTrusted  面向未受信项目：除非显式策略放行，命令都要审批
    OnRequest      默认档：模型自主决定何时请求审批
    Granular(cfg)  细粒度开关（sandbox_approval/rules/skill_approval/
                   request_permissions/mcp_elicitations），置 False 的
                   类别直接自动拒绝（GranularApprovalConfig :1030）
    Never          从不问；失败直接回给模型

  轴二 SandboxPolicy（沙箱策略：环境允许什么）              :1090
    DangerFullAccess  无限制（慎用）                        :1096
    ReadOnly          只读；network_access 可单独开          :1100
    ExternalSandbox   已在外部沙箱中，服从网络设置           :1110
    WorkspaceWrite    只读 + 工作区可写 + 额外可写根/网络开关 :1119

  两轴组合的判定核心（core/src/tools/sandboxing.rs）：
    default_exec_approval_requirement :194 —— 需不需要审批（Skip/Needs/Forbidden）
    sandbox_override_for_first_attempt :238 —— 第一枪要不要绕开沙箱
    unsandboxed_execution_allowed :275 —— 有 denied-read 时绝不能裸跑
  再加 WritableRoot（protocol.rs :1149）：可写根里的提权敏感子路径
  （.codex、.git、尤其 .git/hooks）**恒为只读**——防"改 git hook 拿权限"。

  轴一（审批）             轴二（沙箱）
  Never ─┐                 DangerFullAccess ─┐
  OnRequest ├─ 问不问人     WorkspaceWrite   ├─ 允许什么
  UnlessTrusted┘            ReadOnly ────────┘
        两轴正交：审批管"问不问"，沙箱管"能怎样"，谁也不替谁做决定。

Rust ↔ Python：Rust enum 变体自带字段（tagged enum）↔ dataclass + kind；
`matches!` 宏 ↔ Python 的 isinstance/kind 判断；serde 校验非法组合 ↔
dataclass 构造即合法（课程用注释说明类型系统守门的思想）。

运行：python code.py    （零依赖，离线）
对照真实源码：protocol/src/protocol.rs（枚举定义）、core/src/tools/sandboxing.rs
（判定函数）、sandboxing/src/manager.rs（平台落地）
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.mini_util import force_utf8_stdout

force_utf8_stdout()

# ---------------------------------------------------------------
# 第 1 部分：两根轴（protocol.rs 枚举的 mini 版）
# ---------------------------------------------------------------


@dataclass(frozen=True)
class GranularConfig:
    """对应 GranularApprovalConfig（protocol.rs :1030）：每个开关 False = 该类
    请求不弹窗、直接自动拒绝——"细粒度静音键"。"""

    sandbox_approval: bool = True   # shell 升级类审批
    rules: bool = True              # execpolicy prompt 规则
    skill_approval: bool = True     # skill 脚本执行
    request_permissions: bool = True
    mcp_elicitations: bool = True   # MCP 反向征求（s06 会用到）


@dataclass(frozen=True)
class AskForApproval:
    """审批策略轴。Rust 是带变体的 enum；mini 版用 kind + 可选 cfg。"""

    kind: str  # "untrusted" | "on_request" | "granular" | "never"
    cfg: Optional[GranularConfig] = None


UNTRUSTED = AskForApproval("untrusted")
ON_REQUEST = AskForApproval("on_request")          # #[default]
NEVER = AskForApproval("never")
GRANULAR_OFF = AskForApproval("granular", GranularConfig(sandbox_approval=False))


@dataclass(frozen=True)
class SandboxPolicy:
    """沙箱策略轴。Rust 变体字段（writable_roots/network_access/…）摊平成可选字段。"""

    kind: str                       # "read_only" | "workspace_write" | "danger_full_access" | "external_sandbox"
    network_access: bool = False    # ReadOnly/WorkspaceWrite 的网络开关
    writable_roots: Tuple[str, ...] = ()  # WorkspaceWrite 的额外可写根


READ_ONLY = SandboxPolicy("read_only")
WORKSPACE_WRITE = SandboxPolicy("workspace_write")
WORKSPACE_NET = SandboxPolicy("workspace_write", network_access=True)
DANGER_FULL = SandboxPolicy("danger_full_access")


@dataclass(frozen=True)
class WritableRoot:
    """可写根 + 恒只读子路径。对应 protocol.rs :1149 `WritableRoot`：
    root 可写，但 read_only_subpaths 里的提权敏感路径（.codex/.git/.git/hooks）
    仍不可写——可写性不是"整个目录一把梭"。"""

    root: str
    read_only_subpaths: Tuple[str, ...] = (".codex", ".git", ".git/hooks")

    def write_allowed(self, path: str) -> Tuple[bool, str]:
        norm = path.replace("\\", "/").lstrip("/")
        if not norm.startswith(self.root.lstrip("/")):
            return False, "在可写根之外"
        for sub in self.read_only_subpaths:
            if norm.startswith(f"{self.root.strip('/')}/{sub}"):
                return False, f"提权敏感路径 ./{sub} 恒只读（WritableRoot 保护）"
        return True, "在工作区内"


# ---------------------------------------------------------------
# 第 2 部分：判定矩阵（sandboxing.rs 三个函数的 mini 版）
# ---------------------------------------------------------------


def exec_approval_requirement(policy: AskForApproval, sandbox: SandboxPolicy) -> str:
    """审批判定。对应 default_exec_approval_requirement（sandboxing.rs :194）。

    Never → 不问；OnRequest/Granular → 沙箱受限（非全权）才问；
    UnlessTrusted → 永远问；Granular 且关掉 sandbox_approval → 直接 Forbidden。
    返回值对应 ExecApprovalRequirement（:152）：Skip / NeedsApproval / Forbidden。
    """
    restricted = sandbox.kind in ("read_only", "workspace_write")
    needs = (policy.kind == "untrusted") or (
        policy.kind in ("on_request", "granular") and restricted)
    if needs and policy.kind == "granular" and policy.cfg and not policy.cfg.sandbox_approval:
        return "Forbidden: 策略关闭了沙箱升级类审批（自动拒绝，不弹窗）"
    return "NeedsApproval" if needs else "Skip"


def unsandboxed_execution_allowed(denied_reads: bool) -> bool:
    """对应 :275：有 denied-read 限制时绝不能脱离沙箱执行——
    拒读只存在于沙箱里，裸跑等于把拒读白送。"""

    return not denied_reads


def sandbox_override_for_first_attempt(escalated: bool, denied_reads: bool) -> str:
    """对应 :238：第一枪是否绕开沙箱。escalated 请求 → 绕开；
    但有 denied-read 时 NoOverride（拒读优先级最高）。"""

    if not unsandboxed_execution_allowed(denied_reads):
        return "NoOverride（存在 denied-read，拒绝裸跑）"
    return "BypassSandboxFirstAttempt" if escalated else "NoOverride"


# ---------------------------------------------------------------
# 第 3 部分：mini 沙箱 —— 对文件/网络操作的强制实施
# ---------------------------------------------------------------


class SandboxDenied(Exception):
    pass


def enforce(sandbox: SandboxPolicy, roots: List[WritableRoot], op: str, target: str) -> str:
    """对一次操作做沙箱裁决。真实实施在 sandboxing/ 各平台后端：
    seatbelt.rs（macOS）/ landlock.rs（Linux）/ windows_mxc.rs（Windows）——
    mini 版用一条 if 链表达**同一套语义**。"""
    if sandbox.kind == "danger_full_access":
        return "允许（全权档，无沙箱）"
    if op == "network":
        if sandbox.network_access:
            return "允许（网络已显式开启）"
        raise SandboxDenied(f"网络访问被拒绝（{sandbox.kind} 默认 Restricted，NetworkAccess :1074）")
    if op == "read":
        return "允许（读在所有非全权档位开放）"
    # op == "write"
    if sandbox.kind == "read_only":
        raise SandboxDenied("只读沙箱：写操作被拒绝")
    for root in roots:  # workspace_write：逐个可写根判定（含恒只读子路径）
        ok, why = root.write_allowed(target)
        if ok:
            return "允许（在可写根内）"
        if "恒只读" in why:
            raise SandboxDenied(why)
    raise SandboxDenied("写目标不在任何可写根内（workspace-write 档）")


# ---------------------------------------------------------------
# 第 4 部分：演示
# ---------------------------------------------------------------


def scenario_matrix() -> None:
    print("== 场景 1：判定矩阵 —— 4 档审批 × 3 档沙箱 ==")
    policies = [("untrusted", UNTRUSTED), ("on-request", ON_REQUEST),
                ("granular(关沙箱审批)", GRANULAR_OFF), ("never", NEVER)]
    sandboxes = [("read-only", READ_ONLY), ("workspace-write", WORKSPACE_WRITE),
                 ("danger-full-access", DANGER_FULL)]
    label = {"Skip": "免审批", "NeedsApproval": "需审批"}
    print("    审批 ╲ 沙箱        " + "".join(f"{n:<22}" for n, _ in sandboxes))
    for pname, p in policies:
        cells = []
        for _, s in sandboxes:
            req = exec_approval_requirement(p, s)
            cells.append(("禁止审批" if req.startswith("Forbidden") else label.get(req, req)))
        print(f"    {pname:<20}" + "".join(f"{c:<24}" for c in cells))
    print("    规律：OnRequest 只在沙箱受限时问；UnlessTrusted 永远问；Never 永不问；")
    print("          granular 关掉开关后，本该弹窗的场景直接 Forbidden（:194 的分支）")


def scenario_writable_root() -> None:
    print("\n== 场景 2：workspace-write —— 可写根里的'恒只读'陷阱 ==")
    roots = [WritableRoot(root="workspace")]
    ops = [("write", "workspace/src/login.py"), ("write", "workspace/.git/hooks/pre-commit"),
           ("write", "/etc/hosts"), ("read", "/etc/hosts")]
    for op, target in ops:
        try:
            print(f"    {op:<5} {target:<34} → {enforce(WORKSPACE_WRITE, roots, op, target)}")
        except SandboxDenied as e:
            print(f"    {op:<5} {target:<34} → 拒绝：{e}")
    print("    → .git/hooks 在工作区内却不可写：防'改 git hook 拿权限'的经典逃逸")


def scenario_network() -> None:
    print("\n== 场景 3：网络轴 —— NetworkAccess 是独立开关 ==")
    for name, s in [("read-only（网络关）", READ_ONLY), ("read-only+net", SandboxPolicy("read_only", network_access=True)),
                    ("workspace-write（网络关）", WORKSPACE_WRITE)]:
        try:
            print(f"    {name:<26} curl https://… → {enforce(s, [], 'network', 'https://api.example.com')}")
        except SandboxDenied as e:
            print(f"    {name:<26} curl https://… → 拒绝：{e}")
    print("    → 网络不随档位自动开：ReadOnly 也能开网、workspace-write 默认也断网")


def scenario_full_access() -> None:
    print("\n== 场景 4：danger-full-access + never —— 全权直通与边界（失败路径） ==")
    print(f"    审批判定: {exec_approval_requirement(NEVER, DANGER_FULL)}（不问）")
    print(f"    写 /etc/hosts → {enforce(DANGER_FULL, [], 'write', '/etc/hosts')}")
    print(f"    第一枪旁路: {sandbox_override_for_first_attempt(escalated=True, denied_reads=False)}")
    print(f"    带 denied-read 时: {sandbox_override_for_first_attempt(escalated=True, denied_reads=True)}")
    print(f"    granular 关沙箱审批 + workspace-write → {exec_approval_requirement(GRANULAR_OFF, WORKSPACE_WRITE)}")
    print("    → 拒读比升级更高优先级：环境承诺的'看不见'不因升级而破功")


def main() -> None:
    scenario_matrix()
    scenario_writable_root()
    scenario_network()
    scenario_full_access()
    print("\n结论：审批轴与沙箱轴正交组合 = 可枚举、可审计的安全语义；")
    print("WritableRoot 的'恒只读子路径'是工业级细节——可写 ≠ 可提权。")


if __name__ == "__main__":
    main()
