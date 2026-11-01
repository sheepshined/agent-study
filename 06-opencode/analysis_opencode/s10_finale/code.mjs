#!/usr/bin/env node
/**
 * s10_finale.mjs —— 收官：独立 git-dir 的 undo + 多前端装配对照
 *
 * OpenCode 的 undo 能力建立在一个反直觉的设计上（snapshot/index.ts:71-75）：
 * 不碰项目自己的 .git，而是给 git 两个旗标——
 *
 *     git --git-dir <data>/snapshot/<projectID>/<hash(worktree)> \
 *         --work-tree <worktree> ...
 *
 *   即"把 git 当纯内容寻址存储用"：快照仓库按 projectID + worktree 哈希
 *   隔离，内容寻址意味着相同内容只存一份，非 git 目录也能 revert/undo。
 *   revert 的锚点是消息（revert.ts:40-）：记录 {messageID, partID, snapshot,
 *   diff}，恢复 = snap.restore(snapshot) + snap.revert(patches)。
 *
 *   ┌─ 文件树 ─────┐  snapshot()   ┌─ 内容寻址仓 ─────┐
 *   │ a.ts = "v1"  │ ────────────▶ │ sha1("v1") → v1  │
 *   │ a.ts = "v2"  │  revert(记录)  │ sha1("v2") → v2  │
 *   └──────────────┘ ◀──────────── └──────────────────┘
 *        revert 记录挂在消息上：{messageID, snapshot, diff}
 *
 * 收官第二问：多前端装配。TUI/Web/Electron/VS Code/ACP/GitHub Action
 * 都只是同一协议面的客户端（s09）——装配表里内核只出现一次。
 *
 * 运行：node code.mjs   （零依赖，离线）
 * 对照真实源码：packages/opencode/src/snapshot/index.ts:71-75（独立 git-dir）
 *              packages/opencode/src/session/revert.ts:40-（revert 元数据）
 *              packages/opencode/src/session/session.ts:162-168/:691（fork 命名）
 */

import { createHash } from 'node:crypto'

const sha1 = (s) => createHash('sha1').update(s).digest('hex').slice(0, 12)

// ---------------------------------------------------------------
// 第 1 部分：内容寻址快照仓（独立 git-dir 的 mini 版）
// ---------------------------------------------------------------
/** MiniStore：blob（内容 hash → 内容）+ tree（树 hash → {path: contentHash}）。
 *  相同内容天然去重——这就是"内容寻址"的全部收益。 */
class MiniStore {
  constructor() {
    this.blobs = new Map() // 内容 hash → 内容
    this.trees = new Map() // 树 hash → {path: contentHash}
    this.blobWrites = 0
  }

  snapshot(files) {
    const tree = {}
    for (const [p, c] of Object.entries(files)) {
      const h = sha1(c)
      if (!this.blobs.has(h)) this.blobWrites++
      this.blobs.set(h, c)
      tree[p] = h
    }
    const treeHash = sha1(JSON.stringify(tree))
    this.trees.set(treeHash, tree)
    return treeHash
  }

  checkout(treeHash) {
    const tree = this.trees.get(treeHash)
    if (!tree) throw new Error(`快照不存在: ${treeHash}`)
    const out = {}
    for (const [p, h] of Object.entries(tree)) out[p] = this.blobs.get(h)
    return out
  }
}

// ---------------------------------------------------------------
// 第 2 部分：revert 记录（挂在消息上，不挂时间点）
// ---------------------------------------------------------------
const messages = [] // {id, action, filesBefore}
const revertLog = [] // {messageID, snapshot, diff}

function agentEdit(store, files, file, newContent, messageID) {
  const before = files[file] ?? ''
  const snap = store.snapshot({ ...files }) // ★ 写前快照：undo 的目标就是它（revert 元数据挂在本条消息上）
  files[file] = newContent
  const diff = before ? `${file} 变更 ${Math.abs(newContent.length - before.length)} 字节` : `${file} 首次写入`
  revertLog.push({ messageID, snapshot: snap, diff })
  console.log(`    [消息 ${messageID}] agent 写 ${file} → 写前快照 ${snap}（${diff}）`)
}

function undo(store, files) {
  const last = revertLog.at(-1)
  if (!last) throw new Error('没有可撤销的操作')
  const restored = store.checkout(last.snapshot)
  Object.assign(files, restored)
  revertLog.pop() // mini 版：撤销后该记录消费掉（真实代码用 revert/unrevert 双向记录）
  console.log(`    [undo] 取快照 ${last.snapshot} → ${Object.entries(files).map(([p, c]) => `${p}="${c}"`).join(', ')}`)
  return last
}

// ---------------------------------------------------------------
// 第 3 部分：fork 命名（session.ts:162-168 的 mini 版）
// ---------------------------------------------------------------
const titles = new Set()
function forkTitle(base) {
  // 真实实现：正则 /^(.+) \(fork #(\d+)\)$/ 找前缀，序号从 1 递增找最小空位
  for (let n = 1; ; n++) {
    const t = `${base} (fork #${n})`
    if (!titles.has(t)) {
      titles.add(t)
      return t
    }
  }
}

// ---------------------------------------------------------------
// 第 4 部分：多前端装配（内核零感知前端的落点演示）
// ---------------------------------------------------------------
// 同一份内核，三种壳。壳只能走协议（kernel.app.fetch / 事件流 / 迭代器），
// 直接摸内核私有状态 = 契约越界（s09 的规范条款在代码里的影子）。
async function assembleFrontends(kernel) {
  const manifests = [
    { name: 'stdout 壳（CI/headless）', transport: '进程内 app.fetch', ui: '无（纯文本输出）', real: 'opencode run' },
    { name: '迭代器壳（SDK）', transport: 'async 迭代器', ui: '调用方自选', real: 'packages/sdk/js · client' },
    { name: '事件订阅壳（TUI/Web）', transport: 'SSE /event', ui: 'SolidJS / React 组件', real: 'packages/tui · app · desktop' },
  ]
  console.log('    装配表（内核只出现一次）:')
  for (const m of manifests) console.log(`      ${m.name.padEnd(24)} 传输=${m.transport.padEnd(16)} UI=${m.ui.padEnd(16)} ↔ 真实: ${m.real}`)

  // 三种壳各跑同一轮请求
  const turn = { sessionID: 's-fin', text: '最终验收' }
  const r1 = await kernel.app.fetch(new Request('http://k/turn', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(turn) }))
  const viaHttp = await r1.json()
  const viaIterator = [...(await kernel.app.fetch(new Request('http://k/turn', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ ...turn, text: '最终验收' }) })).then((r) => r.json())).events]
  console.log(`    stdout 壳拿到 ${viaHttp.events.length} 个事件；SDK 壳迭代到 ${viaIterator.length} 个事件 —— 同一内核`)

  // 契约越界演示（失败路径）：壳试图直接改内核私有状态
  try {
    kernel.sessions.get('s-fin').events.length = 0 // 越界：绕过协议改存储
    console.log('    ✗ 越界动作竟然成功了——真实产品靠规范（specs/tui-package.md）+ SDK 生成把这条路堵死')
  } catch (e) {
    console.log(`    越界被拒: ${e.message}`)
  }
}

// ---------------------------------------------------------------
// 第 5 部分：演示
// ---------------------------------------------------------------
async function main() {
  console.log('== 场景 1：非 git 目录的 undo —— 内容寻址快照 ==')
  const store = new MiniStore()
  const files = { 'a.ts': 'export const v = 1' }
  const baseline = store.snapshot(files)
  console.log(`    v1 基线快照: ${baseline}（blob 写入 ${store.blobWrites} 次）`)
  messages.push({ id: 'msg-1', action: 'baseline' })
  agentEdit(store, files, 'a.ts', 'export const v = 2 // agent 改的', 'msg-2')
  console.log(`    当前文件: ${files['a.ts']}`)
  undo(store, files)
  console.log(`    undo 后:  ${files['a.ts']}`)
  console.log('    全程没碰任何项目 .git——快照仓在 data/snapshot/<projectID>/<hash(worktree)>')

  console.log('\n== 场景 2：revert 元数据 —— 锚点是消息，不是时间 ==')
  console.log('    一条 revert 记录的形状（revert.ts:40-）:')
  console.log('      { messageID: "msg-2", partID: "part-1", snapshot: "cd2c90ac8b35", diff: "a.ts 变更 12 字节" }')
  console.log('    → undo 的目标是"这条消息之前"的树；diff 同时服务 unrevert 与"看 agent 改了什么"的 UI')
  console.log('    每条新 prompt 先 revert.cleanup（prompt.ts:1056）；config.snapshot:false 可整体关闭')

  console.log('\n== 场景 3：fork 命名 —— 序号找最小空位（边界路径）==')
  titles.add('demo')
  console.log(`    fork(demo) → "${forkTitle('demo')}"`)
  console.log(`    fork(demo) → "${forkTitle('demo')}"`)
  const f1 = 'demo (fork #1)'
  titles.delete(f1) // 模拟 fork #1 被删除
  console.log(`    删除 "demo (fork #1)" 后再 fork → "${forkTitle('demo')}"（复用空位，不无限累加）`)

  console.log('\n== 场景 4：多前端装配 —— 内核只出现一次 ==')
  // mini 内核：与 s09 同构的 app.fetch（精简为一轮 mock 事件）
  const sessions = new Map()
  const kernel = {
    sessions,
    app: {
      async fetch(request) {
        const { sessionID, text } = await request.json()
        const s = sessions.get(sessionID) ?? { id: sessionID, events: [] }
        s.events = [{ type: 'tool-call', name: 'read' }, { type: 'step-finish', finish: 'stop', tokens: 99, echo: text }]
        sessions.set(sessionID, s)
        return Response.json({ sessionID, events: s.events })
      },
    },
  }
  await assembleFrontends(kernel)

  console.log('\n收官结论：undo 靠"独立 git-dir 的内容寻址快照 + 消息锚点的 revert 记录"；')
  console.log('产品矩阵靠"内核零感知前端 + 装配表里的壳差异"。载具造完了——去真源码里重走一遍吧。')
}

main().catch((e) => { console.error(e); process.exit(1) })
