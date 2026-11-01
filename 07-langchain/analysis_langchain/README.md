# Learn LangChain —— 把 agent 变成"声明式图编译产物"的框架方法论

> 献给想读懂 [LangChain 源码](../langchain/)（langchain-ai/langchain 快照 80b7409）的人。十课，每课：**中文讲解 + 注释版可运行代码 + 图解 + 对照真实源码的精读锚点**。体例对标 [03-deepseek-harness 的同款教材](../../03-deepseek-harness/analysis_deepseek_harness/)，事实对齐本仓 [源码解析与学习路线](../源码解析与学习路线.md)（其全部行号锚点在本课程中已逐一复核）。

## Agency 来自模型，LangChain 特殊在哪

**Agency 来自模型，Agent 产品 = 模型 + Harness（框架/载具）。** 模型是驾驶者，框架是载具——本课程教你造载具。

deepseek-harness 的差异化主张是"一切皆插件"；**LangChain 的差异化是另一句话：把 agent 变成"声明式图编译产物"的框架方法论**。`create_agent(model, tools)` 不写循环，只声明事实——然后编译器把这份声明装配成一张 LangGraph 状态图（model/tools 两节点、两条条件边成环），`compile()` 产出统一的 Runnable。换配置 = 重新编译；改行为 = 插中间件；跨轮次 = 检查点快照。配套的第二块基石是 LCEL：一切组件都是 Runnable，`a | b` 只是运算符重载。**"声明进、图出、协议统一"——这是 LangChain 的全部性格。**

## 语言选型说明

LangChain 本身是 Python 项目，但本课程沿用了 Claude Code 教材（analysis_claude_code）的先例——**"产品用什么语言"与"教材用什么语言"是两个独立决策**：全部 mini 实现用 **Python 纯标准库**（dataclasses / typing / asyncio 可用），保证零依赖、`python code.py` 直跑、离线可复现；每课的"对照真实源码"表给出真实包路径与行号，读 mini 是为了看懂结构，回源码是为了确认真相。模型一律由脚本化 Mock 扮演（完全离线）。

## 课程目录

| 课 | 主题 | 一句话 | 核心不变量 |
|----|------|--------|-----------|
| [s01_agent_compile](s01_agent_compile/) | create_agent 编译器 | 声明式配置 → 编译 → 可运行的 agent 图 | spec 是数据，图是编译产物 |
| [s02_runnable_lcel](s02_runnable_lcel/) | Runnable 与 LCEL | `a \| b` 的脱糖：运算符重载 + 归一化 + 串行管道 | 组合子层不知道组件层的存在 |
| [s03_tool_system](s03_tool_system/) | 工具系统 | @tool 反射 schema，tool_calls 与 ToolMessage 按 id 配对闭合 | 永远不存在悬空的 tool_calls |
| [s04_state_graph](s04_state_graph/) | StateGraph 底座 | 节点表 + 固定边表 + 条件边表，三张表就是图 | 节点不改历史，只提交补丁 |
| [s05_middleware](s05_middleware/) | 中间件 | 七个钩子位织入图；观察型改 state，包裹型拦调用 | 注册顺序即洋葱层级，顺序即安全边界 |
| [s06_memory_checkpointer](s06_memory_checkpointer/) | 记忆与检查点 | 消息列表跨调用存活；快照按 thread_id 隔离、可回溯 | 模型无状态；快照不可变；历史只增不改 |
| [s07_structured_output](s07_structured_output/) | 结构化输出 | schema 进 prompt → 校验 → 失败带原文重试；或借 final_answer 工具拿原生 JSON | 程序拿到的永远是校验过的数据 |
| [s08_rag_retriever](s08_rag_retriever/) | RAG 检索工具 | 检索器包装成工具：模型自主决定查不查、查什么 | 切分保语义、检索带阈值、结果带引文 |
| [s09_streaming](s09_streaming/) | 流式双通道 | 数据通道逐段到达（chunk 相加无损），事件通道交错记录 | sum(chunks) == invoke() |
| [s10_classic_vs_v1](s10_classic_vs_v1/) | classic vs v1 收官 | 兼容层是怎么包的；十课机制总装成一台整机 | 0.x 给循环让你填方法，1.x 给图让你插钩子 |

依赖关系是线性的：s01 先看到终点站，s02 起逐层拆解地基（但每课代码**自包含可独立运行**，跳读也不会断）。

> 相对工作区 9 份 agent 源码解析，本课程在骨架之外加了一课 [s02_runnable_lcel](s02_runnable_lcel/)——Runnable 协议与 LCEL 是 langchain-core 的心脏（源码解析文档第五、六节的主体），agent 的"编译产物是 Runnable"全靠它兜底。

## 运行

唯一前置：**Python ≥ 3.10**（无任何 pip 依赖，全部纯标准库）。逐课：

```bash
cd s04_state_graph && python code.py
```

或一键全跑：

```bat
run.bat        :: Windows
./run.sh       :: Linux / macOS
```

所有课程完全离线（模型由脚本化 Mock 扮演），`run.bat` 会跳过没有 `code.py` 的目录、逐课报错即停，全过打印 `All N lessons passed.`。

## 与本工作区其他材料的关系

- **先读什么**：没有 LangChain 概念时，先看 [本仓源码解析与学习路线](../源码解析与学习路线.md)（含 monorepo 地图与六个阶段路线）→ 再来逐课动手 → 最后按其阶段 4 的精读清单回真源码（[../langchain/](../langchain/)，快照 80b7409）。
- **下一层引擎**：agent 编译出的 StateGraph 由 LangGraph 引擎执行，图怎么跑、reducer 与中断恢复见 [08-langgraph 的源码解析](../../08-langgraph/源码解析与学习路线.md)；两仓各自的 analysis_* 姊妹课程体例一致（08 号侧若尚未创建，以工作区实际为准）。
- **横向对照**：Claude Code 教材见 [01-claude-code](../../01-claude-code/analysis_claude_code/)（Python 最小实现路线）；deepseek-harness 教材见 [03-deepseek-harness](../../03-deepseek-harness/analysis_deepseek_harness/)（TS 源码 + Node mini，"插件树"路线）。三家对照：Claude Code 把循环写死换极致简单，dsh 换插件清单，LangChain 换编译配置。
- **方法论延伸**：RAG 的语料准备与评估见 [rag-handbook/RAG搭建文档](../../rag-handbook/RAG搭建文档.md)（s08 只讲机制不讲工程）；Python 工程底子见 [python-handbook/Python大模型应用开发手册](../../python-handbook/Python大模型应用开发手册.md)；压缩与记忆的通用方法论见 [context-handbook](../../context-handbook/Context与记忆系统手册.md)。

## 免责与安全

本课程的全部代码是**教学用 mini 实现**：不 import langchain / langgraph / pydantic 等任何第三方库，不调用任何真实模型 API，模型全部由脚本化 Mock 扮演。"对照真实源码"表中的包路径与行号在快照 80b7409 上实测核对（方法：`sed -n 'Np' 文件`），代码演进后请以源码为准。课程内容仅用于学习，不构成对 LangChain 1.x API 的完整或最新描述。
