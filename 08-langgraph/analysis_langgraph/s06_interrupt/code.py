# -*- coding: utf-8 -*-
"""
s06_interrupt.py —— interrupt：存档挂起，人类输入后节点从头重跑

LangGraph 的人在环（human-in-the-loop）原语是 interrupt（types.py:887，实测）。
它的三条语义都写在 docstring 里，一条都不能少：

  ① 节点内调用 interrupt(value) → 抛 GraphInterrupt 异常，整图挂起，
     value 送到客户端（types.py:902 之前的段落）。
  ② 恢复必须用 Command(resume=...)；**图从节点开头重跑、所有逻辑再执行一遍**
     （"The graph resumes from the start of the node, re-executing all logic."
     —— types.py:902）。
  ③ 一个节点里有多个 interrupt，按出现顺序与恢复值配对（types.py:905-907）。
  ④ 必须配 checkpointer——中断依赖存档（types.py:912）。

机制上它是 s04/s05 的组合拳：
  · 挂起 = 那一拍照常收尾：检查点落盘、中断值以 INTERRUPT 控制信号记入
    pending writes（_runner.py:584-590 的 commit 把 GraphInterrupt 转成
    put_writes 里的 INTERRUPT 写入，实测）。
  · 恢复 = Command(resume=...) 以 RESUME 信号入账；tick 重新规划出该节点
    的任务（_loop.py:752 的 _reapply_writes_to_succeeded_nodes 跳过
    ERROR/INTERRUPT/RESUME，失败/中断任务保持空写入 → runner 重跑）。
  · 重跑时 interrupt() 不再抛异常，而是按顺序吐出恢复值（resume map，
    _algo.py:1292 的 _scratchpad 一带管理）。

    第一次 invoke:  approval_node: [副作用] interrupt("批准?") ──→ GraphInterrupt
                    检查点照存（含 INTERRUPT 信号）——图"冻结"在这里，进程可以退出
    第二次 invoke:  Command(resume="批准") ──→ approval_node 从头重跑
                    [副作用再来一次] interrupt() 这次返回 "批准" → 节点正常完成

    ★ 推论：interrupt 之前的副作用（API 调用、写库）会执行两次——
      必须幂等，或挪到 interrupt 之后。

运行：python code.py            （零依赖，离线）
对照真实源码：libs/langgraph/langgraph/types.py:887（interrupt）
             libs/langgraph/langgraph/pregel/_runner.py:574（commit 存中断）
             libs/langgraph/langgraph/pregel/_loop.py:752（恢复时跳过控制信号）
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.mini_util import banner, next_version, uid, NULL_VERSION

START = "__start__"
INTERRUPT, RESUME, ERROR = "INTERRUPT", "RESUME", "ERROR"  # 控制信号（constants.py）


class GraphInterrupt(Exception):
    """types.py 的 GraphInterrupt 教学版：payload 是要问人的问题。"""

    def __init__(self, value):
        super().__init__(value)
        self.value = value


class MiniInterrupt:
    """interrupt() 的实现核心：第一次抛异常；恢复后按顺序吐值。

    真实引擎里"第几个 interrupt 配第几个恢复值"的账本叫 resume map
    （挂在 scratchpad 上，_algo.py:1292 _scratchpad 的 resume_map 参数）。
    """

    def __init__(self):
        self.resume_values: list = []   # Command(resume=...) 带来的值，按序消费
        self.consumed: int = 0          # 本次任务执行已消费到第几个

    def interrupt(self, question):
        if self.consumed < len(self.resume_values):
            v = self.resume_values[self.consumed]
            self.consumed += 1
            return v                    # ② 恢复路径：不再抛异常，直接返回人类的答案
        raise GraphInterrupt(question)  # ① 首次路径：挂起

    def command_resume(self, value):
        """Command(resume=value) 的落点：新值排队（真实实现写入 RESUME 信号）。"""
        self.resume_values.append(value)


# ---------------------------------------------------------------
# 引擎：s04 骨架 + 中断挂起/恢复
# ---------------------------------------------------------------
class LastValue:
    def __init__(self, key):
        self.key, self.value, self.version = key, None, None

    def update(self, values):
        if not values:
            return False
        assert len(values) == 1
        self.value = values[-1]
        return True

    def get(self):
        return self.value

    def is_available(self):
        return self.value is not None


class Node:
    def __init__(self, name, fn, triggers):
        self.name, self.fn, self.triggers = name, fn, triggers


class MiniLoop:
    def __init__(self, nodes, channels, versions_seen, saver, thread_id,
                 interrupts: MiniInterrupt, step=0, stop=25):
        self.nodes = {n.name: n for n in nodes}
        self.channels = channels
        self.versions_seen = versions_seen
        self.saver, self.thread_id = saver, thread_id
        self.interrupts = interrupts
        self.step, self.stop, self.status = step, stop, "pending"
        self.pending_writes: list = []   # 控制信号账本（put_writes 的 mini 版）

    def tick(self) -> bool:
        if self.step > self.stop:
            self.status = "out_of_steps"
            return False
        self.tasks = [n for n in self.nodes.values() if self._should_trigger(n)]
        if not self.tasks:
            self.status = "done"
            return False
        self.status = "running"  # 每拍开始都重置——上一拍的 paused 不能带进这一拍
        self.step += 1
        return True

    def _should_trigger(self, node):
        seen = self.versions_seen.get(node.name, {})
        for chan in node.triggers:
            cur = self.channels[chan].version
            if cur is not None and cur > seen.get(chan, NULL_VERSION):
                return True
        # 恢复路径：上一次挂起的节点，靠 pending 里的 INTERRUPT 信号重新上榜
        # （真实引擎：_reapply_writes_to_succeeded_nodes :752 跳过 INTERRUPT，
        #  任务保持空写入 → runner 照常重跑它；mini 用"挂起节点重进任务表"等价呈现）
        return any(pw[0] == node.name for pw in self.pending_writes if pw[1] == INTERRUPT)

    def run_tasks(self):
        for node in self.tasks:
            self.interrupts.consumed = 0  # 节点从头重跑 → interrupt 序号清零重配
            state = {k: c.get() for k, c in self.channels.items() if c.value is not None}
            try:
                yield node.name, list(node.fn(state).items()), None
            except GraphInterrupt as gi:
                yield node.name, [], gi   # 中断不上抛：转成这一拍的一个"结果"

    def after_tick(self, results):
        normal = [(n, w) for n, w, err in results if err is None]
        completed = {n for n, w, err in results if err is None}
        for n, w, err in results:
            if isinstance(err, GraphInterrupt):   # ★ commit（_runner.py:584-590）：
                self.pending_writes.append((n, INTERRUPT, err.value))  # 中断值入账
                self.status = "interrupted"
                print(f"    [挂起] 任务 {n} 抛 GraphInterrupt：问题={err.value!r}")
        # 正常完成的任务会以最终写入覆盖自己的 pending（真实引擎 put_writes 按
        # task_id 覆盖旧信号）——挂起记录随之消失，节点不会被打捞重跑
        self.pending_writes = [pw for pw in self.pending_writes if pw[0] not in completed]
        for name, _ws in normal:
            node = self.nodes[name]
            seen = self.versions_seen.setdefault(name, {})
            for chan in node.triggers:
                if self.channels[chan].version is not None:
                    seen[chan] = self.channels[chan].version
        by_channel: dict = {}
        for _n, ws in normal:
            for chan, val in ws:
                by_channel.setdefault(chan, []).append(val)
        updated = set()
        for chan, vals in by_channel.items():
            ch = self.channels[chan]
            if ch.update(vals) and ch.is_available():
                ch.version = next_version(ch.version)
                updated.add(chan)
        # ★ 每拍必存（_loop.py:734）——中断的那一拍也存！这就是④的由来
        snapshot = {
            "id": uid("ckpt"),
            "channel_values": {k: c.get() for k, c in self.channels.items()},
            "channel_versions": {k: c.version for k, c in self.channels.items() if c.version},
            "versions_seen": {k: dict(v) for k, v in self.versions_seen.items()},
            "pending_writes": list(self.pending_writes),
        }
        self.saver.put(self.thread_id, snapshot, {"source": "loop", "step": self.step,
                                                  "status": self.status})
        if self.status == "interrupted":
            self.status = "paused"


def main() -> None:
    banner("场景 1：审批流 —— interrupt 挂起，Command(resume) 恢复")

    side_effects = []

    def approval_node(state):
        # ★ 副作用在 interrupt 之前：恢复时整节点从头重跑，它会被执行两次！
        side_effects.append(f"已调用风控接口(检查 {state.get(START)!r})")
        print(f"    [approval_node] 副作用: {side_effects[-1]}")
        decision = mini.interrupt("deploy 需要审批：批准还是拒绝？")
        print(f"    [approval_node] 拿到人类决策: {decision!r}")
        return {"decision": decision}

    def deploy_node(state):
        print(f"    [deploy_node] 执行部署（decision={state.get('decision')!r}）")
        return {"deployed": "ok"}

    mini = MiniInterrupt()
    saver = MiniSaver()
    channels = {k: LastValue(k) for k in [START, "request", "decision", "deployed"]}
    channels[START].update(["部署 v2.0"])
    channels[START].version = 1
    nodes = [Node("approval_node", approval_node, [START]),
             Node("deploy_node", deploy_node, ["decision"])]
    loop = MiniLoop(nodes, channels, {}, saver, "t1", interrupts=mini)
    saver.put("t1", _snap(channels, {}), {"source": "input", "step": 0})

    print("  —— 第一次 invoke：跑到 interrupt 就挂起 ——")
    while loop.tick():
        loop.after_tick(list(loop.run_tasks()))
        if loop.status == "paused":
            break
    print(f"    进程此刻可以退出；存档 status={saver.list('t1')[-1]['status']!r}，")
    print(f"    存档 pending_writes={saver.list('t1')[-1]['pending_writes']}")
    print(f"    副作用执行了 {len(side_effects)} 次（第一次）")

    print("  —— 第二次 invoke：Command(resume='批准') ——")
    mini.command_resume("批准")   # 真实 API：graph.invoke(Command(resume="批准"), config)
    channels = {}
    for k, v in saver.list("t1")[-1]["channel_values"].items():
        ch = LastValue(k)
        ch.value = v
        ch.version = saver.list("t1")[-1]["channel_versions"].get(k)
        channels[k] = ch
    loop2 = MiniLoop(nodes, channels, saver.list("t1")[-1]["versions_seen"],
                     saver, "t1", interrupts=mini,
                     step=saver.list("t1")[-1]["step"])
    loop2.pending_writes = list(saver.list("t1")[-1]["pending_writes"])
    while loop2.tick():
        loop2.after_tick(list(loop2.run_tasks()))
        if loop2.status == "paused":
            break
    print(f"    副作用共执行 {len(side_effects)} 次 —— 恢复是'整节点重跑'（types.py:902）")
    print(f"    终态: decision={channels['decision'].get()!r} deployed={channels['deployed'].get()!r}")

    banner("场景 2：一个节点两个 interrupt —— 按出现顺序配对恢复值")
    m2 = MiniInterrupt()

    def two_questions(state):
        name = m2.interrupt("Q1: 项目名？")
        budget = m2.interrupt("Q2: 预算？")
        return {"form": f"{name} / {budget}"}

    saver2 = MiniSaver()
    ch2 = {k: LastValue(k) for k in [START, "form"]}
    ch2[START].update(["开工"])
    ch2[START].version = 1
    loop3 = MiniLoop([Node("form_node", two_questions, [START])], ch2, {}, saver2, "t2", interrupts=m2)
    saver2.put("t2", _snap(ch2, {}), {"source": "input", "step": 0})
    resume_answers = ["气象站", 100]  # 每挂起一次，人类喂一个值（按序配对）
    for answer in resume_answers + [None]:
        while loop3.tick():
            loop3.after_tick(list(loop3.run_tasks()))
            if loop3.status == "paused":
                break
        if loop3.status != "paused":
            break
        print(f"    挂起（{loop3.pending_writes[-1][2]!r}）→ Command(resume={answer!r})")
        m2.command_resume(answer)
    print(f"    form = {ch2['form'].get()!r}")
    print("    → Q1 配第一个值、Q2 配第二个值：按节点内出现顺序，不看 id（types.py:905-907）")

    banner("场景 3：不配 checkpointer —— 直接报错")
    try:
        raise_checkpointer(None)
    except ValueError as e:
        print(f"    [预期报错] ValueError: {e}")
    print("    → 中断依赖存档：没有存档就没有'挂起点'（types.py:912）")


def raise_checkpointer(saver):
    if saver is None:
        raise ValueError("To use interrupt, you must enable a checkpointer.")


def _snap(channels, versions_seen):
    return {
        "id": uid("ckpt"),
        "channel_values": {k: c.get() for k, c in channels.items()},
        "channel_versions": {k: c.version for k, c in channels.items() if c.version},
        "versions_seen": {k: dict(v) for k, v in versions_seen.items()},
        "pending_writes": [],
    }


class MiniSaver:
    def __init__(self):
        self.storage: dict[str, list[dict]] = {}

    def put(self, thread_id, snapshot, metadata):
        self.storage.setdefault(thread_id, []).append({**snapshot, **metadata})

    def list(self, thread_id):
        return list(self.storage.get(thread_id, []))


if __name__ == "__main__":
    main()
