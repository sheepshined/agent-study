# Agent 架构与工具调用：主循环与规划 · 工具系统与 MCP/Skill · 子代理与上下文隔离 · 记忆与压缩 · 权限与持久化 · 多 agent 编排

> 信息基准日：2026-09-28。本册为 AI 应用岗面试题库主题三（20 题）。答案素材取自本工作区六家 agent《架构拆解》（行号级一手证据）与各专题手册（相对链接）；协议版本与框架动态为 2026-09-28 当日核实（口径同各专题手册），随时间漂移。英文术语首次出现标注中文。

## 高频题速览表

| 题号 | 题目 | 难度 | 为什么高频 |
|---|---|---|---|
| Q041 | 什么是 agent？它与 chatbot、workflow 的本质区别是什么？ | 初 | 岗位定义题：控制流在谁手里是 agent 工程的第一性区分，答不出“能 workflow 就别 agent”的取舍原则直接出局 |
| Q042 | agent 的主循环（agent loop）是什么？最小实现长什么样？ | 初 | 循环体是 Agent 工程的“Hello World”：能否说清消息回填不变量与停止条件设计，区分背题与动手过 |
| Q043 | 工具调用的完整时序是怎样的？模型“调用工具”时实际发生了什么？ | 初 | “模型只点菜不做饭”是工具系统的核心心智模型，tool_result 回填、id 对齐、两级错误全是生产坑点 |
| Q045 | MCP（Model Context Protocol）是什么？解决什么问题？ | 初 | 生态标配题：三角色、三大原语、2026-07-28 无状态大改都是当日热点，FDE 岗几乎必考 |
| Q048 | 子代理（subagent）的价值与代价是什么？上下文隔离怎么设计？ | 中 | 90.2% 提升 / 15× token 的量化账本加 handoff 回传协议，是 Agent 工程的硬通货与岗位分水岭 |
| Q049 | 什么时候真的需要多 agent？怎么判断？ | 中 | “看起来该上多 agent 的时刻多半不该”是 Anthropic 与 Cognition 双重背书的第一反直觉结论 |
| Q050 | supervisor、orchestrator-worker、swarm 等编排范式怎么选？ | 中 | 范式选型是方案设计题的骨架，“六种范式一个变量（控制流在哪）”最能区分体系化思维 |
| Q059 | 控制流什么时候交给模型（agent）、什么时候写死（workflow）？怎么取舍？ | 高 | 选型总纲题：六问判据可直接套进业务方案，混合形态是生产主战场 |

## 题目正文

> **Q041. 什么是 agent？它与 chatbot、workflow 的本质区别是什么？**（难度：初 ｜ 频次：高）
> - 考察点：能不能用“控制流在谁手里”这个第一性区分说清 agent 的定义，而不是背“会调用工具的程序”这类含混说法。
> - 参考回答：
>   - Anthropic《Building Effective Agents》的定义至今是坐标原点：workflow（工作流）是“LLM 与工具经预先定义的代码路径编排”的系统；agent 是“LLM 动态指挥自己的过程与工具使用、自己掌握如何完成任务”的系统——本质区别只有一个变量：控制流（下一步做什么）在开发者代码手里，还是在模型手里。
>   - chatbot（聊天机器人）是“一问一答”：一次请求一次响应，没有工具、没有跨轮的任务推进；agent 的核心是循环——模型输出工具调用、执行、结果回填、再问模型，直到任务收尾，python-handbook §9.3 的 20 行循环就是 agent 的最小形状。
>   - agent = 模型 + 工具 + 循环（环境反馈）三件套；区别不在“有没有接工具”，而在“接完工具之后由谁决定下一步”：固定管道里调一次 LLM 抽参仍是 workflow，模型在循环里自主决定后续步骤才是 agent。
>   - 两种形态各有代价：workflow 的代价是僵化（变更要走开发流程、覆盖不了没预设的情况），agent 的代价是不可预测（成本、延迟、错误级联都难以封顶）——所以 Anthropic 的总原则是“先找最简方案，确有必要再升级”，能 workflow 就别 agent。
>   - 本工作区六家 coding agent 提供反面参照：没有一家提供画布式工作流引擎，编排骨架一律是“主循环 + 委派”，开发者写死的控制流只出现在执行前闸门（审批/权限/沙箱）、上下文治理（压缩触发）、失败路径（重试/熔断）三类护栏位——因为 coding 任务步骤不可枚举，写死路径做不了。
>   - 产品侧的选型谱系（腾讯 ADP 四模式）印证同一坐标：标准 agent（模型决定）→ 单工作流（写死）→ multi-agent（模型规划 + 多角色）→ Claw（全权自主），控制流从代码逐步移交给模型。
> - 追问与陷阱：
>   - 追问：chatbot 加了 function calling（函数调用）算 agent 吗？常见错误：把“有没有 function calling”当分界——工具调用若被代码固定编排（抽参→填表→回复），控制流仍在开发者手里，是 workflow 形态；分界看模型是否在循环中自主决定后续步骤。
>   - 追问：multi-agent 是不是比单 agent 更高级？常见错误：“越复杂越强”——多 agent 是 workflow 与 agent 的叠加态（编排层可以是代码写死的扇出，也可以是模型自己派活），Anthropic 的建议顺序是“能 workflow 就别 agent，能单 agent 就别多 agent”。
>   - 追问：agent 和 RPA/自动化脚本的区别？常见错误：“都能自动化所以一类”——脚本靠硬编码规则，agent 靠模型在开放循环里临场决策，能力边界与失败模式完全不同。
> - 加分项：能指出“agent 的自主性要配沙箱内充分测试与护栏”这句 Anthropic 原则的后半句；或引 OpenClaw 作对照——它是消息驱动的常驻 agent（四角色拓扑 + 每会话 lane 串行化），与 coding CLI 的“一条指令一个 turn”是同一主循环的两种产品形态。
> - 延伸阅读：[workflow-handbook §1 何时用工作流、何时用自主 Agent](../workflow-handbook/Agent工作流编排手册.md)｜[multiagent-handbook §2.0 workflow 与 agent 的区分](../multiagent-handbook/Multi-Agent协同手册.md)｜[python-handbook §9.3 自研循环：20 行看清六家 agent 的内核形状](../python-handbook/Python大模型应用开发手册.md)

> **Q042. agent 的主循环（agent loop）是什么？最小实现长什么样？**（难度：初 ｜ 频次：高）
> - 考察点：能不能写出或精确说出最小 agent loop，以及停止条件、消息回填这些“循环之外才是难点”的工程细节。
> - 参考回答：
>   - 最小实现 = while 循环 + 消息追加（python-handbook §9.3 的 20 行）：组装 messages → 调模型 → 把模型的 assistant 消息回填历史 → 若无 tool_calls 则返回 content；否则逐个执行工具，把结果以 tool 消息（带 tool_call_id）回填，进入下一轮。
>   - 不变量只有一条最关键：模型的“点菜”（含 tool_use 的 assistant 消息）必须先回填历史再执行，且 tool_result 要与 tool_use 一一对应——这是所有 provider API 的硬约束，回填错序直接报错。
>   - 停止条件分三层：模型不再调用工具（正常收尾）；轮次/token 预算上限（防死循环）；用户中断与错误退出。六家的共识取向是“没有工具调用次数硬上限”（ZCode、OpenCode 的 maxSteps 默认 Infinity），停止全靠语义事件：取消、权限拒绝、输出截断、provider 重试上限、无工具调用、Stop hook。
>   - stop_reason（停止原因）不可全信：anon-kode 不以 stop_reason 判断收尾，而以内容块里有没有 tool_use 为准（源码注释明说 stop_reason==='tool_use' 不可靠）；OpenCode 也注释了“有些 provider 带着 tool call 也返回 stop”，用 hasToolCalls 兜底把循环钉住。
>   - 真实产品比 while 多几层：ZCode 是三层循环——Turn 入口（冻结本轮配置、串行准入）、外层 provider-turn 循环（压缩检查、工具集组装、system-reminder 注入）、单个 model step（流式、工具协调、恢复路径）；并发、压缩、权限检查各安其位。
>   - 并发规则：只有全部工具只读才并发执行（受 MAX_TOOL_USE_CONCURRENCY 限制），只要有一个写操作就退回串行，保证写操作顺序确定（anon-kode query() 的实现）。
>   - 错误路径是循环的“第二主体”：ZCode 的单步恢复段（流恢复重试上限 10、取消时持久化快照、超窗反应式压缩）密度是六家最高之一——循环好写，恢复难写。
> - 追问与陷阱：
>   - 追问：为什么用 while(true) 而不是固定步数上限？常见错误：“限 10 次调用更安全”——上限太低任务做不完、太高白烧钱；正确做法是轮次上限 + token 预算 + 超限抛错绝不静默续跑，多 agent 场景再配 effort scaling（按难度分配 agent 数与调用预算）。
>   - 追问：进度类中间输出要不要进上下文？常见错误：全发给模型——anon-kode 明确 progress 消息只给 UI、不发给模型，只有 user 消息（工具结果）才累积进下一轮。
>   - 追问：模型的 tool_calls 参数是字符串怎么执行？常见错误：直接展开——arguments 是 JSON 字符串，要 json.loads 后按 schema 校验再调真函数；非法参数应回灌可读错误而不是崩。
> - 加分项：能背出 ZCode 三层循环的职责划分（turn.ts 冻结配置防竞态、turn-loop.ts 的 PreRequest/MidTurn 两相位压缩检查、turn-model-step.ts 的流式协调），或 OpenClaw 的双层 lane（通道）串行化——每会话 lane 套全局 lane（enqueueSession(enqueueGlobal(...))），把“同一会话被连续消息轰炸”当一等问题解决。
> - 延伸阅读：[python-handbook §9.3 自研循环](../python-handbook/Python大模型应用开发手册.md)｜[01-claude-code 架构拆解 §3 Agent 主循环](../01-claude-code/架构拆解.md)｜[04-zcode 架构拆解 §5 主循环：三层，不是两层](../04-zcode/架构拆解.md)

> **Q043. 工具调用的完整时序是怎样的？模型“调用工具”时实际发生了什么？**（难度：初 ｜ 频次：高）
> - 考察点：是否理解“模型只点菜不做饭”——生成与执行是两个世界，以及 tool_result 回填、id 对齐、两级错误这些生产细节。
> - 参考回答：
>   - 模型不执行任何东西：模型输出的是结构化的 tool_use 请求（工具名 + JSON 参数），执行发生在客户端 harness（代理宿主）；模型对执行结果一无所知，直到结果作为 tool_result 进入下一轮输入。
>   - 完整时序（以 anon-kode 端到端时序为例）：用户输入 → 采集环境上下文拼系统提示词 → 携带全部工具 JSON Schema 调模型（流式）→ 模型返回文本 + tool_use → harness 校验参数（zod/schema）→ 权限判定（checkPermissionsAndCallTool 串起判定→询问→执行→错误格式化）→ 执行 → 结果按原始 tool_use 的 id 顺序回填 tool_result → 递归下一轮。
>   - 关键细节一（id 对齐）：并发执行完成顺序不定，anon-kode 按原始 tool_use 的 id 顺序重排结果，保证 API 端 tool_result 与 tool_use 一一对应——顺序错了直接 400。
>   - 关键细节二（错误两级）：MCP 规范把错误分开——协议错误走 JSON-RPC error（如工具不存在 -32602，模型难以自行修复）；执行错误走 isError: true + 模型可读反馈（“日期必须在未来，今天是 08/08/2025”，连今天几号都告诉模型），让模型能改参重试。
>   - 关键细节三（非法调用不崩）：OpenCode 用 experimental_repairToolCall 把非法工具调用改写成 invalid 工具的结果回灌模型，让模型自我纠正而不是整个会话崩掉。
>   - 关键细节四（结果注入有治理）：大输出截断/落盘——OpenCode 超 2000 行/50KB 全文写盘只回预览，并提示“交给 explore agent 处理，别自己读”；ZCode 用 maxOutputBytes/resultBudget 裁剪 + 大结果落 artifact 只回摘要。
>   - 工具结果本质是“合成的 user 消息”：Chat API 无状态，tool_result 放在 user 角色消息里；OpenCode 后台子代理的结果也以 synthetic user 消息注入父会话——注入消息不继承用户身份，这是权限边界。
> - 追问与陷阱：
>   - 追问：工具全部并发执行更快吗？常见错误：“并发总没错”——只有全只读才并发，有写操作退串行保证顺序确定；dsh 的执行分类也把“独占调用单独运行并构成排序屏障”。
>   - 追问：工具结果全量塞进上下文吗？常见错误：“信息越多越好”——旧工具结果价值衰减最快（会被占位符化），大输出会挤爆窗口与账单，落盘+引用才是正解。
>   - 追问：MCP 场景下 server 能看到对话历史吗？常见错误：“能，这样更聪明”——server 只收到调用参数与明确声明的上下文，完整对话历史只留在 host，这是协议的安全设计。
> - 加分项：能指出 anon-kode 用 Haiku 小模型为每条 Bash 命令生成 5-10 词自然语言描述（给 UI 展示“这条命令要干嘛”，失败回退固定文案）——工具系统服务的不只是模型还有人的监督；或 OpenClaw 的写者围栏：流式前记录 activeWriterRunId，在同步 SQLite 事务内校验，被取代的 run 提交不了脏数据。
> - 延伸阅读：[01-claude-code 架构拆解 §9 端到端时序](../01-claude-code/架构拆解.md)｜[mcp-handbook §2.3 tools/call：两级错误设计](../mcp-handbook/MCP搭建文档.md)｜[python-handbook §9.3 自研循环](../python-handbook/Python大模型应用开发手册.md)

> **Q044. 工具的 JSON Schema 定义怎么写才不容易出错？**（难度：初 ｜ 频次：中）
> - 考察点：工具定义的工程质量——description、schema、错误返回三个面，是否理解“工具名/描述/参数是模型选工具的唯一依据”。
> - 参考回答：
>   - description（工具描述）是写给 LLM 的 API 文档：说清做什么、什么时候该用与不该用、参数含义、失败时返回什么——它是模型选择工具的唯一依据，糊弄它等于工具永远不被选中；tool_01 这种命名“神仙难救”（ADP 原案例）。
>   - inputSchema（入参模式）精确且最小：必填项标 required、枚举约束写 enum、参数越少越好——每个参数都是模型可能填错的格子；工具名用 snake_case + 动词开头（get_/list_/create_/search_），一个 server 内保持同一命名气质。
>   - 用类型系统生成 schema 而不是手写：openai-agents 的 @function_tool 用函数签名即 schema、docstring 即 description；Pydantic/zod 的“类型即协议”让校验与文档同源，schema 漂移在编译期暴露。
>   - 返回值要“具名 JSON”：裸数组 [30, 1] 的语义靠模型猜，{"precision": 30, "recall": 1} 字段自解释（ADP 4.5 原例）；字段语义写在 schema/description 里，不在猜测里——这直接对应调优手册失败分类 F3“工具误用”的首选治理手段。
>   - 错误返回要“可自纠”：失败消息写清楚错在哪、现在是什么状态、该怎么改（MCP 的日期示例连“今天几号”都给）；协议错误与执行错误分开，别把可恢复错误抛成协议异常。
>   - annotations（工具注解）如实标注：只读工具标 readOnlyHint 让 client 放宽确认、写操作标 destructiveHint——乱标等于把整个信任体系搞坏。
>   - 禁止隐藏副作用：一个工具做一件事，“调用 A 会顺便改 B”模型毫无预期；要分步就做多个工具。
> - 追问与陷阱：
>   - 追问：工具越多覆盖越广越好吗？常见错误：“功能全面不亏”——工具越多选择错误率越高，工具列表本身还占上下文；要分组收窄暴露面（github-mcp-server 把 get_issue 等合并成 issue_read 压缩总数），或学 Cloudflare Code Mode 让模型写代码调 API 而不是逐个挑工具。
>   - 追问：模型老填错参数怎么办？常见错误：直接抛异常让调用失败——应回灌模型可读错误让它改参重试；字段缺失会影响后续执行的，用“参数提取 + 缺失追问”节点而不是标签提取（ADP 酒店送物 badcase 的修复）。
>   - 追问：description 里塞点提示词/营销话术行不行？常见错误：无所谓——description 是注入面之一（往里塞指令有注入风险），也是多 server 抢调用的竞争面，保持中性、只写接口事实。
> - 加分项：省 token 是一等设计目标——playwright 的 browser_find 在快照内局部搜索避免全量快照、notion 提供 Markdown 原生读写端点；能把“工具设计八条”（mcp-handbook §3.3）当场背出三四条并说出出处。
> - 延伸阅读：[mcp-handbook §3.3 工具设计规范](../mcp-handbook/MCP搭建文档.md)｜[tuning-handbook §1.2 失败分类学 F3 工具误用](../tuning-handbook/Agent调优手册.md)

> **Q045. MCP（Model Context Protocol）是什么？解决什么问题？**（难度：初 ｜ 频次：高）
> - 考察点：MCP 的架构三角色、三大原语、与 function calling 的关系，以及当日协议版本动态（是否跟踪生态）。
> - 参考回答：
>   - 一句话：MCP（Model Context Protocol，模型上下文协议）把“AI 应用 × 外部系统”的 N×M 胶水代码标准化成协议——应用不再为每个工具写适配、工具不再为每个应用写适配；官方类比 USB-C，一个接口标准，设备（server）与主机（host）各实现一次即可互通。
>   - 三角色：Host（宿主）创建并管理多个 client、控制连接权限与生命周期、强制安全策略与用户同意；Client 与恰好一个 server 一对一通信、维护 server 之间的安全边界；Server 用三大原语暴露能力——tools（模型控制的工具）、resources（应用控制的资源）、prompts（用户控制的提示模板）。
>   - 两条关键设计原则常被忽略：server 看不到整个对话也看不见其他 server（完整历史只在 host，跨 server 交互由 host 控制）；能力渐进协商（各自声明支持什么，缺的能力优雅降级而不是报错崩溃）。
>   - 版本动态（2026-09-28 核实）：现行规范是 2026-07-28 版的“无状态化大改”——去掉 initialize 握手与 Mcp-Session-Id、逐请求 _meta 协商、引入 Extensions 框架与 MCP Apps、能力分级与 OAuth 硬化写入规范、不向后兼容；2025-11-25 及更早是 legacy（legacy，遗留）三段握手时代。
>   - 与 function calling 的关系：function calling 是模型厂商 API 内的生成侧机制，MCP 是应用与工具之间的协议层——MCP server 的工具经 host 转换成 function calling 用的 schema，两层互补不竞争。
>   - 生态证据：六家 agent 全部内置 MCP 客户端，且 MCP 工具与内置工具在注册表层面完全同构（anon-kode 的 getMCPTools() 并入 getTools()）；Codex 更进一步按用户输入动态拉起 required_mcp_servers，只启动需要的 server。
> - 追问与陷阱：
>   - 追问：MCP 会取代 function calling 吗？常见错误：“新标准取代旧机制”——模型侧仍然走 function calling 生成调用，MCP 解决的是工具的发现、接入、分发与安全边界的标准化，两者在不同层。
>   - 追问：stdio 还是 Streamable HTTP？常见错误：“一律上远程”——本地进程 stdio 最简单（客户端把 server 当子进程拉起），远程托管服务才需要 Streamable HTTP + OAuth；选型跟着信任边界与部署形态走。
>   - 追问：MCP 工具的权限怎么管？常见错误：“协议层管了”——host 仍要把 MCP 工具纳入自己的权限链（anon-kode 的 MCP server 有单独审批 UI，OpenCode 每次 MCP 调用前过 permission.ask），协议不管业务授权。
> - 加分项：能讲 tools/call 的两级错误设计（isError:true 让模型自纠是工程上最重要的一节）与五种 content 类型（text/image/audio/resource_link/resource）；补一句 2026-07-28 规范引入的 structuredContent 与 resultType 结果封装说明自己真读过现行规范。
> - 延伸阅读：[mcp-handbook §1 MCP 是什么：架构与角色](../mcp-handbook/MCP搭建文档.md)｜[python-handbook §9.1 MCP 官方 Python SDK：十几行一个 server](../python-handbook/Python大模型应用开发手册.md)

> **Q046. Agent Skill（技能包）是什么？与 MCP、斜杠命令的生态位区别？**（难度：初 ｜ 频次：中）
> - 考察点：Skill 的格式与渐进式披露机制，以及“MCP 提供连接、Skill 提供知识、斜杠命令提供固定模板”的生态位辨析。
> - 参考回答：
>   - 一句话：Agent Skill（技能包）是一个基于文件夹的能力格式——一个目录内含 SKILL.md（YAML frontmatter 元数据 + Markdown 指令正文），可选脚本、参考文档、模板资产；agent 需要某项能力时加载对应 skill，像给新员工发一本操作手册。2025-10 Anthropic 发布并开放为标准（agentskills.io）。
>   - 解决的问题：团队的私有流程知识（品牌规范、部署步骤、数据口径）只有三个去处——常驻系统提示词（每个 token 常驻、99% 时间用不上）、每次手动粘贴（不可复用不可版本化）、Skill 按需加载（只在用到时占上下文，可分发可迭代）——本质是给上下文窗口做分层缓存。
>   - 核心机制是渐进式披露（progressive disclosure，渐进式披露）三级加载：L1 元数据 name+description 常驻系统提示词，每个 skill 约百 token，装几十个也不挤；L2 SKILL.md 正文触发后才加载，官方建议 <5k token；L3 捆绑资源（参考/脚本/模板）读到正文指引后才打开，不限大小。
>   - 四种机制的生态位四分：MCP 提供“连接”（外部系统的工具与数据，模型决定何时调用）；Skill 提供“知识”（做某类事的流程规范脚本，模型按 description 匹配或用户强制加载）；subagent 提供“隔离上下文的执行者”（主代理分派）；slash command（斜杠命令）提供固定提示词模板，用户显式敲命令。
>   - 判断口诀：要连一个新系统 → MCP；要教一套做某类事的流程/规范 → Skill；要固定一句话提示词且用户手敲 → slash command。二者互补的经典例：GitHub MCP 给 create_pull_request 工具，公司发一个 skill 规定“PR 标题必须带 ticket 号、描述必须含测试方案”。
>   - 执行模型差异一句话：skill 是“知识注入”，MCP 是“工具接线”；skill 里的脚本是确定性逻辑工具化的轻量形态——“与其让模型每步生成 2000 token 算一遍，不如让它跑一个 20 行脚本”。
> - 追问与陷阱：
>   - 追问：装了十个 skill 但从不触发，为什么？常见错误：先怀疑加载机制——L1 常驻的只有 description，写不好（没写清“什么时候用”）就永远不被匹配触发；description 是 skill 迭代的第一优先。
>   - 追问：Skill 能替代 MCP 吗？常见错误：“skill 更轻所以更先进”——skill 不提供任何新的连接能力，它只教模型用好已有工具；没有 MCP/API 接线，skill 教的流程无处落地。
>   - 追问：SKILL.md 越写越长怎么办？常见错误：继续堆——超 5k token 就该把细节拆到 L3 参考文件，正文只留工作流程与“何时读哪个文件”的路由表。
> - 加分项：能对照两套“三层”结构——MCP 三原语按控制权分（模型/应用/用户控制），skill 三层按加载时机分（常驻/触发/按需）；再补 Codex 在回合装配时经 build_skills_and_plugins 把技能进入工具与输入项（turn.rs:966）。
> - 延伸阅读：[skill-handbook §1 Skill 是什么：定位与生态位](../skill-handbook/Skill搭建文档.md)｜[mcp-handbook §1.2 三角色职责](../mcp-handbook/MCP搭建文档.md)

> **Q047. agent 的规划（planning）怎么做？任务分解的常见失败有哪些？**（难度：高 ｜ 频次：中）
> - 考察点：规划的实现层次（没有独立 planner 模块的现实）、分解质量的决定性作用，以及 MAST 分类学里的设计类失败。
> - 参考回答：
>   - 现实澄清：生产级 agent 大多没有独立规划模块，规划以三种轻形态存在——think 工具（anon-kode 的 ThinkTool 在工具注册表里，给模型留“纸上推演”位）、plan 模式（ZCode 五模式 plan/build/edit/yolo/auto，OpenCode 用 plan_mode_exit 的 system-reminder 注入）、todo 工具（ZCode 的 todo_reminder 周期注入，外化工作记忆防长任务忘目标）。
>   - 大任务的主流做法是 orchestrator 分解 + 子代理扇出：Anthropic 研究系统的 Lead Agent 拆 3-5 个并行子代理，并配 effort scaling（力度分级）表——简单事实查找 1 个 agent 3-10 次工具调用；比较/综述 2-4 个子代理各 10-15 次；复杂开放研究 10 个以上子代理、显式放宽。
>   - 失败一：模糊委派 → 重复劳动。Anthropic 的原案例：编排者没有明确边界，两个子代理同时查 2025 供应链、另一个孤零零查 2021 芯片危机——治理是“显式分解 + 去重指令”，写清边界与“别人负责哪块”。
>   - 失败二：MAST ①类 specification issues（系统设计问题）——任务分解不合理、角色定义缺陷、缺少验证环节，设计者在纸面上就错了，agent 只是忠实执行。
>   - 失败三：无力度分级——Anthropic 早期 agent 给简单查询派了 50 个子代理，成本与任务难度脱钩。
>   - 失败四：没有验收门——MAST ③类 task verification（任务验证缺失）：没验收步骤、验收标准太弱、带病产出直接交付；治理是每个交接点放验收门，判据优先级“代码 > 规则 > LLM 打分”。
>   - 治理总纲：分解质量 > 提示词质量——Anthropic 经验“模糊委派是重复劳动的第一根因”；Cognition 的两条原则（上下文必须共享、行动隐含决策）进一步说明分解后的同步机制比分解本身更难。
> - 追问与陷阱：
>   - 追问：为什么不让模型先输出完整计划再逐步执行？常见错误：“plan-then-execute 是标准答案”——环境反馈会推翻计划，固定计划脆；ADP 的 Plan & Execute 模式甚至仅支持单轮对话，生产主流是“计划 + 循环修正”的混合。
>   - 追问：todo 列表是形式主义吗？常见错误：“模型自己记得住”——长任务的目标漂移是注意力问题，todo 外化 + reminder 周期注入是六家验证过的工程手段，不是仪式。
>   - 追问：规划失败怎么在评测里抓？常见错误：只看最终答案——要用轨迹评测看分解步骤（eval-handbook 的五分类归因里“规划错”单列），失败发生在哪一步比最终对错信息量大。
> - 加分项：能指出 ZCode dynamic workflow 是规划的“代码态终局”——模型写 TypeScript 表达控制流，编译器用 taint 不动点分析决定哪些步骤能并发，再在 vm 独立 realm 里执行；这是六家里对“agent 如何结构化表达长任务”最独特的答案。
> - 延伸阅读：[multiagent-handbook §1.2 成本-收益判据](../multiagent-handbook/Multi-Agent协同手册.md)｜[multiagent-handbook §6.1 MAST 失败分类学](../multiagent-handbook/Multi-Agent协同手册.md)｜[eval-handbook §6.3 失败归因：五分类与“验证世界”纪律](../eval-handbook/Agent评测与质量工程手册.md)

> **Q048. 子代理（subagent）的价值与代价是什么？上下文隔离怎么设计？**（难度：中 ｜ 频次：高）
> - 考察点：隔离的上下文经济学（为什么值钱）、15× 的量化代价、以及“三张白名单 + handoff 协议”的隔离设计完整度。
> - 参考回答：
>   - 价值只来自三处：上下文隔离（子代理在独立窗口干脏活，只把结论带回主窗口，主窗口留给决策）、并行（墙钟时间除以并发数，Anthropic 实测研究类任务最多省 90% 时间）、专业化（窄提示词 + 窄工具集带来的可靠性）。
>   - 代价也来自三处：token 放大（Anthropic 账本：单 agent 循环约 4× 普通对话，multi-agent 约 15×）、工程复杂度（通信、状态、失败处理、可观测）、评测难度（轨迹更长、失败归因更难）；token 用量单独解释了 BrowseComp 上 80% 的成绩方差——多 agent 的本质是“用搜索量换准确率”。
>   - 收益的上限样本：Anthropic 多 agent 研究系统在内部研究评测上比单 agent Opus 4 好 90.2%——但这是预算买来的，预算就是能力的物理上限。
>   - 实现形态高度收敛：递归同一个主循环——anon-kode 的 AgentTool 在隔离消息列表里递归调用同一个 query()，OpenCode 的 task 工具同进程递归同一个 runLoop（深度默认 1）；OpenClaw 用 sessions_spawn 开独立会话 + 专用 subagent lane（并发 8）。
>   - 隔离设计是三张独立白名单：上下文（独立消息列表/会话）；工具（子代理工具面只减不增——ZCode 只读 Explore 子代理限 7 个工具 Bash/Glob/Grep/Read/WebFetch/WebSearch/TodoWrite，OpenClaw 子代理默认拿不到 session/message 工具“让工具面难以被滥用”，OpenCode 额外 deny todowrite/task）；权限（OpenCode 子代理只继承父 deny 规则；ZCode 项目级 md 定义的 permissionMode 被强制忽略，防“仓库自带 agent 定义给自己提权”）。
>   - handoff（交接）回传协议四条：回传“简明报告”（结论 + 可定位证据的路径引用：文件：行号、命令与退出码 + 未决问题）不回传全量过程；回传通道即身份边界（synthetic user 消息不继承 operator 身份——信息可以从子代理流回，权限不能）；默认拿走高危工具；首步不打扰（ZCode 后台结果从第二个 model step 起 drain，主代理第一个模型调用永远聚焦用户原请求）。
>   - 反面教材：OpenClaw 默认 tools.sessions.visibility = all——任何未沙箱化的 agent 能读所有 agent 的 transcript，“能互相看见”默认等于“能互相污染”，收窄开关必须当默认项而非加固项。
> - 追问与陷阱：
>   - 追问：子代理为什么不能继承父代理的 allow 权限？常见错误：“全继承省事”——被注入的子代理会横向越权；OpenCode 只继承 deny 是“默认收窄、显式放大”的安全姿态。
>   - 追问：大任务是不是都该拆子代理？常见错误：“拆了总没坏处”——子任务需要互相看中间产物时硬拆会因上下文不同步而决策矛盾（Cognition：上下文必须共享）；先问“能不能只派一个子代理”。
>   - 追问：子代理的结果怎么防“自述造假”？常见错误：信子代理的总结——父代理复核时核对的是可定位证据（文件：行号、退出码），不是自述，即“verify the world（验证世界）”纪律。
> - 加分项：ZCode 后台子代理支持“前台超时自动后台化”（runner.ts），后台结果经控制工具 TaskOutput/TaskStop 取回；能指出 ZCode 是六家里唯一把“peer 消息降权”写成协议级规则（被拒后转托 = 权限洗白，要拒绝并上报）的。
> - 延伸阅读：[context-handbook §3 子代理上下文隔离与信息传递](../context-handbook/Context与记忆系统手册.md)｜[multiagent-handbook §1 何时真的需要多 Agent](../multiagent-handbook/Multi-Agent协同手册.md)｜[01-claude-code 架构拆解 §7 子代理与并行](../01-claude-code/架构拆解.md)

> **Q049. 什么时候真的需要多 agent？怎么判断？**（难度：中 ｜ 频次：高）
> - 考察点：单 agent 三条边界 + 四问判据 + 伪需求识别——“看起来该上多 agent 的时刻多半不该”是否内化。
> - 参考回答：
>   - 先看单 agent 的三条边界（撞上哪个才考虑哪类解法）：上下文边界（读几个大文件后忘掉最初目标、工具输出淹没决策）→ 对症子代理隔离；角色边界（一个系统提示词身兼研究员/写手/评审，行为漂移）→ 对症专业化（窄提示词 + 窄工具集）；并行边界（多路独立搜索串行太慢）→ 对症并行扇出。三条边界都发生在“任务变大”之后。
>   - 四问判据全部答“是”才上多 agent：可分解（能拆成边界清晰、接口明确的子任务）；信息隔离有意义（中间产物装不进主窗口，或互相看了会污染）；可独立验收（每个子任务能用代码/规则/独立评审单独判对错——不可验收的协作等于错误自由传播）；收益大于 15× token（预算买得起且换来覆盖率/时间/质量的真实提升）。
>   - 五类伪需求：①“上下文记不住 → 上多 agent”——多数是上下文工程问题（压缩、剪枝、工具输出落盘），Claude Code 的答案是主循环 + 按需 Task 工具；②“拆给便宜小模型省钱”——编排本身有 token 开销，15× 放大下总成本常常更高，省钱的正确路径是模型路由 + 缓存；③“辩论/投票/头脑风暴更聪明”——开放任务增加协作轮次就是增加失败面，MAST 的数据是增益常常 minimal；④“给每个 agent 配全套工具”——工具越多角色越模糊、选择错误率越高，六家的共识是子代理工具面只减不增。
>   - 真需求长什么样：任务结构本身就长着“多角色”——Codex 的 multi_agents_v2（角色注册表 + 智能体关系图）、Anthropic 的并行研究子代理、Storm 的多视角提问；共同点是有明确验收的天然独立子域，而不是“单 agent 效果不好，试试多 agent”。
>   - 反方最强论点也要会讲：Cognition《Don't Build Multi-Agents》两条原则——上下文必须共享（信息不一致则决策互相矛盾）、行动隐含决策（A 选了框架 B 不知道，后面全是冲突）——决定了“平行 agent 各干各的”天然不稳。
>   - 结论一句话：正确的第一问永远是“能不能只派一个子代理”，而不是“要不要建 agent 团队”；评两条线（任务质量 + 协作质量）再决定是否保留。
> - 追问与陷阱：
>   - 追问：上下文装不下为什么不直接拆多 agent？常见错误：“装不下=该拆”——先过上下文工程三板斧（压缩/剪枝/落盘），隔离是结构性答案但成本是 15× token，多数场景负收益。
>   - 追问：多 agent 的收益怎么验收？常见错误：只评最终答案质量——要同时评协作质量（交接点指标），MAST ②类失败发生在接缝上，每个 agent 单独评测全绿不等于系统可用。
>   - 追问：已经在跑的多 agent 什么时候该撤？常见错误：“上了就不撤”——转交不稳定、分解总出重复时就该降级为工作流编排或合并回单 agent，撤退是调优的正常动作。
> - 加分项：能引 Anthropic 生产失败清单佐证（早期 agent 给简单查询派 50 个子代理、子代理无穷搜索不存在的来源、偏好 SEO 内容农场胜过权威学术 PDF）——说明伪需求不是理论担忧而是已发生的生产事故。
> - 延伸阅读：[multiagent-handbook §1 何时真的需要多 Agent：边界、成本-收益与伪需求](../multiagent-handbook/Multi-Agent协同手册.md)｜[context-handbook §2 上下文预算与压缩机制](../context-handbook/Context与记忆系统手册.md)

> **Q050. supervisor、orchestrator-worker、swarm 等编排范式怎么选？**（难度：中 ｜ 频次：高）
> - 考察点：六种范式是否收敛到“控制流放在哪里”这一个变量，选型判据与各自风险能否说全。
> - 参考回答：
>   - 六种范式一个变量——控制流在哪：supervisor（监督者，中心逐轮路由）、orchestrator-worker（编排者-工人，一次性扇出汇总）、swarm/handoff（蜂群/交接，去中心逐跳移交）、hierarchical（分层团队，supervisor 的递归）、blackboard（黑板，共享状态驱动）、protocol-based（协议化协作，跨信任边界）。
>   - supervisor：worker 之间互不见面，所有消息过主管——这是六家 agent 默认形态的抽象（Claude Code 主循环递归 query()、ZCode 的 Agent/Task 工具、OpenClaw 的 spawn + 结果 announce 回请求方，全是“worker 只向调用方汇报”）；适用子任务有先后依赖、需要统一裁决；风险是 supervisor 上下文成为全系统最挤的窗口（ZCode 首步不打扰、Anthropic 把计划存窗口外，都是给 supervisor 减负的专门设计）。
>   - orchestrator-worker：一次性并行扇出而非逐轮路由，最后汇总去重——Anthropic 研究系统的形态（Lead Agent 拆 3-5 个并行子代理）；适用研究、多文件改造、多数据源汇总等独立可并行场景，收益最大（最多省 90% 时间）；成败手筋在分解质量，模糊委派是重复劳动的第一根因。
>   - swarm/handoff：没有常驻主管，每个 agent 判断“该谁接”，控制权连同对话上下文整段移交——OpenAI Agents SDK 把 handoff 做成一等原语，其前身 openai/swarm（22.0k star）README 已明示被取代；适用客服/工单式分流，交接点就是责任交接点；风险是无全局视图、链条长了责任漂移。
>   - hierarchical：supervisor 的递归嵌套，适用大规模可分域任务；风险是层间失真放大、延迟叠加，别为了规模感而分层。
>   - blackboard：共享状态是唯一真源，消息只是通知——治“两个 agent 对同一事实各执一词”的通信失真；风险是读写冲突与状态治理。
>   - protocol-based：跨厂商/跨组织的互操作（A2A），同信任域内部不需要；选型口诀“进程内用函数，进程间用消息，组织间用协议”。
>   - 再叠一层坐标：编排层本身可以是 workflow（代码写死的扇出）也可以是 agent（模型自己派活）——Anthropic 建议能 workflow 就别 agent。
> - 追问与陷阱：
>   - 追问：supervisor 和 orchestrator-worker 区别到底是什么？常见错误：混为一谈——前者逐轮路由、worker 可与主管多轮往返；后者一次性扇出、worker 独立跑完、编排者最后汇总去重。
>   - 追问：swarm 交接时最怕什么？常见错误：“交给下家就行”——交接消息丢失上下文 = 用户体验断裂，handoff 消息要带交接理由与已做事项清单。
>   - 追问：什么时候用 hierarchical 而不是单层 supervisor？常见错误：“规模大就分层”——只在子域天然独立且每域自身稳定时用，否则层间失真与延迟是纯负资产。
> - 加分项：能指出六家内部协作全部用私有机制（工具结果、synthetic 消息、announce、mailbox），没有一个走开放协议——协议化只出现在跨 harness/跨组织边界（dsh 委派给 Codex、OpenClaw 挂 ACP）；再补 ADP 的协同方式小谱系（自由转交/工作流编排/Plan & Execute）印证“确定性编排是协同方式的收敛点”。
> - 延伸阅读：[multiagent-handbook §2 编排范式谱系：六种形态，一个变量](../multiagent-handbook/Multi-Agent协同手册.md)｜[workflow-handbook §2 工作流模式谱系](../workflow-handbook/Agent工作流编排手册.md)

> **Q051. agent 的记忆系统怎么设计？有哪些记忆类型？**（难度：中 ｜ 频次：中）
> - 考察点：记忆四类型学与实现映射、写入与召回的边界设计、以及“难点在写入而非检索”的工程判断。
> - 参考回答：
>   - 类型学四分法（认知科学三分 + 前瞻）：语义记忆（semantic，稳定事实：“用户的部署目标是 X”，实现如 MEMORY.md、mem0 事实条目）；情景记忆（episodic，事件轨迹：“上周三那次部署失败因为…”，实现如日记 memory/YYYY-MM-DD.md 与会话 transcript）；程序记忆（procedural，怎么做事：AGENTS.md/CLAUDE.md、Skill、USER.md 祈使句指令）；前瞻记忆（prospective，“周五提醒我”“发布时提到 changelog”，OpenClaw 实现 standing intents：时间型编译成 cron、事件型进 SQLite intent 表）。
>   - 关键洞察在第四类：“记得做”是触发器问题不是检索问题——TriggerBench 实证前瞻记忆随上下文变长急剧退化而情景记忆几乎不退化，且模型会不可信地自发取消；OpenClaw 明说“把意图存成 memory 文件里的一句话是最不可靠的设计”，所以把意图从模型手里编译出去（cron/触发器表）。
>   - OpenClaw 五层 tier（层级）模型是完整参照系：Instructions（仅人类写，总是注入）→ Curated core（MEMORY.md/USER.md，由 dreaming 整理 pass 唯一主写）→ Episodic（日记/转录，从不自动注入、只能显式搜索）→ Prospective（触发器命中时注入）→ Review（整理报告，供人审）。
>   - 最重要的边界在 curated 与 episodic 之间：未 vet（审核）的内容无论检索分多高都结构性禁止自动进入 prompt——“这是安全性质，不是调优选择”。
>   - 三条记忆卫生规则：session-kind gating（cron/心跳/子代理会话的产物永不具备晋升资格）；recall-loop prevention（从记忆注入上下文的内容被结构性标记、永不再次被提取为新记忆——“一个事实被召回一百次仍是一个事实”）；taint 传播（工具声明为网络来源后，本轮内后续 assistant 消息都被标记 untrusted，直到下一条 user 消息）。
>   - 写入哲学：难点在写入而非检索（把 curation 移出回复热路径交给专门后台 pass）；记忆故障永不阻塞回复（每步都有超时或回退）；向量检索在 OpenClaw 里是可选插件而非核心。
>   - 程序记忆的实证：PrefEval（ICLR 2025）——偏好“mere presence in context”几轮后即失效，就近重述指令比更重的检索机制更能恢复遵守。
> - 追问与陷阱：
>   - 追问：长期记忆上向量库就完事了吗？常见错误：“embedding 检索=记忆系统”——LongMemEval 证明“写了什么比怎么索引更重要”；写入策略（何时存、存什么、冲突怎么办、provenance 来源追溯）才是主体。
>   - 追问：记忆会不会被注入污染？常见错误：只防检索端——写路径就是安全边界：内容级扫描挡不住投毒，要在写入处强制 provenance 与结构化门槛，而不是事后检测。
>   - 追问：用户隐私怎么处理？常见错误：忽略合规——记忆是高价值个人信息库，GDPR 的“被遗忘权”落在文件系统上并不平凡（删除主文件不等于删净索引与衍生条目）。
> - 加分项：能说出 OpenClaw 的预算三数字（单文件 20k 字符、总 60k、USER.md 固定 4k 且“调大全局值也放不开 USER.md”）与“群聊不加载 MEMORY.md”这类注入场景收窄；或 mem0 从两阶段流水线到单遍 ADD-only 的算法代际（context-handbook §7.1）。
> - 延伸阅读：[context-handbook §4 长期记忆体系：类型学、写入、召回、遗忘](../context-handbook/Context与记忆系统手册.md)｜[05-openclaw 架构拆解 §8 上下文、记忆与压缩](../05-openclaw/架构拆解.md)

> **Q052. agent 的上下文预算与压缩（compact）策略怎么设计？**（难度：高 ｜ 频次：中）
> - 考察点：三层预算模型、剪枝先于摘要的顺序不变量、“日志为真源压缩只改投影”的架构约束，以及缓存锚点与保险丝设计。
> - 参考回答：
>   - 三层预算模型（ZCode 是最清晰样本）：microcompact 微压缩（thresholdRatio 0.9 触发，只把旧 tool result 换成 [Old tool result content cleared] 占位符，保留最近 5 条，近零信息损失）→ auto compact 自动压缩（200k 窗口、输出预留 min(maxOutput, 21k)、buffer 13k，摘要替换历史，有损）→ reactive compact 反应式压缩（超窗错误后补救，最贵——已经付了一次失败请求）。
>   - 顺序不变量：剪枝排在摘要前面——工具结果是上下文中信噪比衰减最快的部分（第 3 轮读的文件到第 30 轮只剩“我读过它”的事实价值）；六家共识梯度是“工具结果 → 占位符；对话历史 → 摘要；宁可新开窗口也不无限摘要”。
>   - 架构不变量：日志为真源，压缩只改投影——dsh 的“模型可见即已记录”（仅追加 SessionEvent 日志，deriveMessages() 投影并冻结模型历史）；OpenClaw 根 AGENTS.md“只有 compaction 可以改写历史，完整历史留在磁盘”；状态可重建的前提是事实（事件）与视图（投影）分离。
>   - 保险丝：rapid-refill 断路器——压缩后立刻又装满，说明有东西在快速回填，继续压缩只是烧钱循环，直接抛错；auto compact 连续失败 3 次熔断。
>   - 摘要保真：ZCode 摘要提示词强制纯文本、禁调工具、9 段结构（Primary Request / Key Concepts / Files & Code / Errors & Fixes / Solving / All user messages / Pending / Current Work / Optional Next Step），并两次强调安全相关指令必须逐字保留——六家里唯一把“压缩会削弱安全边界”当显式设计约束的；OpenCode tail 逐字保留 clamp(usable×0.25, 2k, 15k) 且 splitTurn 允许从 turn 中间切。
>   - token 估算与实算分开：OpenCode 用于压缩预算的估算是字符数/4（粗估，token.ts:4），真实用量走 provider usage 并归一化各家 cache 语义；估算只服务预算判断，记账必须用实算。
>   - 缓存锚点是“最便宜的一笔钱”：agent 每轮重发全量上下文，缓存读约 1/10 价格；要点是段序稳定、cache-control 在 provider 投影之后统一设置、动态内容追加在缓存前缀之后；反面教材是时间戳/随机 ID 写进前缀——一次污染全轮缓存报废。
>   - 大输出治理三拼法：OpenCode 2000 行/50KB 落盘只回预览 + “委派 explore agent”反向引导；dsh 的 spill 外溢到存储上下文只留引用；ZCode 的 maxOutputBytes/resultBudget 裁剪 + artifact 落盘回摘要。
> - 追问与陷阱：
>   - 追问：能不能全靠自动摘要？常见错误：“摘要是万能的”——摘要是有损的，安全边界与关键约束会丢；所以要“安全指令逐字保留”这类硬约束，且压缩失败要熔断而不是无限重试。
>   - 追问：什么时候触发压缩最好？常见错误：“满了再压”——PreRequest/MidTurn 两相位检查让压缩发生在请求前，避免超窗浪费一次失败请求；OpenCode 的 overflow 也不当场压（打标记下一轮压）。
>   - 追问：模型应该知道自己快没空间了吗？常见错误：一刀切——六家里只有 Codex 把上下文管理工具化（get_context_remaining 查余额 + new_context_window 开新窗）让模型参与预算决策，其余五家 harness 单方面裁决；两条路线优劣尚无定论，但前者对长会话主动收尾有独特价值。
> - 加分项：能指出压缩的“代际差”就是 agent 的代际差（2025 初的 anon-kode 无自动治理 → 2025 末压缩成为回合内策略 → 2026 的 ZCode/OpenClaw 为压缩配熔断、质量审计与安全约束——上下文治理从功能变成子系统）；再补远程压缩（Codex RemoteCompactionSupport::V2）说明压缩正在搬进 provider。
> - 延伸阅读：[context-handbook §2 上下文预算与压缩机制：三层模型与六家横向对照](../context-handbook/Context与记忆系统手册.md)｜[04-zcode 架构拆解 §8 上下文、提示词与三层压缩](../04-zcode/架构拆解.md)

> **Q053. 工具返回结果怎么注入上下文？为什么要“具名 JSON”？**（难度：中 ｜ 频次：中）
> - 考察点：工具结果的注入位置与治理（裁剪/落盘/占位符），以及“具名 JSON”背后的模型可读性工程。
> - 参考回答：
>   - 注入位置：工具结果作为 tool_result 内容块回填到 user 消息，与 tool_use 一一对应、按原始 id 排序（并发执行完成顺序不定，anon-kode 按原始顺序重排）；Chat API 无状态，每轮全量重发，所以“注入什么”直接决定窗口与账单。
>   - 为什么要具名 JSON：模型读到的一切都是文本，裸数组 [30, 1] 的字段语义要靠猜、跨轮会猜错；{"precision": 30, "recall": 1} 字段自解释（ADP 4.5 原例），且字段语义要写进 schema/description——“消息里的结构化字段优先于自然语言叙述”是工具与 agent 间通信的通用纪律。
>   - 协议层支撑：MCP 2025-06-18 引入 structuredContent，可返回符合 outputSchema 的结构化 JSON，同时要求 text 里给序列化 JSON 兼容旧客户端——结构化与人类可读两份都要。
>   - 大输出走“落盘 + 引用”：OpenCode 超 2000 行/50KB 全文写 truncation 目录、只回预览，提示词还教模型“交给 explore agent 处理，别自己读”——用截断机制反向引导模型做上下文外包；dsh 的 spill 把大输出外溢到存储、上下文只留引用；ZCode 用 maxOutputBytes/resultBudget 裁剪 + 大结果落 artifact 只回摘要。
>   - 旧结果会过期：microcompact 把旧 tool result 换成占位符（保留最近 5 条）——工具结果的价值随轮次衰减最快，这是剪枝排在摘要前面的原因。
>   - 错误结果同样要可注入、可自纠：isError: true + “错在哪/现在状态/怎么改”（MCP 日期示例连“今天几号”都告诉模型）；OpenCode 把非法调用改写成 invalid 工具结果回灌而不是崩。
>   - 多模态结果有专门治理：OpenCode 图片压不下去就在文本里追加 [N images omitted]；OpenClaw 被省略的图片插固定标记且每次请求最多 847 UTF-8 字节（刻意固定大小避免估算漂移）。
> - 追问与陷阱：
>   - 追问：返回全量数据让模型自己挑不好吗？常见错误：“信息充分决策才好”——上下文是预算不是画布，全量返回挤爆窗口还稀释注意力；server 侧就该做局部返回（playwright browser_find 在快照内搜索）与工具合并（github-mcp-server 的 issue_read）。
>   - 追问：工具结果要不要永久保留在历史里？常见错误：“全量保留才完整”——历史投影会被占位符化，真源在日志与落盘文件；需要时按路径引用回取，不在上下文里养数据。
>   - 追问：JSON 嵌套很深怎么办？常见错误：直接 stringify 整个对象——嵌套越深模型读取出错率越高，返回面向模型的视图（拍平关键字段），原始结构落盘。
> - 加分项：能串起三处一致性——工具返回具名 JSON（tuning F3 治理）、子代理回传简明报告带结构化字段（handoff 协议）、黑板范式“消息只传引用”——同一原则（传结论不传过程、字段语义在 schema 里）在三个层面的应用。
> - 延伸阅读：[mcp-handbook §2.3 tools/call：两级错误设计](../mcp-handbook/MCP搭建文档.md)｜[tuning-handbook §1.2 失败分类学 F3 工具误用](../tuning-handbook/Agent调优手册.md)｜[context-handbook §2.4 大输出的两个答案：落盘委派与外溢](../context-handbook/Context与记忆系统手册.md)

> **Q054. agent 的权限与审批模型怎么设计？（结合六家 agent 对照）**（难度：中 ｜ 频次：中）
> - 考察点：最小权限的四个落点、六家权限机制的横向视野、审批绑定强度与“用户在不在场”的选型判断。
> - 参考回答：
>   - 最小权限（least privilege）在 agent 上有四个落点：工具面收窄（默认只装配任务需要的工具，Codex 按输入动态拉起 MCP/插件）；动作分级（只读/写/破坏性三级——注意 ZCode 硬编码集合的代价是新工具/MCP 工具会落错档，声明式分级是正解）；资源边界（可写目录白名单，Codex 的 WritableRoot 把 .git/hooks 保持只读防“改 hook 提权”）；出口控制（对外通信单独成轴单独审批——lethal trifecta 的第三条腿）。
>   - 六家机制光谱（能报出三家以上即合格）：01 三层判定（SAFE_COMMANDS 白名单 → 精确匹配 → 前缀授权）；02 Codex 内核级双轴 AskForApproval × SandboxPolicy，沙箱六家最强（macOS Seatbelt / Linux Landlock+bwrap / Windows）；04 ZCode 五模式 + checkPermission 优先级链 + 1.9MB 命令知识库；05 OpenClaw 五套并存但默认几乎不设防（沙箱默认关、host exec 默认 security=full）；06 OpenCode 五层 ruleset 求值式 findLast，无匹配规则默认 ask（fail-safe）。
>   - 审批绑定的“防漂移”程度是代际差：01 批准 Bash(git push) 放行同前缀（前缀授权的漏洞面：git push origin main 批准过，git push --force 未必被拦住）→ 05 OpenClaw 把批准绑定 cwd + 精确 argv + env + 可执行文件真实路径 + 内容哈希，等待期 PATH 漂移即拒——六家最硬。
>   - 权限不随消息流动是多 agent 时代的底线：ZCode 把同伴消息显式降权（不得改权限/AGENTS.md、不得当成用户批准、“被拒后转托 = 权限洗白，要拒绝并上报”）；OpenCode 子代理只继承父 deny；OpenClaw 审批绑定 operator 身份不随排队/委派漂移。
>   - 选型的核心问题不是“要不要沙箱”而是“用户在不在场”：在场（coding 场景）→ 审批为主、沙箱为辅，ZCode/OpenCode 证明没有内核沙箱也能靠权限链维持日常安全；不在场（cron/webhook/多渠道）→ 沙箱必须默认开——OpenClaw 反例：有沙箱但默认关闭等于没有。
>   - 危险操作基线清单：文件破坏（rm -rf/dd）deny-by-default + 人审；提权链（sudo/chmod/写 .git/hooks）一律 deny；网络（curl|bash 拒绝、出口域白名单、渲染外部资源默认禁）；凭据（.env 默认 ask、agent 不看到值地取凭据 SecretRef 模式）；不可逆外部动作（git push --force、发邮件、支付）显式批准且审批绑定执行要素。
>   - 供应链面是 2025-2026 最实的攻击面：恶意 MCP 包（postmark-mcp）、规则文件后门（.cursorrules 藏 Unicode 隐字符）、幻觉包名——把仓库自带配置当不可信输入（ZCode 工作区 hook 信任状态机：声明变更即失效）。
> - 追问与陷阱：
>   - 追问：有沙箱还需要权限链吗（或反之）？常见错误：“二选一”——沙箱与权限是两个独立维度：Codex 双轴全开是最强档，OpenClaw 证明有沙箱默认关等于没有，ZCode/OpenCode 证明没沙箱也能靠权限链 + 人在场维持安全。
>   - 追问：默认策略 fail-open 还是 fail-safe？常见错误：fail-open 更顺滑——OpenCode 无匹配默认 ask、ZCode 的 alwaysAsk 压过 yolo 放行（但压不过硬阻断），fail-safe 是底线。
>   - 追问：审批过的操作要不要复检？常见错误：“批准过就永久信任”——前缀授权有覆盖面漏洞，高危操作应绑定执行要素（argv/env/哈希）并考虑有效期。
> - 加分项：一句“安全声明要读代码不看 README”能直接加分——OpenClaw 官方文档写审批结果落 JSON 文件、实际代码已迁 SQLite；ZCode 保留 dangerouslyDisableSandbox 参数但语义已空（四处独立证据证明无沙箱）。
> - 延伸阅读：[security-handbook §3 工具与权限安全：六家机制横向对照](../security-handbook/AI应用安全手册.md)｜[01-claude-code 架构拆解 §5 权限与安全](../01-claude-code/架构拆解.md)｜[02-codex 架构拆解 §5 审批与沙箱（双轴控制）](../02-codex/架构拆解.md)

> **Q055. agent 的状态持久化怎么设计？会话文件与事件溯源怎么选？**（难度：中 ｜ 频次：低）
> - 考察点：存储选型的演进逻辑（JSON 文件 → SQLite/事件日志）、事件溯源不变量、fork/revert 对存储的要求。
> - 参考回答：
>   - 演进光谱：早期 anon-kode 用 JSON 文件 + /resume（history.ts 落盘）→ 生产级六家全部收敛到 SQLite（ZCode/OpenClaw/OpenCode）或结构化事件日志（dsh、Codex rollout）——并发写、审计、fork 需求把纯文件方案淘汰。
>   - ZCode：SQLite 是唯一真源（~/.zcode/cli/db/db.sqlite，31 张表：session 含 parent_id 分叉树、message、part、permission、usage 三表、todo、workflow_* 等）；“事件即事实”——ModelRequest/TurnComplete/TurnError 等事件 appendEvent 落库，冷恢复走 resumeFromStore；模型 I/O 轨迹目录（rollout）是无可观测网时最重要的调试入口。
>   - OpenClaw：一律 SQLite——transcript、路由、auth profile 全在 per-agent sqlite；写者围栏是亮点：流式开始前记录持久的 activeWriterRunId，每次 transcript 追加都在同步 SQLite 事务内校验是否仍是当前声明 ⇒ 被取代的 run 提交不了脏数据。
>   - OpenCode：SQLite + Drizzle（opencode.db），消息模型 = 关系骨架 + JSON 载荷（message/part 整条 data 存 JSON 列）；revert 依赖独立 --git-dir 快照（<data>/snapshot/<projectID>/<hash(worktree)>），所以非 git 目录也能 undo。
>   - 事件溯源（event sourcing，事件溯源）范式的价值：dsh 明文“仅追加 SessionEvent 日志是模型所见上下文的来源，deriveMessages() 从日志投影并冻结——模型可见即已记录是运行时不变量”；好处是 fork/回放/审计免费获得，压缩只改投影不动事实。
>   - 选型判据：要 fork/回卷/审计 → 事件溯源（事件即事实，投影可重建）；只要恢复会话 → 结构化会话文件够用；多进程/多渠道并发 → SQLite 单写者（JSON 文件并发写会撕）；成本与计量审计 → usage 单独成表（ZCode 的 model_usage/turn_usage/tool_usage）。
>   - fork 有三个层次：会话分叉（session parent_id 树，ZCode/OpenCode 都有）、消息级回卷（OpenCode revert 沿 message/part 定位切点 + 快照回滚磁盘）、文件级 rewind（ZCode 的 file-rewind 与 /rewind 入口）。
> - 追问与陷阱：
>   - 追问：为什么不用纯 JSON 文件？常见错误：“简单透明”——并发写无原子性、查询与审计难、部分写损坏难恢复；OpenClaw 的每条 transcript 追加都进事务，是消息驱动场景的硬需求。
>   - 追问：压缩之后历史丢了怎么办？常见错误：摘要覆盖原文——不变量“日志为真源，压缩只改投影”，原文永远在盘上，摘要只是下一轮的视图。
>   - 追问：会话导出/分享要注意什么？常见错误：随手给链接——OpenCode 的 share 是 URL + secret 即读完整会话（含工具输出与文件内容），非端到端加密，默认应禁用或 manual。
> - 加分项：能说出 Codex 的 rollout 轨迹录制与重建（rollout_reconstruction）与远程压缩对持久化的影响；或 dsh 的 inbox 语义（注入的上下文留在 inbox 中直到被领取/唤醒，splice 坐标可回放）——持久化设计延伸到了输入侧。
> - 延伸阅读：[04-zcode 架构拆解 §9 会话与持久化](../04-zcode/架构拆解.md)｜[03-deepseek-harness 架构拆解 §5 会话日志：唯一真源](../03-deepseek-harness/架构拆解.md)｜[06-opencode 架构拆解 §10 持久化、fork、revert、share](../06-opencode/架构拆解.md)

> **Q056. A2A 协议与 MCP 的边界是什么？**（难度：中 ｜ 频次：低）
> - 考察点：两个协议的连接两端、暴露物、交互语义与信任模型差异，能否一句话说清“互补不竞争”。
> - 参考回答：
>   - A2A（Agent2Agent）是“agent 对 agent”的开放协议：让不同厂商、不同框架、跑在不同服务器上的 agent 以 agent 的身份（README 原话 as agents, not just as tools）互相发现、协商、委托长时任务，且互不暴露内部状态、记忆与工具（opaque，不透明）。
>   - 四个核心对象：Agent Card（智能体名片：能力/端点/认证的自描述文档，供发现）、Message（交互载荷）、Task（长时任务的声明式生命周期状态机：submitted→working→completed/failed）、Artifact（任务产物）；传输 JSON-RPC 2.0 over HTTP(S)，三种交互模式（同步 request/response、SSE 流式、异步 push notification）。
>   - 边界一张表：连接两端——A2A 是 agent↔agent（对等黑盒），MCP 是 agent↔工具/数据（透明功能提供方）；暴露物——A2A 只暴露名片，MCP 完整暴露工具 schema；交互语义——A2A 委托任务（长时、有状态机、可异步），MCP 调用函数（无状态请求-响应为主）；信任模型——A2A 跨信任域（企业间认证授权一等公民），MCP 多为本机/同域（stdio/localhost 常态）。
>   - 组合形态：一个 A2A server 背后可以是一个 LangGraph/CrewAI 编排的 agent 团队，它的工具面仍然全部走 MCP——“A2A 是组织间的前门，MCP 是系统内的水管”。
>   - 治理动态（2026-09-28 核实）：A2A 2025-04 由 Google 发布、2025-06 捐给 Linux Foundation、2026-08-27 加入 Agentic AI Foundation；最新 release v1.0.1（2026-05-28），官方 SDK 六种语言。
>   - 何时才需要：同信任域内的协作，六家全部用私有机制（工具结果、synthetic 消息、announce、mailbox），没有一个内部多 agent 走开放协议；协议化只出现在跨 harness/跨组织边界（dsh 委派给 Codex、OpenClaw 挂 ACP、企业间互联）——口诀：进程内用函数，进程间用消息，组织间用协议。
> - 追问与陷阱：
>   - 追问：A2A 是不是下一代 MCP？常见错误：“新协议取代旧协议”——两端不同、暴露物不同、语义不同（任务 vs 函数），互补不竞争；一个系统完全可以同时用。
>   - 追问：公司内部两个服务上的 agent 互联要用 A2A 吗？常见错误：“标准总没错”——每跳要付发现、协商、认证的元数据开销（社区俗称 A2A tax）；同域内用消息/函数即可，A2A 留给跨组织。
>   - 追问：A2A 成熟了吗？常见错误：“v1.0 就是终态”——规范仍在成熟期（Agent Card 内嵌凭据、QuerySkill 动态技能查询等列在未完事项），把它当“跨组织互操作的标准插座”来跟踪，不要当“进程内编排方案”来用。
> - 加分项：能指出 A2A 的“不透明”是设计而非缺陷——跨厂商互操作必须隐藏内部状态与工具面，这与 MCP“server 看不到对话”同属最小暴露原则；Google ADK 与 CrewAI 均已内建 A2A 暴露能力。
> - 延伸阅读：[multiagent-handbook §5 协议化协作：A2A 现状与 MCP 的角色边界](../multiagent-handbook/Multi-Agent协同手册.md)｜[mcp-handbook §1 MCP 是什么：架构与角色](../mcp-handbook/MCP搭建文档.md)

> **Q057. 什么是 lethal trifecta（致命三要素）？**（难度：中 ｜ 频次：中）
> - 考察点：能否把提示词注入风险从“玄学”收敛为一条可当场套用的充分条件判断，并给出断腿式防御。
> - 参考回答：
>   - 定义（Simon Willison 2025-06）：agent 可被注入打穿的充分条件是三要素齐备——①访问私有数据（邮件、文件、凭据、客户记录）；②接触不可信内容（网页、附件、issue 评论、检索片段——攻击者可控的任何文本/图片）；③对外通信能力（发邮件、发消息、出站 HTTP、写公开仓库）。
>   - 攻击链闭环机理：不可信内容里的指令驱动 agent 读私有数据，再从对外通道送出去——三腿齐立则提示词注入（prompt injection）链成立；经典应用安全的第一公理“指令与数据有边界”在 LLM 上失效，模型会把不可信文本里的指令当指令。
>   - 生产级实证：EchoLeak 的零点击全链——三要素齐备的真实案例（邮件场景：附件/正文为不可信内容、邮箱为私有数据、外发链接为出口）。
>   - 防御含义是断腿优先级：私有数据通常是业务价值所在、不可信内容通常是功能来源，都难砍；最容易也最值得砍的是第三条——出口（egress，出站通信）。落点是网络独立成轴：Codex 的 read-only 沙箱默认 network_access 关闭、OpenClaw 沙箱网络独立配置、出口域白名单、curl|bash 拒绝、自动渲染外部图片默认禁。
>   - 与权限设计的联动：三要素解释了为什么“网络”要单独成审批轴（security-handbook 的最小权限第四落点），而不仅按读/写分级。
>   - 持久化变体：注入的持久化形态是记忆污染——被注入的内容被存进记忆，下次会话继续作恶；对应防御是写入侧 provenance 与未 vet 内容禁止自动进 prompt（context-handbook §6.2）。
> - 追问与陷阱：
>   - 追问：加一个注入检测器够吗？常见错误：把检测器当安全边界——“永不注入成功”是错误目标（检测器水位有限），正确姿势是分层防御 + 断腿（出口控制），检测器只是其中一层。
>   - 追问：我的 agent 只读内部知识库，没有 trifecta 风险吧？常见错误：“没有网页就安全”——不可信内容包括用户上传附件、issue/工单评论、检索片段、同事转发的文档，甚至记忆里的污染内容；内部知识库也可能被写入污染。
>   - 追问：三要素全都有但“模型够聪明”行不行？常见错误：拿模型能力当防线——trifecta 是结构条件不是能力条件，模型再强也无法在指令与数据无边界的前提下可靠区分恶意指令。
> - 加分项：OpenClaw 的 taint 传播机制（工具声明为网络来源后，本轮内后续所有 assistant 消息被污染标记为 untrusted，直到下一条 user 消息）是“接触不可信内容”这条腿的运行时标记方案——把抽象威胁落成了实现。
> - 延伸阅读：[security-handbook §1.4 lethal trifecta：一条可以当场套用的公式](../security-handbook/AI应用安全手册.md)｜[security-handbook §2 Prompt Injection 专题](../security-handbook/AI应用安全手册.md)

> **Q058. 多 agent 的失败模式有哪些？怎么治理？**（难度：中 ｜ 频次：低）
> - 考察点：MAST 三大类 14 种失败分类学、“失败发生在接缝上”的推论、以及治理清单的工程化程度。
> - 参考回答：
>   - MAST（Multi-Agent System Failure Taxonomy，arXiv:2503.13657，UC Berkeley，NeurIPS 2025）是第一个系统性多 agent 失败分类学：从 7 个主流框架收集 1600+ 条标注轨迹，专家标注高一致性（κ=0.88），归纳出 3 大类 14 种失败模式——失败是可分类的工程对象，不是玄学。
>   - 三大类：①系统设计问题（specification issues：任务分解不合理、角色定义缺陷、缺验证环节——纸面上就错了）；②agent 之间失配（inter-agent misalignment：交接信息丢失/曲解、矛盾或重复的行动、隐瞒信息、对话绕圈——最频繁的大类，约四成）；③任务验证缺失（task verification：没验收步骤、验收标准太弱、带病产出直接交付）。
>   - 两个工程推论：失败发生在接缝上——每个 agent 单独评测全绿不等于系统可用，评测必须覆盖交接点；需要比“更好的 prompt”更结构化的解法（协议、验收、编排约束）。
>   - 六类经典失败 × 治理（逐条可背）：死循环 → 轮次上限 + token 预算 + 超限抛错绝不静默续跑（ZCode rapid-refill 熔断同源）；成本爆炸 → effort scaling 按难度定 agent 数与调用预算 + 每 agent 独立预算、编排者记账；角色漂移 → 窄系统提示 + 工具白名单构造时锁定；错误传播 → 每个交接点放验收门（“verify the world”，判据代码 > 规则 > LLM 打分）；通信失真 → 共享工件板为唯一真源、消息只带引用与摘要；权限洗白 → 权限不随消息流动（peer 消息降权、审批绑定操作者身份）。
>   - Anthropic 生产失败样本（每条都能对上 MAST 分类）：给简单查询派 50 个子代理（无力度分级）；子代理无穷搜索不存在的来源（验证缺失 + 预算失控）；子代理过度更新互相干扰（通信噪声）；委派含糊导致重复劳动（分解不清）；偏好 SEO 内容农场胜过权威学术 PDF（信源治理缺失）。
>   - 治理十条（上线前逐条过）的核心六条：每个 agent 有轮次上限与 token 预算；工具集构造时锁定白名单；子代理权限 ≤ 父代理且继承规则显式写下；权限不随消息流动；每个交接点有验收门；熔断降级——协作失败能退回单 agent 路径完成核心任务。
> - 追问与陷阱：
>   - 追问：最频繁的失败是哪类？常见错误：“模型能力不够”——②agent 间失配约占四成，是接缝问题不是单点能力问题；堆模型不如修协议。
>   - 追问：治理先上哪条？常见错误：先堆检测器——预算上限（止血）与交接验收门（断根）是杠杆最高的两条；可见性默认收窄（OpenClaw 的 visibility=all 教训）是最容易被忽略的一条。
>   - 追问：失败分类对评测有什么用？常见错误：只当知识背——归因时先看中间信号（检索命中、工具返回、交接消息）再选失败类，五分类归因（工具错/规划错/幻觉/环境错/判据错）+ MAST 大类双轴定位。
> - 加分项：κ=0.88 这个数字本身值得引——失败标注一致性高说明“失败模式”是可复现的研究对象；能顺带指出 MAST 结论（需要系统级解法）与 Cognition 原则（上下文必须共享）殊途同归。
> - 延伸阅读：[multiagent-handbook §6 失败模式与治理](../multiagent-handbook/Multi-Agent协同手册.md)｜[eval-handbook §6 轨迹评测：不只看最终答案](../eval-handbook/Agent评测与质量工程手册.md)

> **Q059. 控制流什么时候交给模型（agent）、什么时候写死（workflow）？怎么取舍？**（难度：高 ｜ 频次：高）
> - 考察点：六问判据能否直接套进业务方案、混合形态的三种拼法、以及“护栏位写死”的工程直觉。
> - 参考回答：
>   - 第一性区分（Anthropic 原文）：workflow 是 LLM 与工具经预先定义的代码路径编排；agent 是 LLM 动态指挥自己的过程与工具使用——唯一变量是控制流在谁手里。两种代价：workflow 僵化（变更走开发流程、覆盖不了没预设的情况），agent 不可预测（成本、延迟、错误级联难封顶）；总原则“先找最简方案，确有必要再升级”。
>   - 六问判据（都答“是”→ workflow；有一个“否”→ 倾向 agent）：步骤可枚举吗；输入输出可契约化吗；结果可程序验收吗；确定性是硬要求吗；变更频率低吗；错误代价高吗——注意第 4/6 问的方向：越是要确定性、错误代价越高，越要写死（退款、支付、合规话术）。
>   - 混合形态是生产主战场，三种标准拼法：画布里嵌 LLM 节点（流程骨架写死、个别节点让模型自由发挥——Anthropic 五种 workflow pattern 全是这个形态）；agent 里调子工作流（模型在开放循环里遇到“固定套路”就调一个写死的工作流工具）；工作流内置 Agent 接管层（腾讯 ADP：Agent 负责接管对话、控制节点跳转、识别退出意图，节点图管办事路径——把模型的灵活性装进确定性的壳）。
>   - 六家反面参照：没有一家提供画布式工作流引擎——coding 任务步骤不可枚举，写死路径做不了；但开发者写死的控制流只出现在三类护栏位：执行前闸门（审批/权限/沙箱）、上下文治理（压缩触发）、失败路径（重试/升级/熔断）——“办事路径交给模型，护栏写死”是 coding agent 给出的分工答案。
>   - 唯一成体系的例外是 ZCode dynamic workflow（代码态编排）：模型写 TypeScript 表达控制流 → 编译器静态分析（typecheck、依赖推断、taint 不动点决定并发与脏数据）→ 子进程 vm 独立 realm 执行（裸 vm 没有 process/require/fetch，只注入 __host 桥接宿主工具）→ SQLite journal 持久化。它回答的是“模型需要比画布拖拽更强的表达能力时，怎么不退回给模型一个 shell”——比 prompt 编排可验证、比 shell 可控。
>   - 两个工程信号：对话灵活度——需要多轮澄清但不破坏流程确定性的，用“工作流内置澄清”解决（ADP 工作流自动判断必填完整并生成反问话术）；规模信号——流程超过 15-20 个节点画布开始“拉面条”时，优先拆子工作流而不是继续加节点。
>   - 产品侧坐标系：腾讯 ADP 四模式谱系（标准 agent / 单工作流 / multi-agent / Claw 全权自主）就是“控制流从写死到全交给模型”的现成刻度，且 Agent 与 Workflow 双向互调已是平台级一等公民。
> - 追问与陷阱：
>   - 追问：流程经常变是不是就该上 agent？常见错误：忽略第 5 问的反面——结构未定的原型期写死路径等于每次改需求都改代码，但“内容常变、结构不变”的政策类流程仍是 workflow 的主场（改的只是内容不是结构）。
>   - 追问：高风险流程（支付/退款）能交给 agent 灵活处理吗？常见错误：“加个审批就行”——确定性是硬要求 + 错误代价高，判据两问直接判 workflow；agent 最多做外围（客服意图识别、工单预填）。
>   - 追问：五步以内的小流程用 agent 还是 workflow？常见错误：“小无所谓”——Anthropic 的原则是最简方案优先：步骤可枚举 + 可验收就写成固定管道，成本、延迟、可测性全面占优。
> - 加分项：能说出“工作流不是 agent 的替代，而是同一谱系的另一端；选型先问任务结构，再问产品形态”；并指出五种 workflow pattern（prompt chaining/routing/parallelization/orchestrator-workers/evaluator-optimizer）共享同一积木（augmented LLM），差别只在控制流形状。
> - 延伸阅读：[workflow-handbook §1 何时用工作流、何时用自主 Agent：确定性编排 vs 模型自由发挥](../workflow-handbook/Agent工作流编排手册.md)｜[multiagent-handbook §2.0 workflow 与 agent 的区分](../multiagent-handbook/Multi-Agent协同手册.md)｜[04-zcode 架构拆解 §10.3 dynamic workflow](../04-zcode/架构拆解.md)

> **Q060. 为什么 Claude Code、OpenClaw 等六家头部 agent 全部自研而不用 LangChain 等编排框架？**（难度：高 ｜ 频次：低）
> - 考察点：框架 vs 自研的工程判断力，能否给出需求侧原因而非“大厂傲慢”的叙事，并知道框架的正确适用区。
> - 参考回答：
>   - 事实（本工作区证据链）：六家生产级 agent（Claude Code/Codex/DeepSeek Harness/ZCode/OpenClaw/OpenCode）没有一个用 LangChain/LangGraph 等编排框架——它们把循环、工具注册、上下文管理写进自己的内核（python-handbook §4.7 选型决策树专门标注了这一行）。
>   - 原因一：绝对控制权。权限、压缩、并发是这类产品的命脉，框架的抽象层会挡在中间——anon-kode 的 query() 全文 519 行把并发判定、权限检查、递归全捏在手里；ZCode 三层循环把流恢复、取消快照、超窗压缩的恢复路径密度做到六家最高之一，这些都不是框架预留的扩展点能表达的。
>   - 原因二：需求特殊度高、核心代码量小。coding agent 需要 stop_reason 不可信的兜底、流式期间工具协调、doom-loop 检测、cache-control 必须在 provider 投影之后设置等细节，任何通用框架都要绕；而主循环本体只有 20-500 行——框架解决的是“不会写循环”的问题，六家的难点根本不在这里。
>   - 原因三：上下文经济学冲突。框架的每层抽象都会引入消息改写点，与“日志为真源、投影可重建”“缓存前缀稳定”直接冲突——一次隐藏改写就可能报废整轮缓存折扣。
>   - 框架侧自身在剧烈换代（2026-09-28 核实）：microsoft/autogen（61.2k star）已挂 Maintenance Mode（维护模式），接班人是 microsoft/agent-framework；openai/swarm 已被 OpenAI Agents SDK 取代（README 明示）；langchain-ai/open_deep_research 已归档（2026-08）——把产品命脉押在快速换代的编排框架上风险可见。
>   - 但结论不是“框架无用”：框架适合“应用”（业务编排、快速验证、需要 HITL/断点续跑的图状态机场景——LangGraph 核心包 1.2.12，2026-09-21 发布，仍是 deer-flow 等项目的生产底座）；自研适合“产品”（agent 本身就是产品）。选型决策树：需要多步状态机 → LangGraph；类型安全优先 → PydanticAI；生态广度 → LangChain 1.x create_agent；否则 openai-agents 或自研循环。
>   - 折中证据：ZCode dynamic workflow 是“自研 + 编译器验证”的第三种形态——不引入框架，但把编排表达力升级为代码 + 静态分析（taint 不动点）+ 受限运行时，说明自研路线也在吸收框架要解决的问题。
> - 追问与陷阱：
>   - 追问：新项目该自研还是用框架？常见错误：“大厂自研所以我也自研”——六家自研的前提是 agent 就是产品本身；做业务应用用 create_agent/LangGraph/openai-agents 起步更快，先建立手感再决定要不要下沉。
>   - 追问：自研循环最容易被低估的坑是什么？常见错误：以为难在循环——难在循环外：停止条件、错误恢复、权限闸门、压缩触发、缓存时序；这些恰是框架原本想替你做但做不深的部分。
>   - 追问：用框架是不是就没有控制权了？常见错误：二极管——框架按“应用”用法（固定管道 + 受控节点）可控性尚可；失控发生在把开放循环硬塞进框架抽象的那一刻，风险与用法有关而不仅是选型。
> - 加分项：能对比 anon-kode 519 行 query() 与 ZCode 三层循环的复杂度差距，说明“主循环”如何从函数长成子系统；或引 OpenClaw 约 60 个内置工具的 tool-catalog 分组 + preset 收窄，说明自研工具系统同样在做“框架式”的治理抽象。
> - 延伸阅读：[python-handbook §4.7 选型决策树](../python-handbook/Python大模型应用开发手册.md)｜[python-handbook §9 Agent 协议接入：MCP SDK、openai-agents 与自研循环](../python-handbook/Python大模型应用开发手册.md)｜[workflow-handbook §1.5 反面参照：六家 coding agent 为什么全都不用画布工作流](../workflow-handbook/Agent工作流编排手册.md)

本主题 20 题：难度 初 6 / 中 10 / 高 4；频次 高 8 / 中 8 / 低 4。
