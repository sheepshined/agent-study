#!/usr/bin/env node
/**
 * s05_model_shape.mjs —— 模型特化：工具面互斥开关 + 提示词前缀路由
 *
 * 同一个 harness 服务所有模型，但模型能力差异是真实的。OpenCode 的做法：
 * 差异写进代码，两处最有代表性——
 *
 *  ① 工具面互斥开关（tool/registry.ts:297-300）
 *     const usePatch = modelID.includes("gpt-")
 *                   && !modelID.includes("oss")      // 本地开源权重不吃 patch 格式
 *                   && !modelID.includes("gpt-4")    // 老一代没练过 patch
 *     usePatch 为真：apply_patch 出现，edit + write 消失；为假：反过来。
 *     ★ 三行是一个互斥开关，不能只改其中一行（真实代码注释原话）。
 *
 *  ② 提示词前缀路由（session/system.ts:43-66）——行序就是优先级：
 *     muse → meta.txt（带 {{MODEL_NAME}} 槽位）
 *     gpt-4|o1|o3 → beast.txt        ← 必须早于泛化的 gpt
 *     gpt → 内分 gpt-6 → gpt-astra / codex → codex / 其余 → gpt.txt
 *     gemini- / claude / trinity → 各自家族
 *     kimi：id 命中 或 providerID ∈ {moonshotai,...}  ← 双通道防网关改名
 *     兜底 → default.txt
 *
 *   +----------------+   includes("gpt-") 等   +------------------+
 *   │ models-dev 目录 │ ──── 前缀/互斥判据 ────▶ │ 工具面 + 提示词家族│
 *   └────────────────┘                        └──────────────────┘
 *
 * 运行：node code.mjs   （零依赖，离线）
 * 对照真实源码：packages/opencode/src/tool/registry.ts（usePatch 三行）
 *              packages/opencode/src/session/system.ts（家族路由）
 *              packages/opencode/src/session/prompt/*.txt（15 个模板）
 */

// ---------------------------------------------------------------
// 第 1 部分：工具面互斥开关（registry.ts:297-300 的 mini 版）
// ---------------------------------------------------------------
function usePatch(modelID) {
  return modelID.includes('gpt-') && !modelID.includes('oss') && !modelID.includes('gpt-4')
}

/** 给定模型，返回"模型可见的文件编辑工具面"。
 *  互斥不变量：apply_patch ∈ 可见集 ⇔ edit ∉ 可见集 且 write ∉ 可见集。 */
function editToolSurface(modelID) {
  return usePatch(modelID) ? ['apply_patch'] : ['edit', 'write']
}

// ---------------------------------------------------------------
// 第 2 部分：提示词前缀路由（system.ts:43-66 的 mini 版）
// ---------------------------------------------------------------
// 用有序规则表模拟 if-else 链——故意保留"顺序敏感"这一特性供场景 2 演示。
// 每条规则：{test(model, providerID), family}；从上到下第一个命中的生效。
function familyRules() {
  return [
    { family: 'meta.txt', test: (id) => id.includes('muse'), note: '模板带 {{MODEL_NAME}} 槽位，须在 gpt 之前' },
    {
      family: 'beast.txt',
      test: (id) => ['gpt-4', 'o1', 'o3'].some((k) => id.includes(k)),
      note: '必须早于泛化的 gpt，否则老式 GPT 被套上新模型提示词',
    },
    {
      family: 'gpt-astra.txt',
      test: (id) => id.includes('gpt') && id.includes('gpt-6'),
      note: 'gpt 内部分支：gpt-6 必须早于兜底 gpt.txt',
    },
    { family: 'codex.txt', test: (id) => id.includes('gpt') && id.includes('codex'), note: '同上' },
    { family: 'gpt.txt', test: (id) => id.includes('gpt'), note: 'gpt 家族兜底' },
    { family: 'gemini.txt', test: (id) => id.includes('gemini-'), note: '带连字符：避开自定义 id 偶含 "gemini" 字样' },
    { family: 'anthropic.txt', test: (id) => id.includes('claude'), note: '不带连字符' },
    { family: 'trinity.txt', test: (id) => id.toLowerCase().includes('trinity'), note: '小写匹配' },
    {
      family: 'kimi.txt',
      test: (id, providerID) => id.toLowerCase().includes('kimi') || ['kimi-for-coding', 'moonshotai', 'moonshotai-cn'].includes(providerID),
      note: '双通道：第三方网关常把 Moonshot 模型改名，id 里没有 kimi',
    },
  ]
}

function routeFamily(modelID, providerID, rules = familyRules()) {
  const hit = rules.find((r) => r.test(modelID, providerID))
  return hit ? { family: hit.family, via: hit.note } : { family: 'default.txt', via: '兜底：目录里查无此人' }
}

// ---------------------------------------------------------------
// 第 3 部分：演示
// ---------------------------------------------------------------
function main() {
  console.log('== 场景 1：工具面互斥开关 —— 谁用 apply_patch，谁保住 edit/write ==')
  const models = ['gpt-5.1', 'gpt-4o', 'gpt-oss-120b', 'claude-sonnet-x']
  for (const m of models) {
    console.log(`    ${m.padEnd(18)} → 编辑工具面: [${editToolSurface(m).join(', ')}]`)
  }
  const invariant = models.every((m) => {
    const s = editToolSurface(m)
    return s.includes('apply_patch') === !(s.includes('edit') || s.includes('write'))
  })
  console.log(`    互斥不变量成立（apply_patch ⇔ 无 edit/write）: ${invariant}`)
  console.log('    → 真实代码注释强调：三行是一个互斥开关，不能只改其中一行')

  console.log('\n== 场景 2：前缀路由 —— 8 个模型各归其位，然后故意打乱顺序 ==')
  const cases = [
    ['muse-glimmer-1', 'opencode'],
    ['gpt-4o', 'openai'],
    ['gpt-6-turbo', 'openai'],
    ['gpt-5-codex', 'openai'],
    ['gpt-5.1', 'openai'],
    ['gemini-2.5-pro', 'google'],
    ['claude-sonnet-x', 'anthropic'],
    ['k2-pro', 'moonshotai'], // id 里没有 kimi —— 靠 providerID 兜住
  ]
  console.log('    正确顺序:')
  for (const [id, provider] of cases) {
    const r = routeFamily(id, provider)
    console.log(`      ${id.padEnd(18)} (provider=${provider.padEnd(10)}) → ${r.family.padEnd(15)}`)
  }
  console.log('    打乱顺序（把泛化 gpt 提到最前）——失败路径演示:')
  const wrong = [
    { family: 'gpt.txt', test: (id) => id.includes('gpt') }, // 泛化分支被错误提前
    ...familyRules().filter((r) => r.family !== 'gpt.txt'),
  ]
  for (const [id, provider] of cases.filter(([i]) => i.includes('gpt') || i.includes('muse'))) {
    const r = routeFamily(id, provider, wrong)
    console.log(`      ${id.padEnd(18)} → ${r.family.padEnd(15)}${r.family === 'gpt.txt' ? '  ← 被截胡，静默拿错家族！' : ''}`)
  }
  console.log('    → 行序就是优先级；改路由顺序 = 静默换提示词，没有任何报错')

  console.log('\n== 场景 3：未知模型兜底 —— default.txt 保证任何模型都能跑 ==')
  const odd = routeFamily('my-private-llm-3000', 'self-hosted')
  console.log(`    my-private-llm-3000 (provider=self-hosted) → ${odd.family}（${odd.via}）`)
  console.log('    → 不报错、不猜测；未识别的模型用通用家族，工具面也不分叉')

  console.log('\n结论：模型目录外置在 models.dev（加 provider 去那边提 PR），')
  console.log('本仓只保留"按模型分叉"的三个落点：工具面、提示词家族、schema 改写。')
}

try {
  main()
} catch (e) {
  console.error(e)
  process.exit(1)
}
