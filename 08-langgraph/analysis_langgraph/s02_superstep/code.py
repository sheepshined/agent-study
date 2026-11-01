# -*- coding: utf-8 -*-
"""
s02_superstep.py —— Pregel/BSP 引擎：一拍（superstep）的一生

LangGraph 引擎的执行模型借自 Google Pregel 论文的 BSP
（Bulk Synchronous Parallel，整体同步并行）：计算分成一拍一拍的
**超步（superstep）**，超步内所有活跃节点并发执行、互不通信，
超步之间同步一次、统一写入。主循环上方那四行官方注释就是定义
（libs/langgraph/langgraph/pregel/main.py:2970-2974，实测行号）：

    # Similarly to Bulk Synchronous Parallel / Pregel model
    # computation proceeds in steps, while there are channel updates.
    # Channel updates from step N are only visible in step N+1
    # channels are guaranteed to be immutable for the duration of the step,
    # with channel updates applied only at the transition between steps.

翻译：① 只要通道还有更新就继续拍；② 第 N 拍的写入，第 N+1 拍才可见；
③ 拍进行中通道不可变；④ 写入只在拍间统一生效。

主循环本体（main.py:2975-2996）：

    while loop.tick():                 # 规划：这一拍跑谁？  _loop.py:611
        for _ in runner.tick(...):     # 执行：线程池并发跑任务 _runner.py:176
            yield from _output(...)    # 流式产出（本课省略）
        loop.after_tick()              # 写回：apply_writes + 存档 _loop.py:697

"边"在这里露出真相：a→b 不是函数调用，而是 **b 在 a 写过的通道上
注册了触发条件**——a 写入使通道版本前进，b 因"版本差"被规划进下一拍。

    ┌──────────────── 超步 N ────────────────┐
    │ tick()    规划：版本对比 → 任务列表      │
    │ runner.tick() 执行：读通道 → 跑节点函数   │
    │ after_tick()  写回：合并写入 → 版本前进   │
    └────────────────────────────────────────┘
                      │ 写入下一拍才可见
                      ▼
    ┌──────────────── 超步 N+1 ───────────────┐
    │ tick() 重新规划：版本变了的触发者才上榜…… │
    └─────────────────────────────────────────┘

运行：python code.py            （零依赖，离线）
对照真实源码：libs/langgraph/langgraph/pregel/{main.py,_loop.py,_runner.py,_algo.py}
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.mini_util import banner, next_version, NULL_VERSION

START = "__start__"  # 真实源码 constants.START：入口伪通道，它的写入只触发第一拍


# ---------------------------------------------------------------
# 第 1 部分：通道（s01 的浓缩版，够本课用）
# ---------------------------------------------------------------
class LastValue:
    """默认通道：一拍只收一个值；版本号记录"上次被写是第几拍之前"。"""

    def __init__(self, key: str):
        self.key = key
        self.value = None
        self.version = None  # None = 从未被写（对应真实引擎的 null_version 语义）

    def update(self, values: list) -> bool:
        if not values:
            return False
        assert len(values) == 1, "LastValue 一拍只收一个值（s01 已演示冲突）"
        self.value = values[-1]
        return True

    def get(self):
        return self.value


# ---------------------------------------------------------------
# 第 2 部分：任务规划 —— 版本差分触发（"边"的运行时真相）
# ---------------------------------------------------------------
class Node:
    """节点 = 函数 + 触发条件。triggers 是它监听的通道名列表。

    真实源码里触发条件挂在 PregelNode.triggers 上（pregel/_read.py:97），
    `add_edge("a", "b")` 在编译时做的事就是给 b 的 triggers 里加 "a" 写的通道。
    """

    def __init__(self, name, fn, triggers):
        self.name, self.fn, self.triggers = name, fn, triggers


def should_trigger(node: Node, channels: dict, versions_seen: dict) -> bool:
    """版本差分：任一触发通道"当前版本 > 我见过的版本"才触发。

    逐行对应 libs/langgraph/langgraph/pregel/_algo.py:1272 的 _triggers：
        versions.get(chan, null_version) > seen.get(chan, null_version)   # :1285-1288
    这就是"边"的运行时真相——不是图遍历，是版本比较。
    """
    seen = versions_seen.get(node.name, {})
    for chan in node.triggers:
        cur = channels[chan].version if channels[chan].version is not None else None
        if cur is not None and cur > seen.get(chan, NULL_VERSION):
            return True
    return False


# ---------------------------------------------------------------
# 第 3 部分：一拍的三段式 —— tick / 执行 / after_tick
# ---------------------------------------------------------------
class MiniLoop:
    """PregelLoop 的教学版（真实实现在 pregel/_loop.py:611 tick / :697 after_tick）。

    状态四件套就是 Checkpoint 的全部家底（s04 展开）：
      channels        通道值 + 当前版本
      versions_seen   节点名 -> 它见过的通道版本（规划依据）
      step / stop     当前拍号 / 递归上限
    """

    def __init__(self, nodes, channels, versions_seen, stop=25):
        self.nodes, self.channels = nodes, channels
        self.node_map = {n.name: n for n in nodes}
        self.versions_seen = versions_seen
        self.step, self.stop = 0, stop
        self.status = "pending"
        self.tasks: dict = {}          # 本拍任务表
        self.updated_channels: set = set()

    # ---- 第一拍：tick —— 只规划，不执行（_loop.py:611-691）----
    def tick(self) -> bool:
        if self.step > self.stop:                       # :617-619
            self.status = "out_of_steps"
            return False
        self.tasks = {n.name: n for n in self.nodes if should_trigger(n, self.channels, self.versions_seen)}
        print(f"  [tick]     超步 {self.step}：规划出任务 {[t for t in self.tasks]}")
        if not self.tasks:                              # :661-663 通道不再触发任何节点
            self.status = "done"
            return False
        self.step += 1
        return True

    # ---- 第二拍：执行 —— 真实引擎交给 Runner 线程池（_runner.py:176）----
    def run_tasks(self):
        for name, node in self.tasks.items():
            state = {k: ch.get() for k, ch in self.channels.items() if ch.value is not None}
            patch = node.fn(state)                       # 节点读 state，交增量补丁
            yield name, list(patch.items())              # 产出 writes（不在此刻生效！）

    # ---- 第三拍：after_tick —— 统一写回（_loop.py:697-742）----
    def after_tick(self, task_writes: list):
        n = sum(len(w) for _, w in task_writes)
        print(f"  [after_tick] 超步 {self.step}：统一应用写入 {n} 条")
        # ① 先记录"见过"的版本——必须在写入应用之前！任务是被"旧版本差"
        #    唤醒的，它见过的是旧版本（对应 _algo.py:275-279 的位置）。
        #    记成新版本的话，本轮被更新的触发通道将永远不再触发任何人。
        for name, _ws in task_writes:
            node = self.node_map[name]
            seen = self.versions_seen.setdefault(name, {})
            for chan in node.triggers:
                if self.channels[chan].version is not None:
                    seen[chan] = self.channels[chan].version
        # ② 按通道分组应用写入（_algo.py:315-331）
        by_channel: dict = {}
        for _name, writes in task_writes:
            for chan, val in writes:
                by_channel.setdefault(chan, []).append(val)
        self.updated_channels = set()
        for chan, vals in by_channel.items():
            ch = self.channels[chan]
            if ch.update(vals) and ch.is_available():
                ch.version = next_version(ch.version)    # 版本前进（_algo.py:331-335）
                self.updated_channels.add(chan)
        print(f"  [checkpoint] 存档 @ 超步 {self.step}（每拍必存，s04 展开）")


# 通道加一个小助手，避免污染主类
LastValue.is_available = lambda self: self.value is not None


# ---------------------------------------------------------------
# 第 4 部分：组装引擎并演示
# ---------------------------------------------------------------
def build_engine():
    """三节点图：START → write_plan → {critic, planner2}。

    write_plan 写 plan 通道；critic 与 planner2 都监听 plan——
    所以超步 1 只有 write_plan 跑，超步 2 它俩并发跑（同拍互不可见）。
    """
    def write_plan(state):
        print(f"    write_plan 读到: plan=None（它自己是第 1 拍）")
        return {"plan": "三步走计划"}

    def critic(state):
        print(f"    critic    读到: plan='{state.get('plan')}' ← 第 2 拍才可见")
        return {"verdict": "有 1 个漏洞"}

    def planner2(state):
        print(f"    planner2  读到: plan='{state.get('plan')}' verdict=None（同拍不共享）")
        return {"notes": "并行节点互不知道对方"}

    nodes = [
        Node("write_plan", write_plan, [START]),
        Node("critic", critic, ["plan"]),
        Node("planner2", planner2, ["plan"]),
    ]
    channels = {k: LastValue(k) for k in [START, "plan", "verdict", "notes"]}
    channels[START].update(["go"])                       # 注入输入 → 触发第一拍
    channels[START].version = next_version(None)
    return MiniLoop(nodes, channels, versions_seen={}), channels


def main() -> None:
    banner("场景 1：完整三拍循环 —— 第 N 拍写入，第 N+1 拍才可见")
    loop, _ = build_engine()
    print("  图：START → write_plan → {critic, planner2}（后两者都监听 plan）")
    while loop.tick():
        writes = list(loop.run_tasks())
        loop.after_tick(writes)
    print(f"  结局 status={loop.status}：通道不再触发新任务 → done（_loop.py:661）")

    banner("场景 2：递归上限 —— out_of_steps 保护")
    loop2, _ = build_engine()
    loop2.stop = 1                                       # 故意只许 1 拍
    while loop2.tick():
        loop2.after_tick(list(loop2.run_tasks()))
    print(f"  结局 status={loop2.status}（对应 :617 的 step > stop 守卫，")
    print("  真实默认 recursion_limit=25——死环图靠它兜底）")

    banner("场景 3：同一拍的两个并发节点，读写彼此隔离")
    print("  场景 1 的输出已证明：critic 与 planner2 在同一拍都读到了 plan，")
    print("  但 planner2 读不到 critic 同拍写的 verdict——通道在拍内不可变（main.py:2973）。")


if __name__ == "__main__":
    main()
