#!/usr/bin/env node
/**
 * s05_context_budget.mjs —— mini 三层上下文预算：microcompact → auto compact → reactive + 熔断
 *
 * ZCode 把"窗口装不下"拆成三个层次处理，全部长在 turn-loop 的治理段（s01 第 2 层）：
 *
 *   ① microcompact（compact/microcompact.ts，纯函数 maybeLocalMicrocompactMessages :83）
 *      只把"旧 tool result"换成 "[Old tool result content cleared]"（:27）。
 *      三条纪律：消息条数与 tool_use/tool_result 配对恒定；最近 keepRecentToolResults=5
 *      个结果永不碰；收益 < minTokenSavings=256 就当没发生。
 *
 *   ② auto compact（compact/policy.ts）
 *      预算 = contextWindow(200k) − 输出预留 min(maxOutput, 21_000)(:22) − buffer 13_000(:26)。
 *      shouldAutoCompact(:90-160) 决策必带 reason；连续失败 3 次熔断(:163)。
 *      摘要提示词九段结构（prompt.ts:33-44），两次强调安全指令 verbatim 保留(:49,:40)。
 *
 *   ③ reactive compact（turn-model-step.ts:742-803）
 *      超窗错误 / finish reason 之后的补救压缩，压完 continue。
 *
 *   ④ rapid-refill 熔断（turn-loop.ts:103-121）
 *      evaluateRapidRefill 在"确实需要压缩"那一刻判定；压完立刻又满 → 抛
 *      CompactRapidRefillError 交还用户 —— 治理段里少见的主动终止路径。
 *
 *   预算账本（字符估算）：
 *   0 ├──────────── 可用 ────────────┤├─ 输出 21k ─┤├─ buffer 13k ─┤ 200k
 *                    ^ 摘要线：越线先 microcompact，再 auto compact
 *
 * 运行：node code.mjs        （零依赖，离线；摘要器 Mock，真实版走同一模型缝）
 * 对照真实源码：core/src/compact/{microcompact,policy,prompt}.ts、
 *              core/src/runtime/methods/{turn-loop.ts,turn-model-step.ts}
 */

import { assert, banner } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：预算账本（compact/policy.ts 的 mini 版）
// ---------------------------------------------------------------
const CONFIG = {
  contextWindow: 200_000,        // 窗口
  maxOutputTokens: 40_000,
  outputReserve: 21_000,         // :22 min(maxOutput, 21_000)
  buffer: 13_000,                // :26 AUTOCOMPACT_BUFFER_TOKENS
  minTokenSavings: 256,          // microcompact 的最小收益
  keepRecentToolResults: 5,      // microcompact 永不碰的最近 N 个
  maxConsecutiveRapidRefills: 2, // 熔断阈值
}

function estimateTokens(text) {
  // 真实版 manual.ts:102-112 按字符/除数估算，且把 toolCall 入参计入（旧估算漏算是事故）
  return Math.ceil([...text].length / 4)
}

/** 消息数组的 token 总量 */
function measure(messages) {
  return messages.reduce((sum, m) => sum + estimateTokens(m.text), 0)
}

/** auto compact 的决策：必带 reason（policy.ts:90-160 的 mini 版）。cfg 可注入小窗口便于教学。 */
function shouldAutoCompact(usedTokens, cfg = CONFIG) {
  const outputReserve = Math.min(cfg.maxOutputTokens, cfg.outputReserve)
  const byPercent = usedTokens > cfg.contextWindow * 0.92          // thresholdPercent 路
  const byBuffer = usedTokens > cfg.contextWindow - cfg.buffer - outputReserve // buffer 路
  if (byBuffer) return { should: true, reason: 'buffer_exhausted' }
  if (byPercent) return { should: true, reason: 'threshold_percent' }
  return { should: false, reason: 'within_budget' }
}

// ---------------------------------------------------------------
// 第 2 部分：microcompact —— 只换旧 tool result（microcompact.ts 的 mini 版）
// ---------------------------------------------------------------
const CLEARED = '[Old tool result content cleared]'

function microcompact(messages, keepRecent = CONFIG.keepRecentToolResults) {
  // 找出所有 tool result 的下标（mini 版：role==='tool_result'）
  const resultIdx = messages.map((m, i) => (m.role === 'tool_result' ? i : -1)).filter((i) => i >= 0)
  const candidates = resultIdx.slice(0, Math.max(0, resultIdx.length - keepRecent)) // 最近 N 个永不碰
  const before = measure(messages)
  const out = messages.map((m, i) =>
    candidates.includes(i) ? { ...m, text: CLEARED, __cleared: true } : m,
  )
  const savings = before - measure(out)
  // 纪律 3：收益太低就不压 —— 避免"为了 100 tok 制造一条压缩边界事件"
  if (savings < CONFIG.minTokenSavings) return { messages, savings: 0, cleared: 0, skipped: 'below_min_savings' }
  assert(out.length === messages.length, '消息条数必须恒定') // 纪律 1
  const clearedCount = out.filter((m) => m.__cleared).length
  // 纪律 2 由 keepRecent 切片保证；这里再验一次配对：tool_use 与 tool_result 数量不变
  assert(out.filter((m) => m.role === 'tool_result').length === messages.filter((m) => m.role === 'tool_result').length,
    'tool_result 条数必须恒定（只换文本不删条目）')
  return { messages: out, savings, cleared: clearedCount }
}

// ---------------------------------------------------------------
// 第 3 部分：auto compact —— 九段摘要（prompt.ts 的 mini 版）
// ---------------------------------------------------------------
const SUMMARY_SECTIONS = [ // 九段结构（prompt.ts:33-44）：稳定契约，下游按编号解析
  'Primary Request', 'Key Concepts', 'Files & Code', 'Errors & Fixes', 'Problem Solving',
  'All User Messages', 'Pending', 'Current Work', 'Optional Next Step',
]

function autoCompact(messages, dropBefore) {
  const oldPart = messages.slice(0, dropBefore)
  const recentPart = messages.slice(dropBefore)
  // 真实版发一次"禁用工具的纯文本摘要请求"（MAX_OUTPUT_TOKENS_FOR_SUMMARY=20_000）。
  // mini 版直接折叠：注意最后一段"安全相关指令逐字保留"——这是显式设计约束。
  const securityLines = oldPart
    .filter((m) => m.role === 'user' && /绝不|never|禁止|must not/i.test(m.text))
    .map((m) => `[verbatim] ${m.text}`)     // ← 逐字保留，不概括、不改写
  const summary = {
    role: 'summary',
    sections: SUMMARY_SECTIONS,
    text: `[摘要] 早期 ${oldPart.length} 条消息折叠；安全指令：\n${securityLines.join('\n')}`,
  }
  assert(recentPart.length >= 1, '至少保留最近 1 组对话（compact-selection.ts 的底线）')
  return [...oldPart.filter(() => false), summary, ...recentPart] // 老消息整体折叠，只留摘要+近期
}

// ---------------------------------------------------------------
// 第 4 部分：rapid-refill 断路器（turn-loop-state.ts:154-178 + turn-loop.ts:103-121 的 mini 版）
// ---------------------------------------------------------------
const RAPID_REFILL_TOOL_TURN_THRESHOLD = 3   // turn-loop-state.ts:21
const MAX_CONSECUTIVE_RAPID_REFILLS = 3      // :22

/**
 * 每个 provider-turn 圈首调用（真实签名只收 tracking，不看 token —— token 判定在
 * autoCompactIfNeeded 内部做）。"rapid refill"= 压缩后不满 3 个工具轮又要压：
 *   consecutiveRapidRefills 递增；连续 3 次 → shouldBlock，熔断。
 * 中间跑了 >= 3 个健康的工具轮，计数归零 —— 正常长任务永不被误伤。
 */
function evaluateRapidRefill(tracking) {
  const toolTurnsSinceCompact = tracking?.toolTurnsSinceCompact ?? 0
  const consecutiveRapidRefills =
    tracking && toolTurnsSinceCompact < RAPID_REFILL_TOOL_TURN_THRESHOLD
      ? tracking.consecutiveRapidRefills + 1
      : 0
  return {
    consecutiveRapidRefills,
    shouldBlock: consecutiveRapidRefills >= MAX_CONSECUTIVE_RAPID_REFILLS,
    toolTurnsSinceCompact,
  }
}

function recordCompactSuccess(tracking, decision) {
  return { consecutiveRapidRefills: decision.consecutiveRapidRefills, toolTurnsSinceCompact: 0 }
}
function recordCompletedToolBatch(tracking) {
  return tracking ? { ...tracking, toolTurnsSinceCompact: tracking.toolTurnsSinceCompact + 1 } : tracking
}

class CompactRapidRefillError extends Error {
  constructor(consecutive) {
    super(`rapid_refill_blocked: 连续 ${consecutive} 次压完立刻又要压 —— 这轮信息量本身超窗，交还用户`)
    this.code = 'rapid_refill_blocked'
  }
}

/** 一个 provider-turn 圈：先熔断判定，需要就压，否则跑一轮工具批 */
function loopIteration({ messages, tracking, cfg, label }) {
  const rapidRefill = evaluateRapidRefill(tracking)
  const decision = shouldAutoCompact(measure(messages), cfg)
  if (decision.should && rapidRefill.shouldBlock) throw new CompactRapidRefillError(rapidRefill.consecutiveRapidRefills)
  if (decision.should) {
    const mc = microcompact(messages, 2)
    const out = autoCompact(mc.messages, Math.max(1, Math.floor(mc.messages.length / 2)))
    console.log(`  ${label} → 压缩（reason=${decision.reason}）${measure(messages)} → ${measure(out)} tok，tracking=${JSON.stringify(rapidRefill)}`)
    return { messages: out, tracking: recordCompactSuccess(tracking, rapidRefill), compacted: true }
  }
  tracking = recordCompletedToolBatch(tracking)
  console.log(`  ${label} → 预算内（${measure(messages)} tok），跑工具批，toolTurnsSinceCompact=${tracking?.toolTurnsSinceCompact ?? 0}`)
  return { messages, tracking, compacted: false }
}

// ---------------------------------------------------------------
// 第 5 部分：main() —— 四个场景
// ---------------------------------------------------------------
function fillMessages() {
  return [
    { role: 'user', text: '读一下这个 4000 token 的配置文件' },
    { role: 'tool_result', text: 'x'.repeat(4000 * 4) },
    { role: 'user', text: '跑一下测试' },
    { role: 'tool_result', text: 'y'.repeat(2000 * 4) },
    { role: 'assistant', text: '测试通过。' },
    { role: 'tool_result', text: 'z'.repeat(1500 * 4) },
    { role: 'tool_result', text: 'w'.repeat(900 * 4) },
    { role: 'user', text: '绝不 push 到 main 分支，只允许开 PR。' },
    { role: 'tool_result', text: 'v'.repeat(600 * 4) },
  ]
}

async function main() {
  banner('场景 1：microcompact —— 三条纪律')
  const msgs = fillMessages()
  console.log(`  压前 token=${measure(msgs)}，消息=${msgs.length} 条`)
  const r = microcompact(msgs, 2)
  console.log(`  压后 token=${measure(r.messages)}，消息=${r.messages.length} 条（条数恒定✓），清了 ${r.cleared} 个旧结果`)
  const recent = r.messages.filter((m) => m.role === 'tool_result').slice(-2)
  console.log(`  最近 2 个结果原文保留: ${recent.every((m) => !m.__cleared)}`)
  // 收益太低 → 直接不压
  const tiny = [{ role: 'tool_result', text: 'abc' }]
  const r2 = microcompact(tiny, 0)
  console.log(`  收益 ${r2.savings} < minTokenSavings → skipped=${r2.skipped}`)

  banner('场景 2：auto compact —— 九段摘要 + 安全指令 verbatim')
  const big = [...fillMessages(), { role: 'user', text: '绝不 push 到 main 分支，只允许开 PR。' }]
  // 教学用小窗口（真实 200k）：500 tok 窗口、50 buffer，让 demo 真的越线
  const tinyCfg = { ...CONFIG, contextWindow: 500, outputReserve: 100, buffer: 50 }
  const decision = shouldAutoCompact(measure(big), tinyCfg)
  console.log(`  决策: ${decision.should}（reason=${decision.reason}，小窗口 ${tinyCfg.contextWindow} tok，用量 ${measure(big)} tok）`)
  const compacted = autoCompact(big, 9) // 老消息含安全指令，一起折叠
  const summaryText = compacted.find((m) => m.role === 'summary').text
  console.log(`  压后 token=${measure(compacted)}（原 ${measure(big)}），保留 ${compacted.length} 条`)
  console.log(`  摘要九段: ${SUMMARY_SECTIONS.length} 段固定契约`)
  assert(summaryText.includes('绝不 push 到 main 分支，只允许开 PR。'), '安全指令必须 verbatim 保留')
  console.log('  安全指令在摘要中原样保留 ✓（改写=给模型新的解释权）')

  banner('场景 3：reactive + 恢复 —— 压缩后跑了健康工具轮，计数归零')
  const loopCfg = { ...CONFIG, contextWindow: 40_000, outputReserve: 100, buffer: 50 }
  let tracking = undefined
  let msgs3 = [...fillMessages(), { role: 'tool_result', text: 'q'.repeat(30_000 * 4) }]
  // 圈 1：超窗 → 压缩（reactive 的入口就是"确实需要压缩"这一刻）
  let r3 = loopIteration({ messages: msgs3, tracking, cfg: loopCfg, label: '圈1' })
  tracking = r3.tracking
  // 圈 2-4：预算内跑工具批 → toolTurnsSinceCompact 涨到 3 → 下次 refill 计数归零
  msgs3 = r3.messages
  for (let i = 2; i <= 4; i++) {
    r3 = loopIteration({ messages: msgs3, tracking, cfg: loopCfg, label: `圈${i}` })
    tracking = r3.tracking
  }
  console.log(`  → 连续 refill 计数 ${evaluateRapidRefill(tracking).consecutiveRapidRefills}（健康任务不被熔断误伤）`)

  banner('场景 4：rapid-refill 熔断 —— 压完不到 3 个工具轮又要压，连续 3 次')
  try {
    let msgs4 = [...fillMessages(), { role: 'tool_result', text: 'q'.repeat(30_000 * 4) }]
    let t4 = undefined
    // 圈 1、圈 2：每圈都因为"模型又拉回一个巨型工具结果"而需要再压
    for (let i = 1; i <= 3; i++) {
      const r = loopIteration({ messages: msgs4, tracking: t4, cfg: loopCfg, label: `圈${i}` })
      t4 = r.tracking
      if (r.compacted) msgs4 = [...r.messages, { role: 'tool_result', text: 'q'.repeat(30_000 * 4) }]
    }
    // 圈 4：连续第 3 次 rapid refill → 熔断抛错
    const r = loopIteration({ messages: msgs4, tracking: t4, cfg: loopCfg, label: '圈4' })
    void r
  } catch (e) {
    console.log(`  ✋ ${e.message}`)
    console.log('  → 循环终止而不是无限压缩：压缩预算失控时把决定权交还用户')
  }

  console.log('\n结论：三层各管一段强度，决策都带 reason；摘要保护安全指令；熔断防止压缩死循环。')
}

main().catch((e) => {
  if (e.code === 'rapid_refill_blocked') { console.log(`  ✋ ${e.message}`); return }
  console.error(e); process.exit(1)
})
