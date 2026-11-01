#!/usr/bin/env node
/**
 * s08_prompt_family.mjs —— 提示词拼装线：四段顺序 + 指令发现 + 就近附带去重
 *
 * s05 看了"按模型选家族模板"，本课看完整拼装线（prompt.ts:1264-1269）：
 *
 *   system[] = [
 *     family template      ← system.ts 的 system(model)（s05 的前缀路由）
 *     environment          ← 模型身份 + <env>（cwd/worktree/git/平台/日期，:74-104）
 *     instructions         ← AGENTS.md 类项目指令（instruction.ts，首个命中即停）
 *     mcp_instructions     ← MCP 工具说明（session/tools.ts 生成）
 *     skills               ← 技能清单（verbose 版；工具描述里另有简版）
 *   ]
 *
 *   顺序纪律：system 数组排在请求最前面，任何逐请求变化的字节都会让
 *   provider 的前缀缓存整段失效——所以日期刻意按天冻结（toDateString()）。
 *
 * 指令发现（instruction.ts）：
 *   · 全局：~/.config/opencode/AGENTS.md（兼容 ~/.claude/CLAUDE.md）
 *   · 项目：候选 ["AGENTS.md","CLAUDE.md","CONTEXT.md"(deprecated)]，
 *     从当前目录 findUp 到 worktree，★ 首个命中即 break，不逐层堆叠
 *   · 就近附带：模型读到某文件时，从该文件目录向上找 AGENTS.md 附带进本轮；
 *     去重 Map 的 key 是 assistant messageID（一轮一清），不是 sessionID
 *
 * 运行：node code.mjs   （零依赖，离线）
 * 对照真实源码：packages/opencode/src/session/prompt.ts:1264-1269（拼装顺序）
 *              packages/opencode/src/session/system.ts:74-119（环境段/skills）
 *              packages/opencode/src/session/instruction.ts（指令发现与 resolve）
 */

import { countTokens } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：四段拼装（prompt.ts:1264-1269 的 mini 版）
// ---------------------------------------------------------------
function assemble({ family, environment, instructions, mcpInstructions, skills }) {
  const sections = [
    ['family', family],
    ['environment', environment],
    ['instructions', instructions],
    ['mcp_instructions', mcpInstructions],
    ['skills', skills],
  ].filter(([, text]) => text)
  return sections.map(([name, text]) => ({ name, text, tokens: countTokens(text) }))
}

/** 环境段（system.ts:74-104 的 mini 版）：注意日期按天冻结 */
function buildEnvironment({ modelID, providerID, cwd, worktree, isGit }) {
  return [
    `You are powered by the model named ${modelID}. The exact model ID is ${providerID}/${modelID}`,
    'Here is some useful information about the environment you are running in:',
    '<env>',
    `  Working directory: ${cwd}`,
    `  Workspace root folder: ${worktree}`,
    `  Is directory a git repo: ${isGit ? 'yes' : 'no'}`,
    `  Platform: ${process.platform}`,
    `  Today's date: ${new Date().toDateString()}`, // 粒度=天：同一天内字节完全一致，保前缀缓存
    '</env>',
  ].join('\n')
}

// ---------------------------------------------------------------
// 第 2 部分：指令发现（instruction.ts 的 mini 版）
// ---------------------------------------------------------------
// mock 文件树：路径 → 是否存在指令文件；CANDIDATES 顺序即优先级。
const FILES = {
  'repo/AGENTS.md': 'repo 级规矩：提交前跑 lint。',
  'repo/src/AGENTS.md': 'src 级规矩：新增模块要配测试。',
  'repo/src/db/AGENTS.md': 'db 级规矩：连接池必须复用，禁止每查询建连。',
  'repo/src/api/AGENTS.md': 'api 级规矩：所有端点先过 zod 校验。',
}
const CANDIDATES = ['AGENTS.md', 'CLAUDE.md', 'CONTEXT.md'] // CONTEXT.md 已标 deprecated

/** 从 fileDir 向上 findUp 到 worktree 为止；每个目录内按 CANDIDATES 顺序试；
 *  ★ 首个命中即 break——不逐层堆叠 */
function findProjectInstruction(fileDir, worktree, { stackAll = false } = {}) {
  const hits = []
  let dir = fileDir
  outer: while (true) {
    for (const name of CANDIDATES) {
      const path = `${dir}/${name}`
      if (FILES[path]) {
        hits.push(path)
        if (!stackAll) break outer // 真实行为：首个命中即停
      }
    }
    if (dir === worktree) break
    dir = dir.split('/').slice(0, -1).join('/')
  }
  return hits
}

/** 就近附带 + claims 去重（instruction.ts resolve 的 mini 版）。
 *  claims 的 key 是 assistant messageID：一条 assistant 消息 = 一轮 provider
 *  往返，这轮里模型可能连读十几个文件，同目录只附带一次；下轮（新 messageID）
 *  允许重新附带——那时它已是"很久之前读过的文件"。 */
function resolveNearby(filePath, claims, messageID) {
  const dir = filePath.split('/').slice(0, -1).join('/')
  const hits = findProjectInstruction(dir, 'repo')
  const attached = []
  for (const path of hits) {
    const key = `${messageID}:${path}`
    if (claims.has(key)) {
      console.log(`      ${filePath} → ${path} 已在本轮附带过，去重跳过`)
      continue
    }
    claims.set(key, true)
    attached.push(path)
    console.log(`      ${filePath} → 附带 ${path}`)
  }
  return attached
}

// ---------------------------------------------------------------
// 第 3 部分：演示
// ---------------------------------------------------------------
function main() {
  console.log('== 场景 1：四段拼装 —— 顺序与 token 账本 ==')
  const sections = assemble({
    family: '（anthropic.txt 家族模板……约 1200 token 的系统人格与行为规范）',
    environment: buildEnvironment({ modelID: 'claude-sonnet-x', providerID: 'anthropic', cwd: '/home/u/repo', worktree: '/home/u/repo', isGit: true }),
    instructions: 'repo 级规矩：提交前跑 lint。',
    mcpInstructions: '（MCP 工具使用说明……）',
    skills: '## Skills\n- pdf：处理 PDF……（verbose 版，工具描述里另有简版）',
  })
  let total = 0
  for (const s of sections) {
    total += s.tokens
    console.log(`    ${s.name.padEnd(18)} ~${String(s.tokens).padStart(5)} tok`)
  }
  console.log(`    ${'合计'.padEnd(16)} ~${total} tok（估算式 = 字符数/4，core/src/util/token.ts:4）`)
  console.log('    → 前两段在同一天内字节稳定（前缀缓存友好）；会话相关内容压到后段')

  console.log('\n== 场景 2：指令发现 —— 首个命中即停，不逐层堆叠 ==')
  const best = findProjectInstruction('repo/src/db', 'repo')
  console.log(`    从 repo/src/db 向上: 命中 ${JSON.stringify(best)}`)
  console.log(`    命中内容: "${FILES[best[0]]}"`)
  const greedy = findProjectInstruction('repo/src/db', 'repo', { stackAll: true })
  const waste = greedy.reduce((n, p) => n + countTokens(FILES[p]), 0) - countTokens(FILES[best[0]])
  console.log(`    若逐层堆叠: ${JSON.stringify(greedy)} → 多花 ~${waste} tok，且三层规矩互相覆盖语义模糊`)

  console.log('\n== 场景 3：就近附带 + claims 去重（key = messageID）==')
  const claims = new Map()
  console.log('    第 1 轮（messageID=asst-1），模型连读三个文件:')
  resolveNearby('repo/src/db/pool.ts', claims, 'asst-1')
  resolveNearby('repo/src/db/index.ts', claims, 'asst-1') // 同目录 → 去重
  resolveNearby('repo/src/api/server.ts', claims, 'asst-1')
  console.log('    第 2 轮（messageID=asst-2），再读 src/db/ 下的文件:')
  resolveNearby('repo/src/db/pool.ts', claims, 'asst-2') // 新一轮 → 允许重新附带
  console.log('    → key 若用 sessionID，第 2 轮会被错误去重——语境已经变了')

  console.log('\n== 场景 4：空指令兜底（边界路径）==')
  const bare = assemble({
    family: '（anthropic.txt）',
    environment: buildEnvironment({ modelID: 'm', providerID: 'p', cwd: '/x', worktree: '/x', isGit: false }),
    instructions: null,
    mcpInstructions: null,
    skills: null,
  })
  console.log(`    只有 ${bare.length} 段: ${bare.map((s) => s.name).join(' + ')} → 照样能跑`)

  console.log('\n结论：系统提示词 = family + environment + instructions + mcp + skills；')
  console.log('指令发现"首个命中即停"，就近附带按 messageID 去重——克制才有缓存与可控的 token。')
}

try {
  main()
} catch (e) {
  console.error(e)
  process.exit(1)
}
