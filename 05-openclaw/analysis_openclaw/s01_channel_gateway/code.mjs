#!/usr/bin/env node
/**
 * s01_channel_gateway.mjs —— 渠道网关：适配器归一化 + gateway run 生命周期
 *
 * Coding CLI 的宿主是"终端 + 一个人"：输入只有一种形状（人在键盘前敲的 prompt）。
 * OpenClaw 的宿主是"一台常开机器 + 27 类通讯渠道"：WhatsApp/Telegram/Discord/Slack/
 * Signal/iMessage……每家报文结构完全不同，而且消息随时插进来——没有人在旁边看着。
 * 于是它把两件事做成了基础设施：
 *
 *   1. channel 适配器（channel adapter，渠道适配层）
 *      插件只负责"翻译"：把各家的原始报文归一化成统一的 InboundMessage；
 *      归一化之后的门控、路由、prompt 装配全归 core（职责切分见
 *      docs/plugins/sdk-channel-plugins.md:19-37）。
 *
 *   2. gateway run 生命周期（gateway = 常驻网关进程，一台主机一个 = 一个信任边界）
 *      boot（装配 WS+HTTP :18789）→ channels（逐个拉起连接）→ admission（入站预检）
 *      → dispatch（消息变 run）→ reply（按来源渠道回程）→ drain（停收新消息、
 *      排空在途）→ closed。关停预算见 gateway-shutdown-budget.mjs。
 *
 *   +----------+   normalize   +-----------+  admission   +------------------+
 *   | Telegram | ------------> |           | -----------> | dispatch → agent |
 *   | WhatsApp | ------------> |  adapter  |              +------------------+
 *   | Discord  | ------------> | (只做翻译) |                ↓ 回复按来源渠道发回
 *   +----------+               +-----------+            <------------------+
 *
 *   生命周期：  boot → channels-up → [accepting turns] → draining → closed
 *
 * 运行：node code.mjs    （零依赖，离线；"agent"由 Mock 扮演）
 * 对照真实源码：src/gateway/server.ts:20 startGatewayServer、
 *   src/gateway/server-start.ts:21 startGatewayServerCore、
 *   src/channels/turn/run-channel-turn.ts:159 runChannelTurn、
 *   src/auto-reply/dispatch.ts:234 dispatchInboundMessage、
 *   src/channels/bundled-channel-ids.generated.ts:11（27 个 bundled 渠道 id）
 */

import { assert } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：统一入站契约 —— InboundMessage
// ---------------------------------------------------------------
// 渠道插件的第一义务：把自家报文翻译成这个形状。OpenClaw 里这一步发生在
// 渠道插件内部（extensions/<channel>/），core 只认归一化产物。

/** 归一化入站消息。字段名有意与真实实现对齐（channel/chatType/senderId/…）。 */
function makeInboundMessage({ channel, chatType, senderId, chatId, text, messageId, threadId }) {
  return deepSeal({
    channel,      // 渠道 id：'telegram' | 'whatsapp' | ...
    chatType,     // 会话形态：'direct'（私聊）| 'group'（群聊）| 'channel'（频道）
    senderId,     // 平台侧发送者 id（决定"谁能触发"—— s05 的主角）
    chatId,       // 平台侧会话 id（私聊=对端 id，群聊=群 id）
    text,         // 已剥离平台标记的正文
    messageId,    // 平台侧消息 id（去重/引用/回复定位）
    threadId: threadId ?? null, // Slack/Discord 线程 id（进 sessionKey 后缀 —— s02）
  })
}
function deepSeal(o) { return Object.freeze(structuredClone(o)) } // 归一化产物定型即不可变

// ---------------------------------------------------------------
// 第 2 部分：渠道适配器 —— 插件只管翻译
// ---------------------------------------------------------------
/**
 * mini 适配器基类：register 时 core 只认 `id` + `normalize` 两个接缝。
 * 真实渠道插件还要实现 outbound/typing/threading 等（见 sdk-channel-plugins 文档），
 * mini 只保留教学必需的最小面。
 */
class ChannelAdapter {
  constructor(id, { label }) { this.id = id; this.label = label; this.connected = false }
  /** 生命周期：拉起渠道连接（真实实现里是连 WebSocket / 轮询 / 监听桥） */
  async connect(logs) { this.connected = true; logs.push(`[${this.id}] 已连接`) }
  /** 生命周期：关停时先断连接（drain 之后才允许断 —— 见 MiniGateway.stop） */
  async disconnect(logs) { this.connected = false; logs.push(`[${this.id}] 已断开`) }
}

// 三个 mock 适配器：每家的"原始报文"故意长得完全不同，翻译后却完全同形。
class TelegramAdapter extends ChannelAdapter {
  constructor() { super('telegram', { label: 'Telegram(grammY)' }) }
  /** grammY 的 update：message.chat.id / from.id / text —— 全平台最难看的那种嵌套 */
  normalize(update) {
    const m = update.message
    return makeInboundMessage({
      channel: this.id,
      chatType: m.chat.type === 'private' ? 'direct' : m.chat.type,
      senderId: String(m.from.id),
      chatId: String(m.chat.id),
      text: m.text,
      messageId: `tg-${m.message_id}`,
    })
  }
}

class WhatsAppAdapter extends ChannelAdapter {
  constructor() { super('whatsapp', { label: 'WhatsApp(Baileys)' }) }
  /** Baileys 的消息：key.remoteJid / participant / conversation —— 字段名另起一套 */
  normalize(msg) {
    const jid = msg.key.remoteJid
    return makeInboundMessage({
      channel: this.id,
      chatType: jid.endsWith('@g.us') ? 'group' : 'direct',
      senderId: msg.participant ?? jid.split('@')[0],
      chatId: jid,
      text: msg.conversation ?? '[非文本]',
      messageId: `wa-${msg.key.id}`,
    })
  }
}

class DiscordAdapter extends ChannelAdapter {
  constructor() { super('discord', { label: 'Discord' }) }
  /** Discord 的 message create：author.id / channel_id / content —— 雪花 id 全是数字 */
  normalize(event) {
    return makeInboundMessage({
      channel: this.id,
      chatType: event.guild_id ? 'group' : 'direct',
      senderId: event.author.id,
      chatId: event.channel_id,
      text: event.content,
      messageId: `dc-${event.id}`,
    })
  }
}

// ---------------------------------------------------------------
// 第 3 部分：MiniGateway —— 常驻网关生命周期
// ---------------------------------------------------------------
// 状态机：boot → channels-up → accepting → draining → closed。
// 两条铁律从真实实现抄来：
//   ① 同一个渠道 id 只能注册一次（否则回复路由就有两个主人）；
//   ② 回复必回来源渠道 —— 模型无权选渠道（docs/channels/channel-routing.md:10-13）。

const GATEWAY_STATE = ['boot', 'channels-up', 'accepting', 'draining', 'closed']

class MiniGateway {
  constructor() {
    this.state = 'boot'
    this.adapters = new Map()   // channelId -> adapter（回复路由的真源）
    this.turns = []             // 在途 turn 记账（drain 时要排空）
    this.logs = []
  }
  get log() { return this.logs }

  /** 生命周期 ①②：boot + 逐个拉起渠道。 */
  async start(adapterList) {
    if (this.state !== 'boot') throw new Error(`[gateway] start 只允许从 boot 进入，当前 ${this.state}`)
    for (const ad of adapterList) {
      if (this.adapters.has(ad.id)) {
        // 边界路径：重复 id 拒绝注册。真实实现里重复渠道 id 会在启动期报错，
        // 因为"回复回哪个插件"必须唯一。
        throw new Error(`[gateway] 渠道 id 重复注册: ${ad.id}`)
      }
      this.adapters.set(ad.id, ad)
    }
    for (const ad of this.adapters.values()) await ad.connect(this.logs)
    this.state = 'channels-up'
    this.logs.push(`[gateway] channels-up: ${[...this.adapters.keys()].join(', ')}`)
    this.state = 'accepting'
  }

  /**
   * 生命周期 ③④：一个渠道 turn = 归一化 → admission（入站预检）→ dispatch。
   * 对应 runChannelTurn（run-channel-turn.ts:159）：先预检再进 agent；
   * 未注册渠道的消息在这里被丢弃，根本不会变成 run。
   */
  async acceptTurn(raw, agentMock) {
    if (this.state !== 'accepting') throw new Error(`[gateway] 状态 ${this.state} 不收新消息`)
    const ad = this.adapters.get(raw.__channel)
    if (!ad) {
      // admission 拒绝：渠道没注册 = 不归这台网关管。计入日志但直接丢弃。
      this.logs.push(`[gateway] 丢弃：未注册渠道 '${raw.__channel}' 的消息`)
      return { ok: false, reason: 'unknown-channel' }
    }
    let msg
    try { msg = ad.normalize(raw) } catch (e) {
      // 翻译失败也是 admission 的事：坏报文不能炸网关进程。
      this.logs.push(`[gateway] 丢弃：${ad.id} 报文无法归一化 (${e.message})`)
      return { ok: false, reason: 'normalize-error' }
    }
    const turn = { id: `turn-${this.turns.length + 1}`, msg, status: 'dispatching' }
    this.turns.push(turn)
    this.logs.push(`[gateway] dispatch ${turn.id}: ${msg.channel}/${msg.chatType} "${msg.text}"`)
    // dispatch（dispatch.ts:234 的 mini 版）：mock agent 跑一轮，产一个回复文本。
    const replyText = await agentMock({ channel: msg.channel, text: msg.text })
    turn.status = 'done'
    // 生命周期 ⑤：回复必回来源渠道。路由真源是 this.adapters —— 模型拿不到它。
    await ad.deliverReply?.(msg.chatId, replyText)
    this.logs.push(`[gateway] reply ${turn.id} → ${msg.channel}:${msg.chatId} "${replyText}"`)
    return { ok: true, turn }
  }

  /**
   * 生命周期 ⑥⑦：drain（排空）→ closed。真实实现有一个显式关停预算
   * （gateway-shutdown-budget.mjs：drain 315s + reserve 10s + supervisor margin 5s），
   * 顺序是：先停入站（不再收新 turn），等在途 turn 落地，最后才断渠道连接。
   */
  async stop(pendingWork) {
    if (this.state !== 'accepting') throw new Error(`[gateway] 只能从 accepting 关停，当前 ${this.state}`)
    this.state = 'draining'
    this.logs.push('[gateway] draining: 停收新入站，排空在途 turn')
    if (pendingWork) await pendingWork()   // 在途工作排空（mini：一个回调）
    for (const ad of this.adapters.values()) await ad.disconnect(this.logs)
    this.state = 'closed'
  }
}

// Telegram 适配器补一个发送面：outbound 只对已连接的适配器可用。
Object.defineProperty(TelegramAdapter.prototype, 'deliverReply', {
  value: async function (chatId, text) {
    if (!this.connected) throw new Error('[telegram] 未连接，无法发送')
    this._lastOut = { chatId, text }
  },
})

// ---------------------------------------------------------------
// 演示
// ---------------------------------------------------------------
async function main() {
  const log = (...a) => console.log(...a)

  console.log('== 1. boot：三个渠道适配器注册（重复 id 是启动期错误）==')
  const gw = new MiniGateway()
  const tg = new TelegramAdapter()
  await gw.start([tg, new WhatsAppAdapter(), new DiscordAdapter()])
  log(gw.log.slice(-1)[0])
  try {
    await new MiniGateway().start([new TelegramAdapter(), new TelegramAdapter()])
  } catch (e) { log(`边界路径 → ${e.message}`) }

  console.log('\n== 2. 三渠道各来一条消息：报文异形，归一化后同形 ==')
  const mockAgent = async ({ channel, text }) => `(mock reply to "${text}" @${channel})`
  await gw.acceptTurn({ __channel: 'telegram', message: { message_id: 7, text: '帮我看下天气', chat: { id: 42, type: 'private' }, from: { id: 1001 } } }, mockAgent)
  await gw.acceptTurn({ __channel: 'whatsapp', key: { remoteJid: '8613800000000@s.whatsapp.net', id: 'ABC' }, conversation: '明天几点开会' }, mockAgent)
  await gw.acceptTurn({ __channel: 'discord', id: '999', content: '跑一下测试', author: { id: '2002' }, channel_id: '555', guild_id: 'g1' }, mockAgent)
  log('三份异形报文 → 同一形状 InboundMessage（channel/chatType/senderId/chatId/text…）')
  log(`telegram outbound 请求体（回来源渠道）: ${JSON.stringify(tg._lastOut)}`)

  console.log('\n== 3. admission 拒绝：未注册渠道 / 坏报文都不该变成 run ==')
  await gw.acceptTurn({ __channel: 'nostr', text: 'x' }, mockAgent)
  await gw.acceptTurn({ __channel: 'whatsapp' /* 缺 key，Baileys 翻译必炸 */ }, mockAgent)
  log(`网关仍健康：state=${gw.state}, turns 完成数=${gw.turns.length}`)

  console.log('\n== 4. drain 关停：先停入站 → 排空在途 → 再断渠道连接 ==')
  const inFlight = new Promise((r) => setTimeout(r, 10))
  await gw.stop(async () => { await inFlight; log('  [drain] 在途 turn 已落地') })
  log(gw.log.filter((l) => l.includes('drain') || l.includes('断开') || l.includes('已断开')).join('\n') || gw.log.slice(-3).join('\n'))
  log(`final state = ${gw.state}（合法迁移: ${GATEWAY_STATE.join(' → ')}）`)
  assert(gw.state === 'closed', '关停后必须是 closed')
  assert(!tg.connected, '渠道连接必须已断开')
}

main().catch((e) => { console.error(e); process.exit(1) })
