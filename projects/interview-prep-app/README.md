# 面试备战站（自建项目）

> 信息基准日：2026-09-28。本目录是一个**可运行的本地 Web 应用**（不是手册）：
> 把工作区 [interview-handbook](../../interview-handbook/README.md) 的 128 道面试题变成
> 能检索、能自测、能记错题、能看进度的刷题站。Python 后端 + 原生前端，无数据库、无前端构建链。

## 架构一句话图

```mermaid
flowchart LR
    A["interview-handbook/*.md<br/>七个题集（只读）"] -->|"build_index.py 解析<br/>失败即报错退出"| B["data/index.json<br/>128 题索引（幂等产物）"]
    B -->|"启动时只读加载"| C["app.py · FastAPI<br/>/api/* 五组接口 + /healthz /readyz"]
    C <-->|"读写加锁<br/>原子替换落盘"| D["data/state.json<br/>自评记录（唯一事实源）"]
    E["static/ 原生单页<br/>仪表盘/题库/自测/错题本"] -->|"fetch"| C
    C -.->|"/workspace 只读挂载"| F["工作区各手册<br/>（延伸阅读回查）"]
```

- **索引是构建产物**：`index.json` 由 `build_index.py` 从题集 .md 生成，服务只读；
  输出不含时间戳，同输入必同输出（幂等），两次构建 sha256 一致。
- **错题本是推导视图不是存储实体**：磁盘上只存每题最新自评（`know/half/no`）与历史轨迹，
  "错题本" = 最新自评 ∈ {半会, 不会} 且未被手动移除。重测改评自动进出错题本，无需手工同步。
- **state 读写加锁 + 原子落盘**：所有读-改-写持同一把进程内锁；写盘走"临时文件 + os.replace"，
  崩溃只留完整旧文件或新文件，不会留半截 JSON。
- **健康检查两层语义**（借 deploy-handbook §9）：`/healthz` 进程活着即 200（liveness），
  `/readyz` 索引加载完成才 200（readiness），索引缺失时服务起得来但报 503 并提示先跑构建脚本。

## 启动三步

```bash
cd projects/interview-prep-app
python build_index.py     # ① 解析七个题集 → data/index.json（解析失败会列出全部错误并退出）
python app.py             # ② 起服务，默认 http://127.0.0.1:8765（可用 PREP_PORT 改端口）
# ③ 浏览器打开 http://127.0.0.1:8765
```

可选：`python smoke_test.py` 跑 42 项冒烟测试（独立端口 + 独立状态文件，不污染真实数据）。
环境要求：Python 3.10+，`fastapi`、`uvicorn`、`requests`（仅冒烟测试用；本机实抓版本
fastapi 0.138.2 / uvicorn 0.48.0 / requests 2.33.0 / Python 3.13.5）。

## 功能对照表

| # | 需求功能 | 实现 | 验证入口 |
|---|---|---|---|
| 1 | 题库浏览与检索 | 「题库检索」视图：主题/难度/频次/关键词/自测状态五维过滤 + 分页；详情弹层渲染四件套全文（考察点/参考回答/追问与陷阱/加分项/延伸阅读） | `GET /api/questions`、`GET /api/questions/{qid}` |
| 2 | 卡片自测 | 「卡片自测」视图：按主题/难度/频次/范围（全部/未测/错题本/高频）组卷、可乱序；正面题干、背面参考回答；自评三档 会(know)/半会(half)/不会(no) 写入服务端 | `POST /api/reviews` |
| 3 | 错题本 | 半会/不会自动入本；支持移除（dismiss 标记）与重测（改评自动出本）；单题重测入口 | `GET /api/wrongbook`、`POST /api/wrongbook/{qid}/dismiss` |
| 4 | 进度统计仪表盘 | 首页四卡（总数/已测/完成率/错题率）+ 全库自评分布条 + 每主题完成率/错题率/分布表 | `GET /api/stats` |
| 5 | JSON 持久化 | `data/state.json` 服务端落盘，无数据库；跨重启数据仍在（冒烟测试有专项验证） | `data/state.json` |

## Markdown 渲染说明（离线降级方案）

题目四件套是 Markdown（粗体/行内码/链接/两级列表/``` 围栏代码块）。前端 `static/app.js` 的
`mdRender()` 是**极简自实现渲染器**，不引 marked.js CDN——这就是离线降级方案本体：
断网/内网环境照常渲染，`static/` 三个文件自包含。代价是不支持的语法（表格、图片等）按纯文本显示，
题库正文实测只用到上述五种语法，已全覆盖；代码块渲染为深色 `<pre><code>`（07 手撕题 16 题的
代码骨架实测可读）。

延伸阅读链接原文是工作区相对路径（`../tuning-handbook/...`），前端改写为 `/workspace/...`
由后端只读挂载直出，点击可回查原手册章节。

## 验证记录（2026-09-28 本机实跑）

### ① 冒烟测试：42/42 全 PASS

`python smoke_test.py` 覆盖五功能关键路径 + 幂等不变量 + 跨重启持久化，
完整输出存档 [data/smoke_test_output.txt](data/smoke_test_output.txt)。摘录：

```text
== 冒烟测试：http://127.0.0.1:8799（状态文件 state_smoke.json）==

[PASS] 索引构建幂等：两次构建 sha256 一致
[PASS] healthz 200 且返回 ok
[PASS] readyz 200 且题数 128
[PASS] meta 主题数 = 7
[PASS] 全量列表 total = 128
[PASS] 按主题过滤：topic=01 → 20 题
[PASS] 按难度过滤：初 → 38 题
[PASS] 按频次过滤：高 → 52 题
[PASS] 组合过滤：01+高 → 4 题
[PASS] 关键词检索：'token' 命中 ≥1
[PASS] 详情 Q001 四件套齐全且非空
[PASS] 非法 rating → 400
[PASS] Q001 自评'不会'生效
[PASS] 错题本自动收 2 题（Q001/Q002）
[PASS] 手动移除 Q001 成功
[PASS] 重复移除 → 404
[PASS] 重测再答'不会'自动回错题本（dismissed 被重置）
[PASS] 重测改评'会'自动出错题本
[PASS] 统计：主题01 完成 2/20=0.1、错题率 0.5
[PASS] state.json 已落盘
[PASS] 原子写无残留 .tmp 文件
[PASS] 重启后错题本仍含 Q002（真持久化而非内存态）

== 结果：42/42 PASS ==
全 PASS：五功能关键路径 + 幂等 + 持久化全部通过
```

### ② 解析校验：与总 README 登记口径交叉核对全过

`build_index.py` 除解析 128 题外，还逐主题核对题数/高频数/难度分布/频次分布与
interview-handbook/README.md 两张登记表（构建自校验，题库将来增删题时口径漂移会当场报错）：

```text
[build_index] OK：7 主题 / 128 题 → data/index.json
[build_index] 难度分布 {'初': 38, '中': 58, '高': 32}，频次分布 {'高': 52, '中': 47, '低': 29}
[build_index] 产物大小 527 KB（幂等：再跑一次字节级不变）
```

### ③ 浏览器实机抽查（2026-09-28，Chromium 1280×720）

四视图 + 详情弹层逐一截图核验：仪表盘统计卡/分布条/主题表渲染正确；题库列表 128 条命中、
难度/频次/自评徽章正确；Q001 详情四件套全文渲染、延伸阅读链接可达 `/workspace/...`；
自测卡片正面→翻面→自评"半会"→推进下一题；错题本显示 Q011（半会）并带重测/移除按钮；
Q120 手撕题代码骨架以深色代码块渲染。抽查中发现并修复 2 处：详情接口漏 `topic_name` 字段
（主题徽章显示 undefined）、渲染器缺 ``` 围栏代码块支持；修复后复验通过。

## 已知边界

- **单 worker 进程锁**：state 加锁是进程内的（`threading.Lock`），`python app.py` 默认单 worker
  没有问题；若改多 worker 部署需换文件锁或换存储——本地刷题工具按单进程设计，不做过度工程。
- **索引不热更新**：题集 .md 改动后需重跑 `build_index.py` 并重启服务（服务启动时一次性加载索引）。
- **延伸阅读是只读直出**：`/workspace` 挂载把整个工作区根目录只读暴露给本机回查手册用，
  仅限本机自用（服务默认只绑 127.0.0.1），不要把这个端口暴露到公网。
- **算法题不在题库**：数据源只有 interview-handbook 七个题集（Q001-Q128），leetcode-hot100
  算法题按原分工不进本应用。
- **自评是单浏览器共用状态**：state.json 没有用户体系，默认本机一人使用；多人各刷各的
  可用 `PREP_STATE_PATH` 环境变量起多个实例（不同端口）。
- **数据文件说明（gitignore 风格）**：`data/index.json` 是构建产物、可随时重建；
  `data/state.json` 是你的学习记录（删除即清零重开）；两者入真仓库时都应 ignore，
  见 [.gitignore](.gitignore)。`data/smoke_test_output.txt` 是最近一次冒烟输出存档。

## 文件清单

| 文件 | 说明 |
|---|---|
| [build_index.py](build_index.py) | 解析 interview-handbook/*.md → data/index.json；失败报错列出、幂等输出、与 README 登记表交叉核对 |
| [app.py](app.py) | FastAPI 后端：五组 API + 两层健康检查 + 静态/工作区只读挂载；state 加锁 + 原子落盘 |
| [smoke_test.py](smoke_test.py) | 冒烟测试 42 项：五功能关键路径 + 幂等 + 跨重启持久化；独立端口与状态文件隔离 |
| [static/index.html](static/index.html) | 单页骨架：四视图 + 详情弹层 |
| [static/style.css](static/style.css) | 原生样式：仪表盘卡片/徽章/进度条/代码块 |
| [static/app.js](static/app.js) | 原生 JS：检索/自测/错题本/统计逻辑 + 极简 Markdown 渲染器 |
| [data/](data/) | index.json（构建产物）、state.json（学习状态，运行时生成）、smoke_test_output.txt |
