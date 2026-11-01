#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
s06_mcp_bridge/code.py —— mini MCP：stdio JSON-RPC 双向接入

MCP（Model Context Protocol，模型上下文协议）：agent 与外部工具服务器之间的
标准协议。Codex 的接入面：

  客户端侧  codex-rs/codex-mcp/（McpRuntime :23）、rmcp-client/；
            运行期管理在 core/src/session/mcp_runtime.rs（连接投影与发布）、
            mcp_prewarm.rs（预热）、mcp_refresh.rs（刷新）
  按需启动  turn.rs 的 required_mcp_servers_for_input（:882）：输入里提及的
            server 才拉起——s01 场景里那行"按需装配"的正主
  工具注册  MCP 工具经 handlers/mcp.rs 以内核同一套 CoreToolRuntime 注册
            （registry.rs :77 一带的 mcp_server_name 切面）——外部工具不搞特权
  反向通道  elicitation（服务端反向征求用户输入）：core/src/elicitation.rs，
            受 GranularApprovalConfig.mcp_elicitations（protocol.rs :1030）控制

MCP 的 stdio 传输 = **行分隔 JSON-RPC**：
    client ──{"id":1,"method":"tools/list"}──────────▶ server
    client ◀─{"id":1,"result":{"tools":[…]}}────────── server
    client ◀─{"id":9,"method":"elicitation/create"}─── server   ← 反向请求！
    client ──{"id":9,"result":{"action":"allow"}}────▶ server
关键认知：JSON-RPC 通道是**双向多路复用**的——谁都能发起请求，响应靠 id
配对（交错返回）。Codex 的 app-server 甚至注明自己不是严格 JSON-RPC 2.0
（不发 jsonrpc 字段，app-server-protocol/src/rpc.rs :1）——骨架仍是这套。

mini 版怎么跑：本文件**把自己再启动一份当 MCP server 子进程**
（`python code.py --serve`），主进程当 client——单文件自包含地演示
client 与 server 两侧。线程模型：读线程泵入站行 + 工作线程处理请求，
读线程永不阻塞——这是双向通道不死锁的关键。

  +-----------+  spawn 子进程   +-------------+
  |  client   |◄──stdio 行─────►|  mcp server |
  | (本课主体) |  JSON-RPC 双向  | (同文件 --serve)|
  +-----------+                 +-------------+
     │  ①initialize ②tools/list ③tools/call(echo/weather/未知工具)
     │  ◀── weather 调用中，server 反向发 elicitation/create 问用户

Rust ↔ Python：tokio 子进程 + mpsc ↔ subprocess + 线程队列；
async trait handler ↔ 同步 handler + 每请求一线程（教学从简）。

运行：python code.py    （零依赖，离线；子进程为同一文件的 --serve 模式）
对照真实源码：codex-rs/codex-mcp/、core/src/session/mcp_runtime.rs
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.mini_util import force_utf8_stdout

force_utf8_stdout()

# ===============================================================
# 通用层：行分隔 JSON-RPC 双向通道（client/server 共用）
# ===============================================================


class LineRPC:
    """一条 stdio 通道上的双向 JSON-RPC。

    核心结构：
      · 读线程：逐行读入站消息——响应（有 id 且在 pending 表）唤醒等待者；
        请求（有 method）丢给工作线程跑 handler，绝不占住读线程。
      · 写锁：两侧交替写，一行一条消息。
      · pending 表：id -> [等待的响应容器]，请求-响应靠 id 配对，可任意交错。

    对应真实实现：app-server-transport/src/transport/stdio.rs（:73 起逐行读）、
    codex-mcp/src/connection_manager.rs（Stdio 传输 :350 一带）。
    """

    def __init__(self, name: str, reader, writer,
                 handler: Optional[Dict[str, Any]] = None):
        self.name = name
        self.reader, self.writer = reader, writer
        self.handler = handler or {}          # method -> fn(params) -> result（可反向调用别人）
        self.pending: Dict[Any, Dict[str, Any]] = {}
        self.next_id = 100                    # 两端 id 空间独立；client 用小号便于阅读
        self.write_lock = threading.Lock()
        self.alive = True
        threading.Thread(target=self._read_loop, daemon=True).start()

    # ---- 出站：请求（等响应）----
    def request(self, method: str, params: Dict[str, Any], timeout: float = 5.0) -> Any:
        with self.write_lock:
            rid = self.next_id
            self.next_id += 1
            self._send({"id": rid, "method": method, "params": params})
        box: Dict[str, Any] = {}
        event = threading.Event()
        self.pending[rid] = {"box": box, "event": event}
        if not event.wait(timeout):
            self.pending.pop(rid, None)
            raise TimeoutError(f"{self.name}: 等待 {method} 响应超时")
        if "error" in box:
            raise RPCError(box["error"])
        return box.get("result")

    # ---- 出站：通知（不等响应）----
    def notify(self, method: str, params: Dict[str, Any]) -> None:
        with self.write_lock:
            self._send({"method": method, "params": params})

    def _send(self, msg: Dict[str, Any]) -> None:
        self.writer.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.writer.flush()

    # ---- 入站泵 ----
    def _read_loop(self) -> None:
        for raw in self.reader:
            raw = raw.strip()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if "method" in msg:  # 入站请求（对端发起）：工作线程处理，读线程继续泵
                threading.Thread(target=self._serve_request, args=(msg,), daemon=True).start()
            elif msg.get("id") in self.pending:  # 入站响应：唤醒等待者
                entry = self.pending.pop(msg["id"])
                entry["box"].update(msg)
                entry["event"].set()
        self.alive = False

    def _serve_request(self, msg: Dict[str, Any]) -> None:
        method, params, rid = msg["method"], msg.get("params") or {}, msg.get("id")
        fn = self.handler.get(method)
        try:
            result = fn(params) if fn else None
            if fn is None:
                self._reply_error(rid, -32601, f"方法不存在: {method}")
            else:
                with self.write_lock:
                    self._send({"id": rid, "result": result})
        except RPCError as e:
            self._reply_error(rid, e.code, e.message)
        except Exception as e:  # noqa: BLE001 —— handler 崩了也要回协议错误，不让对端挂等
            self._reply_error(rid, -32000, f"handler 异常: {e}")

    def _reply_error(self, rid: Any, code: int, message: str) -> None:
        with self.write_lock:
            self._send({"id": rid, "error": {"code": code, "message": message}})


class RPCError(Exception):
    """协议级错误。两种用法：收到对端 error 对象时用 dict 构造；
    handler 内主动抛错时用 (code, message) 构造。"""

    def __init__(self, code_or_error: Any, message: Optional[str] = None):
        if isinstance(code_or_error, dict):
            self.code = code_or_error.get("code", -32000)
            self.message = code_or_error.get("message", "unknown")
        else:
            self.code, self.message = code_or_error, message or ""
        super().__init__(f"[{self.code}] {self.message}")


# ===============================================================
# server 侧（--serve 模式）：mini MCP server
# ===============================================================


def run_server() -> None:
    """mini MCP server：initialize / tools/list / tools/call。

    tools/call 'weather' 时**反向**发起 elicitation（征求用户同意联网）——
    对应 core/src/elicitation.rs + GranularApprovalConfig.mcp_elicitations。
    """
    rpc_holder: Dict[str, LineRPC] = {}

    def elicitation(params: Dict[str, Any]) -> Dict[str, Any]:
        # server 作为 client 的 client：向对端（宿主）发请求并等待响应
        result = rpc_holder["rpc"].request("elicitation/create", params)
        return result

    def tools_list(params: Dict[str, Any]) -> Dict[str, Any]:
        return {"tools": [
            {"name": "echo", "description": "原样返回文本"},
            {"name": "weather", "description": "查天气（需要联网，会征求用户同意）"},
        ]}

    def tools_call(params: Dict[str, Any]) -> Dict[str, Any]:
        name = params["name"]
        if name == "echo":
            return {"content": f"echo: {params.get('arguments', {}).get('text', '')}"}
        if name == "weather":
            # 反向征求：elicitation 由宿主（真正看得见用户的前端）作答
            el = elicitation({"message": "查询天气需要联网，允许吗？", "server": "mini-mcp"})
            if el.get("action") == "allow":
                return {"content": "（模拟）晴，22°C"}
            return {"isError": True, "content": "用户拒绝联网，未查询天气"}
        raise RPCError(-32602, f"未知工具: {name}")

    rpc = LineRPC("server", sys.stdin, sys.stdout, {
        "initialize": lambda p: {"protocolVersion": "2026-07-28", "serverInfo": {"name": "mini-mcp"}},
        "tools/list": tools_list,
        "tools/call": tools_call,
        "elicitation/create": elicitation,  # 不会有人调它，占位说明 handler 表的对称性
    })
    rpc_holder["rpc"] = rpc
    import time
    while rpc.alive:
        time.sleep(0.05)  # stdin EOF 后读线程结束，进程自然退出


# ===============================================================
# client 侧（默认模式）：宿主如何接入一个 MCP server
# ===============================================================


def run_client() -> None:
    proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--serve"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8",
    )

    # 宿主对 elicitation 的应答策略（剧本化"用户"）：都允许，但记录在案
    def on_elicitation(params: Dict[str, Any]) -> Dict[str, Any]:
        print(f"    [client] ◀── server 反向征求用户：{params['message']} → 回答 allow")
        return {"action": "allow"}

    rpc = LineRPC("client", proc.stdout, proc.stdin, {
        "elicitation/create": on_elicitation,
    })

    print("== 场景 1：initialize + tools/list —— 握手与能力发现 ==")
    info = rpc.request("initialize", {"clientInfo": {"name": "mini-host"}})
    rpc.notify("notifications/initialized", {})
    print(f"    server: {info['serverInfo']['name']}（协议 {info['protocolVersion']}）")
    tools = rpc.request("tools/list", {})
    print(f"    工具面: {[t['name'] for t in tools['tools']]} → 会被注册进 ToolRegistry（s03 一张表）")

    print("\n== 场景 2：tools/call echo —— 普通请求/响应 ==")
    out = rpc.request("tools/call", {"name": "echo", "arguments": {"text": "hi from codex"}})
    print(f"    结果: {out['content']}")

    print("\n== 场景 3：tools/call weather —— server 反向 elicitation（双向！） ==")
    out = rpc.request("tools/call", {"name": "weather", "arguments": {}})
    print(f"    结果: {out['content']}（server 先问宿主、宿主答完才继续执行）")

    print("\n== 场景 4：未知工具 —— JSON-RPC 错误对象（失败路径） ==")
    try:
        rpc.request("tools/call", {"name": "deploy_prod", "arguments": {}})
    except RPCError as e:
        print(f"    收到协议级错误: {e}")

    proc.stdin.close()  # 关 stdin → server 读到 EOF → 自然退出
    proc.wait(timeout=5)
    print("\n结论：MCP = 行分隔 JSON-RPC 上的双向多路复用；外部工具经同一张")
    print("ToolRegistry 进内核（无特权），还能反向 elicitation 找用户要决定。")


if __name__ == "__main__":
    if "--serve" in sys.argv:
        run_server()
    else:
        run_client()
