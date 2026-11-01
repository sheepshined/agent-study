#!/usr/bin/env node
/**
 * s08_dynamic_workflow.mjs —— mini DWF 信任链：静态守门 → taint 不动点 → vm realm
 *
 * ZCode 独有的编排形态：主 agent 对着 TS facade 写脚本，编译器恢复严格性，
 * 子进程 vm.createContext 独立 realm 执行，NDJSON 桥回宿主，journal 落 dwf_* 表。
 *
 * 本课 mini 版四层信任链（真实实现对应物写在每段注释里）：
 *
 *   ① facade.dts —— 模型可见 API 的唯一事实源
 *      （dynamic-workflow/src/facade/dts.ts：嵌入字符串资产，纯库无 I/O）
 *
 *   ② staticCheck —— 编译期就死的东西
 *      禁词 require / process. / import( / eval / Function；无界 while 拒绝
 *      （compile.ts 虚拟宿主 typecheck；facade-misuse.ts 的 authoring diagnostics）
 *
 *   ③ taintFixpoint —— 污点分析（taint analysis）不动点
 *      world.run 的返回值 = 外部世界观察值 = 脏；沿赋值传播；
 *      脏值作为 agent.ask 的 prompt 参数 = 注入违例（外部数据不得变成给
 *      其他模型/子代理的指令）。循环到不动点，再做时序遍历
 *      （interpret.ts："taint fixpoint, then one temporal walk"；domain.ts AbstractValue）
 *
 *   ④ runInRealm —— vm.createContext 独立 realm
 *      只注入 __host + 必要 intrinsics；裸 vm context 天然没有
 *      process/require/Buffer/fetch；import() 抛 ERR_VM_DYNAMIC_IMPORT_CALLBACK_MISSING
 *      （child-source.ts 头注释；harness.ts spawn + NDJSON）
 *      ★ 本课用 Node 内置 vm 做教学演示，非安全边界 —— 真实 DWF 还叠加
 *        子进程边界 + NDJSON 协议白名单 + journal 审计，四层缺一不可。
 *
 *   ⑤ journal —— 每个节点调用追加 journal 行，失败是节点态不是进程态
 *      （migrations.ts 0019_dwf_journal：dwf_run/actor/node/event）
 *
 * 运行：node code.mjs        （零依赖，离线）
 * 对照真实源码：apps/zcode-cli/packages/dynamic-workflow 与 dynamic-workflow-runtime、
 *              apps/zcode-cli/packages/adapters/src/storage/session-store/migrations.ts:799
 */

import vm from 'node:vm'
import { assert, banner } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：facade —— 模型可见 API 的唯一事实源
// ---------------------------------------------------------------
/**
 * 真实实现是一份嵌入的 .d.ts 字符串（facade/dts.ts）。模型对着它写脚本，
 * 编译器对它 typecheck —— .d.ts 里没有的能力，模型"写不出来"（写了不过编译）。
 */
const FACADE_DTS = `
declare namespace workflow {
  function agent: {
    ask(actor: string, prompt: string): Promise<string>   // 派发给子代理
  }
  function world: {
    run(tool: string, args: object): Promise<unknown>     // 外部世界观察（读文件/查网页）
  }
  function log(msg: string): void
}
`

// ---------------------------------------------------------------
// 第 2 部分：静态守门 —— 编译期就该死的东西
// ---------------------------------------------------------------
const FORBIDDEN_PATTERNS = [
  [/\brequire\s*\(/, 'require() 不可用（realm 无 CommonJS）'],
  [/\bprocess\./, 'process 不可访问（realm 天然缺失）'],
  [/\bimport\s*\(/, '动态 import 被禁（ERR_VM_DYNAMIC_IMPORT_CALLBACK_MISSING）'],
  [/\beval\s*\(/, 'eval 被禁'],
  [/\bFunction\s*\(/, '动态 Function 被禁'],
  [/\bfetch\s*\(/, 'fetch 不可用（ realm 无网络）'],
]

/** 无界 while 检测：while(true)/while(1) 且函数体内没有 break —— mini 启发式 */
function hasUnboundedLoop(script) {
  const m = script.match(/while\s*\(\s*(true|1|1===1)\s*\)/)
  if (!m) return false
  const after = script.slice(m.index)
  const bodyStart = after.indexOf('{')
  const bodyEnd = after.indexOf('}', bodyStart)
  return !after.slice(bodyStart, bodyEnd).includes('break')
}

/** 返回 null = 通过；返回 {code, reason} = 编译期拒绝（根本不进运行期） */
function staticCheck(script) {
  for (const [re, reason] of FORBIDDEN_PATTERNS) {
    if (re.test(script)) return { code: 9003, reason }
  }
  if (hasUnboundedLoop(script)) return { code: 9004, reason: '无界循环（while(true) 无 break）' }
  return null
}

// ---------------------------------------------------------------
// 第 3 部分：taint 不动点 —— 污点分析（interpret.ts "taint fixpoint" 的 mini 版）
// ---------------------------------------------------------------
/**
 * 站点收集 + 污点传播。污点域 { UNTAINTED | TAINTED }（真实版是 AbstractValue 代数）：
 *   · world.run(...) 的返回值 = TAINTED（外部观察值不可信）
 *   · TAINTED = TAINTED op 任何值 = TAINTED（赋值/拼接传播）
 *   · agent.ask(actor, <TAINTED prompt>) = 违例 9001（注入：外部数据不得指挥别的模型）
 * 循环到不动点：多遍扫描直到没有新的违例/新污染变量。
 */
function taintFixpoint(script) {
  const askRe = /agent\.ask\(\s*['"]([^'"]+)['"]\s*,\s*([^)]+)\)/g
  const worldRe = /(?:const|let|var)\s+(\w+)\s*=\s*(?:await\s+)?world\.run\(/g
  const tainted = new Set()
  const violations = []
  const seen = new Set() // 违例去重：不动点迭代会反复扫描同一 ask 站点
  for (let round = 1; round <= 5; round++) {
    const before = tainted.size + seen.size
    for (const m of script.matchAll(worldRe)) tainted.add(m[1])          // 污源
    // 传播：TAINTED 拼接过的模板串/变量（mini 版：模板串里引用了污变量 → 污串变量）
    for (const t of [...tainted]) {
      const propRe = new RegExp(`(?:const|let|var)\\s+(\\w+)\\s*=\\s*[^\n]*\\$\\{${t}\\}`, 'g')
      for (const m of script.matchAll(propRe)) tainted.add(m[1])
    }
    for (const m of script.matchAll(askRe)) {
      const [, actor, promptExpr] = m
      if ([...tainted].some((t) => promptExpr.includes(t))) {
        const key = `${actor}::${promptExpr}`
        if (!seen.has(key)) { seen.add(key); violations.push({ round, actor, code: 9001, why: 'prompt 含污点值（来自 world.run 的外部观察）' }) }
      }
    }
    if (tainted.size + seen.size === before) break                       // 不动点
  }
  return { tainted: [...tainted], violations }
}

// ---------------------------------------------------------------
// 第 4 部分：vm realm —— 只注入 __host（child-source.ts 头注释的 mini 版）
// ---------------------------------------------------------------
/**
 * 真实实现：vm.createContext 只含 ES intrinsics + __host；跨 realm 收敛
 * （脚本触及的 Promise/JSON/Error 都在 context 内构造，防原型污染）；
 * runFn 经 vm.runInContext 编译且不提供 importModuleDynamically 回调。
 * mini 版演示同样的"缺失物"：process/require 为 undefined，fetch 被禁。
 */
function runInRealm(script, host, { timeoutMs = 1000 } = {}) {
  const journal = []
  const __host = {
    ask: (actor, prompt) => { journal.push({ node: 'ask', actor, prompt }); return host.ask(actor, prompt) },
    run: (tool, args) => { journal.push({ node: 'world.run', tool, args }); return host.run(tool, args) },
    log: (msg) => journal.push({ node: 'log', msg }),
  }
  const sandbox = {
    // facade 的运行时形态：三个全局对象，背后是唯一的 __host（真实实现同构：
    // 脚本可见的 API 面被注入的 globals 钉死，__host 是唯一跨界出口）
    agent: { ask: __host.ask },
    world: { run: __host.run },
    workflow: { log: __host.log },
    console: { log: () => {} },
    // 注意：没有 process / require / Buffer / fetch —— 缺失本身就是设计
  }
  const context = vm.createContext(sandbox)
  const wrapped = `(async () => { ${script} })()`
  const value = vm.runInContext(wrapped, context, { timeout: timeoutMs })
  return { promise: Promise.resolve(value).then(() => journal), journal }
}

// ---------------------------------------------------------------
// 第 5 部分：journal（0019_dwf_journal 的 mini 版）
// ---------------------------------------------------------------
const journalTable = []   // 每行 { seq, runId, type, payload } —— dwf_event 的 mini 形状
function appendJournal(runId, type, payload) {
  journalTable.push({ seq: journalTable.length + 1, runId, type, payload })
  return journalTable.length
}

// ---------------------------------------------------------------
// 第 6 部分：main() —— 五个阶段
// ---------------------------------------------------------------
async function main() {
  banner('阶段 1：facade 与静态守门 —— 恶意脚本编译期死亡')
  const evil1 = `const fs = require('node:fs'); fs.readFileSync('/etc/passwd')`
  const evil2 = `while (true) { agent.ask('a', 'spam') }`
  for (const [i, s] of [evil1, evil2].entries()) {
    const verdict = staticCheck(s)
    console.log(`  恶意脚本#${i + 1} → ${verdict ? `拒绝 code=${verdict.code}（${verdict.reason}）` : '通过?!'}`)
    assert(verdict, '恶意脚本必须编译期拒绝')
  }
  console.log(`  facade 能力面（模型可见 API）：\n${FACADE_DTS.trim().split('\n').map((l) => '    ' + l.trim()).join('\n')}`)

  banner('阶段 2：taint 不动点 —— 外部观察值不得指挥子代理')
  const inject = `
    const page = await world.run('web_fetch', { url: 'https://example.com' })
    const summary = \`页面说: \${page}\`
    await agent.ask('writer', summary)        // 脏值进了 ask 的 prompt —— 注入！
    await agent.ask('writer', '请总结页面内容')  // 干净 prompt —— 合法
  `
  const t = taintFixpoint(inject)
  console.log(`  污点变量: ${JSON.stringify(t.tainted)}（world.run 产出 + 沿赋值传播）`)
  for (const v of t.violations) console.log(`  违例 code=${v.code} round=${v.round} ask(${v.actor}) ← ${v.why}`)
  assert(t.violations.length === 1, '只有脏 prompt 的 ask 是违例')
  console.log('  → 干净的 ask 照常放行：拦的是数据流，不是能力')

  banner('阶段 3：realm 执行 —— 缺失物清单与合法工作流')
  const host = {
    ask: async (actor, prompt) => `（${actor} 回复）关于: ${prompt.slice(0, 12)}…`,
    run: async (tool, args) => `（观察 ${tool}: ${JSON.stringify(args).slice(0, 20)}）`,
  }
  const legal = `
    const jobs = ['a', 'b', 'c'].map((name) => agent.ask(name, '翻译这段话'))
    const meta = await world.run('read_file', { path: 'meta.json' })
    workflow.log('fan-out 完成: ' + jobs.length + ' 个 ask 独立可并发')
    const results = await Promise.all(jobs)
    workflow.log('全部节点完成 ' + results.length)
  `
  const realm = runInRealm(legal, host)
  await realm.promise
  for (const j of realm.journal) console.log(`  [realm] ${JSON.stringify(j)}`)
  // 缺失物验证：realm 里 process/require 真的是 undefined
  const probe = runInRealm(`workflow.log(typeof process + '/' + typeof require + '/' + typeof fetch)`, host)
  await probe.promise
  console.log(`  [realm] process/require/fetch → ${JSON.stringify(probe.journal.at(-1).msg)}`)

  banner('阶段 4：失败节点落 journal —— 失败是节点态，不是进程态')
  const runId = 'run-1'
  appendJournal(runId, 'node_started', { actor: 'writer' })
  try {
    const bad = runInRealm(`throw new Error('子任务失败')`, host, { timeoutMs: 500 })
    await bad.promise
  } catch (e) {
    appendJournal(runId, 'node_failed', { error: e.message })
    console.log(`  节点失败已记录: ${JSON.stringify(journalTable.at(-1))}`)
  }
  appendJournal(runId, 'node_started', { actor: 'reviewer' })
  appendJournal(runId, 'node_finished', { actor: 'reviewer' })
  console.log(`  journal 共 ${journalTable.length} 行，可分页取数可回放（dwf_event 按 sequence）`)
  assert(journalTable.some((r) => r.type === 'node_failed'), '失败必须可见于 journal')

  console.log('\n结论：能力面靠 facade 钉死；数据流靠 taint 追；执行域靠 realm 封；失败靠 journal 记。')
}

main().catch((e) => { console.error(e); process.exit(1) })
