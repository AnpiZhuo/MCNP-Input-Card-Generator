"""mcnp_tasks — MCNP `tasks N`（OpenMP 线程数）解析与排他卡校验的单测。

纯 stdlib 深模块、无外部依赖。⚠️ **不得** import gui.backend.api_server（项目纪律：会引入
pyvista/FreeCAD 探测污染），故被测逻辑单独住在 `app/mcnp_tasks.py`。

权威依据：C810.pdf 页 875 —— "DBCN(2,3,4), SSW, and PTRAC are incompatible with
tasks > 1 (FATAL error)."
"""
import os

from app.mcnp_tasks import detect_tasks_conflict, expand_mcnp_numbers, resolve_mcnp_tasks

_CPU = int(os.cpu_count() or 1)


# ── expand_mcnp_numbers：nJ/nj 跳格展开 ──
def test_expand_jump_expands_to_zeros():
    assert expand_mcnp_numbers(["28j", "0"]) == [0.0] * 29


def test_expand_uppercase_jump():
    assert expand_mcnp_numbers(["3J", "5"]) == [0.0, 0.0, 0.0, 5.0]


def test_expand_non_numeric_is_none():
    assert expand_mcnp_numbers(["abc"]) == [None]


def test_expand_empty():
    assert expand_mcnp_numbers([]) == []


# ── detect_tasks_conflict：C810 页 875 的排他卡 ──
def test_ptrac_conflicts():
    assert detect_tasks_conflict("mode n\nptrac file=asc\nnps 1000") == "PTRAC 卡"


def test_ssw_conflicts():
    assert detect_tasks_conflict("ssw 1 2 3") == "SSW 面源卡"


def test_ssr_conflicts():
    assert detect_tasks_conflict("ssr 1 2") == "SSR 面源卡"


def test_dbcn_2nd_entry_nonzero_conflicts():
    assert detect_tasks_conflict("dbcn 0 1") == "DBCN 卡的第 2 项"


def test_dbcn_3rd_entry_nonzero_conflicts():
    assert detect_tasks_conflict("dbcn 0 0 7") == "DBCN 卡的第 3 项"


def test_dbcn_4th_entry_nonzero_conflicts():
    assert detect_tasks_conflict("dbcn 0 0 0 -1") == "DBCN 卡的第 4 项"


def test_dbcn_all_zero_ok():
    assert detect_tasks_conflict("dbcn 0 0 0 0") == ""


def test_dbcn_jump_zeros_ok():
    """conftest 里的真实写法 `DBCN 28j 0 13j 0`：跳格展开后全为 0 → 不冲突。

    这是最容易误报的一条 —— 若把 `28j` 当成"非数值即冲突"，正常卡会被降级成单线程。
    """
    assert detect_tasks_conflict("DBCN  28j  0  13j  0") == ""


def test_dbcn_first_entry_nonzero_ok():
    """第 1 项是常规调试开关，不属 C810 的 (2,3,4)。"""
    assert detect_tasks_conflict("dbcn 1 0 0 0") == ""


def test_comment_line_ignored():
    assert detect_tasks_conflict("c ptrac file=asc\nmode n") == ""


def test_inline_dollar_comment_ignored():
    assert detect_tasks_conflict("mode n $ ptrac file=asc") == ""


def test_clean_card_no_conflict():
    assert detect_tasks_conflict("mode n\nnps 1000\nsdef pos=0 0 0") == ""


def test_empty_text():
    assert detect_tasks_conflict("") == ""
    assert detect_tasks_conflict(None) == ""


# ── resolve_mcnp_tasks：请求 → (tasks, note) ──
def test_normal_request_passes_through():
    want = min(4, _CPU)
    tasks, note = resolve_mcnp_tasks(want, "mode n")
    assert tasks == want and note == ""


def test_single_thread_has_no_note():
    assert resolve_mcnp_tasks(1, "ptrac file=asc") == (1, "")


def test_conflict_forces_single_and_notes():
    tasks, note = resolve_mcnp_tasks(min(8, _CPU), "mode n\nptrac file=asc")
    assert tasks == 1, "PTRAC 与 tasks>1 不兼容，必须压回单线程"
    assert "PTRAC 卡" in note and "单线程" in note


def test_conflict_note_mentions_detected_card():
    _, note = resolve_mcnp_tasks(2, "dbcn 0 1")
    assert "DBCN 卡的第 2 项" in note


def test_missing_tasks_defaults_to_one():
    assert resolve_mcnp_tasks(None, "mode n") == (1, "")


def test_garbage_tasks_defaults_to_one():
    assert resolve_mcnp_tasks("abc", "mode n") == (1, "")


def test_zero_and_negative_clamp_to_one():
    assert resolve_mcnp_tasks(0, "mode n")[0] == 1
    assert resolve_mcnp_tasks(-5, "mode n")[0] == 1


def test_oversized_clamped_to_cpu_count():
    """超过逻辑核数的请求被夹回 cpu_count()（但**不**主动降到物理核 —— 那是用户的选择）。"""
    tasks, _ = resolve_mcnp_tasks(99999, "mode n")
    assert tasks == _CPU
