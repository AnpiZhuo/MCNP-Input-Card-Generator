# -*- coding: utf-8 -*-
"""`app/spline_skip.py` 单测 + 与 GEOUNED 判据的一致性锁。

背景（用户指定）：「遇到样条曲线了就跳过而不是终止或暂停，并报告」。
GEOUNED 的默认档是 `stop`（`load_step.py:69-71` 直接 `exit()`），worker 的兜底只会
吐一句"GEOUNED 终止: None" —— 所以本程序把默认档改成 `remove`（跳过），并把
"跳过了谁、什么曲面、多少个面"写进 `warnings`。

锁死的契约：
  1. **默认档 = 跳过**（`normalize_policy` 对 None/垃圾值都给 remove）；
  2. 报告必须**具体**：实体序号（0 起，与「跳过实体编号」同口径）、中文曲面类型、面数；
  3. `stop` 档与"全部实体都是样条"要**提前失败并说清怎么办**，不是含糊地退出；
  4. 物理剔除实体后的 `skip_solids` 重映射不许错位（错位 = 默默跳过另一个实体）；
  5. 判据只有一份 —— 与 GEOUNED 自己的 `spline()` **逐字一致**（装了 GEOUNED 才检查）。
"""
import os
import re
from pathlib import Path

import pytest

from app import spline_skip as S

PROJECT_DIR = Path(__file__).resolve().parents[2]
WORKER_PATH = PROJECT_DIR / "app" / "geouned_worker.py"
GEOUNED_SRC = os.environ.get("GEOUNED_PATH") or r"D:\MCNP\GEOUNED"
GEOUNED_SPLINE_PY = Path(GEOUNED_SRC) / "geouned" / "GEOUNED" / "loadfile" / "load_functions.py"


# ── 1. 档位归一：默认 = 跳过 ────────────────────────────────────

def test_default_policy_is_skip():
    """没填（None）/空串/垃圾值 → 一律「跳过」；GEOUNED 的 stop 不再是本程序默认。"""
    assert S.DEFAULT_POLICY == "remove"
    for raw in (None, "", "  ", "skip", 0, [], "STOPP"):
        assert S.normalize_policy(raw) == "remove", raw


def test_policy_normalizes_case_and_spaces():
    assert S.normalize_policy("Stop") == "stop"
    assert S.normalize_policy(" remove ") == "remove"
    assert S.normalize_policy("IGNORE") == "ignore"


# ── 2. 扫描：序号口径与"哪些实体"────────────────────────────────

def test_scan_keeps_zero_based_indices_and_drops_clean_solids():
    """空列表 = 该实体干净。序号必须是**原文件**里的 0 起下标（与 skip_solids 同口径）。"""
    rows = [[], ["BSplineSurface"], [], ["SurfaceOfExtrusion", "SurfaceOfExtrusion"]]
    rep = S.scan(rows)
    assert rep.indices == (1, 3)
    assert rep.total_solids == 4
    assert rep.face_count == 3
    assert not rep.is_total_loss


def test_scan_is_empty_when_no_spline():
    rep = S.scan([[], [], []])
    assert rep.solids == ()
    assert rep.indices == ()
    assert S.describe(rep, "remove") == []


def test_scan_passes_through_none_when_step_unreadable():
    """读不出来（worker 那边 Part 失败）→ None；调用方据此说"没检查"，不假装干净。"""
    assert S.scan(None) is None
    assert S.describe(None, "remove") == []
    assert S.blocking_reason(None, "stop") is None


def test_total_loss_only_when_every_solid_has_spline():
    assert S.scan([["BSplineSurface"], ["SurfaceOfRevolution"]]).is_total_loss
    assert not S.scan([["BSplineSurface"], []]).is_total_loss
    assert not S.scan([]).is_total_loss


# ── 3. 报告文案：具体到序号与曲面类型 ──────────────────────────

def test_describe_remove_reports_indices_kinds_and_faces():
    rep = S.scan([[], ["BSplineSurface", "BSplineSurface"], ["SurfaceOfExtrusion"]])
    (line,) = S.describe(rep, "remove")
    assert "实体 1、2" in line
    assert "NURBS 曲面" in line and "拉伸面" in line
    assert "3 个面" in line
    assert "已跳过这 2 个实体" in line
    assert "其余照常转换" in line


def test_describe_ignore_warns_about_wrong_geometry():
    rep = S.scan([["BSplineSurface"]])
    (line,) = S.describe(rep, "ignore")
    assert "强行翻译" in line
    assert "核对" in line and "重叠" in line


def test_describe_unknown_kind_is_not_swallowed():
    """GEOUNED 将来加了新的样条类，中文名认不得也要把原名带上（不吞信息）。"""
    (line,) = S.describe(S.scan([["SomeNewSplineSurface"]]), "remove")
    assert "SomeNewSplineSurface" in line


# ── 4. 提前失败：stop 档 / 全部是样条 ──────────────────────────

def test_stop_policy_blocks_with_actionable_text():
    rep = S.scan([[], ["BSplineSurface"]])
    reason = S.blocking_reason(rep, "stop")
    assert reason and "实体 1" in reason
    assert "停止转换" in reason and "跳过该实体" in reason     # 换哪一档能继续
    assert S.describe(rep, "stop") == []                      # 终止了就不再多说一句


def test_remove_policy_blocks_only_when_nothing_left():
    partial = S.scan([["BSplineSurface"], []])
    assert S.blocking_reason(partial, "remove") is None
    total = S.scan([["BSplineSurface"], ["SurfaceOfRevolution"]])
    reason = S.blocking_reason(total, "remove")
    assert reason and "全部" in reason and "没有可转换的实体" in reason
    # 换成"强行翻译"是给出路之一，但必须同时说清风险
    assert "强行翻译" in reason and "核对" in reason


def test_ignore_policy_never_blocks():
    """强行翻译是最"能出东西"的档：即便全是样条也不该拦住（用户自己的选择）。"""
    total = S.scan([["BSplineSurface"], ["SurfaceOfRevolution"]])
    assert S.blocking_reason(total, "ignore") is None


# ── 5. 物理剔除后的编号重映射（错位 = 默默跳过别的实体）──────────

def test_remap_shifts_indices_after_removal():
    assert S.remap_skip_solids([3], [1]) == ([2], [])
    assert S.remap_skip_solids([0, 3], [1, 2]) == ([0, 1], [])
    assert S.remap_skip_solids([5], [0, 1, 2]) == ([2], [])


def test_remap_drops_redundant_indices_and_reports_them():
    """用户跳过的实体恰好也被样条剔除 ⇒ 丢掉并上报，不能让序号错位。"""
    mapped, redundant = S.remap_skip_solids([1, 4], [1])
    assert mapped == [3] and redundant == [1]


def test_remap_handles_empty_strings_and_duplicates():
    assert S.remap_skip_solids([], []) == ([], [])
    assert S.remap_skip_solids(["2", "2", 5], []) == ([2, 5], [])
    assert S.remap_skip_solids(None, [0]) == ([], [])


# ── 6. 判据只有一份：worker 的 isinstance 必须与 GEOUNED 的 spline() 一致 ──

def _part_types_in(text: str):
    """从源码里抠出 `Part.XXX` 类型名（只看 isinstance 那一处）。"""
    return set(re.findall(r"Part\.([A-Za-z_]\w*)", text))


def test_worker_uses_geouneds_spline_criterion():
    """worker 里判定"含样条面"的 isinstance 元组必须与 GEOUNED `spline()` 逐字一致。"""
    src = WORKER_PATH.read_text(encoding="utf-8")
    body = src.split("def _spline_kinds_per_solid", 1)[1].split("\ndef ", 1)[0]
    names = _part_types_in(body)
    assert names == {"BSplineSurface", "SurfaceOfRevolution", "SurfaceOfExtrusion"}, names
    assert "isinstance" in body


@pytest.mark.skipif(not GEOUNED_SPLINE_PY.is_file(),
                    reason=f"本机没有 GEOUNED 源码可对照：{GEOUNED_SPLINE_PY}")
def test_criterion_matches_the_installed_geouned():
    """对照 GEOUNED 自己的 `load_functions.spline()`（本机装了才跑）。"""
    text = GEOUNED_SPLINE_PY.read_text(encoding="utf-8", errors="replace")
    body = text.split("def spline(", 1)[1].split("\ndef ", 1)[0]
    assert _part_types_in(body) == {"BSplineSurface", "SurfaceOfRevolution", "SurfaceOfExtrusion"}

    worker = WORKER_PATH.read_text(encoding="utf-8")
    wbody = worker.split("def _spline_kinds_per_solid", 1)[1].split("\ndef ", 1)[0]
    assert _part_types_in(wbody) == _part_types_in(body)


# ── 7. 接线锁：worker 真的走了这套逻辑（没有别的观察面）──────────

def test_worker_wires_spline_policy_and_reporting():
    src = WORKER_PATH.read_text(encoding="utf-8")
    assert "import spline_skip" in src
    assert "spline_skip.normalize_policy(load_step.get(\"spline_surfaces\"))" in src
    assert "spline_skip.scan(_spline_kinds_per_solid(step_path))" in src
    assert "spline_skip.blocking_reason(" in src
    assert "spline_skip.describe(" in src
    assert "spline_skip.remap_skip_solids(" in src
    # 曾经的致命默认值不许回来（GEOUNED 的 stop 会让整个导入以一句
    # "GEOUNED 终止: None" 收场）
    assert 'load_step.get("spline_surfaces", "stop")' not in src
    # 也绝不能再在下面这行重写默认档
    assert 'spline_surfaces=load_step' not in src


def test_worker_does_not_pollute_the_json_protocol():
    """GEOUNED 会 print 到 stdout（load_step.py:67），必须改道 —— 否则 stdout 的 JSON 解析失败。"""
    src = WORKER_PATH.read_text(encoding="utf-8")
    assert "_StdoutTee" in src
    assert "sys.stdout = tee" in src
    assert "sys.stdout = real_stdout" in src
