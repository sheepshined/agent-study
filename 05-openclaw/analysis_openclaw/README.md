# Learn OpenClaw —— "没有人看着"的助理网关工程

> 献给想读懂 [openclaw](../openclaw/)（OpenClaw v2026.9.5，MIT，TS + Rust，pnpm monorepo）源码的人。十课，每课：**中文讲解 + 注释版可运行代码 + 图解 + 对照真实源码的精读锚点**。体例对标 [03-deepseek-harness/analysis_deepseek_harness](../../03-deepseek-harness/analysis_deepseek_harness/)，事实锚点来自本工作区 [架构拆解](../架构拆解.md) 与 [阅读指南](../阅读指南.md)（均已带 文件:行号 考据）。

## 先换脑子：它不是 coding CLI

**Agency 来自模型，Agent 产品 = 模型 + Harness。** 模型是驾驶者，harness 是载具——这条总纲和本工作区其他五家课程一致。但 OpenClaw 把"载具"造在了完全不同的地形上：

> Claude Code / Codex / DeepSeek Harness 的宿主是**"终端 + 一个仓库 + 一个坐在键盘前审批的人"**——输入是人敲的 prompt，出事有人兜底。
>
> OpenClaw 的宿主是**"一台常开机器 + 27 类通讯渠道 + 一组配对设备"**（WhatsApp/Telegram/Discord/Slack/Signal/iMessage…，`src/channels/bundled-channel-ids.generated.ts`）——输入是**随时插进来的消息事件**，而人类大概率不在键盘前。

于是它多出整套 coding CLI 从来不需要的基础设施，这门课就叫它 **"没有人看着"的全套工程**：sessionKey 路由语法（s02）、双层 lane（车道/串行队列）+ 写者围栏（s03）、工具面八层收窄（s04）、DM 配对码与审批绑定（s05）、cron/webhook/语音唤醒三类无人值守输入源（s06）、把记忆写路径当安全边界（s07）、七档 skills 优先级（s08）、17 个钩子位 + 插件注册面（s09）、设备签名配对与六条限流（s10）。它的信任模型一句话：**trusted gateway, untrusted execution**（`README.md:20`），应对顺序 **Identity first → Scope next → Model last**（`docs/gateway/security/trust-model.md:76-80`）。

## 课程目录

| 课 | 主题 | 一句话 | 核心不变量 |
|----|------|--------|-----------|
| [s01_channel_gateway](s01_channel_gateway/) | 渠道网关 | channel 适配器归一化入站，gateway run 常驻生命周期 | 回复必回来源渠道，模型无权改道 |
| [s02_session_key](s02_session_key/) | sessionKey 路由 | 多渠道消息归一到会话的确定性语法 | sessionKey 是路由选择器，不是授权令牌 |
| [s03_lanes_writer_fence](s03_lanes_writer_fence/) | 并发纪律 | 双层 lane 串行化 + 写者围栏 | 同会话串行、整机限流、脏数据提交不进去 |
| [s04_tool_pipeline](s04_tool_pipeline/) | 工具面收窄 | 八层配置单调收窄 + 客户端能力裁剪 | 每层只能删不能加，可用性 ≠ 授权 |
| [s05_security_gates](s05_security_gates/) | 安全闸门 | dmPolicy 配对码 / 两层白名单 / exec 审批绑定 | policy、allowlist、用户批准三者同取更严者 |
| [s06_unattended_inputs](s06_unattended_inputs/) | 无人值守输入源 | cron / webhook / 语音唤醒汇入同一 dispatch | 输入没有人类在场，身份必须随输入自带 |
| [s07_memory_compaction](s07_memory_compaction/) | 记忆与压缩 | 六个 workspace 注入文件 + 唯一能改写历史的机制 | 记忆故障永不阻塞回复；只有 compaction 改写历史 |
| [s08_skills_priority](s08_skills_priority/) | skills 七档优先级 | 同名技能谁说了算 | 高优先级源赢，装载顺序即权限 |
| [s09_hooks_plugins](s09_hooks_plugins/) | 钩子与插件 | 17 个钩子位的时序与终态 + 插件注册面 | 终态裁决（block/cancel）不可被低优先级推翻 |
| [s10_pairing_rate_limits](s10_pairing_rate_limits/) | 设备配对与限流收官 | 签名 challenge + 六条限流，无人值守的最后一道墙 | 无人值守系统按"身份 + 预算"双轨设防 |

依赖关系是线性的：每课建立在前一课的 mini 实现心智上（但每课代码**自包含可独立运行**，跳读也不会断）。

## 运行

唯一前置：**Node.js ≥ 18**（无任何 npm 依赖；模型一律由脚本化 Mock 扮演，全程离线）。逐课：

```bash
cd s03_lanes_writer_fence && node code.mjs
```

或一键全跑：

```bat
run.bat        :: Windows
./run.sh       :: Linux / macOS
```

全部通过会打印 `All 10 lessons passed.`

## 与本工作区其他材料的关系

- **先读什么**：没有 OpenClaw 概念时，先看 [阅读指南](../阅读指南.md)（20 分钟级导览，含六阶段精读路线）→ 再来逐课动手 → 最后按 [架构拆解](../架构拆解.md) 第 14 节"关键文件索引"回真源码。
- **真源码**：`../openclaw/`，本地检出为 `study-cn-comments` 注释分支——核心文件头部带 `[中文导读 · 学习注释]` 块，注释文件内的行号相对上游 main 整体下移十几行，**跳转认符号名**（`runChannelTurn`、`resolveSessionLane`、`runBeforeToolCallHook`）。本课程"对照真实源码"表的行号以本地检出现状给出，并附漂移警告。
- **同门课程**：DeepSeek Harness 的教材见 [03-deepseek-harness/analysis_deepseek_harness](../../03-deepseek-harness/analysis_deepseek_harness/)（插件内核路线）；Claude Code 的见 [01-claude-code/analysis_claude_code](../../01-claude-code/analysis_claude_code/)。三家对照：dsh 把**组装面**做到极致，Claude Code 把**工具面**做到极致，OpenClaw 把**"无人值守"的运行时纪律**做到极致——s03/s05/s10 三课是它独有的。
- **方法论延伸**：压缩/记忆的通用方法论见 [context-handbook](../../context-handbook/Context与记忆系统手册.md)（s07 对照阅读）；多 agent 协同见 [multiagent-handbook](../../multiagent-handbook/Multi-Agent协同手册.md)（对照 `docs/concepts/multi-agent.md`）；安全视角见 [security-handbook](../../security-handbook/AI应用安全手册.md)（s05/s10 对照阅读，OpenClaw 自己的 `SECURITY.md` 是第一手材料）。

## 免责与安全

OpenClaw 官方明示：它是 **local-first agent infrastructure for trusted operators**（`SECURITY.md:5`），沙箱默认关闭，不支持互不信任的用户共享一个 Gateway。本课程的全部代码是**教学用 mini 实现**——零依赖、离线、不依赖也不执行真实 OpenClaw 二进制，只演示机制形状，不代表上游的工程完成度。任何把真实 assistant 接入公网渠道的动作，请先读完它的 `SECURITY.md`。
