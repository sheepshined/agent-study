#!/usr/bin/env node
/**
 * s06_unattended_inputs.mjs —— 无人值守输入源：cron / webhook / 语音唤醒
 *
 * coding CLI 的输入源只有一种：人在终端敲 prompt——有键盘就有兜底。
 * OpenClaw 的输入源是"没有人敲键盘"的三类事件，它们必须汇入与人类消息
 * 完全相同的 dispatch 管道，而且**身份与预算随输入自带**：
 *
 *   ① cron（定时任务）：调度器持久化 job、到点唤醒 agent，输出可投递到
 *      渠道/webhook/不投（docs/automation/cron-jobs.md）。触发者身份 =
 *      job 配置本身（管理员所配）。lane 语义：cron 槽被外层持有，内层 run
 *      改派 cron-nested——排回 cron 就是等自己（s03 场景 5 的死锁故事）。
 *   ② webhook（网络钩子）：外部系统 HTTP POST 到 /hooks，先过鉴权与
 *      限流（失败 20/60s + 60s 锁定，不可配——docs/gateway/security/
 *      rate-limiting.md），签名合法才归一化入站。
 *   ③ 语音唤醒（voicewake）：唤醒词表全局唯一、Gateway 拥有，存
 *      config_machine_state.voicewake（≤32 条 × 64 UTF-16，默认
 *      openclaw/claude/computer）；识别在设备端本地跑（apps/swabble），
 *      设备身份来自 s10 的签名配对。
 *
 *   时间轴（cron）──────┐
 *   外部系统（webhook）──┼──→ 统一 admission → sessionKey → lane → run
 *   麦克风（voicewake）──┘         （s05 的闸门在这里，一个不少）
 *
 * 运行：node code.mjs    （零依赖，离线；时钟/HTTP/语音全由 Mock 驱动）
 * 对照真实源码：src/cron/（active-jobs.ts、command-runner.ts 等约 225 文件）、
 *   src/agents/tools/cron-tool.ts:222 createCronTool、
 *   src/gateway/server/hooks.ts:235 createGatewayHookDispatcher / :737 请求处理器、
 *   docs/nodes/voicewake.md、apps/swabble/README.md（端侧唤醒词守护进程）
 */

import { assert } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：cron —— 时间驱动的输入源
// ---------------------------------------------------------------
/** mini 调度器：job 有 cron 表达式（mini 简化成"每 N tick"）、session 钉定、
 *  wakeMode 与 deleteAfterRun。真实实现里调度器持久化 job、到点发 wake，
 *  并经 job-session-bindings 钉到指定会话。 */
class MiniCronScheduler {
  constructor(clock) { this.clock = clock; this.jobs = []; this.laneOf = (job) => 'cron' } // 外层跑在 cron lane
  add(job) { this.jobs.push(job); return job }

  /** 到点触发的"内层 run"的 lane 解析：这就是防自锁改派（s03 resolveGlobalLane）。 */
  resolveInnerLane(job) {
    if (job.wakeMode === 'now') return 'cron-nested' // cron 槽内再排队 cron = 等自己
    return 'cron-nested'
  }

  /** 调度一跳：返回这一拍到点的 job。 */
  tick() {
    const due = this.jobs.filter((j) => this.clock.tick % j.everyNTicks === 0)
    return due.map((j) => ({ job: j, lane: this.resolveInnerLane(j) }))
  }
}

// ---------------------------------------------------------------
// 第 2 部分：webhook —— 外部系统驱动的输入源
// ---------------------------------------------------------------
/** mini webhook 鉴权：共享密钥签名 + 认证失败限流（失败 20/60s + 60s 锁定，
 *  不可配——六条限流之一，s10 全表展开）。签名用极简 HMAC 比对示意。 */
class MiniWebhookEndpoint {
  constructor(secret) { this.secret = secret; this.failCount = 0; this.lockedUntil = 0 }
  sign(body) { return `sig(${this.secret}:${body})` } // 教学版"签名"：真实实现是 HMAC + 时间戳

  accept(body, signature, now = Date.now()) {
    if (now < this.lockedUntil) return { status: 429, reason: '锁定中（认证失败过多）' }
    if (signature !== this.sign(body)) {
      this.failCount++
      if (this.failCount >= 20) { this.lockedUntil = now + 60_000; return { status: 429, reason: '20 次认证失败/60s → 锁定 60s' } }
      return { status: 401, reason: `签名不合法（失败计数 ${this.failCount}/20）` }
    }
    this.failCount = 0 // 成功重置计数（错误凭证才消耗预算）
    return { status: 200, event: JSON.parse(body) }
  }
}

// ---------------------------------------------------------------
// 第 3 部分：voicewake —— 声音驱动的输入源
// ---------------------------------------------------------------
/** mini 唤醒词表：全局唯一、Gateway 拥有；set 时规范化（trim/去空/≤32 条/
 *  每条 ≤64 UTF-16 码元/不劈开代理对），空表回落内置默认。 */
const VOICEWAKE_DEFAULTS = ['openclaw', 'claude', 'computer']
class MiniVoicewakeTable {
  constructor() { this.triggers = [...VOICEWAKE_DEFAULTS] }
  set(next) {
    const cleaned = next.map((t) => t.trim()).filter(Boolean)
      .map((t) => [...t].slice(0, 64).join('')) // [...t] 按码点切，避免劈开代理对
      .slice(0, 32)
    this.triggers = cleaned.length ? cleaned : [...VOICEWAKE_DEFAULTS] // 空表回落默认
    return this.triggers
  }
  /** 设备端本地判定：唤醒词命中 → 才开始转写并投递（端侧零网络，见 swabble）。 */
  detectAndRoute(device, utterance) {
    const hit = this.triggers.find((w) => utterance.toLowerCase().startsWith(w))
    if (!hit) return { wake: false, reason: '未命中唤醒词，不产生任何输入' }
    return { wake: true, device, text: utterance.slice(hit.length).trim() || '(仅唤醒，无指令)' }
  }
}

// ---------------------------------------------------------------
// 第 4 部分：统一 admission —— 三类输入汇入同一管道
// ---------------------------------------------------------------
/** mini dispatch：三类输入都先过身份裁决（s05 的闸一个不少），
 *  再算 sessionKey（s02）与 lane（s03），最后才是一条 mock run。 */
function dispatchAdmission(input, { trustedDevices, approvedSenders }) {
  if (input.kind === 'voice') {
    if (!trustedDevices.includes(input.device)) return { ok: false, reason: '设备未配对（s10 签名配对）' }
  }
  if (input.kind === 'webhook') {
    if (!input.authenticated) return { ok: false, reason: 'webhook 未通过鉴权' }
  }
  if (input.kind === 'human-dm') {
    if (!approvedSenders.includes(input.senderId)) return { ok: false, reason: 'DM 未通过 dmPolicy（s05）' }
  }
  return { ok: true, sessionKey: input.sessionKey ?? 'agent:main:main', lane: input.lane ?? 'main' }
}

// ---------------------------------------------------------------
// 演示
// ---------------------------------------------------------------
async function main() {
  const log = (...a) => console.log(...a)

  console.log('== 1. cron：到点唤醒，内层 run 改派 cron-nested ==')
  const clock = { tick: 0 }
  const sched = new MiniCronScheduler(clock)
  sched.add({ name: '早报', everyNTicks: 3, session: 'main', wakeMode: 'now', deleteAfterRun: false })
  const fired = []
  for (clock.tick = 1; clock.tick <= 6; clock.tick++) {
    for (const { job, lane } of sched.tick()) {
      fired.push(`tick${clock.tick}:${job.name}(lane=${lane})`)
      log(`  [tick ${clock.tick}] 触发 ${job.name} → 内层 lane=${lane}（cron 槽内排回 cron = 等自己）`)
    }
  }
  assert(fired.length === 2, '每 3 拍触发一次，6 拍共 2 次')

  console.log('\n== 2. webhook：签名合法才入站；认证失败限流（失败路径）==')
  const ep = new MiniWebhookEndpoint('shared-secret')
  const body = JSON.stringify({ type: 'ci.failed', repo: 'foo' })
  log(`合法签名 POST → ${JSON.stringify({ ...ep.accept(body, ep.sign(body)), event: undefined, status: 200 })}`)
  // 失败路径：坏签名累积到 20 次触发锁定。
  let last
  for (let i = 0; i < 21; i++) last = ep.accept(body, 'sig(wrong)')
  log(`连续 21 次坏签名 → 最后一次 ${JSON.stringify(last)}`)
  log(`锁定期间再发合法签名 → ${JSON.stringify({ status: ep.accept(body, ep.sign(body)).status, reason: ep.accept(body, ep.sign(body)).reason })}`)

  console.log('\n== 3. voicewake：唤醒词命中才产生输入；规范化边界 ==')
  const table = new MiniVoicewakeTable()
  log(`默认唤醒词: ${table.triggers.join(' / ')}（macOS 端 swabble 守护进程默认词是 ` +
    `'clawd'/别名 'claude'，命中表后才有输入）`)
  log(`"claude 帮我订机票" → ${JSON.stringify(table.detectAndRoute('mac-living-room', 'claude 帮我订机票'))}`)
  log(`"今天天气怎样"     → ${JSON.stringify(table.detectAndRoute('mac-living-room', '今天天气怎样'))}`)
  // 规范化边界：33 条截到 32；超长截到 64 码元；全空回落默认。
  const many = table.set(Array.from({ length: 33 }, (_, i) => `词${i}`))
  log(`设置 33 条 → 保留 ${many.length} 条（≤32）；` +
    `设 80 字超长词 → ${table.set(['w'.repeat(80)])[0].length} 个码元；` +
    `设全空表 → 回落默认 [${table.set(['', '  '].map(() => ' ')).join(', ')}]`)

  console.log('\n== 4. 统一 admission：三类输入过同一组闸（失败路径）==')
  log(`human-dm 陌生发送者 → ${JSON.stringify(dispatchAdmission({ kind: 'human-dm', senderId: 'stranger' }, { trustedDevices: [], approvedSenders: ['alice'] }))}`)
  log(`webhook 未鉴权     → ${JSON.stringify(dispatchAdmission({ kind: 'webhook', authenticated: false }, {}))}`)
  log(`voice 未配对设备   → ${JSON.stringify(dispatchAdmission({ kind: 'voice', device: 'ghost-phone' }, { trustedDevices: ['mac-living-room'], approvedSenders: [] }))}`)
  log(`cron job（管理员所配，身份即配置）→ ${JSON.stringify(dispatchAdmission({ kind: 'cron', sessionKey: 'agent:main:main', lane: 'cron' }, {}))}`)
  console.log('\n结论：输入源千差万别，admission 只有一套——身份与预算随输入自带。')
}

main().catch((e) => { console.error(e); process.exit(1) })
