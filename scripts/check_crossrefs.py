#!/usr/bin/env python3
"""check_crossrefs.py — agent-study 工作区文档一致性检查器。

扫描工作区所有自产 .md 文件，检查三类问题：
  1. ERROR   断链：相对链接指向的目标文件不存在
  2. ERROR   锚点失效：链接的 #fragment 在目标文件（或链接文件自身）中无对应标题
  3. WARN    悬空引用：REQUIRED_LINKS 互引矩阵中声明的"目录→目录"引用只存在单向
             （被引用目录树内没有任何文档回链来源目录树）

用法：
  python scripts/check_crossrefs.py            # 检查并打印摘要
  python scripts/check_crossrefs.py --report   # 同时写 scripts/check_crossrefs_report.md

退出码：存在 ERROR 时为 1，否则 0（WARN 不影响退出码）。
输出可复现：同输入同输出（结果按路径+行号排序；无网络、无随机源）。
"""

from __future__ import annotations

import re
import sys
import urllib.parse
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------
# 扫描范围：工作区自产文档；排除 01-08 与 project-study 内部 clone 的
# 上游源码仓（其中 .md 属于上游项目，不归本文档一致性体系管）。
# ---------------------------------------------------------------
EXCLUDED_PREFIXES = [
    "01-claude-code/anon-kode",
    "01-claude-code/claude-code-official",
    "01-claude-code/analysis_claude_code",
    "01-claude-code/claude-code-reverse",
    "02-codex/codex",
    "03-deepseek-harness/deepseek-harness",
    "04-zcode/ZCode",
    "05-openclaw/openclaw",
    "06-opencode/opencode",
    "07-langchain/langchain",
    "08-langgraph/langgraph",
    "project-study/browser-use",
    "project-study/camel",
    "project-study/crewai",
    "project-study/repro",
    "projects/interview-prep-app",
    ".zcode",
    ".git",
    "node_modules",
    "scripts/check_crossrefs_report.md",
]

# ---------------------------------------------------------------
# 互引矩阵（目录树 → 目录树）：from_dir 中任一文档链接了 to_dir 中任一文档时，
# to_dir 树内必须存在任一文档回链 from_dir 树内任一文档，否则报 WARN。
# 清单依据《⑬ 中文化收尾》C 象限：新批次（mianjing/cloud/project-study/
# kaogong/cet4）与既有手册的双向覆盖。
# ---------------------------------------------------------------
REQUIRED_LINKS = [
    # (from_dir, to_dir, 说明)
    ("mianjing-handbook", "interview-handbook", "面经精评 ↔ 题库（姊妹册互链）"),
    ("interview-handbook", "mianjing-handbook", "题库 ↔ 面经精评（姊妹册互链）"),
    ("cloud-handbook", "deploy-handbook", "云平台对比 ↔ 部署手册（托管平台视角互换）"),
    ("deploy-handbook", "cloud-handbook", "部署手册 ↔ 云平台对比（§1 深全版）"),
    ("kaogong-handbook", "tuning-handbook", "考公复盘闭环借调优手册五步结构"),
    ("tuning-handbook", "kaogong-handbook", "调优手册反向链接考公手册（方法论迁移实例）"),
    ("cet4-handbook", "tuning-handbook", "四级周复盘借调优手册五步结构"),
    ("tuning-handbook", "cet4-handbook", "调优手册反向链接四级手册（方法论迁移实例）"),
    ("kaogong-handbook", "interview-handbook", "考公冲刺路线参考面试题库体例"),
    ("interview-handbook", "kaogong-handbook", "面试题库反向链接考公手册（方法论同构）"),
    ("cet4-handbook", "interview-handbook", "四级路线参考面试题库体例"),
    ("interview-handbook", "cet4-handbook", "面试题库反向链接四级手册（方法论同构）"),
    ("cet4-handbook", "kaogong-handbook", "四级与考公套卷策略同构互参"),
    ("kaogong-handbook", "cet4-handbook", "考公与四级套卷策略同构互参"),
    ("project-study", "multiagent-handbook", "项目实战范式判定沿用协同手册六范式"),
    ("multiagent-handbook", "project-study", "协同手册反向链接项目实战（blackboard/supervisor 实证）"),
    ("project-study", "08-langgraph", "camel 黑板语义与 LangGraph 共享 state 互补"),
    ("08-langgraph", "project-study", "LangGraph 文档反向链接项目实战（camel 实证）"),
    ("project-study", "05-openclaw", "browser-use 与 OpenClaw browser 工具同赛道对照"),
    ("05-openclaw", "project-study", "OpenClaw 架构拆解反向链接项目实战（browser-use 对照）"),
    ("cloud-handbook", "fde-handbook", "云平台选型以 FDE 视角作答"),
    ("fde-handbook", "cloud-handbook", "FDE 手册反向链接云平台对比（选型答题面）"),
    ("kaogong-handbook", "eval-handbook", "考公模考评分与评测方法论同构"),
    ("cet4-handbook", "python-handbook", "四级与 Python 手册无直接依赖（豁免示例占位）"),
]

# 设计上的单向引用豁免（from→to 允许无反向）：
EXEMPT_PAIRS = {
    # cet4 对 python-handbook 只有"语言栈参照"式弱关联，不强制反向
    ("cet4-handbook", "python-handbook"),
}

MD_LINK_RE = re.compile(
    r"!?\[([^\]]*)\]\(([^)\s]+(?:\s+\"[^\"]*\")?)\)"
)
HTML_HREF_RE = re.compile(r"<a\s[^>]*href=\"([^\"]+)\"")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")

CODE_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def iter_md_files() -> list[Path]:
    files = []
    for p in sorted(WORKSPACE.rglob("*.md")):
        rel = p.relative_to(WORKSPACE).as_posix()
        if any(rel == e or rel.startswith(e + "/") for e in EXCLUDED_PREFIXES):
            continue
        files.append(p)
    return files


def strip_code_fences(text: str) -> list[str]:
    """返回去掉代码围栏内内容的行列表（保留行号语义：返回与原行号对应的行）。"""
    lines = text.splitlines()
    out, in_fence = [], False
    fence_marker = ""
    for line in lines:
        m = CODE_FENCE_RE.match(line)
        if m:
            marker = m.group(1)
            if not in_fence:
                in_fence, fence_marker = True, marker[0]
            elif marker[0] == fence_marker:
                in_fence = False
            out.append("")
            continue
        out.append("" if in_fence else line)
    return out


def github_slug(title: str) -> str:
    title = title.strip().lower()
    out = []
    for ch in title:
        if ch.isalnum() or ch in " -_":
            out.append(ch)
    return "".join(out).replace(" ", "-")


def collect_anchors(text: str) -> set[str]:
    anchors: set[str] = {}
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if not m:
            continue
        title = re.sub(r"`([^`]*)`", r"\1", m.group(2))  # 去行内代码反引号
        slug = github_slug(title)
        n = anchors.get(slug, 0)
        anchors[slug if n == 0 else f"{slug}-{n}"] = True
        anchors[slug] = n + 1
    return set(anchors.keys())


def is_external(target: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target)) or target.startswith("//")


def parse_links(lines: list[str]) -> list[tuple[int, str, str]]:
    """返回 (行号, 原始目标, 解析后的 target#fragment)。"""
    found = []
    for i, line in enumerate(lines, 1):
        for _text, raw in MD_LINK_RE.findall(line):
            raw = raw.strip()
            raw = re.sub(r"\s+\"[^\"]*\"$", "", raw)  # 去 title
            if raw.startswith("<") and raw.endswith(">"):
                raw = raw[1:-1]
            found.append((i, raw, raw))
        for href in HTML_HREF_RE.findall(line):
            found.append((i, href, href))
    return found


def resolve_target(source: Path, raw: str) -> tuple[Path | None, str]:
    """把链接拆成 (目标文件绝对路径或 None, fragment)。外部链接返回 (None, '')。"""
    raw = raw.strip()
    if raw.startswith("#"):
        return source, urllib.parse.unquote(raw[1:])
    if is_external(raw) or raw.startswith("mailto:"):
        return None, ""
    path_part, _, frag = raw.partition("#")
    path_part = urllib.parse.unquote(path_part)
    if not path_part:
        return source, urllib.parse.unquote(frag)
    target = (source.parent / path_part).resolve()
    return target, urllib.parse.unquote(frag)


def dir_tree_has_link_to(from_dir: Path, to_dir: Path, index: dict[Path, list[tuple[Path, str]]]) -> bool:
    """from_dir 树内任一 md 是否链接了 to_dir 树内任一 md（index 值为 (目标路径, 原始链接) 对）。"""
    to_files = {p.resolve() for p in index if to_dir in p.parents or p.parent == to_dir}
    for p, pairs in index.items():
        if from_dir not in p.parents and p.parent != from_dir:
            continue
        for tp, _raw in pairs:
            if tp in to_files:
                return True
    return False


def main() -> int:
    report_mode = "--report" in sys.argv
    errors: list[str] = []
    warnings: list[str] = []

    files = iter_md_files()
    texts: dict[Path, str] = {}
    lines_map: dict[Path, list[str]] = {}
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = p.read_text(encoding="utf-8", errors="replace")
        texts[p] = text
        lines_map[p] = strip_code_fences(text)

    # 索引：文件 → 解析后的目标路径与原始目标
    index: dict[Path, list[tuple[Path, str]]] = {}
    for p in files:
        pairs = []
        for _i, raw, _norm in parse_links(lines_map[p]):
            tp, frag = resolve_target(p, raw)
            if tp is not None:
                pairs.append((tp, raw))
        index[p] = pairs

    # 1) 断链 + 2) 锚点
    anchor_cache: dict[Path, set[str]] = {}
    for p in sorted(files):
        for i, raw_line in enumerate(parse_links(lines_map[p]), 0):
            line_no, _raw_display, raw = raw_line
            # 代码形态的伪链接：`dict[key](**kwargs)` 形态被 markdown 误渲染，
            # 目标以 * 开头的（如 **json.loads(...)）不是真链接，跳过检查。
            if raw.startswith("*"):
                continue
            target, frag = resolve_target(p, raw)
            if target is None:
                continue
            if not target.exists():
                errors.append(
                    f"BROKEN: {p.relative_to(WORKSPACE).as_posix()}:{line_no} -> {raw}"
                )
                continue
            if frag:
                if target.suffix.lower() != ".md":
                    continue  # 非 md 目标的锚点不做校验
                if target not in anchor_cache:
                    anchor_cache[target] = collect_anchors(texts[target])
                if frag not in anchor_cache[target]:
                    errors.append(
                        f"ANCHOR: {p.relative_to(WORKSPACE).as_posix()}:{line_no} "
                        f"-> {raw} (锚点 #{frag} 不存在于 {target.relative_to(WORKSPACE).as_posix()})"
                    )

    # 3) 悬空引用（互引矩阵）
    for from_dir_s, to_dir_s, note in REQUIRED_LINKS:
        if (from_dir_s, to_dir_s) in EXEMPT_PAIRS:
            continue
        from_dir, to_dir = WORKSPACE / from_dir_s, WORKSPACE / to_dir_s
        if not from_dir.exists() or not to_dir.exists():
            warnings.append(
                f"MISSING-DIR: {from_dir_s} 或 {to_dir_s} 不存在（矩阵项：{note}）"
            )
            continue
        has_forward = dir_tree_has_link_to(from_dir, to_dir, index)
        has_back = dir_tree_has_link_to(to_dir, from_dir, index)
        if has_forward and not has_back:
            warnings.append(
                f"DANGLING: {from_dir_s} -> {to_dir_s} 单向引用，{to_dir_s} 缺反向链接（{note}）"
            )

    # 汇总
    print(f"扫描 {len(files)} 个 md 文件")
    print(f"ERROR（断链/锚点）: {len(errors)}")
    print(f"WARN（悬空引用） : {len(warnings)}")
    for e in errors:
        print("  " + e)
    for w in warnings:
        print("  " + w)

    if report_mode:
        report = WORKSPACE / "scripts" / "check_crossrefs_report.md"
        # 保留历史"修复留档"节：报告重生成时是当前状态快照，留档是长期记录。
        preserved = ""
        if report.exists() and "## 修复留档" in report.read_text(encoding="utf-8"):
            old = report.read_text(encoding="utf-8")
            idx = old.index("## 修复留档")
            preserved = "\n" + old[idx:].rstrip() + "\n"
        lines = [
            "# 文档一致性与交叉引用检查报告",
            "",
            f"- 生成器：`scripts/check_crossrefs.py`（确定性输出：同输入同输出）",
            f"- 扫描范围：工作区自产 markdown（排除 01-08 / project-study 内部 clone 的上游源码仓）",
            f"- 扫描文件数：{len(files)}",
            f"- ERROR（断链/锚点失效）：{len(errors)}",
            f"- WARN（悬空引用，互引矩阵 REQUIRED_LINKS）：{len(warnings)}",
            "",
            "## 结论",
            "",
        ]
        if not errors and not warnings:
            lines.append("**全部 PASS**：无断链、无锚点失效、互引矩阵无单向引用。")
        else:
            if not errors:
                lines.append("断链/锚点检查 **PASS**。")
            else:
                lines.append("断链/锚点检查 **FAIL**，清单如下：")
            if warnings:
                lines.append("悬空引用检查 **FAIL**，清单如下：")
        if errors:
            lines += ["", "```"] + errors + ["```"]
        if warnings:
            lines += ["", "```"] + warnings + ["```"]
        lines += [
            "",
            "## 检查项说明",
            "",
            "1. `BROKEN` 相对链接目标不存在；2. `ANCHOR` md 目标文件中无对应标题锚点"
            "（GitHub slug 规则：小写、空格→-、去标点、重复标题加 -N）；"
            "3. `DANGLING` 互引矩阵声明的目录对只有单向引用（被引用目录树内无任何文档回链）。",
            "",
            "互引矩阵与豁免清单内嵌于 `scripts/check_crossrefs.py` 的 `REQUIRED_LINKS` / `EXEMPT_PAIRS`，"
            "修改矩阵请同步更新脚本并在本报告中重跑留档。",
            "",
        ]
        if preserved:
            lines.append(preserved)
        report.write_text("\n".join(lines), encoding="utf-8")
        print(f"报告已写入 {report.relative_to(WORKSPACE)}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
