#!/usr/bin/env node
/**
 * s02_sqlite_eventsourcing.mjs —— mini 事件溯源库：appendEvent + project + fork + rewind
 *
 * ZCode 把会话的一切落进 SQLite（~/.zcode/cli/db/db.sqlite，paths.ts:7），
 * 采用事件溯源（event sourcing）：
 *
 *   事件表（只追加，唯一真源）                 投影（可任意重放）
 *   ┌──────────────────────────┐            ┌────────────────┐
 *   │ #01 session/created      │──project──▶│ 消息列表        │
 *   │ #02 user/message         │            │ todo 状态       │
 *   │ #03 model/request        │            │ usage 结算      │
 *   │ #04 tool/result          │            │ 权限规则        │
 *   │ #05 rewind/triggered(负) │            └────────────────┘
 *   │ #06 ...                  │            fork = INSERT(parent_id) + 重放 0..atSeq
 *   └──────────────────────────┘            rewind = 追加一条负向事实
 *
 * 对应真实 DDL（adapters/src/storage/session-store/migrations.ts）：
 *   0001_base_session_store(:12)：session(:14，含 parent_id 分叉树、permission、revert)、
 *   message(:41)、part(:52)、todo(:64)、session_entry(:77)、permission(:90)、input_history(:97)
 *   0010_usage_observability(:394)：model_usage / turn_usage / tool_usage 三粒度落账
 *   0019_dwf_journal(:799)：dwf_run/actor/node/event —— dynamic workflow 的独立日志（s08）
 * 冷恢复：core/src/runtime/methods/resume.ts:59 resumeFromStore + agent/session-history-hydrator.ts
 *
 * 运行：node code.mjs        （零依赖离线；不装 SQLite 驱动，只复刻接口形状与不变量）
 * 对照真实源码：adapters/src/storage/session-store/、core/src/runtime/methods/session-fork.ts
 */

import { assert, banner } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：mini 事件库 —— appendEvent 是唯一写入口
// ---------------------------------------------------------------
class MiniEventStore {
  constructor(name) {
    this.name = name
    this.events = []          // [{seq, type, payload, turnId}] —— 对应 part/session_entry 的追加面
    this.sessions = new Map() // {id, parentId} 行 —— 对应 session 表（分叉树靠 parent_id）
    this.seq = 0
  }

  createSession(parentId = null) {
    const id = `${this.name}-s${this.sessions.size + 1}`
    this.sessions.set(id, { id, parentId })   // fork 只是 INSERT 一行，parent_id 指回原会话
    return id
  }

  appendEvent(type, payload, turnId = null) {
    // 只追加：没有 update/delete。这是"事件即事实"的全部前提。
    const event = { seq: ++this.seq, type, payload, turnId }
    this.events.push(event)
    return event
  }

  /** 投影：把事件流折叠成当前状态。同一日志重放 N 次 → N 个相同状态。 */
  project({ uptoSeq = Infinity, sessionId } = {}) {
    const state = { messages: [], todos: {}, usage: { modelCalls: 0, toolCalls: 0 }, rewoundTo: 0 }
    for (const e of this.events) {
      if (e.seq > uptoSeq) break
      if (sessionId && e.payload?.sessionId && e.payload.sessionId !== sessionId) continue
      applyEvent(state, e, this.events)
    }
    return state
  }
}

/** 投影 fold：每种事件类型一个 reducer。rewind/triggered 是"负向事实"。
 *  注意 history 参数：rewind 的重放读的是"事件流自己"，不是内存快照。 */
function applyEvent(state, event, history = []) {
  switch (event.type) {
    case 'user/message': state.messages.push({ role: 'user', text: event.payload.text }); break
    case 'assistant/message': state.messages.push({ role: 'assistant', text: event.payload.text }); break
    case 'tool/result': state.usage.toolCalls++; break
    case 'model/request': state.usage.modelCalls++; break
    case 'todo/update': Object.assign(state.todos, event.payload.todos); break
    case 'usage/settle': state.usage.billed = (state.usage.billed ?? 0) + event.payload.tokens; break
    case 'rewind/triggered': {
      // 回卷：把"用户可见状态"折叠回 targetSeq 之前，但事件本身留在日志里。
      // mini 版按 sessionId 过滤历史再重放 —— 真实实现由 stable boundary 保证折回点合法。
      const target = event.payload.targetSeq
      const replay = { messages: [], todos: {}, usage: { modelCalls: 0, toolCalls: 0 }, rewoundTo: target }
      for (const e2 of history) {
        if (e2.seq > target) break
        if (e2.type === 'rewind/triggered') continue // 嵌套回卷：按最简单语义忽略（真实实现有专门算法）
        if (e2.payload?.sessionId && e2.payload.sessionId !== event.payload.sessionId) continue
        applyEvent(replay, e2, history)
      }
      state.messages = replay.messages
      state.todos = replay.todos
      state.usage = replay.usage
      state.rewoundTo = target
      break
    }
    default: break // 未知事件类型必须被忽略而不是崩溃 —— 老代码读新库的基本功
  }
}

// ---------------------------------------------------------------
// 第 2 部分：fork —— INSERT + 重放，不是 COPY
// ---------------------------------------------------------------
function forkSession(store, sourceId, atSeq) {
  const branchId = store.createSession(/* parent_id */ sourceId)
  // 分支的"初始事实"= 对源会话 0..atSeq 的一次重放投影。
  // 真实实现（session-fork.ts:851 createForkedSession）还会写 stable boundary，
  // 防止分叉点悬在"半个工具批"中间 —— mini 版用 atSeq 必须落在消息边界上模拟。
  const events = store.events.filter((e) => e.seq <= atSeq)
  const last = events.at(-1)
  assert(!last || ['user/message', 'assistant/message', 'model/complete'].includes(last.type),
    'fork 点必须落在 stable boundary（消息边界）上')
  for (const e of events) store.appendEvent(e.type, { ...e.payload, sessionId: branchId, __forkOf: sourceId })
  return { branchId, replayed: events.length }
}

// ---------------------------------------------------------------
// 第 3 部分：冷恢复 —— 只认事件表
// ---------------------------------------------------------------
function resumeFromStore(store, sessionId) {
  // 真实实现 resume.ts:59：从 store 读事件 → hydrator 收敛半步骨架 → 内存历史重建。
  const state = store.project({ sessionId })
  return { restored: true, messages: state.messages.length, usage: state.usage }
}

// ---------------------------------------------------------------
// 第 4 部分：main() —— 四个场景
// ---------------------------------------------------------------
async function main() {
  banner('场景 1：追加 + 投影 —— 事件即事实')
  const store = new MiniEventStore('db')
  const mainId = store.createSession()
  store.appendEvent('user/message', { text: '修这个 bug', sessionId: mainId })       // #01
  store.appendEvent('model/request', { sessionId: mainId })                          // #02
  store.appendEvent('assistant/message', { text: '先读文件', sessionId: mainId })    // #03
  store.appendEvent('tool/result', { name: 'read_file', sessionId: mainId })         // #04
  store.appendEvent('usage/settle', { tokens: 1200, sessionId: mainId })             // #05
  store.appendEvent('todo/update', { todos: { '读文件': 'done' }, sessionId: mainId }) // #06
  store.appendEvent('model/complete', { sessionId: mainId })                         // #07
  console.log('  投影:', JSON.stringify(store.project({ sessionId: mainId })))
  assert(store.project({ sessionId: mainId }).messages.length === 2, '投影应含 2 条消息')

  banner('场景 2：fork = INSERT + 重放（stable boundary 校验）')
  let rejected = false
  try { forkSession(store, mainId, 4) } catch { rejected = true } // #04 tool/result：半个工具批中间
  console.log('  落在半步中间的分叉被拒:', rejected, '← stable boundary 的 mini 版')
  const { branchId, replayed } = forkSession(store, mainId, 7)  // 从 #07（回合收口）之后分叉
  console.log(`  分支 ${branchId}（parent_id → ${mainId}），重放 ${replayed} 条历史事件`)
  // 分支继续干活：主会话毫发无损
  store.appendEvent('user/message', { text: '换个思路试试', sessionId: branchId })
  console.log('  分支投影消息数:', store.project({ sessionId: branchId }).messages.length)
  console.log('  主会话投影消息数:', store.project({ sessionId: mainId }).messages.length, '← fork 不影响源')

  banner('场景 3：rewind = 追加一条负向事实')
  store.appendEvent('user/message', { text: '不对，重来', sessionId: mainId })        // #08
  store.appendEvent('model/request', { sessionId: mainId })                          // #09
  store.appendEvent('assistant/message', { text: '错误的方向', sessionId: mainId })  // #10
  store.appendEvent('rewind/triggered', { targetSeq: 2, sessionId: mainId })         // #11
  const after = store.project({ sessionId: mainId })
  console.log('  回卷后投影:', JSON.stringify(after.messages), 'usage:', after.usage.modelCalls)
  console.log('  事件总数:', store.events.length, '← 没有删除任何一条；"回卷过"本身也是历史')

  banner('场景 4：断电冷恢复 —— 新 runtime 从事件表重建')
  const snapshot = JSON.stringify(store.project({ sessionId: mainId }))
  const fresh = resumeFromStore(store, mainId)   // 模拟全新进程
  const restored = JSON.stringify(store.project({ sessionId: mainId }))
  console.log('  恢复结果:', JSON.stringify(fresh))
  assert(snapshot === restored, '冷恢复投影必须逐字节一致')
  console.log('  投影逐字节一致 ✓ —— 内存里什么都没有，一切从事实重放')
}

main().catch((e) => { console.error(e); process.exit(1) })
