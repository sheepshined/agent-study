#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
s08_multi_agents/code.py —— mini 多智能体：spawn / send / wait 三件套 + 角色 + 命名空间

一个 agent 不够用时怎么办？Codex 的答案不是"再造一个进程"，而是
**在同一内核里多开一条 thread（会话）**，并且把"开子代理"做成模型自己会调的工具。

  真实源码（codex-rs/，快照 818f1cc；行号实测）
    core/src/tools/handlers/multi_agents_v2/  —— MultiAgentV2 工具面（Feature::MultiAgentV2；
        spec_plan.rs :645 按 MultiAgentVersion 在 v1/v2 两套装配之间分支）
        spawn.rs :93 handle_spawn_agent —— :124 next_thread_spawn_depth、:137
            apply_spawn_agent_role、:161 带 task_name、:262 只返回 HiddenMetadata{task_name}
        send_message.rs / followup_task.rs    —— 两种投递语义（见下）
        wait.rs :40 handle_call —— :53-64 超时三档 clamp，:73 subscribe_activity，
            :187 wait_for_activity（timeout_at + watch::changed）
        list_agents.rs :11 / interrupt_agent.rs —— plain 工具名与打断
    core/src/tools/handlers/multi_agents_spec.rs —— 工具 schema：:14 MULTI_AGENT_V1_NAMESPACE
        = "multi_agent_v1"（v1 是命名空间工具 multi_agent_v1.spawn_agent…）；:200 send_message
        与 :233 followup_task 的描述原文就是两种投递语义的规范；:360 状态枚举字面量
    core/src/agent/registry.rs —— :79-85 session_depth、:87 next_thread_spawn_depth（父 +1）、
        :91 exceeds_thread_spawn_depth_limit(depth, max) = depth > max
    core/src/config/mod.rs —— :247 DEFAULT_AGENT_MAX_DEPTH = 1（默认**只许一层**！）、
        :239-:241 wait 超时三档（min 10s / max 3600s / default 30s）、:1286 每会话并发上限
    agent-roles/src/ —— :10 AgentRoleConfig{config_file: Option<PathBuf>}、:38 解析角色文件；
        loader.rs :78 从 codex home 的 agents/ 目录发现；discovery.rs :7 递归收 *.toml
    protocol/src/agent_path.rs —— :15 AgentPath(newtype)、:18 ROOT="/root"、:19 MORPHEUS、
        :54 join、:127-:143 命名规则（小写字母数字下划线、禁 "root"、禁 "/"）
    protocol/src/items.rs —— :353 SubAgentActivityItem{id, kind, agent_thread_id, agent_path}
        —— 只有身份与**种类**，没有内容：子代理的推理与工具过程不进父上下文
    protocol/src/protocol.rs —— :4333 SubAgentActivityKind{Started, Interacted, Interrupted,
        Completed}；:1843 AgentStatus{PendingInit, Running, Interrupted, Completed(Option<String>),
        Errored, Shutdown, NotFound}

  四种投递/等待语义（本课的关节）
    spawn_agent     起一条新 thread，给它一个任务；返回路径，不返回过程
    send_message    投递到 mailbox，**不触发新回合**——等子代理在消息边界吸收
    followup_task   投递**并触发回合**：idle 就开新一轮；running 也在消息边界或
                    待决工具调用完成后送达（multi_agents_spec.rs :233 原文）
    wait_agent      等"活动"而不是等"内容"：mailbox 变化或终态通知；用户插话会提前
                    结束并给出 interruption 摘要；超时返回 timeout 摘要，**不是异常**

  Rust ↔ Python：tokio::spawn ↔ asyncio.create_task；tokio watch::channel ↔ asyncio.Queue
  （事件总线）；mpsc mailbox ↔ asyncio.Queue；Arc<Mutex<Registry>> ↔ 对象 + 事件循环独占；
  FunctionCallError::RespondToModel ↔ 把错误文本当工具结果回填给模型（不炸内核）。

运行：python code.py   （零依赖，离线；模型全部脚本化 Mock；wait 的真实时长按 1:1000 加速，
      clamp 与超时的**语义**不变）
对照真实源码：core/src/tools/handlers/multi_agents_v2/、core/src/agent/registry.rs、
             core/src/config/mod.rs、agent-roles/src/、protocol/src/{agent_path,items}.rs
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Union

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.mini_util import ToolCall, TurnOutput, force_utf8_stdout, sleep_ms

force_utf8_stdout()

TIME_SCALE = 1 / 1000.0          # 教学加速：真实 30s → 演示 30ms（三档 clamp 语义不变）
DEFAULT_AGENT_MAX_DEPTH = 1      # config/mod.rs:247
MIN_WAIT_MS, MAX_WAIT_MS, DEFAULT_WAIT_MS = 10_000, 3_600_000, 30_000   # config :239-:241
IDLE_GRACE_S = 0.02              # 空闲多久回收协程（名册记录保留，可被 followup 唤醒）


class SpawnError(Exception):
    """对应 collab_spawn_error（multi_agents_common.rs:84）：错误文本回给模型，不炸内核。"""


# ---------------------------------------------------------------
# AgentPath：路径寻址（protocol/src/agent_path.rs:15）
# ---------------------------------------------------------------


class AgentPath:
    ROOT = "/root"
    _NAME_OK = set("abcdefghijklmnopqrstuvwxyz0123456789_")

    def __init__(self, path: str):
        self.path = path

    @classmethod
    def root(cls) -> "AgentPath":
        return cls(cls.ROOT)

    def is_root(self) -> bool:
        return self.path == self.ROOT

    def name(self) -> str:
        return "root" if self.is_root() else self.path.rsplit("/", 1)[-1]

    def join(self, agent_name: str) -> "AgentPath":
        """对应 join（:54）：先过命名校验（:127-:143），再拼出绝对路径。"""
        if not agent_name:
            raise ValueError("agent path must not be empty")
        if agent_name == "root":
            raise ValueError("agent_name `root` is reserved")
        if "/" in agent_name:
            raise ValueError("agent_name must not contain `/`")
        if not set(agent_name) <= self._NAME_OK:
            raise ValueError("agent_name must use only lowercase letters, digits, and underscores")
        return AgentPath(f"{self.path}/{agent_name}")

    def resolve(self, reference: str) -> "AgentPath":
        """相对引用（如 "bob"、"../sister"）解析成绝对路径——send_message 收相对路径的依据。"""
        if reference.startswith("/"):
            return AgentPath(reference)
        base = self
        for part in reference.split("/"):
            if part == "..":
                base = AgentPath(base.path.rsplit("/", 1)[0] or self.ROOT)
            elif part:
                base = base.join(part)
        return base

    def __str__(self) -> str:
        return self.path


def session_depth(path: Optional[AgentPath]) -> int:
    """registry.rs:79-85：根会话 0，子 thread 用路径深度（/root/alice → 1）。"""
    if path is None:
        return 0
    return max(0, len([s for s in str(path).split("/") if s]) - 1)


# ---------------------------------------------------------------
# 角色与线程记录
# ---------------------------------------------------------------


@dataclass
class AgentRole:
    """agent-roles：角色 = 一层可叠在继承 config 之上的模板（AgentRoleConfig, :10）。"""

    name: str
    model: str = "gpt-5"
    instructions: str = ""
    config_file: Optional[str] = None      # 真实字段：Option<PathBuf>


@dataclass
class Agent:
    path: AgentPath
    depth: int
    role: AgentRole
    status: str = "pending_init"      # AgentStatus（protocol.rs:1843）的小写面
    mailbox: asyncio.Queue = field(default_factory=asyncio.Queue)
    history: List[tuple] = field(default_factory=list)
    result: Optional[str] = None
    steps: int = 0
    model: Optional["MiniModel"] = None
    task: Optional[asyncio.Task] = None


@dataclass
class Activity:
    """SubAgentActivityItem（items.rs:353）：只有身份与种类，**没有内容**。"""

    kind: str
    path: str
    note: str = ""

    def __str__(self) -> str:
        return f"{self.kind:<11} {self.path}" + (f"  ({self.note})" if self.note else "")


# ---------------------------------------------------------------
# 名册 + 两道闸（registry.rs 的 mini 版）
# ---------------------------------------------------------------


class Registry:
    def __init__(self, max_depth: int = DEFAULT_AGENT_MAX_DEPTH, max_concurrent: int = 2):
        self.agents: Dict[str, Agent] = {}
        self.max_depth = max_depth
        self.max_concurrent = max_concurrent

    def next_thread_spawn_depth(self, parent: AgentPath) -> int:              # registry.rs:87
        return session_depth(parent) + 1

    def exceeds_thread_spawn_depth_limit(self, depth: int) -> bool:           # registry.rs:91
        return depth > self.max_depth

    def live_count(self) -> int:
        return sum(1 for a in self.agents.values() if a.status in ("pending_init", "running"))


@dataclass
class WaitResult:
    """wait_agent 的返回：摘要，不是内容（wait.rs:139 from_outcome）。"""

    kind: str                      # "activity" | "timeout" | "interrupted"
    updates: List[str] = field(default_factory=list)
    note: str = ""

    def __str__(self) -> str:
        if self.kind == "timeout":
            return f"timeout（{self.note}）——超时是**返回值**，不是异常"
        if self.kind == "interrupted":
            return f"interrupted：用户插话提前结束等待（{self.note}）"
        return "activity: " + "; ".join(self.updates) + (f"  [{self.note}]" if self.note else "")


class Kernel:
    def __init__(self, roles: Dict[str, AgentRole], max_depth: int = DEFAULT_AGENT_MAX_DEPTH,
                 max_concurrent: int = 2, verbose: bool = True):
        self.roles = roles
        self.registry = Registry(max_depth=max_depth, max_concurrent=max_concurrent)
        self.events: asyncio.Queue = asyncio.Queue()      # tokio watch ↔ asyncio.Queue
        self.verbose = verbose

    def log(self, s: str) -> None:
        if self.verbose:
            print(f"  [kernel] {s}")

    # ---- 活动总线：父代理只看见这些 ----
    def emit(self, agent: Agent, kind: str, note: str = "") -> None:
        act = Activity(kind, str(agent.path), note)
        self.log(f"活动 ▶ {act}")
        self.events.put_nowait(act)

    # ---- spawn ----
    async def spawn_agent(self, task_name: str, task: str, role_name: str = "default",
                          from_path: Optional[AgentPath] = None,
                          model_script: Optional[List[Union[TurnOutput, Callable]]] = None,
                          fork_turns: str = "none") -> str:
        parent = from_path or AgentPath.root()
        child_depth = self.registry.next_thread_spawn_depth(parent)
        if self.registry.exceeds_thread_spawn_depth_limit(child_depth):
            raise SpawnError(
                f"thread spawn depth {child_depth} exceeds limit {self.registry.max_depth}"
                "（agents.max_depth，默认 1 = 只许一层）")
        if self.registry.live_count() >= self.registry.max_concurrent:
            raise SpawnError(
                f"concurrent threads limit reached ({self.registry.max_concurrent})"
                "——先等/先收（agents.max_concurrent_threads_per_session）")
        path = parent.join(task_name)
        role = self.roles.get(role_name) or self.roles["default"]
        ag = Agent(path=path, depth=child_depth, role=role)
        # apply_spawn_agent_role（multi_agents_common.rs:355）：角色叠在继承来的 config 之上
        ag.history.append(("instructions", f"[role={role.name}] {role.instructions}"))
        ag.model = MiniModel(model_script) if model_script else MiniModel(per_turn=research_turn)
        self.registry.agents[str(path)] = ag
        self.log(f"spawn {path} role={role.name} model={role.model} fork_turns={fork_turns}"
                 f"（继承父 config 再叠角色）→ 子 thread 建立，父只拿到路径")
        ag.status = "running"
        self.emit(ag, "Started", f"task={task[:14]}…")
        ag.task = asyncio.create_task(self._agent_loop(ag, task))
        return str(path)

    # ---- 两种投递 ----
    def send_message(self, ref: str, message: str, from_path: Optional[AgentPath] = None) -> str:
        target = self._resolve(ref, from_path)
        target.mailbox.put_nowait(message)        # 不触发回合：等它在消息边界吸收
        return (f"send_message → {target.path} 已入队（mailbox={target.mailbox.qsize()}），"
                f"不触发新回合")

    async def followup_task(self, ref: str, task: str) -> str:
        target = self._resolve(ref, None)
        target.mailbox.put_nowait(task)
        if target.task is None or target.task.done():
            target.status = "running"
            target.task = asyncio.create_task(self._agent_loop(target, None))
            return (f"followup_task → {target.path} 原已空闲（status={target.status}），"
                    f"入队并**开新回合**")
        return (f"followup_task → {target.path} 正在运行，任务在**消息边界或待决工具调用完成后**"
                f"送达（mailbox={target.mailbox.qsize()}）")

    async def interrupt_agent(self, ref: str) -> str:
        target = self._resolve(ref, None)
        previous = target.status
        if target.task and not target.task.done():
            target.task.cancel()
            target.status = "interrupted"
            self.emit(target, "Interrupted", f"前态 {previous}")
        return f"interrupt_agent {target.path}：前态 {previous} → interrupted"

    def list_agents(self) -> List[str]:
        return [f"{a.path}  depth={a.depth}  role={a.role.name}  status={a.status}  steps={a.steps}"
                for a in self.registry.agents.values()]

    def steer(self, text: str) -> None:
        """用户在活跃回合里插话：wait 提前结束并给出 interruption 摘要（multi_agents_spec.rs:283 描述）。"""
        self.events.put_nowait(Activity("Steered", AgentPath.ROOT, text))

    def _resolve(self, ref: str, from_path: Optional[AgentPath]) -> Agent:
        path = AgentPath(ref) if ref.startswith("/") else (from_path or AgentPath.root()).resolve(ref)
        ag = self.registry.agents.get(str(path))
        if ag is None:
            raise SpawnError(f"unknown agent {path}（resolve_agent_target 解析失败）")
        return ag

    # ---- wait：等"活动"，三档 clamp ----
    async def wait_agent(self, timeout_ms: Optional[int] = None, want: int = 1) -> WaitResult:
        if timeout_ms is not None and timeout_ms > MAX_WAIT_MS:
            raise SpawnError(f"timeout_ms must be at most {MAX_WAIT_MS}")
        ms = DEFAULT_WAIT_MS if timeout_ms is None else max(timeout_ms, MIN_WAIT_MS)
        if timeout_ms is not None and timeout_ms < MIN_WAIT_MS:
            self.log(f"请求 {timeout_ms}ms 被抬到下限 {MIN_WAIT_MS}ms（wait.rs:63）")
        collected: List[str] = []
        terminals = 0
        loop = asyncio.get_running_loop()
        until = loop.time() + ms * TIME_SCALE
        while True:
            remaining = until - loop.time()
            if remaining <= 0:
                return WaitResult("timeout", collected,
                                  note=f"{ms}ms（演示按 1:{int(1 / TIME_SCALE)} 加速）内无新活动")
            try:
                act: Activity = await asyncio.wait_for(self.events.get(), min(remaining, 0.004))
            except asyncio.TimeoutError:
                continue
            if act.kind == "Steered":
                return WaitResult("interrupted", collected, note=f"用户插话：{act.note}")
            collected.append(f"{act.kind} {act.path}")
            if act.kind in ("Completed", "Interrupted"):
                terminals += 1
            if terminals >= want:
                return WaitResult("activity", collected, note=f"收到 {terminals} 个终态通知")

    # ---- 子代理的回合循环：mini run_turn ----
    async def _agent_loop(self, ag: Agent, first_task: Optional[str]) -> None:
        queue: List[str] = [first_task] if first_task else []
        while True:
            while not ag.mailbox.empty():                 # 消息边界吸收 mailbox
                queue.append(ag.mailbox.get_nowait())
                self.emit(ag, "Interacted", "mailbox 在消息边界被吸收")
            if not queue:
                try:
                    queue.append(await asyncio.wait_for(ag.mailbox.get(), IDLE_GRACE_S))
                    self.emit(ag, "Interacted", "空闲期被消息唤醒")
                except asyncio.TimeoutError:
                    return                               # 协程退出；名册记录与 status 保留
            await self._run_turn(ag, queue.pop(0))

    async def _run_turn(self, ag: Agent, task_text: str) -> None:
        """一个回合：采样 →（工具 → 回填）→ 直到出文本。过程**留在子 thread**。"""
        ag.history.append(("user", task_text))
        step_in_turn = 0
        while True:
            step_in_turn += 1
            ag.steps += 1
            assert ag.model is not None
            out: TurnOutput = await ag.model.sample(ag.history, step_in_turn)
            if out.tool_calls:
                for c in out.tool_calls:
                    if c.name == "spawn_agent":
                        try:
                            await self.spawn_agent(c.arguments["task_name"], c.arguments["task"],
                                                   from_path=ag.path)
                            ag.history.append(("tool", "ok"))
                        except SpawnError as e:
                            ag.history.append(("tool", f"ERROR: {e}"))
                            self.log(f"↺ {ag.path} 的 spawn_agent 被拒，错误文本回填给模型")
                    else:
                        ag.history.append(("tool", f"{c.name} → 3 条结果"))
                        self.log(f"    ⸨{ag.path.name()}⸩ 第 {ag.steps} 步调用 {c.name}（父不可见）")
            elif out.text is not None:
                ag.result = out.text
                ag.history.append(("assistant", out.text))
                ag.status = "completed"                   # AgentStatus::Completed(Option<String>)
                self.emit(ag, "Completed", f"结论={ag.result[:22]}…")
                return


# ---------------------------------------------------------------
# 脚本化模型
# ---------------------------------------------------------------


class MiniModel:
    """两种用法：script（逐幕给，演完就收尾）或 per_turn(step, context)（每回合可重演）。"""

    def __init__(self, script: Optional[List[Union[TurnOutput, Callable]]] = None,
                 per_turn: Optional[Callable[[int, List[tuple]], TurnOutput]] = None):
        self.script, self.cursor, self.per_turn = script or [], 0, per_turn

    async def sample(self, context: List[tuple], step_in_turn: int) -> TurnOutput:
        await sleep_ms(8)
        if self.per_turn is not None:
            return self.per_turn(step_in_turn, context)
        if self.cursor >= len(self.script):
            return TurnOutput(text="（剧本已尽）")
        item = self.script[self.cursor]
        self.cursor += 1
        return item(context) if callable(item) else item


def research_turn(step_in_turn: int, context: List[tuple]) -> TurnOutput:
    """研究型子代理：第一步检索，第二步出结论（每回合都照这个形状重演）。"""
    if step_in_turn == 1:
        return TurnOutput(tool_calls=[ToolCall(f"c{len(context)}", "web_search",
                                               {"q": _last_user(context)[:16]})])
    return TurnOutput(text=f"结论：{_last_user(context)[:16]} → 3 条证据，建议见正文")


def _last_user(context: List[tuple]) -> str:
    return next((v for k, v in reversed(context) if k == "user"), "")


async def settle(kernel: Kernel) -> None:
    """等本场景所有子 thread 落定，避免输出串到下一场景。"""
    pending = [a.task for a in kernel.registry.agents.values() if a.task and not a.task.done()]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


# ---------------------------------------------------------------
# 演示
# ---------------------------------------------------------------


async def main() -> None:
    roles = {
        "default": AgentRole("default", model="gpt-5", instructions="按需使用工具"),
        "researcher": AgentRole("researcher", model="gpt-5-mini",
                                instructions="只检索汇总", config_file="~/.codex/agents/researcher.toml"),
    }

    print("== 场景 1：spawn 是模型会调的一个工具 —— 起一条子 thread，只拿路径 ==")
    k = Kernel(roles)
    p = await k.spawn_agent("alice", "调研 2026 年 agent harness 的安全机制",
                            role_name="researcher", from_path=AgentPath.root())
    print(f"    wait_agent → {await k.wait_agent()}")
    alice = k.registry.agents[p]
    print(f"    父可见：路径 {p}、活动标记、结论 {alice.result!r}")
    print(f"    父不可见：子 thread 内部 {alice.steps} 步（含 1 次 web_search）"
          "——SubAgentActivityItem 只带 kind（items.rs:353）")
    await settle(k)

    print("\n== 场景 2：send_message vs followup_task —— 两种投递，两种触发 ==")
    k2 = Kernel(roles, max_concurrent=5)
    p2 = await k2.spawn_agent("bob", "写一份周报大纲", role_name="researcher")
    await sleep_ms(2)                                  # 让 bob 进入采样中
    print("    " + k2.send_message(p2, "附带：记得对齐季度目标"))
    print("    ↑ 只入队、不触发回合（spec.rs:200）；bob 在下一个消息边界吸收")
    print("    " + await k2.followup_task(p2, "再补一条：风险项"))
    print("    ↑ spec.rs:233：idle 则开新回合，running 则在消息/工具边界送达")
    await settle(k2)
    bob = k2.registry.agents[p2]
    print(f"    bob 落定：status={bob.status} 内部步数={bob.steps} "
          f"回合数={sum(1 for k_, _ in bob.history if k_ == 'user')}")

    print("\n== 场景 3：并发扇出、插话与名册 ==")
    k3 = Kernel(roles, max_concurrent=6, verbose=False)
    for name in ("carol", "dave", "erin"):
        await k3.spawn_agent(name, f"任务 {name}", role_name="researcher")
    got = await k3.wait_agent(want=3)
    print(f"    三条子 thread 并发：{got}")
    k3.steer("用户：先别管 dave")
    print(f"    再等一次，插话先到 → {await k3.wait_agent()}")
    await settle(k3)
    print("    " + "\n    ".join(k3.list_agents()))

    print("\n== 场景 4：agent-roles —— 角色改变装配（model / 指令 / 配置文件） ==")
    k4 = Kernel(roles, max_concurrent=3)
    a = await k4.spawn_agent("frank", "任务", role_name="default")
    b = await k4.spawn_agent("grace", "任务", role_name="researcher")
    await settle(k4)
    for path in (a, b):
        ag = k4.registry.agents[path]
        print(f"    {path}: model={ag.role.model} config_file={ag.role.config_file} "
              f"注入={ag.history[0][1][:26]}… 结论={ag.result!r}")
    print("    → 真实侧：agents/ 目录发现 *.toml（loader.rs:78 / discovery.rs:7），"
          "spawn 时角色层叠在继承来的 config 上（multi_agents_common.rs:355）")

    print("\n== 场景 5：深度闸 —— 默认 max_depth=1，子代理不许再开子代理 ==")
    k5 = Kernel(roles, max_concurrent=3)
    deep_script = [TurnOutput(tool_calls=[ToolCall("s1", "spawn_agent",
                                                   {"task_name": "ivan", "task": "子任务"})]),
                   lambda ctx: TurnOutput(text="收到深度限制，我自己来")]
    p5 = await k5.spawn_agent("heidi", "尝试再派活", model_script=deep_script)
    await settle(k5)
    heidi = k5.registry.agents[p5]
    tool_row = next(v for kk, v in heidi.history if kk == "tool")
    print(f"    工具回填：{tool_row[:58]!r}")
    print(f"    它的最终结论：{heidi.result!r}")
    print("    → 拒绝发生在 spawn_agent 内部，错误当**工具结果**回给模型（RespondToModel 语义）")

    print("\n== 场景 6：并发闸 + wait 三档 clamp（失败路径） ==")
    k6 = Kernel(roles, max_concurrent=2, verbose=False)
    await k6.spawn_agent("judy", "任务")
    await k6.spawn_agent("ken", "任务")
    try:
        await k6.spawn_agent("lisa", "任务")
    except SpawnError as e:
        print(f"    SpawnError: {e}")
    try:
        await k6.wait_agent(MAX_WAIT_MS + 1)
    except SpawnError as e:
        print(f"    SpawnError: {e}（wait.rs:58-61 的上限拒绝）")
    quiet = Kernel(roles, verbose=False)
    print(f"    无活动可等：wait_agent(1000) → {await quiet.wait_agent(1_000)}")
    print("    → 下限 clamp 生效（1000ms → 10s），到点返回 timeout 摘要：不是异常，模型可再等")
    await settle(k6)

    print("\n== 场景 7：命名空间 —— v1 与 v2 是两套工具面 ==")
    v1 = ["multi_agent_v1.spawn_agent", "multi_agent_v1.send_input", "multi_agent_v1.wait_agent",
          "multi_agent_v1.resume_agent", "multi_agent_v1.close_agent"]
    v2 = ["spawn_agent", "send_message", "followup_task", "wait_agent", "list_agents",
          "interrupt_agent"]
    print(f"    V1（namespace，multi_agents_spec.rs:14）: {v1}")
    print(f"    V2（plain，spec_plan.rs:645 分支）      : {v2}")
    print("    → 换代写在工具名上：v1 用 id + resume/close，v2 用 AgentPath + interrupt，"
          "并把'派任务'与'递消息'拆成两个动词")

    print("\n结论：子代理是**内核里的另一条 thread**，入口是模型的一次工具调用；")
    print("父可见的是路径 + 活动 + 结论，不可见的是过程——深度/并发两道闸 + 四种投递等待语义。")


if __name__ == "__main__":
    asyncio.run(main())
