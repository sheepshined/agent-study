#!/usr/bin/env node
/**
 * s07_memory_compaction.mjs —— 记忆与压缩：注入顺序、分层记忆、唯一改写历史的机制
 *
 * OpenClaw 的记忆哲学（docs/concepts/memory-architecture.md:23-46，五原则）：
 *   ① 无隐藏状态（模型只记得 workspace 文件里写的东西）
 *   ② 难点在写入而非检索（curation 移出回复热路径，交给后台 pass）
 *   ③ 写路径就是安全边界（内容级扫描挡不住投毒 → 写入处强制 provenance）
 *   ④ 确定性门槛，模型判断只在门槛内
 *   ⑤ 记忆故障永不阻塞回复（每步都有超时或回退）
 *
 * 两条与"上下文"相关的机制：
 *
 *   A. bootstrap 注入（引导注入，workspace-bootstrap-policy.ts:19-48 的 mini 版）
 *      注入顺序 = 行为：AGENTS → SOUL → IDENTITY → USER → BOOTSTRAP → MEMORY。
 *      TOOLS.md 有常量但不在注入集——"内核认得这个名字"≠"会被读进 prompt"。
 *      预算（bootstrap-budget.ts:46-49）：单文件 20000、总 60000、
 *      USER.md 固定 4000（Math.min——调大全局也放不开 USER.md）。
 *      缺失文件注入 "missing file" 标记后继续；群聊不加载 MEMORY.md。
 *
 *   B. compaction（上下文压缩，docs/concepts/compaction.md）
 *      窗口溢出 → 压缩 → 重试。它是**唯一被允许改写历史的机制**（根
 *      AGENTS.md："Stable conversation context"）；新配置默认 mode:"safeguard"
 *      （带摘要质量审计）；保留 tool_call ⇄ toolResult 配对；被省略的图片
 *      插固定标记，每次请求最多 847 UTF-8 字节（刻意固定大小防估算漂移）；
 *      CJK 字符计入估算。
 *
 *   workspace 文件 ─→ 注入（顺序+预算）─→ prompt 前缀（要稳定，别重建）
 *   长会话溢出 ─→ compaction（保配对/固定标记预算）─→ 重试成功
 *
 * 运行：node code.mjs    （零依赖，离线；"记忆后台/摘要器"由 Mock 扮演）
 * 对照真实源码：src/agents/workspace-bootstrap-policy.ts、src/agents/bootstrap-budget.ts、
 *   src/memory/root-memory-files.ts:7-9、
 *   src/agents/embedded-agent-runner/compact*.ts + compaction-*.ts（约 30 文件）、
 *   docs/concepts/memory-architecture.md、docs/concepts/compaction.md
 */

import { assert } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：注入文件唯一真源（workspace-bootstrap-policy.ts 的 mini 版）
// ---------------------------------------------------------------
// 注释直接点明设计意图：这组名字是"runtime 校验集、名字 union 与 UI 核心文件
// 列表的唯一来源；别处再抄一份私有列表，会在文件退役时静默漂移。"

const DEFAULT_AGENTS_FILENAME = 'AGENTS.md'
const DEFAULT_SOUL_FILENAME = 'SOUL.md'
const DEFAULT_TOOLS_FILENAME = 'TOOLS.md'      // 有常量，但——
const DEFAULT_IDENTITY_FILENAME = 'IDENTITY.md'
const DEFAULT_USER_FILENAME = 'USER.md'
const DEFAULT_BOOTSTRAP_FILENAME = 'BOOTSTRAP.md'
const DEFAULT_MEMORY_FILENAME = 'MEMORY.md'    // 名字 owner 在 memory 模块（root-memory-files.ts:7）

// 数组顺序 = prompt 注入顺序，属行为不是排版（:41-48）
const WORKSPACE_BOOTSTRAP_FILENAMES = [
  DEFAULT_AGENTS_FILENAME, DEFAULT_SOUL_FILENAME, DEFAULT_IDENTITY_FILENAME,
  DEFAULT_USER_FILENAME, DEFAULT_BOOTSTRAP_FILENAME, DEFAULT_MEMORY_FILENAME,
]
// 注意 DEFAULT_TOOLS_FILENAME 不在上面这组里。

// ---------------------------------------------------------------
// 第 2 部分：预算（bootstrap-budget.ts:46-49 的 mini 版）
// ---------------------------------------------------------------
const BOOTSTRAP_MAX_CHARS = 20_000
const BOOTSTRAP_TOTAL_MAX_CHARS = 60_000
const USER_BOOTSTRAP_MAX_CHARS = 4_000

function effectiveFileLimit(name, bootstrapMaxChars) {
  return name.toLowerCase() === 'user.md'
    ? Math.min(bootstrapMaxChars, USER_BOOTSTRAP_MAX_CHARS) // 调大全局值也放不开 USER.md
    : bootstrapMaxChars
}

/** 组装 bootstrap 上下文：按规范顺序、逐文件预算、总预算；缺失文件打标记后继续。
 *  @param sessionKind 'main-private' | 'group' —— 群聊不加载 MEMORY.md（分层记忆规则） */
function buildBootstrapPrompt(workspaceFiles, { bootstrapMaxChars = BOOTSTRAP_MAX_CHARS, sessionKind = 'main-private' } = {}) {
  const sections = []
  let remainingTotal = BOOTSTRAP_TOTAL_MAX_CHARS
  for (const name of WORKSPACE_BOOTSTRAP_FILENAMES) {
    if (name === DEFAULT_MEMORY_FILENAME && sessionKind === 'group') continue // 群聊不加载长期记忆
    const raw = workspaceFiles[name]
    if (raw === undefined) {
      sections.push(`[${name}: missing file 标记]`) // 缺失继续，不炸
      continue
    }
    const limit = Math.min(effectiveFileLimit(name, bootstrapMaxChars), remainingTotal)
    const body = raw.length > limit ? raw.slice(0, limit) + `…[截断@${limit}]` : raw
    remainingTotal -= body.length
    sections.push(`### ${name}\n${body}`)
  }
  return sections.join('\n\n')
}

// ---------------------------------------------------------------
// 第 3 部分：记忆层 —— 分层 + 故障不阻塞（五原则的落点）
// ---------------------------------------------------------------
class MiniMemoryLayer {
  constructor() { this.daily = new Map(); this.longTerm = '' }

  writeDaily(date, note) { this.daily.set(date, [...(this.daily.get(date) ?? []), note]) }

  /** 检索：带超时与回退——记忆挂了也不能吃掉这个 turn（原则⑤）。 */
  async recall(sessionKind, { timeoutMs = 20, simulateHang = false } = {}) {
    if (sessionKind === 'group') return { items: [], note: '群聊不加载 MEMORY.md（分层规则）' }
    if (simulateHang) {
      const timeout = new Promise((r) => setTimeout(() => r({ items: [], note: '记忆检索超时 → 回退：无记忆继续回复（原则⑤）' }), timeoutMs))
      const hang = new Promise(() => {}) // 永不 resolve，模拟后台卡死
      return Promise.race([hang, timeout])
    }
    return { items: this.longTerm ? [this.longTerm] : [], note: '主私聊加载 MEMORY.md' }
  }
}

// ---------------------------------------------------------------
// 第 4 部分：compaction —— 唯一能改写历史的机制
// ---------------------------------------------------------------
/** 估算 token：CJK 字符计入估算（每字 ~1 tok，ASCII 按 4 字符 1 tok 粗估）。 */
function estimateTokens(text) {
  const cjk = (text.match(/[\u3000-\u9fff\uff00-\uffef]/g) ?? []).length
  return cjk + Math.ceil((text.length - cjk) / 4)
}

/**
 * safeguard 压缩：老轮次折叠成摘要，但——
 *  ① tool_call 与 toolResult 必须同生同灭（拆开 = 重放时悬空调用）；
 *  ② 被省略的图片只插固定标记，全请求标记总量 ≤ 847 UTF-8 字节（刻意固定，
 *     防估算漂移；compaction.md:23）；
 *  ③ 压缩改写的是"发给模型的投影"，transcript 真源不动（s03 的历史 + 围栏）。
 */
function compact(history, { windowBudget = 120, keepRecent = 2, imageMarkersBudget = 847 } = {}) {
  const usableForMarkers = Math.min(imageMarkersBudget, 847)
  let markersBytes = 0
  const marker = () => {
    const m = '[image data omitted from summary input]'
    if (markersBytes + m.length > usableForMarkers) return '[omitted]' // 预算内放不下就换短标记
    markersBytes += m.length
    return m
  }
  // 配对分组：每个 assistant 工具调用与其结果绑成一组，同生同灭。
  const groups = []
  for (let i = 0; i < history.length; i++) {
    const m = history[i]
    if (m.type === 'tool_call') {
      const result = history[i + 1]?.type === 'tool_result' ? history[i + 1] : null
      groups.push({ kind: 'pair', items: result ? [m, result] : [m], idx: i })
      if (result) i++
    } else groups.push({ kind: 'single', items: [m], idx: i })
  }
  const old = groups.slice(0, Math.max(0, groups.length - keepRecent))
  const recent = groups.slice(Math.max(0, groups.length - keepRecent))
  // 摘要器只拿文本：每条截断成片段（真实实现里被省略的图片插固定标记）。
  const clip = (s) => (s.length > 24 ? s.slice(0, 24) + '…' : s)
  const summary = {
    type: 'summary',
    text: `[摘要] 早期 ${old.length} 组消息：` +
      old.map((g) => g.items.map((m) => m.type === 'image' ? marker() : clip(m.text ?? `<${m.type}>`)).join(' → ')).join(' | '),
  }
  const projected = [summary, ...recent.flatMap((g) => g.items)]
  return { projected, summary, markersBytes, before: estimateTokens(history.map((m) => m.text ?? '').join('')), after: estimateTokens(projected.map((m) => m.text ?? '').join('')) }
}

// ---------------------------------------------------------------
// 演示
// ---------------------------------------------------------------
async function main() {
  const log = (...a) => console.log(...a)

  console.log('== 1. bootstrap 注入：顺序即行为；TOOLS.md 不在注入集 ==')
  const ws = {
    'AGENTS.md': '规范：回复要短。',
    'SOUL.md': '人格：毒舌但可靠。',
    'IDENTITY.md': '身份：家里那台老龙虾。',
    'USER.md': '主人：Alice，时区 UTC+8。',
    'BOOTSTRAP.md': '今天先整理收件箱。',
    'MEMORY.md': '长期记忆：Alice 讨厌早上开会。',
    'TOOLS.md': '(存在但不会被注入——不在这组常量里)',
  }
  const prompt = buildBootstrapPrompt(ws)
  const order = prompt.split('\n\n').map((s) => s.split('\n')[0])
  log('注入顺序:', order.join(' → '))
  assert(order.length === 6, '六个文件注入')
  assert(!prompt.includes('TOOLS.md'), 'TOOLS.md 不注入')

  console.log('\n== 2. 预算边界：缺失文件、USER.md 固定帽、总预算 ==')
  const partial = { 'AGENTS.md': 'x'.repeat(500), 'USER.md': 'u'.repeat(30_000) } // 无 SOUL/IDENTITY/BOOTSTRAP/MEMORY
  const p2 = buildBootstrapPrompt(partial)
  log(`缺失 4 个文件 → 打 "missing file" 标记继续（不炸 prompt）`)
  log(`USER.md 写了 30000 字 → 注入 ${p2.split('\n\n').find((s) => s.startsWith('### USER')).length - '### USER.md\n'.length} 字符以内（固定帽 ${USER_BOOTSTRAP_MAX_CHARS}，Math.min 生效）`)
  assert(!buildBootstrapPrompt(partial, { bootstrapMaxChars: 999_999_999 }).includes('u'.repeat(4001)), '全局预算调到天大也放不开 USER.md 固定帽')

  console.log('\n== 3. 分层记忆：群聊不加载 MEMORY.md；记忆挂了不阻塞回复 ==')
  const mem = new MiniMemoryLayer()
  mem.longTerm = '长期记忆：Alice 讨厌早上开会；文件服务器叫"龙虾窝"。'
  mem.writeDaily('2026-10-05', 'Alice 让我把会议纪要归档')
  log(`主私聊 recall → ${JSON.stringify(await mem.recall('main-private'))}`)
  log(`群聊   recall → ${JSON.stringify(await mem.recall('group'))}`)
  log(`失败路径（后台卡死）→ ${JSON.stringify(await mem.recall('main-private', { simulateHang: true }))}`)

  console.log('\n== 4. compaction：溢出 → 压缩（保配对 + 847 字节标记预算）→ 重试 ==')
  const longReport = 'x'.repeat(400) // 很长的 ASCII 工具输出（CJK 之外的字符按 4:1 粗估）
  const history = [
    { type: 'user', text: '帮我看下这份报告' },
    { type: 'assistant', text: '先读附件' },
    { type: 'image', text: '(截图 1 的像素数据)' },
    { type: 'tool_call', name: 'read', text: 'read(report.md)' },
    { type: 'tool_result', text: `……(很长的报告内容 ${longReport})` },
    { type: 'user', text: '总结一下' },
    { type: 'assistant', text: '结论是 A，依据在第 3 节' },
  ]
  const before = estimateTokens(history.map((m) => m.text).join(''))
  log(`压缩前估算 ${before} tok（窗口预算 120）→ ${before > 120 ? '溢出！触发 compaction' : '不触发'}`)
  const { projected, summary, markersBytes, after } = compact(history)
  log(`压缩后 ${after} tok，标记字节消耗 ${markersBytes} B（预算 847，刻意固定防估算漂移）`)
  const danglingCall = projected.some((m) => m.type === 'tool_call' || m.type === 'tool_result')
  const pairFoldedTogether = summary.text.includes('read(report.md)') && summary.text.includes('(很长的报告内容')
  log(`配对原子性: 调用与结果同组折叠=${pairFoldedTogether}，投影里无悬空调用=${!danglingCall}（拆开=重放时悬空）`)
  log('摘要片段:', summary.text)
  assert(after <= 120 && pairFoldedTogether && !danglingCall && markersBytes <= 847, '压缩三不变量')
  log('→ 重试成功。而且压缩改写的只是"下一次请求的投影"——transcript 真源一个字节没动。')
  console.log('\n五原则回顾：无隐藏状态 / 写入是难点 / 写路径即安全边界 / 确定性门槛 / 故障不阻塞回复。')
}

main().catch((e) => { console.error(e); process.exit(1) })
