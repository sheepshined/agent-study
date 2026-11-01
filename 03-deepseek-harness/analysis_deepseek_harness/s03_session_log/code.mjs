#!/usr/bin/env node
/**
 * s03_session_log.mjs —— 仅追加的会话日志：真源（source of truth）
 *
 * dsh 的会话（packages/core/session）只有一条铁律：**日志只追加，永不改写**。
 * 修正 = 追加一条新事件（feedback/message-delete / feedback/message-put），
 * 投影负责"按时间折叠出当前状态"。这带来三个性质：
 *
 *   1. 可重放 —— 任何时刻从 JSONL 重放全部事件，重建出完全一致的状态
 *   2. 可审计 —— 发生过什么 = 日志里有什么，没有隐藏的内存态
 *   3. 可兼容 —— 读到"不认识的事件类型"时：
 *      · 没有 ignorable 标记 → 拒绝读（静默跳过会重建出错误的会话）
 *      · 带 ignorable 标记 → 可跳过（上游留下的前向兼容口）
 *
 *   事件流（JSONL，一行一条）                投影（fold）
 *   ┌───────────────────────────┐          ┌──────────────┐
 *   │ #01 user/message          │ ───────▶ │ 消息列表      │
 *   │ #02 assistant/message     │ ───────▶ │ inbox 队列   │
 *   │ #03 feedback/message-put  │ ───────▶ │ 工具状态 …    │
 *   └───────────────────────────┘          └──────────────┘
 *        只追加（append-only）                 无状态函数：events → state
 *
 * 运行：node code.mjs   （真实读写本课目录下 tmp/session.jsonl）
 * 对照真实源码：packages/core/session/src/types.ts、known-event-types.ts、
 *              repair.ts、packages/session/session-persistence-jsonl/
 */

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const LOG_PATH = path.join(HERE, 'tmp', 'session.jsonl')

// ---------------------------------------------------------------
// 第 1 部分：仅追加日志 + JSONL 落盘
// ---------------------------------------------------------------
class AppendOnlyLog {
  constructor() { this.events = []; this.seq = 0 }

  /** 唯一入口：append。seq 必须连续 —— 中间出现空洞说明日志被截断/损坏 */
  append(type, payload, extra = {}) {
    const event = { seq: ++this.seq, type, payload, ts: Date.now(), ...extra }
    this.events.push(event)
    return event
  }

  /** 落盘：一行一个 JSON（JSONL）。dsh 的 session-persistence-jsonl 同构 */
  save(file) {
    fs.mkdirSync(path.dirname(file), { recursive: true })
    fs.writeFileSync(file, this.events.map((e) => JSON.stringify(e)).join('\n') + '\n')
  }

  /** 读盘：逐行解析 + 逐条校验（顺序、seq 连续性、未知类型闸门） */
  static load(file, { knownTypes }) {
    const log = new AppendOnlyLog()
    const lines = fs.readFileSync(file, 'utf8').split('\n').filter(Boolean)
    for (const line of lines) {
      const e = JSON.parse(line)
      // 校验 1：seq 必须连续（dsh：repair.ts 的管辖范围）
      if (e.seq !== log.seq + 1) throw new Error(`日志损坏：seq 出现空洞（期望 ${log.seq + 1}，实际 ${e.seq}）`)
      // 校验 2：未知事件类型的兼容闸门（dsh：known-event-types.ts 的核心逻辑）
      if (!knownTypes.has(e.type) && !e.ignorable) {
        throw new Error(
          `拒绝读取：未知事件类型 "${e.type}" 且无 ignorable 标记。\n` +
          '  这份日志可能出自更新的 harness —— 静默跳过会重建出错误的会话，\n' +
          '  所以宁可拒绝读（dsh known-event-types.ts 头部注释的原话）。',
        )
      }
      log.events.push(e); log.seq = e.seq
    }
    return log
  }
}

/** 本课理解的"事件词汇表"——对应 dsh 的 KNOWN_SESSION_EVENT_TYPES（生成物，勿手改） */
const KNOWN_TYPES = new Set([
  'user/message', 'assistant/message', 'tool/call', 'tool/result',
  'feedback/message-delete', 'feedback/message-put', 'experimental/boom',
])

// ---------------------------------------------------------------
// 第 2 部分：投影 —— 无状态的 fold：events → 当前状态
// ---------------------------------------------------------------
/**
 * 投影（projection）= 从事件流折叠状态的纯函数。
 * dsh 里 inbox、消息列表、系统提示词快照全部是投影（s02 的 deriveRequest
 * 就是最简投影）。关键性质：**同一日志重放 N 次，得到 N 个相同状态**。
 */
function projectMessages(events) {
  const messages = [] // id -> 消息（按追加序）
  for (const e of events) {
    if (e.type === 'user/message') messages.push({ id: `m${e.seq}`, role: 'user', text: e.payload.text })
    else if (e.type === 'assistant/message') messages.push({ id: `m${e.seq}`, role: 'assistant', text: e.payload.text })
    else if (e.type === 'feedback/message-delete') {
      // 修正也是事件：删除 = 投影里标记消失，日志原文不动
      const m = messages.find((m) => m.id === e.payload.id)
      if (m) m.deleted = true
    } else if (e.type === 'feedback/message-put') {
      const m = messages.find((m) => m.id === e.payload.id)
      if (m) { m.text = e.payload.text; m.deleted = false } // put = 改写/复活（顺序敏感）
    }
  }
  return messages.filter((m) => !m.deleted)
}

// ---------------------------------------------------------------
// 第 3 部分：演示 —— 写入 → 崩溃 → 重放重建 → 前向兼容闸门
// ---------------------------------------------------------------
async function main() {
  console.log('== 1. 正常对话 + 一次"编辑历史"（追加修正事件，不改写日志） ==')
  {
    const log = new AppendOnlyLog()
    log.append('user/message', { text: '帮我总结这份文档' })
    log.append('assistant/message', { text: '文档的主旨是……（第一版，有点跑偏）' })
    // 用户不满意，编辑了 AI 的回复 —— dsh 的做法：追加 feedback 事件，日志原文保留
    log.append('feedback/message-delete', { id: 'm2' })
    log.append('feedback/message-put', { id: 'm2', text: '文档的主旨是：压缩上下文、外置记忆。' })
    log.save(LOG_PATH)
    console.log(`已写入 ${log.events.length} 条事件 → ${path.relative(process.cwd(), LOG_PATH)}`)
    console.log('投影出的当前消息:')
    for (const m of projectMessages(log.events)) console.log(`  [${m.role}] ${m.text}`)
    const raw = fs.readFileSync(LOG_PATH, 'utf8').trim().split('\n')
    console.log(`注意：日志里仍保留 4 条原文（含被"删掉"的旧回复）—— 只追加，永不改写`)
    console.log(`日志行数 = ${raw.length}，投影后消息数 = ${projectMessages(log.events).length}`)
  }

  console.log('\n== 2. 模拟崩溃：内存全丢，从 JSONL 重放重建 ==')
  {
    const log = AppendOnlyLog.load(LOG_PATH, { knownTypes: KNOWN_TYPES })
    const rebuilt = projectMessages(log.events)
    console.log(`重放 ${log.events.length} 条事件，重建出:`)
    for (const m of rebuilt) console.log(`  [${m.role}] ${m.text}`)
    console.log('→ 与崩溃前一致。s02 的"请求从日志推导"靠的就是这个可重放性')
  }

  console.log('\n== 3. 前向兼容闸门：新版 harness 留下旧版不认识的事件 ==')
  {
    // 场景 A：新版事件没带 ignorable —— 旧版拒绝读，而不是静默跳过后给出错误会话
    const logA = new AppendOnlyLog()
    logA.append('user/message', { text: 'hi' })
    logA.append('experimental/boom', { note: '新版才懂的事件' })
    logA.save(LOG_PATH.replace('session.jsonl', 'session-future.jsonl'))
    try {
      AppendOnlyLog.load(LOG_PATH.replace('session.jsonl', 'session-future.jsonl'), { knownTypes: KNOWN_TYPES })
    } catch (e) { console.log('场景 A（无标记）→ 拒绝读:', e.message.split('\n')[0]) }

    // 场景 B：带 ignorable 标记 —— 可安全跳过（上游明确的兼容口）
    const logB = new AppendOnlyLog()
    logB.append('user/message', { text: 'hi' })
    logB.append('experimental/boom', { note: '新版才懂的事件' }, { ignorable: true })
    logB.save(LOG_PATH.replace('session.jsonl', 'session-future.jsonl'))
    const ok = AppendOnlyLog.load(LOG_PATH.replace('session.jsonl', 'session-future.jsonl'), { knownTypes: KNOWN_TYPES })
    console.log(`场景 B（带 ignorable）→ 跳过不认识的事件，其余 ${ok.events.length} 条照常重建`)
  }

  console.log('\n== 4. seq 空洞 = 日志损坏，读路径当场拒绝（dsh repair.ts 的管辖范围） ==')
  {
    const bad = [
      JSON.stringify({ seq: 1, type: 'user/message', payload: { text: 'a' }, ts: 0 }),
      JSON.stringify({ seq: 3, type: 'assistant/message', payload: { text: 'b' }, ts: 0 }), // 2 号丢了
    ]
    const p = LOG_PATH.replace('session.jsonl', 'session-broken.jsonl')
    fs.writeFileSync(p, bad.join('\n') + '\n')
    try { AppendOnlyLog.load(p, { knownTypes: KNOWN_TYPES }) }
    catch (e) { console.log('拒绝读:', e.message) }
  }
  fs.rmSync(path.join(HERE, 'tmp'), { recursive: true, force: true }) // 演示完清理
  console.log('\n（演示产生的 tmp/ 已清理）')
}

main().catch((e) => { console.error(e); process.exit(1) })
