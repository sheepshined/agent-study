#!/usr/bin/env node
/**
 * s01_runloop.mjs —— mini-runLoop：while(true) 主循环 + processor 三态
 *
 * OpenCode 的主循环是 packages/opencode/src/session/prompt.ts 里的 runLoop
 * （上游 dev :1081-1341）：一个 260 行的 while(true)，每轮做四件事——
 * 重读投影 → 判退出 → 分派任务/压缩 → 调 processor 跑一步。
 *
 * 真实的三态判定（processor.ts :693-695）可能和直觉相反：
 *   if (needsCompaction) return "compact"
 *   if (blocked || error) return "stop"     ← 只有"权限被拒/出错"才停
 *   return "continue"                        ← 健康完成（哪怕 finish=stop）也是 continue！
 * 循环的"正常退出"完全由 runLoop 循环顶部的四条件说了算（prompt.ts :1106-1130）。
 *
 *   ┌────────────────────── miniRunLoop ──────────────────────┐
 *   │ while (true) {                                          │
 *   │   msgs = 重读投影(过滤已压缩)      ← 每轮重来，不拿旧数组 │
 *   │   if (shouldStop()) break  ← finish可信 ∧ 无挂账tool call│
 *   │                             ∧ 同轮配对                   │
 *   │   if (溢出标记) 入队压缩任务     ← 延迟一轮，不当场压     │
 *   │   if (分派 tasks: compaction) continue                   │
 *   │   result = processStep()  ← "compact"/"stop"/"continue"  │
 *   │   if (result === "stop") break  ← 只有 blocked/error 走这 │
 *   │   结算 tool call（真实代码在 stream 消费期间并发执行）      │
 *   │ }                                                       │
 *   └─────────────────────────────────────────────────────────┘
 *
 * 运行：node code.mjs   （零依赖，离线；模型由剧本化 Mock 扮演）
 * 对照真实源码：packages/opencode/src/session/prompt.ts（runLoop）
 *              packages/opencode/src/session/processor.ts（Result 三态）
 *              packages/opencode/src/session/overflow.ts（usable/isOverflow）
 */

// ---------------------------------------------------------------
// 第 1 部分：消息日志（只增不减的数组，s02 会把它升级成事件溯源）
// ---------------------------------------------------------------
// assistant 消息带 finish（provider 报的结束原因）与 parentID（回应哪条 user）；
// tool call 是挂在这条 assistant 上的 part（parentAssistant 指回它）——
// 这正是真实 hasToolCalls 的检查对象：最后一条 assistant 自己挂着的 tool parts。
let seq = 0
let log = []
const resetLog = () => { log = []; seq = 0 }
const append = (m) => { m.id = `m${++seq}`; log.push(m); return m }

// ---------------------------------------------------------------
// 第 2 部分：停环判定（prompt.ts :1106-1130 的 mini 版，四条件缺一不可）
// ---------------------------------------------------------------
function latest(msgs) {
  const user = [...msgs].reverse().find((m) => m.role === 'user')
  const assistant = [...msgs].reverse().find((m) => m.role === 'assistant')
  const tasks = msgs.filter((m) => m.role === 'task' && !m.done)
  return { user, assistant, tasks }
}

function shouldStop(msgs) {
  const { user, assistant } = latest(msgs)
  if (!assistant || !assistant.finish) return { stop: false, why: '无 finish，继续' }
  if (['tool-calls', 'unknown'].includes(assistant.finish))
    return { stop: false, why: `finish=${assistant.finish} 不可信，继续` }
  // hasToolCalls：最后一条 assistant 自己挂着的 tool call part（排除服务端自执行与中断孤儿，
  // mini 版从简）。provider 报 stop 但消息里还有 tool call → 继续跑，把结果回灌给模型。
  const hasToolCalls = log.some((m) => m.role === 'tool' && m.parentAssistant === assistant.id)
  if (hasToolCalls) return { stop: false, why: 'finish=stop 可信，但该 assistant 挂着 tool call（hasToolCalls）→ 回灌结果' }
  if (assistant.parentID !== user?.id) return { stop: false, why: 'assistant 不是对当前 user 的回应，继续' }
  return { stop: true, why: 'finish 可信 ∧ 无挂账 ∧ 同轮配对 → 停' }
}

// ---------------------------------------------------------------
// 第 3 部分：processor —— 消费一步流式事件，只回答三态
// ---------------------------------------------------------------
// 一次 processStep = 一次 provider 请求（消费一个"步"的剧本）。assistant 消息
// 在步开始时创建、随事件累积 parts、到 step-finish 写 finish。
async function processStep(stepScript, { parentID }) {
  const assistant = append({ role: 'assistant', finish: null, parentID })
  let needsCompaction = false
  for (const event of stepScript) {
    if (event.type === 'tool-call') {
      append({ role: 'tool', name: event.name, args: event.args, parentAssistant: assistant.id })
      console.log(`    [事件] tool-call ${event.name}(${JSON.stringify(event.args)})`)
    } else if (event.type === 'text') {
      console.log(`    [事件] text: ${event.text}`)
    } else if (event.type === 'step-finish') {
      assistant.finish = event.finish ?? 'stop'
      // overflow.ts：count >= usable 即判溢出（注意是 >=；limit=0 视为未知模型，不判溢出）
      needsCompaction = event.limit > 0 && event.tokens >= event.limit
      assistant.tokens = event.tokens
      console.log(`    [事件] step-finish finish=${assistant.finish} tokens=${event.tokens}/${event.limit}`)
    }
  }
  // 三态判定（processor.ts :693-695）：blocked/error 才 "stop"，健康完成也是 "continue"
  if (needsCompaction) return 'compact'
  return 'continue'
}

/** 步间结算：真实代码里工具执行发生在 stream 消费期间（AI SDK 的工具执行器），
 *  mini 版挪到两步之间——tool call 拿到结果、标记完成（part 本身仍挂在 assistant 上）。 */
function settleTools(executor) {
  for (const m of log) {
    if (m.role === 'tool' && m.result === undefined) {
      m.result = executor(m)
      console.log(`    [结算] ${m.name}(${JSON.stringify(m.args)}) → ${m.result}`)
    }
  }
}

// ---------------------------------------------------------------
// 第 4 部分：miniRunLoop —— 两级收束的主循环
// ---------------------------------------------------------------
async function miniRunLoop({ script, executor = () => 'ok', maxSteps = Infinity, label }) {
  console.log(`\n  ── ${label} 开始（maxSteps=${maxSteps === Infinity ? '∞' : maxSteps}）──`)
  let step = 0
  let cursor = 0 // 剧本游标：压缩轮不消费剧本（真实的压缩是独立一次模型调用，s08 展开）
  let overflowFlag = false // prompt.ts :1161-1168 的"溢出不当场压"标记
  while (true) {
    step++
    // 每轮从日志重读"压缩后视图"（真实代码 filterCompactedEffect :1092）
    const msgs = log.filter((m) => !m.compacted)

    // ① 先判退出（四条件）——正常轮唯一的出口
    const verdict = shouldStop(msgs)
    console.log(`  [轮 ${step}] 判停: ${verdict.why}`)
    if (verdict.stop) break

    // ② 溢出延迟处理：上一轮判出溢出，本轮才把压缩任务入队
    if (overflowFlag) {
      overflowFlag = false
      append({ role: 'task', kind: 'compaction', done: false })
      console.log('  [轮] 上一轮溢出 → 压缩任务入队（延迟一轮，不当场压）')
    }

    // ③ 分派任务队列：compaction 任务由内建压缩 agent 处理（这里 mock 之）
    const { tasks, user } = latest(msgs)
    const compaction = tasks.find((t) => t.kind === 'compaction')
    if (compaction) {
      compaction.done = true
      log.filter((m) => m.role !== 'task' && m !== user).forEach((m) => (m.compacted = true))
      // 摘要 assistant：finish 留空——它不是一次完整的 provider 轮次，不该触发停环
      append({ role: 'assistant', finish: null, parentID: compaction.id, summary: true })
      console.log('  [轮] 执行压缩：旧消息打 compacted 标记（日志只标记不删除，见 s02）')
      continue
    }

    // ④ maxSteps：末轮往历史尾部塞一条 assistant 角色的 prefill（:1304-1307）——
    //    靠"模型刚说完这句话"的惯性要求它只出文本。提示词级约束，不是硬闸。
    if (step >= maxSteps) console.log('  [轮] 末轮 → 尾部追加 MAX_STEPS_PROMPT（assistant prefill）')

    // ⑤ 调 processor 跑一步（剧本按步分发，每次消费一个"步"）
    const thisStep = script[cursor] ?? [{ type: 'step-finish', finish: 'stop', tokens: 50, limit: 8000 }]
    cursor++
    const result = await processStep(thisStep, { parentID: user?.id })
    console.log(`  [轮 ${step}] 三态: ${result}`)
    if (result === 'stop') break // 真实代码只有 blocked（权限被拒）/error 才走这条
    if (result === 'compact') { overflowFlag = true; settleTools(executor); continue }
    settleTools(executor) // "continue" → 结算欠账，回循环顶部
  }
  console.log(`  ── ${label} 收束，共 ${step} 轮 ──`)
}

// ---------------------------------------------------------------
// 第 5 部分：演示 —— 四种收束路径（每课至少一条失败/边界路径）
// ---------------------------------------------------------------
const user = (text) => append({ role: 'user', text })

async function main() {
  console.log('== 场景 1：正常两步工具轮（读文件 → 回答）==')
  resetLog()
  user('帮我看下 README 写了什么')
  await miniRunLoop({
    label: '正常轮',
    executor: (m) => (m.name === 'read' ? '# demo —— 42 字符的文件内容' : 'ok'),
    script: [
      [{ type: 'tool-call', name: 'read', args: { path: 'README.md' } }, { type: 'step-finish', finish: 'tool-calls', tokens: 900, limit: 8000 }],
      [{ type: 'text', text: 'README 介绍了 demo 项目。' }, { type: 'step-finish', finish: 'stop', tokens: 1500, limit: 8000 }],
    ],
  })

  console.log('\n== 场景 2：provider 说谎 —— 带 tool call 报 stop，hasToolCalls 驳回收束 ==')
  resetLog()
  user('跑一下测试')
  await miniRunLoop({
    label: '说谎的 provider',
    executor: (m) => (m.name === 'bash' ? 'all tests passed' : 'ok'),
    script: [
      // 第一步：模型发 tool call 却报 finish=stop——真实仓库 :1103 英文注释直说
      // "Some providers return 'stop' even when the assistant message contains tool calls"
      [
        { type: 'text', text: '我来跑测试。' },
        { type: 'tool-call', name: 'bash', args: { cmd: 'npm test' } },
        { type: 'step-finish', finish: 'stop', tokens: 400, limit: 8000 }, // 说谎点
      ],
      [{ type: 'text', text: '测试全部通过。' }, { type: 'step-finish', finish: 'stop', tokens: 1200, limit: 8000 }],
    ],
  })

  console.log('\n== 场景 3：上下文溢出 —— 打标记 continue，下一轮才压缩 ==')
  resetLog()
  user('总结这个超大仓库')
  await miniRunLoop({
    label: '溢出轮',
    executor: (m) => (m.name === 'glob' ? '10000 个文件' : m.name === 'read' ? '巨型文件内容' : 'ok'),
    script: [
      [{ type: 'tool-call', name: 'glob', args: { pattern: '**/*' } }, { type: 'step-finish', finish: 'tool-calls', tokens: 17000, limit: 16000 }], // 17000>=16000 溢出
      [{ type: 'tool-call', name: 'read', args: { path: 'core.ts' } }, { type: 'step-finish', finish: 'tool-calls', tokens: 12000, limit: 16000 }],
      [{ type: 'text', text: '（基于压缩后上下文给出的回答）' }, { type: 'step-finish', finish: 'stop', tokens: 3000, limit: 16000 }],
    ],
  })

  console.log('\n== 场景 4：maxSteps=1 —— 末轮 prefill 提示收束（提示词级约束，非硬闸）==')
  resetLog()
  user('无限聊下去')
  await miniRunLoop({
    label: '受限轮',
    maxSteps: 1,
    executor: () => 'ok',
    script: [
      [{ type: 'text', text: '好的，我收束作答。' }, { type: 'step-finish', finish: 'stop', tokens: 300, limit: 8000 }],
    ],
  })

  console.log('\n结论：循环的退出不靠计数，靠循环顶四条件；processor 只回答三态，')
  console.log('且健康完成也返回 continue——"stop" 三态只留给权限被拒与错误（s04 再见）。')
}

main().catch((e) => { console.error(e); process.exit(1) })
