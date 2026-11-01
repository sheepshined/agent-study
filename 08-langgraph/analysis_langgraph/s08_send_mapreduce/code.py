# -*- coding: utf-8 -*-
"""
s08_send_mapreduce.py —— Send / Map-Reduce：运行时才知道扇出几个，怎么办

静态图有个先天限制：拓扑在建图期就定了。但 agent 常见的需求是
**运行时才知道要并行多少路**——主题列表有 3 个就开 3 路研究，有 7 个开 7 路。
LangGraph 的答案是 Send（types.py:732，实测）：

    class Send:
        '''A message or packet to send to a specific node in the graph.
        ... the sent state can differ from the core graph's state, ...
        One such example is a "map-reduce" workflow ...'''   # docstring 原文

    def continue_to_jokes(state):
        return [Send("generate_joke", {"subject": s}) for s in state["subjects"]]

三个语义：
  ① 条件边可以返回 Send 列表——扇出数量是**运行时**算出来的（:1595-1602
     的 packets: Sequence[str | Send]；:1766 _control_branch 把 Send 转
     (TASKS, value) 写入）。
  ② 每个 Send 自带**私有输入**（node + arg 两个属性，:802-803）——
     目标节点拿到的不是共享 state，而是你塞给它的 arg（map-reduce 的 map）。
  ③ 扇出的任务在**同一拍内**追加执行：main.py:2979-2982 把
     schedule_task=loop.accept_push 传给 runner.tick——执行中的任务还能
     往本拍塞新任务（push），这就是动态并发的机制入口。

    条件边（map 阶段）                 同一拍内的 pushed 任务（并发）
    ┌──────────────┐   Send×N     ┌────────────────────────────┐
    │ router 节点   │ ──────────→ │ Send("generate", {"s": A})  │
    │ 读 subjects   │             │ Send("generate", {"s": B})  │ → 各自私有输入
    │ 返回 N 个 Send│             │ Send("generate", {"s": C})  │ → 写 reducer 通道
    └──────────────┘             └────────────────────────────┘
                                        ↓ reduce 阶段（下一拍）
                                  jokes 通道按 reducer 折叠汇总

运行：python code.py            （零依赖，离线）
对照真实源码：libs/langgraph/langgraph/types.py:732（Send）
             libs/langgraph/langgraph/graph/state.py:1766（_control_branch）
             libs/langgraph/langgraph/pregel/main.py:2979（accept_push）
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.mini_util import banner, next_version, uid, NULL_VERSION

START = "__start__"


class Send:
    """types.py:732 的教学版：node + arg（私有输入）。"""

    def __init__(self, node: str, arg):
        self.node, self.arg = node, arg

    def __repr__(self):
        return f"Send(node={self.node!r}, arg={self.arg!r})"


class ReducerChannel:
    """reduce 阶段的落点：扇出任务的写入全部折叠进这里（binop.py:143）。"""

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

    def is_available(self):
        return self.value is not None


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
    """fn 读共享 state；branch 是"出口条件边"：返回节点名列表或 Send 列表。

    branch 就 state.py:994 add_conditional_edges 的 path 函数——返回值若含
    Send，引擎转成 pushed 任务（真实入口 _control_branch :1766）。
    """

    def __init__(self, name, fn, triggers, branch=None, push_input=False):
        self.name, self.fn, self.triggers = name, fn, triggers
        self.branch, self.push_input = branch, push_input


class MiniLoop:
    def __init__(self, nodes, channels, versions_seen, step=0, stop=25):
        self.nodes = {n.name: n for n in nodes}
        self.channels = channels
        self.versions_seen = versions_seen
        self.step, self.stop, self.status = step, stop, "pending"
        self.push_log: list = []

    def tick(self) -> bool:
        if self.step > self.stop:
            self.status = "out_of_steps"
            return False
        self.tasks = [n for n in self.nodes.values() if self._should_trigger(n)]
        if not self.tasks:
            self.status = "done"
            return False
        self.status = "running"
        self.step += 1
        return True

    def _should_trigger(self, node):
        seen = self.versions_seen.get(node.name, {})
        for chan in node.triggers:
            cur = self.channels[chan].version
            if cur is not None and cur > seen.get(chan, NULL_VERSION):
                return True
        return False

    def run_tasks(self):
        for node in self.tasks:
            state = {k: c.get() for k, c in self.channels.items() if c.value is not None}
            writes, pushed = self._run_one(node, state)
            yield node.name, writes, pushed

    def _run_one(self, node, state):
        """执行一个任务：本体 + branch 求值 + pushed 任务在同一拍内跑完。"""
        writes = list(node.fn(state).items())
        pushed_writes: list = []
        pushed_tasks: list = []
        if node.branch is not None:
            targets = node.branch(state)              # ★ 运行时才算扇出
            for t in targets:
                if isinstance(t, Send):
                    if t.node not in self.nodes:
                        raise RuntimeError(f"Send 目标节点不存在: {t.node!r}")
                    self.push_log.append((self.step, node.name, t))
                    pushed_tasks.append(t)
                elif isinstance(t, str):
                    writes.append((f"__branch__{t}", None))  # 普通路由，mini 略
        # ★ 同拍执行 pushed 任务（真实引擎经 accept_push 进线程池，main.py:2979）
        for t in pushed_tasks:
            target = self.nodes[t.node]
            print(f"      [pushed] {t} ← 私有输入，不读共享 state")
            out = target.fn(t.arg) if target.push_input else target.fn(state)
            pushed_writes.extend(out.items())
        return writes + pushed_writes, pushed_tasks

    def after_tick(self, results):
        all_writes = [(n, w) for n, w, _p in results]
        for name, _ws in all_writes:
            node = self.nodes[name]
            seen = self.versions_seen.setdefault(name, {})
            for chan in node.triggers:
                if self.channels[chan].version is not None:
                    seen[chan] = self.channels[chan].version
        by_channel: dict = {}
        for _n, ws in all_writes:
            for chan, val in ws:
                by_channel.setdefault(chan, []).append(val)
        updated = set()
        for chan, vals in by_channel.items():
            ch = self.channels[chan]
            if ch.update(vals) and ch.is_available():
                ch.version = next_version(ch.version)
                updated.add(chan)
        print(f"    [after_tick] 超步 {self.step} 写入合并: {by_channel}")


def main() -> None:
    banner("场景 1：Map-Reduce —— 3 个主题开 3 路，折叠汇总")

    def router_fn(state):
        # 节点本体：交一份空增量（map 决策全在 branch 里）
        return {}

    def router(state):
        # branch（条件边 path 函数）：扇出数量由 state 里的列表长度决定——运行时才知道
        subjects = state.get("subjects", [])
        print(f"    [router] 读到 {len(subjects)} 个主题 → 发出 {len(subjects)} 个 Send")
        return [Send("generate", {"subject": s}) for s in subjects]

    def generate(arg):
        # map 任务：拿私有输入，写 reducer 通道（reduce 阶段的原料）
        return {"jokes": [f"关于{arg['subject']}的段子"]}

    def finish(state):
        print(f"    [finish] 汇总 {len(state.get('jokes', []))} 条：{state.get('jokes')}")
        return {"digest": "完成"}

    subjects_ch = LastValue("subjects")
    subjects_ch.update([["Python", "会议", "周一"]])
    subjects_ch.version = 1
    channels = {"__start__": LastValue("__start__"), "subjects": subjects_ch,
                "jokes": ReducerChannel("jokes", lambda a, b: a + b),
                "digest": LastValue("digest")}
    channels["__start__"].update(["go"])
    channels["__start__"].version = 1
    nodes = [Node("router", router_fn, ["__start__"], branch=router),  # 条件边 = branch 函数
             Node("generate", generate, [], push_input=True),
             Node("finish", finish, ["jokes"])]
    loop = MiniLoop(nodes, channels, {})
    while loop.tick():
        loop.after_tick(list(loop.run_tasks()))
    print(f"  push 账本：{[(s, f'{src}→{t.node}') for s, src, t in loop.push_log]}")
    print("  → 扇出发生在'拍内'（accept_push），汇总发生在'下一拍'（版本差分唤醒 finish）")

    banner("场景 2：运行时决定扇出 —— 同一张图，换输入就换拓扑")
    for n_topics in [2, 5]:
        subjects_ch2 = LastValue("subjects")
        subjects_ch2.update([[f"主题{i}" for i in range(n_topics)]])
        subjects_ch2.version = 1
        ch2 = {"__start__": LastValue("__start__"), "subjects": subjects_ch2,
               "jokes": ReducerChannel("jokes", lambda a, b: a + b),
               "digest": LastValue("digest")}
        ch2["__start__"].update(["go"])
        ch2["__start__"].version = 1
        loop2 = MiniLoop([Node("router", router_fn, ["__start__"], branch=router),
                          Node("generate", generate, [], push_input=True),
                          Node("finish", finish, ["jokes"])], ch2, {})
        while loop2.tick():
            loop2.after_tick(list(loop2.run_tasks()))
        print(f"    输入 {n_topics} 个主题 → 实际执行 {n_topics} 个并行任务，"
              f"jokes={len(ch2['jokes'].get())} 条（图定义零改动）")

    banner("场景 3：失败路径 —— Send 指向不存在的节点")
    ch3 = {"__start__": LastValue("__start__"), "subjects": subjects_ch,
           "jokes": ReducerChannel("jokes", lambda a, b: a + b)}
    ch3["__start__"].update(["go"])
    ch3["__start__"].version = 1
    bad_router = Node("router_bad", lambda s: {}, ["__start__"],
                      branch=lambda s: [Send("ghost_node", {})])
    loop3 = MiniLoop([bad_router, Node("generate", generate, [], push_input=True)], ch3, {})
    try:
        while loop3.tick():
            loop3.after_tick(list(loop3.run_tasks()))
    except RuntimeError as e:
        print(f"    [预期报错] RuntimeError: {e}")
    print("  → 动态扇出的错误也是运行时错误：建图器没法检查'运行时才知道'的目标")


if __name__ == "__main__":
    main()
