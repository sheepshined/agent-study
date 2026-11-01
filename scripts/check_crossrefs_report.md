# 文档一致性与交叉引用检查报告

- 生成器：`scripts/check_crossrefs.py`（确定性输出：同输入同输出）
- 扫描范围：工作区自产 markdown（排除 01-08 / project-study 内部 clone 的上游源码仓）
- 扫描文件数：97
- ERROR（断链/锚点失效）：0
- WARN（悬空引用，互引矩阵 REQUIRED_LINKS）：0

## 结论

**全部 PASS**：无断链、无锚点失效、互引矩阵无单向引用。

## 检查项说明

1. `BROKEN` 相对链接目标不存在；2. `ANCHOR` md 目标文件中无对应标题锚点（GitHub slug 规则：小写、空格→-、去标点、重复标题加 -N）；3. `DANGLING` 互引矩阵声明的目录对只有单向引用（被引用目录树内无任何文档回链）。

互引矩阵与豁免清单内嵌于 `scripts/check_crossrefs.py` 的 `REQUIRED_LINKS` / `EXEMPT_PAIRS`，修改矩阵请同步更新脚本并在本报告中重跑留档。


## 修复留档（2026-09-28，⑬ 中文化收尾任务 B 象限）

首跑结果：**ERROR 49 · WARN 11**。修复动作与复跑验证：

| 类别 | 首跑数量 | 根因 | 修复动作 | 复跑 |
|---|---|---|---|---|
| `BROKEN` 图片链接（`FDE认证课程全文.md` + 3 份 lessons） | 46 | `images/` 下 `2.2上/2.2中/2.2下` 三个子目录名当年被抓取工具以 URL 编码形态（`2.2%E4%B8%8A`）落盘，md 链接渲染时解码为中文后找不到目录 | 磁盘目录重命名为中文名（链接与语义对齐，不动文档） | 0 |
| `BROKEN` 代码伪链接（`interview-handbook/07-手撕代码与工程实践.md:40/90/528`） | 3 | `dict[key](**kwargs)` 形态的 Python 代码被 markdown 误渲染为链接，目标以 `*` 开头 | 脚本对目标以 `*` 开头的代码形态链接跳过检查（精确豁免，不掩盖真链接） | 0 |
| `DANGLING` 互引矩阵单向引用 | 11 | 新批次（mianjing/cloud/project-study/kaogong/cet4）引用了既有手册，既有手册侧缺反向链接 | 在 interview/deploy/tuning/kaogong/multiagent/08-langgraph/05-openclaw/fde 八侧各补一行反向交叉引用（只新增行） | 0 |
| `BROKEN` 新增（修复过程中自检发现） | 1 | 08 文档补链接时相对路径笔误（`langchain/` → `langgraph/`） | 改正路径 | 0 |

复跑（`python scripts/check_crossrefs.py --report`）：**ERROR 0 · WARN 0，全部 PASS**。本节由脚本在重新生成报告时自动保留（保留逻辑在 `--report` 分支内）。
