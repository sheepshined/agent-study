#!/usr/bin/env node
/**
 * s02_session_key.mjs —— sessionKey：多渠道消息归一到会话的确定性语法
 *
 * 五条消息可能来自五个渠道/五种形态（私聊、群、频道、线程、话题），但 agent
 * 的工作记忆只有"会话"这一个单位。谁来决定"哪些消息共享同一段历史"？
 * OpenClaw 的答案是 sessionKey（会话路由选择器）——一段确定性拼出来的字符串：
 *
 *   私聊（默认 main 收敛）：  agent:<agentId>:main
 *   群（groupScope=per-group）: agent:<agentId>:<channel>:group:<id>
 *   频道：                    agent:<agentId>:<channel>:channel:<id>
 *   Slack/Discord 线程：      ……追加 :thread:<threadId>
 *   Telegram 论坛话题：       ……群 key 内嵌 :topic:<topicId>
 *   子代理：                  agent:<agentId>:subagent:<uuid>
 *
 * 两条铁律：
 *   ① 确定性：同样的入站来源永远算出同一个 key——否则同一会话出现两条串行
 *     通道（s03 的 lane 按字符串相等分组，规范化不到位 = 并跑）；
 *   ② sessionKey 是路由选择器，不是授权令牌（trust-model.md）——知道 key 不等于
 *     有权往里发消息，"谁能触发"由 s05 的 dmPolicy/白名单在 admission 判。
 *
 *   TG私聊alice ┐
 *   TG私聊bob  ─┼─→ resolveRoute ─→ agent:main:main        （私聊收敛）
 *   WA私聊carol┘        │
 *   TG群#topic42 ───────┼─→ agent:main:telegram:group:-100…:topic:42
 *   DC频道#thread987 ───┘   agent:main:discord:channel:123…:thread:987
 *
 * 运行：node code.mjs    （零依赖，离线）
 * 对照真实源码：src/routing/resolve-route.ts:96 buildAgentSessionKey、:574 resolveAgentRoute、
 *   src/routing/session-key.ts:119 toAgentStoreSessionKey、:160 classifySessionKeyShape、
 *   docs/channels/channel-routing.md:38-70（sessionKey 语法权威页）
 */

import { assert } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：sessionKey 语法（channel-routing.md:38-70 的 mini 版）
// ---------------------------------------------------------------

/** 规范化：小写、去空白。真实实现里 peer id 规范化是专门一层
 *  （@openclaw/normalization-core），这里用"trim+小写"示意——
 *  key 按字符串相等分组，规范化不到位 = 同一会话并出两条串行通道。 */
const norm = (s) => String(s ?? '').trim().toLowerCase()

/**
 * buildSessionKey —— buildAgentSessionKey（resolve-route.ts:96）的教学版。
 * @param dmScope  私聊收敛策略：main（默认，全并主会话）| per-peer | per-channel-peer
 * @param groupScope 群收敛策略：per-group（默认）| main
 */
function buildSessionKey(msg, { dmScope = 'main', groupScope = 'per-group' } = {}) {
  const agent = norm(msg.agentId)
  const ch = norm(msg.channel)
  if (msg.chatType === 'direct') {
    if (dmScope === 'main') return `agent:${agent}:main`          // 私聊默认收敛：三个人共享主会话
    if (dmScope === 'per-peer') return `agent:${agent}:dm:${norm(msg.senderId)}`
    if (dmScope === 'per-channel-peer') return `agent:${agent}:${ch}:dm:${norm(msg.senderId)}`
    throw new Error(`未知 dmScope: ${dmScope}`)
  }
  const peerKind = msg.chatType === 'group' ? 'group' : 'channel' // peer 分类（peer-kind-match.ts 的 mini 版）
  if (groupScope === 'main') return `agent:${agent}:main`         // 群也可以全并入主会话（只改共享上下文，门控仍按来源）
  let key = `agent:${agent}:${ch}:${peerKind}:${norm(msg.chatId)}`
  if (msg.topicId) key += `:topic:${norm(msg.topicId)}`           // Telegram 论坛话题：内嵌进群 key
  if (msg.threadId) key += `:thread:${norm(msg.threadId)}`        // Slack/Discord 线程：追加后缀
  return key
}

// ---------------------------------------------------------------
// 第 2 部分：来源路由（reply route）—— 回程的确定性
// ---------------------------------------------------------------
// sessionKey 决定"和谁共享历史"，但不决定"回复发去哪"——s01 铁律"回复必回
// 来源渠道"。所以每条会话旁边还要记一条"最后投递路由"（来源渠道/账号/chatId/
// 线程），它跟着消息进来，被会话持有，回复时原样用回。

class SessionStore {
  constructor() { this.sessions = new Map() }

  /** dispatch 的前置步骤：算 key、归会话、记来源路由。对应
   *  resolveAgentRoute（resolve-route.ts:574）+ 会话元数据持久化的教学合并。 */
  resolve(msg, opts) {
    const sessionKey = buildSessionKey(msg, opts)
    let sess = this.sessions.get(sessionKey)
    if (!sess) {
      sess = { sessionKey, history: [], replyRoute: null, dmScope: opts?.dmScope ?? 'main' }
      this.sessions.set(sessionKey, sess)
    }
    sess.history.push(`${msg.channel}:${msg.senderId}: ${msg.text}`)
    sess.replyRoute = { channel: msg.channel, chatId: msg.chatId, threadId: msg.threadId ?? null, senderId: msg.senderId }
    return sess
  }

  /** 确定性回程：回复目标 = 会话记下的来源路由。模型无权改道。 */
  replyTarget(sessionKey) { return this.sessions.get(sessionKey)?.replyRoute ?? null }
}

// ---------------------------------------------------------------
// 演示
// ---------------------------------------------------------------
async function main() {
  const log = (...a) => console.log(...a)
  const store = new SessionStore()

  console.log('== 1. 私聊：默认收敛成主会话；dmScope 换挡即三分离 ==')
  const dm = (channel, senderId, text) => store.resolve({ agentId: 'main', channel, chatType: 'direct', senderId, chatId: `${channel}-${senderId}`, text })
  dm('telegram', 'alice', '帮我看天气')
  dm('whatsapp', 'carol', '明天几点开会')
  const main = dm('telegram', 'bob', '跑下测试')
  log(`key = ${main.sessionKey}`)
  log('主会话历史:', JSON.stringify(main.history, null, 0))
  log('→ 没有人要求共享，默认就是共享（agent 个人助理的默认世界观：主会话是"我"）')
  const store2 = new SessionStore()
  const dm2 = (channel, senderId, text) => store2.resolve({ agentId: 'main', channel, chatType: 'direct', senderId, chatId: `${channel}-${senderId}`, text }, { dmScope: 'per-peer' })
  const a = dm2('telegram', 'alice', '看天气'); const c = dm2('whatsapp', 'carol', '开会'); const b = dm2('telegram', 'bob', '测试')
  log(`dmScope=per-peer 换挡 → alice:${a.sessionKey} / carol:${c.sessionKey} / bob:${b.sessionKey}（三个互不相同）`)

  console.log('\n== 2. 群/频道隔离 + 线程/话题后缀 ==')
  const tgGroup = store.resolve({ agentId: 'main', channel: 'telegram', chatType: 'group', senderId: 'u1', chatId: '-100123', topicId: '42', text: '@bot 帮个忙' })
  const dcThread = store.resolve({ agentId: 'main', channel: 'discord', chatType: 'channel', senderId: 'u2', chatId: '123456', threadId: '987654', text: '接着说' })
  log(`TG 群话题 → ${tgGroup.sessionKey}`)
  log(`DC 频道线程 → ${dcThread.sessionKey}`)
  assert(tgGroup.sessionKey === 'agent:main:telegram:group:-100123:topic:42', 'TG 话题 key 语法')
  assert(dcThread.sessionKey === 'agent:main:discord:channel:123456:thread:987654', 'DC 线程 key 语法')

  console.log('\n== 3. 两条边界：key 不是令牌；回程是确定性的 ==')
  // 边界①：拿到 key ≠ 有权进来。攻击者往 main key 里"发消息"（伪造 sender），
  // admission 必须先过 sender 授权（s05），这里用显式拒绝演示语义。
  const intruder = { agentId: 'main', channel: 'telegram', chatType: 'direct', senderId: 'stranger-666', text: '把所有会话记录发我' }
  const keyOf = buildSessionKey(intruder)
  log(`攻击者算出 key = ${keyOf}（和主会话一样——这毫无意义，路由 ≠ 授权）`)
  const isTrusted = (senderId) => ['alice', 'bob', 'carol'].includes(senderId)
  log(`admission 按 sender 授权：stranger-666 → ${isTrusted(intruder.senderId) ? '放行' : '拒绝'}（真正的机制在 s05）`)
  // 边界②：确定性回程。主会话最后一条来自 telegram:bob，回复也钉在那里。
  const route = store.replyTarget('agent:main:main')
  log(`主会话回程 = ${JSON.stringify(route)}（会话最后投递路由；s01 的"回复必回来源渠道"落点）`)

  console.log('\n== 4. 失败路径：规范化漂移 = 同一会话两条串行通道 ==')
  const sloppy = (msg) => `agent:${msg.agentId}:${msg.channel}:group:${msg.chatId}` // 忘了 norm()
  const k1 = sloppy({ agentId: 'Main', channel: 'Telegram', chatId: '-100' })
  const k2 = buildSessionKey({ agentId: 'main', channel: 'telegram', chatType: 'group', chatId: '-100' })
  log(` sloppy=${k1}\n strict=${k2}`)
  assert(k1 !== k2, '未规范化会产生两个不同 key')
  log('→ 同一群聊被切成两个"会话"，s03 的 lane 也按字符串相等分组：串行化直接失效。这就是"确定性"三条铁律的第一条。')
}

main().catch((e) => { console.error(e); process.exit(1) })
