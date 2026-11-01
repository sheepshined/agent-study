# Python Handbook

> Python 方向的专题手册集。与工作区其他手册（MCP/Skill/RAG/提示词）定位互补：那些手册讲"如何构建 agent"，这里沉淀"Python 语言栈与算法基本功"。

## 目录

| 文件 / 子目录 | 内容 | 完成日期 |
|---|---|---|
| [Python大模型应用开发手册.md](Python大模型应用开发手册.md) | 单册十章：生态位（脚本/服务/数据/模型四类用法）→ 工程基座（uv/ruff/pytest/Pydantic）→ SDK 横评（openai/anthropic/google-genai/litellm）→ 编排框架横评（LangChain/LangGraph/LlamaIndex/DSPy/PydanticAI + 选型决策树）→ RAG 工具链 → 本地推理（transformers/vLLM/Ollama）→ 服务与界面（FastAPI/Gradio/Streamlit）→ 评测与可观测 → MCP 接入与 20 行自研循环 → 企业范例横向对比 + 三家精读 + 30 天上手清单 | 2026-09-27 |
| [leetcode-hot100/](leetcode-hot100/README.md) | 力扣 Hot 100 全解题解集（Python 3 · 教学导向）：12 个专题文件覆盖 17 个官方专题全部 100 题，每题四件套（① 题意速览 ② 思路讲解 ③ 注释代码 ④ 复杂度 · 易错点 · 面试追问），附 17 专题导航、难度分布统计与 14 天刷题路线 | 2026-09-27 |

## 约定

- 全部代码为 Python 3、中文注释——注释讲**机制与不变量**，不做逐行语法翻译。
- 英文术语首次出现处标注中文解释（延续本工作区惯例）。
- 网络/平台信息以当日实抓为准：题单题号/题名/难度取自 leetcode.cn GraphQL API，库版本取自 PyPI JSON API，各自首页标注信息基准日。

> 本文是 agent-study 工作区 **Python 大模型应用开发 + 力扣 Hot 100** 专题入口，与 eval/tuning（工程方法论）、interview（AI 应用岗题库）互补，全景见[根 README](../README.md)。
