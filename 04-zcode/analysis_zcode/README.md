# Learn ZCode —— 同一个内核，装进每一种壳

> 献给想读懂 [ZCode](../ZCode/)（zai-org/ZCode v3.14.0）源码的人。十课，每课：**中文讲解 + 注释密集的可运行代码 + 图解 + 对照真实源码的精读锚点**。体例对标 [03-deepseek-harness/analysis_deepseek_harness](../../03-deepseek-harness/analysis_deepseek_harness/)，事实锚点全部来自本工作区 [阅读指南](../阅读指南.md) 与 [架构拆解](../架构拆解.md)（带 文件:行号），并已在仓库 `study-cn-comments` 分支逐文件核实。

## 为什么值得造 ZCode 这台载具

**Agency（自主性）来自模型，Agent 产品 = 模型 + Harness（挽具/载具）。** 模型是驾驶者，harness 是载具——载具决定油门踩多深时会不会翻车。ZCode 自述 "Z.ai's coding agent harness"，它把"载具"这件事做到了一个罕见的高度：**同一个 agent 内核，装进终端 TUI、Electron 桌面、Web 服务器、SDK、乃至手机远控五种壳**（`README.md:16-20`）。

它值得单独学一门课的差异化主张，从架构拆解可以提炼成五条：

1. **三层显式循环**。turn（回合入口）→ provider-turn 外层循环 → 单个 model step（`core/src/runtime/methods/{turn,turn-loop,turn-model-step}.ts`）。别家的循环是"一个 while 塞所有事"，ZCode 把**回合编排、请求前治理、单步执行与恢复**拆成三层，每层职责单一、可独立恢复——这是它声称"面向长程任务、不用 tool call 次数做硬停止"（`apps/zcode-cli/AGENTS.md:11`）的结构底气。
2. **事件溯源 SQLite**。会话、消息、权限、usage、工作流全部落 `~/.zcode/cli/db/db.sqlite`（31 张表的上游口径，本地检出 0001→0022 迁移、23 个独立表名）——"事件即事实"，fork/rewind/checkpoint 都是对事实的另一次投影，不是改历史。
3. **权限格子细到通道级**。5 值模式（plan/build/edit/yolo/auto）不是挡位切换那么简单：`alwaysAsk`（工具自报"必须问人"）是一独立通道，**压过 yolo 的放行、却压不过硬阻断**（`permission/service.ts:114,367`）；外加一个把 CLI 手册编译成 1.9 MB 权限数据的知识库（六家独一份）。
4. **dynamic workflow（动态工作流）**。让模型**写 TS 程序**编排长任务，再经编译器静态分析（taint 污点分析不动点）决定并发与脏节点，最后在 `vm.createContext` 独立 realm 的子进程里受限执行（`dynamic-workflow*/`）——比"再派一个子代理"结构化，比"给模型一个 shell"可控，六家独一份。
5. **协议化多宿主**。内核与宿主之间是 ZCode Protocol V4 stdio 帧通道，协议类型只落 `packages/shared/src/zcode-protocol/index.ts` 一个文件；`CommandInbox` 串行 admission（准入）让五种宿主共享同一条"输入即命令"的纪律。

同时也要诚实地说它的边界（详见 [架构拆解](../架构拆解.md) 第 13 节）：**没有操作系统沙箱**、headless 默认 `yolo`、写文件不做路径硬拦——安全完全压在"模式 + 规则 + 审批 + 工具自声明"的应用层格子上。这套格子有多细、缺了 OS 层会漏什么，正是 s04 要亲手摸的。

## 课程目录

| 课 | 主题 | 一句话 | 核心不变量 |
|----|------|--------|-----------|
| [s01_three_layer_loop](s01_three_layer_loop/) | 三层循环 | turn → provider-turn 循环 → model step，为什么不是"一个 while" | 配置冻结在 await 之前；停止靠语义事件不靠计数 |
| [s02_sqlite_eventsourcing](s02_sqlite_eventsourcing/) | 事件溯源 | SQLite 31 表：会话 fork/rewind/checkpoint 都是投影 | 事件即事实，只追加；fork 不复制、rewind 不删除 |
| [s03_tool_dual_schema](s03_tool_dual_schema/) | 工具双轨 | zod 管运行时校验，手写 JSON Schema 下发 provider；边流式边执行 | 审批绝不被"提前执行"绕过；错误回灌模型而非抛出 |
| [s04_permission_lattice](s04_permission_lattice/) | 权限格子 | 5 模式 + alwaysAsk 独立通道 + 命令知识库 | alwaysAsk 压过 yolo 却压不过 deny；auto 未实现即 deny |
| [s05_context_budget](s05_context_budget/) | 上下文预算 | microcompact → auto compact → reactive，外加 rapid-refill 熔断 | 安全指令逐字保留；刚压又满就熔断而不是无限压 |
| [s06_hooks_trust](s06_hooks_trust/) | hooks 与信任 | 7 个 hook 事件 + 工作区 hook 信任状态机 | 仓库输入不可自我提权：声明变更即信任失效 |
| [s07_plugin_host](s07_plugin_host/) | 插件独立进程 | 插件跑在 plugin-host 进程，`zcode_` 变量只展开白名单 | 插件崩溃不连坐内核；凭据不裸躺在插件环境里 |
| [s08_dynamic_workflow](s08_dynamic_workflow/) | 动态工作流 | 模型写 TS → 静态/taint 分析 → vm 独立 realm 受限执行 | 模型可见 API 只认 facade .d.ts；沙箱里没有 process |
| [s09_provider_catalog](s09_provider_catalog/) | 目录驱动 | 20 个模板、3 种 api.type，加 provider = 加一条 rule | 重试自持（AI SDK maxRetries 关 0），两层重试不相乘 |
| [s10_one_kernel_many_hosts](s10_one_kernel_many_hosts/) | 多形态收官 | TUI/Desktop/Web/手机远控，同一内核同一协议 | stdout 是严格帧通道；busy 输入必须串行 admission |

依赖关系是线性的：每课建立在前一课的概念上（但每课代码**自包含可独立运行**，跳读也不会断）。

## 运行

唯一前置：**Node.js ≥ 18**（无任何 npm 依赖；模型一律由脚本化 Mock 扮演，完全离线）。逐课：

```bash
cd s01_three_layer_loop && node code.mjs
```

或一键全跑：

```bat
run.bat        :: Windows
./run.sh       :: Linux / macOS
```

## 与本工作区其他材料的关系

- **先读什么**：没有 ZCode 概念时，先看 [阅读指南](../阅读指南.md)（坐标系 + 包导览 + 阅读路线）→ 再来逐课动手 → 最后按 [架构拆解](../架构拆解.md) 第 14 节的 30 条精读清单回真源码。
- **真源码**：`../ZCode/`，当前检出是带 `[中文导读 · 学习注释]` 文件头的学习分支——多数核心文件头部自带 `关键入口：符号 :行号` 锚点，本课程"对照真实源码"表优先引用这些锚点。**行号以当前检出为准，上游会漂移；跨分支请认符号名**。
- **横向对照**：DeepSeek Harness 的教材见 [03-deepseek-harness/analysis_deepseek_harness](../../03-deepseek-harness/analysis_deepseek_harness/)。两家是绝佳对照组：dsh 把"组装面"做到极致（一切皆插件），ZCode 把"治理面"做到极致（三层循环/权限格子/事件溯源/受限执行）；Claude Code 的 Python 路线见 [01-claude-code](../../01-claude-code/)。
- **方法论延伸**：压缩/记忆的通用方法论见 [context-handbook](../../context-handbook/Context与记忆系统手册.md)（s05 的三层预算是它的一个具体实现）；评测口径见 [eval-handbook](../../eval-handbook/Agent评测与质量工程手册.md)。

## 免责与安全

ZCode 是快速迭代的上游（本课锚定 v3.14.0 检出），**行号会漂移，结论请回源码验证**。`NOTICE.md` 明确声明：共享 Agent 执行适配器**不提供默认的 OS 沙箱**，Computer Use 为占位，凭据存储不是系统钥匙串。本课程全部代码是**教学用 mini 实现**，不依赖、不执行真实 ZCode 二进制、不发起任何网络请求；s08 的"受限求值器"使用 Node 内置 `vm` 演示 realm 隔离思想，仅用于离线教学，**不是安全边界**。
