#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s06_memory_checkpointer.py —— 短期记忆与 checkpointer（检查点器）

agent 的"记忆"并不神秘：**短期记忆就是消息列表（state.messages）跨调用存活**。
模型每次都只看到 messages——上一轮说了什么，只要还在列表里，模型就"记得"。
LangGraph 的 agent 把这件事落成两个机制：

  · add_messages reducer（归约器）：节点返回新消息时，按 id **追加或覆盖**，
    消息历史只增不改（AgentState.messages 上挂的就是它，middleware/types.py:349）。
  · checkpointer（检查点器）：每步把 state 快照存档，按 thread_id（线程 id，
    即会话 id）隔离——下一轮 invoke 先取回快照再继续，跨轮记忆、断点续跑、
    时间旅行（time travel，回到任意历史版本）全部由此而来。

    create_agent(model, tools, checkpointer=...)   ← factory.py:891 参数
        └── graph.compile(checkpointer=checkpointer)  ← factory.py:1926

    thread t1: [m1 我叫小明] → [m2 你好小明] → [m3 我叫什么?] → [m4 你是小明]  ← 记得
    thread t2: [m1 我叫什么?] → [m2 抱歉，我不记得]                            ← 隔离

本文件用纯标准库实现：add_messages reducer + MemoryCheckpointer + 带检查点的
mini agent，并演示：多轮记忆、线程隔离、版本回溯（time travel）、同 id 修正。

运行：python code.py          （零依赖，离线；模型由确定性函数 Mock）
对照真实源码（快照 80b7409，行号以源码为准）：
    libs/langchain_v1/langchain/agents/factory.py
        :891  checkpointer: Checkpointer | None = None        参数入口
        :1926 return graph.compile(checkpointer=checkpointer) 传给图引擎
    libs/langchain_v1/langchain/agents/middleware/types.py
        :349  class AgentState（messages 挂 add_messages reducer）
    libs/langchain_v1/langchain/agents/middleware/summarization.py
        :232  class SummarizationMiddleware   长对话的官方记忆策略：超预算先摘要
        :398  def before_model                在模型调用前判断要不要压缩
"""

from __future__ import annotations

import copy
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from mini_util import banner, estimate_tokens, show  # noqa: E402

Message = dict  # {"id": "m1", "role": "user"/"assistant", "content": str}


# ---------------------------------------------------------------
# 第 1 部分：add_messages reducer —— 按 id 追加或覆盖，历史只增不改
# ---------------------------------------------------------------
def add_messages(current: list[Message], new: list[Message]) -> list[Message]:
    """mini reducer：同 id 覆盖（修正），新 id 追加。

    真实实现 langgraph.graph.message.add_messages：消息带 id 时"同 id 替换、
    无 id 追加"，还支持 REMOVE_ALL_MESSAGES 整段清空（factory.py:44 有 import）。
    这是"历史只增不改"不变量的机器保证——修正也是一次显式更新，不是篡改。
    """
    out = list(current)
    index_by_id = {m["id"]: i for i, m in enumerate(out)}
    for m in new:
        if m["id"] in index_by_id:
            out[index_by_id[m["id"]]] = m      # 修正：覆盖同 id
        else:
            index_by_id[m["id"]] = len(out)
            out.append(m)                       # 追加新消息
    return out


# ---------------------------------------------------------------
# 第 2 部分：MemoryCheckpointer —— 按 thread_id 存档 state 快照
# ---------------------------------------------------------------
@dataclass
class Checkpoint:
    version: int
    thread_id: str
    state: dict
    meta: dict = field(default_factory=dict)

    def describe(self) -> str:
        tokens = sum(estimate_tokens(m["content"]) for m in self.state["messages"])
        return (f"v{self.version} thread={self.thread_id} "
                f"消息数={len(self.state['messages'])} 约{tokens}tok {self.meta}")


class MemoryCheckpointer:
    """mini 检查点器：{thread_id: [Checkpoint, ...]}，版本号单调递增。

    真实实现是 langgraph.checkpoint 的 BaseCheckpointSaver（内存/SQLite/Postgres
    等后端可换）——接口语义一致：put 存档、get 取档、list 列版本。
    存取一律深拷贝：**快照必须不可变**，调用方改了自己的引用不能污染存档。
    """

    def __init__(self) -> None:
        self._threads: dict[str, list[Checkpoint]] = {}
        self._counter = 0

    def put(self, thread_id: str, state: dict, meta: dict | None = None) -> Checkpoint:
        self._counter += 1
        cp = Checkpoint(version=self._counter, thread_id=thread_id,
                        state=copy.deepcopy(state), meta=meta or {})
        self._threads.setdefault(thread_id, []).append(cp)
        return cp

    def get(self, thread_id: str, version: int | None = None) -> Checkpoint | None:
        cps = self._threads.get(thread_id)
        if not cps:
            return None
        if version is None:
            cp = cps[-1]
        else:
            cp = next((c for c in cps if c.version == version), None)
        # 取档即深拷贝：真实检查点器从序列化字节（msgpack）重建对象，天然是副本；
        # mini 版用 deepcopy 表达同一不变量——**调用方永远拿不到存档本体**。
        return copy.deepcopy(cp) if cp else None

    def list(self, thread_id: str) -> list[Checkpoint]:
        return list(self._threads.get(thread_id, []))


# ---------------------------------------------------------------
# 第 3 部分：确定性 Mock 模型 + 带检查点的 agent
# ---------------------------------------------------------------
def mock_reply(messages: list[Message]) -> str:
    """确定性回复：记忆完全来自传入的 messages——消息不在，模型就"不记得"。

    这正是短期记忆的机制本质：模型无状态，状态全在消息列表里。
    """
    last = messages[-1]["content"] if messages else ""
    history = " ".join(m["content"] for m in messages)
    # 否定前瞻：匹配"我叫X"但排除"我叫什么"（那是提问，不是自我介绍）
    name_match = re.search(r"我叫(?!什么)([\u4e00-\u9fa5A-Za-z0-9]{1,8})", history)
    name = name_match.group(1) if name_match else None
    if "我叫什么" in last:
        return f"你是{name}。" if name else "抱歉，我还不知道你的名字。"
    if "我叫" in last and name:
        return f"记住啦，{name}！"
    return "（收到）"


class CheckpointedAgent:
    """带检查点的 mini agent：invoke 前取档、结束后存档。"""

    def __init__(self, checkpointer: MemoryCheckpointer) -> None:
        self.checkpointer = checkpointer

    def invoke(self, user_input: str, thread_id: str, from_checkpoint: Checkpoint | None = None) -> str:
        # ① 取回该会话的快照：默认最新；给了 from_checkpoint 就从那一版继续（time travel）
        cp = from_checkpoint if from_checkpoint is not None else self.checkpointer.get(thread_id)
        messages = list(cp.state["messages"]) if cp else []
        messages = add_messages(messages, [{"id": f"m{len(messages)+1}", "role": "user",
                                            "content": user_input}])
        # ② 模型"记得"与否，取决于取回了什么
        reply = mock_reply(messages)
        messages = add_messages(messages, [{"id": f"m{len(messages)+1}", "role": "assistant",
                                            "content": reply}])
        # ③ 存档新版本
        new_cp = self.checkpointer.put(thread_id, {"messages": messages},
                                       meta={"轮次": user_input[:10]})
        print(f"  [checkpoint] {new_cp.describe()}")
        return reply


# ---------------------------------------------------------------
# 第 4 部分：演示
# ---------------------------------------------------------------
def main() -> None:
    banner("场景 1：同一 thread 多轮对话", "记忆成立：模型看到的 messages 跨调用存活")
    cp_store = MemoryCheckpointer()
    agent = CheckpointedAgent(cp_store)
    print(f"  轮1: {agent.invoke('我叫小明，你好', thread_id='t1')}")
    print(f"  轮2: {agent.invoke('我叫什么？', thread_id='t1')}")
    print("  ↑ 轮2 答'你是小明'——不是模型有记忆，是 t1 的消息历史被取回来了")

    banner("场景 2：换 thread（隔离）", "thread_id 是会话边界的唯一钥匙")
    print(f"  t2 轮1: {agent.invoke('我叫什么？', thread_id='t2')}")
    print("  ↑ t2 没有历史 → 模型只能说不记得：隔离即隐私边界")

    banner("场景 3：版本列表与时间旅行", "回到 v1 从那里继续——同一 thread 里 fork 出一条分支")
    for c in cp_store.list("t1"):
        print(f"  {c.describe()}")
    v1 = cp_store.get("t1", version=1)
    print(f"  回到 v1，此时的历史: {[m['content'] for m in v1.state['messages']]}")
    print(f"  从 v1 继续（time travel）: {agent.invoke('我叫什么？', thread_id='t1', from_checkpoint=v1)}")
    print("  ↑ 以 v1 的历史接着走，同样能答出'你是小明'——检查点让任一历史时刻都可续跑")

    banner("场景 4（边界）：add_messages 的同 id 修正", "修正是覆盖，不是追加篡改")
    base = [{"id": "m1", "role": "user", "content": "我叫小明"}]
    fixed = add_messages(base, [{"id": "m1", "role": "user", "content": "（修正）我叫小明明"}])
    appended = add_messages(base, [{"id": "m2", "role": "user", "content": "我叫小明明"}])
    show("同 id 覆盖后", [m["content"] for m in fixed])
    show("新 id 追加后", [m["content"] for m in appended])
    print(f"  ↑ 列表长度：同 id {len(fixed)} 条（覆盖）、新 id {len(appended)} 条（追加）")

    banner("场景 5（边界）：快照不可变", "改了取回来的引用，存档毫发无损")
    v2 = cp_store.get("t1", version=2)
    snapshot_before = copy.deepcopy(v2.state["messages"])
    v2.state["messages"].clear()  # 恶意/失误清空
    restored = cp_store.get("t1", version=2).state["messages"]
    print(f"  存档未被污染: {restored == snapshot_before}")

    print("\n结论：短期记忆 = 消息列表跨调用存活；检查点 = 按 thread_id 的不可变快照流。")
    print("长对话塞不下时怎么办？官方答案就是中间件：SummarizationMiddleware 超预算先摘要（summarization.py:232）。")


if __name__ == "__main__":
    main()
