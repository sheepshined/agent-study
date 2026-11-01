# Learn LangGraph —— 低层编排引擎的执行语义

> 献给想读懂 [langchain-ai/langgraph](../langgraph/)（`libs/langgraph/` 快照 `7daa3ab`）源码的人。十课，每课：**中文讲解 + 注释版可运行代码 + 图解 + 对照真实源码的精读锚点**。体例对标 [03-deepseek-harness/analysis_deepseek_harness](../../03-deepseek-harness/analysis_deepseek_harness/)；事实对齐本工作区的 [源码解析与学习路线](../源码解析与学习路线.md)（其行号锚点在本课程中已复核，偏移见下）。

## LangGraph 是什么，它特殊在哪

**Agency 来自模型，Agent 产品 = 模型 + Harness（框架/引擎）。** 本课程教你造这台引擎。

LangGraph 官方自述是"**低层编排框架与运行时**（low-level orchestration framework）"——它不做 agent 的产品决策，只把执行语义做死：

- **状态不在节点里，在通道（channel）里**：节点读一份快照、交一份增量，合并由键自己声明的 reducer 裁决（`channels/`）；
- **时间是拍（superstep）**：一拍内世界冻结，写入在拍尾统一合并并推进版本号，触发靠版本差分（BSP 模型，`pregel/main.py`）；
- **存档是拍的快照**：`channel_versions` + `versions_seen` + pending writes，所以能恢复、能分叉、能重跑（`libs/checkpoint/`）；
- **控制流可以冒泡**：`GraphInterrupt`（人在环）与 `ParentCommand`（跨图交接）同属 `GraphBubbleUp` 家族——停止本任务，把控制权交给上一层。

一句话立场：**给原语，不给观点。** 你因此能在它上面写出 `create_agent`（[07-langchain](../../07-langchain/analysis_langchain/) 的 s01）、supervisor 拓扑、map-reduce 工作流，也能写出一个 Codex 式的内核。

## 语言选型说明

LangGraph 本身是 Python 项目，本课程沿用 Claude Code 教材（[analysis_claude_code](../../01-claude-code/analysis_claude_code/)）与 [07-langchain 教材](../../07-langchain/analysis_langchain/README.md) 的先例：**全部 mini 实现用 Python 纯标准库**（dataclasses / typing / asyncio 可用），零 pip 依赖，`python code.py` 直跑、完全离线（模型一律由脚本化 Mock 扮演）。**不 import langgraph 本体**——课程目的是看懂语义并能在纸上推演，而不是复现 API：真实侧的 `Send`、`Command`、`BaseChannel`、`Checkpointer` 在每课的"对照真实源码"表里给出**包路径 + 行号**，读 mini 是为了建立心智模型，回源码是为了确认真相。

## 课程目录

| 课 | 主题 | 引擎层 | 核心不变量 |
|----|------|--------|-----------|
| [s01_state_reducer](s01_state_reducer/) | StateGraph 与 reducer | 状态面 | 节点不改历史，只交增量；合并规则写在键上，不写在引擎里 |
| [s02_superstep](s02_superstep/) | Pregel/BSP 超步 | 执行循环 | 一拍内世界冻结；写入在拍尾统一生效 |
| [s03_apply_writes](s03_apply_writes/) | apply_writes 与写冲突 | 合并面 | 同拍 N 份补丁按通道分组折叠；LastValue 收到两写即报错 |
| [s04_checkpoint](s04_checkpoint/) | Checkpoint 每拍必存 | 持久化面 | 快照 id 唯一且可排序；任意一拍都能被恢复 |
| [s05_time_travel](s05_time_travel/) | Time Travel | 时间面 | 历史是树；分叉不改写旧档，只长出新线 |
| [s06_interrupt](s06_interrupt/) | Interrupt / 人在环 | 人在环 | 恢复时节点**从头重跑**，副作用必须幂等 |
| [s07_subgraph](s07_subgraph/) | Subgraphs 嵌套图 | 组合面 | 子图状态隔离，同名键透传；失败边界按命名空间划 |
| [s08_send_mapreduce](s08_send_mapreduce/) | Send / Map-Reduce | 动态面 | map 在拍内（accept_push），reduce 在拍间（版本差分） |
| [s09_command](s09_command/) | Command 组合语义 | 控制面 | 一个返回值 = update 写通道 + goto 写 branch + resume 进 NULL 任务 + PARENT 冒泡 |
| [s10_capstone](s10_capstone/) | 整机与横向对照 | 整机 | 四条规则覆盖全部机制；环无出口与同拍双写必须报错 |

依赖关系是线性的：每课建立在前一课的概念上（但每课代码**自包含可独立运行**，跳读也不会断）。s01-s03 是"状态与拍"的地基，s04-s06 是"时间与人在环"，s07-s09 是"组合与动态控制流"，s10 收官总装。

## 运行

唯一前置：**Python ≥ 3.10**（仅标准库，无任何 pip 依赖）。逐课：

```bash
cd s01_state_reducer && python code.py
```

或一键全跑：

```bat
run.bat        :: Windows
./run.sh       :: Linux / macOS
```

十课全部离线、零依赖；`run.bat` / `run.sh` 只跑存在 `code.py` 的 `s*` 目录，一课失败即停并打出报错，全过打印 `All N lessons passed.`。

## 与本工作区其他材料的关系

- **先读什么**：没有 LangGraph 概念时，先看 [源码解析与学习路线](../源码解析与学习路线.md)（monorepo 地图 + 六阶段路线 + 附录 12 问）→ 再来逐课动手 → 最后按其阶段 4 的精读清单回真源码（[../langgraph/](../langgraph/)，快照 `7daa3ab`，引擎本体在 `libs/langgraph/langgraph/pregel/`）。
- **上一层**：`create_agent` 把声明编译成这张图——见 [07-langchain/analysis_langchain](../../07-langchain/analysis_langchain/README.md) 的 s01（编译器）/ s04（StateGraph 底座）/ s06（记忆与检查点）。两册体例一致，行号各自独立实测。
- **换立场对照**：[02-codex 教材](../../02-codex/analysis_codex/README.md)（内核服务化 + 审批×沙箱双轴，收官课有同题横向比较）、[03-deepseek-harness 教材](../../03-deepseek-harness/analysis_deepseek_harness/README.md)（一切皆插件）、[01-claude-code 教材](../../01-claude-code/analysis_claude_code/)（把循环写死）；终端产品三家 [04-zcode](../../04-zcode/analysis_zcode/README.md) / [05-openclaw](../../05-openclaw/analysis_openclaw/README.md) / [06-opencode](../../06-opencode/analysis_opencode/README.md)。
- **方法论延伸**：编排模式与最小引擎见 [Agent工作流编排手册](../../workflow-handbook/Agent工作流编排手册.md)（s02/s03/s08 的理论底座）；状态、记忆与压缩见 [Context与记忆系统手册](../../context-handbook/Context与记忆系统手册.md)（s04/s05/s06）；多智能体拓扑见 [Multi-Agent协同手册](../../multiagent-handbook/Multi-Agent协同手册.md)（s07/s09）；评测与回归见 [Agent评测与质量工程手册](../../eval-handbook/Agent评测与质量工程手册.md)。

## 免责与安全

本课程的全部代码是**教学用 mini 实现**：不 import langgraph / langchain / pydantic 等任何第三方库，不调用任何真实模型 API，模型一律由脚本化 Mock 扮演，不连接任何 checkpointer 后端（内存字典替身）。"对照真实源码"表中的包路径与行号在快照 `7daa3ab` 上以 `sed -n 'Np'` 逐条实测；**本仓带 `[中文导读]` 注释，`_algo.py`、`state.py` 等文件的行号比上游下移约 12 行**，且既有文档中的部分行号存在偏移——本课程一律采用实测值。上游版本演进后请以符号名为锚，行号只当路标。课程内容仅用于学习，不构成对 LangGraph API 的完整或最新描述。
