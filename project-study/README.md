# GitHub 开源 Agent 项目实战精读

> 首版：2026-09-28 ｜ 信息基准日：**2026-09-28**
>
> 本专题与 01-08 源码学习目录**互补而非重复**：那八家是"逐行拆解"（生产级 harness 与框架的架构精读），本专题是"**上手复现 + 设计对照**"——三个 GitHub 开源 Agent 项目，每个都走完 **clone → 安装 → 真机跑通官方最小示例 → 源码核锚点 → 与六家 harness 对照** 的完整闭环。所有复现记录真实（跑了什么、输出什么、坑是什么），跑不通的如实写边界。

## 三项目导航

| 册 | 项目 | 赛道 | 快照 commit | 当日实抓 star | 一句话定位 |
|---|---|---|---|---|---|
| [01-camel.md](01-camel.md) | [camel-ai/camel](https://github.com/camel-ai/camel) | 多 agent 会话/任务编排（黑板范式） | `fc27907`（master） | 17,784 | ChatAgent 大一统循环 + Task 任务树 + Workforce/TaskChannel 黑板编排 |
| [02-crewai.md](02-crewai.md) | [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | 角色制 crew 编排（supervisor 范式） | `4ed2abc`（main） | 59,101 | Agent=岗位说明书（role/goal/backstory）+ Task=工单 + Process 流程开关 |
| [03-browser-use.md](03-browser-use.md) | [browser-use/browser-use](https://github.com/browser-use/browser-use) | 浏览器 agent（环境特化型） | `4cbe921`（main） | 116,507 | DOM 序列化当眼睛 + 结构化动作当手 + 步数预算当缰绳 |

每册统一六节：**§1 定位与生态**（当日实抓数据）→ **§2 架构总览**（file:line 锚点，回源码验证）→ **§3 最小复现记录**（命令/输出/踩坑）→ **§4 与 01-08 六家对照**（编排/记忆/工具/护栏/可观测五维）→ **§5 精读清单**（必读/选读两级）→ **§6 FAQ + 上手清单**。

## 选型速览表（2026-09-28 当日实抓，GitHub API）

| 项目 | star | License | 最新 release | 最近 push | 近 60 天 commits | 维护判断 |
|---|---|---|---|---|---|---|
| camel-ai/camel | 17,784 | Apache-2.0 | v0.2.91a7 / 2026-09-03 | 2026-09-20 | 34 | 活跃（预发布节奏，生产固定 commit） |
| crewAIInc/crewAI | 59,101 | MIT | 1.15.22 / 2026-09-16 | 2026-09-27 | 100+（分页打满） | 活跃（周节奏发版） |
| browser-use/browser-use | 116,507 | MIT | 0.13.10 / 2026-09-04 | 2026-09-26 | 100+（分页打满） | 活跃 |
| ~~microsoft/autogen~~ | 61,188 | CC-BY-4.0 | python-v0.7.5 / **2025-09-30** | 2026-04-15 | — | **停止发版 12 个月，官方 Maintenance Mode** |
| microsoft/agent-framework（AutoGen 官方接班人） | 13,825 | MIT 系 | — | 2026-09-27 | — | 活跃 |
| ~~FoundationAgents/MetaGPT~~ | 70,658 | MIT 系 | v0.8.2 / **2025-03-09** | 2026-01-21 | — | 半停更（release 停 18 个月） |

> 附注：microsoft/autogen 仓库 API 返回 license 为 CC-BY-4.0（代码目录实际各包另有声明），与 multiagent-handbook §4.1 的当日实抓口径一致。

## ⚠️ 选型变更说明：AutoGen → camel-ai/camel

原计划第三家为 `microsoft/autogen`，2026-09-28 当日实抓触发替换条件（"已归档/停更超过 6 个月"）：

1. **停止发版 12 个月**：最后 release `python-v0.7.5`（2025-09-30）【实抓 releases API】；
2. **官方维护模式**：README 挂 Maintenance Mode 横幅，且最近的实质 commit（2026-04-06）就是"更新维护模式横幅"【实抓 commits API】；
3. **官方已指定接班人** [microsoft/agent-framework](https://github.com/microsoft/agent-framework)（当日实抓 13,825 star、pushed 2026-09-27，活跃）；
4. 替换候选逐一实抓：**MetaGPT 同样半停更**（最后 release 2025-03-09、最后 push 2026-01-21），**camel 是唯一活跃者**（9 月内两连发版）且赛道吻合（多 agent 会话/任务编排）——故选 camel。

这是工作区"框架选型必做归档/维护模式扫描"纪律的第三次实证（前两次：Flowise 归档见 [workflow-handbook §4.2.4](../workflow-handbook/Agent工作流编排手册.md)；Letta 主仓转壳见 [context-handbook](../context-handbook/Context与记忆系统手册.md)；AutoGen 维护模式首次记录见 [multiagent-handbook §4.1](../multiagent-handbook/Multi-Agent协同手册.md)）。

## 复现环境总说明（三家通用）

| 项 | 值 | 说明 |
|---|---|---|
| 宿主 | Windows 11（win32 10.0.26100 x64） | Git Bash shell |
| Python | 3.13.5（Anaconda，`D:\anaconda`） | 三家要求：camel ≥3.10,<3.15 ｜ crewai ≥3.10,<**3.14** ｜ browser-use ≥**3.11**,<4.0 |
| 包管理 | uv 0.12.5 | 三家均 `uv sync` 一次通过（按各自 uv.lock） |
| git 代理 | 全局 `http.proxy=127.0.0.1:7890` | clone/pull 时加 `-c http.proxy= -c https.proxy=` 绕过（本机直连可用），**不改全局配置** |
| LLM | 无海外 key | 当日可用：阿里百炼 `DASHSCOPE_API_KEY`（qwen-plus/turbo，OpenAI 兼容端点）→ **会话中途整账号 Arrearage（欠费）**；改用智谱 `glm-4-flash`（免费档）与 `DEEPSEEK_API_KEY`（deepseek-chat）完成剩余复现 |

三家复现的真实发生矩阵（全部真机、非文档级）：

| 册 | 模型 | 跑通内容 | 关键踩坑 |
|---|---|---|---|
| 01-camel | qwen-plus（百炼） | ChatAgent 工具调用；Workforce 双角色编排（自动分解 + 质量评分 92/95） | ① `ChatAgentResponse` 工具记录在 `.info["tool_calls"]`；② Workforce 必须传 `default_model` |
| 02-crewai | glm-4-flash（智谱） | sequential（含自定义工具）；hierarchical（Manager 自动委派） | ① 百炼 Arrearage 边界；② 实例 `.base_url` 显示 None 但请求正常；③ 运行结束 trace 分享交互提示要设 `CREWAI_DISABLE_TELEMETRY=true`；④ 模型名与端点三件套必须配套 |
| 03-browser-use | deepseek-chat（DeepSeek） | 真实 Chromium 三步完成"读网页标题"（DOM 文本模态） | ① 官方示例全是付费云端模型，开源路径自己换 provider；② 纯文本模型必须 `use_vision=False` |

复现脚本与说明存于 [`repro/`](repro/)：`camel_min.py`、`camel_workforce.py`、`crewai_min.py`、`crewai_hierarchical.py`、`browser_use_min.py`。仓库快照均 shallow clone 于各册同名子目录（`camel/`、`crewai/`、`browser-use/`），更新方式同工作区约定：`git -c http.proxy= -c https.proxy= -C <目录> pull --depth 1`。

## 与既有内容的关系

- **对照基准**：三家 §4 的"与 01-08 六家对照"全部引用六份《架构拆解》的既有章节结论（01 §3/§5/§7 ｜ 02 §3/§4.3/§5 ｜ 03 §4/§5/§8 ｜ 04 §5/§9/§10 ｜ 05 §4/§7/§9 ｜ 06 §4/§8/§10），不重复拆解六家源码；
- **范式坐标系**：三家的编排范式判定沿用 [multiagent-handbook §2](../multiagent-handbook/Multi-Agent协同手册.md) 六范式与 [workflow-handbook §1](../workflow-handbook/Agent工作流编排手册.md) 的"控制流在谁手里"第一性区分；
- **07/08 框架线的分工**：LangChain/LangGraph（07/08）讲"图引擎语义"，本专题讲"拿现成框架干活"——camel 的 TaskChannel 是黑板范式的框架实现（与 08 的共享 state 语义互补），crewai 的 Flow 与 workflow-handbook 五模式同构；
- **题材分工**：六家 harness 是"coding/助理 agent 怎么造"，browser-use 是"环境特化 agent 怎么造"——它是 05-openclaw `browser` 工具、Codex computer-use 同赛道里唯一"浏览器即整个世界"的样本。

## 学习路线建议

1. 先跑通 [03-browser-use.md](03-browser-use.md) §3（安装链路最顺、反馈最直观，半小时见真浏览器在动）；
2. 再读 [02-crewai.md](02-crewai.md)（编排面最薄，适合建立"角色/工单/流程"三概念）；
3. 最后读 [01-camel.md](01-camel.md)（编排面最厚，Workforce/TaskChannel 值得逐行精读，对照 08-langgraph 的共享 state 语义）；
4. 每册 §5 精读清单当打卡表，§6 上手清单半天走完一轮。

> 本文是 agent-study 工作区 **GitHub 开源 Agent 项目实战精读** 专题入口，与 01-08 源码仓（逐行拆解）、multiagent-handbook（范式判定）互补，全景见[根 README](../README.md)。
