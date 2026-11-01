#!/usr/bin/env node
/**
 * s09_sandbox_approval.mjs —— 权限闸门与沙箱："能做"与"该做"的分界线
 *
 * s05 的流水线留了一道 pre 钩子没正式化——这一课补上。dsh 的安全域：
 *
 *   packages/interaction/   user-approval（审批服务）、tool-ask-user、
 *                           permission-presets（权限预设）
 *   packages/sandbox/       sandbox / sandbox-local / sandbox-policy /
 *                           sandbox-windows-acl（Windows ACL 落地）
 *   native/system/          Landlock launcher（Linux 内核级文件访问控制）
 *   事件词汇：approval/asked · approval/decided · approval/policy ·
 *            permission/preset · sandbox/mode
 *
 *   模型调工具 ──→ 权限预设（preset：allow/ask/deny）──┬─ allow → 直接放行
 *                                                    ├─ ask  → 审批服务
 *   审批也可临时放行同类调用（本会话记住）←── 决定 ──┘        │ approval/asked
 *   放行后进沙箱执行（路径边界/超时）←──────────────────────── approval/decided
 *
 *   关键不变量：**每一个"问过"和"判过"都是事件** —— 安全决策也要可审计。
 *
 * 运行：node code.mjs   （零依赖，离线；"人类"由脚本扮演）
 * 对照真实源码：packages/interaction/user-approval/、permission-presets/、
 *              packages/sandbox/、native/system/（Landlock）
 */

// ---------------------------------------------------------------
// 第 1 部分：权限预设 —— 按风险等级分三档
// ---------------------------------------------------------------
/**
 * 权限预设（permission-presets）：把"哪些动作要问人"变成配置而非散落
 * 的 if。dsh 里预设本身也是一个可切换的事件（permission/preset）。
 */
const PRESETS = {
  readonly: { read_file: 'allow', list_dir: 'allow', write_file: 'deny', delete_file: 'deny', run_code: 'deny' },
  standard: { read_file: 'allow', list_dir: 'allow', write_file: 'ask', delete_file: 'ask', run_code: 'ask' },
  yolo: { '*': 'allow' }, // 官方文档的安全提示：仅限一次性 VM/容器（见仓库 SAFETY.zh.md）
}

// ---------------------------------------------------------------
// 第 2 部分：审批服务 —— ask/decide，全部落事件
// ---------------------------------------------------------------
class ApprovalService {
  constructor({ preset, human, events }) { Object.assign(this, { preset, human, events, remembered: new Map() }) }

  setPreset(name) {
    this.preset = name
    this.events.push(['permission/preset', { preset: name }])
  }

  /** 流水线 pre 钩子的正式版：返回 allow / deny / { ask } */
  async check(tool, args) {
    const policy = PRESETS[this.preset]
    const verdict = policy[tool] ?? policy['*'] ?? 'ask'

    // 本会话已记住的临时放行：同键不再重复打扰（dsh 的会话级审批记忆）
    const key = `${tool}:${args.path ?? ''}`
    if (this.remembered.has(key)) return { verdict: this.remembered.get(key), remembered: true }

    if (verdict === 'allow') { this.events.push(['approval/policy', { tool, verdict }]); return { verdict: 'allow' } }
    if (verdict === 'deny') { this.events.push(['approval/policy', { tool, verdict }]); return { verdict: 'deny' } }

    // ask：先落 approval/asked，等人（真实实现里是 UI 弹窗/ACP 往返）
    this.events.push(['approval/asked', { tool, args }])
    const decision = await this.human({ tool, args })
    this.events.push(['approval/decided', { tool, decision, remember: decision.remember }])
    if (decision.remember) this.remembered.set(key, decision.allow ? 'allow' : 'deny')
    return { verdict: decision.allow ? 'allow' : 'deny' }
  }
}

// ---------------------------------------------------------------
// 第 3 部分：沙箱 —— 放行 ≠ 出笼，执行期还有边界
// ---------------------------------------------------------------
/**
 * sandbox-policy 的 mini 版：路径边界检查。真实实现里 sandbox-local 用
 * 进程级隔离，native/system 的 Landlock launcher 在内核层兜底（Linux），
 * Windows 由 sandbox-windows-acl 用 ACL 实现 —— 多层防线，一层失守还有下一层。
 */
function sandboxGuard({ workdir }) {
  return {
    name: 'sandbox',
    // 作为 pre 钩子接进 s05 流水线：审批通过后、真正执行前的最后一道
    pre(tool, args) {
      const target = args.path ?? args.cwd ?? workdir
      const resolved = target.startsWith('/') ? target : `${workdir}/${target}`
      if (!resolved.startsWith(workdir)) {
        return { ok: false, reason: `沙箱拒绝：${target} 越出工作目录边界` }
      }
      return { ok: true }
    },
  }
}

// ---------------------------------------------------------------
// 第 4 部分：演示 —— 同一批调用，三种预设下三种命运
// ---------------------------------------------------------------
async function main() {
  const events = []

  console.log('== 场景 A：readonly 预设 —— 写操作直接 deny，不问人 ==')
  {
    const approval = new ApprovalService({ preset: 'readonly', human: null, events })
    console.log('  write_file →', (await approval.check('write_file', { path: 'a.txt' })).verdict)
    console.log('  read_file  →', (await approval.check('read_file', { path: 'a.txt' })).verdict)
  }

  console.log('\n== 场景 B：standard 预设 —— ask 问人 + 会话内记住决定 ==')
  {
    // "人类"由脚本扮演：第一次同意写 a.txt 并记住，第二次自动放行
    let asked = 0
    const human = async ({ tool, args }) => {
      asked++
      return { allow: true, remember: true, note: `第 ${asked} 次被打扰：同意 ${tool} ${args.path}` }
    }
    const approval = new ApprovalService({ preset: 'standard', human, events })
    console.log('  第一次 write_file:', (await approval.check('write_file', { path: 'a.txt' })).verdict, '（问了人）')
    console.log('  第二次 write_file:', (await approval.check('write_file', { path: 'a.txt' })).verdict, '（remembered，不再打扰）')
    console.log('  write b.txt     :', (await approval.check('write_file', { path: 'b.txt' })).verdict, '（新路径，又问）')
  }

  console.log('\n== 场景 C：审批通过后，沙箱仍可能拦下越界执行 ==')
  {
    const guard = sandboxGuard({ workdir: '/home/user/project' })
    const sandbox = (args) => guard.pre('write_file', args)
    console.log('  写 project/a.txt :', sandbox({ path: 'a.txt' }).ok ? '放行' : guard.pre('write_file', { path: 'a.txt' }).reason)
    console.log('  写 /etc/hosts    :', sandbox({ path: '/etc/hosts' }).ok ? '放行' : `拦截 —— ${sandbox({ path: '/etc/hosts' }).reason}`)
  }

  console.log('\n== 审计轨迹：每个决定都是事件（这就是"安全决策可回溯"） ==')
  for (const [type, payload] of events) console.log(`  ${type.padEnd(20)} ${JSON.stringify(payload).slice(0, 88)}`)
  console.log('\n结论：权限不是散落的 if，是 配置（preset）→ 服务（approval）→ 边界（sandbox）三层；')
  console.log('  每层都落事件。dsh 官方的告诫也很直白：实验性软件，先读 SAFETY，VM/容器里跑。')
}

main().catch((e) => { console.error(e); process.exit(1) })
