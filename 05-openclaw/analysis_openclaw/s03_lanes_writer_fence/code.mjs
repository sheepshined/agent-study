#!/usr/bin/env node
/**
 * s03_lanes_writer_fence.mjs —— 双层 lane 串行化 + 写者围栏
 *
 * "同一会话被连续多条消息轰炸"在 OpenClaw 是一等问题：Telegram 群里三个人
 * 同时 @机器人、cron 与用户同时写同一个会话——而 coding CLI 基本靠
 * "人坐在键盘前一次只发一条"逃避这个问题。OpenClaw 的答案是三件套：
 *
 *   1. 双层 lane（lane = 车道/串行队列）
 *      · 外层会话 lane：`session:<key>`，宽度恒 1 —— 同会话绝对串行；
 *      · 内层全局 lane：`main`/`subagent`/`cron`… 十个命名 lane —— 整机并发上限；
 *      · 两层是嵌套不是二选一：enqueueSession(enqueueGlobal(...))
 *        （run-orchestrator.ts:254/:269）。
 *
 *   2. 队列模式（docs/concepts/queue.md:37-42，同会话已有 active run 时）
 *      steer（默认，转向/中途插话）| followup（排队）| collect（合并一轮）| interrupt（打断）
 *
 *   3. 写者围栏（writer fence，docs/concepts/agent-loop.md:50）
 *      流式开始前登记持久写者声明 activeWriterRunId；每次 transcript 追加带
 *      expectedWriterRunId，在同步 SQLite 提交事务内校验——被取代的 run
 *      提交不进脏数据。这是"历史只有一个真相写者"的全部保证。
 *
 *   消息轰炸                          同步 SQLite 事务
 *   ────────→ session:xxx (宽1) → 全局lane → run#1 声明写者 → 追加✓
 *                run#2 排队          ↑          run#2 声明写者
 *                run#3 排队      main（整机闸）  run#1 迟到写入 → 拒绝✗
 *
 * 运行：node code.mjs    （零依赖，离线；"模型 run"由 Mock 扮演，sleep 模拟耗时）
 * 对照真实源码：src/agents/embedded-agent-runner/lanes.ts:16-33（lane 命名唯一 owner）、
 *   src/process/lanes.ts:12-35（十 lane 拓扑登记表）、
 *   src/agents/embedded-agent-runner/run-orchestrator.ts:254/:269（双层入队）、
 *   src/agents/session-tool-result-guard.ts:641-661（围栏供料点）、
 *   src/agents/embedded-agent-subscribe.ts:57（三条事件流桥接）
 */

import { sleep } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：lane 命名（lanes.ts:16-33 的忠实 mini 移植）
// ---------------------------------------------------------------
// 关键点①：会话 lane 前缀 `session:` 是"同一个会话"的串行化身份证——
// 队列只按字符串相等分组，key 规范化（s02 场景 5）不到位就会并跑。
export function resolveSessionLane(key) {
  const cleaned = (key ?? '').trim() || 'main'
  return cleaned.startsWith('session:') ? cleaned : `session:${cleaned}`
}

// 关键点②：global lane 是"整机同时跑多少 run"的第二道闸；cron 槽位被外层定时
// 任务持有时，内层若再排回 cron 就是等自己 ⇒ 永久自锁，所以改派 cron-nested。
export function resolveGlobalLane(lane) {
  const cleaned = lane?.trim()
  if (cleaned === 'cron') return 'cron-nested' // 防死锁改派（lanes.ts:29-31）
  return cleaned ? cleaned : 'main'
}

// ---------------------------------------------------------------
// 第 2 部分：双层命令队列（command-queue + run-orchestrator 的 mini 版）
// ---------------------------------------------------------------
/** 并发默认值（docs/concepts/queue.md:19）：未配置 lane 为 1；main = max(8, CPU×4)；
 *  subagent = 8。mini 用 CPU=2 固定演示。 */
export const LANE_WIDTH = { main: Math.max(8, 2 * 4), subagent: 8, 'cron-nested': 1 }
const widthOf = (lane) => LANE_WIDTH[lane] ?? 1

class MiniCommandQueue {
  constructor({ globalLane = 'main' } = {}) {
    this.globalLane = globalLane
    this.sessionQueues = new Map() // sessionLane -> Promise 尾巴（宽 1 串行）
    this.globalInFlight = 0        // 全局 lane 在途数
    this.globalWaiters = []
    this.trace = []                // 时序记录：lane 事件时间线
  }
  note(t) { this.trace.push(t) }

  /** 全局闸：占一个整机槽位。宽度来自 LANE_WIDTH。 */
  async enterGlobal() {
    const lane = this.globalLane
    if (this.globalInFlight >= widthOf(lane)) {
      this.note(`全局 lane ${lane} 满（${this.globalInFlight}/${widthOf(lane)}），等待`)
      await new Promise((r) => this.globalWaiters.push(r))
    }
    this.globalInFlight++
    this.note(`进入全局 lane ${lane}（${this.globalInFlight}/${widthOf(lane)}）`)
  }
  exitGlobal() {
    this.globalInFlight--
    this.note(`退出全局 lane（剩 ${this.globalInFlight}）`)
    this.globalWaiters.shift()?.()
  }

  /**
   * 双层入队：外层会话闸（宽 1）内层再过全局闸——顺序与真实实现一致
   * （enqueueSession(enqueueGlobal(...))）。会话闸用"链尾续接"实现串行。
   */
  enqueue(sessionLane, work) {
    const tail = (this.sessionQueues.get(sessionLane) ?? Promise.resolve()).then(work)
    // 链尾吞掉错误避免断链：真实实现里单个 run 失败不能卡死整条会话 lane。
    this.sessionQueues.set(sessionLane, tail.catch(() => {}))
    return tail
  }
}

// ---------------------------------------------------------------
// 第 3 部分：写者围栏（session-tool-result-guard 的机制骨架）
// ---------------------------------------------------------------
class TranscribedSession {
  constructor(sessionKey) {
    this.sessionKey = sessionKey
    this.transcript = []          // 会话历史（真源）
    this.activeWriterRunId = null // ★ 持久写者声明：同一时刻至多一个 run 拥有写权
  }
  /** 流式开始前声明写者：后声明的取代先声明的（interrupt 语义的落点）。 */
  claimWriter(runId) {
    const superseded = this.activeWriterRunId
    this.activeWriterRunId = runId
    return { superseded }
  }
  /**
   * transcript 追加：带 expectedWriterRunId，同步（无 await）校验后落盘。
   * 真实实现的硬纪律：写事务里不许有 Promise/await（根 AGENTS.md），校验必须
   * 在同一个同步事务里完成，否则围栏有竞态窗口。
   */
  append(runId, entry) {
    if (runId !== this.activeWriterRunId) {
      return { ok: false, reason: `writer-fence: 声明已是 ${this.activeWriterRunId}，${runId} 的写入被拒绝` }
    }
    this.transcript.push(`[by ${runId}] ${entry}`)
    return { ok: true }
  }
}

// ---------------------------------------------------------------
// 第 4 部分：run 的 mini 编排 + mock agent
// ---------------------------------------------------------------
/** 一次 embedded run：双层入队 → 声明写者 → 模拟流式产出 → 追加 transcript。 */
async function embeddedRun(q, session, { runId, text, workMs, onSteer }) {
  const sessionLane = resolveSessionLane(session.sessionKey)
  return q.enqueue(sessionLane, async () => {
    await q.enterGlobal()
    q.note(`run ${runId} 开跑`)
    try {
      session.claimWriter(runId)
      // 模拟流式：产出分两次追加；onSteer 模拟 steer 模式把新消息注入运行时。
      const mid = onSteer?.(runId) // steer 注入发生在"下一个模型边界"
      await sleep(workMs)
      const r1 = session.append(runId, `回答前半段${mid ? `（已吸收 steer: "${mid}"）` : ''}`)
      await sleep(5)
      const r2 = session.append(runId, `回答后半段`)
      return { r1, r2 }
    } finally {
      q.exitGlobal()
      q.note(`run ${runId} 结束`)
    }
  })
}

// ---------------------------------------------------------------
// 演示
// ---------------------------------------------------------------
async function main() {
  const log = (...a) => console.log(...a)

  console.log('== 1. 同会话轰炸：外层会话 lane 宽 1，三条消息严格串行 ==')
  const q = new MiniCommandQueue()
  const sess = new TranscribedSession('agent:main:main')
  const t0 = Date.now()
  const runs = await Promise.all([
    embeddedRun(q, sess, { runId: 'run#1', text: '第一条', workMs: 40 }),
    embeddedRun(q, sess, { runId: 'run#2', text: '第二条', workMs: 20 }),
    embeddedRun(q, sess, { runId: 'run#3', text: '第三条', workMs: 5 }),
  ])
  log(`三条 run 全部落定耗时 ${Date.now() - t0}ms（≥ 40+20+5ms：串行可证）`)
  log('transcript 追加顺序 = run#1 → run#2 → run#3（与会话 lane 一致）')
  log(`lane 命名：${resolveSessionLane('agent:main:main')} / 全局=${resolveGlobalLane(undefined)}`)
  console.log(`并发默认值（queue.md:19）：main 宽度 = ${LANE_WIDTH.main}（max(8, CPU×4)），subagent = ${LANE_WIDTH.subagent}，未配置 lane = ${LANE_WIDTH['不存在'] ?? 1}`)
  log('→ 会话闸管"谁先谁后"，全局闸管"总共放几个"')

  console.log('\n== 2. 队列模式 steer：新消息注入正在跑的运行时 ==')
  const q2 = new MiniCommandQueue()
  const sess2 = new TranscribedSession('agent:main:main')
  // steer 模式：run#1 已在跑，第二条消息不排队，而是注入"下一个模型边界"。
  const steerInjected = { msg: '用户补充：只要北京的天气' }
  await Promise.all([
    embeddedRun(q2, sess2, { runId: 'run#A', text: '查天气', workMs: 30, onSteer: () => (steerInjected.msg ? steerInjected.msg : null) }),
    sleep(5).then(() => log(`  [steer] run#A 进行中收到新消息 → 注入而非排队: "${steerInjected.msg}"`)),
  ])
  log('run#A 的 transcript:', JSON.stringify(sess2.transcript, null, 0))
  log('→ 已启动的工具跑完、未启动的调用可跳过、在下一次模型决策前 steer 可见（queue.md:37）')

  console.log('\n== 3. 写者围栏（失败路径）：被取代的 run 提交不进脏数据 ==')
  const q3 = new MiniCommandQueue()
  const sess3 = new TranscribedSession('agent:main:main')
  sess3.claimWriter('run#old')                       // 旧 run 已声明写者（流式进行中）
  sess3.claimWriter('run#new')                       // interrupt：新 run 取代旧 run
  const late = sess3.append('run#old', '旧 run 迟到的分析结果')
  log(`旧 run 迟到写入 → ${late.ok ? '竟然成功了(BUG!)' : `拒绝: ${late.reason}`}`)
  const okNew = sess3.append('run#new', '新 run 的结果')
  log(`新 run 写入 → ok=${okNew.ok}`)
  // 无声明：连写权都没有的 run 直接被拒（围栏默认关闭世界）。
  const ghost = sess3.append('run#ghost', '幽灵写入')
  log(`幽灵 run 写入 → ok=${ghost.ok}（${ghost.reason}）`)

  console.log('\n== 4. 十 lane 拓扑 + cron 防死锁改派 ==')
  const STATIC_LANES = ['main', 'system-agent', 'system-agent-inference', 'cron', 'cron-nested',
    'hook-dispatch', 'background', 'subagent', 'active-memory', 'nested'] // process/lanes.ts:12-35
  log('静态 lane：', STATIC_LANES.join(' · '))
  log(`cron 槽内再触发 agent run：resolveGlobalLane('cron') → ${resolveGlobalLane('cron')}（排回 cron = 等自己 = 永久自锁）`)
  log(`动态 lane 示例：${resolveSessionLane('agent:main:main')}（永不进静态清单，防诊断快照无界膨胀）`)
  console.log('\n不变量回顾：同会话串行（会话闸）→ 整机限流（全局闸）→ 历史唯一写者（围栏）。')
}

main().catch((e) => { console.error(e); process.exit(1) })
