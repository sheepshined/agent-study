# AI 应用岗面试题库：LLM 应用开发 · Agent 工程 · FDE 方向（128 题）

> 信息基准日：2026-09-28。本册是**纯做题库与答题训练**：题目素材全部取自本工作区既有专题手册（mcp / skill / rag / prompt / python / eval / context / multiagent / security / workflow / tuning / fde），每题答案带相对链接可回查原文；模型价格与框架动态为 2026-09-28 当日实抓口径（与 [tuning-handbook §6.6](../tuning-handbook/Agent调优手册.md) 一致——四家官方定价页当日抓取），随时间漂移。
>
> 分工边界：**求职策略、公司名单、薪资行情、投递方法看 [fde-handbook《FDE转行手册》](../fde-handbook/FDE转行手册.md)**（其 §8.6 十道高频题只有问题没有答案，本册主题六是它们的答题训练版）；**算法题（链表/DP/图论等）看 [python-handbook/leetcode-hot100](../python-handbook/leetcode-hot100/README.md)**，本册"手撕代码"只考 AI 应用工程写法。英文术语首次出现处标注中文。

## 文件清单

| 文件 | 主题 | 题数 | 高频题速览 |
|---|---|---|---|
| [01-LLM基础与提示词.md](01-LLM基础与提示词.md) | token 与计费 · 采样参数 · 流式与结构化输出 · 提示词工程 · 提示缓存 · 注入防御 | 20 | 9 题 |
| [02-RAG与知识库.md](02-RAG与知识库.md) | 管线与切分 · 混合检索与重排 · 引用与评测 · 多租户隔离 · 检索安全 | 20 | 6 题 |
| [03-Agent架构与工具调用.md](03-Agent架构与工具调用.md) | 主循环与规划 · 工具系统与 MCP/Skill · 子代理与上下文 · 权限与持久化 · 多 agent 编排 | 20 | 8 题 |
| [04-评测调优与成本工程.md](04-评测调优与成本工程.md) | 评测集与判据 · LLM-as-judge · 轨迹归因 · 调优闭环 · 失败分类学 · 成本与延迟 | 18 | 10 题 |
| [05-系统设计与场景题.md](05-系统设计与场景题.md) | 知识库问答 · 客服与审核 · 多租户与网关 · 长文档 · 记忆与私有化 · 多 agent 系统 | 18 | 6 题 |
| [06-行为面与FDE实战场景.md](06-行为面与FDE实战场景.md) | STAR 行为题 · 客户情景轮 · 欠规格场景拆解 · 排障 triage · 拆解轮演练 | 16 | 6 题 |
| [07-手撕代码与工程实践.md](07-手撕代码与工程实践.md) | agent loop · 工具调用 · RAG 管线 · 评测脚本 · 流式端点 · 编排器 · judge | 16 | 7 题 |
| **合计** | | **128** | **52 题（40.6%）** |

每题统一四件套格式：**Q 编号与标签（难度｜频次）→ 考察点 → 参考回答（要点式，达到"能通过面试"的完整度）→ 追问与陷阱（2-3 个追问 + 常见错误答案）→ 加分项 → 延伸阅读（相对链接指向工作区手册章节）**。各主题开头有"高频题速览表"，面试前一晚只刷速览表。

## 怎么刷（三遍法）

1. **第一遍·过面（速览表）**：只做每主题"高频题速览表"（52 题）。每题先自己答一遍再对照"参考回答"，能复述 70% 要点即过；答不出的把"延伸阅读"那节手册读了。目标：2-3 天。
2. **第二遍·过线（追问链）**：全量 128 题按主题推进。重点不是背"参考回答"，而是练"追问与陷阱"——每题让同伴（或自己扮演面试官）沿追问方向连追 3 层，追到答不上为止，把"常见错误"清单当扣分项自查。目标：7-10 天。
3. **第三遍·过关（白板与情景）**：只练 07（手撕，白板写骨架并出声讲解）与 06（行为面与客户情景，限时口头作答）。手撕题标准：先说接口设计再动手，10-30 行骨架写完，边界与错误处理主动补上。

## 怎么模拟（全真面试）

- **限时纪律**：基础/概念题 5 分钟、系统设计 25 分钟（含澄清）、行为面每题 8 分钟、手撕 15-20 分钟。超时即切"收尾话术"。
- **FDE 铁律先澄清再作答**：任何场景题第一句都应是向"面试官"澄清需求（规模、数据敏感级、实时性、成功标准）——"无二值成功标准的任务 = 高风险未知项，必须显式记录"（[fde-handbook §3.2](../fde-handbook/FDE转行手册.md)）。
- **出声思考**：Palantir 拆解轮考的就是出声思考与澄清提问（[fde-handbook §8.5](../fde-handbook/FDE转行手册.md)），平时练习就要开口。
- **五段式全真模拟**（每周一次，流程见 [fde-handbook §8.5](../fde-handbook/FDE转行手册.md)）：① recruiter 自我介绍 + Why FDE（Q097）→ ② 编码轮（07 抽 2 题）→ ③ 系统设计（05 抽 1 题）→ ④ 客户情景轮（06 抽 2 题，同伴扮演挑剔客户/暴怒 CTO）→ ⑤ 行为轮（STAR 故事 8 个已备好）。
- **录音复盘**：对照"参考回答"补齐缺失要点，统计自己踩了哪些"常见错误"，同题三天后复测。
- **行为面弹药库**：每个项目写 5 个故事、共备 8 个 STAR（Situation-Task-Action-Result）故事（[fde-handbook §8.7](../fde-handbook/FDE转行手册.md)）；工作区学习者可直接拿"六家 agent《架构拆解》+ 评测/调优手册"当项目案例库（映射关系见 [fde-handbook §4](../fde-handbook/FDE转行手册.md)）。

## 14 天面试冲刺路线

| 天 | 题目 | 配套手册精读 | 产出 |
|---|---|---|---|
| D1 | 01 高频 9 题 | [prompt-handbook §2/§5](../prompt-handbook/提示词搭建文档.md) | 概念卡：token/参数/缓存 |
| D2 | 01 其余 11 题 | [tuning-handbook §2/§6](../tuning-handbook/Agent调优手册.md) | 注入防御四分层默写 |
| D3 | 02 高频 6 题 | [rag-handbook §1-§3](../rag-handbook/RAG搭建文档.md) | RAG 管线图默画 |
| D4 | 02 其余 14 题 | [rag-handbook §6](../rag-handbook/RAG搭建文档.md)、[eval-handbook §4](../eval-handbook/Agent评测与质量工程手册.md) | 分诊口诀 + RAGAS 四指标 |
| D5 | 03 高频 8 题 | [01-claude-code 架构拆解 §3/§5](../01-claude-code/架构拆解.md)、[mcp-handbook §1-§2](../mcp-handbook/MCP搭建文档.md) | 白板写一遍最小 loop |
| D6 | 03 其余 12 题 | [context-handbook §2-§4](../context-handbook/Context与记忆系统手册.md)、[multiagent-handbook §1-§3](../multiagent-handbook/Multi-Agent协同手册.md) | 何时多 agent 四问判据 |
| D7 | 机动/复盘（缓冲半天） | 第一周错题全部重答 | 追问链记录 |
| D8 | 04 全部 18 题 | [eval-handbook §1-§6](../eval-handbook/Agent评测与质量工程手册.md) | 评测集设计模板 |
| D9 | 04 复盘 + 成本 | [tuning-handbook §7](../tuning-handbook/Agent调优手册.md) | 用 §6.6 价格表算一笔账 |
| D10 | 05 高频 6 题 | ADP 课程 [3.1](../fde-handbook/tencent-adp-fde-course/lessons/3.1_方案设计方法.md)/[3.3](../fde-handbook/tencent-adp-fde-course/lessons/3.3_单工作流模式实战：客服助手.md) | 系统设计答题框架 |
| D11 | 05 其余 12 题 | [security-handbook §5/§7](../security-handbook/AI应用安全手册.md)、[tuning-handbook §7](../tuning-handbook/Agent调优手册.md) | 上线检查单默写 |
| D12 | 06 全部 16 题 | [FDE实战工具箱 §2/§4/§8](../fde-handbook/FDE实战工具箱.md)、[fde-handbook §8.5-8.7](../fde-handbook/FDE转行手册.md) | 8 个 STAR 故事定稿 |
| D13 | 07 高频 7 题 | [python-handbook §5/§9](../python-handbook/Python大模型应用开发手册.md)、[workflow-handbook §8](../workflow-handbook/Agent工作流编排手册.md) | 白板骨架默写 3 题 |
| D14 | 07 其余 9 题 + 全真模拟 | 五段式全流程走一遍（按"怎么模拟"） | 录音复盘报告 |

> 算法题不在本路线主线：每天并行 1-2 题保手感即可，用 [leetcode-hot100 的 14 天路线](../python-handbook/leetcode-hot100/README.md)（100 题：简单 20 / 中等 68 / 困难 12）。

## 难度与频次分布

难度合计：**初级 38 题（29.7%）/ 中级 58 题（45.3%）/ 高级 32 题（25.0%）**；频次合计：**高 52（40.6%）/ 中 47（36.7%）/ 低 29（22.7%）**。

| 主题 | 初 | 中 | 高 | 频次高 | 频次中 | 频次低 |
|---|---|---|---|---|---|---|
| 01 LLM 基础与提示词 | 6 | 10 | 4 | 9 | 4 | 7 |
| 02 RAG 与知识库 | 7 | 9 | 4 | 6 | 7 | 7 |
| 03 Agent 架构与工具调用 | 6 | 10 | 4 | 8 | 8 | 4 |
| 04 评测调优与成本工程 | 5 | 8 | 5 | 10 | 6 | 2 |
| 05 系统设计与场景题 | 3 | 9 | 6 | 6 | 9 | 3 |
| 06 行为面与 FDE 实战场景 | 6 | 7 | 3 | 6 | 7 | 3 |
| 07 手撕代码与工程实践 | 5 | 5 | 6 | 7 | 6 | 3 |
| **合计** | **38** | **58** | **32** | **52** | **47** | **29** |

> 定位：初级题（30%）保证"概念清楚+能举例"不出错；中级题（45%）是多数 LLM 应用/Agent 岗的主战场；高级题（25%）面向系统设计轮与 FDE 客户情景轮的拉开差距环节。

## 全部题目索引

"对应手册"列只列首选一条；每题正文里的"延伸阅读"有更全的 1-3 条（含六家 agent《架构拆解》与 ADP 课程）。

### 01-LLM基础与提示词（Q001-Q020）

| 题号 | 题目 | 难度 | 频次 | 对应手册 |
|---|---|---|---|---|
| Q001 | 什么是 token？为什么按 token 计费与限流 | 初 | 高 | [tuning §6.6/§7.1](../tuning-handbook/Agent调优手册.md) |
| Q002 | temperature/top_p/seed 控制什么，生产怎么设 | 初 | 高 | [tuning §6.1](../tuning-handbook/Agent调优手册.md) |
| Q003 | system/user 提示词区别与分层 | 初 | 中 | [prompt §5](../prompt-handbook/提示词搭建文档.md) |
| Q004 | 幻觉是什么，RAG 为何缓解不根除 | 初 | 高 | [rag §1/§6](../rag-handbook/RAG搭建文档.md) |
| Q005 | 上下文窗口大为何不能全塞 | 初 | 低 | [context §1](../context-handbook/Context与记忆系统手册.md) |
| Q006 | 流式输出与 SSE | 初 | 中 | [python §3/§7](../python-handbook/Python大模型应用开发手册.md) |
| Q007 | few-shot 选择与排序 | 中 | 高 | [tuning §2.2](../tuning-handbook/Agent调优手册.md) |
| Q008 | CoT 与 ReAct，何时 CoT 有害 | 中 | 高 | [tuning §2.3](../tuning-handbook/Agent调优手册.md) |
| Q009 | 结构化输出方案与可靠性排序 | 中 | 高 | [tuning §6.3](../tuning-handbook/Agent调优手册.md) |
| Q010 | 提示缓存原理定价与稳定前缀 | 中 | 高 | [tuning §2.4/§7.2](../tuning-handbook/Agent调优手册.md) |
| Q011 | 中文 token 计量与成本估算的坑 | 中 | 中 | [context §2](../context-handbook/Context与记忆系统手册.md) |
| Q012 | 推理模型与快思考分工与价差 | 中 | 中 | [tuning §6.5-6.6](../tuning-handbook/Agent调优手册.md) |
| Q013 | 微调/提示工程/RAG 怎么选 | 中 | 低 | [prompt §1](../prompt-handbook/提示词搭建文档.md) |
| Q014 | 多模态输入怎么计价 | 中 | 低 | [tuning §6.6](../tuning-handbook/Agent调优手册.md) |
| Q015 | API 超时、重试与幂等设计 | 中 | 低 | [python §3](../python-handbook/Python大模型应用开发手册.md) |
| Q016 | 嵌入调用 vs 生成式调用 | 中 | 低 | [rag §2](../rag-handbook/RAG搭建文档.md) |
| Q017 | 注入防御为何检测器当边界是反模式 | 高 | 高 | [security §2](../security-handbook/AI应用安全手册.md) |
| Q018 | 生产级提示词的组织与装配（六家） | 高 | 高 | [prompt §4-§5](../prompt-handbook/提示词搭建文档.md) |
| Q019 | context rot 与 lost-in-the-middle | 高 | 低 | [context §1-§2](../context-handbook/Context与记忆系统手册.md) |
| Q020 | 为何顶级 agent 按模型分 prompt | 高 | 低 | [prompt §4.3](../prompt-handbook/提示词搭建文档.md) |

### 02-RAG与知识库（Q021-Q040）

| 题号 | 题目 | 难度 | 频次 | 对应手册 |
|---|---|---|---|---|
| Q021 | RAG 完整管线 | 初 | 高 | [rag §1](../rag-handbook/RAG搭建文档.md) |
| Q022 | 文档切分与 chunk 大小 | 初 | 高 | [rag §2](../rag-handbook/RAG搭建文档.md) |
| Q023 | 相似度度量与 top-k | 初 | 中 | [python §5](../python-handbook/Python大模型应用开发手册.md) |
| Q024 | 混合检索与 BM25 | 初 | 高 | [rag §3.3](../rag-handbook/RAG搭建文档.md) |
| Q025 | 重排与检索的关系 | 初 | 中 | [python §5](../python-handbook/Python大模型应用开发手册.md) |
| Q026 | 元数据字段 | 初 | 低 | [rag §2](../rag-handbook/RAG搭建文档.md) |
| Q027 | 引用可验证 | 初 | 低 | [rag §2](../rag-handbook/RAG搭建文档.md) |
| Q028 | 没召回 vs 召回答错的分诊 | 中 | 高 | [tuning §3.1](../tuning-handbook/Agent调优手册.md) |
| Q029 | 查询改写三招 | 中 | 中 | [tuning §3.4](../tuning-handbook/Agent调优手册.md) |
| Q030 | RAGAS 四指标与 golden dataset | 中 | 高 | [rag §6](../rag-handbook/RAG搭建文档.md) |
| Q031 | GraphRAG 与 Agentic RAG | 中 | 中 | [rag §7](../rag-handbook/RAG搭建文档.md) |
| Q032 | 多租户数据隔离 | 中 | 高 | [rag §6.5](../rag-handbook/RAG搭建文档.md) |
| Q033 | 嵌入选型与升级迁移 | 中 | 中 | [rag §6](../rag-handbook/RAG搭建文档.md) |
| Q034 | Agentic 检索 vs 索引式 RAG | 中 | 中 | [rag §1.4/§7.2](../rag-handbook/RAG搭建文档.md) |
| Q035 | 知识库三问分诊 | 中 | 中 | [ADP 4.3](../fde-handbook/tencent-adp-fde-course/lessons/4.3_知识库质量与_RAG_调优.md) |
| Q036 | 父子切分 | 中 | 低 | [tuning §3.3](../tuning-handbook/Agent调优手册.md) |
| Q037 | 检索 vs 记忆边界 | 高 | 中 | [context §7.5](../context-handbook/Context与记忆系统手册.md) |
| Q038 | 检索结果即不可信内容 | 高 | 低 | [security §2](../security-handbook/AI应用安全手册.md) |
| Q039 | PDF/表格/图片 RAG 要点 | 高 | 低 | [rag §2](../rag-handbook/RAG搭建文档.md) |
| Q040 | RAG 月度成本估算 | 高 | 低 | [tuning §7](../tuning-handbook/Agent调优手册.md) |

### 03-Agent架构与工具调用（Q041-Q060）

| 题号 | 题目 | 难度 | 频次 | 对应手册 |
|---|---|---|---|---|
| Q041 | agent 定义，与 chatbot/workflow 区别 | 初 | 高 | [workflow §1](../workflow-handbook/Agent工作流编排手册.md) |
| Q042 | 最小 agent loop | 初 | 高 | [01-claude-code §3](../01-claude-code/架构拆解.md) |
| Q043 | 工具调用完整时序 | 初 | 高 | [python §3](../python-handbook/Python大模型应用开发手册.md) |
| Q044 | 工具 JSON Schema 写法 | 初 | 中 | [multiagent §3](../multiagent-handbook/Multi-Agent协同手册.md) |
| Q045 | MCP 是什么解决什么 | 初 | 高 | [mcp §1-§2](../mcp-handbook/MCP搭建文档.md) |
| Q046 | Skill 与 MCP/斜杠命令生态位 | 初 | 中 | [skill §1](../skill-handbook/Skill搭建文档.md) |
| Q047 | 规划与任务分解失败 | 高 | 中 | [eval §6.3](../eval-handbook/Agent评测与质量工程手册.md) |
| Q048 | 子代理价值与上下文隔离 | 中 | 高 | [context §3](../context-handbook/Context与记忆系统手册.md) |
| Q049 | 何时真的需要多 agent | 中 | 高 | [multiagent §1](../multiagent-handbook/Multi-Agent协同手册.md) |
| Q050 | 编排范式怎么选 | 中 | 高 | [multiagent §2](../multiagent-handbook/Multi-Agent协同手册.md) |
| Q051 | 记忆类型与设计 | 中 | 中 | [context §4](../context-handbook/Context与记忆系统手册.md) |
| Q052 | 上下文预算与三层压缩 | 高 | 中 | [context §2](../context-handbook/Context与记忆系统手册.md) |
| Q053 | 工具返回具名 JSON | 中 | 中 | [multiagent §3](../multiagent-handbook/Multi-Agent协同手册.md) |
| Q054 | 权限与审批模型（六家对照） | 中 | 中 | [security §3](../security-handbook/AI应用安全手册.md) |
| Q055 | 状态持久化与事件溯源 | 中 | 低 | [04-zcode §10](../04-zcode/架构拆解.md) |
| Q056 | A2A 与 MCP 边界 | 中 | 低 | [multiagent §4](../multiagent-handbook/Multi-Agent协同手册.md) |
| Q057 | lethal trifecta | 中 | 中 | [security §1](../security-handbook/AI应用安全手册.md) |
| Q058 | 多 agent 失败模式与治理 | 中 | 低 | [multiagent §5](../multiagent-handbook/Multi-Agent协同手册.md) |
| Q059 | 控制流交给模型还是写死 | 高 | 高 | [workflow §1](../workflow-handbook/Agent工作流编排手册.md) |
| Q060 | 六家为何全自研不用框架 | 高 | 低 | [python §4.7](../python-handbook/Python大模型应用开发手册.md) |

### 04-评测调优与成本工程（Q061-Q078）

| 题号 | 题目 | 难度 | 频次 | 对应手册 |
|---|---|---|---|---|
| Q061 | 怎么证明 agent"变好了" | 初 | 高 | [eval §1](../eval-handbook/Agent评测与质量工程手册.md) |
| Q062 | LLM-as-judge 偏差与校准 | 初 | 高 | [eval §5](../eval-handbook/Agent评测与质量工程手册.md) |
| Q063 | 判据类型与优先级 | 初 | 中 | [eval §2.3](../eval-handbook/Agent评测与质量工程手册.md) |
| Q064 | 改一行 prompt 为何要回归 | 初 | 高 | [eval §2.2](../eval-handbook/Agent评测与质量工程手册.md) |
| Q065 | 调试五步法与批量评测分工 | 初 | 中 | [ADP 4.1](../fde-handbook/tencent-adp-fde-course/lessons/4.1_智能体调试与评测基础.md) |
| Q066 | 公共基准怎么选，能否当验收 | 高 | 中 | [eval §3](../eval-handbook/Agent评测与质量工程手册.md) |
| Q067 | 自建评测集怎么建 | 中 | 高 | [eval §4](../eval-handbook/Agent评测与质量工程手册.md) |
| Q068 | 轨迹评测：15 步做完 3 步任务 | 高 | 高 | [eval §6](../eval-handbook/Agent评测与质量工程手册.md) |
| Q069 | badcase 回流成资产 | 中 | 高 | [rag §6.4](../rag-handbook/RAG搭建文档.md) |
| Q070 | 可观测栈怎么搭 | 中 | 中 | [eval §7](../eval-handbook/Agent评测与质量工程手册.md) |
| Q071 | 调优闭环五步与单变量纪律 | 中 | 高 | [tuning §1.1](../tuning-handbook/Agent调优手册.md) |
| Q072 | 六类失败分诊 | 中 | 高 | [tuning §1.2](../tuning-handbook/Agent调优手册.md) |
| Q073 | prompt 调优杠杆 | 中 | 中 | [tuning §2](../tuning-handbook/Agent调优手册.md) |
| Q074 | A/B 评测可信设计 | 中 | 低 | [tuning §9](../tuning-handbook/Agent调优手册.md) |
| Q075 | 延迟预算分解 | 中 | 中 | [tuning §7.5](../tuning-handbook/Agent调优手册.md) |
| Q076 | 成本精算与缓存省钱 | 高 | 高 | [tuning §7.1-7.2](../tuning-handbook/Agent调优手册.md) |
| Q077 | 模型路由与级联降级 | 高 | 高 | [tuning §6.5](../tuning-handbook/Agent调优手册.md) |
| Q078 | 成本-质量-延迟三角 | 高 | 低 | [tuning §7.6](../tuning-handbook/Agent调优手册.md) |

### 05-系统设计与场景题（Q079-Q096）

| 题号 | 题目 | 难度 | 频次 | 对应手册 |
|---|---|---|---|---|
| Q079 | 企业知识库问答系统 | 初 | 高 | [rag §1-§3](../rag-handbook/RAG搭建文档.md) |
| Q080 | 文档审核流水线编排 | 初 | 中 | [workflow §2](../workflow-handbook/Agent工作流编排手册.md) |
| Q081 | 给产品加 AI 助手第一步 | 初 | 中 | [ADP 3.1](../fde-handbook/tencent-adp-fde-course/lessons/3.1_方案设计方法.md) |
| Q082 | 多租户 RAG 隔离设计 | 高 | 高 | [rag §6.5](../rag-handbook/RAG搭建文档.md) |
| Q083 | 客服 agent 与 HITL | 中 | 高 | [ADP 3.3](../fde-handbook/tencent-adp-fde-course/lessons/3.3_单工作流模式实战：客服助手.md) |
| Q084 | 数据分析 agent | 中 | 高 | [multiagent §2](../multiagent-handbook/Multi-Agent协同手册.md) |
| Q085 | 高并发 LLM 网关 | 高 | 中 | [tuning §7](../tuning-handbook/Agent调优手册.md) |
| Q086 | 千页 PDF 结构化提取 | 高 | 中 | [context §2](../context-handbook/Context与记忆系统手册.md) |
| Q087 | 跨会话记忆系统 | 中 | 中 | [context §4-§5](../context-handbook/Context与记忆系统手册.md) |
| Q088 | guardrails 分层 | 中 | 中 | [security §5](../security-handbook/AI应用安全手册.md) |
| Q089 | 私有化部署 | 中 | 低 | [python §6](../python-handbook/Python大模型应用开发手册.md) |
| Q090 | <100ms 实时风控加 LLM | 中 | 中 | [fde §8.6](../fde-handbook/FDE转行手册.md) |
| Q091 | prompt 版本管理与发布 | 中 | 低 | [workflow §6.5](../workflow-handbook/Agent工作流编排手册.md) |
| Q092 | 流式前后端链路 | 中 | 低 | [python §7](../python-handbook/Python大模型应用开发手册.md) |
| Q093 | 线上评测运营体系 | 中 | 中 | [eval §2/§7](../eval-handbook/Agent评测与质量工程手册.md) |
| Q094 | multi-agent 研究报告系统 | 高 | 高 | [multiagent §2-§3](../multiagent-handbook/Multi-Agent协同手册.md) |
| Q095 | 从 0 搭 agent 平台 | 高 | 中 | [03-deepseek-harness](../03-deepseek-harness/架构拆解.md) |
| Q096 | 存量系统渐进引入 agent | 高 | 高 | [security §7](../security-handbook/AI应用安全手册.md) |

### 06-行为面与FDE实战场景（Q097-Q112）

| 题号 | 题目 | 难度 | 频次 | 对应手册 |
|---|---|---|---|---|
| Q097 | Why FDE 动机故事 | 初 | 高 | [fde §8.7](../fde-handbook/FDE转行手册.md) |
| Q098 | 第一周做什么 | 初 | 高 | [fde §8.6](../fde-handbook/FDE转行手册.md) |
| Q099 | "AI doesn't work" 怎么调试 | 初 | 高 | [工具箱 §8](../fde-handbook/FDE实战工具箱.md) |
| Q100 | STAR 打磨项目介绍 | 初 | 中 | [fde §8.7/§4](../fde-handbook/FDE转行手册.md) |
| Q101 | 技术栈差距怎么补 | 初 | 中 | [fde §3](../fde-handbook/FDE转行手册.md) |
| Q102 | 向非技术客户讲概念 | 初 | 低 | [工具箱 §6](../fde-handbook/FDE实战工具箱.md) |
| Q103 | 数据质量差 deadline 已定 | 中 | 高 | [工具箱 §2](../fde-handbook/FDE实战工具箱.md) |
| Q104 | POC 成功集成失败 | 中 | 高 | [工具箱 §4](../fde-handbook/FDE实战工具箱.md) |
| Q105 | one-off 定制怎么处理 | 中 | 高 | [工具箱 §6](../fde-handbook/FDE实战工具箱.md) |
| Q106 | 暴怒 CTO 现场 triage | 中 | 中 | [eval §6](../eval-handbook/Agent评测与质量工程手册.md) |
| Q107 | 报价与成本模型 | 中 | 中 | [工具箱 §7](../fde-handbook/FDE实战工具箱.md) |
| Q108 | "准确率是多少"怎么答 | 中 | 中 | [eval §1.2](../eval-handbook/Agent评测与质量工程手册.md) |
| Q109 | 客户 IT 不配合 | 中 | 低 | [工具箱 §6](../fde-handbook/FDE实战工具箱.md) |
| Q110 | Palantir 拆解轮真题 | 高 | 中 | [fde §8.5](../fde-handbook/FDE转行手册.md) |
| Q111 | OpenAI 式 case study | 高 | 中 | [fde §8.5](../fde-handbook/FDE转行手册.md) |
| Q112 | 律所合同审查一周计划 | 高 | 低 | [工具箱 §2/§3/§5](../fde-handbook/FDE实战工具箱.md) |

### 07-手撕代码与工程实践（Q113-Q128）

| 题号 | 题目 | 难度 | 频次 | 对应手册 |
|---|---|---|---|---|
| Q113 | 手写最小 agent loop | 初 | 高 | [python §9](../python-handbook/Python大模型应用开发手册.md) |
| Q114 | 工具调用封装与分发 | 初 | 高 | [python §3/§9](../python-handbook/Python大模型应用开发手册.md) |
| Q115 | SSE 流式端点 | 初 | 中 | [python §7](../python-handbook/Python大模型应用开发手册.md) |
| Q116 | 超时与重试客户端 | 初 | 中 | [python §3](../python-handbook/Python大模型应用开发手册.md) |
| Q117 | 四档成本计算函数 | 初 | 低 | [tuning §7.1](../tuning-handbook/Agent调优手册.md) |
| Q118 | 手写 RAG 检索管线 | 中 | 高 | [python §5](../python-handbook/Python大模型应用开发手册.md) |
| Q119 | 评测脚本四文件 | 高 | 中 | [eval §10](../eval-handbook/Agent评测与质量工程手册.md) |
| Q120 | 递归文本切分器 | 中 | 高 | [rag §2](../rag-handbook/RAG搭建文档.md) |
| Q121 | 权限闸门工具循环 | 高 | 中 | [security §6](../security-handbook/AI应用安全手册.md) |
| Q122 | 结构化输出解析重试 | 中 | 中 | [tuning §6.3](../tuning-handbook/Agent调优手册.md) |
| Q123 | 对话历史滑窗+摘要 | 中 | 中 | [context §2/§8](../context-handbook/Context与记忆系统手册.md) |
| Q124 | prompt 模板渲染器 | 中 | 低 | [prompt §2](../prompt-handbook/提示词搭建文档.md) |
| Q125 | supervisor 多 agent 编排 | 高 | 高 | [multiagent §8](../multiagent-handbook/Multi-Agent协同手册.md) |
| Q126 | 最小工作流编排器 | 高 | 高 | [workflow §8](../workflow-handbook/Agent工作流编排手册.md) |
| Q127 | LLM-as-judge 评测器 | 高 | 高 | [eval §5/§10](../eval-handbook/Agent评测与质量工程手册.md) |
| Q128 | 预算熔断与语义缓存 | 高 | 低 | [tuning §7](../tuning-handbook/Agent调优手册.md) |

## 口径与维护

- 题库答案口径：数字（价格、百分比、基准规模、star）均取自工作区手册当日实抓记录或本册事实核查（2026-09-28），未新增未核实数字；引用六家 agent 机制的题以《架构拆解》的 `文件:行号` 为一手证据。
- 价格事实锚点（2026-09-28 官方定价页实抓，同 [tuning-handbook §6.6](../tuning-handbook/Agent调优手册.md)）：Anthropic Fable 5.1 $10/$50、Opus 5.5 $4/$20、Sonnet 5 $2/$10、Haiku 4.5 $1/$5；OpenAI gpt-5.2 $1.75/$14（缓存输入 10%）、gpt-5-nano $0.05/$0.40；Gemini 3.8-flash $0.75/$3.75（1M 窗口）、3.1-pro >200k 输入计价翻倍；DeepSeek flash $0.30/$1.20（缓存命中≈2%）。批处理一律 -50%，输出比输入贵 4-10×。
- 更新方式：价格与版本类答案随各手册季度复查时同步；题目本体稳定，新增题按主题追加编号（Q129 起）。
- 相关入口：[FDE 转行手册](../fde-handbook/FDE转行手册.md)（策略/公司/薪资）· [leetcode-hot100](../python-handbook/leetcode-hot100/README.md)（算法题）· [eval-handbook](../eval-handbook/Agent评测与质量工程手册.md) 与 [tuning-handbook](../tuning-handbook/Agent调优手册.md)（评测与调优方法论全集）。
- 相关入口（姊妹与同构册）：[mianjing-handbook](../mianjing-handbook/AI应用岗真实面经精评.md)（真实面经精评——本册的"现场版"，题号 Q001-Q128 互链）· [kaogong-handbook](../kaogong-handbook/考公备考手册.md)（冲刺路线与刷题三遍法体例同构，赛道不同）· [cet4-handbook](../cet4-handbook/英语四级备考手册.md)（路线表与真题三遍用法同构，赛道不同）。
