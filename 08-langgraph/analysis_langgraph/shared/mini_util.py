# -*- coding: utf-8 -*-
"""
mini_util.py —— 十课共用的零依赖小工具。

只放与"图引擎语义"无关的通用件：
  force_utf8_stdout() 把 stdout/stderr 重配成 UTF-8——Windows 控制台默认 GBK，
                 课程里的 ⏸ ↟ ⚠ 这类符号会直接抛 UnicodeEncodeError
  uid()          模拟 LangGraph 的唯一 id 生成（真实现用 uuid5/xxh3，见
                 libs/langgraph/langgraph/pregel/_algo.py 的 task_id_func）
  next_version() 模拟 checkpointer 的 get_next_version（真实现挂在
                 BaseCheckpointSaver 上，libs/checkpoint/langgraph/checkpoint/base/__init__.py）
  banner()       场景分隔标题
  expect_error() 断言"这里必须抛错"——把报错变成教学内容
  fmt_state()    字典状态的紧凑打印
"""

from __future__ import annotations

import itertools
import sys
import time

_counter = itertools.count(1)


def force_utf8_stdout() -> None:
    """控制台编码不归课程管，但报错会打断跑课：统一切到 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def uid(prefix: str = "ckpt") -> str:
    """生成单调递增的唯一 id。

    真实 LangGraph 的 checkpoint id 要求"唯一且单调递增、可排序"
    （libs/checkpoint/langgraph/checkpoint/base/__init__.py:98-102），
    用 uuid5/xxh3 从 checkpoint_id_bytes 派生；这里用计数器前缀模拟
    同一性质：字典序 == 时间序。
    """
    return f"{prefix}-{next(_counter):04d}-{time.time_ns() % 100000:05d}"


def next_version(current) -> int:
    """通道版本号推进：返回严格大于 current 的整数。

    真实现是 BaseCheckpointSaver.get_next_version(current, channel)：
    整数十六进制自增再转字符串（Checkpoint 里可排序是唯一硬性质）。
    mini 直接用 int，保持"可比较"这一性质且不受字典序陷阱影响。
    """
    return (current or 0) + 1


NULL_VERSION = 0  # 真实引擎里的 null_version：从未被写过时的占位版本


def banner(title: str) -> None:
    print(f"\n{'=' * 62}\n== {title}\n{'=' * 62}")


def expect_error(label: str, fn, exc=Exception):
    """运行 fn，断言它抛出 exc，并把报错信息打印出来当教材。

    LangGraph 把大量错误左移到建图/写入期（InvalidUpdateError 等），
    "预期报错"本身就是课程内容——所以跑课的人应该在输出里看到它。
    """
    try:
        fn()
    except exc as e:
        print(f"  [预期报错] {label}: {type(e).__name__}: {e}")
        return e
    raise AssertionError(f"{label}: 预期抛出 {exc.__name__}，但没有抛")


def fmt_state(d: dict) -> str:
    """紧凑打印状态字典（截断长值，保证输出可读）。"""
    parts = []
    for k, v in d.items():
        s = repr(v)
        if len(s) > 48:
            s = s[:45] + "..."
        parts.append(f"{k}={s}")
    return "{" + ", ".join(parts) + "}"
