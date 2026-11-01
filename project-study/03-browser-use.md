# browser-use 精读：把浏览器变成 Agent 的行动空间

> 对象：`project-study/browser-use/`（browser-use/browser-use 官方仓库快照，commit `4cbe921`，main 分支）
> 信息基准日：**2026-09-28**。§1 全部数据当日经 GitHub API 实抓并标注来源；行号均指本快照，代码演进后以源码为准。注意：本仓库源码用 **tab 缩进**，grep 方法名时用宽匹配。
> 证据口径：`【实证】` = 本机读到的源码行或本机实跑输出；`【声称】` = 官方文档/README 叙述。
> 前置阅读：[01-camel.md](01-camel.md)、[02-crewai.md](02-crewai.md)（同专题姊妹篇）；浏览器工具与沙箱对照见 [05-openclaw/架构拆解.md §7](../05-openclaw/架构拆解.md)。

---

## 0. TL;DR

browser-use 是"浏览器 agent"赛道的事实标准库：把 Playwright/CDP（Chrome DevTools Protocol，Chrome 开发者协议）驱动的真实浏览器包成 agent 的**环境**，LLM 在"页面状态摘要 → 决策 → 动作执行"的循环里用**结构化动作**（点击/输入/滚动/done）完成任务。核心三件事：

1. **Agent 循环**：`Agent`（`browser_use/agent/service.py:134`）的 `run()`（`:2503`）里一个 `while self.state.n_steps <= max_steps`（`:2600`【实证】）——每步 = `_prepare_context`（`:1087`，提取 DOM 状态摘要）→ `_get_next_action`（`:1176`，LLM 结构化决策）→ `_execute_actions`（`:1211`，CDP 执行）；
2. **步骤预算熔断**：预算过半注入 "BUDGET WARNING" 进提示词（`:1548-1565`【实证】），**最后一步强制只留 `done` 工具**（`:1572` 官方注释原文："Your only tool available is the 'done' tool"）；
3. **浏览器会话**：`BrowserSession`（`browser/session.py:134`）+ `BrowserProfile`（`browser/profile.py`，1300 行配置面）+ watchdog（`watchdog_base.py`）自愈体系。

一句话记住：**browser-use = DOM 序列化当眼睛 + 结构化动作当手 + 步数预算当缰绳**。与六家 harness 对照，它是"环境特化型 agent"：权限问题被简化成 `allowed_domains`，护栏问题被简化成步数与循环检测。本册 §3 已在本机真机跑通（DeepSeek + 本机 Chromium，3 步完成 example.com 标题提取）。

---

## 1. 项目定位与生态

### 1.1 定位一句话

**browser-use：让 AI agent 操作真实浏览器的开源库**——2026 年"computer use"浪潮里开源侧最成功的实现之一，从"网页自动化"切入 agent 赛道，反向长出全套 agent 基建（工具注册、上下文压缩、循环检测、文件系统、技能包）。

### 1.2 当日实抓数据（2026-09-28，GitHub API）

| 项目 | 数值 | 来源 |
|---|---|---|
| star | **116,507** | [api.github.com/repos/browser-use/browser-use](https://api.github.com/repos/browser-use/browser-use) |
| fork / open issues | 12,838 / 514 | 同上 |
| 语言 / 许可证 | Python / **MIT** | 同上 |
| 最新 release | **0.13.10**（2026-09-04） | [releases](https://github.com/browser-use/browser-use/releases) |
| 最近 push | 2026-09-26 | 同 API |
| 近 60 天 commits | 100+（当日实抓触及分页上限） | 同 API |
| 创建时间 | 2024-10-31 | 同 API |
| PyPI 包名 / 版本 | `browser-use` / 0.13.10（与 release 同步） | 仓库 `pyproject.toml`【实证】 |

**维护节奏**：三家最活跃之一（分页打满）；`requires-python >=3.11,<4.0`【实证】——比另两家都高，Python 3.13.5 可用。

### 1.3 商业模式与"云-开源"边界【声称，官方 README】

README 与官方示例（`examples/simple.py` 等）默认引导 `ChatBrowserUse`——**自家云端模型**（`BROWSER_USE_API_KEY`，cloud.browser-use.com 发放）【实证 examples 源码】。开源库本身 MIT、可全离线运行（任意 OpenAI 兼容模型 + 本机 Chromium）；云服务是托管模型 + 托管浏览器。**读官方教程时先分清哪部分是云能力**——这是本赛道特有的"文档即销售"现象，本册 §3 全部用开源路径复现。

### 1.4 生态位

- 与 05-openclaw 的 `browser` 工具、Codex/computer-use 类产品同赛道（计算机/浏览器操作 agent），但 browser-use 是**库**而非产品：六家 harness 里"浏览器只是工具之一"，browser-use 里"浏览器是整个世界"；
- 仓库自带 `skills/`（技能包）、`mcp/`（MCP server 暴露）、`sandbox/`——agent 基建的标配面一应俱全【实证目录】，可对照 [mcp-handbook](../mcp-handbook/MCP搭建文档.md)、[skill-handbook](../skill-handbook/Skill搭建文档.md) 理解这两个插槽的标准用法。

---

## 2. 架构总览：循环、预算、浏览器三层

### 2.1 分层地图（本机实测）

```
┌──────────────────────────────────────────────────────────────────┐
│ Agent 循环层 (agent/service.py, 4163 行, tab 缩进)                 │
│   Agent (:134) → run(:2503) → while n_steps<=max_steps (:2600)     │
│   step(:1035):                                                     │
│     _prepare_context(:1087)     DOM/标签页/文件状态 → 提示词        │
│     _maybe_compact_messages(:1162)  历史压缩                        │
│     _get_next_action(:1176)     LLM 结构化决策（AgentOutput）       │
│     _execute_actions(:1211)     执行 + _post_process               │
│   预算与熔断: BUDGET WARNING(:1548-1565) / 末步 done-only(:1572)     │
│   循环检测: _inject_loop_detection_nudge(:1496) 等四类 nudge         │
├──────────────────────────────────────────────────────────────────┤
│ 动作/工具层 (tools/service.py)                                     │
│   Tools(:441) 注册动作（@action 装饰器 :2102 自定义）               │
│   done 动作 (:2016 结构化输出版 / :2053 普通版)                     │
│   act(:2178) 执行入口                                               │
├──────────────────────────────────────────────────────────────────┤
│ 浏览器会话层 (browser/)                                            │
│   BrowserSession(:134)  CDP 驱动 + ResilientEventBus(:106)         │
│   BrowserProfile (profile.py)  1300 行配置面                        │
│     headless 环境探测(:28-29,:430-432) user_agent(:373)             │
│   session_manager.py(918行) watchdog_base.py 自愈                   │
├──────────────────────────────────────────────────────────────────┤
│ LLM 抽象层 (llm/)  自研 BaseChatModel + 13 家 provider              │
│   ChatDeepSeek(llm/deepseek/chat.py:30, 默认 base_url 指向官方)     │
│   dom/ DOM 序列化 ｜ filesystem/ agent 虚拟文件系统(:699)            │
│   skills/ mcp/ sandbox/ telemetry/(posthog) observability.py        │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Agent 循环：每一步发生什么

`Agent.__init__`（`:136`）参数面即配置面：`task/llm/browser_profile/browser_session/tools/use_vision/max_failures/max_actions_per_step/page_extraction_llm` 等【实证 ：136-262】。`run()`（`:2503`，`max_steps` 默认 **500**【实证】）的主循环每拍执行 `step()`（`:1035`）：

1. **`_prepare_context`（`:1087`）**：调 `BrowserSession.get_browser_state_summary()` 拿页面快照（可点击元素序列化 + 标签页列表 + 滚动位置），拼进提示词；`use_vision` 决定是否附带截图——**DOM 文本与视觉双模**，纯文本模型也能跑（§3 实证）；
2. **`_maybe_compact_messages`（`:1162`）**：历史消息超限时压缩——与 [context-handbook §2](../context-handbook/Context与记忆系统手册.md) 的"压缩只改投影"同思路，压缩发生**在发给 LLM 的消息序列上**，真源是 `AgentHistoryList`；
3. **`_get_next_action`（`:1176`）**：LLM 返回 `AgentOutput`（`agent/views.py`，Pydantic）——**一次可以发多个动作**（`max_actions_per_step` 默认 5【实证】）；
4. **`_execute_actions`（`:1211`）**：经 `Tools.act`（`tools/service.py:2178`）到 CDP；出错走 `_handle_step_error`（`:1258`）。

### 2.3 预算熔断与循环检测：这个库的"护栏艺术"

browser-use 的护栏全部长在**循环层**，两段实现值得整段读：

- **步骤预算**（`:1548-1572`）：`budget_ratio = steps_used / step_info.max_steps`，过阈值把 "BUDGET WARNING: You have used X/Y steps" 注入下一步提示词【实证】；`max_steps` 最后一拍直接把可用工具**裁到只剩 `done`**（`:1572`），逼模型交卷——对照六家：01-claude-code 的 compact 是"上下文熔断"，04-zcode 的 rapid-refill 是"注入熔断"，browser-use 是"**行动空间熔断**"（把工具面砍掉来强制终止）；
- **循环检测 nudge**：`_inject_loop_detection_nudge`（`:1496`）检测到重复动作/重复页面状态后往提示词里注入劝导（同类还有 `_inject_replan_nudge` :1464、`_inject_exploration_nudge` :1480）——**不改状态、只改提示词**的软护栏，与 CrewAI 的 max_iter 硬熔断互补。

### 2.4 浏览器会话：CDP + 事件总线 + watchdog

`BrowserSession`（`session.py:134`）是 Pydantic 模型，内部走 **ResilientEventBus**（`:106`）的事件驱动——连接、导航、下载、弹窗都有对应事件与 watchdog（`watchdog_base.py:321` 行级基类，`session.py` 内派生多个自愈 watchdog）。`BrowserProfile`（`profile.py`）是配置中枢：`headless` 默认值按环境探测（`_get_headless_default` :28-29，`BROWSER_USE_HEADLESS` 环境变量可覆盖，字段定义 ：430-432）、`user_agent`（:373）、`allowed_domains`（域名白名单——**这个库的"权限系统"就这一条**）。`session_manager.py`（918 行）管理多会话生命周期。

### 2.5 LLM 抽象与外围

`llm/` 是**自研**多 provider 抽象（`BaseChatModel`，`llm/base.py`）：anthropic/openai/google/deepseek/ollama/litellm 等 13 个目录【实证】——不依赖 LangChain 的模型层，与 07-langchain 的 `BaseChatModel` 概念同构但独立实现（命名撞车纯属巧合）。`ChatDeepSeek`（`llm/deepseek/chat.py:30`）默认 `base_url='https://api.deepseek.com/v1'`、从 `DEEPSEEK_API_KEY` 读 key【实证 :43/:53-56】。外围三件套：`filesystem/`（agent 私有虚拟文件系统，`_set_file_system` :699）、`dom/`（可点击元素序列化，`python_highlights.py` 等）、`telemetry/`（posthog 埋点，`BROWSER_USE_DISABLE_TELEMETRY` 可关【声称，profile 注释；本机未逐一验证 env 名】）。

---

## 3. 最小复现记录（本机真机，2026-09-28）

### 3.0 环境与模型底座

同前两册：Windows 11 + Python 3.13.5 + uv 0.12.5。模型用 **DeepSeek**（原生 `ChatDeepSeek` provider；当日实测 `deepseek-chat` 可用——百炼账户 Arrearage 见 [01-camel.md §3.4](01-camel.md)、GLM 用于 crewAI 见 [02-crewai.md §3.0](02-crewai.md)，三家 key 矩阵正好铺满）。**视觉模式关闭**（`use_vision=False`）：deepseek-chat 无视觉能力，走 DOM 文本模态。

### 3.1 clone + 安装

```bash
cd E:/hiagent/agent-study/project-study
git -c http.proxy= -c https.proxy= clone --depth 1 --branch main \
    https://github.com/browser-use/browser-use.git browser-use   # → commit 4cbe921
cd browser-use && uv sync                    # 依赖一次装齐，含 playwright
uv run playwright install chromium           # 浏览器本体（本机已有多版本缓存，chromium-1234 就位）
```

`uv sync` 一次通过（依赖面比另两家"现代"：aiohttp/anyio/bubus/posthog/pydantic 全新版本线【实证 pyproject】）。`playwright install chromium` 无输出即成功——可用 `ls ~/AppData/Local/ms-playwright/` 验证 `chromium-1234` 目录存在【实证】。

### 3.2 复现：Agent 完成"读网页标题"（真机跑通）

脚本 `../repro/browser_use_min.py`（改编自官方 `examples/simple.py`：把 `ChatBrowserUse` 云端模型换成原生 `ChatDeepSeek`）：

```python
llm = ChatDeepSeek(model='deepseek-chat', temperature=0.0)
agent = Agent(
    task='打开 https://example.com ，读取页面主标题(h1)文本，用 done 动作返回它。',
    llm=llm,
    use_vision=False,
)
history = await agent.run(max_steps=5)
print(history.final_result())
```

```bash
export $(grep DEEPSEEK_API_KEY E:/hiagent/.env | tr -d ' ' | xargs)
uv run python ../repro/browser_use_min.py
```

**实跑输出摘录**【实证】（真实浏览器被拉起并导航）：

```
INFO [Agent] 📍 Step 2:
INFO [Agent]   👍 Eval: Success: search_page confirmed the h1 text "Example Domain" exists on the page.
INFO [Agent]   🧠 Memory: Navigated to https://example.com; h1 text is "Example Domain". Task complete.
INFO [Agent]   🎯 Next goal: Return the h1 text via done action.
INFO [Agent]   ▶️  done: text: The main heading (h1) of https://example.com is: "Example Domain", success: True
INFO [Agent] 📋 Plan updated with 3 steps
📄  Final Result: The main heading (h1) of https://example.com is: "Example Domain"
✅ Task completed successfully
=== 实际步数 === 3
```

3 步完成（导航 → 评估确认 → done 交卷），Eval/Memory/Next goal 三行正是 agent 提示词要求的自评估结构——**这本身就是 [prompt-handbook](../prompt-handbook/提示词搭建文档.md) "结构化自评"的真实案例**。

### 3.3 踩坑与边界（如实记录）

- **坑 1：官方示例全是云端模型**。`examples/simple.py`、`getting_started/*` 一律 `ChatBrowserUse`（需付费 `BROWSER_USE_API_KEY`）【实证 examples 源码】。开源路径要自己换 provider——好在 `llm/` 目录即 provider 清单，挑有 key 的那家即可；
- **坑 2：`use_vision=False` 必须显式**。默认 `use_vision=True`【实证 ：142 附近参数默认值】，无视觉模型直接跑会拿到截图模态的请求失败；纯文本模型务必关；
- **无坑记录**：安装链路是三家最顺的（playwright 二进制走官方 CDN 一次成功）；本次任务没遇到浏览器启动/CDP 问题——Windows 11 + chromium-1234 组合即开即用；
- **边界**：只复现了"纯文本 DOM 模态 + 单标签页 + 3 步任务"；验证码/反爬、多标签页编排、文件下载、CDP 连接已有 Chrome、云端托管浏览器**未复现**——如实标注。`telemetry` 埋点未验证其网络行为，合规环境建议直接设环境变量关闭。

---

## 4. 与 01-08 六家对照：环境特化型 agent 的取舍

> 六家行号级证据出处同 [01-camel.md §4](01-camel.md)。

| 维度 | browser-use 的选择 | 六家主流做法 | 谁走反方向 |
|---|---|---|---|
| 编排模型 | **单 agent 单循环**，无委派无层级；`while n_steps<=max_steps` 一条道 | 六家均有子代理/委派面（01 §7 / 04 §10 / 05 §9） | browser-use 反向：把全部复杂度压进"一个 agent 看一个世界" |
| 状态载体 | **环境即状态**：页面快照（DOM 序列化 + 可选截图）每步重建 | 会话/事件日志为真源（03 §5、04 §10） | browser-use 的"记忆"只是历史消息投影，真源在世界本身 |
| 工具协议 | 动作=Pydantic 模型（AgentOutput），一次多动作；`@action` 装饰器注册 | 双轨 JSON Schema + MCP（04/05）；browser-use 自己也留了 `mcp/` 暴露口 | 它把"工具调用"收窄成**动作枚举**——比六家的开放工具面窄得多，换来可靠 |
| 护栏位 | **循环层软硬结合**：步数预算注入 + 末步工具面砍到只剩 done + 循环检测 nudge + `allowed_domains` | 执行层：审批四绑定（05 §7.3）、内核沙箱（02 §5） | 方向不同：browser-use 没有进程/文件权限问题（浏览器即容器），护栏防的是"绕圈子和跑不完" |
| 记忆 | 历史消息 + 压缩投影（`_maybe_compact_messages` :1162）+ 任务文件系统（filesystem/） | 多层记忆体系（05 §8 五层、04 三层预算） | 它给 agent 配的是"下载目录"，不是"知识库" |
| 可观测 | 步骤日志结构化（Eval/Memory/Next goal）+ gif.py 回放录像 + posthog | OTel/审计/事件溯源（03/04/05） | gif 回放是六家没有的"行动轨迹可视化"原语 |

三条"谁抄谁的"判断：

1. **末步 done-only 抄了 eval 的"强制收束"思路但用在工具面**：六家的等价物是 04-zcode 的 `alwaysAsk`（权限压过自主），browser-use 是 `done` 压过一切——都是"终局态优先"；
2. **DOM 序列化 vs 截图是 computer-use 的两条路线**，browser-use 两条都留（`use_vision` 开关）——05-openclaw 的 `computer` 工具走的是纯截图派（05 §10 设备能力），browser-use 默认 DOM 派（token 便宜一个量级）；
3. **`@action` 装饰器与六家工具注册同构**（06-opencode 的 17 内置 + 三层来源、04 的双轨 schema），但它注册的是"浏览器里的动作"而非"进程里的能力"——环境特化让 schema 面可以保持极小。

---

## 5. 精读清单（必读 → 选读）

### 必读（按顺序，约 1000 行）

| # | 文件:行 | 阅读目标 |
|---|---|---|
| 1 | `browser_use/agent/service.py:134-262` | Agent 构造面：每个参数都是配置杠杆（use_vision/max_failures/max_actions_per_step…） |
| 2 | `browser_use/agent/service.py:1035-1087` | step() 全貌：一步的完整生命周期 |
| 3 | `browser_use/agent/service.py:2503-2620` | run() 主循环 + step 循环（对照 §2.2 四拍） |
| 4 | `browser_use/agent/service.py:1548-1572` | 预算注入与末步 done-only——护栏艺术的精华 25 行 |
| 5 | `browser_use/tools/service.py:441-520,2016-2060` | Tools 注册面与 done 动作（结构化输出版 vs 普通版） |
| 6 | `browser_use/browser/session.py:134-220` | BrowserSession 字段面：CDP 连接、事件总线、watchdog 挂载点 |
| 7 | `browser_use/agent/views.py`（AgentOutput 定义段） | 模型输出的结构契约 |

### 选读

| # | 文件:行 | 阅读目标 |
|---|---|---|
| 8 | `browser_use/agent/prompts.py`（600 行） | 系统提示词全文：Eval/Memory/Next goal 三段式的出处，对照 prompt-handbook |
| 9 | `browser_use/browser/profile.py:28-60,373-440` | 默认值工程：headless 探测与 user_agent |
| 10 | `browser_use/agent/service.py:1162-1176,1464-1527` | 消息压缩与四类 nudge（replan/exploration/loop） |
| 11 | `browser_use/llm/base.py` + `llm/deepseek/chat.py:30-70` | 自研模型抽象：BaseChatModel 接口与 provider 实现 |
| 12 | `browser_use/dom/`（python_highlights.py 等） | DOM 序列化：可点击元素怎么变成文本 |
| 13 | `browser_use/browser/watchdog_base.py` + `session_manager.py` | 浏览器自愈与多会话管理 |
| 14 | `examples/simple.py` + `examples/getting_started/01_basic_search.py` | 官方最小示例（对照 §3 改编处） |

---

## 6. FAQ + 上手清单

### FAQ

**Q1 use_vision 开还是关？**
有视觉模型（GPT-4o/Gemini/GLM-4V 类）开视觉对复杂页面更稳；纯文本模型必须关（§3.3 坑 2）。DOM 文本模态 token 成本远低于截图，**默认建议 DOM 优先、疑难页面再切视觉**。

**Q2 怎么防止 agent 跑去不该去的网站？**
`BrowserProfile(allowed_domains=['...'])` 域名白名单【实证 profile 字段面】——这是它唯一的"权限系统"。再配合 `max_steps` 小值（5-15）与步数预算注入（§2.3），三层合起来就是该库的全部缰绳。

**Q3 每一步的成本结构是什么？**
一步 ≈ 一次 LLM 调用（输入=系统提示词 + 页面状态 + 历史）+ 若干 CDP 往返。页面越大 DOM 序列化越长——`max_clickable_elements_length`（默认 40000【实证 :210】）截断可点击元素列表。预算意识见 [tuning-handbook §7](../tuning-handbook/Agent调优手册.md)。

**Q4 遇到验证码/反爬怎么办？**
如实说：这不是开源库能承诺的边界（云版有托管的会话与指纹能力【声称】）。合规姿势是走官方 API/白名单站点。参见 [security-handbook](../security-handbook/AI应用安全手册.md) 对自动化边界的讨论。

**Q5 换国产模型怎么接？**
`ChatDeepSeek` 开箱即用（读 `DEEPSEEK_API_KEY`）；智谱等 OpenAI 兼容端点走 `ChatOpenAI(base_url='...', api_key='...', model='...')`【实证 llm/openai/chat.py:56 支持 base_url 参数】。模型要支持 function calling/结构化输出——browser-use 的动作决策依赖它。

**Q6 能接 CDP 复用我已登录的 Chrome 吗？**
能：`BrowserProfile` 支持 CDP 连接与 user data dir 复用【声称，官方文档；本机未复现】。本机复现走的是"新起一个干净 Chromium"。

**Q7 和 Playwright MCP 什么关系？**
同一底层（CDP），两种暴露：Playwright MCP 把浏览器动作暴露为 MCP 工具给任意 agent（[mcp-handbook](../mcp-handbook/MCP搭建文档.md) 的接入配置）；browser-use 自带 agent 循环与状态工程。想要"只有浏览器工具的裸 agent"用前者，要"带预算/压缩/循环检测的成品浏览器 agent"用后者。

**Q8 循环检测误报/不报怎么办？**
nudge 只是提示词劝导（§2.3），不保证触发。可靠性要求高的场景把 `max_steps` 当真护栏（别设 500），并在 `_execute_actions` 外层挂自己的超时——库的默认值是"探索友好"，生产要收紧。

### 上手清单（半天走完）

1. `uv sync` + `playwright install chromium`（15 分钟）；
2. 跑 §3.2 example.com 三步任务，换一个自己常用的网站再跑（30 分钟）；
3. 设 `max_steps=3` 复跑同一个任务，观察 BUDGET WARNING 注入与末步 done-only（20 分钟）；
4. 用 `@action` 写一个自定义动作（如"把页面标题存文件"），观察它出现在动作枚举里（1 小时）；
5. `use_vision` 两态对比同一任务，观察提示词与 token 差异（30 分钟）；
6. 给 `BrowserProfile` 配 `allowed_domains` + user_agent，跑一个"越界站点"验证白名单生效（20 分钟）；
7. 精读清单 #1-#7 过一遍，把 2-6 步的每个现象对应到代码行（1 小时）。

---

> 交叉引用：浏览器工具与沙箱化的产品级对照见 [05-openclaw/架构拆解.md §7/§10](../05-openclaw/架构拆解.md)；MCP 暴露口用法见 [mcp-handbook](../mcp-handbook/MCP搭建文档.md)；自动化安全边界见 [security-handbook](../security-handbook/AI应用安全手册.md)。同专题姊妹篇：[01-camel.md](01-camel.md)（黑板任务编排）、[02-crewai.md](02-crewai.md)（角色制编排）。
