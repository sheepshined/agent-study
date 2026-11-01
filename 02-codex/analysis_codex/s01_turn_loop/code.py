#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
s01_turn_loop/code.py —— mini run_turn：回合制 agent 循环

Codex 内核的第一块骨头是回合制（turn-based）循环。真实实现：
codex-rs/core/src/session/turn.rs 的 `run_turn`（约 :176，3050 行大文件）。
它不是"一个大 while 到底"，而是三层结构：

    用户输入 ──► run_turn（一次回合）                      【回合层：世界重置点】
                  1. guardian 前置审查 → 2. 结算延迟钩子
                  3. 预采样压缩（腾窗口）→ 4. 按需装配 MCP/插件
                  loop {                                  【步层：step】
                    捕获 step 上下文（冻结一份请求快照）
                    采样 → 有工具调用？
                      ├─ 是：执行 → 结果回填 → 预算检查/自动压缩 → 回到 loop
                      └─ 否：终稿 → 退出 loop             【回合收尾】
                  }

    "步"（step）= 一次采样请求及其工具执行。step 内工具清单/系统提示是冻结快照，
    步与步之间才是世界可以变的窗口——这是 Codex 与"单 while 裸循环"的分水岭。

  +------------------------------------------------------------------+
  | run_turn(输入)                                                    |
  |  [guardian审查][结算延迟hooks][预采样压缩][按需装配MCP]              |
  |      │                                                           |
  |      ▼                                                           |
  |  ┌── step 循环 ◄─────────────────────────────┐                    |
  |  │ 捕获step快照 → 采样 → 工具? ─是→ 执行+回填+预算检查│               |
  |  └───────────────────────────┘否→ 终稿        │                    |
  |      ▲ 用户插话(steering) 在 loop 顶部并入 ────┘                    |
  +------------------------------------------------------------------+

本文件用 ~200 行 Python（纯标准库 asyncio）复刻这个骨架。对应关系：
  tokio task / mpsc        ↔ asyncio.Queue / asyncio 协程
  CancellationToken        ↔ asyncio.Event（本课 sess.turn_aborted）
  Arc<Session>（共享引用）  ↔ Python 对象直接共享（单线程事件循环下等价）
  serde tagged enum        ↔ dataclass + kind 判别字段

运行：python code.py        （零依赖，离线；模型由 MockModel 脚本扮演）
对照真实源码（crate codex-core）：core/src/session/turn.rs
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 课程根
from shared.mini_util import MockModel, ToolCall, TurnInput, TurnOutput, force_utf8_stdout

force_utf8_stdout()

# ---------------------------------------------------------------
# 第 1 部分：会话与回合上下文（对应 Session / TurnContext）
# ---------------------------------------------------------------


@dataclass
class TurnContext:
    """一次回合的不变配置。对应 turn.rs 的 `TurnContext`（cwd/策略/预算/模型客户端）。"""

    cwd: str = "/repo"
    token_budget: int = 200  # 上下文窗口预算（教学版用字符数/4 近似 token）
    model: MockModel = None  # 真实实现经 model-provider crate 发 HTTP（课程用 Mock）


class Session:
    """跨回合存续的会话状态。对应 `Session`（thread_manager 管理，见 s09）。

    history 只增不减（铁律在 s02 正式化：rollout 会话记录）；
    input_queue 承载"回合进行中"的用户插话——tokio mpsc ↔ asyncio.Queue。
    """

    def __init__(self) -> None:
        self.history: List[Dict[str, str]] = []
        self.input_queue: "asyncio.Queue[TurnInput]" = asyncio.Queue()
        self.deferred_hooks: List[str] = []  # 上一回合末尾未结算的 hook 结果
        self.turn_aborted = asyncio.Event()  # CancellationToken 的教学替身
        self.window_id = "w1"  # context_window 概念（s02/s08 相关），教学版恒定

    def tokens(self) -> int:
        """教学版 token 估算：JSON 序列化长度 // 4。真实实现见 token_budget.rs。"""
        return len(json.dumps(self.history, ensure_ascii=False)) // 4


def drain_pending_input(sess: Session) -> List[TurnInput]:
    """把回合进行中到达的用户插话全部取出（steering，转向）。

    对应 turn.rs 循环顶部的 `sess.input_queue.get_pending_input(...)`：
    插话不重启回合，而是在下一 step 开头并入——先入库历史，再随下一次采样可见。
    """
    pending = []
    while not sess.input_queue.empty():
        pending.append(sess.input_queue.get_nowait())
    return pending


# ---------------------------------------------------------------
# 第 2 部分：step 上下文快照（capture_step_context 的 mini 版）
# ---------------------------------------------------------------


@dataclass
class StepContext:
    """一次采样的冻结视图。对应 `capture_step_context_with_required_mcp_servers`（turn.rs :272）。

    为什么快照？同一 step 里的多次工具执行共享同一份"工具清单 + 系统提示 + 上下文"，
    模型行为可复现、可断言；变化只发生在 step 之间。
    """

    step_no: int
    system_prompt: str = "你是编码助手：只读文件，直到确有把握再下结论。"
    tools: List[str] = field(default_factory=lambda: ["read_file", "apply_patch"])
    frozen_history: List[Dict[str, str]] = field(default_factory=list)

    def view(self) -> List[Dict[str, str]]:
        """发给模型的完整请求视图（真实实现还要拼 AGENTS.md/skills，见架构拆解 §9.5）。"""
        return [{"role": "system", "content": self.system_prompt}, *self.frozen_history]


def capture_step_context(sess: Session, step_no: int) -> StepContext:
    return StepContext(step_no=step_no, frozen_history=list(sess.history))  # 浅拷贝列表快照


# ---------------------------------------------------------------
# 第 3 部分：mini 工具执行（正式版在 s03/s05 的 orchestrator）
# ---------------------------------------------------------------


async def dispatch_tool(call: ToolCall) -> Dict[str, str]:
    """教学版工具表：read_file 返回假内容。真实版必经 tools/orchestrator.rs 四段闸门。"""
    table = {
        "read_file": lambda args: f"(模拟) {args['path']} 共 42 行：def login(): ...",
    }
    if call.name not in table:
        return {"role": "tool", "name": call.name, "content": f"错误：工具不存在 {call.name}"}
    return {"role": "tool", "name": call.name, "content": table[call.name](call.arguments)}


def maybe_auto_compact(sess: Session, tc: TurnContext, protect_from: int = 0) -> bool:
    """预算触顶就折叠最旧的工具输出（auto compact 的极简版，正式讨论见姊妹课程 s08）。

    protect_from：本回合内新增条目的起点下标——最近语境不折叠（真实实现见
    retained_context.rs / compact_token_budget.rs 的"保留近 N 轮"）。
    预采样压缩调用时 protect_from=当前长度（旧物全可折）；
    回合中调用时 protect_from=回合起点（本回合的新工具结果受保护）。
    """
    if sess.tokens() <= int(tc.token_budget * 0.9):
        return False
    for i, item in enumerate(sess.history):
        if i >= protect_from:
            break  # 本回合新增的（模型正要看的）一律不折
        if item["role"] == "tool" and not item["content"].startswith("[auto-compact"):
            sess.history[i] = {"role": "tool", "name": item["name"],
                               "content": "[auto-compact 已折叠：早期工具输出]"}
            return True
    return False


# ---------------------------------------------------------------
# 第 4 部分：run_turn —— 本课主角
# ---------------------------------------------------------------


class TurnAborted(Exception):
    """回合被取消。对应 codex 的 TurnAborted 错误路径。"""


async def run_turn(sess: Session, tc: TurnContext, inputs: List[TurnInput]) -> str:
    """一次回合：从用户输入到模型终稿。行号注释对照 turn.rs（@818f1cc 检出）。"""
    # --- 开场四件事（turn.rs :185-:272 一带）---
    # 1) guardian 前置审查：会话来源/安全检查（教学 stub，只打日志）
    print("  [turn] guardian 前置审查 … 通过")
    # 2) 结算上一回合遗留的延迟钩子结果（先于新输入入库）
    for h in sess.deferred_hooks:
        sess.history.append({"role": "hook", "content": h})
    sess.deferred_hooks.clear()
    # 3) 预采样压缩：记录新输入之前先腾窗口（run_pre_sampling_compact，turn.rs :1247）
    maybe_auto_compact(sess, tc, protect_from=len(sess.history))  # 旧物全可折
    # 4) 记录用户输入 + 按需装配：输入里 @提及 的 MCP server 才启动（turn.rs :882 语义）
    turn_start = len(sess.history)
    for item in inputs:
        sess.history.append({"role": "user", "content": item.text})
        if "@fs" in item.text:
            print("  [turn] 输入提及 @fs → 按需启动 MCP server 'fs'（未提及不挂载）")

    # --- 回合循环（turn.rs :438 `loop {`）---
    step_no = 0
    while True:
        if sess.turn_aborted.is_set():
            raise TurnAborted("取消令牌触发：回合中止，已入库内容不回滚（见 s02）")
        # loop 顶部并入插话（steering）：入库但不重启回合
        for p in drain_pending_input(sess):
            print(f"  [turn] 并入插话（steering）：{p.text}")
            sess.history.append({"role": "user", "content": p.text})

        step_no += 1
        step = capture_step_context(sess, step_no)  # 一拍一快照
        print(f"  [step {step_no}] 快照 tools={step.tools} 上下文≈{sess.tokens()}tok → 采样")

        out: TurnOutput = await tc.model.sample(step.view())
        if out.tool_calls:
            for call in out.tool_calls:  # 真实实现可并行（tools/parallel.rs），教学串行
                print(f"  [step {step_no}] 工具 {call.name}({call.arguments})")
                sess.history.append(await dispatch_tool(call))
            maybe_auto_compact(sess, tc, protect_from=turn_start)  # 回合中随时可能触发
            continue  # 回到 loop：下一 step 把工具结果喂回模型

        sess.history.append({"role": "assistant", "content": out.text or ""})
        print("  [turn] turn-stop hooks（教学 stub）→ 回合收尾")
        return out.text or ""

# ---------------------------------------------------------------
# 第 5 部分：演示 —— 四个场景
# ---------------------------------------------------------------


async def main() -> None:
    print("== 场景 1：快乐路径 —— 两步完成一次回合 ==")
    sess = Session()
    tc = TurnContext(model=MockModel([
        TurnOutput(tool_calls=[ToolCall("c1", "read_file", {"path": "login.py"})]),
        TurnOutput(text="已定位：login() 缺少空指针检查；建议补丁见下一步。"),
    ]))
    final = await run_turn(sess, tc, [TurnInput(text="修复登录 bug")])
    print(f"  终稿：{final}")
    print(f"  历史条数={len(sess.history)}（用户/工具/助手 逐条入库，铁律见 s02）")

    print("\n== 场景 2：steering —— 回合进行中用户插话，下一 step 并入 ==")
    sess2 = Session()
    tc2 = TurnContext(model=MockModel([
        TurnOutput(tool_calls=[ToolCall("c2", "read_file", {"path": "login.py"})]),
        TurnOutput(text="已复查测试：现有用例未覆盖空指针分支。"),
    ], delay_ms=25))  # 第一幕采样拖 25ms，给插话留出到达窗口
    turn_task = asyncio.create_task(run_turn(sess2, tc2, [TurnInput(text="修复登录 bug")]))
    await asyncio.sleep(0.01)  # 10ms 时用户在 UI 上按了回车
    await sess2.input_queue.put(TurnInput(kind="interupt", text="顺便看看测试覆盖"))
    print(f"  终稿：{await turn_task}")
    print("  → 插话没有重启回合，而是在 loop 顶部入历史、随第二次采样生效")

    print("\n== 场景 3：预算触顶 —— 预采样压缩折叠旧物，保护最新工具结果 ==")
    sess3 = Session()
    tc3 = TurnContext(token_budget=20, model=MockModel([
        TurnOutput(tool_calls=[ToolCall("c3", "read_file", {"path": "big_report.txt"})]),
        TurnOutput(text="总结完毕。"),
    ]))
    sess3.history = [{"role": "tool", "name": "old", "content": "x" * 200}]  # 旧物 ~65tok
    await run_turn(sess3, tc3, [TurnInput(text="读报告")])
    print(f"  历史第 1 条：{sess3.history[0]['content'][:26]} ← 预采样压缩折叠（turn.rs :1247）")
    print(f"  历史第 3 条：{sess3.history[2]['content'][:26]} ← 最新工具结果受保护，未被折叠")
    print("  → 预算 20：起始 65tok 触顶先折叠；真实实现保留近 N 轮（compact_token_budget.rs）")

    print("\n== 场景 4：取消 —— CancellationToken 触发，回合中止（失败路径） ==")
    sess4 = Session()
    tc4 = TurnContext(model=MockModel([TurnOutput(text="这幕永远用不上")]))
    sess4.turn_aborted.set()  # 开跑前就取消
    try:
        await run_turn(sess4, tc4, [TurnInput(text="修复登录 bug")])
    except TurnAborted as e:
        print(f"  捕获 TurnAborted：{e}")
        print(f"  → 用户输入已入库（{len(sess4.history)} 条），不回滚——崩溃恢复靠 s02 的 rollout")


if __name__ == "__main__":
    asyncio.run(main())
