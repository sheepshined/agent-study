# Agent 工作流编排手册：何时用工作流 · 模式谱系 · 节点与原语 · 引擎横评 · 状态与数据流 · 调试可观测 · 企业范例 · 最小实现

> 信息基准日：2026-09-28。工作流（Workflow）指**开发者预先用画布或代码把控制流写死**的编排形态，与"模型自己决定控制流"的 agent（智能体）相对。本文的引擎与平台信息（star 数、版本、维护状态）均为当日对 GitHub API / npm / PyPI 与各官方文档的**实际抓取**，随时间漂移，以仓库现状为准。
>
> 本工作区惯例是结论带 `文件:行号`；本文一部分是源码对照（六家 agent 的编排机制，全部出自本工作区六份《架构拆解》），一部分是网络调研（平台、引擎、官方文档），等价做法是**结论带来源链接**（各节末尾标 URL 或本工作区相对路径）。

---

## 0. TL;DR

- **第一性区分只有一句话：控制流在哪**。Anthropic《Building Effective Agents》的原句：*"Workflows are systems where LLMs and tools are orchestrated through predefined code paths"*（工作流 = LLM 与工具沿着预定义代码路径被编排）；*"Agents are systems where LLMs dynamically direct their own processes"*（agent = LLM 动态指挥自己的流程）。每多把一步控制交给模型，就多一分不可预测性——所以官方建议顺序是**能 workflow 就别 agent**（§1.1）。
- **判据一句话**：步骤能预先枚举、每步输入输出能写清楚、结果能程序化验收、错一步代价高 → 用工作流；步骤写不死、需要模型临场判断 → 用自主 agent；两者中间是最常见的真实形态——**画布里也长着 LLM 节点，agent 里也能调子工作流**（§1.2/§1.4）。
- **腾讯 ADP 四种构建模式是一个现成的选型坐标系**（标准 / 单工作流 / Multi-Agent / Claw）：控制流从"开发者写死"到"模型全权自主"连成一条谱系，四种模式各占一档，Agent 与 Workflow 还支持**双向互调**（§1.3）。
- **模式谱系五种**（Anthropic 官方命名）：prompt chaining（提示词链）/ routing（路由）/ parallelization（并行化）/ orchestrator-workers（编排者-工人）/ evaluator-optimizer（评估者-优化者）。每种一张最小结构图、一组适用场景、一组失败模式，见 §2——它们的本质差别只在**控制流的形状**（串行 / 分叉 / 扇出 / 回环）。
- **节点原语七种就够搭 90% 的流程**：LLM 节点、代码节点、条件分支、循环/迭代、并行、变量聚合、子工作流，外加两个"接缝"原语——参数提取（自然语言 → 结构化契约）与 HITL（Human-in-the-Loop，人工介入/审批）。**契约设计比节点选型更决定成败**：上游输出字段与下游引用字段不一致，是工作流失败的第一根因（§3）。
- **引擎格局（2026-09-28 实抓）**：n8n 206,112 star（fair-code，SaaS 自动化 + AI）、Dify 157,329（LLM 应用 + Agentic Workflow 可视化平台）、LangFlow 155,300（MIT，LangChain 系画布）、LangGraph 42,360（代码态图编排，核心包 1.2.12）、Prefect 23,935（Python 代码态数据编排）、Temporal 23,317（durable execution，持久化执行引擎）、Coze Studio 21,649（字节开源版，**主分支 push 停在 2026-07、半年无正式版，开源节奏明显放缓**）、Mastra 28,368（TS 全栈）。⚠️ **FlowiseAI/Flowise 已整库归档**（2026-08-13 最后推送）。选型决策树见 §4.3。
- **状态三条军规**：① 重试必须配幂等（Idempotency，同一操作重复执行结果不变）——ADP 调优课原话"重试要设置次数、间隔和幂等约束，避免重复建单或重复写入"；② 错误要能走分支而不是崩掉流程——ADP 的"执行异常流程"把失败也变成一条画布路径；③ 变量作用域分清应用级/工作流级/节点级，上游字段名就是下游的契约（§5）。
- **调试方法论来自 ADP 4.4 课**：三层定位（管理页 → 画布 → 节点详情）+ 先问三句（触发了没有？经过了哪些节点？失败在哪个节点？）+ **单节点调试与端到端调试结合**，改动沉淀为可复测的 Badcase 记录——与 [eval-handbook](../eval-handbook/Agent评测与质量工程手册.md) 的评测集与版本指纹闭环（§6）。
- **企业范例横评 12 家 + 精读三家**（n8n / Temporal / Dify）：SaaS 自动化选 n8n，长事务强一致选 Temporal，LLM 应用可视化选 Dify，agent 工程代码态选 LangGraph/Mastra（§7）。
- **最小实现约 250 行**：DAG（Directed Acyclic Graph，有向无环图）拓扑执行 + 条件分支 + 重试幂等 + 异常分支，纯标准库，已本机验证——先跑通它再谈引擎（§8）。

**阅读路线**：拿不准"要不要工作流" → §1；选模式画结构 → §2；搭节点定契约 → §3；选引擎 → §4；管状态防翻车 → §5；调优上线 → §6；抄企业作业 → §7；动手造轮子 → §8。与已有内容的六个接口：**本文与 [multiagent-handbook §2.0](../multiagent-handbook/Multi-Agent协同手册.md) 是同一坐标系的两半**（那边讲"控制流交给模型的六种多 agent 范式"，这边讲"控制流写死的五种 workflow 模式"，Anthropic 的 workflow/agent 区分与五种 pattern 两边共用）；ADP 一手课程出自 [fde-handbook](../fde-handbook/FDE转行手册.md) 的腾讯认证课整理（[2.2下](../fde-handbook/tencent-adp-fde-course/lessons/2.2下_任务执行与编排能力：Workflow、Multi-Agent_与_Claw.md) / [3.3](../fde-handbook/tencent-adp-fde-course/lessons/3.3_单工作流模式实战：客服助手.md) / [4.4](../fde-handbook/tencent-adp-fde-course/lessons/4.4_Workflow_调优.md) 是本文的三份一手底稿）；调试与 Badcase 闭环复用 [eval-handbook](../eval-handbook/Agent评测与质量工程手册.md) 的轨迹评测与版本指纹；LangGraph 的图引擎语义（StateGraph / checkpoint / interrupt）已在 [08-langgraph](../08-langgraph/源码解析与学习路线.md) 源码级拆过，本文 §4 只做横评视角；"六家 agent 为什么全都不用画布工作流"的源码证据链见 §1.5。

---

## 1. 何时用工作流、何时用自主 Agent：确定性编排 vs 模型自由发挥

### 1.1 第一性区分：控制流在谁手里

Anthropic《Building Effective Agents》（2024-12，2026-09-28 仍可访问）给的定义至今是坐标原点：

> **Workflows** are systems where LLMs and tools are orchestrated through **predefined code paths**.
> **Agents**, on the other hand, are systems where LLMs **dynamically direct their own processes** and tool usage, maintaining control over how they accomplish tasks.

两种形态各有代价：工作流的代价是**僵化**（变更要走开发流程、覆盖不了没预设的情况），agent 的代价是**不可预测**（成本、延迟、错误级联都难以封顶）。所以 Anthropic 的总原则是 *"finding the simplest solution possible, and only increasing complexity when needed"*——先找最简方案，确有必要再升级；agent 只留给"无法预测需要几步、写不出固定路径"的开放问题，且必须配沙箱内充分测试与护栏（guardrails）。

这条谱系在 [multiagent-handbook §2.0](../multiagent-handbook/Multi-Agent协同手册.md) 已经立过一次坐标系：那边把它推广到"编排层可以是 workflow（代码写死的扇出）也可以是 agent（模型自己派活）"的多 agent 世界；本文聚焦谱系的"开发者写死"一端，把**工作流自身的模式、原语、引擎、状态与调优**讲透。

> 来源：https://www.anthropic.com/engineering/building-effective-agents （定义原句与"最简方案"原则均出自该文当日版）

### 1.2 判据表：六个问题定形态

| # | 问题 | 都答"是" → 工作流 | 有一个"否" → 倾向 agent |
|---|---|---|---|
| 1 | **步骤可枚举**：处理路径能预先列全吗？ | 客服分流、审批、开票、工单流转 | 开放研究、临场排障 |
| 2 | **输入输出可契约化**：每步的输入字段、输出字段写得清楚吗？ | 参数提取 → 意图 → 分支 → 回复 | "看着办"式综合判断 |
| 3 | **结果可程序验收**：能用代码/规则判定对错吗？ | 订单号格式、分支命中、必填齐不齐 | 创意质量、主观偏好 |
| 4 | **确定性是硬要求**：同一输入应给同一处理吗？ | 退款政策、合规话术 | 探索性对话 |
| 5 | **变更频率低**：流程一个月内会大改吗？ | 政策类流程（改的只是内容不是结构） | 原型期、结构未定 |
| 6 | **错误代价高**：走错分支会重复扣款/建单/对外发送吗？ | 支付、退款、工单 | 低风险内部试用 |

补充两个工程信号：**对话灵活度**——需要多轮澄清但不破坏流程确定性的，用"工作流内置澄清"解决（ADP 的工作流会自动判断必填信息是否完整，缺了自动生成反问话术，[2.2下](../fde-handbook/tencent-adp-fde-course/lessons/2.2下_任务执行与编排能力：Workflow、Multi-Agent_与_Claw.md)）；**规模信号**——流程超过 15-20 个节点、画布已经开始"拉面条"时，优先考虑拆子工作流而不是继续加节点（§3.1）。

### 1.3 腾讯 ADP 四种构建模式：一条现成的选型谱系

腾讯云 ADP（Agent Development Platform，智能体开发平台，2026-09-28 官网实抓）把"控制流从写死到全交给模型"做成了四种应用模式，是市面上最清晰的选型坐标系之一（一手整理出自 [fde-handbook/tencent-adp-fde-course](../fde-handbook/tencent-adp-fde-course/README.md) 的 [2.2下](../fde-handbook/tencent-adp-fde-course/lessons/2.2下_任务执行与编排能力：Workflow、Multi-Agent_与_Claw.md)、3.2-3.5 与 [官网产品页](https://cloud.tencent.com/product/adp)）：

| 模式 | 控制流在哪 | 典型任务 | 何时选 | 代价/约束 |
|---|---|---|---|---|
| **标准模式**（standard agent） | 模型决定（提示词 + 工具 + 知识库） | 知识问答、开放咨询 | 需求多变、起步最快 | 行为不完全可预测，依赖调优（[3.2 实战](../fde-handbook/tencent-adp-fde-course/lessons/3.2_标准模式实战：知识助手.md)） |
| **单工作流模式** | 开发者写死（画布节点 + 连线） | 售后客服分流、工单处理、报告生成 | "输入明确、流程固定、步骤可拆解"，要稳定可控可验收（[3.3 实战](../fde-handbook/tencent-adp-fde-course/lessons/3.3_单工作流模式实战：客服助手.md)） | 灵活性差；结构变更要走画布与发布 |
| **Multi-Agent 模式** | 模型规划 + 多角色协同 | 内容创作（选题/撰写/审校分工） | 任务天然多角色、需要转交关系 | token 与延迟放大；协同方式要选对（§1.4） |
| **Claw 模式** | 模型全权自主 + 独立工作空间 | 数据分析、文件处理、长时自主任务 | 要"数字同事"跑代码出产物 | 最贵最不可控；**创建后不支持切换到其他模式**（其他三种之间可互切） |

三个容易漏掉的细节：

1. **单工作流的"单"不是只能建一个工作流**，而是应用最终指定一个**主工作流**承接用户请求（[3.3](../fde-handbook/tencent-adp-fde-course/lessons/3.3_单工作流模式实战：客服助手.md) Step 3）——主流程 + 可复用子工作流的形态。
2. **Multi-Agent 的协同方式本身又是一层小谱系**：自由转交（默认，模型挑人）/ 工作流编排（转交顺序固定，任务执行可控）/ Plan & Execute（Planner 拆解 → Executor 执行，耗时较长，**仅支持单轮对话**）——注意"工作流编排"作为多 agent 的协同选项出现，恰好说明确定性编排是**协同方式的收敛点**（[2.2下](../fde-handbook/tencent-adp-fde-course/lessons/2.2下_任务执行与编排能力：Workflow、Multi-Agent_与_Claw.md)）。
3. **ADP 官网把"Agent 与 Workflow 双向互调"列为核心能力**：工作流提供流程确定性、Agent 提供灵活性；Agent Harness 云托管运行时支持**断点续跑、按需暂停**（托管级 durable execution + HITL）——混合形态已是平台级一等公民（来源：https://cloud.tencent.com/product/adp ，2026-09-28 实抓）。

### 1.4 混合形态：今天最常见的真实答案

两端之间的灰度地带才是生产主战场，三种标准拼法：

- **画布里嵌 LLM 节点**：流程骨架写死，个别节点让模型自由发挥（Dify 的 agent 节点、ADP 工作流里的大模型节点）。Anthropic 的五种 pattern 全部是这个形态——每一步是 LLM 调用，但**步与步之间怎么走是代码定的**。
- **agent 里调子工作流**：模型在开放循环里，遇到"固定套路"就调一个写死的工作流工具（ADP 的 Agent/Workflow 双向互调、OpenClaw 用 skills 固化流程后由主循环按需加载）。
- **工作流内置 Agent 接管层**：ADP 工作流**内置 Agent 全局监控节点跳转**，无需区分"对话流"和"工作流"——Agent 负责接管对话、控制节点跳转、识别退出/寒暄意图并智能回复；模型管"说不说、怎么接"，节点图管"办事路径"。这是把"模型的灵活性"装进"确定性的壳"的典型设计（[2.2下](../fde-handbook/tencent-adp-fde-course/lessons/2.2下_任务执行与编排能力：Workflow、Multi-Agent_与_Claw.md)）。

### 1.5 反面参照：六家 coding agent 为什么全都不用画布工作流

本工作区六家 agent（01-claude-code / 02-codex / 03-deepseek-harness / 04-zcode / 05-openclaw / 06-opencode）提供了"agent 端"的完整样本：**没有一家提供画布式/业务流程式工作流引擎**——编排骨架一律是"主循环 + 委派"，"下一步做什么"几乎全在模型手里（六份《架构拆解》交叉核对：[01 §3](../01-claude-code/架构拆解.md) / [02 §3](../02-codex/架构拆解.md) / [03 §4](../03-deepseek-harness/架构拆解.md) / [04 §5](../04-zcode/架构拆解.md) / [05 §4](../05-openclaw/架构拆解.md) / [06 §4](../06-opencode/架构拆解.md)）。开发者写死的控制流只出现在三类**护栏位**：执行前闸门（审批/权限/沙箱）、上下文治理（压缩触发）、失败路径（重试/升级/熔断）。

原因正是 §1.2 判据的镜像：coding agent 的任务**步骤不可枚举**（每个仓库、每个 bug 的处理路径都不同），写死路径反而做不了。唯一成体系的例外是 ZCode 的 dynamic workflow（模型写 TypeScript → 编译器静态分析 → 独立 vm realm（虚拟机隔离执行域）运行，[04 §10.3](../04-zcode/架构拆解.md)）——它是"代码态编排"的完整答案：**比 prompt 编排可验证、比给模型一个 shell 可控**，详见 §3.5。结论：**工作流不是 agent 的替代，而是同一谱系的另一端**；选型先问任务结构（§1.2），再问产品形态。

---

## 2. 工作流模式谱系：五种 pattern，一个变量

Anthropic 官方命名了五种 workflow pattern（2026-09-28 实抓原文）：**prompt chaining**（提示词链）、**routing**（路由）、**parallelization**（并行化）、**orchestrator-workers**（编排者-工人）、**evaluator-optimizer**（评估者-优化者）。它们共享同一积木——augmented LLM（带检索/工具/记忆增强的单次 LLM 调用）——差别只在**控制流的形状**：串行接力、分叉定向、扇出聚合、扇出汇总、生成-评审回环。以下每种给最小结构图、适用场景与失败模式；多 agent 侧的对照范式（supervisor / orchestrator-worker 等）见 [multiagent-handbook §2](../multiagent-handbook/Multi-Agent协同手册.md)。

### 2.1 prompt chaining（提示词链）：串行接力

```
  输入 ──▶ [LLM ①] ──▶ [gate] ──▶ [LLM ②] ──▶ [LLM ③] ──▶ 输出
                     （通过才放行）
```

前一步的输出是后一步的输入，任务被分解为**固定的步骤序列**；可以在链上插 gate（检查点门禁）——程序化校验，不过关就终止或走重试。**适用**：步骤间有明确依赖、每步都可单独验证的任务（生成营销文案 → 检查长度约束 → 翻译；解析需求 → 生成代码 → 解释代码）。**失败模式**：**误差级联**——上游错一字，下游全盘歪；链越长越脆。对策：① gate 前置到"最贵一步"之前（便宜的正则/规则先挡）；② 每步输出写契约（§3.3），契约校验失败即断链，不让垃圾数据往下流。**对照**：ADP 3.3 实战的主链就是一条链——参数提取 → 分支策略 → 最终回复，每个节点都有严格输出格式（输出要求逐字段列明）。

### 2.2 routing（路由）：分类定向

```
           ┌──▶ [LLM 分支 A] ──┐
  输入 ──▶ [分类器] ──▶ [LLM 分支 B] ──┼──▶ 输出
           │   └──▶ [LLM 分支 C] ──┘
           └（每条分支是专门化的后续流程）
```

先分类输入，再把不同类别定向到**专门化的后续流程**。分类器可以是一次 LLM 调用（意图识别、问题分类节点），也可以是规则（正则、字段值）。**适用**：输入类型天然分域且各域处理方式不同（客服分流、难度分级路由——简单题小模型、难题大模型；检索查询的"检索 vs 直答"分流）。**失败模式**：**意图边界模糊**——语义相近但业务意图不同的 query 分错支（ADP 4.4 的例子："入住时间"和"完成入住的耗时"）；**边界样例缺失**。对策：① 分类节点的意图描述 + 示例要**专门覆盖边界样例**（ADP 4.4：意图识别错误时通过意图示例强制干预）；② 分错支的代价要可控——每条分支自带兜底（如"其他/转人工"分支，见 2.6）。**对照**：Dify 的 question-classifier 节点、ADP 的意图识别节点、n8n 的 switch 节点，全是本模式的原语化。

### 2.3 parallelization（并行化）：扇出聚合

```
  输入 ──┬──▶ [LLM ①] ──┬
         ├──▶ [LLM ②] ──┼──▶ [聚合器] ──▶ 输出
         └──▶ [LLM ③] ──┘
```

多个 LLM 调用同时进行，输出由程序聚合。两个官方变体：**sectioning**（分块并行——任务可独立切分，各块互不依赖，如"一个问题同时审安全性与用户情绪"或 guardrails 与生成并行跑）；**voting**（投票——同一任务跑多次取多数，用于"漏报代价高"的评审类任务）。**适用**：子任务独立可并行（研究、多数据源汇总）、或需要多票降低漏检率（内容安全审查）。**失败模式**：**聚合冲突**——各路输出互相矛盾时聚合器没有裁决规则；**部分失败语义不明**——三路挂了一路，整体算成功还是失败？对策：聚合规则预先写死（取交集/多数/引用优先），失败语义显式声明（全成功才过 or 容忍 N 路失败，对照 miniflow 的 `tolerate_skip`，§8.2）。**对照**：Dify iteration 节点的并行模式、Codex 多工具并行执行（只读才并发，[02 §3.1](../02-codex/架构拆解.md)）。

### 2.4 orchestrator-workers（编排者-工人）：动态扇出

```
            ┌──────────────┐  ① 拆解为 N 个子任务
  输入 ──▶ │ orchestrator │ ───────────────────────┐
            └──────▲───────┘                        ▼
                   │③ 汇总          [w1]   [w2]   [w3]   （② 并行执行）
                   └───────────────────────┴──────┴──────┘
```

中心 LLM **动态**拆解任务、派给 worker LLM、汇总结果。与 2.3 的唯一差别：**扇出几路、每路干什么，由模型在运行时决定**，不是画布写死的 N 路。**适用**：子任务数量与内容事先不可知（多文件改造、开放式研究的多路搜索）。**失败模式**：**分解不清晰**——子任务边界模糊导致重复劳动（Anthropic 实测：模糊委派直接让两个子代理重复查同一主题）；**编排者上下文过载**。对策：子任务描述带边界声明与产出契约；worker 回传结论不回传过程（交接协议见 [multiagent-handbook §3.3](../multiagent-handbook/Multi-Agent协同手册.md)）。**注意与 agent 世界的关系**：本模式是 Anthropic 谱系里**最接近多 agent 的一格**——编排者若获得了"自己决定调什么工具"的权力，它就是一个 agent；工作流版与 agent 版的分界仍是 §1.1 那句话（控制流在画布里还是在模型里）。

### 2.5 evaluator-optimizer（评估者-优化者）：生成-评审回环

```
  输入 ──▶ [生成器 LLM] ──▶ [评估器 LLM] ──┐
              ▲                          │ 反馈
              └──────（不达标则带反馈重生成）◀┘
```

一个 LLM 生成，另一个 LLM 给评价与改进反馈，循环到达标。**适用**：有明确的评价标准（rubric）、且评审能产出可执行反馈的任务（文学翻译润色、搜索结果不足时主动补搜）。**失败模式**：**评审不收敛**——两模型互相礼貌挑刺，循环不停；**标准漂移**——每轮评价口径不一致。对策：**轮次上限是必配项**（两到三轮封顶，超限带着当前最好结果退出并标注未达标）；评价标准作为契约写死而不是让评审自由发挥。**对照**：代码节点上挂 lint 规则跑"生成 → 报错 → 修复"循环是它的程序化特例（Dify loop 节点 v1.2.0+ 每轮基于上轮结果迭代）。

### 2.6 组合律：真实流程都是复合 pattern

五种 pattern 是乐高块，真实业务流程几乎全是复合体。[ADP 3.3 单工作流实战](../fde-handbook/tencent-adp-fde-course/lessons/3.3_单工作流模式实战：客服助手.md)的售后客服助手就是一张复合图：

```
 开始 ──▶ [参数提取] ──▶ [意图识别] ──┬─ 物流 ──▶ [知识检索+策略] ──┐
         （chaining 首环）  （routing） ├─ 支付退款 ─▶ [知识检索+策略] ──┤（每支内部又是 chaining）
                                       ├─ 退换货 ─▶ [知识检索+策略] ──┤
                                       └─ 其他/转人工 ─▶ [转人工说明] ─┤
                                                                      ▼
                                        [变量聚合] ──▶ [最终回复生成] ──▶ [回复节点] ──▶ 结束
                                        （聚合）        （chaining 末环）
```

读法：**骨架是 routing**（意图四分支），**每条分支内部是 chaining**（检索 → 策略生成），**分支间以 parallelization 的失败语义收束**（意图识别后只有一条分支会运行、其他分支输出为空，变量聚合节点把四条分支合并回统一链路——正是"容忍部分依赖缺失"的聚合，§2.3 的失败模式对策在这里产品化了）。这张图建议原样记住：它是 §3 契约设计与 §8 最小实现的蓝本。**它的失败语义同样是复合的**：参数提取节点开异常处理，"执行异常流程"连到转人工说明节点——失败路径也是画布上的一等公民（§5.4）。

> 来源：Anthropic 五种 pattern 名称与定义 https://www.anthropic.com/engineering/building-effective-agents ｜ ADP 实战流程图出自 [fde-handbook 3.3 节](../fde-handbook/tencent-adp-fde-course/lessons/3.3_单工作流模式实战：客服助手.md)（含 35 张截图的一手整理）

---
## 3. 节点与编排原语：搭流程的零件与契约

### 3.1 原语清单：七种节点 + 两个接缝

以 Dify 官方文档节点目录（2026-09-28 实抓，24 类节点）与 ADP 的四类节点划分（信息收集类 / 信息处理类 / 变量处理类 / 基础节点，[2.2下](../fde-handbook/tencent-adp-fde-course/lessons/2.2下_任务执行与编排能力：Workflow、Multi-Agent_与_Claw.md)）为参照，工作流原语可以收敛为**七种节点 + 两个接缝原语**：

| 原语 | 干什么 | 典型实现 | 用错时的症状 |
|---|---|---|---|
| **LLM 节点** | 一次受控的模型调用（提示词 + 输入变量 + 输出契约） | Dify LLM、ADP 大模型节点、miniflow 的 `extract/classify` | 输出格式漂移、夹带内部词（"知识库片段"），靠提示词输出要求收敛 |
| **代码节点** | 确定性变换（正则/计算/拼装），不花钱不出错 | Dify code（Python/JS）、ADP 代码节点、n8n Function | 把该用代码的判断塞给 LLM，徒增不稳定 |
| **条件分支** | 按字段/意图走不同路径 | Dify ifelse / question-classifier、ADP 意图识别、n8n switch、miniflow `guard` | 意图边界样例没覆盖，分错支（§2.2） |
| **循环/迭代** | 同构重复处理（逐元素 / 逐轮迭代） | Dify iteration（数组）/ loop（每轮基于上轮结果）、n8n split-in-batches | 循环体里塞不可收敛的生成任务 → 死循环（配轮次上限） |
| **并行** | 多路同时执行 | Dify iteration 并行模式、开始/处理节点多连线（ADP 画布支持输出连多后续节点） | 失败语义不明（§2.3） |
| **变量聚合** | 多分支汇回统一链路 | Dify variable-aggregator、ADP 变量聚合节点、miniflow `aggregate`（`tolerate_skip`） | 不聚合就只能在每条分支末尾重复写一遍下游 |
| **子工作流** | 流程复用与分层（主流程调子流程） | ADP"工作流调用工作流"（结束节点输出变量的主用途之一）、n8n sub-workflow、Dify 嵌套 | 画布拉面条（15-20 节点以上就该拆） |
| **接缝①参数提取** | 自然语言 → 结构化字段（带必填追问） | Dify parameter-extractor、ADP 参数提取节点（**会主动追问缺失必填**） | 用"标签提取"收集参数 → 缺字段不追问 → 下游插件报错（§3.2） |
| **接缝②HITL** | 流程挂起，等人工批准/补输入再继续 | Dify human-input 节点、n8n Human review / Wait、Temporal Signal/Update、LangGraph `interrupt()` | 把"高危操作直接放行"或"人工绕过画布"当成审批 |

三个非节点但同样是一等公民的原语：**开始/结束节点**（ADP 硬约束：至少一个结束回复节点，流程才能执行；结束节点的输出变量主要用于"工作流调用工作流"，要给用户看必须挂**回复节点**——这是 3.3 实战的坑）、**系统变量**（如 ADP 的 `SYS.UserQuery`/`SYS.ChatHistory`，用户输入与对话历史作为系统级变量进入流程）、**触发器**（手动/定时/Webhook/插件事件——Dify trigger 节点族，n8n 的 trigger 节点是画布入口）。

### 3.2 节点选型的 Badcase：节点选错，提示词写得再细也不稳

[ADP 4.4 调优课](../fde-handbook/tencent-adp-fde-course/lessons/4.4_Workflow_调优.md)给了本节最好的教材——调优的第一原则不是调提示词，而是**先确认节点没选错**：

- **用标签提取节点收集参数**（酒店客需送物场景）：需要收集"物品 + 数量"作为插件入参，原配置用大模型**标签提取**节点——用户没明确说部分参数时节点**不会主动追问**，插件入参缺失直接报错。改成**参数提取**节点（带缺失追问）即愈。
- **判据一句话**：标签提取适合"给已有文本打类别标签"；参数提取适合"围绕后续工具调用收集必填字段"。**只要字段缺失会影响下游执行，就优先用参数提取 + 缺失追问。**
- 同课的第二组 Badcase：**语种输出不稳定**——不要只在提示词里写"中文问题中文回复"，更稳定的做法是**加一个大模型节点先判断语种、输出语言变量**，后续节点引用变量（把"提示词约束"升级为"数据流约束"）；**意图识别错误**——用意图示例强制干预；**前端识别失败**——在回复节点配置输出变量让前端稳定识别内容类型。

这条原则的普遍形式：**能用结构（节点类型、变量、连线）解决的，就不要用提示词解决**——提示词是软约束，数据流是硬约束。

### 3.3 输入输出契约设计规范（六条）

工作流的可靠性不来自模型，来自**节点间接口的严谨程度**。ADP 4.4 的根因分析是总纲："很多'流程失败'本质上不是节点不会处理，而是**上游输出字段和下游引用字段不一致**，或者**分支判断拿到的是空值**。"由此归纳六条规范：

1. **显式声明字段名与类型**：每个节点的输出变量明确名称、类型（字符串/数字/数组/对象），下游只允许引用已声明的字段。miniflow 用 `outputs` 契约在引擎层强制（§8.2）。
2. **必填与缺失值处理显式化**：会影响下游执行的输入字段设必填并配**追问**（不完整自动生成澄清话术，见 [2.2下](../fde-handbook/tencent-adp-fde-course/lessons/2.2下_任务执行与编排能力：Workflow、Multi-Agent_与_Claw.md)）；允许缺失的字段要写明缺失时走哪个分支，不允许"判空靠运气"。
3. **枚举值收敛**：分类/等级类输出收敛为有限枚举（如情绪等级只能取"平静、着急、愤怒、无法判断"四值，[3.3](../fde-handbook/tencent-adp-fde-course/lessons/3.3_单工作流模式实战：客服助手.md)），让下游条件分支可穷举。
4. **输出变量服务前端识别**：前端需要结构化区分内容类型时，在回复节点配置输出变量，而不是靠解析自然语言（4.4 旅游攻略案例）。
5. **跨节点引用只走变量，不走"默契"**：检索问题里插入上游输出要用变量引用（`{{c_description}}`），不要指望下一个节点"自己记得"上一个节点的全文——所有依赖在画布（或 miniflow 的 `deps`）里可见、可静态检查。
6. **契约进版本指纹**：节点输出契约变更 = 流程行为变更，评测集与版本号要跟着动（与 [eval-handbook §4 版本指纹](../eval-handbook/Agent评测与质量工程手册.md) 互引）。

### 3.4 HITL 原语横评：五家引擎怎么写"等人"

HITL（Human-in-the-Loop，人在环/人工介入）的本质是**把运行中的流程挂起，把恢复权交给人或外部系统**。2026-09-28 实抓的机制对照：

| 引擎 | 挂起原语 | 恢复机制 | 状态存于 |
|---|---|---|---|
| Dify | human-input 节点（官方节点目录实证） | 用户在会话中补输入 | 平台会话状态 |
| n8n | ① AI Agent 工具级审批（Human review 步骤，暂停并通过 Chat/Slack/Gmail 等九渠道发审批请求，拒绝则"action is canceled and the AI is informed"）；② app 节点 Send and Wait for Approval；③ **Wait 节点**（通用挂起原语，等 resume URL 被调用或超时） | 渠道回调 / resume URL | 工作流状态存库 |
| Temporal | **Signal**（异步改状态，不返回值）/ **Update**（同步可追踪、可带 validator） | `workflow.condition` 等待信号：`await workflow.wait_condition(lambda: self.approved_for_release)`——等待本身持久化（Signal 到达记 `WorkflowExecutionSignaled` 事件） | **事件历史**（History） |
| LangGraph | `interrupt()`（暂停图执行，把值返回给调用方；官方原句：*"pauses graph execution and returns a value to the caller"*） | `Command(resume=...)` 以同一 thread ID 重入，resume 值成为 `interrupt()` 的返回值；**恢复时节点从头重执行，需写幂等** | checkpointer（检查点器） |
| 腾讯 ADP | Agent Harness 按需暂停（官网能力页，2026-09-28 实抓） | 断点续跑 | 平台托管 |

选型要点：审批要走**渠道**（n8n 模式，审批消息进聊天工具最贴近运营）；审批要**可追溯**（Temporal/ADP 模式，等待是历史事件不是内存态，服务重启不丢）；挂起要**幂等**（LangGraph 明示恢复重执行节点——挂起点之后的副作用必须能安全重放）。共同不变量：**挂起不是暂停进程，而是把"等待"本身持久化为状态**。

> 来源：Dify 节点目录 https://docs.dify.ai/en/cloud/use-dify/nodes/ ｜ n8n https://docs.n8n.io/build/integrate-ai/ai-examples/human-in-the-loop-for-tools.md ｜ Temporal https://docs.temporal.io/develop/python/workflows/message-passing ｜ LangGraph https://docs.langchain.com/oss/python/langgraph/interrupts （均为 2026-09-28 实抓）

### 3.5 六家对照：agent 端的"节点"长什么样

把 §3.1 的原语表投影到六家 agent 上，能看清两个世界的同构与分界（行号出自六份《架构拆解》）：

| 工作流原语 | 六家 agent 端的对应物 | 代表证据 |
|---|---|---|
| LLM 节点 | 主循环里的单个 model step（ZCode `turn-model-step.ts:133`、OpenCode runLoop 内的每轮采样） | [04 §5](../04-zcode/架构拆解.md) / [06 §4.1](../06-opencode/架构拆解.md) |
| 条件分支 | 开发者写死的护栏判定（Claude Code 权限三级判定 `src/permissions.ts:19-60`；Codex 审批策略枚举 `protocol/src/protocol.rs:992`） | [01 §5](../01-claude-code/架构拆解.md) / [02 §5.1](../02-codex/架构拆解.md) |
| 循环 | 主循环本身（`while(true)`）+ 重试上限（ZCode `STREAM_RECOVERY_MAX_RETRIES=10`） | [04 §5](../04-zcode/架构拆解.md) |
| 并行 | 只读工具并发（Claude Code `runToolsConcurrently`，有写操作退回串行） | [01 §3.1](../01-claude-code/架构拆解.md) |
| 参数提取 | 工具的 schema 校验（zod/JSON Schema）——模型输出必须过契约才能执行 | [04 §6 双轨 schema](../04-zcode/架构拆解.md) |
| HITL | 审批闸门（Codex Approval → 执行链、OpenClaw 审批绑定 cwd+argv+env+哈希） | [02 §4.3](../02-codex/架构拆解.md) / [05 §7.3](../05-openclaw/架构拆解.md) |
| 子工作流 | 子代理（`Task` 工具 / `sessions_spawn`）与 ZCode dynamic workflow | [01 §7](../01-claude-code/架构拆解.md) / [05 §9](../05-openclaw/架构拆解.md) / [04 §10.3](../04-zcode/架构拆解.md) |

其中 **ZCode dynamic workflow 值得单独一读**——六家里唯一的"代码态编排"完整实现（[04 §10.3](../04-zcode/架构拆解.md)，`CLI:dynamic-workflow/README.md:1-30`）：模型写 TypeScript 脚本表达控制流 → 编译器做 typecheck、schema 合成、依赖推断与 **taint 不动点分析**（由静态分析决定哪些步骤能并发、哪些数据是脏的）→ 子进程 `vm.createContext` 独立 realm 执行（裸 vm 天然没有 `process/require/Buffer/fetch`，只注入 `__host` 桥接宿主工具）→ NDJSON 父子桥 + SQLite journal 持久化运行状态。它回答的问题是：**当模型需要比"画布拖拽"更强的表达能力时，怎么不退回"给模型一个 shell"**——答案是"模型写程序 + 编译器验证 + 受限运行时"。与本文 §8 的手写引擎对照读，能看到"静态分析换可靠性"这条路的最小形态。

---

## 4. 引擎横评（2026-09-28 当日实抓）

### 4.1 总表

star、最新版本、维护状态均为 2026-09-28 经 GitHub API / npm / PyPI 实抓（数据时间戳为 UTC；抓取记录含 open issues 与 pushed_at，全部结论带仓库链接）：

| 引擎 | star | License | 最新版本 / 发布日 | 维护状态 | 形态 | 心智模型一句话 |
|---|---|---|---|---|---|---|
| [n8n](https://github.com/n8n-io/n8n) | 206,112 | Sustainable Use（fair-code，非 OSI 开源） | 2.40.7 / 2026-09-25 | 活跃（pushed 2026-09-27） | 可视化画布 | SaaS 自动化 + AI：trigger 节点 + 处理节点链，items 在节点间流动 |
| [Dify](https://github.com/langgenius/dify) | 157,329 | Dify 自有许可（API 标 NOASSERTION） | v1.17.1 / 2026-09-10 | 活跃（pushed 2026-09-27） | 可视化画布 | LLM 应用 + Agentic Workflow + RAG 一体；24 类节点 |
| [LangFlow](https://github.com/langflow-ai/langflow) | 155,300 | MIT | v1.12.3 / 2026-09-22 | 活跃（pushed 2026-09-27） | 可视化画布 | LangChain 系组件画布，flow 可发布为 API 或嵌套为组件 |
| [Mastra](https://github.com/mastra-ai/mastra) | 28,368 | 自有许可（NOASSERTION） | @mastra/core 1.71.0 / 2026-09-25 | 活跃（pushed 2026-09-27） | 代码优先 | TS 全栈 agent 框架：`createStep`/`createWorkflow` + `.then()` 链 |
| [Prefect](https://github.com/PrefectHQ/prefect) | 23,935 | Apache-2.0 | 3.8.7 / 2026-09-26 | 活跃（pushed 2026-09-27） | 代码态（Python 装饰器） | `@flow`/`@task` 即工作流；v3 明确**去 DAG 化**，拥抱原生 Python 控制流 |
| [Temporal](https://github.com/temporalio/temporal) | 23,317 | MIT | v1.32.0 / 2026-09-11 | 活跃（pushed 2026-09-27） | 代码态（durable execution） | Workflow（确定性可重放）+ Activity（副作用），状态=事件历史 |
| [Coze Studio](https://github.com/coze-dev/coze-studio) | 21,649 | Apache-2.0 | v0.5.1 / 2026-02-05 | **开源节奏放缓**（pushed 2026-07-29，半年无正式版） | 可视化画布 | 字节 Coze 开源版，Go + React，源自 SaaS 平台 |
| [LangGraph](https://github.com/langchain-ai/langgraph) | 42,360 | MIT | 核心包 1.2.12（PyPI 实抓） | 活跃（pushed 2026-09-27） | 代码态图编排 | StateGraph：共享状态 + node/edge，compile 后运行，checkpointer 持久化 |
| [Windmill](https://github.com/windmill-labs/windmill) | 18,039 | AGPL 系（NOASSERTION） | （未抓 release） | 活跃（pushed 2026-09-27） | 低代码 + 脚本 | 脚本变 webhook/工作流/UI，Rust 实现自称 13× 快于 Airflow |
| [Activepieces](https://github.com/activepieces/activepieces) | 24,752 | MIT 系（NOASSERTION） | （未抓 release） | 活跃（pushed 2026-09-27） | 可视化画布 | AI agents + MCP + 工作流自动化，约 400 个 MCP 连接器（n8n 替代定位） |
| [Hatchet](https://github.com/hatchet-dev/hatchet) | 8,011 | MIT | （未抓 release） | 活跃（pushed 2026-09-27） | 代码态任务编排 | Go 事件驱动后台任务 + durable workflow + AI agent 编排 |
| ~~[Flowise](https://github.com/FlowiseAI/Flowise)~~ | 55,485 | NOASSERTION | — | **已整库归档**（最后 push 2026-08-13） | 可视化画布 | "Build AI Agents, Visually"——选型必须避开 |

> 腾讯 ADP 为闭源 SaaS/私有化平台（免费版 0 元、专业版 188 元/月、企业版 4,880 元/月，2026-09-28 官网实抓），无 star 可比，单列于 §4.2.1。

### 4.2 分引擎要点

#### 4.2.1 腾讯 ADP：企业级平台上的四种模式 + 托管 Harness

心智模型不是"一个画布"而是"**四种模式 + 托管运行时**"（§1.3 的选型谱系落在一个平台里）。工程上最值得看的是平台把 §5/§6 的难题产品化的方式：Agent Harness 云托管运行时提供**断点续跑、按需暂停、全链路可追溯、密钥隔离**；工作流画布提供节点状态、输入输出变量详情与连线状态的端到端调试视图；发布走版本说明 + 变更项确认（[3.3](../fde-handbook/tencent-adp-fde-course/lessons/3.3_单工作流模式实战：客服助手.md) Step 15）。**适用**：企业级 Agent 规模化运营（AgentOps 视角）、需要"Agent 灵活性 + Workflow 确定性"混合的审批/工单类业务。来源：https://cloud.tencent.com/product/adp ｜ 一手课程整理 [fde-handbook/tencent-adp-fde-course](../fde-handbook/tencent-adp-fde-course/README.md)。

#### 4.2.2 Dify：LLM 应用团队的可视化工作流

**Workflow 与 Chatflow 是两种类型**（官方文档原句）：*"A Workflow runs once from start to finish"*（一次输入一次输出，适合自动化报告、数据管道、批处理）；*"A Chatflow adds a conversation layer"*（每条消息触发一次流程、以 User Input 开始、**必须以 Answer 节点结束**，支持内容审核、TTS）。节点清单 24 类（§3.1 已列），控制流有 ifelse / iteration（数组逐元素，可并行）/ loop（v1.2.0+ 每轮基于上轮结果）；状态用变量系统（Start 输入变量 / 环境变量 / 会话变量）；HITL 有 human-input 节点；触发支持定时与 Webhook。**适用**：需要可视化编排 + RAG + Agent 节点混合的 LLM 应用团队——它是"RAG 手册（知识管线）+ 工作流手册（流程管线）"两本手册能力交集最大的引擎（知识库对接见 [rag-handbook](../rag-handbook/RAG搭建文档.md)）。来源：https://docs.dify.ai/en/cloud/use-dify/build/workflow-chatflow 、https://docs.dify.ai/en/cloud/use-dify/nodes/ （2026-09-28 实抓）。

#### 4.2.3 n8n：SaaS 自动化 + AI 混合的老牌画布

node-based 画布（trigger 节点 + 处理节点链，数据以 items 流动），AI 侧用 **cluster nodes**（官方定义："node groups that work together to provide functionality in an n8n workflow"，root node 挂 sub-node）；官方 AI 构件目录覆盖"LLM providers, agents, tools, memory, and MCP servers"，节点内部命名空间即 `n8n-nodes-langchain`——**LangChain 概念被原样搬进了画布**（官方专页 "LangChain in n8n"）。HITL 三层（§3.4 表）。**适用**：跨 SaaS 工具的运营/IT 自动化为主、AI 为辅的场景；它是七家里"非 AI 生态"最厚的一家（400+ 集成）。注意许可：Sustainable Use License（fair-code），**不是 OSI 开源**，商用分发前先读许可条款。来源：https://docs.n8n.io/build/integrate-ai.md 、https://docs.n8n.io/integrations/builtin/cluster-nodes/ （2026-09-28 实抓）。

#### 4.2.4 LangFlow / Coze Studio / Flowise：画布赛道的三面镜子

- **LangFlow**（155,300 star，MIT，2026-09-22 仍在高节奏发版）：LangChain 系组件画布，React Flow 画布 + 组件可嵌套，是 **Flowise 归档后该赛道最活跃的开源选项**。
- **Coze Studio**（字节开源版，21,649 star，Apache-2.0）：源自 Coze SaaS 平台（README 原话 "derived from the 'Coze Development Platform'"），可视化拖拽画布 + 工作流创建/修改/发布/删除 + 插件/知识库/多模型。⚠️ **开源版明显放缓**：主分支最后 push 2026-07-29、最后正式版 v0.5.1（2026-02-05）——生产采用前先评估活跃度，或改用 SaaS 版。
- **Flowise**（55,485 star）：**整库已归档**（2026-08-13 最后推送）——"star 高"不等于"可依赖"，本工作区从 multiagent（AutoGen 维护模式）、context（Letta 转壳）到本文（Flowise 归档）反复验证同一条纪律：**框架选型必须做"归档/维护模式"扫描**。

#### 4.2.5 Temporal：durable execution（持久化执行）的工程化答案

心智模型是**两类函数**：Workflow（必须确定性、可重放）+ Activity（非确定性副作用：API 调用、写库）。核心机制是**事件溯源式状态恢复**（官方文档）："The values passed to Activities through invocation parameters or returned through a result value are recorded in the Execution history"——参数与返回值都记录在执行历史里，恢复时把整条历史从服务端传回 worker 重放，**服务挂掉可精确续跑**。重试是内建语义（Retry Policy 官方默认值：Initial Interval 1s / Backoff Coefficient 2.0 / Maximum Interval 100×初始 / **Maximum Attempts ∞**；Activity 默认自动重试，而 **Workflow 本身默认不配重试策略**——重放机制使然，Workflow Task 失败按指数退避至多 10 分钟一直重试）。HITL 用 Signal/Update（§3.4）。**适用**：长时运行、跨服务、强一致要求的业务流程与基础设施级编排；重试/超时/挂起语义在横评里最完备。**代价**：部署与心智负担最重（自托管集群或 Temporal Cloud），"确定性约束"要求写代码的人换脑子。来源：https://docs.temporal.io/retry-policies 、https://docs.temporal.io/develop/python/workflows/message-passing （2026-09-28 实抓）。

#### 4.2.6 Prefect：Python 代码态的数据/ML 管线编排

心智模型是**装饰器**：`@flow` 装饰 Python 函数即工作流、`@task` 即任务；官方定位 *"Write workflows in native Python—no DSLs, YAML, or special syntax"*，且 v3 明确**去 DAG 化**（原文：removed the constraint that workflows be written explicitly as DAGs, fully embracing native Python control flow——运行时按数据/条件动态创建任务）。状态机管理 run（success/failure/retry 状态跟踪、"Resume interrupted runs from the last successful point"）；task 级 `retries=` / `retry_delay_seconds=`；结果缓存（cache key 命中即恢复结果不重跑）；flow 可调子 flow，每个 run 在 UI 独立可观测。**适用**：数据/ML 管线（ETL、批处理、模型训练），团队写 Python 的场合。**与 Temporal 的分界**（综合官方文档与对比文章）：Prefect 是**数据编排器**（状态跟踪后重投），Temporal 是**执行引擎**（事件溯源重放到任意断点）；"AI agent 的 durable execution"两者正在重叠，选型先选家族再选成员。来源：https://docs.prefect.io/v3/concepts/flows-and-tasks （2026-09-28 实抓）。

#### 4.2.7 LangGraph：agent 工程的代码态图编排

官方定位 *"a low-level orchestration framework and runtime for building, managing, and deploying long-running, stateful agents"*。核心是 **StateGraph**：共享状态（如 MessagesState）+ node（变换状态的函数）+ edge（含 START/END），compile 后运行；官方明确支持 *"mix deterministic, hand-coded steps with LLM-driven agentic steps in the same graph"*——确定性步骤与 agent 步骤同图混编，正是 §1.4 混合形态的框架级实现。持久化用 checkpointer（写"exact graph state"、thread ID 是持久游标，生产必须配 durable checkpointer）；HITL 用 `interrupt()`（§3.4）。**引擎语义（BSP 超步模型、9 种通道与 reducer、每拍 checkpoint）已在 [08-langgraph](../08-langgraph/源码解析与学习路线.md) 源码级拆过**，本文不重复；横评视角的定位是：**横评里唯一"图约束 + 代码优先"的 agent 工程 apex**——画布引擎给不了的灵活性、纯代码引擎缺的图结构约束，它都在。来源：https://docs.langchain.com/oss/python/langgraph/overview （2026-09-28 实抓）。

#### 4.2.8 Mastra 与小众选项

**Mastra**（TS 全栈，28,368 star）：`createStep()`（Zod/Valibot schema + execute 函数）→ `createWorkflow()` 用 `.then()` 链接、`.commit()` 定稿；内建 suspension/resumption（run 状态可为 suspended，`resumeStream` 续传、服务重启自动恢复活动 run）；可接 Inngest 等外部 runner。TS 团队做 agent + 工作流的一站式选项。**Windmill**（脚本转应用/工作流，Rust）、**Activepieces**（n8n 替代定位、400 个 MCP 连接器）、**Hatchet**（Go 事件驱动 + durable workflow）作为补位选项，横评表中给了定位；本文不展开。来源：https://mastra.ai/docs/workflows/overview （2026-09-28 实抓）。

### 4.3 选型决策树

```
任务是什么形态？
├─ 业务流程确定、要可视化运维/交接给运营 ──────────▶ LLM 应用团队？ Dify
│                                                    SaaS 工具自动化？ n8n（或 Activepieces）
│                                                    国内生态/中文场景？ ADP（SaaS/私有化）或 Coze（注意开源版放缓）
├─ 数据/ML 管线、团队写 Python ─────────────────▶ Prefect（轻）／ Windmill（要脚本即应用时）
├─ 长事务、跨服务、强一致、重试/挂起语义要完备 ──▶ Temporal（付出部署与确定性约束的代价）
├─ agent 工程：确定性步骤与 LLM 步骤同图混编 ────▶ LangGraph（Python/JS）／ Mastra（TS）
└─ 只是给现有 agent 加"固定套路" ──────────────▶ 先不引引擎：子工作流工具/技能包（skill-handbook）通常够用
选型前必做：归档/维护模式扫描（Flowise 已归档、coze-studio 放缓、AutoGen 维护模式的教训）
```

三条经验法则：① **先选家族再选成员**（可视化画布 / 数据编排 / durable execution / agent 图编排，家族错了成员再优也是错）；② **许可先看**（n8n 非 OSI 开源、Dify/Windmill/Activepieces 自有许可条款，商用分发前逐家确认）；③ **六家 agent 全自研不用框架**的证据链（[python-handbook §4.7](../python-handbook/Python大模型应用开发手册.md)）提示：做 agent **产品**，harness 自研的"管"问题（权限/沙箱/上下文）框架不替你解决；做 agent **应用**，引擎的编排糖是净收益。

---
## 5. 状态与数据流：变量、幂等、重试与错误分支

### 5.1 变量作用域：三级作用域是一条分界线

工作流的"数据流"就是把变量在节点间传下去。主流引擎的作用域约定惊人地一致（2026-09-28 对照实抓）：

| 层级 | 生命周期 | 典型内容 | 代表实现 |
|---|---|---|---|
| **应用级**（全局） | 跨会话持久 | 业务配置、模型选择、全局人设 | ADP 应用级变量（[2.2上](../fde-handbook/tencent-adp-fde-course/lessons/2.2上_基础能力：应用、模型、角色指令、变量与长期记忆.md)）、Dify 环境变量 |
| **工作流级**（会话/流程实例） | 一次流程执行（或一个会话） | 中间产物：提取的订单号、判定的语种、聚合的策略 | ADP 工作流级变量、Dify 会话变量、miniflow 的 `results` 字典 |
| **节点级**（输入/输出） | 单节点 | 输入变量引用（**节点输入可以引用所有祖先节点的输出变量**，ADP 4.4）+ 输出变量 | 各家一致；miniflow 的 `deps_view` |

三条纪律：① **节点输入只能引用祖先输出**——ADP 画布的连线约束（"当前节点的输入一定要连接前一个节点的输出；输入之间、输出之间不能连接"）本质是把"数据依赖"显式化，miniflow 的 `deps` 声明是它的代码形态（§8.2 不变量 I1）；② **系统变量别和业务变量混**（`SYS.UserQuery`/`SYS.ChatHistory` 是平台注入的，业务变量别占这个名字空间）；③ **分支未选中 = 该分支输出不存在**（ADP：意图识别后只有一条分支会运行、其他分支输出为空）——下游要么用变量聚合容忍缺失（§3.1），要么判空，这是空值 Bug 的第一来源。

### 5.2 全局状态设计：唯一真源不变量

流程越长、分支越多，越要回答"**哪份数据是真的**"。本工作区源码里已经立过一条不变量——"**日志为真源，压缩只改投影**"（[context-handbook §2](../context-handbook/Context与记忆系统手册.md)；[03-deepseek-harness §4.1/§5](../03-deepseek-harness/架构拆解.md)：模型历史从仅追加事件日志**派生并冻结**（derive and freeze），"模型可见即已记录"）——工作流引擎把它扩展为两条：

1. **执行历史是真源，节点输出是投影**。Temporal 的恢复机制（把整条事件历史传回 worker 重放）、dsh 的日志派生、ZCode/OpenClaw/OpenCode 的"事件即事实" SQLite（[05 §12](../05-openclaw/架构拆解.md) 明令禁止新增 JSON/JSONL 状态文件），全是同一原则：**状态可以从历史完整重建，就永远不会丢**。画布引擎里对应的机制是运行历史 + checkpoint（Dify 官方表述 "clear conditions, checkpoints, and fallback paths"）。
2. **并发写要围栏**。OpenClaw 的 writer fence（流式前记录 `activeWriterRunId`，每次 transcript 追加在同步 SQLite 事务内校验仍是当前声明，"⇒ 被取代的 run 提交不了脏数据"，[05 §4](../05-openclaw/架构拆解.md)）是并行分支写共享状态的最小防线；工作流侧的等价物是**聚合节点**（§3.1）——不让分支直写全局，而是把输出汇到一个点再统一流转。

### 5.3 幂等与重试：重试三要素 + 引擎默认值对照

ADP 4.4 运维 Tips 原话给出了完整的三要素："**重试要设置次数、间隔和幂等约束，避免重复建单或重复写入**。"展开成工程规范：

- **次数**：有限次。瞬时错误（网络抖动、限流）才值得重试；确定性错误（参数错、契约违约）重试无益。OpenCode 用 8 条正则识别瞬时错误、**context overflow 明确不重试**（`session/retry.ts`，[06 §4.2](../06-opencode/架构拆解.md)）。
- **间隔**：指数退避 + 抖动。ZCode 默认 `maxRetries 10 / base 2000ms / max 60000ms / jitter`，且把底层 SDK 的重试**关成 0** 防止重试相乘（`retry-policy.ts:13-16`、`runner-options.ts:92`，[04 §5](../04-zcode/架构拆解.md)）；OpenCode 默认 2s 指数退避上限 30s、最多 5 次。
- **幂等约束**：重复执行不产生额外副作用。机制是**幂等键**（Idempotency Key）：同一操作的多次尝试携带同一键，外部系统按键去重。ADP 4.4 的"避免重复建单"就是它；Temporal 的 Activity 重试之所以敢默认 ∞ 次，前提也是把 Activity 写成幂等的。

引擎默认值对照（2026-09-28 实抓）：

| 引擎 | 默认重试 | 幂等要求 | 备注 |
|---|---|---|---|
| Temporal | Activity：1s 起步 ×2 退避，**∞ 次** | 隐式强制（重放机制） | Workflow Task 失败指数退避至多 10 分钟持续重试；`Non-Retryable Errors` 可配置 |
| OpenCode | 2s 指数 ×jitter，≤5 次 | — | 8 正则识别瞬时错误；overflow 不重试 |
| ZCode | 10 次 / 2000ms 起 / 60s 封顶 / jitter | — | SDK 重试关零防相乘；idle 窗口随重试放宽 30s |
| LangGraph | — | **显式要求**（interrupt 恢复时节点从头重执行，官方文档原句要求幂等） | 重试策略自写 |
| n8n | 节点级可配 retry on fail | — | Wait 节点管挂起 |

> 来源：Temporal https://docs.temporal.io/retry-policies ｜ n8n/LangGraph 官方文档（均 2026-09-28 实抓）｜ 六家行号出自《架构拆解》

### 5.4 错误分支：失败也是画布上的一条路径

无人在场的工作流，失败处理必须**预先编排**而不是临场兜底。ADP 给了两种节点级异常处理方式（[3.3](../fde-handbook/tencent-adp-fde-course/lessons/3.3_单工作流模式实战：客服助手.md) Step 10）：**执行异常流程**（把失败路由到指定节点——3.3 把参数提取节点的异常连到"生成转人工说明"节点）与**输出特定内容**（自定义失败话术）。这就是"**失败也是画布上的一条路径**"：异常分支汇回主链路（聚合节点把正常策略与异常话术统一给回复节点），用户看到的是"转人工"而不是报错堆栈。

六家 agent 的失败路径是同一思想的手写版（全部出自《架构拆解》，[04 §5](../04-zcode/架构拆解.md) / [06 §4.2](../06-opencode/架构拆解.md) / [02 §4.3](../02-codex/架构拆解.md)）：Codex 的"审批 → 执行 → **被拒后升级沙箱策略重试**且不重复弹审批"；OpenCode 的"非法工具调用改写成 `invalid` 工具结果**回灌模型**而非崩溃" + doom-loop 熔断（最近 3 个 part 同工具同参数即拦截）；ZCode 的恢复路径密度最高（流恢复 10 次重试、取消时持久化快照回写防冷热不一致）。共同模式：**失败 → 分类（瞬时/确定）→ 可重试的带幂等重试，不可重试的走降级分支（转人工/回灌/降级话术）→ 全程留痕**。miniflow 的 `on_error_of` + `fallback` 节点是这套模式的最小实现（§8.2 不变量 I4）。

### 5.5 长事务与挂起：状态在历史里，人可以慢慢点

审批、跨天任务、等外部回执——这些"挂起几小时甚至几天"的需求，考验的是**挂起状态的持久化**。§3.4 的 HITL 横评已经列了机制，这里补心智模型的一句话总结：**挂起不是暂停进程，而是把"等待条件"写进持久状态**——n8n 的 Wait 节点把工作流状态存库、等 resume URL；Temporal 的 `workflow.condition` 把等待写成事件历史里的持久状态（Signal 到达记 `WorkflowExecutionSignaled`）；LangGraph 的 `interrupt()` 把图状态存进 checkpointer 后"waits indefinitely until you resume"。服务重启、机器换人，都不丢等待中的流程——这是"工作流 vs 一段脚本"在工程上的分水岭。

---

## 6. 调试与可观测：定位、单点测试、回放与版本管理

### 6.1 三层定位法：从页面到节点逐步缩小

[ADP 4.4](../fde-handbook/tencent-adp-fde-course/lessons/4.4_Workflow_调优.md) 的方法论开场就反对"只看用户最后看到的回答"——要回到工作流页面看流程本身。三层结构：

1. **工作流管理页**：流程存在吗？启用了吗？（最粗）
2. **画布**：节点连对了吗？分支都汇到聚合了吗？回复节点连到结束了吗？
3. **节点详情页**：单个节点的输入变量、处理逻辑、输出变量、异常设置（最细）。

配合三问：**当前问题触发这个工作流了吗？触发后经过了哪些节点？失败或偏差发生在哪个节点？**——比"直接改整条流程"更容易定位根因。miniflow 的审计日志（`AUDIT`，§8.4 实跑输出）是这三层定位的最小代码形态：每个节点的每次尝试、每次守卫判定、每次 SKIPPED 传播都有行可查。

### 6.2 单点测试与端到端调试：缺一不可

ADP 支持单节点调试与端到端调试（4.4/3.3），纪律是**结合使用**：单节点调试验证"这个节点能不能独立工作"（开发期），端到端调试验证"整条流程从输入跑到回复"（集成期）。**不要把端到端当唯一手段**——端到端失败先定位失败节点，再回该节点做单点调试，避免在整条链路里盲目修改。3.3 实战的建议顺序：按"参数提取 → 意图识别 → 分支策略 → 最终回复"逐段调试；调试通过工作流才进入待发布状态。单点测试的前提是 §3.3 的契约设计——**输入输出契约清晰的节点，才能脱离上下游独立测试**；这也是代码节点比 LLM 节点好测的根本原因。

### 6.3 节点级日志与 trace：挂在可观测体系上

工作流的天然结构（节点边界清晰、每步有输入输出）使它比 agent 循环**更容易做结构化追踪**：每个节点一次 span（追踪区间），span 属性记输入输出变量与耗时。行业标准是 OTel GenAI 语义约定（span 命名、`gen_ai.*` 属性族）——现状与 Langfuse/Phoenix/LangSmith 的横评见 [eval-handbook §7](../eval-handbook/Agent评测与质量工程手册.md)（Langfuse 35.1 万 star、Phoenix 11.6 万，均为当日实抓）；LLM 节点的 token 成本按节点归因（缓存读 ≈0.1×、输出 4-5× 的价差工程，见 [eval-handbook §8](../eval-handbook/Agent评测与质量工程手册.md)）。画布引擎（ADP/Dify/n8n）内置执行历史视图 = 每次运行逐节点的输入输出快照；自研引擎按 miniflow 的 `AUDIT` 起步，够不着 OTel 时先把"节点名 + 尝试序号 + 结果 + 耗时"四元组记全。

### 6.4 回放：durable execution 的调试超能力

事件溯源状态（§5.2）送了一份调试大礼：**历史可以重放**。Temporal 的调试模型是拿一份执行历史在本地重放（replay），能精确重现"服务挂掉前发生了什么"——因为状态本就从历史重建。六家里的对应物：dsh 的会话日志派生（模型可见的历史 = 日志的投影，投影可重算）、ZCode 的 rollout 轨迹（模型 I/O 落 `~/.zcode/cli/rollout`，[04 §9](../04-zcode/架构拆解.md)）、OpenCode 的 SQLite + 独立 `--git-dir` 快照（连磁盘状态都能 revert，[06 §10](../06-opencode/架构拆解.md)）。画布引擎的等价物是**运行历史页**（每次运行逐节点展开）；自研工作流想获得这个能力，最低配是**把每个节点的输入输出 JSON 落盘**（只追加，不覆盖）——成本极低，回报是任何"当时为什么走错分支"都有据可查。

### 6.5 版本管理与灰度发布：发布 ≠ 生效

[3.3](../fde-handbook/tencent-adp-fde-course/lessons/3.3_单工作流模式实战：客服助手.md) Step 15 的发布流程藏着三条纪律：① 发布要**确认变更项**（主工作流、知识库、节点配置逐项列出）；② 发布要**写版本说明**（V1.0 的写法范式："完成 XX 搭建。新增 A/B/C，并完成测试集验证"）；③ **发布后必须从用户侧再测一次**——课程原话："开发态调试正常，不代表用户侧已经拿到最新版本"。与 [eval-handbook](../eval-handbook/Agent评测与质量工程手册.md) 的接口：工作流配置（节点图 + 提示词 + 契约）要纳入**版本指纹**（§3.3 规范六），评测集按版本回归；改节点结构 = 改评测对象。

### 6.6 Badcase 驱动的调优循环

ADP 4.4 把调优动作沉淀为"**可复测的 Badcase 记录**"，并把问题定位到具体配置位置——这是工作流调试与评测体系（[eval-handbook](../eval-handbook/Agent评测与质量工程手册.md)）的接合点：

| 症状 | 先查的位置 | 动作 |
|---|---|---|
| 参数缺失、下游插件报错 | 参数提取节点 | 换参数提取节点 + 必填追问（§3.2 Badcase） |
| 语种/格式不稳定 | 有没有语言判断**变量** | 加判断节点输出语言变量，下游引用（把提示词约束升级为数据流约束） |
| 意图识别错误 | 意图示例 | 补边界样例强制干预（"入住时间"vs"完成入住的耗时"） |
| 前端识别不了内容类型 | 回复节点的输出变量 | 配输出变量（§3.3 规范四） |
| 工具节点频繁超时 | 外部接口性能 / 超时与重试配置 | 查并发限流；重试三要素（§5.3）；接口变更后分鉴权/正常/超时/异常四分支回归再发布 |
| 回复夹带内部词（"变量/节点/知识库片段"） | 最终回复节点的提示词 | 强化"面向客户回复"要求（3.3 测试清单） |
| 编造订单状态/退款时间 | 分支策略与最终回复两层提示词 | 双层强化"不能编造实时状态"约束 |

循环：用户反馈/测试暴露 Badcase → 三层定位（§6.1）→ 改配置位置 → 单点 + 端到端复测 → Badcase 记录入册 → 版本发布 + 用户侧验证。跑熟之后，这个循环就是 eval-handbook 的"评测先行"在工作流上的形态：**Badcase 是免费评测集，每次故障都该让下次变难复发**。

---

## 7. 企业范例：横评与精读

### 7.1 企业视角横评（2026-09-28 GitHub 实抓）

§4.1 的总表已给技术横评；换企业视角（背后主体、商业模式、企业采用证据、私有化能力）再看一遍，选型时两表合用：

| 项目 | 背后主体 | 商业模式 | 企业采用证据（官方口径） | 私有化 |
|---|---|---|---|---|
| n8n | n8n GmbH（柏林，2019 起） | fair-code（Sustainable Use License）+ 云订阅 + 企业版 | 面向 IT/运营团队的自托管自动化标准之一，400+ 集成 | ✅ 自托管 |
| Dify | LangGenius（开源商业公司） | 开源许可（自有条款）+ 云/VPC 订阅 | 定位 LLM 应用平台，云/自托管/企业版齐备 | ✅ 自托管/VPC |
| LangFlow | LangChain 系（DataStax 孵化后回社区） | MIT + 商业云 | LangChain 生态的画布门面 | ✅ Python 自托管 |
| Temporal | Temporal Technologies（创立即公司） | MIT + Temporal Cloud | 官方口径覆盖大量生产级长事务场景（支付/订单/基础设施） | ✅ 自托管集群 |
| Prefect | Prefect Technologies | Apache-2.0 + Prefect Cloud | 数据团队管线编排 | ✅ 开源服务端 |
| Coze Studio | 字节跳动（2025-07 开源） | Apache-2.0（SaaS 版商业运营） | 源自 Coze/扣子 SaaS 平台；⚠️ 开源版节奏放缓（§4.2.4） | ✅ 一键私有化部署 |
| Mastra | Mastra（YC 系） | 自有许可 + 云 | TS 全栈 agent 框架 | ✅ 自托管 |
| ADP | 腾讯云 | SaaS 订阅 + 私有化 | 企业原生智能体底座（AgentOps）；认证课程体系（本工作区一手整理） | ✅ 私有化部署 |

### 7.2 精读一：n8n——"把 LangChain 搬进画布"与三层 HITL

**为什么值得精读**：它是"传统自动化 × AI"混合场景的事实标准（20.6 万 star，2026-09-28 实抓），且把自己的 AI 层**完全架构在 LangChain 概念上**——节点命名空间就叫 `n8n-nodes-langchain`，官方专页"LangChain in n8n"直说实现关系。

**可抄的作业四条**：① **cluster nodes 设计**——一个 root node（如 AI Agent 节点）挂多个 sub-node（model / memory / tool），"组合即能力"的画布表达比平行铺 N 个节点干净得多；② **三层 HITL 分级**（§3.4 表）——工具级审批（AI 要调高危工具先问人，拒绝则"action is canceled and the AI is informed"——**拒绝要回灌给 AI，不是静默失败**）、app 级 Send and Wait for Approval、通用 Wait 挂起原语；③ **拒绝即分支**——审批拒绝不是终止流程而是走分支，和 ADP"执行异常流程"同构（§5.4）；④ **fair-code 的边界意识**——Sustainable Use License 允许自托管与内部商用、限制"以 n8n 为产品再分发"，选它做底座前先画清自己产品的许可边界。

### 7.3 精读二：Temporal——把"确定性"变成工程纪律

**为什么值得精读**：横评里唯一把"状态不丢、重试不滥、挂起可恢复"三件事做成**内建语义**的引擎；它的设计文档本身就是分布式工作流的最好教材。

**可抄的作业五条**：① **Workflow/Activity 两分法**——确定性逻辑与副作用严格分离，Workflow 只做编排与决策（且必须确定性，否则重放错位），副作用全部下沉 Activity；② **重试默认值即最佳实践**（1s / ×2 / 100× 封顶 / ∞ 次 / 可配 `Non-Retryable Errors`，官方文档 2026-09-28 实抓）——注意它敢于 ∞ 的前提：Activity 天然带幂等期望 + 指数退避封顶；③ **事件历史即状态**（§5.2）——参数与返回值全记录，恢复 = 重放，调试 = 重放（§6.4）；④ **Signal/Update 分工**——Signal 异步改状态不返回值、Update 同步可追踪可校验，审批类 HITL 用 Update 更严谨（调用方拿得到接受/拒绝回执，§3.4）；⑤ **"Workflow 本身不配重试"**——重放机制下整流程重试是伪需求，失败治理下沉到 Activity 级。这五条即使不部署 Temporal，也值得写进任何自研工作流引擎的设计约束（miniflow §8 的幂等与事件思想即受此影响）。

### 7.4 精读三：Dify——画布引擎的产品化决策

**为什么值得精读**：15.7 万 star 的 LLM 应用平台（2026-09-28 实抓），它的功能划分处处回应"LLM 应用工作流到底和普通自动化有什么不同"。

**可抄的作业四条**：① **Workflow 与 Chatflow 分型**——批处理（跑一次完）与对话（每条消息触发、必须以 Answer 节点收尾）是两种执行语义，分型比"一个引擎硬兼容两种"清晰（官方原句见 §4.2.2）；② **24 类节点的取舍**——比通用自动化引擎多出来的都是 LLM 特有：parameter-extractor（参数提取）、question-classifier（问题分类）、knowledge-retrieval（知识检索）、variable-aggregator（变量聚合，§3.1），少的都是工作流引擎不该管的（无 BPMN 审批流那套）；③ **变量聚合是必须品不是甜点**——意图分支后"只有一条分支运行、其他输出为空"，没有聚合原语的引擎会逼用户在每条分支末尾复制一遍下游；④ **循环节点 v1.2.0 才补上**——说明"每轮基于上轮结果"的真迭代需求（evaluator-optimizer 模式，§2.5）在 LLM 应用里比想象的晚熟，画布引擎的能力边界要看清版本。

> 三家精读的机制细节全部出自官方文档当日实抓（n8n：https://docs.n8n.io/build/integrate-ai.md ；Temporal：https://docs.temporal.io/retry-policies ；Dify：https://docs.dify.ai/en/cloud/use-dify/build/workflow-chatflow ），企业定位出自各官网/README。

---
## 8. 从零搭一个最小工作流编排器（Python 3，已本机验证）

### 8.1 设计目标与四条不变量

造这个轮子不是为了替代引擎，而是把 §1-§5 的机制落到一个能通读的内核里。目标：**DAG 拓扑执行 + 条件分支 + 重试幂等 + 异常分支**，纯标准库，约 250 行。四条不变量（引擎的"宪法"，每条都对应前文的一个教训）：

| # | 不变量 | 对应前文 |
|---|---|---|
| I1 | **无环且引用必已产出**：拓扑排序排不出即拒绝执行；节点执行时依赖必须全部到达终态 | 画布连线约束（§5.1）；"上游字段下游契约"（§3.3） |
| I2 | **未选中分支只许"跳过"传播**：守卫不满足 → SKIPPED 向下游传染；聚合节点显式声明容忍 | ADP 意图分支"其他分支输出为空"（§2.6）；聚合原语（§3.1） |
| I3 | **重试必幂等**：配置了重试却未声明幂等的节点，引擎拒绝执行；副作用用幂等键去重 | ADP"避免重复建单或重复写入"（§5.3） |
| I4 | **失败必须可路由**：`on_error_of` 把失败交给异常分支节点，异常汇回主链路 | ADP"执行异常流程"（§5.4） |

### 8.2 机制讲解：五个部件

1. **图定义 = 节点 dict**：每个节点声明 `deps`（数据依赖，即画布连线）、`run`（执行函数，签名 `run(ctx) -> dict`）、`outputs`（输出契约：字段名 → 类型）。`ctx` 里带 `deps`（依赖节点输出）、`seed`（流程级输入）、`error`（异常分支拿到的错误）、`ikey`（幂等键）、`attempt`（尝试序号）。
2. **拓扑执行 = Kahn 算法**：按依赖序逐节点跑；排序排不出 = 有环，启动即拒绝（I1）。生产引擎在这一步之后天然可以并行化——就绪节点（依赖全部就绪）可同时执行。
3. **条件分支 = guard 原语**：`("classify.route", {"退款"})` 表示"本节点只在 route ∈ {退款} 时执行"；不满足 → SKIPPED（I2）。这比"ifelse 节点 + 两棵子树"更贴近画布的真实语义（ADP 3.3 的意图分支就是这样挂在各分支上的）。
4. **重试与幂等 = 幂等键**：`ikey = sha1(节点名 + 依赖输入指纹)`——同一输入的重试拿到同一个键；副作用函数（`submit_ticket`）按键去重，"副作用已发生但响应丢失"的重试不会重复建单（I3）。
5. **异常分支 = `on_error_of` 锚点**：节点声明"我承接谁的失败"；引擎把锚点并入其依赖（保证排序在锚点定案之后），锚点 FAILED 才执行，否则 SKIPPED。异常分支的输出经普通依赖汇回主链路（I4）。

### 8.3 完整代码（miniflow）

```python
# -*- coding: utf-8 -*-
"""
miniflow：最小工作流编排器 —— Python 3 纯标准库，教学用。

一个工作流引擎的最小内核 = 五件事：
  1. 图定义：节点 dict（deps 声明依赖 = 画布连线）
  2. 拓扑执行：按依赖序逐节点跑，天然可改造为并行
  3. 条件分支：guard 原语 —— 守卫不满足的分支标 SKIPPED 并向后传播
  4. 重试与幂等：要重试必须声明幂等，副作用用幂等键去重
  5. 异常分支：on_error_of 把失败变成一条可控路径，而不是崩掉整条流程

四条不变量：
  I1 无环且引用必已产出 —— 拓扑排序排不出即拒绝执行；节点执行时依赖必须全部到达终态
  I2 未选中分支只许"跳过"传播 —— SKIPPED 向下游传染，聚合节点显式声明容忍
  I3 重试必幂等 —— 非幂等节点配置重试 = 引擎拒绝执行
  I4 失败必须可路由 —— on_error 节点承接 FAILED，异常也能汇回主链路
"""
from __future__ import annotations

import hashlib
import json
import re
import time

# ---------------- 基础设施：审计与副作用登记 ----------------

AUDIT: list = []        # 执行审计：引擎做的每个决定都留痕（节点级日志的微缩版）
RUNBOOK: list = []      # 外部系统副作用登记簿：工单只能在这里真实发生


def audit(msg: str) -> None:
    AUDIT.append(msg)


def submit_ticket(ikey: str, content: str) -> str:
    """外部接口：创建工单。幂等键命中 = 重复调用被去重（I3 的执行点）。"""
    for t in RUNBOOK:
        if t["ikey"] == ikey:
            audit(f"[外部系统] 工单已存在（幂等键 {ikey}），拒绝重复建单")
            return t["id"]
    tid = f"T{len(RUNBOOK) + 1:03d}"
    RUNBOOK.append({"ikey": ikey, "id": tid, "content": content})
    audit(f"[外部系统] 工单 {tid} 已创建（幂等键 {ikey}）")
    return tid


class EngineError(RuntimeError):
    """图定义非法。"""


class ContractError(RuntimeError):
    """节点输出违反契约。"""


# ---------------- 执行器 ----------------

def _dig(deps: dict, path: str):
    """按 '节点.字段' 取变量（工作流变量引用的最小实现）。"""
    node, _, field = path.partition(".")
    val = deps.get(node)
    if val is None or not field:
        return val
    return val.get(field)


def _invoke(name: str, node: dict, ctx: dict) -> dict:
    """单节点执行：重试 + 幂等键 + 输出契约校验。抛出异常 = 本节点失败。"""
    retries = int(node.get("retries", 0))
    if retries and not node.get("idempotent"):
        # I3：生产引擎应在配置装载时拒绝；这里在执行时兜底
        raise EngineError(f"节点 {name} 配置了重试但未声明 idempotent=True（重试非幂等副作用会重复建单）")
    ctx["ikey"] = None
    if node.get("idempotent"):
        # 幂等键 = 节点名 + 依赖输入指纹：同一输入的重试拿到同一个键
        payload = json.dumps(ctx["deps"], sort_keys=True, ensure_ascii=False)
        ctx["ikey"] = hashlib.sha1(f"{name}|{payload}".encode("utf-8")).hexdigest()[:12]
    last: Exception = ContractError("未执行")
    for i in range(retries + 1):
        ctx["attempt"] = i + 1
        try:
            out = node["run"](ctx)
            for k, t in (node.get("outputs") or {}).items():  # 输出契约校验
                if k not in out:
                    raise ContractError(f"输出契约违约：缺字段 {k}")
                if not isinstance(out[k], t):
                    raise ContractError(f"输出契约违约：{k} 应为 {t.__name__}")
            audit(f"[{name}] 第 {i + 1} 次尝试成功")
            return out
        except Exception as e:
            last = e
            audit(f"[{name}] 第 {i + 1} 次尝试失败：{type(e).__name__}: {e}")
            if i < retries:
                time.sleep(node.get("interval", 0.03))
    raise last


def execute(nodes: dict, seed: dict):
    """执行整张图。返回 (results, states)。results 只含 OK 节点的输出。"""
    # 预处理：异常分支节点把锚点并入依赖，保证拓扑序上锚点先定案（I4 的排序前提）
    norm = {}
    for n, nd in nodes.items():
        nd = dict(nd)
        if "on_error_of" in nd:
            a = nd["on_error_of"]
            if a not in nodes:
                raise EngineError(f"异常分支 {n} 的锚点 {a} 不存在")
            nd["deps"] = sorted(set(nd.get("deps", [])) | {a})
        norm[n] = nd
    # I1 之无环：Kahn 拓扑排序，排不出 = 有环
    rev = {n: [] for n in norm}
    indeg = {}
    for n, nd in norm.items():
        for d in nd["deps"]:
            if d not in norm:
                raise EngineError(f"节点 {n} 引用了不存在的依赖 {d}")
            rev[d].append(n)
        indeg[n] = len(nd["deps"])
    ready = [n for n, v in indeg.items() if v == 0]
    order = []
    while ready:
        u = ready.pop()
        order.append(u)
        for v in rev[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                ready.append(v)
    if len(order) != len(norm):
        raise EngineError("图有环：拓扑排序未覆盖全部节点（I1）")
    # 按拓扑序执行
    results, states, errors = {}, {}, {}
    for name in order:
        node = norm[name]
        deps = node["deps"]
        # I1 之引用必已产出：依赖必须全部到达终态
        if any(d not in states for d in deps):
            raise EngineError(f"节点 {name} 的依赖未全部到达终态（图定义错误）")
        # I4：异常分支节点只承接锚定节点的 FAILED
        anchor = node.get("on_error_of")
        if anchor:
            if states.get(anchor) == "FAILED":
                audit(f"[{name}] 承接 {anchor} 的失败，进入异常分支")
                ctx = {"deps": {}, "seed": seed, "error": errors[anchor],
                       "attempt": 1, "ikey": None}
                out = _invoke(name, node, ctx)
                results[name], states[name] = out, "OK"
            else:
                states[name] = "SKIPPED"
                audit(f"[{name}] 锚定节点未失败 → SKIPPED")
            continue
        # 条件分支：守卫不满足 → SKIPPED（被路由抛弃的分支）
        guard = node.get("guard")
        if guard:
            path, allowed = guard
            gnode = path.split(".", 1)[0]
            if states.get(gnode) != "OK" or _dig(results, path) not in allowed:
                states[name] = "SKIPPED"
                audit(f"[{name}] 守卫 {path} ∈ {sorted(allowed)} 不满足 → SKIPPED")
                continue
        # I2：SKIPPED 向下游传播；tolerate_skip 的聚合节点在"至少一支成功"时照常执行
        if node.get("tolerate_skip"):
            if not any(states[d] == "OK" for d in deps):
                states[name] = "SKIPPED"
                audit(f"[{name}] 全部依赖未成功且无可容忍项 → SKIPPED")
                continue
            deps_view = {d: (results.get(d) if states[d] == "OK" else None) for d in deps}
        else:
            if any(states[d] != "OK" for d in deps):
                states[name] = "SKIPPED"
                audit(f"[{name}] 依赖未成功（{'/'.join(states[d] for d in deps)}）→ SKIPPED 传播")
                continue
            deps_view = {d: results[d] for d in deps}
        ctx = {"deps": deps_view, "seed": seed, "error": None, "attempt": 1, "ikey": None}
        try:
            out = _invoke(name, node, ctx)
            results[name], states[name] = out, "OK"
        except Exception as e:
            states[name] = "FAILED"
            errors[name] = f"{type(e).__name__}: {e}"
            audit(f"[{name}] 失败定案：{errors[name]}")
    return results, states


# ---------------- 业务节点（仿 ADP 3.3 售后客服工作流的微缩版）----------------

def _start(ctx):
    return {"query": ctx["seed"]["query"]}


def _extract(ctx):
    """参数提取节点（真实系统是 LLM 节点；这里用规则模拟，机制完全同构）。"""
    q = ctx["deps"]["start"]["query"]
    m = re.search(r"订单\s*([0-9]+)", q)
    prod = next((p for p in ("蓝牙耳机", "键盘", "鼠标") if p in q), "未知商品")
    appeal = "退款" if "退款" in q else "催发货"
    mood = "着急" if "着急" in q else ("愤怒" if "投诉" in q else "平静")
    return {"order_id": m.group(1) if m else "", "product": prod,
            "issue": q, "appeal": appeal, "mood": mood}


def _classify(ctx):
    """意图识别节点：输出 route 变量，供三个分支节点的 guard 引用。"""
    e = ctx["deps"]["extract"]
    if e["appeal"] == "退款":
        return {"route": "退款"}
    if "发货" in e["issue"] or "物流" in e["issue"]:
        return {"route": "物流"}
    return {"route": "转人工"}


def _br_ship(ctx):
    e = ctx["deps"]["extract"]
    return {"strategy": f"已安抚并核实发货状态：{e['product']}（{e['order_id']}）超时未发，将催促仓库并按平台规则处理。"}


_FLAKY = {"armed": False}  # 演示开关：外部接口"响应丢失"只注入一次


def _br_refund(ctx):
    """退款分支：先真实建单（带幂等键），再演示'副作用已发生但响应丢失'的重试。"""
    e = ctx["deps"]["extract"]
    tid = submit_ticket(ctx["ikey"], f"订单 {e['order_id']} 退款工单")
    if ctx["attempt"] == 1 and _FLAKY["armed"]:
        _FLAKY["armed"] = False
        raise ConnectionError("退款服务返回前连接中断（模拟）")
    return {"strategy": f"已核实订单 {e['order_id']} 符合退款政策，工单 {tid} 已提交，退款将原路退回。"}


def _br_human(ctx):
    return {"strategy": "问题需人工核实（涉及实时订单状态或投诉升级），已生成转人工说明。"}


def _fallback(ctx):
    """异常分支：承接失败节点，把异常翻译成用户可读的转人工话术（I4）。"""
    return {"text": f"您好，系统处理出现异常（{ctx['error']}），已为您转接人工客服，请提供订单号以便人工核实。"}


def _aggregate(ctx):
    """变量聚合节点：多分支汇成统一链路，容忍未选中的分支（I2 的容忍端）。"""
    skipped = [d for d, v in ctx["deps"].items() if v is None]
    hit = next((v["strategy"] for v in ctx["deps"].values() if v), "")
    return {"strategy": hit, "skipped": skipped}


def _reply(ctx):
    fb = ctx["deps"].get("fallback")
    if fb:  # 异常分支接管：fallback 有输出时直接采用
        return {"text": fb["text"]}
    agg = ctx["deps"]["aggregate"]
    note = "、".join(agg["skipped"]) or "无"
    return {"text": f"{agg['strategy']}（本次未走的分支：{note}）"}


def _boom(ctx):
    raise RuntimeError("LLM 节点故障（注入）")


NODES = {
    "start":     {"deps": [], "run": _start, "outputs": {"query": str}},
    "extract":   {"deps": ["start"], "run": _extract,
                  "outputs": {"order_id": str, "issue": str, "appeal": str, "mood": str}},
    "classify":  {"deps": ["extract"], "run": _classify, "outputs": {"route": str}},
    "br_ship":   {"deps": ["classify", "extract"], "guard": ("classify.route", {"物流"}),
                  "run": _br_ship, "outputs": {"strategy": str}},
    "br_refund": {"deps": ["classify", "extract"], "guard": ("classify.route", {"退款"}), "run": _br_refund,
                  "retries": 2, "interval": 0.05, "idempotent": True, "outputs": {"strategy": str}},
    "br_human":  {"deps": ["classify", "extract"], "guard": ("classify.route", {"转人工"}),
                  "run": _br_human, "outputs": {"strategy": str}},
    "fallback":  {"deps": [], "on_error_of": "extract", "run": _fallback, "outputs": {"text": str}},
    "aggregate": {"deps": ["br_ship", "br_refund", "br_human"], "tolerate_skip": True,
                  "run": _aggregate, "outputs": {"strategy": str, "skipped": list}},
    "reply":     {"deps": ["aggregate", "fallback"], "tolerate_skip": True,
                  "run": _reply, "outputs": {"text": str}},
}


def demo():
    print("== 场景 A：正常路径（含一次'副作用已发生但响应丢失' → 幂等重试）==")
    _FLAKY["armed"] = True
    results, states = execute(NODES, {"query": "我买的蓝牙耳机订单 20260709001，三天没发货，很着急，不行就退款"})
    for line in AUDIT:
        print("  ", line)
    print("  状态表：", {k: states[k] for k in NODES})
    print("  最终回复：", results["reply"]["text"])
    print("  副作用登记簿：", [t["id"] for t in RUNBOOK])

    AUDIT.clear()
    print("\n== 场景 B：注入参数提取节点故障 → 异常分支接管，异常汇回主链路 ==")
    broken = {k: dict(v) for k, v in NODES.items()}
    broken["extract"] = {"deps": ["start"], "run": _boom}
    results, states = execute(broken, {"query": "我买的蓝牙耳机三天没发货，要求退款"})
    for line in AUDIT:
        print("  ", line)
    print("  状态表：", {k: states[k] for k in NODES})
    print("  最终回复：", results["reply"]["text"])
    print("  副作用登记簿：", [t["id"] for t in RUNBOOK], "（场景 B 不应新增工单）")


if __name__ == "__main__":
    demo()
```

**读代码时对照四处"机制即正文"**：`_invoke` 的契约校验循环是 §3.3 规范一/三的执行点；`submit_ticket` 的幂等键去重是 §5.3"避免重复建单"的执行点；`guard` 判定 + SKIPPED 传播是 ADP 3.3 意图分支"其他分支输出为空"的代码形态；`on_error_of` 的锚点并入依赖是"异常汇回主链路"（§5.4）的实现方式。业务图就是 [ADP 3.3](../fde-handbook/tencent-adp-fde-course/lessons/3.3_单工作流模式实战：客服助手.md) 主链的微缩：开始 → 参数提取 → 意图识别 → 三分支 → 聚合 → 回复，外加异常分支。

### 8.4 本机实跑输出（2026-09-28，Python 3.13）

```text
== 场景 A：正常路径（含一次'副作用已发生但响应丢失' → 幂等重试）==
   [start] 第 1 次尝试成功
   [extract] 第 1 次尝试成功
   [fallback] 锚定节点未失败 → SKIPPED
   [classify] 第 1 次尝试成功
   [br_human] 守卫 classify.route ∈ ['转人工'] 不满足 → SKIPPED
   [外部系统] 工单 T001 已创建（幂等键 f20e1e9ccb3e）
   [br_refund] 第 1 次尝试失败：ConnectionError: 退款服务返回前连接中断（模拟）
   [外部系统] 工单已存在（幂等键 f20e1e9ccb3e），拒绝重复建单
   [br_refund] 第 2 次尝试成功
   [br_ship] 守卫 classify.route ∈ ['物流'] 不满足 → SKIPPED
   [aggregate] 第 1 次尝试成功
   [reply] 第 1 次尝试成功
  状态表： {'start': 'OK', 'extract': 'OK', 'classify': 'OK', 'br_ship': 'SKIPPED', 'br_refund': 'OK', 'br_human': 'SKIPPED', 'fallback': 'SKIPPED', 'aggregate': 'OK', 'reply': 'OK'}
  最终回复： 已核实订单 20260709001 符合退款政策，工单 T001 已提交，退款将原路退回。（本次未走的分支：br_ship、br_human）
  副作用登记簿： ['T001']

== 场景 B：注入参数提取节点故障 → 异常分支接管，异常汇回主链路 ==
   [start] 第 1 次尝试成功
   [extract] 第 1 次尝试失败：RuntimeError: LLM 节点故障（注入）
   [extract] 失败定案：RuntimeError: LLM 节点故障（注入）
   [fallback] 承接 extract 的失败，进入异常分支
   [fallback] 第 1 次尝试成功
   [classify] 依赖未成功（FAILED）→ SKIPPED 传播
   [br_human] 守卫 classify.route ∈ ['转人工'] 不满足 → SKIPPED
   [br_refund] 守卫 classify.route ∈ ['退款'] 不满足 → SKIPPED
   [br_ship] 守卫 classify.route ∈ ['物流'] 不满足 → SKIPPED
   [aggregate] 全部依赖未成功且无可容忍项 → SKIPPED
   [reply] 第 1 次尝试成功
  状态表： {'start': 'OK', 'extract': 'FAILED', 'classify': 'SKIPPED', 'br_ship': 'SKIPPED', 'br_refund': 'SKIPPED', 'br_human': 'SKIPPED', 'fallback': 'OK', 'aggregate': 'SKIPPED', 'reply': 'OK'}
  最终回复： 您好，系统处理出现异常（RuntimeError: LLM 节点故障（注入）），已为您转接人工客服，请提供订单号以便人工核实。
  副作用登记簿： ['T001'] （场景 B 不应新增工单）
```

两个场景各演示一条不变量的价值：场景 A 中**工单只建了一次**——第一次尝试的副作用已发生（T001），响应丢失触发重试，重试凭同一个幂等键被外部系统拒绝重复建单（§5.3 三要素的真实代价：没有幂等键，这次重试就是一笔重复退款）；场景 B 中**失败没有砸掉流程**——异常分支接管后汇回主链路，用户拿到"转人工"话术而不是报错（§5.4）。

### 8.5 miniflow 原语与真实引擎对照

| miniflow | 画布引擎（ADP/Dify） | 代码引擎（Temporal/LangGraph/Prefect） |
|---|---|---|
| `deps` 声明 | 画布连线 | LangGraph edge / Prefect task 调用 |
| `run(ctx)` | 节点详情页的处理逻辑 | Workflow 函数体 / Activity |
| `outputs` 契约 | 节点输出变量面板（字段名+类型） | LangGraph state schema / Mastra step schema（Zod） |
| `guard` | 意图识别分支 / ifelse 条件边 | LangGraph 条件 edge |
| SKIPPED 传播 | "分支未运行输出为空" | 不入图路径 |
| `tolerate_skip` 聚合 | 变量聚合节点 | reducer 合并 |
| `retries` + `idempotent` + `ikey` | 节点异常重试配置 | Temporal Retry Policy（默认 ∞ + 幂等期望） |
| `on_error_of` + `fallback` | "执行异常流程"连线 | Activity 失败 → 补偿 Workflow |
| `AUDIT` | 画布运行历史 / 节点状态视图 | Temporal 事件历史 / OTel span |
| `execute()` 拓扑序 | 画布执行引擎 | Prefect 并发子图 / LangGraph BSP 超步 |

### 8.6 常见坑 FAQ

1. **问：工作流和 agent 到底怎么选？** 用 §1.2 六问；现实答案是混合（§1.4）——骨架写死、关节让模型判断。反着来（全靠提示词约束流程）是最常见的翻车姿势（§3.2：能用结构解决的不要用提示词）。
2. **问：意图识别老分错支？** 三件事按序做：补**边界样例**到意图描述与示例（ADP 4.4"入住时间 vs 完成入住的耗时"）；分类器输出收敛为枚举（§3.3 规范三）；每条分支配兜底（"其他/转人工"分支必须是意图之一，不是可选项）。
3. **问：分支后面取变量是空的？** 这是分支语义不是 Bug：意图识别后只有一条分支运行、其他分支输出为空（§2.6）。下游用**变量聚合**（或 miniflow 的 `tolerate_skip`）显式容忍缺失；不要在下游"判空兜底"里藏业务逻辑。
4. **问：重试加了反而更糟？** 先分错误类型：瞬时错误（网络/限流）才重试，确定性错误（契约违约/参数错）重试无益（OpenCode 的 8 条瞬时错误正则 + overflow 不重试，§5.3）；再查幂等——外部写操作没有幂等键的重试就是重复建单（§8.4 场景 A 的反面）。
5. **问：LLM 节点里能"顺便"调外部系统写库吗？** 不能。副作用下沉到代码节点/Activity（Temporal 的 Workflow/Activity 两分法，§7.3）；LLM 节点只产出数据，副作用节点才配重试与幂等——否则"模型换个说法"就是一次重复写入。
6. **问：流程超过多少节点该拆子工作流？** 经验线 15-20 个节点或一个屏幕放不下（"拉面条"）。拆的接缝 = 高内聚的子流程 + 清晰的输入输出契约；子工作流同时是复用单元（ADP 结束节点输出变量的主用途就是"工作流调用工作流"，§3.1）。
7. **问：多分支同时写一个共享变量？** 不要让分支直写全局。OpenClaw 的 writer fence 只保证"只有一个写者提交"（§5.2），工作流侧的正解是**聚合节点统一汇流**（§3.1）——并行分支产出各自的输出，聚合点做合并裁决。
8. **问：审批挂半天，服务重启会丢吗？** 取决于挂起是否持久化（§5.5）：n8n Wait 存库、Temporal 等待进事件历史、LangGraph `interrupt()` 存 checkpointer——都不会丢；自己写的"sleep 等审批"会丢。挂起 = 把等待条件写进持久状态。
9. **问：画布引擎和代码引擎（LangGraph/Prefect/Temporal）怎么选？** 先选家族（§4.3）：运营可视化/交接 → 画布；工程团队、要版本管理与代码评审 → 代码态。中间态也存在：Dify 的代码节点、n8n 的 Function 节点都是"画布里嵌代码"，但结构复杂后维护成本反超代码态。
10. **问：LangGraph 的 `interrupt()` 恢复后为什么重复执行了？** 官方文档明示：恢复时节点从头重执行（§3.4）——挂起点之后的副作用必须幂等。这与 miniflow 的 I3 是同一条不变量，框架不会替你做。
11. **问：怎么知道该信引擎的哪些"智能"？** 引擎的可靠性来自**确定性内核**（拓扑、重试、状态），不是来自模型（§1.1）；凡是引擎把决策交给模型的地方（动态路由、agentic 节点），都自动继承 §1 的不可预测性——对照 [multiagent-handbook §6 失败治理](../multiagent-handbook/Multi-Agent协同手册.md) 配预算与熔断。
12. **问：工作流怎么接评测体系？** 三步（§6.6）：Badcase 入册成回归用例；流程配置纳入版本指纹（[eval-handbook §4](../eval-handbook/Agent评测与质量工程手册.md)）；节点级 trace 挂 OTel（[eval-handbook §7](../eval-handbook/Agent评测与质量工程手册.md)），失败归因定位到节点而不是"流程不稳定"。

### 8.7 上手清单

**30 分钟（建立手感）**：
- [ ] 跑通 §8.3 miniflow，把 §8.4 两个场景的输出逐行对上不变量；
- [ ] 改坏三件事观察三类失败：① 删掉 `br_refund` 的 `idempotent=True`（引擎应拒绝执行——I3）；② 删掉 `aggregate` 的 `tolerate_skip`（分支语义破坏，聚合变 SKIPPED——I2）；③ 给 `reply` 加回对 `aggregate` 的环形依赖（拓扑排序拒绝启动——I1）。

**2 小时（连到真模型）**：
- [ ] 把 `_extract`/`_classify` 的规则模拟换成真 LLM 调用（SDK 最小示例见 [python-handbook §3](../python-handbook/Python大模型应用开发手册.md)），提示词按 [prompt-handbook](../prompt-handbook/提示词搭建文档.md) 八区块写；
- [ ] 把 `AUDIT` 升级为 JSONL 落盘（只追加），对照 §6.4 感受"回放"的第一步。

**1 天（上引擎）**：
- [ ] 按 §4.3 决策树选一家引擎复刻 [ADP 3.3 客服工作流](../fde-handbook/tencent-adp-fde-course/lessons/3.3_单工作流模式实战：客服助手.md)（推荐 Dify 或 n8n 起步）；
- [ ] 把 §3.3 契约六条与 §6.6 Badcase 清单逐条映射到引擎的配置项；
- [ ] 发布前给流程配三个测试问句（各意图一支 + 异常一支），发布后**从用户侧再测一次**（§6.5 纪律三）。

---

## 参考资料

**方法论**
- Anthropic，《Building Effective Agents》（2024-12，五种 pattern 与 workflow/agent 定义出处）：https://www.anthropic.com/engineering/building-effective-agents

**腾讯 ADP 一手课程与官网（本工作区整理）**
- 课程整理总入口：[fde-handbook/tencent-adp-fde-course/README.md](../fde-handbook/tencent-adp-fde-course/README.md)（4 章 19 节 + 266 图，2026-09-26 提取）
- 本文三份一手底稿：[2.2下 任务执行与编排能力](../fde-handbook/tencent-adp-fde-course/lessons/2.2下_任务执行与编排能力：Workflow、Multi-Agent_与_Claw.md) ｜ [3.3 单工作流模式实战](../fde-handbook/tencent-adp-fde-course/lessons/3.3_单工作流模式实战：客服助手.md) ｜ [4.4 Workflow 调优](../fde-handbook/tencent-adp-fde-course/lessons/4.4_Workflow_调优.md)
- ADP 产品页（四种模式 / Agent-Workflow 双向互调 / Agent Harness，2026-09-28 实抓）：https://cloud.tencent.com/product/adp

**引擎与框架（star/版本均为 2026-09-28 实抓）**
- n8n：https://github.com/n8n-io/n8n ｜ https://docs.n8n.io/build/integrate-ai.md ｜ https://docs.n8n.io/integrations/builtin/cluster-nodes/ ｜ https://docs.n8n.io/build/integrate-ai/ai-examples/human-in-the-loop-for-tools.md ｜ https://registry.npmjs.org/n8n/latest
- Dify：https://github.com/langgenius/dify ｜ https://docs.dify.ai/en/cloud/use-dify/build/workflow-chatflow ｜ https://docs.dify.ai/en/cloud/use-dify/nodes/
- LangFlow：https://github.com/langflow-ai/langflow ｜ Coze Studio：https://github.com/coze-dev/coze-studio ｜ Flowise（已归档）：https://github.com/FlowiseAI/Flowise
- Temporal：https://github.com/temporalio/temporal ｜ https://docs.temporal.io/retry-policies ｜ https://docs.temporal.io/develop/python/workflows/message-passing
- Prefect：https://github.com/PrefectHQ/prefect ｜ https://docs.prefect.io/v3/concepts/flows-and-tasks
- LangGraph：https://github.com/langchain-ai/langgraph ｜ https://docs.langchain.com/oss/python/langgraph/overview ｜ https://docs.langchain.com/oss/python/langgraph/interrupts ｜ PyPI：https://pypi.org/pypi/langgraph/json
- Mastra：https://github.com/mastra-ai/mastra ｜ https://mastra.ai/docs/workflows/overview ｜ Windmill：https://github.com/windmill-labs/windmill ｜ Activepieces：https://github.com/activepieces/activepieces ｜ Hatchet：https://github.com/hatchet-dev/hatchet

**本工作区交叉引用**
- 同坐标系两半：[multiagent-handbook §2.0 workflow/agent 区分与 §2 编排范式](../multiagent-handbook/Multi-Agent协同手册.md)（本文 §1.1/§2 与之互为对照）
- 一手源码证据：六份《架构拆解》的编排面（[01 §3/§5/§7](../01-claude-code/架构拆解.md) ｜ [02 §3/§4.3/§5](../02-codex/架构拆解.md) ｜ [03 §4/§5/§8](../03-deepseek-harness/架构拆解.md) ｜ [04 §5/§9/§10.3](../04-zcode/架构拆解.md) ｜ [05 §4/§7/§9](../05-openclaw/架构拆解.md) ｜ [06 §4/§8/§10](../06-opencode/架构拆解.md)）
- LangGraph 引擎语义源码级详解：[08-langgraph/源码解析与学习路线.md](../08-langgraph/源码解析与学习路线.md)（BSP 超步/checkpoint/reducer，本文 §4.2.7 不重复）
- 评测与调试闭环：[eval-handbook](../eval-handbook/Agent评测与质量工程手册.md)（轨迹评测/版本指纹/OTel GenAI/Langfuse·Phoenix 横评，本文 §6.3/§6.5/§8.6-12 复用）
- 上下文与状态：[context-handbook §2"日志为真源"](../context-handbook/Context与记忆系统手册.md)（本文 §5.2 唯一真源不变量的源码出处）
- 提示词与 LLM 节点：[prompt-handbook](../prompt-handbook/提示词搭建文档.md)（节点提示词的写法）与 [python-handbook §3 SDK 最小示例](../python-handbook/Python大模型应用开发手册.md)（§8.7 上手清单的真模型替换）
- 知识检索节点背后的知识管线：[rag-handbook](../rag-handbook/RAG搭建文档.md)（Dify/ADP 知识库节点的上游工程）

---

> 本文信息基准日 2026-09-28：12 个引擎仓库的 star、license、最新 release 与维护状态当日经 GitHub API / npm / PyPI 实抓（Flowise 归档、coze-studio 放缓为当日核实的关键事实）；各引擎机制细节取自官方文档当日版并逐一标注 URL；ADP 部分以本工作区 2026-09-26 提取的认证课程全文为一手底稿（4.4 节原文链接见参考资料），产品页信息为 2026-09-28 补抓。§8 miniflow 已在 Python 3.13 本机跑通，输出为实跑记录。引擎迭代快，数字与版本以仓库现状为准。
