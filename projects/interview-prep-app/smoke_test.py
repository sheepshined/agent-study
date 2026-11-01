# -*- coding: utf-8 -*-
"""
smoke_test.py —— 面试备战站冒烟测试（requests 直打 HTTP 接口）。

覆盖面（对应五大功能 + 两项工程不变量）：
  健康检查   /healthz /readyz 两层协议位
  ①题库检索  全量列表 / 主题/难度/频次/关键词/状态过滤 / 分页 / 详情四件套 / 404
  ②卡片自测  自评提交（合法三档）+ 非法 rating 400 / 未知题号 404
  ③错题本    半会/不会自动入本 / 手动移除 / 重复移除 404 / 重测改评自动进出
  ④进度统计  完成率/错题率/分布与手工核算一致
  ⑤持久化    state.json 落盘且为合法 JSON；杀进程重启后数据仍在（真持久化而非内存态）
  幂等不变量  build_index.py 连跑两次，index.json 字节级一致（sha256 对比）

隔离机制：服务用独立端口（PREP_PORT=8799）与独立状态文件（PREP_STATE_PATH=data/state_smoke.json）
子进程启动，测试结束清理——绝不污染真实使用时的 data/state.json。
结论口径：逐项打印 PASS/FAIL，全 PASS 退出码 0，任一 FAIL 退出码 1（可接 CI）。
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

APP_ROOT = Path(__file__).resolve().parent
PORT = 8799
BASE = f"http://127.0.0.1:{PORT}"
STATE_PATH = APP_ROOT / "data" / "state_smoke.json"
INDEX_PATH = APP_ROOT / "data" / "index.json"

results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, bool(cond), detail))
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f" —— {detail}" if (detail and not cond) else ""))


def start_server() -> subprocess.Popen:
    """子进程起服务：独立端口 + 独立状态文件，与真实使用环境完全隔离。"""
    env = {**os.environ, "PREP_PORT": str(PORT), "PREP_STATE_PATH": str(STATE_PATH)}
    proc = subprocess.Popen(
        [sys.executable, str(APP_ROOT / "app.py")],
        cwd=str(APP_ROOT), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    # 轮询 /readyz 直到索引加载完成（最多 30s），避免竞态：服务没起就发请求
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            r = requests.get(BASE + "/readyz", timeout=2)
            if r.status_code == 200:
                return proc
        except requests.ConnectionError:
            pass
        time.sleep(0.3)
    proc.terminate()
    out = proc.stdout.read().decode("utf-8", errors="replace") if proc.stdout else ""
    raise RuntimeError(f"服务 30s 内未就绪。子进程输出：\n{out[-2000:]}")


def stop_server(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    print(f"== 冒烟测试：{BASE}（状态文件 {STATE_PATH.name}）==\n")

    # ---- 前置：索引存在且构建幂等（同输入必同输出） ----
    if not INDEX_PATH.exists():
        print("[build] index.json 不存在，先执行 build_index.py")
        subprocess.run([sys.executable, str(APP_ROOT / "build_index.py")], check=True)
    h1 = sha256(INDEX_PATH)
    subprocess.run([sys.executable, str(APP_ROOT / "build_index.py"), "--quiet"],
                   check=True, cwd=str(APP_ROOT))
    h2 = sha256(INDEX_PATH)
    check("索引构建幂等：两次构建 sha256 一致", h1 == h2, f"{h1[:12]}… vs {h2[:12]}…")

    proc = start_server()
    try:
        s = requests.Session()

        # ---- 健康检查两层语义 ----
        r = s.get(BASE + "/healthz")
        check("healthz 200 且返回 ok", r.status_code == 200 and r.json() == "ok")
        r = s.get(BASE + "/readyz")
        check("readyz 200 且题数 128", r.status_code == 200 and r.json().get("questions") == 128)

        # ---- 功能①：题库检索 ----
        r = s.get(BASE + "/api/meta")
        meta = r.json()
        check("meta 主题数 = 7", r.status_code == 200 and len(meta["topics"]) == 7)
        check("meta 静态统计 total = 128", meta["stats"]["total"] == 128)
        check("meta 自评枚举三档", meta["ratings"] == ["know", "half", "no"])

        r = s.get(BASE + "/api/questions")
        data = r.json()
        check("全量列表 total = 128", data["total"] == 128)
        check("默认分页 page_size=50 截断生效", len(data["items"]) == 50)

        r = s.get(BASE + "/api/questions", params={"topic": "01"})
        check("按主题过滤：topic=01 → 20 题", r.json()["total"] == 20)
        r = s.get(BASE + "/api/questions", params={"difficulty": "初"})
        check("按难度过滤：初 → 38 题", r.json()["total"] == 38)
        r = s.get(BASE + "/api/questions", params={"frequency": "高"})
        check("按频次过滤：高 → 52 题", r.json()["total"] == 52)
        r = s.get(BASE + "/api/questions", params={"topic": "01", "difficulty": "高"})
        check("组合过滤：01+高 → 4 题", r.json()["total"] == 4)
        r = s.get(BASE + "/api/questions", params={"q": "token"})
        check("关键词检索：'token' 命中 ≥1", r.json()["total"] >= 1,
              f"实际 {r.json()['total']}")
        r = s.get(BASE + "/api/questions", params={"status": "untested"})
        check("状态过滤：全新状态下未测 = 128", r.json()["total"] == 128)
        r = s.get(BASE + "/api/questions", params={"page": 2, "page_size": 10})
        check("分页：page=2/page_size=10 返回 10 条", len(r.json()["items"]) == 10)

        r = s.get(BASE + "/api/questions/Q001")
        q = r.json()
        check("详情 Q001 四件套齐全且非空",
              all(q["sections"].get(k, "").strip()
                  for k in ("考察点", "参考回答", "追问与陷阱", "加分项", "延伸阅读")))
        check("详情 Q001 延伸阅读链接 ≥1", len(q["links"]) >= 1)
        check("详情 Q001 难度/频次标签正确", q["difficulty"] == "初" and q["frequency"] == "高")
        r = s.get(BASE + "/api/questions/Q999")
        check("未知题号详情 → 404", r.status_code == 404)

        # ---- 功能②：卡片自测（含非法输入边界） ----
        r = s.post(BASE + "/api/reviews", json={"qid": "Q001", "rating": "maybe"})
        check("非法 rating → 400", r.status_code == 400, f"实际 {r.status_code}")
        r = s.post(BASE + "/api/reviews", json={"qid": "Q999", "rating": "know"})
        check("未知题号自评 → 404", r.status_code == 404, f"实际 {r.status_code}")
        r = s.post(BASE + "/api/reviews", json={"qid": "Q001", "rating": "no"})
        body = r.json()
        check("Q001 自评'不会'生效", r.status_code == 200
              and body["latest"] == "no" and body["in_wrongbook"] is True)
        r = s.post(BASE + "/api/reviews", json={"qid": "Q002", "rating": "half"})
        check("Q002 自评'半会'生效并入错题本",
              r.json()["latest"] == "half" and r.json()["in_wrongbook"] is True)

        # ---- 功能③：错题本 ----
        r = s.get(BASE + "/api/wrongbook")
        wb = r.json()
        check("错题本自动收 2 题（Q001/Q002）",
              wb["total"] == 2 and {i["id"] for i in wb["items"]} == {"Q001", "Q002"})
        r = s.post(BASE + "/api/wrongbook/Q001/dismiss")
        check("手动移除 Q001 成功", r.status_code == 200 and r.json()["in_wrongbook"] is False)
        r = s.get(BASE + "/api/wrongbook")
        check("移除后错题本只剩 Q002",
              r.json()["total"] == 1 and r.json()["items"][0]["id"] == "Q002")
        r = s.post(BASE + "/api/wrongbook/Q001/dismiss")
        check("重复移除 → 404", r.status_code == 404, f"实际 {r.status_code}")
        r = s.post(BASE + "/api/reviews", json={"qid": "Q001", "rating": "no"})
        check("重测再答'不会'自动回错题本（dismissed 被重置）",
              r.json()["in_wrongbook"] is True)
        r = s.post(BASE + "/api/reviews", json={"qid": "Q001", "rating": "know"})
        check("重测改评'会'自动出错题本", r.json()["in_wrongbook"] is False)
        r = s.get(BASE + "/api/wrongbook")
        check("最终错题本只剩 Q002",
              r.json()["total"] == 1 and r.json()["items"][0]["id"] == "Q002")
        r = s.get(BASE + "/api/questions", params={"status": "wrongbook"})
        check("检索接口按错题本状态过滤一致", r.json()["total"] == 1)

        # ---- 功能④：进度统计 ----
        r = s.get(BASE + "/api/stats")
        st = r.json()
        check("统计：reviewed = 2", st["reviewed"] == 2)
        check("统计：分布 会1/半会1/不会0",
              st["distribution"]["know"] == 1 and st["distribution"]["half"] == 1
              and st["distribution"]["no"] == 0)
        t01 = next(t for t in st["by_topic"] if t["topic"] == "01")
        check("统计：主题01 完成 2/20=0.1、错题率 0.5",
              t01["reviewed"] == 2 and abs(t01["completion"] - 0.1) < 1e-9
              and abs(t01["wrong_rate"] - 0.5) < 1e-9)
        check("统计：全库完成率 2/128（4 位小数舍入口径）",
              abs(st["completion"] - round(2 / 128, 4)) < 1e-9)

        # ---- 页面与工作区挂载 ----
        r = s.get(BASE + "/")
        check("单页入口 200 且含标题", r.status_code == 200 and "面试备战站" in r.text)
        r = s.get(BASE + "/static/app.js")
        check("静态资源可访问", r.status_code == 200 and "mdRender" in r.text)
        r = s.get(BASE + "/workspace/interview-handbook/README.md")
        check("工作区只读挂载可达（延伸阅读回查）", r.status_code == 200)

        # ---- 功能⑤：持久化（落盘 + 跨重启） ----
        check("state.json 已落盘", STATE_PATH.exists())
        on_disk = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        check("state.json 为合法 JSON 且含 Q001 历史",
              "Q001" in on_disk["reviews"] and len(on_disk["reviews"]["Q001"]["history"]) == 3)
        check("原子写无残留 .tmp 文件",
              not (APP_ROOT / "data" / "state_smoke.json.tmp").exists())
    finally:
        stop_server(proc)

    # ---- 跨重启持久化验证：同一状态文件重新拉起服务 ----
    proc = start_server()
    try:
        r = requests.get(BASE + "/api/wrongbook")
        check("重启后错题本仍含 Q002（真持久化而非内存态）",
              r.status_code == 200 and r.json()["total"] == 1
              and r.json()["items"][0]["id"] == "Q002")
    finally:
        stop_server(proc)

    # ---- 收尾 ----
    STATE_PATH.unlink(missing_ok=True)  # 清理冒烟状态，真实 data/state.json 不受影响
    failed = [name for name, ok, _ in results if not ok]
    print(f"\n== 结果：{len(results) - len(failed)}/{len(results)} PASS ==")
    if failed:
        print("失败项：")
        for name in failed:
            print(f"  - {name}")
        return 1
    print("全 PASS：五功能关键路径 + 幂等 + 持久化全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
