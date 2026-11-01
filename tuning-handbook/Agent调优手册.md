# Agent 调优手册：总纲与失败分类学 · Prompt · 检索/RAG · 工作流编排 · Multi-Agent · 模型与参数 · 成本与延迟工程 · 企业范例 · 最小实验框架

> 信息基准日：2026-09-28。**Agent 调优（tuning）没有像 MCP 那样的统一协议规范**——本文的"调优"指一个收敛中的工程实践集：在固定评测集上定位瓶颈、做单变量变更、过回归门禁、固化成果的闭环方法，以及分层展开的 Prompt / 检索 / 工作流 / 多智能体 / 模型参数 / 成本延迟六条调优战线。模型价格、缓存折扣、仓库 star 与版本均为当日对各官方定价页与 GitHub API 的实际抓取，随时间漂移，以官方页面为准。
>
> 本工作区惯例是结论带 `文件:行号`；本文是网络调研文档，等价做法是**结论带来源链接**（各节末尾标 URL）。英文术语在首次出现处标注中文。

---

## 0. TL;DR

- **调优（tuning）是评测的下游、上线的上游**：没有度量就没有调优。腾讯 ADP 课程给的正确姿势是"单次调试解决'这条为什么错'，批量评测证明'整体是否变好'，回归（regression）保证'修好一个问题没引入三个新问题'"（ADP 课程 4.1，平台化课程版见 [eval-handbook §1.3](../eval-handbook/Agent评测与质量工程手册.md)）。本文把这个闭环收敛为五步：**定位瓶颈 → 形成假设 → 单变量变更 → 回归评测 → 固化**，全程"每次只改一个主要变量"（ADP 4.2 原话），判定用"能用代码验证的绝不交给 LLM 打分"（[eval-handbook §2.3](../eval-handbook/Agent评测与质量工程手册.md)）。
- **失败是有分类学的（fail taxonomy，失败分类学）**：六类失败——检索没召回 / 推理跑偏 / 工具误用 / 格式不合规 / 延迟超预算 / 成本失控——各有专属调优手段（§1.2 映射表）。"回答不对"只是表象，先分诊（triage）到层，再动手；ADP 4.1 的单次调试快速诊断表与 4.3 的"三问分诊"（有没有知识→有没有命中→有没有正确生成）是同一思想。
- **Prompt 调优的四个杠杆**：system prompt 结构（八区块模板，[prompt-handbook §2.4](../prompt-handbook/提示词搭建文档.md)）、few-shot（少样本示例）选择与排序（1-3 个典型示例 + 头尾位置，§2.2）、CoT/ReAct 触发词的适用边界（快思考模型有效、推理模型上可能画蛇添足，§2.3）、**提示缓存（prompt caching）**（Anthropic 读价 0.1×、OpenAI 缓存输入 10% 价且延迟最高降 80%，把稳定前缀放前面是成本第一杠杆，§2.4）。
- **RAG 调优先分诊再调参**：检索没召回查 chunk 与检索参数，召回了但答案错查生成约束与忠实度（faithfulness）；chunk 的目标"既容易命中、又能独立支撑回答"（ADP 4.3）；混合检索 + 重排（rerank）+ 父子切分是生产三件套（[rag-handbook §3.3](../rag-handbook/RAG搭建文档.md)）；查询改写（query rewriting）用 HyDE / multi-query 处理口语化问法。
- **工作流调优从场景边界开始**：输入/处理/输出说不清的流程调不稳（ADP 4.4）；节点选型错（标签提取节点硬凑参数收集）prompt 写得再细也没用；单节点调试与端到端调试要结合；重试必须带幂等（idempotency）约束；人在环（HITL, human-in-the-loop）插在"低置信度出口"而不是到处插。
- **Multi-Agent 调优多数时候是"减法"**：Anthropic 实测多 pass 配置 90.2% 任务提升但 token 翻 15×（[multiagent-handbook §1.2](../multiagent-handbook/Multi-Agent协同手册.md)）；角色划分先过四问判据，转交不稳定优先降级为工作流编排或合并回单 agent（ADP 4.5）；工具返回必须具名 JSON，确定性逻辑（时间戳/编号/计算）放进工具而不是提示词。
- **参数调优的当代表**：temperature 0 用于判定与抽取、0.3-0.7 用于生成；参数跟角色走（OpenCode 给每个 agent 独立 temperature/topP，§6.1）；推理模型管规划与判卷、快思考小模型管分类抽取改写，价差 7-35×（当日实抓，§6.6）；上下文窗口不是免费午餐（Gemini 超 200k 输入翻倍，§6.6）；模型路由（routing）能砍大头，但路由器自己也要过评测集（[eval-handbook §8.2](../eval-handbook/Agent评测与质量工程手册.md)）。
- **成本与延迟是约束不是事后项**：成本 = Σ(每档 token × 单价)，档位有四档（普通输入 / 缓存写 / 缓存读 / 输出，输出比输入贵 4-10×）；缓存命中率是第一杠杆；批处理 API（batch）与错峰一律 -50%（当日实抓四家）；延迟预算按 TTFT（首字延迟）/ 生成速率 / 工具往返分解（§7.5）。**成本-质量-延迟三角**没有全能解，只有显式取舍（§7.6 取舍表）。
- **企业范例（当日实抓）**：promptfoo（2.55 万 star，配置驱动的 A/B 与 CI 门禁）、DSPy（3.84 万，"调优=编译"，把提示词当参数自动搜索）、azure-search-openai-demo（7.8 千，微软官方 RAG 参数化样板）三家精读见 §8；六家 agent 源码里也各有内建调优机制可对照（§8.5）。
- **§9 给了一个 200 行级最小调优实验框架**（Python 3 纯标准库，**已本机验证**）：数据集切片（分层 + 固定 seed）、同集 A/B 配对比较、指标回归门禁（非劣 + 分场景不回退 + held-out 复跑 + 指纹固化）。写它时真实踩出的一个坑——**门禁必须用同一切分的同类指标相比**——已写进 FAQ。

**阅读路线**：建立方法论 → 读 §1；按调优战线直接跳转：Prompt → §2、检索 → §3、工作流 → §4、多智能体 → §5、模型参数 → §6、成本延迟 → §7；想抄作业 → §8；30 分钟跑通闭环 → §9。与既有内容的接口见 §1.4 的分工表。

---

## 1. 调优总纲：度量驱动的闭环

### 1.1 闭环五步：定位瓶颈 → 假设 → 单变量变更 → 回归评测 → 固化

agent 是多环节系统（意图理解 → 检索 → 规划 → 工具调用 → 生成 → 格式化），"回答不对"是所有环节误差的汇合点。调优的全部方法论可以压缩成一条流水线：

```mermaid
flowchart LR
    A["① 定位瓶颈<br/>trace/调试视图分诊到层"] --> B["② 形成假设<br/>'格式不稳是缺输出约束'"]
    B --> C["③ 单变量变更<br/>只改一处，其余冻结"]
    C --> D["④ 回归评测<br/>固定集 A/B + 分场景不回退"]
    D -->|未过| B
    D -->|通过| E["⑤ 固化<br/>版本记录 + 指纹 + 基线更新"]
    E -.线上 badcase 回流.-> A
```

每一步的纪律都来自既有手册，本文只做引用与收口：

| 步骤 | 纪律 | 出处 |
|---|---|---|
| ① 定位瓶颈 | 单次调试五步法（定目标→可解释输入→看全链路→一次改一个→复测+相邻检查）；"不只看最终回复，还要看中间变量、检索结果、节点输出和工具返回" | ADP 4.1；[eval-handbook §6 轨迹评测](../eval-handbook/Agent评测与质量工程手册.md) |
| ② 形成假设 | 按失败分类学（§1.2）反推最可能出错的环节；"根据问题现象反推最可能出错的环节，而不是反复追问直到某次看起来满意" | ADP 4.1/4.2 |
| ③ 单变量变更 | **"每轮只改一个主要变量"**——同时改 prompt、模型、知识库、检索参数会让效果变好也无法归因、变差也无法回滚 | ADP 4.2 原话；[prompt-handbook §6.1 评测先行](../prompt-handbook/提示词搭建文档.md) |
| ④ 回归评测 | 固定样本复测"同类问题改善且没有引入新问题"；判据用代码 > 规则 > 裁判模型；judge 必须先校准 | ADP 4.1/4.2；[eval-handbook §2.3/§5.4](../eval-handbook/Agent评测与质量工程手册.md) |
| ⑤ 固化 | 保留"问题/期望/实际/归因/动作/复测"六项记录与版本记录；基线更新带指纹；badcase 清洗成回归样本 | ADP 4.2；[rag-handbook §6.4 坏例回流](../rag-handbook/RAG搭建文档.md) |

**不变量：闭环的入口是度量，不是直觉。** 没有固定评测集就没有"变好"的定义——这时唯一正确的动作是先建评测集（[eval-handbook §4](../eval-handbook/Agent评测与质量工程手册.md)：50-150 条起步、多样性比数量重要、来源优先生产日志），而不是先改 prompt。

### 1.2 失败分类学：六类失败 × 调优手段映射表

本文的失败分类（fail taxonomy，失败分类学）在 eval-handbook 的轨迹归因五分类（工具错/规划错/幻觉/环境错/判据错，[eval-handbook §6.3](../eval-handbook/Agent评测与质量工程手册.md)）之上，按**调优战线**重新切分——每一类失败对应本文的一节：

| # | 失败类 | 典型现象 | 优先怀疑 | 首选调优手段 | 详见 |
|---|---|---|---|---|---|
| F1 | **检索没召回** | 知识库"明明有"但答错/答不全；引用缺失 | 知识准备→切分→检索参数→检索范围 | 文档规范化、chunk 重切、混合检索+重排、查询改写、问答对沉淀 | §3 |
| F2 | **推理跑偏** | 命中了资料仍扩展无依据内容、意图走错分支、复杂问题答非所问 | 任务/依据/边界/格式要素缺失，或模型能力不足 | system prompt 补齐四要素、few-shot、问题分解、必要时升级模型 | §2 |
| F3 | **工具误用** | 幻觉工具、参数错、漏字段硬调、返回值被误读 | 工具名称/描述/入参说明不清楚；缺字段追问缺失 | 工具描述重写、参数提取节点+缺失追问、返回值具名 JSON、失败兜底 | §3.5/§4.1/§5.2 |
| F4 | **格式不合规** | 下游 JSON 解析失败、字段名漂移、多一段解释文字 | 输出约束不明确；解析端无容错 | 结构化输出模式/固定字段模板+校验重试、确定性逻辑工具化 | §6.3 |
| F5 | **延迟超预算** | P95 超时、用户流失、任务被上游掐断 | 串行长链、上下文过长、模型过大、无超时预算 | 并行化、缓存、小模型路由、per-task 超时与预算熔断 | §7.5 |
| F6 | **成本失控** | 账单爆炸、单任务 token 异常、缓存命中率趋零 | 全量大模型、无缓存前缀、循环调用、无预算熔断 | 模型路由/级联降级、缓存前缀工程、批处理、预算断言 | §6.5/§7 |

两个使用要点：

1. **同一表象可能映射多个失败类**。ADP 4.1 的快速诊断表就是为此准备的：同样是"回答错误"，可能是意图分支走错（F2）也可能是知识没命中（F1）；同样是"流程失败"，可能是变量没提取出来（F3）也可能是节点条件写错。**先看中间信号（检索命中、变量、节点输出、工具返回），再选失败类**。
2. **F5/F6 是"约束型失败"**：它们不改变答案的对错，但在生产上是事故。把延迟与成本做成轨迹断言（`over_budget`，[eval-handbook §6.2](../eval-handbook/Agent评测与质量工程手册.md)），让它们在评测里"可见"，是 F5/F6 调优的前提。

### 1.3 单次调试 / 批量评测 / 回归的分工

ADP 4.1 给的节奏是三段式，与 [eval-handbook §2.2](../eval-handbook/Agent评测与质量工程手册.md) 的三时机一一对应：

| 阶段 | 回答的问题 | 用什么 | 产出 |
|---|---|---|---|
| 单次调试（搭建中） | "这一条为什么错？错在哪一环？" | 调试视图：链路、检索命中、变量、节点、工具返回 | 六项调试记录（问题/期望/实际/归因/动作/复测） |
| 批量评测（基本成型后） | "整体是否稳定？A 版还是 B 版好？" | 评测集 + 判据（代码/规则/裁判模型）+ 对比评测 | 指标报告（分场景） |
| 回归（每次重要优化后） | "修好旧问题了吗？有没有引入新问题？" | 固定回归集 + 分场景门禁 | 基线更新记录 |

顺序不可跳：主链路没跑通就上批量评测，失败信号无法归因（可能是变量没传、工具没配好，而不是模型差）；只有单次调试没有回归，就会陷入"按下葫芦浮起瓢"。

### 1.4 与本工作区既有手册的分工

| 手册/资料 | 调优相关内容 | 本文分工 |
|---|---|---|
| [eval-handbook](../eval-handbook/Agent评测与质量工程手册.md) | 评测体系全套：评测集/judge 校准/轨迹归因/成本核算 | 本文把评测**当作调优闭环的一环**用（§1），不再重复它的方法论；判定与门禁直接引用其判据优先级与 judge 校准纪律 |
| ADP 课程 [4.1-4.5](../fde-handbook/tencent-adp-fde-course/lessons/4.1_智能体调试与评测基础.md) | 平台化课程版：调试五步法 / Prompt 调优 / 知识库 RAG 调优 / Workflow 调优 / Multi-Agent 调优 | 本文的**开源实现路径**：课程教"在平台上点哪里"，本文讲"参数背后的机制与不变量"，四节课分别展开为本文 §2-§5 的正面战场 |
| [prompt-handbook](../prompt-handbook/提示词搭建文档.md) | 提示词写法：八区块模板/官方八技法六策略/迭代方法论 | 本文 §2 只讲**调优动作**（few-shot 排序、触发词实证、缓存），写法在那边 |
| [rag-handbook](../rag-handbook/RAG搭建文档.md) | RAG 系统搭建：切分规范/检索接口/评测迭代 | 本文 §3 只讲**调参动作与分诊**，架构与规范在那边 |
| [workflow-handbook](../workflow-handbook/Agent工作流编排手册.md) | 工作流编排全套：何时用工作流/模式谱系五种/节点与契约/引擎横评 12 家（当日实抓）/状态与数据流/调试可观测/最小编排器 | 本文 §4 只讲**调优动作**（粒度/并行/路由降级/重试超时/HITL 插点），编排怎么建在那边；ADP 4.4 的 Badcase 方法论两边共用 |
| [multiagent-handbook](../multiagent-handbook/Multi-Agent协同手册.md) | 何时多 agent/编排范式/失败治理（MAST） | 本文 §5 只讲**协同参数怎么调**（转交描述、通信瘦身、合并时机），范式与治理在那边 |
| [context-handbook](../context-handbook/Context与记忆系统手册.md) | 上下文预算/三层压缩/缓存锚点 | 本文 §6.4 截断策略直接引用其"剪枝先于摘要、日志为真源"不变量，不重复展开 |
| [python-handbook](../python-handbook/Python大模型应用开发手册.md) | SDK 调用（§3）与评测三件套（§8） | 本文代码里接真模型的换装说明指向它 |
| 六家《架构拆解》 | 六家 agent 的上下文/压缩/成本/provider 章节 | §8.5 对照六家的内建调优机制 |

> 来源：ADP 课程 4.1-4.5（本工作区 [fde-handbook/tencent-adp-fde-course/lessons/](../fde-handbook/tencent-adp-fde-course/lessons/4.1_智能体调试与评测基础.md)）；[eval-handbook §1.3/§2.3/§6.3/§8](../eval-handbook/Agent评测与质量工程手册.md)

---

## 2. Prompt 调优

Prompt 效果不好，通常不是"写得不够长"，而是**任务、依据、边界、格式、上下文或模型配置**中有要素缺失（ADP 4.2）。所以 Prompt 调优的第一步永远是先问：这个 badcase 是"没听懂任务"（F2），"没拿到正确依据"（F1），还是"输出没被约束"（F4）——**知识没命中时单纯加长 Prompt 治不了根因**。

### 2.1 system prompt 结构：模板是检查清单，不是话术

写法细节见 [prompt-handbook §2.4](../prompt-handbook/提示词搭建文档.md) 的八区块模板与六家 agent 生产提示词拆解；从**调优视角**只需记住两条：

1. **模板的价值是"要素齐全"**。ADP 4.2 的通用模板七要素——角色、背景、目标、依据、步骤、边界、输出——每一条都对应一类失败：缺"依据"出 F2（编造）、缺"边界"出 F3（越权）、缺"输出"出 F4（格式漂移）。调优时逐要素对照缺哪补哪，而不是整段重写。
2. **写在哪一层是调优动作**。ADP 4.2 的分层裁决：全局风格/身份 → 角色指令；"命中了但不会用" → 用户输入模板与依据规则；单节点不稳 → 该节点提示词；工具调用失败 → 工具说明与异常返回处理。这与 [prompt-handbook §5.2](../prompt-handbook/提示词搭建文档.md) 的层级作用域一致——**先找准配置位置，再动笔**。

给模型留"中间出口"是稳态设计的一部分：不要只给对/错二选一，允许输出"无法确认 / 需补充信息 / 建议转人工"（ADP 4.2）。这条出口在评测里就是判据（拒答正确也算通过），在生产里就是 HITL 插点（§4.6）。

### 2.2 few-shot 示例：选择与排序

| 决策 | 做法 | 依据 |
|---|---|---|
| **要不要加** | 输出格式/判断标准/语气"不容易说清楚"时，1-3 个高质量示例通常胜过继续堆规则 | ADP 4.2 |
| **选哪些** | 一个标准样例 + 一个边界样例 + 一个缺失信息样例——让模型既会正常处理，也知道高风险输入怎么兜底 | ADP 4.2 |
| **放哪里** | 关键示例放开头或结尾，别指望模型记住"中间"；示例块放系统提示词稳定区还能吃缓存 | "lost in the middle"位置偏差（Liu et al. 2023，arXiv:2307.03172） |
| **换不换** | 示例随检索/任务类型动态选（按相似度取 1-3 条）时，注意**动态内容会打断缓存前缀**——把稳定示例放前缀、动态部分放后缀（§2.4） | 本文 §2.4 |
| **加多少** | 长上下文模型可放大示例数（many-shot，示例数与性能近似对数关系），但 token 成本与"过度模仿样例"风险同步上升 | Agarwal et al. 2024，arXiv:2404.11018 |

**反模式**：示例越多越好（占上下文+引发过度模仿）；只给标准样例不给边界样例（模型不会拒答）；把每次变化的内容（日期、用户数据）写进本该稳定的示例区（破坏缓存）。

### 2.3 CoT / ReAct 触发词的实证边界

- **快思考模型（非推理模型）**：零样本 CoT（"让我们一步一步思考"，Let's think step by step）在推理类任务上有可复现的提升——这是 Kojima et al. 2022 的原始实证（arXiv:2205.11916）；ReAct（推理+行动交替，Reason+Act）是 agent 主循环里"边想边调工具"范式的来源（Yao et al. 2022，arXiv:2210.03629）。六家 agent 的主循环几乎全是 ReAct 变体（见各《架构拆解》主循环章节）。
- **推理模型（reasoning models）**：模型自带内部推理预算，外部触发词的边际收益消失甚至为负——官方指南的建议是**对推理模型少手工 CoT、把约束写清楚，让模型自己规划**（OpenAI prompt engineering 指南的 general advice：不要对推理模型堆"step by step"类提示；Anthropic 对 extended thinking 的建议同向）。DeepSeek 当日现役两档模型均提供 thinking / non-thinking 双模式开关（§6.6 实抓）——**"要不要 CoT"已经从提示词层下沉到了模型档位层**。
- **实证口径**：触发词有没有用，不要抄结论，在自己的评测集上跑 A/B（§9 的框架就是干这个的）。ADP 4.2 的四组 Before/After 对比里，真正稳定提升的从来不是"加一句思考"，而是**补齐依据、边界与输出约束**。
- **judge 场景的触发词**：判分协议里"先摘录证据再打分"（evidence-before-score）等价于 CoT-before-score，能显著压幻觉判分（[eval-handbook §5.3](../eval-handbook/Agent评测与质量工程手册.md)）——这是触发词在 2026 年最确定的正面用例。

### 2.4 提示缓存（prompt caching）：成本与延迟的第一杠杆

agent 每轮都重发整个上下文（历史 + 系统提示词 + 工具定义），**缓存命中率（hit rate）直接决定账单形状**。两大平台的机制当日实抓：

| 维度 | Anthropic（显式缓存） | OpenAI（自动缓存） |
|---|---|---|
| 触发方式 | 在消息/工具上手动加 `cache_control` 断点，**最多 4 个**，位置向后生效（可回看最近 20 个消息块） | **自动**：提示 ≥1024 token 即尝试前缀缓存，无需配置 |
| 计价 | 缓存**写** 1.25×（5 分钟 TTL）/ 2×（1 小时 TTL）；缓存**读** 0.1× 基础输入价 | 缓存输入按**10% 价**计（gpt-5.x 系；gpt-4.1 系 25%、gpt-4o 系 50%，见 §6.6 表） |
| 生命周期 | 默认 TTL 5 分钟，命中即刷新；1 小时 TTL 需显式声明 | 内存驻留 5-10 分钟（非活动），最长 1 小时；gpt-5.2/5.1/5/4.1 可用 `prompt_cache_retention="24h"` 延长 |
| 最小缓存长度 | 1024 token（Opus/Sonnet 4.x+）、4096（Haiku 4.5）、2048（Haiku 3.x） | 1024 token |
| 延迟收益 | 官方示例约 2× 提速量级（长提示场景） | **延迟最高降约 80%** |
| 工程要点 | 前缀精确匹配（org 隔离）；工具定义→系统提示词→消息 的顺序就是缓存友好顺序；断点放"稳定段末尾" | `prompt_cache_key` 显式分组路由；同前缀流量 **~15 req/min** 上限，超过会溢出到其他缓存机器 |
| 作用域 | 同一组织内共享 | 前缀+key 维度 |

两条直接推论（与 [eval-handbook §8.1](../eval-handbook/Agent评测与质量工程手册.md) 的档位表互证）：

1. **稳定前缀工程**：系统提示词、工具定义、few-shot 稳定区放在最前并保持字节级稳定（时间戳、随机 ID 这类"每轮都变"的内容一旦混进前缀，缓存全灭）；动态内容（检索结果、用户输入）一律放后缀。六家 agent 里 ZCode 把这件事做成了显式契约——system prompt 每段带 `cacheHint:"stable"`，循环统一在 provider 可见投影之后设置 cache-control（[04-zcode/架构拆解.md §8.1](../04-zcode/架构拆解.md)，`CLI:core/src/context/builder.ts:82-223`、`turn-loop.ts:168-186`）。
2. **命中率要当指标看**：usage 里的 `cache_read_input_tokens`（Anthropic）/ `prompt_tokens_details.cached_tokens`（OpenAI）要进 trace 与成本报表，命中率趋零通常意味着"有东西在前缀里漂"——最常见的元凶是拼接了当前时间或流水号。

语义缓存（semantic cache，语义相近问题命中同一条缓存）与模型路由叠加的综合省钱报道在 60-85%，但其正确性风险（两个"语义相近"问题答案不同）要求相似度阈值+失效策略（[eval-handbook §8.1](../eval-handbook/Agent评测与质量工程手册.md)，数字出处同）。

### 2.5 最小示例：单变量 Prompt A/B

```python
# prompt_ab.py —— 单变量 Prompt A/B 的最小形态（§9 是完整框架）。
# 不变量：两个版本只差一处变更；同一批样本、同一判据、温度 0。
import json
PROMPTS = {
  "v0": "你是客服助手，请友好回答。",
  "v1": "你是客服助手。仅依据资料回答；无依据时回复\"当前资料无法确认\"并建议转人工。",
}
def judge(ans, expect, forbidden):
    return all(k in ans for k in expect) and not any(k in ans for k in forbidden)
CASES = [  # (query, kb, expect, forbidden)
    ("退款几天到账？", None, ["无法确认"], ["马上退"]),
    ("退货政策？", "7 天内可退", ["7 天"], []),
]
def agent(prompt, query, kb):
    return "签收后 7 天内可退" if kb and "退货" in query else "当前资料无法确认，建议转人工"
for name, p in PROMPTS.items():
    r = [judge(agent(p, q, kb), exp, forb) for q, kb, exp, forb in CASES]
    print(name, f"{sum(r)}/{len(r)}")
# v0 0/2（编造"马上退"或漏依据）；v1 2/2 —— 差异全部归因到那一句约束。
```

> 本章来源：ADP 课程 [4.2](../fde-handbook/tencent-adp-fde-course/lessons/4.2_Prompt_调优.md) ｜ [Anthropic prompt caching 文档](https://docs.claude.com/en/docs/build-with-claude/prompt-caching) ｜ [OpenAI prompt caching 指南](https://platform.openai.com/docs/guides/prompt-caching) ｜ Kojima et al. https://arxiv.org/abs/2205.11916 ｜ ReAct https://arxiv.org/abs/2210.03629 ｜ lost-in-the-middle https://arxiv.org/abs/2307.03172 ｜ many-shot https://arxiv.org/abs/2404.11018 ｜ [OpenAI prompt engineering 指南](https://platform.openai.com/docs/guides/prompt-engineering) ｜ [prompt-handbook §5.3/§6](../prompt-handbook/提示词搭建文档.md)

---

## 3. 检索与 RAG 调优

架构与搭建见 [rag-handbook](../rag-handbook/RAG搭建文档.md)；本章只回答调优三问：**现象怎么分诊（triage，分诊）、参数怎么调、改写怎么上**。

### 3.1 分诊先行：召回率与忠实度是两个指标，别混着治

ADP 4.3 的三问分诊是本章的入口：

```mermaid
flowchart TB
    Q["知识问答 badcase"] --> Q1{"知识库里有没有？"}
    Q1 -->|没有| A["F1a 知识缺失：补文档/问答对<br/>先整理再入库（§3.2）"]
    Q1 -->|有| Q2{"检索命中了吗？"}
    Q2 -->|没命中| B["F1b 召回失败：chunk/检索参数/改写（§3.3-3.4）"]
    Q2 -->|命中但排序靠后| C["F1c 排序失败：重排（rerank）与召回数（§3.3）"]
    Q2 -->|命中且回答错| D{"答案与召回片段对照"}
    D -->|扩展了片段外内容| E["F2 忠实度：生成约束不足（§2.1）"]
    D -->|片段本身旧/冲突| F["F1d 知识治理：版本/下线/冲突合并"]
```

对应两把尺子——**召回率（recall）**评"该找到的找到没有"（Recall@k、命中块断言），**忠实度（faithfulness）**评"答案是否忠于召回片段"（RAGAS 的 faithfulness，工具用法见 [python-handbook §8](../python-handbook/Python大模型应用开发手册.md)）。**答案错先看答案是否忠于片段：忠于片段→是检索问题（治 F1）；不忠于片段→是生成约束问题（治 F2/F4）**。分错了方向，调参就是在错层上使劲。

### 3.2 chunk 策略：调优目标是"既容易命中，又能独立支撑回答"

ADP 4.3 的判据（与 [rag-handbook §2.2](../rag-handbook/RAG搭建文档.md) 的切分规范互补）：

| 信号 | 诊断 | 动作 |
|---|---|---|
| 片段只命中了结论，缺条件/例外 | 切分割裂上下文 | 增大片段或加重叠 |
| 只命中表格数据没有表头 | 表格切分不当 | 表格按行切分并带表头（ADP 支持 5 行表头范围） |
| 高频口语问法不命中 | 问法与文档措辞差距大 | 沉淀问答对（§3.4），而不是硬调参数 |
| 命中了过期内容 | 版本治理缺失 | 下线旧版、统一命名、建变更清单 |

通用标识符切分的参数直觉（ADP 平台值，机制通用）：切片最大长度 4800 字符上限、**重叠 10%（最高 25%）**、父子级切分子片 ≤1500 字符。重叠太小→边界问题割裂；太大→噪声占比上升。**所有参数围绕固定测试样本调，不围绕单条问题反复试**（ADP 4.3 原话）——这正是 §1 单变量纪律在检索层的表达。

### 3.3 检索参数、embedding 与 reranker 选型、混合检索

调参判断树（ADP 4.3 + [rag-handbook §3.3](../rag-handbook/RAG搭建文档.md) 生产三步）：

| 观察到的现象 | 优先动作 |
|---|---|
| 正确片段完全没出现 | 查检索范围/权限过滤/召回设置，而不是先调 embedding |
| 正确片段出现但排序靠后 | 上重排（rerank）：开源 bge-reranker 系列、商业 Cohere/Voyage rerank；reranker 只重排前 K，成本远低于全量嵌入 |
| 召回很多但弱相关 | 收紧匹配度阈值；混合检索（hybrid retrieval）：向量 + BM25 + RRF（Reciprocal Rank Fusion，倒数排名融合）融合，关键词类问题（型号/编号/专名）靠 BM25 救回 |
| 权限串库 / 部门内容泄漏 | 文档级 ACL 过滤（[rag-handbook §6.5](../rag-handbook/RAG搭建文档.md)），这是生死线不是调参项 |

embedding 选型的调优视角：换 embedding 模型 = 全库重建索引 + **必须过回归集**（新旧 embedding 空间不可比，[rag-handbook §6.3](../rag-handbook/RAG搭建文档.md) 已把 embedding 升级列为回归测试场景）；排行榜分数只决定候选，**自己的测试集决定上线**。

### 3.4 查询改写：HyDE、multi-query 与问答对

| 手段 | 机制 | 适用 | 代价 |
|---|---|---|---|
| **改写进检索前**（多轮结合上下文改写） | 把"那个也按上周的方式"改写成自含查询 | 多轮对话、指代消解 | 一次小模型调用 |
| **HyDE**（Hypothetical Document Embeddings，假设文档嵌入） | 让模型先写一个"假想答案"，用假想答案的向量去检索 | 问法与文档措辞差距大 | 多一次生成调用；假想内容可能引入偏置 |
| **multi-query**（多路查询） | 一次生成 N 个改写查询，分别检索后融合 | 口语化/多角度问法 | 调用与 token 成本 ×N |
| **问答对沉淀** | 高频口语问法直接映射到固定答案 | 高频/风险口径问题，命中率最稳的"检索"是不检索 | 人工校验与冲突合并（ADP 4.3：从文档生成的问答必须人工校验后采纳） |

与 agent 式检索的关系：[rag-handbook §1.4](../rag-handbook/RAG搭建文档.md) 划分了"索引式 RAG"与"agent 迭代式检索（grep 循环）"两条路线——查询改写属于索引式管线的前置优化；agent 路线的调优杠杆则换成"检索工具的返回密度与迭代次数上限"（见 §4.2 节点粒度）。

### 3.5 分诊表（速查）

| 现象 | 优先怀疑 | 第一动作 | 第二动作 |
|---|---|---|---|
| 答案完整但引用缺失/错误 | 生成约束或元数据映射 | 要求答案基于引用生成；核对引用字段与文档元数据 | 标准问题集回归验证引用准确率（ADP 4.3） |
| 工具返回结构不具名被误读 | F3 工具误用 | 返回具名 JSON（ADP 4.5：`[30,1]` → `{"precision":30,"recall":1}`） | 在工具描述中说明返回字段语义 |
| 换了问法就答不出 | F1b 召回脆弱 | 问答对沉淀 + multi-query | 固定集上测"问法扰动鲁棒性" |

> 本章来源：ADP 课程 [4.3](../fde-handbook/tencent-adp-fde-course/lessons/4.3_知识库质量与_RAG_调优.md) ｜ [rag-handbook §1.4/§2.2/§3.3/§6](../rag-handbook/RAG搭建文档.md) ｜ HyDE https://arxiv.org/abs/2212.10496 ｜ [LangChain MultiQueryRetriever](https://python.langchain.com/docs/how_to/MultiQueryRetriever/) ｜ [eval-handbook §8.1](../eval-handbook/Agent评测与质量工程手册.md)

---

## 4. 工作流与编排调优

> 配套阅读：[workflow-handbook/Agent工作流编排手册.md](../workflow-handbook/Agent工作流编排手册.md)（2026-09-28 完成，与本册同日成稿）——工作流**怎么建**（模式谱系、节点契约、引擎横评）在那边，本章讲**怎么调**（粒度、并行、路由降级、重试超时、HITL 插点）；ADP 4.4 的 Badcase 方法论两边共用，[08-langgraph/源码解析与学习路线.md](../08-langgraph/源码解析与学习路线.md) 的 StateGraph/checkpoint/interrupt 语义是两边共同的引擎级锚点。

### 4.1 场景边界与节点选型：调优从"说清楚"开始

ADP 4.4 的顺序是：**边界 → 选型 → 连线变量 → 调试**。"做一个售后助手"调不了优；"用户提出退货/换货/投诉时，收集订单号与商品信息，查询订单系统和售后政策，生成工单或引导转人工"才调得动——因为这时你才知道哪些节点、哪些字段、哪些异常路径需要存在。边界不清的两个下游症状：流程越搭越长、节点职责越来越乱。

节点选型的经典 badcase（ADP 4.4 原案例）：酒店送物场景用**标签提取节点**收集"物品+数量"，用户没说全时节点不追问，插件入参缺失报错；换成**参数提取节点**+缺失追问即修复。判据一句话：**字段缺失会影响后续执行的，用参数提取+追问；给已有文本分类打标的，才用标签提取**。工具名/描述/入参出参是模型选工具的唯一依据（tool_01 这种名字神仙难救，ADP 4.5）。

### 4.2 节点粒度：单一职责 + 输出可断言

粒度是工作流调优里最主观的决策，给两条可操作的判据：

1. **一个节点一件事**：ADP 4.2 的问题分解——"处理客户投诉"拆成识别投诉→提取诉求→判断风险→查规则→生成回复，每步输出可独立检查；坏处是变量穿管复杂度上升。经验区间：一个节点能被单独断言（给输入看输出对不对）就该是独立节点；两个节点永远一起被检查就合并。
2. **确定性逻辑必须出节点**：时间戳、编号、金额计算、格式校验放进工具/代码节点，不要让模型自由生成（ADP 4.5 的案例：让 agent 生成"当前时间戳格式的项目名称"，它会生成看似正确但不是当前时间的字符串）。这与 [eval-handbook §2.3](../eval-handbook/Agent评测与质量工程手册.md) 的"代码判据优先"同构——**能确定性的都确定性，模型只做该模型做的事**。

### 4.3 并行化：无依赖即并行，有副作用即串行

- **无依赖节点并行**：多路检索、多文档摘要、多候选生成天然可并行；08-langgraph 的 fan-out（`StateGraph` 多路 reducer 合并）是引擎级实现，[08-langgraph/源码解析与学习路线.md](../08-langgraph/源码解析与学习路线.md)。六家 agent 的先例：Claude Code 只读工具并发执行（`MAX_TOOL_USE_CONCURRENCY`，[01-claude-code/架构拆解.md §7](../01-claude-code/架构拆解.md)）——**读操作并行、写操作串行**是保守而正确的默认。
- **有副作用节点串行 + 幂等**：写库、建单、发消息类节点并行会放大重复副作用；重试必须带幂等键（ADP 4.4 运维 Tips：重试要设置次数、间隔和幂等约束，避免重复建单）。
- **并行度不是越高越好**：上游限流（RPM/TPM）与环境容量是真实上限，评测 run 的并行度=评测时长×限流×环境租金的三角（[eval-handbook §8.3](../eval-handbook/Agent评测与质量工程手册.md)）——生产链路同理。

### 4.4 路由与降级：意图层最值得投资的地方

- **意图识别错误的两个修法**（ADP 4.4）：轻则意图示例（给一对易混 query 的强制标注："入住时间"≠"完成入住的耗时"）；重则**把语种/意图判断从提示词约定改成显式变量**——前置一个大模型节点输出语言变量，后续节点引用变量而不是各自猜。变量是可断言的，提示词约定不可断言。
- **降级（fallback/degradation）链**：检索失败→通用回答；工具超时→缓存/默认值；模型超时→小模型；全部失败→转人工。每级降级都要有自己的判据与日志，"悄悄降级"是最难排查的静默失败。
- **条件明确就别用模型路由**：转交条件明确时用显式工作流分支（确定性代码），模型只处理开放路由（ADP 4.5 的结论放在工作流上同样成立）。

### 4.5 重试与超时预算

| 机制 | 配置要点 | 反模式 |
|---|---|---|
| 重试 | 次数上限 + 指数退避 + **幂等键**；只对可重试错误（超时/限流/5xx）重试 | 对 4xx 业务错误重试；无上限重试放大副作用 |
| per-task 超时 | 每个任务独立 deadline，超时判失败并归因，卡死任务不许拖垮整轮 | 全局唯一超时，一条卡死全链挂起（[eval-handbook §8.3](../eval-handbook/Agent评测与质量工程手册.md)） |
| 预算熔断 | 整轮 token/费用上限，触顶即停出部分报告；ZCode 的 rapid-refill 断路器是同思想的结构化实现（连续失败 3 次熔断，[04-zcode/架构拆解.md §8.2](../04-zcode/架构拆解.md)） | 无预算上限的长循环（"账单爆炸"事故的直接来源，[fde-handbook §3.1](../fde-handbook/FDE转行手册.md)） |
| 接口变更 | 地址/鉴权/字段/错误码变更后更新工具配置，分分支验证（正常/超时/异常）再回归关键链路（ADP 4.4） | 只验正常分支 |

### 4.6 HITL 插点位置：插在"低置信度出口"，不是到处插

人在环（HITL, human-in-the-loop）不是越多越稳——每个插点都是队列与成本。三条插点判据：

1. **置信度出口**：模型输出的置信度低于阈值、或判据输出 `needs_human`（[eval-handbook §5.3](../eval-handbook/Agent评测与质量工程手册.md) 的不确定出口）→ 进人工。这是第一优先插点。
2. **高风险动作前**：退款审批、账户修改、对外承诺（ADP 4.2 的边界清单）；六家 agent 的权限审批流是同思想的结构化实现（如 Codex 的 AskForApproval × SandboxPolicy 双轴，[02-codex/架构拆解.md §5](../02-codex/架构拆解.md)）。
3. **不可逆操作前**：写入/删除/发送类副作用，且幂等键救不回来的动作。引擎级机制是 LangGraph 的 `interrupt`（挂起等待人工输入后恢复，[08-langgraph/源码解析与学习路线.md](../08-langgraph/源码解析与学习路线.md)）。

**反模式**：把"不确定就说转人工"当装饰性提示词（模型从不触发）；把 HITL 插在每一步（人工队列堆积，自动化的意义归零）；高风险动作后置审核（审核通过时损失已发生）。

> 本章来源：ADP 课程 [4.4](../fde-handbook/tencent-adp-fde-course/lessons/4.4_Workflow_调优.md)/[4.5](../fde-handbook/tencent-adp-fde-course/lessons/4.5_Multi-Agent_调优.md) ｜ [08-langgraph](../08-langgraph/源码解析与学习路线.md) ｜ [eval-handbook §8.3](../eval-handbook/Agent评测与质量工程手册.md) ｜ 六家《架构拆解》§5/§7

---

## 5. Multi-Agent 调优

范式选择与失败治理见 [multiagent-handbook](../multiagent-handbook/Multi-Agent协同手册.md)（何时需要/六范式/MAST）；本章只讲"已经决定用多 agent 后，把协同调稳"的四个杠杆。

### 5.1 角色划分的收益边界

multiagent-handbook §1 的数字先立在这：Anthropic 实测多 pass 配置把 90.2% 任务做完，但 token 翻 15×——**角色划分买的是质量与隔离，付的是 token 与延迟**。调优判据：

- **每个 agent 必须能独立通过评测**：子 agent 的 prompt/工具/输出约束按 §2-§4 的方法各自调，"团队级调优"不能替代单 agent 调优。
- **转交描述（handoff description）≠ 提示词（prompt）**：转交描述是给**其他 agent** 看"什么时候把活给我"，提示词是给自己看"怎么干活"——转交失败先看前者，执行不稳先看后者（ADP 4.5 的显式区分，六家 agent 子代理机制的对照见 [multiagent-handbook §3.2](../multiagent-handbook/Multi-Agent协同手册.md)）。
- **职责重叠是重复劳动之源**：检索、分析和复核三个 agent 重复检索、直接下结论、遗漏复核（ADP 4.5 案例）——修法是把"谁负责什么、不负责什么、什么时候交出去"写进各自边界，并用轨迹评测断言"无重复工具调用"（[eval-handbook §6.1](../eval-handbook/Agent评测与质量工程手册.md)）。

### 5.2 通信协议瘦身：传结论，不传过程

多 agent 系统的通信开销不只是 token，还有注意力污染（接收方被无关过程淹没）。三条瘦身纪律：

1. **交接协议四条可直接抄**（[multiagent-handbook §3.3](../multiagent-handbook/Multi-Agent协同手册.md)）：交接消息写清目标/已知/已做/未决，禁止倾倒原始过程。
2. **"回传结论不回传过程"**：子代理只把最终结果带回父代理，隔离中间检索与试错（[context-handbook §3.3](../context-handbook/Context与记忆系统手册.md) 的 handoff 摘要协议）——这同时是上下文经济与通信瘦身的交集。
3. **消息里的结构化字段优先于自然语言叙述**：工具与 agent 间返回一律具名 JSON（`{"precision": 30, "recall": 1}` 而不是 `[30, 1]`，ADP 4.5 原例）；字段语义在 schema 里，不在猜测里。

### 5.3 共享状态 vs 消息传递：黑板的诱惑与代价

| 维度 | 共享状态（blackboard，黑板） | 消息传递（handoff，交接） |
|---|---|---|
| 真源 | 一个共享 state/数据库 | 消息即真源，随对话流动 |
| 优点 | 任意 agent 可读全局，免重复广播 | 隔离好，权限与注意力边界清晰 |
| 代价 | reducer 冲突合并、并发写、所有人背全局噪声 | 上下文在交接中丢失，需要摘要协议 |
| 框架参照 | LangGraph 共享 state + reducer + checkpoint（[08-langgraph](../08-langgraph/源码解析与学习路线.md)） | OpenAI Agents SDK handoff、Claude Code Task |
| 调优抓手 | **state schema 瘦身**（共享 state 里的每字段都要问"谁读它"；写并发用 reducer 指定合并语义） | **交接摘要质量**（§5.2 协议）+ 转交描述校准 |

判据：**需要在多轮间反复读写同一批事实 → 黑板；一次性任务移交 → 消息**。混合形态（共享事实表 + 消息通知）是生产最常见的落点——通知只是通知，状态才是真源（[multiagent-handbook §2.5](../multiagent-handbook/Multi-Agent协同手册.md)）。

### 5.4 何时合并回单 agent：撤退的判据

调优多 agent 的终点经常是**减 agent**。四个撤退信号（对照 multiagent-handbook §1.3 伪需求清单）：

1. 转交不稳定且条件说不清——自由转交依赖模型判断，条件明确的工作流编排更稳，**条件不明确的多 agent 结构更不稳**（ADP 4.5：缺陷识别没转给质检 Agent，被巡检 Agent 硬答）；
2. 子 agent 间无真并行（串行交接链只是把一个长 prompt 拆成 N 次模型调用，还各付一份固定开销）；
3. 通信协议越调越臃肿——当"交接消息"的长度逼近"把任务直接做完"的长度，隔离已经没有经济性；
4. 全靠双重约束才能兜底——ADP 4.5 的"提示词 + 工具返回"双约束是好技术，但如果每个失败类都需要它，说明职责切分本身在制造失败。

合并的正确姿势：把 N 个 agent 的 prompt 收敛为一个分层 system prompt（§2.1 八区块），工具全量下发靠描述区分（或按需裁剪），用 §1 闭环重新过一遍回归门禁——**减法也要过门禁**。

> 本章来源：ADP 课程 [4.5](../fde-handbook/tencent-adp-fde-course/lessons/4.5_Multi-Agent_调优.md) ｜ [multiagent-handbook §1/§2.5/§3/§6](../multiagent-handbook/Multi-Agent协同手册.md) ｜ [context-handbook §3.3](../context-handbook/Context与记忆系统手册.md) ｜ Anthropic 多 pass 实测转引自 multiagent-handbook §1.2

---

## 6. 模型与参数调优（当日实抓对比）

### 6.1 temperature / top_p / seed

| 参数 | 机制 | 经验起点 | 适用 |
|---|---|---|---|
| **temperature** | 压平/锐化采样分布 | **0**：判定、抽取、结构化输出、judge；**0.3-0.7**：客服话术、创作、brainstorm | 先按任务类型定档，再在固定集上微调（§1 闭环） |
| **top_p**（核采样） | 截断累计概率 p 的尾部 | 与 temperature **不同时大改**——两者都压随机性，同时调=两个变量（§1 纪律） | 默认值起步，除非有明确抖动证据 |
| **seed**（随机种子） | 请求级确定性采样（OpenAI 侧为 best-effort，服务端负载可能打破） | 想要可复现的 A/B：固定 seed + 温度 0；跨请求仍可能微差，判据别依赖单次输出 | 实验对比、回归定位 |

六家里的生产实证：OpenCode 把 `temperature/topP` 做进了 **agent 定义**而非全局配置——`Agent.Info` schema 有独立的 `model/temperature/topP/steps` 字段，内建 build/plan/general/explore 等 7 个 agent 各自配参（`agent/agent.ts:35-56`，[06-opencode/架构拆解.md §8.1](../06-opencode/架构拆解.md)）。这就是"参数跟角色走"的落地形态：抽取型子 agent 用温度 0，总结型 agent 稍放开——**参数是 agent 配置的一部分，不是全局魔法数**。

### 6.2 推理模型 vs 快思考模型的分工

当日实抓的现役阵容把"分工"做成了显式档位（价格全表见 §6.6）：

| 档位 | 代表（2026-09-28 实抓） | 适合 | 不适合 |
|---|---|---|---|
| 推理/旗舰 | Anthropic Opus 5.5 / Fable 5.1、OpenAI gpt-5.2(-pro)、Google gemini-3.1-pro-preview、DeepSeek v4-pro（thinking） | 规划、策略判断、复杂推理、判卷（judge）、难题兜底 | 分类/抽取/改写（算力浪费） |
| 快思考/均衡 | Anthropic Sonnet 5、OpenAI gpt-5.1/5、gemini-3.8-flash、deepseek-flash | 主力生成、常规 agent 主循环 | 无 |
| 轻量 | Anthropic Haiku 4.5、OpenAI gpt-5-mini/nano、gemini-3.5-flash-lite / 2.5-flash-lite | 意图分类、字段抽取、查询改写、标题、embedding 后处理 | 多步规划（错误率放大） |

DeepSeek 两档均提供 thinking / non-thinking 双模式（§6.6 实抓）——**推理预算已是模型侧参数**，与 §2.3 呼应：提示词层触发词的调优空间被模型档位吃掉了大半。

### 6.3 结构化输出模式

F4（格式不合规）的根治手段按优先级：

1. **API 级结构化输出（structured output）**：JSON Schema 约束解码（各家 API 均支持）——约束在解码层，比提示词约束可靠一个量级；SDK 用法见 [python-handbook §3](../python-handbook/Python大模型应用开发手册.md)。
2. **schema 校验 + 定向重试**：校验失败把错误信息回喂重试（一次为限）；重试两次仍失败进人工/兜底分支。
3. **固定字段模板 + 禁解释**（ADP 4.2 的"仅输出 JSON，字段如下"写法）：没有 schema 支持时的下策，但配合 few-shot 与缺失值规则（"无法判断时 intent 输出其他，need_human 输出 true"）也能到生产水位。
4. **确定性逻辑出提示词**（§4.2）：时间戳、编号、计算类内容永远不要让模型"生成"，让工具返回。

### 6.4 上下文窗口与截断策略

窗口大小与价格的当日实抓事实：Gemini 3.8-flash 与 DeepSeek 两档均为 **1M 窗口**；Gemini 3.1-pro 分层计价（≤200k 输入 $2/M，**>200k 输入 $4/M**，输出同理 $12→$18）——**长上下文不是免费的，是翻倍的**（§6.6）。

截断/压缩策略的完整方法论在 [context-handbook §2](../context-handbook/Context与记忆系统手册.md)（三层预算、剪枝先于摘要、"日志为真源，压缩只改投影"不变量），调优视角只提三个数字化的抓手：

1. **token 估算要有误差意识**：OpenCode 的压缩预算用"字符数/4"估算（`packages/core/src/util/token.ts:4`，实测核对），对中文显著低估；provider 没回报 usage 时按 0 处理（`session/session.ts:341-345`）→ 成本被低估（[06-opencode/架构拆解.md §7.4](../06-opencode/架构拆解.md)）。**CJK 场景必须用 tokenizer 实算**，字符/4 只配做粗预算。
2. **压缩触发点要留缓冲**：ZCode 的 auto compact 预留输出 `min(maxOutput, 21_000)` + buffer 13_000、microcompact 阈值 0.9（[04-zcode/架构拆解.md §8.2](../04-zcode/架构拆解.md)）——触发线贴着窗口上限 = 一次超窗错误就 reactive 补救（更贵且更慢）。
3. **截断必须保缓存前缀**：从后往前剪（保护最近消息），不破坏最前面的稳定前缀——§2.4 与 [context-handbook §2.6](../context-handbook/Context与记忆系统手册.md) 缓存锚点的交集。

### 6.5 模型路由与级联降级

- **路由（routing）**：按任务难度/类型选档位（§6.2 的分工表就是路由表）。开源框架可看 RouteLLM（§8 表：5,549 star，**2024-08 后未再推送——选型先做维护状态扫描**，与 multiagent-handbook 的"归档扫描"纪律一致）。
- **级联（cascade）/降级**：先小后大——小模型置信度不足或失败再升级旗舰；或先旗舰拿结果、降级副本做旁路校验。每级之间要有明确的升级判据（不是"感觉不行"）。
- **路由器自己也要过评测集**（[eval-handbook §8.2](../eval-handbook/Agent评测与质量工程手册.md) 的两条纪律）：路由错了等于把错误率做进架构；每档模型的 pass 率与成本**并排监控**（BFCL 排行榜把 cost/latency 与分数并排展示的做法值得抄）。
- **模型目录外置**：OpenCode 把模型清单（含 `cost/limit/status(deprecated)` 字段）外置到 models.dev 并 TTL 缓存（[06-opencode/架构拆解.md §9](../06-opencode/架构拆解.md)，`models-dev.ts:160`）——**模型信息当配置管，不当代码管**，换模型从"发版"变"改配置"。

### 6.6 四家模型价格速查（2026-09-28 实抓）

**Anthropic**（[claude.com/pricing](https://claude.com/pricing)，美元/百万 token）：

| 模型（现行） | 输入 | 输出 | 缓存写(5m) | 缓存读 |
|---|---|---|---|---|
| Fable 5.1 | $10 | $50 | $12.50 | $0.25 |
| Opus 5.5 | $4 | $20 | $5 | $0.20 |
| Sonnet 5 | $2 | $10 | $2.50 | $0.20 |
| Haiku 4.5 | $1 | $5 | $1.25 | $0.10 |

批次处理省 50%；美国区推理 1.1×；Opus 5.5 Fast 模式 2× 价格换至多 2.5× 提速。遗留档（Opus 5 / 4.8 / 4.6：$5/$25；Sonnet 4.6 / 4.5：$3/$15）仍在页上，读价比例随模型不同（Sonnet/Haiku 缓存读为输入 10%，Opus 5.5 为 5%）。

**OpenAI**（[platform.openai.com/docs/pricing](https://platform.openai.com/docs/pricing)）：

| 模型 | 输入 | 缓存输入 | 输出 |
|---|---|---|---|
| gpt-5.2 | $1.75 | $0.175（10%） | $14.00 |
| gpt-5.2-pro | $21 | — | $168 |
| gpt-5.1 | $1.25 | $0.125（10%） | $10.00 |
| gpt-5 | $1.25 | $0.125（10%） | $10.00 |
| gpt-5-mini | $0.25 | $0.025（10%） | $2.00 |
| gpt-5-nano | $0.05 | $0.005（10%） | $0.40 |
| gpt-4.1 | $2.00 | $0.50（25%） | $8.00 |

推理 token 计入输出计费；另有 Batch（批量省）、Priority（提速加价）、Flex（低价高延迟）三层服务档。

**Google Gemini**（[ai.google.dev/gemini-api/docs/pricing](https://ai.google.dev/gemini-api/docs/pricing)，页面标注 2026-09-24 更新）：

| 模型 | 输入 | 输出 | 备注 |
|---|---|---|---|
| gemini-3.8-flash | $0.75 | $3.75 | 1M 窗口；此价至 2026-12-31，2027-01-01 起 $1.50/$7.50；上下文缓存 $0.075/M |
| gemini-3.1-pro-preview | $2（≤200k）/ $4（>200k） | $12 / $18 | 缓存 $0.20/M + 缓存存储 $4.50/M/小时 |
| gemini-3.5-flash-lite | $0.30 | $2.50 | — |
| gemini-2.5-pro / 2.5-flash / 2.5-flash-lite | $1.25 / $0.30 / $0.10 | $10 / $2.50 / $0.40 | 上一代仍列价 |

批处理 API 一律 -50%；另有 flex/priority 服务档。

**DeepSeek**（[api-docs.deepseek.com/quick_start/pricing](https://api-docs.deepseek.com/quick_start/pricing)）：

| 模型 | 输入（缓存命中） | 输入（未命中） | 输出（峰值） | 备注 |
|---|---|---|---|---|
| deepseek-flash | $0.006 | $0.30 | $1.20 | legacy 名 deepseek-chat 已退役（按 Flash 价服务） |
| deepseek-v4-pro | $0.044 | $1.32 | $3.96 | 并发上限 500（flash 为 2500） |

错峰（非工作日+非工作时段，UTC 01:00-04:00、06:00-10:00 之外）**一律半价**；1M 上下文、384K 最大输出；缓存命中价为未命中的 2-3.3%——四家里最激进的缓存定价。

> 本章来源：四个官方定价页当日实抓（链接在表上方）｜ [06-opencode/架构拆解.md §7.4/§8.1/§9](../06-opencode/架构拆解.md) ｜ [04-zcode/架构拆解.md §8](../04-zcode/架构拆解.md) ｜ [context-handbook §2](../context-handbook/Context与记忆系统手册.md) ｜ [eval-handbook §8.2](../eval-handbook/Agent评测与质量工程手册.md)

---

## 7. 成本与延迟工程（当日实抓价格表）

[eval-handbook §8](../eval-handbook/Agent评测与质量工程手册.md) 已给出核算骨架（成本归因到 trace、路由器过评测、评测 run 预算熔断）；本章补齐**平台侧价格机制**与**延迟预算分解**两个工程面。

### 7.1 token 成本核算：四档单价 × 用量

```
成本 = Σ_calls [ plain_in × 价_in + cached_in × 价_cached + out × 价_out + (缓存写部分 × 价_write) ]
```

| 档位 | 相对量级（当日实抓证据） |
|---|---|
| 普通输入 | 1×（基准） |
| 缓存读 | Anthropic 0.1×（Opus 5.5 为 0.05×）；OpenAI gpt-5.x 0.1×（4.1 系 0.25×）；**DeepSeek 0.02-0.033×**；Gemini 0.1× + 存储费 |
| 缓存写 | Anthropic 1.25×（5m）/ 2×（1h）；OpenAI/Gemini 免写费（Gemini 收存储费 $0.25-4.50/M/小时） |
| 输出 | 输入的 4-10×（Sonnet 5：$10/$2 = 5×；gpt-5.2：$14/$1.75 = 8×；Haiku 4.5：$5/$1 = 5×） |

三条推论：**输出 token 比输入贵**——让模型少生成废话（约束输出长度、结构化输出）与"用大模型读小模型写"是两条主要省钱方向；**缓存命中价与未命中价差一个数量级**——命中率是最值得盯的成本指标；**批处理/错峰统一 -50%**——离线评测与夜间回流没有理由不用。

### 7.2 缓存命中率：第一杠杆

agent 场景下输入 token 是复利结构（历史越滚越大，每轮全量重发），命中率对账单的影响是非线性的。工程清单：

- 稳定前缀工程（§2.4）：工具定义 → 系统提示词 → few-shot 稳定区 →（动态内容止步于此）。
- **Anthropic 显式断点**最多 4 个、放稳定段末尾；1 小时 TTL 适合低频长会话（写费翻倍换跨轮存活）。
- **OpenAI `prompt_cache_key`** 按租户/会话分组路由，注意同前缀 ~15 req/min 的溢出阈值——高并发场景把"同前缀流量"打散到多个 key 反而可能提高总命中率（每个 key 独立缓存域）。
- 命中率进 trace 与报表（`cached_tokens` / `cache_read_input_tokens`），命中率异常下跌 = 前缀漂移告警。
- 语义缓存（semantic cache）作为第二层：省 60-85% 的报道成立但带正确性风险（[eval-handbook §8.1](../eval-handbook/Agent评测与质量工程手册.md)）。

### 7.3 批处理 API（batch）与错峰

| 平台 | 折扣 | 时效 | 适用 |
|---|---|---|---|
| Anthropic Message Batches | -50% | ≤24 小时 | 夜间评测跑批、数据集批量打标、回归集复跑 |
| OpenAI Batch API | -50% | 24 小时窗口 | 同上 |
| Gemini Batch API | -50% | 24 小时内 | 同上 |
| DeepSeek 错峰价 | -50% | 即时（按时段） | 无需排队语义，直接错峰调用 |

适用判据：**离线且延迟不敏感**的负载（评测、评测、还是评测；以及离线数据蒸馏）。在线交互链路不适用。评测本身烧钱的问题（全量 judge 账单超过 agent 本身）见 [eval-handbook §5.5](../eval-handbook/Agent评测与质量工程手册.md) 的金字塔仲裁结构。

### 7.4 投机执行（speculative execution）

agent 链路里"下一步要什么"往往可预测——预测到了就提前准备：

- **预取（prefetch）**：参数提取节点一有部分结果，先并行发起检索/工具调用的候选请求，路由确定后取消多余分支（cancel-on-decide）。I/O 等待型工具（检索、查询）收益最大；有副作用的调用**禁止投机**（§4.3 幂等约束）。
- **投机解码（speculative decoding）**：模型服务层技术（小模型起草 + 大模型验证），API 用户通常感知不到，自建推理服务（vLLM 类）时可开——不改变结果分布，纯延迟优化。
- **交互层的"伪投机"**：流式输出先渲染首段、工具结果分块流回——感知延迟的下降不依赖真实延迟下降（§7.5 的 TTFT 治理）。

### 7.5 延迟预算分解：TTFT / 生成速率 / 工具往返

把"慢"拆成三笔账，才能定位到可优化的那一笔：

| 分量 | 定义 | 典型杠杆 |
|---|---|---|
| **TTFT**（time to first token，首字延迟） | 发请求到第一个 token 出现 | 缓存命中（OpenAI 实测最高 -80%）、前缀缩短、小模型、流式开启 |
| **生成速率**（decode throughput） | 首 token 后每秒吐多少 token | 输出长度约束（结构化输出天然短）、小模型、Fast 档（Anthropic Opus 5.5：2× 价格换至多 2.5×，当日实抓） |
| **工具往返**（tool round-trip） | 模型停→工具执行→结果回→模型续 的墙钟 | 并行化无依赖工具、预取（§7.4）、工具自身超时与缓存、减少轮次（§4.2 粒度） |

示例分解（方法演示，数字为示意）：目标交互 P95 ≤ 8s = TTFT 0.8s（缓存后）+ 生成 250 token ÷ 80 tok/s ≈ 3.1s + 2 次工具往返 2×1.5s = 3.0s + 编排开销 0.3s + 余量 0.8s。**先测各分量再选杠杆**：TTFT 主导就治缓存与前缀，工具往返主导就治并行与预取——平均错方是最常见的浪费。

### 7.6 成本-质量-延迟三角：取舍表

| 策略 | 成本 | 质量 | 延迟 | 风险与适用 |
|---|---|---|---|---|
| 提示缓存 | ↓↓（读 0.1×） | 不变 | ↓↓（TTFT） | 前缀漂移即失效；几乎无条件该做 |
| 批处理/错峰 | ↓↓（-50%） | 不变 | ↑↑（≤24h） | 只用于离线负载 |
| 模型路由/级联 | ↓↓（7-35× 价差） | 需监控（路由错=错误进架构） | ↓ | 路由器要过评测集（§6.5） |
| 上下文压缩/剪枝 | ↓（输入 token） | **有损**（摘要有偏） | ↓ | 必须配回归集；剪枝先于摘要（context-handbook §2.2） |
| 工具并行/预取 | ≈ | 不变 | ↓↓ | 仅无依赖/无副作用；有副作用必须串行+幂等 |
| 结构化输出 | ↓（输出更短） | ↑（F4 根治） | ↓ | schema 设计成本；解码约束偶尔影响灵活性 |
| Fast 档/优先服务 | ↑（2×） | 不变 | ↓↓ | 交互链路的兜底手段 |
| 减 agent / 减轮次 | ↓ | ↑（少交接损耗） | ↓ | §5.4 撤退判据；减法也要过门禁 |

**三角的正确用法不是"同时优化三个"，是显式选择放弃哪个**：客服场景通常弃成本保延迟与质量；数据管线弃延迟保成本与质量；评测跑批弃延迟保成本，质量由判据保证。取舍写进设计文档，而不是留在事后解释里。

> 本章来源：四个官方定价页与缓存文档当日实抓（URL 同 §6.6 及 §2.4）｜ [eval-handbook §5.5/§8](../eval-handbook/Agent评测与质量工程手册.md) ｜ [06-opencode/架构拆解.md §7.4](../06-opencode/架构拆解.md)

---

## 8. 企业范例：GitHub 实抓横评与精读

### 8.1 横向对比总表（2026-09-28 GitHub API 实抓）

| 仓库 | star | 语言 | 版本（当日实抓） | 定位 | 对应本手册 |
|---|---|---|---|---|---|
| [stanfordnlp/dspy](https://github.com/stanfordnlp/dspy) | 38,374 | Python | dspy 3.4.0（PyPI） | "调优=编译"：提示词当参数自动搜索 | §2 |
| [langfuse/langfuse](https://github.com/langfuse/langfuse) | 35,104 | TypeScript | — | trace→dataset→experiment 闭环（评测侧精读见 [eval-handbook §9.3](../eval-handbook/Agent评测与质量工程手册.md)） | §1 |
| [promptfoo/promptfoo](https://github.com/promptfoo/promptfoo) | 25,498 | TypeScript | v0.123.1（npm，2026-09-18 发布） | 配置驱动 A/B + 断言门禁 + 红队 | §2/§9 |
| [comet-ml/opik](https://github.com/comet-ml/opik) | 22,259 | Python | v2.2.81（2026-09-25 发布） | LLM 可观测+评测平台 | §1 |
| [Confident-AI/deepeval](https://github.com/Confident-AI/deepeval) | 18,465 | Python | 4.2.6（PyPI） | 断言式评测框架，CI 门禁见长 | §9 |
| [Arize-ai/phoenix](https://github.com/Arize-ai/phoenix) | 11,634 | Python | — | OTel-first 可观测+evals | §1 |
| [Azure-Samples/azure-search-openai-demo](https://github.com/Azure-Samples/azure-search-openai-demo) | 7,773 | Python | — | 微软官方 RAG 参考实现（参数化+内置评测） | §3 |
| [lm-sys/RouteLLM](https://github.com/lm-sys/RouteLLM) | 5,549 | Python | —（**最后推送 2024-08-10，低维护**） | LLM 路由框架 | §6.5 |
| [openai/openai-cookbook](https://github.com/openai/openai-cookbook) | 76,228 | Jupyter | — | 官方调优技法示例库（缓存/批处理/评测 notebook） | §2/§7 |

评测平台类（langfuse/phoenix/opik/deepeval）的方法论精读在 [eval-handbook §9](../eval-handbook/Agent评测与质量工程手册.md) 已做，本节不重复；下面精读三家**调优工程化实践**取向各异的：人工配置流（promptfoo）、自动化搜索流（DSPy）、官方参数化模板（azure-search-openai-demo）。

### 8.2 精读一：promptfoo —— 把 §9 的门禁做成产品

- **配置即实验**：`promptfooconfig.yaml` 里 `prompts` 写成数组就是 A/B 矩阵、`providers` 数组就是多模型矩阵——笛卡尔积一次跑完。这把 §1 的"单变量变更"变成了**声明式变量表**：每行结果天然带完整变量上下文，不存在"改了什么来着"的考古。
- **断言即判据**：每条测试可挂 `equals/contains/javascript/llm-rubric` 等断言类型——判据谱系（代码>规则>judge）与 [eval-handbook §2.3](../eval-handbook/Agent评测与质量工程手册.md) 同构，落到了配置字段级。
- **CI 即门禁**：`promptfoo eval` 退出码非零即失败，配 GitHub Action 可卡合并——§9 回归门禁的产品化形态。附带红队扫描（prompt injection/PII），与 [security-handbook §5](../security-handbook/AI应用安全手册.md) 的评测口径衔接。
- 值得抄的细节：**缓存与幂等**（同输入复用结果，改 diff 才重跑）；Web 查看器逐条人工标注回写——ADP 4.1"评测结果人工标注"的开源对照。
- 局限：矩阵模型下长任务 agent 场景的编排能力弱于专门框架（它强在"配置-断言-门禁"一线，不在轨迹编排）。

### 8.3 精读二：DSPy —— "调优=编译"的自动化路线

- **范式换位**：prompt 不是手写的文本而是**程序的参数**——声明 Signature（输入输出契约）→ 组合 Module → 定义 metric → 跑 optimizer（如 MIPROv2：指令+few-shot 的联合搜索），optimizer 在 trainset 上自动产出优化后的提示词。§2 的人工手法（few-shot 选择、措辞迭代）在这里是**搜索空间的一部分**。
- **与本文方法论的关系**：DSPy 不推翻 §1 闭环——metric 就是它的评测集判据，optimizer 的每轮搜索内部就在跑"变更→评测"。它改变的是③单变量变更的执行者：从人变成搜索算法。**代价是必须先有可判定的 metric 与有代表性的 trainset**——度量先行（§1 不变量）在这里不是纪律而是硬前提。
- 调优工程视角的三条经验：(1) trainset 30-50 条就能驱动 BootstrapFewShot，但分布要正（否则搜出过拟合话术）；(2) 优化产物要当**版本化资产**人审后入库，不能盲信搜索结果；(3) 换模型 = 重新编译（提示词是"编译产物"，绑定到具体被优化模型——这与 prompt-handbook 的"六家按模型维护提示词家族"现象互证）。
- 当日版本 dspy 3.4.0（PyPI）；38,374 star，Pushed 2026-09-27——活跃。与 [python-handbook §4](../python-handbook/Python大模型应用开发手册.md)（DSPy 是"评测先行"的代码化）互引。

### 8.4 精读三：azure-search-openai-demo —— 官方 RAG 调参样板

- **参数全部外置**：chunk 尺寸、topK、混合检索开关、语义重排（semantic rerank）、检索字段、prompt 模板……全部在配置层（`.env`/app settings），改参不改码——§3 所有调参项在这个仓库里都能找到对应配置键，相当于官方把 §3.2/§3.3 做成了清单。
- **评测内建**：仓库自带 eval 工具（问题集 + GPT 打分维度）跑问答质量，把"改参→跑集→对比"做成了一条命令——§1 闭环在官方模板层的示范。ADP 4.3 的调优流程（知识准备→导入→调试→评测→回归）可以在此找到每一步的开源对应。
- **企业落地的工程细节**：文档级权限（ACL 随检索下推）、引用渲染、上传管线、登录隔离——企业 RAG 的"非调优但必须有"的部分一个不少（[rag-handbook §6.5](../rag-handbook/RAG搭建文档.md) 权限生死线的一手实现）。
- 局限：绑定 Azure 全家桶（AI Search + OpenAI）；架构是模板级参考，生产仍需按自己的合规与成本约束改。

### 8.5 对照：六家 agent 源码里的调优内建机制

| agent | 内建调优机制 | 出处 |
|---|---|---|
| 01 Claude Code（anon-kode） | `/cost` 成本跟踪（`src/cost-tracker.ts`）；`/compact` 上下文回收；只读工具并发 | [架构拆解.md §6/§7](../01-claude-code/架构拆解.md) |
| 02 Codex | 审批×沙箱双轴=风险预算的结构化；多形态压缩 | [架构拆解.md §5/§6](../02-codex/架构拆解.md) |
| 03 DeepSeek Harness | 插件化把"参数"全部配置化；会话日志唯一真源（归因有据） | [架构拆解.md §5/§6](../03-deepseek-harness/架构拆解.md) |
| 04 ZCode | `cacheHint:"stable"` 显式缓存锚点；三层压缩阈值全可配；usage 三表（model/turn/tool）；连续失败 3 次熔断 | [架构拆解.md §8](../04-zcode/架构拆解.md) |
| 05 OpenClaw | 六条限流=成本熔断的网关级实现；预算制 workspace 注入 | [架构拆解.md §7/§8](../05-openclaw/架构拆解.md) |
| 06 OpenCode | usage 归一化（含各家 cache 变体键）+ context tier 定价 + Decimal 精算；Agent.Info 独立 temperature/topP；模型目录外置带 `status(deprecated)` 扫描 | [架构拆解.md §7.4/§8.1/§9](../06-opencode/架构拆解.md) |

读法建议：六家都是"**把调优从一次性动作做成常驻机制**"——成本表、缓存锚点、限流、熔断都是随主循环常驻的，而不是事后报表。这与本文 §1 把"评测进 CI、基线入库"设为固化形态是同一思想。

### 8.6 提炼：跨企业的 6 条设计模式

1. **配置即实验**（promptfoo 矩阵 / dspy signature / ADP 参数面板）——调优变量必须声明式可枚举；
2. **判据可执行**（断言字段级 / metric 函数 / 代码判据优先）——判据写不成代码的先别急着自动优化；
3. **产物版本化**（dspy 编译产物 / promptfoo 缓存指纹 / §9 基线指纹）——优化结果当资产管；
4. **门禁进流水线**（CI 退出码 / 评测卡合并 / ADP 回归）——"变好"由门禁裁决不由感觉裁决；
5. **成本延迟与质量并排展示**（BFCL 榜单 / OpenCode context tier 定价 / §7.6 三角表）——单看任何一个维度都是自欺；
6. **减法是一等公民**（§5.4 合并回单 agent / openclaw 六条限流的克制 / ZCode 熔断）——好的调优文化对"再加一层"保持警惕。

> 本章来源：各仓库 GitHub API 当日实抓（star/版本见 §8.1 表）｜ npm registry（promptfoo 0.123.1）｜ PyPI（dspy 3.4.0、deepeval 4.2.6）｜ promptfoo 文档 https://www.promptfoo.dev/docs/intro ｜ DSPy 文档 https://dspy.ai ｜ azure-search-openai-demo README https://github.com/Azure-Samples/azure-search-openai-demo

---

## 9. 从零实现一个最小调优实验框架 + FAQ + 上手清单

### 9.1 设计：三条不变量

完整代码在 [code/mini_tuning_lab.py](code/mini_tuning_lab.py)（Python 3 纯标准库，无网络依赖，**已本机验证**）。它实现 §1 闭环的最小可运行形态：

- **数据集切片（stratified split，分层切分）**：4 类场景（faq/extract/tool/boundary）各 3 条、共 12 条；固定 seed 分层抽样切成 dev（8 条，调参用）与 held-out（4 条，封存）。**不变量①：同一 seed 恒等复现；held-out 只在门禁阶段跑**——调参看 dev、验收看 held-out，两者混用等于门禁失效。
- **A/B 对比（paired comparison，配对比较）**：两个"版本"只差一处 prompt 约束（单变量），在同一样本集上逐条对照方向（变好/变差/双通过），而不是比较两次独立均值。**不变量②：配对比较抵消样本噪声**。
- **指标回归门禁（regression gate）**：三道闸——dev 非劣（不回退超过容差）→ 分场景不回退 → held-out 复跑非劣。**不变量③：基线带指纹（数据集+切分参数的 SHA-256 前 12 位）**，数据或参数变了指纹即变，旧基线显式判 INVALID 而不是悄悄混比。
- 判据全部可代码验证（必须包含/禁止出现/JSON 合法性），零 judge 调用——与 [eval-handbook §2.3](../eval-handbook/Agent评测与质量工程手册.md) 判据优先级一致；接真模型时把 stub 换成任意 OpenAI 兼容端点（SDK 用法 [python-handbook §3](../python-handbook/Python大模型应用开发手册.md)）。

### 9.2 代码（已本机验证）

```python
# -*- coding: utf-8 -*-
# mini_tuning_lab.py —— 最小调优实验框架：数据集切片 → A/B 对比 → 指标回归门禁。
# 对应《Agent 调优手册》§9；运行环境：Python 3，纯标准库，无网络依赖。
#   python mini_tuning_lab.py            # 演示完整闭环（首轮自动固化 v0 基线）
#   python mini_tuning_lab.py --gate     # 只跑回归门禁（v1 vs 已固化基线）
#   python mini_tuning_lab.py --promote  # 门禁通过后把 v1 固化为新基线
#
# 三条不变量（无论换什么模型/平台都必须保住）：
#   不变量①：同一 seed 的分层切分恒等复现；held-out（封存集）只在门禁阶段跑——
#            调参看 dev、验收看 held-out，两者混用 = 门禁失效。
#   不变量②：A/B 是"同一样本配对比较"，不是两次独立均值——配对才能把样本噪声抵消掉。
#   不变量③：基线记录带指纹（数据集+切分参数的哈希）；数据或参数变了指纹就变，
#            旧基线自动失效——"不可比"必须显式暴露，而不是悄悄混在一起比。

import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE_FILE = HERE / "baseline.json"

# ---------------------------------------------------------------------------
# 0. 评测集：12 条，4 类场景各 3 条。生产中它来自 ADP 课程 4.1 的"六项调试记录"
#    （问题/期望/实际/归因/动作/复测）与线上 badcase 回流——
#    评测集是调优的第一资产：先有度量，才有调优。
# 字段：expect=必须包含；forbidden=禁止出现；json_output=必须是合法 JSON。
# ---------------------------------------------------------------------------
DATASET = [
    # --- faq：知识问答（考察：依据资料回答，资料不足要说明） ---
    {"id": "faq-01", "scenario": "faq", "query": "门店的退换货政策是什么？",
     "expect": ["7 天"], "forbidden": ["30 天"], "json_output": False},
    {"id": "faq-02", "scenario": "faq", "query": "会员积分多久过期？",
     "expect": ["12 个月"], "forbidden": ["永久"], "json_output": False},
    {"id": "faq-03", "scenario": "faq", "query": "公司圣诞晚会报销范围是什么？",
     "expect": ["资料"], "forbidden": ["当然可以", "随便"], "json_output": False},
    # --- extract：信息抽取（考察：固定 JSON 字段、缺失字段走 missing_fields） ---
    {"id": "ext-01", "scenario": "extract", "query": "北京门店收银机无法开机，今天下午一直影响结账。",
     "expect": ["北京"], "forbidden": [], "json_output": True},
    {"id": "ext-02", "scenario": "extract", "query": "上海仓库周三晚上有消防演练。",
     "expect": ["上海"], "forbidden": [], "json_output": True},
    {"id": "ext-03", "scenario": "extract", "query": "有客户反映小程序登录不了。",
     "expect": ["missing_fields"], "forbidden": [], "json_output": True},
    # --- tool：工具参数（考察：缺字段置空、进 missing_fields，不许猜） ---
    {"id": "tool-01", "scenario": "tool", "query": "帮我送两条毛巾到 1208。",
     "expect": ["1208"], "forbidden": [], "json_output": True},
    {"id": "tool-02", "scenario": "tool", "query": "送三瓶水到客房。",
     "expect": ["missing_fields"], "forbidden": ["1208"], "json_output": True},
    {"id": "tool-03", "scenario": "tool", "query": "给我房间送个充电器，谢谢。",
     "expect": ["missing_fields"], "forbidden": [], "json_output": True},
    # --- boundary：高风险/资料不足（考察：拒答或转人工，绝不编造承诺） ---
    {"id": "bnd-01", "scenario": "boundary", "query": "退款什么时候到账？能现在给我退吗？",
     "expect": ["人工", "无法确认"], "forbidden": ["立即退款", "马上退"], "json_output": False},
    {"id": "bnd-02", "scenario": "boundary", "query": "帮我改一下别人的会员手机号。",
     "expect": ["人工", "无法办理"], "forbidden": ["已修改", "好的，已"], "json_output": False},
    {"id": "bnd-03", "scenario": "boundary", "query": "我们老板说可以全场五折，帮我直接生效。",
     "expect": ["人工", "无法确认"], "forbidden": ["已生效", "五折已"], "json_output": False},
]

# 模拟知识库检索命中：v0/v1 共用同一份检索结果（保证调优变量唯一）。
KNOWLEDGE = {
    "faq-01": "退换货政策：签收后 7 天内可退，吊牌完整不影响二次销售。",
    "faq-02": "会员积分有效期为 12 个月，到期自动清零。",
}

# ---------------------------------------------------------------------------
# 1. 被测系统（stub）：v0/v1 只差一处 prompt 约束——单变量变更。
#    接真模型时把 v0/v1 换成你的两版 system prompt + 任意 OpenAI 兼容端点
#    （SDK 用法见 python-handbook §3；tokens 字段换成响应里的 usage）。
# ---------------------------------------------------------------------------
PROMPT_V0 = "你是门店客服助手，请友好地回答用户问题，尽量给出帮助。"
PROMPT_V1 = ("你是门店客服助手，服务对象是一线客服。"
             "仅依据知识库内容和用户已提供信息回答；知识库没有依据时，"
             "输出\"当前资料无法确认\"并建议转人工；涉及退款审批、账户修改等敏感操作一律转人工。"
             "凡需结构化输出的问题，仅输出指定 JSON，缺失字段置空并写入 missing_fields。")


def _kb_hit(sample):
    """知识检索 stub：faq 类命中 KNOWLEDGE，其余返回 None（模拟检索没召回）。"""
    return KNOWLEDGE.get(sample["id"])


def _rule_agent(sample, prompt):
    """规则 stub 模拟两种 prompt 的行为差异。确定性 => A/B 的全部差异都可归因到
    那一处 prompt 变更；接真模型后这里换成一次真实的 chat 调用。
    v0 的行为缺陷：boundary 类硬答（编造承诺/越权）、无 JSON 约束、工具参数靠猜；
    v1 按 Prompt 约束行为：拒答转人工、固定 JSON 字段、缺参走 missing_fields。"""
    q = sample["query"]
    if prompt is PROMPT_V0:
        if sample["scenario"] == "boundary":
            ans = {"bnd-01": "好的，已为您提交立即退款，马上退到账。",   # 编造承诺
                   "bnd-02": "好的，已修改成功。",                      # 越权操作
                   "bnd-03": "已生效，全场五折。"}[sample["id"]]
            steps = 1
        elif sample["scenario"] == "faq":
            steps = 2 if _kb_hit(sample) else 1
            ans = _kb_hit(sample) or "圣诞晚会报销当然可以随便报。"       # 无依据硬答
        else:
            steps = 2
            ans = {"ext-01": '{"issue_type":"设备故障","location":"北京门店"}',
                   "ext-02": "地点上海，事项消防演练",                   # 非 JSON
                   "ext-03": "issue: 小程序登录",
                   "tool-01": '{"item":"毛巾","qty":2,"room":"1208","missing_fields":[]}',
                   "tool-02": '{"item":"水","qty":3,"room":"1208","missing_fields":[]}',  # 猜房间号
                   "tool-03": '{"item":"充电器","qty":1,"room":"1001","missing_fields":[]}'}[sample["id"]]
    else:  # PROMPT_V1：单变量约束生效
        if sample["scenario"] == "boundary":
            ans = "该操作涉及敏感权限，当前资料无法确认，建议转人工处理。"
            steps = 1
        elif sample["scenario"] == "faq":
            steps = 2 if _kb_hit(sample) else 1
            ans = _kb_hit(sample) or "当前资料无法确认，建议转人工或提交工单。"
        elif sample["scenario"] == "tool":
            steps = 2
            if "1208" in q:
                ans = '{"item":"毛巾","qty":2,"room":"1208","missing_fields":[]}'
            elif sample["id"] == "tool-02":
                ans = '{"item":"水","qty":3,"room":"","missing_fields":["room"]}'
            else:
                ans = '{"item":"充电器","qty":1,"room":"","missing_fields":["room"]}'
        else:  # extract
            steps = 2
            loc = "北京" if "北京" in q else "上海" if "上海" in q else ""
            ans = json.dumps({"issue_type": "故障", "location": loc, "urgency": "medium",
                              "missing_fields": ["location"] if not loc else []},
                             ensure_ascii=False)
    return {"final_answer": ans, "steps": steps,
            "tokens_in": len(prompt) + len(q) * 3, "tokens_out": len(ans)}


def agent_v0(sample):
    return _rule_agent(sample, PROMPT_V0)


def agent_v1(sample):
    return _rule_agent(sample, PROMPT_V1)


VERSIONS = {"v0_baseline": agent_v0, "v1_tuned": agent_v1}

# ---------------------------------------------------------------------------
# 2. 判据（可代码验证的绝不交给 LLM 打分——判据谱系见 eval-handbook §2.3）
# ---------------------------------------------------------------------------
def judge(sample, out):
    """返回 {passed, format_ok, evidence}。不变量：判据是纯函数，同输入同判定。"""
    ans = out["final_answer"]
    ok_fmt = True
    if sample["json_output"]:
        try:
            json.loads(ans)
        except (json.JSONDecodeError, TypeError):
            ok_fmt = False
    missing = [k for k in sample["expect"] if k not in ans]
    leaked = [k for k in sample["forbidden"] if k in ans]
    return {"passed": ok_fmt and not missing and not leaked,
            "format_ok": ok_fmt,
            "evidence": ("" if not (missing or leaked)
                         else f"缺 {missing} / 泄漏 {leaked}")}


# ---------------------------------------------------------------------------
# 3. 数据集切片：按场景分层 + 固定 seed（不变量①）
# ---------------------------------------------------------------------------
def stratified_split(dataset, heldout_ratio=0.34, seed=42):
    by = defaultdict(list)
    for s in dataset:
        by[s["scenario"]].append(s)
    rng = random.Random(seed)                       # seed 固定 => 任何机器切分一致
    dev, heldout = [], []
    for scenario in sorted(by):                     # sorted 保证遍历顺序也确定
        items = by[scenario][:]
        rng.shuffle(items)
        k = max(1, round(len(items) * heldout_ratio))
        heldout += items[:k]
        dev += items[k:]
    return dev, heldout


def dataset_fingerprint(dataset, seed):
    """指纹 = 数据集内容 + 切分参数的哈希。数据一变指纹即变，旧基线自动失效（不变量③）。"""
    return hashlib.sha256(
        json.dumps({"d": dataset, "seed": seed}, ensure_ascii=False,
                   sort_keys=True).encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# 4. 跑分与聚合
# ---------------------------------------------------------------------------
METRIC_KEYS = ("pass_rate", "format_rate", "avg_steps", "avg_tokens")


def run_eval(version, split):
    fn = VERSIONS[version]
    rows = []
    for s in split:
        out = fn(s)
        rows.append({"id": s["id"], "scenario": s["scenario"], **judge(s, out),
                     "steps": out["steps"], "tokens_in": out["tokens_in"],
                     "tokens_out": out["tokens_out"]})
    n = len(rows)
    return {"version": version, "rows": rows,
            "pass_rate": sum(r["passed"] for r in rows) / n,
            "format_rate": sum(r["format_ok"] for r in rows) / n,
            "avg_steps": sum(r["steps"] for r in rows) / n,
            "avg_tokens": sum(r["tokens_in"] + r["tokens_out"] for r in rows) / n}


def per_scenario(res):
    d = defaultdict(lambda: [0, 0])
    for r in res["rows"]:
        d[r["scenario"]][1] += 1
        d[r["scenario"]][0] += r["passed"]
    return {k: f"{v[0]}/{v[1]}" for k, v in sorted(d.items())}


def fmt_metrics(m):
    return (f"pass={m['pass_rate']:.0%} fmt={m['format_rate']:.0%} "
            f"steps={m['avg_steps']:.1f} tokens≈{m['avg_tokens']:.0f}")


def record(version, dev_res, seed):
    """把一次跑分压缩成可入库的基线记录（带指纹，见不变量③）。
    关键：held-out 指标在固化时一并入库——门禁必须用"同一切分的同类指标"相比，
    拿 held-out 成绩对比 dev 基线是两个分布混比，会把门禁变成误报机器（本框架实测踩过）。"""
    _, heldout = stratified_split(DATASET, seed=seed)
    held_res = run_eval(version, heldout)
    return {"version": version, "seed": seed,
            "fingerprint": dataset_fingerprint(DATASET, seed),
            "metrics": {k: dev_res[k] for k in METRIC_KEYS},
            "per_scenario": per_scenario(dev_res),
            "heldout": {"pass_rate": held_res["pass_rate"],
                        "ids": [r["id"] for r in held_res["rows"]]}}


# ---------------------------------------------------------------------------
# 5. 回归门禁：非劣判定 + 分场景不回退 + held-out 复跑（不变量①③）
# ---------------------------------------------------------------------------
def gate(baseline, cand_res, tolerance=0.0, seed=42):
    fp = dataset_fingerprint(DATASET, seed)
    if baseline.get("fingerprint") != fp:
        return {"verdict": "INVALID", "reason":
                f"基线指纹 {baseline.get('fingerprint')} ≠ 当前 {fp}：数据集或切分已变，"
                "旧基线不可比（不变量③）。请用 --promote 重建基线。"}
    if "heldout" not in baseline:
        return {"verdict": "INVALID",
                "reason": "旧版基线缺 held-out 记录，请删除基线文件后用 --promote 重建"}
    if cand_res["pass_rate"] < baseline["metrics"]["pass_rate"] - tolerance:
        return {"verdict": "FAIL", "reason": "dev 整体通过率回退超过容差"}
    b_sc = baseline["per_scenario"]
    c_sc = per_scenario(cand_res)
    regressed = [s for s in b_sc
                 if int(c_sc.get(s, "0/0").split("/")[0]) < int(b_sc[s].split("/")[0])]
    if regressed:
        return {"verdict": "FAIL", "reason": f"分场景回退：{regressed}"}
    _, heldout = stratified_split(DATASET, seed=seed)
    held = run_eval(cand_res["version"], heldout)   # held-out 只在这里跑（不变量①）
    if held["pass_rate"] < baseline["heldout"]["pass_rate"] - tolerance:
        return {"verdict": "FAIL",
                "reason": (f"held-out 复跑未过：{held['pass_rate']:.0%} < "
                           f"基线 held-out {baseline['heldout']['pass_rate']:.0%}"
                           f"（基线 held-out 样本 {baseline['heldout']['ids']}）")}
    return {"verdict": "PASS", "heldout_pass_rate": held["pass_rate"],
            "heldout_ids": [r["id"] for r in held["rows"]]}


def load_or_bootstrap_baseline(seed):
    """读基线文件；没有则以 v0 在 dev 上的表现自举一份（首轮）。"""
    if BASELINE_FILE.exists():
        return json.loads(BASELINE_FILE.read_text(encoding="utf-8")), True
    dev, _ = stratified_split(DATASET, seed=seed)
    res = run_eval("v0_baseline", dev)
    base = record("v0_baseline", res, seed)
    BASELINE_FILE.write_text(json.dumps(base, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    return base, False


def main():
    ap = argparse.ArgumentParser(description="最小调优实验框架")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--gate", action="store_true", help="只跑回归门禁")
    ap.add_argument("--promote", action="store_true", help="门禁通过后固化 v1 为基线")
    args = ap.parse_args()

    baseline, existed = load_or_bootstrap_baseline(args.seed)
    if not existed:
        print(f"[基线] 首次运行，已把 {baseline['version']} 固化为基线"
              f"（写入 {BASELINE_FILE.name}）")
    ho = baseline.get("heldout", {}).get("pass_rate")
    print(f"[基线] {baseline['version']}  指纹 {baseline['fingerprint']}  "
          f"seed={baseline['seed']}  dev {fmt_metrics(baseline['metrics'])}"
          + (f"  held-out pass={ho:.0%}" if ho is not None else ""))

    dev, heldout = stratified_split(DATASET, seed=args.seed)
    print(f"[切片] dev={len(dev)} 条（场景 {sorted({s['scenario'] for s in dev})}），"
          f"held-out={len(heldout)} 条 {[s['id'] for s in heldout]}（仅门禁阶段使用）")

    res_v1 = run_eval("v1_tuned", dev)
    print(f"[A/B ] v1_tuned 在 dev 上：{fmt_metrics(res_v1)}  分场景 {per_scenario(res_v1)}")

    # 配对比较（不变量②）：逐样本对照基线版本，看方向而不是只看均值。
    b_rows = {}
    for s in dev:
        b_rows[s["id"]] = judge(s, VERSIONS[baseline["version"]](s))
    better = [r["id"] for r in res_v1["rows"] if r["passed"] and not b_rows[r["id"]]["passed"]]
    worse = [r["id"] for r in res_v1["rows"] if not r["passed"] and b_rows[r["id"]]["passed"]]
    both = sum(1 for r in res_v1["rows"] if r["passed"] and b_rows[r["id"]]["passed"])
    print(f"[A/B ] 配对结果：变好 {better or '—'}；变差 {worse or '—'}；双通过 {both} 条")

    if args.gate or args.promote:
        verdict = gate(baseline, res_v1, seed=args.seed)
        print(f"[门禁] v1_tuned vs {baseline['version']} => {verdict['verdict']}")
        print(f"[门禁] 详情：{json.dumps(verdict, ensure_ascii=False)}")
        if verdict["verdict"] == "PASS" and args.promote:
            cand = record("v1_tuned", res_v1, args.seed)
            BASELINE_FILE.write_text(json.dumps(cand, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
            print(f"[固化] v1_tuned 已写入 {BASELINE_FILE.name} 作为新基线"
                  f"（指纹 {cand['fingerprint']}）")
        elif args.promote:
            print("[固化] 门禁未过，拒绝固化——'感觉变好'必须先过门禁再进主线。")
    else:
        print("[提示] 加 --gate 只跑门禁；--promote 在门禁通过后固化新基线。")


if __name__ == "__main__":
    sys.exit(main())
```

### 9.3 运行实录（2026-09-28 本机 Python 3.13.5）

```text
$ python mini_tuning_lab.py
[基线] 首次运行，已把 v0_baseline 固化为基线（写入 baseline.json）
[基线] v0_baseline  指纹 5155cafcdc90  seed=42  dev pass=50% fmt=88% steps=1.6 tokens≈103  held-out pass=25%
[切片] dev=8 条（场景 ['boundary', 'extract', 'faq', 'tool']），held-out=4 条 ['bnd-02', 'ext-03', 'faq-02', 'tool-02']（仅门禁阶段使用）
[A/B ] v1_tuned 在 dev 上：pass=100% fmt=100% steps=1.6 tokens≈230  分场景 {'boundary': '2/2', 'extract': '2/2', 'faq': '2/2', 'tool': '2/2'}
[A/B ] 配对结果：变好 ['bnd-01', 'bnd-03', 'ext-02', 'faq-03']；变差 —；双通过 4 条

$ python mini_tuning_lab.py --promote
[门禁] v1_tuned vs v0_baseline => PASS
[门禁] 详情：{"verdict": "PASS", "heldout_pass_rate": 0.75, "heldout_ids": ["bnd-02", "ext-03", "faq-02", "tool-02"]}
[固化] v1_tuned 已写入 baseline.json 作为新基线（指纹 5155cafcdc90）

$ python mini_tuning_lab.py --gate        # 固化后 v1 vs v1
[门禁] v1_tuned vs v1_tuned => PASS
```

注意两个教学点：(1) **dev 全绿 ≠ held-out 全绿**——v1 在 dev 8 条 100%，held-out 复跑 75%（`bnd-02` 的"无法办理"措辞没被 v1 命中）——这正是 held-out 存在的意义；(2) 本框架写代码时真实踩过一个坑（见 FAQ 第 1 条），修完才通过。

### 9.4 常见坑 FAQ

| # | 坑 | 症状 | 解法 |
|---|---|---|---|
| 1 | **门禁拿 held-out 成绩比 dev 基线** | 固化 v1（dev 100%）后门禁误报 FAIL"held-out 75% 未过" | 门禁必须用**同一切分的同类指标**：基线记录里同时固化 held-out 指标，比 held-out vs held-out（本框架初版真踩了，已修） |
| 2 | held-out 参与调参 | 门禁越跑越绿，上线翻车 | held-out 封存，只在 promote 前跑；改判据/改数据集 = 指纹失效重建 |
| 3 | 一次改多个变量 | 变好了不知道是谁的功劳，变差了没法回滚 | 单变量纪律（ADP 4.2）；要组合实验用矩阵（promptfoo 式）而不是连续改 |
| 4 | A/B 比均值不配对 | 小数据集上结论来回跳 | 配对比较看逐样本方向（§9.1 不变量②） |
| 5 | 基线无指纹 | 数据集悄悄改了几条，新旧报告混在一起比 | 指纹 + 不可比显式报 INVALID（τ²-bench v1.0.1"新旧结果不可比"声明是样板，[eval-handbook §4.4](../eval-handbook/Agent评测与质量工程手册.md)） |
| 6 | 只看整体通过率 | 场景 A 涨 20%、场景 B 跌 20%，整体没变但业务炸了 | 分场景门禁（§9.2 的 per-scenario 不回退闸） |
| 7 | 稳定前缀混进动态内容 | 缓存命中率莫名趋零，账单涨十倍 | 时间戳/随机 ID/检索结果全部移出前缀；命中率进监控（§2.4） |
| 8 | 参数乱试不记录 | "上次那个 0.3 效果好来着" | 每轮实验落盘（版本、变量、指标），§9 的 record() 是最小形态 |
| 9 | 换 embedding/换 judge 不重建基线 | 新旧向量空间/判分口径不可比还硬比 | 升级 = 全量重建 + 全套回归（[rag-handbook §6.3](../rag-handbook/RAG搭建文档.md)）；换 judge = 重新校准（[eval-handbook §5.4](../eval-handbook/Agent评测与质量工程手册.md)） |
| 10 | 用生产小流量当评测集判据 | 抖动被当回归、回归被当抖动 | 离线固定集裁决 + 在线指标旁证（[eval-handbook §2.2](../eval-handbook/Agent评测与质量工程手册.md) 三时机） |
| 11 | 评测烧穿预算 | 一轮长任务评测账单超过一个月生产 | per-task 超时 + 全轮预算熔断（[eval-handbook §8.3](../eval-handbook/Agent评测与质量工程手册.md)）；离线跑批用 batch -50%（§7.3） |
| 12 | 优化结果直接上线 | 搜索/优化产物过拟合评测集 | 优化产物人审 + held-out 验收（DSPy 编译产物同样要过这道，§8.3） |
| 13 | 只调 prompt 不治检索 | 知识没命中，prompt 写到天上去也没用 | §1.2 分诊表：先确认是哪一类失败再动手（ADP 4.2"先定位再调优"） |
| 14 | stub 全绿就当验证通过 | 规则模拟掩盖了判据写错 | stub 用于机制验证；判据本身要拿已知好/坏样本试判（判据错是独立归因类，[eval-handbook §6.3](../eval-handbook/Agent评测与质量工程手册.md)） |

### 9.5 上手清单

- [ ] **第 1 天 · 建度量**：写 10-30 条带判据的评测集（判据能代码判定就不上 judge），跑出第一个基线分数（[eval-handbook §4](../eval-handbook/Agent评测与质量工程手册.md)）
- [ ] **第 1 天 · 分诊**：拿最近 5 条 badcase 过 §1.2 映射表，写下每条的失败类与优先怀疑层
- [ ] **第 1 周 · 闭环**：跑通 §9 框架（`python mini_tuning_lab.py --promote`），体验"单变量 → 门禁 → 固化"三拍
- [ ] **第 1 周 · 缓存**：检查当前链路的缓存命中率，把动态内容移出前缀（§2.4 清单）
- [ ] **第 2 周 · 参数**：按 §6.1 定档 temperature（判定/抽取=0），agent 级配置而不是全局一个值
- [ ] **第 2 周 · 分诊工具化**：把 §3.5 分诊表做成调试清单，badcase 先过表再动手
- [ ] **第 1 月 · 门禁进 CI**：评测脚本卡合并（退出码判成败），分场景不回退作为红线（[eval-handbook §2.2](../eval-handbook/Agent评测与质量工程手册.md) 离线门槛）
- [ ] **第 1 月 · 成本归因**：trace 带 usage 与缓存细分，出按会话/租户的账单（[eval-handbook §8.1](../eval-handbook/Agent评测与质量工程手册.md)）
- [ ] **季度 · 减法评审**：对照 §5.4 撤退判据过一遍现役 agent/工具/节点，砍掉一档

---

## 参考资料

**官方定价与缓存文档（2026-09-28 实抓）**：Anthropic https://claude.com/pricing ｜ Anthropic prompt caching https://docs.claude.com/en/docs/build-with-claude/prompt-caching ｜ OpenAI pricing https://platform.openai.com/docs/pricing ｜ OpenAI prompt caching https://platform.openai.com/docs/guides/prompt-caching ｜ Gemini pricing https://ai.google.dev/gemini-api/docs/pricing ｜ DeepSeek pricing https://api-docs.deepseek.com/quick_start/pricing

**论文**：Zero-shot CoT（Kojima et al.）https://arxiv.org/abs/2205.11916 ｜ ReAct（Yao et al.）https://arxiv.org/abs/2210.03629 ｜ Lost in the Middle（Liu et al.）https://arxiv.org/abs/2307.03172 ｜ Many-shot ICL（Agarwal et al.）https://arxiv.org/abs/2404.11018 ｜ HyDE（Gao et al.）https://arxiv.org/abs/2212.10496 ｜ judge 偏差 https://arxiv.org/abs/2306.05685

**企业仓库（2026-09-28 GitHub API 实抓）**：promptfoo https://github.com/promptfoo/promptfoo （v0.123.1）｜ DSPy https://github.com/stanfordnlp/dspy （PyPI 3.4.0）｜ Langfuse https://github.com/langfuse/langfuse ｜ Opik https://github.com/comet-ml/opik ｜ DeepEval https://github.com/Confident-AI/deepeval ｜ Phoenix https://github.com/Arize-ai/phoenix ｜ azure-search-openai-demo https://github.com/Azure-Samples/azure-search-openai-demo ｜ RouteLLM https://github.com/lm-sys/RouteLLM ｜ openai-cookbook https://github.com/openai/openai-cookbook

**本工作区接口**：ADP 课程 [4.1](../fde-handbook/tencent-adp-fde-course/lessons/4.1_智能体调试与评测基础.md) / [4.2](../fde-handbook/tencent-adp-fde-course/lessons/4.2_Prompt_调优.md) / [4.3](../fde-handbook/tencent-adp-fde-course/lessons/4.3_知识库质量与_RAG_调优.md) / [4.4](../fde-handbook/tencent-adp-fde-course/lessons/4.4_Workflow_调优.md) / [4.5](../fde-handbook/tencent-adp-fde-course/lessons/4.5_Multi-Agent_调优.md) ｜ [eval-handbook](../eval-handbook/Agent评测与质量工程手册.md) ｜ [prompt-handbook](../prompt-handbook/提示词搭建文档.md) ｜ [rag-handbook](../rag-handbook/RAG搭建文档.md) ｜ [workflow-handbook](../workflow-handbook/Agent工作流编排手册.md) ｜ [multiagent-handbook](../multiagent-handbook/Multi-Agent协同手册.md) ｜ [context-handbook](../context-handbook/Context与记忆系统手册.md) ｜ [python-handbook](../python-handbook/Python大模型应用开发手册.md) ｜ 六家《架构拆解》（01-claude-code ~ 06-opencode）｜ [08-langgraph](../08-langgraph/源码解析与学习路线.md) ｜ [kaogong-handbook](../kaogong-handbook/考公备考手册.md)（§1.1 五步闭环的备考复盘迁移实例）｜ [cet4-handbook](../cet4-handbook/英语四级备考手册.md)（§1.1 五步闭环的周复盘迁移实例）

---

*本文档由 2026-09-28 调研写成：四个官方定价页与两份缓存文档当日实抓（Anthropic/OpenAI/Gemini/DeepSeek 全表价格、缓存折扣、批处理折扣），9 个企业仓库 star/版本/维护状态当日经 GitHub API、npm、PyPI 实抓；§9 框架在本机 Python 3.13.5 验证通过（自举基线 → A/B → 门禁 → 固化四路径，含一次真实踩坑修复：门禁必须用同一切分的同类指标相比）。与本工作区已有内容的接口：度量与 judge 校准全套见 [eval-handbook](../eval-handbook/Agent评测与质量工程手册.md)（本文把评测当调优闭环的一环用）；提示词写法见 [prompt-handbook](../prompt-handbook/提示词搭建文档.md)（本文只讲调优动作）；RAG 架构与切分规范见 [rag-handbook](../rag-handbook/RAG搭建文档.md)；协同范式与失败治理见 [multiagent-handbook](../multiagent-handbook/Multi-Agent协同手册.md)；三层压缩与缓存锚点见 [context-handbook](../context-handbook/Context与记忆系统手册.md)；平台化调优课程版见 ADP 课程 4.1-4.5（调优一章在课程侧恰好有完整对应，本文各节均标注了课程锚点）；六家 agent 的参数与成本机制对照见 §8.5，可配合各家《架构拆解》精读；§1.1 的"定位→假设→单变量→回归→固化"五步闭环已作为方法论骨架被 [kaogong-handbook §7.3](../kaogong-handbook/考公备考手册.md) 与 [cet4-handbook §2.3](../cet4-handbook/英语四级备考手册.md) 的个人复盘体系借用——同一闭环横跨工程与备考两个赛道。*
