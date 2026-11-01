# Learn OpenAI Codex —— 工业化 Agent 的安全与工程答案

> 献给想读懂 [openai/codex](../codex/)（Rust workspace `codex-rs/`，100+ crate）源码的人。十课，每课：**中文讲解 + 注释版可运行代码 + 图解 + 对照真实源码的精读锚点**。体例对标 [03-deepseek-harness/analysis_deepseek_harness](../../03-deepseek-harness/analysis_deepseek_harness/)；事实对齐本工作区的 [阅读指南](../阅读指南.md) 与 [架构拆解](../架构拆解.md)（结论均带 文件:行号）。

## Harness 是什么，Codex 特殊在哪

**Agency 来自模型，Agent 产品 = 模型 + Harness。** 模型是驾驶者，harness 是载具——本课程教你造载具（与 Claude Code / DeepSeek 两套教材同一立场）。

Codex 的差异化主张是一句话：**权限与沙箱是内核级一等公民，前端只是客户端**。它的所有工具执行都统一穿过 `orchestrator`（审批 → 选沙箱 → 执行 → 拒绝后升级重试，`core/src/tools/orchestrator.rs` 文件头注释即设计文档）；"能不能做"由 `AskForApproval` × `SandboxPolicy` × `NetworkAccess` 三轴组合表达，可审计、可缓存、可跨平台落地（macOS Seatbelt / Linux Landlock+bwrap / Windows 沙箱）。而内核只此一份——TUI、IDE 插件、桌面 App、SDK 全部通过 **app-server 守护进程**（JSON-RPC over stdio）驱动它，"没有特权前端，也没有特权内核"。

如果说 DeepSeek Harness（s 课程姊妹篇）把"可组装"做到了极致（Everything is a Plugin），Codex 把"**工程化与安全**"做到了极致：同一个 agent loop，两份工业化答案。

## 语言选型说明（先读这段再上课）

Codex 本体是 Rust（异步运行时 tokio）。本课程**不用 Rust 教**：一是本教材假定读者没有 Rust 工具链（本机即无 cargo），二是回合循环、审批、沙箱、协议这些概念与语言无关。因此沿用 01-claude-code 的先例（TS 产品用 Python 教）：**每课的 mini 实现用 Python 纯标准库编写（asyncio / dataclasses / typing / json / subprocess…），零 pip 依赖，`python code.py` 直跑、全离线（模型由脚本化 Mock 扮演）**。Rust 侧概念映射到 Python 时会在注释里注明对应关系——例如 tokio mpsc ↔ `asyncio.Queue`、trait ↔ `typing.Protocol`、serde tagged enum ↔ 带判别字段的 dataclass、`Arc<Mutex<T>>` ↔ 普通对象 + asyncio 锁。读懂 mini 版之后，再按每课"对照真实源码"表回到 Rust 源码精读，路径与行号都已核实并标注漂移警告。

## 课程目录

| 课 | 主题 | 一句话 | 核心不变量 |
|----|------|--------|-----------|
| [s01_turn_loop](s01_turn_loop/) | 回合循环 | `run_turn`：预压缩 → 按需装配 → step 循环（采样→工具→预算检查） | 一步一快照：step 内世界冻结，步与步之间才是变更窗口 |
| [s02_rollout](s02_rollout/) | 会话记录 | rollout：JSONL 追加录制 + 重放重建（resume / fork） | 轨迹只增不减，重建必须确定性 |
| [s03_tool_registry](s03_tool_registry/) | 工具编排 | ToolRegistry + orchestrator 四段：审批 → 选沙箱 → 执行 → 升级重试 | 每次执行必过总闸，没有旁路 |
| [s04_sandbox_axes](s04_sandbox_axes/) | 沙箱双轴 | AskForApproval × SandboxPolicy 判定矩阵 + WritableRoot 保护 | 审批管"问不问"，沙箱管"能怎样"，两轴正交 |
| [s05_escalation](s05_escalation/) | 升级重试 | 沙箱拒绝 → 升级判定 → 免重审批重跑（escalation 语义） | 只有"策略挡了"才升级；命令报错不重试 |
| [s06_mcp_bridge](s06_mcp_bridge/) | MCP 双向 | stdio JSON-RPC 接外部工具（client），elicitation 反向征求用户（server 侧） | 外部工具与内置工具走同一套运行时 |
| [s07_apply_patch](s07_apply_patch/) | 补丁式编辑 | apply_patch 格式 + seek_sequence 模糊定位 + code mode 一览 | 编辑是补丁事务，不是散落的读写 |
| [s08_multi_agents](s08_multi_agents/) | 多智能体 | spawn / send / wait + agent-roles + 命名空间工具 | 子代理过程不可见，结论与活动可见 |
| [s09_app_server](s09_app_server/) | 服务化 | JSON-RPC over stdio 守护进程，多前端共享内核 | 内核只此一份，前端都是客户端 |
| [s10_frontends](s10_frontends/) | 收官装配 | CLI / exec / app-server 客户端对照 + 与 DeepSeek profile 横向比较 | 同一事件流，不同投影 |

依赖关系是线性的：每课建立在前一课的概念上（但每课代码**自包含可独立运行**，跳读也不会断）。

## 运行

唯一前置：**Python ≥ 3.11**（仅标准库，无任何 pip 依赖）。逐课：

```bash
cd s01_turn_loop && python code.py
```

或一键全跑：

```bat
run.bat        :: Windows
./run.sh       :: Linux / macOS
```

全部课程完全离线：模型由脚本化 Mock 扮演，外部进程（MCP server、app-server）由同一文件以子进程方式扮演——这本身就是 s06/s09 的教学内容。

## 与本工作区其他材料的关系

- **先读什么**：没有 Codex 概念时，先看 [阅读指南](../阅读指南.md)（crate 导览 + 阅读路线，20 分钟级）→ 再来逐课动手 → 最后按 [架构拆解](../架构拆解.md) 第 11 节"关键文件索引（精读清单）"回真源码。收官课 s10 末尾也附了这条路线。
- **真源码**：`../codex/`（github.com/openai/codex @ 快照 `818f1cc`，Apache-2.0），核心在 `../codex/codex-rs/`。本课程所有 文件:行号 都对该检出核实过；**行号以当前检出为准，上游会漂移**——以每课"对照真实源码"表的路径为锚，行号只当路标。
- **姊妹教材**：DeepSeek Harness 的十课见 [03-deepseek-harness/analysis_deepseek_harness](../../03-deepseek-harness/analysis_deepseek_harness/)（TS/Node 路线）。两家对照着学：一个把**组装面**做到极致（插件树 + profile），一个把**安全面**做到极致（orchestrator + 双轴沙箱）；s10 有逐项横向比较。
- **横向对照**：Claude Code 的教材见 [01-claude-code/analysis_claude_code](../../01-claude-code/analysis_claude_code/)（Python 路线，本课程的语言先例）。
- **方法论延伸**：沙箱/审批的安全原理见 [security-handbook/AI应用安全手册.md](../../security-handbook/AI应用安全手册.md)（s03–s05 的理论底座）；MCP 协议本身见 [mcp-handbook/MCP搭建文档.md](../../mcp-handbook/MCP搭建文档.md)（s06 的协议背景）；多智能体协作模式见 [multiagent-handbook/Multi-Agent协同手册.md](../../multiagent-handbook/Multi-Agent协同手册.md)（s08 背景）。

## 免责与安全

Codex 是 OpenAI 官方开源项目，迭代极快（本文档快照 2026-09，行号会漂移）。本课程的全部代码是**教学用 mini 实现**：不依赖、不执行真实 Codex 二进制；沙箱与审批均为教学模拟，**不能**当作真实安全边界使用。真实沙箱语义请以官方文档（仓库 `docs/sandbox.md`、`docs/config.md`）与源码为准，并在一次性容器/VM 中运行真实 agent——见 [AI应用安全手册](../../security-handbook/AI应用安全手册.md)。
