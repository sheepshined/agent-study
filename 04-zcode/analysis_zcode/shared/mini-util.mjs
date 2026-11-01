/**
 * shared/mini-util.mjs —— ZCode 课程共享小工具
 *
 * 对应真实源码里的两个习惯：
 *  - 冻结定型对象：ZCode 的工具契约（toContracts）与 provider 配置解析后都不允许再改，
 *    避免"某个调用点偷偷篡改共享状态"。见 core/src/tool/registry.ts 的 toContracts。
 *  - 断言不变量：AGENTS.md 要求"测试 case 很关键，能证明结果是否符合预期"；
 *    本仓几乎没有随源码发布的测试，课程代码就用 assert 当轻量回归。
 */

/** 深冻结：注册表条目、权限规则这类"定型即只读"的对象通用。 */
export function deepFreeze(obj) {
  for (const v of Object.values(obj ?? {})) if (v && typeof v === 'object') deepFreeze(v)
  return Object.freeze(obj)
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

/** 轻量断言：课程演示里用来证明"不变量真的守住了"。 */
export function assert(cond, msg) {
  if (!cond) throw new Error(`[不变量被破坏] ${msg}`)
}

/** 打印一个小节标题，让 main() 的输出像一份实验报告。 */
export function banner(title) {
  console.log(`\n== ${title} ==`)
}
