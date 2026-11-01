#!/usr/bin/env node
/**
 * s01_plugin_kernel.mjs —— mini-Cordis：插件内核
 *
 * dsh 的第一性原理是"一切皆插件"（Everything is a Plugin）：
 * 模型适配器、工具注册表、会话日志、乃至 agent loop 本身都是插件，
 * 全部可从配置替换 —— 不存在需要打补丁的特权内核。
 *
 * 那底座是什么？Cordis：一个"事件中心 + 依赖容器 + 可逆副作用"的插件树。
 * 本文件用 ~150 行实现一个 mini-Cordis，演示四个核心机制：
 *
 *   1. Context   —— 插件的宿主：既是事件总线（emit/on），又是服务容器（provide/get）
 *   2. Service   —— "每次注入一次"：插件用 ctx[service] 拿到惰性构造的单例
 *   3. plugin    —— setup(ctx) 返回清理函数：副作用必须可逆（reversible）
 *   4. 子作用域  —— ctx.fork() 长出子 Context：子卸载时自动反初始化它加载的插件
 *
 *   +----------------+  fork   +------------------+
 *   |  root Context  | ------> |  child Context   |
 *   |  (agent 内核)  |         |  (一次会话/子代理)|
 *   +---+--------+---+         +--------+---------+
 *       | emit/on                事件冒泡  |
 *       v                                 v
 *   插件A清理 <---- dispose（逆序回滚）---- 插件B清理
 *
 * 运行：node code.mjs        （零依赖，离线可跑）
 * 对照真实源码：docs/cordis-primer.zh.md、docs/cordis-tutorial/
 */

// ---------------------------------------------------------------
// 第 1 部分：Context —— 事件总线 + 服务容器
// ---------------------------------------------------------------

/** 极简事件表：type -> Set<listener>。dsh 里对应 Cordis 的 ctx.emit / ctx.on。 */
class MiniContext {
  constructor(parent = null, name = 'root') {
    this.name = name
    this.parent = parent          // 子作用域指回父 Context，形成一棵树
    this.disposed = false
    /** @type {Map<string, Set<Function>>} */
    this.listeners = new Map()
    /** @type {Map<string, {factory: Function, instance: any}>} 服务注册表 */
    this.services = new Map()
    /** 本作用域已加载的插件卸载函数：dispose 时逆序执行（可逆副作用的落点） */
    this.teardowns = []
    /** 子作用域引用：父卸载时级联 */
    this.children = new Set()
    if (parent) parent.children.add(this)
  }

  // ---- 事件面（对应 Cordis ctx.emit / ctx.on）----
  on(type, fn) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set())
    this.listeners.get(type).add(fn)
    return () => this.listeners.get(type)?.delete(fn) // 返回退订函数：也是可逆的
  }

  emit(type, payload) {
    // 事件沿树冒泡：子作用域发出的事件父作用域也能听到 —— dsh 的 agent/* 事件
    // （agent/inbox/spliced、tool/call…）正是靠这个机制被上层 UI/日志插件统一接收。
    for (const ctx of this.bubbleChain()) {
      const set = ctx.listeners.get(type)
      if (set) for (const fn of set) fn(payload, this)
    }
  }

  *bubbleChain() {
    for (let c = this; c; c = c.parent) yield c
  }

  // ---- 服务面（对应 Cordis 的 Service 注入：每次注入一次）----
  /**
   * provide(key, factory)：注册惰性单例。第一次 get 时才构造 ——
   * dsh 的 ctx.tools / ctx.sessions / ctx.agentLoop 都是这种 seam（能力缝），
   * 插件之间只认 key，不认具体实现：换实现 = 换注册，不改调用方。
   */
  provide(key, factory) {
    this.services.set(key, { factory, instance: undefined })
  }

  get(key) {
    for (const ctx of this.bubbleChain()) {
      // 沿树向上查找：子作用域没注册的服务回落到父作用域 —— 作用域分层可见性
      const reg = ctx.services.get(key)
      if (reg) {
        if (reg.instance === undefined) {
          reg.instance = reg.factory(this) // 惰性构造，构造函数拿到 ctx 以便再注入
          this.emit('service/created', { key, ctx: ctx.name })
        }
        return reg.instance
      }
    }
    throw new Error(`[mini-cordis] 服务未注册: ${key}`)
  }

  // ---------------------------------------------------------------
  // 第 2 部分：plugin —— 副作用必须可逆
  // ---------------------------------------------------------------
  /**
   * 加载插件：setup(ctx) 干三件事 —— 注册服务 / 监听事件 / 挂 teardown。
   * Cordis 的纪律：插件在 setup 里做的每一件事（注册、监听、修改）都必须
   * 能被逆序撤销。dsh 的 profile 装配、插件热插拔、会话结束的资源回收
   * 全部建立在这条纪律上 —— 所以"换插件"不需要重启，"卸插件"不留垃圾。
   */
  plugin(setup) {
    if (this.disposed) throw new Error('[mini-cordis] Context 已卸载，拒绝加载插件')
    const teardown = setup(this)
    if (typeof teardown === 'function') this.teardowns.push(teardown)
    this.emit('plugin/loaded', { ctx: this.name })
    return this
  }

  /** 逆序回滚：后加载的先卸载（栈式），然后级联卸载子作用域。 */
  async dispose() {
    if (this.disposed) return
    this.disposed = true
    for (const child of [...this.children]) await child.dispose()
    while (this.teardowns.length) {
      const fn = this.teardowns.pop()
      await fn()
    }
    this.emit('ctx/disposed', { ctx: this.name })
    this.parent?.children.delete(this)
  }
}

// ---------------------------------------------------------------
// 第 3 部分：演示 —— 用 mini-Cordis 装一个"会打日志的工具注册表"
// ---------------------------------------------------------------
// 场景对应 dsh 的真实分层：
//   root ctx 装内核插件（工具注册表 ctx.tools）
//   child ctx（一次会话）装会话级插件（往 ctx.tools 里注册一个会话私有工具）
//   —— 工具"作用域分层"就是 ctx 树分层的自然结果（见 s05）。

// 插件 A：工具注册表。注意 setup 里注册了服务 + 挂了 teardown，两件事都可逆。
const toolsPlugin = (ctx) => {
  const tools = new Map()
  ctx.provide('tools', () => ({
    register(name, run) { tools.set(name, run); ctx.emit('tools/changed', { name }) },
    async call(name, args) {
      if (!tools.has(name)) throw new Error(`工具不存在: ${name}`)
      return tools.get(name)(args)
    },
    names: () => [...tools.keys()],
  }))
  return () => ctx.emit('tools/changed', { removed: '整个注册表' })
}

// 插件 B：事件日志插件（对应 dsh 把一切写成 SessionEvent 的口吻）。
const auditPlugin = (ctx) => {
  const log = []
  const off = ctx.on('tools/changed', (p) => log.push(`[audit] ${ctx.name}: ${JSON.stringify(p)}`))
  ctx.provide('audit', () => log)
  return () => { off(); log.push('[audit] 已退订') } // 退订也要做干净
}

async function main() {
  console.log('== 1. 装配 root：内核插件 ==')
  const root = new MiniContext(null, 'root')
  root.plugin(toolsPlugin).plugin(auditPlugin)

  const tools = root.get('tools')
  tools.register('read_file', async ({ path }) => `（模拟）读了 ${path}`)
  console.log('root 可见工具:', tools.names())

  console.log('\n== 2. fork 出 child（一次会话），遮蔽一个会话私有的工具注册表 ==')
  const child = new MiniContext(root, 'session#1')
  child.plugin((ctx) => {
    // 先回落拿到底层注册表（此刻 child 还没 provide，get('tools') 命中 root 的）
    const rootTools = ctx.get('tools')
    // 再 provide 同名服务把 root 的遮蔽掉：本地层 + 父级回落。
    // 这就是 dsh 工具系统 ScopedLayers（作用域分层）的雏形 —— 见 s05。
    ctx.provide('tools', () => {
      const local = new Map()
      return {
        register(name, run) { local.set(name, run); ctx.emit('tools/changed', { name }) },
        async call(name, args) {
          return local.has(name) ? local.get(name)(args) : rootTools.call(name, args)
        },
        names: () => [...new Set([...local.keys(), ...rootTools.names()])],
      }
    })
    // 会话级插件：给这次会话临时加一个工具 —— dsh 的 tool-subagent / plan-mode
    // 这类"按会话开关的能力"就是这么挂上去的。
    ctx.get('tools').register('session_private', async () => '只有本会话可见')
    return () => console.log(`[teardown] ${ctx.name} 的私有工具层已回收`)
  })
  console.log('child 可见工具:', child.get('tools').names(), '<- 本地层在前，父级回落在后')

  console.log('\n== 3. 事件冒泡：child 里注册工具，root 的 audit 插件也收到 ==')
  console.log(child.get('audit'))

  console.log('\n== 4. 卸载 child：逆序回滚，root 不受影响 ==')
  await child.dispose()
  console.log('root 可见工具:', root.get('tools').names())
  console.log('root audit 日志:', root.get('audit'))

  console.log('\n== 5. 卸载 root：全部插件逆序清理 ==')
  await root.dispose()

  console.log('\n结论：装配 = 加载一组插件；换能力 = 换插件；卸能力 = dispose。')
  console.log('dsh 的 web/headless/sdk profile 就是同一内核 + 不同插件清单（见 s10）。')
}

main().catch((e) => { console.error(e); process.exit(1) })
