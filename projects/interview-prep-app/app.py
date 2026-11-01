# -*- coding: utf-8 -*-
"""
app.py —— 面试备战站后端（FastAPI）。

架构一句话：build_index.py 把 interview-handbook/*.md 解析为 data/index.json（只读加载进内存），
本服务在其上提供 题库检索 / 卡片自测 / 错题本 / 进度统计 四组 API，学习状态落盘 data/state.json，
前端是 static/ 下的原生单页（无构建链）。

端口与文件路径可用环境变量覆盖（冒烟测试靠它隔离状态文件）：
    PREP_PORT=8765  PREP_STATE_PATH=data/state.json  python app.py

机制与不变量：
1. 索引只读加载：index.json 由 build_index.py 一次性产出，服务只读不写；
   启动时加载进内存，128 题约 527KB，换进程内查询零 IO。索引缺失时服务仍可启动
   但 /readyz 返回 503——"活着"与"能用"是两个协议位（借 deploy-handbook §9 的健康检查语义）。
2. state 读写加锁：所有对 state 的读-改-写都持同一把 threading.Lock，
   防止并发请求交错导致丢更新；写盘走"临时文件 + os.replace"原子替换，
   进程中途崩溃只会留下完整的旧文件或新文件，不会留下半截 JSON。
   边界：锁是进程内的，多 worker 部署需换文件锁（本应用单 worker 运行，README 已注明）。
3. 错题本是推导视图不是存储实体：磁盘上只存每题的最新自评与历史轨迹，
   "错题本"= 最新自评 ∈ {half, no} 且未被手动移除（dismissed）的题集合。
   重测提交新自评会自动进出错题本，无需手工同步——单一事实源，无第二处可漂移的状态。
4. 便宜检查挡在贵调用前面：rating/qid 合法性校验在读请求体之后、
   触碰 state 之前完成，非法请求根本不进锁（借 deploy-handbook §9 的顺序原则）。
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

APP_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = APP_ROOT.parent.parent
INDEX_PATH = APP_ROOT / "data" / "index.json"
STATIC_DIR = APP_ROOT / "static"
STATE_PATH = Path(os.environ.get("PREP_STATE_PATH", str(APP_ROOT / "data" / "state.json")))
PORT = int(os.environ.get("PREP_PORT", "8765"))

# 三档自评的唯一合法取值：know=会 / half=半会 / no=不会
RATINGS = ("know", "half", "no")
WRONGBOOK_RATINGS = ("half", "no")  # 落入错题本的两档

app = FastAPI(title="面试备战站", docs_url="/api/docs")

# ---- 全局可变状态：索引（启动后只读）与学习状态（锁保护） ----
_index: Optional[dict] = None
_questions_by_id: dict[str, dict] = {}
_state_lock = threading.Lock()
_state: dict = {"version": 1, "reviews": {}}


def load_index() -> None:
    """加载 index.json；失败不抛异常——服务照常启动，但 /readyz 报 503。"""
    global _index, _questions_by_id
    try:
        _index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        _questions_by_id = {q["id"]: q for q in _index["questions"]}
    except (OSError, json.JSONDecodeError, KeyError):
        _index = None
        _questions_by_id = {}


def load_state() -> None:
    """启动时读回 state.json；文件缺失或损坏视为空状态（首次运行是常态，不算错误）。"""
    global _state
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "reviews" in data:
            _state = data
    except (OSError, json.JSONDecodeError):
        _state = {"version": 1, "reviews": {}}


def save_state_locked() -> None:
    """原子写盘（调用方必须已持有 _state_lock）。

    机制：写同目录临时文件 → os.replace 原子覆盖。replace 保证目标路径
    要么是旧完整文件、要么是新完整文件，崩溃不会留下半截 JSON。
    """
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(_state, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_PATH)


def card_view(qid: str) -> dict:
    """从 state 推导单题的自测视图（最新档位、是否在错题本）。"""
    review = _state["reviews"].get(qid)
    if not review:
        return {"latest": None, "in_wrongbook": False, "reviewed": False}
    latest = review.get("latest")
    return {
        "latest": latest,
        "reviewed": True,
        "in_wrongbook": latest in WRONGBOOK_RATINGS and not review.get("dismissed", False),
    }


def require_index() -> dict:
    """索引缺失时统一报 503，让前端给出"先跑 build_index.py"的明确指引。"""
    if _index is None:
        raise HTTPException(503, "索引未加载：请先运行 python build_index.py 再重启服务")
    return _index


# ---- 模块级启动加载：无论 python app.py 还是 uvicorn app:app 都生效 ----
load_index()
load_state()


# ---------------- 健康检查（两层语义，借 deploy-handbook §9） ----------------

@app.get("/healthz")
def healthz():
    """liveness：进程活着即 200，编排器据它决定重启。"""
    return "ok"


@app.get("/readyz")
def readyz():
    """readiness：索引加载完成才 200，否则 503——据它决定是否接流量。"""
    if _index is None:
        raise HTTPException(503, "索引未加载")
    return {"ready": True, "questions": len(_questions_by_id)}


# ---------------- 功能 1：题库浏览与检索 ----------------

@app.get("/api/meta")
def meta():
    """主题列表 + 全库静态统计 + 三档自评枚举（前端初始化用）。"""
    idx = require_index()
    return {"topics": idx["topics"], "stats": idx["stats"], "ratings": list(RATINGS)}


@app.get("/api/questions")
def list_questions(
    topic: Optional[str] = None,
    difficulty: Optional[str] = None,
    frequency: Optional[str] = None,
    q: Optional[str] = None,
    status: Optional[str] = None,  # untested / wrongbook / know / half / no
    page: int = 1,
    page_size: int = 50,
):
    """题库检索：主题/难度/频次/关键词四维过滤 + 自测状态过滤 + 分页。

    关键词匹配题干（不搜答案正文——刷题阶段先按题目定位，避免答案关键词误命中）。
    """
    idx = require_index()
    if page < 1 or page_size < 1 or page_size > 200:
        raise HTTPException(400, "分页参数不合法：page>=1，1<=page_size<=200")

    keyword = (q or "").strip().lower()
    items = []
    for question in idx["questions"]:
        view = card_view(question["id"])
        if topic and question["topic"] != topic:
            continue
        if difficulty and question["difficulty"] != difficulty:
            continue
        if frequency and question["frequency"] != frequency:
            continue
        if keyword and keyword not in question["title"].lower():
            continue
        if status == "untested" and view["reviewed"]:
            continue
        if status == "wrongbook" and not view["in_wrongbook"]:
            continue
        if status in RATINGS and view["latest"] != status:
            continue
        items.append(
            {
                "id": question["id"],
                "title": question["title"],
                "difficulty": question["difficulty"],
                "frequency": question["frequency"],
                "topic": question["topic"],
                "topic_name": next(t["name"] for t in idx["topics"] if t["id"] == question["topic"]),
                **view,
            }
        )

    total = len(items)
    start = (page - 1) * page_size
    return {"total": total, "page": page, "page_size": page_size, "items": items[start : start + page_size]}


@app.get("/api/questions/{qid}")
def question_detail(qid: str):
    """单题详情：四件套全文 + 延伸阅读链接 + 自测状态。"""
    idx = require_index()
    question = _questions_by_id.get(qid)
    if question is None:
        raise HTTPException(404, f"未知题号 {qid}")
    topic_name = next(t["name"] for t in idx["topics"] if t["id"] == question["topic"])
    return {**question, "topic_name": topic_name, **card_view(qid)}


# ---------------- 功能 2：卡片自测（自评三档） ----------------

class ReviewIn(BaseModel):
    qid: str
    rating: str  # know / half / no，手工校验以返回中文 400


@app.post("/api/reviews")
def submit_review(body: ReviewIn):
    """提交一次自评。机制：新自评覆盖 latest、重置 dismissed、追加 history。

    不变量：错题本成员资格由 latest 推导（见文件头注释 3），
    因此"重测改评"自动完成进出错题本，不需要也不存在第二个同步入口。
    """
    require_index()
    if body.rating not in RATINGS:
        raise HTTPException(400, f"rating 必须是 {'/'.join(RATINGS)} 之一，收到 {body.rating!r}")
    if body.qid not in _questions_by_id:
        raise HTTPException(404, f"未知题号 {body.qid}")

    with _state_lock:
        now = datetime.now().isoformat(timespec="seconds")
        review = _state["reviews"].setdefault(
            body.qid, {"latest": None, "updated_at": None, "dismissed": False, "history": []}
        )
        review["latest"] = body.rating
        review["updated_at"] = now
        review["dismissed"] = False  # 新自评重置手动移除标记：再答"不会"就该回错题本
        review["history"].append({"rating": body.rating, "ts": now})
        save_state_locked()
        view = card_view(body.qid)
    return {"qid": body.qid, **view}


# ---------------- 功能 3：错题本 ----------------

@app.get("/api/wrongbook")
def wrongbook():
    """错题本：最新自评为 半会/不会 且未被手动移除的题（推导视图，实时一致）。"""
    idx = require_index()
    items = []
    for question in idx["questions"]:
        view = card_view(question["id"])
        if view["in_wrongbook"]:
            items.append({**{k: question[k] for k in ("id", "title", "difficulty", "frequency", "topic")}, **view})
    return {"total": len(items), "items": items}


@app.post("/api/wrongbook/{qid}/dismiss")
def dismiss_wrongbook(qid: str):
    """手动移出错题本：只改 dismissed 标记，不动自评历史。

    不变量：dismissed 只对"当前在错题本里"的题有意义，其余情况报 404，
    防止把dismissed 标记悄悄写到无关题目上。
    """
    require_index()
    with _state_lock:
        review = _state["reviews"].get(qid)
        if not review or review.get("latest") not in WRONGBOOK_RATINGS or review.get("dismissed"):
            raise HTTPException(404, f"题号 {qid} 当前不在错题本中，无法移除")
        review["dismissed"] = True
        save_state_locked()
        view = card_view(qid)
    return {"qid": qid, **view}


# ---------------- 功能 4：进度统计 ----------------

@app.get("/api/stats")
def stats():
    """进度统计：全库 + 每主题的完成率/错题率/自评分布（推导自 state，实时计算）。"""
    idx = require_index()
    topics = {t["id"]: t for t in idx["topics"]}
    per_topic = {
        tid: {"topic": tid, "name": topics[tid]["name"], "total": 0,
              "reviewed": 0, "know": 0, "half": 0, "no": 0}
        for tid in topics
    }
    overall = {"know": 0, "half": 0, "no": 0, "untested": 0}
    for question in idx["questions"]:
        row = per_topic[question["topic"]]
        row["total"] += 1
        latest = _state["reviews"].get(question["id"], {}).get("latest")
        if latest is None:
            overall["untested"] += 1
        else:
            row["reviewed"] += 1
            row[latest] += 1
            overall[latest] += 1

    total = idx["stats"]["total"]
    reviewed = total - overall["untested"]
    for row in per_topic.values():
        row["completion"] = round(row["reviewed"] / row["total"], 4) if row["total"] else 0.0
        row["wrong_rate"] = (
            round((row["half"] + row["no"]) / row["reviewed"], 4) if row["reviewed"] else 0.0
        )
    return {
        "total": total,
        "reviewed": reviewed,
        "completion": round(reviewed / total, 4) if total else 0.0,
        "wrong_rate": round((overall["half"] + overall["no"]) / reviewed, 4) if reviewed else 0.0,
        "distribution": overall,
        "by_topic": list(per_topic.values()),
    }


# ---------------- 静态资源 ----------------

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
# 工作区根只读托管：题目"延伸阅读"的相对链接 ../xxx-handbook/... 由前端改写为 /workspace/...，
# 点击可回查原手册。只读挂载，不写不动既有目录。
app.mount("/workspace", StaticFiles(directory=str(WORKSPACE_ROOT)), name="workspace")


@app.get("/")
def index_page():
    """单页入口。"""
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    load_index()
    load_state()
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
