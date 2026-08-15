"""MESHTAL 文件解析测试 —— app/meshtal/meshtal_parser.py（契约 meshtal-visualization.md §2.2 / §3.4）。

现状（2026-08-14，功能未实现 → 红基线）：`app/meshtal/` 模块不存在，
`from app.meshtal.meshtal_parser import parse_meshtal` 即 ImportError → 全部用例红。

红基线 pin（按契约 §9.1 / §9.4，vendor fixture 解析）：
  1. valid_38（10×10×100 网格，单能量/无时间）：dims/binEdges/grid_bounds/逐 bin 值/scalar_range —— RED
  2. valid_39（4 时间 bin）：时间边界/帧数/总行数 —— RED
  3. valid_40（2 能量 × 2 时间 bin）：dims/帧键/总行数 —— RED
  4. 能量/时间单 bin 边界（bins_energy==[0,1e36]、无时间→bins_time==[]）—— RED
  5. 兜底路径：minimal_meshtal.txt（非 pymcnp 产出格式，2×2×2 网格）—— RED
  6. 畸形输入 → 明确错误（优雅错误信封，不静默成功）—— RED

纪律：不 import gui.backend.api_server / FreeCAD。pymcnp 惰性 import（契约 §2.2）。
"""
from pathlib import Path

import pytest

try:
    from app.meshtal.meshtal_parser import parse_meshtal, parse_meshtal_file
    _MISSING = None
except ImportError as _e:  # pragma: no cover - 红基线：功能未实现
    _MISSING = _e


def _require_module():
    """模块缺失守卫：app/meshtal/meshtal_parser 不存在 → 本用例红（pin 缺口，非崩溃断言）。"""
    assert _MISSING is None, f"app.meshtal.meshtal_parser 模块缺失（红基线，功能未实现）: {_MISSING}"


FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _fixture(name: str) -> str:
    path = FIXTURES / name
    if not path.is_file():
        raise FileNotFoundError(f"fixture 缺失: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


# ── 1. valid_38：10×10×100 网格 ─────────────────────────────────
def test_valid38_dims_and_bin_edges():
    """valid_38 网格维度与 bin 边界（契约 §3.2 示例值）。"""
    _require_module()
    mf = parse_meshtal(_fixture("valid_38.meshtal"))
    assert mf.code == "mcnp" and mf.histories == pytest.approx(10000000.0)
    assert len(mf.tallies) == 1
    t = mf.tallies[0]
    assert t.number == 4
    assert t.particle == "n"
    assert t.geom == "xyz"
    assert len(t.bins_x) == 11 and len(t.bins_y) == 11 and len(t.bins_z) == 101
    assert t.bins_x[0] == -100 and t.bins_x[-1] == 100
    assert t.bins_y[0] == -100 and t.bins_y[-1] == 100
    assert t.bins_z[0] == -150 and t.bins_z[-1] == -50


def test_valid38_grid_bounds():
    """grid_bounds（契约 §3.2 A1.2）：由 bin 边界算网格世界包围盒。"""
    _require_module()
    t = parse_meshtal(_fixture("valid_38.meshtal")).tallies[0]
    bounds = {
        "min": [t.bins_x[0], t.bins_y[0], t.bins_z[0]],
        "max": [t.bins_x[-1], t.bins_y[-1], t.bins_z[-1]],
    }
    assert bounds == {
        "min": [-100.0, -100.0, -150.0],
        "max": [100.0, 100.0, -50.0],
    }, "valid_38 grid_bounds 与契约 §3.2 示例不一致"


def test_valid38_data_dims_and_values():
    """valid_38 稠密数组 shape (ni,nj,nk)=(10,10,100) + 逐 bin 已知值。"""
    _require_module()
    t = parse_meshtal(_fixture("valid_38.meshtal")).tallies[0]
    # 单能量单时间帧
    assert len(t.data) == 1 and len(t.error) == 1
    (e, tm), frame = next(iter(t.data.items()))
    assert (e, tm) == (0, 0)
    assert frame.shape == (10, 10, 100)
    # 逐 bin 值（z 最快；x/y 中心 = (edge+edge)/2）
    assert frame[0, 0, 0] == pytest.approx(3.99211, rel=1e-4)    # x=-90 y=-90 z=-149.5
    assert frame[0, 0, 1] == pytest.approx(4.94717, rel=1e-4)    # x=-90 y=-90 z=-148.5
    assert frame[9, 9, 99] == pytest.approx(58.6145, rel=1e-4)   # x=90 y=90 z=-50.5


def test_valid38_scalar_range():
    """scalar_range（全 tally 全帧 dataMin/dataMax，契约 §2.2）。"""
    _require_module()
    t = parse_meshtal(_fixture("valid_38.meshtal")).tallies[0]
    lo, hi = t.scalar_range
    assert lo == pytest.approx(3.99211, rel=1e-4)
    assert hi == pytest.approx(374.803, rel=1e-4)


# ── 2. valid_39：4 时间 bin ─────────────────────────────────────
def test_valid39_time_bins_and_frames():
    """valid_39 时间分箱：4 个时间 bin，data dict 4 帧，每帧 (10,10,100)。"""
    _require_module()
    mf = parse_meshtal(_fixture("valid_39.meshtal"))
    t = mf.tallies[0]
    assert t.bins_time == pytest.approx([-1e36, 2.0, 3.0, 4.0, 1000.0])
    assert len(t.bins_time) - 1 == 4
    # 帧数 = energyBins × timeBins = 1 × 4
    assert len(t.data) == 4
    for (e, tm), frame in t.data.items():
        assert e == 0 and 0 <= tm < 4
        assert frame.shape == (10, 10, 100)
    # 总行数守恒：全部帧 voxel 数 == 文件数据行数（40000）
    total = sum(frame.size for frame in t.data.values())
    assert total == 4 * 10 * 10 * 100 == 40000


# ── 3. valid_40：2 能量 × 2 时间 ────────────────────────────────
def test_valid40_energy_time_frames():
    """valid_40 能量/时间双分箱：2 能量 × 2 时间 = 4 帧，每帧 (4,4,4)。"""
    _require_module()
    t = parse_meshtal(_fixture("valid_40.meshtal")).tallies[0]
    assert t.bins_energy == pytest.approx([0.0, 3.0, 14.0])
    assert t.bins_time == pytest.approx([-1e36, 2.0, 3.0])
    assert len(t.data) == 2 * 2 == 4
    for (e, tm), frame in t.data.items():
        assert 0 <= e < 2 and 0 <= tm < 2
        assert frame.shape == (4, 4, 4)
    assert sum(frame.size for frame in t.data.values()) == 256
    lo, hi = t.scalar_range
    assert lo == pytest.approx(0.0, abs=1e-9)
    assert hi == pytest.approx(104.241, rel=1e-4)


# ── 4. 能量/时间单 bin 边界 ─────────────────────────────────────
def test_single_energy_bin_no_time_boundary():
    """无能量分箱 → bins_energy==[0,1e36]（恒单帧可切 0）；无时间分箱 → bins_time==[]。"""
    _require_module()
    t = parse_meshtal(_fixture("valid_38.meshtal")).tallies[0]
    assert t.bins_energy == pytest.approx([0.0, 1e36])
    assert t.bins_time == []


# ── 5. 兜底路径（minimal_meshtal.txt）───────────────────────────
def test_minimal_meshtal_fallback():
    """minimal_meshtal.txt（非 pymcnp 产出格式）→ 轻量兜底路径产出同一 MeshtalFile。"""
    _require_module()
    mf = parse_meshtal(_fixture("minimal_meshtal.txt"))
    t = mf.tallies[0]
    assert t.number == 1 and t.particle == "n"
    assert t.bins_x == [0.0, 1.0, 2.0]
    assert t.bins_y == [0.0, 1.0, 2.0]
    assert t.bins_z == [0.0, 0.5, 1.0]
    assert t.bins_energy == [0.0, 1e36]
    assert len(t.data) == 1
    frame = next(iter(t.data.values()))
    assert frame.shape == (2, 2, 2)
    assert frame[0, 0, 0] == pytest.approx(1.0)   # x=0.5 y=0.5 z=0.25
    assert frame[1, 1, 1] == pytest.approx(8.0)   # x=1.5 y=1.5 z=0.75
    lo, hi = t.scalar_range
    assert lo == pytest.approx(1.0) and hi == pytest.approx(8.0)


def test_parse_meshtal_file_mtime_path():
    """parse_meshtal_file：path/mtime 元数据 + 同 parse_meshtal 解析结果。"""
    _require_module()
    path = FIXTURES / "minimal_meshtal.txt"
    mf = parse_meshtal_file(str(path))
    assert mf.path == str(path)
    assert mf.mtime > 0
    assert len(mf.tallies) == 1


# ── 6. 成功解析不 emit 误导性警告（Bug 2 收尾，2026-08-15）────────────
def test_successful_parse_no_misleading_warning():
    """合法 meshtal 成功解析 → warnings 不含「pymcnp 解析失败」误导条目。

    现状（Bug 2 收尾）：`from pymcnp.meshtal import Meshtal` 恒 ImportError
    （pymcnp.meshtal 只导出 Block/Header/Tally，Meshtal 类在 src/pymcnp/Meshtal.py
    大写 M），pymcnp 校验从不生效，但成功解析后仍 emit 一条「pymcnp 解析失败…」
    → 前端 OutputTab 显示「警告 1 条」与解析成功自相矛盾。
    修复：成功解析 warnings 为空；真正失败走异常传播（worker 转 error 信封）。
    col 与矩阵（out=jk）两类真实样本都要覆盖。
    """
    _require_module()
    for name in ("valid_38.meshtal", "real_meshtal_jk.meshtal"):
        mf = parse_meshtal(_fixture(name))
        assert mf.tallies, f"{name} 应解析出 tally"
        assert mf.warnings == [], f"{name} 成功解析后不应带误导性警告: {mf.warnings}"


# ── 7. 畸形输入 → 优雅错误信封 ──────────────────────────────────
def test_malformed_input_raises_graceful_error():
    """畸形/空输入 → 抛明确错误（不静默返回空文件、不裸崩溃）。"""
    _require_module()
    for bad in ("", "this is not a meshtal file at all", "Mesh Tally Number 4\n garbage"):
        with pytest.raises(Exception) as ei:
            parse_meshtal(bad)
        assert str(ei.value), "错误信息不能为空"
        # 不许是解析器内部裸崩溃类型（应是有意义的自定义/标准错误）
        assert type(ei.value).__name__ not in ("KeyError", "IndexError", "AttributeError"), \
            f"畸形输入触发内部裸崩溃: {type(ei.value).__name__}"
