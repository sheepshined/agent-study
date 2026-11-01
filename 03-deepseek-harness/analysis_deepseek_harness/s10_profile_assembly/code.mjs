#!/usr/bin/env node
/**
 * s10_profile_assembly.mjs —— profile 装配：同一棵插件树，装出不同产品形态
 *
 * 收官课：把 s01–s09 的插件全部装回一棵树，然后回答 dsh 最有辨识度的问题
 * ——同一个内核怎么同时是 CLI、Web 应用、桌面应用和 SDK 服务？
 *
 * dsh 的答案：profile 只是**插件清单**的差异 + 一个薄壳。
 *
 *   bundle/base（dsh-base）—— 共享第一层：模型适配器、工具、持久化、沙箱与审批
 *   bundle/headless ────── 增量：一次性跑完 turn → stdout（自动化/CI）
 *   bundle/web-app ─────── 增量：webserver + 会话控制器 + 前端静态资源
 *   bundle/sdk-app ─────── 增量：JSON-RPC 协议面（程序化调用）
 *   apps/cli 的 `dsh` 命令 = profile 引导器（选清单、装树、进壳）
 *
 *   共享插件层（s01-s09 全部家当）
 *   ┌──────────────────────────────┐
 *   │ loop · session · tools · llm │
 *   └───────────┬──────────────────┘
 *       ┌───────┴────────┐
 *   headless 壳        web 壳
 *   跑完打印退出       http://127.0.0.1:PORT/turn
 *
 * 运行：node code.mjs   （会临时起一个本地 http 服务，演示完即关）
 * 对照真实源码：packages/bundle/{base,headless,web-app,sdk-app}/、packages/boot/、apps/cli/
 */

import http from 'node:http'

// ---------------------------------------------------------------
// 第 0 部分：极简内核（s01 的 mini-Cordis 压缩版，只为装配演示）
// ---------------------------------------------------------------
function createContext(name) {
  const ctx = { name, plugins: [], services: new Map(), events: [] }
  ctx.emit = (type, payload) => ctx.events.push({ type, payload })
  ctx.provide = (key, factory) => ctx.services.set(key, { factory })
  ctx.get = (key) => {
    const reg = ctx.services.get(key)
    if (reg && !reg.instance) reg.instance = reg.factory(ctx)
    return reg?.instance
  }
  ctx.plugin = (label, setup) => { setup(ctx); ctx.plugins.push(label); return ctx }
  return ctx
}

// ---------------------------------------------------------------
// 第 1 部分：共享插件层 —— dsh-base 的 mini 版（s02/s03/s05 的家当）
// ---------------------------------------------------------------
const sharedPlugins = {
  session: (ctx) => { ctx.provide('session', () => ({ events: [] })) },          // s03
  tools: (ctx) => {
    ctx.provide('tools', () => ({
      registry: new Map(),
      register(name, run) { this.registry.set(name, run) },
      async call(name, args) { return this.registry.get(name)(args) },
    }))
  },                                                                             // s05（简化）
  loop: (ctx) => {
    // s02 的循环压缩版：模型脚本驱动，两步收工
    ctx.provide('loop', () => ({
      async turn({ script }) {
        const session = ctx.get('session')
        const trace = []
        for (const resp of script) {
          trace.push(`assistant: ${resp.text || '(调工具)'}`)
          for (const c of resp.calls ?? []) {
            trace.push(`tool/call: ${c.name}`)
            trace.push(`tool/result: ${await ctx.get('tools').call(c.name, c.args)}`)
          }
        }
        session.events.push(...trace)
        return { text: script.at(-1).text, trace }
      },
    }))
  },
}

/** 每个内核都有的内置工具 —— 同一份注册，所有 profile 共享 */
const builtinTools = (ctx) => {
  ctx.get('tools').register('read_file', async ({ path }) => `（模拟）${path} 的内容`)
}

// ---------------------------------------------------------------
// 第 2 部分：profile = 清单 + 薄壳
// ---------------------------------------------------------------
/** headless：跑完一轮 → 打印 → 退出。自动化 / CI 的形态 */
function createHeadlessKernel({ script }) {
  const ctx = createContext('headless')
  ctx.plugin('session', sharedPlugins.session)
  ctx.plugin('tools', sharedToolsWithBuiltins())
  ctx.plugin('loop', sharedPlugins.loop)
  return {
    async run(input) {
      const { text, trace } = await ctx.get('loop').turn({ script })
      return `【headless】输入: ${input}\n${trace.map((t) => `  ${t}`).join('\n')}\n  → ${text}`
    },
  }
}
function sharedToolsWithBuiltins() {
  return (ctx) => { sharedPlugins.tools(ctx); builtinTools(ctx) }
}

/** web：同一个内核，外面套 http 壳。交互产品的形态 */
function createWebKernel({ script }) {
  const ctx = createContext('web')
  ctx.plugin('session', sharedPlugins.session)
  ctx.plugin('tools', sharedToolsWithBuiltins())
  ctx.plugin('loop', sharedPlugins.loop)          // ★ 与 headless 完全同一份
  return {
    ctx,
    listen() {
      const server = http.createServer(async (req, res) => {
        if (req.method === 'POST' && req.url === '/turn') {
          let body = ''
          for await (const chunk of req) body += chunk
          const { message } = JSON.parse(body)
          const session = ctx.get('session')       // 真实 dsh：每请求映射到会话控制器
          const { text, trace } = await ctx.get('loop').turn({ script })
          session.events.push({ request: message, trace })
          res.setHeader('content-type', 'application/json')
          res.end(JSON.stringify({ reply: text, trace }))
        } else { res.statusCode = 404; res.end() }
      })
      return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)))
    },
  }
}

/** sdk：程序化 API 面。被别的代码当库用的形态 */
function createSdkKernel({ script }) {
  const ctx = createContext('sdk')
  ctx.plugin('session', sharedPlugins.session)
  ctx.plugin('tools', sharedToolsWithBuiltins())
  ctx.plugin('loop', sharedPlugins.loop)
  return { ctx, async *stream(input) { const r = await ctx.get('loop').turn({ script }); yield `${input} => ${r.text}` } }
}

// ---------------------------------------------------------------
// 第 3 部分：演示 —— 三种形态，同一份循环代码
// ---------------------------------------------------------------
async function main() {
  const script = [
    { text: '', calls: [{ name: 'read_file', args: { path: 'notes.txt' } }] },
    { text: 'notes.txt 写着今晚记得买牛奶。', calls: [] },
  ]

  console.log('== 1. headless 壳：跑完即走（CI / 脚本场景） ==')
  const headless = createHeadlessKernel({ script })
  console.log(await headless.run('看看 notes.txt'))

  console.log('\n== 2. web 壳：同一份 loop，套上 HTTP（浏览器产品的后端） ==')
  const web = createWebKernel({ script })
  const server = await web.listen()
  const port = server.address().port
  const resp = await fetch(`http://127.0.0.1:${port}/turn`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ message: '看看 notes.txt' }),
  })
  const data = await resp.json()
  console.log(`  POST http://127.0.0.1:${port}/turn`)
  console.log(`  回复: ${data.reply}`)
  console.log(`  web 会话日志条数: ${web.ctx.get('session').events.length}（请求级会话管理接的就是这里）`)
  server.close()

  console.log('\n== 3. sdk 壳：async 迭代器当 API（被别的程序当库用） ==')
  const sdk = createSdkKernel({ script })
  for await (const chunk of sdk.stream('看看 notes.txt')) console.log(`  ${chunk}`)

  console.log('\n== 4. 对照：三种形态的插件清单 ==')
  console.log('  headless: [session, tools, loop]')
  console.log('  web     : [session, tools, loop] + http 壳   ← loop 是同一份')
  console.log('  sdk     : [session, tools, loop] + 迭代器壳')
  console.log('\n结论：产品形态 = 共享插件层 + 清单差异 + 薄壳。')
  console.log('  dsh 的 web / desktop / acp / sdk profile 与此同构 —— "可组装的 agent 平台"')
  console.log('  说的不是口号，是装配方式：没有 fork 的代码库，只有不同的插件清单。')
  console.log('\n课程收官：回到 ../README.md 看整棵知识树，然后去真源码里重走一遍。')
}

main().catch((e) => { console.error(e); process.exit(1) })
