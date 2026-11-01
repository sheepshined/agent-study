#!/usr/bin/env node
/**
 * s06_subagent.mjs —— 子代理：task 递归同一 runLoop + 权限只继承父 deny
 *
 * OpenCode 的子代理不是第二种引擎，而是同一个主循环的递归调用：
 *
 *   父 runLoop(session#1)
 *     └─ 模型发起 task(subagent_type:"explore", prompt:"...")
 *          ├─ ① 深度检查：沿 parentID 链上溯计数（task.ts:106-128，默认 1）
 *          ├─ ② 权限确认：ctx.ask({permission:"task", patterns:[type]})
 *          ├─ ③ 权限继承：deriveSubagentSessionPermission
 *          │      = 父 deny 规则 + external_directory 规则
 *          │      + (子自己没允许就 deny) todowrite / task
 *          │      ★ 父的 allow / ask 一律不下传 —— 委派不放大权限
 *          ├─ ④ sessions.create({ parentID, agent, permission })
 *          └─ ⑤ 递归调用同一个 runLoop(child)（task.ts:200-225）
 *                 └─ 结果：取子会话最后一段 text，包成
 *                    <task id=… state=completed><summary>…</summary>（:64-79）
 *
 *   深度链：session#1 (depth 0) ──task──▶ session#2 (depth 1)
 *   subagent_depth=1 时 session#2 再 task → "Subagent depth limit reached (1)"
 *
 * 运行：node code.mjs   （零依赖，离线）
 * 对照真实源码：packages/opencode/src/tool/task.ts（委派全流程）
 *              packages/opencode/src/agent/subagent-permissions.ts（27 行权限继承）
 *              packages/opencode/src/agent/agent.ts:140-265（内建 7 个 agent）
 */

// ---------------------------------------------------------------
// 第 0 部分：权限求值（s04 的精简版，本课自包含）
// ---------------------------------------------------------------
function wildcardMatch(input, pattern) {
  const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.')
  return new RegExp('^' + escaped + '$', 's').test(input)
}
function evaluate(permission, pattern, ...rulesets) {
  return (
    rulesets.flat().findLast((r) => wildcardMatch(permission, r.permission) && wildcardMatch(pattern, r.pattern)) ?? {
      action: 'ask',
      permission,
      pattern: '*',
    }
  )
}
const rule = (permission, pattern, action) => ({ permission, pattern, action })

// ---------------------------------------------------------------
// 第 1 部分：agent 注册表（agent.ts:140-265 的 mini 版）
// ---------------------------------------------------------------
const AGENTS = [
  { name: 'build', mode: 'primary', hidden: false },
  { name: 'plan', mode: 'primary', hidden: false },
  { name: 'general', mode: 'subagent', hidden: false },
  { name: 'explore', mode: 'subagent', hidden: false },
  { name: 'compaction', mode: 'primary', hidden: true },
  { name: 'title', mode: 'primary', hidden: true },
  { name: 'summary', mode: 'primary', hidden: true },
]

/** task 工具描述里的委派面：只列 mode=subagent 且未被 deny 的 agent
 *  （registry.ts:265-278 —— 模型看到的委派选项 = 权限求值的结果） */
function delegatableAgents(rules) {
  return AGENTS.filter((a) => a.mode === 'subagent').filter((a) => {
    const v = evaluate('task', a.name, rules)
    return v.action !== 'deny'
  })
}

// ---------------------------------------------------------------
// 第 2 部分：权限继承（agent/subagent-permissions.ts:10-27 的逐行 mini 版）
// ---------------------------------------------------------------
/**
 * 真实文件注释原话：只组合 (1) 父会话的 deny 规则与 external_directory 规则，
 * (2) 子自己的 ruleset 没允许 todowrite/task 时默认 deny。
 * 父的 allow 只管父代理自己；子代理的能力由子代理自己的 ruleset 决定。
 */
function deriveChildRuleset({ parentRuleset, subagentRuleset = [] }) {
  const canTask = subagentRuleset.some((r) => r.permission === 'task')
  const canTodo = subagentRuleset.some((r) => r.permission === 'todowrite')
  return [
    ...parentRuleset.filter((r) => r.permission === 'external_directory' || r.action === 'deny'),
    ...(canTodo ? [] : [rule('todowrite', '*', 'deny')]),
    ...(canTask ? [] : [rule('task', '*', 'deny')]),
  ]
}

// ---------------------------------------------------------------
// 第 3 部分：会话表 + runLoop（父子共用同一段循环代码）
// ---------------------------------------------------------------
const sessions = new Map() // id -> { id, parentID, depth, agent, messages[] }
const newSession = (parentID, agent, depth) => {
  const id = `session#${sessions.size + 1}`
  sessions.set(id, { id, parentID, depth, agent, messages: [] })
  return sessions.get(id)
}

/**
 * mini-runLoop：s01 的收束协议骨架（判停从简：按剧本走完即收）。
 * 关键点：父会话与子会话调用的是**同一个函数**——递归而非另起引擎。
 * 剧本里 type:"task" 的事件会递归触发子代理。
 */
async function runLoop(session, script, ctx) {
  console.log(`  [${session.id}] runLoop 开始（agent=${session.agent}, depth=${session.depth}）`)
  for (const step of script) {
    if (step.type === 'tool-call') {
      const brief = { ...step.args }
      delete brief.script // 剧本是 mock 注入，真实调用没有这个字段；打印时省略
      console.log(`  [${session.id}]   tool-call ${step.name}(${JSON.stringify(brief)})`)
      if (step.name === 'task') await taskTool(session, step, ctx)
      else step.result = `<${step.name} 结果>`
    } else if (step.type === 'text') {
      session.messages.push({ role: 'text', text: step.text })
      console.log(`  [${session.id}]   text: ${step.text}`)
    }
  }
  console.log(`  [${session.id}] runLoop 收束`)
}

/** task 工具本体（task.ts 的 mini 版）：深度检查 → 权限确认 → 建子会话 → 递归 */
async function taskTool(parent, step, ctx) {
  const subagentType = step.args.subagent_type

  // ① 深度检查：沿 parentID 链上溯（task.ts:106-128）
  let depth = 0
  let current = parent
  while (current.parentID) {
    current = sessions.get(current.parentID)
    depth++
  }
  if (depth >= ctx.config.subagent_depth) {
    step.result = `Subagent depth limit reached (${ctx.config.subagent_depth}). Increase "subagent_depth" to allow nested subagents.`
    console.log(`  [${parent.id}]   ✗ ${step.result}`)
    return
  }

  // ② 权限确认：task 键按 subagent_type 求 pattern（s04 的求值式）
  const verdict = evaluate('task', subagentType, parent.ruleset)
  console.log(`  [${parent.id}]   权限 task/${subagentType} → ${verdict.action}`)
  if (verdict.action === 'deny') {
    step.result = `Permission denied for task: ${subagentType}`
    return
  }

  // ③ 权限继承：只拿父的 deny + external_directory
  const subagentDef = AGENTS.find((a) => a.name === subagentType)
  const childRuleset = deriveChildRuleset({ parentRuleset: parent.ruleset })
  console.log(`  [${parent.id}]   子规则集: ${JSON.stringify(childRuleset.map((r) => `${r.permission}:${r.pattern}:${r.action}`))}`)

  // ④ 建子会话 + ⑤ 递归调用同一个 runLoop
  const child = newSession(parent.id, subagentType, depth + 1)
  console.log(`  [${parent.id}]   建子会话 ${child.id}（parentID=${parent.id}）→ 递归进入同一个 runLoop`)
  await runLoop(child, step.args.script, ctx)
  const summary = child.messages.filter((m) => m.role === 'text').at(-1)?.text ?? ''
  step.result = `<task id="${child.id}" state="completed"><summary>${summary}</summary></task>`
}

// ---------------------------------------------------------------
// 第 4 部分：演示
// ---------------------------------------------------------------
async function main() {
  console.log('== 场景 1：递归委派 —— explore 子代理跑完，结论包回父会话 ==')
  const parent = { ...newSession(null, 'build', 0), ruleset: [rule('*', '*', 'allow')] }
  const exploreScript = [
    { type: 'tool-call', name: 'grep', args: { pattern: 'runLoop' } },
    { type: 'text', text: '主循环在 session/prompt.ts:1081，260 行 while(true)，靠四条件收束。' },
  ]
  const parentScript = [
    { type: 'text', text: '我需要摸清主循环结构，委派 explore 去找。' },
    { type: 'tool-call', name: 'task', args: { subagent_type: 'explore', prompt: '找到 runLoop 的位置与退出条件', script: exploreScript } },
    { type: 'text', text: '收到，按子代理结论继续作答。' },
  ]
  await runLoop(parent, parentScript, { config: { subagent_depth: 1 } })
  console.log(`  父会话过程消息: ${parent.messages.map((m) => m.text.slice(0, 18)).join(' / ')}`)
  console.log(`  （task 工具结果 = ${parentScript[1].result.slice(0, 90)}...）`)
  console.log('  → 子会话的中间 grep 调用留在子会话日志里；父上下文只进 <task> 包裹的结论')

  console.log('\n== 场景 2：权限收敛 —— 父的 allow/ask 不下传，deny 死死跟住 ==')
  const parentRuleset = [
    rule('*', '*', 'allow'),
    rule('bash', 'git push *', 'deny'), // 父千辛万苦收窄的能力
    rule('webfetch', '*', 'ask'),
    rule('external_directory', '/tmp/*', 'allow'),
  ]
  const childRuleset = deriveChildRuleset({ parentRuleset })
  console.log(`    父规则集:    ${JSON.stringify(parentRuleset.map((r) => `${r.permission}:${r.pattern}:${r.action}`))}`)
  console.log(`    子规则集:    ${JSON.stringify(childRuleset.map((r) => `${r.permission}:${r.pattern}:${r.action}`))}`)
  console.log(`    父问 bash git push origin main → ${evaluate('bash', 'git push origin main', parentRuleset).action}`)
  console.log(`    子问 bash git push origin main → ${evaluate('bash', 'git push origin main', childRuleset).action}（deny 跟下来了）`)
  console.log(`    子问 bash npm test             → ${evaluate('bash', 'npm test', childRuleset).action}（父的 allow 没跟下来 → 落到默认 ask）`)
  console.log(`    子问 todowrite                 → ${evaluate('todowrite', '*', childRuleset).action}（自动 deny：子代理不记账）`)

  console.log('\n== 场景 3：深度限制 —— 子代理里再委派（失败路径）==')
  const child = { ...newSession(parent.id, 'explore', 1), ruleset: childRuleset }
  await taskTool(child, { name: 'task', args: { subagent_type: 'explore', prompt: '再钻一层' } }, { config: { subagent_depth: 1 } })

  console.log('\n== 场景 4：委派面 —— 模型在 task 描述里只看见 subagent 模式且未 deny 的 ==')
  console.log(`    无额外 deny: ${delegatableAgents([rule('*', '*', 'allow')]).map((a) => a.name).join(', ')}`)
  console.log(`    deny explore 后: ${delegatableAgents([rule('*', '*', 'allow'), rule('task', 'explore', 'deny')]).map((a) => a.name).join(', ')}`)
  console.log('    （build/plan 是 primary、compaction/title/summary 是 hidden，永远不进委派面）')

  console.log('\n结论：task = 深度检查 + 权限确认 + deny 继承 + 建子会话 + 递归同一 runLoop；')
  console.log('过程不可见、结论可见，委派不放大权限。')
}

main().catch((e) => { console.error(e); process.exit(1) })
