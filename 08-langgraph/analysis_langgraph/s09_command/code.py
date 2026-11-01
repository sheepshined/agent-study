# -*- coding: utf-8 -*-
"""
s09_command/code.py —— Command：状态更新 + 走向 + 恢复值，一次说完

s08 的 Send 让**边**能长出新任务；Command 让**节点返回值**同时表达三件事：
改状态（update）、去哪儿（goto）、拿什么继续跑（resume）。它是多 agent 交接的语法。

    class Command(Generic[N], ToolOutputMixin):        # types.py:827（实测）
        graph: str | None = None                      # :849  None=当前图；Command.PARENT=最近的父图
        update: Any | None = None                     # :850  写进状态的增量
        resume: dict[str, Any] | Any | None = None    # :851  恢复 interrupt 的值
        goto: Send | Sequence[Send | N] | N = ()      # :852  节点名 / Send / 它们的序列
        PARENT: ClassVar = "__parent__"               # :876

三条落地路径（都实测过行号）：
  ① 节点返回的 Command → 拆成两笔写入：
     update 走 `_get_updates`（graph/state.py:1477-1484：graph==PARENT 就**不回写本图**），
     goto 走 `_control_branch`（graph/state.py:1763-:1789）：字符串 → 写
     `branch:to:{node}` 通道（模板 :110，通道类型 EphemeralValue，见 :1538-:1546 的 triggers）；
     Send → (TASKS, send) 走 s08 的 push；graph==PARENT → `raise ParentCommand(command)`（:1776）。
  ② 图输入是 Command → `map_command`（pregel/_io.py:56-:78）：
     goto 字符串 → (NULL_TASK_ID, "branch:to:{node}", START)，Send → (NULL_TASK_ID, TASKS, send)，
     resume → (NULL_TASK_ID, RESUME, cmd.resume)（:75），update → 逐键写（:77-:78）；
     **输入带 graph=PARENT → InvalidUpdateError("There is no parent graph")**（:58-:59）。
  ③ 子图里 raise 的 ParentCommand → 在 `_retry.py:618-:629` 判定归属：给自己的图就地处理，
     给父图的就把 `graph` 字段改写成父图的 checkpoint namespace 后**继续上抛**——
     这就是"交接"的实现：一条命令跨一层图。
     （errors.py:129 `class ParentCommand(GraphBubbleUp)`：和 interrupt 同族，都是"冒泡"。）

运行：python code.py       （零依赖，离线）
对照真实源码：libs/langgraph/langgraph/{types.py, graph/state.py, pregel/_io.py,
             pregel/_algo.py, pregel/_retry.py, errors.py}
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.mini_util import banner, expect_error, fmt_state, force_utf8_stdout, next_version, NULL_VERSION

force_utf8_stdout()

START = "__start__"
END = "__end__"
TASKS = "__tasks__"
RESUME = "__resume__"
BRANCH_TO = "branch:to:{}"            # graph/state.py:110


# ---------------------------------------------------------------
# Command 与两种"冒泡"异常
# ---------------------------------------------------------------


@dataclass
class Command:
    """types.py:827 的教学版：四个字段一个不差。"""

    graph: Optional[str] = None
    update: Optional[Any] = None
    resume: Optional[Any] = None
    goto: Union[Send, Sequence, Any] = ()

    PARENT = "__parent__"              # :876

    def __repr__(self) -> str:
        bits = ", ".join(f"{k}={v!r}" for k, v in
                         [("graph", self.graph), ("update", self.update),
                          ("resume", self.resume), ("goto", self.goto)] if v)
        return f"Command({bits})"


@dataclass
class Send:
    """s08 的原语：node + 私有输入（types.py:732）。"""

    node: str
    arg: Any = None


class ParentCommand(Exception):
    """errors.py:129：带一条要交给父图的 Command（和 GraphInterrupt 同族）。"""

    def __init__(self, command: Command):
        super().__init__(repr(command))
        self.command = command


class GraphInterrupt(Exception):
    """s06：interrupt() 抛出，把图挂起。"""

    def __init__(self, prompt: Any):
        super().__init__(f"interrupt: {prompt!r}")
        self.prompt = prompt


class InvalidUpdateError(Exception):
    pass


# ---------------------------------------------------------------
# 通道与建图（沿用 s01/s08 的最小形状）
# ---------------------------------------------------------------


class LastValue:
    def __init__(self, key):
        self.key, self.value, self.version = key, None, None

    def update(self, values):
        if not values:
            return False
        if len(values) > 1:
            raise InvalidUpdateError(f"{self.key}: 同一超步收到 {len(values)} 个值，"
                                     f"LastValue 不知道听谁的（s03 的规则）")
        self.value = values[0]
        return True

    def get(self):
        return self.value


class Ephemeral:
    """branch:to:X 用的通道（state.py:1543 EphemeralValue(guard=False)）：拍后清空。"""

    def __init__(self, key):
        self.key, self.value, self.version = key, None, None

    def update(self, values):
        if not values:
            return False
        self.value = values[-1]
        return True

    def get(self):
        return self.value

    def checkpoint(self):
        self.value = None                  # ephemeral：存档后就不在了（s04 的细节）


class Reducer:
    def __init__(self, key, reducer):
        self.key, self.reducer, self.value, self.version = key, reducer, None, None

    def update(self, values):
        if not values:
            return False
        if self.value is None:
            self.value, values = values[0], values[1:]
        for v in values:
            self.value = self.reducer(self.value, v)
        return True

    def get(self):
        return self.value


class Node:
    def __init__(self, name, fn, extra_triggers=(), defer=False):
        self.name, self.fn = name, fn
        self.triggers = [BRANCH_TO.format(name), *extra_triggers]
        self.defer, self.seen = defer, {}


# ---------------------------------------------------------------
# 引擎：Command 的两笔写入 + 图输入 + PARENT 冒泡
# ---------------------------------------------------------------


class MiniGraph:
    def __init__(self, nodes: List[Node], keys: Dict[str, Any], namespace: str = ""):
        self.nodes = {n.name: n for n in nodes}
        self.channels: Dict[str, Any] = {START: Ephemeral(START)}
        for n in nodes:
            self.channels[BRANCH_TO.format(n.name)] = Ephemeral(BRANCH_TO.format(n.name))
        for k, reducer in keys.items():
            self.channels[k] = reducer or LastValue(k)
        self.namespace = namespace
        self.step = 0
        self.log: List[str] = []
        self.pending_resume: List[Any] = []      # scratchpad.resume（_algo.py:1332 get_null_resume）
        self.interrupted_at: Optional[str] = None

    # ---- 图输入侧：map_command（_io.py:56） ----
    def map_command(self, cmd: Command) -> List[tuple]:
        writes: List[tuple] = []
        if cmd.graph == Command.PARENT:                     # :58-:59
            raise InvalidUpdateError("There is no parent graph")
        if cmd.goto:
            targets = cmd.goto if isinstance(cmd.goto, (list, tuple)) else [cmd.goto]
            for go in targets:
                if isinstance(go, Send):
                    writes.append((TASKS, go))              # :67
                elif go != END:
                    writes.append((BRANCH_TO.format(go), START))   # :69
        if cmd.resume is not None:
            writes.append((RESUME, cmd.resume))             # :75
        if cmd.update:
            for k, v in (cmd.update.items() if isinstance(cmd.update, dict) else [("__root__", cmd.update)]):
                writes.append((k, v))                        # :77-:78
        return writes

    # ---- 节点输出侧：_control_branch（state.py:1763） + _get_updates（:1477） ----
    def control_branch(self, value: Any) -> List[tuple]:
        if isinstance(value, Send):
            return [(TASKS, value)]
        commands = [value] if isinstance(value, Command) else \
            [v for v in value if isinstance(v, Command)] if isinstance(value, (list, tuple)) else []
        rtn: List[tuple] = []
        for cmd in commands:
            if cmd.graph == Command.PARENT:                  # :1776
                raise ParentCommand(cmd)
            targets = [cmd.goto] if isinstance(cmd.goto, (Send, str)) else list(cmd.goto or [])
            for go in targets:
                if isinstance(go, Send):
                    rtn.append((TASKS, go))
                elif go != END:
                    rtn.append((BRANCH_TO.format(go), None))
        return rtn

    def get_updates(self, value: Any) -> List[tuple]:
        if isinstance(value, Command):
            if value.graph == Command.PARENT:                # :1478-:1479 不回写本图
                return []
            return list(value.update.items()) if isinstance(value.update, dict) else []
        if isinstance(value, dict):
            return list(value.items())
        return []

    # ---- interrupt 的读侧：顺序配对（types.py:1006-:1018） ----
    def read_resume(self, idx: int) -> Any:
        if idx < len(self.pending_resume):
            return self.pending_resume[idx]
        raise GraphInterrupt(f"(第 {idx + 1} 次询问)")

    def invoke(self, source: Union[dict, Command, None], stop: int = 12) -> Dict[str, Any]:
        self.pending_resume = []
        if isinstance(source, Command):
            if source.resume is not None:
                # 真实可用 mapping（interrupt id → 值），这里按"列表 = 依次配对"教学简化
                self.pending_resume = list(source.resume) if isinstance(source.resume, (list, tuple)) \
                    else [source.resume]
            writes = self.map_command(source)
            if source.resume is not None and self.interrupted_at in self.nodes:
                # 真实由 checkpoint 的 pending writes 决定重跑哪个任务（s04/s06）；
                # mini 用"记住挂起节点 + 重新触发它"表达同一件事
                writes.append((BRANCH_TO.format(self.interrupted_at), START))
            for chan, val in writes:
                self._write([(chan, val)])
        elif source is not None:
            self._write([(START, None), *source.items()])
        self.run(stop)
        return self.view()

    def _write(self, writes: List[tuple]) -> None:
        by_chan: Dict[str, List[Any]] = {}
        for chan, val in writes:
            if chan not in self.channels:
                self.channels[chan] = LastValue(chan)
            by_chan.setdefault(chan, []).append(val)
        updated = []
        for chan, vals in by_chan.items():
            ch = self.channels[chan]
            if ch.update(vals):
                ch.version = next_version(ch.version)
                updated.append(chan)
        if updated:
            self.log.append(f"    写入通道：{updated}")

    def run(self, stop: int) -> None:
        while self.step <= stop:
            tasks = [n for n in self.nodes.values() if self._should_trigger(n)]
            if not tasks:
                return
            self.step += 1
            self.log.append(f"  超步 {self.step}：任务 {[n.name for n in tasks]}")
            all_writes: List[tuple] = []
            for node in tasks:
                state = self.view()
                try:
                    out = node.fn(state, self)
                    writes = self.get_updates(out) + self.control_branch(out)
                except GraphInterrupt as gi:
                    self.interrupted_at = node.name
                    self.log.append(f"    ⏸ {node.name} 挂起：{gi}（整节点从头重跑才继续）")
                    self._record_seen(tasks)
                    return
                except ParentCommand as pc:
                    # _retry.py:620-629 的判据：goto 命中本图节点 → 就地落地；
                    # 不是本图的目标 → 继续往上冒（真实侧还会改写 graph 字段成父 namespace）
                    targets = [pc.command.goto] if isinstance(pc.command.goto, (str, Send)) \
                        else list(pc.command.goto or [])
                    if not any(isinstance(t, str) and t in self.nodes for t in targets):
                        raise
                    self._accept_parent_command(node, pc)
                    self._record_seen(tasks)
                    continue
                pushed = [v for c, v in writes if c == TASKS]
                all_writes.extend((c, v) for c, v in writes if c != TASKS)
                for s in pushed:                             # s08：同拍执行 pushed 任务
                    target = self.nodes[s.node]
                    all_writes.extend(self.get_updates(target.fn(s.arg, self)) or [])
                    self.log.append(f"    pushed {s.node}（私有输入 {s.arg}）")
            self._record_seen(tasks)
            self._write(all_writes) if all_writes else None
        self.log.append("  ⚠ 到达 recursion 上限")

    def _accept_parent_command(self, node: Node, pc: ParentCommand) -> None:
        """_retry.py:618-:629：goto 命中本图节点，就在本图落地（把 graph 字段改写掉）。"""
        cmd = pc.command
        for chan, val in self.map_command(replace(cmd, graph=None)):
            if chan != RESUME:
                self._write([(chan, val)])
        self.log.append(f"    ↟ 来自子图节点 {node.name} 的 Command 在本图落地："
                        f"goto={cmd.goto!r} update={cmd.update!r}"
                        f"（子图自己不回写：state.py:1478）")

    def _should_trigger(self, node: Node) -> bool:
        for chan in node.triggers:
            ch = self.channels.get(chan)
            if ch is None or ch.version is None:
                continue
            if ch.version > node.seen.get(chan, NULL_VERSION):
                return True
        return False

    def _record_seen(self, tasks: List[Node]) -> None:
        for n in tasks:
            for chan in n.triggers:
                ch = self.channels.get(chan)
                if ch is not None and ch.version is not None:
                    n.seen[chan] = ch.version

    def view(self) -> Dict[str, Any]:
        return {k: c.get() for k, c in self.channels.items()
                if not k.startswith(("branch:to:", "__")) and c.get() is not None}


# ---------------------------------------------------------------
# 演示
# ---------------------------------------------------------------


def scenario_update_and_goto() -> None:
    banner("场景 1：update + goto —— 一次返回说两件事")

    def a(state, g):
        return Command(update={"n": state.get("n", 0) + 1}, goto="b")

    def b(state, g):
        return Command(update={"trail": ["进 b 时 n=" + str(state.get("n"))]}, goto=END)

    g = MiniGraph([Node("a", a, extra_triggers=[START]), Node("b", b)],
                  {"n": None, "trail": Reducer("trail", lambda x, y: x + y)})
    g.invoke({"n": 0})
    print("\n".join(g.log))
    print(f"  → 状态与路由**同一拍**生效：{fmt_state(g.view())}")
    print("    （真实侧：update 走 _get_updates（state.py:1477），goto 写 branch:to:b（:110/:1788））")


def scenario_goto_variants() -> None:
    banner("场景 2：goto 的四种取值 —— 名字、多个名字、Send、END")

    def fan(state, g):
        return Command(goto=["c1", "c2"])

    def c1(state, g):
        return Command(update={"hits": ["c1"]}, goto=END)

    def c2(state, g):
        return Command(update={"hits": ["c2"]}, goto=END)

    g = MiniGraph([Node("fan", fan, extra_triggers=[START]), Node("c1", c1), Node("c2", c2)],
                  {"hits": Reducer("hits", lambda x, y: x + y)})
    g.invoke({})
    print(f"  多个名字：{g.view()}")

    def via_send(state, g):
        return Command(goto=Send("c1", {"tag": "私有输入"}))

    g2 = MiniGraph([Node("s", via_send, extra_triggers=[START]), Node("c1", c1)], {"hits": None})
    g2.invoke({})
    print(f"  Send（s08 的 push 通道）：{g2.log[-2].strip()}")
    print("  → goto 接受 名字 / 名字序列 / Send / Send 序列（types.py:852），END 表示到此为止")


def scenario_command_as_input() -> None:
    banner("场景 3：Command 当图输入 —— 不经 START 边直接落地")

    def worker(state, g):
        return Command(update={"did": state.get("seed", "?")}, goto=END)

    g = MiniGraph([Node("worker", worker)], {"seed": None, "did": None})
    out = g.invoke(Command(goto="worker", update={"seed": "从输入 Command 带进来的"}))
    print(f"  {fmt_state(g.view())}")
    expect_error("图输入里不许指向父图",
                 lambda: MiniGraph([Node("worker", worker)], {}).invoke(
                     Command(graph=Command.PARENT, goto="worker")),
                 InvalidUpdateError)
    print("  → 真实文案：_io.py:58-:59 InvalidUpdateError(\"There is no parent graph\")")


def scenario_resume_handoff() -> None:
    banner("场景 4：Command(resume=…) —— 恢复值的交接（s06 的另一半）")

    reruns = {"count": 0}

    def human_gate(state, g):
        reruns["count"] += 1
        print(f"    节点从头重跑，第 {reruns['count']} 次进入")
        first = g.read_resume(0)          # 第一次 interrupt：拿不到就抛 GraphInterrupt
        second = g.read_resume(1)         # 第二次：按出现顺序配对
        return Command(update={"ok": f"{first} / {second}"}, goto=END)

    g = MiniGraph([Node("gate", human_gate, extra_triggers=[START])], {"ok": None})
    g.invoke({"x": 1})
    print(f"  首轮挂起在 {g.interrupted_at}，状态里没有 ok：{fmt_state(g.view())}")
    g.invoke(Command(resume=["批准", "再给 5 分"]))
    print(f"  同一个 g 上 Command(resume=[…]) 恢复：{fmt_state(g.view())}"
          f"（节点重跑 {reruns['count']} 次——从头重跑，不是接着跑）")
    print("  → resume 值写成 (NULL_TASK_ID, RESUME, value)（_io.py:75），"
          "节点按出现顺序配对（types.py:1006-1018）")


def scenario_parent_handoff() -> None:
    banner("场景 5：Command(graph=PARENT) —— 跨层交接（多 agent 的语法）")

    def worker(state, g):
        # 子图里干活的人，决定"下一棒交给兄弟"
        return Command(update={"log": "worker 交棒"}, goto="sibling", graph=Command.PARENT)

    inner = MiniGraph([Node("worker", worker, extra_triggers=[START])],
                      {"log": None}, namespace="agent1")

    def sibling(state, g):
        return Command(update={"log": "sibling 接手"}, goto=END)

    def run_agent1(state, g):
        inner.invoke({})                  # 子图抛出的 ParentCommand 从这里冒出来
        return {}

    def append(x, y):
        return (x if isinstance(x, list) else [x]) + ([y] if isinstance(y, list) else [y])

    parent = MiniGraph([Node("agent1", run_agent1, extra_triggers=[START]), Node("sibling", sibling)],
                       {"log": Reducer("log", append)})
    print("  ① 子图单独跑（无父图）：ParentCommand 直接冒到调用方")
    try:
        MiniGraph([Node("worker", worker, extra_triggers=[START])], {"log": None},
                  namespace="solo").invoke({})
    except ParentCommand as e:
        print(f"     raise ParentCommand({e})")
    print("  ② 子图作为父图的一个节点：冒泡到父引擎，父引擎改路由")
    parent.invoke({})
    print(f"    父图视图：{fmt_state(parent.view())}")
    print("\n".join("    " + l for l in parent.log))
    print("  → 真实侧 _retry.py:618-:629：给自己的图就地处理，给父图的把 graph 改写成"
          "父 checkpoint namespace 再继续上抛（errors.py:129 与 interrupt 同族）")


def scenario_tool_commands_merged() -> None:
    banner("场景 6：工具也能返回 Command —— 多条 PARENT 命令会被合并")

    def tool_result(name: str, target: str) -> Command:
        return Command(graph=Command.PARENT, goto=[Send(target, {"from": name})])

    outputs = [tool_result("转移给A", "agent_a"), tool_result("转移给B", "agent_b")]
    merged: Optional[Command] = None
    for out in outputs:                                       # tool_node.py:895-:913 的合并逻辑
        if out.graph is Command.PARENT and isinstance(out.goto, list) \
                and all(isinstance(s, Send) for s in out.goto):
            merged = replace(merged, goto=list(merged.goto) + list(out.goto)) if merged else \
                Command(graph=Command.PARENT, goto=out.goto)
    print(f"  两条工具命令 → 合并成一条：{merged}")
    print("  → 真实：prebuilt/tool_node.py:657-:660『Command 可以改状态、触发跳转、发消息』，"
          ":864-:913 把多条 PARENT+Send 命令并成一条（一次交接而不是两次）")


def main() -> None:
    scenario_update_and_goto()
    scenario_goto_variants()
    scenario_command_as_input()
    scenario_resume_handoff()
    scenario_parent_handoff()
    scenario_tool_commands_merged()
    print("\n结论：Command 的四格（graph/update/resume/goto）各自落到已有机制上——")
    print("update→通道写入、goto→branch:to 或 TASKS、resume→NULL 任务上的 RESUME、PARENT→冒泡；"
          "新语法，没有新引擎。")


if __name__ == "__main__":
    main()
