#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s08_rag_retriever.py —— RAG：mini 内存检索器 + 检索工具化

RAG（Retrieval-Augmented Generation，检索增强生成）= 先检索外部知识，
再让模型带着检索结果作答。在 agent 语境下它的正确形态是**把检索器做成工具**：

    文档 ──split──▶ chunks ──embed──▶ 向量库        （入库，一次性）
                                        │
    用户问题 ──▶ 模型 ──要工具?──▶ search_docs 工具   （检索，每问一次）
                     ▲                    │ top-k Document
                     └──(带着引文作答)◀────┘

LangChain 把这条链拆成四个标准件（本文件各有一个 mini 影子）：

  · Document（documents/base.py:288）：page_content + metadata——metadata 是
    引文（来源/页码）的家。
  · TextSplitter（RecursiveCharacterTextSplitter，text-splitters character.py:91）：
    按 "\n\n" → "\n" → "。" → 硬切 递归降级，尽量保住语义单元。
  · VectorStore（vectorstores/base.py:43：add_texts :46 / similarity_search :361）：
    mini 版用字符 bigram + 余弦相似度，纯标准库、完全离线。
  · Retriever（retrievers.py:55：BaseRetriever 也是 Runnable）→ create_retriever_tool
    （tools/retriever.py:31）：**检索器包装成工具，agent 才能自主决定"查不查、查什么"**。

运行：python code.py          （零依赖，离线；向量是字符 bigram，模型由脚本化 Mock）
对照真实源码（快照 80b7409，行号以源码为准）：
    libs/core/langchain_core/documents/base.py        :288 class Document(BaseMedia)
    libs/text-splitters/langchain_text_splitters/character.py  :91 RecursiveCharacterTextSplitter
    libs/core/langchain_core/vectorstores/base.py
        :43  class VectorStore(ABC)      :46 def add_texts      :361 def similarity_search
    libs/core/langchain_core/retrievers.py            :55 class BaseRetriever(RunnableSerializable, ABC)
    libs/core/langchain_core/tools/retriever.py       :31 def create_retriever_tool
    libs/core/langchain_core/tools/base.py            :433 class BaseTool
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from math import sqrt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from mini_util import banner, show  # noqa: E402

# ---------------------------------------------------------------
# 第 1 部分：Document 与递归切分
# ---------------------------------------------------------------
@dataclass
class Document:
    """文档最小单元（documents/base.py:288）：内容 + 元数据（引文的来源）。"""

    page_content: str
    metadata: dict = field(default_factory=dict)


SEPARATORS = ["\n\n", "\n", "。", "；", " "]


def recursive_split(text: str, chunk_size: int, seps: list[str] | None = None) -> list[str]:
    """递归字符切分（RecursiveCharacterTextSplitter，character.py:91 的影子）：

    想法是"尽量在大缝上切"：段落切不动再切句子，句子切不动再硬切——
    保住语义单元，而不是把一段话拦腰斩断。
    """
    seps = seps if seps is not None else SEPARATORS
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    if not seps:
        # 全部缝都切不动：硬切（真实实现用 tokenizer 计数，这里用字符数）
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
    sep, rest = seps[0], seps[1:]
    pieces = text.split(sep) if sep else [text]
    chunks: list[str] = []
    buf = ""
    for piece in pieces:
        candidate = f"{buf}{sep}{piece}" if buf else piece
        if len(candidate) <= chunk_size:
            buf = candidate
            continue
        if buf:
            chunks.append(buf)
        buf = piece if len(piece) <= chunk_size else ""
        if not buf:  # 单片仍超长：递归降级到更细的缝
            chunks.extend(recursive_split(piece, chunk_size, rest))
    if buf:
        chunks.append(buf)
    return chunks


# ---------------------------------------------------------------
# 第 2 部分：内存向量库 —— 字符 bigram + 余弦相似度（零依赖）
# ---------------------------------------------------------------
def bigram_vector(text: str) -> Counter:
    t = re.sub(r"\s+", "", text)
    grams = [t[i:i + 2] for i in range(len(t) - 1)]
    return Counter(grams if grams else [t])


def cosine(a: Counter, b: Counter) -> float:
    common = set(a) & set(b)
    dot = sum(a[g] * b[g] for g in common)
    na, nb = sqrt(sum(v * v for v in a.values())), sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


class InMemoryVectorStore:
    """mini 向量库（vectorstores/base.py:43 的影子）：add_texts / similarity_search。"""

    def __init__(self) -> None:
        self.docs: list[Document] = []
        self.vectors: list[Counter] = []

    def add_texts(self, texts: list[str], metadatas: list[dict] | None = None) -> int:
        """入库（:46）。真实实现会调 Embeddings 模型；mini 版是确定性 bigram。"""
        metadatas = metadatas or [{} for _ in texts]
        for text, meta in zip(texts, metadatas):
            self.docs.append(Document(page_content=text, metadata=meta))
            self.vectors.append(bigram_vector(text))
        return len(texts)

    def similarity_search(self, query: str, k: int = 2) -> list[tuple[Document, float]]:
        """相似检索（:361）：返回 top-k（Document, 分数）。"""
        qv = bigram_vector(query)
        scored = [(doc, cosine(qv, vec)) for doc, vec in zip(self.docs, self.vectors)]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]


# ---------------------------------------------------------------
# 第 3 部分：检索器 → 检索工具（RAG 接上 agent 的关键一步）
# ---------------------------------------------------------------
class MiniRetriever:
    """检索器（retrievers.py:55 BaseRetriever 的影子）：invoke(query) → list[Document]。

    真实 BaseRetriever 是 RunnableSerializable——检索器也能 | 进链（s02 的协议）。
    """

    def __init__(self, store: InMemoryVectorStore, k: int = 2, min_score: float = 0.05) -> None:
        self.store = store
        self.k = k
        self.min_score = min_score  # 相关性阈值：低于它宁可说"没有资料"

    def invoke(self, query: str) -> list[Document]:
        hits = [(d, s) for d, s in self.store.similarity_search(query, self.k) if s >= self.min_score]
        return [d for d, _ in hits]


def create_retriever_tool(retriever: MiniRetriever, name: str = "search_docs") -> dict:
    """检索工具化（tools/retriever.py:31 的影子）：retriever → 工具三件套。

    schema 固定是 {"query": string}——模型自己决定查询词怎么写。
    """
    return {
        "name": name,
        "description": "在公司文档库中检索资料，返回最相关的片段及来源。",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        "run": lambda args: format_hits(retriever.invoke(args["query"])),
    }


def format_hits(hits: list[Document]) -> str:
    """把检索结果渲染成模型可读的观察文本（带来源引文）。"""
    if not hits:
        return "（资料库中没有找到相关内容）"
    return "\n".join(f"[{h.metadata.get('source', '未知')}·片段{i+1}] {h.page_content}"
                     for i, h in enumerate(hits))


# ---------------------------------------------------------------
# 第 4 部分：脚本化 Mock 模型 + RAG agent 循环
# ---------------------------------------------------------------
def run_rag_agent(tool: dict, script: list[tuple[str, object]]) -> str:
    """两步循环：("tool", 查询词函数) → 工具执行；("final", 回答) → 出环。"""
    messages: list[str] = []
    for kind, payload in script:
        if kind == "tool":          # 工具轮：模型给出查询词 → 执行工具 → 结果入历史
            query = payload(messages)
            observation = tool["run"]({"query": query})
            print(f"  [tool] {tool['name']}(query={query!r}) →")
            for line in observation.splitlines():
                print(f"        {line}")
            messages.append(observation)
        else:                        # 回答轮
            answer = payload(messages) if callable(payload) else payload
            print(f"  [final] {answer}")
            return answer
    return "（剧本耗尽）"


# ---------------------------------------------------------------
# 演示
# ---------------------------------------------------------------
def main() -> None:
    banner("场景 1：切分与入库", "递归降级：段落 → 句号 → 硬切")
    raw = Document(
        page_content=(
            "LangChain 1.x 的 create_agent 把 agent 编译成 LangGraph 图。\n\n"
            "checkpointer 按 thread_id 保存状态快照，支持时间旅行。\n\n"
            "中间件提供 before_model、wrap_model_call 等七个钩子。\n\n"
            "员工差旅报销标准：市内交通实报实销，每日餐补 100 元。"
        ),
        metadata={"source": "langchain-内部笔记.md"},
    )
    chunks = recursive_split(raw.page_content, chunk_size=60)
    store = InMemoryVectorStore()
    n = store.add_texts([c for c in chunks], [{"source": raw.metadata["source"]} for _ in chunks])
    print(f"  原文 {len(raw.page_content)} 字符 → {n} 个 chunk（每个都带 source 元数据）")
    print(f"  首 chunk 预览: {chunks[0][:36]}...")

    banner("场景 2：检索器直调", "top-2 命中与余弦分数（字符 bigram，零依赖）")
    retriever = MiniRetriever(store, k=2)
    for doc in retriever.invoke("agent 的状态快照怎么保存？"):
        show("命中", {"source": doc.metadata["source"], "text": doc.page_content[:30]})

    banner("场景 3：检索工具化进 agent", "模型自主决定查什么，带着引文作答")
    tool = create_retriever_tool(retriever)
    show("工具 schema", tool["parameters"])
    run_rag_agent(tool, [
        ("tool", lambda msgs: "checkpointer 状态快照 保存"),        # 模型自拟查询词
        ("final", lambda msgs: "根据 [langchain-内部笔记.md]：checkpointer 按 thread_id 保存状态快照，支持时间旅行。"),
    ])

    banner("场景 4（边界）：资料库里没有", "低于阈值宁可说没有——不幻觉")
    tool2 = create_retriever_tool(MiniRetriever(store, k=2, min_score=0.5))
    run_rag_agent(tool2, [
        ("tool", lambda msgs: "公司年会去哪儿开"),                  # 相关资料不存在
        ("final", "资料库中未找到相关内容，我无法回答这个问题。"),
    ])

    print("\n结论：RAG 在 agent 语境下就是'一个带 schema 的检索工具'。")
    print("切分保语义、检索带阈值、结果带引文——模型负责综合，标准件负责纪律。")


if __name__ == "__main__":
    main()
