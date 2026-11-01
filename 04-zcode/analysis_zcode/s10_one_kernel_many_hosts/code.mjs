#!/usr/bin/env node
/**
 * s10_one_kernel_many_hosts.mjs —— mini 多形态装配：一内核、帧协议、CommandInbox
 *
 * 收官课：s01-s09 的浓缩内核，装进三种宿主壳（TUI / Desktop / Web），机制对应：
 *
 *   协议唯一改动点（packages/shared/src/zcode-protocol/index.ts，3717 行）
 *     协议类型与运行时校验只落一个文件（根 AGENTS.md:59 的纪律）
 *
 *   stdio 帧通道（cli/src/main.ts + run.ts:525-533）
 *     app-server / agent-server --stdio：stdout = 严格帧通道；
 *     console 全部改道 stderr —— 任何依赖的一行普通日志都会让传输层 JSON 解析崩溃，
 *     所以"改道"必须在进程入口做（顺序即安全顺序，呼应 s07）
 *
 *   CommandInbox（bootstrap/src/zcode-protocol-v4/command-inbox.ts:107）
 *     已接受的 busy/running 输入做串行 admission：
 *     · handle(raw) 逐条准入，admissionSeq 单调递增（:162-164）
 *     · per-session admission gate 持有到 settle（:139"固定锁序"）
 *     · 输入即命令，命令全序 —— 多宿主共享内核也不打架
 *
 *   手机远控（根 AGENTS.md:61-63）
 *     attachment 复用桌面已有 Host，不另起 Agent/Local Host/远程会话；
 *     desktop-continuous（实时链路）与 web-remote-replayable（恢复链路）语义必须区分
 *
 *   headless（run.ts:42 / :494）
 *     -p 模式默认 yolo；需要审批的调用无人应答 = 失败退出（呼应 s04）
 *
 * 运行：node code.mjs        （零依赖，离线）
 * 对照真实源码：packages/shared/src/zcode-protocol/index.ts、
 *              apps/zcode-cli/packages/bootstrap/src/zcode-protocol-v4/command-inbox.ts、
 *              apps/zcode-cli/packages/cli/src/{main.ts,run.ts}
 */

import { assert, banner } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：浓缩内核（s01-s05 的投影，不 import 任何宿主代码）
// ---------------------------------------------------------------
class Kernel {
  constructor() {
    this.listeners = new Set()
    this.inboxQueue = []
    this.settled = true
  }
  onEvent(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn) }
  emit(type, payload) { for (const fn of this.listeners) fn({ type, payload }) }

  /** 一次 model step 的浓缩版：事件先落"库"（s02），再广播给所有宿主（本课） */
  async step(input) {
    this.emit('user/message', { text: input })
    const tools = /删除|rm/.test(input) ? [{ name: 'bash', sideEffectScope: 'workspace' }] : []
    this.emit('model/request', { step: 0, tools: tools.length })
    if (tools.length) this.emit('permission/requested', { tool: 'bash', mode: 'headless' })
    else this.emit('model/complete', { text: `已回答: ${input}` })
  }
}

// ---------------------------------------------------------------
// 第 2 部分：三种宿主壳 —— 只订阅事件，不碰循环
// ---------------------------------------------------------------
function tuiHost() {
  const lines = []
  return {
    name: 'TUI',
    onEvent: (e) => lines.push(`[TUI 渲染] ${e.type}`),
    frames: () => lines,
  }
}
function desktopHost() {
  const frames = []
  return {
    name: 'Desktop',
    onEvent: (e) => frames.push({ v4frame: true, type: e.type }), // 经 V4 协议发给 renderer
    frames: () => frames,
  }
}
function webHost() {
  const ws = []
  return {
    name: 'Web',
    onEvent: (e) => ws.push(JSON.stringify(e)),
    frames: () => ws,
  }
}

// ---------------------------------------------------------------
// 第 3 部分：帧通道 —— stdout 卫生由入口保证（main.ts :30-35 的 mini 版）
// ---------------------------------------------------------------
class FrameChannel {
  constructor() {
    this.stdoutFrames = []
    this.stderrLines = []
    this.consoleRouted = false // 真实代码在进程入口把 console 改道 stderr
  }
  installConsoleBoundary() {
    this.consoleRouted = true
    return {
      log: (msg) => this.stderrLines.push(String(msg)), // console.log → stderr
    }
  }
  writeFrame(obj) {
    if (!this.consoleRouted) throw new Error('[channel] 必须先安装 stderr 边界再开帧通道（入口顺序即安全顺序）')
    this.stdoutFrames.push(JSON.stringify(obj))
  }
  /** 协议解析端：任何非 JSON 帧都会崩 —— 这就是为什么卫生必须在入口做 */
  static parse(frame) {
    const v = JSON.parse(frame)
    if (!v.v4frame) throw new Error('[protocol] 未知的帧类型 —— 协议校验失败')
    return v
  }
}

// ---------------------------------------------------------------
// 第 4 部分：CommandInbox —— 串行 admission（command-inbox.ts 的 mini 版）
// ---------------------------------------------------------------
class CommandInbox {
  constructor(kernel) {
    this.kernel = kernel
    this.seq = 0
    this.queue = []
    this.busy = false
  }
  /** 逐条准入：admissionSeq 在"准入时"分配（不是执行时），UI 顺序才有权威 */
  async handle(input) {
    const admissionSeq = ++this.seq // :162-164 —— 每条命令只准入一次
    if (this.busy) {
      this.queue.push({ input, admissionSeq })
      this.kernel.emit('command/admitted', { input, admissionSeq })
      return { outcome: 'queued', admissionSeq }
    }
    this.kernel.emit('command/admitted', { input, admissionSeq })
    await this.execute(input)
    return { outcome: 'accepted', admissionSeq }
  }

  /** per-session gate 持有到 settle（:139"固定锁序"）；排空队列按准入序执行 */
  async execute(input) {
    this.busy = true
    try {
      await this.kernel.step(input)
    } finally {
      this.busy = false
      const next = this.queue.shift()
      if (next) await this.execute(next.input)
    }
  }
}

// ---------------------------------------------------------------
// 第 5 部分：main() —— 四个场景
// ---------------------------------------------------------------
async function main() {
  banner('场景 1：一内核三宿主 —— 内核不感知宿主')
  const kernel = new Kernel()
  const hosts = [tuiHost(), desktopHost(), webHost()]
  const unsubs = hosts.map((h) => kernel.onEvent(h.onEvent))
  await kernel.step('帮我总结这个仓库')
  console.log('  同一次 step 的事件，三种宿主各拿各的形态:')
  console.log('   ', hosts[0].frames().at(-1))
  console.log('   ', JSON.stringify(hosts[1].frames().at(-1)))
  console.log('   ', hosts[2].frames().at(-1))
  unsubs.forEach((u) => u())
  console.log('  → 宿主只是事件订阅者；换宿主 = 换订阅者集合，内核零改动')

  banner('场景 2：帧通道卫生 —— console 改道 stderr')
  const channel = new FrameChannel()
  const bounded = channel.installConsoleBoundary()
  bounded.log('某个依赖随手 console.log 的调试输出') // → stderr，不进帧流
  channel.writeFrame({ v4frame: true, type: 'user/message', payload: { text: 'hi' } })
  console.log(`  stdout 帧: ${channel.stdoutFrames.length} 条（纯净）`)
  console.log(`  stderr: ${channel.stderrLines.length} 条（日志去向）`)
  console.log('  协议端解析:', JSON.stringify(FrameChannel.parse(channel.stdoutFrames[0])))
  try { FrameChannel.parse('随机污染')} catch (e) { console.log(`  污染帧的下场: ${e.message}`) }

  banner('场景 3：CommandInbox —— busy 输入串行 admission')
  const inbox = new CommandInbox(kernel)
  const seen = []
  kernel.onEvent((e) => { if (e.type === 'command/admitted') seen.push(e.payload) })
  const p1 = inbox.handle('第一条：总结仓库')
  const p2 = inbox.handle('第二条：同时删掉日志')   // busy 期间 → 排队（且触发权限事件）
  const outcomes = [await p1, await p2]
  console.log('  准入结果:', outcomes.map((o) => `${o.outcome}#${o.admissionSeq}`).join(', '))
  console.log('  准入序:', seen.map((s) => `#${s.admissionSeq}"${s.input}"`).join(' → '))
  console.log('  → admissionSeq 在准入时分配：UI 显示顺序以它为权威，与执行完成顺序无关')

  banner('场景 4：失败/边界路径 —— headless 无人应答的审批')
  // run.ts:42：-p 模式默认 yolo；但若显式指定保守模式，需要审批的调用无人应答
  const headless = { mode: 'build' } // 显式给了保守模式
  const toolCall = { name: 'bash', sideEffectScope: 'workspace' }
  const needsApproval = headless.mode !== 'yolo'
  if (needsApproval) {
    console.log(`  ${toolCall.name}（sideEffectScope=${toolCall.sideEffectScope}）需要审批；headless 无人应答`)
    console.log('  → 结构化失败退出（exit code 非零），而不是挂死等一个永远不会来的"允许"')
    console.log('  ⚠ 若 mode 缺省 = yolo（run.ts:42 DEFAULT_HEADLESS_PROMPT_MODE）——脚本化集成最容易踩的默认值')
    assert(needsApproval, '演示保守模式')
  }

  console.log('\n收官：内核零改动装进任意宿主 —— 协议唯一改动点 + 帧通道卫生 + 命令全序 admission。')
}

main().catch((e) => { console.error(e); process.exit(1) })
