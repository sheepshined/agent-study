# Learn OpenCode —— HTTP-first 多前端 Agent Server 的工程构造

> 献给想读懂 [opencode](../opencode/)（anomalyco/opencode v1.18.32）源码的人。十课，每课：**中文讲解 + 注释版可运行代码 + 图解 + 对照真实源码的精读锚点**。体例对标 [03-deepseek-harness/analysis_deepseek_harness](../../03-deepseek-harness/analysis_deepseek_harness/)，全部事实锚点来自本工作区 [阅读指南](../阅读指南.md) 与 [架构拆解](../架构拆解.md)（结论带 文件：行号）。

## 为什么值得造 OpenCode 这台载具

**Agency 来自模型，Agent 产品 = 模型 + Harness。** 模型是驾驶者，harness 是载具——本课程教你造载具（这个立场与 deepseek 课程一致）。而 OpenCode 是六家里把"载具的服务端形态"推得最远的一台：

1. **HTTP-first 边界，但默认零网络**。会话、工具、权限、provider 全部住在一个 Effect 写成的 server 里；TUI、Web、Electron、VS Code、ACP（Agent Client Protocol，编辑器经 stdio 接入的协议）、GitHub Action 都只是同一套 HttpApi 的客户端。最妙的是：默认部署下 server 跑在 Bun Worker 线程，`fetch` 被桥成 `app.fetch(request)` 的**进程内直调**，一次 TCP 都没有（`cli/tui/worker.ts:56`）——"客户端/服务端分离"是契约层面的（`specs/tui-package.md` 明文禁止 TUI 依赖内核包），不是部署层面的。
2. **上下文工程密度最高**。9+ 个 per-model 提示词家族（`session/system.ts`）、按模型替换工具（gpt 系用 `apply_patch` 取代 `edit`+`write`）、工具输出超限落盘后反向引导模型"委派 explore agent 去读"（`tool/truncate.ts`）、可从 turn 中间切开的 compaction tail 预算、doom-loop（死循环工具调用）自动拦截——每一处都值得单独精读。
3. **Effect（效果系统）作为骨架**。整颗内核是 `Effect.Effect<成功, 失败, 依赖>` 的组合：权限审批用 `Deferred.await` 挂起整轮、流式截断用 `takeUntil`、重试用 `Effect.retry(policy)`。mini 课程不需要会 Effect，但每课的"对照真实源码"都会指出对应机制在 Effect 里的位置。
4. **双内核演进的活标本**。V1（`packages/opencode/src/session/*`）是当前生产主路径；V2（`packages/core/src/session/*`，durable admission 语义）与它并存，靠 `event-v2-bridge.ts` 与 `config/v2-compat.ts` 缝合。读它的仓库你会同时看到"一个成熟 harness 怎么跑"和"一个 harness 怎么在不停车的前提下换引擎"。

一个必须先建立的预期：**OpenCode 没有 OS 级沙箱**——安全模型 = 权限规则 + 弹窗 + 提示词，`--yolo` 一键全放（架构拆解第 6.4 节实证）。学习它，既要学它的长处，也要看清这条最薄的防线。

## 课程目录

| 课 | 主题 | 一句话 | 核心不变量 |
|----|------|--------|-----------|
| [s01_runloop](s01_runloop/) | 主循环 | `while(true)` + processor 三态收束一轮 | 停环要"finish 可信 ∧ 本地无未结算 tool call" |
| [s02_session_store](s02_session_store/) | 会话存储 | 追加日志 + 投影重建；V2 换 SQLite 的理由 | 日志只增不减，状态是投影 |
| [s03_tool_system](s03_tool_system/) | 工具系统 | 内置 + 磁盘 + 插件三层来源，按模型动态裁剪 | 模型可见集 = 权限与模型约束的交 |
| [s04_permission](s04_permission/) | 权限 | `{permission, pattern, action}` + findLast 双通配 | 后写覆盖先写；未知即弹窗 |
| [s05_model_shape](s05_model_shape/) | 模型特化 | gpt 系换 apply_patch：工具面与提示词按模型分叉 | provider 差异写在代码里，不写进配置 |
| [s06_subagent](s06_subagent/) | 子代理 | task 递归同一 runLoop，权限只继承父 deny | 委派不放大权限 |
| [s07_plugin_hooks](s07_plugin_hooks/) | 插件钩子 | 21 个 Hooks 贴到推理链路的时序 | 钩子改的是"下一次请求"，不碰已落库历史 |
| [s08_prompt_family](s08_prompt_family/) | 提示词家族 | 9+ per-model 模板的前缀路由与拼装 | 模板顺序即优先级；指令首个命中即停 |
| [s09_http_boundary](s09_http_boundary/) | HTTP-first 边界 | 同一内核，网络传输与进程内直调互换 | 客户端只认协议，不认进程 |
| [s10_finale](s10_finale/) | 收官 | 独立 git-dir 做 undo + 多前端装配对照 | 快照与会话日志解耦；内核只有一份 |

依赖关系是线性的：s01 是其余各课的骨架（所有课都回到 runLoop）；每课代码**自包含可独立运行**，跳读也不会断。

## 运行

唯一前置：**Node.js ≥ 18**（无任何 npm 依赖）。逐课：

```bash
cd s04_permission && node code.mjs
```

或一键全跑：

```bat
run.bat        :: Windows
./run.sh       :: Linux / macOS
```

全部课程完全离线：模型一律由脚本化 Mock（剧本化 LLMEvent 流）扮演，s09 起的 HTTP 服务也只绑定本机随机端口、演示完即关。

## 与本工作区其他材料的关系

- **先读什么**：没有 OpenCode 概念时，先看 [阅读指南](../阅读指南.md)（含包导览与推荐阅读路线）→ 再来逐课动手 → 最后按 [架构拆解](../架构拆解.md) 第 14 节的 31 条精读索引回真源码。
- **真源码**：[../opencode/](../opencode/)，本地检出在 `study-cn-comments` 分支——核心文件头部有 `[中文导读 · 学习注释]` 块（会使文件内行号整体下移），本课程"对照真实源码"表的行号以**上游 dev 树**为准并附漂移警告。
- **横向对照**：deepseek-harness（dsh）的教材见 [03-deepseek-harness/analysis_deepseek_harness](../../03-deepseek-harness/analysis_deepseek_harness/)。两家对照着学：dsh 把**组装面**做到极致（Everything is a Plugin，子代理可以是别家引擎）；OpenCode 把**服务化与上下文工程**做到极致（HTTP-first 双内核，task 就是同进程递归调自己的 runLoop）。压缩/记忆的通用方法论另见 [context-handbook](../../context-handbook/Context与记忆系统手册.md)。
- **V2 语义的官方口径**：仓库根 `CONTEXT.md`（V2 权威术语表）与 [specs/](../opencode/specs/)（`specs/v2/session.md`、`specs/v2/tools.md` 等）——读 V2 概念后务必回 V1 主路径核对是否实跑。

## 免责与安全

本课程的全部代码是**教学用 mini 实现**，不依赖、不执行、不安装真实 opencode 二进制；脚本内的模型输出全部是预置剧本。OpenCode 是快速迭代的上游（默认分支 `dev`），行号与行为可能漂移，一切以源码为准。另请注意真实产品的两条安全边界：`--yolo` 会放开全部权限审批；`share` 功能会把完整会话（含工具输出与文件内容）上云，拿到链接 + secret 即可读——日常使用建议 `OPENCODE_DISABLE_SHARE`。
