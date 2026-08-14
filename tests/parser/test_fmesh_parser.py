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


# ── 7. 解析容错：EINTS/EMINTS、TINTS/TMINTS 两种拼写都映射 ──────
def test_eints_emints_tints_tmints_tolerance():
    """EINTS=/EMINTS=、TINTS=/TMINTS= 两种拼写导入都映射到 emints/tmints。

    字段对齐 MCNP6（生成关键字用 EMINTS/TMINTS），但旧卡体（EINTS/TINTS）导入不丢。
    """
    old_lines = [
        "FMESH4:N GEOM=XYZ ORIGIN=0 0 0",
        "     EMESH=1 10 EINTS=2 2",
        "     TMESH=0 100 TINTS=2",
    ]
    defs_old = parse_fmesh_lines(old_lines)
    assert len(defs_old) == 1
    assert defs_old[0].emints == "2 2", "EINTS 未映射到 emints"
    assert defs_old[0].tmints == "2", "TINTS 未映射到 tmints"

    new_lines = [
        "FMESH4:N GEOM=XYZ ORIGIN=0 0 0",
        "     EMESH=1 10 EMINTS=2 2",
        "     TMESH=0 100 TMINTS=2",
    ]
    defs_new = parse_fmesh_lines(new_lines)
    assert len(defs_new) == 1
    assert defs_new[0].emints == "2 2", "EMINTS 未映射到 emints"
    assert defs_new[0].tmints == "2", "TMINTS 未映射到 tmints"


# ── 8. 生成：EMINTS/TMINTS 关键字 + GEOM 连写 ────────────────────
def test_generation_uses_emints_tmints_and_geom_connected():
    """卡体输出含 EMINTS/TMINTS（非 EINTS/TINTS）+ GEOM=XYZ/GEOM=CYL 连写。

    避免 `GEOM=X Y Z` 非法输出：GEOM 值必须是单个 token（MCNP 关键字值连写）。
    """
    from app.models import FmeshDefinition
    fd = FmeshDefinition(number=4, kind="FMESH", particle="N", geom="XYZ",
                         origin="0 0 0", emesh="1 10", emints="2 2",
                         tmesh="0 100", tmints="2")
    lines = fmesh_defs_to_lines([fd])
    out = "\n".join(lines)
    assert "EMINTS=2 2" in out, f"卡体未含 EMINTS: {out}"
    assert "TMINTS=2" in out, f"卡体未含 TMINTS: {out}"
    assert "EINTS=" not in out, "不应再输出旧关键字 EINTS"
    assert "TINTS=" not in out, "不应再输出旧关键字 TINTS"
    assert "GEOM=XYZ" in out, f"GEOM 未连写为单 token: {out}"
    assert "GEOM=X Y Z" not in out, "GEOM 值被空格拆开（非法）"

    fd_cyl = FmeshDefinition(number=5, kind="FMESH", particle="N", geom="CYL",
                             origin="0 0 0", axs="1 0 0")
    out_cyl = "\n".join(fmesh_defs_to_lines([fd_cyl]))
    assert "GEOM=CYL" in out_cyl, f"cyl GEOM 未连写: {out_cyl}"
    assert "GEOM=C Y L" not in out_cyl


# ── 9. 新字段 round-trip：AXS/VEC/TR/OUT + emints/tmints ─────────
def test_axs_vec_tr_out_roundtrip():
    """含 AXS=/VEC=/TR=/OUT= 的卡体 → 解析 → 再生成 → 字段保留。

    FMESH cyl（GEOM=CYL + AXS/VEC）+ TR 变换 + OUT 单位，全链 round-trip。
    """
    lines = [
        "FMESH4:N GEOM=CYL ORIGIN=0 0 0",
        "     AXS=1 0 0 VEC=0 1 0",
        "     TR=1 OUT=f",
        "     EMESH=1 10 EMINTS=5",
        "     TMESH=0 100 TMINTS=2",
    ]
    defs = parse_fmesh_lines(lines)
    assert len(defs) == 1
    fd = defs[0]
    assert fd.kind == "FMESH" and fd.number == 4
    assert fd.axs == "1 0 0", "AXS 未解析"
    assert fd.vec == "0 1 0", "VEC 未解析"
    assert fd.tr == "1", "TR 未解析"
    assert fd.out == "f", "OUT 未解析"
    assert fd.emints == "5" and fd.tmints == "2"

    emitted = fmesh_defs_to_lines(defs)
    out = "\n".join(emitted)
    assert "AXS=1 0 0" in out, f"回放丢失 AXS: {out}"
    assert "VEC=0 1 0" in out, f"回放丢失 VEC: {out}"
    assert "TR=1" in out, f"回放丢失 TR: {out}"
    assert "OUT=f" in out, f"回放丢失 OUT: {out}"
    assert "EMINTS=5" in out and "TMINTS=2" in out

    defs2 = parse_fmesh_lines(emitted)
    a, b = defs[0], defs2[0]
    for attr in ("kind", "number", "geom", "origin", "axs", "vec", "tr", "out",
                 "emints", "tmints"):
        assert getattr(a, attr) == getattr(b, attr), f"字段 {attr} 往返丢失"


# ── 10. 旧拼写导入 → 新关键字回放 → 再解析（round-trip 全链）────
def test_old_spelling_import_emits_new_keywords_roundtrip():
    """EINTS/TINTS 旧拼写导入 → 生成回放为 EMINTS/TMINTS → 再解析字段保留。"""
    lines = [
        "FMESH4:N GEOM=XYZ ORIGIN=0 0 0",
        "     EMESH=1 10 EINTS=5",
        "     TMESH=0 100 TINTS=2",
    ]
    defs = parse_fmesh_lines(lines)
    emitted = fmesh_defs_to_lines(defs)
    out = "\n".join(emitted)
    assert "EMINTS=5" in out and "TMINTS=2" in out, f"旧拼写未转为新关键字: {out}"
    defs2 = parse_fmesh_lines(emitted)
    assert defs2[0].emints == "5" and defs2[0].tmints == "2"
