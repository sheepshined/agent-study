#!/usr/bin/env node
/**
 * s03_tool_dual_schema.mjs —— 工具双轨 schema + 契约投影 + 流中执行闸门
 *
 * 模型报出的 tool call 是不可信输入。ZCode 的三道工程决策：
 *
 *   1. 双轨 schema（contracts/src/tools/bash.ts）
 *      · zod schema :6      —— Node 内部：运行时校验 + TS 类型推导（随代码演进）
 *      · 手写 JSON Schema:76 —— 下发 provider 的字节级稳定契约（护 prompt cache）
 *      · 两轨不互相派生：执行端 validation.ts 先试 zod，再退 JSON Schema
 *
 *   2. 声明即契约（core/src/tool/registry.ts:122 toContracts）
 *      · readOnly / destructive / concurrentSafe / sideEffectScope / needsApproval
 *        全部随契约投影——权限系统与流式闸门只读声明，不猜调用点
 *      · 投影冻结 + execute 显式置空（跨 provider 边界不能带函数）
 *      · alias→canonical 冲突保护在 register :47（Agent↔Task 见 compat.ts）
 *
 *   3. 边流式边执行（runtime/methods/streaming-tool-coordinator.ts:376）
 *      · 模型还在吐 tool call 时，满足六条件的只读工具立即开跑
 *      · readOnly && concurrentSafe && !destructive && !needsApproval
 *        && !requiresUserInteraction && sideEffectScope === "none"
 *      · ★ 任何一项 undefined → false："未知即不跑"——审批绝不被提前执行绕过
 *      · 失败也是结果：早退合成错误回灌模型（call-runner.ts 头注释），日志无空洞
 *
 *   模型流式输出：
 *      t=0  ─┬─ tool_call read_file      ── 闸门全绿 → 立即开跑（重叠 40ms）
 *            ├─ tool_call bash           ── sideEffectScope=workspace → 等流结束
 *            ├─ tool_call ask_user       ── needsApproval → 等
 *            └─ tool_call unknown_tool   ── registry miss → 等后合成错误结果
 *
 * 运行：node code.mjs        （零依赖，离线；zod 用手写校验函数模拟语义）
 * 对照真实源码：contracts/src/tools/bash.ts、core/src/tool/registry.ts、
 *              core/src/tool/executor/{validation,call-runner}.ts、streaming-tool-coordinator.ts
 */

import { deepFreeze, assert, banner } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：双轨定义 —— 两个消费者，两份 schema，不互相派生
// ---------------------------------------------------------------
/**
 * defineTool({ name, validate, jsonSchema, ...metadata })
 *   validate    —— 运行时校验（真实代码是 zod safeParse）
 *   jsonSchema  —— 下发 provider 的契约（真实代码是手写 toToolJsonSchema 产物）
 *   两者是同一"真相"的两种投影，但**演进速度相反**：内部可以重构，外部一变就烧缓存。
 */
function defineTool(spec) { return spec }

// ---------------------------------------------------------------
// 第 2 部分：注册表 —— alias→canonical + 契约投影
// ---------------------------------------------------------------
class ToolRegistry {
  constructor() {
    this.tools = new Map()   // canonical name -> definition
    this.aliases = new Map() // alias -> canonical
  }

  register(tool) {
    // 真实代码 registry.ts:47：别名冲突时"拒绝新别名、保留已注册身份"，绝不静默覆盖——
    // 静默覆盖会把一次调用送到错误的 handler 和错误的权限档位。
    for (const alias of tool.aliases ?? []) {
      if (this.tools.has(alias)) throw new Error(`[register] 别名 ${alias} 与已有 canonical 冲突，拒绝注册`)
      this.aliases.set(alias, tool.name)
    }
    this.tools.set(tool.name, deepFreeze(tool))
    return () => { this.tools.delete(tool.name) } // 注销可逆（s01 纪律）
  }

  /** 别名解析只此一处：此后事件、权限、日志再没有第二套名字 */
  resolve(name) {
    const canonical = this.aliases.get(name) ?? name
    return { canonical, tool: this.tools.get(canonical) ?? null }
  }

  /** 契约投影（registry.ts:122 的 mini 版）：冻结 + execute 置空 */
  toContracts() {
    return [...this.tools.values()]
      .filter((t) => t.providerVisible !== false)
      .map((t) => deepFreeze({
        name: t.name,
        description: t.description,
        inputJsonSchema: t.jsonSchema,     // ← 下发的是手写 JSON Schema，不是 zod
        readOnly: t.readOnly,
        destructive: t.destructive,
        concurrentSafe: t.concurrentSafe,
        sideEffectScope: t.sideEffectScope,
        needsApproval: t.needsApproval,
        execute: undefined,                // 显式置空：跨边界对象不能带函数
      }))
  }
}

// ---------------------------------------------------------------
// 第 3 部分：流中执行闸门（streaming-tool-coordinator.ts:376 的 mini 版）
// ---------------------------------------------------------------
/**
 * 六条件全过才允许"模型还在流式输出时"提前执行。
 * 真实代码注释自陈：这是"整个提前执行设计唯一的安全边界"。
 * 实现要点（对齐真实代码的判定形状）：
 *   · readOnly / concurrentSafe 必须严格 === true —— 忘了声明(undefined)直接拦下
 *   · sideEffectScope 必须严格 === "none" —— 忘了声明同样拦下
 *   · destructive / needsApproval / requiresUserInteraction 是"声明了 true 就拦"
 * 三处严格等号合起来就是"未知即不跑"：一个没写全声明的工具永远进不了流中快道。
 */
function shouldExecuteDuringStream(tool) {
  if (!tool) return false
  return (
    tool.readOnly === true &&
    tool.concurrentSafe === true &&
    !tool.destructive &&
    !tool.needsApproval &&
    !tool.requiresUserInteraction &&
    tool.sideEffectScope === 'none'
  )
}

// ---------------------------------------------------------------
// 第 4 部分：执行器 —— 校验失败也合成结果（错误回灌，不抛出）
// ---------------------------------------------------------------
async function runToolCall(registry, rawCall) {
  const { canonical, tool } = registry.resolve(rawCall.name)
  if (!tool) {
    // registry miss：合成错误结果回灌（真实代码 call-runner.ts 早退也必须 emitToolCallError）
    return { name: rawCall.name, ok: false, error: `工具不存在: ${rawCall.name}` }
  }
  // 输入校验：先试 runtime 轨（zod），失败退 JSON Schema 轨 —— validation.ts 的顺序
  const runtimeCheck = tool.validate(rawCall.args ?? {})
  if (runtimeCheck !== true) {
    return { name: canonical, ok: false, error: `参数校验失败（zod 轨）: ${runtimeCheck}` }
  }
  const result = await tool.execute(rawCall.args ?? {})
  return { name: canonical, ok: true, result }
}

// ---------------------------------------------------------------
// 第 5 部分：main() —— 四个场景
// ---------------------------------------------------------------
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function main() {
  banner('场景 1：双轨独立 —— jsonSchema 写错，zod 照常通过')
  const registry = new ToolRegistry()
  registry.register(defineTool({
    name: 'read_file',
    description: '读文件',
    // zod 轨（mini 版用手写函数模拟 safeParse 语义）
    validate: (a) => typeof a.path === 'string' && a.path.length > 0 ? true : 'path 必须是非空字符串',
    // JSON Schema 轨：故意把 required 写错成 PATH —— 演示"两轨不互相派生"
    jsonSchema: { type: 'object', properties: { path: { type: 'string' } }, required: ['PATH'] },
    readOnly: true, destructive: false, concurrentSafe: true, sideEffectScope: 'none',
    execute: async ({ path }) => `（模拟）${path} 的内容`,
  }))
  const call = await runToolCall(registry, { name: 'read_file', args: { path: 'a.ts' } })
  console.log(`  运行时校验（zod 轨）: ${call.ok} —— 外部契约笔误不影响内部执行；反之同理`)

  banner('场景 2：契约投影 —— 冻结 + execute 置空')
  const contract = registry.toContracts()[0]
  console.log('  下发给 provider 的契约:', JSON.stringify(contract))
  assert(contract.execute === undefined, '契约不带函数')
  let frozenBlocked = false
  try { contract.readOnly = false } catch { frozenBlocked = true }
  console.log(`  偷改 readOnly 被拒: ${frozenBlocked} —— 权限系统读到的声明不可被事后篡改`)

  banner('场景 3：流中闸门 —— 未知即不跑')
  const streamCalls = [
    { name: 'read_file', note: '声明全绿 → 流中立即执行' },
    { name: 'bash', note: 'sideEffectScope=workspace → 等流结束' },
    { name: 'ask_user', note: 'needsApproval=true → 等' },
    { name: 'forgot_declaration', note: 'concurrentSafe 未声明(undefined) → 等' },
  ]
  for (const c of streamCalls) {
    const t = registry.resolve(c.name).tool ?? builtinUnknown(c.name)
    const gate = shouldExecuteDuringStream(t)
    console.log(`  ${gate ? '▶ 流中执行' : '⏸ 等流结束'}  ${c.name.padEnd(20)} ${c.note}`)
    if (c.name === 'read_file') await sleep(1) // 模拟提前 40ms 的重叠窗口
  }

  banner('场景 4：错误回灌 —— 失败也是结果，循环不断')
  const miss = await runToolCall(registry, { name: 'unknown_tool', args: {} })
  console.log('  registry miss  →', JSON.stringify(miss))
  const bad = await runToolCall(registry, { name: 'read_file', args: {} })
  console.log('  参数校验失败   →', JSON.stringify(bad))
  assert(miss.ok === false && bad.ok === false, '两次失败都必须有配对结果')
  console.log('  → 两条都合成 {ok:false} 落日志：模型下一轮自行纠正，没有异常逃出工具层')

  console.log('\n结论：双轨 schema 分开内外契约；声明即契约；流中执行的安全边界是"未知即不跑"。')
}

/** 场景 3 用的两个注册表外工具（在真实代码里它们各自声明自己的 metadata） */
function builtinUnknown(name) {
  if (name === 'bash') return { name, readOnly: false, destructive: false, concurrentSafe: false, needsApproval: false, sideEffectScope: 'workspace' }
  if (name === 'ask_user') return { name, readOnly: true, destructive: false, concurrentSafe: true, needsApproval: true, sideEffectScope: 'none' }
  if (name === 'forgot_declaration') return { name, readOnly: true, destructive: false, /* concurrentSafe 忘了声明 */ needsApproval: false, sideEffectScope: 'none' }
  return null
}

main().catch((e) => { console.error(e); process.exit(1) })
