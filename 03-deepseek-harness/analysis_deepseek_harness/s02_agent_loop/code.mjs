#!/usr/bin/env node
/**
 * s02_agent_loop.mjs —— 内核循环：轮次（turn）→ 步骤（step）→ inbox
 *
 * dsh 的 agent loop（packages/core/agent-loop）自己也是一个 Cordis 插件，
 * 它的头部注释只有一句话却是最重要的设计承诺：
 *
 *     "Every request is derived from the session log."
 *     （每一次请求都是从会话日志推导出来的）
 *
 * 本文件实现一个 mini 版 ReactLoopAgent，覆盖四个核心机制：
 *
 *   1. 轮次/步骤两级状态机 —— turn 是"一次用户输入到最终回复"，
 *      step 是"组装请求 → 流式收模型 → 工具调用"的一拍；turn 由若干 step 组成。
 *   2. inbox（收件箱）—— 两条待处理列表：next-turn / next-step；
 *      唯一写操作是 splice（像数据库只有一条 UPDATE 语句）。
 *   3. 唤醒分类 —— send（下一轮）/ steer（步间插话）/ inject（静默注入）/
 *      followup（排队下一轮），目标与是否唤醒被精确区分。
 *   4. 粘性结局 —— 任何一步撞到 max-tokens，本轮结局就是 max-tokens，
 *      后续步骤正常完成也不能"降级"回 completed（统计口径不漂移）。
 *
 *   +----------------+  send    +-------------+
 *   |     用户       | -------> | inbox       |
 *   +----------------+          | next-turn:[]|        +------------------+
 *         | steer(插话)         | next-step:[]|        |    一轮 turn     |
 *         +--------------------+-------------+        |  step1 → step2…  |
 *                                                      |  每步：请求→流式  |
 *   每 step 前先 claim：取走 next-step 全部 + next-turn 一条             |
 *   模型不调工具 → turn/end，收工                                        |
 *
 * 运行：node code.mjs        （零依赖、离线，模型是脚本化的 MockModel）
 * 对照真实源码：packages/core/agent-loop/src/agent.ts（:225 kick / :269 turn /
 *              :352 step / :501 prepareRequest）、inbox.ts
 */

// ---------------------------------------------------------------
// 第 0 部分：最小会话日志（s03 有完整版：持久化 + 投影 + 修复）
// ---------------------------------------------------------------
class MiniLog {
  constructor() { this.events = []; this.seq = 0 }
  append(type, payload) {
    const event = { seq: ++this.seq, type, payload, ts: Date.now() }
    this.events.push(event)
    return event
  }
}

// ---------------------------------------------------------------
// 第 1 部分：inbox —— 两条列表，一种写操作（splice）
// ---------------------------------------------------------------
/**
 * dsh 的 inbox 头部注释："每一次增删都是一条持久化 splice 事件——
 * 连输入队列本身都是事件溯源的投影，没有内存态。"
 * 关键不变量（mini 版照样遵守）：
 *  - 全队列只有一种写操作 splice + 一种事件 agent/inbox/spliced；
 *  - claim 是"取走"不是"复制"：消息从队列消失、进入会话日志，不重复持有；
 *  - clear 先清 next-step 再清 next-turn（顺序可重放）。
 */
class MiniInbox {
  constructor(log) {
    this.log = log
    this.queues = { 'next-turn': [], 'next-step': [] }
  }
  /** 唯一写入口。op: append/prepend/remove/clear 之一 —— 高层操作全是它的语法糖 */
  splice(target, op, message) {
    const q = this.queues[target]
    if (message) {
      // 消息 ID 全队列唯一：同一条消息同时在两条列表是逻辑错误，写路径直接拒绝
      for (const q2 of Object.values(this.queues))
        if (q2.some((m) => m.id === message.id)) throw new Error(`消息重复入队: ${message.id}`)
    }
    if (op === 'append') q.push(message)
    else if (op === 'prepend') q.unshift(message)
    else if (op === 'remove') {
      const i = q.findIndex((m) => m.id === message.id)
      if (i >= 0) q.splice(i, 1)
    } else if (op === 'clear') q.length = 0
    // 落日志：队列状态可从事件流重放重建（s03 投影的主角色）
    this.log.append('agent/inbox/spliced', { target, op, message: message?.text ?? null })
  }
  send(msg)     { this.splice('next-turn', 'append', msg) }   // 正常发送 → 下一轮
  steer(msg)    { this.splice('next-step', 'append', msg) }   // 插话 → 本轮下一步
  inject(msg)   { this.splice('next-step', 'prepend', msg) }  // 静默注入（不唤醒）
  followup(msg) { this.splice('next-turn', 'append', msg) }   // 排队下一轮

  /** 步开始时原子取走：next-step 全部 + 至多一条 next-turn（"取走"不是"复制"） */
  claim() {
    const taken = this.queues['next-step'].splice(0)
    if (this.queues['next-turn'].length) taken.push(this.queues['next-turn'].shift())
    return taken
  }
}

// ---------------------------------------------------------------
// 第 2 部分：脚本化 MockModel —— 按"请求第几次"返回预制响应
// ---------------------------------------------------------------
/** 一个响应 = 若干内容块 + 停止原因。dsh 里对应 assistant 消息的 blocks。 */
const text = (t) => ({ blocks: [{ type: 'text', text: t }], stopReason: 'end_turn' })
const call = (id, name, args) => ({ blocks: [{ type: 'tool_call', id, name, args }], stopReason: 'tool_use' })
const hitLimit = (t) => ({ blocks: [{ type: 'text', text: t }], stopReason: 'max_tokens' })

class MockModel {
  /** @param {Array<{blocks, stopReason}>} script 按调用次序取用 */
  constructor(script) { this.script = script; this.calls = 0 }
  async generate(request) {
    const resp = this.script[this.calls++] ?? text('（脚本用尽，兜底回答）')
    return resp
  }
}

// ---------------------------------------------------------------
// 第 3 部分：MiniAgentLoop —— 循环本体（它自己也只是个插件）
// ---------------------------------------------------------------
class MiniAgentLoop {
  constructor({ model, tools, log }) {
    this.model = model
    this.tools = tools          // { name: async (args) => string }，s05 换成注册表+流水线
    this.log = log
    this.inbox = new MiniInbox(log)
    this.running = false
  }

  /** 驱动器：dsh 的 kick 就是 `while (await this.turn())` —— 驱动器本身是个 while 循环 */
  async kick() {
    if (this.running) return            // 幂等：运行中重复 kick 只是把唤醒排队
    this.running = true
    try { while (await this.turn()) { /* 有排队的 followup → 继续下一轮 */ } }
    finally { this.running = false }
  }

  /** 一轮：turn/start → 步循环 → turn/end，全部落日志 */
  async turn() {
    const first = this.inbox.claim()
    if (first.length === 0) return false           // 没活儿 → 驱动器停转
    this.log.append('turn/start', {})
    let outcome = 'completed'                       // 轮次结局
    for (const msg of first) this.log.append('user/message', { text: msg.text })

    let step = 0
    while (true) {
      step++
      this.log.append('step/start', { step })

      // ★ "请求从日志推导"：不持有任何私有的对话内存，
      //   每一步都从日志重放投影出消息列表（s03 的投影在这里只做最简版）。
      const request = this.deriveRequest()
      const resp = await this.model.generate(request)

      // 流结束先落 assistant 消息，再谈工具 —— "日志里没有悬空流"
      this.log.append('assistant/message', {
        stopReason: resp.stopReason,
        blocks: resp.blocks.map((b) => (b.type === 'text' ? { type: 'text', text: b.text } : { type: 'tool_call', name: b.name })),
      })
      // ★ 粘性结局：撞过 max-tokens 就记住，正常完成也不降级
      if (resp.stopReason === 'max_tokens') outcome = 'max-tokens'

      const calls = resp.blocks.filter((b) => b.type === 'tool_call')
      if (resp.stopReason === 'end_turn' && calls.length === 0) {
        this.log.append('step/end', { step, reason: 'completed' })
        break                                        // 模型不再调工具 → 本轮收工
      }
      for (const c of calls) {
        this.log.append('tool/call', { id: c.id, name: c.name, args: c.args })
        let result
        try { result = await this.tools[c.name](c.args) }
        catch (e) { result = `工具错误: ${e.message}` }   // 业务失败落日志，不炸循环
        this.log.append('tool/result', { id: c.id, result })
      }
      this.log.append('step/end', { step, reason: resp.stopReason })

      // 步间收信：steer/inject 的插话在这里进入本轮（作为追加的 user 消息）
      const inter = this.inbox.claim()
      for (const m of inter) this.log.append('user/message', { text: m.text })
    }

    this.log.append('turn/end', { reason: outcome })  // ★ 结局取轮内最坏值（粘性）
    // 下一轮还有排队输入（send/followup）→ 返回 true 让驱动器继续转
    return this.inbox.queues['next-turn'].length > 0
  }

  /** 从日志推导请求：把 user/assistant/tool 消息按 seq 顺序重放成对话数组 */
  deriveRequest() {
    const messages = []
    for (const e of this.log.events) {
      if (e.type === 'user/message') messages.push({ role: 'user', content: e.payload.text })
      else if (e.type === 'assistant/message')
        messages.push({ role: 'assistant', content: e.payload.blocks.map((b) => b.text ?? `[调用 ${b.name}]`).join('') })
      else if (e.type === 'tool/result') messages.push({ role: 'tool', content: e.payload.result })
    }
    return { messages }
  }
}

// ---------------------------------------------------------------
// 第 4 部分：演示 —— 三个场景
// ---------------------------------------------------------------
async function main() {
  const tools = {
    read_file: async ({ path }) => `（模拟）${path} 的内容：今晚记得买牛奶。`,
  }

  console.log('========== 场景 1：一轮 = 两个 step（调用工具 → 收尾） ==========')
  {
    const log = new MiniLog()
    const model = new MockModel([
      call('c1', 'read_file', { path: 'notes.txt' }),   // step1：模型要工具
      text('看完 notes.txt：里面写着今晚记得买牛奶。'),      // step2：收尾
    ])
    const agent = new MiniAgentLoop({ model, tools, log })
    agent.inbox.send({ id: 'u1', text: '帮我看看 notes.txt 说了什么' })
    await agent.kick()
    printLog(log)
  }

  console.log('\n========== 场景 2：steer 步间插话（同一轮内被吸收） ==========')
  {
    const log = new MiniLog()
    const model = new MockModel([
      call('c1', 'read_file', { path: 'notes.txt' }),
      text('notes.txt 说买牛奶；todo.txt 我也顺手看了。'),
    ])
    // 工具故意慢 30ms：给 5ms 后到达的 steer 留出"跑在 step1 中途"的窗口
    const slowTools = { ...tools, read_file: async (a) => { await new Promise((r) => setTimeout(r, 30)); return tools.read_file(a) } }
    const agent = new MiniAgentLoop({ model, tools: slowTools, log })
    agent.inbox.send({ id: 'u1', text: '看看 notes.txt' })
    const p = agent.kick()
    // 趁 step1 的工具在跑，用户插话 —— steer 的目标是"下一步"，不是"下一轮"
    setTimeout(() => agent.inbox.steer({ id: 'u2', text: '顺便把 todo.txt 也看了' }), 5)
    await p
    printLog(log, ['turn/start', 'user/message', 'step/start', 'tool/', 'step/end', 'assistant/message', 'turn/end'])
  }

  console.log('\n========== 场景 3：粘性结局 —— 撞过 max-tokens 就不许降级 ==========')
  {
    const log = new MiniLog()
    const model = new MockModel([
      hitLimit('我讲到一半……'),                             // step1：被截断
      text('补完了。'),                                    // step2：正常完成
    ])
    const agent = new MiniAgentLoop({ model, tools, log })
    agent.inbox.send({ id: 'u1', text: '写一份长报告' })
    await agent.kick()
    const end = log.events.find((e) => e.type === 'turn/end')
    console.log(`step2 明明正常完成了，turn/end 的 reason 仍是: ${end.payload.reason}`)
    console.log('→ 轮次结局取轮内最坏值，统计口径不漂移（dsh agent.ts :305-310 的不变量）')
  }
}

function printLog(log, types) {
  for (const e of log.events) {
    if (types && !types.some((t) => e.type.startsWith(t) || t === e.type)) continue
    const p = JSON.stringify(e.payload)
    console.log(`  #${String(e.seq).padStart(2, '0')} ${e.type.padEnd(22)} ${p.length > 88 ? p.slice(0, 88) + '…' : p}`)
  }
}

main().catch((e) => { console.error(e); process.exit(1) })
