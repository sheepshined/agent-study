# -*- coding: utf-8 -*-
"""
s10_capstone/code.py —— 收官：把九课的零件装回一台整机，并与八家 harness 横向对照

前九课每课只点亮一个机制；这一课全部点亮在同一个引擎里跑一个"研究型 agent"：

    通道(s01) → 超步(s02) → 写入合并(s03) → 存档(s04) → 时间旅行(s05)
              → 中断/恢复(s06) → 子图(s07) → Send 扇出(s08) → Command 交接(s09)

  真实源码锚点（快照 7daa3ab，行号本册逐条 sed 实测；本仓带中文导读注释的文件
  行号比上游下移约 12 行）：
    pregel/_algo.py:331        每拍写入前调通道 update（s03 的落点）
    pregel/main.py:2979        runner.tick(..., schedule_task=loop.accept_push)（s08 的扇出入口）
    pregel/_loop.py:434-446    NULL 任务写入累加（s09 的输入补丁）
    checkpoint/base/__init__.py  get_next_version / get_tuple / list（s04、s05）
    types.py:732 / :827         Send 与 Command（s08、s09）
    graph/state.py:110          _CHANNEL_BRANCH_TO = "branch:to:{}"（路由即通道）
    errors.py:50/102/129        GraphBubbleUp 家族：GraphInterrupt / ParentCommand（跨层同一种机制）

  LangGraph 的立场（收官一句话）：**它是编排引擎，不是 agent 产品**。
  它把"状态怎么合、拍怎么走、怎么存档、怎么中断、怎么扇出、怎么交接"做成通用原语，
  agent 只是这些原语的一种用法（`create_agent` 那套在 07-langchain 的 s01/s04）。

运行：python code.py    （零依赖，离线）
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.mini_util import banner, expect_error, fmt_state, force_utf8_stdout, next_version, uid, NULL_VERSION

force_utf8_stdout()

START, END = "__start__", "__end__"
TASKS, RESUME = "__tasks__", "__resume__"
BRANCH_TO = "branch:to:{}"


# ---------------------------------------------------------------
# 公共类型：Command / Send / 冒泡异常
# ---------------------------------------------------------------


@dataclass
class Send:
    node: str
    arg: Any = None


@dataclass
class Command:
    graph: Optional[str] = None
    update: Optional[Any] = None
    resume: Optional[Any] = None
    goto: Any = ()
    PARENT = "__parent__"


class GraphInterrupt(Exception):
    def __init__(self, prompt):
        super().__init__(f"interrupt: {prompt!r}")
        self.prompt = prompt


class ParentCommand(Exception):
    def __init__(self, command: Command):
        super().__init__(repr(command))
        self.command = command


class InvalidUpdateError(Exception):
    pass


# ---------------------------------------------------------------
# 通道（s01）
# ---------------------------------------------------------------


class LastValue:
    def __init__(self, key):
        self.key, self.value, self.version = key, None, None

    def update(self, values):
        if not values:
            return False
        if len(values) > 1:
            raise InvalidUpdateError(f"{self.key}: 同拍 {len(values)} 写，听谁的？")
        self.value = values[0]
        return True

    def get(self):
        return self.value


class Reducer:
    def __init__(self, key, fn):
        self.key, self.fn, self.value, self.version = key, fn, None, None

    def update(self, values):
        if not values:
            return False
        if self.value is None:
            self.value, values = values[0], values[1:]
        for v in values:
            self.value = self.fn(self.value, v)
        return True

    def get(self):
        return self.value


class Ephemeral:
    """branch:to:X 用的通道：一次性信号（state.py:1543 EphemeralValue(guard=False)）。"""

    def __init__(self, key):
        self.key, self.value, self.version = key, None, None

    def update(self, values):
        if not values:
            return False
        self.value = values[-1]
        return True

    def get(self):
        return self.value


# ---------------------------------------------------------------
# 存档（s04）与检查点
# ---------------------------------------------------------------


@dataclass
class Checkpoint:
    id: str
    step: int
    values: Dict[str, Any]
    versions_seen: Dict[str, Dict[str, int]]
    channel_versions: Dict[str, int] = field(default_factory=dict)
    pending_writes: List[tuple] = field(default_factory=list)
    next_node: Optional[str] = None     # mini 用它记录"挂起在哪个节点"（真实由 pending writes 表达）


class MemorySaver:
    def __init__(self):
        self.by_thread: Dict[str, List[Checkpoint]] = {}

    def put(self, thread: str, cp: Checkpoint) -> None:
        self.by_thread.setdefault(thread, []).append(cp)

    def list(self, thread: str) -> List[Checkpoint]:
        return self.by_thread.get(thread, [])

    def get_tuple(self, thread: str, cp_id: Optional[str] = None) -> Optional[Checkpoint]:
        chain = self.by_thread.get(thread, [])
        if not chain:
            return None
        if cp_id is None:
            return chain[-1]
        return next((c for c in chain if c.id == cp_id), None)


# ---------------------------------------------------------------
# 引擎：超步（s02）+ 写入合并（s03）+ 中断（s06）+ 扇出（s08）+ 交接（s09）
# ---------------------------------------------------------------


@dataclass
class Node:
    name: str
    fn: Callable[[Dict[str, Any], "Pregel"], Any]
    extra_triggers: List[str] = field(default_factory=list)

    @property
    def triggers(self):
        return [BRANCH_TO.format(self.name), *self.extra_triggers]


class Pregel:
    def __init__(self, nodes: List[Node], keys: Dict[str, Optional[Callable]],
                 saver: Optional[MemorySaver] = None, recursion_limit: int = 25,
                 namespace: str = "", parent: Optional["Pregel"] = None,
                 logger: Optional[Callable[[str], None]] = None):
        self.nodes = {n.name: n for n in nodes}
        self.channels: Dict[str, Any] = {START: Ephemeral(START), RESUME: LastValue(RESUME)}
        for n in nodes:
            self.channels[BRANCH_TO.format(n.name)] = Ephemeral(BRANCH_TO.format(n.name))
        for k, fn in keys.items():
            self.channels[k] = Reducer(k, fn) if fn else LastValue(k)
        self.keys = keys
        self.saver = saver or MemorySaver()
        self.recursion_limit = recursion_limit
        self.namespace, self.parent = namespace, parent
        self.log = logger or (lambda s: print(f"    {s}"))
        self.versions_seen: Dict[str, Dict[str, int]] = {n.name: {} for n in nodes}
        self.step = 0
        self.resume_values: List[Any] = []
        self.thread = "t-" + uid("th")[3:]

    # ---- 状态视图 ----
    def view(self) -> Dict[str, Any]:
        return {k: c.get() for k, c in self.channels.items()
                if not k.startswith(("branch:to:", "__")) and c.get() is not None}

    # ---- 拍 ----
    def _should_trigger(self, node: Node) -> bool:
        for chan in node.triggers:
            ch = self.channels.get(chan)
            if ch is None or ch.version is None:
                continue
            if ch.version > self.versions_seen[node.name].get(chan, NULL_VERSION):
                return True
        return False

    def tick_tasks(self) -> List[Node]:
        if self.step >= self.recursion_limit:
            raise RecursionError(f"达到 recursion_limit={self.recursion_limit}：图里有环没出口")
        return [n for n in self.nodes.values() if self._should_trigger(n)]

    # ---- 写入合并（_algo.py:331 的位置） ----
    def apply_writes(self, writes: List[tuple]) -> None:
        by_chan: Dict[str, List[Any]] = {}
        for chan, val in writes:
            if chan not in self.channels:
                self.channels[chan] = LastValue(chan)
            by_chan.setdefault(chan, []).append(val)
        for chan, vals in by_chan.items():
            if self.channels[chan].update(vals):
                self.channels[chan].version = next_version(self.channels[chan].version)

    def _record_seen(self, tasks: List[Node]) -> None:
        for n in tasks:
            for chan in n.triggers:
                ch = self.channels.get(chan)
                if ch is not None and ch.version is not None:
                    self.versions_seen[n.name][chan] = ch.version

    # ---- Command 的拆解（s09） ----
    def map_command(self, cmd: Command) -> List[tuple]:
        writes: List[tuple] = []
        if cmd.graph == Command.PARENT:
            raise InvalidUpdateError("There is no parent graph")
        for go in (cmd.goto if isinstance(cmd.goto, (list, tuple)) else [cmd.goto] if cmd.goto else []):
            if isinstance(go, Send):
                writes.append((TASKS, go))
            elif go != END:
                writes.append((BRANCH_TO.format(go), START))
        if cmd.resume is not None:
            writes.append((RESUME, cmd.resume))
        if cmd.update:
            writes.extend(cmd.update.items() if isinstance(cmd.update, dict) else [("__root__", cmd.update)])
        return writes

    def control_branch(self, value: Any) -> List[tuple]:
        if isinstance(value, Send):
            return [(TASKS, value)]
        cmds = [value] if isinstance(value, Command) else \
            [v for v in value if isinstance(v, Command)] if isinstance(value, (list, tuple)) else []
        rtn: List[tuple] = []
        for cmd in cmds:
            if cmd.graph == Command.PARENT:
                raise ParentCommand(cmd)
            for go in ([cmd.goto] if isinstance(cmd.goto, (str, Send)) else list(cmd.goto or [])):
                if isinstance(go, Send):
                    rtn.append((TASKS, go))
                elif go != END:
                    rtn.append((BRANCH_TO.format(go), None))
        return rtn

    def get_updates(self, value: Any) -> List[tuple]:
        if isinstance(value, Command):
            if value.graph == Command.PARENT:
                return []
            return list(value.update.items()) if isinstance(value.update, dict) else []
        if isinstance(value, dict):
            return list(value.items())
        return []

    # ---- 中断与恢复（s06） ----
    def interrupt(self, prompt: Any) -> Any:
        if not self.resume_values:
            raise GraphInterrupt(prompt)
        return self.resume_values.pop(0)     # 顺序配对，消费一次（types.py:1006-1018）

    # ---- 主循环 ----
    def invoke(self, source: Union[dict, Command, None] = None) -> Dict[str, Any]:
        if isinstance(source, Command):
            if source.resume is not None:
                # 恢复：记下恢复值 + 重新触发挂起的节点（真实由 checkpoint 的 pending writes 决定）
                self.resume_values = list(source.resume) \
                    if isinstance(source.resume, (list, tuple)) else [source.resume]
                writes = self.map_command(source)
                if self._suspended() in self.nodes:
                    writes.append((BRANCH_TO.format(self._suspended()), START))
                self._run(writes)
                return self.view()
            self._run(self.map_command(source))
            return self.view()
        self._run([(START, None), *(source or {}).items()])
        return self.view()

    def _suspended(self) -> Optional[str]:
        if getattr(self, "_force_next", None):
            return self._force_next
        last = self.saver.get_tuple(self.thread)
        return last.next_node if last else None

    def _run(self, initial_writes: List[tuple]) -> None:
        if initial_writes:
            self.apply_writes(initial_writes)
            self._checkpoint()
        while True:
            tasks = self.tick_tasks()
            if not tasks:
                self.log("无任务可跑 → 本轮结束")
                return
            self.step += 1
            self.log(f"超步 {self.step}：任务 {[n.name for n in tasks]}")
            self._checkpoint()
            all_writes: List[tuple] = []
            for node in tasks:
                state = self.view()
                try:
                    out = node.fn(state, self)
                    writes = self.get_updates(out) + self.control_branch(out)
                except GraphInterrupt as gi:
                    self.log(f"⏸ {node.name} 挂起：{gi}")
                    self._record_seen(tasks)
                    self._checkpoint(next_node=node.name)
                    return
                except ParentCommand as pc:
                    targets = [pc.command.goto] if isinstance(pc.command.goto, (str, Send)) \
                        else list(pc.command.goto or [])
                    if not any(isinstance(t, str) and t in self.nodes for t in targets):
                        raise
                    self.log(f"↟ {node.name} 交来的 Command 在本图落地：goto={pc.command.goto!r}")
                    all_writes.extend(self.map_command(replace(pc.command, graph=None, resume=None)))
                    self._record_seen(tasks)
                    continue
                for s in [v for c, v in writes if c == TASKS]:      # s08：同拍 pushed 任务
                    target = self.nodes[s.node]
                    self.log(f"  pushed {s.node}（私有输入 {s.arg}）")
                    all_writes.extend(self.get_updates(target.fn(s.arg, self)))
                all_writes.extend((c, v) for c, v in writes if c != TASKS)
            self._record_seen(tasks)
            self.apply_writes(all_writes)
            self._checkpoint()

    def _checkpoint(self, next_node: Optional[str] = None) -> None:
        self.saver.put(self.thread, Checkpoint(
            id=uid("ckpt"), step=self.step, values=self.view(),
            versions_seen={k: dict(v) for k, v in self.versions_seen.items()},
            channel_versions={k: c.version or NULL_VERSION for k, c in self.channels.items()},
            next_node=next_node))

    # ---- 时间旅行（s05） ----
    def history(self) -> List[Checkpoint]:
        return self.saver.list(self.thread)

    def fork(self, cp_id: str, update: Optional[dict] = None,
              trigger_node: Optional[str] = None) -> "Pregel":
        """回到某个检查点重建一台引擎（可选改写状态、指定从哪个节点继续）。"""
        cp = self.saver.get_tuple(self.thread, cp_id)
        if cp is None:
            raise KeyError(f"checkpoint {cp_id} 不存在")
        fresh = Pregel([Node(n.name, n.fn, n.extra_triggers) for n in self.nodes.values()],
                      dict(self.keys), saver=self.saver, recursion_limit=self.recursion_limit,
                      namespace=self.namespace, parent=self.parent, logger=self.log)
        fresh.step = cp.step
        fresh.versions_seen = {k: dict(v) for k, v in cp.versions_seen.items()}
        # 通道值与版本号都按存档原样恢复（真实 Checkpoint 里就带 channel_versions）；
        # 只对本次改写的键推进版本——否则会把不该重跑的前驱也唤醒
        for k, v in cp.values.items():
            if k in fresh.channels:
                fresh.channels[k].value = v
                fresh.channels[k].version = cp.channel_versions.get(k)
        for k, v in (update or {}).items():
            fresh.channels.setdefault(k, LastValue(k))
            fresh.channels[k].value = v
            fresh.channels[k].version = next_version(fresh.channels[k].version)
        target = trigger_node or cp.next_node
        if target in fresh.nodes:          # 让挂起的那个节点重新被触发（真实由 pending writes 决定）
            fresh.versions_seen.setdefault(target, {})[BRANCH_TO.format(target)] = NULL_VERSION
        fresh._force_next = target
        fresh.thread = self.thread + "#fork"
        return fresh


# ---------------------------------------------------------------
# 一台整机：研究型 agent（模型节点 → 审批门 → 工具扇出 → 汇总；外加一个子图交接）
# ---------------------------------------------------------------


class ScriptedModel:
    """脚本化模型：第 1 次扇出三个主题并行检索（s08），第 2 次综合。"""

    def __init__(self):
        self.calls = 0

    def __call__(self, state: Dict[str, Any], g: Pregel):
        self.calls += 1
        if self.calls == 1:
            return Command(update={"messages": ["规划：三个主题并行检索"]},
                           goto=[Send("research", {"topic": t}) for t in ("沙箱", "存档", "交接")])
        return Command(update={"messages": [f"综合 {len(state.get('notes', []))} 份笔记，出结论"]},
                       goto="approval")


def notes_reducer(a, b):
    return (a or []) + ([b] if not isinstance(b, list) else b)


def build_graph(logger=None) -> Pregel:
    def research(state, g):
        """pushed 任务：拿私有输入（s08），写 reducer 通道 notes（s03 的合并）。"""
        topic = state.get("topic") if isinstance(state, dict) and "topic" in state else None
        return {"notes": [f"关于{topic or state}的笔记"]}

    def synthesize(state, g):
        """监听 notes 通道：扇入之后才跑（s02 的版本差分）。"""
        return Command(goto="model")

    def approval(state, g):
        answer = g.interrupt("要发布吗？（人在环，s06）")
        return Command(update={"messages": [f"人答：{answer}"]},
                       goto="handoff" if answer == "转交" else END)

    def handoff(state, g):
        """子图（s07）里的 worker 决定交棒给父图的 writer：一条 Command(graph=PARENT)。"""
        sub = Pregel([Node("worker", lambda s, gg: Command(
            update={"messages": ["worker 干完，交棒"]}, goto="writer", graph=Command.PARENT),
            extra_triggers=[START])], {"messages": notes_reducer},
            namespace="agent-sub", parent=g, logger=lambda s: g.log(f"  ⌙ 子图：{s}"))
        sub.invoke({})                        # ParentCommand 从这里冒到本引擎
        return {}

    def writer(state, g):
        return Command(update={"messages": ["writer 收尾"]}, goto=END)

    nodes = [Node("model", ScriptedModel(), extra_triggers=[START]),
             Node("research", research),
             Node("synthesize", synthesize, extra_triggers=["notes"]),
             Node("approval", approval), Node("handoff", handoff), Node("writer", writer)]
    keys = {"messages": notes_reducer, "notes": notes_reducer, "topic": None}
    return Pregel(nodes, keys, logger=logger)


# ---------------------------------------------------------------
# 演示
# ---------------------------------------------------------------


def scenario_assembly() -> Pregel:
    banner("场景 1：机制总装 —— 一张图用到九课的全部机制")
    print("    通道(s01) · 超步(s02) · 写入合并(s03) · 存档(s04) · 中断(s06) · 子图(s07) · Send(s08) · Command(s09)")
    g = build_graph()
    print(f"    拓扑：{' → '.join(g.nodes)} ＋ 条件/命令边若干（触发靠 branch:to:* 版本差分）")
    out = g.invoke({"topic": None})
    print(f"    首轮结果（挂起在审批）：{fmt_state(out)}")
    return g


def scenario_resume(g: Pregel) -> None:
    banner("场景 2：恢复 → 交接 → 冒泡到本图落地")
    out = g.invoke(Command(resume="转交"))
    print(f"    resume 后：{fmt_state(out)}")
    print(f"    存档 {len(g.history())} 份，最后一条 next_node={g.history()[-1].next_node}")
    print("    → 审批（s06）与交接（s09）在同一次恢复里连起来跑：interrupt 之前只有规划，没有发布")


def scenario_time_travel(g: Pregel) -> None:
    banner("场景 3：时间旅行 —— 回到挂起处，换一个答复走另一条结局")
    suspended = next(c for c in g.history() if c.next_node == "approval")
    print(f"    选中检查点 {suspended.id}（step={suspended.step}，next_node={suspended.next_node}）")
    print(f"    当时的状态：{fmt_state(suspended.values)}")
    forked = g.fork(suspended.id, update={"notes": g.view()["notes"] + ["临时补一条：审计要求"]})
    forked.invoke(Command(resume="直接发布"))
    print(f"    分叉结局：{fmt_state(forked.view())}")
    print("    → 注意超步 5 同时跑了 synthesize：改 notes 就把它的下游唤醒了，版本差分不讲情面")
    print(f"    → 主线历史不受影响（{g.thread} {len(g.history())} 份 / 分叉 {forked.thread} "
          f"{len(forked.history())} 份）——同一条历史可以长出两个未来（s05）")


def scenario_failure_paths() -> None:
    banner("场景 4：两条失败路径（引擎的边界条件）")
    loop_nodes = [Node("ping", lambda s, g: Command(goto="pong"), extra_triggers=[START]),
                  Node("pong", lambda s, g: Command(goto="ping"))]
    g = Pregel(loop_nodes, {"x": None}, recursion_limit=6)
    expect_error("环里没有出口", lambda: g.invoke({}), RecursionError)
    print("    → 真实同款：GraphRecursionError（errors.py:67），recursion_limit 是唯一兜底")

    two_writers = [Node("a", lambda s, g: {"hit": 1}, extra_triggers=[START]),
                   Node("b", lambda s, g: {"hit": 2}, extra_triggers=[START])]
    g2 = Pregel(two_writers, {"hit": None})
    expect_error("LastValue 同拍双写", lambda: g2.invoke({}), InvalidUpdateError)
    print("    → 要并存就声明 reducer（s01）；引擎不替你猜（_algo.py:331 的位置）")


def scenario_cross_compare() -> None:
    banner("场景 5：收官横向对照 —— 五家 harness 的同一层抽象")
    rows = [
        ("执行单元", "超步 + 通道版本差分（本册 s01-s03）", "回合 run_turn + 一次一快照（Codex s01）",
         "while 循环写死（Claude Code）", "插件装配出的 loop（dsh s02）", "编译成图的 agent（LangChain s01）"),
        ("状态载体", "通道（reducer 决定合并）", "rollout JSONL 可重放", "会话消息列表", "session 日志", "StateGraph schema"),
        ("人在环", "interrupt + Command(resume)", "AskForApproval × SandboxPolicy", "工具前确认", "插件提供审批", "middleware 钩子"),
        ("扩展点", "节点/边/reducer/checkpointer", "工具 handler + MCP + 角色 toml", "改代码", "一切皆插件", "中间件七钩子"),
        ("多智能体", "Send 扇出 + Command.PARENT 交接", "同内核多 thread，活动与结论跨边界", "子任务并行", "委派插件", "subgraph + handoff 工具"),
        ("一句话", "低层编排引擎：给原语不给观点", "工业化与安全做到极致", "简单即正确", "可组装做到极致", "声明进、图出"),
    ]
    head = ["维度", "LangGraph", "Codex", "Claude Code", "dsh", "LangChain"]
    for row in rows:
        print(f"    【{row[0]}】")
        for name, cell in zip(head[1:], row[1:]):
            print(f"      {name:<11}：{cell}")
    print("    参考：07-langchain（编译路线）、02-codex（服务化路线）、03-deepseek-harness（插件路线）、"
          "01-claude-code（极简循环路线）、04-zcode / 05-openclaw / 06-opencode（终端产品路线）")


def main() -> None:
    g = scenario_assembly()
    scenario_resume(g)
    scenario_time_travel(g)
    scenario_failure_paths()
    scenario_cross_compare()
    print("\n结论：LangGraph 的整机 = 通道 + 版本差分 + 一次性写入合并 + 可重放存档；")
    print("中断、扇出、交接全是同一套原语的用法。看懂原语，任何 agent 拓扑都是它的一种写法。")


if __name__ == "__main__":
    main()
