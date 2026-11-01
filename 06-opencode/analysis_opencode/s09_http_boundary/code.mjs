#!/usr/bin/env node
/**
 * s09_http_boundary.mjs —— HTTP-first 边界：同一份 app.fetch，两种传输
 *
 * OpenCode 的服务端是一个 Effect HttpApi 应用（24 个 group）。它的精髓在
 * cli/tui/worker.ts:56（上游 :42）这一行：
 *
 *     const response = await Server.Default().app.fetch(request)
 *
 *   —— 默认部署下（Bun Worker 线程），TUI 的 fetch 被桥成对同一个
 *   HttpApi 应用的"进程内直调"：协议是契约，不是网络。只有传了
 *   --port/--hostname/--mdns 才走 Server.listen 真开端口（rpc.server 分支）；
 *   server.ts:120-121 的端口策略是"先试 4096，被占则随机"。
 *   specs/tui-package.md 更是把边界写成规范：TUI 不得依赖内核包。
 *
 * mini 版用 Node 内置能力复刻同一内核的两种传输（零依赖）：
 *
 *   ┌─ kernel ────────────────────────────────────┐
 *   │ app.fetch(request)  ← 唯一的请求处理器        │
 *   │   POST /turn     → 跑一轮 mock runLoop       │
 *   │   GET  /events   → SSE 事件流                │
 *   │   GET  /session  → 会话投影                  │
 *   └─────────────────────────────────────────────┘
 *     场景1: kernel.app.fetch(Request)      ← 无端口，进程内
 *     场景2: http.createServer 包同一函数    ← 随机端口 + 全局 fetch
 *     两种模式的响应逐字节相同 → 协议与传输解耦
 *
 * 运行：node code.mjs   （会临时绑定本机随机端口，演示完即关）
 * 对照真实源码：packages/opencode/src/cli/tui/worker.ts（进程内直调桥）
 *              packages/opencode/src/server/server.ts:120-121（端口回退）
 *              packages/opencode/src/server/routes/instance/httpapi/handlers/event.ts（SSE）
 */

import http from 'node:http'

// ---------------------------------------------------------------
// 第 1 部分：mini 内核 —— app.fetch 是唯一的请求处理器
// ---------------------------------------------------------------
// 会话状态与 mock turn（剧本化，s01 的三态从简为"事件流"）
const sessions = new Map()
let eventSeq = 0

function mockTurn(userText) {
  return [
    { type: 'tool-call', name: 'read', args: { path: 'README.md' } },
    { type: 'tool-result', name: 'read', result: `README 内容（回应 "${userText}"）` },
    { type: 'step-finish', finish: 'stop', tokens: 420 },
  ]
}

/** 把请求交给处理器并返回 web-standard Response——与真实 app.fetch 同构 */
const kernel = {
  sessions,
  app: {
    async fetch(request) {
      const url = new URL(request.url)
      if (request.method === 'POST' && url.pathname === '/turn') {
        let body
        try {
          body = await request.json()
        } catch {
          return Response.json({ error: 'invalid json' }, { status: 400 }) // 失败也走协议
        }
        if (!body?.sessionID || !body?.text) return Response.json({ error: 'sessionID and text required' }, { status: 400 })
        const session = sessions.get(body.sessionID) ?? { id: body.sessionID, events: [], messages: [] }
        sessions.set(body.sessionID, session)
        session.messages.push({ role: 'user', text: body.text })
        const events = mockTurn(body.text).map((e) => ({ ...e, seq: ++eventSeq }))
        session.events.push(...events)
        session.messages.push({ role: 'assistant', text: 'done' })
        return Response.json({ sessionID: body.sessionID, events, messages: session.messages.length })
      }
      if (request.method === 'GET' && url.pathname === '/events') {
        // SSE：mini 版把缓存的三个会话事件按帧推完即收（真实版是长连 + 10s 心跳）
        const sid = url.searchParams.get('sessionID') ?? 's1'
        const session = sessions.get(sid)
        const stream = new ReadableStream({
          start(controller) {
            const enc = new TextEncoder()
            const frames = (session?.events ?? []).map((e) => enc.encode(`event: session\nid: ${e.seq}\ndata: ${JSON.stringify(e)}\n\n`))
            frames.forEach((f) => controller.enqueue(f))
            controller.enqueue(enc.encode(': heartbeat\n\n')) // 心跳语义（真实版每 10s）
            controller.close()
          },
        })
        return new Response(stream, { headers: { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' } })
      }
      if (request.method === 'GET' && url.pathname === '/session') {
        const sid = url.searchParams.get('sessionID') ?? 's1'
        const session = sessions.get(sid)
        if (!session) return Response.json({ error: 'not found' }, { status: 404 })
        return Response.json({ id: session.id, messageCount: session.messages.length, eventCount: session.events.length })
      }
      return Response.json({ error: 'no such route' }, { status: 404 })
    },
  },
}

// ---------------------------------------------------------------
// 第 2 部分：演示
// ---------------------------------------------------------------
async function main() {
  console.log('== 场景 1：进程内直调 —— 无端口、无 TCP，协议即契约 ==')
  const req1 = new Request('http://kernel.internal/turn', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ sessionID: 's1', text: '读一下 README' }),
  })
  // 注意：此刻没有任何 server 在监听——请求直接进处理器函数
  const res1 = await kernel.app.fetch(req1)
  const body1 = await res1.json()
  console.log(`    POST /turn → ${res1.status}`)
  console.log(`    事件序列: ${body1.events.map((e) => `${e.seq}:${e.type}`).join(' → ')}`)
  console.log(`    （请求 URL 的主机名是虚构的——根本没建立连接）`)

  console.log('\n== 场景 2：真 HTTP —— http.createServer 包同一个 app.fetch ==')
  // 与真实 Server.listen 同构：处理器只有一个，传输换了
  const server = http.createServer(async (req, res) => {
    const chunks = []
    for await (const chunk of req) chunks.push(chunk) // GET 无 body → 空串
    const bodyText = Buffer.concat(chunks).toString('utf8')
    const url = `http://localhost${req.url}`
    const webReq = new Request(url, {
      method: req.method,
      headers: req.headers,
      body: ['GET', 'HEAD'].includes(req.method) ? undefined : bodyText,
    })
    const webRes = await kernel.app.fetch(webReq)
    res.writeHead(webRes.status, Object.fromEntries(webRes.headers))
    res.end(Buffer.from(await webRes.arrayBuffer()))
  })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve)) // 端口 0 = OS 随机
  const port = server.address().port
  console.log(`    监听 127.0.0.1:${port}（端口 0 → OS 随机；真实代码先试 4096 被占则随机）`)

  const res2 = await fetch(`http://127.0.0.1:${port}/turn`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ sessionID: 's1', text: '读一下 README' }),
  })
  const body2 = await res2.json()
  console.log(`    网络模式 POST /turn → ${res2.status}，事件: ${body2.events.map((e) => e.type).join(',')}`)
  // seq 是全局递增的（跨模式共享事件序），等价性看事件类型与载荷
  const same =
    JSON.stringify(body1.events.map((e) => [e.type, e.name ?? null])) ===
    JSON.stringify(body2.events.map((e) => [e.type, e.name ?? null]))
  console.log(`    与场景 1 同一内核同一处理器：${same ? '事件序列等价' : '不一致!'}`)

  console.log('\n== 场景 3：SSE 事件流 —— 两个客户端共享同一条流 ==')
  const sse = await fetch(`http://127.0.0.1:${port}/events?sessionID=s1`)
  const raw = await sse.text()
  const frames = raw.split('\n\n').filter((f) => f.startsWith('event:'))
  console.log(`    GET /events → ${sse.headers.get('content-type')}`)
  frames.forEach((f) => {
    const data = JSON.parse(f.split('data: ')[1])
    console.log(`    ← [TUI 客户端] 帧 seq=${data.seq} type=${data.type}`)
  })
  // 第二个客户端（审计器）也只走协议收同一股事件——多前端共享事件流
  const sse2 = await fetch(`http://127.0.0.1:${port}/events?sessionID=s1`)
  const frames2 = (await sse2.text()).split('\n\n').filter((f) => f.startsWith('event:'))
  console.log(`    ← [审计客户端] 也收到 ${frames2.length} 帧（同一内核同一事件源）`)
  console.log(`    ${frames.length} 帧 + 1 条心跳注释（真实版长连 + 10s 心跳 + 目录过滤）`)

  console.log('\n== 场景 4：失败也走协议（404 / 400）==')
  const r404 = await fetch(`http://127.0.0.1:${port}/nope`)
  console.log(`    GET /nope → ${r404.status} ${JSON.stringify(await r404.json())}`)
  const r400 = await fetch(`http://127.0.0.1:${port}/turn`, { method: 'POST', body: 'not-json' })
  console.log(`    POST /turn (坏 JSON) → ${r400.status} ${JSON.stringify(await r400.json())}`)

  await new Promise((resolve) => server.close(resolve))
  console.log('\n结论：HTTP-first 的落点是一个可被直接调用的 app.fetch；')
  console.log('加 --port 变网络服务，不加就是零开销的进程内调用——契约与传输彻底解耦。')
}

main().catch((e) => { console.error(e); process.exit(1) })
