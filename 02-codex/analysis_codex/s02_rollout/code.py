#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
s02_rollout/code.py —— mini rollout：会话轨迹的录制与重建

s01 的铁律是"历史只增不减"。Codex 把这条承诺落成磁盘上的 rollout
（会话轨迹文件）：一边跑回合，一边把每条状态**追加**写进 JSONL 文件；
进程崩溃或重启后，从文件**重放**即可重建出同样的会话——resume / fork
都建立在这上面。

真实实现横跨三个 crate：
  codex-history  —— 数据形状：RolloutItem（条目枚举）/ RolloutLine（信封）
  codex-rollout  —— 持久化：RolloutRecorder（追加写）、state_db、重放解析
  codex-core     —— 消费：session/rollout_reconstruction.rs 重建会话

mini 版核心结构（RolloutLine = timestamp + ordinal + item）：

  {"timestamp":"2026-10-06T10:00:00","ordinal":0,"item":{"type":"session_meta",...}}
  {"timestamp":"...","ordinal":1,"item":{"type":"response_item","payload":{...}}}
  {"timestamp":"...","ordinal":2,"item":{"type":"compacted",...}}      ← 压缩也是事件
                          ▲
              只追加、不改写、不删除（append-only JSONL）

三条纪律：
  1. 只增不减：修正/压缩/撤销也是新条目（compacted），旧条目永不动；
  2. 重建确定性：同一条轨迹重放 N 次，得到 N 个相同的会话状态；
  3. 写入抗损：按行追加 + 完整行才生效——半行（崩溃残页）重放时跳过。

Rust ↔ Python 对应：serde tagged enum（`#[serde(tag="type")]`）↔ 带 "type"
判别字段的 dict/dataclass；tokio 文件 IO ↔ 普通 open + flush（教学不模拟异步盘）。

运行：python code.py     （零依赖，离线；文件写进系统临时目录并在结束时清理）
对照真实源码：codex-rs/history/src/lib.rs（RolloutItem/RolloutLine）、
             codex-rs/rollout/src/recorder.rs（RolloutRecorder）
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.mini_util import force_utf8_stdout

force_utf8_stdout()

# ---------------------------------------------------------------
# 第 1 部分：轨迹条目（RolloutItem 的 mini 版）
# ---------------------------------------------------------------


def item(kind: str, **fields: Any) -> Dict[str, Any]:
    """造一个带判别字段的条目。对应 history/src/lib.rs :122 的 `RolloutItem` 枚举：
    SessionMeta / ResponseItem / Compacted / TurnContext / TokenUsageRecord / …
    serde 用 `#[serde(flatten)]` 把判别字段摊平进信封；教学版显式带 type 字段。"""
    return {"type": kind, **fields}


def is_persisted(item: Dict[str, Any]) -> bool:
    """持久化策略：哪些条目值得落盘。

    对应 rollout/src/policy.rs 的 `is_persisted_rollout_item`：真实实现按
    响应条目类型与历史模式逐条判断（例如纯 UI 展示的过渡条目可以不落盘）。
    mini 版：ephemeral（易失）条目不落盘，其余全落。
    """
    return item.get("type") != "ephemeral"


# ---------------------------------------------------------------
# 第 2 部分：RolloutRecorder —— 追加写 JSONL
# ---------------------------------------------------------------


@dataclass
class RolloutRecorder:
    """轨迹录制器。对应 rollout/src/recorder.rs :86 的 `RolloutRecorder`。

    真实实现是 tokio 异步写 + writer_lock.rs 的文件锁（多进程抢同一个会话文件）；
    mini 版同步写 + flush，但**行完整性**语义保持一致：每行一个 json + 换行。
    """

    path: Path
    ordinal: int = 0  # 单调递增序号：对应 RolloutLine.ordinal（乱序可检测、重放可排序）

    def append(self, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not is_persisted(entry):
            print(f"    [recorder] 跳过易失条目：{entry.get('type')}（不落盘）")
            return None
        line = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "ordinal": self.ordinal, "item": entry}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
            f.flush()  # 立刻冲刷：崩溃时最多丢当前行，不丢已确认的历史
        self.ordinal += 1
        return line

    def raw_lines(self) -> List[str]:
        return self.path.read_text(encoding="utf-8").splitlines()


# ---------------------------------------------------------------
# 第 3 部分：重放重建 —— resume 与 fork
# ---------------------------------------------------------------


@dataclass
class ResumedHistory:
    """重放产物。对应 history/src/lib.rs 的 `InitialHistory::Resumed(ResumedHistory)`。"""

    items: List[Dict[str, Any]] = field(default_factory=list)      # 全部有效条目（含 compacted）
    history: List[Dict[str, Any]] = field(default_factory=list)    # 模型可见的会话状态
    dropped_lines: int = 0                                          # 半行/损坏行计数
    source: str = ""


def resume(path: Path) -> ResumedHistory:
    """从 JSONL 重放重建会话。对应 session/rollout_reconstruction.rs + rollout 的解析器。

    真实实现强调"必须用 codex_rollout 的规范解析器"（RolloutLine 注释里明说
    不实现 Deserialize，防嵌套小数被宽松解析破坏）；mini 版逐行 json.loads，
    解析失败的**尾部残行**跳过并计数（中途损坏则上抛——那不是掉电，是踩了文件）。
    """
    out = ResumedHistory(source=str(path))
    for idx, raw in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not raw.strip():
            continue
        try:
            line = json.loads(raw)
        except json.JSONDecodeError:
            if idx == len(path.read_text(encoding="utf-8").splitlines()) - 1:
                out.dropped_lines += 1  # 尾部半行：上次进程中断的残页，安全跳过
                continue
            raise  # 中间坏行：数据被外部改过，拒绝静默吞掉
        out.items.append(line["item"])
        out.history = project(out.items)  # 每次全量投影：教学版简单可靠
    return out


def project(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """把轨迹投影成"模型可见的会话状态"。

    关键：compacted 条目不是"删旧加新"，而是一个**标记**——投影时它之后的
    被折叠条目不再渲染，但轨迹里原样都在。日志不动，投影动。
    """
    history: List[Dict[str, Any]] = []
    for it in items:
        if it["type"] == "session_meta":
            continue  # 元数据不进模型上下文
        if it["type"] == "compacted":
            # 折叠点：之前的响应条目全部被摘要替代（mini 版直接清空，留摘要条目）
            history = [h for h in history if h["type"] == "compacted"]
            history.append({"type": "summary", "text": it["summary"]})
            continue
        history.append(it)  # response_item / token_usage … 原样可见
    return history


def fork(source: Path, upto_ordinal: int, dest: Path) -> ResumedHistory:
    """分叉：取原轨迹前缀写成新文件。对应 `InitialHistory::Forked(Vec<RolloutItem>)`。"""
    rec = RolloutRecorder(path=dest)
    kept: List[Dict[str, Any]] = []
    for raw in source.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        line = json.loads(raw)
        if line["ordinal"] > upto_ordinal:
            break
        rec.append(line["item"])
        kept.append(line["item"])
    out = ResumedHistory(items=kept, history=project(kept), source=str(dest))
    return out


# ---------------------------------------------------------------
# 第 4 部分：演示 —— 录制 → 重放续聊 → 分叉 → 半行抗损
# ---------------------------------------------------------------


def demo_turn_1(rec: RolloutRecorder) -> None:
    """把 s01 场景 1 的回合"录下来"：每条状态一个 rollout 条目。"""
    rec.append(item("session_meta", cli_version="mini-0.1", cwd="/repo"))
    rec.append(item("response_item", payload={"role": "user", "content": "修复登录 bug"}))
    rec.append(item("turn_context", cwd="/repo", approval="on-request"))
    rec.append(item("response_item",
                    payload={"role": "tool", "name": "read_file", "content": "def login(): ..."}))
    rec.append(item("ephemeral", payload={"note": "UI 过渡动画，不值得落盘"}))
    rec.append(item("response_item",
                    payload={"role": "assistant", "content": "已定位：缺少空指针检查。"}))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="mini-rollout-"))
    try:
        print("== 场景 1：录制一次回合 —— JSONL 只追加 ==")
        rec = RolloutRecorder(path=tmp / "rollout-2026-10-06.jsonl")
        demo_turn_1(rec)
        for line in rec.raw_lines():
            d = json.loads(line)
            print(f"    #{d['ordinal']} {d['item']['type']:<14} {json.dumps(d['item'], ensure_ascii=False)[:58]}")
        print(f"    → 共 {len(rec.raw_lines())} 行，ephemeral 条目被策略拦下未落盘")

        print("\n== 场景 2：resume —— 重放重建，接着上次继续 ==")
        resumed = resume(rec.path)
        print(f"    重建出 {len(resumed.history)} 条可见历史 / {len(resumed.items)} 条轨迹条目")
        again = resume(rec.path)  # 重放两次，结果必须一致
        assert again.history == resumed.history, "重建必须确定性"
        print("    重放两次 → 相同状态（重建确定性 ✓）")
        # 续聊：新回合的历史就是重建产物
        rec2 = RolloutRecorder(path=rec.path, ordinal=rec.ordinal)
        rec2.append(item("response_item", payload={"role": "user", "content": "那写个补丁"}))
        print(f"    续聊追加一条，ordinal 接续为 {rec2.ordinal - 1}（单调不回头）")

        print("\n== 场景 3：压缩也是条目 —— 投影折叠，轨迹原样 ==")
        rec3 = RolloutRecorder(path=tmp / "rollout-compacted.jsonl")
        for it in resumed.items:
            rec3.append(it)
        rec3.append(item("compacted", summary="此前：定位到 login() 缺空指针检查（折叠前 3 条原文见轨迹）"))
        after = resume(rec3.path)
        print(f"    可见历史：{[h['type'] for h in after.history]}")
        print(f"    轨迹条目：{[i['type'] for i in after.items]} ← 被折叠的原文一条没删")
        print("    → 日志不动，投影动：想看原文？轨迹里全在")

        print("\n== 场景 4：分叉与半行抗损（失败/边界路径） ==")
        forked = fork(rec3.path, upto_ordinal=2, dest=tmp / "rollout-fork.jsonl")
        print(f"    fork@2 → 可见历史 {len(forked.history)} 条，之后的新分支与主线无关")
        # 模拟崩溃残页：手工追加半行
        with open(rec.path, "a", encoding="utf-8") as f:
            f.write('{"timestamp":"2026-10-06T10:01:00","ordinal":5,"item":{"type":"resp')
        patched = resume(rec.path)
        print(f"    尾部半行 → 跳过 {patched.dropped_lines} 行，重建仍成功（{len(patched.history)} 条历史）")

        print("\n结论：只增不减 + 确定性重放 + 行级抗损 = 会话的'黑匣子'。")
        print("Codex 的 resume/fork/回放审计/评测对齐，全部站在这份 JSONL 上。")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
