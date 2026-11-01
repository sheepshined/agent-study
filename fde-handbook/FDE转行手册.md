# FDE 转行从业手册

> 面向想转型 FDE（Forward Deployed Engineer，前线部署工程师）的中文工程师/技术人。
> 数据基准日：2026-09-26。配套数据：[data/github-repos.xlsx](data/github-repos.xlsx)（49 个仓库）· [data/videos.xlsx](data/videos.xlsx)（115 条 B站 + 15 条 YouTube + 18 条播客图文）。
> 所有关键论断附来源链接；薪资/热度数字会过时，方法论不会。

---

## 目录

1. [认识 FDE：它是什么，为什么突然爆火](#一认识-fde它是什么为什么突然爆火)
2. [真实工作状态：祛魅篇](#二真实工作状态祛魅篇)
3. [能力模型：共识技能清单](#三能力模型共识技能清单)
4. [你的独特起点：agent 源码学习如何映射到 FDE](#四你的独特起点agent-源码学习如何映射到-fde)
5. [转行路线图：按起点分路径](#五转行路线图按起点分路径)
6. [学习资源：GitHub 仓库精选 + 书单](#六学习资源github-仓库精选--书单)
7. [视频与播客资源清单](#七视频与播客资源清单)
8. [求职实战：公司、薪资、简历、面试](#八求职实战公司薪资简历面试)
9. [避坑指南](#九避坑指南)
10. [附录：统计摘要与来源索引](#十附录统计摘要与来源索引)

---

## 一、认识 FDE：它是什么，为什么突然爆火

### 1.1 定义

FDE（Forward Deployed Engineer，前线部署工程师；中文也译作**前沿部署工程师**、**前向部署工程师**——三种译名在中文互联网都在流通：范冰的书和虎嗅报道用「前线」，B站培训机构多用「前沿」，部分媒体用「前向」，检索时建议都搜一遍）。

一句话定义：**被派驻到客户现场、在客户真实环境里理解业务问题，并用代码 + AI 产品把问题真正解决的工程师**。它是「半个软件工程师 + 半个解决方案架构师 + 半个顾问」的混合角色，Palantir 官方把它形容为"像创业公司的 CTO——小团队、极少监督、端到端负责"（来源：[Fortune 2026-09 报道](https://fortune.com/2026/09/03/forward-deployed-engineers-fast-growing-six-figure-silicon-valley-job-integrate-ai-with-customers-tech-careers-palantir)、[Palantir 官方博客](https://blog.palantir.com/a-day-in-the-life-of-a-palantir-forward-deployed-software-engineer-45ef2de257b1)）。

核心概念是 **The Delta**（差值）：产品与客户现实之间的那道缝隙。FDE 的存在就是为了填这道缝——并且要把现场学到的模式沉淀回产品，让下一道缝变小。

### 1.2 起源：Palantir 的 Echo 与 Delta

Palantir 在 2000 年代中后期到 2010 年代初为情报机构客户首创了这套模式：客户说不清需求、数据也不能带出来，传统的需求调研（interviews，访谈）完全失效。Palantir 的洞察是——**客户要看到能跑的东西，才知道自己要什么**。于是把顶尖工程师直接派到现场，形成两个团队：

- **Echo team**：懂客户行业的专家，负责在客户现场找到高价值问题；
- **Delta team**：快速执行的工程师，负责把问题做成系统。

关键机制是「土路 → 高速公路」循环：先在现场给客户修一条"土路"（定制方案），再把土路的经验修成"高速公路"（沉淀为标准产品 Foundry/Gotham）。**这是 FDE 与咨询、外包的根本区别：现场劳动必须转化为产品资产。** 到 2016 年前后，Palantir 的驻场工程师据报已多于传统软件工程师。（来源：[FDE Academy 起源文](https://fde.academy/blog/how-palantir-invented-the-forward-deployed-engineer-model)、[虎嗅《万字长文｜FDE 的前世今生》](https://www.huxiu.com/article/4889923.html)）

### 1.3 为什么在 2025–2026 爆火

- **a16z 定调**：2025 年 6 月，a16z 合伙人 Joe Schmidt 发表 [《Trading Margin for Moat: Why the Forward Deployed Engineer Is the Hottest Job in Startups》](https://a16z.com/services-led-growth/)，核心论点：企业买 AI 就像"给奶奶买 iPhone——想用，但需要你装"；**"软件不再只是辅助工作者——软件就是工人"**，AI agent（智能体）需要像新员工一样被 onboarding（入职引导），FDE 就是干这个的；创业公司应该早期"用毛利换护城河"。
- **需求侧数据**（口径不同，引用时注意）：Lightcast 统计 2026 年 1–8 月 FDE 职位发布同比 **+1000%**（2023 年同比 +4600%），同期 tech 整体仅 +13%；另有 Indeed 口径 12 个月 **+729%**；LinkedIn 美国在招 FDE 超 1.1 万个（来源：[Fortune](https://fortune.com/2026/09/03/forward-deployed-engineers-fast-growing-six-figure-silicon-valley-job-integrate-ai-with-customers-tech-careers-palantir)、[观智潮/潮新闻](https://tidenews.com.cn/news.html?id=3527834)）。
- **巨头动作**：OpenAI 2025 年初组建 FDE 团队，2026 年 5 月成立 Deployment Company（收购 Tomoro 带入约 150 位 FDE）；Anthropic FDE 岗位薪资可达 $400K；Salesforce 围绕 Agentforce 组建 FDE 团队、6 个月扩张 3 倍；连 Deloitte（德勤）都开设了 "Senior OpenAI/Anthropic Forward Deployed Engineer" 合作岗（来源：[Fortune](https://fortune.com/2026/09/03/forward-deployed-engineers-fast-growing-six-figure-silicon-valley-job-integrate-ai-with-customers-tech-careers-palantir)、[Business Insider](https://www.businessinsider.com/forward-deployed-engineers-hottest-job-in-tech-ai-consulting-2026-8)）。
- **根本原因**：MIT NANDA 报告称约 **95% 的企业 GenAI 项目没有产生可入账价值**（被范冰、RichardXu、jiji262 三个中文仓库共同引用）。模型已经不稀缺，**能把模型塞进客户真实业务里的人才稀缺**——这就是 FDE 的市场。

### 1.4 国内声量

- 腾讯云 ADP 组织 42 支 FDE 团队深入客户一线；工信部发通知鼓励 AI 应用服务商搭建 FDE 团队；上海把「培育前沿部署工程师（FDE）队伍」写进了政策文件（来源：[新华网 IITC 报道](https://app.xinhuanet.com/news/article.html?articleId=2026090410baf1d5a04148e0881477e9f6ef6e1e)、[什么值得买汇总](https://post.smzdm.com)）。
- B站数据（本次采集）：FDE 相关视频从 2026 年 3 月开始起量，**2026 年 9 月单月新增 55 条**（强相关去重后），培训机构课程占播放量头部——热度真实，噪声也真实。
- 腾讯研究院 2026 年 7 月发布《FDE 模式行业观察》；国内招聘从字节、腾讯蔓延到蚂蚁数科与大模型创企（详见[第八节](#八求职实战公司薪资简历面试)）。

### 1.5 和相邻岗位的区别

| 岗位 | 做什么 | 与 FDE 的区别 |
|---|---|---|
| 售前 / SA（Solutions Architect，解决方案架构师） | 讲方案、做 POC（Proof of Concept，概念验证）演示 | 一般不写生产代码、不端到端负责上线 |
| 驻场外包 / 实施 | 在客户现场做配置、运维、二次开发 | 劳动不沉淀为产品资产，没有"土路→高速公路"循环 |
| AI 产品经理 | 定义产品、排优先级 | 不直接交付工程；不过 FDE 是 PM（Product Manager，产品经理）的常见来源 |
| 咨询顾问 | 出报告、给建议 | FDE 要"把东西做出来跑起来"，依附于自家产品 |
| 后端工程师 | 在自家代码库里开发 | FDE 在**客户的**环境里开发，面对模糊性和人 |

### 1.6 一分钟自测：适不适合

以下描述越多条命中，FDE 与你的匹配度越高（源自 [FDEGreenBook 画像测试](https://github.com/liuhuanyong/FDEGreenBook)与各仓库共识）：

- 看到"客户系统里一堆脏数据"兴奋多于烦躁；
- 能忍受几周到几个月在客户现场/出差；
- 喜欢同时管代码、管方案、管人的预期；
- 对"上线后没人用"感到愤怒并愿意负责推广；
- 能向 CTO 和一线业务员分别讲清同一件事。

---

## 二、真实工作状态：祛魅篇

这一节来自中文一手报道，建议转行前逐字读完——**媒体报道的平均值，就是你入职后的日常波动区间**。

### 2.1 日常与强度

- "六分沟通、四分技术"——深圳某公司首位专职 FDE 冯又又，**入职第一周就被派驻客户现场近一个月**（来源：[定焦One《第一批做FDE的人，离高薪差远了》](https://www.huxiu.com/article/4881334.html)）。
- 月出差 20 天以上是常态；复合压力 = 写代码 + 对接客户 + 处理线上故障，还常被误认为"高级驻场运维"（来源：[观智潮](https://tidenews.com.cn/news.html?id=3527834)）。
- 出差强度因公司而异：Palantir FDSE 按需最多 25%，OpenAI JD 写明期望 50%，国防方向的 Anduril 可达 80%（来源：[thecoder8890/roadmap 对比表](https://github.com/thecoder8890/forward-deployed-engineer-roadmap)、[OpenAI JD](https://openai.com/careers/forward-deployed-engineer-singapore-singapore/)）。
- 虎嗅记者张卓的观察：国内 FDE"好苦，好痛，正在救火路上"——经常在为前端销售的过度承诺填坑，"更像乙方外包人力"（来源：[虎嗅](https://www.huxiu.com/article/4873792.html)）。

### 2.2 收入的真实分布

- 国内：月薪 **9 千 – 8 万**严重分层；字节"豆包FDE"3.5万–7万×15薪（年包最高约 105 万），蚂蚁数科 4万–6万/月；但同期前程无忧上"数字化工程师（AI落地工程师、前沿部署工程师）"月薪只有 9 千–1.2 万（来源：[虎嗅 FDE 前世今生](https://www.huxiu.com/article/4889923.html)、[爱范儿](https://www.ifanr.com)、[新华报业](https://www.xhby.net/content/s6a226993e4b0f1b15e6997b9.html)）。
- 案例：FDE 实习生日薪 200 元（忙时一周近 50 小时）；有人拿的是产品经理薪资；自由职业 FDE 的项目报价从 2 千元到 19 万元不等；"外界传的百万年薪几乎没人真拿到"（来源：[定焦One](https://www.huxiu.com/article/4881334.html)）。
- 海外：FDE 广告薪资中位数超 $188K（传统 SWE 约 $145K）；Palantir 总包约 $175K–$315K；OpenAI mid–senior 总包 $350K–$550K（详见[第八节薪资表](#83-薪资行情)）。

### 2.3 获客与组织现实（独立执业视角）

- 30 岁前金融风控开发 @82LSF 转自由职业 FDE（服务餐饮连锁）：**六七成首单来自熟人**；建议沉淀 10+ 个行业 skill（技能包）复用（来源：[定焦One](https://www.huxiu.com/article/4881334.html)）。
- 23 岁 XIAO（杭州）：客户年营收过亿，但一套方案最多 30% 能标准化——**定制是常态，别指望"一套打天下"**。
- 组织权责博弈可能重于技术：某国企千万级 AI 项目最终交付 7 个不可用的智能体（来源：[虎嗅 FDE 前世今生](https://www.huxiu.com/article/4889923.html)）。

### 2.4 争议：FDE 是新咨询吗？

- 批评方：Blind/Reddit 常见" glorified consultants（贴牌顾问）——利润随人头线性增长"；Michael Burry 甚至称 Palantir 是"伪装成 SaaS 的咨询公司"。
- 辩护方（[Latent.Space](https://www.latent.space/p/forward-deployed-engineer-best-practices)）：FDE 依附产品团队、产出必须反哺平台（土路→高速公路），否则"只是头衔更好看的服务团队——薪水不错，但不复利"。
- 还有一条从业者警告：约 5 年 FDE 后"作为纯工程师变弱"——更多胶水脚本，更少系统设计深度。**对策：定期回补硬技能（见第五节路线图）。**

---

## 三、能力模型：共识技能清单

综合 16 个头部 GitHub 仓库的横向共识（按提及频次排序，完整清单见 [github-repos.xlsx](data/github-repos.xlsx)）：

### 3.1 硬技能

| # | 技能 | 提及率 | 说明 |
|---|---|---|---|
| 1 | **Python + SQL** | ~14/16 | 公认硬门槛，没有商量余地 |
| 2 | **RAG**（Retrieval-Augmented Generation，检索增强生成）全链路 | ~12/16 | 分块、嵌入、混合检索、重排序、向量库、**数据权限治理** |
| 3 | **Agent 工程** | ~12/16 | agent loop（智能体主循环）、工具调用、多 Agent、MCP（Model Context Protocol，模型上下文协议）、记忆 |
| 4 | **Evals**（效果评估体系） | ~11/16 | **"demo 者与能上线者的分水岭"**；error analysis（错误分析）优先 |
| 5 | Prompt / Context Engineering（提示/上下文工程） | ~8/16 | 含防注入 |
| 6 | 安全与护栏 | ~8/16 | OWASP LLM Top 10、红队、guardrails |
| 7 | 可观测性与 LLMOps | ~7/16 | Langfuse / MLflow / tracing、成本归因（"账单爆炸"是常见事故） |
| 8 | AI 系统设计 | ~7/16 | QPS / VRAM / 延迟 / 成本估算 |
| 9 | 云与部署 | ~6/16 | Docker / K8s / Terraform / 私有化与气隙部署（政企刚需） |
| 10 | 数据工程与微调 | ~5/16 | Spark / Airflow / LoRA——进阶项 |

### 3.2 软技能（很多技术转行者真正的短板）

- **Discovery（需求发现）**：客户口述的问题 ≠ 真实问题（[fdestack](https://github.com/Dan-Cleary/fdestack) 要求两者都写下来）；《The Mom Test》三原则；"无二值成功标准的任务 = 高风险未知项，必须显式记录"。
- **Scoping（范围界定）与客户沟通**：咨询方法论——MECE（相互独立、完全穷尽）、金字塔原理；信任公式 `Trust = (Credibility + Reliability + Intimacy) / Self-Orientation`（可信度+可靠度+亲密度）/（自我导向）。
- **端到端方法论**：[dataPro-lgtm/fieldbook](https://github.com/dataPro-lgtm/fde-interview-fieldbook) 的 **FIELD loop**：Frame the mission（界定任务）→ Inspect reality（勘察现场）→ Engineer the thin slice（做最小薄片）→ Launch and learn（上线学习）→ Distill into product（沉淀为产品）。
- **最常见失败模式**："在理解要改变的工作之前先画架构图"（fieldbook 原话）。
- 能力配比共识："**40% 写码 + 60% 面客**"（[jiji262/fde-guide](https://github.com/jiji262/fde-guide)）；Anthropic JD 原文要求 "high agency, low ego"（高主动性、低自我）。

---

## 四、你的独特起点：agent 源码学习如何映射到 FDE

这一节是为你定制的——你正在逐家精读六家 AI agent 的源码（[01-claude-code](../01-claude-code) ~ [06-opencode](../06-opencode)），这件事本身就是稀缺的 FDE 素材。对应关系：

| 你的学习内容 | 对应的 FDE 能力 | 证据/要求出处 |
|---|---|---|
| Agent 主循环与工具调用拆解（01/02/04） | Agent 工程底层理解——calmrocks 明确建议"先手写 agent loop 再用框架，**Patterns are durable; wrappers churn**（模式持久，封装易朽）" | [calmrocks/ai-engineer-notebooks](https://github.com/calmrocks/ai-engineer-notebooks) |
| MCP 协议实现（04-zcode 等） | Anthropic FDE JD 的核心交付物就是 **MCP servers、sub-agents、agent skills** | [Anthropic Greenhouse JD](http://job-boards.greenhouse.io/anthropic/jobs/5302966008) |
| Skills / harness（马具层）工程（03-deepseek-harness、anbeime/skill 生态） | global-fde 提出"agent 工程拆为 harness 工程"；开源社区已有 [sofagent](https://github.com/KongFangXun/sofagent)（FDE Harness）与 [fdestack](https://github.com/Dan-Cleary/fdestack)（FDE 技能包）两个直接样本 | [global-fde/awesome-fde-resources](https://github.com/global-fde/awesome-fde-resources) |
| 多渠道常驻网关（05-openclaw） | 企业集成、私有化/边缘部署的直觉——国内 FDE 的核心场景 | yeasy《前线部署工程实践指南》工程篇 |
| 工作流与可观测（04-zcode 的 dynamic-workflow） | evals 与 LLMOps 分水岭能力 | calmrocks："评估是全程脊柱" |

**行动建议**（把学习变成求职证据）：

1. 按 wmc 教程的标准——"**用证据而不是功能截图评审项目**"——把每家 agent 的拆解升级为一篇带运行截图/复现步骤的公开笔记；
2. 在 06-opencode 或 04-zcode 上做一个小而完整的**带评估的企业场景改造**（比如给 opencode 加一个面向某行业的只读 MCP 工具集 + 评测集），作为 Capstone（毕业作品）候选；
3. 这两样合起来正好覆盖面试必考的 "生产级 AI 设计题" 和 "客户情景题" 的素材。

---

## 五、转行路线图：按起点分路径

### 5.1 共识六阶段

各仓库的路线图骨架高度一致（时长共识：有编程基础者 2–4 个月；纯零基础 12–24 个月；常见的中间态是 8–12 周集训 + 24 周完整路线）：

```
① 岗位认知与自评        →  搞清 FDE 是什么、和售前/外包的边界、自己适不适合（1-2 周）
② 编程与 LLM 基础       →  Python、SQL、Git、LLM API、prompt（有基础可跳）
③ RAG → 评估 → Agent    →  应用 AI 三部曲，评估穿插其中（4-8 周）
④ 生产化工程            →  部署、可观测、安全、成本控制、私有化（2-4 周）
⑤ 客户交付实战          →  discovery → scoping → PoC → 集成 → 移交（贯穿）
⑥ 作品集 + 面试求职     →  Capstone 上线带证据、模拟面试、定向投递（2-4 周）
```

### 5.2 按起点分路径

| 起点 | 难度 | 重点 | 参考时长 |
|---|---|---|---|
| **后端/全栈工程师**（你的情况最接近） | ★★☆ 最平滑 | 直接跳到 ③④；补客户侧技能与 evals；6 个月周计划照 [thecoder8890](https://github.com/thecoder8890/forward-deployed-engineer-roadmap) 执行 | 2–4 个月 |
| **算法/ML 工程师** | ★★☆ | ML 工程师是转型最容易的背景（[alexeygrigorev JD 实证](https://github.com/alexeygrigorev/ai-engineering-field-guide)）；补全栈交付与沟通 | 2–4 个月 |
| **数据工程师** | ★★☆ | "最平滑"；补 LLM 应用层 | 3–4 个月 |
| **应届生/学生** | ★★★ | 优先实习入口（字节已有 FDE 实习生岗）；作品集 > 证书；Google 型 FDE 校招要求 1 年+经验，提前按 [google-fde-interview-guide](https://github.com/YagyanshB/google-fde-interview-guide) 备 | 6–12 个月 |
| **产品/咨询/非开发岗** | ★★★★ | 先补 Python+SQL 硬门槛；可从 AI 产品经理/售前过渡；"**先低成本验证适不适合**"（冯又又）；勿信速成 | 12–24 个月 |
| **加密/金融科技/后端老兵** | ★★☆ | 参照 [libaice/Awesome-FDE](https://github.com/libaice/Awesome-FDE) 的技能翻译表：真金白银的生产系统经验是优势，短板通常是业务翻译 | 2–3 个月 |

### 5.3 Capstone（毕业作品）建议

- 经典选题：**企业 RAG + MCP 助手**（[wmc 24 周教程](https://github.com/wmc837911722-del/fde-learning)）或 **Customer Operations Copilot**（thecoder8890 的 8 里程碑毕业项目）。
- 验收标准不是"能跑"，而是：有评估报告（基线→改进）、有成本账单、有权限设计、有一个模拟客户（哪怕朋友的公司）的真实需求简报。
- 发布：GitHub 开源 + 一篇复盘长文（jiji262："公开写作 = 第四件作品"）。

### 5.4 认证：可锦上添花，不可当敲门砖

| 认证 | 性质 | 备注 |
|---|---|---|
| Anthropic Academy 免费证书 | 厂商课证 | jiji262 建议当"Day 1 凭证"，成本低 |
| **腾讯云 ADP 前沿部署工程师 (FDE) 认证**（2026-08-18 由"智能体开发平台 AI应用工程师认证"更名上线，[官方详情页](https://cloud.tencent.com/edu/training/cert/detail?type=CFD)） | 厂商认证（TCCA 专项认证，国内首个标准化 FDE 认证） | **考试费 ¥1200（含 1 次机会，补考重新购买）；配套在线课程限时免费开放**。线下理论考试：单选+多选 60 题 / 90 分钟 / 70 分及格；证书有效期 2 年。课程四章 19 节（AI/Agent 基础 → ADP 产品能力 → 实战开发 → 评测调优），已整理成本地讲义：[tencent-adp-fde-course/](tencent-adp-fde-course/README.md) |
| 工信部 IITC「FDE 岗位能力评价」 | 官方背书评价（2026-09-04 启动） | 经合作单位报名、先培训后测评；**警惕衍生"教练营"付费链与山寨报名网站**（[新华网](https://app.xinhuanet.com/news/article.html?articleId=2026090410baf1d5a04148e0881477e9f6ef6e1e)） |

> 腾讯云 FDE 认证的考试知识分布以"场景理解与方案设计"（25%）和"ADP 核心功能与应用搭建"（22%）为大头——方向是**交付实战**而不是纯理论，与其免费课程配套食用性价比高。

---

## 六、学习资源：GitHub 仓库精选 + 书单

完整 49 个仓库见 [github-repos.xlsx](data/github-repos.xlsx)。这里只放精选，按使用顺序分层：

### 6.1 第一层：认知入门（1–2 周读完）

| 仓库 | Stars | 用法 |
|---|---|---|
| [xdash/FDE-…-Engineer](https://github.com/xdash/FDE-the-Guidance-Book-of-Forward-Deployed-Engineer) | 4,857 | 范冰（《增长黑客》作者）的中文电子书：8 章 + 165 案例，交付六阶段方法论；另有纸书《前线部署工程师》（[在线阅读版](https://github.com/LeoLee0812/fde-book)） |
| [liuhuanyong/FDEGreenBook](https://github.com/liuhuanyong/FDEGreenBook) | 25 | 交互式网站：教程 + 游戏 + 画像自测，测适不适合 |
| [RichardXu001/the-fde-handbook](https://github.com/RichardXu001/the-fde-handbook) | 54 | 《企业 AI 落地实战手册》六部 28 章：组织、收费、移交的中国视角 |

### 6.2 第二层：系统路线（8–24 周跟练）

| 仓库 | Stars | 用法 |
|---|---|---|
| [pierpaolo28/Awesome-FDE-Roadmap](https://github.com/pierpaolo28/Awesome-FDE-Roadmap) | 1,231 | 英文最全：三阶段路线 + C.A.S.E. 面试框架 + 厚书单 |
| [thecoder8890/…-roadmap](https://github.com/thecoder8890/forward-deployed-engineer-roadmap) | 47 | 四层技能栈 + **6/12/24 个月计划** + 薪酬数据，可操作性最强 |
| [wmc837911722-del/fde-learning](https://github.com/wmc837911722-del/fde-learning) | 19 | 中文 24 周教程（已全发布）+ 全套模板（discovery-brief、eval-plan 等） |
| [jiji262/fde-guide](https://github.com/jiji262/fde-guide) | 22 | 中文付费课开源版：38 讲 11.6 万字 + 手绘图，**含劝退章与真伪岗位三判据** |
| [calmrocks/ai-engineer-notebooks](https://github.com/calmrocks/ai-engineer-notebooks) | 642 | 动手 notebook：免框架、免费 Groq API，RAG/评估/Agent/客户交付全覆盖 |

### 6.3 第三层：面试冲刺

| 仓库 | Stars | 用法 |
|---|---|---|
| [guocong-bincai/ai-interview-guide](https://github.com/guocong-bincai/ai-interview-guide) | 708 | 中文 720 题含 FDE 专题；"30 秒版/3 分钟版/追问版"三答案法 |
| [dataPro-lgtm/fde-interview-fieldbook](https://github.com/dataPro-lgtm/fde-interview-fieldbook) | 47 | 中文面试实战手册：FIELD loop + 10 个案例包 + 评分卡 + 模拟面试环 |
| [YagyanshB/google-fde-interview-guide](https://github.com/YagyanshB/google-fde-interview-guide) | 372 | Google FDE 全流程备考记录 |
| [ombharatiya/ai-system-design-guide](https://github.com/ombharatiya/ai-system-design-guide) | 3,404 | AI 系统设计 128 题 + 15 案例（高阶） |
| [alexeygrigorev/ai-engineering-field-guide](https://github.com/alexeygrigorev/ai-engineering-field-guide) | 5,653 | **6,964 条真实 JD 数据**（含 146 个 FDE 岗）——了解市场要什么的最快方式 |
| [pingananth/fde-decomp-interview-guide](https://github.com/pingananth/fde-decomp-interview-guide) | 5 | Palantir 式 decomposition（问题拆解）轮评分标准 |

### 6.4 书单（共识高频）

- 《Designing Data-Intensive Applications》——pierpaolo28 称"FDE 圣经"；
- Chip Huyen《AI Engineering》——应用 AI 主教材；
- 《The Mom Test》——客户需求发现；
- 《The Pyramid Principle》（金字塔原理）+《The Trusted Advisor》——咨询沟通双件套；
- 范冰《前线部署工程师》（纸书）。

### 6.5 常备工具（练手时直接用）

评估与可观测：Langfuse、RAGAS、promptfoo、Arize Phoenix；Agent 参考：[humanlayer/12-factor-agents](https://github.com/humanlayer/12-factor-agents)、[microsoft/mcp-for-beginners](https://github.com/microsoft/mcp-for-beginners)、Hugging Face agents-course。

---

## 七、视频与播客资源清单

完整清单（115 条 B站、15 条 YouTube、18 条播客图文）见 [videos.xlsx](data/videos.xlsx)。这里放精选：

### 7.1 B站精选（播放量为 2026-09-26 快照）

**认知科普**
- [卢菁博士：FDE 前沿部署工程师，岗位能力、工作模式全讲透（含 40 分钟实战）](http://www.bilibili.com/video/av116351268029106) — 23.6 万播放，2026-04
- [九天Hector：10 分钟彻底搞懂 FDE（概念+三大核心能力+8 阶段工作流）](http://www.bilibili.com/video/av117225243547142) — 1.5 万，2026-09
- [极海Channel：3 分钟了解 FDE，20 年前的概念最近火了？](http://www.bilibili.com/video/av117047673494384) — 1.9 万
- [五里墩茶社：FDE 是什么？薪酬、真实岗位描述、怎么准备（客观分享）](http://www.bilibili.com/video/av116802810025129) — 2.7 千

**深度对谈**
- [十字路口：OpenAI 和 Anthropic 共同看好的 FDE｜对谈 Roll](http://www.bilibili.com/video/av116674883750606) — 3.7 万
- [课代表立正：请一位真正的内行人全面讲解 FDE](http://www.bilibili.com/video/av116943352761078) — 1.05 万
- [硅基立场Pro：对话元理智能张帆——去他X的FDE](http://www.bilibili.com/video/av117326007504330) — 2.1 千（反方视角）
- [GoldenSpiderAI：从 Palantir 到 AI 时代——FDE 模式深度解析](http://www.bilibili.com/video/av115194579650771) — 2.7 千（2025-09，B站最早的系统性介绍之一）

**从业者实战**
- [Datawhale 特辑：真正在交付的 FDE 是怎么做的（工作实践到产品化）](http://www.bilibili.com/video/av117108826447630) — 1.3 千
- [Leon同学哟：两个月，从 0 到 1 交付一个企业级 AI 智能体｜FDE 驻场复盘](http://www.bilibili.com/video/av117038731297831) — 5 千
- [isaac_coding：FDE 必看 Ontology（本体论）落地技术细节](http://www.bilibili.com/video/av117190145609137) — 7.5 千（Palantir 本体论方法论）
- [Alan杨哲：05 年文科毕业生，做 FDE 的一天](http://www.bilibili.com/video/av117015528341919) — 7.7 千（vlog）

**批判与避坑（转行前必看）**
- [老头们的快乐生活：这恐怕是 FDE 最真实的现状了](http://www.bilibili.com/video/av117281581501679) — 8.4 万
- [公众号-ToB老人家：终于，FDE 也要烂大街了！](http://www.bilibili.com/video/av116854114751879) — 1.6 万
- [苍述SV：AI 和 FDE 可能会毁了你的人生](http://www.bilibili.com/video/av117139746855816) — 1.6 万
- [人月聊IT：年薪百万 FDE 工程师——你是真的想多了！](http://www.bilibili.com/video/av117238195554135) — 3.7 千
- [老骥farmer：FDE 不就是顶级外包吗？](http://www.bilibili.com/video/av117298274769022) — 7.5 千

### 7.2 YouTube 精选（英文）

- [Greg Isenberg: FDE — The $1M/Year AI Job Explained](https://www.youtube.com/watch?v=zXysLUTLjw4)（21.3 万）
- [YC: The FDE Playbook for AI Startups（前 OpenAI/Palantir 高管 Bob McGrew）](https://www.youtube.com/watch?v=Zyw-YA0k3xo)（14.4 万）
- [Palantir 官方：The Role of a Forward Deployed Software Engineer](https://www.youtube.com/watch?v=5OYy_UtINo4)（9.2 万，2015 年元老级）
- [Tech With Tim: How to Become a FDE in 2026](https://www.youtube.com/watch?v=vLlIBT0HSSc)（5.2 万）
- [Prepfully: Palantir Decomposition Interview Tips](https://www.youtube.com/watch?v=IslCQszgr4I)（3.9 万，面试备 Canvas）
- [Aced: FDE Interviews at LangChain](https://www.youtube.com/watch?v=knEiqlfpV5k)（2.1 万）

### 7.3 播客（小宇宙/Apple Podcasts 均可搜到）

- 硅谷101 E240《OpenAI 联手 PE 砸下 40 亿美元，聊聊硅谷最火新职位 FDE》+ E248《一个"催发货"AI 要跑通 260 步》（中国篇）
- 科技早知道 S10E27《硅谷"最性感"工作落地中国：一个 FDE 的救火日常》
- 十字路口（对谈 Roll / 对话海纳 AI 梁公军）
- Hao的游戏PM笔记【番外12】游戏公司 FDE 的六个落地方向（垂直行业样本）
- VK科技阅读时间《FDE：前向部署工程师的诞生》

### 7.4 生态观察（本次统计的核心发现）

- **时间线**：B站强相关视频 2025-09 出现第一条系统介绍 → 2026-03 起量 → 2026-08/09 爆发（29/55 条）。岗位热度与内容热度同步，目前仍在上升期。
- **噪声比例**：播放量 Top 20 里约一半是培训机构课程（"全 748 集""七天从小白到大神""从零基础到 40k"话术高度雷同，多机构互相搬运）。**看认知科普找个人 UP 主和播客，看实战找驻场复盘，课程广告一律跳过**——辨别方法见[第九节](#九避坑指南)。
- 抖音/小红书存在大量同名内容但平台反爬无法条目级统计（[videos.xlsx](data/videos.xlsx) 已收录搜索引擎索引到的条目并注明局限）。

---

## 八、求职实战：公司、薪资、简历、面试

### 8.1 搜索关键词全景（找工作先把这几个都搜一遍）

FDE 在国内的马甲很多，只搜 "FDE" 会漏掉一半岗位：**FDE / 前线部署工程师 / 前沿部署工程师 / AI解决方案工程师 / AI交付工程师 / 大模型交付工程师 / AI落地工程师 / Agent架构师 / AI售前解决方案专家 / Applied AI Engineer**。

### 8.2 目标公司清单

**海外**（完整 JD 链接见来源）：

| 梯队 | 公司 | 备注 |
|---|---|---|
| FDE 模式发源地 | Palantir | JD base $135K–$200K + RSU；出差最多 25%；另有平行职系 Deployment Strategist |
| 前沿实验室 | OpenAI、Anthropic | OpenAI 期望 50% 出差；Anthropic $280K–$320K、交付 MCP servers/sub-agents |
| 数据/云平台 | Databricks、Google、Microsoft、Salesforce（Agentforce）、Nvidia、Scale AI | Google 面试资料最具体（见 6.3） |
| AI 应用创企 | Harvey、Sierra、Glean、Writer、Decagon、Hebbia、Cresta、Cursor、Vercel | 垂直场景多 |
| 国防/高合规 | Anduril、Palantir（NATO 等专属驻场岗） | 出差可达 80% |
| 咨询系 | Deloitte（Senior OpenAI/Anthropic FDE 合作岗）、Accenture（$122.7K–$366.3K band） | 服务型 |

**国内**：

| 公司 | 岗位与薪资信号 | 来源 |
|---|---|---|
| 字节跳动 | "AI FDE工程师"（飞书/火山引擎/数据平台）、"豆包AI大模型FDE"（3.5万–7万×15薪）、有 FDE 实习生岗 | [爱范儿/腾讯新闻](https://view.inews.qq.com/a/20260829A05RWF00) |
| 腾讯 | 社招"前线部署工程师"（产品类，3–5 年经验）；腾讯云 ADP 组织 42 支 FDE 团队 | [careers.tencent.com](https://careers.tencent.com)、[搜狐](https://m.sohu.com) |
| 阿里/阿里云 | FDE 与"AI解决方案工程师"（端侧 LLM 方案） | [观智潮](https://tidenews.com.cn/news.html?id=3527834)、[BOSS直聘](https://www.zhipin.com) |
| 蚂蚁数科 | B 端 FDE，月薪 4 万–6 万 | [新华报业](https://www.xhby.net/content/s6a226993e4b0f1b15e6997b9.html) |
| 大模型创企 | MiniMax"AI售前解决方案专家"；月之暗面×中软国际共建"FDE创新实验室"（能源行业）；智谱/通义/混元 JD 高度趋同 | [金色财经](https://m.jinse.com.cn)等 |
| 参照系 | 月之暗面与中软国际、腾讯研究院《FDE 模式行业观察》、工信部服务商政策 | 见附录 |

### 8.3 薪资行情

| 市场 | 数字 | 口径来源 |
|---|---|---|
| 海外·广告中位数 | **$188K**（传统 SWE 约 $145K） | Lightcast，经 Fortune |
| Palantir FDE | 总包 $175K–$315K（美国 median 约 $201K；staff 上限 $750K+，股权占 60–70%） | levels.fyi（二手交叉核对） |
| OpenAI FDE | base $162K–$280K + PPU 权益；mid–senior 总包 $350K–$550K | 官方 JD + fde.academy |
| Anthropic FDE | $280K–$320K（部分可达 $400K） | Greenhouse JD |
| 国内·大厂 | 年包 42 万–105 万（字节 3.5万–7万×15薪；蚂蚁 4–6 万/月） | 观智潮、新华报业 |
| 国内·分层下限 | 月薪 9 千–1.2 万的"AI落地工程师"（实为低配驻场） | 前程无忧，经虎嗅 |
| 国内·独立执业 | 日薪 200（实习）到单项目 19 万不等，首单六七成靠熟人 | 定焦One |

> 汇率与购买力自辨：海外数字是总包（含股权），国内数字多为现金；两者不能直接划等号。

### 8.4 JD 共性关键词（简历就往这些词上对齐）

customer-facing shipping（面向客户的交付）· prototype→production 端到端 ownership · LLM/agent/evals 生产经验 · full-stack + 数据管线 · stakeholder communication · ambiguity 下的 high agency · Python 强（最好加 TypeScript/Java）· travel 25%–50%

### 8.5 面试全流程（五段式）

```
① Recruiter 初筛    → 准备：动机 + 1 个 Agentic 案例 + 1 个经典 ML 案例 + 反问（30-45 分钟）
② 编码轮 1-2 轮     → 重质量与沟通，非算法炫技；Google 系考 DSA + Vibe Coding
③ 系统设计          → 绑定公司产品的实战架构（多租户 RAG 隔离、<100ms 欺诈检测等）
④ 客户情景轮 ★FDE特有 → 面试官扮演挑剔客户/暴怒 CTO，边讲边设计
⑤ 行为/价值观轮     → STAR 故事 8 个备好，"Why FDE"最重要
```

- **Palantir 最著名的 decomposition round（拆解轮）**：给模糊现实问题（真题示例："为视力不佳、想自己做饭的老人设计一项技术"），只写伪代码，考出声思考、澄清提问、结构化与同理心——"最优算法不是重点"（来源：[interviewing.io](https://interviewing.io/palantir-interview-questions)）。
- **OpenAI**：deployment case study（故意欠规格的客户场景：先问什么、先做什么、如何衡量成功、哪里会失败）。
- **Anthropic**：客户模拟轮约**六成技术通过者倒在这里**（来源：[爱范儿](https://www.ifanr.com)）。
- **Take-home（带回家作业）**：3–5 小时常见（两个 API 间做集成、清洗脏数据集），之后有 walkthrough 答辩。
- 全程时长：Palantir 3–5 周、OpenAI/Anthropic 2–3 周、Google 6–8 周。

### 8.6 高频面试题清单（练到能脱口而出）

1. 客户要一个"减少客服负载"的 AI 助手，第一周你做什么？
2. 客户说 "AI doesn't work"，你怎么调试？（生产 agent 表现差的诊断）
3. 部署中途发现客户数据质量很差，deadline 已定，怎么办？
4. 客户要一个产品团队拒绝做的 one-off 定制功能，怎么处理？
5. 变更后延迟和错误率上升，走一遍 triage（分诊排查）。
6. 多租户 RAG 如何保证竞争对手看不到彼此的数据？
7. 给银行设计 <100ms 实时欺诈检测，LLM 用在哪一层？
8. Agent 用 15 步做完 3 步的任务，怎么调试？
9. 如何为 agentic 系统设计评估集（新题型，2026 年高频）？
10. 5PB 本地数据 48 小时进 BigQuery，怎么架构？

（来源：[pierpaolo28](https://github.com/pierpaolo28/Awesome-FDE-Roadmap)、[libaice](https://github.com/libaice/Awesome-FDE)、[ombharatiya](https://github.com/ombharatiya/ai-system-design-guide)、[thecoder8890](https://github.com/thecoder8890/forward-deployed-engineer-roadmap)、[jiji262](https://github.com/jiji262/fde-guide)）

### 8.7 简历与作品集

- **故事库法**：每个项目写 5 个故事，共备 8 个 STAR（Situation-Task-Action-Result）故事；"Why FDE"是行为面最重要的一题（jiji262）。
- Anthropic 重视 200–400 字 "Why Anthropic" 小作文——提前写好。
- 作品集三条硬标准（wmc 教程）：**用证据而不是功能截图评审**；有评估报告与成本账单；有一个真实（或模拟真实）客户的需求简报。
- 求职漏斗：30 个目标团队 × 3 类角色定向投递（thecoder8890）；国内独立执业首单六七成来自熟人——**内推与社群优先于海投**（Lawted）。
- 可用工具：[career-ops](https://github.com/career-ops-hq/career-ops)（72.8K★ 开源 AI 求职 agent：扫岗位、评分、改简历、跟踪投递，可跑在本地 coding CLI）。

---

## 九、避坑指南

### 9.1 培训话术识别（B站/抖音高发区）

| 话术特征 | 实情 |
|---|---|
| "零基础三个月转行 FDE，年薪百万/40k" | 定焦One 调查："百万年薪几乎没人真拿到"；实习日薪 200 元才是入场常态 |
| "全 526 集/748 集""七天从小白到大神""学完即可就业" | 多机构互相搬运的营销课程（马士兵/码士/图灵学院等），本次采集的 B站播放头部约一半是此类 |
| "FDE 就是捡钱的蓝海" | 虎嗅：某 AI 产品负责人称团队里真优秀的 FDE 只有 2–3 人；"**名词会烂大街，能力不会**"（[虎嗅《终于，FDE也要烂大街了》](https://m.huxiu.com/article/4871958.html)） |
| "官方认证保过班" | IITC 认证衍生出付费"教练营"，并出现山寨报名网站；腾讯云认证官方详情页尚不完整——**一切以官方渠道为准** |

### 9.2 岗位真伪判据（jiji262 三判据，投递前对照）

1. JD 里有没有**端到端交付责任**（从需求发现到上线运维），还是只做"部署配置"？
2. 团队是否**依附产品**（现场经验回流产品），还是独立项目组（= 外包人力）？
3. 汇报线与考核是否包含**客户成功指标**（续约/采纳率），还是只有工时？

名不副实信号：实施顾问直接改名 FDE；月薪 9 千–1.2 万的"数字化工程师（AI落地）"；"销售支持"序列里的 FDE（可能主要是售前 demo）。

### 9.3 预期管理清单（入职前问自己）

- [ ] 能接受月出差 20 天+ / 驻场数周吗？
- [ ] 能接受"为销售的过度承诺填坑"吗（国内特有）？
- [ ] 接受 3–5 年后纯工程深度可能下降、需要刻意回补吗？
- [ ] 收入预期按"分层下限"而不是"宣传上限"来做家庭财务规划？
- [ ] 如果公司业务收缩，FDE 的可迁移出口（PM / 解决方案架构师 / 创业）想清楚了吗？（fde.academy："FDE 不是终点，是发射台"）

### 9.4 一句话总结

> **真实门槛 = 工程能力 + 行业理解 + 沟通，三者都不可速成。** 转行动作应该是"先低成本验证"（接一个小项目/内推一次驻场），而不是"先交一笔培训费"。

---

## 十、附录：统计摘要与来源索引

### 10.1 本次调研统计摘要

| 维度 | 数字 |
|---|---|
| GitHub 仓库收录 | 49 个（核心相关 36，合计 97,343 stars；2026 年新建 47 个——生态极年轻） |
| 其中中文内容仓库 | 22 个 |
| B站视频 | 原始命中 242 条 → 去重后强相关 **115 条**，总播放约 80 万 |
| B站时间线 | 2025-09 首条系统介绍 → 2026-03 起量 → 2026-09 单月 55 条 |
| B站内容构成 | 培训机构课程 16 / 科普讲解 24 / 从业者分享 12 / 批判避坑 7 / 面试相关 4 / 深度对谈 3 / 其他 49（启发式标注） |
| YouTube 收录 | 15 条（头部 21.3 万播放，Greg Isenberg） |
| 播客与深度图文 | 18 条（硅谷101、科技早知道、十字路口等 6 档播客 + 虎嗅/定焦One/观智潮等深度文） |
| 抖音/小红书 | 平台反爬，仅搜索引擎索引条目 2 条（数据局限，如实标注） |

> 明细与可筛选数据：[data/github-repos.xlsx](data/github-repos.xlsx) · [data/videos.xlsx](data/videos.xlsx)

### 10.2 核心来源索引

**深度报道（中文）**
- 观智潮/潮新闻：《大厂抢人、薪资倒挂：FDE为何成为AI落地时代的新贵？》 https://tidenews.com.cn/news.html?id=3527834
- 定焦One：《第一批做FDE的人，离高薪差远了》 https://www.huxiu.com/article/4881334.html
- 虎嗅·张卓：《硅谷最火职位在中国：好苦，好痛，正在救火路上》 https://www.huxiu.com/article/4873792.html
- 虎嗅：《万字长文｜FDE的前世今生》 https://www.huxiu.com/article/4889923.html
- 虎嗅：《终于，FDE也要烂大街了》 https://m.huxiu.com/article/4871958.html
- 新华网：工信部 IITC FDE 岗位能力评价启动 https://app.xinhuanet.com/news/article.html?articleId=2026090410baf1d5a04148e0881477e9f6ef6e1e

**报道与数据（英文）**
- Fortune: Forward Deployed Engineers — fast-growing six-figure job（2026-09-03） https://fortune.com/2026/09/03/forward-deployed-engineers-fast-growing-six-figure-silicon-valley-job-integrate-ai-with-customers-tech-careers-palantir
- a16z: Trading Margin for Moat（2025-06） https://a16z.com/services-led-growth/
- Business Insider: FDEs are the hottest job in tech（2026-08） https://www.businessinsider.com/forward-deployed-engineers-hottest-job-in-tech-ai-consulting-2026-8
- Latent.Space: Forward Deployed Engineer Best Practices（Project Frontline） https://www.latent.space/p/forward-deployed-engineer-best-practices
- FDE Academy: How Palantir Invented the FDE Model https://fde.academy/blog/how-palantir-invented-the-forward-deployed-engineer-model

**一手 JD**
- OpenAI FDE – Singapore: https://openai.com/careers/forward-deployed-engineer-singapore-singapore/
- Anthropic FDE – Applied AI: http://job-boards.greenhouse.io/anthropic/jobs/5302966008
- Palantir FDSE – New York: https://jobs.lever.co/palantir/dab396d4-2f14-4796-aac0-0d82883dccf0

**数据文件**
- [data/github-repos.xlsx](data/github-repos.xlsx)：49 个仓库（Stars/Forks/类别/点评/链接）+ 统计摘要
- [data/videos.xlsx](data/videos.xlsx)：B站 115 条（含播放/弹幕/日期/类型标注）+ YouTube 15 条 + 播客图文 18 条 + 统计摘要（含采集方法与局限说明）

---

*本手册由 ZCode 于 2026-09-26 调研生成：GitHub Search API + 三路并行网络调研（GitHub 仓库精读 / 英文互联网 / 中文互联网）+ B站搜索 API 采集。薪资与热度数据会过时，建议每季度对照数据文件更新一次；方法论章节（三、五、六、八、九节）相对稳定。*

*延伸阅读：云平台选型是 FDE 常见答题面（"客户问该用哪朵云"），系统化的八家平台对比与决策树见 [cloud-handbook](../cloud-handbook/云厂商AI平台对比手册.md)（FDE 视角写就，与本文第八章求职场景互补）。*
