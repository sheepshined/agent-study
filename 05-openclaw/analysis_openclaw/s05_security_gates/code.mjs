#!/usr/bin/env node
/**
 * s05_security_gates.mjs —— 安全三道闸：dmPolicy 配对码 / 两层白名单 / exec 审批绑定
 *
 * 无人值守系统的安全设计必须回答：没有人在旁边说"不"的时候，谁来拒绝？
 * OpenClaw 的应对顺序是三拍（docs/gateway/security/trust-model.md:76-80）：
 *
 *   Identity first → Scope next → Model last（先定身份，再圈范围，最后才轮到模型）
 *
 * 第一道闸 dmPolicy（谁能私聊它，access-control.md:13-20）：
 *   pairing（默认）/ allowlist / open / disabled。
 *   pairing 下未知发送者拿到一条配对码，消息本身被忽略——机器人不理他；
 *   码 1 小时过期、每渠道最多 3 条待批；批准用 `openclaw pairing approve <channel> <code>`。
 *   审批结果当前写进共享 SQLite（pairing-store.ts:13/:296）——官方文档四页仍写
 *   "落盘 credentials/<channel>-allowFrom.json"，以源码为准。
 *
 * 第二道闸 两层白名单（DM 的 allowFrom + 群的 groups/groupAllowFrom）：
 *   检查顺序 groupPolicy → 激活方式；"回复机器人消息（隐式提及）不绕过
 *   groupAllowFrom"（access-control.md:34-38）。contextVisibility 再把
 *   "能触发"与"引用内容能否进模型"分开。
 *
 * 第三道闸 exec approvals（沙箱 agent 想在真实 host 跑命令的伴生护栏，
 *   docs/tools/exec-approvals.md:56-59 全文最硬的一段）：
 *   policy + allowlist +（可选）用户批准三者同时同意才执行，严格程度取
 *   tools.exec.* 与 approvals 的更严者；被批准的命令绑定 cwd、精确 argv、
 *   env 绑定、解析后真实路径（可写文件再加内容哈希）；等待期 PATH 上出现
 *   更早的可执行文件即拒绝；脚本类要绑唯一本地文件操作数，认不出就拒签。
 *
 *   入站消息 ─→ [闸1 dmPolicy] ─→ [闸2 两层白名单+提及门控] ─→ 变 run
 *   run 里要 exec ─→ [闸3 三重同意+审批绑定（cwd/argv/env/真实路径哈希）] ─→ 执行
 *
 * 运行：node code.mjs    （零依赖，离线）
 * 对照真实源码：src/pairing/pairing-store.ts:217/:285/:420/:439/:458、
 *   src/channels/direct-dm-guard-policy.ts:39、src/channels/command-gating.ts:20/:49/:71、
 *   src/channels/mention-gating.ts:157、src/agents/bash-tools.exec-approval-request.ts:373、
 *   src/infra/state-migrations.channel-pairing.ts:19（遗留 JSON 迁移）
 */

import { assert } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：第一道闸 —— dmPolicy 与 DM 配对码（pairing-store 的机制骨架）
// ---------------------------------------------------------------
const CODE_TTL_MS = 60 * 60 * 1000       // 码 1 小时过期
const MAX_PENDING_PER_CHANNEL = 3        // 每渠道最多 3 条待批

class MiniPairingStore {
  constructor() {
    this.pending = new Map()    // channel -> [{code, senderId, expiresAt}]
    this.allowFrom = new Map()  // channel -> Set<senderId>（真实实现落共享 SQLite）
  }
  /**
   * 未知 DM 发送者：发一条配对码，消息本身被忽略（返回值不带"进 run"的许可）。
   * 对应 upsertChannelPairingRequest（pairing-store.ts:285）。
   */
  issuePairingCode(channel, senderId, now = Date.now()) {
    const list = this.pending.get(channel) ?? []
    if (list.length >= MAX_PENDING_PER_CHANNEL) {
      return { ok: false, reason: `每渠道最多 ${MAX_PENDING_PER_CHANNEL} 条待批，先处理旧请求` }
    }
    const code = `OPENCLAW-${channel.slice(0, 3).toUpperCase()}-${Math.floor(1000 + Math.random() * 9000)}`
    list.push({ code, senderId, expiresAt: now + CODE_TTL_MS })
    this.pending.set(channel, list)
    return { ok: true, code, reply: `你的配对码是 ${code}（1 小时内有效）。请让管理员执行 openclaw pairing approve。` }
  }
  /** 批准配对码：码存在、未过期 → 发送者进 allowFrom。对应 approveChannelPairingCode（:420）。 */
  approveCode(channel, code, now = Date.now()) {
    const list = this.pending.get(channel) ?? []
    const idx = list.findIndex((p) => p.code === code)
    if (idx === -1) return { ok: false, reason: '配对码不存在（或已被批准/驳回）' }
    if (list[idx].expiresAt < now) { list.splice(idx, 1); return { ok: false, reason: '配对码已过期（1 小时），请重新发起' } }
    const senderId = list[idx].senderId
    list.splice(idx, 1)
    if (!this.allowFrom.has(channel)) this.allowFrom.set(channel, new Set())
    this.allowFrom.get(channel).add(senderId)
    return { ok: true, senderId }
  }
  isAllowed(channel, senderId) { return this.allowFrom.get(channel)?.has(senderId) ?? false }
}

/** dmPolicy 裁决：返回 null=放行进 run；返回字符串=回复话术并丢弃消息。 */
function dmGate(dmPolicy, channel, senderId, store) {
  switch (dmPolicy) {
    case 'open': return null
    case 'disabled': return '本渠道已停用私聊'
    case 'allowlist': return store.isAllowed(channel, senderId) ? null : '你不在白名单'
    case 'pairing':
    default:
      return store.isAllowed(channel, senderId) ? null : '配对流程' // 未知发送者 → 走配对
  }
}

// ---------------------------------------------------------------
// 第 2 部分：第二道闸 —— 群门控与两层白名单（mention-gating 的机制骨架）
// ---------------------------------------------------------------
/**
 * 群内消息的裁决顺序（真实实现在 runChannelTurn 管道里）：
 * ① groupPolicy 决定"这个群本身收不收"；② 群内发送者过 groupAllowFrom；
 * ③ 激活方式（@提及/回复）只是触发条件，不能替代授权——
 *   ★ 隐式提及（回复机器人消息）不绕过 groupAllowFrom。
 */
function groupGate({ groupPolicy, groupAllowFrom }, { senderId, activation, isReplyToBot }) {
  if (groupPolicy === 'open') return { ok: true, note: 'groupPolicy=open（官方文档里的示例配置，但安全面最宽）' }
  if (groupPolicy !== 'allowlist') return { ok: false, reason: `未知 groupPolicy: ${groupPolicy}` }
  const mention = activation === 'mention' || (activation === 'reply' && isReplyToBot)
  if (!mention) return { ok: false, reason: '未被提及/回复，非激活消息（不需要拒，只是不唤醒）' }
  if (!groupAllowFrom.includes(senderId)) {
    // 文档点名的一刀：隐式提及同样要过白名单。
    return { ok: false, reason: `激活了，但 ${senderId} 不在 groupAllowFrom（回复机器人不构成豁免）` }
  }
  return { ok: true }
}

// ---------------------------------------------------------------
// 第 3 部分：第三道闸 —— exec 审批绑定（exec-approval-request 的机制骨架）
// ---------------------------------------------------------------
/**
 * 审批背书（approval-backed run）绑定四件事；执行前重验，漂移即拒。
 * 对应 buildExecApprovalRequesterContext（:264）/ registerExecApprovalRequestForHostOrThrow（:373）。
 */
function mintExecApproval({ policyMode, allowlist, userApproved, command, resolvedExePath, exeContentHash, fileOperand }) {
  if (policyMode === 'deny') return { ok: false, reason: 'policy=deny：直接拒绝' }
  if (policyMode === 'allowlist' && !allowlist.includes(command[0])) {
    return { ok: false, reason: `policy=allowlist 且 '${command[0]}' 不在名单` }
  }
  if (!userApproved) return { ok: false, reason: '三重同意缺一：没有用户批准' }
  // ★ 脚本/解释器类：必须绑一个具体本地文件操作数；认不出唯一操作数 → 拒签
  //   审批背书（而不是假装全覆盖）。文档：File binding is best-effort。
  if (command[0] === 'bash' && !fileOperand) {
    return { ok: false, reason: '解释器类命令认不出唯一本地文件操作数 → 拒签审批背书' }
  }
  return {
    ok: true,
    binding: { argv: command, exePath: resolvedExePath, exeHash: exeContentHash, fileOperand: fileOperand ?? null },
  }
}
/** 执行前重验：等待审批期间 PATH/文件漂移 → 拒绝（:56-59 最硬的一条）。 */
function reverifyBeforeLaunch(binding, nowResolvedExePath, nowResolvedHash) {
  if (nowResolvedExePath !== binding.exePath) {
    return { ok: false, reason: `解析路径漂移：批准时 ${binding.exePath}，执行时 ${nowResolvedExePath}（PATH 上出现了更早的同名可执行文件？）` }
  }
  if (nowResolvedHash && nowResolvedHash !== binding.exeHash) {
    return { ok: false, reason: '可写可执行文件内容哈希变了 → 拒绝执行漂移内容' }
  }
  return { ok: true }
}

// ---------------------------------------------------------------
// 演示
// ---------------------------------------------------------------
async function main() {
  const log = (...a) => console.log(...a)

  console.log('== 1. 第一道闸：未知 DM → 配对码，消息被忽略（失败路径随后出现）==')
  const store = new MiniPairingStore()
  const gate1 = dmGate('pairing', 'telegram', 'stranger-666', store)
  log(`dmPolicy=pairing，未知发送者 → ${gate1 === null ? '放行' : '不进 run：' + gate1}`)
  const r = store.issuePairingCode('telegram', 'stranger-666')
  log(`配对码签发: ${r.code}（回复给发送者一条话术；这条消息本身不会触发 run）`)
  const approved = store.approveCode('telegram', r.code)
  log(`管理员批准 → ${JSON.stringify(approved)}；再次私聊 → ${dmGate('pairing', 'telegram', approved.senderId, store) === null ? '放行进 run' : '仍被拒'}`)
  // 失败路径①：过期码。
  const old = store.issuePairingCode('telegram', 'late-bird', Date.now() - 2 * 60 * 60 * 1000)
  log(`失败路径① 2 小时前签发的码再来批准 → ${JSON.stringify(store.approveCode('telegram', old.code))}`)
  // 失败路径②：待批上限。
  const store2 = new MiniPairingStore()
  for (let i = 0; i < 3; i++) store2.issuePairingCode('telegram', `spammer-${i}`)
  log(`失败路径② 第 4 条待批请求 → ${JSON.stringify(store2.issuePairingCode('telegram', 'spammer-4'))}`)

  console.log('\n== 2. 第二道闸：群白名单——回复机器人（隐式提及）不绕过 groupAllowFrom ==')
  const cfg = { groupPolicy: 'allowlist', groupAllowFrom: ['alice'] }
  log(`alice @机器人   → ${JSON.stringify(groupGate(cfg, { senderId: 'alice', activation: 'mention' }))}`)
  const eveReply = groupGate(cfg, { senderId: 'eve', activation: 'reply', isReplyToBot: true })
  log(`eve 回复机器人 → ${JSON.stringify(eveReply)}  ★激活不等于授权`)
  log(`非激活消息      → ${JSON.stringify(groupGate(cfg, { senderId: 'alice', activation: 'none' }))}`)

  console.log('\n== 3. 第三道闸：exec 审批——三重同意 + 四绑定 ==')
  const a1 = mintExecApproval({
    policyMode: 'allowlist', allowlist: ['npm'], userApproved: true,
    command: ['npm', 'test'], resolvedExePath: '/usr/local/bin/npm', exeContentHash: 'sha256-aa11',
  })
  log(`npm test 审批 → ok=${a1.ok}，绑定=${JSON.stringify(a1.binding)}`)
  const a2 = mintExecApproval({ policyMode: 'allowlist', allowlist: ['npm'], userApproved: false, command: ['npm', 'publish'] })
  log(`失败路径③ 名单在但无用户批准 → ${JSON.stringify(a2)}`)
  const a3 = mintExecApproval({ policyMode: 'allowlist', allowlist: ['npm', 'bash'], userApproved: true, command: ['bash'] })
  log(`失败路径④ 解释器类认不出唯一文件操作数 → ${JSON.stringify(a3)}`)

  console.log('\n== 4. 审批的"更严者"语义：等待期 PATH 漂移即拒（最硬的一条）==')
  log(`执行前重验（PATH 未漂移）→ ${JSON.stringify(reverifyBeforeLaunch(a1.binding, '/usr/local/bin/npm'))}`)
  const drifted = reverifyBeforeLaunch(a1.binding, '/home/attacker/.local/bin/npm')
  log(`失败路径⑤ 执行前解析到更早的 PATH 同名文件 → ${JSON.stringify(drifted)}`)
  const tampered = reverifyBeforeLaunch(a1.binding, '/usr/local/bin/npm', 'sha256-bb22')
  log(`失败路径⑥ 可写可执行文件内容哈希变化 → ${JSON.stringify(tampered)}`)
  assert(drifted.ok === false && tampered.ok === false, '漂移必须被拒')
  console.log('\n三拍回顾：Identity first（闸1）→ Scope next（闸2+3）→ Model last（爆炸半径已被圈定）。')
}

main().catch((e) => { console.error(e); process.exit(1) })
