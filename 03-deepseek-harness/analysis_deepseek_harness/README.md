# Learn DeepSeek Harness —— 真正的"可组装 Agent 平台"工程

> 献给想读懂 [deepseek-harness](../deepseek-harness/)（dsh）源码的人。十课，每课：**中文讲解 + 注释版可运行代码 + 图解 + 对照真实源码的精读锚点**。体例对标 [01-claude-code/analysis_claude_code](../../01-claude-code/analysis_claude_code/)，事实对齐本仓 `study-cn-comments` 分支的中文导读注释。

## Harness 是什么，dsh 特殊在哪

**Agency 来自模型，Agent 产品 = 模型 + Harness。** 模型是驾驶者，harness 是载具——本课程教你造载具（这个立场与 shareAI-lab 的 Claude Code 教材完全一致）。

dsh 的差异化主张是一句话：**Everything is a Plugin（一切皆插件）**。它构建在 Cordis 插件框架之上，模型适配器、工具注册表、会话日志、沙箱审批、**乃至 agent loop 本身**都是可替换的插件——不存在需要打补丁的特权内核。同一棵插件树，换一份清单（profile），就装成 Web 应用、桌面应用、SDK 服务或自动化服务；它甚至内置了把 Claude Code、Codex 当子代理调用的适配器——别家 harness 在这里"只是另一个 provider"。

## 课程目录

| 课 | 主题 | 一句话 | 核心不变量 |
|----|------|--------|-----------|
| [s01_plugin_kernel](s01_plugin_kernel/) | 插件内核 | mini-Cordis：事件总线 + 服务容器 + 可逆副作用 | 副作用必须可逆 |
| [s02_agent_loop](s02_agent_loop/) | 内核循环 | 轮次/步骤两级状态机 + inbox 唤醒分类 | Every request is derived from the session log |
| [s03_session_log](s03_session_log/) | 会话日志 | 仅追加 + JSONL 持久化 + 投影重建 | 日志只增不减，修正也是事件 |
| [s04_system_prompt](s04_system_prompt/) | 提示词组装 | 碎片 section → 冻结的 PromptAssembly | 注册表是唯一真源，提示词不存副本 |
| [s05_tool_pipeline](s05_tool_pipeline/) | 工具流水线 | 作用域注册表 + 四拍把关 + 有界滚动池 | 执行可以乱序，提交必须模型序 |
| [s06_llm_adapter](s06_llm_adapter/) | 模型适配缝 | 流式块组装 + 瞬态重试 + token 计量 | 半成品消息不落日志 |
| [s07_subagent](s07_subagent/) | 子代理 | spawn 就是普通工具，提供方决定引擎 | 过程不可见、结论可见 |
| [s08_compaction](s08_compaction/) | 上下文管理 | spill 落盘 + prune 剪枝 + summary 折叠 | 日志不动，投影动 |
| [s09_sandbox_approval](s09_sandbox_approval/) | 安全三层 | 权限预设 → 审批服务 → 沙箱边界 | 每个安全决策都是事件 |
| [s10_profile_assembly](s10_profile_assembly/) | profile 装配 | 同一棵树装出 headless / web / sdk | 没有 fork 的代码库，只有清单差异 |

依赖关系是线性的：每课建立在前一课的 mini 实现上（但每课代码**自包含可独立运行**，跳读也不会断）。

## 运行

唯一前置：**Node.js ≥ 18**（无任何 npm 依赖）。逐课：

```bash
cd s02_agent_loop && node code.mjs
```

或一键全跑：

```bat
run.bat        :: Windows
./run.sh       :: Linux / macOS
```

多数课程完全离线（模型由脚本化 Mock 扮演）；s06 在设置 `DEEPSEEK_API_KEY` 后会追加一段**真实的 DeepSeek 流式调用**，其余代码零改动——这本身就是"适配缝"的体感教学。

## 与本工作区其他材料的关系

- **先读什么**：没有 dsh 概念时，先看 [阅读指南](../阅读指南.md)（20 分钟级导览）→ 再来逐课动手 → 最后按 [架构拆解](../架构拆解.md) 的精读清单回真源码。
- **真源码**：`../deepseek-harness/`，当前检出 `study-cn-comments` 分支——核心文件的头部有 `[中文导读 · 学习注释]` 块（含行号锚点），本课程"对照真实源码"表的行号与之一致。
- **横向对照**：Claude Code 的教材见 [01-claude-code/analysis_claude_code](../../01-claude-code/analysis_claude_code/)（Python 最小实现路线）；dsh 走的是 TS/Node 路线（贴近真源码语言）。两家对照着学：一个把工具面做到极致，一个把组装面做到极致。
- **方法论延伸**：压缩/记忆的通用方法论见 [context-handbook](../../context-handbook/Context与记忆系统手册.md)；评测口径（如 s02 的粘性结局为什么重要）见 [eval-handbook](../../eval-handbook/Agent评测与质量工程手册.md)。

## 免责与安全

dsh 是 developer preview（会有破坏性变更），官方明确建议在一次性 VM/容器中运行（见仓库 `SAFETY.zh.md`）。本课程的全部代码是**教学用 mini 实现**，不依赖、不执行真实 dsh 二进制；s06 的真实 API 调用仅在你主动设置 `DEEPSEEK_API_KEY` 时发生。
