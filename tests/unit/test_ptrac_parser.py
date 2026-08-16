"""PTRAC 粒子径迹解析器测试 —— app/ptrac/ptrac_parser.py（契约 ptrac-visualization.md v2 §2/§5）。

- fixture tests/fixtures/ptrac_sample.txt = example_02.ptrac 头部 8 行 + 2 历史子集
  （历史 1：src/sur/flag 3 点；历史 2：src/col/sur/flag 4 点，col 带能量 112.6）。
- L 表驱动能量（变量 ID 10 = NXS(2,IEX)）与粒子类型（变量 ID 16 = IPT）提取。
- max_tracks 截断标 truncated；max_points 均匀抽稀保持首尾。
- 第 1 行非 "-1" 或行数 <8 → PTRACFormatError。

铁律：本文件【不 import】gui.backend.api_server（模块级 pyvista/FreeCAD 探测）。
"""
import ast
from pathlib import Path

import pytest

PARSER = Path(__file__).resolve().parent.parent.parent / "app" / "ptrac" / "ptrac_parser.py"
WORKER = Path(__file__).resolve().parent.parent.parent / "app" / "ptrac" / "_ptrac_worker.py"
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

FIXTURE = FIXTURES / "ptrac_sample.txt"


# ── 契约 §2：模块顶只 stdlib（照 meshtal 范式）───────────────────
def _module_top_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
    return names


def test_parser_top_level_stdlib_only():
    """契约 §2：ptrac_parser 模块顶只 import stdlib（numpy/pymcnp 不进模块顶）。"""
    roots = {t.split(".")[0] for t in _module_top_imports(PARSER)}
    forbidden = {"numpy", "pymcnp"}
    assert not (forbidden & roots), f"parser 模块顶不应 import: {sorted(forbidden & roots)}"


def test_worker_top_level_stdlib_only():
    """契约 §2：_ptrac_worker 模块顶只 import stdlib（照 _meshtal_worker）。"""
    roots = {t.split(".")[0] for t in _module_top_imports(WORKER)}
    forbidden = {"numpy", "pymcnp"}
    assert not (forbidden & roots), f"worker 模块顶不应 import: {sorted(forbidden & roots)}"


# ── 解析器核心（契约 §2 / §5）───────────────────────────────────
def _parse(path=FIXTURE, **kw):
    import importlib.util
    spec = importlib.util.spec_from_file_location("ptrac_parser_under_test", PARSER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.parse_ptrac(str(path), **kw)


def test_parse_header_code_title():
    """头 ②③ 行：code + title 提取。"""
    r = _parse()
    assert r["header"]["code"] == "mcnp"
    assert r["header"]["title"].strip() == "PTRAC sample fixture"


def test_parse_two_histories_seven_points():
    """fixture：2 历史 / 7 点（历史 1=3 点，历史 2=4 点）。"""
    r = _parse()
    assert len(r["tracks"]) == 2
    assert r["stats"]["nps"] == 2
    assert r["stats"]["events"] == 7
    assert r["stats"]["points"] == 7
    assert r["stats"]["truncated"] is False
    assert r["truncated"] is False
    assert [len(t["points"]) for t in r["tracks"]] == [3, 4]


def test_parse_point_type_position_energy():
    """点结构 [x,y,z,type,energy]：类型/位置/能量。"""
    r = _parse()
    t1, t2 = r["tracks"][0], r["tracks"][1]
    # 历史 1：src(3000)/sur(5000)/flag(9000)
    assert [p[3] for p in t1["points"]] == [3000, 5000, 9000]
    assert t1["points"][0][:4] == pytest.approx([0.0, 0.0, 0.0, 3000])
    # 历史 2：src(3000)/col(4000, 能量 112.6)/sur(5000)/flag(9000)
    assert [p[3] for p in t2["points"]] == [3000, 4000, 5000, 9000]
    col = t2["points"][1]
    assert col[3] == 4000
    assert col[4] == pytest.approx(112.6)          # L 表 ID 10 = 能量
    assert col[:3] == pytest.approx([-4.7453, -11.894, 72.0])
    # 非碰撞事件能量取不到 → 0
    assert t1["points"][0][4] == 0.0
    assert t1["points"][1][4] == 0.0


def test_parse_particle_types():
    """track.particle = 节点粒子类型（IPT=1 → n）；stats.particles 计数。"""
    r = _parse()
    assert [t["particle"] for t in r["tracks"]] == ["n", "n"]
    assert r["stats"]["particles"] == {"n": 2, "p": 0, "e": 0}


def test_parse_world_box():
    """world_box = 所有点 min/max 包围盒。"""
    r = _parse()
    wb = r["world_box"]
    assert wb["min"] == pytest.approx([-4.7453, -11.894, 0.0])
    assert wb["max"] == pytest.approx([101.7, 94.656, 143.87])


# ── 截断 / 抽稀（契约 §2）───────────────────────────────────────
def test_parse_max_tracks_truncation():
    """max_tracks=1 → 只留第 1 历史，truncated 如实标记。"""
    r = _parse(max_tracks=1)
    assert len(r["tracks"]) == 1
    assert r["tracks"][0]["nps"] == 1
    assert r["truncated"] is True
    assert r["stats"]["truncated"] is True


def test_parse_max_points_decimation_keeps_ends():
    """max_points 均匀抽稀保持首尾：构造 4 点单历史，max_points=2 → 首尾两点。"""
    import importlib.util
    import tempfile
    spec = importlib.util.spec_from_file_location("ptrac_parser_under_test", PARSER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # 头 8 行 + 1 历史 4 事件（src/sur/flag + 一个 col）
    text = (
        "   -1\n"
        "mcnp    6                        08/15/26 23:00:00 \n"
        "decimate fixture\n"
        "   1.0000E+00  1.0000E+00  1.0000E+02  0.0000E+00  0.0000E+00  1.0000E+00  1.0000E+00  0.0000E+00  1.0000E+00  1.0000E+04\n"
        "   0.0000E+00  0.0000E+00  0.0000E+00  0.0000E+00  0.0000E+00  0.0000E+00  1.0000E+00  1.0000E+00  0.0000E+00  0.0000E+00\n"
        "     2    6    3    7    3    7    3    7    3    7    3    0    4    0    0    0    0    0    0    0\n"
        "    1   2   7   8   9  16  17  18  20  21  22   7   8  10  11  16  17  18  20  21  22   7   8  12  13  16  17  18  20  21\n"
        "   22   7   8  10  11  16  17  18  20  21  22   7   8  14  15  16  17  18  20  21  22\n"
        "          1      1000\n"
        "       3000         1        40         1        77         1\n"
        "   0.00000E+00  0.00000E+00  0.00000E+00\n"
        "       4000         2     112.6       169         1        12         3\n"
        "  -0.47453E+01 -0.11894E+02  0.72000E+02\n"
        "       5000         2       999         0         1        99         0\n"
        "  -0.47453E+01 -0.11894E+02  0.72000E+02\n"
        "       9000         2         1         1         1        99         0\n"
        "  -0.47453E+01 -0.11894E+02  0.72000E+02\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".ptrac", delete=False, encoding="utf-8") as f:
        f.write(text)
        tmp = f.name
    try:
        r = mod.parse_ptrac(tmp, max_tracks=500, max_points=2)
        pts = r["tracks"][0]["points"]
        # 保持首尾（第 1 个与最后 1 个必留），且总点数 ≤ 预算允许的抽稀
        assert pts[0][3] == 3000
        assert pts[-1][3] == 9000
        assert 1 < len(pts) <= 2 + 1  # 首尾 + 最多 1 个中间点（抽稀步长内）
    finally:
        import os
        os.unlink(tmp)


# ── 坏文件 / 缺文件（契约 §2 / §5）──────────────────────────────
def test_parse_bad_file_first_line():
    """第 1 行非 "-1" → PTRACFormatError。"""
    import importlib.util
    import tempfile
    spec = importlib.util.spec_from_file_location("ptrac_parser_under_test", PARSER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("this is not ptrac\n" + "x" * 10 + "\n")
        tmp = f.name
    try:
        with pytest.raises(mod.PTRACFormatError):
            mod.parse_ptrac(tmp)
    finally:
        import os
        os.unlink(tmp)


def test_parse_too_few_lines():
    """行数 <8 → PTRACFormatError。"""
    import importlib.util
    import tempfile
    spec = importlib.util.spec_from_file_location("ptrac_parser_under_test", PARSER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("   -1\nmcnp\n")
        tmp = f.name
    try:
        with pytest.raises(mod.PTRACFormatError):
            mod.parse_ptrac(tmp)
    finally:
        import os
        os.unlink(tmp)


def test_parse_missing_file():
    """文件不存在 → FileNotFoundError（端点/worker 转 hint）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("ptrac_parser_under_test", PARSER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with pytest.raises(FileNotFoundError):
        mod.parse_ptrac(str(FIXTURES / "does_not_exist.ptrac"))
