# -*- coding: utf-8 -*-
"""
build_index.py —— 把工作区 interview-handbook/ 的七个题集 .md 解析为 data/index.json。

数据流：interview-handbook/*.md（只读）→ 本脚本 → data/index.json（构建产物）。

不变量（机制说明）：
1. 索引构建幂等：输出 JSON 里不含任何时间戳/机器相关字段，同一份题集输入
   必然产出字节级相同的 index.json（可用两次构建后 diff / sha256 对比验证）。
2. 解析失败必须显式报错：任何文件级/题目级解析问题都收集进 errors 列表，
   最终一次性列出并以非零码退出——绝不静默跳过（宁可起不来，不可错着跑）。
3. 与总 README 登记表交叉核对：interview-handbook/README.md 的文件清单表
   （题数/高频数）与难度频次分布表是"登记口径"，逐主题核对实测值，
   对不上即报错——题库将来增删题目时，这里会第一时间拦住口径漂移。
4. 只读源目录：本脚本对 interview-handbook/ 只开读句柄，不写不改不移动。

用法：
    python build_index.py            # 构建 + 校验，成功后打印摘要
    python build_index.py --quiet    # 只在出错时输出
"""

import json
import os
import re
import sys
from pathlib import Path

# ---- 路径解析：脚本位于 projects/interview-prep-app/，工作区根在两级之上 ----
APP_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = APP_ROOT.parent.parent
SOURCE_DIR = WORKSPACE_ROOT / "interview-handbook"
README_SRC = SOURCE_DIR / "README.md"
DATA_DIR = APP_ROOT / "data"
INDEX_PATH = DATA_DIR / "index.json"

# ---- 题目头正则：形如 "> **Q001. 什么是 token？……**（难度：初 ｜ 频次：高）" ----
# 全工作区 128 题头格式已 grep 全量核对一致（2026-09-28），此处按精确格式匹配，
# 不做模糊兼容——格式漂移就该报错，而不是猜。
Q_HEADER_RE = re.compile(
    r"^\*\*(Q\d+)\.\s*(.+?)\*\*（难度：([初中高])\s*｜\s*频次：([高中低])）$"
)
# 四件套各节的行首标记（在去掉 "> " 前缀后形如 "- 考察点：……"）
SECTION_KEYS = ("考察点", "参考回答", "追问与陷阱", "加分项", "延伸阅读")
SECTION_RE = re.compile(r"^- (考察点|参考回答|追问与陷阱|加分项|延伸阅读)：(.*)$")
# 延伸阅读里的 markdown 链接：[文本](相对路径)
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def parse_questions_from_file(path: Path) -> tuple[list[dict], list[str]]:
    """解析单个题集文件，返回 (题目列表, 错误列表)。

    块结构：题目是连续的 "> " 引用行，块与块之间用空行分隔；
    块首行必须是 Q 头，块内四件套按 SECTION_RE 切节，节内容保留原文行。
    """
    questions: list[dict] = []
    errors: list[str] = []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [], [f"{path.name}: 文件读取失败 {exc}"]

    # 先按"空行分隔的引用块"切块，再逐块解析——避免逐行状态机误吞块间空行
    blocks: list[list[str]] = []
    current: list[str] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if raw.startswith(">"):
            current.append((lineno, raw[1:].lstrip(" ")))  # 去掉 "> " 前缀
        else:
            if current:
                blocks.append(current)
                current = []
    if current:
        blocks.append(current)

    started = False  # 是否已遇到第一道题：之前的引用块是册首"信息基准日"引言，合法跳过
    for block in blocks:
        lineno0, header_line = block[0]
        m = Q_HEADER_RE.match(header_line)
        if not m:
            if not started:
                continue  # 引言块：题目开始前允许存在
            errors.append(
                f"{path.name}:{lineno0} 题目开始后又出现非题目引用块：{header_line[:60]}"
            )
            continue
        started = True
        qid, title, difficulty, frequency = m.groups()

        # 四件套切节：SECTION_RE 命中即开新节，其余行归入当前节（保留缩进的嵌套 bullet）
        sections: dict[str, list[str]] = {}
        cur_key: str | None = None
        for lineno, line in block[1:]:
            sm = SECTION_RE.match(line)
            if sm:
                cur_key = sm.group(1)
                sections.setdefault(cur_key, [])
                if sm.group(2).strip():
                    sections[cur_key].append(sm.group(2))
            elif cur_key is not None:
                sections[cur_key].append(line)
            else:
                errors.append(f"{path.name}:{lineno} {qid} 节前出现孤立行：{line[:50]}")

        missing = [k for k in SECTION_KEYS if k not in sections]
        if missing:
            errors.append(f"{path.name}:{lineno0} {qid} 缺少分节：{'、'.join(missing)}")
            continue

        # 延伸阅读提取链接（原文也保留）；空链接列表视为可疑但不致命
        links = [
            {"text": t.strip(), "href": h.strip()}
            for t, h in LINK_RE.findall(sections["延伸阅读"][0] if sections["延伸阅读"] else "")
        ]
        if not links:
            errors.append(f"{path.name}:{lineno0} {qid} 延伸阅读未提取到任何链接")

        questions.append(
            {
                "id": qid,
                "topic": "",  # 由调用方补 topic id
                "title": title.strip(),
                "difficulty": difficulty,
                "frequency": frequency,
                "sections": {k: "\n".join(v).strip() for k, v in sections.items()},
                "links": links,
            }
        )
    return questions, errors


def parse_readme_registry() -> tuple[dict[str, dict], list[str]]:
    """解析 interview-handbook/README.md 的两张登记表，作为交叉核对口径。

    表一（文件清单）：| 文件 | 主题 | 题数 | 高频题速览 |
    表二（难度频次分布）：| 主题 | 初 | 中 | 高 | 频次高 | 频次中 | 频次低 |
    """
    registry: dict[str, dict] = {}
    errors: list[str] = []
    try:
        text = README_SRC.read_text(encoding="utf-8")
    except OSError as exc:
        return registry, [f"README.md 读取失败：{exc}"]

    section = None
    for raw in text.splitlines():
        if raw.startswith("## "):
            section = "files" if "文件清单" in raw else ("dist" if "难度与频次分布" in raw else None)
            continue
        if section is None or not raw.startswith("|"):
            continue
        cells = [c.strip() for c in raw.strip("|").split("|")]
        if section == "files" and len(cells) == 4:
            # 第一列是 markdown 链接壳：[01-LLM基础与提示词.md](01-LLM基础与提示词.md)
            lm = re.match(r"^\[([^\]]+)\]\(", cells[0])
            if not lm or not lm.group(1).endswith(".md"):
                continue  # 合计行等非文件行
            fname = lm.group(1)
            m_count = re.match(r"^(\d+)$", cells[2])
            m_high = re.match(r"^(\d+) 题$", cells[3])
            if not (m_count and m_high):
                errors.append(f"README.md 文件清单表数字列无法解析：{raw[:60]}")
                continue
            registry[fname] = {
                "subtitle": cells[1],
                "expect_count": int(m_count.group(1)),
                "expect_high_freq": int(m_high.group(1)),
            }
        if section == "dist" and len(cells) == 7 and re.match(r"^\d{2} ", cells[0]):
            tid = cells[0][:2]
            nums = []
            for c in cells[1:]:
                nm = re.match(r"^(\d+)$", c)
                if not nm:
                    errors.append(f"README.md 分布表数字列无法解析：{raw[:60]}")
                    nums = None
                    break
                nums.append(int(nm.group(1)))
            if nums:
                # 找到该主题对应的文件名（按 id 前缀关联）
                for fname in registry:
                    if fname[:2] == tid:
                        registry[fname].update(
                            expect_difficulty={"初": nums[0], "中": nums[1], "高": nums[2]},
                            expect_frequency={"高": nums[3], "中": nums[4], "低": nums[5]},
                        )
                        break
                else:
                    errors.append(f"README.md 分布表主题 {tid} 在文件清单中找不到对应文件")
    if len(registry) != 7:
        errors.append(f"README.md 文件清单应登记 7 个题集，实际解析到 {len(registry)} 个")
    return registry, errors


def atomic_write_json(path: Path, payload: dict) -> None:
    """原子写盘：先写同目录临时文件，再 os.replace 覆盖目标。

    不变量：os.replace 在同一文件系统上是原子操作，进程写一半崩溃/断电
    只会留下完整的旧文件或完整的新文件，不会留下半截 JSON。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")
    os.replace(tmp, path)


def main() -> int:
    quiet = "--quiet" in sys.argv
    errors: list[str] = []

    if not SOURCE_DIR.is_dir():
        print(f"[build_index] 致命：源目录不存在 {SOURCE_DIR}")
        return 1

    registry, reg_errors = parse_readme_registry()
    errors.extend(reg_errors)

    files = sorted(SOURCE_DIR.glob("0*.md"))
    if len(files) != 7:
        errors.append(f"预期 7 个题集文件（0*.md），实际找到 {len(files)} 个")

    all_questions: list[dict] = []
    topics: list[dict] = []
    seen_ids: set[str] = set()

    for path in files:
        # 主题名取文件首行 "# 主题一：token 与计费 · ……" 的冒号前段
        first_line = path.read_text(encoding="utf-8").splitlines()[0] if path.exists() else ""
        name = first_line.lstrip("# ").split("：")[0].strip()
        tid = path.name[:2]
        qs, file_errors = parse_questions_from_file(path)
        errors.extend(file_errors)

        for q in qs:
            if q["id"] in seen_ids:
                errors.append(f"{path.name}: 题号 {q['id']} 重复出现（跨文件题号必须唯一）")
            seen_ids.add(q["id"])
            q["topic"] = tid
        all_questions.extend(qs)

        reg = registry.get(path.name)
        topics.append(
            {
                "id": tid,
                "file": path.name,
                "name": name,
                "subtitle": reg["subtitle"] if reg else "",
                "count": len(qs),
                "high_freq": sum(1 for q in qs if q["frequency"] == "高"),
            }
        )

        # ---- 交叉核对：实测题数/难度/频次 vs README 登记口径 ----
        if reg:
            if len(qs) != reg["expect_count"]:
                errors.append(
                    f"{path.name}: 实测 {len(qs)} 题，README 登记为 {reg['expect_count']} 题"
                )
            if topics[-1]["high_freq"] != reg["expect_high_freq"]:
                errors.append(
                    f"{path.name}: 实测高频 {topics[-1]['high_freq']} 题，README 登记为 {reg['expect_high_freq']} 题"
                )
            if "expect_difficulty" in reg:
                for lv in ("初", "中", "高"):
                    actual = sum(1 for q in qs if q["difficulty"] == lv)
                    if actual != reg["expect_difficulty"][lv]:
                        errors.append(
                            f"{path.name}: 实测难度{lv} {actual} 题，README 登记为 {reg['expect_difficulty'][lv]} 题"
                        )
            if "expect_frequency" in reg:
                for lv in ("高", "中", "低"):
                    actual = sum(1 for q in qs if q["frequency"] == lv)
                    if actual != reg["expect_frequency"][lv]:
                        errors.append(
                            f"{path.name}: 实测频次{lv} {actual} 题，README 登记为 {reg['expect_frequency'][lv]} 题"
                        )
        else:
            errors.append(f"{path.name}: 在 README.md 文件清单表中没有登记，无法交叉核对")

    if len(all_questions) != 128:
        errors.append(f"全库题数实测 {len(all_questions)}，口径要求 128")

    # ---- 失败即列出并退出，不产出索引（避免半成品被服务加载）----
    if errors:
        print(f"[build_index] 解析/核对失败，共 {len(errors)} 处：")
        for e in errors:
            print(f"  - {e}")
        print("[build_index] 已放弃写出 index.json（宁可不起服务，不可带错运行）")
        return 1

    by_difficulty = {"初": 0, "中": 0, "高": 0}
    by_frequency = {"高": 0, "中": 0, "低": 0}
    for q in all_questions:
        by_difficulty[q["difficulty"]] += 1
        by_frequency[q["frequency"]] += 1

    payload = {
        "version": 1,
        "source_dir": "interview-handbook",
        "topics": topics,
        "questions": all_questions,
        "stats": {
            "total": len(all_questions),
            "by_difficulty": by_difficulty,
            "by_frequency": by_frequency,
        },
    }
    atomic_write_json(INDEX_PATH, payload)

    if not quiet:
        print(f"[build_index] OK：7 主题 / {len(all_questions)} 题 → {INDEX_PATH}")
        print(f"[build_index] 难度分布 {by_difficulty}，频次分布 {by_frequency}")
        size_kb = INDEX_PATH.stat().st_size / 1024
        print(f"[build_index] 产物大小 {size_kb:.0f} KB（幂等：再跑一次字节级不变）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
