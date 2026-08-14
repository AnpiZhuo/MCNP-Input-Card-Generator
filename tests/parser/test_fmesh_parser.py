"""fmesh_parser 卡体 parse/emit 往返测试 —— app/meshtal/fmesh_parser.py（契约 meshtal-visualization.md §5.3/§6）。

测 FMESH/TMESH 卡体 → FmeshDefinition → 回放 → 再解析字段保留；多区间 IMESH；
CMESH(cyl) 降级 + raw 保留；structured 空 → raw 回放。
纯 stdlib + app.models，不 import gui.backend.api_server / FreeCAD。
"""
import pytest

from app.meshtal.fmesh_parser import fmesh_defs_to_lines, parse_fmesh_lines

FMESH4 = [
    "FMESH4:N GEOM=XYZ ORIGIN=-100 -100 -150",
    "     IMESH=100 IINTS=10",
    "     JMESH=100 JINTS=10",
    "     KMESH=50 KINTS=100",
]

TMESH5 = [
    "TMESH5",
    "RMESH5:N GEOM=XYZ ORIGIN=-50 -50 -50",
    "     IMESH=50 IINTS=5",
    "     JMESH=50 JINTS=5",
    "     KMESH=50 KINTS=5",
]


# ── 1. FMESH 卡体 → FmeshDefinition ────────────────────────────
def test_fmesh4_parse_fields():
    """FMESH4:N → kind/number/particle/geom/origin/IMESH×INTS。"""
    defs = parse_fmesh_lines(FMESH4)
    assert len(defs) == 1
    fd = defs[0]
    assert fd.kind == "FMESH" and fd.number == 4 and fd.particle == "N"
    assert fd.geom.lower() == "xyz"
    assert fd.origin == "-100 -100 -150"
    assert fd.imesh == "100" and fd.iints == "10"
    assert fd.jmesh == "100" and fd.jints == "10"
    assert fd.kmesh == "50" and fd.kints == "100"


# ── 2. TMESH + RMESH 子卡 ──────────────────────────────────────
def test_tmesh5_parse_fields():
    """TMESH5 标题 + RMESH5 子卡 → 单一 kind=TMESH 定义。"""
    defs = parse_fmesh_lines(TMESH5)
    assert len(defs) == 1
    fd = defs[0]
    assert fd.kind == "TMESH" and fd.number == 5 and fd.particle == "N"
    assert fd.origin == "-50 -50 -50"
    assert fd.imesh == "50" and fd.iints == "5"
    assert fd.jmesh == "50" and fd.jints == "5"
    assert fd.kmesh == "50" and fd.kints == "5"


# ── 3. emit → reparse 往返 ─────────────────────────────────────
def test_fmesh_emit_reparse_roundtrip():
    """FMESH 结构化 → 回放 → 再解析字段保留。"""
    defs = parse_fmesh_lines(FMESH4)
    lines = fmesh_defs_to_lines(defs)
    assert any("FMESH4" in ln for ln in lines)
    defs2 = parse_fmesh_lines(lines)
    assert len(defs2) == 1
    a, b = defs[0], defs2[0]
    for attr in ("kind", "number", "particle", "geom", "origin", "imesh", "iints",
                 "jmesh", "jints", "kmesh", "kints"):
        assert getattr(a, attr) == getattr(b, attr), f"字段 {attr} 往返丢失"


def test_tmesh_emit_reparse_roundtrip():
    """TMESH 结构化 → 回放（TMESH 标题 + RMESH 卡）→ 再解析字段保留。"""
    defs = parse_fmesh_lines(TMESH5)
    lines = fmesh_defs_to_lines(defs)
    assert lines[0].startswith("TMESH5")
    defs2 = parse_fmesh_lines(lines)
    assert len(defs2) == 1
    a, b = defs[0], defs2[0]
    assert a.kind == b.kind and a.number == b.number
    assert a.origin == b.origin and a.imesh == b.imesh and a.jints == b.jints


# ── 4. 多区间 IMESH（边界值原文保留，不数值化）────────────────
def test_multi_interval_imesh_preserved():
    """IMESH=10 20 IINTS=2 2 → imesh='10 20'、iints='2 2'（多值原文，不数值化）。"""
    lines = [
        "FMESH7:N GEOM=XYZ ORIGIN=0 0 0",
        "     IMESH=10 20 IINTS=2 2",
        "     JMESH=10 20 JINTS=2 2",
        "     KMESH=10 KINTS=2",
    ]
    defs = parse_fmesh_lines(lines)
    assert len(defs) == 1
    assert defs[0].imesh == "10 20"
    assert defs[0].iints == "2 2"
    assert defs[0].jmesh == "10 20"
    assert defs[0].jints == "2 2"


# ── 5. CMESH(cyl)：降级 + raw 保留 ─────────────────────────────
def test_cmesh_unsupported_geom_raw_preserved():
    """CMESH8(cyl) → geom='cyl'（unsupported 降级），raw 保留 AXS/VEC。"""
    lines = [
        "TMESH8",
        "CMESH8:N GEOM=CYL ORIGIN=0 0 0",
        "     AXS=1 0 0 VEC=1",
    ]
    defs = parse_fmesh_lines(lines)
    assert len(defs) == 1
    fd = defs[0]
    assert fd.kind == "TMESH" and fd.number == 8 and fd.particle == "N"
    assert fd.geom.lower() == "cyl"
    # 回放不把 CMESH 变 RMESH、不丢 AXS/VEC
    emitted = fmesh_defs_to_lines(defs)
    assert any("CMESH8" in ln for ln in emitted)
    assert any("AXS=1" in ln for ln in emitted)
    # 再解析仍识别为 cyl
    defs2 = parse_fmesh_lines(emitted)
    assert defs2[0].geom.lower() == "cyl"


# ── 6. structured 空 → raw 回放（round-trip 兜底）──────────────
def test_structured_empty_raw_fallback():
    """结构化字段为空 → raw 回放（照 D-10 raw_line 先例，round-trip 不丢）。"""
    from app.models import FmeshDefinition
    fd = FmeshDefinition(number=4, kind="FMESH", particle="N",
                         raw="FMESH4:N GEOM=XYZ ORIGIN=1 1 1\n     IMESH=10 IINTS=2")
    lines = fmesh_defs_to_lines([fd])
    assert any("FMESH4" in ln for ln in lines)
    assert any("IMESH=10" in ln for ln in lines)
