#!/usr/bin/env node
/**
 * s07_subagent.mjs —— 子代理：把整个 agent loop 当作一个工具
 *
 * dsh 的 subagent 域（packages/subagent/）有两个关键词：
 *
 *   提供方（provider）—— 谁来跑这个子代理？
 *     · fork-in-process：本进程 fork 出一个独立会话的子 loop（dsh 自带）
 *     · subagent-claude-code / subagent-codex：把别家 CLI 当子代理调（适配器）
 *     · subagent-acp / subagent-dsh-sdk：跨进程协议 / SDK 服务
 *   隔离 —— 子代理有自己的会话日志、自己的作用域，父代理只拿到"汇报"。
 *
 *   ┌── 父 loop（session: parent）────────────────────┐
 *   │ 模型调用工具 spawn("explore", "查清 X")         │
 *   │        │                                        │
 *   │        ▼  provider.fork(descriptor)             │
 *   │   ┌── 子 loop（session: child，独立日志/作用域）─┐│
 *   │   │ step1: 调工具 → step2: 收尾汇报             ││
 *   │   └──────────────┬─────────────────────────────┘│
 *   │        ◀─────────┘ tool/result = 子代理的总结   │
 *   │ （子代理的完整过程留在子日志里，父只看汇报）      │
 *   └────────────────────────────────────────────────┘
 *
 * 运行：node code.mjs   （零依赖，离线）
 * 对照真实源码：packages/subagent/（core + 各提供方）、tool-subagent / tool-subagent-control
 */

import { sleep } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：提供方 seam —— spawn(descriptor) 是唯一契约
// ---------------------------------------------------------------
/** 子代理描述符：catalog 里的一条（对应 subagent/descriptor 事件） */
const descriptor = (name, { provider, prompt, tools, model = 'deepseek-chat' }) =>
  Object.freeze({ name, provider, prompt, tools, model })

/** 提供方注册表：catalog = 当前可用的 agent 类型（对应 subagent/catalog 事件） */
class SubagentCatalog {
  constructor() { this.providers = new Map(); this.types = new Map() }
  registerType(type, d) { this.types.set(type, d) } // agent 类型 → 默认 descriptor
  registerProvider(name, provider) { this.providers.set(name, provider) }
  catalog() { return [...this.types.keys()] }
}

/** 提供方一：fork-in-process —— 本进程内 fork 一个独立会话的子 loop */
class ForkInProcessProvider {
  constructor({ tools, modelFactory }) { this.tools = tools; this.modelFactory = modelFactory }

  async *spawn(desc, { log }) {
    // 子代理的边界在这里显式划出来：
    //  · 自己的日志（log 是新开的子日志，不是父的）
    //  · 自己的工具子集（descriptor.tools 白名单 → s05 的作用域分层）
    //  · 自己的模型脚本（modelFactory 按 descriptor 造）
    const childTools = Object.fromEntries(
      desc.tools.map((name) => [name, this.tools[name]]),
    )
    const child = { log, tools: childTools, model: this.modelFactory(desc) }
    yield* runMiniLoop(child) // 复用 s02 的循环形状：驱动器就是个 while
  }
}

/** mini 循环（s02 的紧凑版）：模型要工具就跑工具，不调就收工 */
async function* runMiniLoop({ model, tools, log }) {
  let seq = 0
  const append = (type, payload) => log.push({ seq: ++seq, type, payload })
  while (true) {
    const resp = model.next()
    append('assistant/message', { text: resp.text, calls: resp.calls })
    if (!resp.calls?.length) { yield resp.text; return } // 收尾：汇报给父代理
    const results = []
    for (const c of resp.calls) {
      append('tool/call', c)
      results.push(await tools[c.name](c.args))
    }
    append('tool/result', { results })
    await sleep(2) // 留出观察窗口
  }
}

// ---------------------------------------------------------------
// 第 2 部分：spawn 工具 —— 子代理对模型暴露的形态就是一个普通工具
// ---------------------------------------------------------------
function createSpawnTool({ catalog, events }) {
  return async function spawn(args) {
    events.push(['subagent/descriptor', { type: args.type, task: args.task }])
    const desc = catalog.types.get(args.type)
    const provider = catalog.providers.get(desc.provider)
    const childLog = [] // ★ 子代理自己的日志：父代理永远不直接读它
    const report = []
    for await (const partial of provider.spawn(desc, { log: childLog })) report.push(partial)
    events.push(['subagent/descriptor', { type: args.type, done: true }])
    // 给父代理的只是"汇报"；子日志可以按需转存/审计（dsh 的会话树可整体回看）
    return `【${args.type} 汇报】${report.join('')}\n（子日志 ${childLog.length} 条事件，独立留存）`
  }
}

// ---------------------------------------------------------------
// 第 3 部分：演示 —— 父代理派活给 explore 子代理
// ---------------------------------------------------------------
async function main() {
  const events = []
  const tools = {
    read_file: async ({ path }) => `（模拟）${path}：找到了三处相关引用`,
    search_web: async ({ query }) => `（模拟）搜索 "${query}"：官方文档是最权威来源`,
    spawn: null, // 稍后接上
  }

  const catalog = new SubagentCatalog()
  catalog.registerProvider('fork-in-process', new ForkInProcessProvider({
    tools,
    // 子代理的模型脚本：explore 类型固定跑"查资料 → 汇报"
    modelFactory: () => {
      const script = [
        { text: '', calls: [{ name: 'read_file', args: { path: 'docs/x.md' } }] },
        { text: 'X 的机制在 docs/x.md 有三处引用，结论：走官方文档最稳。', calls: [] },
      ]
      let i = 0
      return { next: () => script[i++] }
    },
  }))
  catalog.registerType('explore', descriptor('explore', {
    prompt: '只查证、不改动。产出结构化事实清单。',
    tools: ['read_file', 'search_web'], // ★ 工具白名单：explore 没有 write 权限
    provider: 'fork-in-process',
  }))

  tools.spawn = createSpawnTool({ catalog, events })

  console.log('== 1. catalog：父代理的提示词里会列出可用的 agent 类型（s04 的 tools section） ==')
  console.log('  可用类型:', catalog.catalog(), '← 对应 subagent/catalog 事件')

  console.log('\n== 2. 父 loop：模型调用 spawn 工具，拿到的是"汇报"不是过程 ==')
  // 父模型脚本：第一步派活，第二步根据汇报收尾
  const parentScript = [
    { text: '', calls: [{ name: 'spawn', args: { type: 'explore', task: '查清 X 的机制' } }] },
    { text: '子代理查清了 X：走官方文档最稳。我不再重复查证。', calls: [] },
  ]
  let pi = 0
  const parentRun = {
    log: events, tools,
    model: { next: () => parentScript[pi++] },
  }
  // 父代理日志（独立于子代理日志）
  const parentLog = []
  let pseq = 0
  const parentAppend = (type, payload) => parentLog.push({ seq: ++pseq, type, payload })
  // 手动展开父循环两步（与 runMiniLoop 同形，便于打印对照）
  for (const resp of parentScript) {
    parentAppend('assistant/message', resp)
    if (resp.calls?.length) {
      for (const c of resp.calls) {
        parentAppend('tool/call', c)
        const result = await tools[c.name](c.args)
        parentAppend('tool/result', { result })
        console.log(`  父收到 tool/result:\n    ${result.replace(/\n/g, '\n    ')}`)
      }
    }
  }

  console.log('\n== 3. 两本日志：父子各记各的，互不掺和 ==')
  console.log('  父日志:', parentLog.map((e) => `#${e.seq}${e.type}`).join(' '))
  console.log('  父日志里没有子代理的工具细节 —— 只有那条汇报')
  console.log('\n结论：子代理 = 一层"过程不可见、结论可见"的抽象 ——')
  console.log('  上下文隔离（子过程不占父窗口）+ 权限隔离（工具白名单）+ 审计隔离（日志独立）。')
  console.log('  dsh 甚至内置了把 Claude Code / Codex 当子代理的提供方 —— 别家 harness 也只是另一个 provider。')
}

main().catch((e) => { console.error(e); process.exit(1) })
