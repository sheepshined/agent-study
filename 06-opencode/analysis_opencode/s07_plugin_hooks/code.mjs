#!/usr/bin/env node
/**
 * s07_plugin_hooks.mjs —— 插件钩子：21 个 Hooks 的时序与 output 原地改写
 *
 * OpenCode 的插件面（packages/plugin/src/index.ts:222-334）列出 21 个钩子位，
 * 按一次 turn 的时间轴分布：
 *
 *   配置期        config · auth · provider · shell.env
 *   请求构造期    chat.message → chat.params → chat.headers
 *                 （+ experimental.chat.messages/system.transform 可整体替换）
 *   执行期        permission.ask → tool.execute.before → 工具体 → tool.execute.after
 *   收尾期        tool.definition（注册期）· text.complete · event（全程只读）· dispose
 *
 * 两个关键机制（mini 版逐一对齐）：
 *   ① output 原地改写：钩子签名 (input, output)，没有返回值——直接改 output 的字段，
 *      触发完之后"将要生效的对象"才定型（tool.definition 改描述、permission.ask 改判定、
 *      chat.params 改 temperature，全是这个模式）
 *   ② 失败隔离：单个钩子抛错被 trigger() 捕获，其余插件与主流程照常
 *
 *   turn 时间轴（场景 1 的输出就是这条线）：
 *   config → chat.message → chat.params → chat.headers → [流式输出]
 *     → tool.execute.before → 工具体 → tool.execute.after → text.complete
 *
 * 运行：node code.mjs   （零依赖，离线）
 * 对照真实源码：packages/plugin/src/index.ts:222-334（Hooks 全清单）
 *              packages/opencode/src/session/tools.ts:123/:138（执行期触发点）
 */

// ---------------------------------------------------------------
// 第 1 部分：钩子总线（Plugin.trigger 的 mini 版）
// ---------------------------------------------------------------
/** 插件 = (input) => Hooks 对象（真实 :74 的形状）。
 *  trigger：按插件加载顺序逐个 await；单个钩子抛错只记不炸（失败隔离）。 */
function createBus() {
  const plugins = []
  const errors = []
  return {
    register(name, hooks) {
      plugins.push({ name, hooks })
      return () => {
        const i = plugins.findIndex((p) => p.name === name)
        if (i >= 0) plugins.splice(i, 1)
      }
    },
    async trigger(hookName, input, output) {
      for (const p of plugins) {
        const hook = p.hooks[hookName]
        if (!hook) continue
        try {
          await hook(input, output) // output 引用传递：钩子改它就是改"将要生效的对象"
        } catch (e) {
          errors.push(`[hook-error] 插件 ${p.name} 的 ${hookName} 抛错: ${e.message}`)
        }
      }
    },
    dumpErrors() {
      for (const e of errors) console.log(`    ${e}`)
      errors.length = 0
    },
  }
}

// ---------------------------------------------------------------
// 第 2 部分：21 个钩子位清单（plugin/src/index.ts:222-334 的分组索引）
// ---------------------------------------------------------------
const HOOKS = {
  配置期: ['config', 'auth', 'provider', 'shell.env'],
  请求构造期: ['chat.message', 'chat.params', 'chat.headers', 'experimental.chat.messages.transform', 'experimental.chat.system.transform'],
  执行期: ['permission.ask', 'command.execute.before', 'tool.execute.before', 'tool.execute.after'],
  注册与收尾: ['tool', 'tool.definition', 'text.complete', 'event', 'dispose'],
  实验面: ['experimental.provider.small_model', 'experimental.session.compacting', 'experimental.compaction.autocontinue'],
}
const TOTAL = Object.values(HOOKS).reduce((n, xs) => n + xs.length, 0)

// ---------------------------------------------------------------
// 第 3 部分：一次 turn 的执行器（在正确的位置触发钩子）
// ---------------------------------------------------------------
async function runTurn({ bus, userText, tool }) {
  // 请求构造期
  const message = { role: 'user', text: userText }
  await bus.trigger('chat.message', { message }, { message })
  const params = { temperature: 0.7, topP: 0.9 }
  await bus.trigger('chat.params', { tool }, params) // 钩子可原地改 temperature 等
  const headers = {}
  await bus.trigger('chat.headers', {}, headers)
  console.log(`    [请求] temperature=${params.temperature} headers=${JSON.stringify(headers)}`)

  // 执行期：before → 工具体 → after（tools.ts:123/:138 的触发点）
  const toolOutput = { description: tool.description, title: '' }
  await bus.trigger('tool.definition', { toolID: tool.name }, toolOutput) // 注册期改描述
  const executed = { description: toolOutput.description }
  const execResult = { ok: true, result: '' }
  await bus.trigger('tool.execute.before', { tool: tool.name }, { args: tool.args, description: executed })
  if (tool.permissionVerdict === 'blocked-by-hook') {
    execResult.ok = false
    execResult.result = 'Error: permission denied by plugin'
  } else {
    execResult.result = `${tool.name} 执行完成`
  }
  await bus.trigger('tool.execute.after', { tool: tool.name }, execResult)
  console.log(`    [工具] ${tool.name} → ok=${execResult.ok}（生效描述: "${executed.description}"）`)
  await bus.trigger('text.complete', { text: 'done' }, {})
  return execResult
}

// ---------------------------------------------------------------
// 第 4 部分：演示
// ---------------------------------------------------------------
async function main() {
  console.log(`== 场景 0：21 个钩子位清单（真实共 ${TOTAL} 个，:222-334）==`)
  for (const [stage, hooks] of Object.entries(HOOKS)) console.log(`    ${stage.padEnd(6)} ${hooks.join(', ')}`)

  console.log('\n== 场景 1：钩子时序 —— 一次 turn 的触发点顺序 ==')
  const bus = createBus()
  const timeline = []
  // 给每个钩子位包一层时间线记录
  const rawTrigger = bus.trigger.bind(bus)
  bus.trigger = async (name, input, output) => {
    timeline.push(name)
    return rawTrigger(name, input, output)
  }
  const tool = { name: 'read', description: 'Reads a file', args: { path: 'a.ts' } }
  await runTurn({ bus, userText: '读一下 a.ts', tool })
  console.log(`    实际触发顺序: ${timeline.join(' → ')}`)

  console.log('\n== 场景 2：output 原地改写 —— 钩子没有返回值，改的是引用 ==')
  const bus2 = createBus()
  bus2.register('describe-rewriter', {
    // 对齐 :334 tool.definition?: (input, output: { description }) => Promise<void>
    'tool.definition': async (input, output) => {
      output.description = '[改写] 先列目录再读目标文件，避免盲读'
    },
    // 对齐 experimental.chat.system.transform：整体替换系统提示词
    'experimental.chat.system.transform': async (input, output) => {
      output.system = 'You are a careful reader. Always list before you read.'
    },
  })
  const sysOut = { system: '（原装系统提示词）' }
  await bus2.trigger('experimental.chat.system.transform', {}, sysOut)
  console.log(`    系统提示词被整体替换: "${sysOut.system}"`)
  await runTurn({ bus: bus2, userText: '读 a.ts', tool })

  console.log('\n== 场景 3：permission.ask 钩子 + 失败隔离（失败路径）==')
  const bus3 = createBus()
  bus3.register('deploy-blocker', {
    // 对齐 :261 permission.ask?: (input, output: { status: "ask"|"deny"|"allow" })
    'permission.ask': async (input, output) => {
      if (input.permission === 'deploy') output.status = 'deny' // 连弹窗都不出，直接拒
    },
  })
  bus3.register('audit-only', {
    event: async (input) => console.log(`    [audit] 事件: ${input.type}`), // 只读面
  })
  bus3.register('buggy-plugin', {
    'tool.execute.after': async () => {
      throw new Error('我是个有 bug 的插件')
    },
  })
  const verdict = { status: 'ask' }
  await bus3.trigger('permission.ask', { permission: 'deploy', pattern: '*' }, verdict)
  console.log(`    deploy 的审批被钩子改写为: ${verdict.status} → 跳过弹窗直接拦`)
  const deployResult = { ok: false, result: 'Error: permission denied by plugin' }
  await bus3.trigger('tool.execute.after', { tool: 'deploy' }, deployResult)
  bus3.dumpErrors() // buggy-plugin 的异常在这里被隔离，主流程没炸
  console.log('    → buggy 抛错只进了错误桶；audit 与主流程照常')

  console.log('\n结论：21 个钩子位 = 时间轴上的锚点；output 引用改写让插件能"改请求"而不只是"看请求"；')
  console.log('失败隔离保证第三方代码永远炸不烂推理链路。')
}

main().catch((e) => { console.error(e); process.exit(1) })
