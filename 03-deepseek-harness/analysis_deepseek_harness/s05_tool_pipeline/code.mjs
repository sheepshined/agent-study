#!/usr/bin/env node
/**
 * s05_tool_pipeline.mjs —— 工具注册表与把关执行流水线
 *
 * 模型点了工具名之后发生什么？dsh 的答案分两层：
 *
 *   注册表层（packages/core/tools 的 ToolRuntime，:780）
 *     · 作用域分层（ScopedLayers）：MCP 工具、内置工具、插件工具同一张表，
 *       谁可见由作用域决定；变更以 tools/change 事件广播
 *     · executionMode（:1266）：parallel（可并发）| exclusive（互斥屏障）
 *
 *   执行层（packages/core/agent-loop 的 tool-calls.ts）
 *     · 四拍：prepare（可同步拒否）→ dispatch（真正开跑）→ finalize → finish
 *     · exclusive 调用是屏障；parallel 调用进有界滚动池
 *     · ★ "模型序提交"：执行可以乱序完成，但 tool/result 落日志的顺序
 *       必须与模型 tool/call 的顺序严格一致（commitReady 只提交连续前缀，:147）
 *     · abort 不制造空洞：已开始的等完成照常提交，未开始的补写合成错误结果
 *
 *   模型给了 [A并行·慢, B并行·快, C互斥, D被拒]：
 *
 *    t=10  B 完成 ──┐ (等 A)
 *    t=40  A 完成 ──┴→ 提交 A,B（模型序） → 跑 C（屏障独占） → 提交 C → D 被 pre 拒 → 合成错误结果
 *    日志顺序永远是 A,B,C,D —— 与模型给定的顺序严格一致
 *
 * 运行：node code.mjs   （零依赖，离线）
 * 对照真实源码：packages/core/tools/src/index.ts、packages/core/agent-loop/src/tool-calls.ts
 */

import { deepFreeze } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：作用域分层注册表（ScopedLayers 的 mini 版）
// ---------------------------------------------------------------
class ScopedToolRegistry {
  constructor() { this.layers = [] } // [{scope, tools:Map}]，越靠前越"局部"

  register(scope, tool) {
    let layer = this.layers.find((l) => l.scope === scope)
    if (!layer) { layer = { scope, tools: new Map() }; this.layers.push(layer) }
    layer.tools.set(tool.name, deepFreeze(tool)) // 注册即冻结：注册表条目不可变
    return () => layer.tools.delete(tool.name)   // 注销也是可逆的（s01 纪律）
  }

  /** 谁可见？沿作用域链合并（局部遮蔽全局）—— s04 的提示词就是从这里取 schema */
  visible(scopeChain) {
    const seen = new Map()
    for (const scope of scopeChain) {
      const layer = this.layers.find((l) => l.scope === scope)
      if (layer) for (const t of layer.tools.values()) if (!seen.has(t.name)) seen.set(t.name, t)
    }
    return [...seen.values()]
  }

  /** executionMode（:1266）：parallel | exclusive —— 这是调度器（agent-loop）的输入 */
  static executionMode(tool) { return tool.mode ?? 'parallel' }
}

// ---------------------------------------------------------------
// 第 2 部分：把关流水线（pre / around / post）
// ---------------------------------------------------------------
/**
 * dsh 拆成 prepare → dispatch → finalize → finish 四拍（:789 门面）：
 * prepare 可同步拒否（拒了就不进并发池）；agent-loop 的"模型序提交"
 * 依赖这个分拍。mini 版保留三个钩子位，语义一致。
 */
function createPipeline({ hooks = [] }) {
  return {
    /** 一拍的完整执行：钩子链 → 工具体 → 结果。永远返回结果，不抛给调度器 */
    async run(tool, args) {
      for (const h of hooks) if (h.pre) {
        const verdict = h.pre(tool, args)
        if (!verdict.ok) return { ok: false, error: `[pre·${h.name}] ${verdict.reason}` } // 同步拒否
      }
      const around = hooks.filter((h) => h.around)
      const core = around.reduceRight(
        (next, h) => () => h.around(tool, next),
        async () => ({ ok: true, result: await tool.run(args) }),
      )
      const out = await core()
      for (const h of hooks) if (h.post) h.post(tool, out)
      return out
    },
  }
}

// ---------------------------------------------------------------
// 第 3 部分：调度器 —— 分组 + 有界滚动池 + 模型序提交
// ---------------------------------------------------------------
/**
 * executeToolCalls（tool-calls.ts :60 的 mini 版）：
 * 连续的 parallel 调用为一组（共享滚动池），exclusive 调用自成一组（屏障）。
 * 关键不变量：slots[i] 只有当 slots[0..i-1] 全部提交后才能提交（commitReady）。
 */
async function executeToolCalls(calls, { registry, pipeline, scopeChain, log, poolSize = 2 }) {
  const tools = new Map(registry.visible(scopeChain).map((t) => [t.name, t]))
  const slots = calls.map((call, idx) => ({ call, idx, ready: null, committed: false }))
  let commitPtr = 0

  const commit = () => {
    // ★ 只在连续的模型序 slot 上推进提交指针（commitReady :147）
    while (commitPtr < slots.length && slots[commitPtr].ready) {
      const s = slots[commitPtr]
      log('tool/result', { id: s.call.id, ok: s.ready.ok, result: s.ready.ok ? s.ready.result : s.ready.error })
      s.committed = true
      commitPtr++
    }
  }

  // 按 exclusive 屏障切成组（组内是 slot 对象）：[parallel...] [exclusive] [parallel...]
  const groups = []
  let cur = []
  for (const s of slots) {
    const mode = ScopedToolRegistry.executionMode(tools.get(s.call.name) ?? {})
    if (mode === 'exclusive') { if (cur.length) groups.push(cur); groups.push([s]); cur = [] }
    else cur.push(s)
  }
  if (cur.length) groups.push(cur)

  for (const group of groups) {
    let next = 0
    const workers = Array.from({ length: Math.min(poolSize, group.length) }, async () => {
      while (next < group.length) {
        const s = group[next++] // 滚动池：干完一个再领一个（有界并发）
        const tool = tools.get(s.call.name)
        if (!tool) { s.ready = { ok: false, error: `工具不存在: ${s.call.name}` }; commit(); continue }
        // dispatch 前最后再看一眼 executionMode（:87）：注册表变化影响未开始的调用
        if (ScopedToolRegistry.executionMode(tool) === 'exclusive' && group.length > 1) {
          s.ready = { ok: false, error: '重分类为 exclusive，移交屏障组' }
          commit(); continue
        }
        s.ready = await pipeline.run(tool, s.call.args)
        commit() // 每次落定都尝试推进提交指针
      }
    })
    await Promise.all(workers) // 屏障语义：本组全部提交后才进入下一组
  }
  commit()
  return slots.map((s) => s.ready)
}

// ---------------------------------------------------------------
// 第 4 部分：演示 —— 乱序完成，模型序提交
// ---------------------------------------------------------------
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function main() {
  console.log('== 1. 作用域分层：会话私有工具对别的 agent 不可见 ==')
  const registry = new ScopedToolRegistry()
  registry.register('builtin', { name: 'read_file', description: '读文件', run: async () => '内容' })
  registry.register('builtin', { name: 'deploy', description: '发布', mode: 'exclusive', run: async () => '已发布' })
  registry.register('session#1', { name: 'draft_helper', description: '本会话私有', run: async () => '草稿' })
  console.log('session#1 可见:', registry.visible(['session#1', 'builtin']).map((t) => t.name))
  console.log('session#2 可见:', registry.visible(['session#2', 'builtin']).map((t) => t.name))

  console.log('\n== 2. 把关流水线：pre 拒否 + around 计时（计时输出在场景 3 执行时可见） ==')
  const hooks = [
    { name: 'permission', pre: (tool, args) => (tool.name === 'deploy'
      ? { ok: false, reason: '需要审批（s09 的 approval 会正式化这道闸）' }
      : args.secret ? { ok: false, reason: '拒绝读取带 secret 标记的调用' } : { ok: true }) },
    { name: 'timer', around: async (tool, next) => { const t = Date.now(); const r = await next(); console.log(`  [timer] ${tool.name} 耗时 ${Date.now() - t}ms`); return r } },
  ]
  const pipeline = createPipeline({ hooks })

  console.log('\n== 3. 调度：[A 慢·并行, B 快·并行, C 互斥, D 被拒] —— 完成可以乱序，提交必须模型序 ==')
  const events = []
  const log = (type, payload) => { events.push({ type, payload }); console.log(`  ${type.padEnd(13)} ${JSON.stringify(payload)}`) }

  registry.register('builtin', { name: 'slow_read', run: async () => { await sleep(40); return '慢查询结果' } })
  registry.register('builtin', { name: 'fast_stat', run: async () => { await sleep(10); return '快速统计' } })

  log('tool/call', { order: ['A slow_read', 'B fast_stat', 'C deploy', 'D slow_read@denied'] })
  const t0 = Date.now()
  await executeToolCalls(
    [
      { id: 'A', name: 'slow_read', args: {} },   // 并行·40ms
      { id: 'B', name: 'fast_stat', args: {} },   // 并行·10ms（先完成，但等 A）
      { id: 'C', name: 'deploy', args: {} },      // 互斥屏障
      { id: 'D', name: 'slow_read', args: { secret: true } }, // pre 拒否 → 合成错误结果
    ],
    { registry, pipeline, scopeChain: ['session#1', 'builtin'], log },
  )
  console.log(`  总耗时 ${Date.now() - t0}ms（B 先完成但排在 A 后提交；C 独占；D 未执行也有结果）`)
  console.log('  → 日志里 tool/result 的顺序与模型 tool/call 的顺序严格一致：重放与引用才成立')
  console.log('  → D 没有被 dispatch，但日志里有配对的 tool/result（pre 拒否 = 合成错误结果，不制造空洞）')
}

main().catch((e) => { console.error(e); process.exit(1) })
