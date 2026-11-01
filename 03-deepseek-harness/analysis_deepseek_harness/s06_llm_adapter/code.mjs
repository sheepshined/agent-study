#!/usr/bin/env node
/**
 * s06_llm_adapter.mjs —— LLM 适配缝：流式、重试与 token 计量
 *
 * s02 的循环里模型调用只有一行 `model.generate(request)`。dsh 把这一跳
 * 拆成可替换的插件带（packages/llm/）：
 *
 *   llm/llm            词汇表与 seam：adapter 接口、BlockAssembler（流→块）、
 *                      LlmCallConfig（含 adapterDefaults）、retry-policy
 *   llm/llm-deepseek   DeepSeek 官方适配器（wire 扩展见 deepseek-llm-api-extensions）
 *   llm/llm-retry      重试（落 llm/retry 事件）
 *   llm/token-meter    token 计量
 *
 *   adapter.stream(call) ─┬─→ BlockAssembler ─→ 完整 assistant 消息
 *        │ 429/网络抖动    │
 *        └─ retry-policy ──┘（指数退避，逐次落 llm/retry 事件）
 *
 *   关键细节（agent.ts :501 prepareRequest 的 requestProposal）：
 *   adapter 声明"哪些参数归我管"（adapterDefaults）——这些参数在插件
 *   提议下一跳配置前被剥离，防止插件改了也白改。
 *
 * 运行：node code.mjs                     （默认离线，Mock 流）
 *       DEEPSEEK_API_KEY=sk-... node code.mjs   （末尾追加真实 DeepSeek 流式调用）
 * 对照真实源码：packages/llm/llm/src/{assembler,retry-policy,call-config}.ts、
 *              packages/llm/llm-deepseek/、llm/token-meter/
 */

import { sleep } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：BlockAssembler —— 增量块累积成完整消息
// ---------------------------------------------------------------
/**
 * 流式响应是一堆 delta：text_delta、tool_call_delta（带 index，
 * name/arguments 分片到达）。BlockAssembler 按 index 归位、拼接，
 * 流结束时产出结构化 blocks —— dsh 的 assembler.ts 同职责。
 */
class BlockAssembler {
  constructor() { this.text = ''; this.calls = new Map() } // index -> {id,name,args}

  push(delta) {
    if (delta.type === 'text_delta') this.text += delta.text
    else if (delta.type === 'tool_call_delta') {
      const c = this.calls.get(delta.index) ?? { id: delta.id, name: '', args: '' }
      c.name += delta.nameDelta ?? ''
      c.args += delta.argsDelta ?? ''
      this.calls.set(delta.index, c)
    }
    return this
  }

  /** 流结束：结构化 blocks + 停止原因（循环据此决定继续还是收工） */
  finish(stopReason) {
    const blocks = []
    if (this.text) blocks.push({ type: 'text', text: this.text })
    for (const [, c] of [...this.calls.entries()].sort((a, b) => a[0] - b[0]))
      blocks.push({ type: 'tool_call', id: c.id, name: c.name, args: JSON.parse(c.args || '{}') })
    return { blocks, stopReason }
  }
}

// ---------------------------------------------------------------
// 第 2 部分：重试策略 —— 指数退避，逐次落事件
// ---------------------------------------------------------------
/**
 * dsh 的 retry-policy.ts + llm-retry 包：只重试"瞬态错误"
 * （429/5xx/网络抖动），参数错误重试一万次也不会好。
 * 每次重试落 llm/retry 事件 —— 计量与排障都靠它。
 */
class RetryPolicy {
  constructor({ maxAttempts = 3, baseMs = 20, log }) { Object.assign(this, { maxAttempts, baseMs, log }) }
  /** 判定瞬态：真实实现会看 HTTP 状态与错误链（errorChain） */
  isTransient(err) { return /429|503|timeout|ECONNRESET/.test(err.message) }

  async run(fn) {
    for (let attempt = 1; ; attempt++) {
      try { return await fn(attempt) }
      catch (err) {
        if (attempt >= this.maxAttempts || !this.isTransient(err)) throw err
        const wait = this.baseMs * 2 ** (attempt - 1)
        this.log('llm/retry', { attempt, wait, error: err.message })
        await sleep(wait)
      }
    }
  }
}

// ---------------------------------------------------------------
// 第 3 部分：适配器 —— Mock 流 + 可选的 DeepSeek 真流
// ---------------------------------------------------------------
/** Mock 适配器：前 2 次抛 429（触发重试），之后产出一条流式响应 */
class FlakyMockAdapter {
  constructor(script) { this.script = script; this.calls = 0; this.fail = 2 }
  /** adapterDefaults：声明"哪些参数归我管"（agent-loop 提议配置前要剥离它们） */
  adapterDefaults = { reasoningEffort: true }

  async *stream(call) {
    this.calls++
    if (this.calls <= this.fail) { await sleep(5); throw new Error('429 rate limited') }
    const resp = this.script[(this.calls - this.fail - 1) % this.script.length]
    for (const delta of resp) { await sleep(3); yield delta } // 模拟分片到达
  }
}

/** DeepSeek 官方适配器（mini）：仅在设置了 DEEPSEEK_API_KEY 时启用 */
class DeepSeekAdapter {
  adapterDefaults = { reasoningEffort: true }
  constructor(apiKey) { this.apiKey = apiKey }
  async *stream(call) {
    const resp = await fetch('https://api.deepseek.com/chat/completions', {
      method: 'POST',
      headers: { 'content-type': 'application/json', authorization: `Bearer ${this.apiKey}` },
      body: JSON.stringify({
        model: 'deepseek-chat', messages: call.messages, stream: true,
        stream_options: { include_usage: true }, // 真实代码里 token 计量走这里
      }),
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const reader = resp.body.getReader()
    const dec = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      for (const line of buf.split('\n')) {
        if (!line.startsWith('data:')) continue
        const data = line.slice(5).trim()
        if (data === '[DONE]') return
        const chunk = JSON.parse(data).choices?.[0]?.delta
        if (chunk?.content) yield { type: 'text_delta', text: chunk.content }
      }
      buf = buf.slice(buf.lastIndexOf('\n') + 1)
    }
  }
}

// ---------------------------------------------------------------
// 第 4 部分：调用门面 + token 计量
// ---------------------------------------------------------------
/** 粗略计量：dsh 的 token-meter 是精确口径（含缓存命中计费差），mini 版演示形状 */
const approxTokens = (s) => Math.ceil(s.length / 4)
class TokenMeter {
  constructor() { this.total = 0; this.perCall = [] }
  meter(call, resp) {
    const inTok = call.messages.reduce((n, m) => n + approxTokens(m.content), 0)
    const outTok = resp.blocks.reduce((n, b) => n + approxTokens(b.text ?? b.name ?? ''), 0)
    this.total += inTok + outTok
    this.perCall.push({ inTok, outTok })
  }
}

/**
 * 调用门面：重试包住"流→块"的全程。中途断流会让已收的 delta 作废，
 * 整次调用从头再来 —— 这就是为什么 assembler 在重试环内。
 */
async function callWithRetry(adapter, call, { retry, meter, log }) {
  const resp = await retry.run(async () => {
    const asm = new BlockAssembler()
    for await (const delta of adapter.stream(call)) asm.push(delta)
    const r = asm.finish('end_turn')
    // 中途抛错会向上传播给 retry.run —— 已收块不产出半成品消息
    return r
  })
  meter.meter(call, resp)
  log('assistant/message', { blocks: resp.blocks.map((b) => b.text ?? `[调用 ${b.name}]`), stopReason: resp.stopReason })
  return resp
}

/** requestProposal（agent.ts :501）：插件提议下一跳配置前，剥离 adapter 自管的参数 */
function requestProposal(config, adapter) {
  const proposal = { ...config }
  if (adapter.adapterDefaults?.reasoningEffort) delete proposal.reasoningEffort
  return proposal
}

// ---------------------------------------------------------------
// 第 5 部分：演示
// ---------------------------------------------------------------
async function main() {
  const events = []
  const log = (type, payload) => { events.push({ type, payload }); console.log(`  ${type.padEnd(19)} ${JSON.stringify(payload).slice(0, 100)}`) }
  const retry = new RetryPolicy({ log })
  const meter = new TokenMeter()

  console.log('== 1. 429 两次 → 指数退避重试 → 流式块组装 ==')
  const mock = new FlakyMockAdapter([
    [{ type: 'text_delta', text: '正在' }, { type: 'text_delta', text: '读文件…' },
     { type: 'tool_call_delta', index: 0, id: 'c1', nameDelta: 'read_', argsDelta: '' },
     { type: 'tool_call_delta', index: 0, nameDelta: 'file', argsDelta: '{"path":"a.txt"}' }],
  ])
  const call = { messages: [{ role: 'user', content: '帮我读一下 a.txt' }], config: { model: 'deepseek-chat', temperature: 0.2, reasoningEffort: 'high' } }
  const resp = await callWithRetry(mock, call, { retry, meter, log })
  console.log('  组装出的 blocks:', JSON.stringify(resp.blocks))
  console.log('  token 计量:', JSON.stringify(meter.perCall), `累计 ${meter.total} tok（mini 口径）`)

  console.log('\n== 2. adapterDefaults：插件提议配置前剥离 adapter 自管参数 ==')
  const proposal = requestProposal(call.config, mock)
  console.log('  原配置:', JSON.stringify(call.config))
  console.log('  提议给插件的:', JSON.stringify(proposal), '<- reasoningEffort 被 adapter 声明为自管，先剥离')
  console.log('  （否则插件改了也白改 —— adapter 每跳都会覆盖回来）')

  const apiKey = process.env.DEEPSEEK_API_KEY
  if (apiKey) {
    console.log('\n== 3. 真实 DeepSeek 流式调用（检测到 DEEPSEEK_API_KEY） ==')
    const real = new DeepSeekAdapter(apiKey)
    const realResp = await callWithRetry(real, { messages: call.messages }, { retry, meter, log })
    console.log('  真实回复块数:', realResp.blocks.length)
  } else {
    console.log('\n== 3. （未设 DEEPSEEK_API_KEY，跳过真实调用）==')
    console.log('   想看真流：export DEEPSEEK_API_KEY=sk-... 后重跑 —— 适配缝保证其余代码零改动')
  }
}

main().catch((e) => { console.error(e); process.exit(1) })
