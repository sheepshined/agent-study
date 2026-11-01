# -*- coding: utf-8 -*-
"""
s05_time_travel.py —— 时间旅行：从检查点回放与分叉

s04 建好了检查点链——链在手上，时间旅行只是把它用起来。两件事：

  回放（replay）：把第 k 拍的 checkpoint 装回引擎，从头再跑一遍。
    BSP 换来的确定性在这里兑现：同样的档 + 同样的节点函数
    = 同样的后续每一拍。get_state_history（main.py:1491，实测）+ 重新 invoke。

  分叉（fork）：把第 k 拍的档取出，**手改某个通道**，存成一条新档
    （_loop.py:987 的 _put_checkpoint({"source": "fork"})，实测），
    再继续 invoke。引擎自动算出"哪些节点要重算"——就是 s02 的版本差分：
    被手改的通道版本前进 → 下游节点（见过旧版本）重新触发，
    上游节点（已见过当前版本）保持不动。

    检查点链：  #0(input) ── #1 ── #2 ── #3
    回放：      取 #1 重跑 → 得到与 #2/#3 逐拍相同的值
    分叉：      取 #1 手改 plan → 存 fork 档 #1'
                → #2'/#3' 只重算下游，上游原样

    对应的官方 API：graph.get_state_history(config) 取链；
    graph.update_state(config, values, as_node="...") 手改历史；
    把改后的 config 传给 invoke 即从该档继续。

运行：python code.py            （零依赖，离线）
对照真实源码：libs/langgraph/langgraph/pregel/main.py:1491（get_state_history）
             libs/langgraph/langgraph/pregel/_loop.py:987（fork 存档）
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.mini_util import banner, next_version, uid, NULL_VERSION

START = "__start__"


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


class MiniSaver:
    """s04 存取接口的浓缩版（put/get_tuple/list），快照直接以 dict 存储。"""

    def __init__(self):
        self.storage: dict[str, list[dict]] = {}

    def put(self, thread_id, snapshot, metadata):
        self.storage.setdefault(thread_id, []).append({**snapshot, **metadata})

    def list(self, thread_id):
        return list(self.storage.get(thread_id, []))


class MiniLoop:
    """s04 引擎原样复用：恢复 = 重建通道/版本/versions_seen，规划逻辑零改动。"""

    def __init__(self, nodes, channels, versions_seen, saver, thread_id, step=0, stop=25):
        self.nodes = {n.name: n for n in nodes}
        self.channels = channels
        self.versions_seen = versions_seen
        self.saver, self.thread_id = saver, thread_id
        self.step, self.stop, self.status = step, stop, "pending"

    def tick(self) -> bool:
        if self.step > self.stop:
            self.status = "out_of_steps"
            return False
        self.tasks = [n for n in self.nodes.values() if self._should_trigger(n)]
        if not self.tasks:
            self.status = "done"
            return False
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
            yield node.name, list(node.fn(state).items())

    def after_tick(self, results, source="loop"):
        for name, _ws in results:
            node = self.nodes[name]
            seen = self.versions_seen.setdefault(name, {})
            for chan in node.triggers:
                if self.channels[chan].version is not None:
                    seen[chan] = self.channels[chan].version
        by_channel: dict = {}
        for _n, ws in results:
            for chan, val in ws:
                by_channel.setdefault(chan, []).append(val)
        updated = set()
        for chan, vals in by_channel.items():
            ch = self.channels[chan]
            if ch.update(vals) and ch.is_available():
                ch.version = next_version(ch.version)
                updated.add(chan)
        self.saver.put(self.thread_id, self._snapshot(updated), {"source": source, "step": self.step})

    def _snapshot(self, updated):
        return {
            "id": uid("ckpt"),
            "channel_values": {k: c.get() for k, c in self.channels.items()},
            "channel_versions": {k: c.version for k, c in self.channels.items() if c.version},
            "versions_seen": {k: dict(v) for k, v in self.versions_seen.items()},
            "updated_channels": sorted(updated),
        }


def build_graph(saver, thread_id):
    """三节点链 + 一条会随 plan 变化的 review。"""

    def planner(state):
        return {"plan": f"方案(由输入'{state.get(START)}'生成)"}

    def reviewer(state):
        return {"review": f"复审'{state.get('plan')}'→通过"}

    def archiver(state):
        return {"archive": f"归档[{state.get('review')[:12]}...]"}

    nodes = [Node("planner", planner, [START]),
             Node("reviewer", reviewer, ["plan"]),
             Node("archiver", archiver, ["review"])]
    channels = {k: LastValue(k) for k in [START, "plan", "review", "archive"]}
    return MiniLoop(nodes, channels, {}, saver, thread_id), channels, nodes


def restore(snapshot, channels_spec):
    """把一份 checkpoint 快照装回引擎：值 + 版本 + versions_seen 三样。"""
    channels = {}
    for k in channels_spec:
        ch = LastValue(k)
        ch.value = snapshot["channel_values"].get(k)
        ch.version = snapshot["channel_versions"].get(k)
        channels[k] = ch
    return channels, copy.deepcopy(snapshot["versions_seen"])


def fork(saver, thread_id, snapshot, writes, as_node):
    """update_state(config, values, as_node=...) 的 mini 版。

    ① 把 writes 应用到通道（版本前进）；
    ② 把这些写入记到 as_node 名下——它的 versions_seen 同步推进，
       所以"它自己"不会因这批写入重跑，重跑的是下游；
    ③ 存一条 source=fork 的新档（_loop.py:987）。
    """
    new_seen = copy.deepcopy(snapshot["versions_seen"])
    seen = new_seen.setdefault(as_node, {})
    for chan, _val in writes:  # 归属节点的"见过"推进：它不再被这批写入唤醒
        seen[chan] = next_version(snapshot["channel_versions"].get(chan))
    channels = {}
    for k in snapshot["channel_values"]:
        ch = LastValue(k)
        ch.value = snapshot["channel_values"].get(k)
        ch.version = snapshot["channel_versions"].get(k)
        channels[k] = ch
    updated = set()
    for chan, val in writes:  # 手改写入：版本前进，下游（见过旧版）将被唤醒
        channels[chan].update([val])
        channels[chan].version = next_version(channels[chan].version)
        updated.add(chan)
    snap = {"id": uid("fork"),
            "channel_values": {k: c.get() for k, c in channels.items()},
            "channel_versions": {k: c.version for k, c in channels.items() if c.version},
            "versions_seen": new_seen,
            "updated_channels": sorted(updated)}
    saver.put(thread_id, snap, {"source": "fork", "step": snapshot["step"]})
    return snap, channels, new_seen


def run_from(saver, thread_id, nodes, snapshot, step):
    channels, seen = restore(snapshot, list(snapshot["channel_values"]))
    loop = MiniLoop(nodes, channels, seen, saver, thread_id, step=step)
    while loop.tick():
        loop.after_tick(list(loop.run_tasks()))
    return [t for t in saver.list(thread_id)]


def main() -> None:
    banner("场景 1：跑原线，拿到一条完整的检查点链")
    saver = MiniSaver()
    loop, channels, nodes = build_graph(saver, "main")
    channels[START].update(["go"])
    channels[START].version = 1
    saver.put("main", loop._snapshot([START]), {"source": "input", "step": 0})
    while loop.tick():
        loop.after_tick(list(loop.run_tasks()))
    history = saver.list("main")
    for t in history:
        snap = t["channel_values"]
        print(f"  {t['id']}  source={t['source']:5s} step={t['step']}  "
              f"plan={snap.get('plan')!r:28.28} review={snap.get('review')!r}")

    banner("场景 2：回放 —— 从 step1 的档重跑，逐拍与原线相同")
    replay_saver = MiniSaver()
    step1 = [t for t in history if t["step"] == 1][0]
    run_from(replay_saver, "main", nodes, step1, step=1)
    print("  回放链 vs 原线链（channel_values 逐拍比对）：")
    orig = [t for t in history if t["step"] >= 2]
    replay = [t for t in replay_saver.list("main") if t["source"] == "loop"]
    for a, b in zip(orig, replay):
        same = a["channel_values"] == b["channel_values"]
        print(f"    step{a['step']}: 相同={same}  plan={b['channel_values'].get('plan')!r}")
    print("  → BSP 的确定性在这里兑现：同档 + 同函数 = 同样的后续每一拍")

    banner("场景 3：分叉 —— 手改 step1 的 plan，只有下游重算")
    fork_saver = MiniSaver()
    for t in history:  # 先把原线整体拷进分叉线，模拟"同一条 thread 的历史"
        fork_saver.storage.setdefault("main", []).append(t)
    new_snap, _, _ = fork(fork_saver, "main", step1,
                          [("plan", "方案B：更激进的路线")], as_node="planner")
    print(f"  fork 档已存：{new_snap['id']} source=fork（对应 _loop.py:987）")
    print(f"  手改后 plan = {new_snap['channel_values']['plan']!r}")
    run_from(fork_saver, "main", nodes, new_snap, step=step1["step"])
    print("  分叉后续跑（注意 planner 没有再跑——写入记在它名下）：")
    for t in fork_saver.list("main"):
        tag = " ←原线" if t["id"] in {h["id"] for h in history} else " ←分叉"
        print(f"    {t['id']}  source={t['source']:5s} step={t['step']}{tag}  "
              f"plan={t['channel_values'].get('plan')!r}")
    print("  → reviewer 因 plan 版本前进被唤醒；上游保持不动——重算范围引擎自己算")


if __name__ == "__main__":
    main()
