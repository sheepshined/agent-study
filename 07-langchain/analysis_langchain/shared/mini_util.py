"""shared/mini_util.py —— 课程共享小工具（扮演真实工程里 langchain-core "支撑件"的角色）

各课 code.py 通过把 shared/ 注入 sys.path 后 `from mini_util import ...` 复用。
这里只放真正的"小工具"：打印排版、事件日志、token 估算、编码兜底。
各课的 Mock 模型、消息类、图引擎等主体实现都留在课内——每一课都要能独立读懂。
"""

from __future__ import annotations

import json
import sys


def force_utf8_stdout() -> None:
    """Windows 控制台默认 GBK，中文输出会乱码/报错 —— 统一兜底成 UTF-8。

    真实工程里这类"环境差异吸收层"常被忽略，但它正是课程能在任何机器
    上一键跑通的前提（run.bat 里同时设了 PYTHONIOENCODING，双保险）。
    """
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass  # 某些嵌入环境不可重配，静默放弃：教学代码不做过度防御


def banner(title: str, sub: str | None = None) -> None:
    """分节标题：让 `python code.py` 的输出有清晰的场景分隔。"""
    line = "=" * 62
    print(f"\n{line}\n== {title}")
    if sub:
        print(f"== {sub}")
    print(line)


def show(label: str, obj: object) -> None:
    """带标签打印一个对象的 JSON 视图（中文原样输出，便于人读）。"""
    if isinstance(obj, str):
        print(f"  {label}: {obj}")
        return
    try:
        print(f"  {label}: {json.dumps(obj, ensure_ascii=False, default=str)}")
    except TypeError:
        print(f"  {label}: {obj!r}")


class EventLog:
    """事件日志：按发生顺序收集 (序号, 事件类型, 载荷)。

    LangChain 里"生命周期事件"（on_chat_model_start / on_llm_new_token /
    on_llm_end / on_chain_end ...）走回调体系单独成一条通道，与数据流并行。
    本课程在 s02（回调树）、s05（中间件审计）、s09（流式双通道）都用它扮演
    事件通道：**数据走数据，事件走事件，两者时间线交错但职责分离**。
    """

    def __init__(self) -> None:
        self.items: list[tuple[int, str, dict]] = []
        self._seq = 0

    def log(self, type_: str, **payload: object) -> None:
        self._seq += 1
        self.items.append((self._seq, type_, payload))

    def dump(self, indent: str = "  ") -> None:
        for seq, type_, payload in self.items:
            body = json.dumps(payload, ensure_ascii=False, default=str)
            print(f"{indent}#{seq:<3} {type_:<22} {body}")

    def clear(self) -> None:
        self.items.clear()


def estimate_tokens(text: str) -> int:
    """朴素 token 估算（约 3 字符 ≈ 1 token）。

    真实实现会用 tiktoken / 厂商分词器；这里只求"量级正确"，供
    s05（上下文预算）、s06（检查点元数据）、s09（用量统计）使用。
    """
    return max(1, (len(text) + 2) // 3)


# 导入本模块即完成 stdout 编码兜底，各课无需重复处理。
force_utf8_stdout()
