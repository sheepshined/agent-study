# CAMEL 精读：多 Agent 会话编排的"任务频道"范式

> 对象：`project-study/camel/`（camel-ai/camel 官方仓库快照，commit `fc27907`，master 分支）
> 信息基准日：**2026-09-28**。§1 全部数据当日经 GitHub API 实抓并标注来源；行号均指本快照，代码演进后以源码为准。
> 证据口径（沿用 05-openclaw 约定）：`【实证】` = 本机读到的源码行或本机实跑输出；`【声称】` = 官方文档/README 的叙述。
> 术语首现标中文。前置阅读：[multiagent-handbook §2](../multiagent-handbook/Multi-Agent协同手册.md)（六种编排范式）、[workflow-handbook §4.3](../workflow-handbook/Agent工作流编排手册.md)（"归档/维护模式扫描"纪律）。

---

## 0. TL;DR

CAMEL 是"科研出身的多 agent 会话编排框架"——它的论文叙事是 *Communicative Agents for "Mind" Exploration of Large Language Model Society*（寻找协作 agent 的 scaling law，Scaling Law）。核心三件事：

1. **一个 Agent 一条循环**：`ChatAgent`（`camel/agents/chat_agent.py:376`，单文件 6544 行）把模型调用、工具执行、记忆、上下文摘要、人在环工具、终止器全部装进一个类；
2. **任务是一棵树**：`Task`（`camel/tasks/task.py:216`）可 `decompose()` 分解成子树（`:408`）、`compose()` 汇总（`:579`）；
3. **编排靠"任务频道"**：`Workforce`（`camel/societies/workforce/workforce.py:176`）把任务投递到 `TaskChannel`（`task_channel.py:85`），worker 领任务、交任务，协调 agent 自动分解、评质量分、处理失败——这是 **blackboard（黑板）范式**的框架级实现（[multiagent-handbook §2.5](../multiagent-handbook/Multi-Agent协同手册.md)）。

一句话记住：**CAMEL = ChatAgent（大一统会话循环）+ Task（可分解任务树）+ Workforce/TaskChannel（黑板式任务编排）**。本册 §3 已在本机真机跑通单 agent 工具调用与 Workforce 三角色编排（Qwen 实跑，含完整踩坑记录）。

---

## 1. 项目定位与生态

### 1.1 定位一句话

**CAMEL（Communicative Agents for "Mind" Exploration of Large Language Model Society，大模型社会的"心智"探索通信 agent）**：以"多 agent 对话"为核心原语的研究型框架，从论文项目长成生态——上层有 OWL（通用 agent 应用）与 Eigent 等衍生应用，`pyproject.toml` 的 extras 里直接挂着 `owl`、`eigent`【实证】。

### 1.2 当日实抓数据（2026-09-28，GitHub API）

| 项目 | 数值 | 来源 |
|---|---|---|
| star | **17,784** | [api.github.com/repos/camel-ai/camel](https://api.github.com/repos/camel-ai/camel) |
| fork / open issues | 2,097 / 519 | 同上 |
| 语言 / 许可证 | Python / **Apache-2.0** | 同上 |
| 最新 release | **v0.2.91a7**（2026-09-03 发布，预发布节奏 a7 后缀） | [releases](https://github.com/camel-ai/camel/releases) |
| 最近 push | 2026-09-20 | 同 API |
| 近 60 天 commits | 34（本会话当日实抓计数） | 同 API |
| 创建时间 | 2023-03-17 | 同 API |
| PyPI 包名 / 版本 | `camel-ai` / 0.2.91a7（与仓库同步） | 仓库 `pyproject.toml:project.version`【实证】 |

**维护节奏**：活跃（月内仍在发版），但 release 走"预发布后缀"（`0.2.91a7`），不是严格语义化的稳定版节奏——生产采用前固定 commit。

### 1.3 它与本工作区坐标系的关系

- **赛道**：多 agent 会话/任务编排，与 `07-langchain`/`08-langgraph` 的"框架线"同属 Python，但**不依赖 LangChain**【实证：`pyproject.toml` 依赖表无 langchain 系】，模型/消息/工具三层全部自研抽象；
- **生态位对照**：[multiagent-handbook §4.1](../multiagent-handbook/Multi-Agent协同手册.md) 的九家横评（2026-09-27 实抓）把 CAMEL 归在"研究型多 agent 协作"一档，与 CrewAI（角色制）、AutoGen（会话制）并列；
- **读法**：01-08 八家是"逐行拆解生产级 harness"，本册（及本专题三册）是"上手复现 + 设计对照"——CAMEL 的代码量与工程密度远低于六家 harness，**一两天能读穿主干**，正适合补"自己动手"这一课。

### 1.4 ⚠️ 本册替换了任务单里的 AutoGen——替换理由与证据链

原计划精读 `microsoft/autogen`，2026-09-28 当日实抓触发替换条件（"已归档/停更超过 6 个月"）：

| 证据 | AutoGen 当日实抓值 | 结论 |
|---|---|---|
| 最后 release | **python-v0.7.5，2025-09-30**（距今 12 个月） | 停止发版超 6 个月 ✅ 触发 |
| 最近 commits | 2026-03-26（安全 fix）、2026-04-06（**更新维护模式横幅**） | 收尾维护，无功能开发 |
| 官方状态 | README 挂 Maintenance Mode | 已在 [multiagent-handbook §4.1](../multiagent-handbook/Multi-Agent协同手册.md) 记录 |
| 官方接班人 | `microsoft/agent-framework`（当日实抓 13,825 star，pushed 2026-09-27，活跃） | 新项目应直接选接班人 |

两个候选替换对象当日实抓对比：**MetaGPT**（FoundationAgents/MetaGPT，70,658 star）最后 release **v0.8.2 于 2025-03-09**、最后 push **2026-01-21**——同样半停更，选它违背替换初衷；**camel-ai/camel**（17,784 star，pushed 2026-09-20，9 月内两连发版）是唯一活跃者，且赛道吻合（同属"多 agent 会话/任务编排"）。

> 这条纪律的第三次验证：Flowise 归档（workflow-handbook §4.2.4）→ Letta 主仓转壳（context-handbook）→ AutoGen 停发版 + MetaGPT 放缓（本册）。**"star 高"与"活着"是两回事，选型前必做归档扫描。**

---

## 2. 架构总览：模型层 → Agent 层 → 编排层

### 2.1 分层地图（本机实测）

```
┌────────────────────────────────────────────────────────────────┐
│ 编排层 societies/                                               │
│   Workforce (workforce.py:176)        黑板式任务编排             │
│     ├─ TaskChannel (task_channel.py:85)   任务投递/领取/归还     │
│     ├─ coordinator/task/new_worker 三个内部 ChatAgent           │
│     └─ workers: SingleAgentWorker / RolePlayingWorker / 子 Workforce │
│   RolePlaying (role_playing.py:36)     双 agent 角色对训         │
├────────────────────────────────────────────────────────────────┤
│ 任务层 tasks/task.py                                            │
│   Task (task.py:216) 可分解任务树 + TaskManager (:627) 拓扑排序 │
├────────────────────────────────────────────────────────────────┤
│ Agent 层 agents/chat_agent.py (6544 行，单文件)                  │
│   ChatAgent (:376)：循环 + 工具 + 记忆 + 摘要 + 人在环 + 终止器  │
├────────────────────────────────────────────────────────────────┤
│ 支撑层                                                          │
│   messages/base.py:55 BaseMessage ｜ memories/agent_memories.py │
│   toolkits/function_tool.py:529 FunctionTool (docstring→schema) │
│   models/model_factory.py:71 ModelFactory（平台路由）           │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 ChatAgent：一个类装下一条完整 agent 循环

`ChatAgent`（`camel/agents/chat_agent.py:376`）的构造器在 `:490`，`max_iteration` 存到 `:636`。单步执行的同步实现在 `_step_impl`（`:2959`），主干是一个 `while True`（`:3015`）：

```python
# camel/agents/chat_agent.py:3015 起的主干（摘要，行号为快照实测）【实证】
while True:
    # ① 组上下文：记忆 → OpenAI 消息序列；超出 token 限额时先摘要再压缩
    openai_messages, num_tokens = self._get_context_with_summarization()   # :3026
    # ② 调模型（工具 schema 一并下发；若"来自 RegisteredAgentToolkit"则禁工具）
    response = self._get_model_response(...)                               # :3035
    # ③ 模型要调工具：分"内部工具"与"外部工具"
    if tool_call_requests := response.tool_call_requests:                  # :3077
        for tool_call_request in internal_tool_requests:                   # :3104
            result = self._execute_tool(tool_call_request)                 # :3114
        if external_tool_call_requests: break                              # :3118 人在环：交回调用方
        if iteration_count >= self.max_iteration: break                    # :3121-3126
        continue
    # ④ 不调工具但有终止器：没到终止条件就注入 "Please continue." 让模型接着干
    if self.response_terminators:                                          # :3131
        ...continue                                                        # :3165
    break
```

四个 CAMEL 特有设计，值得与六家 harness 对照：

1. **内外工具二分 = 框架级人在环**（`:3078-3119`）：模型请求调用的工具若不在本地工具表、而在 `_external_tool_schemas` 里，`step()` 直接返回并把请求交给调用方（宿主应用）执行【实证】。六家 harness 的审批发生在"执行前"（Codex 审批→沙箱→执行，02 §5）；CAMEL 把它做成"框架交还控制权"，护栏位在**应用层**。
2. **Terminator（终止器）**（`:3131-3165`）：不是模型说"完了就完了"，而是显式 `response_terminators` 逐个判定；未终止就注入固定续跑消息。对照：六家的循环退出条件是"模型不再发工具调用"或用户打断，**没有"任务完成判据"这个抽象**。
3. **上下文摘要内建**（`:3026` → `_get_context_with_summarization` :1032）：超阈值自动摘要并写回记忆（`_update_memory_with_summary` :1146），阈值自适应（`_calculate_next_summary_threshold` :1104）。与 [context-handbook §2](../context-handbook/Context与记忆系统手册.md) 的"剪枝先于摘要"同族，但 CAMEL 是**摘要驱动的记忆更新**。
4. **工具结果记忆清洗**（`:3184-3185`）：`prune_tool_calls_from_memory` 开启时 `memory.clean_tool_calls()`——工具噪音不进长期上下文。

### 2.3 消息 / 记忆 / 工具三件套

| 抽象 | 位置 | 一句话 |
|---|---|---|
| `BaseMessage` | `camel/messages/base.py:55` | role_name/role_type/content/meta_dict 五元组，`AgentMessage` 继承它带 `video_bytes/images`【实证】 |
| `AgentMemory` | `camel/memories/base.py`（抽象）+ `agent_memories.py` | 三实现：`ChatHistoryMemory`（:26，对话史）、`VectorDBMemory`（:151，向量检索式）、`SummaryMemory`（摘要式）——**记忆是可替换策略**，构造器注入 |
| `FunctionTool` | `camel/toolkits/function_tool.py:529` | **从函数 docstring 生成工具 schema**：`get_openai_tool_schema()`（:804）+ 模块级 `get_openai_tool_schema(func)`（:228）；docstring 缺失直接影响模型调用质量——写 CAMEL 工具先写文档 |
| `ModelFactory` | `camel/models/model_factory.py:71` | 平台枚举 → 具体后端；`OPENAI_COMPATIBLE_MODEL` 路由到 `OpenAICompatibleModel`（`openai_compatible_model.py:73`）——本机接 DashScope/智谱全靠它【实证，见 §3】 |

### 2.4 Task 与 Workforce：黑板范式如何落地

**Task**（`camel/tasks/task.py:216`，Pydantic 模型）自带 `id/content/state/result/subtasks`；`decompose()`（`:408`）调模型把任务拆成子树（流式解析部分结果 `:550`），`compose()`（`:579`）自底向上汇总；`TaskManager`（`:627`）负责 ID 生成、当前任务指针与**拓扑排序**（`topological_sort` :660）。

**Workforce**（`workforce.py:176`，继承 `BaseNode`）两种模式【实证 `WorkforceMode` :142-146】：`AUTO_DECOMPOSE`（自动分解）与 `PIPELINE`（预定义流水线，`pipeline_add/fork/join/build` :886-1157）。三种处理路径：`_process_task_with_pipeline`（:2714）、`_process_task_with_snapshot`（:2873，带快照续跑）、`_process_task_with_intervention`（:2903，人工介入）。

主循环 `start()`（`:5822`）→ `await self._listen_to_channel()`（`:5834`），真正的编排心脏在 `_listen_to_channel`（`:5282`）：

```python
# workforce.py:5282 起【实证】
while (self._task is None or self._pending_tasks or self._in_flight_tasks > 0) \
        and not self._stop_requested:                    # :5294 退出条件
    await self._pause_event.wait()                        # :5302 支持暂停
    if self._pending_tasks and self._in_flight_tasks == 0:
        if next_task.additional_info.get('_needs_decomposition'):
            await self.handle_decompose_append_task(...)  # :5347 调协调 agent 分解
            await self._handle_completed_task(next_task)  # :5353
    if self._pending_tasks:                               # :5378 节流快照（断点续跑）
        if time.time() - self._last_snapshot_time >= self.snapshot_interval:
            self.save_snapshot(...)                       # :5386
    returned_task = await self._get_returned_task()       # :5393 收 worker 的归还
    await self._post_ready_tasks()                        # 再投递
```

`TaskChannel`（`task_channel.py:85`）是黑板本体：`post_task`（:203）挂任务、`get_assigned_task_by_assignee`（:174）worker 领取、`return_task`（:228）/`archive_task`（:242）回写。**agent 之间从不直接通信，一切经任务频道**——对照 [08-langgraph](../08-langgraph/源码解析与学习路线.md)：LangGraph 用"共享 state + 版本号"对齐节点，CAMEL 用"任务对象 + 状态机"对齐 worker，两者都是"消息只是通知，状态才是真源"（multiagent-handbook §2.5 的 blackboard 判据）。

**质量评分**【实证：本节复现输出出现 `quality score: 92`】：协调 agent 用结构化输出评价子任务，`structured_output_handler.py:255-269` 正则抽 `quality_score`，`prompts.py:335` 规定 **< 60 即不合格、触发恢复策略**——CAMEL 把"质量护栏"做进了编排循环，这是六家 harness 没有的原语（六家的质量保障靠权限/审批/评测，见 [eval-handbook](../eval-handbook/Agent评测与质量工程手册.md)）。

---

## 3. 最小复现记录（本机真机，2026-09-28）

### 3.0 环境与模型底座

- Windows 11（win32 10.0.26100）｜ Python **3.13.5**（Anaconda）｜ **uv 0.12.5** ｜ git 2.54.0（全局配置 `http.proxy=127.0.0.1:7890`，本机直连 GitHub 可用，clone 时加 `-c http.proxy= -c https.proxy=` 绕过，沿用工作区 README 约定）
- **LLM**：无 OpenAI/Anthropic key；用 `DASHSCOPE_API_KEY`（阿里云百炼，OpenAI 兼容端点 `https://dashscope.aliyuncs.com/compatible-mode/v1`，模型 `qwen-plus`）当日实测可用

### 3.1 clone + 安装

```bash
cd E:/hiagent/agent-study/project-study
git -c http.proxy= -c https.proxy= clone --depth 1 --branch master \
    https://github.com/camel-ai/camel.git camel          # → commit fc27907
cd camel && uv sync                                      # 按 uv.lock 装核心依赖
```

`uv sync` 一次通过，核心依赖 14 个（openai、pydantic、mcp、httpx、tiktoken 等【实证 pyproject.toml】），无编译坑。**注意 `requires-python >=3.10,<3.15`**，Python 3.13.5 在范围内。

### 3.2 复现一：ChatAgent 工具调用（真机跑通）

脚本 `../repro/camel_min.py`（要点：`ModelPlatformType.OPENAI_COMPATIBLE_MODEL` + `url` + `api_key` 三参直连百炼；工具用 `FunctionTool(add)`）：

```python
model = ModelFactory.create(
    model_platform=ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
    model_type="qwen-plus",
    url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=os.environ["DASHSCOPE_API_KEY"],
)
agent = ChatAgent(system_message="你是精确计算助手，算术必须调用工具完成。",
                  model=model, tools=[FunctionTool(add)])
resp = agent.step("请计算 17 加 25 等于多少？")
```

**实跑输出**【实证】：

```
=== 最终回答 ===
17 加 25 等于 42。
=== 工具调用记录 ===
Tool Execution: add
	Args: {'a': 17, 'b': 25}
	Result: 42
```

**踩坑 1**：`ChatAgentResponse` 没有 `.tool_calls` 属性，第一版脚本 `AttributeError`。真相：工具记录在 `resp.info["tool_calls"]`，`ChatAgentResponse` 是 `msgs/terminated/info` 三字段 Pydantic 模型（`camel/responses/agent_responses.py:21-37`【实证】）。

### 3.3 复现二：Workforce 多角色编排（真机跑通）

脚本 `../repro/camel_workforce.py`：一个 Workforce + 两个 ChatAgent worker（调研员/计划者），任务"为周末一日游收集两个候选地点事实并给出最终推荐"：

```python
workforce = Workforce("旅行规划小队", default_model=make_model())
workforce.add_single_agent_worker("调研员：收集目的地信息", researcher)
workforce.add_single_agent_worker("计划者：输出最终建议", planner)
result = workforce.process_task(Task(content="..."))
```

**实跑输出摘录**【实证】：协调 agent 自动把主任务分解为 3 个子任务（周庄事实 → 同里事实 → 对比推荐），worker 逐个领任务、交回，日志可见编排全过程与质量评分：

```
Task 5cbcd479-…1 completed successfully (quality score: 92).
Worker node 7a9fb69f-… (计划者：输出最终建议) get task 5cbcd479-…3: Compare the two
water towns… Output a final recommendation …
Task 5cbcd479-…3 completed successfully (quality score: 95).
=== 最终结果 ===
--- Subtask ….1 Result --- （周庄事实清单）
--- Subtask ….2 Result --- （同里事实清单）
--- Subtask ….3 Result --- Recommended: Tongli. …
```

这正是 §2.4 描述的分解→投递→领取→归还→汇总全链路在真机上的样子。

**踩坑 2**：`Workforce("旅行规划小队")` 不传模型直接炸——`ValueError: Missing or empty required API keys in environment variables: OPENAI_API_KEY`。真相【实证，traceback 指向 workforce.py:418】：Workforce 内部的 coordinator/task/new_worker 三个 ChatAgent 默认按 `ModelPlatformType.DEFAULT`（openai）创建。**解法：`Workforce(..., default_model=make_model())`**——编排器自己的"大脑"也要显式指定模型。

### 3.4 复现边界（如实记录）

- 本仓库 `examples/workforce/` 官方示例多数依赖 `SearchToolkit`（需搜索 API key）；本机无 key，故改写为无搜索依赖的等价任务，**编排链路本身未经删减**；
- 当日会话后半段，该百炼账户对所有模型返回 `Arrearage`（欠费/配额尽）【实证，curl 与 crewai 请求同报错】，后续 crewAI/browser-use 两册改用智谱 GLM 与 DeepSeek——CAMEL 部分全部调用发生在欠费之前，均真实成功。这也顺手实证了 multiagent-handbook §1.2 的成本判断：**一次 Workforce 分解+执行就是几十次模型调用**，免费/低额度账户跑编排示例要盯着余额。

---

## 4. 与 01-08 六家对照：CAMEL 的取舍在哪

> 六家行号级证据出自各自《架构拆解》：01-claude-code §3/§5/§7、02-codex §3/§4.3/§5、03-deepseek-harness §4/§5/§8、04-zcode §5/§9/§10、05-openclaw §4/§7/§9、06-opencode §4/§8/§10；子代理章节映射见 multiagent-handbook §3。

| 维度 | CAMEL 的选择 | 六家主流做法 | 谁走反方向 |
|---|---|---|---|
| 编排模型 | **黑板**：TaskChannel 任务板 + worker 领取归还；agent 互不通信 | 六家全是 **supervisor**（主循环递归委派，worker 只向调用方汇报：01 §7 Task 工具、05 §9 sessions_spawn） | CAMEL 反向：状态在频道，消息只是任务对象 |
| 状态载体 | `Task` 对象树（Pydantic，可 decompose/compose/快照） | 会话消息流为真源（05 §8"日志为真源，压缩只改投影"；04 事件溯源 SQLite） | CAMEL 把"任务"提升为一等持久物，六家只有"会话" |
| 记忆 | 构造器注入式策略（ChatHistory/VectorDB/Summary 三选一）+ 循环内自动摘要 | 手搓上下文预算与压缩（01 §6、04 §8 三层预算） | CAMEL 是"策略注入"，六家是"预算工程" |
| 工具协议 | docstring → OpenAI schema（`get_openai_tool_schema`）；工具=函数 | 双轨 schema/TypeBox/Effect 注册表（04/05/06）；MCP 一等公民 | CAMEL 最简——没有任何注册表/收窄流水线 |
| 护栏位 | **任务层**：max_iteration + Terminator + quality_score<60 触发恢复 + 人在环 external tools | **执行层**：审批绑定 argv/cwd/哈希（05 §7.3）、内核级沙箱（02 §5）、权限格子（04 §7） | 方向相反：CAMEL 假设环境可信，管"任务做没做完"；六家假设环境危险，管"agent 能不能碰" |
| 可观测 | langfuse 集成点内建（`astep` 挂 `@observe()` 装饰器、agent_id 作 session_id【实证 chat_agent.py:2970-2976】）+ workforce_logger | 事件溯源/审计/OTel（03/04/05） | CAMEL 把可观测做成"挂钩子"，六家做成"日志即数据库" |

三条"谁抄谁的"判断（基于机制相似度，非代码血缘）：

1. **CAMEL ↔ LangGraph 同走 blackboard**：TaskChannel 之于 worker，等于共享 state 之于节点——但 CAMEL 的黑板上是"任务"而 LangGraph 的黑板上是"数据"；
2. **CAMEL 的 external tools 抄了 OpenAI 的思路、走了应用层**：把"工具调用请求交还宿主"做成返回值语义，与六家"审批后框架自己执行"不同；
3. **quality_score 是六家没抄也没走的第三条路**：六家管"允许做什么"（权限），CAMEL 管"做得好不好"（质量门）——它更像 [eval-handbook](../eval-handbook/Agent评测与质量工程手册.md) 的在线化。

---

## 5. 精读清单（必读 → 选读）

### 必读（按顺序，约 1200 行）

| # | 文件:行 | 阅读目标 |
|---|---|---|
| 1 | `camel/agents/chat_agent.py:376-666` | ChatAgent 构造面：model/tools/memory/token_limit 怎么装配成"一个 agent" |
| 2 | `camel/agents/chat_agent.py:2959-3195` | `_step_impl` 主循环：上下文→模型→工具分流→终止器→记忆清洗，一屏读完一条 agent 生命周期 |
| 3 | `camel/responses/agent_responses.py:21-43` + `camel/types/agents/tool_calling_record.py:19-40` | 返回面契约：msgs/terminated/info 与工具调用记录（§3 踩坑 1 的出处） |
| 4 | `camel/tasks/task.py:216-290,408-460,579-620` | Task 树：decompose/compose 的数据流 |
| 5 | `camel/societies/workforce/task_channel.py:45-100,203-260` | 黑板本体：Packet 状态机 + post/assign/return/archive 四原语 |
| 6 | `camel/societies/workforce/workforce.py:5282-5420` | `_listen_to_channel`：黑板范式在真实代码里长什么样 |

### 选读（按兴趣）

| # | 文件:行 | 阅读目标 |
|---|---|---|
| 7 | `camel/toolkits/function_tool.py:228-330,529-620` | docstring→schema 的生成细节；写自己的工具前必读 |
| 8 | `camel/memories/agent_memories.py:26-90,151-200` | 三种记忆策略的实现差异 |
| 9 | `camel/messages/base.py:55-120` | BaseMessage 与 meta_dict 的开放扩展点 |
| 10 | `camel/societies/role_playing.py:36-200` | CAMEL 出道原语：双 agent 角色对训（inception prompting） |
| 11 | `camel/societies/workforce/workforce.py:1549-1650` | 分解提示词怎么写（对照 prompt-handbook 八区块） |
| 12 | `camel/societies/workforce/structured_output_handler.py:255-269` + `prompts.py:335-368` | quality_score 抽取与 <60 失败门 |
| 13 | `camel/models/model_factory.py:131-240` + `openai_compatible_model.py:73-120` | 平台路由；接私有模型时的正确姿势 |
| 14 | `examples/workforce/multiple_single_agents.py` | 官方编排示例（对照 §3 复现脚本的删改处） |

---

## 6. FAQ + 上手清单

### FAQ

**Q1 CAMEL 与 LangGraph 怎么选？**
做"节点/数据流"的确定性编排选 LangGraph（08 册：图语义/checkpoint/interrupt 语义完备）；做"任务分解 + 角色协作"选 CAMEL。CAMEL 的 TaskChannel 只懂任务，LangGraph 的 StateGraph 只懂数据——两者甚至可以嵌套（一个子任务节点内部跑一个 LangGraph 图）。

**Q2 为什么所有东西都塞在 `chat_agent.py` 一个 6544 行的类里？**
取舍使然：CAMEL 把"会话"当唯一原语，流式/异步/摘要/人在环都是这条会话的变体。好处是主干一屏可读（§2.2 的 4 步）；代价是改一行要面对全类状态耦合——学习时认准方法名跳，别按行号顺序读。

**Q3 external tools 到底是什么？**
`step()` 遇到不在本地工具表、而在 external 集合里的调用请求时，**不执行、直接返回请求**（chat_agent.py:3118 `break`），由宿主应用决定执行并回填。适合"工具执行权在别处"的集成（比如浏览器/数据库在宿主进程）。对照六家：这是把审批权上移到应用层。

**Q4 quality score 从哪来、低于 60 会怎样？**
协调 agent 用结构化输出打分（structured_output_handler.py:255 抽取），`prompts.py:335` 规定 <60 判不合格并触发恢复策略（重派/重新分解）。本机复现看到 92/95 的真实打分。

**Q5 没有海外 key 怎么跑？**
`ModelPlatformType.OPENAI_COMPATIBLE_MODEL` + 任意 OpenAI 兼容端点（本册实证：阿里百炼；智谱 `https://open.bigmodel.cn/api/paas/v4` 同理）。注意 §3.4 的 Arrearage 教训。

**Q6 成本有什么坑？**
Workforce 一次 `process_task` = 分解（1-2 次调用）+ 每子任务（worker 执行 ≥1 次 + 协调评分 ≥1 次）+ compose——N 个子任务约 2N+3 次起。给 coordinator/task agent 传 `default_model` 时可用更便宜的模型（§3.3 踩坑 2 的延伸）。

**Q7 和 AutoGen 什么关系？**
同赛道（会话式多 agent），AutoGen 已维护模式（§1.4）。概念映射：AutoGen 的 GroupChat ≈ RolePlaying/Workforce，ConversableAgent ≈ ChatAgent。读旧 AutoGen 教程的人可按此对照迁移。

**Q8 装哪些 extras？**
核心依赖即装即用；需要 web 工具装 `camel-ai[web_tools]`，RAG 装 `[rag]`，全量 `[all]`（体积大、依赖多，学习期不建议）。

### 上手清单（半天走完）

1. `uv sync` 装依赖，用 `OPENAI_COMPATIBLE_MODEL` 接一个 OpenAI 兼容端点（10 分钟）；
2. 跑 §3.2 单 agent 工具调用，改 `add` 为你自己的业务函数（20 分钟）；
3. 给 ChatAgent 换 `ChatHistoryMemory → VectorDBMemory`，观察上下文变化（30 分钟）；
4. 跑 §3.3 Workforce 双 worker，日志对照 `workforce.py:5282` 主循环逐行验证（1 小时）；
5. 给 Task 加 `additional_info={'_needs_decomposition': True}` 触发自动分解，盯质量分（30 分钟）；
6. 写一个 external tool（人在环）：模型返回请求 → 你执行 → 回填再 step（1 小时）；
7. 精读清单 #1-#6 过一遍，在代码里找到你在第 2-6 步看到的每个现象（1 小时）。

---

> 交叉引用：CAMEL 的 blackboard 定位详见 [multiagent-handbook §2.5](../multiagent-handbook/Multi-Agent协同手册.md)；与 LangGraph 图语义的逐条对照见 [08-langgraph](../08-langgraph/源码解析与学习路线.md) §12；"六家全自研"证据链见 [python-handbook §4.7](../python-handbook/Python大模型应用开发手册.md)。同专题姊妹篇：[02-crewai.md](02-crewai.md)（角色制）、[03-browser-use.md](03-browser-use.md)（浏览器 agent）。
