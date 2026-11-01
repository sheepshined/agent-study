#!/usr/bin/env node
/**
 * s10_pairing_rate_limits.mjs —— 设备配对与六条限流（收官课）
 *
 * 无人值守系统的最后一道墙回答两个问题：**谁在敲门**（身份），以及
 * **敲门有多急**（预算）。coding CLI 两个问题都不存在——进程是你自己启动的。
 *
 * A. 设备配对（docs/concepts/architecture.md:99-115）：
 *    · 所有 WS 客户端（operator + node）connect 时带 device identity；
 *    · 新 device id 需要配对批准；Gateway 下发 challenge nonce，客户端必须
 *      签名；签名 payload v3 还绑 platform 与 deviceFamily（防签名挪用）；
 *    · 通过后下发 device token 供重连；重连钉住配对元数据，元数据变化
 *      要求重新配对；
 *    · loopback 本机可自动批准（同机 UX）；tailnet/LAN 一律显式批准；
 *    · 配对的那头：Rust openclaw-node 设备节点宿主（unsafe_code="forbid"，
 *      离线签名、密钥擦除、headless）。
 *
 * B. 六条独立限流（docs/gateway/security/rate-limiting.md:17-24）：
 *    认证失败 10/60s→锁 5 分钟（loopback 豁免，浏览器 WS 不豁免）
 *    ｜webhook 认证失败 20/60s→锁 60s（不可配）
 *    ｜控制面写 RPC 30/60s per method+device+IP（不可配）
 *    ｜ACP 会话创建 120/10s ｜Gateway 重启 30s 冷却。
 *    各自保护不同边界、按不同身份计数、错误形状不同——不是一条总闸。
 *
 *   设备 connect ──→ challenge ──→ 签名验证 ──→ device token
 *        │                                              │
 *        └── 恶意方 ──→ 六条限流按边界各挡各的 ──→ 锁定/冷却
 *
 * 运行：node code.mjs    （零依赖，离线；签名/时钟由 Mock 驱动）
 * 对照真实源码：src/pairing/pairing-challenge.ts（challenge 签发/校验）、
 *   src/node-host/（TS 侧节点宿主 + exec-policy.ts）、crates/openclaw-node-host/
 *   （Rust 侧，Cargo.toml:33 unsafe_code="forbid"）、
 *   src/gateway/methods/core-descriptors.ts（RPC method → scope 声明表）、
 *   docs/gateway/security/rate-limiting.md、docs/gateway/security/trust-model.md
 */

import { assert } from '../shared/mini-util.mjs'
import { createHash } from 'node:crypto'

// ---------------------------------------------------------------
// 第 1 部分：设备配对（architecture.md:99-115 的机制骨架）
// ---------------------------------------------------------------
/** 教学"签名"：HMAC 不引依赖，用 sha256(mac || nonce || platform || deviceFamily) 示意。
 *  真实实现是 ed25519（Rust 侧 crates 用 ed25519-dalek），payload v3 绑 platform/deviceFamily。 */
const mockSign = (secret, { nonce, platform, deviceFamily }) =>
  createHash('sha256').update(`${secret}|${nonce}|${platform}|${deviceFamily}`).digest('hex')

class MiniGatewayPairing {
  constructor({ secret = 'pairing-secret' } = {}) { this.secret = secret; this.tokens = new Map(); this.pinned = new Map() }

  /** loopback 自动批准；远程设备走显式批准（这里 mock 为 true=管理员点了批准）。 */
  async onConnect({ deviceId, loopback, platform, deviceFamily, approvedByOperator }) {
    if (this.tokens.has(deviceId) && !loopback) {
      // 已配对设备重连：钉住元数据，变了要重新配对。
      const pinnedMeta = this.pinned.get(deviceId)
      if (pinnedMeta && (pinnedMeta.platform !== platform || pinnedMeta.deviceFamily !== deviceFamily)) {
        return { ok: false, reason: `配对元数据漂移（${pinnedMeta.platform}/${pinnedMeta.deviceFamily} → ${platform}/${deviceFamily}），要求重新配对` }
      }
      return { ok: true, reconnected: true, token: this.tokens.get(deviceId) }
    }
    if (loopback) return this.finishPairing({ deviceId, platform, deviceFamily }) // 本机自动批准
    if (!approvedByOperator) return { ok: false, reason: '非本机连接需要显式配对批准（tailnet/LAN 也不例外）' }
    const challenge = { nonce: `nonce-${deviceId}-${Math.floor(Math.random() * 1e6)}` }
    return { ok: false, needsChallenge: challenge, note: '先签名 challenge 再来' }
  }

  /** challenge 验签：签名错误/平台绑定不符都拒绝（失败路径）。 */
  verifyAndApprove({ deviceId, platform, deviceFamily }, challenge, signature) {
    const expected = mockSign(this.secret, { nonce: challenge.nonce, platform, deviceFamily })
    if (signature !== expected) return { ok: false, reason: 'challenge 签名验证失败' }
    // 攻击者拿着"为旧平台签好的名"换个平台用——v3 绑定让签名挪用失效。
    const misplaced = mockSign(this.secret, { nonce: challenge.nonce, platform: 'macos', deviceFamily })
    if (signature === misplaced && platform !== 'macos') return { ok: false, reason: '签名 payload 平台绑定不符（v3）' }
    return this.finishPairing({ deviceId, platform, deviceFamily })
  }
  finishPairing({ deviceId, platform, deviceFamily }) {
    const token = `devtok-${createHash('sha256').update(deviceId).digest('hex').slice(0, 16)}`
    this.tokens.set(deviceId, token)
    this.pinned.set(deviceId, { platform, deviceFamily }) // 元数据钉住：重连比对
    return { ok: true, token, note: '后续重连用 device token' }
  }
}

// ---------------------------------------------------------------
// 第 2 部分：六条独立限流（rate-limiting.md:17-24 的机制骨架）
// ---------------------------------------------------------------
class RateLimiter {
  constructor(name, { limit, windowMs, lockoutMs, keyedBy, configurable, exempt }) {
    Object.assign(this, { name, limit, windowMs, lockoutMs, keyedBy, configurable, exempt })
    this.buckets = new Map() // key -> {count, windowStart, lockedUntil}
  }
  hit(key, { now = Date.now(), exempted = false } = {}) {
    const b = this.buckets.get(key) ?? { count: 0, windowStart: now, lockedUntil: 0 }
    if (now < b.lockedUntil) return { ok: false, status: 429, reason: `${this.name}：锁定中至 ${new Date(b.lockedUntil).toISOString()}` }
    if (now - b.windowStart >= this.windowMs) { b.count = 0; b.windowStart = now } // 窗口滑动
    if (this.exempt?.(exempted)) return { ok: true, note: '豁免（未消耗预算）' }
    b.count++
    this.buckets.set(key, b)
    if (b.count > this.limit) {
      if (this.lockoutMs > 0) {
        b.lockedUntil = now + this.lockoutMs
        return { ok: false, status: 429, reason: `${this.name}：${this.limit} 次/${this.windowMs / 1000}s 上限 → 锁 ${this.lockoutMs / 1000}s` }
      }
      // 有些限流没有"锁定"语义（如控制面写 RPC）：窗口滑走之前一律拒，不追加惩罚。
      return { ok: false, status: 429, reason: `${this.name}：本 ${this.windowMs / 1000}s 窗口预算（${this.limit} 次）已用完，窗口滑动后恢复` }
    }
    return { ok: true, count: b.count }
  }
}

const LIMITS = [
  new RateLimiter('认证失败', { limit: 10, windowMs: 60_000, lockoutMs: 300_000, keyedBy: 'IP+credential scope', configurable: true, exempt: (loopback) => loopback }),
  new RateLimiter('浏览器WS认证失败', { limit: 10, windowMs: 60_000, lockoutMs: 300_000, keyedBy: 'IP/origin', configurable: true, exempt: () => false }), // loopback 不豁免！
  new RateLimiter('webhook认证失败', { limit: 20, windowMs: 60_000, lockoutMs: 60_000, keyedBy: 'IP', configurable: false, exempt: () => false }),
  new RateLimiter('控制面写RPC', { limit: 30, windowMs: 60_000, lockoutMs: 0, keyedBy: 'method+device+IP', configurable: false, exempt: () => false }),
  new RateLimiter('ACP会话创建', { limit: 120, windowMs: 10_000, lockoutMs: 0, keyedBy: 'translator instance', configurable: false, exempt: () => false }),
  new RateLimiter('Gateway重启', { limit: 1, windowMs: 30_000, lockoutMs: 0, keyedBy: 'process', configurable: false, exempt: () => false }),
]

// ---------------------------------------------------------------
// 演示
// ---------------------------------------------------------------
async function main() {
  const log = (...a) => console.log(...a)

  console.log('== 1. 设备配对：本机自动批准，远程必须签名（失败路径）==')
  const gw = new MiniGatewayPairing()
  const local = await gw.onConnect({ deviceId: 'mac-local', loopback: true, platform: 'macos', deviceFamily: 'desktop' })
  log(`本机 loopback → ok=${local.ok}（自动批准，${local.note}）`)
  const remoteNoApproval = await gw.onConnect({ deviceId: 'lan-phone', loopback: false, platform: 'ios', deviceFamily: 'mobile', approvedByOperator: false })
  log(`远程未批准 → ${JSON.stringify({ ok: remoteNoApproval.ok, reason: remoteNoApproval.reason })}`)
  const ch = await gw.onConnect({ deviceId: 'lan-phone', loopback: false, platform: 'ios', deviceFamily: 'mobile', approvedByOperator: true })
  const badSig = gw.verifyAndApprove({ deviceId: 'lan-phone', platform: 'ios', deviceFamily: 'mobile' }, ch.needsChallenge, 'deadbeef')
  log(`坏签名 → ${JSON.stringify({ ok: badSig.ok, reason: badSig.reason })}`)
  const goodSig = gw.verifyAndApprove({ deviceId: 'lan-phone', platform: 'ios', deviceFamily: 'mobile' }, ch.needsChallenge, mockSign('pairing-secret', { nonce: ch.needsChallenge.nonce, platform: 'ios', deviceFamily: 'mobile' }))
  log(`正确签名 → ok=${goodSig.ok}（${goodSig.note}）`)
  // 元数据漂移：同一 token，换了个 deviceFamily 重连 → 拒绝。
  const drift = await gw.onConnect({ deviceId: 'lan-phone', loopback: false, platform: 'ios', deviceFamily: 'tablet' })
  log(`失败路径：元数据漂移重连 → ${JSON.stringify({ ok: drift.ok, reason: drift.reason })}`)
  assert(local.ok && !remoteNoApproval.ok && !badSig.ok && goodSig.ok && !drift.ok)

  console.log('\n== 2. 认证限流：loopback 豁免，但浏览器来源不豁免（失败路径）==')
  const authLimiter = LIMITS[0], browserLimiter = LIMITS[1]
  for (let i = 0; i < 12; i++) authLimiter.hit('127.0.0.1', { exempted: true })
  log(`loopback 打 12 次失败 → 全部豁免（本地 CLI 不该被自己锁死）`)
  for (let i = 0; i < 11; i++) browserLimiter.hit('127.0.0.1|browser-origin', { exempted: false })
  const blocked = browserLimiter.hit('127.0.0.1|browser-origin', {})
  log(`浏览器来源（同样来自 loopback IP）打 11 次 → 第 11 次 ${JSON.stringify(blocked)}`)
  assert(blocked.ok === false, '浏览器来源不豁免')

  console.log('\n== 3. 逐条看六条限流：各挡各的边界 ==')
  const wh = LIMITS[2]
  for (let i = 0; i < 21; i++) wh.hit('10.0.0.9')
  log(`webhook 认证失败 21 次 → ${JSON.stringify(wh.hit('10.0.0.9'))}`)
  const write = LIMITS[3]
  for (let i = 0; i < 31; i++) write.hit('agents.set|dev-1|10.0.0.9')
  log(`控制面写 RPC（per method+device+IP）31 次 → ${JSON.stringify(write.hit('agents.set|dev-1|10.0.0.9'))}`)
  const restart = LIMITS[5]
  restart.hit('process'); const twice = restart.hit('process', { now: Date.now() + 5_000 })
  log(`30s 内第二次重启 → ${JSON.stringify(twice)}`)
  log(`（ACP 会话创建 120/10s 按 translator 实例计——五类身份五种口径，不是一条总闸）`)

  console.log('\n== 4. 收官复盘：十课不变量连成一张网 ==')
  const invariants = [
    ['s01', '回复必回来源渠道，模型无权改道'],
    ['s02', 'sessionKey 是路由选择器，不是授权令牌'],
    ['s03', '同会话串行、整机限流、脏数据提交不进去'],
    ['s04', '收窄单调：每层只能删不能加；可用性 ≠ 授权'],
    ['s05', 'policy/allowlist/用户批准，三者同取更严者'],
    ['s06', '无人值守输入：身份与预算随输入自带'],
    ['s07', '记忆故障不阻塞回复；只有 compaction 改写历史'],
    ['s08', '装载顺序即权限；角色闸挡住运维技能'],
    ['s09', '终态裁决不可被低优先级推翻'],
    ['s10', '身份配对解决"谁在敲门"，限流解决"敲门有多急"'],
  ]
  invariants.forEach(([n, s]) => log(`  ${n}  ${s}`))
  log('  ↳ 这就是"没有人看着"的全套基础设施。')
}

main().catch((e) => { console.error(e); process.exit(1) })
