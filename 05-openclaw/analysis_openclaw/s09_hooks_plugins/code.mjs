#!/usr/bin/env node
/**
 * s09_hooks_plugins.mjs —— 钩子时序与终态裁决 + 插件注册面
 *
 * OpenClaw 给插件留了 17 个钩子位（docs/concepts/agent-loop.md:85-95），覆盖
 * 一条消息的全部生命周期。两个语义是骨架：
 *
 *   ① 时序即契约：钩子按固定顺序触发——
 *      message_received → session_start → before_model_resolve →
 *      before_prompt_build → before_agent_reply → before_tool_call →
 *      tool_result_persist → after_tool_call → before/after_compaction →
 *      agent_end → session_end → message_sending → message_sent
 *      （外加 gateway_start/stop、before_install）
 *
 *   ② 终态裁决（terminal verdict）：
 *      before_tool_call  { block: true }  → 终态，低优先级处理器不再运行（:99）
 *      message_sending   { cancel: true } → 终态，出站消息被取消（:101）
 *      { block: false } / { cancel: false } 是 no-op，不清除先前的终态。
 *
 * 插件注册面：api.registerTool 是"登记式捕获"（captured-registration.ts:377）——
 * 插件把工具/钩子登记给 core，core 拥有共享工具（如 message）；接口越小越稳定。
 *
 * 另要分清三套"钩子"（容易混）：
 *   ① 插件钩子矩阵（进程内，本课主角）；
 *   ② 内部钩子（command:new/reset/stop、agent:bootstrap，文件驱动，docs/automation/hooks/）；
 *   ③ HTTP webhooks（src/gateway/server/hooks.ts，外部系统入站，s06 讲过）。
 *
 *   消息 →[收]→ 会话 →[模型前]→ [prompt 前] → [回复前] → 工具 ★block
 *        → [结果落盘] → [压缩观察] → agent_end → 出站 ★cancel → 发送
 *
 * 运行：node code.mjs    （零依赖，离线）
 * 对照真实源码：docs/concepts/agent-loop.md:85-101（钩子矩阵权威表）、
 *   src/plugins/captured-registration.ts:341/:377、src/plugins/api-builder.ts、
 *   src/gateway/server/hooks.ts:235、docs/automation/hooks/*.md
 */

import { assert } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：钩子时序表（agent-loop.md:85-95 的 17 位清单）
// ---------------------------------------------------------------
const HOOK_ORDER = [
  'gateway_start', 'message_received', 'session_start', 'before_model_resolve',
  'before_prompt_build', 'before_agent_reply', 'before_tool_call', 'after_tool_call',
  'tool_result_persist', 'before_compaction', 'after_compaction', 'agent_end',
  'session_end', 'message_sending', 'message_sent', 'gateway_stop', 'before_install',
]
const TERMINAL_HOOKS = { before_tool_call: 'block', message_sending: 'cancel', before_install: 'block' }
const OBSERVE_ONLY = ['before_compaction', 'after_compaction'] // 文档明写：不重写、不否决压缩

/** 优先级：数值大者先跑；同优先级按注册序。 */
class HookBus {
  constructor() { this.handlers = new Map(HOOK_ORDER.map((h) => [h, []])); this.fired = [] }
  on(hook, handler, { priority = 0, name = 'anon' } = {}) {
    if (!this.handlers.has(hook)) throw new Error(`未知钩子位: ${hook}（17 位之外不存在）`)
    this.handlers.get(hook).push({ handler, priority, name })
  }
  /** 派发：按优先级逐个跑；终态钩子一旦拿到 block/cancel=true 立即停。 */
  async dispatch(hook, payload) {
    if (!this.handlers.has(hook)) throw new Error(`未知钩子位: ${hook}`)
    this.fired.push(hook)
    const sorted = [...this.handlers.get(hook)].sort((a, b) => b.priority - a.priority)
    for (const h of sorted) {
      const verdict = (await h.handler(payload)) ?? {}
      const key = TERMINAL_HOOKS[hook]
      if (key && verdict[key] === true) {
        return { terminal: true, by: h.name, verdict }
      }
    }
    return { terminal: false, by: null, verdict: {} }
  }
}

// ---------------------------------------------------------------
// 第 2 部分：插件注册面（captured-registration.ts:377 的 mini 版）
// ---------------------------------------------------------------
/** 插件 api：registerTool/registerHook 全是"登记"，core 收集后再统一装配——
 *  插件不直接改内核状态（登记式捕获，captured registration）。 */
function createPluginApi(bus) {
  const registered = { tools: [], hooks: [] }
  return {
    registered,
    registerTool(tool) { registered.tools.push(tool) },        // :377
    registerToolMetadata(meta) { registered.tools.push({ __meta: meta }) }, // :341（元数据版）
    on(hook, handler, opts) { bus.on(hook, handler, opts); registered.hooks.push(hook) },
  }
}

// ---------------------------------------------------------------
// 演示
// ---------------------------------------------------------------
async function main() {
  const log = (...a) => console.log(...a)

  console.log('== 1. 装配 + 全时序：两个插件登记，一条消息穿过钩子矩阵 ==')
  const bus = new HookBus()
  const apiA = createPluginApi(bus) // 插件 A：安全插件
  const apiB = createPluginApi(bus) // 插件 B：日志插件
  apiA.registerTool({ name: 'corp_lookup', run: async () => '内部数据' })
  apiB.registerToolMetadata({ name: 'corp_lookup_beta' }) // 只登记元数据
  log(`插件 A 注册工具: ${apiA.registered.tools.map((t) => t.name).join(', ')}；插件 B 登记元数据: ${apiB.registered.tools.filter((t) => t.__meta).map((t) => t.__meta.name).join(', ')}`)
  apiB.on('message_received', () => log('  [日志插件] message_received 记录'), { name: 'logger' })
  apiB.on('before_model_resolve', (p) => { p.forced = p.forced; }, { name: 'logger' })
  // before_model_resolve 是确定性改判点：插件可以在会话解析前覆盖 provider/model。
  apiB.on('before_model_resolve', (p) => { p.modelOverride = null }, { name: 'logger' })
  apiB.on('agent_end', () => log('  [日志插件] agent_end 记账'), { name: 'logger' })
  await bus.dispatch('gateway_start', {})
  await bus.dispatch('message_received', { text: '帮我重启服务器' })
  await bus.dispatch('session_start', { sessionKey: 'agent:main:main' })
  const mr = { model: null }
  await bus.dispatch('before_model_resolve', mr)
  await bus.dispatch('before_prompt_build', {})
  await bus.dispatch('before_agent_reply', {})
  await bus.dispatch('agent_end', {})
  log(`  已触发顺序: ${bus.fired.join(' → ')}`)
  log('  → 顺序是矩阵定义的：想在 before_prompt_build 改 prompt？先确认你排在谁前面。')

  console.log('\n== 2. before_tool_call {block:true} 终态（失败路径）==')
  apiA.on('before_tool_call', (t) => (t.name === 'exec' ? { block: true, reason: 'exec 不允许在会话中执行' } : {}), { priority: 100, name: 'security' })
  apiB.on('before_tool_call', () => log('  [日志插件] before_tool_call 观察记录'), { priority: 10, name: 'logger' })
  const execVerdict = await bus.dispatch('before_tool_call', { name: 'exec' })
  log(`exec → 终态=${execVerdict.terminal}（被 ${execVerdict.by} 阻断；优先级 10 的日志处理器没运行）`)
  const readVerdict = await bus.dispatch('before_tool_call', { name: 'read' })
  log(`read → 终态=${readVerdict.terminal}（放行，两个处理器都跑了）`)
  assert(execVerdict.terminal && !readVerdict.terminal)

  console.log('\n== 3. message_sending {cancel:true}：出站前的最后一道闸（失败路径）==')
  apiA.on('message_sending', (m) => (m.text.includes('密钥 sk-') ? { cancel: true, reason: '拦截疑似密钥泄漏' } : {}), { priority: 100, name: 'security' })
  const leak = await bus.dispatch('message_sending', { text: '我的密钥 sk-123 是…' })
  const okMsg = await bus.dispatch('message_sending', { text: '今天天气不错' })
  log(`疑似密钥消息 → 终态=${leak.terminal}（${leak.verdict.reason}；message_sent 不会触发）`)
  log(`正常消息     → 终态=${okMsg.terminal}（放行，随后 message_sent）`)

  console.log('\n== 4. 观察位、no-op 与三套"钩子"的边界 ==')
  apiA.on('before_compaction', () => log('  [安全插件] 观察到压缩开始（不能否决）'), { name: 'security' })
  await bus.dispatch('before_compaction', {})
  log(`观察位不能改写：${OBSERVE_ONLY.join('/')} 只观察不裁决（agent-loop.md:89）`)
  // no-op 语义：低优先级先 block:true？不可能——高优先级先跑。反过来：先到的
  // {block:false} 是 no-op，不会"赦免"后面处理器给出的终态。
  apiB.on('before_tool_call', () => ({ block: false }), { priority: 99, name: 'noop-plug' })
  const noopVerdict = await bus.dispatch('before_tool_call', { name: 'exec' })
  log(`{block:false} no-op 语义：exec 仍被 security 终态阻断 → ${noopVerdict.terminal}（:99 后半句）`)
  // 三套"钩子"别混为一谈（收尾清单）：
  log('边界：① 插件钩子矩阵（本课，进程内 17 位）｜② 内部钩子 command:new/reset/stop、agent:bootstrap（docs/automation/hooks/）｜③ HTTP webhooks（src/gateway/server/hooks.ts，外部入站）')
  console.log('\n终态裁决是插件体系的"法院终审"：优先级定谁先说，终态定谁能一锤定音。')
}

main().catch((e) => { console.error(e); process.exit(1) })
