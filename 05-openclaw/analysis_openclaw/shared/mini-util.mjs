/**
 * shared/mini-util.mjs —— 课程共享小工具（对应 OpenClaw 的 @openclaw/normalization-core
 * 一类"零依赖基础件"的口吻：越底层的东西越要小、越要可测）。
 * 各课 import { deepFreeze, sleep } from '../shared/mini-util.mjs'
 */

/** 深冻结：OpenClaw 的工具清单（tool-catalog）与收窄流水线（tool-policy-pipeline）
 *  都遵循"定型即不可变"——跨模块共享的注册表条目一旦发布就不许再改，
 *  防"某个插件偷偷篡改共享工具面"。教学实现里用 Object.freeze 表达同一纪律。 */
export function deepFreeze(obj) {
  for (const v of Object.values(obj)) if (v && typeof v === 'object') deepFreeze(v)
  return Object.freeze(obj)
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

/** 极简断言：run.bat 逐课跑 code.mjs 时靠抛错判失败（非零退出码）。 */
export function assert(cond, msg) {
  if (!cond) throw new Error(`[mini-openclaw] 断言失败: ${msg}`)
}
