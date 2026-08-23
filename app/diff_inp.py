"""INP 文本行级 diff（纯 stdlib difflib，零新依赖）。

供 /api/diff-inp 使用；输出 unified diff 文本 + 增删统计。
"""

from __future__ import annotations

import difflib


def unified_diff_text(a: str, b: str, n: int = 3) -> str:
    """两段 INP 文本 → unified diff 字符串（无差异返回空串）。"""
    a_lines = (a or "").splitlines()
    b_lines = (b or "").splitlines()
    return "\n".join(
        difflib.unified_diff(a_lines, b_lines, lineterm="", n=n)
    )


def diff_stats(diff_text: str) -> dict:
    """统计 unified diff 的增删行数（忽略 +++/--- 文件头）。"""
    added = 0
    removed = 0
    for line in (diff_text or "").splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return {"added": added, "removed": removed}


__all__ = ["unified_diff_text", "diff_stats"]
