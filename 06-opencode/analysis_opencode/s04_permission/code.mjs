#!/usr/bin/env node
/**
 * s04_permission.mjs —— 权限：{permission, pattern, action} + findLast 双通配求值
 *
 * OpenCode 的整个权限系统建立在一个极小的数据结构与一行求值式上：
 *
 *   Rule    = { permission: string,   // 权限键：bash / read / edit / doom_loop ...
 *               pattern: string,      // 通配模式（glob）：* / npm run * / *.env
 *               action: "allow" | "deny" | "ask" }
 *   Ruleset = Rule[]                  // 多条规则，顺序有意义
 *
 *   evaluate(permission, pattern, ...rulesets):      // permission/index.ts:44-52
 *     return rulesets.flat().findLast(rule =>
 *       Wildcard.match(permission, rule.permission) &&
 *       Wildcard.match(pattern, rule.pattern)
 *     ) ?? { action: "ask" }          // ← 无匹配默认弹窗："未知即 ask"
 *
 *   两个要点：
 *   · findLast 取"最后一条命中的规则" ⇒ 后写覆盖先写 ⇒ 五层叠加
 *     （defaults → agent 特例 → config → session → CLI）只是"按顺序传参"
 *   · Wildcard.match 是"双通配"：permission 键与 pattern 都要命中
 *
 * 审批运行时（ask/reply 状态机，:67-167）：
 *   deny → 立即失败；ask → 发 permission.asked 事件 + Deferred.await 挂起整轮；
 *   reply once/always/reject —— reject 会级联拒绝同 session 全部 pending，
 *   always 写进程内 approved 并自动放行已满足的其他 pending。
 *
 * 运行：node code.mjs   （零依赖，离线）
 * 对照真实源码：packages/opencode/src/permission/index.ts（evaluate/ask/reply）
 *              packages/schema/src/v1/permission.ts（Rule/Reply 权威定义）
 *              packages/core/src/util/wildcard.ts（通配匹配）
 *              packages/opencode/src/agent/agent.ts:119-136（默认 ruleset）
 */

import { wildcardMatch as match } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：求值式（permission/index.ts:44-52 的逐字 mini 版）
// ---------------------------------------------------------------
function evaluate(permission, pattern, ...rulesets) {
  return (
    rulesets
      .flat() // 五层拍平成一个数组——后面 findLast 只认顺序，不认层
      .findLast((rule) => match(permission, rule.permission) && match(pattern, rule.pattern)) ?? {
      action: 'ask',
      permission,
      pattern: '*',
    }
  )
}

const rule = (permission, pattern, action) => ({ permission, pattern, action })

// ---------------------------------------------------------------
// 第 2 部分：审批状态机（ask/reply 的 mini 版）
// ---------------------------------------------------------------
// pending: Map<审批ID, {permission, pattern, resolve}>；approved: 已 always 放行的规则。
// "挂起"用未 resolve 的 Promise——这正是 Effect.Deferred.await 的原始形态。
class PermissionService {
  constructor() {
    this.pending = new Map()
    this.approved = [] // always 的落点：进程内存，不落 config（重启即失效）
    this.events = []
    let uid = 0
    this.nextId = () => `perm-${++uid}`
  }

  /** ask：逐条求值。deny 立即失败；allow 直接放行；ask 发事件并挂起。 */
  async ask(permission, pattern, ...rulesets) {
    const verdict = evaluate(permission, pattern, ...rulesets)
    if (verdict.action === 'deny') return { status: 'denied', rule: verdict }
    if (verdict.action === 'allow') return { status: 'allowed', rule: verdict }
    // always 缓存命中：上次点了"总是允许"，这次直接过
    const cached = this.approved.find((r) => match(permission, r.permission) && match(pattern, r.pattern))
    if (cached) return { status: 'allowed', rule: cached, via: 'always-cache' }
    this.events.push({ type: 'permission.asked', permission, pattern })
    return await new Promise((resolve) => {
      this.pending.set(this.nextId(), { permission, pattern, resolve })
    })
  }

  /** reply：once 只放行当前一条；always 放行并收编缓存 + 自动放行同 pattern 的其他 pending；
   *  reject 级联拒绝同 session 全部 pending（mini 版：全部 pending）。 */
  reply(id, replyKind) {
    const entry = this.pending.get(id)
    if (!entry) throw new Error(`无此 pending: ${id}`)
    if (replyKind === 'always') {
      this.approved.push(rule(entry.permission, entry.pattern, 'allow'))
      for (const [pid, p] of [...this.pending]) {
        if (match(p.permission, entry.permission) && match(p.pattern, entry.pattern)) {
          p.resolve({ status: 'allowed', via: 'always-cascade' })
          this.pending.delete(pid)
        }
      }
    }
    if (replyKind === 'reject') {
      // 级联：用户拒绝一个，同 session 排队的全部拒绝——不给模型"下一个也许能过"的假象
      for (const [pid, p] of [...this.pending]) {
        p.resolve({ status: 'rejected', cascaded: pid !== id })
        this.pending.delete(pid)
      }
    }
  }
}

// ---------------------------------------------------------------
// 第 3 部分：演示
// ---------------------------------------------------------------
async function main() {
  console.log('== 场景 1：findLast 语义 —— 后写覆盖先写 ==')
  const ruleset = [
    rule('read', '*.env', 'ask'), // 先写：读 .env 弹窗
    rule('read', '*.env', 'allow'), // 后写：又允许了 → 取这条
  ]
  console.log(`    evaluate('read', '.env', 规则集) → ${JSON.stringify(evaluate('read', '.env', ruleset))}`)
  console.log('    → flat() 后 findLast 只认顺序：同一层内的先后、跨层的先后，机制完全相同')

  console.log('\n== 场景 2：五层叠加 —— npm test 与 read .env 的判定逐层演变 ==')
  // 对齐 agent/agent.ts:119-136 的默认 ruleset（形态即产品取向）：
  // "*":allow、doom_loop:ask、question/plan_enter/plan_exit:deny、
  // read 对 *.env / *.env.* 弹窗但 *.env.example 放行（镜像 gitignore 语义）。
  // （external_directory 默认 ask + 白名单 allow，此处从简未列）
  const defaults = [
    rule('*', '*', 'allow'),
    rule('doom_loop', '*', 'ask'),
    rule('question', '*', 'deny'),
    rule('read', '*.env', 'ask'),
    rule('read', '*.env.*', 'ask'),
    rule('read', '*.env.example', 'allow'),
  ]
  const agentLayer = [rule('bash', 'npm run *', 'deny')] // 这个 agent 不许跑 npm run 系列
  const configLayer = [rule('bash', 'npm run test', 'allow')] // 用户给 test 开了白名单
  const sessionLayer = [rule('bash', '*', 'ask')] // 会话参数临时收紧所有 bash

  const show = (label, ...layers) => {
    const npm = evaluate('bash', 'npm run test', ...layers)
    const env = evaluate('read', '.env', ...layers)
    const example = evaluate('read', '.env.example', ...layers)
    console.log(`    ${label.padEnd(26)} npm test→${npm.action.padEnd(5)} .env→${env.action.padEnd(5)} .env.example→${example.action}`)
  }
  show('defaults', defaults)
  show('+ agent 特例(deny npm run *)', defaults, agentLayer)
  show('+ 用户 config(allow test)', defaults, agentLayer, configLayer)
  show('+ session 级(bash 全 ask)', defaults, agentLayer, configLayer, sessionLayer)
  console.log('    → 每层只是往参数表尾部追加规则；findLast 让后面的层天然覆盖前面的层')

  console.log('\n== 场景 3：ask/reply 状态机 —— always 收编缓存 / reject 级联 ==')
  // 剧情一：两个审批用同一个 pattern（模型一轮里两次触达同一敏感文件），
  // 对第一个点 always → 第二个被自动放行；之后再触发同 pattern 审批 → 走缓存直接过
  let svc = new PermissionService()
  const a = svc.ask('read', '.env', defaults)
  const b = svc.ask('read', '.env', defaults)
  const ids = [...svc.pending.keys()]
  console.log(`    两个同 pattern 审批挂起: ${ids.join(', ')}（Deferred.await 中，模型整轮停在这）`)
  svc.reply(ids[0], 'always')
  console.log(`    第一个点 always → ${JSON.stringify(await a)}`)
  console.log(`    第二个被自动放行 → ${JSON.stringify(await b)}`)
  console.log(`    之后再 ask 同 pattern → ${JSON.stringify(await svc.ask('read', '.env', defaults))}（approved 缓存，不再弹窗）`)
  // 剧情二：reject 级联拒绝全部 pending
  svc = new PermissionService()
  const c = svc.ask('read', '.env', defaults)
  const d = svc.ask('read', '.env.production', defaults) // 匹配 defaults 的 *.env.* → ask
  const ids2 = [...svc.pending.keys()]
  console.log(`    换剧情：两个审批挂起 ${ids2.join(', ')}，对第一个点 reject`)
  svc.reply(ids2[0], 'reject')
  console.log(`    → .env            : ${JSON.stringify(await c)}`)
  console.log(`    → .env.production : ${JSON.stringify(await d)}（级联，不给"下一个也许能过"的假象）`)

  console.log('\n== 场景 4：未知即弹窗 + 兜底优先级 ==')
  console.log(`    evaluate('doom_loop', '*', defaults) → ${JSON.stringify(evaluate('doom_loop', '*', defaults))}`)
  console.log('    → doom_loop（最近 3 个 part 同工具+同参数的死循环检测）在 defaults 里就是 ask；')
  console.log('      若某键连规则都没有，evaluate 的 ?? {action:"ask"} 兜底同样交给用户——')
  console.log('      安全默认值不是 allow，"未知即 ask" 写在求值式最后一行')

  console.log('\n结论：一条 findLast 双通配求值式 + 五层按序传参 + reject 级联，')
  console.log('就是 OpenCode 权限系统的全部骨架；剩余复杂度都在"pattern 怎么生成"（tree-sitter + arity 字典）。')
}

main().catch((e) => { console.error(e); process.exit(1) })
