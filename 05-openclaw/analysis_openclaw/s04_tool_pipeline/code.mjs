#!/usr/bin/env node
/**
 * s04_tool_pipeline.mjs —— 工具面收窄：八层配置单调流水线 + 客户端能力裁剪
 *
 * run 开跑之前有个前置问题：模型这次到底能看到哪些工具？OpenClaw 把它拆成
 * 两处收窄（别混为一谈）：
 *
 *   A. 配置层单调收窄 —— tool-policy-pipeline.ts:66 buildDefaultToolPolicyPipelineSteps
 *      八层依次收窄（数组字面量的顺序即优先级）：
 *        1 profile（场景预设，tool-catalog 的 minimal/coding/messaging/full）
 *        2 tools.byProvider.profile   3 tools.allow   4 tools.byProvider.allow
 *        5 agents.<id>.tools.allow    6 agents.<id>.tools.byProvider.allow
 *        7 group tools.allow          8 tools.toolsBySender
 *      不变量：由粗到细，每层只能删不能加——后一层不能复活前一层删掉的工具；
 *      warning/审计按 step.label 归属到层，"最后一次排除"就是决定者。
 *
 *   B. 装配期可用性终化 —— openclaw-tools.ts:700
 *      finalizeAgentToolAvailability(filterToolsByClientCaps(allTools, clientCaps))
 *      客户端能力决定工具可用性：后端进程 flag 描述的是宿主，不是远端客户端——
 *      手机客户端没有画布，canvas 就不该进它的 prompt。
 *
 *   收窄发生在"进 prompt 的工具清单"层：少一个 schema 就少一份常驻 token，
 *   也少一次模型可尝试的误用面。
 *
 *   目录(约60) → ①profile → ②provider profile → ③allow → ④provider allow
 *              → ⑤agent allow → ⑥agent provider allow → ⑦group → ⑧sender
 *              → 客户端能力裁剪 → 进 prompt 的工具面 → 运行期 before_tool_call 终态闸
 *
 * 运行：node code.mjs    （零依赖，离线）
 * 对照真实源码：src/agents/tool-policy-pipeline.ts:66/:145、src/agents/tool-catalog.ts:38/:69、
 *   src/agents/openclaw-tools.ts:107/:700、src/agents/agent-tool-availability.ts、
 *   src/agents/tools/common.ts:38（requiredClientCaps）、
 *   src/agents/agent-tools.before-tool-call.policy.ts:117（runBeforeToolCallHook）
 */

import { deepFreeze, assert } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：权威工具目录（tool-catalog.ts 的 mini 版）
// ---------------------------------------------------------------
// 每个条目：分组 + profiles（哪些场景预设收它）+ requiredClientCaps。
// 注册即冻结：目录条目不可变（真实实现用 const + 只读类型表达同一纪律）。

const CATALOG = deepFreeze([
  { name: 'read',         group: 'fs',      profiles: ['coding'] },
  { name: 'write',        group: 'fs',      profiles: ['coding'] },
  { name: 'edit',         group: 'fs',      profiles: ['coding'] },
  { name: 'exec',         group: 'runtime', profiles: ['coding'] },
  { name: 'process',      group: 'runtime', profiles: ['coding'] },
  { name: 'web_search',   group: 'web',     profiles: ['coding', 'messaging'] },
  { name: 'message',      group: 'messaging', profiles: ['coding', 'messaging'] },
  { name: 'memory_search', group: 'memory', profiles: ['coding', 'messaging'] },
  { name: 'sessions_spawn', group: 'agents', profiles: ['coding'] },
  { name: 'cron',         group: 'automation', profiles: ['coding', 'messaging'] },
  { name: 'canvas',       group: 'ui',      profiles: ['coding'], requiredClientCaps: ['canvas'] },
  { name: 'screen',       group: 'ui',      profiles: ['coding'], requiredClientCaps: ['screen'] },
])

/** 场景预设（preset）：messaging 的模型看不到任何文件/执行工具——
 *  收窄发生在进 prompt 的清单层，不等运行时拒调用。 */
function toolsForProfile(catalog, profile) {
  return catalog.filter((t) => t.profiles.includes(profile))
}

// ---------------------------------------------------------------
// 第 2 部分：八层单调收窄流水线（tool-policy-pipeline.ts 的机制骨架）
// ---------------------------------------------------------------
/**
 * 每层 = { label, policy }。policy(tool) 返回 true=允许该层留下它。
 * 关键不变量①：层序即优先级，允许集只能做交集（单调收窄）——
 * 后一层 give-back 的"allow"绝不能把前一层删掉的捞回来。
 * 关键不变量②：诊断绑定 step.label——不许合并成一条无主人的汇总。
 */
function buildPipelineSteps({ profile, toolsAllow, agentAllow, senderAllow }) {
  const steps = []
  steps.push({ label: `tools.profile (${profile})`, policy: (t) => toolsForProfile(CATALOG, profile).some((p) => p.name === t.name) })
  steps.push({ label: 'tools.byProvider.profile', policy: () => true }) // mini：未配置 provider 维度 = 不收窄
  steps.push({ label: 'tools.allow', policy: (t) => !toolsAllow || toolsAllow.includes(t.name) })
  steps.push({ label: 'tools.byProvider.allow', policy: () => true })
  steps.push({ label: 'agent tools.allow', policy: (t) => !agentAllow || agentAllow.includes(t.name) })
  steps.push({ label: 'agent tools.byProvider.allow', policy: () => true })
  steps.push({ label: 'group tools.allow', policy: () => true })
  steps.push({ label: 'tools.toolsBySender', policy: (t) => !senderAllow || senderAllow.includes(t.name) })
  return steps
}

/** applyToolPolicyPipeline：逐层收窄 + 把排除原因记到层名上。 */
function applyToolPolicyPipeline(tools, steps) {
  const audit = []
  let surviving = tools
  for (const step of steps) {
    const kept = surviving.filter((t) => step.policy(t))
    for (const gone of surviving.filter((t) => !kept.includes(t))) {
      audit.push(`${gone.name} ← 被层 [${step.label}] 排除`)
    }
    surviving = kept
  }
  return { tools: surviving, audit }
}

// ---------------------------------------------------------------
// 第 3 部分：客户端能力裁剪 + 可用性终化（openclaw-tools.ts:700 的 mini 版）
// ---------------------------------------------------------------
/** 后端进程 flag 描述的是宿主，不是远端客户端：同一后端可同时服务手机和桌面。 */
function filterToolsByClientCaps(tools, clientCaps) {
  return tools.filter((t) => !t.requiredClientCaps || t.requiredClientCaps.every((c) => clientCaps.includes(c)))
}
function finalizeAgentToolAvailability(tools, clientCaps) {
  return deepFreeze(filterToolsByClientCaps(tools, clientCaps)) // 终化 = 再也不改
}

// ---------------------------------------------------------------
// 演示
// ---------------------------------------------------------------
async function main() {
  const log = (...a) => console.log(...a)

  console.log('== 1. messaging 预设：文件/执行工具整个消失 ==')
  const messagingNames = toolsForProfile(CATALOG, 'messaging').map((t) => t.name)
  log(`messaging 可见: ${messagingNames.join(' ')}`)
  assert(!messagingNames.includes('read') && !messagingNames.includes('exec'), 'messaging 不含 fs/runtime')
  log('→ 群聊助理的模型根本不知道有 read/exec 存在，而不是"试了再被拒"')

  console.log('\n== 2. 八层流水线：由粗到细，每层只能删不能加 ==')
  const steps = buildPipelineSteps({
    profile: 'coding',
    toolsAllow: ['read', 'write', 'edit', 'exec', 'web_search', 'message', 'memory_search', 'canvas', 'screen', 'cron'],
    agentAllow: ['read', 'write', 'edit', 'exec', 'message'],
    senderAllow: ['read', 'message'],
  })
  const { tools, audit } = applyToolPolicyPipeline(CATALOG, steps)
  log(`流水线后存活: ${tools.map((t) => t.name).join(' ')}`)
  log('排除审计（每条绑定到层）:')
  audit.forEach((a) => log(`  ${a}`))
  // 不变量验证：试图在细层"捞回"粗层删掉的工具是无效的——allow 集是交集。
  const attack = applyToolPolicyPipeline(CATALOG, buildPipelineSteps({ profile: 'messaging', toolsAllow: [...messagingNames, 'read'] }))
  log(`失败路径 → messaging profile 层删掉 read 后，细层 allow 名单写回 read 也无效: 存活 ${attack.tools.map((t) => t.name).join(' ')}`)
  assert(!attack.tools.some((t) => t.name === 'read'), '后层不能复活前层的删除')

  console.log('\n== 3. 客户端能力裁剪：同一后端，手机与桌面看到不同的面 ==')
  // 配置层只走到全局 allow（前 4 层）：agent/sender 的细粒度收窄是另一次维度，
  // 客户端能力裁剪与它们正交——同一份配置，不同客户端呈现不同工具面。
  const configNarrowed = applyToolPolicyPipeline(CATALOG, buildPipelineSteps({ profile: 'coding', toolsAllow: null }).slice(0, 4)).tools
  const desktop = finalizeAgentToolAvailability(configNarrowed, ['canvas', 'screen'])
  const mobile = finalizeAgentToolAvailability(configNarrowed, [])
  log(`桌面客户端: ${desktop.map((t) => t.name).join(' ')}`)
  log(`手机客户端: ${mobile.map((t) => t.name).join(' ')}（canvas/screen 需要呈现能力，不进手机 prompt）`)
  assert(desktop.length > mobile.length, '桌面可见面 ⊇ 手机可见面')
  log('availability ≠ authorization：这里只决定"进不进 prompt"，执行边界仍逐调用授权（s05）')

  console.log('\n== 4. 运行期最后一道闸：before_tool_call {block:true} 是终态 ==')
  // 模拟一个安全插件挂 before_tool_call：拦 exec。{block:true} 终态，
  // 低优先级处理器不再运行（agent-loop.md:99）。priority 越大越先跑。
  const hooks = [
    { name: 'audit', priority: 30, handler: (t) => { log(`  [audit] 观察到 ${t}`); return {} } },
    { name: 'security-guard', priority: 20, handler: (t) => (t === 'exec' ? { block: true, reason: 'exec 需走审批（s05）' } : {}) },
    { name: 'lazy-logger', priority: 10, handler: (t) => { log(`  [lazy-logger] 运行了 (${t})`); return {} } },
  ]
  for (const toolName of ['read', 'exec']) {
    log(`调用 ${toolName}:`)
    const sorted = [...hooks].sort((a, b) => b.priority - a.priority) // 优先级高先跑
    let blocked = null
    for (const h of sorted) {
      if (blocked) break // 终态已定：低优先级处理器被跳过
      const verdict = h.handler(toolName)
      if (verdict.block) { blocked = { hook: h.name, ...verdict }; log(`  [${h.name}] block:true → ${verdict.reason}`) }
    }
    if (blocked) log(`  终态: ${toolName} 被 ${blocked.hook} 阻断；后续处理器未执行`)
    else log(`  放行: 无处理器 block`)
  }
}

main().catch((e) => { console.error(e); process.exit(1) })
