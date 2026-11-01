/**
 * shared/mini-util.mjs —— 课程共享小工具（对应 dsh 的 @deepseek-ai/dsh-util-values）
 * 各课 import { deepFreeze, sleep } from '../shared/mini-util.mjs'
 */

/** 深冻结：dsh 在冻结请求面（requestProposal/deepFreeze）时反复使用的手法 ——
 *  跨插件共享的对象一旦定型就不许再改，防"某个插件偷偷篡改共享状态"。 */
export function deepFreeze(obj) {
  for (const v of Object.values(obj)) if (v && typeof v === 'object') deepFreeze(v)
  return Object.freeze(obj)
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
