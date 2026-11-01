#!/usr/bin/env node
/**
 * s04_permission_lattice.mjs —— mini 权限内核：三段优先级链 + alwaysAsk 通道 + 命令知识库
 *
 * 权限模式不是挡位开关。ZCode 的 5 值模式（session.port.ts:32）：
 *   plan | build | edit | yolo | auto      （没有 acceptEdits / bypassPermissions）
 *
 * checkPermission（permission/service.ts:114）把三类输入压成 allow|ask|deny，
 * 顺序即语义，分三段：
 *
 *   第 1 段 特殊通道（通道级，命中即返回，不看任何模式）
 *     · plan 模式切换特例 → requiresUserInteraction → ★ alwaysAsk（:367）
 *       alwaysAsk 是工具自报的"必须问人"：压过 yolo/plan 的放行（:357 注释），
 *       但压不过硬阻断 —— checkAlwaysAsk :377 先重跑 auto deny，:398 起看项目 deny。
 *
 *   第 2 段 模式与硬阻断（策略层）
 *     · auto → deny (:166)：未实现的档位绝不能被理解成"没有规则 = 放行"
 *     · yolo → 直通 (:156) —— 排在 disallowedTools (:171) 之前！
 *       头注释明说："yolo 下配置禁用清单不生效。这不是笔误，改它等于改契约。"
 *     · 项目 deny → 项目 ask
 *
 *   第 3 段 逐工具推导（plan / edit / build 各自的直通与要求）
 *     · 工具未声明 capability 时按"最坏假设"兜底（:630 resolveCapability）
 *
 * 决策对象带结构化 alwaysAsk 标记（:61/:88）—— PreToolUse hook 看得到它，
 * 所以"确认"不可被 hook 洗掉；会话级 allow 只存内存，重启即失效。
 *
 * Bash 另有一层命令知识库：generated/bash-command-registry.ts（1.9 MB，
 * @withfig/autocomplete 确定性生成 + sha256），HIGH_RISK_ROOT_COMMANDS + wrapper 穿透。
 *
 * 运行：node code.mjs        （零依赖，离线）
 * 对照真实源码：core/src/permission/service.ts、rule-matching.ts、
 *              core/src/tool/handlers/bash-command-permission-policy.ts
 */

import { deepFreeze, assert, banner } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：决策对象 —— 结构化 + 冻结（hook 只能读，不能洗）
// ---------------------------------------------------------------
function makeDecision(decision, ruleId, extra = {}) {
  return deepFreeze({ decision, ruleId, ...extra })
}

// ---------------------------------------------------------------
// 第 2 部分：mini 权限内核 —— 顺序即语义
// ---------------------------------------------------------------
class PermissionService {
  /**
   * @param cfg { mode, planEnabled, disallowedTools:Set, projectRules:{deny:Set,ask:Set,allow:Set},
   *              sessionAllows:Set }   —— 会话级 allow 只存内存（真实代码 :88）
   */
  constructor(cfg) { this.cfg = cfg }

  checkPermission(tool, args) {
    const cap = this.capability(tool)
    const c = this.cfg

    // ── 第 1 段：特殊通道 ──────────────────────────────────────
    if (cap.requiresUserInteraction) {
      return makeDecision('ask', 'channel.requires_user_interaction')
    }
    if (cap.alwaysAsk) {
      // checkAlwaysAsk（:367）：ask 压过所有"放行"分支，但要先重跑硬阻断。
      const r = this.checkAlwaysAsk(tool, cap, args)
      if (r) return r // 否则继续往下走逐工具推导（它最终仍会落 ask，见 capability.needsApproval）
    }

    // ── 第 2 段：模式与硬阻断 ─────────────────────────────────
    if (c.mode === 'auto') {
      // :166 —— 占位档位直接 deny，排在所有规则匹配之前
      return makeDecision('deny', 'mode.auto.unimplemented',
        { reason: 'Auto mode is reserved but not implemented yet' })
    }
    // :156 yolo 直通 —— 刻意排在 disallowedTools 之前（"改它等于改契约"）
    if (c.mode === 'yolo' && !c.planEnabled) {
      if (cap.alwaysAsk) return makeDecision('ask', 'tool.alwaysAsk', { alwaysAsk: true })
      return makeDecision('allow', 'mode.yolo')
    }
    if (c.disallowedTools.has(tool.name)) {
      return makeDecision('deny', 'config.disallowed_tools')
    }
    if (c.projectRules.deny.has(tool.name)) {
      return makeDecision('deny', 'project.rule_deny')
    }
    if (c.projectRules.ask.has(tool.name)) {
      return makeDecision('ask', 'project.rule_ask')
    }

    // ── 第 3 段：逐工具推导 ───────────────────────────────────
    if (c.mode === 'plan') {
      return cap.sideEffectScope === 'none'
        ? makeDecision('allow', 'plan.read_only')
        : makeDecision('ask', 'plan.write_requires_ask')
    }
    if (c.mode === 'edit' && cap.sideEffectScope === 'workspace') {
      return makeDecision('allow', 'edit.workspace_write')
    }
    if (c.mode === 'build') {
      return makeDecision('allow', 'build.default')
    }
    // 默认最保守：不知道就问人
    return makeDecision('ask', 'fallback.unclassified')
  }

  /** checkAlwaysAsk 的 mini 版（:367）：先重跑"压得过 alwaysAsk 的硬阻断"，再落 ask */
  checkAlwaysAsk(tool, cap, args) {
    const c = this.cfg
    if (c.mode === 'auto') {
      // :377 —— 通道也压不过 auto 占位。注意 deny 上也带 alwaysAsk 标记（真实代码 :70-75：
      // 标记跟着 capability 走，不只 ask 才有）—— 下游据此知道"这个调用源自一条 alwaysAsk 声明"
      return makeDecision('deny', 'mode.auto.unimplemented', { alwaysAsk: true })
    }
    if (c.projectRules.deny.has(tool.name)) {
      return makeDecision('deny', 'project.rule_deny', { alwaysAsk: true }) // 通道压不过项目 deny
    }
    return makeDecision('ask', 'tool.alwaysAsk', { alwaysAsk: true })
  }

  /** capability 的 mini 版（resolveCapability :630）：声明缺失按最坏假设兜底 */
  capability(tool) {
    return {
      alwaysAsk: tool.alwaysAsk ?? false,
      requiresUserInteraction: tool.requiresUserInteraction ?? false,
      sideEffectScope: tool.sideEffectScope ?? 'workspace',   // 未声明 → 当成有副作用
    }
  }
}

// ---------------------------------------------------------------
// 第 3 部分：mini 命令知识库（真实版 1.9 MB 确定性生成，这里只放 40 条示意）
// ---------------------------------------------------------------
const READ_ONLY_COMMANDS = new Set([
  'ls', 'cat', 'head', 'tail', 'grep', 'rg', 'find', 'pwd', 'which', 'whoami',
  'git status', 'git log', 'git diff', 'git show', 'git branch', 'git blame',
  'node --version', 'npm ls', 'python --version', 'echo',
  ...Array.from({ length: 20 }, (_, i) => `readonly_cmd_${i}`), // 凑足 40 条，示意"知识库规模"
])
const HIGH_RISK_ROOT_COMMANDS = new Set(['bash', 'chmod', 'dd', 'mount', 'rm', 'sudo', 'sh']) // :16-33 的 mini 集

/** 解析命令首段（真实代码由 bash-command-parser.ts + rule-evaluator.ts 完成） */
export function classifyBashCommand(cmdline) {
  const segs = cmdline.trim().split(/\s+/)
  const head = segs[0]
  if (HIGH_RISK_ROOT_COMMANDS.has(head)) return { verdict: 'ask', ruleId: 'bash.high_risk_root' }
  // wrapper 穿透：sudo git status 的主体按 wrapper 后的命令算，且 sudo 本身高危
  const twoWord = segs.slice(0, 2).join(' ')
  if (READ_ONLY_COMMANDS.has(twoWord) || READ_ONLY_COMMANDS.has(head)) {
    return { verdict: 'readonly-eligible', ruleId: 'bash.readonly_registry' }
  }
  return { verdict: 'ask', ruleId: 'bash.unclassified' }
}

// ---------------------------------------------------------------
// 第 4 部分：main() —— 四个场景
// ---------------------------------------------------------------
async function main() {
  const terminalWrite = { name: 'terminal_write', alwaysAsk: true }        // 自报"必须问人"
  const readFile = { name: 'read_file', sideEffectScope: 'none' }
  const writeFile = { name: 'write_file', sideEffectScope: 'workspace' }

  banner('场景 1：三段链 —— 顺序即语义')
  const svc = new PermissionService({
    mode: 'build', planEnabled: false,
    disallowedTools: new Set(['write_file']),
    projectRules: { deny: new Set(), ask: new Set(), allow: new Set() },
    sessionAllows: new Set(),
  })
  for (const [t, label] of [[readFile, '只读'], [writeFile, '写在禁用清单'], [{ name: 'mystery_tool' }, '未声明能力']]) {
    const d = svc.checkPermission(t, {})
    console.log(`  ${String(label).padEnd(12)} ${t.name.padEnd(14)} → ${d.decision.padEnd(5)} (${d.ruleId})`)
  }
  console.log('  注：build 模式下 disallowedTools 拦得住；下个场景看 yolo 模式下它拦不住 ——')

  banner('场景 2：yolo 与 disallowed 的次序（:156 vs :171）+ alwaysAsk 通道')
  const yolo = new PermissionService({
    mode: 'yolo', planEnabled: false,
    disallowedTools: new Set(['write_file']),
    projectRules: { deny: new Set(['terminal_write']), ask: new Set(), allow: new Set() },
    sessionAllows: new Set(),
  })
  const d1 = yolo.checkPermission(writeFile, {})
  console.log(`  yolo + 禁用清单含 write_file → ${d1.decision} (${d1.ruleId}) ← 禁用清单不生效：这不是笔误`)
  const d2 = yolo.checkPermission(terminalWrite, {})
  console.log(`  yolo + alwaysAsk 工具（项目 deny）→ ${d2.decision} (${d2.ruleId}, alwaysAsk=${!!d2.alwaysAsk}) ← 通道压不过硬阻断`)
  const buildSvc = new PermissionService({
    mode: 'build', planEnabled: false, disallowedTools: new Set(),
    projectRules: { deny: new Set(), ask: new Set(), allow: new Set() }, sessionAllows: new Set(),
  })
  const d3 = buildSvc.checkPermission(terminalWrite, {})
  console.log(`  build + alwaysAsk 工具 → ${d3.decision} (${d3.ruleId}) ← 通道压过模式放行`)
  assert(d2.decision === 'deny' && d3.decision === 'ask', 'alwaysAsk 语义')

  banner('场景 3：命令知识库 —— 只读免批 / 高危必问 / wrapper 穿透')
  for (const cmd of ['git status', 'ls -la', 'rm -rf tmp', 'sudo git status', 'node --version']) {
    const v = classifyBashCommand(cmd)
    console.log(`  ${cmd.padEnd(16)} → ${v.verdict.padEnd(17)} (${v.ruleId})`)
  }

  banner('场景 4：失败路径 —— auto 占位即 deny；hook 洗不掉确认')
  const autoSvc = new PermissionService({
    mode: 'auto', planEnabled: false, disallowedTools: new Set(),
    projectRules: { deny: new Set(), ask: new Set(), allow: new Set() }, sessionAllows: new Set(),
  })
  const d4 = autoSvc.checkPermission(readFile, {})
  console.log(`  auto 模式 + 只读工具 → ${d4.decision} (${d4.ruleId}) ← 未实现档位绝不"没规则=放行"`)
  // hook 尝试洗白：PreToolUse hook 收到的是冻结决策，改写 ask→allow 直接被拒
  const hookReceives = buildSvc.checkPermission(terminalWrite, {})
  let blocked = false
  try { hookReceives.decision = 'allow' } catch { blocked = true } // 冻结对象 → 抛错
  console.log(`  hook 洗白 ask→allow: ${blocked ? '被冻结拒绝' : '竟然成功'}；决策带 alwaysAsk=${!!hookReceives.alwaysAsk} 标记，hook 侧契约禁止抹掉`)
  assert(blocked, '决策对象必须冻结')

  console.log('\n结论：模式是策略不是赦免；alwaysAsk 通道压过放行、压不过阻断；知识库让"只读免批"成规模。')
}

main().catch((e) => { console.error(e); process.exit(1) })
