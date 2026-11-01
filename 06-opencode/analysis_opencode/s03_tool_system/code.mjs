#!/usr/bin/env node
/**
 * s03_tool_system.mjs —— 工具注册表：三层来源、按模型裁剪、截断外包
 *
 * OpenCode 每一轮请求前都现场重算"模型可见工具集"（session/tools.ts 的
 * resolve → tool/registry.ts 的 tools()），流程是三层过滤的交集：
 *
 *   ① 三层合并      内置(17个, registry.ts:231-249)
 *                 + 磁盘 {tool,tools}/*.{js,ts} (:184-197)
 *                 + 插件 p.tool (:199-204)
 *   ② 按模型裁剪    websearch 仅 opencode provider (:293-295)
 *                 gpt-* 换 apply_patch、去 edit/write (:297-300, s05 展开)
 *                 question 仅 client ∈ {app,cli,desktop} (:207)
 *   ③ 权限削视野    全 deny 的权限键直接从可见集消失
 *                 (permission/index.ts:204-219) —— 模型根本不知道它存在
 *
 *   请求里最终出现的 schema = 三层合并 ∩ 模型裁剪 ∩ 权限视野
 *
 * 另有一处上下文工程代表作：工具输出超 2000 行 / 50KB（tool/truncate.ts:14-15）
 * → 全文落 truncation 目录 → 只回预览 + 反向引导："交给 explore agent 去读"
 * （:129-133）—— 用截断机制引导模型做上下文外包。
 *
 * 运行：node code.mjs   （零依赖，离线）
 * 对照真实源码：packages/opencode/src/tool/registry.ts、tool/truncate.ts、
 *              tool/tool.ts（自动包裹）、permission/index.ts（visibleTools）
 */

import { deepFreeze } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：三层合并的注册表
// ---------------------------------------------------------------
// 每个工具：{ id, description, gate?, run }。
// gate 是"裁剪谓词"——对应 registry.ts 里 tools() 那段 filter 的每个 if。
class ToolRegistry {
  constructor() {
    this.layers = { builtin: new Map(), disk: new Map(), plugin: new Map() }
  }

  /** 同名遮蔽：disk 盖 builtin，plugin 盖 disk——与真实 merge 顺序一致 */
  register(layer, tool) {
    if (!this.layers[layer]) throw new Error(`未知来源层: ${layer}`)
    this.layers[layer].set(tool.id, deepFreeze(tool))
    return this
  }

  /** 第①步：三层合并（builtin → disk → plugin） */
  merged() {
    const out = new Map()
    for (const layer of ['builtin', 'disk', 'plugin']) for (const t of this.layers[layer].values()) out.set(t.id, t)
    return out
  }

  /**
   * 第②步：按模型/客户端/旗标裁剪（registry.ts :293-300 的 mini 版）。
   * 注意：裁剪发生在 schema 进请求之前，被裁掉的工具对模型"不存在"。
   */
  byModel({ providerID, modelID, client = 'cli', flags = {} }) {
    const out = new Map()
    for (const t of this.merged().values()) {
      if (t.id === 'websearch' && providerID !== 'opencode' && !flags.exa && !flags.parallel) continue
      if (t.id === 'question' && !['app', 'cli', 'desktop'].includes(client)) continue
      if (t.id === 'execute' && !flags.experimentalCodeMode) continue
      out.set(t.id, t)
    }
    return out
  }

  /** 第③步：权限削视野（permission/index.ts :204-219 的 mini 版）——
   *  对某权限键"任意 pattern 都 deny"的工具从可见集里删掉 */
  static denyPrune(tools, rules) {
    const out = new Map()
    for (const [id, t] of tools) {
      const denied = rules.some((r) => r.permission === id && r.pattern === '*' && r.action === 'deny')
      if (!denied) out.set(id, t)
    }
    return out
  }
}

// ---------------------------------------------------------------
// 第 2 部分：截断 + 落盘 + 反向引导（tool/truncate.ts 的 mini 版）
// ---------------------------------------------------------------
const MAX_LINES = 2000
const MAX_BYTES = 50 * 1024

/** 判定是"行数与字节数都不超才原样返回"——两个阈值各管一类失控 */
function needsTruncation(text) {
  return text.split('\n').length > MAX_LINES || Buffer.byteLength(text, 'utf8') > MAX_BYTES
}

/** 超限 → 全文落 truncation 目录 → 只回预览 + 委派提示 */
function truncate(text, artifactStore) {
  const lines = text.split('\n')
  const preview = lines.slice(0, 20).join('\n')
  const path = `truncation/artifact-${artifactStore.length + 1}.txt`
  artifactStore.push({ path, totalLines: lines.length, content: text })
  const hint =
    'Output truncated. If this agent has the task tool, delegate to the explore agent to read it, instead of reading it yourself.'
  return `${preview}\n... [showing 20 of ${lines.length} lines. Full output saved to ${path}]\n[tool emits hint] ${hint}`
}

// ---------------------------------------------------------------
// 第 3 部分：演示
// ---------------------------------------------------------------
function main() {
  console.log('== 场景 1：三层合并 —— 内置 / 磁盘 / 插件，同名后者遮蔽 ==')
  const reg = new ToolRegistry()
  reg.register('builtin', { id: 'read', description: '读文件（内置）', run: () => '...' })
  reg.register('builtin', { id: 'bash', description: '跑命令（内置）', run: () => '...' })
  reg.register('disk', { id: 'db_query', description: '用户丢在 .opencode/tool/ 的查询工具', run: () => '...' })
  reg.register('plugin', { id: 'deploy', description: 'npm 插件注册的部署工具', run: () => '...' })
  reg.register('disk', { id: 'read', description: '用户覆写的 read（遮蔽内置）', run: () => '...' })
  console.log(`    合并结果: ${[...reg.merged().keys()].join(', ')}`)
  console.log(`    read 的描述来自: ${reg.merged().get('read').description}`)

  console.log('\n== 场景 2：按模型/客户端裁剪 —— 同一张表，四种请求视野不同 ==')
  reg
    .register('builtin', { id: 'websearch', description: '联网搜索', run: () => '...' })
    .register('builtin', { id: 'question', description: '向用户提问', run: () => '...' })
    .register('builtin', { id: 'execute', description: 'code-mode 解释器', run: () => '...' })
  const views = [
    ['opencode provider + cli', { providerID: 'opencode', modelID: 'claude-x', client: 'cli' }],
    ['第三方 provider + cli', { providerID: 'anthropic', modelID: 'claude-x', client: 'cli' }],
    ['opencode provider + vscode 扩展', { providerID: 'opencode', modelID: 'claude-x', client: 'vscode' }],
    ['opencode provider + 实验旗标全开', { providerID: 'opencode', modelID: 'claude-x', client: 'cli', flags: { experimentalCodeMode: true } }],
  ]
  for (const [label, req] of views) {
    console.log(`    ${label.padEnd(22)} → [${[...reg.byModel(req).keys()].join(', ')}]`)
  }
  console.log('    → websearch 只跟 provider 走；question 只跟 client 走；execute 只跟实验旗标走')

  console.log('\n== 场景 3：deny 削视野 —— 被禁的工具从请求里消失（失败路径前半段）==')
  const req = { providerID: 'opencode', modelID: 'claude-x', client: 'cli' }
  console.log(`    无权限规则: [${[...ToolRegistry.denyPrune(reg.byModel(req), []).keys()].join(', ')}]`)
  const rules = [{ permission: 'deploy', pattern: '*', action: 'deny' }]
  console.log(`    deny deploy 后: [${[...ToolRegistry.denyPrune(reg.byModel(req), rules).keys()].join(', ')}]`)
  console.log('    → 模型不会看到 deploy schema，也就不会反复发起注定被拒的调用')

  console.log('\n== 场景 4：截断外包 —— 3000 行构建日志的落地（失败路径后半段）==')
  const artifactStore = []
  const buildLog = Array.from({ length: 3000 }, (_, i) => `[build] step ${i}: ok`).join('\n')
  console.log(`    超限判定: ${buildLog.split('\n').length} 行 > ${MAX_LINES} → ${needsTruncation(buildLog)}`)
  const result = truncate(buildLog, artifactStore)
  console.log(`    返回给模型的预览（前 3 行）:`)
  result.split('\n').slice(0, 3).forEach((l) => console.log(`      ${l}`))
  console.log(`    落盘 artifact: ${artifactStore[0].path}（全文 ${artifactStore[0].totalLines} 行，模型可按 path 读回）`)
  console.log(`    委派提示已附在结果尾部 → 模型会转而调 task 工具外包给 explore agent`)

  console.log('\n结论：模型可见工具集 = 三层合并 ∩ 模型裁剪 ∩ 权限视野；')
  console.log('截断不只是防御，还是"引导模型外包上下文"的主动设计。')
}

try {
  main()
} catch (e) {
  console.error(e)
  process.exit(1)
}
