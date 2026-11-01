#!/usr/bin/env node
/**
 * s07_plugin_host.mjs —— mini plugin-host：入口短路、manifest 校验、白名单变量、进程隔离
 *
 * ZCode 的插件（MCP server / 技能包 / 自定义命令）跑在独立 plugin-host 进程：
 *
 *   main.ts 入口顺序（顺序就是安全顺序）：
 *     1 清洗 shell 注入的 NODE_ENV/代理/证书变量
 *     2 protocol/TUI 模式把 console 改道 stderr（stdout 是帧通道，s10）
 *     3 ★ plugin-host 短路：isPluginHostInvocation(argv) 命中就直接当宿主，
 *       绝不 import 整套 Agent（23 万行内核）—— 只为跑插件不必装内核
 *     4 普通路径才 await import("./run.js") 进命令分流
 *
 *   plugin-host（cli/src/plugin-host-command.ts）：
 *     · 拉起 plugin 声明的 server 入口，与内核经 stdio 通信
 *     · broker token 不裸躺在 env（入口已 capture）——恢复凭据前必须三重校验
 *       （权威 plugin id + 完整凭据组 + canonical socket），任一不匹配在 import() 之前拒绝：
 *       "capture 的存在不能证明当前 server 可信"（头注释的威胁模型）
 *
 *   变量白名单（apps/zcode-cli/README.md:114-122）：
 *     manifest 里 ${VAR} 只展开 ZCODE_ 前缀环境变量与固定变量
 *     （ZCODE_PLUGIN_ROOT / ZCODE_PLUGIN_DATA / ZCODE_PROJECT_DIR / user_config.*）。
 *     白名单外原样保留 —— 不展开 = 不泄漏。
 *
 *   manifest 契约（.zcode-plugin/plugin.json）：
 *     name/version/description/author/license/skills/commands/mcpServers/userConfig
 *
 * 运行：node code.mjs        （零依赖，离线；"进程"用 try/catch + 退出码模拟进程边界）
 * 对照真实源码：apps/zcode-cli/packages/cli/src/{main.ts,plugin-host-command.ts}、
 *              apps/zcode-cli/README.md（插件章节）、CONTEXT.md（安装态编目）
 */

import { assert, banner } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：入口分流（main.ts 的 mini 版，顺序即安全顺序）
// ---------------------------------------------------------------
const AGENT_RUNTIME = Symbol('整 Agent 运行时（很重：三层循环/权限/工具/压缩…）')

function sanitizeEnv(env) {
  const cleaned = { ...env }
  // main.ts :21 注释：入口先清洗用户 shell 注入的 NODE_ENV、代理和证书变量
  delete cleaned.NODE_ENV
  return cleaned
}

function isPluginHostInvocation(argv) {
  return argv[0] === '__zcode-plugin-host'   // 真实常量 ZCODE_PLUGIN_HOST_COMMAND
}

/** 模拟 main(argv)：返回 { loaded } 表示这条路径实际加载了什么 */
function cliMain(argv, env) {
  const cleaned = sanitizeEnv(env)
  if (isPluginHostInvocation(argv)) {
    // ★ 短路：不 import run.js —— 下面的 AGENT_RUNTIME 不会被碰
    return { loaded: ['plugin-host-runtime'], cleaned, agentLoaded: false, argv }
  }
  return { loaded: ['full-agent-runtime'], cleaned, agentLoaded: true, argv } // await import("./run.js")
}

// ---------------------------------------------------------------
// 第 2 部分：manifest 校验 + 白名单变量展开
// ---------------------------------------------------------------
const REQUIRED_FIELDS = ['name', 'version', 'license']

function validateManifest(manifest) {
  for (const f of REQUIRED_FIELDS) {
    if (!manifest[f]) throw new Error(`[manifest] 缺少必填字段 ${f} —— 拒绝装载`)
  }
  return true
}

/** 只展开白名单变量（README:114-122 的 mini 版）。返回展开表让"什么被留白"可见。 */
function expandVars(template, { env, userConfig }) {
  const fixed = {
    ZCODE_PLUGIN_ROOT: '/plugins/cache/browser-use',
    ZCODE_PLUGIN_DATA: '/plugins/data/browser-use',
    ZCODE_PROJECT_DIR: '/work/demo',
  }
  return template.replace(/\$\{([A-Za-z_][A-Za-z0-9_.]*)\}/g, (_, name) => {
    if (name in fixed) return fixed[name]
    if (name.startsWith('ZCODE_')) return env[name] ?? `(未设置:${name})`
    if (name.startsWith('user_config.')) return userConfig[name.slice('user_config.'.length)] ?? ''
    // 白名单外：原样保留。不展开 = 插件拿不到 = 信息不泄漏
    return `\${${name}}`
  })
}

function loadPlugin(manifest, ctx) {
  validateManifest(manifest)
  const resolved = {}
  for (const [k, v] of Object.entries(manifest.env ?? {})) resolved[k] = expandVars(v, ctx)
  return { name: manifest.name, resolved }
}

// ---------------------------------------------------------------
// 第 3 部分：宿主凭据边界（plugin-host-command.ts 头注释威胁模型的 mini 版）
// ---------------------------------------------------------------
function hostBootstrap({ serverPath, declaredPluginId, capture, registry }) {
  // 三重校验：权威 plugin id（由 resolver 写入 registry，不是 server 自己报的）
  //          + 完整凭据组 + canonical socket
  const entry = registry[declaredPluginId]
  if (!entry) throw new Error('declared plugin id 不在权威注册表 —— 拒绝恢复凭据')
  if (entry.serverPath !== serverPath) throw new Error(`server path 与注册表不符（被替换？）: ${serverPath}`)
  if (!capture || !capture.token || !capture.socket) throw new Error('凭据组不完整 —— 拒绝恢复')
  if (capture.socket !== entry.canonicalSocket) throw new Error('socket 不是 canonical —— 拒绝')
  return { tokenRestored: true }
}

// ---------------------------------------------------------------
// 第 4 部分：main() —— 四个场景
// ---------------------------------------------------------------
async function main() {
  banner('场景 1：入口分流 —— plugin-host 不加载 Agent')
  const env = { NODE_ENV: 'production', ZCODE_MAX_TURNS: '5' }
  const normal = cliMain(['zcode', '-p', 'hi'], env)
  const host = cliMain(['__zcode-plugin-host', '/plugins/cache/browser-use/server.js'], env)
  console.log(`  普通路径 loaded: ${normal.loaded}（agentLoaded=${normal.agentLoaded}）`)
  console.log(`  宿主路径 loaded: ${host.loaded}（agentLoaded=${host.agentLoaded}）← 23 万行内核没被碰`)
  assert(host.agentLoaded === false && normal.agentLoaded === true)

  banner('场景 2：白名单变量展开 —— 外面的世界原样保留')
  const manifest = {
    name: 'browser-use', version: '1.0.0', license: 'Apache-2.0',
    env: {
      BROWSER_PATH: '${ZCODE_PLUGIN_ROOT}/bin/chrome',     // 固定变量
      MAX_TURNS: '${ZCODE_MAX_TURNS}',                     // ZCODE_ 前缀 env
      STYLE: '${user_config.theme}',                       // userConfig
      EVIL: '${AWS_SECRET_ACCESS_KEY}',                    // 白名单外！
      PATH_REF: '${PATH}',                                 // 白名单外！
    },
  }
  const loaded = loadPlugin(manifest, { env, userConfig: { theme: 'zai-dark' } })
  for (const [k, v] of Object.entries(loaded.resolved)) console.log(`  ${k.padEnd(12)} = ${v}`)
  assert(loaded.resolved.EVIL === '${AWS_SECRET_ACCESS_KEY}' && loaded.resolved.PATH_REF === '${PATH}')

  banner('场景 3：宿主凭据边界 —— 被替换的 server 在 import 前被拒')
  const registry = {
    'zcode/browser-use': { serverPath: '/plugins/cache/browser-use/server.js', canonicalSocket: '/tmp/cua-broker.sock' },
  }
  const capture = { token: 'broker-bearer-xxx', socket: '/tmp/cua-broker.sock' }
  try { hostBootstrap({ serverPath: '/plugins/cache/browser-use/server.js', declaredPluginId: 'zcode/browser-use', capture, registry }); console.log('  合法 server: 凭据恢复 ✓') }
  catch (e) { console.log(`  合法 server 被拒（不应发生）: ${e.message}`) }
  try {
    hostBootstrap({ serverPath: '/tmp/evil/server.js', declaredPluginId: 'zcode/browser-use', capture, registry })
  } catch (e) { console.log(`  伪造 server: ${e.message} ← 在 import() 之前拒绝`) }
  try {
    hostBootstrap({ serverPath: '/plugins/cache/browser-use/server.js', declaredPluginId: 'zcode/unknown', capture, registry })
  } catch (e) { console.log(`  未知 plugin id: ${e.message}`) }

  banner('场景 4：失败路径 —— 插件崩溃不连坐内核 + 孤儿编目')
  // "进程边界"：插件在独立进程里崩，这里用同步异常模拟该进程的死亡
  function pluginProcess() { throw new Error('MCP server 内存耗尽（模拟崩溃）') }
  let hostExitCode = 0
  try { pluginProcess() } catch { hostExitCode = 1 }
  const kernelAlive = true // 内核在另一个"进程"，毫发无损
  console.log(`  插件进程退出码=${hostExitCode}；内核进程存活=${kernelAlive} —— 损失一个 MCP server，不陪葬`)
  // 孤儿插件：缓存里有目录，manifest 已缺失
  const installed = [{ id: 'browser-use', manifest: {} }, { id: 'legacy-tool', manifest: null }]
  const catalog = installed.map((p) => ({
    id: p.id,
    state: p.manifest ? 'builtin-or-cdn' : 'orphaned',   // CONTEXT.md:75-81 的分类语义
  }))
  console.log(`  编目: ${JSON.stringify(catalog)} —— orphaned 是编目态，不是崩溃态`)

  console.log('\n结论：入口顺序即安全顺序；变量白名单不展开即不泄漏；进程边界替不存在的 OS 沙箱站岗。')
}

main().catch((e) => { console.error(e); process.exit(1) })
