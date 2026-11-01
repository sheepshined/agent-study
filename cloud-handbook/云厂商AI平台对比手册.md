# 云厂商 AI 平台对比手册：方法论 · 八家画像 · 横向对比 · 选型决策树 · 迁移与锁定 · 中国区特辑 · 企业范例 · 动手验证

> 信息基准日：**2026-09-28**。本文定位是 **FDE 视角的云厂商 AI/Agent 平台选型答题手册**——客户问"我们该上哪家云"时，能给出有依据的对比与推荐。它不是八家产品文档的搬运，而是把当日实抓的产品/定价/合规事实，压进一套可复用的**对比方法论**与**场景化决策路径**。
>
> 所有平台能力与价格均为**当日（2026-09-28）实抓官方产品页、定价页与文档**并逐条标注来源 URL；抓不到的项显式标注"**未当日复核**"，不虚构。云厂商平台命名与计费体系换代极快（当日就核实了三起更名/合并，见 §0），任何结论都有时效——引用时请回到标注的官方页面复核。本文与 [deploy-handbook §1](../deploy-handbook/AI应用部署与运维手册.md) 的分工：那边从**部署视角**做托管平台速览（四家横评 + ADP 七步流程通用化），本册从**选型视角**做深做全（八家 × 八维度）；两册同日成稿，ADP/百炼/Bedrock 的事实口径同源互证。
>
> 术语惯例：英文术语首次出现标中文解释；"MaaS"（Model as a Service，模型即服务）、"PTU/DTU/GSU/CU/PU"等各家计费单位在 §2/§3 首次出现处逐一解释。**本文不构成法律意见**（§6 全章同此声明）。

---

## 0. TL;DR

- **八家不是同一类产品，别用一张尺子量**：美系三家（Bedrock / Microsoft Foundry / Vertex AI）是"**模型目录 + Agent 运行时**"的云平台——模型目录大（10,000+~200+ 第三方模型）、编排偏代码态、按 token 计费为主；中国五家（百炼 / ADP / 火山 / 千帆 / 华为）是"**自研模型绑定 + 低代码优先**"的国产底座——画布/对话式编排为主流、模型与平台强绑定、合规（备案/私有化/信创）是一级卖点。这决定了两套不同的选型问题（§1、§4）。
- **当日核实的三起"平台换代"印证了锁定风险不是理论**：AWS **Bedrock Agents（Classic）自 2026-07-30 起停止新客户**（官方维护模式公告，老客户可用）；微软 **Azure AI Foundry 已更名 Microsoft Foundry**（Agent API 从 Assistants 换成 Responses、资源模型换成"单一资源 + 项目"）；Google **Vertex AI 已更名 Gemini Enterprise Agent Platform**（Agent Engine → Agent Runtime、Vertex AI Search → Agent Search）。国内同期：百度千帆完成 **ModelBuilder + AppBuilder 合并**为统一"百度千帆"（Agent 为核心）。**选型必须做"换代扫描"**——与 [workflow-handbook §4](../workflow-handbook/Agent工作流编排手册.md) 对引擎做"归档/维护模式扫描"是同一条纪律。
- **价格结论（当日实抓）**：中国区 token 价显著低于美区（旗舰档：qwen3.8-max ¥12/36 vs gpt-5.6-sol $5/30 每百万 token 输入/输出；性价比档差更大）；美区成本工程靠**缓存 + 批处理 5 折 + PTU/GSU 预留**（口径承接 [tuning-handbook §6.6/§7](../tuning-handbook/Agent调优手册.md)），中国区另有**错峰/忙闲时价**（DeepSeek 系闲时半价普遍存在）、**平台积分/PU 制**（ADP：1 PU = 0.001 元；扣子积分制；华为 CU 制）三件特色杠杆。
- **MCP（Model Context Protocol，模型上下文协议）已成为八家共同的最小互操作层**：AWS AgentCore Gateway 把任意 API/Lambda 封成 MCP 工具；Microsoft Foundry 的 Toolbox 本身就是 MCP 兼容端点；Google ADK 支持"消费/暴露工具/暴露 agent"三向 MCP；国内百炼有 MCP 广场、ADP 连接器全面支持 MCP、千帆工作流有 MCP Server 节点、华为 AgentArts 支持 MCP 托管部署；扣子 MCP 仅支持远程传输（Streamable HTTP/SSE，不支持 stdio）。**互操作水位见 §5**——一年前这是愿景，当日已是事实，但"MCP 通"≠"编排通/数据通"。
- **合规是选型的第一道闸**：面向中国公众提供生成式 AI 服务需完成**生成式 AI 服务备案**（截至 2025-12-31 累计 748 款，来源见 §6）；数据出境走"三条路径 + 法定豁免 + 自贸区负面清单"；政企采购侧信创（信息技术应用创新）与国产算力（昇腾系）从"加分项"变"入场券"。五家中国云全部提供私有化/专有云交付；美系三家在中国内地均无自营可用区（Azure 中国由世纪互联运营、AWS 中国由光环新网/西云数据运营、Google Cloud 中国内地无区域——见 §6.4）。
- **场景速答**（§4 有完整决策树）：创业公司快速上线 → **百炼 / 扣子 / ADP 免费额度起步**；国企私有化合规 → **ADP 企业版 / 千帆软硬一体 / 华为云（昇腾全栈）**；中国企业出海 → **百炼国际版（新加坡等 6 地域）/ 火山方舟 + 美系一家兜底**；外企入华 → **世纪互联运营 Azure（合规栈最接近原厂体验）+ 中国区模型双轨**；已有 K8s 团队要自控 → **Bedrock AgentCore（Strands/LangGraph）或 Foundry（MAF）跑在自家集群旁，模型层 OpenAI 兼容协议解耦**。
- **§8 给了"同一个 agent 需求"在三家平台的最小实现对照**（腾讯 ADP 零代码 / 阿里百炼低代码 / AWS AgentCore 代码态），步骤级、免账号可走通（官方文档 + 免费额度口径），并标注验证边界。

### 八家一句话定位速览表（2026-09-28 官网口径）

| 平台 | 一句话定位 | 首选场景 | 当日官方入口 |
|---|---|---|---|
| **AWS Bedrock** | "生产级生成式 AI 应用与 Agent 平台"——模型目录最广 + AgentCore 托管运行时，代码态优先 | 全球业务、已有 AWS 资产、要模型自由度 | [aws.amazon.com/bedrock](https://aws.amazon.com/bedrock/) |
| **Microsoft Foundry**（原 Azure AI Foundry） | "AI 应用与智能体工厂"——11,000+ 模型 + Entra 治理栈 + M365/Copilot 生态 | 企业级治理、Microsoft 生态客户、外企入华 | [azure.microsoft.com/products/ai-foundry](https://azure.microsoft.com/en-us/products/ai-foundry) |
| **Google Vertex AI**（Gemini Enterprise Agent Platform） | Google 全托管统一 AI 开发平台——Gemini 系 + ADK 开源框架 + Agent Search | 数据/搜索强需求、TPU/多模态、已有 GCP | [cloud.google.com/vertex-ai](https://cloud.google.com/vertex-ai) |
| **阿里云百炼** | "让大模型落地，让智能体生长"——Qwen 系全模型 + Agent 1.0/2.0 + 工作流 + Managed Agents | 中文场景全能型、电商/政务、Qwen 生态 | [aliyun.com/product/bailian](https://www.aliyun.com/product/bailian) |
| **腾讯云 ADP** | "企业原生智能体底座，以 AgentOps 为核心"——四种构建模式 + Agent Harness + 企微生态 | 企业智能体规模化运营、微信/企微渠道、私有化 | [cloud.tencent.com/product/adp](https://cloud.tencent.com/product/adp) |
| **火山引擎（豆包 + 方舟 + HiAgent/扣子）** | 字节系"一云多平台"：豆包模型 + 方舟 MaaS + HiAgent 企业交付 + 扣子 SaaS 协作 | 内容/视频/推荐场景、App 生态、快速实验 | [volcengine.com/product/ark](https://www.volcengine.com/product/ark) |
| **百度智能云千帆** | "以 Agent 为核心的一站式企业级大模型服务平台"（ModelBuilder + AppBuilder 已合并） | 政务/央国企、文心生态、Text-to-SQL 知识库 | [cloud.baidu.com/product/wenxinworkshop](https://cloud.baidu.com/product/wenxinworkshop) |
| **华为云（盘古 + ModelArts + 智果 AgentArts）** | 全栈昇腾算力 + 盘古行业模型 + 智果智能体平台（公测）——信创属性最强 | 央国企/政企信创、行业大模型、国产算力硬要求 | [huaweicloud.com/product/pangu.html](https://www.huaweicloud.com/product/pangu.html) |

---

## 1. 对比方法论：八个维度与打分口径

### 1.1 为什么需要统一维度

平台间最容易被比的是"模型多不多、便宜不便宜"，但 FDE 答题时客户真正问的是八个问题：模型从哪来、agent 怎么搭、知识怎么接、工具怎么连、效果怎么测、跑在哪、怎么算钱、跑了之后还走不走得掉。八个维度与 [deploy-handbook §1.3](../deploy-handbook/AI应用部署与运维手册.md) 选型判据表的关系：那边是"硬约束一票否决"的判定表（合规/团队/成本/延迟/模型自有度），本节把每个约束展开成**可逐格填实的对比项**——判据决定问什么，维度表决定怎么比。

### 1.2 八个维度定义

| # | 维度 | 回答的问题 | 关键取证点（当日实抓什么） |
|---|---|---|---|
| D1 | **模型目录与自托管接入** | 用谁的模型？能不能自带模型？ | 目录规模与家族（自研/第三方/开源）、Custom Model Import/BYOM/专属实例、跨区域推理与数据驻留 |
| D2 | **Agent 编排形态** | 控制流在平台手里还是代码手里？（第一性区分承接 [workflow-handbook §1.1](../workflow-handbook/Agent工作流编排手册.md)） | 工作流画布有无与节点数、Multi-Agent 原生支持、代码态 SDK/框架（ADK/MAF/Strands…）、低代码↔代码的迁移通道 |
| D3 | **知识库与 RAG 管线** | 企业知识怎么进、怎么检索、怎么计费？ | 知识库实体与解析能力（OCR/表格/音视频）、检索策略（向量/关键词/混合/图谱）、接入自有向量库、检索是否单独计费（管线规范承接 [rag-handbook](../rag-handbook/RAG搭建文档.md)） |
| D4 | **工具·MCP·连接器生态** | agent 的手有多长？ | 连接器数量与深度、MCP 支持形态（消费端/暴露端/托管部署）、函数计算/沙箱、浏览器与代码解释器 |
| D5 | **评测与调优工具链** | 上线后效果谁负责？ | 内置评测（裁判模型/规则/代码）、A/B 与批量对比、红队与安全护栏、prompt/模型优化器、观测（[eval-handbook](../eval-handbook/Agent评测与质量工程手册.md) 方法论的平台化版本） |
| D6 | **部署形态·区域·合规** | 跑在哪、数据在哪、监管怎么过？ | 公有云区域数、数据驻留分层（global/data zone/regional）、私有化/专有云交付、等保与备案、政府云 |
| D7 | **计费模式** | 钱怎么算、怎么省？ | 按 token / 订阅积分制 / PU·CU·PTU·DTU·GSU 等单位制 / 预留吞吐 / 错峰价 / 免费额度规则 |
| D8 | **生态锁定与迁移成本** | 明年想走，带得走什么？ | 三层（模型/编排/数据）可迁移性、专有协议 vs 开放协议、导出能力、换代历史（§5 展开） |

### 1.3 打分口径说明

1. **符号口径**：●=该维度上有当日可验证的完整能力；◐=有能力但存在文档明示的限制（preview/区域受限/配额低等，附具体限制）；○=能力薄弱或仅有营销口径、文档支撑不足；—=无。**不使用数字打分**——云平台能力随版本月级漂移，0-10 分的"精确感"是伪精度；带限制说明的符号更诚实。
2. **取证等级**：每格结论分三级——**[实抓]**（当日打开官方页面核对原文）、**[摘要]**（经当日搜索快照确认存在与要点，未打开原文）、**[未复核]**（当日无法核实，显式标注）。§3 总表只填 [实抓] 或 [摘要]，[未复核] 项写入 §2 各家"短板与坑"或标注于格内。
3. **口径基准**：价格为**当日官方定价页/计费文档数字**，注明币种与计价单位（美区美元/百万 token，中国区多为元/百万 token 或元/千 token——本册统一换算为**每百万 token**口径，与 [tuning-handbook §6.6](../tuning-handbook/Agent调优手册.md) 同源）；平台订阅费按官网月付价。促销价/限折扣不作为基准价，但当日仍在生效的会注明。
4. **画像范围**：每家平台取"官方自营当日可购"的口径——公测中的产品（华为智果 AgentArts）明确标注公测；合作伙伴运营版（Azure 中国）在 §6.4 单独说明。开源框架（Dify 等）不在本册范围（见 [workflow-handbook §4](../workflow-handbook/Agent工作流编排手册.md)），但会作为迁移落点在 §5 引用。
5. **利益声明**：本文素材全部来自公开官方页面与公开社区信息，无厂商提供数据；各家"典型客户"均引自官网案例区，属于厂商自述口径，非独立审计结果。

---

## 2. 八家逐家画像

> 每家一节，固定五件事：**产品矩阵图 → 核心能力 → 定价要点 → 典型客户场景 → 短板与坑**。全部为当日实抓，来源链接随文标注；"未当日复核"项原样保留。

### 2.1 AWS Bedrock（含 AgentCore）

**官方定位**："The platform for building generative AI applications and agents at production scale"，页面称超过 100,000 家组织在用（[aws.amazon.com/bedrock](https://aws.amazon.com/bedrock/)，当日实抓）。

**产品矩阵图**：

| 板块 | 组件 |
|---|---|
| 模型层 | Bedrock 模型目录（官方口径 100+ FM）+ Bedrock Marketplace（第三方端点）+ Custom Model Import（自带权重）+ Model Distillation（蒸馏出专属小模型） |
| Agent 层 | **AgentCore**（Runtime/Gateway/Identity/Memory/Code Interpreter/Browser/Web Search/Policy/Observability/Evaluations/Registry/Payments）+ 托管 harness（配置文件式）+ **Managed Agents powered by OpenAI**（产品页口径）+ ~~Bedrock Agents Classic~~（**2026-07-30 起停止新客户**，官方维护模式公告） |
| 知识层 | Knowledge Bases（托管版 + 客户自管版，Agentic Retrieval 多跳检索） |
| 工作流 | Flows（节点式可视化，$0.035/千节点转换） |
| 安全 | Guardrails（六类防护，可对任意模型独立调用）+ Automated Reasoning checks |
| 成本 | Intelligent Prompt Routing（官方称至多省 30%）+ Prompt Caching + Batch（5 折） |

**核心能力（当日实抓）**：模型目录含 Amazon Nova 系、Anthropic Claude、OpenAI（GPT-6 Astra GA、GPT-5.6 三款、gpt-oss）、xAI Grok 4.6、Meta Llama 4、DeepSeek V3.2/R1、Qwen3、Kimi K3/K2.5、GLM 5 等（[文档 what-is-bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html)）；**Custom Model Import** 支持 S3 权重导入、按 CMU（Custom Model Unit）计费、闲置 5 分钟缩零（仅 3 区域可用）；AgentCore harness 可用 Bedrock/OpenAI/Gemini/任意 LiteLLM 兼容模型且**会话中途可切换 provider**，可导出为 Strands 代码（[harness 文档](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness.html)）；代码态 CLI 向导支持 Strands/LangChain·LangGraph/Google ADK/OpenAI Agents SDK；跨区域推理分 Geographic CRIS（地理边界数据驻留）与 Global CRIS（省约 10%，无驻留保证），**两者均不支持 Provisioned Throughput**。

**定价要点**（[定价页](https://aws.amazon.com/bedrock/pricing/) + [AgentCore 定价页](https://aws.amazon.com/bedrock/agentcore/pricing/)，当日实抓，美元/百万 token，美区 Standard）：Claude 3.5 Sonnet v2 $6/$30；DeepSeek V3.2 $0.62/$1.85；GLM 5 $1.00/$3.20；Kimi K2.5 $0.60/$3.00；Gemma 4 31B $0.14/$0.40。**Nova/Claude 4.x+/GPT-5.x/Grok/Llama 4 单价为页面动态加载，当日未出数字——未当日复核**。AgentCore：Runtime microVM v2 CPU $0.1276/vCPU·时 + 内存 $0.0169/GB·时（按秒计费）；Gateway 调用 $0.005/千次；Web Search $7/千查询；KB Standard 检索 $1/千次、Agentic 检索 $4/千次。官方算例：百万会话/月客服 agent ≈ $6,703/月。新客户最高 $200 credits。

**典型客户场景**（[案例页](https://aws.amazon.com/bedrock/customers/)）：Robinhood（6 个月 token 量 5 亿→50 亿/日、AI 成本降 80%）；Vercel（7,500 万+ 次 AI 代码生成）；AgentCore 案例：Cox Automotive（一年 17 个生产 agent）、Druva（68% 支持问题自动解决）、Thomson Reuters（70% 平台工程自动化）。

**短板与坑**：① 托管 Agents 换代断档——Classic 停止新客、模型目录冻结，新项目事实上必须上 AgentCore（[官方公告](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-classic-maintenance-mode.html)）；② 多智能体弱于自建框架——harness 只支持 agent-as-tool，官方原话"Routing mode multi-agent is not straightforward today"；③ Custom Model Import 仅 3 区域、默认每模型最多 3 副本、冷启动数十秒；④ 新组件区域参差——Agent Registry 仅 5 区、AgentCore Web Search 仅 3 区；⑤ 429 Throttling 是社区最高频抱怨（默认配额低、按模型按区域提额；**社区观察，未直接复核原帖**）；⑥ Anthropic 系 Provisioned Throughput 需联系账户团队报价（不透明）。

### 2.2 Microsoft Foundry（原 Azure AI Foundry）

**官方定位与重大更名**：产品已整体更名为 **Microsoft Foundry**，文档域迁至 `learn.microsoft.com/azure/foundry/`，门户旧版称 "Foundry (classic)"（[what-is-foundry](https://learn.microsoft.com/en-us/azure/foundry/what-is-foundry)，页面更新 2026-09-24）。定位："unified platform to build, ground, and govern AI apps and agents"；中文页口径"统一的可互操作 AI 平台""AI 应用和智能体工厂"（[产品页](https://azure.microsoft.com/en-us/products/ai-foundry)）。

**产品矩阵图**：

| 板块 | 组件 |
|---|---|
| 模型层 | Foundry Models（官方口径 11,000+ 模型，其中微软直销的 "sold by Azure" 类走 Azure 计量，其余走 Azure Marketplace）+ Azure OpenAI 系 |
| Agent 层 | **Foundry Agent Service**（Agents v2 = Responses API；Prompt agent 声明式 / Voice / Hosted agent 三类）+ Control Plane（agent 舰队治理：RBAC/网络/策略/限额） |
| 知识层 | **Foundry IQ**（"Azure AI Search 的演进"：知识源 + agentic retrieval，ACL/Purview 权限感知） |
| 工具层 | Foundry Tools（原 Cognitive Services：Speech/Translator/Document Intelligence…）+ Toolbox（**MCP 兼容统一端点**） |
| 低代码 | Copilot Studio（按 Copilot Credit 计费，与 Foundry 代码态互补） |
| 本地 | Foundry Local（设备端，免费离线）+ Azure Local 路径 |
| 安全 | Content Safety + AI Red Teaming Agent（基于 PyRIT） |

**核心能力（当日实抓）**：编排的框架开放度高——Hosted agent 官方点名支持 **Microsoft Agent Framework、LangGraph、OpenAI Agents SDK、Anthropic Agent SDK、GitHub Copilot SDK**；**Microsoft Agent Framework（MAF）**当日状态：13.8k star / MIT，官方文档明示其是 Semantic Kernel 与 AutoGen 的"直接接班人"（AutoGen 已挂 Maintenance Mode，[仓库](https://github.com/microsoft/autogen) README 原文）；A2A 协议 v1.0 已 GA。Foundry IQ 权限感知（以调用者 Entra 身份执行查询、Purview 标签强制）是八家中企业权限集成最深的一家。Toolbox 把 Web Search/AI Search/Code Interpreter/A2A 等打包为单一 MCP 端点，"Foundry-homed, not Foundry-bound"。数据驻留三层：Global / Data Zone（US/EU/APAC）/ Standard（指定 geography）。

**定价要点**（[Azure OpenAI 定价页](https://azure.microsoft.com/en-us/pricing/details/azure-openai/)，web_reader 当日全表渲染，美元/百万 token，Global Standard）：GPT-5.6-sol $5/$30（长上下文档 $10/$45）；GPT-5.6-terra $2/$12；GPT-5.6-luna $0.20/$1.20；GPT-5.5 $5/$30；GPT-5.3 Codex/GPT-5.2 $1.75/$14；gpt-oss-120b $0.15/$0.60；缓存输入一律 10% 价。PTU（Provisioned Throughput Unit，预留吞吐单位）预留：Global $1/PTU·时、月预留 $260/PTU·月、年预留 $2,652/PTU·年，最低 15 PTU 起。Batch 5 折。Copilot Studio：Credit 包 $200/月 = 25,000 Credits（≈$0.008/Credit）。**Grok/DeepSeek/Llama/Phi 等开放模型价页面 JS 渲染失败——未当日复核**；**GPT-6 Astra/Sol/Luna PAYG 价官方标注"prices are currently in processing for publishing"**。平台免费，新户 $200 额度/30 天；Foundry IQ 有 AI Search 免费层 + agentic retrieval 免费 token 配额。

**典型客户场景**：**Commerzbank**（[官方案例](https://www.microsoft.com/en/customers/story/25676-commerzbank-ag-azure-ai-foundry-agent-service)）"Ava"客服 agent：月 30,000+ 会话、约 75% 自主解决；技术栈 Foundry Agent Service + Azure OpenAI + Content Safety + Cosmos DB + AI Search（精读见 §7.2）。产品页案例轮播：AT&T、Audi、Bayer、Fujitsu、KPMG、Accenture 等；平台口径 80,000+ 企业、含 80% 的 Fortune 500。

**短板与坑**：① 迁移期双门户并存——hub-based 项目与 HF 全集 managed compute 仍只能用 Foundry (classic) 门户（官方 Tip 原文承认）；② 配额复杂——多数模型默认 400k TPM/1,000 RPM/300 并发、每资源仅 32 个部署、**partners/community 模型除 Anthropic 外不支持提额**（[quotas-limits](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/quotas-limits)）；③ PTU 换算按模型按版本各异（GPT-6 Astra min 15、GPT-5.6 Sol Regional min 50）、新模型 PAYG 价常滞后发布；④ 微调部署按小时收 hosting 费与使用无关、15 天不活跃删部署；⑤ 红队 Agent 仅 5 区域、不支持非 Foundry agent 与 function calling 场景（官方限制页）；⑥ 定价页动态渲染导致公开比价困难（本次抓取实证：两轮 `$-` 占位）。

### 2.3 Google Vertex AI（Gemini Enterprise Agent Platform）

**官方定位与重大更名**：2026 年 4 月 Vertex AI 更名为 **Gemini Enterprise Agent Platform**（营销上 Vertex AI 品牌仍在用），Agent Engine → **Agent Runtime**、Vertex AI Search → **Agent Search**、Agentspace → Gemini Enterprise（[官方名称对照表](https://docs.cloud.google.com/gemini-enterprise-agent-platform/vertex-ai-name-changes)当日实抓；此前 [deploy-handbook §1.4](../deploy-handbook/AI应用部署与运维手册.md) 已注"Vertex 官网直连超时未逐项复核"，本节已补齐）。产品主页："全托管式统一 AI 开发平台，Vertex AI Studio、Agent Builder 和 200+ 基础模型"（[cloud.google.com/vertex-ai](https://cloud.google.com/vertex-ai)）。

**产品矩阵图**：

| 板块 | 组件 |
|---|---|
| 模型层 | Gemini 3.x/2.5 系 + Model Garden（200+，含 Claude/Grok/DeepSeek/Qwen/GLM/Kimi/gpt-oss/Gemma 4 MaaS）+ 自托管（Model Garden 一键部署/自定义 vLLM 容器/TPU Hex-LLM） |
| Agent 层 | **ADK**（Agent Development Kit，开源，Python/Java/Go/TS）+ **Agent Runtime**（托管无服务器运行时，Sessions/Memory Bank）+ Agent Garden（可运行示例）+ Gemini Enterprise（无代码 agent builder，面向全员） |
| 知识层 | Agent Search（原 Vertex AI Search：结构化/非结构化 store + 生成式回答）+ RAG Engine（RagCorpus）+ Grounding with Google Search |
| 工具层 | ADK 三向 MCP（消费工具/暴露工具/暴露 agent）+ Apigee 100+ 企业连接器 + MCP Toolbox for Databases |
| 评测调优 | Rapid Evaluation（EvalTask/AutoSxS/LLM-as-judge）+ Prompt Optimizer + **Model Optimizer**（按 prompt 动态路由 Pro/Flash/Flash-Lite）+ Model Armor（护栏） |

**核心能力（当日实抓）**：ADK 是八家云的托管运行时里**唯一"开源框架 + 多语言 + 全托管"组合**（本地 `adk web` 调试 → Express Mode 免费跑通 → Agent Engine 托管）；Model Optimizer 的"cost/balanced/quality 三档动态路由"是当日各家独有形态；Gemini 与企业搜索的耦合（Agent Search + Grounding）是 Google 特长。**注意当日命名/缓存乱象**：models 文档页 CDN 返回两个版本（一版停在 2025-04 只列 2.0/2.5，一版导航至 2026-09-22 列 3.5-3.8 Flash）——核对以页面"Last updated"与定价页为准。

**定价要点**（[Generative AI 定价页](https://cloud.google.com/vertex-ai/generative-ai/pricing)当日实抓，美元/百万 token，≤200K 输入档）：Gemini 3.1 Pro Preview $2/$12；Gemini 3 Flash Preview $0.5/$3；Gemini 2.5 Pro $1.25/$10；2.5 Flash $0.30/$2.50；Claude（经 Vertex）Opus $5/$25、Sonnet $3/$15、Haiku $1/$5；Gemma 4 26B MaaS $0.15/$0.60。Priority 档 +80%、Flex 与 Batch 均 5 折；Context cache 存储 Pro $4.5/M token/时。Provisioned Throughput 按 GSU（General Service Unit）计：$1,200/GSU/周、$2,700/GSU/月（1 个月承诺）至 $2,000/GSU/年。Agent Runtime 计费 $0.00994/vCPU·时 + $0.0105/GiB·时 + 模型用量。Agent Search：Standard $1.50/千查询、Enterprise $4/千；Grounding with Google Search 每月 5,000 次免费、超出 $14/千（2026-01-05 起计费）。新户 $300 credits。**3.5-3.8 Flash 的价格未出现在当日抓取摘录中——未当日复核**。

**典型客户场景**：Golden State Warriors（Gemini on Vertex AI 构建 AI 篮球教练体验，BigQuery 30+ 数据源 1 亿+ 数据点，[案例页](https://cloud.google.com/customers/golden-state-warriors)当日实抓）；Swarovski、Volkswagen 车载助手（**媒体/搜索口径，未当日复核案例页**）。

**短板与坑**：① 命名高频变更与旧 URL 大量 404（当日实测 5 个官方 URL 404），文档跨 cloud.google.com 与 docs.cloud.google.com 双域；② **Preview 模型仅全局端点可用**——与数据驻留要求直接冲突（[locations 页](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/locations)当日实抓）；全局端点本身"可能在任何区域处理请求"；③ [data-residency 页](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/data-residency)全文当日抓取失败——未当日复核；④ Agent Search 配额置 0 无法硬停消耗（社区帖，2026-08，未复核原文）；⑤ 私网接入（PSC/VPC-SC）配置摩擦大（官方专设排障页）。

### 2.4 阿里云百炼（Bailian / Model Studio）

**官方定位**："让大模型落地，让智能体生长"，全链路大模型服务与应用开发平台（[产品页](https://www.aliyun.com/product/bailian)，last-modified 2026-09-27）。与 DashScope/灵积的关系：API 全链路沿用 DashScope 体系（环境变量 `DASHSCOPE_API_KEY`、端点 `dashscope.aliyuncs.com`）——百炼是 DashScope 的平台化升级品牌（当日文档实抓；"原灵积"逐字官方表述未复核）。

**产品矩阵图**：

| 板块 | 组件 |
|---|---|
| 模型层 | Qwen 全系（旗舰 qwen3.8-max）+ 第三方托管（DeepSeek-V4/Kimi/GLM/MiniMax/阶跃/小米 mimo/云知声）+ 多模态（图像/视频/3D/TTS/ASR）+ Embedding/Rerank |
| Agent 层 | **智能体应用 Agent 1.0**（提示词驱动）+ **Agent 2.0**（"知识库、MCP 等统一为工具，自主规划调用"，ReAct 1-50 轮，与 1.0 **互不兼容**）+ 工作流应用（可视化画布，含智能体群组节点，支持一键导入 Dify 工作流）+ 高代码应用 + **Managed Agents**（托管运行时：服务端会话状态、沙箱、中断续接、SSE 事件流） |
| 知识层 | 知识库 RAG（四种类型：文档搜索/数据查询 NL2SQL/图片问答/音视频搜索；向量存储可换 ADB-PG 自购） |
| 工具层 | 插件（官方/三方/自定义）+ **MCP 广场**（官方 MCP + 自定义 MCP 部署 + MCP 市场，插件可一键转 MCP）+ 函数计算节点 + AppFlow 数据连接器 |
| 评测调优 | 模型调优（CPT/SFT/DPO/RL）+ 模型评测（裁判模型/规则/人工 + 13 个公开基线）+ Prompt 板块 |
| 代码态 | DashScope SDK + Spring AI Alibaba（Java 系 agentic 框架，DAG Graph 内核，[java2ai.com](https://java2ai.com)）+ 百炼 CLI |

**核心能力（当日实抓）**：Agent 2.0 把"插件/MCP/技能/数据连接器"统一为工具并展示"规划-执行-反思"全链路（思考卡片），内置沙箱工具 bash/read/edit/grep；模型"智能模式"（AUTO/性能/均衡/经济四档动态路由）。**Assistant API 处于"下线中"状态**（用户指南目录原文）——存量集成注意。工作流节点四类覆盖基础/AI/工具/数据处理，API 节点不支持流式输出、发布后超时固定 600 秒。

**定价要点**（[模型价格表](https://help.aliyun.com/zh/model-studio/model-pricing)，华北2 北京，元/百万 token，当日实抓）：qwen3.8-max ¥12/¥36；qwen3.7-plus ¥2/¥8（非思考，限时 8 折）；qwen3.8-flash ¥0.8/¥2.7；deepseek-v4-pro ¥12/¥24；deepseek-v4.1-flash 忙 ¥2/闲 ¥1（**忙闲分时**）；glm-5.3 ¥8/¥28；kimi-k3 ¥20/¥100。Batch 一律 5 折；显式缓存创建 125%、命中 10%。**新用户免费额度**：每模型各 100 万 token（通常）、90 天、**仅北京地域**、不覆盖 Batch/调优/部署；未认证用户额度用完即停（403）、已认证自动转按量。PTU（预置吞吐预留）与 DTU（模型单元独占，PD 分离）两种专属部署；知识库 RAG **按规格时长独立计费**且不支持资源包——POC 前先算这笔。

**典型客户场景**：零跑汽车（C10 座舱语音大模型，百炼 + AnalyticDB 向量引擎）；语忆科技（电商客服提效超 40%）；哈啰（交易机器人升级；"GMV +5%"数字出自搜索摘要，未当日复核原文）——均见产品页案例区。

**短板与坑**：① 限流按主账号合并且**充值不提额**（默认阈值要商务提额）；快照版模型限流极低（qwen-long 3 RPM）；② 地域割裂——DeepSeek 系/基线评测/调优/自定义模型导入/免费额度全"仅北京"；③ Agent 1.0 与 2.0 互不兼容，旧应用只能重建；Agent 2.0 长期记忆"计划在未来的迭代中支持"；④ 自定义插件超时仅 5 秒（Agent 1.0 文档原文）；⑤ 模型/功能下线频繁（PAI-LangStudio 已下线迁入百炼、Assistant API 下线中）——与千帆同款"换代扫描"纪律适用。

### 2.5 腾讯云智能体开发平台（Tencent Cloud ADP）

**官方定位**："企业原生智能体底座，以 AgentOps 为核心，锻造契合业务的企业级智能体"，产品骨架"构建·分发·治理"（[产品页](https://cloud.tencent.com/product/adp)当日实抓）。一手底稿：[fde-handbook ADP 2.1](../fde-handbook/tencent-adp-fde-course/lessons/2.1_ADP_是什么：企业级智能体开发平台.md)（能力地图=构建模式×核心能力组件×AI Model）与 [ADP 2.3](../fde-handbook/tencent-adp-fde-course/lessons/2.3_从开发到上线：ADP_应用的完整使用流程.md)（七步流程，[deploy-handbook §1.4](../deploy-handbook/AI应用部署与运维手册.md) 已通用化）。当日新事实：体验入口域名为 lke.cloud.tencent.com、产品文档 ID 1759 与原大模型知识引擎 LKE 相同——**ADP 与 LKE 为同一产品线演进的间接证据**（非官方声明）。

**产品矩阵图**：

| 板块 | 组件 |
|---|---|
| 模型层 | 混元全系（hunyuan-turbo/T1/turbos/HY 2.0 Think·Instruct）+ 自研 youtu 系（mrc 企业知识问答精调/intent/rewrite）+ DeepSeek 系（R1/V3.2）+ **Claw 模式底座默认 Kimi K2.5**（可自主切换）+ 企业版自定义模型接入 |
| Agent 层 | **四种构建模式**：Claw（推荐，自然语言驱动 + 独立云端工作空间 + 最多 80 个 Skills，**创建后不可切换模式**）/ 标准模式（思考+生成双模型协同，严肃问答）/ 单工作流（画布编排）/ Multi-Agent（Plan-and-Execute 或工作流协同）+ **Agent Harness** 云托管运行时（断点自动续跑、闲置自动暂停、全链路 Trace、密钥隔离托管）+ 智能工作台 |
| 知识层 | 知识库（pdf/docx 等 ≤200MB、表格 ≤1 万行；网页爬取/腾讯文档/COS/API 导入）+ **Agentic RAG**（极速/规划/规划+反思三阶检索）+ **Text-to-SQL 数据库知识库**（MySQL/SQLServer/PG/Oracle，每账号 100 库×1000 表） |
| 工具层 | 200+ 连接器与工具（产品概述口径）、全面支持 MCP（SSE/streamableHttp，OAuth 2.0 鉴权）+ 工具四种接入（API/MCP/代码/应用）+ Skills 体系 |
| 评测运营 | 应用评测（裁判模型/规则/代码打分；基准+对比评测）+ 运营分析（对话记录/不满意问题/热点）+ 模型对比调试 |

**核心能力（当日实抓）**：ADP 是国内"**零代码起步但有完整逃生通道**"的代表——标准模式表单配置即可上线，工具可下钻到 MCP/代码级；Agent Harness 把 durable execution 做成平台能力（与 [workflow-handbook §4 Temporal](../workflow-handbook/Agent工作流编排手册.md) 对照）；渠道接入（企微/钉钉/飞书/微信全系）是渠道侧最强项；多租户数据强隔离 + 平台/空间/应用/知识库多级权限（集团型企业适配）。评测侧四个亮点：裁判模型可换、规则+代码打分、对比评测（但仅限标准模式且最多 2 组）。

**定价要点**（[计费概述](https://cloud.tencent.com/document/product/1759/127342) + [套餐版本](https://cloud.tencent.com/document/product/1759/129200)，当日实抓）：**套餐订阅制 + PU 资源（1 PU = 0.001 元）**，不支持后付费。免费版 0 元（15,000 PU/月 + 1GB 知识库，**每账号限领一次、1 个月**）；Skill Plan 版 ¥88/月（89,000 PU，原 ClawPro）；专业版 ¥188/月（100GB 知识库，3 空间）；企业版 ¥4,880/月（3,000,000 PU/月 + 2TB 知识库 + 1,000 空间 + 自定义模型 + 私有化）。**当日口径冲突**：专业版 PU 额度产品页写 89,000、计费文档写 150,000——疑产品页未随 Skill Plan 拆分同步更新，引用需注明双源。PU 抵扣模型调用/工具/知识库超量存储（1.5 PU/GB·时）/Claw 运行时长；PU 资源包 1 万 PU=10 元起。旧按量计费标注"即将下线"，老用户套餐包与后付费暂停需工单退款。

**典型客户场景**（产品页/独立站当日实抓）：迈瑞医疗（500+ 产品资料、5000+ 临床知识，关键问题准确率 95%，覆盖 190+ 国家）；华润信托（智能债券助手，80% 咨询由 agent 回答）；碧桂园服务（"一问"AI 客服嵌入 30+ 业务系统，试点工单量降 25%+）；一汽丰田（独立解决率 37%→84%）；华住（38 条工作流）。精读见 §7.3。

**短板与坑**：① 评测盲区——Plan-and-Execute 协同的 Multi-Agent 应用"无法进行完整的应用评测"（文档原文）；② Claw 模式不可逆（创建后不能切回）；③ **Text-to-SQL 数据源 Host 必须公网可达**（文档原文）——内网数据库是硬约束；④ 模型上下架频繁（2026-08/09 连续公告 GLM/Qwen/DeepSeek 旧版下线），应用需预留模型切换成本；⑤ 网页爬取不支持登录授权与 JS 异步渲染站点；⑥ 知识库超量 7 天失效、180 天自动删除；⑦ 免费版限领一次——验证完就没法再来一遍，POC 规划要一次做对。

### 2.6 火山引擎（豆包大模型 + 火山方舟 + HiAgent/扣子）

**官方定位与结构**：火山引擎是"一云多平台"分层结构——①**豆包 Doubao**（模型品牌，ToC App 与 ToB API 同名）；②**火山方舟 Ark**（MaaS：模型训练/推理/评测/精调，[product/ark](https://www.volcengine.com/product/ark) 当日实抓）；③应用层两条线：**HiAgent**（"一站式数字员工派遣站……统一的 Harness 运行时底座"，官网 SEO 原文经搜索当日索引）与**扣子 Coze**（"面向 Agent 时代的新一代 AI 团队协作平台"，[docs.coze.cn](https://docs.coze.cn) 当日实抓，个人/团队/企业三档 SaaS）；④开发者套件 AgentKit CLI + VeADK + 开源 Eino（Go）。

**产品矩阵图**：

| 板块 | 组件 |
|---|---|
| 模型层 | Doubao Seed 2.0 系（pro/lite/mini/code，256k 上下文）+ Seed 1.x 往期 + 视频生成 Seedance 2.0 + 图像 Seedream 5.0 + 3D + 多模态向量 + 第三方托管（DeepSeek-V4/GLM-4.7 等） |
| Agent 层 | 扣子（工作流/对话流画布 + 多 Agent 协作 + AI 生成式工作流）+ HiAgent（企业交付，开发-运行-消费-治理全流程）+ 方舟 AgentKit CLI/云端 Agent Runtime + veFaaS 高代码应用 |
| 知识层 | 扣子知识库（文本/表格/图片）+ **火山知识库**（官方口径：单库 300 万文档、1 万 QPS、单文档 10 万切片）+ 方舟 RAG 知识库/向量库（**免费公测中**）+ VikingDB |
| 工具层 | 扣子插件（每工作空间 1000 插件 × 100 工具上限）+ MCP 客户端（**仅 Streamable HTTP/SSE，不支持 stdio**）+ 方舟 Responses API 模型级 MCP/函数调用/联网插件 + "一键部署 OpenClaw" |
| 评测调优 | 方舟评测 + **扣子罗盘 CozeLoop**（提示词智能优化 + Trace 日志计费项）+ 内容安全护栏 |

**核心能力（当日实抓）**：多模态生成（视频/图像/3D）是八家中产品化最深的；扣子的"人和 Agent 像团队一样协作"（多人多 Agent 协作 + 接入本地 Claude Code/Codex CLI/OpenClaw 统一托管调度）是独有方向；方舟侧对 AI coding 工具的适配（Token Plan 兼容 OpenClaw/Claude Code 等）最积极。

**定价要点**：方舟按 token 后付费 + 包天预付费 + 小时后付费（[模型服务计费](https://www.volcengine.com/docs/82379/1099320)当日实抓）：doubao-1.5-pro-32k ¥0.8/¥2.0 每百万；doubao-1.5-lite ¥0.3/¥0.6；deepseek-r1 ¥4/¥16。旗舰 Doubao-Seed 系价格：**Doubao-Seed-Evolving/2.1-pro 输入 6 元、输出 30 元**（官网页价格片段经搜索当日索引，价格表正文未直抓——[模型价格文档](https://www.volcengine.com/docs/82379/1544106)未当日复核）；Seed-2.0-pro 第三方多源口径 3.2/16 元（**非官方直抓，仅供参考**）。**Agent Plan 订阅**（40/200/500/1000 元/月四档，媒体报道未官网目验）与"协作奖励计划"（免费每日领单模型最高 500 万 token，产品页实抓）。扣子**积分制**：个人免费版（每日登录赠活动积分）、进阶 39.9 元/月、旗舰 199、尊享 999；企业标准 980 元起（5 席位）、企业旗舰 8980 元起（30 席位，含 SSO/VPC 私网/KMS）；超配额 1000 积分:1 元扣现金。**HiAgent 无公开定价页——未当日复核**（搜索命中的"定价文章"为官网内容社区 SEO 软文，不采纳）。

**典型客户场景**（[product/ark](https://www.volcengine.com/product/ark) 案例入口当日实抓）：浙江大学"浙大先生"（7 天构建校园大模型应用体系）；招商银行（智能体应用共探）；南开大学、华泰证券。案例详情页为 JS 渲染未逐一打开。

**短板与坑**：① 官网产品页/定价页全 JS 渲染，公开抓取几乎不可用（本次实测：豆包产品页、HiAgent 产品页、扣子价格 UI 均只返回骨架）——信息透明度差，比价成本高；② 文档滞后——Seed 2.1-pro（2026-09-16 全量）未进入"模型列表"文档推荐区（文档停在 2026-05-29）；③ 计费体系频繁变动（扣子资源点→积分制、个人版月费 9.9→39.9）；④ 扣子 MCP 不支持 stdio——本地工具要过网关；⑤ 免费版能力收紧（不支持自定义模型/云端 Agent 创建）；⑥ HiAgent 与扣子定位重叠，双产品线并行选型需区分；⑦ 方舟限流为"非刚性保障"，QPS 保障需另购。

### 2.7 百度智能云千帆

**官方定位与重大合并**："以 Agent 为核心的一站式企业级大模型服务平台"；官方平台简介原文确认"**原 ModelBuilder 与 AppBuilder 现已合并升级为全新的百度千帆平台**"（[平台简介](https://cloud.baidu.com/doc/qianfan/s/rmh8khvwu)）。**注意市场页与文档口径并存**：市场侧仍并列展示 ModelBuilder/AppBuilder/DataBuilder 三子品牌，文档侧已合并为统一目录（`/doc/qianfan`）——**引用旧双平台口径会失真**。

**产品矩阵图**：

| 板块 | 组件 |
|---|---|
| 模型层 | 文心 ERNIE 5.1（128k，旗舰）/5.0（全模态）/4.5-Turbo 系 + 第三方托管（DeepSeek-V4 全系 1M 上下文/Qwen3.5/GLM-5.3/Kimi-K2.6）+ OCR 系（PaddleOCR-VL 等）+ Embedding/Rerank |
| Agent 层 | 四种 Agent：自主规划（对话式创建）/ **工作流 Agent（23 种节点，MCP Server 节点内置）** / 多智能体协同（**"全面兼容 A2A 协议"**，产品页口径）/ 交互式写作 + 组件工作流（自定义工具封装）+ 官方预置 Agent（网页探索/代码编写/报告撰写） |
| 知识层 | 知识库（本地上传/BOS/网页自动更新）+ 混合/全文/语义三种检索 + **知识图谱 GraphRAG**（enable_graph 开关，要求问答模型 ≥32k 上下文）+ 向量库可换百度 ES(BES)/VectorDB |
| 工具层 | 工具及 MCP 广场（百度搜索/百度百科/百度地图/网盘/文库 PPT 等独家组件，多提供 Skill 与 MCP 双形态）+ 第三方 MCP（同程/支付宝）+ 组件免费额度（搜索类 100 次/天） |
| 评测调优 | 模型评估（自动/人工/性能）+ SFT 精调 + 蒸馏（含 DeepSeek-R1 蒸馏样板）+ **主动 Cache（官方称至多降 80% 推理成本）** |
| 代码态 | AppBuilder-SDK（Python/Java/Go，40+ 组件，[github.com/baidubce/app-builder](https://github.com/baidubce/app-builder)）+ bce-qianfan-sdk + **OpenAI 兼容 base_url=qianfan.baidubce.com/v2**（API Key 永久有效） |

**定价要点**（[计费文档](https://cloud.baidu.com/doc/qianfan/s/wmh4sv6ya)，页面更新 2026-09-24，元/千 token→本册统一为**元/百万 token**：×1000）：ERNIE-5.1 ≤32k 输入 ¥4/输出 ¥18；ERNIE-4.5-Turbo ¥0.8/¥3.2（**缓存命中 ¥0.2，为输入价 1/4**）；DeepSeek-V4.1-Flash 忙时 ¥2/¥8、**闲时 ¥1/¥4**；GLM-5.3 ¥8/¥28。按量包：ERNIE-4.5-Turbo 10 亿 token 包 ¥1,120（8 折）。专属实例"算力单元"预付费 Ⅰ型 ¥15,000/月/单元（5 折活动 ¥7,500）。**新用户免费额度：17 个模型 × 100 万 token、3 个月**（2025-10-24 起注册自动发放，[额度文档](https://cloud.baidu.com/doc/qianfan/s/Imi2rpirg)）；实名认证送 20 元代金券。Token Plan 个人版积分制（Mini ¥4.9/月起，限时 5 折）；**Coding Plan 已停售**（公告标题当日实抓）。

**典型客户场景**：政务"居民助理"（本地政务知识库 RAG，20 万户+ 居民触达）；中华全国总工会（"1+4+N" AI 应用支撑体系，1 个月交付）；上海市医保智能助手（官方页搜索命中，正文未逐页复核）。规模口径："为 40 万客户提供服务"（[开发者中心](https://qianfan.cloud.baidu.com/)当日实抓；注意招行/中石化/长安汽车是**百舸算力平台**客户口径，不能记为千帆平台客户）。

**短板与坑**：① 文档体系割裂（`/doc/qianfan`、`/doc/qianfan-api`、旧 `/doc/WENXINWORKSHOP` 四套并存、版本不一）；② **接口 V1→V2 大迁移**（V1 下线公告在列，旧教程大量失效）；③ 模型下线频繁（当日列表即标注 deepseek-v4-flash/v3.2、ernie-x1.1、glm-5、kimi-k2.6"即将下线"）；④ 组件生态流动性大（官方工具下架/教育类下架/热榜类下架公告并列）；⑤ 知识库计费收紧中（共享资源检索计费公告 + 高级解析计费公告标题在列）；⑥ SFT 按 token 后付费服务**每账户只能发布一个**；⑦ 图谱检索要求问答模型上下文 ≥32k；⑧ 公有云区域列表无公开静态文档——未当日复核，需控制台确认。

### 2.8 华为云（盘古 + ModelArts + 智果 AgentArts）

**官方定位与结构**：行业大模型 **盘古 PanguLM**（5 个基础大模型：LLM/多模态/视觉/预测/气象）+ AI 开发平台 **ModelArts** + 大模型即服务 **MaaS（ModelArts Studio）** + 智能体平台 **智果 AgentArts**（2026-04 上线公测，"人人都能构建自己的企业级智能体"）+ 数据治理 DataArts。算力底座为全栈昇腾（当日官网无独立"昇腾 AI 云服务"产品页，ei.html/ascend.html 实测 404——昇腾叙事已并入 ModelArts/MaaS）。

**产品矩阵图**：

| 板块 | 组件 |
|---|---|
| 模型层 | 盘古 N1/N2/**N4（718B MoE 深度思考）** + 开源 openPangu-2.0-Flash（92B/激活 6B）/Pro（505B MoE/512k 上下文，"基于昇腾 NPU 训练"）+ MaaS 托管 DeepSeek-V4.1-Flash/V4-Pro、GLM-5.3、Kimi-K2.6、Qwen 系 |
| Agent 层 | 智果 AgentArts：低代码（单智能体/工作流/多智能体三类应用，20 种工作流节点，6 种搭建范式，**支持导入 Dify 工作流**）+ 高代码 Runtime SDK（框架无关，LangChain/LangGraph/AgentScope 探针接入）+ Managed/运行时托管双形态 + "智果园"开放平台 + 桌面智能体"果办 OfficeAce" |
| 知识层 | 平台知识库（pangu_embedding/pangu_rerank，语义/关键词/混合/FAQ 检索）+ 第三方知识库（RAGFlow/KooSearch/General 通用接入） |
| 工具层 | 预置 MCP（高德/必应）+ **MCP Server 托管部署**（镜像→运行时→Target）+ Agent 网关（IAM/OAuth 2.0/API Key）+ 插件 + **Skill 体系（含 Skill 完整度/相关性/威胁分析评估器——八家独有）** + 沙箱 |
| 评测调优 | 预置 50+ 评估器（幻觉/工具参数正确性/轨迹质量…）+ 评测集支持 **Trace 回流** + **GRPO 强化学习微调与应用自演进优化**（付费版） |
| 观测 | Trace/Metric/Log → APM/AOM/LTS，支持 OpenTelemetry |

**核心能力（当日实抓）**：**信创属性是根本差异**——openPangu 开源 + 全栈昇腾训练/推理 + 华为云 Stack 私有化（盘古 for Stack 8.5.1 指南存在）；AgentArts 的"Skill 威胁分析评估器"与"Trace 回流做评测集"是安全与评测方法论的深度产品化（分别对应 [security-handbook](../security-handbook/AI应用安全手册.md) 供应链面与 [eval-handbook](../eval-handbook/Agent评测与质量工程手册.md) 灰度回放）。**重大变化**：MaaS 于 2026-08-18 下线"按算力资源规格计费的模型开发能力"（模型部署/调优），官方口径"聚焦 Serverless 化"，迁移路径为 ModelArts（西南-贵阳一）且**不支持平滑迁移**（[FAQ](https://support.huaweicloud.com/maas_faq/maas_faq_0015.md)）。

**定价要点**（[MaaS 价格文档](https://support.huaweicloud.com/price-maas/price-maas-0002.md)，元/百万 token，当日实抓）：openPangu-2.0-Pro 3.2（缓存命中 0.8）/14.5；openPangu-2.0-Flash 0.8/1.6；DeepSeek-V4.1-Flash 忙 2/8、闲 1/4；DeepSeek-V4-Pro 12/24；GLM-5.3 8/28；Kimi-K2.6 6.5/27。**官方注意事项原文："DeepSeek-V4 系列模型价格近期将上调"**。Token Plan 个人版 Lite ¥59/月=5000 万 token…Max ¥799/月=8.8 亿（仅 3 模型可选、月限购、不结转）。**AgentArts 体验版免费**（20CU、2 成员、1GB 知识库、50 应用）+ **开通即赠 2,000,000 token**（限模型调测/智能体试运行）；团队标准版 80CU~企业旗舰版 10880CU 四档付费版当日**"未开放，需提交工单购买"**；CU（Agent 计算单元）超出部分按需/包年。

**典型客户场景**（AgentArts/盘古产品页当日实抓）：温氏食品（育种 4 个智能体，基因组分析效率 +50%）；太平洋保险（"智能保顾"数字员工，满意度 80.5%）；慧通差旅（代码量降 90%）；盘古页：福田区政数局、美图、山东能源。

**短板与坑**：① **区域单一**——MaaS 预置服务/多项 API 仅"西南-贵阳一"（cn-southwest-2），AgentArts 同区，多区域生产需评估；② AgentArts 商用未开闸（公测申请制约 5 个工作日审核、付费版需工单、体验版配额低：单智能体仅挂 1 个知识库、单文件 20MB、1GB 存储）；③ 内容护栏默认开启引入额外时延，关闭需客户等级 V2+；④ 版本口径混乱（官网不标盘古 6.x；媒体口径 5.5/6.0/718B/openPangu-2.0 并存；盘古原生模型无公开 token 价目表——未当日复核）；⑤ 算法备案资质需客户自行申请（官方 FAQ）；⑥ Token Plan 限制多（3 模型、不可退订、不结转）。

## 3. 横向对比总表（2026-09-28 逐格填实）

> 口径：符号 ● 完整能力 / ◐ 有能力但有文档明示限制 / ○ 薄弱或仅营销口径 / — 无。每格为当日实抓结论，关键格带来源；表后列"独有与缺失"差异点清单。八列过宽，按 §1.2 的维度拆成三张子表。

### 3.1 模型与编排（D1 + D2）

| 维度 | AWS Bedrock | MS Foundry | Google Vertex | 阿里百炼 | 腾讯 ADP | 火山引擎 | 百度千帆 | 华为云 |
|---|---|---|---|---|---|---|---|---|
| **D1a 模型目录** | 官方口径 100+ FM，跨 20+ 供应商（含 OpenAI/Grok/Kimi/GLM/MiniMax 等中国系模型）[实抓] | **11,000+**（含 Marketplace 伙伴模型）[实抓] | 200+（Model Garden）[实抓] | "百余款"（主页口径）[实抓] | "十余种"（混元+DeepSeek+youtu 系）[实抓] | Doubao 全系 + DeepSeek/GLM 少量托管 [实抓] | "150+ 精选 SOTA"[实抓] | 盘古系 + MaaS 托管 DeepSeek/GLM/Kimi/Qwen [实抓] |
| **D1b 第三方旗舰当日在架** | Claude 3.5 Sonnet v2 / GPT-6 Astra(GA) / Grok 4.6 / DeepSeek V3.2 | GPT-5.6 三款 / Claude Opus 4.5（经 Marketplace）| Gemini 3.1 Pro / Claude Opus 4.7 / DeepSeek V3.2 / GLM-5 | qwen3.8-max / deepseek-v4-pro / kimi-k3 / glm-5.3 | hunyuan-T1 / HY 2.0 Think / DeepSeek-V3.2 / Kimi K2.5（Claw 底座） | doubao-seed-2-0-pro / deepseek-v4-pro | ernie-5.1 / deepseek-v4.1-flash / qwen3.5 / glm-5.3 | DeepSeek-V4.1-Flash / GLM-5.3 / Kimi-K2.6 / openPangu-2.0 |
| **D1c 自带模型（BYOM）** | ● Custom Model Import（S3 权重，按 CMU，仅 3 区域）[实抓] | ● Managed compute 自定义权重（preview；HF 全集需 classic 门户）[实抓] | ● 自定义 vLLM 容器 / TPU Hex-LLM / Model Garden 一键部署 [摘要] | ◐ 仅支持导入千问系开源模型（仅北京）；自有模型走 PAI [实抓] | ◐ 企业版"自定义模型接入"，步骤文档当日未抓到 [未复核] | ◐ 精调/蒸馏/MLP 推理服务（专属实例细节未复核） | ◐ HF 导入做精调/蒸馏（细节页未逐页复核） | ◐ ModelArts 训练部署自家权重（昇腾适配）；MaaS 侧 2026-08 已收缩 [实抓] |
| **D1d 专属/预留吞吐** | ◐ Provisioned Throughput（Anthropic 系需商务报价）；**CRIS 与 PT 互斥** [实抓] | ● PTU 预留（$260/PTU·月起，min 15）[实抓] | ● GSU（$1,200/周~$2,000/年档）[实抓] | ● PTU + DTU（PD 分离）[实抓] | ◐ 专属并发包不耗 PU（DeepSeek-V3.2 1 并发 ¥9,600/月）[实抓] | ◐ 包天/小时预付费 TPM + QPS 保障另购 [实抓] | ● 算力单元预付费/后付费 [实抓] | ◐ 算力资源口径（单价表未复核）[摘要] |
| **D2a 工作流画布** | ◐ Flows（$0.035/千节点转换）[实抓] | ◐ 无 Foundry 侧画布证据；低代码由 Copilot Studio 承担 [实抓] | ◐ 无画布；Agent Garden + Gemini Enterprise 无代码 builder [实抓] | ● 工作流应用（基础/AI/工具/数据处理四类节点，支持导入 Dify）[实抓] | ● 单工作流模式（画布编排，发布≠生效走版本说明）[实抓] | ● 扣子工作流/对话流 + AI 生成式工作流 [实抓] | ● 工作流 Agent（**23 种节点**，MCP Server 节点内置）[实抓] | ● AgentArts 工作流（20 种节点，6 种范式，**支持导入 Dify**）[实抓] |
| **D2b Multi-Agent** | ◐ harness 仅 agent-as-tool；官方自认 routing 不成熟 [实抓] | ● Hosted agent 承载 MAF graph workflows/LangGraph；A2A v1.0 GA [实抓] | ● ADK 原生 sub-agents；A2A 50+ 伙伴（官方口径）[实抓] | ◐ 工作流"智能体群组节点"；独立多智能体靠 Spring AI Alibaba [实抓] | ● Multi-Agent 模式（Plan-and-Execute / 工作流协同）[实抓] | ● 扣子"多人多 Agent 协作"；HiAgent 数字员工治理 [实抓] | ● 多智能体协同 Agent + **兼容 A2A**（产品页口径）[实抓] | ● 多 Agent 控制器+子智能体调度 [实抓] |
| **D2c 代码态路线** | ● AgentCore CLI（Strands/LangGraph/ADK/OpenAI SDK）+ 托管 harness 可导出 Strands 代码 [实抓] | ● MAF（13.8k star，MIT）+ 四语言 SDK + Hosted agent 容器 [实抓] | ● **ADK 开源**（Python/Java/Go/TS）[实抓] | ● DashScope SDK + Spring AI Alibaba（Java）+ CLI [实抓] | ◐ 工具可写 Python 代码；整体偏低代码（OpenAPI 100+ 接口）[实抓] | ● AgentKit CLI/VeADK/Eino（Go）[实抓] | ● AppBuilder-SDK + qianfan-sdk + OpenAI 兼容 v2 [实抓] | ● Runtime SDK（框架无关，LangChain/LangGraph/AgentScope 探针）[实抓] |
| **D2d 低代码↔代码迁移通道** | ● harness ↔ Strands 代码互导 [实抓] | ◐ Prompt agent ↔ SDK 双路（无导出声明）[实抓] | ● ADK 本地→Express→Agent Runtime 全程同框架 [实抓] | ◐ Agent/工作流↔SDK 调用（DSL 可导入导出，支持 Dify）[实抓] | ◐ 应用→OpenAPI/SDK 调用；模式配置不可导出 [实抓] | ● 扣子↔AgentKit/veFaaS 多入口（同属字节系）[实抓] | ◐ 应用↔AppBuilderClient（SDK 调云端已发布应用）[实抓] | ● 低代码/高代码/自然语言融合开发（官方口径）[实抓] |

### 3.2 知识、工具与评测（D3 + D4 + D5）

| 维度 | AWS Bedrock | MS Foundry | Google Vertex | 阿里百炼 | 腾讯 ADP | 火山引擎 | 百度千帆 | 华为云 |
|---|---|---|---|---|---|---|---|---|
| **D3a 知识库实体与解析** | ● Managed KB（托管解析/embedding/rerank 不另收费；Smart Parsing 含音视频/扫描件）[实抓] | ● Foundry IQ（Blob/SharePoint/OneLake/网页；agentic retrieval；GA/preview 混合）[实抓] | ● Agent Search + RAG Engine（RagCorpus）[实抓] | ● 四种知识库（文档/数据查询 NL2SQL/图片/音视频；五种解析含 Qwen-VL）[实抓] | ● 知识库（10+ 类型 ≤200MB；OCR 积累深）[实抓] | ● 扣子知识库 + 火山知识库（单库 300 万文档/1 万 QPS 官方口径）[实抓] | ● 知识库（混合/全文/语义检索 + **GraphRAG**）[实抓] | ◐ 平台知识库 + 第三方接入（RAGFlow/KooSearch）[实抓] |
| **D3b 检索与权限** | ◐ Agentic Retrieval（多跳/跨库迭代）；文档级 ACL（Web Crawler 除外）[实抓] | ● **调用者 Entra 身份查询 + Purview 标签强制**（权限感知最深）[实抓] | ● Agent Search + Grounding（Google Search 5k 免费/月）；权限页未抓全文 [实抓/未复核] | ◐ 智能调用/必定调用两种方式；权限模型未见文档明示 [实抓] | ◐ 三阶 Agentic RAG + 召回测试；元数据/时效性检索 [实抓] | ◐ 全文/向量/NL2SQL/图片标注检索 [实抓] | ● 混合检索+重排+GraphRAG（模型上下文 ≥32k 前置条件）[实抓] | ◐ 语义/关键词/混合/FAQ + 命中测试 [实抓] |
| **D3c 接入自有向量库** | ● Customer-managed KB（OpenSearch/Aurora/Neptune 等自选）[实抓] | ◐ AI Search 为主（BYO 资源支持存储/Cosmos）[实抓] | ◐ Feature Store 作向量库；Vertex 向量库生态 [摘要] | ● ADB-PG 自购引擎 [实抓] | — 平台存储为主（未见外接选项）[实抓] | ● VikingDB [实抓] | ● 百度 ES(BES)/VectorDB 三选 [实抓] | ● RAGFlow/KooSearch/General 第三方接入 [实抓] |
| **D4a MCP 支持** | ● Gateway 把 API/Lambda/外部 MCP 统一封装为 MCP 工具 + 语义工具发现 [实抓] | ● Toolbox 本身是 MCP 兼容端点（"Foundry-homed, not Foundry-bound"）[实抓] | ● ADK 三向 MCP（消费/暴露工具/暴露 agent）[实抓] | ● MCP 广场 + 云部署自定义 MCP（插件一键转 MCP）[实抓] | ● 连接器/工具全面支持 MCP（SSE/streamableHttp + OAuth）[实抓] | ◐ 扣子 MCP **仅远程传输（Streamable HTTP/SSE）**；方舟 Responses API 模型级 MCP [实抓] | ● 工作流 MCP Server 节点 + 独家组件双形态（Skill/MCP）[实抓] | ● 预置 MCP + **MCP Server 托管部署** + Agent 网关 [实抓] |
| **D4b 企业连接器** | ◐ KB 数据源 7+ 原生（S3/SharePoint/Confluence/Drive/OneDrive/Box/ServiceNow）[实抓] | ● **1,400+ 预置业务连接**（SAP/Salesforce/Dynamics）+ Logic Apps/Power Platform [实抓] | ● Apigee 100+ 连接器 [实抓] | ◐ 数据连接器 + AppFlow（数量未公布）[实抓] | ● **200+ 连接器**（企微/腾讯生态深）[实抓] | ◐ 扣子插件商店（官方文档无总数口径）[实抓] | ◐ 独家组件（百度搜索/百科/地图等）流动性大 [实抓] | ◐ 预置插件+网关（数量未公布）[实抓] |
| **D4c 沙箱/代码执行/浏览器** | ● Code Interpreter + 托管 Browser + Web Search [实抓] | ● Code Interpreter（Toolbox）+ Computer use（直接集成）[实抓] | ◐ ADK 工具生态（Browser/CI 经组件）[摘要] | ● Agent 2.0 内置 bash/read/edit/grep 沙箱 [实抓] | ◐ Claw 模式独立云端工作空间（编码/长时任务）[实抓] | ◐ 扣子 IDE/代码节点；AgentKit 沙箱模板 [实抓] | ● 函数计算 CFC 节点 [实抓] | ● 沙箱代码/命令执行环境 [实抓] |
| **D5a 内置评测** | ● Bedrock Evaluations（自动/人类/judge/RAG）+ AgentCore Evaluations [实抓] | ● 内置评估器（coherence/relevance/groundedness/safety）+ Agent optimizer [实抓] | ● Rapid Evaluation（EvalTask/AutoSxS/judge）[实抓] | ● 模型评测（裁判/规则/人工 + 13 公开基线）+ 应用评测 [实抓] | ● 应用评测（裁判/规则/代码打分；对比评测限标准模式 2 组）[实抓] | ◐ 方舟评测 + 扣子罗盘（提示词优化/Trace 计费项）[实抓] | ◐ 模型评估（自动/人工/性能）三小节 [实抓] | ● **50+ 预置评估器**（幻觉/工具正确性/轨迹）+ Trace 回流评测集 [实抓] |
| **D5b 红队与护栏** | ● Guardrails（六类防护，可对任意模型独立调用）+ Automated Reasoning [实抓] | ● Content Safety + **AI Red Teaming Agent（PyRIT，ASR 记分卡）**[实抓] | ● Model Armor + Check Grounding [实抓] | ● 内容审核（模型/内容双面）[摘要] | ● 多租户隔离 + 内容安全审核 + 细粒度权限（2.1 口径）[实抓] | ● 方舟安全护栏 + 内容风控产品线 [实抓] | ● 内容安全策略协议 + 大模型内容安全平台 [实抓] | ● Skill **威胁分析评估器** + 护栏默认开启（关闭需 V2+）[实抓] |
| **D5c 调优/优化器** | ● Distillation（最高省 75%）+ Prompt Optimization + Intelligent Prompt Routing [实抓] | ◐ Agent optimizer（preview）+ 微调 SFT/DPO/RFT [实抓] | ● Prompt Optimizer + **Model Optimizer 动态路由**（cost/balanced/quality）[实抓] | ● 调优 CPT/SFT/DPO/RL（**不支持调优自有模型**）[实抓] | ◐ Prompt 一键优化 + 模型对比调试 [实抓] | ◐ 扣子罗盘提示词优化 + 方舟精调/蒸馏 [实抓] | ● SFT/蒸馏 + 主动 Cache（官方称至多 -80% 成本）[实抓] | ● **GRPO 强化学习微调 + 应用自演进**（付费版）[实抓] |

### 3.3 部署、计费与锁定（D6 + D7 + D8）

| 维度 | AWS Bedrock | MS Foundry | Google Vertex | 阿里百炼 | 腾讯 ADP | 火山引擎 | 百度千帆 | 华为云 |
|---|---|---|---|---|---|---|---|---|
| **D6a 区域与数据驻留** | ● 20+ 区域（AgentCore 22 区）；Geographic CRIS 地理驻留；GovCloud 可用 [实抓] | ● Global/Data Zone/Standard 三层驻留 + Azure Gov（usgov 两区）+ Top Secret 气隙 [实抓] | ◐ 40+ 区域；**Preview 模型仅全局端点**（驻留冲突点）[实抓] | ◐ 6 地域（北京/新加坡/法兰克福/东京/香港/弗吉尼亚）；大量能力仅北京 [实抓] | ◐ 公有云（区域未单独标注）+ 专有云/私有化/混合云四形态 [实抓] | ◐ 华北为主（cn-north-1）；区域清单未复核 [摘要] | ◐ 区域列表无公开静态文档 [未复核] | ◐ MaaS/AgentArts 仅"西南-贵阳一"[实抓] |
| **D6b 私有化交付** | — 无私有化形态（全部托管口径）[实抓] | ◐ Foundry Local / Azure Local / Sovereign Private Cloud（后两者未复核全文）[摘要] | ◐ GDC air-gapped（Gemini for GDC API）[摘要] | ◐ 未见百炼品牌私有化页（疑走专有云/PAI）[未复核] | ● 企业版含私有化（等保/密评达标、信创全栈适配，独立站口径）[实抓] | ◐ HiAgent 私有化（媒体口径，未官网复核）[摘要] | ● 私有化/软硬一体（千帆一体机，媒体口径未复核）[摘要] | ● 华为云 Stack（盘古 for Stack 8.5.1）+ 全栈信创 [摘要] |
| **D6c 合规提法** | "数据不被存储或用于训练"+ AWS 合规计划（清单未逐项复核）[实抓] | Entra/Purview/Defender/Policy 全栈（微软治理栈最强）[实抓] | Assured Workloads（HIPAA/CJIS/FedRAMP 类）[摘要] | "不会将数据用于模型训练"（FAQ 原文）+ 资质页未抓 [实抓] | 等保/密评开箱即用（独立站口径）[实抓] | 等保三级/ISO 42001/SOC 等（产品页实抓字样）[实抓] | 生成式 AI 备案信息参考文档在列 [实抓] | 等保认证声明 + 信创全栈 [摘要] |
| **D7a 计费主模式** | 按 token + AgentCore 按秒（vCPU/GB·时）+ 组件计费（工具/检索按次）[实抓] | 按 token（PAYG）+ PTU 预留 + Copilot Credit（低代码）[实抓] | 按 token + Agent Runtime 按时（vCPU/GiB）+ Agent Search 按次 [实抓] | 按 token + PTU/DTU + Token Plan 订阅 [实抓] | **套餐订阅 + PU（1 PU=0.001 元）**，不支持后付费 [实抓] | 按 token + 包天/小时 TPM + Agent Plan + 扣子积分制 [实抓] | 按 token + 量包 + TPM 包月 + 算力单元 + Token Plan 积分 [实抓] | 按 token（MaaS）+ Token Plan + CU 套餐（AgentArts）[实抓] |
| **D7b 当日代表价（旗舰，输入/输出，每百万 token）** | Claude 3.5 Sonnet v2 $6/$30（GPT-5.x/Claude 4.x+ 动态未出——未复核）[实抓] | GPT-5.6-sol $5/$30 [实抓] | Gemini 3.1 Pro $2/$12 [实抓] | qwen3.8-max ¥12/¥36 [实抓] | hunyuan-turbos ¥0.8/¥2.0（旧计费口径，套餐内按 PU 抵扣）[实抓] | Doubao-Seed-2.1-pro ¥6/¥30（官网片段；价格表未直抓）[摘要] | ernie-5.1 ¥4/¥18 [实抓] | DeepSeek-V4-Pro ¥12/¥24（**官方预告将上调**）[实抓] |
| **D7c 性价比档（输入/输出）** | DeepSeek V3.2 $0.62/$1.85；Gemma 4 31B $0.14/$0.40 [实抓] | GPT-5.6-luna $0.20/$1.20；gpt-oss-120b $0.15/$0.60 [实抓] | Gemini 2.5 Flash-Lite $0.10/$0.40 [实抓] | qwen3.8-flash ¥0.8/¥2.7 [实抓] | 1 PU=0.001 元（赠 PU 折算约 ¥2/百万 token 量级）[实抓] | doubao-1.5-lite ¥0.3/¥0.6 [实抓] | ernie-4.5-turbo ¥0.8/¥3.2（缓存命中 ¥0.2）[实抓] | DeepSeek-V4.1-Flash 忙 ¥2/¥8、闲 ¥1/¥4 [实抓] |
| **D7d 免费额度** | $200 credits + 30 天 API key + Registry/Policy 月度免费额度 [实抓] | $200/30 天 + Foundry IQ 免费层 + File Search 1GB [实抓] | $300 credits + Express Mode 免费配额 + Grounding 5k/月 [实抓] | **每模型 100 万 token（90 天，仅北京）**+ 联网 MCP 2000 次 [实抓] | 免费版 15,000 PU + 1GB 知识库（**每账号限领一次**）[实抓] | 协作奖励每日领 500 万 token/模型 + 扣子活动积分 [实抓] | **17 模型 ×100 万 token（3 个月）**+ 20 元代金券 [实抓] | AgentArts 体验版免费 + **200 万 token**；MaaS 无统一赠送条款 [实抓] |
| **D8a 模型层可迁移性** | ● OpenAI/Anthropic 双兼容端点（Messages/Responses/Chat Completions API）[实抓] | ● OpenAI 兼容 v1 稳定路由 [实抓] | ● OpenAI 兼容 + Gemini 原生 [实抓] | ● OpenAI 兼容（DashScope compatible-mode）[实抓] | ◐ 应用 OpenAPI（模型层未直接暴露标准协议）[实抓] | ● OpenAI 兼容（ark api/v3）[实抓] | ● OpenAI 兼容 v2 [实抓] | ● OpenAI 兼容 + **Anthropic 兼容接口**（MaaS 文档）[实抓] |
| **D8b 编排层可迁移性** | ◐ Strands 开源可带走；harness 配置不可移植 [实抓] | ◐ MAF 开源可带走；Hosted agent 定义随平台 [实抓] | ● **ADK 全开源**——代码即资产 [实抓] | ◐ 工作流 DSL 可导出且**兼容 Dify**[实抓] | ◐ 应用配置不导出；API 调用可迁移 [实抓] | ◐ 扣子配置不导出；AgentKit 代码可带走 [实抓] | ◐ 组件工作流+SDK 代码可带走；画布不可 [实抓] | ◐ Runtime SDK 代码可带走；**支持导入 Dify 工作流**（单向）[实抓] |
| **D8c 换代风险（当日实证）** | ● Agents Classic 停止新客（2026-07-30）[实抓] | ● 更名 Foundry + Agents v2（Assistants→Responses）[实抓] | ● 更名 GEAP（Agent Engine→Agent Runtime 等 5+ 项）[实抓] | ◐ Assistant API 下线中；Agent 1.0/2.0 不兼容 [实抓] | ◐ 旧按量计费即将下线；模型上下架频繁 [实抓] | ◐ 扣子资源点→积分制；HiAgent/扣子双线并行 [实抓] | ● ModelBuilder+AppBuilder 合并 + V1 接口下线 [实抓] | ◐ MaaS 下线按算力计费的部署/调优（迁移不平滑）[实抓] |

### 3.4 "只有某家有 / 某家没有"差异点清单

**只有某家有**：

- **只有 Google**：开源多语言 ADK（Python/Java/Go/TS）+ 全托管 Agent Runtime 的组合；Model Optimizer 按 prompt 动态路由三档；Grounding with Google Search。
- **只有 Microsoft**：调用者身份执行的权限感知 RAG（Entra + Purview）；Copilot Studio 低代码与 Foundry 代码态的统一治理（Control Plane）；Azure Government / Top Secret 气隙云上的 GPT 系模型。
- **只有 AWS**：Custom Model Import 按秒计费的托管自带权重；Guardrails 可对任意模型（含外部自托管）独立调用；Managed Agents powered by OpenAI（OpenAI harness 跑在 AWS 上）。
- **只有国内平台**：私有化/专有云交付与等保/信创口径（华为/ADP/千帆最完整）；错峰/忙闲时价（DeepSeek 系普遍存在，见 [tuning-handbook §7.3](../tuning-handbook/Agent调优手册.md) 错峰口径）；积分/PU 制订阅。
- **只有华为**：全栈昇腾 + openPangu 开源（信创硬要求的默认答案）；Skill 威胁分析评估器。
- **只有百度**：知识库原生 GraphRAG 开关；"全面兼容 A2A"写进产品页。
- **只有火山**：视频/图像/3D 生成产品化深度（Seedance/Seedream/Seed3D）；扣子"人+Agent 协作团队"形态与 OpenClaw/Claude Code 托管调度。
- **只有腾讯 ADP**：企微/微信渠道原生接入深度 + Claw 模式（类 Claude-Code 云端编码智能体）+ Text-to-SQL 数据库知识库（每账号 100 库）。
- **只有阿里**：Agent 2.0 的"思考卡片"全链路展示 + 智能模式四档路由；Spring AI Alibaba 的 Java 系 agentic 框架。
- **只有 AWS/Google/微软（美系共性）**：Model Distillation（蒸馏成专属托管小模型）三家都有（命名不同）——国内平台以"蒸馏功能"存在但产品化程度弱。

**某家没有（当日核实）**：

- **五家中国平台均无**：Azure Government 式政府气隙云的公开对应物（国内以私有化/专有云交付满足同一需求）；Distillation 级别的"蒸馏托管小模型"完整产品化（千帆/方舟有蒸馏计费项，但无 AWS/Google 式一键蒸馏上架）。
- **三家美系均无**：ADP 式"企微/钉钉/飞书/微信"渠道原生接入；忙闲时错峰价；积分制小额订阅档（最接近的是 Copilot Credit，但面向低代码场景）。
- **华为 MaaS**：2026-08-18 后不再提供按算力计费的模型部署/调优（自托管模型路线收窄到 ModelArts）。
- **Bedrock**：无私有化形态——数据完全不能出 AWS 边界的客户只能转投 Azure Local/GDC 或国内私有化方案。
- **扣子**：MCP 不支持 stdio——本地进程工具必须经网关中转。

## 4. 场景化选型决策树

> 用法：先过 §1 与 [deploy-handbook §1.3](../deploy-handbook/AI应用部署与运维手册.md) 的硬约束（合规/数据位置一票否决），再按场景取路径。每条路径给**推荐组合 + 理由 + 需要当场验证的三件事**。推荐只到"组合"粒度——最终选型必须用 §8 的方法做一次真实 POC。

```text
第一问：数据与模型可以出中国内地吗？
├─ 完全不能（数据不出域 + 境外平台不用）────────▶ 路径 B（国企私有化合规）
├─ 可以出（无中国内地主体/无境内数据）─────────▶ 第二问：客户在哪、团队在哪？
│     ├─ 全球市场 + 已有云资产 ──────────────▶ 路径 A'（美系三选一，见 §4.0）
│     ├─ 中国产品出海（研发在国内）──────────▶ 路径 C（中国企业出海）
│     └─ 外企总部 + 中国子公司合规双轨 ──────▶ 路径 D（外企入华）
└─ 能出域但要自控（有 K8s 团队/多模型策略）──▶ 路径 E（已有 K8s 团队要自控）
```

### 4.0 美系三选一的快速判据（路径 A' 前置）

| 已有资产/偏好 | 首选 | 决定性理由 |
|---|---|---|
| 已在 AWS、要模型目录最广 + 按秒计费的 agent 运行时 | **Bedrock AgentCore** | 目录含中国系模型（Kimi/GLM/DeepSeek/MiniMax），harness 可用任意 LiteLLM 兼容模型；代价：多智能体弱、Classic 停新客 |
| 已在 Microsoft 生态（M365/Entra），要权限感知 RAG 与低代码+代码态双轨 | **Microsoft Foundry** | Foundry IQ 的 Entra/Purview 权限强制是独有；Copilot Studio 兜低代码人群；代价：迁移期双门户、PTU 复杂 |
| 已在 GCP、重搜索/数据/多模态，要开源框架全托管 | **Vertex（GEAP）** | ADK 开源三语言 + Agent Search/Grounding；代价：命名漂移、Preview 模型驻留限制 |

### 4.1 路径 A：创业公司快速上线

**推荐组合**：国内业务 → **百炼（免费额度 + Agent 2.0）或扣子（个人版活动积分）起步，ADP 免费版做企微渠道 demo**；海外业务 → **Gemini API/Express Mode 或 Foundry Developer 部署**（最低门槛）。

**理由**：创业期要的是"零现金跑通 + 快速换模型 + 不背运维"。百炼 17 模型×100 万 token 三个月免费、Agent 2.0 对话式创建 + MCP 广场，一个下午能出可演示的知识库问答；扣子积分制免费版适合非技术创始人自己搭；ADP 免费版 15,000 PU 够一个 1GB 知识库的 demo（**注意限领一次，规划好再开**）。美系里 Express Mode（Vertex）免信用卡、Foundry 有 $200、Bedrock 有 $200 credits + 30 天 API key——都能零成本 POC。

**当场验证三件事**：① 免费额度覆盖的知识库规格（百炼知识库 RAG 独立计费且不吃免费额度！POC 前算规格费）；② 限流是否够 demo 峰值（百炼按主账号合并且充值不提额）；③ 导出通道——POC 沉淀的工作流/配置未来能不能带走（§5）。

### 4.2 路径 B：国企私有化合规

**推荐组合**：**华为云（盘古 + AgentArts + 华为云 Stack）为信创硬要求的默认答案；腾讯 ADP 企业版（私有化 + 等保/密评口径）做智能体应用层；百度千帆软硬一体（一体机）做政务知识库问答**——三者按"算力合规 vs 应用运营 vs 知识问答"组合，而非三选一。

**理由**：这条路径的决策变量不是功能而是**资质与栈**：① 信创采购要求全栈国产（芯片→整机→智算→模型→应用），华为是唯一全栈闭合方；② ADP 企业版 4,880 元/月起含私有化 + 等保/密评开箱即用口径 + 企微渠道——央国企办公生态匹配度最高；③ 千帆一体机（媒体口径未当日复核）与政务案例密度（居民助理/总工会）在政务问答场景成熟。模型侧注意：备案主体与备案模型清单核对（§6.1）、AgentArts 付费版当日需工单（公测未开闸）——**商用合同要在报价里写清公测转商用的时点承诺**。

**当场验证三件事**：① 私有化报价与交付清单（各家均需留资，无公开价）；② 目标行业模型备案状态；③ 私有化环境里的模型上下架机制（本地版本锁定，别接受"随云端滚动升级"）。

### 4.3 路径 C：中国企业出海

**推荐组合**：**百炼国际（新加坡/法兰克福/东京/香港/弗吉尼亚六地域 + dashscope-intl 端点）或火山方舟（北京之外需确认海外接入）为主，叠加一家美系（Bedrock/Foundry/Vertex 按目标市场）做海外本地模型与合规**；agent 编排层用 OpenAI 兼容协议 + ADK/MAF 等开源框架保持中立。

**理由**：出海的硬问题是"模型在目标市场可合法服务 + 数据驻留 + 目标用户可接受"。百炼六地域是国内平台里海外点最多的，Qwen 系开源权重在海外社区接受度高；美系承担"目标市场本地化模型（多语种/区域合规）"的兜底。**关键纪律**：应用层从第一天就按 OpenAI 兼容协议写（[deploy-handbook §8.5 模式⑥](../deploy-handbook/AI应用部署与运维手册.md)），换云只换 base URL。

**当场验证三件事**：① 海外地域的功能对等性（百炼免费额度仅北京、DeepSeek 仅北京——**海外地域模型清单要逐个确认**）；② 目标市场的数据出境路径（§6.2）；③ 双云故障切换演练（模型路由与 failover 口径见 [tuning-handbook §6.5](../tuning-handbook/Agent调优手册.md)、网关落地见 [deploy-handbook §4.4](../deploy-handbook/AI应用部署与运维手册.md)）。

### 4.4 路径 D：外企入华

**推荐组合**：**世纪互联运营的 Microsoft Azure（中国区）为治理栈主轨**（Entra/Purview 治理习惯延续），**模型层做中国模型双轨**（世纪互联 Azure OpenAI + 百炼/千帆国产模型，网关层路由）；低代码人群可评估**世纪互联 Dynamics 365/Power Platform 生态内的 Copilot 能力**。

**理由**：外企入华的三重约束——数据出境受 §6.2 约束（默认策略是"中国数据留中国"）、总部技术栈延续性、中国区内容合规。世纪互联 Azure 提供与全球 Azure 最一致的治理面（但注意：中国区是独立云、账号/门户/功能节奏均独立）；模型层必须接受"OpenAI 最新旗舰在中国区的可得性滞后"的现实，国产模型（Qwen/DeepSeek/GLM）作为能力与成本补充——网关层按 [deploy-handbook §4.4](../deploy-handbook/AI应用部署与运维手册.md) 落地双供应商 failover。

**当场验证三件事**：① 目标模型在世纪互联中国区的在架与版本（与全球区逐个对）；② 数据驻留配置（Global/Data Zone/Standard 三层在中国区场景的实际含义，向世纪互联书面确认）；③ 集团账号体系（Entra ID 租户 vs 世纪互联独立租户）打通方案。

### 4.5 路径 E：已有 K8s 团队要自控

**推荐组合**：**编排层自持**（LangGraph/MAF/Strands 跑在自家 K8s，[workflow-handbook §4](../workflow-handbook/Agent工作流编排手册.md) 引擎选型 + [multiagent-handbook](../multiagent-handbook/Multi-Agent协同手册.md) 范式）+ **模型层"托管 API 为主、自托管为辅"**（Bedrock/Foundry/百炼按 §4.0 选一家做主力模型供应商，vLLM 自托管兜底，[python-handbook §6](../python-handbook/Python大模型应用开发手册.md)）+ **工具层用 MCP 收口**（自家工具封装为 MCP server，任意平台可消费）。

**理由**："要自控"的正确切法是控制**编排与数据**，而不是连模型也自持——[deploy-handbook §1.1](../deploy-handbook/AI应用部署与运维手册.md) 的"反向决策（我们用 K8s 所以模型也自托管）是沉没成本陷阱"直接适用。模型侧保留托管供应商的原因：安全更新/多模态能力/弹性扩容自持成本极高；自托管 vLLM 只承接"数据敏感 + 流量平稳"的部分负载（§6.5 容量算账）。MCP 是这条路径的关键杠杆：把工具层从云平台专有连接器迁到 MCP，供应商可换。

**当场验证三件事**：① 自托管与托管模型的评测基线一致性（换引擎必须过 [eval-handbook §4](../eval-handbook/Agent评测与质量工程手册.md) golden set）；② K8s 侧 GPU 容量账（KV cache 显存公式，[deploy-handbook §6.5](../deploy-handbook/AI应用部署与运维手册.md)）；③ MCP server 的供应链审计（[security-handbook §3.5](../security-handbook/AI应用安全手册.md)）。

---

## 5. 迁移与锁定成本

### 5.1 三层可迁移性：模型层已解，数据层最锁，编排层居中

**模型层（可迁移性最高）**：OpenAI 兼容协议已是八家共同事实——Bedrock（Messages/Responses/Chat Completions 三套兼容端点）、Foundry v1 稳定路由、百炼 compatible-mode、方舟 api/v3、千帆 v2、华为 MaaS 甚至双兼容（OpenAI + Anthropic 格式）。**迁移抓手：应用内不落任何一家 SDK 的专有参数，统一走兼容端点 + 网关**（[deploy-handbook §4.4](../deploy-handbook/AI应用部署与运维手册.md)）。剩余锁定点：各家专有的推理参数（思考模式开关/缓存断点/服务端工具）与"服务端工具"（Grounding/Web Search/KB 检索）——这部分在协议外。

**编排层（可迁移性分化）**：可带走的是**代码态**（ADK/MAF/Strands/LangGraph 全开源，代码即资产）；带不走的是**画布配置**（各家 DSL 互不相通；百炼与华为 AgentArts 支持"导入 Dify 工作流"是单向漏斗——进来容易出去难）。**纪律：核心业务流程写成代码态或 DSL 存档，画布只承载易变部分**；参照 [workflow-handbook §3.3](../workflow-handbook/Agent工作流编排手册.md) 的输入输出契约规范，让节点逻辑与引擎解耦。

**数据层（锁定最深，最被低估）**：知识库的**切片 + 索引 + 元数据 + 权限标注**是各家专有产物——重新摄入要重新解析（成本与质量双损：解析结果决定切片质量，见 [rag-handbook §2](../rag-handbook/RAG搭建文档.md)）；对话历史/记忆（AgentCore Memory、扣子记忆、长期记忆）导出能力普遍未承诺。**纪律：源文档永远留在自己对象存储；知识库把它当"可再生缓存"而非"真源"**——重建管线是"贵但可行"，文档丢了才是"不可行"。

### 5.2 MCP 作为互操作层的现实水位

当日水位（§3.2 D4a 行的展开）：**"工具互通"已达标，"编排互通"未达成**。

| 层 | 当日现实 |
|---|---|
| 工具互通 | ● 八家全部支持消费 MCP server（形态有别：AWS Gateway 统一封装/Foundry Toolbox 端点/ADK 三向/国内各家广场+节点）——把自有系统封装成 MCP server，八家平台都能接 |
| 暴露互通 | ◐ ADK/Foundry/千帆/扣子支持把 agent 或工具**发布为** MCP 端点；ADP 支持应用作为工具被调用——"agent 互相调用"的协议底座在成形，但鉴权/发现机制各家不同 |
| 编排互通 | — 工作流画布 DSL 不互通（Dify DSL 是唯一事实上的交换格式，百炼/华为支持导入，导出仅百炼） |
| 数据互通 | — 知识库索引/记忆不通过 MCP 互通；AgentCore Gateway 的"KB 即 MCP 工具"是平台内部封装，不是跨平台标准 |

**结论**：MCP 解决的是"工具在哪家平台都能用"（横向），不解决"应用从这家迁到那家"（纵向）。迁移规划里 MCP 的正确位置是**工具层防腐层**，不是迁移方案本身。

### 5.3 双云与多云的代价：三笔账

1. **工程账**：双供应商 = 两套限流语义、两套服务端工具、两套观测字段——网关统一（[deploy-handbook §4](../deploy-handbook/AI应用部署与运维手册.md)）是前提条件而非可选优化；failover 链上"降级即换模型"会连带质量预算变化（降级事件必须打标进 trace，[eval-handbook §8.1](../eval-handbook/Agent评测与质量工程手册.md) 归因口径）。
2. **质量账**：同一提示词在两家模型上的行为差异要靠评测集兜底——**双云的真实成本不是 token 价差，是"每条路由都要过一遍评测"的评测账**（[tuning-handbook §6.5](../tuning-handbook/Agent调优手册.md)：路由器要过评测）。
3. **合规账**：跨境场景的双云（境内云 + 境外云）必须先答 §6.2 的出境问题——"两家云"不自动等于"合规出境"，字段级最小化（[security-handbook §4.5](../security-handbook/AI应用安全手册.md)）才是。

**反模式**：为"防止涨价"做双云。模型价格三年内普遍下行（各家 flash 档接连降价），双云的工程+质量成本通常高于潜在价差收益；双云的正当理由是**供给韧性（区域故障/停服公告——本册当日就抓到两起：百度 7 月停服通知、华为 MaaS 能力下线）与合规分域**。

## 6. 中国区特辑：备案、出境、国产算力与信创（非法律意见）

> **本章全部内容是工程视角的"客户会问什么、到哪核实"，不构成法律意见**；法规适用以法务意见与官方原文为准。合规框架的通用简表见 [security-handbook §4.4/§4.5](../security-handbook/AI应用安全手册.md)（GDPR/AI Act/个保法对照与数据出境三口径），本节只展开中国区特有且直接影响**云平台选型**的四件事。

### 6.1 生成式 AI 服务备案：选型时的三个核对动作

**背景数字**（当日检索核实）：自《生成式人工智能服务管理暂行办法》（2023-08-15 施行）确立备案制度以来，截至 **2025-12-31 全国累计 748 款生成式 AI 服务完成备案**（2025 年新增 446 款）；另有基于已备案模型能力的应用由**地方网信办登记**（2025 年新增 330 款）。**备案与登记的分界：自研/自训模型 → 国家网信办备案；仅调用已备案模型 API 的应用 → 地方网信办登记**（来源：人民网 2026-01-10 报道及各地网信办公告，当日检索快照）。北京市累计备案 259 款居首（截至 2026-07-16）。

**对选型的三个核对动作**：
1. **核"模型的备案身份"**：客户自己训/调优过的模型 → 需备案（走云平台的备案支持通道，华为官方 FAQ 明示"算法备案资质需客户自行申请"）；纯调用平台 API → 应用向地方登记即可。百炼/千帆/方舟等平台在其文档"相关协议"栏目普遍提供备案信息参考（千帆《生成式人工智能服务备案信息参考》当日实抓在列）。
2. **核"平台侧的备案链路"**：问清平台是否提供安全评估/备案的配套（测试账号、材料、周期）。私有化场景（路径 B）模型在客户域内运行，备案责任归属要在合同里写清。
3. **核"内容标识"**：《人工智能生成合成内容标识办法》要求显式+隐式标识——平台侧的标识能力（水印/元数据）在选型演示里当一项验收（千帆/ADP 等产品页提及内容安全审核，**标识能力的具体形态未当日逐家复核**）。

### 6.2 数据出境：三条路径 + 豁免 + 自贸区负面清单

现行框架（《促进和规范数据跨境流动规定》，国家网信办令第 16 号，2024-03-22 施行）：
- **三条路径**：数据出境安全评估（重要数据/大规模个人信息）→ 个人信息出境标准合同 → 个人信息保护认证；16 号令放宽了各路径的适用门槛。
- **法定豁免**：履行合同必需、跨境人力资源管理、紧急情况等情形可免予三条路径。
- **自贸区负面清单**：自贸试验区可制定区内数据出境负面清单（经省级批准），清单之外数据出境免予评估/合同/认证——上海（含临港）、北京、天津、海南等已陆续发布（2024 版起）；2025-04 央行等发布金融业数据跨境流动合规指南，行业级清单开始出现。

**对选型的工程含义**（承接 [security-handbook §4.5](../security-handbook/AI应用安全手册.md) 三条工程口径）：① "送进 prompt 的字段 = 出境字段"——境外模型（Bedrock/Foundry/Vertex 国际区）处理中国用户个人信息时，默认按三条路径或豁免论证，把 prompt 字段最小化当数据分类问题管；② 国内平台的**海外地域**（百炼新加坡等 6 地域）同样是出境——"用了中国厂商的云"不等于"没出境"；③ 出海企业反向问题：境外用户数据进境内处理同样受"入境"侧规范约束，路径 C 的双云分域设计要同时管两个方向。

### 6.3 国产算力适配：为什么"昇腾"会成为选型变量

- **驱动**：出口管制下英伟达高端 GPU 在华供给受限 + 政企采购国产化要求（§6.4），智算层国产替代从"可选项"变"入场券"；媒体口径 2025-2027 政企采购呈"芯片→整机→智算中心→模型/应用"全栈国产化路径（当日检索，来源为证券研究/产业报道，非官方文件）。
- **昇腾生态现状**（当日实抓/摘要）：华为云 openPangu 系模型"基于昇腾 NPU 训练"（MaaS 产品页）；CloudMatrix384 超节点（384×昇腾 910C）2025-05 发布、2025-09"AI Token 服务全面接入"（搜索快照，官方新闻页未复核）；**其他云厂商的昇腾适配**：阿里 PAI、百度百舸等均提供昇腾实例（**本册当日未逐家复核其大模型推理适配深度**——昇腾推理生态的主力叙事仍在华为云 + 各自建智算中心）。
- **对选型的含义**：① 客户已有昇腾智算中心 → 自托管推理层天然绑定 CANN/MindSpore 生态，选型问题变成"哪个平台的精调/编排工具链适配昇腾"（ModelArts 优先）；② 客户要"全国产"标 → 模型也要国产（盘古/Qwen/DeepSeek/GLM/文心），托管目录里的美国模型（GPT/Claude/Gemini）直接出局；③ 开源权重模型的昇腾推理成熟度要 POC 验证（vLLM-ascend 等适配层存在，但版本跟进滞后于 CUDA 生态——**未当日复核具体版本水位**）。

### 6.4 信创要求对选型的影响与"中国运营云"现状

- **信创（信息技术应用创新）**：党政机关服务器操作系统国产化替代率 2025 年底突破 40%（当日检索口径）；八大关键行业核心系统国产化渗透持续提升。对 AI 平台选型的直接影响：**央企国企采购目录内，非国产栈的 AI 平台在"入场"环节即被筛掉**——所以 §4.2 路径 B 的推荐组合里华为/ADP/千帆是"目录现实"而非单纯技术偏好。
- **"中国运营云"三例**（外企入华路径 D 的事实基础）：Azure 中国由**世纪互联**运营、AWS 中国由**光环新网（北京区）/西云数据（宁夏区）**运营、Google Cloud 中国内地无区域。含义：① 中国区与国际区是**独立云**——账号、合同、功能节奏、模型清单各自独立；② 全球总部的"用我们统一的 Azure tenant"要求必须调整为中国区租户方案；③ 三家美系的中国区模型清单**滞后于全球区**（GPT-5.6 等旗舰在世纪互联 Azure 中国区的在架状态需向世纪互联确认——**未当日复核**）。

---

## 7. 企业范例（官网案例当日实抓，精读三家）

> 案例数字均为厂商自述口径（官网案例页原文），非独立审计。八家案例区横向浏览结论：金融/政务/制造是共同高频行业；美系案例偏"平台能力叙事"（token 量/成本降幅），国内案例偏"业务指标叙事"（解决率/工单降幅/满意度）——引用给客户时注意口径差异。

### 7.1 横向案例一览（当日实抓节选）

| 平台 | 案例 | 公开指标（厂商口径） |
|---|---|---|
| AWS | Robinhood / Cox Automotive / Druva | token 5亿→50亿/日、成本 -80%；一年 17 个生产 agent；68% 支持问题自动解决 |
| Microsoft Foundry | Commerzbank / AT&T / Audi | 月 30,000+ 会话、75% 自主解决（精读见 §7.2） |
| Google | Golden State Warriors / Swarovski | 30+ 数据源 1 亿+ 数据点；行政工作 -50% |
| 阿里百炼 | 零跑汽车 / 语忆科技 | C10 座舱语音大模型；客服提效 40%+ |
| 腾讯 ADP | 迈瑞医疗 / 碧桂园服务 / 华住 | 精读见 §7.3 |
| 火山引擎 | 浙大先生 / 招商银行 | 7 天构建校园大模型应用体系 |
| 百度千帆 | 居民助理 / 全国总工会 | 20 万户+ 触达；1 个月交付 |
| 华为云 | 温氏食品 / 太平洋保险 | 育种基因组分析 +50%；保顾满意度 80.5% |

### 7.2 精读一：Commerzbank "Ava"（Microsoft Foundry）——银行客服 agent 的完整技术栈样本

[官方案例](https://www.microsoft.com/en/customers/story/25676-commerzbank-ag-azure-ai-foundry-agent-service)（2025-11-18 发布，当日实抓全文）：德国商业银行客户服务 agent "Ava"，**月 30,000+ 客户会话、约 75% 自主解决、7×24**。

**值得抄的三条**：① **技术栈完整暴露**——Foundry Agent Service + Azure OpenAI + Azure Container Apps/AKS + Content Safety + Cosmos DB（会话）+ AI Search（检索）+ Speech（TTS 头像）+ Microsoft Fabric（分析）——这是"托管 agent 平台不替你解决的问题清单"的实物参照：存储、检索、内容安全、分析仍是自选组件拼装；② **75% 自主解决率的达成前提是"能拒绝"**——案例中人工升级通道与 agent 边界设计是隐含主角（对应 [eval-handbook](../eval-handbook/Agent评测与质量工程手册.md) 的失败归因与 HITL 插点）；③ **合规密集行业选 Foundry 的理由在治理不在模型**——Entra 身份、Purview、EU Data Boundary 组合是银行法务能签字的形态。

### 7.3 精读二：腾讯 ADP 双案例（迈瑞医疗 + 碧桂园服务）——国内"知识密集 + 渠道密集"场景样本

（产品页/独立站当日实抓）**迈瑞医疗**：医疗技术服务 agent，融合 500+ 产品资料、5000+ 项临床知识，关键问题准确率 95%，覆盖 190+ 国家。**碧桂园服务**：「一问」AI 客服嵌入 30+ 业务系统、沉淀 8 万+ 知识，试点区域工单量下降 25%+。

**值得抄的三条**：① **知识库规模与准确率的关系被显式给出**——"500 资料×5000 知识点 → 95%"意味着知识工程（解析/切分/更新流程）是主要投入，平台能力只是下限（对应 [rag-handbook](../rag-handbook/RAG搭建文档.md) 全部规范）；② **渠道即 ROI**——碧桂园的工单降幅来自"嵌入 30+ 业务系统"，agent 价值兑现位在既有工单流里；选平台时渠道连接器深度（ADP 的企微/微信优势）直接换算成业务指标；③ **"一问"模式可复制**——一个入口 agent + 知识库 + 工单系统的三件套是中型企业最短路径（对应 [fde-handbook ADP 3.2 知识助手实战](../fde-handbook/tencent-adp-fde-course/lessons/3.2_标准模式实战：知识助手.md)）。

### 7.4 精读三：Cox Automotive（AWS AgentCore）——"一年 17 个生产 agent"的平台化节奏样本

（[AgentCore 案例区](https://aws.amazon.com/bedrock/agentcore/)当日实抓）一年内 17 个生产 agent 上线，支撑售后/金融/库存多场景。

**值得抄的三条**：① **"一年 17 个"说明平台化起效的判据是吞吐**——第 1 个 agent 的成本是方案，第 17 个的成本应是"配置"；衡量平台价值用"每新增一个 agent 的边际交付周期"；② AgentCore 的"any framework, any model"定位在案例里的作用是**允许团队不换技术栈**——已有 LangChain 资产直接上 Runtime，而不是重写；③ Druva"68% 支持问题自动解决"与 Commerzbank"75%"同量级——**客服场景的自主解决率行业水位在 70% 上下**，可以作为客户预期管理的锚点（低于 50% 说明知识工程没做完，高于 90% 要检查评测集是否太窄）。

## 8. 动手验证：同一个 agent 需求在三家平台的最小实现对照 + FAQ + 上手清单

### 8.1 验证设计

**同一个需求**：「知识库问答 + 工具调用」——上传一批企业文档，agent 优先依据文档回答（附引用），并至少调用一个外部工具（联网搜索或天气/地图类 MCP）。这个需求覆盖 D2/D3/D4 三个维度的最小闭环，是 FDE 现场 POC 的标准起点。

**三家对照选型逻辑**：故意取**三种形态的极值**——腾讯 ADP（零代码画布）、阿里百炼（低代码 + API 双轨）、AWS AgentCore（代码态）——跑通三家即可感受"形态差异比功能差异更大"的选型手感。

**验证边界（重要）**：以下步骤均**照官方文档逐条核对（2026-09-28），未使用真实账号实跑**；步骤的正确性以标注的官方文档为准，控制台菜单名可能随版本漂移。免费额度口径为当日官网数字（§2 各家"定价要点"），开账户前再核对一次。**本节是"文档级 POC 预案"，不是"实测报告"**——真实 POC 时按 §8.5 清单补记实测数据。

### 8.2 三家对照总表

| 环节 | 腾讯 ADP（零代码） | 阿里百炼（低代码+API） | AWS AgentCore（代码态） |
|---|---|---|---|
| 前置 | 腾讯云账号实名；免费版 **15,000 PU + 1GB 知识库（限领一次）** | 阿里云账号；**每模型 100 万 token 免费 90 天（仅北京）**；知识库 RAG 独立计费 | AWS 账号；**$200 credits + 30 天 API key**；AgentCore 按秒计费 |
| 知识库建立 | 控制台"知识库"→ 上传（≤200MB/文件）→ 切分设置 → 召回测试 | "知识库（RAG）"→ 文档搜索类型 → 上传（50 个/次、150MB/个）→ 智能切分 → 配检索服务 | Managed KB（S3 数据源）→ 托管解析/embedding（不另收费）→ Sync |
| agent 构建 | 标准模式新建应用 → 配模型+角色指令 → 挂知识库 → 加工具（联网搜索/自定义） | Agent 2.0 对话式创建 → 系统提示词 → 关联知识检索（智能/必定调用）→ 挂 MCP/插件 | `agentcore create`（Harness 或 Strands）→ KB 作为 Gateway MCP 工具挂载 → `agentcore deploy` |
| 工具调用 | 连接器/工具（API/MCP/代码/应用四种接入） | MCP 广场（联网搜索 2000 次免费）或插件 | Browser/Code Interpreter/Web Search 内置 + Gateway 封装自有 API |
| 调试评测 | 右侧调试区 + 模型对比调试 + 应用评测（xlsx 评测集） | 应用内对话（思考卡片可见）+ 应用评测板块 | `agentcore dev`（本地 inspector + trace）+ AgentCore Evaluations |
| 发布渠道 | 企微/钉钉/飞书/微信 + API（HTTP SSE/WebSocket） | API/SDK + 钉钉/微信公众号 + Web 分享 | Runtime 端点（Invoke API）|
| 单步耗时感（文档级预估） | 半天内（全界面操作） | 半天到一天（知识库计费要额外核对） | 1-2 天（CLI + IAM/CDK bootstrap） |
| 主要文档 | [标准模式教程 /122571](https://cloud.tencent.com/document/product/1759/122571) | [Agent 2.0 文档](https://help.aliyun.com/zh/model-studio/new-single-agent-application) | [AgentCore 入门](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-get-started-cli.html) |

### 8.3 分平台步骤（文档级）

**腾讯 ADP**（来源：/122571 标准模式教程、/112702 知识库、/115873 连接器、/104208 评测，均为当日实抓）：
1. lke.cloud.tencent.com 开通免费版 → 新建应用 → 选**标准模式**（Claw 不可逆、Multi-Agent 评测受限，严肃问答选标准）。
2. 知识库：新建 → 本地上传文档 → 智能切分 → 保存；用**召回测试**验证命中率（改切分参数重测）。
3. 应用配置：生成模型（如 hunyuan-turbos）+ 思考模型（youtu-intent）→ 角色指令（模板库起步，"AI 一键优化"消耗 token）→ 挂载知识库 → 添加工具（内置联网搜索或自定义 MCP：填 Server URL + 鉴权）。
4. 右侧调试区对话验证"引用是否附带 + 工具是否真调用"。
5. 评测（可选）：下载官方 xlsx 模板 → 填 query + reference_output → 基准评测（裁判模型/规则打分）。
6. 发布 → 服务状态页取体验链接与 API 信息 → 渠道配置（企微机器人最快见效）。
7. **省钱纪律**：免费版 15,000 PU 一次性——评测跑批前先看 PU 余额（1 PU=0.001 元，知识库超量存储 1.5 PU/GB·时）。

**阿里百炼**（来源：/new-single-agent-application、/rag-knowledge-base、/mcp-introduction、/call-single-agent-application，当日实抓）：
1. 控制台"API-KEY"创建 Key → `export DASHSCOPE_API_KEY=...`。
2. 知识库：RAG → 文档搜索 → 上传（单次 50 个/150MB）→ 智能切分（最大分段默认 600）→ embedding 默认 text-embedding-v4 → 平台存储；创建后配置**检索服务**（排序模型/TopK/阈值）。⚠️ 知识库按规格时长独立计费、不吃免费额度。
3. 应用管理 → 创建**智能体应用（Agent 2.0）** → 模型选 qwen3.8-flash（免费额度内）或"智能模式 AUTO" → 系统提示词写"仅依据知识库回答并给出引用" → 关联检索服务（选"必定调用"保证 POC 里检索真实生效）→ 添加联网搜索 MCP（2000 次免费）。
4. 测试：对话框验证思考卡片（检索→工具→反思链路）；ReAct 轮次上限按需调。
5. 发布 → API 调用：`POST https://dashscope.aliyuncs.com/api/v1/apps/{APP_ID}/completion`，Bearer 认证，流式加 `X-DashScope-SSE: enable`。
6. 需要固定流程时改用**工作流应用**（画布：知识库节点 + 大模型节点 + MCP 节点；支持一键导入 Dify 工作流）。
7. **省钱纪律**：未认证账号额度用完即 403——POC 前决定"认证转按量"还是"用完即停"；Batch 5 折但评测跑批不适合在线接口。

**AWS AgentCore**（来源：agentcore-get-started-cli、kb-build-managed、kb-gateway-target、harness 文档，当日实抓）：
1. IAM 凭证 + CDK bootstrap；`npm install -g @aws/agentcore`。
2. `agentcore create` → 选 Harness（配置式）或 Agent（Strands + Bedrock provider；memory none/short/long）。基础模型默认已开通访问（官方指南原文）。
3. `agentcore dev` 本地起服务 + inspector 聊天/看 trace——**先本地后云端，调试成本最低**。
4. 知识库：Bedrock 控制台 → Knowledge Bases → Managed KB → S3 数据源（建桶传 PDF）→ 托管解析/embedding（不另收费）→ Sync。
5. KB 接入 agent：`agentcore add gateway`（KB 以 MCP 工具暴露）；再 `agentcore add tool --type agentcore_browser`（或 code_interpreter）。
6. `agentcore deploy`（CDK 供给 Runtime endpoint + CloudWatch 观测）→ `agentcore invoke --prompt "依据知识库回答 X 并调用工具查 Y"`。
7. 评测：AgentCore Evaluations（内置评估器 $0.0024/千 token 输入）或先人工抽检。
8. **省钱纪律**：Runtime 按秒计费（v2 $0.1276/vCPU·时）但 I/O 等待不计 CPU、闲置 120 秒回收；KB 检索 Standard $1/千次 vs Agentic $4/千次——POC 用 Standard 档；销毁用 `agentcore remove all && agentcore deploy`，**别只删应用留着 Gateway/KB 计费**。

### 8.4 常见坑 FAQ（12 条，多为当日文档原文/抓取实证）

1. **免费额度"看起来够、实际不够"**：三家的免费额度都不覆盖同一个东西——ADP 不含知识库超量存储、百炼不含知识库 RAG 规格、AWS 不含 KB 之外的 AgentCore 组件叠加。POC 预算 = 模型 token + 检索次数 + 平台组件三笔账分开算。
2. **知识库"已就绪"≠"检索有效"**：三家都有独立"召回测试"环节（ADP 召回测试/百炼命中测试/AgentCore Sync 后查询测试）——跳过它直接建 agent，坏例会伪装成"模型不行"。
3. **ADP 免费版限领一次**：验证完想再来一遍没额度了——POC 方案先在纸面过一遍再开通。
4. **百炼 403 AllocationQuota.FreeTierOnly**：免费额度用尽（未认证账号），不是代码错误；转按量或换有额度的模型。
5. **百炼限流是主账号合并的**：RAM 子账号/API Key/业务空间共享阈值，多脚本并发 POC 会互相打 429；充值也不提额（需商务）。
6. **AWS 403 不一定是权限**：Agents Classic 对无历史使用的新账户返回 403——新项目直接用 AgentCore，别再按旧教程建 Classic。
7. **扣子/火山官网页面 JS 渲染**：公开抓取拿不到价格表——比价要么登录控制台，要么用官方文档站的静态页（docs.coze.cn 文档可抓）。
8. **"支持 MCP"要追三个问题**：消费端还是暴露端？支持哪些传输（stdio/HTTP/SSE——扣子不支持 stdio）？鉴权方式（Header APIKey/OAuth）？三家答案不同，写进 POC 记录。
9. **评测集跨平台不通用**：ADP 限定 xlsx 格式 + 自定义列 ≤10；百炼要 EvaluationSet 类型（Prompt+Completion 两列）；AWS 无内置格式约束——评测数据用 CSV/JSON 自存为主数据源，导出时再转换。
10. **模型对比调试 ≠ 评测**：ADP"模型对比调试"是交互式试用，评测才是可回归的判据（[eval-handbook §2](../eval-handbook/Agent评测与质量工程手册.md) 的判据优先级）——POC 报告里只引用评测任务结果。
11. **区域陷阱**：百炼免费额度/DeepSeek/调优仅北京；华为 MaaS/AgentArts 仅西南-贵阳一；Vertex Preview 模型仅全局端点——开账户时选错区域要重来。
12. **当日口径冲突示例**：ADP 专业版 PU 额度产品页（89,000）与计费文档（150,000）不一致——**凡是两家官方页面打架的数字，两个都记下来并截图存证**，写进方案时注明"以合同口径为准"。

### 8.5 上手清单

- [ ] 选定 3 家平台（建议：1 国内画布型 + 1 国内低代码 + 1 美系代码态），各开免费额度（先核对当日额度页）
- [ ] 三家用**同一批文档**（建议 20-50 份混合 PDF/DOCX/XLSX）建知识库，记录：解析耗时/切分默认值/召回测试命中率
- [ ] 三家跑同一个 20 题评测集（含 5 题必须调用工具），记录：答案正确数/引用正确数/工具调用成功数/单题 token 成本
- [ ] 记录三家全部计费明细（当日截图存证），换算成"单题全链路成本"
- [ ] 各导出一次资产：ADP/百炼应用配置截图、百炼工作流 DSL、AgentCore 代码仓——按 §5.1 评估"带得走多少"
- [ ] 把三家 POC 结果填进 §3 总表对应格，形成客户方案附件
- [ ] 复核本册所有"未当日复核"项是否已有当日数据（云平台月级漂移）

---

## 参考资料

**官方产品页/定价页（2026-09-28 当日实抓）**：AWS Bedrock https://aws.amazon.com/bedrock/ ｜ Bedrock 定价 https://aws.amazon.com/bedrock/pricing/ ｜ AgentCore 定价 https://aws.amazon.com/bedrock/agentcore/pricing/ ｜ Agents Classic 维护模式 https://docs.aws.amazon.com/bedrock/latest/userguide/agents-classic-maintenance-mode.html ｜ Bedrock 文档总览 https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html ｜ Microsoft Foundry https://azure.microsoft.com/en-us/products/ai-foundry ｜ Foundry 文档 https://learn.microsoft.com/en-us/azure/foundry/what-is-foundry ｜ Azure OpenAI 定价 https://azure.microsoft.com/en-us/pricing/details/azure-openai/ ｜ Foundry 定价概览 https://azure.microsoft.com/en-us/pricing/details/ai-foundry/ ｜ Copilot Studio 定价 https://www.microsoft.com/en-us/microsoft-copilot/microsoft-copilot-studio ｜ Vertex AI https://cloud.google.com/vertex-ai ｜ GenAI 定价 https://cloud.google.com/vertex-ai/generative-ai/pricing ｜ 名称变更表 https://docs.cloud.google.com/gemini-enterprise-agent-platform/vertex-ai-name-changes ｜ ADK 文档 https://google.github.io/adk-docs/ ｜ 百炼 https://www.aliyun.com/product/bailian ｜ 百炼价格 https://help.aliyun.com/zh/model-studio/model-pricing ｜ 百炼免费额度 https://help.aliyun.com/zh/model-studio/new-free-quota ｜ 腾讯 ADP https://cloud.tencent.com/product/adp ｜ ADP 独立站 https://adp.tencent.com ｜ ADP 计费概述 https://cloud.tencent.com/document/product/1759/127342 ｜ 火山方舟 https://www.volcengine.com/product/ark ｜ 方舟计费 https://www.volcengine.com/docs/82379/1099320 ｜ 扣子文档 https://docs.coze.cn ｜ 千帆 https://cloud.baidu.com/product/wenxinworkshop ｜ 千帆计费 https://cloud.baidu.com/doc/qianfan/s/wmh4sv6ya ｜ 千帆平台简介 https://cloud.baidu.com/doc/qianfan/s/rmh8khvwu ｜ 华为盘古 https://www.huaweicloud.com/product/pangu.html ｜ 华为 MaaS 价格 https://support.huaweicloud.com/price-maas/price-maas-0002.md ｜ 智果 AgentArts https://www.huaweicloud.com/product/agentarts.html ｜ Spring AI Alibaba https://java2ai.com ｜ MAF https://github.com/microsoft/agent-framework ｜ AutoGen（维护模式）https://github.com/microsoft/autogen ｜ AppBuilder-SDK https://github.com/baidubce/app-builder

**合规与行业（2026-09-28 当日检索，非法律意见）**：生成式 AI 服务备案累计 748 款（人民网 2026-01-10，经当日检索快照核实）｜《促进和规范数据跨境流动规定》（国家网信办令第 16 号，2024-03-22 施行）及自贸区负面清单解读（Mondaq/新浪财经当日检索快照）｜ 信创与国产算力进展（产业研究与媒体报道当日检索快照，标注为二手口径）

**官方案例（当日实抓）**：Commerzbank https://www.microsoft.com/en/customers/story/25676-commerzbank-ag-azure-ai-foundry-agent-service ｜ AWS 客户 https://aws.amazon.com/bedrock/customers/ ｜ Golden State Warriors https://cloud.google.com/customers/golden-state-warriors ｜ 其余各家案例见 §2/§7 标注的产品页案例区

**本工作区互引**：[deploy-handbook §1](../deploy-handbook/AI应用部署与运维手册.md)（托管平台速览与选型判据，本册为深全版）｜ [tuning-handbook §6.6/§7](../tuning-handbook/Agent调优手册.md)（模型价格口径与成本工程，本册价格口径同源）｜ [workflow-handbook §4](../workflow-handbook/Agent工作流编排手册.md)（开源引擎横评——本册管云平台，那边管自建引擎；"归档/换代扫描"纪律共用）｜ [fde-handbook ADP 2.1/2.3](../fde-handbook/tencent-adp-fde-course/lessons/2.1_ADP_是什么：企业级智能体开发平台.md)（ADP 一手底稿）｜ [security-handbook §4.4/§4.5](../security-handbook/AI应用安全手册.md)（合规简表与数据出境三口径，本册 §6 是中国区展开）｜ [mcp-handbook](../mcp-handbook/MCP搭建文档.md)（MCP 协议与 server 搭建，本册 §5.2 讲平台侧消费现状）｜ [rag-handbook](../rag-handbook/RAG搭建文档.md)（知识库管线规范，§8 POC 的质量判据）｜ [eval-handbook](../eval-handbook/Agent评测与质量工程手册.md)（评测方法与成本归因）｜ [multiagent-handbook](../multiagent-handbook/Multi-Agent协同手册.md)（A2A 协议与多 agent 范式）｜ [deploy-handbook §4/§8.5](../deploy-handbook/AI应用部署与运维手册.md)（网关落地与 OpenAI 兼容协议）

> 说明：本册调研执行时单子代理串行实抓（当日并发配额限制），八家各产出一份当日 dossier；文中"未当日复核"项合计 30+ 处，全部原样保留并给出原因——这些正是下次复核时的检查清单。






