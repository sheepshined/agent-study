#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
s10_frontends/code.py —— 收官装配：一份内核，多重身份，同一事件流的不同投影

十课到此，把零件装回一台整机，并回答最后一问：**同一份内核怎么长出 CLI / TUI / IDE / 桌面 App？**

  真实源码（codex-rs/，快照 818f1cc；行号实测）
    cli/src/main.rs   —— :129 `struct MultitoolCli`（一个二进制多身份），:146-:241 `enum Subcommand`：
        Agents(:149) / Exec(:153) / Review(:156) / Login / Logout / Mcp / Plugin /
        AppServer(:171) / RemoteControl(:174) / App(:178) / Completion / Update / Doctor /
        Sandbox(:190) / Debug / Apply(:201) / Resume(:204) / Queue / Archive / Delete /
        MigrateRollouts / Unarchive / Fork(:222) / Cloud(:226) / ResponsesApiProxy /
        StdioToUds(:234，"Internal: relay stdio to a Unix domain socket") / ExecServer(:237) /
        Features(:240)；:123-127 `bin_name = "codex"`——跨平台构建出的
        `codex-x86_64-unknown-linux-musl` 之类的名字，帮助输出仍写 `codex`
    arg0/            —— 单二进制按 argv[0]/子命令切换身份（沙箱助手 bwrap 也走这条路）
    app-server-client/src/ —— :317 `enum AppServerClient::{InProcess, Remote}`；
        lib.rs :295-:300 注释原文："The facade intentionally preserves the server's
        request/notification/event model instead of exposing direct core runtime handles.
        That keeps in-process callers aligned with app-server behavior while still avoiding
        a process boundary."；:72 `RemoteAppServerEndpoint::{WebSocket, UnixSocket}`
    exec/src/        —— 同一事件流的两个投影器：`event_processor_with_human_output.rs`
        （:228-:342 逐条 match `ServerNotification::*`）与 `event_processor_with_jsonl_output.rs`
        （机器读的 JSONL），共用 `event_processor.rs` / `exec_events.rs`
    tui/src/lib.rs   —— :31-:37 只 import `AppServerClient` / `InProcessAppServerClient` /
        `RemoteAppServerClient` / `RemoteAppServerEndpoint`；:404/:422 组 endpoint；
        :3209 起 `AppServerClient::InProcess(...)`——TUI 也不碰 core 句柄

  收官的三条主张（本课代码逐条演示）
    ① **同一事件流，不同投影**：内核只发 `ServerNotification`，人读的要排版、机器读的要成行、
       IDE 要能回放、SDK 要类型化——投影器互相独立，谁都不许反过来改内核。
    ② **没有特权前端**：任何前端想执行工具都得走 orchestrator（s03/s04/s05），
       连"我自己就是 CLI"都不算理由。
    ③ **可重放即正确性**：从 rollout JSONL 重建出的会话，必须与实时投影逐事件相等（s02）。

  Rust ↔ Python：clap `enum Subcommand` ↔ dict 分派；`match ServerNotification::*` ↔
  按 kind 的 if/elif；tracing/JSONL ↔ `json.dumps`；trait 对象 ↔ duck typing。

运行：python code.py    （零依赖，离线；模型脚本化 Mock；不接触真实 codex 二进制）
对照真实源码：cli/src/main.rs、app-server-client/src/lib.rs、exec/src/event_processor_*.rs
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.mini_util import ToolCall, TurnOutput, force_utf8_stdout

force_utf8_stdout()


# ---------------------------------------------------------------
# 内核：把 s01-s09 的零件装回去（每个零件都只留最小形状）
# ---------------------------------------------------------------


@dataclass
class Event:
    """对应 ServerNotification 的最小面：{kind, payload}。"""

    kind: str
    payload: dict

    def as_jsonl(self) -> str:
        return json.dumps({"event": self.kind, **self.payload}, ensure_ascii=False)


@dataclass
class SandboxPolicy:
    """s04：可写根 + 网络开关（教学模拟，不是安全边界）。"""

    writable_roots: List[str] = field(default_factory=lambda: ["workspace/"])
    network: bool = False

    def allows_write(self, path: str) -> bool:
        return any(path.startswith(r) for r in self.writable_roots)


@dataclass
class Approval:
    """s04：问不问，与问到哪一档。"""

    mode: str = "on_request"           # never / on_request / on_failure

    def must_ask(self, tool: str) -> bool:
        return self.mode == "on_request" and tool in ("shell", "apply_patch")


class Kernel:
    """s01 回合循环 + s02 录制 + s03 总闸 + s05 升级 + s07 补丁 + s08 子代理的最小合体。"""

    def __init__(self, model, approval: Approval, sandbox: SandboxPolicy,
                 allow_escalation: bool = True):
        self.model, self.approval, self.sandbox = model, approval, sandbox
        self.allow_escalation = allow_escalation
        self.rollout: List[dict] = []            # s02：只增不减
        self.events: List[Event] = []            # 对外的事件流
        self.registry = {"shell": self._tool_shell, "apply_patch": self._tool_patch,
                         "spawn_agent": self._tool_spawn, "mcp.echo": self._tool_mcp}
        self.files: Dict[str, str] = {"workspace/notes.md": "# notes\n"}
        self.escalated: List[str] = []

    # ---- 唯一出口：发事件 = 录制 + 投影（`/` 让 payload 也能用 kind 这个键名）----
    def emit(self, kind: str, /, **payload) -> None:
        self.rollout.append({"event": kind, **payload})
        self.events.append(Event(kind, payload))

    async def run_turn(self, user_input: str) -> str:
        self.emit("turn/started", input=user_input)
        context = [r for r in self.rollout]
        while True:
            out: TurnOutput = await self.model.sample(context)
            if out.tool_calls:
                for call in out.tool_calls:
                    result = await self.orchestrate(call)          # ★ 没有旁路
                    self.emit("item/completed", tool=call.name, result=result)
                    context = [r for r in self.rollout]
            elif out.text is not None:
                self.emit("turn/completed", text=out.text)
                return out.text

    # ---- s03/s04/s05：审批 → 选沙箱 → 执行 → 拒绝后升级重试 ----
    async def orchestrate(self, call: ToolCall) -> str:
        if call.name not in self.registry:
            return f"ERROR: unknown tool {call.name}"
        if self.approval.must_ask(call.name):
            self.emit("serverRequest", method="item/commandExecution/requestApproval",
                      tool=call.name)
            if not call.arguments.get("approved"):
                # 沙箱先跑一次：挡得住就不用问人
                outcome = self.registry[call.name](call, escalate=False)
                if not outcome.startswith("SANDBOX_DENIED"):
                    return outcome
                if not self.allow_escalation:
                    return outcome
                self.escalated.append(call.name)
                self.emit("serverRequest", method="escalate", tool=call.name,
                          reason="策略挡住了，不是命令报错")
                return self.registry[call.name](call, escalate=True)
        return self.registry[call.name](call, escalate=False)

    # ---- 工具实现（都只留最小形状） ----
    def _tool_shell(self, call: ToolCall, escalate: bool) -> str:
        cmd = call.arguments.get("cmd", "")
        if not escalate and "rm " in cmd:
            return "SANDBOX_DENIED: 写操作越出可写根"
        return f"exit=0 out=…（{cmd}，{'升级后免重审批' if escalate else '沙箱内'}）"

    def _tool_patch(self, call: ToolCall, escalate: bool) -> str:
        path = call.arguments.get("path", "")
        if not self.sandbox.allows_write(path):
            return f"SANDBOX_DENIED: {path} 不在 writable_roots"
        self.files[path] = self.files.get(path, "") + call.arguments.get("append", "")
        return f"patched {path}（s07 的事务，s04 的轴）"

    def _tool_spawn(self, call: ToolCall, escalate: bool) -> str:
        name = call.arguments.get("task_name", "anon")
        self.emit("subAgentActivity", kind="Started", path=f"/root/{name}")
        self.emit("subAgentActivity", kind="Completed", path=f"/root/{name}",
                  conclusion=call.arguments.get("conclusion", "结论"))
        return f"spawned /root/{name}（只回活动与结论，过程不可见）"

    def _tool_mcp(self, call: ToolCall, escalate: bool) -> str:
        return f"mcp echo: {call.arguments.get('text', '')}（外部工具同表同闸，s06）"

    # ---- s02：重放 ----
    @staticmethod
    def replay(rollout: List[dict]) -> List[str]:
        return [r["event"] for r in rollout]


class MockModel:
    """一次任务需要：shell 一次、patch 一次、子代理一次，然后交结论。"""

    def __init__(self, script: List[TurnOutput]):
        self.script, self.cursor = script, 0

    async def sample(self, context: List[dict]) -> TurnOutput:
        if self.cursor >= len(self.script):
            return TurnOutput(text="（剧本已尽）")
        item = self.script[self.cursor]
        self.cursor += 1
        return item


def task_script() -> List[TurnOutput]:
    return [
        TurnOutput(tool_calls=[ToolCall("1", "shell", {"cmd": "ls workspace/"})]),
        TurnOutput(tool_calls=[ToolCall("2", "shell", {"cmd": "rm workspace/scratch.txt"})]),
        TurnOutput(tool_calls=[ToolCall("3", "apply_patch",
                                        {"path": "workspace/notes.md", "append": "+ 摘要一行\n"})]),
        TurnOutput(tool_calls=[ToolCall("4", "mcp.echo", {"text": "复核"})]),
        TurnOutput(tool_calls=[ToolCall("5", "spawn_agent",
                                        {"task_name": "reviewer", "conclusion": "复核通过"})]),
        TurnOutput(text="装配完成：改动已落，复核已收"),
    ]


# ---------------------------------------------------------------
# 投影器：同一份事件流，四种读法（exec/src/event_processor_*.rs 的对照物）
# ---------------------------------------------------------------


def project_human(events: List[Event]) -> List[str]:
    """人读：排版、上色、只留关键信息（exec 的 human output）。"""
    out = []
    for e in events:
        if e.kind == "turn/started":
            out.append(f"◆ 任务开始：{e.payload['input']}")
        elif e.kind == "item/completed":
            out.append(f"  ✓ {e.payload['tool']}: {e.payload['result'][:52]}")
        elif e.kind == "serverRequest":
            out.append(f"  ⚠ 问用户（{e.payload['method']}）——{e.payload.get('reason', '')}")
        elif e.kind == "subAgentActivity":
            out.append(f"  ◈ 子代理 {e.payload['kind']:<9} {e.payload['path']}")
        elif e.kind == "turn/completed":
            out.append(f"◆ 结论：{e.payload['text']}")
    return out


def project_jsonl(events: List[Event]) -> List[str]:
    """机器读：一行一个 JSON，字段全留（exec/src/event_processor_with_jsonl_output.rs）。"""
    return [e.as_jsonl() for e in events]


def project_tui(events: List[Event]) -> List[str]:
    """终端 UI 读法：折叠成框，进度可见（tui 的投影；真实侧还有 ratatui 样式与 insta 快照）。"""
    lines = ["┌ 会话 ─────────────────────────"]
    for e in events:
        tag = {"turn/started": "▶", "item/completed": "·", "serverRequest": "⛔",
               "subAgentActivity": "◈", "turn/completed": "■"}[e.kind]
        text = (e.payload.get("text") or e.payload.get("input") or e.payload.get("tool")
                or e.payload.get("method") or e.payload.get("path") or "")
        lines.append(f"│ {tag} {text}")
    lines.append("└──────────────────────────────")
    return lines


def project_sdk(events: List[Event]) -> dict:
    """SDK 读法：类型化的结果对象，不做排版。"""
    return {"tools": [e.payload["tool"] for e in events if e.kind == "item/completed"],
            "approvals": [e.payload["method"] for e in events if e.kind == "serverRequest"],
            "subAgents": [e.payload["path"] for e in events if e.kind == "subAgentActivity"],
            "final": next(e.payload["text"] for e in events if e.kind == "turn/completed")}


# ---------------------------------------------------------------
# 装配与演示
# ---------------------------------------------------------------

FRONTENDS = {                      # cli/src/main.rs:146-:241 的 Subcommand 抽样
    "codex":            "默认子命令 → TUI（interactive: TuiCli 被 flatten 进 MultitoolCli）",
    "codex exec":       "非交互 → human / jsonl 投影，脚本可直接消费",
    "codex app-server": "起服务：--listen stdio:// | unix:// | ws://IP:PORT | off",
    "codex agents":     "浏览共享守护进程上的所有会话（:149）",
    "codex sandbox":    "在 Codex 提供的沙箱里跑命令（:190）",
    "codex resume":     "从 rollout 重建会话（:204）",
    "codex apply":      "把最近一次 diff 用 git apply 落到工作树（:201）",
    "codex stdio-to-uds": "内部件：stdio 中继到 Unix 域 socket（:234）",
}


async def scenario_assembly() -> Kernel:
    print("== 场景 1：十课零件装回一台整机 ==")
    parts = ["s01 回合循环", "s02 rollout 录制", "s03 工具总闸 orchestrator", "s04 审批×沙箱双轴",
             "s05 拒绝后升级重试", "s06 MCP 同表同闸", "s07 apply_patch 事务",
             "s08 子代理 thread", "s09 app-server 事件流"]
    print("    " + " + ".join(parts))
    k = Kernel(MockModel(task_script()), Approval("on_request"), SandboxPolicy())
    await k.run_turn("给登录页加 remember me 并复核")
    print(f"    事件 {len(k.events)} 条，录制 {len(k.rollout)} 行，升级重试 {k.escalated or '无'}")
    print(f"    落盘文件：{ {p: len(v) for p, v in k.files.items()} }")
    return k


def scenario_projections(k: Kernel) -> None:
    print("\n== 场景 2：同一事件流，四种投影 ==")
    human = project_human(k.events)
    print("    [human] " + " ／ ".join(h for h in human if h.startswith("◆"))[:80])
    for line in project_tui(k.events)[:4]:
        print("    [tui ] " + line)
    print("    [jsonl] " + project_jsonl(k.events)[0][:96])
    sdk = project_sdk(k.events)
    print(f"    [sdk  ] tools={sdk['tools']} approvals={len(sdk['approvals'])} "
          f"subAgents={sdk['subAgents']}")
    print("    → 四个投影器都不改内核；换前端 = 换投影器，不是换引擎")


def scenario_replay(k: Kernel) -> None:
    print("\n== 场景 3：重放必须与实时相等（s02 的确定性） ==")
    live = [e.kind for e in k.events]
    from_log = Kernel.replay(k.rollout)
    print(f"    实时 {len(live)} 事件 ／ 重放 {len(from_log)} 事件 → 逐条相等：{live == from_log}")
    again = json.loads(json.dumps(k.rollout, ensure_ascii=False))
    print(f"    rollout 可原样序列化再反序列化：{Kernel.replay(again) == live}")


async def scenario_no_privileged_frontend() -> None:
    print("\n== 场景 4：坏前端想走旁路 ==")
    k = Kernel(MockModel([TurnOutput(tool_calls=[ToolCall("9", "shell",
                                                          {"cmd": "rm -rf /tmp/x"})])]),
               Approval("never"), SandboxPolicy(network=False))
    direct = await k.orchestrate(ToolCall("9", "rm_everything", {}))
    print(f"    未知工具名 → {direct}")
    out = await k.run_turn("删掉点什么")
    print(f"    同一个前端只能以工具调用的形式提出 → 事件里仍有 {len(k.events)} 条，"
          f"其中 item/completed 的 result 记录了沙箱判定")
    print("    → 没有 `Kernel::exec_privileged()` 这种东西：审批与沙箱不在前端手里（s03 的总闸）")


def scenario_in_process_vs_remote() -> None:
    print("\n== 场景 5：InProcess 与 Remote 是同一个门面 ==")
    rows = [
        ("AppServerClient::InProcess", "同进程嵌入（exec/tui 默认）",
         "没有进程边界，但保留 request/notification/event 模型（lib.rs:295-:300 注释）"),
        ("AppServerClient::Remote(UnixSocket)", "连共享守护进程（IDE/桌面）",
         "UDS + WebSocket（endpoint 定义 remote.rs:72）"),
        ("AppServerClient::Remote(WebSocket)", "跨机 / 远程内核",
         "exec-server 与 app-server 可以异机（协议是同一份）"),
    ]
    for name, who, note in rows:
        print(f"    {name:<40} {who:<22} {note}")
    print("    → 前端代码只认 AppServerEvent 一个面；这就是「多形态」的全部成本")


def scenario_cross_compare() -> None:
    print("\n== 场景 6：收官横向对照（与姊妹教材同一立场） ==")
    rows = [
        ("内核形态", "单二进制多身份（arg0 + Subcommand）", "可装配内核 + 插件清单（Everything is a Plugin）"),
        ("扩展单元", "工具/MCP/角色 toml/补丁协议", "插件（provider/tool/loop 都能换，连 agent loop 都是插件）"),
        ("装配时机", "运行期由 app-server 方法表暴露", "启动期按 profile 装配出形态"),
        ("安全边界", "orchestrator + 审批×沙箱双轴 + 内核级沙箱", "插件必须显式声明权限，内核不偏袒任何插件"),
        ("多智能体", "同一内核多开 thread，活动与结论跨边界", "子代理/委派同样以插件面提供"),
        ("前端", "TUI/IDE/桌面/SDK 全是 RPC 客户端", "Web/桌面/SDK/ACP 同内核多形态投影"),
        ("一句话", "工程化与安全做到极致", "可组装做到极致"),
    ]
    for axis, codex, dsh in rows:
        print(f"    [{axis}]")
        print(f"        Codex：{codex}")
        print(f"        dsh  ：{dsh}")
    print("    （DeepSeek Harness 侧的收官课：03-deepseek-harness/analysis_deepseek_harness/s10_profile_assembly/）")
    print("    → 同一个 agent loop，两份工业化答案：先选立场，再谈实现")


async def main() -> None:
    print("== 场景 0：一个二进制，多重身份（cli/src/main.rs:146-:241） ==")
    for cmd, note in FRONTENDS.items():
        print(f"    {cmd:<18} {note}")
    k = await scenario_assembly()
    scenario_projections(k)
    scenario_replay(k)
    await scenario_no_privileged_frontend()
    scenario_in_process_vs_remote()
    scenario_cross_compare()
    print("\n结论：Codex 的装配答案是——内核一份、闸口一处、事件一条流；")
    print("前端只是投影器与 RPC 客户端。把这句话当成你造 harness 时的验收单。")


if __name__ == "__main__":
    asyncio.run(main())
