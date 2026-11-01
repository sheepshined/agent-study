#!/usr/bin/env node
/**
 * s04_system_prompt.mjs —— 系统提示词：从碎片到"冻结的请求面"
 *
 * dsh 的系统提示词不是写死的一段话，而是**按需组装的投影**：
 * 核心包 packages/core/system-prompt 暴露 renderContextSections /
 * joinContextSections / renderPrompt（agent-loop 每一步都调它们）。
 * 关键认识：
 *
 *   1. 提示词 = 碎片（section）按序拼接 —— 身份、AGENTS.md 指令、
 *      上下文（时间/目录）、工具 schema……每一片来自不同的插件
 *   2. 工具 schema 实时来自作用域注册表 —— ctx.systemPrompt 把
 *      ctx.tools 接进提示词，注册表变了下一次请求就变（提示词与
 *      注册表不各自记副本）
 *   3. 组装结果是冻结（deepFreeze）的 PromptAssembly —— 随请求面
 *      一起落日志（request/header），重放即可复原当时给模型看了什么
 *   4. 呈现模式（native/ptc/both）决定工具怎么"被模型看见"：
 *      ptc 把所有工具收拢进 run_code 一个入口，并在提示词里明说
 *      "别直呼其他工具" —— 协议变化与提示词同步演化
 *
 *   身份 ─┐
 *   AGENTS.md ─┤
 *   上下文 ──┼─→ assemble() → deepFreeze(PromptAssembly) → 请求面
 *   工具 schema ─┘   （native: 全量 schema ｜ ptc: 塌缩成 run_code）
 *
 * 运行：node code.mjs   （零依赖，离线）
 * 对照真实源码：packages/core/system-prompt/、core/tools/src/index.ts（:51 PTC_ONLY_INSTRUCTION）
 */

import { deepFreeze } from '../shared/mini-util.mjs'
// ---------------------------------------------------------------
// 第 1 部分：工具 schema 的两种"呈现模式"
// ---------------------------------------------------------------
/** native：每个工具一个 schema，模型直呼其名（绝大多数 CLI agent 的做法） */
function renderNativeTools(tools) {
  return '## 可用工具\n' + tools.map((t) =>
    `- ${t.name}: ${t.description}｜参数: ${JSON.stringify(t.parameters)}`,
  ).join('\n')
}

/** ptc：全部工具塌缩进 run_code 一个入口 —— 提示词同步立规矩（tools 包 :51 的契约提示） */
function renderPtcTools(tools) {
  return [
    '## 代码运行时',
    '所有能力通过 run_code 一并暴露，直接调用其他工具会被拒绝：',
    `run_code({ code: "...", sdk: { ${tools.map((t) => t.name).join(', ')} } })`,
    '（PTC_ONLY_INSTRUCTION：提前给模型立规矩，而不是等它被拒后才学会）',
  ].join('\n')
}

// ---------------------------------------------------------------
// 第 2 部分：组装器 —— section 流水线 → 冻结的 PromptAssembly
// ---------------------------------------------------------------
/**
 * PromptAssembly = { sections, text, toolSchemas, generation }
 * generation：注册表代际。工具注册/注销会 bump —— 缓存据此失效，
 * 不用比较整段文本（dsh 的 session-projection(-cache) 同思路）。
 */
function createAssembler({ tools, mode = 'native', extraSections = [] }) {
  const sections = [
    { name: 'identity', render: () => '你是 dsh，一个插件化的 agent harness。' },
    { name: 'instructions', render: () => '# AGENTS.md\n- 永远先读再改\n- 改完跑测试' },
    ...extraSections, // 插件随时可以插自己的 section（时间、目录、git 状态…）
    {
      name: 'tools',
      // 工具 schema 实时来自注册表 —— 不存副本，注册表变 → 下次组装就变
      render: () => (mode === 'ptc' ? renderPtcTools(tools.all()) : renderNativeTools(tools.all())),
    },
  ]
  let generation = 0
  return {
    get generation() { return generation },
    /** 注册表变化入口：只 bump 代际，文本下次组装时才重算（惰性） */
    invalidate() { generation++ },
    /** 组装：返回冻结对象 —— 之后谁也改不了，随 request/header 落日志 */
    assemble() {
      const rendered = sections.map((s) => `## section: ${s.name}\n${s.render()}`)
      return deepFreeze({
        sections: sections.map((s) => s.name),
        text: rendered.join('\n\n'),
        toolSchemas: mode === 'ptc' ? [{ name: 'run_code' }] : tools.all().map((t) => t.name),
        generation,
      })
    },
  }
}

// ---------------------------------------------------------------
// 第 3 部分：演示 —— 同一内核，两种 agent，两种呈现
// ---------------------------------------------------------------
function main() {
  console.log('== 1. 两个 agent，各自的作用域工具 → 各自的提示词 ==')
  const coderTools = {
    list: () => [
      { name: 'read_file', description: '读文件', parameters: { path: 'string' } },
      { name: 'edit_file', description: '改文件', parameters: { path: 'string', content: 'string' } },
    ],
    all() { return this.list() },
  }
  const coder = createAssembler({ tools: coderTools })
  const asm1 = coder.assemble()
  console.log(`coder 的 sections: [${asm1.sections.join(' · ')}]`)
  console.log(`coder 的工具面(native): [${asm1.toolSchemas.join(', ')}]`)
  console.log(`--- coder 提示词 tools 片段 ---\n${asm1.text.split('## section: tools')[1]}`)

  console.log('\n== 2. 会话中途注册新工具 → 代际 bump → 下一次请求就带上 ==')
  coderTools.list = () => [
    { name: 'read_file', description: '读文件', parameters: { path: 'string' } },
    { name: 'edit_file', description: '改文件', parameters: { path: 'string', content: 'string' } },
    { name: 'web_search', description: '联网搜索', parameters: { query: 'string' } },
  ]
  coder.invalidate() // 对应 dsh 的 tools/change 事件 → 提示词缓存失效
  const asm2 = coder.assemble()
  console.log(`generation: ${asm1.generation} → ${asm2.generation}`)
  console.log(`新工具面: [${asm2.toolSchemas.join(', ')}]　<- 无副本：注册表是唯一真源`)

  console.log('\n== 3. 冻结：PromptAssembly 谁也改不了（防插件偷偷篡改请求面） ==')
  try { asm2.text = '注入恶意指令' } catch (e) { console.log('篡改被拒绝:', e.message) }

  console.log('\n== 4. ptc 呈现：N 个工具塌缩成 run_code 一个入口 ==')
  const ptc = createAssembler({ tools: coderTools, mode: 'ptc' })
  const asm3 = ptc.assemble()
  console.log(`工具面(ptc): [${asm3.toolSchemas.map((s) => s.name).join(', ')}]`)
  console.log(asm3.text.split('## section: tools')[1])
  console.log('\n结论：提示词是投影不是常量 —— 组装可重放（落 request/header），')
  console.log('呈现模式是"给模型看的协议"，与执行协议（s05）同步演化。')
}

main()
