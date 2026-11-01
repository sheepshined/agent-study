# -*- coding: utf-8 -*-
"""
s07_subgraph.py —— subgraph：把整张图当作另一个图的一个节点

多 agent 系统的基本形状是"图里有图"：监督者（父图）把一个子任务整个
交给一台子 agent（子图），拿回结果继续。LangGraph 的做法朴素到惊人：
**子图就是一个编译好的 CompiledStateGraph，add_node 时它和普通函数
长得一模一样**（节点是 Runnable，函数只是最短的那种 Runnable）。

三个关键语义（都可在源码核实）：

  ① 状态隔离：子图有自己的 schema。父图与子图**同名键**自然透传
     （input/output 重叠的键），子图私有的键留在子图里，父图看不见。
  ② 命名空间嵌套：子图的检查点存在 `父命名空间:节点名:task_id` 之下。
     _algo.py:626（实测）：checkpoint_ns = f"{parent_ns}{NS_SEP}{name}"，
     task_checkpoint_ns = f"{checkpoint_ns}{NS_END}{task_id}"。
     → 每台子图有自己完整的检查点链（Studio 里能看到子图逐拍历史）。
  ③ checkpointer 继承：子图 compile 不传 checkpointer 时可继承父图的
     （graph/state.py:1214 docstring："may inherit the parent graph's
     checkpointer when used as a subgraph"）。

    父图（BSP 引擎）                         子图（自己的 BSP 引擎）
    ┌──────────────────────┐   任务执行    ┌──────────────────────┐
    │ 超步1: supervisor     │ ──────────→ │ 超步1: research       │
    │   交任务(task=...)    │  输入=同名键  │ 超步2: draft          │
    │                       │ ←────────── │ 超步3: (自己的收尾)    │
    │ 超步2: reviewer       │  输出=同名键  │  私有键 notes 不外传   │
    └──────────────────────┘              └──────────────────────┘
      子图的 N 拍在父图里只算 1 拍的一个任务——嵌套即递归，无需特殊机制。

运行：python code.py            （零依赖，离线）
对照真实源码：libs/langgraph/langgraph/pregel/_algo.py:626（命名空间嵌套）
             libs/langgraph/langgraph/graph/state.py:1214（checkpointer 继承）
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.mini_util import banner, next_version, uid, NULL_VERSION

START = "__start__"
NS_SEP, NS_END = ":", "|"   # 真实引擎的命名空间分隔符（constants.NS_SEP/NS_END）


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


class SubgraphSpec:
    """一个"可编译图"的规格：节点表 + 输入/输出键（与父图重叠的同名键）。

    input_keys/output_keys 就是"透传面"——同名键过界，其余键隔离。
    """

    def __init__(self, name, nodes, input_keys, output_keys, keys, stop=25):
        self.name, self.nodes = name, nodes
        self.input_keys, self.output_keys = input_keys, output_keys
        self.keys = keys              # 子图自己的 schema：全部通道键（schema 隔离的实体）
        self.stop = stop


class MiniSaver:
    """按命名空间分桶的存取器：ns="" 是父图，ns="worker|task-id" 是子图。"""

    def __init__(self):
        self.storage: dict[tuple[str, str], list[dict]] = {}

    def put(self, thread_id, ns, snapshot, metadata):
        self.storage.setdefault((thread_id, ns), []).append({**snapshot, **metadata})

    def list(self, thread_id, ns):
        return list(self.storage.get((thread_id, ns), []))


class MiniLoop:
    """s04 引擎 + 命名空间感知的存档。子图循环就是同一个类的另一次实例化。"""

    def __init__(self, nodes, channels, versions_seen, saver, thread_id,
                 ns="", step=0, stop=25):
        self.nodes = {n.name: n for n in nodes}
        self.channels = channels
        self.versions_seen = versions_seen
        self.saver, self.thread_id, self.ns = saver, thread_id, ns
        self.step, self.stop, self.status = step, stop, "pending"

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
            if isinstance(node.fn, SubgraphSpec):   # ★ 节点是一张子图
                yield node.name, list(self._run_subgraph(node.fn, state).items()), None
            else:
                yield node.name, list(node.fn(state).items()), None

    def _run_subgraph(self, spec: SubgraphSpec, state):
        """子图的全部人生：建通道 → 注入同名键 → 自己的 while tick() 循环。"""
        # 子图自己的 schema：全部键都建通道（"notes" 之类私有键与父图无关）
        sub_channels = {k: LastValue(k) for k in [START, *spec.keys]}
        for k in spec.input_keys:
            sub_channels[k].update([state.get(k)])
            sub_channels[k].version = 1
        sub_channels[START].update(["go"])   # 注入输入 → 触发子图第一拍
        sub_channels[START].version = 1
        task_ns = f"{self.ns}{NS_SEP}{spec.name}{NS_END}{uid('task')}"
        print(f"      [子图 {spec.name}] 命名空间 {task_ns!r}（父={self.ns or '根'!r}）")
        sub_loop = MiniLoop(spec.nodes, sub_channels, {}, self.saver,
                            self.thread_id, ns=task_ns, stop=spec.stop)
        self.saver.put(self.thread_id, task_ns, _snap(sub_channels, {}),
                       {"source": "input", "step": 0})
        while sub_loop.tick():
            sub_loop.after_tick(list(sub_loop.run_tasks()))
        # out_of_steps 在 tick 返回 False 那一刻才置位——检查必须放在循环外
        if sub_loop.status == "out_of_steps":
            raise RuntimeError(f"子图 {spec.name} 超出步数上限（父图任务失败）")
        print(f"      [子图 {spec.name}] 跑完 {sub_loop.step} 拍")
        # 输出透传：只有 output_keys 过界；私有键 notes 留在子图命名空间里
        return {k: sub_channels[k].get() for k in spec.output_keys}

    def after_tick(self, results):
        normal = [(n, w) for n, w, err in results if err is None]
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
        self.saver.put(self.thread_id, self.ns, _snap(self.channels, self.versions_seen),
                       {"source": "loop", "step": self.step})


def _snap(channels, versions_seen):
    return {
        "id": uid("ckpt"),
        "channel_values": {k: c.get() for k, c in channels.items()},
        "channel_versions": {k: c.version for k, c in channels.items() if c.version},
        "versions_seen": {k: dict(v) for k, v in versions_seen.items()},
    }


def main() -> None:
    banner("场景 1：父图 → 子图 —— 同名键透传，私有键隔离")

    def supervisor(state):
        print(f"    [supervisor] 收到指令 {state.get(START)!r}，派活")
        return {"task": f"{state.get(START)}（已分派）"}

    # 子图：research → draft。它有自己的生命周期与私有键 notes。
    research = lambda s: (print(f"      [research] 读 task={s.get('task')!r}") or {"findings": "3 条线索"})
    draft = lambda s: (print(f"      [draft] 写报告（私有笔记 notes 记一下）")
                       or {"report": f"报告·基于{s.get('findings')}"})
    worker = SubgraphSpec("worker", [Node("research", research, [START]),
                                     Node("draft", draft, ["findings"])],
                          input_keys=["task"], output_keys=["report"],
                          keys=["task", "findings", "report", "notes"])

    def reviewer(state):
        print(f"    [reviewer] 拿到 report={state.get('report')!r}")
        print(f"    [reviewer] 想看子图的 notes？根本没有这个键——状态隔离")
        return {"final": "通过"}

    saver = MiniSaver()
    channels = {k: LastValue(k) for k in [START, "task", "report", "final"]}
    channels[START].update(["调研 LangGraph"])
    channels[START].version = 1
    nodes = [Node("supervisor", supervisor, [START]),
             Node("worker", worker, ["task"]),      # ★ 子图就位：和普通节点同一种挂法
             Node("reviewer", reviewer, ["report"])]
    loop = MiniLoop(nodes, channels, {}, saver, "t1")
    saver.put("t1", "", _snap(channels, {}), {"source": "input", "step": 0})
    while loop.tick():
        loop.after_tick(list(loop.run_tasks()))
    print(f"  父图终态 keys={sorted(k for k in channels if channels[k].value is not None)}")
    print("  → 'notes'/'findings' 不在其中：子图私有键从未过界；task 进、report 出（透传面）")
    print("  ★ 若把 output_keys 加上 'task'（worker 触发又回写同一键），worker 会自我唤醒")
    print("    无限循环到 recursion_limit——子图拓扑同样要遵守版本差分规则")

    banner("场景 2：命名空间嵌套 —— 子图有自己完整的检查点链")
    for (tid, ns), chain in saver.storage.items():
        print(f"  ns={ns!r:40s} {len(chain)} 条档（最新 step={chain[-1].get('step')}）")
    print("  → 对照 _algo.py:626：子图档在 '父:节点名|task-id' 之下，逐拍可回放（s05 的能力原样可用）")

    banner("场景 3：失败路径 —— 子图超限，异常上抛给父图任务")
    bad = SubgraphSpec(
        "worker_bad",
        [Node("seed", lambda s: {"report": "r1"}, [START]),            # 启动节点
         Node("spinning", lambda s: {"report": "r2"}, ["report"])],    # 自环：触发又回写 report
        input_keys=["task"], output_keys=["report"],
        keys=["task", "report", "notes"], stop=2)                      # 步数上限兜底
    channels3 = {k: LastValue(k) for k in [START, "task", "report"]}
    channels3["task"].update(["死循环任务"])
    channels3["task"].version = 1
    loop3 = MiniLoop([Node("worker_bad", bad, ["task"])], channels3, {}, saver, "t2", stop=25)
    try:   # 真实引擎：节点异常未经 error handler 时，invoke 直接向调用方抛出
        while loop3.tick():
            results = list(loop3.run_tasks())
            loop3.after_tick(results)
    except RuntimeError as e:
        print(f"    父图 invoke 收到异常: {e}")
    print("  → 子图的 out_of_steps 在父图眼里只是一个任务失败——边界清晰，责任也清晰")


if __name__ == "__main__":
    main()
