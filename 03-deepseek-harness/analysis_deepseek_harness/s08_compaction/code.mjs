#!/usr/bin/env node
/**
 * s08_compaction.mjs —— 上下文管理：压缩（compaction）与大输出落盘（spill）
 *
 * 长会话迟早把窗口撑爆。dsh 的解法遵守会话层的铁律（s03）：
 * **日志不动，投影动** —— 压缩不是删历史，而是改变"下一次请求从日志
 * 投影出什么"。全部动作都有事件为证（就在日志里）：
 *
 *   compaction/start → compaction/prune（剪旧工具结果）
 *                    → compaction/summary（老轮次折叠成摘要）
 *                    → compaction/end
 *   spill：超大工具输出写进临时文件，投影里只留"指针 + 元数据"
 *
 *   投影（下一次请求真正发出去的上下文）
 *   ┌─────────────────────────────┐
 *   │ 系统提示词（s04）            │
 *   │ 近 2 轮（原文）              │
 *   │ 更早 → 摘要一条              │ ←── compaction 事件生效的位置
 *   │ 巨型工具输出 → [落盘指针]     │
 *   └─────────────────────────────┘
 *        日志（真源）永远完整 —— 回放/审计/重投影不受影响
 *
 * 运行：node code.mjs   （会真实写 tmp/spill-*.txt，结束清理）
 * 对照真实源码：packages/compaction/{compaction,compaction-basic,
 *              compaction-tool-result-pruner}/、packages/spill/
 */

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const approxTokens = (s) => Math.ceil((s ?? '').length / 4)

// ---------------------------------------------------------------
// 第 1 部分：投影 —— compaction 事件在这里生效
// ---------------------------------------------------------------
/**
 * 投影规则（对比 s03：多了一组"跳过被压缩内容"的规则）：
 *  · payload.summarized === true 的旧消息 → 跳过（内容已折进摘要）
 *  · payload.spilled   === true 的工具结果 → 只显示指针
 *  · payload.pruned    === true 的工具结果 → 跳过
 *  · compaction/summary 事件本身 → 渲染为一条 [摘要]
 */
function projectContext(events) {
  const ctx = []
  const summaries = [] // 摘要代表"更早的内容"，最终排在最近轮次之前
  for (const e of events) {
    if (e.type === 'compaction/summary') { summaries.push(`[摘要] ${e.payload.text}`); continue }
    if (e.type === 'user/message' && !e.payload.summarized) ctx.push(`[user] ${e.payload.text}`)
    else if (e.type === 'assistant/message' && !e.payload.summarized) ctx.push(`[assistant] ${e.payload.text}`)
    else if (e.type === 'tool/result') {
      if (e.payload.pruned) continue
      ctx.push(`[tool] ${e.payload.spilled ? e.payload.pointer : e.payload.result}`)
    }
  }
  return [...summaries, ...ctx]
}
const contextTokens = (ctx) => ctx.reduce((n, line) => n + approxTokens(line), 0)

// ---------------------------------------------------------------
// 第 2 部分：spill —— 巨型工具输出落盘，投影只留指针
// ---------------------------------------------------------------
function spill(toolResult, { limit = 200, dir }) {
  if (toolResult.length <= limit) return { result: toolResult, spilled: false }
  const file = path.join(dir, `spill-${Date.now().toString(36)}.txt`)
  fs.mkdirSync(dir, { recursive: true })
  fs.writeFileSync(file, toolResult) // 原文落盘：审计与"想看全文"的出口
  const lines = toolResult.split('\n').length
  return {
    result: toolResult,   // 日志原文不动（真源！）
    spilled: true,        // 投影据此改显指针
    pointer: `[已落盘 ${path.basename(file)}：共 ${lines} 行 / ${approxTokens(toolResult)} tok，需要时再读]`,
  }
}

// ---------------------------------------------------------------
// 第 3 部分：compaction —— 四阶段，每个阶段都落事件
// ---------------------------------------------------------------
function compact(events, { budget, keepTurns = 2, dir }) {
  const before = contextTokens(projectContext(events))
  events.push({ type: 'compaction/start', payload: { budget, before } })

  // 阶段 0：spill —— 任何超限的工具输出先落盘（无论新老，都占大头）
  let spilled = 0
  for (const e of events) {
    if (e.type === 'tool/result' && !e.payload.spilled && e.payload.result.length > 200) {
      Object.assign(e.payload, spill(e.payload.result, { dir }))
      spilled++
    }
  }

  // 阶段 1：prune —— 近 2 轮之外的工具结果剪出投影（compaction-tool-result-pruner 的思路）
  const maxTurn = Math.max(...events.filter((e) => e.turn).map((e) => e.turn))
  let pruned = 0
  for (const e of events) {
    if (e.type === 'tool/result' && e.turn <= maxTurn - keepTurns && !e.payload.pruned) {
      e.payload.pruned = true // 投影跳过；日志原文不动
      pruned++
    }
  }
  events.push({ type: 'compaction/prune', payload: { spilled, pruned } })

  // 阶段 2：summary —— 更早的消息折叠成一条摘要事件
  const oldMsgs = events.filter((e) => ['user/message', 'assistant/message'].includes(e.type) && e.turn <= maxTurn - keepTurns && !e.payload.summarized)
  if (oldMsgs.length) {
    const digest = oldMsgs
      .map((e) => `${e.type === 'user/message' ? '问' : '答'}:${(e.payload.text ?? '').slice(0, 22)}`)
      .join('；')
    for (const e of oldMsgs) e.payload.summarized = true
    events.push({ type: 'compaction/summary', payload: { text: `早期工作：${digest}。` } })
  }

  const after = contextTokens(projectContext(events))
  events.push({ type: 'compaction/end', payload: { after, withinBudget: after <= budget } })
  return { before, after }
}

// ---------------------------------------------------------------
// 第 4 部分：演示 —— 撑爆 → 落盘 → 剪枝 → 摘要 → 回到预算内
// ---------------------------------------------------------------
function main() {
  const dir = path.join(HERE, 'tmp')
  const events = []
  let turn = 0
  const add = (type, payload) => {
    if (type === 'user/message') turn++
    const e = { type, turn, payload }
    events.push(e)
    return e
  }

  console.log('== 1. 造一个快撑爆的会话（3 轮，巨型工具输出） ==')
  add('user/message', { text: '调研这批依赖的许可证' })
  add('assistant/message', { text: '好的，我先扫描 node_modules 的 LICENSE 文件。' })
  add('tool/result', { result: 'LICENSE 清单：\n' + Array.from({ length: 40 }, (_, i) => `pkg-${i}: MIT`).join('\n') })
  add('user/message', { text: '再看看安全公告' })
  add('assistant/message', { text: '扫描 CVE 列表中。' })
  add('tool/result', { result: 'CVE 报告：\n' + Array.from({ length: 30 }, (_, i) => `CVE-2025-${1000 + i}: 中危`).join('\n') })
  add('user/message', { text: '总结一下整体风险' })
  add('assistant/message', { text: '整体可控：许可证以 MIT 为主，安全公告均为中危。' })

  const budget = 120
  const before = contextTokens(projectContext(events))
  console.log(`  压缩前上下文 ≈ ${before} tok（预算 ${budget}）→ ${before > budget ? '超了，触发 compaction' : '未超'}`)

  console.log('\n== 2. compaction 四阶段（每个动作都落事件） ==')
  const { after } = compact(events, { budget, dir })
  for (const e of events) {
    if (e.type.startsWith('compaction/')) console.log(`  ${e.type.padEnd(20)} ${JSON.stringify(e.payload)}`)
  }

  console.log('\n== 3. 压缩后：投影瘦身，日志原样 ==')
  console.log(`  压缩后上下文 ≈ ${after} tok${after <= budget ? ' ✓ 回到预算内' : ''}；日志事件数仍是 ${events.length} 条（只增不减）`)
  console.log('  下一次请求真正发出去的上下文:')
  for (const line of projectContext(events)) console.log(`    ${line.slice(0, 76)}${line.length > 76 ? '…' : ''}`)

  console.log('\n== 4. 真源未损：巨型输出原文仍可从日志+落盘文件复原 ==')
  const spilled = events.find((e) => e.type === 'tool/result' && e.payload.spilled)
  console.log(`  日志原文前 40 字符: ${JSON.stringify(spilled.payload.result.slice(0, 40))}`)
  console.log(`  落盘文件行数: ${fs.readFileSync(path.join(dir, fs.readdirSync(dir)[0]), 'utf8').split('\n').length - 1}`)

  fs.rmSync(dir, { recursive: true, force: true })
  console.log('\n（演示产生的 tmp/ 已清理）')
}

main()
