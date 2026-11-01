#!/usr/bin/env node
/**
 * s09_provider_catalog.mjs —— mini 目录驱动 provider 系统 + 自持重试 + 流停滞看门狗
 *
 * ZCode 的模型适配层是"目录驱动"：
 *
 *   config/provider/zcode-builtin.json（revision: 30）
 *     · 一切内置 provider 都是一条条 rule（模板），不是代码注册
 *     · api.type 只有三种：anthropic-messages ×19 / openai-chat-completions ×5 /
 *       openai-responses ×4
 *     · access.type：api-key / zhipu-coding-plan-api-key / zhipu-account
 *     · schema 校验入口：packages/provider/src/config/schema.ts（解析期拒绝坏 rule）
 *     · 加新 provider = 往目录加一条 rule —— 没有代码改动
 *
 *   三个工厂（adapters/src/model/model-execution.ts:6-9）
 *     createAnthropic / createOpenAI / createOpenAICompatible
 *     底层 AI SDK streamText（runner-runtime.ts）—— 适配面收敛到 3
 *
 *   自持重试（adapters/src/model/retry-policy.ts + runner-options.ts）
 *     · 外层 maxRetries=10、base 2000ms、max 60000ms、jitter
 *     · ★ AI SDK 自身的 maxRetries 被关成 0（:92/:150）——两层重试相乘 = 100 次请求
 *
 *   流停滞看门狗（adapters/src/model/stream-idle-timeout.ts）
 *     · 默认 idle 窗口 600_000ms（contracts/src/config/index.ts:284）
 *     · :23 的 baseTimeoutMs + retryNumber × 30_000：每重试一次放宽 30 秒 ——
 *       "慢起来的 provider 在重试后更容易慢"，固定窗口会在退避链上自我制造超时
 *
 * 运行：node code.mjs        （零依赖，离线；端点全部 Mock）
 * 对照真实源码：config/provider/zcode-builtin.json、packages/provider/src/config/schema.ts、
 *              apps/zcode-cli/packages/adapters/src/model/{model-execution,retry-policy,stream-idle-timeout}.ts
 */

import { assert, banner } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：目录（zcode-builtin.json 的 mini 版，5 条示意）
// ---------------------------------------------------------------
const CATALOG = [
  { templateId: 'zai-api', api: { type: 'anthropic-messages', base_url: 'https://api.z.ai' }, models: ['glm-4.7'] },
  { templateId: 'bigmodel-api', api: { type: 'openai-chat-completions', base_url: 'https://open.bigmodel.cn' }, models: ['glm-5.3-flash'] },
  { templateId: 'anthropic', api: { type: 'anthropic-messages', base_url: 'https://api.anthropic.com' }, models: ['claude-sonnet'] },
  { templateId: 'deepseek', api: { type: 'openai-chat-completions', base_url: 'https://api.deepseek.com' }, models: ['deepseek-v3'] },
  { templateId: 'openrouter-responses', api: { type: 'openai-responses', base_url: 'https://openrouter.ai' }, models: ['or-any'] },
]

const ALLOWED_API_TYPES = new Set(['anthropic-messages', 'openai-chat-completions', 'openai-responses'])

/** 解析期校验（schema.ts 的 mini 版）：坏 rule 死在这里，不在请求期爆 */
function parseCatalog(catalog) {
  const parsed = []
  for (const rule of catalog) {
    if (!ALLOWED_API_TYPES.has(rule.api.type)) {
      throw new Error(`[parse] rule "${rule.templateId}" 的 api.type "${rule.api.type}" 不在三种之内 —— 解析期拒绝`)
    }
    if (!Array.isArray(rule.models) || rule.models.length === 0) {
      throw new Error(`[parse] rule "${rule.templateId}" 没有任何 model —— 解析期拒绝`)
    }
    parsed.push(rule)
  }
  return parsed
}

// ---------------------------------------------------------------
// 第 2 部分：三工厂 —— 内核只认同一个 runner 接口
// ---------------------------------------------------------------
function createProvider(apiType, endpoint) {
  // model-execution.ts:6-9 的 mini 版：只有三条分支，没有第四个 if
  const frame = {
    'anthropic-messages': (req) => ({ wire: 'anthropic', body: { model: req.model, messages: req.messages } }),
    'openai-chat-completions': (req) => ({ wire: 'openai', body: { model: req.model, messages: req.messages } }),
    'openai-responses': (req) => ({ wire: 'openai-resp', body: { model: req.model, input: req.messages } }),
  }[apiType]
  if (!frame) throw new Error(`[factory] 未知 api.type: ${apiType}`)
  return {
    apiType,
    endpoint,
    async call(req) { return frame(req) },   // 真实版这里走 AI SDK streamText
  }
}

// ---------------------------------------------------------------
// 第 3 部分：自持重试 —— 只允许一层重试
// ---------------------------------------------------------------
const RETRY = { maxRetries: 10, baseDelayMs: 2, maxDelayMs: 20, jitter: true } // 真实版 2000/60000ms

function backoffDelay(attempt) {
  const exp = Math.min(RETRY.baseDelayMs * 2 ** attempt, RETRY.maxDelayMs)
  return RETRY.jitter ? exp + Math.floor(Math.random() * 2) : exp
}

/** 外层重试策略；innerRetries>0 用于演示"双层重试相乘"的反例 */
async function retryWithPolicy(fn, { innerRetries = 0 } = {}) {
  let attempts = 0
  const delays = []
  for (let outer = 0; outer <= RETRY.maxRetries; outer++) {
    for (let inner = 0; inner <= innerRetries; inner++) {
      attempts++
      try { return { ok: true, attempts, delays, result: await fn() } } catch { /* 本课端点永远失败，走退避 */ }
    }
    if (outer < RETRY.maxRetries) delays.push(backoffDelay(outer))
    await new Promise((r) => setTimeout(r, delays.at(-1) ?? 0))
  }
  return { ok: false, attempts, delays }
}

// ---------------------------------------------------------------
// 第 4 部分：流停滞看门狗 —— 固定窗口 vs 放宽窗口
// ---------------------------------------------------------------
const BASE_IDLE_TIMEOUT_MS = 30

/** stream-idle-timeout.ts:23 的 mini 版：每重试一次放宽 30（真实 30_000） */
const idleTimeout = (retryNumber) => BASE_IDLE_TIMEOUT_MS + retryNumber * 30

/** 模拟一个流：每 chunks[i] ms 吐一个字；idle 期超过 watchMs 就误杀 */
async function streamWithWatchdog(chunks, { widening }) {
  let killed = false
  for (let i = 0; i < chunks.length; i++) {
    const watch = widening ? idleTimeout(i) : BASE_IDLE_TIMEOUT_MS
    const gap = chunks[i]
    if (gap > watch) { killed = true; return { killed, received: i } }   // 看门狗杀流
    await new Promise((r) => setTimeout(r, Math.min(gap, 35)))
  }
  return { killed: false, received: chunks.length }
}

// ---------------------------------------------------------------
// 第 5 部分：main() —— 四个场景
// ---------------------------------------------------------------
async function main() {
  banner('场景 1：目录解析 —— 坏 rule 死在解析期')
  const parsed = parseCatalog(CATALOG)
  console.log(`  ${parsed.length} 条 rule 全部通过：${parsed.map((r) => r.templateId).join(', ')}`)
  try {
    parseCatalog([{ templateId: 'gemini-wannabe', api: { type: 'gemini', base_url: 'x' }, models: ['g'] }])
  } catch (e) { console.log(`  ${e.message}`) }

  banner('场景 2：三工厂 —— 同一内核打通三种 api')
  const kernelCall = async (provider, model) => {
    const { wire, body } = await provider.call({ model, messages: [{ role: 'user', text: 'hi' }] })
    return `${provider.apiType} → ${wire} 帧 @ ${provider.endpoint}`
  }
  for (const rule of parsed.slice(0, 3)) {
    const provider = createProvider(rule.api.type, rule.api.base_url)
    console.log(`  ${await kernelCall(provider, rule.models[0])}`)
  }

  banner('场景 3：自持重试 —— 退避序列与双层相乘反例')
  const flaky = async () => { throw new Error('端点持续失败') }
  const single = await retryWithPolicy(flaky, {})
  console.log(`  单层重试（max=10）：${single.attempts} 次尝试，退避序列 [${single.delays.join(', ')}]ms（指数+jitter，封顶）`)
  const doubled = await retryWithPolicy(flaky, { innerRetries: 3 })
  console.log(`  若内层（AI SDK 侧）maxRetries=3 没关：${doubled.attempts} 次尝试 = (${RETRY.maxRetries}+1) × 4 相乘 ← 这就是为什么 runner-options 把它关成 0`)
  assert(doubled.attempts === 4 * single.attempts, '双层重试必须相乘可见')

  banner('场景 4：流停滞看门狗 —— 固定窗口误杀"越重试越慢"的流')
  // 端点特性：每次重试后 idle gap 变长（慢起来的 provider 重试后更容易慢）
  const chunks = [5, 40, 70]   // 3 次尝试的 idle gap（ms）
  const fixed = await streamWithWatchdog(chunks, { widening: false })
  const widened = await streamWithWatchdog(chunks, { widening: true })
  console.log(`  固定窗口(${BASE_IDLE_TIMEOUT_MS}ms)：第 ${fixed.received + 1} 次重试被误杀（killed=${fixed.killed}）`)
  console.log(`  放宽窗口(30+n×30ms)：等到第 ${widened.received} 个字（killed=${widened.killed}）`)
  assert(fixed.killed && !widened.killed, '放宽窗口应救回流')

  console.log('\n结论：扩展走目录不走代码；重试只留一层；超时窗口跟着退避链一起放宽。')
}

main().catch((e) => { console.error(e); process.exit(1) })
