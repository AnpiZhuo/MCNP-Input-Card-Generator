"""INP 行级 diff 纯函数测试（difflib，纯 stdlib）。"""

from app.diff_inp import diff_stats, unified_diff_text


def test_unified_diff_text_identical_is_empty():
    text = "c test\nmode n\nnps 1000\n"
    assert unified_diff_text(text, text) == ""


def test_unified_diff_text_detects_change():
    a = "mode n\nnps 1000\n"
    b = "mode n\nnps 5000\n"
    out = unified_diff_text(a, b)
    assert "-nps 1000" in out
    assert "+nps 5000" in out


def test_diff_stats_counts_added_removed():
    a = "nps 1000\nfoo\nbar\n"
    b = "nps 5000\nfoo\nbaz\n"
    out = unified_diff_text(a, b)
    stats = diff_stats(out)
    assert stats["added"] == 2   # nps 5000 + baz
    assert stats["removed"] == 2  # nps 1000 + bar
    assert diff_stats("") == {"added": 0, "removed": 0}
