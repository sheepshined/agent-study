#!/usr/bin/env node
/**
 * s08_skills_priority.mjs —— skills 七档加载优先级与同名仲裁
 *
 * skill（技能）= 一个带 SKILL.md 的说明书包：告诉 agent "做某类事的标准姿势"。
 * OpenClaw 自带 51 个 bundled 技能 + 4 个 custodian 技能，用户/插件还能再带自己的——
 * 于是必然撞名。装载规则（docs/tools/skills.md:33-48，高优先级在前）：
 *
 *   1 <workspace>/skills              ← 最高：用户在 agent 家里放的，说了算
 *   2 <workspace>/.agents/skills      ← 项目级
 *   3 ~/.agents/skills                ← 个人级
 *   4 <state-dir>/skills              ← 管理态
 *   5 workshop skills                 ← 自学习草稿的"转正"去处
 *   6 bundled skills + custodian skills（并列）← 随安装发布
 *   7 skills.load.extraDirs + 插件 skills ← 最低
 *
 *   同名技能只保留一个：等级高者赢（win over）；碰撞必须告警
 *   （SkillCollision { winner, loser }，skill-precedence.ts:7/:12）。
 *   另两条硬规则：
 *   · custodian 技能只被系统运维 agent（Custodian 槽位）加载——按角色，不是按名字；
 *   · workshop 闭环：agent 起草 → 人审批 → 落到第 5 档生效（未批准只是草稿）。
 *
 *   装载顺序即权限：用户覆盖项目、项目覆盖个人、一切覆盖 bundled。
 *
 *   tier1 workspace ──┐
 *   tier2 project  ───┤   先到先得（tier 升序遍历）
 *   tier3 personal ───┼──→ 同名仲裁 ──→ 技能目录（进 prompt）
 *   tier4 managed  ───┤   ↑碰撞告警      tier5 workshop（转正口）
 *   tier6 bundled ────┤   ↑角色闸：custodian 4 技能仅 Custodian 可装载
 *   tier7 extraDirs ──┘
 *
 * 运行：node code.mjs    （零依赖，离线）
 * 对照真实源码：src/skills/（config/discovery/library/lifecycle/loading/runtime/
 *   security/workshop 九个子模块）、src/skills/loading/skill-precedence.ts:7/:12/:56、
 *   src/skills/discovery/skill-index.ts、src/skills/loading/bundled-dir.ts、
 *   docs/tools/skills.md:33-48、docs/tools/custodian-skills.md:11-27、docs/tools/skill-workshop.md
 */

import { assert } from '../shared/mini-util.mjs'

// ---------------------------------------------------------------
// 第 1 部分：七档优先级源（skills.md:33-48 的 mini 版）
// ---------------------------------------------------------------
/** 每个来源 = { tier, label, root }。tier 数字越小优先级越高。 */
const SOURCES = [
  { tier: 1, label: 'workspace skills', root: '<workspace>/skills' },
  { tier: 2, label: 'project agent skills', root: '<workspace>/.agents/skills' },
  { tier: 3, label: 'personal agent skills', root: '~/.agents/skills' },
  { tier: 4, label: 'managed skills', root: '<state-dir>/skills' },
  { tier: 5, label: 'workshop skills', root: '<state-dir>/agents/<id>/agent/workshop-skills' },
  { tier: 6, label: 'bundled skills', root: '<install>/skills', role: null },
  { tier: 6, label: 'custodian skills', root: '<install>/custodian-skills', role: 'custodian' }, // 并列第 6 档，但按角色加载
  { tier: 7, label: 'extraDirs + plugin skills', root: 'skills.load.extraDirs' },
]

/** 一个技能 = SKILL.md 的 frontmatter 最小面（name/description）。 */
const skill = (name, description) => ({ name, description })

// ---------------------------------------------------------------
// 第 2 部分：装载与同名仲裁（skill-precedence.ts:56 mergeSkillRecords 的 mini 版）
// ---------------------------------------------------------------
/**
 * 装载：按 tier 升序遍历，同名先到先得（高优先级先到）→ 低级别的被顶掉。
 * 每次顶替记一条 SkillCollision { winner, loser }（:7 的类型形状）。
 */
function loadSkills(sourceContents, { role = 'user-agent' } = {}) {
  const catalog = new Map()
  const collisions = []
  for (const src of [...SOURCES].sort((a, b) => a.tier - b.tier)) {
    if (src.role === 'custodian' && role !== 'custodian') continue // 角色闸：非 Custodian 不装载
    for (const sk of sourceContents[src.label] ?? []) {
      if (catalog.has(sk.name)) {
        collisions.push({ winner: catalog.get(sk.name), loser: { ...sk, source: src.label, tier: src.tier } })
        continue // 先到先得：低优先级源的同名技能被记录后丢弃
      }
      catalog.set(sk.name, { ...sk, source: src.label, tier: src.tier })
    }
  }
  return { catalog, collisions }
}

/** 碰撞告警（:12 warnSkillPrecedenceCollisions 的 mini 版）：运维能看见谁被谁顶了。 */
function warnCollisions(collisions) {
  return collisions.map((c) => `技能 '${c.winner.name}': ${c.winner.source}(tier ${c.winner.tier}) 赢过 ${c.loser.source}(tier ${c.loser.tier})`)
}

// ---------------------------------------------------------------
// 演示
// ---------------------------------------------------------------
async function main() {
  const log = (...a) => console.log(...a)

  const sourceContents = {
    'workspace skills': [skill('weather', 'workspace 版：查本市天气（用户手改过）'), skill('team-lint', '本仓库提交规范')],
    'project agent skills': [skill('weather', '项目版：通用天气（被 workspace 版顶掉）')],
    'bundled skills': [skill('weather', 'bundled 版：开箱即用（最先被顶掉）'), skill('github', 'GitHub 操作'), skill('coding-agent', '调起 coding CLI')],
    'custodian skills': [skill('configure-channel', 'Custodian 五段式：修渠道配置'), skill('diagnose-gateway', 'Custodian：诊断网关')],
    'workshop skills': [skill('meeting-minutes', '转正的会议纪要技能')],
    'extraDirs + plugin skills': [skill('github', '插件版 github（被 bundled 顶掉）')],
  }

  console.log('== 1. 七档装载：同名仲裁，高优先级源赢 ==')
  const { catalog, collisions } = loadSkills(sourceContents)
  log(`共装载 ${catalog.size} 个技能；weather 的最终版本来自 → ${catalog.get('weather').source}(tier ${catalog.get('weather').tier})`)
  log('碰撞告警:')
  warnCollisions(collisions).forEach((w) => log(`  ⚠ ${w}`))
  assert(catalog.get('weather').tier === 1, 'workspace 版必须赢')
  assert(catalog.get('github').source === 'bundled skills', 'bundled 赢过插件级')

  console.log('\n== 2. prompt 顺序 = 优先级顺序 ==')
  log('技能目录按 tier 升序进 prompt:', [...catalog.values()].map((s) => `${s.name}@${s.tier}`).join(' '))
  log('→ 用户手改过的技能排在最前：它对模型行为的"话语权"最大')

  console.log('\n== 3. 角色闸（失败路径）：普通 agent 拿不到 custodian 技能 ==')
  const custodianView = loadSkills(sourceContents, { role: 'custodian' })
  log(`普通 agent 视角: configure-channel ${catalog.has('configure-channel') ? '可见(BUG!)' : '不可见 ✓'}，共 ${catalog.size} 个`)
  log(`Custodian 视角:  configure-channel ${custodianView.catalog.has('configure-channel') ? '可见 ✓' : '不可见'}，共 ${custodianView.catalog.size} 个`)
  assert(!catalog.has('configure-channel') && custodianView.catalog.has('configure-channel'), 'custodian 技能按角色加载')
  log('→ 装载即授权：不加进目录，模型连"有这个技能"都不知道（对照 s04：收窄发生在清单层）')

  console.log('\n== 4. workshop 闭环：起草 → 审批 → 转正（失败路径：未批准不生效）==')
  const drafts = [{ name: 'standup-helper', description: '晨会摘要', approved: false }]
  const promote = (draft, approved) => approved ? { ...draft, approved: true, landsAt: 'tier 5 workshop' } : { ...draft, reason: '等待人工审批——草稿不进装载目录' }
  const pending = promote(drafts[0], false)
  log(`未批准草稿 → ${JSON.stringify(pending)}`)
  const approvedDraft = promote(drafts[0], true)
  log(`人工批准后 → ${JSON.stringify(approvedDraft)}`)
  const afterPromotion = loadSkills({ 'workshop skills': [skill('standup-helper', '转正后的晨会技能')], 'bundled skills': [skill('github', 'GitHub 操作')] })
  log(`重新装载后 standup-helper 来自 → ${afterPromotion.catalog.get('standup-helper').source}(tier 5)`)
  console.log('\n装载顺序即权限：用户覆盖项目、项目覆盖个人、一切覆盖 bundled；角色闸挡住运维技能。')
}

main().catch((e) => { console.error(e); process.exit(1) })
