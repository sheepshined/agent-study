# -*- coding: utf-8 -*-
"""
s04_checkpoint.py —— Checkpoint：每拍必存，任意一拍可恢复

LangGraph 敢说"durable execution（持久化执行）"的底气就一句话：
**每一拍结束都写一份检查点（checkpoint，状态快照）**。写入点在
after_tick 里（libs/langgraph/langgraph/pregel/_loop.py:734，实测）：

    self._put_checkpoint({"source": "loop"})     # 每拍必存

存档时机共三类（同一函数，metadata.source 不同）：
    source="input"  输入落地时        _loop.py:1049
    source="loop"   每拍收尾时        _loop.py:734   ← 本课主角
    source="fork"   时间旅行分叉时    _loop.py:987   （s05 的主角）

Checkpoint 的六个字段就是"任意一拍可恢复"的全部家底
（libs/checkpoint/langgraph/checkpoint/base/__init__.py:93-124）：

    v                 格式版本（当前 1）
    id                唯一且单调递增 → 检查点天然是一条可排序的链
    ts                ISO 8601 时间戳
    channel_values    各通道的值（状态本体）
    channel_versions  通道名 → 版本号（下一拍规划依据之一）
    versions_seen     节点名 → 它见过的版本（另一依据）

存取接口是 BaseCheckpointSaver（base/__init__.py:177）：put / get_tuple /
list / delete_thread 四个方法——Sqlite/Postgres 各自实现，学习期 InMemory 够用。
thread_id 是存档槽位的 key：同一 thread 反复 invoke，状态自动续接。

    超步1 ──→ after_tick ──→ saver.put(ckpt#1, source=loop)
    超步2 ──→ after_tick ──→ saver.put(ckpt#2, source=loop)
      ...                          │
    任一拍崩溃                      ▼
    新进程: saver.get_tuple(thread) → 拿到最新档 → 恢复通道/版本 → 继续拍

运行：python code.py            （零依赖，离线）
对照真实源码：libs/checkpoint/langgraph/checkpoint/base/__init__.py
             libs/langgraph/langgraph/pregel/_loop.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.mini_util import banner, next_version, uid, NULL_VERSION

START = "__start__"


# ---------------------------------------------------------------
# 第 1 部分：Checkpoint 结构（对照 base/__init__.py:93-124 逐字段）
# ---------------------------------------------------------------
@dataclass
class Checkpoint:
    v: int = 1
    id: str = ""                                        # 单调递增、可排序（:98-102）
    ts: str = ""                                        # ISO 8601（:103）
    channel_values: dict = field(default_factory=dict)  # 状态本体（:105）
    channel_versions: dict = field(default_factory=dict)  # 通道 → 版本（:110）
    versions_seen: dict = field(default_factory=dict)   # 节点 → 见过的版本（:116）
    updated_channels: list | None = None                # 本档新增（:122）

    @staticmethod
    def from_channels(channels, versions_seen, updated):
        return Checkpoint(
            id=uid("ckpt"),                             # 真实 id 由 uuid5/xxh3 派生
            ts=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            channel_values={k: c.get() for k, c in channels.items()},
            channel_versions={k: c.version for k, c in channels.items() if c.version},
            versions_seen={k: dict(v) for k, v in versions_seen.items()},
            updated_channels=sorted(updated),
        )


@dataclass
class CheckpointTuple:
    """存档读出物：config 定位 + 检查点本体 + 父档指针（base/__init__.py:140）。"""

    config: dict
    checkpoint: Checkpoint
    metadata: dict
    parent_config: dict | None = None


# ---------------------------------------------------------------
# 第 2 部分：MiniSaver —— BaseCheckpointSaver 的四方法接口
# ---------------------------------------------------------------
class MiniSaver:
    """对应 BaseCheckpointSaver（:177）：put :278 / get_tuple :240 / list :254。

    真实实现还要求序列化器（serde）；InMemorySaver 免序列化，mini 同。
    """

    def __init__(self):
        self.storage: dict[str, list[CheckpointTuple]] = {}  # thread_id → 链

    def put(self, thread_id: str, checkpoint: Checkpoint, metadata: dict) -> None:
        chain = self.storage.setdefault(thread_id, [])
        parent = chain[-1].config if chain else None
        chain.append(CheckpointTuple({"thread_id": thread_id, "checkpoint_id": checkpoint.id},
                                     checkpoint, metadata, parent))

    def get_tuple(self, thread_id: str) -> CheckpointTuple | None:
        chain = self.storage.get(thread_id)
        return chain[-1] if chain else None

    def list(self, thread_id: str) -> list[CheckpointTuple]:
        return list(self.storage.get(thread_id, []))


# ---------------------------------------------------------------
# 第 3 部分：把存档织进引擎 —— after_tick 的最后一步
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
    """s02 的引擎 + 存档。注意 tick 的规划逻辑一行未变——恢复全靠 checkpoint。"""

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
            try:
                yield node.name, list(node.fn(state).items()), None
            except Exception as exc:  # 崩溃的任务：写入只到一半，通道分毫未动
                yield node.name, [], exc

    def after_tick(self, results):
        writes = [(n, w) for n, w, err in results if not err]
        for name, _ws in [(n, w) for n, w, err in results if not err]:
            node = self.nodes[name]
            seen = self.versions_seen.setdefault(name, {})
            for chan in node.triggers:
                if self.channels[chan].version is not None:
                    seen[chan] = self.channels[chan].version
        by_channel: dict = {}
        for _n, ws in writes:
            for chan, val in ws:
                by_channel.setdefault(chan, []).append(val)
        updated = set()
        for chan, vals in by_channel.items():
            ch = self.channels[chan]
            if ch.update(vals) and ch.is_available():
                ch.version = next_version(ch.version)
                updated.add(chan)
        # ★ 每拍必存（_loop.py:734）：在写入应用之后、下一拍规划之前
        self.saver.put(self.thread_id,
                       Checkpoint.from_channels(self.channels, self.versions_seen, updated),
                       {"source": "loop", "step": self.step})


def main() -> None:
    banner("场景 1：跑一个三节点图，数一数检查点链")
    saver = MiniSaver()
    thread = {"thread_id": "t1"}
    channels = {k: LastValue(k) for k in [START, "plan", "review", "archive"]}
    channels[START].update(["go"])
    channels[START].version = 1

    # 注意 archiver 写的是"archive"而不是"plan"——若它也写 plan，reviewer 会被
    # 重新唤醒、无限循环到 recursion_limit（试着改一下就能看到 out_of_steps）。
    nodes = [
        Node("planner", lambda s: (print(f"    planner: 收到输入 {s.get(START)!r}") or {"plan": "三步走"}), [START]),
        Node("reviewer", lambda s: (print(f"    reviewer: 审 plan={s.get('plan')!r}") or {"review": "通过"}), ["plan"]),
        Node("archiver", lambda s: (print(f"    archiver: 归档 review={s.get('review')!r}") or {"archive": "done"}), ["review"]),
    ]
    loop = MiniLoop(nodes, channels, {}, saver, "t1")
    saver.put("t1", Checkpoint.from_channels(channels, {}, {START}), {"source": "input", "step": 0})
    while loop.tick():
        loop.after_tick(list(loop.run_tasks()))

    print(f"\n  检查点链（saver.list）共 {len(saver.list('t1'))} 条：")
    for t in saver.list("t1"):
        ck = t.checkpoint
        print(f"    {ck.id}  source={t.metadata['source']:5s} step={t.metadata['step']}  "
              f"values={ {k: v for k, v in ck.channel_values.items() if v is not None} }")
    print("  → 每拍一条、id 单调递增：时间旅行的基础设施已就位（s05）")

    banner("场景 2：第 2 拍崩溃 → 新进程从最新档恢复，状态分毫未丢")
    saver2 = MiniSaver()
    crashed = []

    def boom(state):
        raise RuntimeError("数据库连接中断（模拟崩溃）")

    channels2 = {k: LastValue(k) for k in [START, "plan", "review"]}
    channels2[START].update(["go"])
    channels2[START].version = 1
    nodes2 = [
        Node("planner", lambda s: {"plan": "三步走"}, [START]),
        Node("reviewer", boom, ["plan"]),  # 第 2 拍崩溃
    ]
    loop2 = MiniLoop(nodes2, channels2, {}, saver2, "t2")
    saver2.put("t2", Checkpoint.from_channels(channels2, {}, {START}), {"source": "input", "step": 0})
    while loop2.tick():
        results = []
        for name, ws, err in loop2.run_tasks():
            if err:
                crashed.append(loop2.step)
                print(f"    [超步 {loop2.step}] 任务 {name} 崩溃: {err}")
            results.append((name, ws, err))
        loop2.after_tick(results)
        if crashed:
            break  # 进程"死"在这里
    print(f"  崩溃后 saver 里的最新档：", end=" ")
    last = saver2.get_tuple("t2")
    print(f"{last.checkpoint.id} step={last.metadata['step']} values={last.checkpoint.channel_values}")

    # ---- 新进程：全新的引擎对象，从存档恢复 ----
    ck = last.checkpoint
    channels3 = {}
    for k, v in ck.channel_values.items():   # ① 通道值与版本号一并恢复
        ch = LastValue(k)
        ch.value = v
        ch.version = ck.channel_versions.get(k)
        channels3[k] = ch
    loop3 = MiniLoop(  # ② versions_seen 也恢复——规划逻辑无缝续接
        [Node("reviewer", lambda s: {"review": "重试后通过"}, ["plan"])],
        channels3, ck.versions_seen, saver2, "t2",
        step=last.metadata["step"])
    print("  新进程恢复完成，继续拍：")
    while loop3.tick():
        loop3.after_tick(list(loop3.run_tasks()))
    print(f"  续跑结局 status={loop3.status}；plan={channels3['plan'].get()} review={channels3['review'].get()}")
    print("  → 崩溃只损失'崩溃那一拍'，已完成的拍全部在档（durable execution 的字面含义）")

    banner("场景 3：Checkpoint 六字段逐一核对")
    ck3 = saver.get_tuple("t1").checkpoint
    for name in ["v", "id", "ts", "channel_values", "channel_versions", "versions_seen", "updated_channels"]:
        print(f"    {name:17s} = {getattr(ck3, name)}")
    print("  → 对照 base/__init__.py:93-124：六个字段 + updated_channels，一样不少")


if __name__ == "__main__":
    main()
