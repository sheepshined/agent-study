# AI Agent 源码学习工作区

> 首版：2026-09-11 ｜ 扩充至六家：2026-09-22
>
> 本工作区拉取了八个开源（或以开源形态可考）的 AI agent / 框架源码（01-06 六家 agent + 07/08 LangChain/LangGraph 框架线），每家一个文件夹，文件夹内包含中文文档：**《阅读指南》**（从哪读起、怎么跑、术语表）与**《架构拆解》**（架构图、主循环、关键机制、端到端时序、精读文件索引），07/08 为《源码解析与学习路线》。所有结论都标注 `文件:行号`，写文档前对关键行做过逐一核对。

## 工作区总览（四象限）

> 2026-09-28 收尾（⑬ 中文化收尾）时按「源码仓 / 手册类 / 备考·求职类 / 项目类」四象限重组；每行给一句话定位与入口链接，逐册详解见本文下方对应章节。每个目录的入口 `README.md` 提供一句话定位与互补关系。

### Ⅰ. 源码仓（逐行拆解线）

| 文件夹 | Agent / 框架 | 一句话定位 | star | 文档 |
|---|---|---|---|---|
| `01-claude-code/` | **Claude Code**（Anthropic） | 极简内核 coding agent 的鼻祖与标杆；官方核心未开源，本文件夹用"前身完整源码 + 官方仓库 + 两份社区逆向分析"组合还原 | 14.8 万（官方仓库） | [阅读指南](01-claude-code/阅读指南.md) · [架构拆解](01-claude-code/架构拆解.md) · [源码解析与学习路线](01-claude-code/源码解析与学习路线.md) · [中文导读](01-claude-code/anon-kode/README-cn.md) |
| `02-codex/` | **OpenAI Codex**（2026 版） | 官方开源的 Rust 巨型工程：app-server 守护进程 + 多前端 + 审批/沙箱双轴 + 多智能体 | 12.6 万 | [阅读指南](02-codex/阅读指南.md) · [架构拆解](02-codex/架构拆解.md) · [10 课学习课程](02-codex/analysis_codex/README.md) · [中文导读](02-codex/codex/README-cn.md) |
| `03-deepseek-harness/` | **DeepSeek Harness（dsh）** | 官方"一切皆插件"agent harness：没有特权内核，连 agent loop 都是可替换插件，一套内核装配出 Web/桌面/SDK/ACP 多形态 | 23.3 万 | [阅读指南](03-deepseek-harness/阅读指南.md) · [架构拆解](03-deepseek-harness/架构拆解.md) · [10 课学习课程](03-deepseek-harness/analysis_deepseek_harness/README.md) · [中文导读](03-deepseek-harness/deepseek-harness/README-cn.md) |
| `04-zcode/` | **ZCode**（Z.ai） | "多形态产品里长出来的 agent"：三层显式循环 + 事件溯源 SQLite + ZCode Protocol V4 宿主协议；`alwaysAsk` 不可抹除、把 CLI 手册编译成权限知识库、独有的 dynamic-workflow（模型写 TS → 静态分析 → vm realm 执行） | 6,140（新开源） | [阅读指南](04-zcode/阅读指南.md) · [架构拆解](04-zcode/架构拆解.md) · [10 课学习课程](04-zcode/analysis_zcode/README.md) |
| `05-openclaw/` | **OpenClaw** 🦞 | **不是 coding CLI，而是多渠道个人助理网关**：一台常开机器 + 27 类通讯渠道 + 配对设备；为"没有人类在旁边看着"多出 sessionKey 路由、双层 lane 串行化、写者围栏、DM 配对码、设备签名配对、六条限流 | 39.0 万 | [阅读指南](05-openclaw/阅读指南.md) · [架构拆解](05-openclaw/架构拆解.md) · [10 课学习课程](05-openclaw/analysis_openclaw/README.md) |
| `06-opencode/` | **OpenCode** | **HTTP-first 的多前端 coding agent**：Effect 写成的 agent server 默认跑在同进程 Bun Worker 线程（`fetch` 被桥成进程内直调），TUI/Web/Electron/VS Code/ACP/GitHub Action 都只是同一套 HttpApi 的客户端 | 20.9 万 | [阅读指南](06-opencode/阅读指南.md) · [架构拆解](06-opencode/架构拆解.md) · [10 课学习课程](06-opencode/analysis_opencode/README.md) |
| `07-langchain/` | **LangChain** | 六家之外的框架线：LCEL 组合语义（`a \| b`）、RunnableConfig 与回调树、ChatModel 四层调用链、v1 `create_agent` 编译成 LangGraph 图 | 14.7 万 | [源码解析与学习路线](07-langchain/源码解析与学习路线.md) · [中文导读](07-langchain/langchain/README-cn.md) · [10 课学习课程](07-langchain/analysis_langchain/README.md) |
| `08-langgraph/` | **LangGraph** | 图引擎线：StateGraph 与 reducer 合并语义、BSP 超步主循环、每拍 checkpoint 与时间旅行、interrupt 人在环 | 4.2 万 | [源码解析与学习路线](08-langgraph/源码解析与学习路线.md) · [10 课学习课程](08-langgraph/analysis_langgraph/README.md) · [中文导读](08-langgraph/langgraph/README-cn.md) |

> 八家源码仓的中文导读注释均在各自的本地分支 `study-cn-comments`（04/05/06 为既有，01/02/03/07/08 为 2026-09-28 收尾新增，Python 仓行内注释用 `# [注]`），入口见各仓 `README-cn.md`，详见下方「维护」节。

### Ⅱ. 手册类（专题横评线，13 册 + FDE 双册）

| 目录 | 一句话定位 | 入口 |
|---|---|---|
| `mcp-handbook/` | MCP 协议与 server 搭建：规范两代对照 · 最小实战 · 十家企业横评 · 接入/部署/安全 | [README](mcp-handbook/README.md) |
| `skill-handbook/` | Agent Skill 技能包：格式规范 · 五范例拆解 · 企业精读 · 安装触发机制 · 迭代方法论 | [README](skill-handbook/README.md) |
| `rag-handbook/` | RAG 检索增强：双管线 · 切分与混合检索 · 十家横评 · 评测迭代 · GraphRAG/Agentic | [README](rag-handbook/README.md) |
| `prompt-handbook/` | 提示词工程：四层分层 · 官方技法与八区块模板 · 六家生产提示词拆解 · 缓存边界 | [README](prompt-handbook/README.md) |
| `python-handbook/` | Python 大模型应用开发：工程基座 · SDK/框架横评 · RAG/推理/服务/评测 · MCP 接入；附力扣 Hot 100 全解题解集 | [README](python-handbook/README.md) |
| `eval-handbook/` | Agent 评测与质量工程：三层谱系 · 公共基准实抓 · LLM-as-judge · 轨迹评测 · 最小评测四文件 | [README](eval-handbook/README.md) |
| `context-handbook/` | Context 与记忆系统：上下文经济学 · 三层预算与压缩 · 子代理隔离 · 十家记忆框架横评 | [README](context-handbook/README.md) |
| `multiagent-handbook/` | Multi-Agent 协同：范式六谱系 · 通信交接 · 九家框架横评 · A2A · MAST 失败治理 | [README](multiagent-handbook/README.md) |
| `security-handbook/` | AI 应用安全：威胁模型 · 注入分层防御 · 六家权限沙箱对照 · Guardrails · 红队评测 · 案例库 | [README](security-handbook/README.md) |
| `workflow-handbook/` | Agent 工作流编排：模式谱系 · 12 家引擎实抓 · 状态数据流 · 调试可观测 · 最小编排器 | [README](workflow-handbook/README.md) |
| `tuning-handbook/` | Agent 调优：度量驱动闭环 · 六类失败分诊 · 五层调优 · 成本延迟工程 · 最小实验框架 | [README](tuning-handbook/README.md) |
| `deploy-handbook/` | AI 应用部署与运维：形态谱系 · 推理服务化 · 网关治理 · 可观测 · 发布回滚 · 最小演练 | [README](deploy-handbook/README.md) |
| `cloud-handbook/` | 云厂商 AI 平台对比：八家画像 · 横向总表 · 选型决策树 · 迁移锁定 · 中国区特辑 | [README](cloud-handbook/README.md) |
| `fde-handbook/` | FDE 转行手册（十章）+ 实战工具箱（十一章）+ 腾讯 ADP-FDE 认证课程 19 节讲义 + 两个数据 xlsx | [README](fde-handbook/README.md) |

### Ⅲ. 备考·求职类（4 册）

| 目录 | 一句话定位 | 入口 |
|---|---|---|
| `interview-handbook/` | AI 应用岗面试题库 128 题（四件套格式 · 7 个主题分册 · 14 天冲刺路线 · 全量索引） | [README](interview-handbook/README.md) |
| `mianjing-handbook/` | 真实面经精评 13 场（问题链实录 · 逐题精评 · 考点频率 Top20 · 面试官视角 · mock 流程） | [README](mianjing-handbook/README.md) |
| `kaogong-handbook/` | 考公备考全链路（行测五模块 · 申论五题型 · 面试三形式 · 90 天计划双版） | [README](kaogong-handbook/README.md) |
| `cet4-handbook/` | 英语四级备考全链路（考情当日实抓 · 49 天冲刺/90 天标准双轨计划 · 词汇 · 听力 · 阅读 · 写译 · 真题三遍用法） | [README](cet4-handbook/README.md) |

### Ⅳ. 项目类（真机复现 + 可运行应用）

| 目录 | 一句话定位 | 入口 |
|---|---|---|
| `project-study/` | 三个开源 Agent 项目真机复现与设计对照：camel（blackboard）· crewAI（supervisor）· browser-use（环境特化） | [README](project-study/README.md) |
| `projects/interview-prep-app/` | 面试备战站（可运行本地 Web 应用）：把题库 128 题变成可检索/自测/错题本/进度的刷题站（Python 后端 + 原生前端，无构建链） | [README](projects/interview-prep-app/README.md) |

> star 数与语言/许可证取自 GitHub API，01-06 为 2026-09-22、07/08 为 2026-09-27。OpenClaw 的 API 返回 `NOASSERTION`，但仓库 `LICENSE` 是 MIT（已核对文件）。

## 各文件夹内容明细

### `01-claude-code/`
| 子目录 | 说明 |
|---|---|
| `anon-kode/` | Claude Code 前身 anon-kode 完整 TypeScript 源码（v0.0.54）。原仓库 `dnakov/anon-kode` 已被 Anthropic 于 2025-04-28 DMCA 下架，本副本取自社区保存 fork `ripgrim/anon-kode`，**仅供学习研究** |
| `claude-code-official/` | Anthropic 官方仓库（文档/插件/examples/devcontainer；非开源代码，核心以 minified npm 包分发） |
| `analysis_claude_code/` | shareAI-lab《Learn Claude Code》17 课教材（每课 Python 最小实现 + 中文讲解），另有 `agents/` 可运行模块 |
| `claude-code-reverse/` | Yuyz0112 动态逆向：抓取真实 API 请求，还原系统提示词/工具定义，附 compress/sub-agent 等场景日志 |

### `02-codex/`
| 子目录 | 说明 |
|---|---|
| `codex/` | `openai/codex` 完整仓库（`codex-rs/` 100+ crate 的 Rust workspace；`sdk/` TS+Python；`docs/`） |
| `analysis_codex/` | 自建《Learn OpenAI Codex》10 课教材（体例同 [analysis_deepseek_harness](03-deepseek-harness/analysis_deepseek_harness/README.md)：每课中文讲解 + 注释版可运行代码 + SVG 图解 + 真实源码精读锚点）：回合循环 → rollout 录制 → 工具总闸 orchestrator → 审批×沙箱双轴 → 拒绝后升级重试 → MCP 双向 → apply_patch 补丁事务 → 多智能体 thread → app-server 服务化 → 多前端装配收官。Codex 本体是 Rust 而本机无 cargo，沿用 Claude Code 教材"产品语言与教学语言分离"的先例：**mini 实现全部用 Python 纯标准库**（asyncio/dataclasses，零 pip 依赖，注释里标注 Rust 概念对应物）；`run.bat` / `run.sh` 一键全跑，入口 [README](02-codex/analysis_codex/README.md) |

### `03-deepseek-harness/`
| 子目录 | 说明 |
|---|---|
| `deepseek-harness/` | `deepseek-ai/deepseek-harness` 完整仓库（49 个包域、150+ 包的 pnpm monorepo；`docs/` 双语文档质量极高） |
| `analysis_deepseek_harness/` | 自建《Learn DeepSeek Harness》10 课教材（体例对标 [analysis_claude_code](01-claude-code/analysis_claude_code/)：每课中文讲解 + 注释版零依赖 Node 可运行代码 + SVG 图解 + 真实源码精读锚点；s01 插件内核 → s10 profile 装配，入口 [README](03-deepseek-harness/analysis_deepseek_harness/README.md)，`run.bat` 一键全跑；s06 可选接真实 DeepSeek API） |

### `04-zcode/`（122 MB，6973 文件）
| 子目录 | 说明 |
|---|---|
| `ZCode/` | `zai-org/ZCode` v3.14.0，Apache-2.0。agent 内核在**内嵌的第二 workspace** `apps/zcode-cli/`（`core`/`contracts`/`adapters`/`bootstrap`/`cli`/`tui`/`dynamic-workflow*` 共 16 子包），共享产品层在 `packages/`（`ui`/`services`/`desktop`/`shared`/`client`/`rpc`/`server`/`web`/`provider*` 共 14 包）。注意：`harness/` 只是 SSH 联调容器、`third-party/` 只是合规材料、`DESIGN.md` 是 UI 规范、`CONTEXT.md` 是插件商店词汇表 |

| `analysis_zcode/` | 自建《Learn ZCode》10 课教材（体例同 [analysis_deepseek_harness](03-deepseek-harness/analysis_deepseek_harness/README.md)：每课中文讲解 + 注释版零依赖 Node 可运行代码 + SVG 图解 + 真实源码精读锚点）：三层循环 → 事件溯源 SQLite → 工具双轨 schema → 权限格子 → 上下文预算 → hooks 信任 → 插件进程 → dynamic-workflow → provider 目录 → 多形态收官；`run.bat` 一键全跑 |

### `05-openclaw/`（883 MB，48321 文件）
| 子目录 | 说明 |
|---|---|
| `openclaw/` | `openclaw/openclaw` v2026.9.5，MIT（© 2026 OpenClaw Foundation）。pnpm workspace 只有 5 个成员（`.`、`ui`、`packages/*`、`extensions/*`、`examples/*`）；`src/` 属根包本体（`gateway` 1880 文件、`agents` 1807 文件），`extensions/` 171 个插件（渠道/provider/能力），`skills/` 52 + `custodian-skills/` 4，`packages/` 22 个可复用内核包，`crates/` 是设备节点宿主的 Rust 实现（`openclaw-node`，`forbid(unsafe_code)`），`apps/` 是 macOS/iOS/Android/Linux/唤醒词守护进程，`docs/` 约 1325 篇（无中文） |

| `analysis_openclaw/` | 自建《Learn OpenClaw》10 课教材（同上体例）：渠道网关 → sessionKey 路由 → 双层 lane 与写者围栏 → 八层工具收窄 → 三道安全闸 → 无人值守输入源 → 记忆与 compaction → skills 七档优先级 → 17 钩子位 → 设备配对与六条限流收官 |

### `06-opencode/`（219 MB，6632 文件）
| 子目录 | 说明 |
|---|---|
| `opencode/` | `anomalyco/opencode` v1.18.32，MIT，纯 TypeScript（无 Go）。bun workspace：`packages/opencode`（63k 行，内核+server+CLI）、`core`（68k 行，Drizzle + **V2 session 内核** + models-dev）、`llm`、`tui`（31.9k 行，SolidJS + `@opentui/core`）、`app`/`ui`/`session-ui`/`desktop`、`plugin`/`protocol`/`schema`/`client`/`sdk`、`codemode`；另有 `console/*`（SaaS 站点）、`stats/*`、`specs/`（V2 权威规范）、`CONTEXT.md`（32 KB 术语表）。⚠️ **V1/V2 双内核并存**，生产主路径仍是 V1 |

| `analysis_opencode/` | 自建《Learn OpenCode》10 课教材（同上体例）：runLoop 三态 → 会话存储与 durable 收件箱 → 工具三层来源与裁剪 → 权限 findLast 双通配 → 模型特化 apply_patch → 子代理 → 21 个钩子 → 提示词家族 → HTTP-first 边界 → 收官 |

## 六家横向对比（读前速览）

| 维度 | Claude Code（含 anon-kode 溯源） | OpenAI Codex（2026） | DeepSeek Harness | **ZCode** | **OpenClaw** | **OpenCode** |
|---|---|---|---|---|---|---|
| 语言/栈 | TypeScript（ink TUI） | Rust（app-server + 多前端） | TypeScript（Cordis + pnpm monorepo） | TypeScript（pnpm + Electron/Hono/自研 opentui-react） | TypeScript + Rust 节点宿主（pnpm） | TypeScript + Effect（bun workspace） |
| 开源程度 | 核心闭源（minified），本区用前身源码+逆向还原 | 完全开源（Apache-2.0） | 完全开源（MIT，developer preview） | 完全开源（Apache-2.0，**v3.14.0 刚开源**） | 完全开源（MIT） | 完全开源（MIT） |
| 产品定位 | 终端 coding agent | coding agent + 多前端 | 可组装 agent 平台 | coding agent + Desktop/Web/手机远控 | **多渠道常驻个人助理网关** | HTTP-first coding agent + SaaS |
| 内核形态 | 单循环 `query()` 递归 | `run_turn` 回合循环 + step | Cordis 插件树上的 agent-loop 驱动器 | **三层**：turn → provider-turn 循环 → model step | Gateway run 生命周期 + **双层 lane 串行化** | `runLoop` while(true) + processor 三态 |
| 工具系统 | zod schema 注册表 + MCP 同构 | ToolRegistry + 编排器（审批→沙箱→执行→升级重试） | `ctx.tools` 作用域注册表 + 三段式流水线 | ~45 内置，**双轨 schema**（zod 校验 + 手写 JSON Schema 下发），边流式边执行 | **~60 内置 + 六段收窄流水线** + 客户端能力裁剪 | 17 内置（+三层来源），按模型动态裁剪（gpt 系换 `apply_patch`） |
| 权限/沙箱 | 白名单/精确/前缀三级授权，无内核级沙箱 | 内核级双轴：AskForApproval × SandboxPolicy（Seatbelt/Landlock/Windows） | sandbox-policy + permission-presets + Landlock/Windows ACL + e2b | **无 OS 沙箱**；5 模式（含未实现 `auto`）+ **`alwaysAsk` 压过 yolo** + 命令知识库 | 5 套并存（dmPolicy/两层白名单/设备签名/exec approvals/**6 种沙箱后端但默认关闭**） | `{permission,pattern,action}` + `findLast` 双通配；**无 OS 沙箱** |
| 上下文 | 手动/自动 compact | 多形态压缩 + 上下文工具化 | 会话日志为真源 + 剪枝后摘要 + spill 外溢 | **三层预算**：microcompact → auto compact → reactive + **rapid-refill 熔断**；显式 cache 锚点 | 6 个 workspace 注入文件 + 预算；**只有 compaction 能改写历史**；CJK 计入估算 | 9+ per-model 提示词家族；tail 可切 turn；独立 prune；**token 估算是字符/4** |
| 子代理 | Task 工具递归 query | multi_agents_v2 + agent-roles | subagent 提供方（可委派给 Claude Code / Codex！）+ Agent Teams | `Agent`/`Task` + 前后台 runner + **dynamic workflow（模型写 TS → taint 分析 → vm realm）** | `sessions_spawn` + swarm + ACP 接入外部 harness；**默认拿不到 session/message 工具** | `task` 递归同一 runLoop；子代理**只继承父 deny** |
| 状态持久化 | 会话文件 | 会话 + rollout | 仅追加会话事件日志 + 版本化迁移 | **SQLite 31 表 + 事件溯源** + fork/rewind/checkpoint + rollout 轨迹 | **一律 SQLite（Kysely + worker 线程）**，明令禁止新增 JSON/JSONL | SQLite + Drizzle（V2 有 `session_input` 收件箱）+ 独立 `--git-dir` 做 undo |
| 扩展 | MCP / hooks / plugins / skills | MCP 双向 + plugins + skills + code mode | MCP + hooks（兼容 CC/Codex 格式）+ 插件 + 技能 + Cordis 运行时扩展 | 7 hooks + **工作区 hook 信任状态机** + 插件独立进程 + skills + provider 目录驱动 | skills(7 档优先级)/plugins(171)/**17 钩子**/channels/nodes/canvas/语音唤醒 | 21 个插件 Hooks（含 `chat.messages.transform`）+ commands + skills + themes + LSP + ACP |
| 输入源 | 人在终端敲 | 人在终端/IDE | 人 + webhook + ACP | 人（TUI/Desktop/Web/手机） | **消息事件 + cron + webhook + 语音**（无人值守） | 人（TUI/Web/IDE/GitHub Action 评论） |
| 最佳学习点 | 用最少代码理解 agent loop 的本质 | 工程化与安全沙箱的工业化答案 | 插件化架构与"可组装平台"的系统设计 | **权限格子的细度**与"给 agent 读的仓库"如何制度化 | **"没有人类在旁边看着"所需的全套基础设施** | **HTTP-first 边界 + 上下文工程密度** |

## 建议学习路线

1. **先读 `01-claude-code/架构拆解.md`**（配合 `anon-kode/src/query.ts`）——用最小的真实实现建立 agent loop 心智模型。
2. **再读 `02-codex/架构拆解.md`**——看工业化 agent 如何解决权限、沙箱、上下文、多智能体。
3. **然后读 `06-opencode/架构拆解.md`**——同一件事（coding agent）在"客户端/服务端分离"这条路上的样子；它的权限求值与上下文工程密度最高，且**没有沙箱**，正好与 Codex 对照。
4. **再读 `04-zcode/架构拆解.md`**——三层循环怎么切、`alwaysAsk` 为什么压不过 deny、dynamic workflow 如何把"编排"从 prompt 变成可静态分析的程序。
5. **然后读 `03-deepseek-harness/架构拆解.md`**（配合官方 `docs/architecture.zh.md`）——看"一切皆插件"如何把 agent 做成可组装平台。
6. **最后读 `05-openclaw/架构拆解.md`**——把视角从"一个人一个仓库"换成"一个常驻网关 + N 个渠道 + M 台设备"，看并发、路由、配对、审批绑定、限流这些**在 CLI 形态下可以省掉的整套基础设施**。它的第 7、13 节也是六家里安全面最值得关注的一份。
7. 六份《阅读指南》里都有分阶段精读文件清单，可当打卡表；每份末尾的术语表建议在精读前先扫一遍，能省掉大量来回。

## 维护

- 所有仓库均为 shallow clone（`--depth 1`），可用 `git -C <仓库> pull --depth 1` 更新；文档中已记录各仓库 commit 快照。
- ⚠️ **学习注释分支**：八家仓库（`01-claude-code/anon-kode`、`02-codex/codex`、`03-deepseek-harness/deepseek-harness`、`04-zcode/ZCode`、`05-openclaw/openclaw`、`06-opencode/opencode`、`07-langchain/langchain`、`08-langgraph/langgraph`）里，内核关键文件的**中文导读注释**加在各自的本地分支 `study-cn-comments` 上（不属于上游代码，是本地手工添加；04/05/06 三家为既有，01/02/03/07/08 五家为 2026-09-28 收尾新增，各仓入口见 `README-cn.md`）：
  ```bash
  git -C 01-claude-code/anon-kode checkout study-cn-comments  # 带中文注释读代码（各家同名分支同体例）
  git -C 06-opencode/opencode checkout dev                    # 回到上游原样（OpenCode 默认分支是 dev，07/08 与其余各家是 main）
  git -C 02-codex/codex diff --stat main..study-cn-comments   # 看这个分支到底动了哪些文件
  ```
  注释只新增行、不改代码，所以两分支间可自由来回切换；要更新上游就先切回 `main`/`dev` 再 `pull`，之后用 `rebase` 或重新加注都行。所有学习注释都有可识别标记（文件头块以 `[中文导读` 起始、行内以 `// [注]` 起始，Python 仓为 `# [注]`），需要一把清掉时按这两个标记过滤即可。
- ⚠️ **文档行号一律指上游原始树**（`main` / OpenCode 的 `dev`）。学习注释分支在每个文件顶部插了 13-16 行文件头块，所以**同一符号在 `study-cn-comments` 上会整体下移**——这是注释造成的位移，不是文档过期。核对方法：`git -C <仓库> show main:<路径> | sed -n '1081p'`；跨分支跳转认符号名，不认行号。
- 文档结论均标注了来源文件路径，代码演进后如与文档不符，**以源码为准**。
- ⚠️ 本机 git 全局配置了 `http.proxy = http://127.0.0.1:7890`。若该代理未运行而直连可用，更新/克隆请加参数绕过（**不要改全局配置**）：
  ```bash
  git -c http.proxy= -c https.proxy= -C 06-opencode/opencode pull --depth 1
  ```
- 新增仓库时的目录约定：`NN-<小写名>/<仓库名>/` + 同级的《阅读指南.md》《架构拆解.md》。

## 还可以补进来的候选

本轮按"精选三家"落地（ZCode / OpenClaw / OpenCode）。以下同样是已开源、且与现有六家形成架构对照的候选（数据取自 2026-09-22 GitHub API）：

| 仓库 | star | 语言 | 为什么值得补 |
|---|---|---|---|
| `NousResearch/hermes-agent` | 24.8 万 | Python | "the agent that grows with you"——记忆/成长取向的 agent，Python 栈代表 |
| `earendil-works/pi` | 10.8 万 | TypeScript | agent 工具箱（统一 LLM API + agent loop + TUI + coding CLI），适合"自己造一个"的参照 |
| `bytedance/deer-flow` | 8.3 万 | Python | 长时程 SuperAgent harness：sandbox + memory + skill + subagent + message gateway |
| `OpenHands/OpenHands` | 8.9 万 | TS/Python | AI 驱动开发平台，事件流 + 沙箱运行时是另一条技术路线 |
| `shareAI-lab/learn-claude-code` | 7.7 万 | Python | "Bash is all you need"：0→1 的 nano agent harness，与 `01` 里的教材同源 |
| `xai-org/grok-build` | 2.7 万 | Rust | 全屏、鼠标交互、可扩展的 Rust coding harness + TUI，与 Codex 形成 Rust 双样本 |
| `aaif-goose/goose` | 5.5 万 | Rust | 超越代码补全的通用 extensible agent |
| `charmbracelet/crush` | 2.8 万 | Go | **唯一的 Go 实现**，补上语言维度 |

## 职业方向：FDE 转行手册（`fde-handbook/`）

与上面的源码学习并行的另一条线：转型 FDE（Forward Deployed Engineer，前线部署工程师）的调研与手册，2026-09-26 完成。

| 文件 | 说明 |
|---|---|
| [fde-handbook/FDE转行手册.md](fde-handbook/FDE转行手册.md) | 主手册（十章）：认知 → 真实工作状态 → 能力模型 → agent 学习成果映射 → 转行路线图 → GitHub/视频资源 → 求职实战 → 避坑 → 统计与来源 |
| [fde-handbook/FDE实战工具箱.md](fde-handbook/FDE实战工具箱.md) | 第二册·上岗实战（十一章）：交付全景与角色边界 → 需求诊断 → 方案设计（四模式选型）→ POC/Demo → 交付物模板六件套 → 客户沟通与变更请求 → 成本报价 → 现场排障故障树 → 企业案例（Palantir/Latent.Space 当日实抓）与工具链 → FAQ 与上手清单 |
| [fde-handbook/data/github-repos.xlsx](fde-handbook/data/github-repos.xlsx) | 49 个 GitHub 仓库（核心 36 个，合计 97,343 stars）+ 统计摘要 |
| [fde-handbook/data/videos.xlsx](fde-handbook/data/videos.xlsx) | B站 115 条强相关视频 + YouTube 15 条 + 播客图文 18 条 + 统计摘要（含采集方法与局限） |
| [fde-handbook/tencent-adp-fde-course/](fde-handbook/tencent-adp-fde-course/README.md) | 腾讯云 ADP-FDE 认证免费课程整理讲义：4 章 19 节全文（约 13 万字）+ 266 张配图，浏览器自动化提取（2026-09-26，个人学习用） |

数据基准日 2026-09-26；手册第四章把本工作区六家 agent 源码学习成果映射到了 FDE 能力模型，建议对照阅读。《FDE实战工具箱》信息基准日 2026-09-28（企业案例与 JD 为当日实抓），与转行手册互补：转行手册讲"怎么进这行"，工具箱讲"上岗后怎么干活"。

## 专题：MCP 搭建文档（`mcp-handbook/`）

与源码学习并行的协议专题：MCP（Model Context Protocol）搭建手册，2026-09-27 完成。

| 文件 | 说明 |
|---|---|
| [mcp-handbook/MCP搭建文档.md](mcp-handbook/MCP搭建文档.md) | 单册十章：架构三角色 → 协议格式规范（2026-07-28 现行版 vs legacy 两代对照）→ 最小 server 实战与工具设计八条 → 十家官方企业 MCP 对比 + 三个精读（github-mcp-server / playwright-mcp / awslabs·supabase·notion）→ 四大客户端接入配置 → 部署三形态 → 版本迭代/别名兼容/Registry/测试 → 安全清单 → 常见坑 FAQ |

信息基准日 2026-09-27（协议规范 2026-07-28 版 + 企业仓库当日实抓）；读源码时若遇到六家 agent 的 MCP 接入实现，可与本文 §1.2/§4 对照。

## 专题：Skill 搭建文档（`skill-handbook/`）

与 MCP 手册并行的能力格式专题：Agent Skill（技能包）搭建手册，2026-09-27 完成。

| 文件 | 说明 |
|---|---|
| [skill-handbook/Skill搭建文档.md](skill-handbook/Skill搭建文档.md) | 单册七章：概念定位与生态位（vs MCP/subagent/斜杠命令）→ agentskills.io 格式规范逐条（6 字段 frontmatter / 三级渐进式披露 / 发现路径与遮蔽）→ 五个真实范例构成拆解（骨架 / 纯提示词 / 流程纪律 / 路由器 / 生产级 50 文件）→ 三家 GitHub 企业范例精读（anthropics/skills 17.9 万 star、obra/superpowers 29.2 万 star、Notion）→ 安装/触发/执行机制 → 迭代方法论（五步循环 + 改进四原则 + 反模式清单）→ 30 分钟上手清单与最小示例 |

信息基准日 2026-09-27（agentskills.io 现行规范 + 企业仓库当日实抓）；本文与 MCP 手册互补——MCP 管"连接外部系统"，Skill 管"教流程与规范"；读 04-zcode 源码里的 skill 发现/加载实现时，可与本文 §1.4/§2.6 对照。

## 专题：RAG 搭建文档（`rag-handbook/`）

与 MCP/Skill 手册并列的知识系统专题：RAG（Retrieval-Augmented Generation，检索增强生成）搭建手册，2026-09-27 完成。

| 文件 | 说明 |
|---|---|
| [rag-handbook/RAG搭建文档.md](rag-handbook/RAG搭建文档.md) | 单册九章：架构与双管线 → 格式规范（摄入/切分/元数据/嵌入/检索接口/引用六项工程约定）→ 最小可用管线与生产化三步 → 十家开源企业 RAG 横向对比 + 四个精读（onyx / ragflow / kotaemon+FastGPT）→ 接入与部署 → 评测迭代（RAGAS/DeepEval/反馈闭环/文档级权限）→ 拓展（GraphRAG/Agentic RAG）→ 常见坑 FAQ |

信息基准日 2026-09-27（十家企业仓库当日实抓；切分/检索数字取自 Anthropic Contextual Retrieval 与 Pinecone/Weaviate 官方指南）。与已有内容的三个接口：企业知识库调优纪律对照 `fde-handbook` 的腾讯 ADP 课程 4.3 节；把知识库暴露给 agent 用的 MCP 协议对照 `mcp-handbook`；agent 式检索（grep 迭代）与索引式 RAG 的对比见本文 §1.4/§7.2，可结合六家《架构拆解》的主循环章节阅读。

## 专题：提示词搭建文档（`prompt-handbook/`）

与 MCP/Skill/RAG 手册并列的行为层专题：提示词（Prompt）搭建手册，2026-09-27 完成。

| 文件 | 说明 |
|---|---|
| [prompt-handbook/提示词搭建文档.md](prompt-handbook/提示词搭建文档.md) | 单册八章：概念分层（四层提示词 + 六家 agent 提示词载体索引）→ 格式规范（Anthropic 八技法 + OpenAI 六策略 + 从真实范例归纳的八区块模板）→ 五个真实范例拆解（Claude Code 逆向 12 文件 / Codex 按模型 5 份 prompt.md / OpenCode 15 文件提示词家族 / OpenClaw 1340 行渲染器）→ GitHub 企业范例收集（x1xhlol 14.4 万 star 收录库、官方教学双库等六库当日实抓）→ 使用机制（运行时组装/层级裁决/缓存边界）→ 迭代方法论（评测先行 + 五组化石证据 + promptfoo/DSPy）→ 30 分钟上手清单与八区块最小示例 → 常见坑 FAQ |

信息基准日 2026-09-27（两大官方指南现行版 + 企业仓库当日实抓）；一手样本是本工作区六家 agent 的生产提示词（三家开源原文 + Claude Code 逆向，全部可本机打开对照）。与已有内容的四个接口：Skill 正文即按需加载的提示词（skill-handbook §1.4）；工具定义占提示词预算且策略由提示词约定（mcp-handbook、六家《架构拆解》工具行）；检索结果作为上下文注入提示词（rag-handbook）；提示词注入的真正防线在权限与沙箱（mcp-handbook 安全章节、六家《架构拆解》权限行）。

## 专题：LangChain / LangGraph 学习文档（`07-langchain/` `08-langgraph/`）

六家 agent 之外的框架线：官方仓库本机源码（Python）+ 源码级学习文档，参照 01-claude-code《源码解析与学习路线》规格（架构图 + 源码逐段精读 + 行号 + 六阶段路线 + 自测题），2026-09-27 完成。

| 文件夹 | 仓库 | star（2026-09-27 实测） | 文档 |
|---|---|---|---|
| `07-langchain/langchain/` | `langchain-ai/langchain`（commit 80b7409） | 14.7 万 | [源码解析与学习路线](07-langchain/源码解析与学习路线.md) · [10 课学习课程](07-langchain/analysis_langchain/README.md) |
| `08-langgraph/langgraph/` | `langchain-ai/langgraph`（commit 7daa3ab） | 4.2 万 | [源码解析与学习路线](08-langgraph/源码解析与学习路线.md) · [10 课学习课程](08-langgraph/analysis_langgraph/README.md) |

要点：LangChain 文档覆盖 LCEL（`__or__`/RunnableSequence/线程池 batch）、RunnableConfig 与回调树、ChatModel 四层调用链、消息与工具 schema 生成、v1 `create_agent` 如何编译成 LangGraph 图；LangGraph 文档覆盖 StateGraph/三种边、9 种通道与 reducer 合并语义、BSP 超步主循环（tick→runner→after_tick）、每拍 checkpoint 与时间旅行、interrupt 人在环、create_react_agent 与 ToolNode。两份文档各带 12 道自测题（附行号答案）与 GitHub 高分学习资源实测表（17+ 条，标注中文友好性与三个"曾用 langchain 现已移除"的陷阱项目）；LangGraph 文档末节与六家 agent 做了执行模型/持久化/人在环/并发的对照。

信息基准日 2026-09-27。重要前提：仓库快照是 LangChain 1.x——`libs/langchain` 实为 `langchain-classic`（0.x 兼容层），主包在 `libs/langchain_v1`（包名 `langchain`），读网上 0.x 教程时注意 API 已换代。学习顺序建议：07 阶段 0-4 → 08 阶段 0-4（框架语义）→ 两份的阶段 5（项目对照）。

## 专题：Python 手册（`python-handbook/`）

与 MCP/Skill/RAG/提示词手册并列的语言栈专题，2026-09-27 完成两份：《Python 大模型应用开发手册》与《力扣 Hot 100 全解题解集》。

| 文件 | 说明 |
|---|---|
| [python-handbook/Python大模型应用开发手册.md](python-handbook/Python大模型应用开发手册.md) | 单册十章：生态位（对照 01-08 语言分布，Python 的四类用法：脚本/服务/数据/模型）→ 工程基座（uv/ruff/pytest/Pydantic，"类型即协议"不变量）→ SDK 横评（openai/anthropic/google-genai/litellm，流式·工具调用·结构化输出·异步最小示例）→ 编排框架横评（LangChain/LangGraph/LlamaIndex/DSPy/PydanticAI + 选型决策树 + "六家 agent 全自研"对照）→ RAG 工具链（sentence-transformers/faiss/chromadb/rank_bm25/bge-reranker，40 行混合检索）→ 本地推理（transformers/vLLM/Ollama/llama-cpp-python）→ 服务与界面（FastAPI+SSE/Gradio/Streamlit）→ 评测与可观测（ragas/deepeval/langfuse 三件套分工）→ 协议接入（MCP Python SDK/openai-agents/20 行自研循环）→ 企业范例七家横向对比 + 三家精读（hermes-agent / deer-flow 2.0 / OpenHands）+ 常见坑 FAQ + 30 天上手清单 |
| [python-handbook/leetcode-hot100/README.md](python-handbook/leetcode-hot100/README.md) | 力扣 Hot 100 全解题解集导航：12 个题解文件覆盖 17 个官方专题全部 100 题（明细外链可点）、难度分布（简单 20 / 中等 68 / 困难 12）、14 天刷题路线、四件套使用方法 |

信息基准日 2026-09-27（Python 当前稳定版 3.14.7 取自 python.org；32 个库的 PyPI 版本与发布日、30+ 仓库 star 与维护状态当日经 PyPI JSON API 与 GitHub API 实抓；每章配最小可运行 Python 代码，讲机制与不变量）。与已有内容的接口：RAG 工具链逐节对接 [rag-handbook](rag-handbook/RAG搭建文档.md) 的切分/元数据/混合检索/评测规范；MCP Python SDK 与 [mcp-handbook](mcp-handbook/MCP搭建文档.md) §2/§3 互补（那边协议、这边代码）；DSPy 是 [prompt-handbook](prompt-handbook/提示词搭建文档.md) "评测先行"方法论的代码化；deer-flow 的 LangGraph 生产用法与 [08-langgraph](08-langgraph/源码解析与学习路线.md) 的引擎语义互证；hermes-agent 与 [05-openclaw](05-openclaw/架构拆解.md) 同赛道（自带 `hermes claw migrate` 迁移命令）；FDE 视角的四类用法含义见 [fde-handbook](fde-handbook/FDE转行手册.md)。

题解集部分：按官方专题分组的 12 个题解文件（Python 3），每题统一四件套——题意速览 → 思路讲解（从暴力演进到最优、点明不变量（Invariant）与套路迁移）→ 中文注释代码 → 复杂度 · 易错点 · 面试追问；英文术语首次出现标中文。当日从 leetcode.cn GraphQL API 实抓 `top-100-liked` 题单核对 100 题题号/题名/难度/分组（简单 20 / 中等 68 / 困难 12）。目录内各册总入口见 [python-handbook/README.md](python-handbook/README.md)。

## 专题：Agent 评测与质量工程手册（`eval-handbook/`）

与 MCP/Skill/RAG/提示词/Python 手册并列的质量工程专题：Agent 评测（Evals）搭建手册，2026-09-27 完成。

| 文件 | 说明 |
|---|---|
| [eval-handbook/Agent评测与质量工程手册.md](eval-handbook/Agent评测与质量工程手册.md) | 单册十章：为什么评测是落地第一问（对照 ADP 课程"五堵墙"与 FDE 交付验收场景）→ 评测谱系（单元/轨迹/端到端三层 × 离线/在线/灰度回放三时机 × 判据优先级）→ 公共基准当日实抓总表与怎么选（SWE-bench 家族 / τ²·τ³-bench / GAIA / WebArena / OSWorld / AgentBench / BFCL V4 / Terminal-Bench，含数据污染与 τ² v1.0.1 改分不可比案例）→ 自建评测集（生产日志四信号、任务分类学、可验证 reward 优先、版本指纹管理）→ LLM-as-judge（协议五件套、位置/长度/自我偏好偏差与交换仲裁、人工标注校准、多 judge 仲裁）→ 轨迹评测（工具调用正确性、pass^k、失败归因五分类、"Verify the world"）→ 可观测（OTel GenAI 约定独立成仓现状、Langfuse/Phoenix/LangSmith 横评、trace→dataset→评测闭环）→ 成本与延迟工程（缓存价差、模型路由、预算熔断）→ 企业范例横评与三家精读（openai/evals→simple-evals、Langfuse、Phoenix）+ 六家 agent 源码评测/自检机制对照 → 最小评测四文件（dataset→agent→judge→报告，已本机验证）+ 12 条坑 FAQ + 上手清单 |

信息基准日 2026-09-27（22 个基准/工具仓库的 star、版本、维护状态当日经 GitHub API 与官网实抓；每章配最小可运行 Python 代码——verify/dataset/judge/trajectory/otel_demo/cost/mini-eval 七组代码均已本机跑通验证）。与已有内容的接口：RAG 评测迭代（golden dataset/RAGAS/坏例四信号）的原始版本见 [rag-handbook §6](rag-handbook/RAG搭建文档.md)，本手册 §4/§5 是它向 agent 场景的推广；平台化调试-评测-回归的课程版见 [fde-handbook/tencent-adp-fde-course/lessons/4.1](fde-handbook/tencent-adp-fde-course/lessons/4.1_智能体调试与评测基础.md)（"五堵墙"原图在 1.3 节）；ragas/deepeval/langfuse 三件套库用法见 [python-handbook §8](python-handbook/Python大模型应用开发手册.md)；"评测先行"的提示词迭代见 [prompt-handbook](prompt-handbook/提示词搭建文档.md) §6.1；§9.4 对照 01-06 六家源码的评测资产梯度（openclaw qa-lab 产品级 → deepseek-harness 方法论 → codex/opencode 仅性能 bench → anon-kode 空白），可与六家《架构拆解》配合阅读；Evals 作为 FDE 硬技能"demo 者与能上线者的分水岭"的论证见 [fde-handbook](fde-handbook/FDE转行手册.md) 第三章。

## 专题：Context 与记忆系统手册（`context-handbook/`）

与 MCP/Skill/RAG/提示词/Python/评测手册并列的上下文层专题：Context 与记忆系统手册，2026-09-27 完成。

| 文件 | 说明 |
|---|---|
| [context-handbook/Context与记忆系统手册.md](context-handbook/Context与记忆系统手册.md) | 单册九章：为什么上下文工程是 agent 时代的新学科（注意力预算/context rot/lost-in-the-middle 位置偏差的上下文经济学）→ 三层预算与压缩（microcompact → auto compact → reactive 熔断、剪枝先于摘要、"日志为真源，压缩只改投影"不变量、spill 外溢、cache 锚点，配 **01-06 六家机制横向对照表**）→ 子代理上下文隔离与 handoff 摘要协议（权限继承三派：只继承 deny / 默认摘走高危工具 / 项目级定义强制降权；"回传结论不回传过程"）→ 长期记忆体系（语义/情景/程序/**前瞻**四类型学、OpenClaw 五层 tier 与 dreaming 整理、写入三问"何时存/存什么/冲突消解"、双 lane 召回、遗忘与衰减）→ **主流记忆框架横评当日实抓十家**（mem0 66.1k、Graphiti 31.2k、Letta 主仓已转壳现役 letta-code、MemOS 11.6k、cognee、supermemory、memU、basic-memory、langmem、memobase 低维护警示；四流派分野 + 选型决策树）→ 记忆评测与安全（LongMemEval/PrefEval/TriggerBench/HaluMem 四维评测、OWASP ASI06 记忆投毒、provenance/tier 隔离/taint 传播的结构防御、GDPR 遗忘合规）→ 企业精读三家（mem0 两阶段→单遍 ADD-only 的算法换代、Graphiti bi-temporal、Letta 转型教训）+ **05-openclaw 内建记忆对照小节** + **rag-handbook「检索 vs 记忆」边界小节** → 最小 agent（工作记忆 + 长期记忆，Python 3 纯标准库已本机验证，trace=microcompact+compact 实跑输出）+ 14 条坑 FAQ + 上手清单 |

信息基准日 2026-09-27（10 个记忆框架仓库的 star、版本、维护状态当日经 GitHub API 与 PyPI 实抓；mem0/Graphiti/Letta/MemOS 架构细节取自各仓 README 当日版）。与已有内容的接口：§2/§3 的六家机制对照全部出自六家《架构拆解》与 OpenClaw 本地一手文档（`05-openclaw/openclaw/docs/concepts/memory-architecture.md`、`compaction.md`）；[rag-handbook §1.4](rag-handbook/RAG搭建文档.md) 划分了检索的两条路线，本手册 §7.5 补上另一半——「检索 vs 记忆」边界（口诀：预有的权威的进 RAG，交互中长出来的进记忆）；记忆评测复用 [eval-handbook](eval-handbook/Agent评测与质量工程手册.md) 的 judge 校准与"golden set + 指纹"回归（记忆库快照也要指纹）；§8 最小实现的 LLM 换装见 [python-handbook §3](python-handbook/Python大模型应用开发手册.md)，压缩提示词写法见 [prompt-handbook](prompt-handbook/提示词搭建文档.md)；投毒防御与 [mcp-handbook](mcp-handbook/MCP搭建文档.md) 安全章节互补。当日核实的关键事实：**letta-ai/letta 主仓已只剩文档壳，原 V1 记忆服务归档，现役代码迁至 letta-code（TypeScript）**——读旧 MemGPT 教程前先看本文 §7.3。

## 专题：Multi-Agent 协同手册（`multiagent-handbook/`）

与 MCP/Skill/RAG/提示词/Python/评测/Context 手册并列的协同层专题：Multi-Agent 协同手册，2026-09-27 完成。

| 文件 | 说明 |
|---|---|
| [multiagent-handbook/Multi-Agent协同手册.md](multiagent-handbook/Multi-Agent协同手册.md) | 单册九章：何时真的需要多 agent（单 agent 三条边界、四问判据、五类伪需求，含 Anthropic 90.2%/15× token/effort scaling 实测数字）→ 编排范式谱系六种（supervisor / orchestrator-worker / swarm·handoff / hierarchical / blackboard / protocol-based，各配最小结构图，对照 Anthropic《Building Effective Agents》）→ 通信与交接机制（**六家 agent 子代理机制横向对照表** + 可直接抄的交接协议四条 + "权限不随消息漂移"）→ 框架横评当日实抓九家（CrewAI 59.1k / LangGraph 42.4k / AutoGen **已进 Maintenance Mode** / Microsoft Agent Framework / OpenAI Agents SDK / Google ADK / AG2 / Claude Agent SDK / AgentScope，含选型决策树与"六家全自研"对照）→ A2A 协议现状（v1.0.1、2026-08-27 加入 Agentic AI Foundation、与 MCP 的边界：进程内用函数、进程间用消息、组织间用协议）→ 失败模式与治理（MAST 三大类 14 种失败模式 + Anthropic 实测失败清单 + 六类失败×治理手段表 + 十条上线前治理清单）→ 多 agent 评测（协作质量六指标，与 eval-handbook 轨迹评测/judge 校准互引）→ 企业范例横评八家 + 三家精读（agent-framework 接班人治理 / STORM 视角驱动协作 / open_deep_research 归档教训）+ 最小双 Agent 协作实现（Python 3 纯标准库，**已本机验证**，四条不变量）+ 12 条 FAQ + 上手清单 |

信息基准日 2026-09-27（20+ 框架/范例仓库的 star、版本、维护状态当日经 GitHub API 与 PyPI 实抓并核对 GitHub latest release；A2A 治理沿革与协议对象取自 a2aproject/A2A 仓库 README 当日版与 a2a-protocol.org；Anthropic 两篇工程博客与 MAST 论文（arXiv:2503.13657）当日核实）。与已有内容的接口：本文 §3 的六家对照表是六家《架构拆解》子代理章节（01 §7 / 02 §7 / 03 §8 / 04 §10 / 05 §9 / 06 §8）的编排面汇总，与 [context-handbook §3](context-handbook/Context与记忆系统手册.md) 的隔离面互补；A2A 与 [mcp-handbook](mcp-handbook/MCP搭建文档.md) 是协议层的两半（MCP 管 agent↔工具，A2A 管 agent↔agent）；评测方法论全部复用 [eval-handbook](eval-handbook/Agent评测与质量工程手册.md)（轨迹评测/LLM-as-judge/失败归因五分类 + MAST 三大类）；"六家 agent 全部自研、不用编排框架"的证据链见 [python-handbook §4.7](python-handbook/Python大模型应用开发手册.md)；blackboard 范式的框架级参照是 [08-langgraph](08-langgraph/源码解析与学习路线.md) 的共享 state/reducer/checkpoint 语义。当日核实的关键事实：**microsoft/autogen（61.2k star）已挂 Maintenance Mode，官方接班人为 microsoft/agent-framework；openai/swarm 已被 OpenAI Agents SDK 取代；langchain-ai/open_deep_research 已归档（2026-08）**——多 agent 框架选型必须做"归档/维护模式"扫描。

## 专题：AI 应用安全手册（`security-handbook/`）

与 MCP/Skill/RAG/提示词/Python/评测/Context/Multi-Agent 手册并列的安全专题：AI 应用安全手册，2026-09-27 完成。

| 文件 | 说明 |
|---|---|
| [security-handbook/AI应用安全手册.md](security-handbook/AI应用安全手册.md) | 单册九章：威胁模型总览（经典应用安全"代码/数据二分"第一公理在 LLM 上失效、十类 agent 攻击面、OWASP LLM Top 10 2025 与 Agentic ASI 双清单、**lethal trifecta（致命三要素）**：私有数据 × 不可信内容 × 对外通信三腿齐立则注入链成、断一腿即破）→ Prompt Injection 专题（直接/间接/跨域三型、EchoLeak 零点击链路逐段拆解、防御四分层：指令隔离 / 来源标记 spotlighting / 双 LLM（CaMeL 为 by-design 标杆）/ 最小权限配合；"检测器当边界"是反模式）→ 工具与权限安全（**六家权限/审批/沙箱机制横向对照表**带文件:行号：Codex 内核级双轴最强、OpenClaw 审批绑定 cwd+argv+env+可执行文件哈希最硬、ZCode/OpenCode 无 OS 沙箱；危险操作基线清单；"权限不随消息漂移"；MCP server/技能包/规则文件三类供应链载体防线）→ 数据与隐私（presidio PII 进出口双侧脱敏、记忆与日志治理、SecretRef"不看到值地取凭据"、合规简表注明非法律意见）→ Guardrails 工程（当日实抓七家横评：NeMo Guardrails 7.2k/Guardrails AI 7.5k/PurpleLlama 4.4k/presidio 11.1k/**llm-guard 已归档**；注入检测器真实水位与三条使用纪律；结构化约束）→ 红队与安全评测（AdvBench/HarmBench/JailbreakBench/XSTest/AgentDojo 与 promptfoo/garak/PyRIT 当日实抓、ASR×overrefusal 双轴指标、最小实现 ActionGate 闸门已本机验证）→ 企业落地清单（OWASP LLM Top 10 逐条对照 + 五组上线检查单）→ 真实案例库（EchoLeak / Rules File Backdoor / postmark-mcp / **OpenClaw 事件群**：Zenity 研究、MITRE ATLAS AML.CS0051、恶意技能 1.7M+ 安装 / slopsquatting 五案例）+ 14 条坑 FAQ + 上手清单 |

信息基准日 2026-09-27（护栏/红队/数据集 12 个仓库的 star、版本、维护状态当日经 GitHub API 与 PyPI/npm 实抓；**protectai/llm-guard 与 Azure/PyRIT 已归档**为当日核实的关键事实——后者 PyPI 仍以 1.1.0 发版、新仓库未公开；五个案例经一手来源核对：EchoLeak 论文 arXiv:2509.10540、slopsquatting 论文 arXiv:2406.10279、Koi Security 原文链接可点）。与已有内容的七个接口：§3 六家横向表的源码证据出自六家《架构拆解》权限章节（01 §5 / 02 §5 / 03 §9 / 04 §7+§10.2 / 05 §7+§13 / 06 §6），OpenClaw 一手安全文档在 `05-openclaw/openclaw/docs/gateway/security/`；注入防御的协议侧对照 [mcp-handbook §6.6](mcp-handbook/MCP搭建文档.md)；记忆与上下文投毒的完整版见 [context-handbook §6](context-handbook/Context与记忆系统手册.md)；安全评测方法论（判据优先级/judge 校准/轨迹归因）复用 [eval-handbook](eval-handbook/Agent评测与质量工程手册.md)；检索结果即不可信内容的权限模型见 [rag-handbook §6.5](rag-handbook/RAG搭建文档.md)；技能包供应链面见 [skill-handbook](skill-handbook/Skill搭建文档.md)；§3.4"权限不随消息漂移"与 [multiagent-handbook](multiagent-handbook/Multi-Agent协同手册.md) §3 的交接协议互补。案例库印证了本工作区的两个一手结论：postmark-mcp 是 [mcp-handbook](mcp-handbook/MCP搭建文档.md) 安全清单的现实注脚；OpenClaw 事件群是 [05-openclaw/架构拆解.md](05-openclaw/架构拆解.md) §7/§13 信任模型分析的现实注脚。

## 专题：Agent 工作流编排手册（`workflow-handbook/`）

与 MCP/Skill/RAG/提示词/Python/评测/Context/Multi-Agent/安全手册并列的编排层专题：Agent 工作流编排手册，2026-09-28 完成。

| 文件 | 说明 |
|---|---|
| [workflow-handbook/Agent工作流编排手册.md](workflow-handbook/Agent工作流编排手册.md) | 单册九章：何时用工作流 vs 自主 agent（Anthropic"控制流在哪"第一性区分 + 六问判据 + **腾讯 ADP 四种构建模式选型谱系**（标准/单工作流/Multi-Agent/Claw）+ 混合形态 + 六家 agent 为何全不用画布工作流）→ 模式谱系五种（prompt chaining / routing / parallelization / orchestrator-workers / evaluator-optimizer，各配最小结构图 + 失败模式；ADP 3.3 实战主链的复合 pattern 解读）→ 节点与编排原语（七节点 + 参数提取/HITL 两接缝 + **输入输出契约六条规范** + 节点选型 Badcase + 五家引擎 HITL 机制对照 + 六家"节点"对照含 ZCode dynamic-workflow 代码态编排）→ 引擎横评（**2026-09-28 当日实抓 12 家**：n8n 206k / Dify 157k / LangFlow 155k / Flowise **已归档** / LangGraph 42k 核心包 1.2.12 / Mastra 28k / Prefect 24k / Temporal 23k / Coze Studio 22k **开源节奏放缓** 等 + ADP，分引擎心智模型 + 选型决策树）→ 状态与数据流（三级变量作用域 / 唯一真源不变量 / **重试三要素与引擎默认值对照** / 错误分支"失败也是画布上的一条路径" / 挂起即持久化）→ 调试与可观测（三层定位法 / 单点+端到端调试 / 节点级日志 / 事件历史回放 / 版本管理与"发布≠生效" / Badcase 驱动调优循环）→ 企业范例（企业视角横评八家 + 精读三家：n8n 把 LangChain 搬进画布、Temporal 把确定性变工程纪律、Dify 画布产品化决策）→ **最小工作流编排器 miniflow**（Python 3 纯标准库约 250 行，DAG 拓扑执行 + guard 条件分支 + 幂等键重试 + on_error 异常分支，四条不变量，**已本机验证**含两个场景实跑输出）+ 12 条 FAQ + 上手清单 |

信息基准日 2026-09-28（12 个引擎仓库的 star、license、最新 release 与维护状态当日经 GitHub API / npm / PyPI 实抓；**Flowise 整库归档、coze-studio 主分支 push 停在 2026-07 为当日核实的关键事实**；各引擎机制细节取自官方文档当日版并逐一标注 URL）。一手底稿是 [fde-handbook](fde-handbook/FDE转行手册.md) 腾讯 ADP 认证课程的 [2.2下](fde-handbook/tencent-adp-fde-course/lessons/2.2下_任务执行与编排能力：Workflow、Multi-Agent_与_Claw.md)（四类节点/三种协同方式）、[3.3](fde-handbook/tencent-adp-fde-course/lessons/3.3_单工作流模式实战：客服助手.md)（单工作流实战全链路）与 [4.4](fde-handbook/tencent-adp-fde-course/lessons/4.4_Workflow_调优.md)（调优方法论）三节，ADP 产品页当日补抓。与已有内容的接口：**本文与 [multiagent-handbook §2.0](multiagent-handbook/Multi-Agent协同手册.md) 是同一坐标系的两半**（那边讲控制流交给模型的多 agent 范式，这边讲控制流写死的 workflow 模式，Anthropic 五种 pattern 两边共用）；六家 agent 编排面（主循环+委派、护栏位、ZCode dynamic-workflow、重试/熔断细节）的行号级证据出自六份《架构拆解》（01 §3/§5/§7 ｜ 02 §3/§4.3/§5 ｜ 03 §4/§5/§8 ｜ 04 §5/§9/§10.3 ｜ 05 §4/§7/§9 ｜ 06 §4/§8/§10）；LangGraph 图引擎语义（BSP/checkpoint/interrupt）已在 [08-langgraph](08-langgraph/源码解析与学习路线.md) 源码级拆过、本文只做横评视角；调试与 Badcase 闭环复用 [eval-handbook](eval-handbook/Agent评测与质量工程手册.md)（轨迹评测/版本指纹/OTel）；"唯一真源"不变量承接 [context-handbook §2](context-handbook/Context与记忆系统手册.md)；知识库节点上游管线见 [rag-handbook](rag-handbook/RAG搭建文档.md)。

## 专题：Agent 调优手册（`tuning-handbook/`）

与 MCP/Skill/RAG/提示词/Python/评测/Context/Multi-Agent/安全/工作流手册并列的调优层专题：Agent 调优（Tuning）手册，2026-09-28 完成。

| 文件 | 说明 |
|---|---|
| [tuning-handbook/Agent调优手册.md](tuning-handbook/Agent调优手册.md) | 单册十章：调优总纲（度量驱动闭环五步：定位瓶颈→假设→单变量变更→回归评测→固化 + **六类失败×调优手段映射表**：检索没召回/推理跑偏/工具误用/格式不合规/延迟超预算/成本失控）→ Prompt 调优（system prompt 分层裁决、few-shot 选择与头尾排序、CoT/ReAct 触发词的快思考 vs 推理模型实证边界、提示缓存对成本延迟的影响与稳定前缀工程）→ 检索与 RAG 调优（召回率×忠实度两把尺子分诊、chunk 策略信号表、embedding/reranker 选型与混合检索、HyDE/multi-query/问答对三类查询改写）→ 工作流调优（场景边界与节点选型、节点粒度两判据、无依赖并行+幂等串行、路由与降级链、重试/超时/预算熔断、HITL 三条插点判据）→ Multi-Agent 调优（角色收益边界与转交描述≠提示词、通信协议瘦身三纪律、共享状态 vs 消息传递选型表、四条撤退信号合并回单 agent）→ 模型与参数调优（temperature/top_p/seed 与"参数跟角色走"、推理模型 vs 快思考三档分工、结构化输出四级方案、上下文窗口与截断三抓手、模型路由与级联降级，**四家价格当日实抓表**）→ 成本与延迟工程（四档单价核算公式、缓存命中率工程清单、批处理/错峰 -50% 一览、投机执行与预取、TTFT/生成速率/工具往返延迟预算分解、**成本-质量-延迟三角取舍表**）→ 企业范例（9 家 GitHub 当日实抓横评 + promptfoo/DSPy/azure-search-openai-demo 三家精读 + 六家 agent 内建调优机制对照 + 跨企业 6 条设计模式）→ 最小调优实验框架（Python 3 纯标准库，分层切片/配对 A/B/三道闸回归门禁三不变量，**已本机验证**）+ 14 条坑 FAQ + 上手清单 |
| [tuning-handbook/code/mini_tuning_lab.py](tuning-handbook/code/mini_tuning_lab.py) | §9 最小调优实验框架：分层切片（固定 seed）→ 单变量 A/B 配对比较 → 三道闸门禁（dev 非劣 / 分场景不回退 / held-out 复跑）→ 基线指纹固化；`python mini_tuning_lab.py --promote` 一条命令跑通闭环（纯标准库、无网络依赖） |

信息基准日 2026-09-28（Anthropic/OpenAI/Gemini/DeepSeek 四家官方定价页与两份 prompt caching 文档当日实抓：Anthropic 缓存读 0.1×/写 1.25×、OpenAI 缓存输入 10% 价与延迟最高 -80%、批处理一律 -50%、DeepSeek 缓存命中价低至 2% 且错峰半价；9 个企业仓库 star/版本当日经 GitHub API/npm/PyPI 实抓，**RouteLLM 最后推送停在 2024-08 为当日核实的低维护警示**；§9 框架在本机 Python 3.13.5 验证通过自举→A/B→门禁→固化四路径，并真实踩出"门禁必须用同一切分的同类指标相比"一坑修入 FAQ）。与已有内容的接口：方法论骨架承接 [eval-handbook](eval-handbook/Agent评测与质量工程手册.md)（判据优先级/judge 校准/轨迹归因/成本核算，本文把评测当调优闭环的一环用）；一手底稿是 [fde-handbook](fde-handbook/FDE转行手册.md) 腾讯 ADP 课程的 [4.1-4.5](fde-handbook/tencent-adp-fde-course/lessons/4.1_智能体调试与评测基础.md) 五节调优课（调试评测/Prompt/知识库 RAG/Workflow/Multi-Agent，本手册 §2-§5 逐节展开为开源实现路径）；提示词**写法**见 [prompt-handbook](prompt-handbook/提示词搭建文档.md)（八区块模板/官方技法），本文只讲**调优动作**与缓存边界；RAG 架构与切分规范见 [rag-handbook](rag-handbook/RAG搭建文档.md)；工作流**怎么建**见 [workflow-handbook](workflow-handbook/Agent工作流编排手册.md)（两册同日成稿：那边建、这边调，ADP 4.4 Badcase 方法论共用）；协同范式与 MAST 治理见 [multiagent-handbook](multiagent-handbook/Multi-Agent协同手册.md)；三层压缩与缓存锚点见 [context-handbook](context-handbook/Context与记忆系统手册.md)；六家 agent 参数与成本机制对照（§8.5）出自各家《架构拆解》（01 §6/§7 ｜ 02 §5/§6 ｜ 03 §5/§6 ｜ 04 §8 ｜ 05 §7/§8 ｜ 06 §7.4/§8.1/§9）。

## 专题：AI 应用部署与运维手册（`deploy-handbook/`）

与 MCP/Skill/RAG/提示词/Python/评测/Context/Multi-Agent/安全/工作流/调优手册并列的部署层专题：AI 应用部署与运维（Deploy & Ops）手册，2026-09-28 完成。

| 文件 | 说明 |
|---|---|
| [deploy-handbook/AI应用部署与运维手册.md](deploy-handbook/AI应用部署与运维手册.md) | 单册十章：部署是两层问题（模型侧 × 应用侧四象限）+ 五档形态谱系与选型判据表 + 托管平台横评（Bedrock/百炼/ADP/Vertex 当日实抓，ADP 2.3 七步流程通用化）→ 容器化与镜像工程（多阶段构建与层缓存、**模型权重与镜像分离三不变量**、GPU 镜像治理、供应链锁定）→ 推理服务化（prefill/decode/KV cache 生命周期 → continuous batching/PagedAttention 为什么决定吞吐 → **30 仓库当日实抓横评**）→ 网关与流量治理（RPM/TPM 双尺限流、超时预算分解、熔断三态、模型路由与 failover 落地、三层灰度）→ 可观测性（OTel GenAI 部署落地、LLM 专属指标第四类、trace 采样、PII 脱敏挂 exporter）→ 成本与容量（GPU 利用率反直觉、spot up to 90% 边界、缓存三层次、KV cache 显存算账公式）→ 发布与回滚（**发布单元=模型×提示词×工作流三层组合快照**、双闸灰度、回滚判据演练）→ 企业范例（10 家横评 + production-stack/LibreChat/Higress 三家精读 + 跨企业 6 条设计模式）→ **最小部署演练**（docker-compose 起 agent 服务 + Prometheus，五条不变量 + 12 条 FAQ + 上手清单，**已本机验证**） |
| [deploy-handbook/code/](deploy-handbook/code/) | §9 演练四文件：`agent.py`（纯标准库约 260 行：liveness/readiness 双探针、Counter/Gauge/Histogram 指标渲染、预算熔断、日志 PII 脱敏、SIGTERM 优雅停机）、`Dockerfile`（多阶段构建 + 非 root + HEALTHCHECK）、`compose.yml`（服务名互通 + stop_grace_period）、`prometheus.yml` |

信息基准日 2026-09-28（推理引擎/网关/可观测/基础设施/应用平台 30 个仓库的 star、版本、维护状态当日经 GitHub API 实抓；Bedrock/百炼/ADP/AWS Spot 官网当日实抓，**Vertex AI 官网直连超时已显式标注未逐项复核**；当日核实的关键事实：**huggingface/TGI 已整库归档**（最后 release 2025-12-19）、**AutoAWQ 与 AutoGPTQ 双归档**（量化工具链收敛到 vllm-project/llm-compressor v0.14.0）、llama_deploy 半年未 push；§9 演练在本机 Docker 29.6.2 + Compose v5.3.1 + Python 3.13.5 全链路验证——build→healthy→健康检查/预算熔断/PII 脱敏→Prometheus 3.15.0 抓通→SIGTERM 优雅停机→down 清场，真实踩坑三条（空依赖表多阶段构建翻车/同名指标重复 HELP 被拒抓/镜像源故障走备用源）已入 FAQ）。与已有内容的接口：模型路由的"怎么分"与价格口径见 [tuning-handbook §6.5/§7](tuning-handbook/Agent调优手册.md)（本文 §4.4/§6 只讲网关侧"怎么落"）；OTel GenAI 协议字段与可观测平台横评见 [eval-handbook §7/§8](eval-handbook/Agent评测与质量工程手册.md)（本文 §5 讲部署落地：collector/采样/脱敏）；重试三要素与"发布≠生效"见 [workflow-handbook §5/§6](workflow-handbook/Agent工作流编排手册.md)；secrets/PII/合规/供应链见 [security-handbook §3.5/§4](security-handbook/AI应用安全手册.md)；MCP server 部署三形态见 [mcp-handbook §5.2](mcp-handbook/MCP搭建文档.md)、RAG 服务部署见 [rag-handbook §5.2](rag-handbook/RAG搭建文档.md)、vLLM/Ollama 用法与服务界面见 [python-handbook §6/§7](python-handbook/Python大模型应用开发手册.md)；部署生命周期的一手底稿是 [fde-handbook ADP 2.3](fde-handbook/tencent-adp-fde-course/lessons/2.3_从开发到上线：ADP_应用的完整使用流程.md) 七步流程（§1.4 通用化）；六家 agent 的部署面（OpenClaw 常驻网关六条限流/OpenCode HTTP-first/Codex app-server 守护进程等）对照见本文 §1.5，行号级证据出自各家《架构拆解》。

## 专题：AI 应用岗面试题库（`interview-handbook/`）

与源码学习、各专题手册并行的求职训练专题：AI 应用岗面试题库（LLM 应用开发 / Agent 工程 / FDE 方向），2026-09-28 完成。

| 文件 | 说明 |
|---|---|
| [interview-handbook/README.md](interview-handbook/README.md) | 总入口：怎么刷（三遍法）与全真模拟指南、14 天面试冲刺路线、难度/频次分布统计（难度 初 30% / 中 45% / 高 25%；频次高 52 题）、全部 128 题索引表（题号→题目→难度→频次→对应手册章节） |
| [01-LLM基础与提示词.md](interview-handbook/01-LLM基础与提示词.md) | 20 题：token 与计费 · 采样参数 · 幻觉与上下文窗口 · few-shot/CoT 边界 · 结构化输出 · 提示缓存 · 中文 token 坑 · 推理模型分工 · 注入防御 · 六家提示词组织 · context rot · 按模型分 prompt |
| [02-RAG与知识库.md](interview-handbook/02-RAG与知识库.md) | 20 题：RAG 管线 · 切分与 top-k · 混合检索/重排 · 引用与元数据 · 分诊两把尺子 · RAGAS 与 golden dataset · 多租户隔离 · 检索 vs 记忆 · 检索结果不可信 · 成本估算 |
| [03-Agent架构与工具调用.md](interview-handbook/03-Agent架构与工具调用.md) | 20 题：agent 定义 · 最小 loop · 工具调用时序 · MCP/Skill 生态位 · 规划与分解 · 子代理隔离 · 何时多 agent · 编排范式 · 记忆 · 上下文压缩 · 权限六家对照 · 事件溯源 · A2A · MAST · 六家全自研证据 |
| [04-评测调优与成本工程.md](interview-handbook/04-评测调优与成本工程.md) | 18 题：评测第一问 · LLM-as-judge · 判据优先级 · 回归 · 公共基准 · 自建评测集 · 轨迹评测（15 步 3 步题）· badcase 回流 · 可观测 · 调优闭环 · 六类失败分诊 · 延迟预算 · 成本精算 · 模型路由 · 三角取舍 |
| [05-系统设计与场景题.md](interview-handbook/05-系统设计与场景题.md) | 18 题：知识库问答 · 审核流水线 · 多租户 RAG · 客服 agent · 数据分析 agent · LLM 网关 · 千页 PDF · 记忆系统 · guardrails · 私有化 · <100ms 风控 · prompt 版本管理 · multi-agent 报告系统 · agent 平台 · 渐进引入 |
| [06-行为面与FDE实战场景.md](interview-handbook/06-行为面与FDE实战场景.md) | 16 题：Why FDE · 第一周 · "AI doesn't work" · STAR · 数据质量差 · POC 集成失败 · one-off 定制 · 暴怒 CTO triage · 报价算账 · Palantir 拆解轮真题 · OpenAI case study · 律所一周计划——即 [fde-handbook §8.6](fde-handbook/FDE转行手册.md) 十道高频题的**答题训练版** |
| [07-手撕代码与工程实践.md](interview-handbook/07-手撕代码与工程实践.md) | 16 题：手写 agent loop · 工具封装 · SSE · 重试客户端 · 成本函数 · RAG 管线 · 评测脚本 · 切分器 · 权限闸门循环 · 结构化解析 · 历史压缩 · supervisor · 最小编排器 · judge · 预算熔断（每题带白板可写代码骨架；算法题互引 [leetcode-hot100](python-handbook/leetcode-hot100/README.md)） |

每题统一四件套格式：**考察点 → 参考回答（"能通过面试"完整度，含关键数字与失败模式）→ 追问与陷阱（2-3 个追问 + 常见错误答案）→ 加分项 → 延伸阅读**；各主题开头有高频题速览表（共 52 题）。相对链接共 357 处、28 个目标文件，已逐一验证指向存在。

信息基准日 2026-09-28。与既有内容的四个接口：**求职策略/公司名单/薪资行情看 [fde-handbook](fde-handbook/FDE转行手册.md) 第八章，本册是它的"做题版"**，分工在题库 README 里写明；算法题不进本册，与 [python-handbook/leetcode-hot100](python-handbook/leetcode-hot100/README.md) 互引；答案素材全部回链 mcp/skill/rag/prompt/python/eval/context/multiagent/security/workflow/tuning/deploy 各手册对应章节与 ADP 课程七节讲义（1.3/3.1/3.2/3.3/4.1/4.3/4.4），价格与框架事实沿用 [tuning-handbook §6.6](tuning-handbook/Agent调优手册.md) 的 2026-09-28 当日实抓口径（四家官方定价页），随时间漂移；05 的网关/私有化/渐进引入等部署向题目与 [deploy-handbook](deploy-handbook/AI应用部署与运维手册.md) 的网关流量治理/发布回滚章节互补（那边讲怎么落，这边讲怎么答）。

## 专题：云厂商 AI 平台对比手册（`cloud-handbook/`）

与 MCP/Skill/RAG/提示词/Python/评测/Context/Multi-Agent/安全/工作流/调优/部署手册并列的选型层专题：云厂商 AI 平台对比（FDE 视角的选型答题手册），2026-09-28 完成。

| 文件 | 说明 |
|---|---|
| [cloud-handbook/云厂商AI平台对比手册.md](cloud-handbook/云厂商AI平台对比手册.md) | 单册八章：TL;DR（含八家一句话定位速览表）→ 对比方法论（八维度定义：模型目录与自托管接入 / Agent 编排形态 / 知识库与 RAG 管线 / 工具·MCP·连接器 / 评测与调优 / 部署·区域·合规 / 计费模式 / 生态锁定与迁移成本 + 符号与取证等级打分口径）→ 八家逐家画像（AWS Bedrock / Microsoft Foundry〔原 Azure AI Foundry〕/ Google Vertex AI〔现 Gemini Enterprise Agent Platform〕/ 阿里百炼 / 腾讯 ADP / 火山引擎豆包+方舟+HiAgent+扣子 / 百度千帆 / 华为云盘古+ModelArts+智果 AgentArts，各含产品矩阵图·核心能力·定价要点·典型客户·短板与坑）→ 横向对比总表（三张子表逐格填实带来源 + "只有某家有/没有"差异点清单）→ 场景化选型决策树（创业快速上线 / 国企私有化合规 / 中国企业出海 / 外企入华 / 已有 K8s 团队自控，各给推荐组合+理由+当场验证三件事）→ 迁移与锁定成本（模型/编排/数据三层可迁移性 + MCP 互操作现实水位 + 双云三笔账）→ 中国区特辑（生成式 AI 备案 748 款与备案/登记分界 · 数据出境三条路径+豁免+自贸区负面清单 · 昇腾国产算力 · 信创与中国运营云三例，注明非法律意见）→ 企业范例横览 + 三家精读（Commerzbank / 腾讯 ADP 迈瑞+碧桂园 / Cox Automotive）→ 同一个"知识库问答+工具调用"需求在腾讯 ADP（零代码）/阿里百炼（低代码）/AWS AgentCore（代码态）的最小实现对照（文档级步骤 + 验证边界）+ 12 条坑 FAQ + 上手清单 |

信息基准日 2026-09-28（八家平台的产品页/定价页/官方文档当日经子代理逐家实抓，结论带来源链接，"未当日复核"项 25+ 处显式保留并注明原因——当日即核实三起平台换代：Bedrock Agents Classic 停止新客、Azure 更名 Microsoft Foundry、Vertex 更名 Gemini Enterprise Agent Platform，以及百度千帆 ModelBuilder+AppBuilder 合并、华为 MaaS 下线按算力计费的部署/调优、ADP 专业版 PU 额度产品页与计费文档口径冲突等当日事实；调研执行受当日并发配额限制为单子代理串行抓取）。与已有内容的八个接口：本册是 [deploy-handbook §1](deploy-handbook/AI应用部署与运维手册.md) 托管平台速览的"深全版"（那边部署视角四家横评，这边选型视角八家×八维度，ADP/百炼/Bedrock 口径同源互证）；价格口径承接 [tuning-handbook §6.6/§7](tuning-handbook/Agent调优手册.md)（缓存/批处理/错峰三杠杆在 §4 各路径复用）；引擎换代扫描纪律与自建引擎选型见 [workflow-handbook §4](workflow-handbook/Agent工作流编排手册.md)（那边管开源引擎，这边管云平台）；ADP 画像的一手底稿是 [fde-handbook ADP 2.1/2.3](fde-handbook/tencent-adp-fde-course/lessons/2.1_ADP_是什么：企业级智能体开发平台.md)；§6 中国区特辑是 [security-handbook §4.4/§4.5](security-handbook/AI应用安全手册.md) 合规简表与数据出境三口径的中国区展开（同样注明非法律意见）；§5.2 的 MCP 互操作水位与 [mcp-handbook](mcp-handbook/MCP搭建文档.md) 互补（那边协议与 server 搭建，这边平台侧消费现状）；§8 POC 的检索质量判据用 [rag-handbook](rag-handbook/RAG搭建文档.md)、评测判据用 [eval-handbook](eval-handbook/Agent评测与质量工程手册.md)、多 agent 形态判断用 [multiagent-handbook](multiagent-handbook/Multi-Agent协同手册.md)（A2A 在千帆产品页与 Foundry GA 现状已互证）。

## 专题：AI 应用岗真实面经精评（`mianjing-handbook/`）

与源码学习、各专题手册、面试题库并行的求职训练专题：AI 应用岗真实面经精评（[interview-handbook](interview-handbook/README.md) 的姊妹册），2026-09-28 完成。

| 文件 | 说明 |
|---|---|
| [mianjing-handbook/AI应用岗真实面经精评.md](mianjing-handbook/AI应用岗真实面经精评.md) | 单册九章：TL;DR 与"面经怎么用"三条纪律（面经是分布样本不是题库 / 按考点聚类不按公司背 / 复盘自己的答法）→ 面经样本说明（S/A/B/C 四级来源可信度分级 + 平台/幸存者/岗位/时效四项偏差声明 + FDE 等样本不足显式声明）→ 按方向聚类 13 场精评（社招全景 26 家 / 28 家上岸、腾讯 AI 应用暑期实习、字节豆包三轮、腾讯终端 Agent 深挖、石头科技 Agent 三轮、美团 RAG 专项、快手/阿里应用面、蚂蚁 judge 线+百度数据线、字节 DPO 对照组、FDE 拆解轮合成、Agent 深度面共性追问；每场统一"背景→问题链实录→逐题精评（考察点/参考答法/追问预测/五档得分档位）→全场复盘→题号互链"）→ 考点频率统计（七大主题归簇分布 + 必考 Top20，按独立证据源共现排序）→ 面试官视角（四轮次考察重心 + 深度/广度/工程感/沟通四条评分暗线 + 红灯信号清单）→ 反问环节弹药库（按公司类型 + 禁忌清单）→ 模拟面试流程（六步 mock + 判档自评表模板 + judge 校准式防坑）→ 失败案例集 6 例（匿名化，归因对治链接题库）→ FAQ 12 条 + 30 天面经使用计划 + 上手清单 + 来源清单 |

信息基准日 2026-09-28。**素材全部当日实抓并逐篇标注来源链接与抓取日期**：掘金第一人称面经 5 篇（2025-07 至 2026-07）、GitHub 面经仓库 4 个（dong-frank/AgentInterviewNotes 亲历、jingtian11/EasyOffer 28 篇转载、guocong-bincai/ai-interview-guide 收录的石头科技三轮可溯源抖音原帖、adongwanai/AgentGuide 案例集）、FDE 线沿用 [fde-handbook §8](fde-handbook/FDE转行手册.md) 已核实来源；抓取过程中核实并**排除**了 CSDN 的 AI 生成伪面经（教学体+引流），牛客/脉脉/知乎因登录墙未能直抓已在偏差声明中如实记录，FDE 中文第一人称面经样本不足已显式声明（按 C 级二手合成，未编造）。与题库的互链经脚本校验：237 条相对链接、201 条 Q 题号互链（Q001–Q128 与题库七分册归属逐一核对）、48 个标题锚点全部通过。本册与 [interview-handbook](interview-handbook/README.md) 的分工：题库是"题与标准答法"（四件套），本册是"真实面试现场记录与复盘"（问题链实录 + 得分档位 + 追问链）；"面试官视角评分"的 rubric 设计方法沿用 [eval-handbook §5](eval-handbook/Agent评测与质量工程手册.md) 的 judge 校准思路（语义锚定/证据先行/长度偏差控制）；求职策略、公司名单与薪资行情仍归 [fde-handbook §8](fde-handbook/FDE转行手册.md)，三册互链不重复。

## 专题：GitHub 开源 Agent 项目实战精读（`project-study/`）

与 01-08 源码学习互补的第三条线：**"上手复现 + 设计对照"**（那八家是"逐行拆解"），2026-09-28 完成。三个 GitHub 开源 Agent 项目各走完 clone → 安装 → **真机跑通官方最小示例** → 源码核锚点 → 与六家 harness 对照的完整闭环，每册统一六节（定位生态 / 架构总览 / 最小复现记录 / 与 01-08 六家对照 / 精读清单 / FAQ+上手清单），复现记录全部真实并如实标注边界。

| 文件 | 项目 | 赛道 | star（2026-09-28 实抓） | 真机复现内容 |
|---|---|---|---|---|
| [project-study/01-camel.md](project-study/01-camel.md) | `camel-ai/camel`（commit fc27907） | 多 agent 会话/任务编排（黑板范式） | 17,784 | ChatAgent 工具调用 + Workforce 双角色编排（自动分解 + quality score 92/95），Qwen 实跑 |
| [project-study/02-crewai.md](project-study/02-crewai.md) | `crewAIInc/crewAI`（commit 4ed2abc） | 角色制 crew 编排（supervisor 范式） | 59,101 | sequential（自定义工具）+ hierarchical（Manager 自动委派），GLM-4-Flash 实跑 |
| [project-study/03-browser-use.md](project-study/03-browser-use.md) | `browser-use/browser-use`（commit 4cbe921） | 浏览器 agent（环境特化型） | 116,507 | 本机 Chromium 三步完成"读网页标题"（DeepSeek + DOM 文本模态） |
| [project-study/README.md](project-study/README.md) | —（总入口） | 三项目导航 + 选型速览表 + 复现环境总说明 | — | 复现脚本存 `project-study/repro/` 五个文件 |

信息基准日 2026-09-28（star/release/维护状态当日经 GitHub API 实抓并标注来源；**AutoGen 替换为 camel 是当日实抓的关键事实**：microsoft/autogen 停止发版 12 个月（最后 release python-v0.7.5 于 2025-09-30）、官方 Maintenance Mode、接班人 microsoft/agent-framework 活跃（13,825 star，pushed 2026-09-27），且替换候选 MetaGPT 同样半停更（最后 release 2025-03-09）——"归档/维护模式扫描"纪律的又一次实证；LLM 底座当日实况：阿里百炼账号在复现会话中途整账号 Arrearage（欠费），camel 册的 Qwen 实证全部发生在欠费前，后两家改用智谱 glm-4-flash 与 deepseek-chat 完成，三册 §3 各自如实记录踩坑与边界）。与已有内容的接口：三家 §4 的六家对照全部回链六份《架构拆解》既有章节结论（不重复拆解六家源码）；编排范式判定沿用 [multiagent-handbook §2](multiagent-handbook/Multi-Agent协同手册.md) 六范式（camel=blackboard、crewai=hierarchical/supervisor、browser-use=单 agent 环境特化）；camel 的 TaskChannel 黑板语义与 [08-langgraph](08-langgraph/源码解析与学习路线.md) 的共享 state 语义互补（那边框架语义、这边拿框架干活）；browser-use 是 [05-openclaw](05-openclaw/架构拆解.md) `browser` 工具同赛道的"库形态"对照。学习顺序建议：03（最直观，半小时见真浏览器在动）→ 02（编排面最薄）→ 01（编排面最厚，Workforce/TaskChannel 值得逐行精读）。

## 专题：考公备考手册（`kaogong-handbook/`）

与源码学习、各专题手册、求职训练各册并行的"个人备考"专题：公考（国考/省考/选调生/事业编/军队文职）行测·申论·面试全链路作战手册——不是机构广告册，是给"会自学的人"的方法论+计划+题法手册，2026-09-28 完成。

| 文件 | 说明 |
|---|---|
| [kaogong-handbook/考公备考手册.md](kaogong-handbook/考公备考手册.md) | 单册九章：TL;DR（"考公是信息战+体力战"三条总纲 · 一个考季全程时间轴速览 · 什么时候看哪章）→ 考情全景（五类编制考试差异表〔组织方/规模/科目/竞争比口径/编制/适合谁〕· 报考时间轴 · 职位表三遍筛选法〔硬条件筛→条件叠加→性价比终筛，含专业目录与备注陷阱〕· 应届生身份认定五要点 · 合格线 vs 进面线口径）→ 行测五模块题法（政治理论与常识取舍纪律 / 言语主旨·意图·逻辑填空信号词法 / 数量放弃与必拿题清单 + 代入排除·赋值法 / 判断推理图形·定义·类比·逻辑四子类套路表 / 资料分析速算三件套 + 必背公式表；每模块"题型→识别信号→解法→限时标准"四列速查）→ 行测套卷策略（题序 · 120 分钟时间预算表 · 涂卡节奏 · 放弃决策树）→ 申论答题框架（材料四类句标记法 + 归纳概括/综合分析/提出对策/贯彻执行四型"审题三问→标记→合并→模板→字数" + 公文 15 种法定文种格式速查）→ 申论大作文（材料总论点三步提炼 · 标题与分论点句式库 · 素材三类来源清单 · 四类开头结尾模板）→ 面试（结构化/结构化小组/无领导三形式流程与得分点 · 综合分析/计划组织/人际关系/应急应变四题型框架 · 五个反模板化动作 · 2025 国考面试真题精评 3 道）→ 90 天备考计划（三阶段总览 · 全职/在职两套每日时间表 · 错题本与复盘闭环 · 模考评分与目标分数线设定）→ 资源与工具（免费/付费取舍表 · 刷题 APP 横评 · 网课选择纪律 · 可复制模板：素材本/模考台账/错题本）→ FAQ 15 问 + 考前一周与考试日清单 |

信息基准日 2026-09-28。**考情数据当日实抓，级别如实标注**：国家公务员局/军队人才网等官方站点在本机环境直连失败，§1 一律采用"官方口径 + 当日公开报道转述核实"级（附录来源清单逐条列明），抓不到的岗位级数据显式标注"未当日复核"、禁跨年直接比较——已实录：2026 年度国考招录 3.81 万人 / 过审 371.8 万（约 98:1）、2027 年度公告截至基准日未发（按近三年规律预计 2026-10 中旬）、2026 多省联考 23 省+新疆兵团约 12.59 万人、2026 军队文职 22,812 人、2026 国考合格线三档（105/95/90，行测 60/50/45）；进面分参考引自 2025 国考首批面试名单（21 世纪经济报道 2025-01："20 省最低进面分超 140、最高 149.8"）口径。**真题引用纪律**：一律"考生回忆版大意转述 + 年份 + 出处"（§6.4 三道 2025 国考面试真题精评均带场次与机构转载来源），不逐字复制真题、不引无出处"网传真题"。与已有内容的接口：§7.3 复盘闭环借 [tuning-handbook §1.1](tuning-handbook/Agent调优手册.md) 的"定位→假设→单变量→回归→固化"结构（应用层——错题六字段/模考台账/单变量周计划——为本手册原创设计）；§9 冲刺节奏体例参考 [interview-handbook](interview-handbook/README.md) 的路线写法（AI 应用岗面试 vs 公考全链路，方法论同构、赛道不同）；年度复核点（每年 10 月中旬国考 / 1-2 月省考 / 11 月初军队文职）与维护纪律见手册附录。

## 专题：英语四级备考手册（`cet4-handbook/`）

"个人备考"专题第二册（第一册考公）：大学英语四级（CET-4）备考作战手册——面向大学生与在职重考者，方法论 + 计划 + 题法 + 素材四位一体，不卖课不贩卖焦虑。2026-09-28 首版；**2026-10-24 按当前时间重排为双轨制**（旧版距考 75 天仍按"90 天通用 + 压缩规则"组织，新版距 2026-12-12 笔试仅 49 天，改为主推 49 天冲刺版，并把翻译例句全部换成当日核实的真题原文）。

| 文件 | 说明 |
|---|---|
| [cet4-handbook/英语四级备考手册.md](cet4-handbook/英语四级备考手册.md) | 单册十章（§0-§9 + 附）：TL;DR（两条总纲〔分数 = 词汇量 × 熟练度 · 输入项拉分输出项保分〕· 全程时间轴速览〔2026-10-24 起算，距笔试 49 天〕· 什么时候看哪章）→ 考情全景（题型分值官方口径表〔听力+阅读占 70%、听力篇章与仔细阅读单题 2% 为最高单价〕· 考试日内部时段〔惯例口径标注〕· 报名窗口与报考资格官方原句〔"四级 425 分及以上可报六级"〕· 常模分制原句〔710 分、单项 249/249/212、不设及格线〕· 425 三档目标线设定）→ 双轨备考计划（A 轨 49 天冲刺版〔10-25~12-12：词汇 14 天/题型 21 天/模考 14 天〕冲本届 + B 轨 90 天标准版〔30/35/25，锚点 2027-03-15〕备 2027-06；在校 2h/在职 1h 双时间表 · 周复盘模板〔借调优手册五步〕）→ 词汇工程（高频 800/中频 1200/认知 2000 三档词频带与分组记忆表 · 20 组高产词根 · 搭配 20 + 短语动词 10 · 艾宾浩斯 6 复习点表与 17 天法取舍）→ 听力（三遍精听法 · 选项预读与六类信号词表 · 新闻/长对话/篇章三题型定位 · 音形义绑定三件套）→ 阅读（段落匹配三步定位法 · 仔细阅读四题型解法 · 选词填空"词性→搭配→语境"三步 · 40 分钟时间预算与取舍纪律）→ 写作（议论文/说明文/应用文书信三框架 · 开头/过渡/结尾句式库各 8 句 · 论证三法 · 常见错误 Top20 · 反模板化五招）→ 翻译（拆句→定主干→补修饰→连句四步 · 文化/经济/社会/科技四主题词表各 30 词带例句 · 主动被动/无主语句/四字格句式转换 · 当日核实真题例句精评 3 句）→ 真题使用法（三遍用法与场次分配 · 精析表错因四分类〔词汇/语法/定位/逻辑〕· 模考评分与目标分线性换算）→ FAQ 12 问 + 考前一周（D-7→D-1）与考试日（8:20→11:20）清单 |

信息基准日 2026-10-24（官网六页当日实抓并标注链接：报名公告〔笔试 12-12、四级 9:00-11:20、口试 11-21/22、准考证 11-17 与 12-01 起打印、电子成绩报告单〕· 四级笔试介绍页〔题型题量分值全表〕· 分数解释页〔常模原句〕· 报考资格页 · 考试时间页〔12 月仅开考英语〕· 报名系统；"未当日复核"项 12 处显式保留〔考试日内部时段/报名费/2027 届日期等〕）。**真题例句全部当日核实**：2023-06 第一套（高等教育）、2025-06 第一套（袁隆平）、2025-06 第三套（便民生活圈），注明年月套数与来源链接；并勘误"自驾游=2023-06"的流传误区（实为 2023-03 加考卷）。与已有内容的接口：§2.5 周复盘与 §8.2 精析表的错题复盘结构借 [tuning-handbook §1.1](tuning-handbook/Agent调优手册.md) 的"定位→假设→单变量→回归→固化"闭环；路线表体例参考 [interview-handbook](interview-handbook/README.md) 的冲刺路线写法；套卷纪律与 [kaogong-handbook](kaogong-handbook/考公备考手册.md) 的模考方法论同构（赛道不同）；年度复核点（每年 2-3 月 / 8-9 月报名季，只更新时间轴两表）见手册附录。

## 专题：面试备战站（`projects/interview-prep-app/`，自建应用）

与前面所有"手册"性质不同的第一条**应用线**：这是自建的可运行本地 Web 应用（非手册、非文档），把 [interview-handbook](interview-handbook/README.md) 的 128 道题变成能检索、能自测、能记错题、能看进度的刷题站，2026-09-28 完成。Python（FastAPI）后端 + 原生 HTML/CSS/JS 单页，无数据库、无前端构建链、无 CDN 依赖（Markdown 渲染为极简自实现，断网可用）。

| 文件 | 说明 |
|---|---|
| [projects/interview-prep-app/build_index.py](projects/interview-prep-app/build_index.py) | 解析七个题集 .md → `data/index.json`（128 题：题号/主题/难度/频次/题干/四件套原文/延伸阅读链接）；解析失败逐条报错退出而非静默跳过，并与题库总 README 登记表交叉核对（题数/难度/频次分布对不上即拦截）；输出不含时间戳，同输入必同输出（幂等，两次构建 sha256 一致） |
| [projects/interview-prep-app/app.py](projects/interview-prep-app/app.py) | FastAPI 后端：题库检索（主题/难度/频次/关键词/状态过滤+分页）、卡片自测（会/半会/不会三档自评）、错题本（半会/不会自动入本+移除/重测）、进度统计（每主题完成率/错题率/分布）四组 API + `/healthz` `/readyz` 两层健康检查（借 deploy-handbook §9 语义）；state 读写加锁 + "临时文件+os.replace"原子落盘；错题本是推导视图不是存储实体（重测改评自动进出） |
| [projects/interview-prep-app/smoke_test.py](projects/interview-prep-app/smoke_test.py) | 冒烟测试 42 项：五功能关键路径 + 索引幂等（sha256 对比）+ 跨重启持久化（杀进程重启后错题本仍在）；独立端口与状态文件隔离，不污染真实数据；2026-09-28 本机实跑 42/42 全 PASS（输出存档 `data/smoke_test_output.txt`） |
| [projects/interview-prep-app/static/](projects/interview-prep-app/static/index.html) | 原生单页前端三件套：进度仪表盘 / 题库检索 / 卡片自测 / 错题本四视图 + 题目详情弹层（四件套全文 + 代码块深色渲染 + 延伸阅读经 `/workspace` 只读挂载回查原手册） |
| [projects/interview-prep-app/README.md](projects/interview-prep-app/README.md) | 应用说明：架构一句话图、启动三步、功能对照表、验证记录（冒烟摘录+解析校验+浏览器实机抽查）、已知边界（单 worker 进程锁/索引不热更新/仅限本机等） |

信息基准日 2026-09-28。数据源只读复用 [interview-handbook](interview-handbook/README.md) 七个题集（Q001-Q128，128 题四件套原文不改动不复制进应用——索引按需解析生成），学习状态落盘应用自己的 `data/state.json`；本应用不改题库任何文件。健康检查、预算校验顺序（便宜检查挡在贵调用前）与指标思路借鉴 [deploy-handbook §9](deploy-handbook/AI应用部署与运维手册.md) 的最小部署演练（那边 docker-compose + Prometheus 全套，这边本机 uvicorn 直跑，只取两层健康检查与不变量纪律）。启动：`python build_index.py` → `python app.py` → 浏览器开 `http://127.0.0.1:8765`。

## 收尾与持续维护

> 本节是 18 项任务队列的收官登记（2026-09-28，⑬ 中文化收尾）：前面 17 项任务的产出已全部纳入上文四象限总览；本节记录收官任务本身的产出、工作区的可持续维护机制，以及后续扩展建议。

### 本次收官任务（⑬）产出清单

| 产出 | 说明 |
|---|---|
| **五个源码仓中文化导读** | `01-claude-code/anon-kode`（10 文件 185 行）、`02-codex/codex`（7 文件 112 行）、`03-deepseek-harness/deepseek-harness`（5 文件 75 行）、`07-langchain/langchain`（4 文件 63 行）、`08-langgraph/langgraph`（4 文件 53 行）——共 **30 个关键源码文件、488 行新增、0 行删除**，全部在本地分支 `study-cn-comments`；每仓配 [README-cn.md](#ⅰ-源码仓逐行拆解线)（定位 + 文件地图 + 阅读顺序 + 与《架构拆解》对照表）。与既有 04/05/06 三家体例一致，学习注释分支现为八家全家 |
| **文档一致性脚本** | [scripts/check_crossrefs.py](scripts/check_crossrefs.py)：扫描全部自产 md，报断链 / 锚点失效 / 悬空引用（互引矩阵 REQUIRED_LINKS）；确定性输出（同输入同输出）。首跑 ERROR 49 · WARN 11，修复后复跑 **全 PASS**（97 个 md），修复留档见 [check_crossrefs_report.md](scripts/check_crossrefs_report.md) |
| **断链修复** | 46 处图片断链（ADP 课程 `images/` 三个子目录名被 URL 编码落盘，已重命名为中文对齐语义）；3 处代码伪链接（`dict[key](**kwargs)` 被 markdown 误渲染，脚本精确豁免） |
| **互引整合** | 新批次（mianjing / cloud / project-study / kaogong / cet4）与既有手册之间补齐 **11 条反向交叉引用**（interview↔mianjing/kaogong/cet4、deploy↔cloud、tuning↔kaogong/cet4、multiagent→project-study、08-langgraph→project-study、05-openclaw→project-study、fde↔cloud），只新增行不动既有内容 |
| **README 收尾** | 根 README「文件夹总览」重组为**四象限总览**（Ⅰ 源码仓 8 家 ｜ Ⅱ 手册类 13+2 ｜ Ⅲ 备考·求职 4 册 ｜ Ⅳ 项目类 2 项），每行一句话定位 + 入口链接；16 个手册目录新建入口 `README.md`（一句话定位 + 互补关系 + 全景导航），3 个已有 README 补齐指向根 README 的一句 |

### 内容地图（按学习目标检索）

- **看懂一个 agent 怎么跑**：Ⅰ 源码仓《架构拆解》→ `study-cn-comments` 分支带注源码 → Ⅳ project-study 真机复现对照。想动手：八家各有《Learn X》十课教材（`analysis_*` 目录，01-claude-code 用第三方 17 课），每课 中文讲解 + 零依赖可运行代码 + SVG 图解 + 真实源码 文件:行号 锚点，`run.bat` 一键全跑。
- **搭一个系统能力**（RAG/MCP/Skill/提示词/评测/部署）：Ⅱ 对应专题手册的"最小实现"章节（均已本机验证），配合 python-handbook 的代码用法。
- **回答面试题**：Ⅲ interview-handbook 题库（题号索引）→ mianjing-handbook 真实现场 → 各手册对应章节深挖（题库每题的延伸阅读已回链）。
- **找工作/上岗**：fde-handbook 双册（策略与实战）→ cloud-handbook（选型答题）→ Ⅲ 求职两册。
- **个人备考**：kaogong / cet4 两册（与工程手册方法论同构，复盘闭环共用 tuning 五步）。

### 后续扩展建议

- **可以补的主题手册**：LangGraph 进阶（多 agent 图 / streaming 深入）；结构化输出与函数调用规范横评；Agent 记忆的长期评测基准（LongMemEval 实战化）。
- **可以深化的交叉引用**：面试题库 Q129 起新增题回链 cloud/fde 两册的场景题；workflow/tuning 两册的最小实现与 projects/interview-prep-app 的工程实践互证。
- **可以新增中文化的代码仓**：04-zcode 内嵌 workspace 的 `dynamic-workflow` 子包（目前未加注）；05-openclaw 的 `src/gateway` 主循环（体量大，建议挑 5-8 文件）；08-langgraph 的 `prebuilt/tool_node.py` 与 `checkpoint/base`。
- **维护节奏**：价格/版本类事实每季度对照各手册"信息基准日"复核；上游代码更新后先切回 `main`/`dev` 再 pull（见「维护」节）；每次结构改动后跑 `python scripts/check_crossrefs.py --report` 留档。
