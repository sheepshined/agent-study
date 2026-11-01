/**
 * shared/mini-util.mjs —— 课程共享小工具
 * 各课 import { deepFreeze, sleep, countTokens } from '../shared/mini-util.mjs'
 */

/** 深冻结：OpenCode 的工具定义、权限规则集一旦进入注册表就不再改动，
 *  每轮都是"重新 resolve 出一份新视图"——冻结是 mini 版对这一纪律的表达。 */
export function deepFreeze(obj) {
  for (const v of Object.values(obj)) if (v && typeof v === 'object') deepFreeze(v)
  return Object.freeze(obj)
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

/**
 * token 估算：字符数 / 4。
 * 这正是 OpenCode 真实压缩预算用的估算式（packages/core/src/util/token.ts:4，
 * `CHARS_PER_TOKEN = 4`，`estimate = round(len/4)`）——粗，但只服务于
 * prune/select 的预算判断；真实成本以 provider 回报的 usage 为准。
 */
export const CHARS_PER_TOKEN = 4
export const countTokens = (text) => Math.max(0, Math.round(text.length / CHARS_PER_TOKEN))

/**
 * 通配匹配（mini 版 Wildcard.match）：`*` → `.*`，`?` → `.`，其余正则元字符转义。
 * 对照 packages/core/src/util/wildcard.ts 的 match()（转义 → 替换 → 全串锚定），
 * 语义一致；真实版还处理路径分隔符归一与 Windows 大小写不敏感。
 */
export function wildcardMatch(input, pattern) {
  const escaped = pattern
    .replace(/[.+^${}()|[\]\\]/g, '\\$&')
    .replace(/\*/g, '.*')
    .replace(/\?/g, '.')
  return new RegExp('^' + escaped + '$', 's').test(input)
}

/** 剧本化 Mock 模型的通用外壳：按剧本顺序吐出事件，像真的流式响应一样逐个回调。 */
export function scriptedStream(script, onEvent) {
  return {
    async run() {
      for (const event of script) {
        await sleep(event.delay ?? 0) // 用小延迟模拟流式到达的节奏
        onEvent(event)
      }
    },
  }
}
