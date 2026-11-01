#!/usr/bin/env node
/**
 * s01_three_layer_loop.mjs —— mini 三层循环：turn → provider-turn 循环 → model step
 *
 * ZCode 的主循环分三层（与"单一 while"的根本区别是职责归属）：
 *
 *   第 1 层 turn.ts（回合入口）
 *     · executeTurn :83 只做串行 admission —— 输入先排队，绝不并发开两个回合
 *     · executeTurnCommand :108 开轮，⚠️ 在任何 await 之前冻结本轮配置
 *       （模型选择 / outputStyle / /compact / /rewind），消灭"一半步骤用新配置"的竞态
 *
 *   第 2 层 turn-loop.ts（provider-turn 外层循环，while(true) :62）
 *     · 每圈治理都是局部事实：microcompact → rapid-refill/auto compact → MCP →
 *       本步工具集 → system-reminder 注入 → cache-control → 才轮到模型请求
 *
 *   第 3 层 turn-model-step.ts（单个 model step）
 *     · 单次模型请求 + 全部恢复路径（流恢复/退避/取消快照/超窗补救）+ 工具批执行
 *     · 返回给第 2 层的信号只有 "continue" | "break"
 *
 *   停止裁决 turn-stop.ts :178：先持久化 assistant → guide 转向？→ Stop hook？→ break
 *   全程没有"工具调用次数上限"（AGENTS.md:11 公理）：停止 = 语义事件。
 *
 *   +--------------------------------------------------------------+
 *   | turn: admission → 冻结配置 → hooks → 落用户消息               |
 *   |   +------------------------------------------------------+   |
 *   |   | loop: while(true) { 治理段; step() }  ← 局部事实每圈算 |   |
 *   |   |   +----------------------------------------------+   |   |
 *   |   |   | step: mock 模型请求 → 工具批 → 恢复路径        |   |   |
 *   |   |   +----------------------------------------------+   |   |
 *   |   | 裁决: 无工具→break / 被拒→break / 取消→break          |   |
 *   |   +------------------------------------------------------+   |
 *   +--------------------------------------------------------------+
 *
 * 运行：node code.mjs        （零依赖，离线，模型由 Mock 扮演）
 * 对照真实源码：core/src/runtime/methods/{turn,turn-loop,turn-model-step,turn-stop}.ts
 */

import { deepFreeze, sleep, banner } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：回合配置与冻结（turn.ts 的"冻结在 await 之前"）
// ---------------------------------------------------------------
class TurnConfig {
  constructor({ model, mode, outputStyle }) {
    this.model = model
    this.mode = mode          // 权限模式，s04 展开
    this.outputStyle = outputStyle
  }
  /** 冻结：Object.freeze 返回同一对象的只读视图 —— 迟到的一切修改都被拒收 */
  freeze() { return deepFreeze({ ...this }) }
}

// ---------------------------------------------------------------
// 第 2 部分：三层循环本体
// ---------------------------------------------------------------
class TurnRuntime {
  constructor({ model }) {
    this.modelClient = model                       // Mock 模型（离线）
    this.frozen = null                             // 本回合冻结配置
    this.steerQueue = []                           // steering 队列（用户中途插话）
    this.events = []                               // 会话事件（s02 展开：事件即事实）
    this.abort = false                             // 取消信号（对应 AbortSignal 级联）
    this.turnCount = 0
  }

  /** 第 1 层入口：admission —— 串行排队。真实实现是 enqueueCancellableRuntimeCommand */
  async turn(input) {
    if (this.running) throw new Error('[admission] 上一回合未结束，输入排队而非并发') // mini 版直接拒
    this.running = true
    try { return await this.executeTurnCommand(input) } finally { this.running = false }
  }

  async executeTurnCommand(input) {
    // ⚠️ 冻结在 await 之前：下面第一个 await 之前，配置已经拍死。
    this.frozen = this.pendingConfig.freeze()
    this.log('turn/start', { input, model: this.frozen.model, mode: this.frozen.mode })

    // SessionStart hooks、用户消息持久化在真实代码里发生在这里（turn.ts :227-257, :503-541）
    this.events.push({ type: 'user/message', payload: { text: input } })

    let state = { stepIndex: 0, stopReason: null }
    try {
      state = await this.runRegularTurnLoop(input)          // 进入第 2 层
    } catch (e) {
      // turn.ts :715-740 的 catch：失败也变成事件 + guide 回投，而不是裸崩
      this.log('turn/error', { error: e.message })
      state.stopReason = 'error'
    }
    this.events.push({ type: 'turn/complete', payload: { stopReason: state.stopReason, steps: state.stepIndex } })
    this.log('turn/complete', { stopReason: state.stopReason, steps: state.stepIndex })
    this.turnCount++
    return state
  }

  // 第 2 层：provider-turn 外层循环（turn-loop.ts :56，while(true) :62）
  async runRegularTurnLoop(input) {
    let state = { stepIndex: 0, stopReason: null }
    while (true) {
      this.throwIfAborted()

      // —— 治理段（每圈重算的局部事实）——
      this.governStep(state)          // microcompact / 提醒注入 / 工具集 —— s03/s05 展开
      if (state.stepIndex >= 1) this.drainSteering(state) // 从第二个 step 起才 drain 插话
      // —— 单步 ——
      const verdict = await this.modelStep(input, state)  // 进入第 3 层
      state.stepIndex++

      // —— 停止裁决（turn-stop.ts :178 的 mini 版）——
      // 顺序固定：先"持久化 assistant"（events.push 已发生）→ 再试 guide → 再试 hook → break
      if (verdict.stop) { state.stopReason = verdict.reason; break }
      if (this.abort) { state.stopReason = 'cancelled'; break }
    }
    return state
  }

  /** 治理段：真实代码是 microcompactIfNeeded → evaluateRapidRefill → initializeMcp → 工具集 → 提醒 */
  governStep(state) {
    const items = ['压缩检查', '本步工具集重算', 'system-reminder 注入']
    this.log('loop/govern', { step: state.stepIndex, items })
  }

  /** steering drain：真实代码从第二个 model step 起合入后台结果与命令队列（turn-loop.ts :55-65） */
  drainSteering(state) {
    while (this.steerQueue.length) {
      const msg = this.steerQueue.shift()
      this.log('loop/steer-drain', { step: state.stepIndex, msg })
    }
  }

  // 第 3 层：单个 model step（turn-model-step.ts :133 起）
  async modelStep(input, state) {
    // 治理产物进请求；Mock 模型按剧本回答
    const script = this.modelClient.next({ input, step: state.stepIndex, mode: this.frozen.mode })
    if (script.sleep) await sleep(script.sleep)          // 模拟网络延迟
    this.throwIfAborted()

    this.events.push({ type: 'model/request', payload: { step: state.stepIndex } })
    this.log('step/model', { step: state.stepIndex, reply: script.reply ?? null, tools: script.tools ?? null })

    if (script.cancel) { this.abort = true; return { stop: true, reason: 'cancelled' } }

    if (script.tools && script.tools.length) {
      for (const call of script.tools) {
        const result = await this.runToolCall(call)
        // 权限拒绝是"语义停止"：整轮结束而不是数次数（s04 展开权限格子）
        if (result.status === 'denied') return { stop: true, reason: `permission-denied:${call.name}` }
      }
      return { stop: false }   // 有工具执行 → 模型还需要下一轮，继续循环
    }
    // 无工具调用 → 正常收口（turn-stop.ts finishModelStepWithoutToolCalls）
    return { stop: true, reason: 'no-tool-calls' }
  }

  async runToolCall(call) {
    const rule = this.permissionRules?.[call.name]
    if (rule === 'deny') {
      this.log('tool/denied', { name: call.name })
      this.events.push({ type: 'tool/denied', payload: call })
      return { status: 'denied' }
    }
    this.log('tool/ok', { name: call.name })
    this.events.push({ type: 'tool/result', payload: { name: call.name, ok: true } })
    return { status: 'ok' }
  }

  /** 用户中途转向：进队列，不并发打断（对应 CommandInbox 的串行 admission 思想，s10 展开） */
  enqueueSteer(msg) {
    this.steerQueue.push(msg)
    this.log('steer/enqueue', { msg })
  }

  changeMode(mode) {
    // 冻结后的改配置被拒收 —— 但只影响本回合：pendingConfig 改动下一回合生效
    if (this.running) {
      this.pendingConfig = new TurnConfig({ ...this.pendingConfig, mode })
      return { accepted: false, why: '本回合配置已冻结，新模式将从下一回合生效' }
    }
    this.pendingConfig = new TurnConfig({ ...this.pendingConfig, mode })
    return { accepted: true }
  }

  throwIfAborted() {
    if (this.abort) { const e = new Error('TurnCancelled'); e.cancelled = true; throw e }
  }

  log(type, payload) {
    this.events.push({ type, payload })
    console.log(`  ${type.padEnd(16)} ${JSON.stringify(payload)}`)
  }
}

// ---------------------------------------------------------------
// 第 3 部分：Mock 模型（脚本化剧本，离线可复现）
// ---------------------------------------------------------------
function scriptedModel(scenario) {
  let i = 0
  return {
    next({ step }) {
      const s = scenario[i++ % scenario.length]
      return typeof s === 'function' ? s({ step }) : s
    },
  }
}

// ---------------------------------------------------------------
// 第 4 部分：main() —— 四个场景
// ---------------------------------------------------------------
async function main() {
  // 场景 1：一次完整 turn 的分层轨迹。观察事件顺序：
  // 冻结发生在 loop/govern 之前；治理段每圈跑；无工具调用才收口。
  banner('场景 1：一次完整 turn —— 三层各管一件事')
  {
    const rt = new TurnRuntime({
      model: scriptedModel([
        { reply: '先看看文件', tools: [{ name: 'read_file' }] },
        { reply: '总结：这个问题出在 X。' },
      ]),
    })
    rt.pendingConfig = new TurnConfig({ model: 'mock-glm', mode: 'build', outputStyle: 'default' })
    await rt.turn('帮我看看这个 bug')
  }

  // 场景 2：冻结 —— 迟到的改模式被拒收，下一回合生效。
  banner('场景 2：await 期间改模式 —— 冻结在 await 之前')
  {
    const rt = new TurnRuntime({
      model: scriptedModel([
        async () => {
          // 模型请求"在途"时，用户尝试改模式 —— 真实世界里这是一个必然出现的竞态
          const r = rt.changeMode('yolo')
          console.log(`  [用户] changeMode('yolo') → ${JSON.stringify(r)}`)
          await sleep(5)
          return { reply: '（一次就回答完了）' }
        },
      ]),
    })
    rt.pendingConfig = new TurnConfig({ model: 'mock-glm', mode: 'build', outputStyle: 'default' })
    await rt.turn('快速回答我一个问题')
    console.log('  下一回合 newTurn 用新配置:', JSON.stringify(rt.pendingConfig))
  }

  // 场景 3：权限拒绝 = 语义停止。注意循环没有"调用次数上限"，
  // 停机由"被拒"这一语义事件承担 —— 对应 AGENTS.md:11 的公理。
  banner('场景 3：权限拒绝触发停止（不数次数）')
  {
    const rt = new TurnRuntime({
      model: scriptedModel([
        { tools: [{ name: 'read_file' }] },
        { tools: [{ name: 'rm_rf' }] },   // 被权限规则拒绝 → 整轮结束
        { reply: '永远不会被执行到' },
      ]),
    })
    rt.pendingConfig = new TurnConfig({ model: 'mock-glm', mode: 'build', outputStyle: 'default' })
    rt.permissionRules = { rm_rf: 'deny' }
    const out = await rt.turn('清理一下磁盘')
    console.log(`  停止原因: ${out.stopReason} —— 循环没有任何次数上限，停止全靠语义事件`)
  }

  // 场景 4：steering —— 中途插话不并发打断，从第二个 step 起被 drain。
  banner('场景 4：steering 插话 —— 第二步开头才 drain')
  {
    const rt = new TurnRuntime({
      model: scriptedModel([
        { reply: '开始搜索', tools: [{ name: 'web_search' }], sleep: 5 },
        { reply: '按你的补充要求重写完毕。' },
      ]),
    })
    rt.pendingConfig = new TurnConfig({ model: 'mock-glm', mode: 'build', outputStyle: 'default' })
    const p = rt.turn('写一篇文章')
    rt.enqueueSteer('用户补充：请用中文标题')
    await p
    console.log('  → 首步没有被打断；插话在第二步治理段被合入（真实代码 turn-loop.ts :55-65）')
  }

  console.log('\n结论：三层拆分把"冻结/治理/执行+恢复"各归其位；停止靠语义事件，不靠计数器。')
}

main().catch((e) => { console.error(e); process.exit(1) })
