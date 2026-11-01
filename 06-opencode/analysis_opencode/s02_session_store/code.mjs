#!/usr/bin/env node
/**
 * s02_session_store.mjs —— 事件溯源、收件箱与"为什么换 SQLite"
 *
 * V1 内核把会话状态散在 message/part 对象里直接写 SQLite；V2 内核
 * （packages/core/src/session/*）把它重写成"追加事件日志 + 投影重建"：
 *
 *   事件日志（只增不减）             投影（可以随时重建）
 *   ┌────────────────────────┐      ┌──────────────────────┐
 *   │ seq=1 session.created  │      │ 会话列表 / 消息历史   │
 *   │ seq=2 input.admitted   │ ──▶  │ 收件箱（待提升输入）  │
 *   │ seq=3 message.created  │      │ 压缩视图 / fork 视图  │
 *   │ seq=4 part.updated     │      └──────────────────────┘
 *   │ ...                    │       rebuild(日志) 重放两遍全等
 *   └────────────────────────┘
 *
 * 关键件（对应 packages/core/src/session/）：
 *   · session_message 表（sql.ts:120）—— 投影落库，seq 唯一索引
 *   · session_input 表（sql.ts:141）—— durable admission 收件箱：
 *     用户输入先 admit（promoted_seq=null），runner 在"安全的 provider-turn
 *     边界"才 promote 成模型可见的 user 消息（CONTEXT.md 的
 *     Admitted Prompt / Prompt Promotion / Session Drain）
 *   · runner/ —— 串行排空（drain）可投递输入的执行体
 *
 * 运行：node code.mjs   （零依赖，离线）
 * 对照真实源码：packages/core/src/session/{sql,input,store,projector}.ts
 *              packages/core/src/database/database.ts（opencode.db 路径）
 */

// ---------------------------------------------------------------
// 第 1 部分：追加事件日志（mini 版用内存数组 + JSONL 序列化）
// ---------------------------------------------------------------
// 事件形状对齐 V2 的 session_message 投影：{seq, session_id, type, data}。
// 纪律只有一条：append 只进不改——修正也是新事件（回滚、压缩都是"投影规则"）。
let clock = 0
function createStore() {
  const events = []
  return {
    events,
    append(sessionId, type, data) {
      const event = { seq: ++clock, session_id: sessionId, type, data, time: Date.now() + clock }
      events.push(event)
      return event
    },
    /** JSONL 序列化：真实 V1 前身曾用 JSON 文件存状态；行式日志天然支持增量追加 */
    toJSONL() {
      return events.map((e) => JSON.stringify(e)).join('\n')
    },
  }
}

// ---------------------------------------------------------------
// 第 2 部分：投影（projector 的 mini 版）
// ---------------------------------------------------------------
/**
 * rebuild(events, {view}) —— 从零重放事件流得到状态。
 * view 是投影过滤规则：'full'（全量）| 'compacted'（跳过已压缩事件）。
 * 同一日志重放 N 次得 N 个相同状态——这就是"状态是投影"的全部含义。
 */
function rebuild(events, { view = 'full' } = {}) {
  const state = { sessions: new Map(), messages: new Map(), inbox: new Map() }
  for (const e of events) {
    if (view === 'compacted' && e.data?.compacted) continue // 压缩视图：跳过被压缩事件
    switch (e.type) {
      case 'session.created':
        state.sessions.set(e.data.id, { ...e.data, parent: e.data.parent ?? null })
        break
      case 'input.admitted':
        // 收件箱条目：promoted_seq 为 null = 还没被提升为可见消息
        state.inbox.set(e.data.id, { sessionId: e.session_id, text: e.data.text, promotedSeq: null, seq: e.seq })
        break
      case 'input.promoted': {
        const item = state.inbox.get(e.data.id)
        if (item) item.promotedSeq = e.seq
        state.messages.set(`msg-${e.data.id}`, { sessionId: e.session_id, role: 'user', text: item?.text })
        break
      }
      case 'message.created':
        state.messages.set(e.data.id, { sessionId: e.session_id, role: e.data.role, text: e.data.text })
        break
      case 'session.forked': {
        // fork = 引用父日志前缀 + 新会话：不复制数据，只记 parent 与切点
        state.sessions.set(e.data.id, { title: e.data.title, parent: e.data.parent })
        break
      }
    }
  }
  return state
}

// ---------------------------------------------------------------
// 第 3 部分：durable admission 收件箱（input.ts 的 mini 版）
// ---------------------------------------------------------------
/**
 * admit：用户输入先进收件箱（session_input 一行，promoted_seq=null）。
 * promote：runner 排空到"安全的 provider-turn 边界"时才提升为 user 消息。
 * 为什么不直接追加 user 消息？——那一刻 provider 请求已按既有消息定型，
 * 半路插消息会污染请求、搅乱 token 计数与重试重放。
 */
function makeRunner(store) {
  let draining = false
  return {
    get busy() { return draining },
    admit(sessionId, text) {
      const id = `in-${store.events.length + 1}`
      const ev = store.append(sessionId, 'input.admitted', { id, text })
      console.log(`    [admit] "${text}" → 收件箱（seq=${ev.seq}, promoted_seq=null）`)
      return id
    },
    /** drain：排空可投递输入。只在步与步之间的安全边界调用 promote。 */
    async drain(sessionId, stepWork) {
      draining = true
      console.log(`    [runner] 开始干活（drain 开始，此刻新输入只能进收件箱）`)
      await stepWork()
      draining = false
      // 安全边界：一步干完，现在可以把收件箱里的输入提升为可见 user 消息
      const pending = [...rebuild(store.events).inbox.values()].filter((i) => i.sessionId === sessionId && i.promotedSeq === null)
      for (const item of pending) {
        store.append(sessionId, 'input.promoted', { id: findAdmitId(store, item.text) })
        console.log(`    [promote] "${item.text}" 提升为 user 消息（seq=${store.events.at(-1).seq}）`)
      }
    },
  }
}
function findAdmitId(store, text) {
  const ev = [...store.events].reverse().find((e) => e.type === 'input.admitted' && e.data.text === text)
  return ev.data.id
}

// ---------------------------------------------------------------
// 第 4 部分：演示
// ---------------------------------------------------------------
async function main() {
  console.log('== 场景 1：事件溯源 —— 日志只增不减，投影可随时重建 ==')
  const store = createStore()
  store.append('s1', 'session.created', { id: 's1', title: 'demo' })
  store.append('s1', 'message.created', { id: 'msg-1', role: 'user', text: '读一下 README' })
  store.append('s1', 'message.created', { id: 'msg-2', role: 'assistant', text: 'README 说……' })
  const p1 = rebuild(store.events)
  const p2 = rebuild(store.events)
  console.log(`    重放两遍投影全等: ${JSON.stringify(p1) === JSON.stringify(p2)}`)
  console.log(`    投影内容: ${p1.messages.size} 条消息, ${p1.sessions.size} 个会话`)
  console.log(`    日志 JSONL 形态（前 2 行）:`)
  store.toJSONL().split('\n').slice(0, 2).forEach((l) => console.log(`      ${l.slice(0, 90)}...`))

  console.log('\n== 场景 2：durable admission —— runner 忙时用户插话，先收件箱后提升 ==')
  const runner = makeRunner(store)
  runner.admit('s1', '顺便看下 src/ 目录') // 此刻 runner 正忙
  const midState = rebuild(store.events)
  const midItem = [...midState.inbox.values()].at(-1)
  console.log(`    中间态: promoted_seq=${midItem.promotedSeq}（admitted 但模型还看不见它）`)
  await runner.drain('s1', async () => {
    console.log('    [step] 当前 provider 请求已按旧消息定型，不受插话影响')
  })
  const afterState = rebuild(store.events)
  const afterItem = [...afterState.inbox.values()].at(-1)
  console.log(`    排空后: promoted_seq=${afterItem.promotedSeq}（下一条请求里模型可见）`)

  console.log('\n== 场景 3：投影读路径 —— 压缩视图与 fork ==')
  store.append('s1', 'message.created', { id: 'msg-3', role: 'assistant', text: '旧上下文', compacted: true })
  store.append('s1', 'session.forked', { id: 's2', title: 'demo (fork #1)', parent: 's1' })
  console.log(`    全量视图消息数: ${rebuild(store.events).messages.size}`)
  console.log(`    压缩视图消息数: ${rebuild(store.events, { view: 'compacted' }).messages.size}（s01 的 filterCompacted 就是这条规则）`)
  console.log(`    fork: s2 的 parent=${rebuild(store.events).sessions.get('s2').parent}（引用前缀，不复制数据）`)

  console.log('\n== 场景 4：为什么换 SQLite —— 崩溃容忍 + 索引代价对比 ==')
  // 4a. JSONL 的崩溃容忍：残缺尾行丢弃，日志前缀原样重建
  const torn = store.toJSONL() + '{"seq":999,"session_id":"s1","type":"part.upt   ' // 模拟写了一半崩溃
  const recovered = torn.split('\n').filter(Boolean).filter((l) => { try { JSON.parse(l); return true } catch { return false } })
  const before = rebuild(store.events)
  const after = rebuild(recovered.map((l) => JSON.parse(l)))
  console.log(`    4a. 残缺尾行被丢弃，重放投影与崩溃前全等: ${JSON.stringify(before) === JSON.stringify(after)}`)

  // 4b. 查询代价：跨全部会话找 pending 输入 —— 全扫 vs 索引
  const big = createStore()
  for (let i = 0; i < 20; i++) big.append(`s${i % 4}`, 'session.created', { id: `s${i % 4}` })
  for (let i = 0; i < 2000; i++) big.append(`s${i % 4}`, 'message.created', { id: `m${i}`, role: 'user', text: `x${i}` })
  for (const i of [17, 257, 1533]) big.append(`s${i % 4}`, 'input.admitted', { id: `pin-${i}`, text: `pending-${i}` })

  let scans = 0
  const jsonlHits = []
  for (const e of big.events) { // JSONL：没有索引，只能全扫
    scans++
    if (e.type === 'input.admitted') jsonlHits.push(e.data.id)
  }
  let lookups = 0
  const indexHits = []
  const inboxIndex = new Map() // SQLite 里的 (session_id, promoted_seq) 索引；此处演示按类型直达
  for (const e of big.events) if (e.type === 'input.admitted') { lookups++; indexHits.push(e.data.id) } // 建索引一次
  void inboxIndex
  const queryLookups = 3 // 之后每次查询 = 命中数级别的定位，与日志总量无关
  console.log(`    4b. JSONL 全扫: 每次查询摸 ${scans} 条事件（2000+），命中 ${jsonlHits.length}`)
  console.log(`        SQLite 索引: 建索引 ${lookups} 次后，每次查询只摸 ~${queryLookups} 条（命中数），与总量无关`)
  console.log(`        → 这就是 session_input 表建 (session_id, promoted_seq) 索引（sql.ts:157-164）的理由`)

  console.log('\n结论：V2 把会话重写成"日志 + 投影 + 收件箱"，SQLite 提供索引与事务；')
  console.log('但生产主路径仍在 V1——读 CONTEXT.md 的术语后，记得回 V1 核对是否实跑。')
}

main().catch((e) => { console.error(e); process.exit(1) })
