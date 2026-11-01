# -*- coding: utf-8 -*-
"""
s03_apply_writes.py —— apply_writes：同一拍多节点写同一通道，合并规则谁说了算

s02 看到 after_tick 调 apply_writes 收尾；本课把这个函数拆开。
它真实位于 libs/langgraph/langgraph/pregel/_algo.py:244（实测），
是"一拍的全部写入 → 通道 + 检查点"的唯一入口。五段动作，一段都不能少：

    ① 确定性排序   tasks = sorted(tasks, key=task_path_str)     # :268
    ② versions_seen 落账（先于写入！任务见过的旧版本）            # :275-279
    ③ 消费被读通道 consume()（Topic/Ephemeral 类通道用完即走）    # :301-303
    ④ 按通道分组 → channels[chan].update(vals)（reducer 在此执行）# :315-335
    ⑤ bump_step：本拍没被写的通道也推进版本（Ephemeral 借此清空） # :339-345
       finish：疑似终局时通知所有通道                            # :348-354

冲突问题的答案因此分两层：
    · 键声明了 reducer  → 一拍 N 个值折叠 N 次（_algo.py:331 调到 binop.py:143）
    · 键没声明 reducer  → channels[chan].update() 内部抛 InvalidUpdateError
                          （last_value.py:64，错误码 INVALID_CONCURRENT_GRAPH_UPDATE）
引擎自己从不裁决"听谁的"——它只把写入按通道分组交出去，裁决权全在键声明里。

    同一拍的写入                       apply_writes 内部
    task a: ("logs", "A")  ─┐
    task b: ("logs", "B")  ─┼─→  按通道分组 {"logs": ["A","B"]}
    task c: ("msgs", [...]) ─┘         │
                                       ├─ logs 无 reducer → LastValue.update 抛错
                                       └─ msgs 有 reducer → 逐值折叠

运行：python code.py            （零依赖，离线）
对照真实源码：libs/langgraph/langgraph/pregel/_algo.py（apply_writes :244）
             libs/langgraph/langgraph/channels/{last_value,binop,ephemeral_value}.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.mini_util import banner, expect_error, next_version, NULL_VERSION, uid

START = "__start__"
# 真实引擎里的控制信号常量（constants.py）：出现在写入流里但不进普通通道
CONTROL_MARKERS = {"NO_WRITES", "PUSH", "RESUME", "INTERRUPT", "RETURN", "ERROR"}


# ---------------------------------------------------------------
# 第 1 部分：通道家族（本轮新增 EphemeralValue 与 AfterFinish）
# ---------------------------------------------------------------
class LastValue:
    def __init__(self, key):
        self.key, self.value, self.version = key, None, None

    def update(self, values):
        if not values:
            return False
        if len(values) != 1:  # ★ 冲突裁决点：last_value.py:59-64 原样复刻
            raise InvalidUpdateError(
                f"At key '{self.key}': Can receive only one value per step. "
                "Use an Annotated key to handle multiple values."
            )
        self.value = values[-1]
        return True

    def get(self):
        return self.value

    def is_available(self):
        return self.value is not None

    def update_empty(self):  # bump_step 时的空写入：LastValue 无事发生
        return False

    def finish(self):
        return False


class InvalidUpdateError(Exception):
    pass


class ReducerChannel:
    """带 reducer 的通道：N 个值折叠 N 次（binop.py:123-146 的主干）。"""

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

    def update_empty(self):
        return False

    def finish(self):
        return False


class EphemeralValue:
    """一次性通道：读一次（或拍间空写入）就消失。对应 channels/ephemeral_value.py。

    它的存在解释了 bump_step 为什么必须存在：__start__ 这类通道
    写入一次、触发一拍之后，靠"没被写的通道 update(EMPTY_SEQ)"被清空——
    否则输入通道会永动触发。
    """

    def __init__(self, key):
        self.key, self.value, self.version = key, None, None

    def update(self, values):
        if not values:
            return False
        self.value = values[-1]
        return True

    def get(self):
        return self.value

    def is_available(self):
        return self.value is not None

    def update_empty(self):  # ★ 空写入 = 清空自己（ephemeral 的消费语义）
        self.value = None
        return True

    def finish(self):
        return False


# ---------------------------------------------------------------
# 第 2 部分：主角 apply_writes（对照 _algo.py:244-357 逐段实现）
# ---------------------------------------------------------------
def apply_writes(checkpoint, channels, tasks):
    """把一拍的全部写入应用到通道与检查点，返回本拍被更新的通道集合。"""
    # ① 确定性排序：按任务路径字符串排序（:268）——同样输入永远同样合并序
    tasks = sorted(tasks, key=lambda t: t.path)

    # ② versions_seen 落账：记录任务触达通道的"旧版本"（:275-279，先于写入）
    for t in tasks:
        seen = checkpoint["versions_seen"].setdefault(t.name, {})
        for chan in t.triggers:
            if channels[chan].version is not None:
                seen[chan] = channels[chan].version

    next_version = next_version_of(checkpoint)  # 全通道最高版本 + 1

    # ③ 消费被读通道（:301-303）：真实引擎对 trigger 通道调 consume()
    #    mini 用 EphemeralValue.update_empty 在 ⑤ 里等价呈现消费效果

    # ④ 按通道分组；控制信号不进普通通道（:315-323 的 RESERVED 过滤）
    by_channel: dict = {}
    for t in tasks:
        for chan, val in t.writes:
            if chan in CONTROL_MARKERS:
                continue
            by_channel.setdefault(chan, []).append(val)

    updated = set()
    for chan, vals in by_channel.items():
        if channels[chan].update(vals) and channels[chan].is_available():
            channels[chan].version = next_version          # ★ reducer 在 update 里执行
            checkpoint["channel_versions"][chan] = next_version
            updated.add(chan)

    # ⑤ bump_step（:339-345）：本拍没被写、但可用的通道也"空写入"一次——
    #    Ephemeral 借此清空；所有通道版本单调前进（"步数信号"）。
    bump_step = any(t.triggers for t in tasks)             # :271
    if bump_step:
        for chan, ch in channels.items():
            if ch.is_available() and chan not in updated and ch.update_empty():
                ch.version = next_version
                checkpoint["channel_versions"][chan] = next_version
                updated.add(chan)
    return updated


def next_version_of(checkpoint):
    versions = list(checkpoint["channel_versions"].values())
    return next_version(max(versions) if versions else NULL_VERSION)


class Task:
    """一拍里的一个任务：path 用于排序，triggers 是触发通道，writes 是增量补丁。"""

    def __init__(self, name, path, triggers, writes):
        self.name, self.path, self.triggers, self.writes = name, path, triggers, writes


# ---------------------------------------------------------------
# 第 3 部分：演示
# ---------------------------------------------------------------
def main() -> None:
    banner("场景 1：同拍双写无 reducer 键 → apply_writes 内部抛冲突")
    channels = {"x": LastValue("x"), "logs": LastValue("logs")}
    ckpt = {"channel_versions": {}, "versions_seen": {}}
    tasks = [
        Task("node_b", ("5", "node_b"), ["x"], [("logs", "B 节点写的")]),
        Task("node_a", ("4", "node_a"), ["x"], [("logs", "A 节点写的")]),
    ]
    expect_error("同拍双写 logs", lambda: apply_writes(ckpt, channels, tasks), InvalidUpdateError)
    print("  → 引擎不裁决，键的声明（无 reducer）才是裁决者；错误码 INVALID_CONCURRENT_GRAPH_UPDATE")

    banner("场景 2：同拍三写 reducer 键 → 确定性顺序折叠")
    concat = lambda a, b: a + "|" + b  # 非交换 reducer：顺序错了结果就不同，最能暴露排序
    channels = {"x": LastValue("x"), "plan": ReducerChannel("plan", concat)}
    ckpt = {"channel_versions": {}, "versions_seen": {}}
    tasks = [
        Task("gamma", ("6", "gamma"), ["x"], [("plan", "γ")]),
        Task("alpha", ("4", "alpha"), ["x"], [("plan", "α")]),
        Task("beta", ("5", "beta"), ["x"], [("plan", "β")]),
    ]
    apply_writes(ckpt, channels, tasks)
    print(f"  合并结果: {channels['plan'].get()}  ← 按任务路径排序后的结果，不是完成序")
    print(f"  channel_versions: {ckpt['channel_versions']}")
    print(f"  versions_seen: {ckpt['versions_seen']}  ← 下拍规划的依据（s02）")

    banner("场景 3：bump_step 与 EphemeralValue —— 输入通道为什么不会永动")
    channels = {START: EphemeralValue(START), "plan": LastValue("plan")}
    channels[START].update(["go"])  # 注入输入
    channels[START].version = 1
    ckpt = {"channel_versions": {START: 1}, "versions_seen": {}}
    tasks = [Task("planner", ("1", "planner"), [START], [("plan", "计划")])]
    updated = apply_writes(ckpt, channels, tasks)
    print(f"  本拍被更新通道: {sorted(updated)}")
    print(f"  {START} 通道在拍后 is_available={channels[START].is_available()}（被 bump_step 清空）")
    print("  → 第 2 拍起没有任何东西再触发 planner：Ephemeral 通道用完即走（ephemeral_value.py）")

    banner("场景 4：finish 终局通知 —— 疑似最后一拍时全体通道收到信号")
    print("  apply_writes 的收尾（_algo.py:348-354）：本拍疑似终局且无触发者时，")
    print("  对所有通道调 finish()——LastValueAfterFinish（last_value.py:81）这类通道")
    print("  在 finish 之前不可读，保证'中间态不外泄'。mini 版从略，语义已在上表锚点。")


if __name__ == "__main__":
    main()
