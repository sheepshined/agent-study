#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
s07_apply_patch/code.py —— mini apply_patch：统一补丁式编辑 + code mode 一瞥

模型改代码，为什么 Codex 用"打补丁"而不是"读文件→整个重写→写回"？

  apply-patch crate（codex-rs/apply-patch/src/）
    parser.rs        —— 补丁格式标记（:37 BEGIN / :38 END / :39-:41 Add·Delete·Update、
                        :42 Move to、:43 End of File、:44-:45 @@ 变更上下文）；
                        parse_patch（:145）→ parse_patch_text（:193）；
                        Hunk（:66）三种块，UpdateFile 带 move_path（:76）与有序 chunks；
                        UpdateFileChunk（:115）是核心结构：change_context 只有一行（:117 注释），
                        old_lines 必须"严格出现在 change_context 之后"，chunk 之间按文件顺序推进
    seek_sequence.rs —— 定位（:12）：exact → 忽略行尾空白 → 忽略首尾空白，三级递减严格度；
                        带 start 游标（只从游标往后找）与 eof 语义（从文件尾往前试）；
                        三级都不中就返回 None——真实实现没有"相似度打分"这一步
    file_update.rs   —— derive_new_contents_from_chunks（:26）由有序 chunk 推导新内容；
                        unified_diff_from_chunks（:256）反向产出 diff 供 UI 展示
    streaming_parser.rs —— 流式解析（:22 StreamingPatchParser）：模型边生成边应用，
                        不必等整段补丁吐完
    lib.rs / 调用侧 —— ParseMode::Lenient（parser.rs :154，:53 恒为 lenient）：容忍模型把补丁
                        包进 <<'EOF' … EOF 外壳（gpt-4.1 的经典毛病）

  为什么是补丁（统一编辑协议的三笔账）：
    1. 省往返：N 处编辑 = 1 次工具调用（对比 N 次 read/write 往返）
    2. 可展示：补丁天然是 diff——UI 能渲染、人能审、rollout 能存（s02）
    3. 可靠性：上下文行是"位置锚"，文件被别人改过时能检测错位；有序 chunk + 单调游标
       还解决"同名函数改错一处"的歧义

  apply_patch 是 **freeform（自由文本）工具**，不是 JSON 函数：
    core/src/tools/handlers/apply_patch_spec.rs:9 create_apply_patch_freeform_tool，
    :19-20 描述原文 "This is a FREEFORM tool, so do not wrap the patch in JSON."
    —— 编辑协议的形状用文本法描述比塞进 JSON schema 更自然，也更省 token。

  code mode（codex-rs/code-mode/、code-mode-host/、code-mode-runtime/）：
    工具规模再大一步后，Codex 把"一批工具调用"升级成"一段可执行脚本"
    （宿主握手暴露能力：code-mode-host/src/lib.rs:281 HostHello::new(...)）
    —— 补丁式的"声明一次、批量应用"思想在更大的粒度上重演。

mini 版演示：三种块 + Move to + End of File、三级定位（与真实同构）、有序 chunk 消歧、
lenient 外壳剥离、失败明确报错。

Rust ↔ Python：Result<T, ParseError> ↔ 异常；Option<T> ↔ None；enum Hunk ↔ 三个 dataclass
（serde tagged enum 的教学退化）。

运行：python code.py    （零依赖，离线；文件操作在临时目录，结束清理）
对照真实源码：codex-rs/apply-patch/src/{parser,seek_sequence,file_update,streaming_parser}.rs
"""

from __future__ import annotations

import difflib
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.mini_util import force_utf8_stdout

force_utf8_stdout()

# 标记常量：与 parser.rs :37-:45 一一对应
BEGIN, END = "*** Begin Patch", "*** End Patch"
ADD_FILE, DELETE_FILE, UPDATE_FILE = "*** Add File: ", "*** Delete File: ", "*** Update File: "
MOVE_TO, EOF_MARKER = "*** Move to: ", "*** End of File"
CONTEXT, EMPTY_CONTEXT = "@@ ", "@@"


class PatchError(Exception):
    """对应 parser.rs 的 ParseError（:57）：InvalidPatchError / InvalidHunkError{line_number}。

    带行号是刻意的——报错要能回给模型，让它知道补丁第几行写坏了。
    """

    def __init__(self, message: str, line_number: Optional[int] = None):
        self.line_number = line_number
        super().__init__(message if line_number is None else f"补丁第 {line_number} 行：{message}")


# ---------------------------------------------------------------
# 第 1 部分：解析（parser.rs 的 mini 版）
# ---------------------------------------------------------------


@dataclass
class UpdateChunk:
    """对应 UpdateFileChunk（parser.rs:115）。

    change_context 只有**一行**（真实字段是 Option<String>，注释称"通常是类/方法/函数定义行"）；
    old_lines 必须严格出现在 change_context 之后；一个 Update File 块里可以排多个 chunk。
    """

    change_context: Optional[str] = None
    old_lines: List[str] = field(default_factory=list)
    new_lines: List[str] = field(default_factory=list)
    end_of_file: bool = False        # 对应 is_end_of_file（parser.rs:131）


@dataclass
class AddFile:
    path: str
    lines: List[str] = field(default_factory=list)


@dataclass
class DeleteFile:
    path: str


@dataclass
class UpdateFile:
    path: str
    move_to: Optional[str] = None    # 对应 move_path：重命名也是补丁的一部分
    chunks: List[UpdateChunk] = field(default_factory=list)


Hunk = Union[AddFile, DeleteFile, UpdateFile]


def strip_heredoc(patch: str) -> str:
    """ParseMode::Lenient（parser.rs :154 + :53 恒启用）的 mini 版。

    模型有时把补丁包在 <<'EOF' … EOF 里（local_shell 用 execvpe 而非 shell，
    heredoc 不会被展开，只会成为字面字符串）——解析器自己剥壳。
    """
    body = patch.strip()
    if body.startswith("<<'EOF'") and body.endswith("EOF"):
        first = body.find("\n") + 1
        return body[first:body.rfind("EOF")].strip()
    return patch


def parse_patch(patch: str) -> List[Hunk]:
    """解析补丁文本 → 有序 Hunk 列表。对应 parse_patch（parser.rs:145）。"""
    patch = strip_heredoc(patch)
    if not patch.startswith(BEGIN):
        raise PatchError("补丁必须以 '*** Begin Patch' 开头")
    if END not in patch:
        raise PatchError("补丁必须以 '*** End Patch' 结尾")

    hunks: List[Hunk] = []
    cur_update: Optional[UpdateFile] = None
    cur_add: Optional[AddFile] = None
    cur_chunk: Optional[UpdateChunk] = None
    deleting = False

    for ln, raw in enumerate(patch.splitlines()[1:], start=2):
        if raw == END:
            break
        if raw.startswith(ADD_FILE):
            cur_add, cur_update, cur_chunk, deleting = AddFile(raw[len(ADD_FILE):]), None, None, False
            hunks.append(cur_add)
        elif raw.startswith(DELETE_FILE):
            cur_add, cur_update, cur_chunk = None, None, None
            deleting, hunks = True, [*hunks, DeleteFile(raw[len(DELETE_FILE):])]
        elif raw.startswith(UPDATE_FILE):
            cur_add, cur_chunk, deleting = None, None, False
            cur_update = UpdateFile(raw[len(UPDATE_FILE):])
            hunks.append(cur_update)
        elif raw.startswith(MOVE_TO):
            if cur_update is None:
                raise PatchError("'*** Move to:' 只能出现在 Update File 块内", ln)
            cur_update.move_to = raw[len(MOVE_TO):]
        elif raw == EOF_MARKER:
            if cur_chunk is None:
                raise PatchError("'*** End of File' 前没有 @@ chunk", ln)
            cur_chunk.end_of_file = True
        elif raw.startswith(CONTEXT) or raw == EMPTY_CONTEXT:
            if cur_update is None:
                raise PatchError("@@ 变更上下文只能出现在 Update File 块内", ln)
            cur_chunk = UpdateChunk(change_context=None if raw == EMPTY_CONTEXT else raw[len(CONTEXT):])
            cur_update.chunks.append(cur_chunk)
        elif raw.startswith("+"):
            if cur_add is not None:
                cur_add.lines.append(raw[1:])
            elif cur_chunk is not None:
                cur_chunk.new_lines.append(raw[1:])
            else:
                raise PatchError("'+' 行只能出现在 Add File / @@ chunk 内", ln)
        elif raw.startswith("-"):
            if cur_chunk is None:
                raise PatchError("'-' 行只能出现在 @@ chunk 内", ln)
            cur_chunk.old_lines.append(raw[1:])
        elif raw.startswith(" "):
            # 上下文行：既是 old 也是 new——真实解析用它记 context_line_indices
            if cur_chunk is None:
                raise PatchError("上下文行只能出现在 @@ chunk 内", ln)
            cur_chunk.old_lines.append(raw[1:])
            cur_chunk.new_lines.append(raw[1:])
        elif not raw.strip():
            continue
        else:
            raise PatchError(f"无法解析的行：{raw!r}", ln)
    return hunks


# ---------------------------------------------------------------
# 第 2 部分：seek_sequence —— 三级定位 + 单调游标（seek_sequence.rs 的 mini 版）
# ---------------------------------------------------------------


def seek_sequence(lines: List[str], pattern: List[str], start: int, eof: bool = False) -> Optional[int]:
    """在 lines 里找 pattern 的起始下标，返回 None 表示没找到（不猜）。

    与真实实现同构的三点（seek_sequence.rs :12 及其 doc comment :1-13）：
      ① 三级递减严格度：exact → 忽略行尾空白 → 忽略首尾空白；
      ② start 游标：只从游标往后找——配合"chunk 按文件顺序"这一不变量消除同名锚的歧义；
      ③ eof=True 时先从文件尾往前试（补丁锚的是文件结尾时不会误命中前面的同名行）。
    防御分支同样保留：空 pattern → 直接返回 start；pattern 比文件还长 → None（不可能命中）。

    真实实现**没有**相似度打分这一级——三级都不中就报错回去让模型重写补丁。
    """
    if not pattern:
        return start
    if len(pattern) > len(lines):
        return None

    def search(from_idx: int, same) -> Optional[int]:
        for i in range(from_idx, len(lines) - len(pattern) + 1):
            if same(lines[i:i + len(pattern)], pattern):
                return i
        return None

    levels = [
        lambda win, pat: win == pat,
        lambda win, pat: [l.rstrip() for l in win] == [l.rstrip() for l in pat],
        lambda win, pat: [l.strip() for l in win] == [l.strip() for l in pat],
    ]
    search_start = len(lines) - len(pattern) if eof else start
    for same in levels:
        hit = search(search_start, same)
        if hit is None and eof:
            hit = search(start, same)      # 尾锚没中 → 退回从游标全量搜
        if hit is not None:
            return hit
    return None


# ---------------------------------------------------------------
# 第 3 部分：应用（file_update.rs 的 mini 版）
# ---------------------------------------------------------------


def apply_hunk(root: Path, hunk: Hunk, log: List[str]) -> None:
    if isinstance(hunk, AddFile):
        target = root / hunk.path
        if target.exists():
            raise PatchError(f"Add File 但文件已存在：{hunk.path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(hunk.lines) + "\n", encoding="utf-8")
        log.append(f"ADD     {hunk.path}（{len(hunk.lines)} 行）")
    elif isinstance(hunk, DeleteFile):
        target = root / hunk.path
        if not target.exists():
            raise PatchError(f"Delete File 但文件不存在：{hunk.path}")
        target.unlink()
        log.append(f"DELETE  {hunk.path}")
    elif isinstance(hunk, UpdateFile):
        target = root / hunk.path
        if not target.exists():
            raise PatchError(f"Update File 但文件不存在：{hunk.path}")
        old = target.read_text(encoding="utf-8").splitlines()
        new, cursor = list(old), 0
        for idx, chunk in enumerate(hunk.chunks):
            # ① 先定位 change_context（一行锚），② 再在它之后找 old_lines —— 两次都用游标
            ctx_at: Optional[int] = None
            anchor_at = cursor
            if chunk.change_context is not None:
                ctx_at = seek_sequence(new, [chunk.change_context], cursor)
                if ctx_at is None:
                    raise PatchError(f"找不到变更上下文行 {chunk.change_context!r}")
                anchor_at = ctx_at + 1
            body_at = seek_sequence(new, chunk.old_lines, anchor_at, eof=chunk.end_of_file)
            if body_at is None:
                raise PatchError(f"chunk #{idx + 1} 的待删行在上下文之后没有出现在文件里")
            new[body_at:body_at + len(chunk.old_lines)] = chunk.new_lines
            cursor = body_at + len(chunk.new_lines)   # ★ 下一块只能改更靠后的位置
            where = f"context 第 {ctx_at + 1} 行 → " if ctx_at is not None else ""
            log.append(f"UPDATE  {hunk.path} chunk#{idx + 1}"
                       f"（{where}替换第 {body_at + 1} 行起的 {len(chunk.old_lines)} 行）")
        if hunk.move_to:
            (root / hunk.path).unlink()
            log.append(f"MOVE    {hunk.path} → {hunk.move_to}")
        dest = root / (hunk.move_to or hunk.path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("\n".join(new) + "\n", encoding="utf-8")
    else:
        raise PatchError("未知块类型")


def apply_patch(root: Path, patch: str) -> List[str]:
    """一次调用，批量应用：这是"省往返"账本的落点。"""
    log: List[str] = []
    for h in parse_patch(patch):
        apply_hunk(root, h, log)
    return log


def unified_diff(old: List[str], new: List[str], path: str) -> List[str]:
    """对应 unified_diff_from_chunks（file_update.rs:256）：给人看/给 UI 渲染的那份 diff。"""
    return [l for l in difflib.unified_diff(old, new, fromfile=f"a/{path}",
                                            tofile=f"b/{path}", lineterm="")][2:]


# ---------------------------------------------------------------
# 第 4 部分：演示
# ---------------------------------------------------------------

LOGIN_SRC = """import sys


def login(user):
    print('hi', user)


def check(token):
    return bool(token)


def check(token):
    return bool(token)
"""

PATCH_MULTI = """*** Begin Patch
*** Add File: src/config.py
+DEBUG = False
+RETRIES = 3
*** Update File: src/login.py
@@ def login(user):
-    print('hi', user)
+    print('welcome', user)
*** Delete File: src/legacy.py
*** End Patch
"""

PATCH_RENAME = """*** Begin Patch
*** Update File: src/config.py
*** Move to: src/settings.py
@@ DEBUG = False
-RETRIES = 3
+RETRIES = 5
*** End Patch
"""

PATCH_DUP_ANCHOR = """*** Begin Patch
*** Update File: src/login.py
@@ def check(token):
-    return bool(token)
+    return token is not None
*** End Patch
"""

PATCH_TWO_CHUNKS = """*** Begin Patch
*** Update File: src/login.py
@@ def check(token):
-    return bool(token)
+    return bool(token) and token != ""
@@ def check(token):
-    return bool(token)
+    return str(token).strip() != ""
*** End Patch
"""

PATCH_FUZZY_INDENT = """*** Begin Patch
*** Update File: src/login.py
@@ def check(token):
-  return bool(token)
+    return token is not None
*** End Patch
"""

PATCH_HEREDOC = """<<'EOF'
*** Begin Patch
*** Add File: src/legacy.py
+def old(): ...
*** End Patch
EOF
"""

PATCH_NO_MATCH = """*** Begin Patch
*** Update File: src/login.py
@@ def nonexistent():
-    return 1
+    return 2
*** End Patch
"""


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="mini-patch-"))
    try:
        (tmp / "src").mkdir()
        (tmp / "src" / "login.py").write_text(LOGIN_SRC, encoding="utf-8")
        (tmp / "src" / "legacy.py").write_text("def old(): ...\n", encoding="utf-8")
        legacy_before = (tmp / "src" / "legacy.py").read_text(encoding="utf-8").splitlines()

        print("== 场景 1：一次调用三种块 —— Add / Update / Delete ==")
        for line in apply_patch(tmp, PATCH_MULTI):
            print(f"    {line}")
        print("    → login.py 第 5 行现在是：", repr(
            (tmp / "src" / "login.py").read_text(encoding="utf-8").splitlines()[4]))
        print("    → legacy.py 已删除：", (tmp / "src" / "legacy.py").exists() is False)
        print("    → diff（unified_diff_from_chunks 的产物，供 UI 渲染与人审）：")
        for d in unified_diff(legacy_before, [], "src/legacy.py")[:3]:
            print("      ", d)

        print("\n== 场景 2：Lenient 解析 —— 模型包的 <<'EOF' 外壳自己剥掉 ==")
        for line in apply_patch(tmp, PATCH_HEREDOC):
            print(f"    {line}")
        print("    → 真实动机见 parser.rs:154 的注释：local_shell 用 execvpe 而非 shell，"
              "heredoc 不会展开，只能由解析器容错")

        print("\n== 场景 3：Move to —— 重命名也在这一个补丁事务里 ==")
        for line in apply_patch(tmp, PATCH_RENAME):
            print(f"    {line}")
        print("    src/ 现在：", sorted(p.name for p in (tmp / "src").iterdir()))

        print("\n== 场景 4：锚不唯一 —— 命中游标之后的第一个同名处 ==")
        for line in apply_patch(tmp, PATCH_DUP_ANCHOR):
            print(f"    {line}")
        body = (tmp / "src" / "login.py").read_text(encoding="utf-8").splitlines()
        print(f"    第一处 check：{body[8]!r}｜第二处仍是：{body[12]!r}")
        print("    → change_context 只把范围缩到「某个定义之后」，同名函数还得靠位置先后裁决")

        print("\n== 场景 5：有序 chunk —— 一块补丁把两处同名改成两个不同的样子 ==")
        (tmp / "src" / "login.py").write_text(LOGIN_SRC, encoding="utf-8")   # 复位
        for line in apply_patch(tmp, PATCH_TWO_CHUNKS):
            print(f"    {line}")
        body = (tmp / "src" / "login.py").read_text(encoding="utf-8").splitlines()
        print(f"    两处 check 现在是：{body[8]!r}｜{body[12]!r}")
        print("    → 第二个 chunk 的 old_lines 必须发生在第一个之后（parser.rs:69 的注释），"
              "游标单调前进让「第几块」这个意图变得可执行")

        print("\n== 场景 6：三级定位 —— 模型抄的缩进不对也能贴上 ==")
        (tmp / "src" / "login.py").write_text(LOGIN_SRC, encoding="utf-8")   # 复位
        for line in apply_patch(tmp, PATCH_FUZZY_INDENT):
            print(f"    {line}")
        body = (tmp / "src" / "login.py").read_text(encoding="utf-8").splitlines()
        print(f"    补丁写 2 空格、文件是 4 空格 → {body[8]!r}")
        print("    → 命中的是第三级（忽略首尾空白）；真实实现到第三级为止，"
              "**没有相似度打分**：三级不中就报错")

        print("\n== 场景 7：彻底找不到 —— 明确报错而非乱贴（失败路径） ==")
        try:
            apply_patch(tmp, PATCH_NO_MATCH)
        except PatchError as e:
            print(f"    PatchError: {e}")
        print("    → 定位失败即整块中止：错误回给模型重写补丁，比错位修改安全")

        print("\n== 场景 8：三笔账 —— N 处编辑 = 1 次工具调用 ==")
        big = [BEGIN]
        for i in range(3):
            big += [f"*** Add File: gen/mod{i}.py", f"+ # module {i}"]
        big.append(END)
        log = apply_patch(tmp, "\n".join(big))
        print(f"    3 个新文件，工具调用次数 = 1（模型往返 1 次而非 3 次）；产出 {len(log)} 条")
        print("    → 再放大一步就是 code mode：一批工具调用变成一段脚本"
              "（code-mode-host/src/lib.rs:281 的 HostHello 握手）")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n结论：补丁 = 位置锚（change_context）+ 有序变更（chunk 内 -/+）+ 批量事务；")
    print("seek_sequence 的三级容错提供鲁棒性，单调游标提供歧义裁决，失败报告提供回路。")


if __name__ == "__main__":
    main()
