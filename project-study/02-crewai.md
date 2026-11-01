# CrewAI 精读：角色制 Crew 的"岗位说明书"范式

> 对象：`project-study/crewai/`（crewAIInc/crewAI 官方仓库快照，commit `4ed2abc`，main 分支）
> 信息基准日：**2026-09-28**。§1 全部数据当日经 GitHub API 实抓并标注来源；行号均指本快照，代码演进后以源码为准。
> 证据口径：`【实证】` = 本机读到的源码行或本机实跑输出；`【声称】` = 官方文档/README 叙述。
> 前置阅读：[01-camel.md](01-camel.md)（同专题姊妹篇，范式对照在 §4 互引）、[multiagent-handbook §2.1/§2.4](../multiagent-handbook/Multi-Agent协同手册.md)（supervisor 与 hierarchical 范式）。

---

## 0. TL;DR

CrewAI 是"角色制 crew（团队）编排"框架——把 agent 当**团队成员**建模：`Agent` = role/goal/backstory（角色/目标/背景故事）三件套的岗位说明书，`Task` = 带期望产出与 guardrail（护栏）的工单，`Crew` = 一群人 + 一列工单 + 一种协作流程（sequential/hierarchical，`process.py:5-13`【实证】）。核心循环极薄：`crew.kickoff()`（`crew.py:995`）→ `_execute_tasks`（`:1571`）按工单顺序把任务塞给每个 Agent 的执行器，执行器内部是 ReAct（推理-行动交替）或原生工具调用循环。

一句话记住：**CrewAI = 岗位说明书（Agent）+ 工单（Task/guardrail）+ 流程开关（Process）**——编排面最薄、提示词面最厚，是三家框架里"少写代码、多写人设"的极端。本册 §3 已在本机真机跑通 sequential 与 hierarchical 两种流程（GLM-4-Flash 实跑，含三个真实踩坑）。

---

## 1. 项目定位与生态

### 1.1 定位一句话

**CrewAI：角色驱动的多 agent 协作框架**——官方口号 "AI agent teams"。与 CAMEL 的"任务/黑板"相反，它把复杂度放在**人设与流程的提示词工程**上：你定义"谁、要什么、凭什么背景"，框架替你跑委派循环。

### 1.2 当日实抓数据（2026-09-28，GitHub API）

| 项目 | 数值 | 来源 |
|---|---|---|
| star | **59,101** | [api.github.com/repos/crewAIInc/crewAI](https://api.github.com/repos/crewAIInc/crewAI) |
| fork / open issues | 8,585 / 503 | 同上 |
| 语言 / 许可证 | Python / **MIT** | 同上 |
| 最新 release | **1.15.22**（2026-09-16）；此前 1.15.21（09-09）、1.15.20（09-04）——**周节奏发版** | [releases](https://github.com/crewAIInc/crewAI/releases) |
| 最近 push | 2026-09-27 | 同 API |
| 近 60 天 commits | 100+（当日实抓触及分页上限） | 同 API |
| 创建时间 | 2023-10-27 | 同 API |

**维护节奏**：当日实抓里三家最活跃（周发版 + 分页打满）。`multiagent-handbook §4.1`（2026-09-27 实抓 59.1k star）将其归为"角色制编排"代表。

### 1.3 仓库形态：1.x 已 monorepo 化【实证，本机实测目录】

```
crewai/ 仓库根
├── lib/
│   ├── crewai/          ★ 主包（pip install crewai；本精读主体）
│   │   └── src/crewai/  crew.py(2559行) agent/ agents/ tasks/ tools/ flow/ memory/ llms/ mcp/ a2a/ …
│   ├── crewai-core/     共享工具包（版本号/存储路径/telemetry/printer），README 自述
│   │                    "a leaf — no dependency on the crewai framework"【实证】
│   ├── crewai-cli/      crewai 命令行
│   ├── crewai-tools/    工具包生态（pip install crewai-tools）
│   └── devtools/        crewai 调试台
└── docs/                官方文档站源码
```

注意两点：① 主包依赖锁定 `crewai-core==1.15.22`、`crewai-cli==1.15.22`【实证 pyproject.toml】——三个包同步发版；② 主包**自带 `llms/` 原生多 provider 路由**（openai/anthropic/azure/gemini/bedrock/openai_compatible 等），已从"全靠 litellm"的旧印象中走出，但兼容层仍保留（`llm.py:457` 路由失败时提示安装 LiteLLM【实证】）。**requires-python >=3.10,<3.14**——3.13.5 本机可用，但 3.14 用户装不上【实证】。

### 1.4 生态位

企业教程生态最大（ Udemy/博客教程以它为多 agent 首选的最多，本工作区 [fde-handbook](../fde-handbook/FDE转行手册.md) 的选型材料多次出现）；与 LangChain 系的关系是"脱钩但在观感上被混淆"——`08-langgraph` 是图引擎，CrewAI 是角色编排，两者常被并列比较但抽象层不同（对照见 §4）。

---

## 2. 架构总览：三层薄壳 + 一个厚执行器

### 2.1 分层地图（本机实测）

```
┌──────────────────────────────────────────────────────────────────┐
│ Crew 编排层（src/crewai/crew.py:164，Crew(FlowTrackable, BaseModel)）│
│   kickoff(:995) → _execute_tasks(:1571)                           │
│   Process.sequential → 按任务顺序执行                              │
│   Process.hierarchical → _run_hierarchical_process(:1526)         │
│     └─ _create_manager_agent(:1531) 造 Manager（委托工具）         │
├──────────────────────────────────────────────────────────────────┤
│ Agent 执行层                                                       │
│   Agent (agent/core.py:218, BaseAgent :187)  岗位说明书 + 装配     │
│   CrewAgentExecutor (agents/crew_agent_executor.py:98)            │
│     ├─ _invoke_loop_react(:352)        文本 ReAct 循环（思-动-观）  │
│     ├─ _invoke_loop_native_tools(:505) 原生 function calling 循环  │
│     └─ max_iter 熔断检查（:365/:524/:1178/:1323 四处对称）          │
├──────────────────────────────────────────────────────────────────┤
│ LLM 路由层（llm.py:382 LLM.__new__）：模型名 → provider 路由       │
│   环境变量 OPENAI_API_BASE / OPENAI_BASE_URL【实证 :670-671】       │
├──────────────────────────────────────────────────────────────────┤
│ 横切面：memory/unified_memory.py ｜ Task.guardrail (task.py:252)   │
│         flow/ 事件驱动（@start :18 @listen :18 @router :97）        │
│         translations/ 多语言提示词 ｜ telemetry/ OTel + 自家埋点    │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Crew：编排面薄到只有两段

`Crew`（`crew.py:164`）继承 `FlowTrackable` 的 Pydantic 模型，验证器一长串（`validate_tasks` :770、`validate_end_with_at_most_one_async_task` :783 等【实证】）——**契约校验前置**是编排层的主要厚度。执行只有两段：

- **sequential**：`_execute_tasks`（`:1571`）按列表顺序遍历 Task；`async_execution=True` 的任务挂 Future，在下一个同步任务前收割（`:1610-1633`【实证】）；上下文 = 之前所有任务输出（`_get_context`）。
- **hierarchical**：`_run_hierarchical_process`（`:1526`）先 `_create_manager_agent`（`:1531`）——Manager 是一个普通 `Agent`，但工具被替换成 **DelegateWorkTool + AskQuestionTool**（`tools/agent_tools/agent_tools.py:16-43`【实证】，`AgentTools.tools()` 把成员角色的 role 名拼进工具 description），`allow_delegation=True`。**所谓"层级管理"= 一个拿到委派工具的 LLM**，与 [multiagent-handbook §2.1](../multiagent-handbook/Multi-Agent协同手册.md) 的 supervisor 范式一一对应；Manager 有自己的固定提示词（i18n 文件 `hierarchical_manager_agent` 三段【实证 crew.py:1549-1560】），且**禁止携带工具**（`:1543-1548` 检查后直接 raise【实证】）。

### 2.3 Agent 执行器：ReAct 与原生工具双循环

`CrewAgentExecutor`（`crew_agent_executor.py:98`）是一个 LangChain 风格的执行器（`invoke`/`ainvoke` :230/:1107【实证】），内部两条循环并存【实证，方法签名均本机核实】：

- `_invoke_loop_react`（`:352`）：经典的 Thought → Action → Action Input → Observation 文本协议，靠正则解析（`agents/parser.py`）——**模型不支持 function calling 时的兜底**，也是 crewAI 起家的协议；
- `_invoke_loop_native_tools`（`:505`）：原生 tool_calls 协议（`_handle_native_tool_calls` :687、单工具执行 `_execute_single_native_tool_call` :888）。

哪个模型用哪条路由，对用户基本透明；但**理解这两条循环对调试至关重要**——ReAct 模式的解析失败（模型输出格式漂移）是社区最常见的报错源，且两者对 `max_iter` 的熔断点对称分布在四处（`:365/:524/:1178/:1323`【实证】）。

### 2.4 护栏位：迭代熔断 + 任务级 guardrail + RPM

| 护栏 | 位置 | 语义 |
|---|---|---|
| `max_iter` | `agents/agent_builder/base_agent.py:286-288`，**默认 25**【实证】 | 单任务最大思考-行动轮次；超限时 `handle_max_iterations_exceeded` 强制收束（executor :365 等） |
| `max_execution_time` | `agent/core.py:258` + `:1004-1057` | 任务级超时，超时日志明说"Consider increasing max_execution_time"【实证】 |
| `max_rpm` | `agent/core.py:834` + `_rpm_controller` | 每分钟请求上限——**限流是 agent 属性**，六家里没有这种粒度（05-openclaw 的限流在网关层） |
| `Task.guardrail` | `task.py:252-261`【实证】 | 任务输出校验器（函数或 LLM 判据），不通过则重试/重派——把 [eval-handbook](../eval-handbook/Agent评测与质量工程手册.md) 的"结构化校验"做成编排原语 |
| `respect_context_window` | `agent/core.py:298` | 上下文超限自动摘要——与 CAMEL 的循环内摘要同思路 |

**设计取向判断**【本册结论】：CrewAI 的护栏全部是"**软护栏**"（轮次/时限/频次/输出校验），**没有执行层硬护栏**——无沙箱、无审批、无权限格子。六家 harness 的安全预算花在"agent 能碰什么"（01 §5 白名单三级、02 §5 双轴沙箱、05 §7 审批四绑定），CrewAI 花在"agent 别跑飞"（轮次与时限）。这与它的目标场景一致：企业内容生产/研究类任务，而非执行系统命令的 coding agent。

### 2.5 Flow：编排层的另一半（事件驱动）

`flow/flow.py:33` 的 `Flow` 是与 Crew 并列的第二种形态：`@start`（`dsl/_start.py:18`）/`@listen`（`dsl/_listen.py:18`）/`@router`（`dsl/_router.py:97`）装饰器把方法连成**事件驱动的状态机**——控制流写死在代码里，是 [workflow-handbook §1.1](../workflow-handbook/Agent工作流编排手册.md) "控制流在谁手里"第一性区分里的 workflow 一侧（Crew 是 agent 一侧）。**一个项目两种形态，按控制流归属选**——这与 Anthropic《Building Effective Agents》的建议同构。

---

## 3. 最小复现记录（本机真机，2026-09-28）

### 3.0 环境与模型底座

同 [01-camel.md §3.0](01-camel.md)：Windows 11 + Python 3.13.5 + uv 0.12.5。模型底座有一个**当日实况**：阿里百炼账户在本会话中途对所有模型返回 `Arrearage`（欠费/配额尽）【实证，curl 直连同报错】，故本册改用 **智谱 GLM（`glm-4-flash`，OpenAI 兼容端点 `https://open.bigmodel.cn/api/paas/v4`，当日实测免费可用）**。

### 3.1 clone + 安装

```bash
cd E:/hiagent/agent-study/project-study
git -c http.proxy= -c https.proxy= clone --depth 1 --branch main \
    https://github.com/crewAIInc/crewAI.git crewai          # → commit 4ed2abc
cd crewai && uv sync                                        # monorepo：主包+core+cli+tools 一次装齐
```

`uv sync` 一次通过（31 个依赖【实证 pyproject.toml】：openai、instructor、chromadb、pdfplumber、OTel 三件套等）。唯一的约束：`requires-python >=3.10,<3.14`，Python 3.13.5 恰好在内。

### 3.2 复现一：sequential Crew（真机跑通）

脚本 `../repro/crewai_min.py`：自定义 `CalculatorTool(BaseTool)` + 两个 Agent（研究员带工具、撰写人不带）+ 两个 Task + `Process.sequential`；模型接智谱（环境变量 + `llm="glm-4-flash"`）：

```bash
export $(grep ZHIPUAI_API_KEY E:/hiagent/.env | tr -d ' ' | xargs)
OPENAI_API_KEY="$ZHIPUAI_API_KEY" \
OPENAI_API_BASE="https://open.bigmodel.cn/api/paas/v4" \
uv run python ../repro/crewai_min.py
```

**实跑输出**【实证】：

```
=== 最终输出 ===
计算结果显示，该项目的成功率达到了42%。
```

数字 42 从工具调用链路真实传导到了最终总结——但注意这个输出同时是个 **badcase**：任务只是"计算 17+25"，writer 却把 42 写成"成功率"。**工具算对了，叙述自由发挥**——这正是 CrewAI "执行强、收束弱" characteristic 的活样本，也印证 [multiagent-handbook §6](../multiagent-handbook/Multi-Agent协同手册.md) 的 MAST 失败分类里"输出歪曲"一类。修法见 §6 FAQ Q2。

**踩坑 1（环境变量路由的"假象"）**：`LLM(model='glm-4-flash')` 实例的 `.base_url` 属性显示 `None`【实证】，但请求确实发到了智谱——原生 provider 在**客户端构造时**读取 `OPENAI_API_BASE`（`llms/providers/openai/completion.py:420-421`【实证】），不回填实例属性。**排查连通性时别信 `.base_url`，直接 `llm.call()` 打一发**。

**踩坑 2（trace 分享交互提示）**：跑完 Crew 会打印 "Share this execution trace with CrewAI? [y/N] (20s timeout)" 并**等待 20 秒**【实证】——CI/自动化场景必须设 `CREWAI_DISABLE_TELEMETRY=true`（本机 hierarchical 复现即带上）。

### 3.3 复现二：hierarchical Crew（真机跑通）

脚本 `../repro/crewai_hierarchical.py`：两个 worker（事实核查员/文案）+ `Process.hierarchical` + `manager_llm="glm-4-flash"`：

**实跑输出**【实证】：

```
=== 最终输出 ===
根据最新的数据，中国国土面积约为960万平方公里。
```

Manager 真实完成了"派活-收结果-汇总"循环（日志级 verbose=False 下仅见最终结果；verbose=True 时可看到 DelegateWork 调用轨迹）。**没有写一行编排代码**——这就是 §2.3 说的"Manager = 拿到委派工具的 LLM"。

**踩坑 3（模型名与端点必须配套）**：第一次跑智谱端点时脚本里残留 `llm="qwen-plus"`，智谱返回 `400 code 1211 模型不存在`【实证】。规则：**换 provider 时端点、key、模型名三件套必须一起换**——框架不会替你校验"这个模型在不在那个平台上"。

### 3.4 复现边界（如实记录）

- DashScope 账户 Arrearage 属账号侧状态（§3.0），Qwen 系列本机未能完成 crewAI 真机验证；camel 册的 Qwen 实证 + 本册 GLM/DeepSeek 实证合起来覆盖了"三家框架 × 三家国内模型"的矩阵；
- `crewai` 的 Flow 形态、memory（chromadb）、knowledge、enterprise features（plus_api）**未在本机复现**，仅源码级核实（§2.5）——如实标注，不做"云验证"。

---

## 4. 与 01-08 六家对照：角色制的取舍在哪

> 六家行号级证据出处同 [01-camel.md §4](01-camel.md)。

| 维度 | CrewAI 的选择 | 六家主流做法 | 谁走反方向 |
|---|---|---|---|
| 编排模型 | **流程开关**：sequential（固定顺序）/ hierarchical（Manager 委派）；另有 Flow 把控制流写死 | 主循环递归委派，模型自决定（01 §3 单循环、02 §3 回合制）；或黑板（见 01-camel） | CrewAI 反向：**编排是配置项不是程序**——一行 `Process.hierarchical` 切换全局协作形态 |
| 状态载体 | Task 输出链（`task_outputs` 列表 + Future 收割） | 会话流/事件日志为真源（03 §5、04 §10 事件溯源） | CrewAI 没有"会话"概念——Agent 之间不共享对话，只共享工单产出 |
| 记忆 | unified_memory（short-term/long-term/entity，chromadb 底座），Crew 级开关 `memory=True` | 文件/SQLite 自治体系（05 §8 五层记忆、04 三层预算） | CrewAI 把记忆外包给向量库产品，六家把记忆当数据结构自己写 |
| 工具协议 | `BaseTool._run` 子类化 + docstring description；ReAct 文本协议兜底 | JSON Schema 双轨 + MCP 一等公民（04/05） | CrewAI 是唯一把**纯文本协议当生产路径**保留的主流框架 |
| 护栏位 | **软护栏**：max_iter=25 / max_execution_time / max_rpm / Task.guardrail | **硬护栏**：审批+沙箱+权限（02 §5、05 §7.3） | 方向相反（§2.4 详述）：管"别跑飞" vs 管"别乱碰" |
| 可观测 | 自家事件总线（events/）+ OTel 导出 + trace 分享提示（§3.2 踩坑 2） | 日志即数据库（03/04/05） | CrewAI 的可观测是"产品化埋点"，六家是"基础设施" |

三条"谁抄谁的"判断：

1. **CrewAI 的 hierarchical 抄的是 OpenAI swarm/Claude 的 supervisor 老思路**（multiagent-handbook §2.1 的框架级实现之一），但它用"委派工具"而非"控制权移交"——Manager 不交出对话，只下工单收产出，这更像 05-openclaw 的 `sessions_spawn`（05 §9）；
2. **backstory 人格提示词是 prompt-handbook 的框架化**：role/goal/backstory 三件套本质是 [prompt-handbook](../prompt-handbook/提示词搭建文档.md) 八区块模板的"岗位说明书"切片——CrewAI 把提示词工程固化为类字段，六家把提示词当内部资产（prompt-handbook 拆解过的 OpenClaw 1340 行渲染器即其代表）；
3. **Task.guardrail 与 eval-handbook 的轨迹评测同宗**，但 CrewAI 把它放在**执行环内**（不通过就重试），六家放在环外（CI/回放评测）。

---

## 5. 精读清单（必读 → 选读）

### 必读（按顺序，约 900 行）

| # | 文件:行 | 阅读目标 |
|---|---|---|
| 1 | `src/crewai/process.py` 全文（13 行） | 整个框架的编排世界观就两个枚举值——先看最小的 |
| 2 | `src/crewai/crew.py:164-430` | Crew 字段与校验器：编排面契约 |
| 3 | `src/crewai/crew.py:995-1100` | kickoff 主入口：输入折叠 → 执行 → 输出 |
| 4 | `src/crewai/crew.py:1522-1640` | 两条执行路径 + `_execute_tasks`（Future 收割节奏） |
| 5 | `src/crewai/tools/agent_tools/agent_tools.py:1-43` | 43 行读懂 hierarchical 的全部秘密 |
| 6 | `src/crewai/agents/agent_builder/base_agent.py:187-310` | BaseAgent 字段面（max_iter 默认 25 在 ：286） |
| 7 | `src/crewai/task.py:120-290` | Task 与 guardrail、context（含 ConditionalTask 引用） |

### 选读

| # | 文件:行 | 阅读目标 |
|---|---|---|
| 8 | `src/crewai/agents/crew_agent_executor.py:98-360,352-660` | ReAct 与原生工具双循环逐段对照（调试报错必读） |
| 9 | `src/crewai/agent/core.py:218-400` | Agent 装配：llm/tools/memory/执行器缓存 |
| 10 | `src/crewai/llm.py:382-470,560-680` | 模型名路由规则与 OPENAI_API_BASE 读取点（§3.2 踩坑 1 出处） |
| 11 | `src/crewai/memory/unified_memory.py` | 记忆读写面（recall 在 :686） |
| 12 | `src/crewai/flow/dsl/_start.py:18 / _listen.py:18 / _router.py:97` + `flow/flow.py:33` | 事件驱动形态：装饰器语义 |
| 13 | `src/crewai/translations/`（hierarchical_manager_agent 三段） | Manager 的固定提示词原文——改委派行为从这里下手 |
| 14 | `src/crewai/utilities/guardrail.py` | guardrail 的处理管线 |

---

## 6. FAQ + 上手清单

### FAQ

**Q1 sequential 还是 hierarchical？**
工单有明确依赖顺序 → sequential（便宜、可预测）；任务需要"先理解再分派"的动态拆解 → hierarchical（多一层 Manager LLM 成本与失真）。判据同 [multiagent-handbook §1.2](../multiagent-handbook/Multi-Agent协同手册.md) 的成本-收益表：hierarchical 每个任务多 Manager 一跳。

**Q2 工具算对了、总结却在自由发挥，怎么治？**
本册 §3.2 的 "42% 成功率" badcase 三连修：① 给收尾 Task 的 `description` 写死"只转述上一任务给出的数字，不得改述"；② 挂 `Task.guardrail` 校验输出含目标数字；③ 给 `expected_output` 一个模板。根因：crewAI 的上下文传递是"把上一任务输出塞进提示词"，**收尾任务的自由度没有约束**。

**Q3 max_iter=25 是不是烧钱机器？**
是它的设计假设（ReAct 模式每轮一调用）。纪律：给每个 Agent 显式设 `max_iter`（简单任务 5-8 足够），并配 `max_execution_time`；`verbose=True` 观察实际轮次再收紧——这套动作就是 [tuning-handbook §7](../tuning-handbook/Agent调优手册.md) 的延迟预算分解。

**Q4 国内模型怎么接？**
OpenAI 兼容两件套：环境变量 `OPENAI_API_KEY` + `OPENAI_API_BASE`（或 `OPENAI_BASE_URL`），`llm="glm-4-flash"` / `llm="deepseek-chat"` 直传。坑：实例 `.base_url` 属性可能是 `None` 但请求正常（§3.2 踩坑 1）；换 provider 记得模型名一起换（§3.3 踩坑 3）。

**Q5 backstory 真的有用吗？**
有证据地有用：它决定 Manager 委派给谁（DelegateWork 按 role 名匹配【实证 agent_tools.py:26-33 把 role 拼进 description】）——所以 **role 命名要写成可检索的职责词**，backstory 写"能力边界"比写"性格故事"更影响行为。性格叙事的边际收益低，见 [tuning-handbook §2](../tuning-handbook/Agent调优手册.md) 的 few-shot 与人设实证边界。

**Q6 telemetry 能全关吗？**
能：`CREWAI_DISABLE_TELEMETRY=true`。它默认上传匿名使用数据并在运行结束弹 trace 分享确认（§3.2 踩坑 2）。合规敏感环境首日就关。

**Q7 Crew 和 Flow 什么时候分家？**
控制流可写死就 Flow（`@start/@listen/@router`，代码即图）；要让模型自己决定分工才 Crew。两者同仓共存（§2.5），混用时 Flow 节点内嵌 `Crew.kickoff()` 是官方推荐姿势【声称，官方文档；本机未复现】。

**Q8 为什么网上教程说它"依赖 LangChain"？**
旧版本执行器兼容 LangChain 工具（社区教程写作背景），当前 1.x 的执行器已内置化、LLM 路由自研（§1.3）。读 2024-2025 年教程时注意 API 已换代——与 07-langchain 册的 "0.x 教程已过时" 提示同理。

### 上手清单（半天走完）

1. `uv sync` 装依赖，接一个 OpenAI 兼容端点（10 分钟）；
2. 跑 §3.2 sequential 双任务，故意把 writer 的 description 写模糊，观察 badcase（30 分钟）；
3. 按 Q2 三连修重跑，验证 guardrail 生效（30 分钟）；
4. 跑 §3.3 hierarchical，verbose=True 盯 Manager 的 DelegateWork 轨迹（30 分钟）；
5. 给每个 Agent 设 max_iter/max_execution_time，用 verbose 日志数轮次（20 分钟）；
6. 写一个 `BaseTool` 子类挂给第二个 Agent，让 hierarchical Manager 真实委派工具调用（1 小时）；
7. 精读清单 #1-#7 过一遍，把 2-6 步的每个现象对应到代码行（1 小时）。

---

> 交叉引用：supervisor/hierarchical 范式判据见 [multiagent-handbook §2.1/§2.4](../multiagent-handbook/Multi-Agent协同手册.md)；MAST 输出歪曲与失败治理见其 §6；guardrail 与评测闭环见 [eval-handbook](../eval-handbook/Agent评测与质量工程手册.md)；人设提示词写法见 [prompt-handbook](../prompt-handbook/提示词搭建文档.md)。同专题姊妹篇：[01-camel.md](01-camel.md)（黑板任务编排）、[03-browser-use.md](03-browser-use.md)（浏览器 agent）。
