#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
s09_app_server/code.py —— mini app-server：一个内核，多前端连接（行分隔 JSON-RPC）

为什么 CLI、IDE 插件、桌面 App、SDK 都能驱动同一个 Codex？因为内核被**服务化**了：
`codex-rs/app-server/` 把 core 包成 RPC 服务器，`app-server-daemon/` 让它常驻共享，
`app-server-client/` 给前端的门面在"同进程"与"连远端"之间不加区别。

  真实源码（codex-rs/，快照 818f1cc；行号实测）
    app-server-protocol/src/rpc.rs      —— :1-2 原文："We do not do true JSON-RPC 2.0, as we
        neither send nor expect the \"jsonrpc\": \"2.0\" field."；`RequestId` 支持 String / Integer
    app-server-protocol/src/protocol/common.rs —— 方法表由宏生成：:507 "initialize"、
        :559 "thread/start"、:587 "thread/unsubscribe"、:1038 "turn/start"、:1050 "turn/steer"、
        :1056 "turn/interrupt"；服务端**反向请求** :1756 "item/commandExecution/requestApproval"、
        :1763 "item/fileChange/requestApproval"、:1781 "item/permissions/requestApproval"、
        :1775 "mcpServer/elicitation/request"；通知 :1935 "turn/started"、:1937 "turn/completed"、
        :1939 "turn/diff/updated"
    app-server/src/message_processor.rs —— :960 dispatch_initialized_client_request：
        :967 未 initialize → invalid_request("Not initialized")；
        :973 未 opt-in 却调实验 API → invalid_request(experimental_required_message(reason))；
        :184 / :206 把 capabilities.experimentalApi 存成连接会话状态
    app-server/src/connection_rpc_gate.rs —— 文件头注释：**每连接一个闸**——关门后"已排队的
        handler 不再启动，已取得令牌的 handler 跑完收尾"（鉴权归属变更时用）
    app-server-transport/src/transport/mod.rs —— :28 CHANNEL_CAPACITY = 128（有界通道），
        :49-:50 INTERNAL_ERROR -32603 / OVERLOADED_ERROR_CODE -32001，
        :88 `AppServerTransport::{Stdio, UnixSocket, WebSocket, Off}`，:103 报错文案列出
        `stdio://` / `unix://` / `unix://PATH` / `ws://IP:PORT` / `off`，:123 DEFAULT_LISTEN_URL，
        :67 app_server_control_socket_path；stdio.rs :73 逐行泵
    app-server-daemon/src/client.rs —— :63/:67 连 UDS 后跑 **WebSocket** 握手（复用 ws codec）
    app-server/README.md —— "thread/archive 与 thread/delete 想删掉在活的内部 worker 时返回
        JSON-RPC error -32600：worker 的关闭由它的 owner 控制"

  本课演示的四件事
    ① initialize 握手与能力协商（clientInfo / capabilities.experimentalApi）
    ② 请求—响应靠 id 配对；通知（notification）没有 id，构成事件流
    ③ **反向请求**：内核要审批时往"这条连接"发 request，客户端回 response（s04 的出口）
    ④ 一个内核、多条连接：两个前端订阅同一条 thread，看到同一份事件流

  Rust ↔ Python：tokio mpsc(128) ↔ asyncio.Queue(maxsize=128)；ConnectionId(u64) ↔ 自增 int；
  每连接一个 task ↔ asyncio.create_task；serde tagged enum ↔ method 字符串 + dict 参数。

运行：python code.py   （零依赖，离线；场景 1 真的起一个子进程走 stdio，其余场景在同进程用
      内存管道模拟多连接——真实侧多连接走 UDS/WebSocket，见 app-server-daemon）
对照真实源码：app-server-protocol/src/{rpc.rs,protocol/common.rs}、app-server/src/message_processor.rs、
             app-server-transport/src/transport/
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.mini_util import force_utf8_stdout

force_utf8_stdout()

PROTOCOL_VERSION = "v2"
CHANNEL_CAPACITY = 128                                        # transport/mod.rs:28
INVALID_REQUEST, METHOD_NOT_FOUND = -32600, -32601            # error_code.rs:3 / 标准码
OVERLOADED = -32001                                           # transport/mod.rs:50
EXPERIMENTAL_METHODS = {"thread/queue/add", "thread/search", "server/diagnostics"}
APPROVAL_METHOD = "item/commandExecution/requestApproval"      # common.rs:1756


def err(code: int, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


# ---------------------------------------------------------------
# 传输：一行一个 JSON 对象（stdio 与内存管道两种实现，server 代码不关心）
# ---------------------------------------------------------------


class Transport:
    async def recv(self) -> Optional[dict]:
        raise NotImplementedError

    async def send(self, msg: dict) -> None:
        raise NotImplementedError


class PipeTransport(Transport):
    """内存管道一条端点：真实侧对应 UDS / WebSocket 上的一条连接。"""

    def __init__(self, inbound: asyncio.Queue, outbound: asyncio.Queue):
        self.inbound, self.outbound = inbound, outbound

    async def recv(self) -> Optional[dict]:
        return await self.inbound.get()

    async def send(self, msg: dict) -> None:
        await self.outbound.put(msg)


class StdioTransport(Transport):
    """子进程 stdio：行分隔 JSON（stdio.rs:73 的逐行泵），EOF 即断线。"""

    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer

    async def recv(self) -> Optional[dict]:
        line = await self.reader.readline()
        if not line:
            return None
        return json.loads(line.decode("utf-8"))

    async def send(self, msg: dict) -> None:
        self.writer.write((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
        await self.writer.drain()


def pair() -> tuple:
    a: asyncio.Queue = asyncio.Queue()
    b: asyncio.Queue = asyncio.Queue()
    return PipeTransport(a, b), PipeTransport(b, a)      # (server 侧, client 侧)


# ---------------------------------------------------------------
# 内核替身
# ---------------------------------------------------------------


@dataclass
class Thread:
    id: str
    owner: int                                    # 哪条连接开的（worker 的关闭由 owner 控制）
    turn_task: Optional[asyncio.Task] = None
    approval: Optional[asyncio.Future] = None
    steered: bool = False
    last_decision: str = ""


class Kernel:
    """core 的替身：内核只此一份，所有连接都是客户端。"""

    def __init__(self) -> None:
        self.threads: Dict[str, Thread] = {}
        self.n = 0

    def new_thread(self, owner: int) -> Thread:
        self.n += 1
        t = Thread(id=f"thread-{self.n:03d}", owner=owner)
        self.threads[t.id] = t
        return t


@dataclass
class Connection:
    cid: int
    transport: Transport
    outbox: asyncio.Queue
    initialized: bool = False
    experimental_api: bool = False
    gate_open: bool = True                         # connection_rpc_gate.rs
    threads: Set[str] = field(default_factory=set)  # 订阅集（真实侧 thread/unsubscribe :587）
    next_server_id: int = 0
    pending: Dict[str, asyncio.Future] = field(default_factory=dict)


class AppServer:
    def __init__(self, kernel: Kernel, name: str = "codex-app-server-mini"):
        self.kernel = kernel
        self.name = name
        self.connections: Dict[int, Connection] = {}
        self._cid = 0

    # ---- 连接生命周期 ----
    async def attach(self, transport: Transport) -> int:
        self._cid += 1
        cid = self._cid
        conn = Connection(cid=cid, transport=transport,
                          outbox=asyncio.Queue(maxsize=CHANNEL_CAPACITY))
        self.connections[cid] = conn
        asyncio.create_task(self._writer_loop(conn))
        asyncio.create_task(self._reader_loop(conn))
        return cid

    async def _reader_loop(self, conn: Connection) -> None:
        while True:
            msg = await conn.transport.recv()
            if msg is None:
                return
            if "method" not in msg and "id" in msg:              # 客户端对我们反向请求的应答
                fut = conn.pending.pop(str(msg["id"]), None)
                if fut and not fut.done():
                    fut.set_result(msg.get("result") or {})
                continue
            if "method" in msg and "id" not in msg:              # notification：单向，无应答
                continue
            await self._dispatch(conn, msg)

    async def _writer_loop(self, conn: Connection) -> None:
        while True:
            await conn.transport.send(await conn.outbox.get())

    # ---- 出站：有界队列满 → OVERLOADED（transport/mod.rs:50），不静默丢 ----
    async def push(self, conn: Connection, msg: dict) -> None:
        try:
            conn.outbox.put_nowait(msg)
        except asyncio.QueueFull:
            if "id" in msg:
                await conn.transport.send({"id": msg["id"], **err(OVERLOADED, "outbound queue full")})
            else:
                await conn.transport.send({"method": "error/dropped",
                                           "params": err(OVERLOADED, "outbound queue full")})

    async def reply(self, conn: Connection, rid, result=None, error=None) -> None:
        await self.push(conn, {"id": rid, "error": error} if error else {"id": rid, "result": result})

    async def emit(self, t: Thread, method: str, params: dict) -> None:
        """通知只发给订阅了这条 thread 的连接——同一事件流，不同投影。"""
        for cid, c in self.connections.items():
            if t.id in c.threads:
                await self.push(c, {"method": method, "params": params})

    async def ask_client(self, conn: Connection, method: str, params: dict) -> dict:
        """反向请求：内核 → 这条连接的客户端（审批的通路，s04 的服务化形态）。"""
        conn.next_server_id += 1
        rid = f"s{conn.next_server_id}"
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        conn.pending[rid] = fut
        await self.push(conn, {"id": rid, "method": method, "params": params})
        return await fut

    # ---- 方法表（common.rs 的宏生成物，这里手写七个代表） ----
    async def _dispatch(self, conn: Connection, msg: dict) -> None:
        rid, method = msg.get("id"), msg.get("method", "")
        params = msg.get("params") or {}
        if not conn.gate_open:                          # 门关：不启动新 handler
            await self.reply(conn, rid, error=err(INVALID_REQUEST, "connection gate closed"))
            return
        if method == "initialize":                      # :507
            conn.initialized = True
            conn.experimental_api = bool((params.get("capabilities") or {}).get("experimentalApi"))
            await self.reply(conn, rid, {
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": {"name": self.name, "version": "0.0.0-mini"},
                "capabilities": {"experimentalApi": conn.experimental_api}})
            return
        if not conn.initialized:                        # :967
            await self.reply(conn, rid, error=err(INVALID_REQUEST, "Not initialized"))
            return
        if method in EXPERIMENTAL_METHODS and not conn.experimental_api:      # :973
            await self.reply(conn, rid, error=err(
                INVALID_REQUEST, f"{method} requires experimental API opt-in"))
            return
        if method == "thread/start":                    # :559
            t = self.kernel.new_thread(conn.cid)
            conn.threads.add(t.id)
            await self.reply(conn, rid, {"thread": {"id": t.id, "owner": conn.cid}})
            return
        if method == "thread/subscribe":
            t = self.kernel.threads.get(params.get("threadId", ""))
            if t is None:
                await self.reply(conn, rid, error=err(METHOD_NOT_FOUND, "unknown threadId"))
                return
            conn.threads.add(t.id)
            await self.reply(conn, rid, {"subscribed": t.id})
            return
        if method == "turn/start":                      # :1038
            t = self.kernel.threads.get(params.get("threadId", ""))
            if t is None:
                await self.reply(conn, rid, error=err(METHOD_NOT_FOUND, "unknown threadId"))
                return
            await self.reply(conn, rid, {"turn": {"id": "turn-1", "status": "in_progress"}})
            t.turn_task = asyncio.create_task(self._run_turn(conn, t, params.get("input", "")))
            return
        if method == "turn/steer":                      # :1050 用户插话
            t = self.kernel.threads.get(params.get("threadId", ""))
            ok = bool(t and t.turn_task and not t.turn_task.done())
            if ok:
                t.steered = True
                if t.approval and not t.approval.done():
                    t.approval.set_result({"decision": "denied", "reason": "steered"})
            await self.reply(conn, rid, {"steered": ok})
            return
        if method == "thread/delete":                   # README：在活的 thread 上返回 -32600
            t = self.kernel.threads.get(params.get("threadId", ""))
            if t and t.turn_task and not t.turn_task.done():
                await self.reply(conn, rid, error=err(
                    INVALID_REQUEST, "cannot delete a live thread; its owner controls shutdown"))
                return
            await self.reply(conn, rid, {})
            return
        await self.reply(conn, rid, error=err(METHOD_NOT_FOUND, f"method not found: {method}"))

    # ---- 一个回合：事件流 + 一次审批（可被插话抢先否定） ----
    async def _run_turn(self, conn: Connection, t: Thread, user_input: str) -> None:
        await self.emit(t, "turn/started", {"threadId": t.id})                    # :1935
        await self.emit(t, "item/started", {"threadId": t.id, "item": {
            "type": "agentMessage", "text": f"我打算执行 `ls {user_input}`"}})
        loop = asyncio.get_running_loop()
        t.approval = loop.create_future()
        ask = asyncio.create_task(self.ask_client(conn, APPROVAL_METHOD,
                                                 {"threadId": t.id, "command": f"ls {user_input}"}))
        done, _pending = await asyncio.wait({ask, t.approval}, return_when=asyncio.FIRST_COMPLETED)
        decision = ask.result() if ask in done else t.approval.result()
        ask.cancel()
        t.last_decision = decision.get("decision", "?")
        why = decision.get("reason", "")
        await self.emit(t, "item/completed", {"threadId": t.id, "item": {
            "type": "commandExecution", "output": f"{t.last_decision} {why}".strip()}})
        if t.steered:
            await self.emit(t, "turn/steered", {"threadId": t.id, "note": "用户插话已生效"})
        await self.emit(t, "turn/completed", {"threadId": t.id, "turn": {"status": "completed"}})  # :1937


# ---------------------------------------------------------------
# 客户端门面（app-server-client 的极小替身）
# ---------------------------------------------------------------


class AppServerClient:
    def __init__(self, transport: Transport, name: str = "client", auto_respond: bool = True):
        self.transport, self.name, self.auto_respond = transport, name, auto_respond
        self.rid = 0
        self.pending: Dict[str, asyncio.Future] = {}
        self.events: List[dict] = []
        self._task = asyncio.create_task(self._pump())

    async def _pump(self) -> None:
        while True:
            msg = await self.transport.recv()
            if msg is None:
                return
            if "id" in msg and "method" in msg:                 # 服务端反向请求
                print(f"    [{self.name}] ⤴ 反向请求 {msg['method']}："
                      f"{msg['params'].get('command', '')}")
                if self.auto_respond:
                    await self.transport.send({"id": msg["id"],
                                               "result": {"decision": "allow"}})
            elif "id" in msg:                                   # 我们请求的响应：靠 id 配对
                fut = self.pending.pop(str(msg["id"]), None)
                if fut and not fut.done():
                    fut.set_result(msg)
            else:
                self.events.append(msg)                          # 通知 → 事件流

    async def request(self, method: str, params: Optional[dict] = None, timeout: float = 2.0) -> dict:
        self.rid += 1
        rid = str(self.rid)
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self.pending[rid] = fut
        await self.transport.send({"id": rid, "method": method, "params": params or {}})
        return await asyncio.wait_for(fut, timeout)

    def close(self) -> None:
        self._task.cancel()


async def connect(server: AppServer) -> PipeTransport:
    t_srv, t_cli = pair()
    await server.attach(t_srv)
    return t_cli


# ---------------------------------------------------------------
# 场景
# ---------------------------------------------------------------


async def scenario_stdio_subprocess() -> None:
    print("== 场景 1：真的起一个子进程 —— stdio 上的行分隔 JSON-RPC ==")
    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(Path(__file__).resolve()), "--serve",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
    transport = StdioTransport(proc.stdout, proc.stdin)
    client = AppServerClient(transport, name="mini-tui")

    r = await client.request("initialize", {
        "clientInfo": {"name": "mini-tui", "version": "0"},
        "capabilities": {"experimentalApi": False}})
    print(f"    initialize → {json.dumps(r['result'], ensure_ascii=False)}")
    started = await client.request("thread/start")
    tid = started["result"]["thread"]["id"]
    print(f"    thread/start → {tid}（owner=conn {started['result']['thread']['owner']}）")
    await client.request("turn/start", {"threadId": tid, "input": "src/"})
    await asyncio.sleep(0.2)
    print(f"    事件流：{[e['method'] for e in client.events]}")
    e1 = await client.request("thread/queue/add")
    print(f"    实验方法未 opt-in → {json.dumps(e1.get('error'), ensure_ascii=False)}")
    e2 = await client.request("thread/delete", {"threadId": tid})
    print(f"    删除活跃 thread → {json.dumps(e2.get('error'), ensure_ascii=False)}")
    client.close()
    proc.terminate()
    await proc.wait()
    print("    → 没有 jsonrpc:2.0 字段（rpc.rs:1-2），EOF 即断线：行分隔就是全部 framing")


async def scenario_one_kernel_many_connections() -> None:
    print("\n== 场景 2：一个内核，两条连接 —— 同一事件流的不同投影 ==")
    server = AppServer(Kernel())
    c1 = AppServerClient(await connect(server), name="tui")
    c2 = AppServerClient(await connect(server), name="ide")
    r1 = await c1.request("initialize", {"clientInfo": {"name": "codex-tui"},
                                         "capabilities": {"experimentalApi": True}})
    r2 = await c2.request("initialize", {"clientInfo": {"name": "codex-vscode"}})
    print(f"    tui: {r1['result']['serverInfo']['name']} caps={r1['result']['capabilities']}")
    print(f"    ide: caps={r2['result']['capabilities']}（没 opt-in，实验方法对它不可见）")

    tid = (await c1.request("thread/start"))["result"]["thread"]["id"]
    print(f"    tui 开 {tid}；ide 先 thread/subscribe 才能看到它的事件")
    await c2.request("thread/subscribe", {"threadId": tid})
    await c1.request("turn/start", {"threadId": tid, "input": "src/"})
    await asyncio.sleep(0.1)
    print(f"    tui 事件：{[e['method'] for e in c1.events]}")
    print(f"    ide 事件：{[e['method'] for e in c2.events]}  ← 同一内核同一份流")
    print("    → 前端只是客户端：审批请求只发给**开这条 thread 的连接**（owner）")

    print("\n== 场景 3：turn/steer —— 另一个前端往活跃回合里插话 ==")
    c1.events.clear()
    c2.events.clear()
    slow = AppServerClient(await connect(server), name="cli-noinput", auto_respond=False)
    await slow.request("initialize", {"clientInfo": {"name": "codex exec"}})
    tid2 = (await slow.request("thread/start"))["result"]["thread"]["id"]
    await slow.request("turn/start", {"threadId": tid2, "input": "tests/"})
    await asyncio.sleep(0.05)
    print(f"    回合卡在审批上（{APPROVAL_METHOD} 无人应答）")
    sub = await c2.request("thread/subscribe", {"threadId": tid2})
    print(f"    ide 订阅 → {sub['result']}；现在由 ide 插话")
    steer = await c2.request("turn/steer", {"threadId": tid2})
    print(f"    turn/steer → {steer['result']}")
    await asyncio.sleep(0.1)
    print(f"    ide 看到：{[e['method'] for e in c2.events]}")
    tail = next((e for e in c2.events if e["method"] == "item/completed"), None)
    print(f"    审批结果被插话改写成：{tail['params']['item']['output'] if tail else '?'}")
    print("    → 插话不用'通知内核作者'：它只是同一条 RPC 上的另一个请求")

    for c in (c1, c2, slow):
        c.close()


async def scenario_transport_and_backpressure() -> None:
    print("\n== 场景 4：同一 server，四种传输 ==")
    rows = [
        ("stdio://", "被前端 spawn 的子进程，行分隔 JSON（DEFAULT_LISTEN_URL，mod.rs:123）"),
        ("unix://[PATH]", "共享守护进程的 UDS + WebSocket 握手（daemon/client.rs:63；路径 mod.rs:67）"),
        ("ws://IP:PORT", "跨机/远程前端（transport/websocket.rs）"),
        ("off", "不监听：纯库用法（app-server/src/in_process.rs，s10 的主角）"),
    ]
    for url, note in rows:
        print(f"    --listen {url:<14} {note}")
    print("    → 传输可换、协议不变：这就是「没有特权前端」的工程前提")

    print("\n== 场景 5：有界通道与背压 ==")
    server = AppServer(Kernel())
    t_srv, t_cli = pair()
    cid = await server.attach(t_srv)
    conn = server.connections[cid]
    for i in range(CHANNEL_CAPACITY):
        conn.outbox.put_nowait({"method": "flood", "params": {"i": i}})
    print(f"    outbox 容量 {CHANNEL_CAPACITY}（transport/mod.rs:28）已塞满，再推一条：")
    await server.push(conn, {"id": "overflow", "method": "turn/started", "params": {}})
    dropped: Optional[dict] = None
    for _ in range(CHANNEL_CAPACITY + 2):                 # 洪水消息先出队，找到那条错误为止
        got = await asyncio.wait_for(t_cli.inbound.get(), 0.3)
        if "error" in got:
            dropped = got
            break
    print(f"    → {json.dumps(dropped, ensure_ascii=False)}（OVERLOADED -32001，不静默丢弃）")


async def scenario_gate() -> None:
    print("\n== 场景 6：每连接一个闸（connection_rpc_gate） ==")
    server = AppServer(Kernel())
    client = AppServerClient(await connect(server), name="late-client")
    r = await client.request("thread/start")
    print(f"    未握手 → {json.dumps(r.get('error'), ensure_ascii=False)}")
    conn = next(iter(server.connections.values()))
    conn.gate_open = False                       # 例如鉴权归属变更
    r2 = await client.request("initialize", {"clientInfo": {"name": "late"}})
    print(f"    门关后 → {json.dumps(r2.get('error'), ensure_ascii=False)}")
    print("    → 关门 = 不再启动排队 handler；已取得令牌的跑完收尾（connection_rpc_gate.rs 文件头）")
    client.close()


async def main() -> None:
    await scenario_stdio_subprocess()
    await scenario_one_kernel_many_connections()
    await scenario_transport_and_backpressure()
    await scenario_gate()
    print("\n结论：内核只此一份，前端都是客户端——握手定能力、id 配请求响应、")
    print("通知构成事件流、反向请求把审批送回用户所在的那条连接。")


# ---------------------------------------------------------------
# --serve：本文件自己当一个 mini app-server（stdio）
# ---------------------------------------------------------------


class StdioServerScript:
    """教学替身：把 common.rs 方法表的形状演示出来，不驱动真实 core。

    用**阻塞式** stdin/stdout（逐行读写）：Windows 的 Proactor 事件循环对管道配对挑剔，
    而"逐行泵"本来就是 stdio.rs:73 的形状——读一行、处理、写若干行，不需要异步。
    """

    def __init__(self) -> None:
        self.initialized = False
        self.experimental = False
        self.thread_id: Optional[str] = None
        self.turn_open = False

    def run(self) -> None:
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        out = sys.stdout
        for line in sys.stdin:                    # EOF → 循环自然结束：这就是断线
            line = line.strip()
            if not line:
                continue
            self.handle(json.loads(line), out)

    def send(self, out, msg: dict) -> None:
        out.write(json.dumps(msg, ensure_ascii=False) + "\n")
        out.flush()

    def handle(self, msg: dict, out) -> None:
        if "id" in msg and "method" not in msg:   # 客户端对反向请求的应答 → 继续回合
            if self.turn_open:
                self.turn_open = False
                d = msg.get("result") or {}
                self.send(out, {"method": "item/completed", "params": {
                    "threadId": self.thread_id,
                    "item": {"type": "commandExecution", "output": d.get("decision", "?")}}})
                self.send(out, {"method": "turn/completed", "params": {
                    "threadId": self.thread_id, "turn": {"status": "completed"}}})
            return
        method, params, rid = msg.get("method"), msg.get("params") or {}, msg.get("id")
        if method == "initialize":
            self.initialized = True
            self.experimental = bool((params.get("capabilities") or {}).get("experimentalApi"))
            self.send(out, {"id": rid, "result": {"protocolVersion": PROTOCOL_VERSION,
                                                  "serverInfo": {"name": "mini", "version": "0"}}})
            return
        if not self.initialized:
            self.send(out, {"id": rid, **err(INVALID_REQUEST, "Not initialized")})
            return
        if method in EXPERIMENTAL_METHODS and not self.experimental:
            self.send(out, {"id": rid, **err(INVALID_REQUEST,
                                             f"{method} requires experimental API opt-in")})
            return
        if method == "thread/start":
            self.thread_id = "thread-001"
            self.send(out, {"id": rid, "result": {"thread": {"id": self.thread_id, "owner": 1}}})
            return
        if method == "turn/start":
            self.send(out, {"id": rid, "result": {"turn": {"id": "turn-1", "status": "in_progress"}}})
            self.send(out, {"method": "turn/started", "params": {"threadId": self.thread_id}})
            self.send(out, {"method": "item/started", "params": {
                "threadId": self.thread_id, "item": {"type": "agentMessage",
                                                     "text": f"我打算执行 `ls {params.get('input', '')}`"}}})
            self.turn_open = True
            self.send(out, {"id": "s1", "method": APPROVAL_METHOD,
                            "params": {"threadId": self.thread_id,
                                       "command": f"ls {params.get('input', '')}"}})
            return
        if method == "thread/delete":
            self.send(out, {"id": rid, **err(INVALID_REQUEST, "cannot delete a live thread")})
            return
        self.send(out, {"id": rid, **err(METHOD_NOT_FOUND, f"method not found: {method}")})


if __name__ == "__main__":
    if "--serve" in sys.argv:
        StdioServerScript().run()
    else:
        asyncio.run(main())
