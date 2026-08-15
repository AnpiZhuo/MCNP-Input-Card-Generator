"""MESHTAL 非 col 布局解析测试 —— out=ij/ik/jk 二维矩阵格式（Bug 2 回归）。

背景（2026-08-15，Bug 2）：用户用官方 case 生成卡（`out=jk`）跑完 MCNP 后，
解析 MESHTAL 报「文件格式不对或版本不兼容」。根因：meshtal_parser 只认默认
`col` 格式（每体素一行），`out=jk` 的二维矩阵布局（每行 = 一个坐标轴上多个
体素）无法解析 → `_parse_tally_block` 全部数据行被跳过 → 抛「未解析到数据行」。

本文件 pin 的回归样本全部为**真实 MCNP6 输出**（tests/fixtures/）：
  - real_meshtal_jk.meshtal  用户真实 out=jk 文件（D:\\MCNP\\new\\claude\\meshtal 原样复制）
  - real_meshtal_ij.meshtal  MCNP6.1 实跑 out=ij
  - real_meshtal_ik.meshtal  MCNP6.1 实跑 out=ik
  - real_meshtal_col.meshtal MCNP6.1 实跑 out=col（同一计数，用于跨格式等价断言）
  - real_meshtal_jk_multi.meshtal MCNP6.1 实跑 out=jk + 2 能量 × 2 时间 bin

全部为 1×2×2 网格（X 1 bin / Y 2 bin / Z 2 bin），与 valid_38 系列同为官方
case1 的 fmesh14:p。矩阵与 col 数据逐体素等价（MCNP 默认随机种子 → 跨 run 可复现）。
"""
from pathlib import Path

import pytest

try:
    from app.meshtal.meshtal_parser import parse_meshtal
    _MISSING = None
except ImportError as _e:  # pragma: no cover - 红基线：功能未实现
    _MISSING = _e


def _require_module():
    assert _MISSING is None, f"app.meshtal.meshtal_parser 模块缺失: {_MISSING}"


FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _fixture(name: str) -> str:
    path = FIXTURES / name
    if not path.is_file():
        raise FileNotFoundError(f"fixture 缺失: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


# ── 公共：单能量单时间 1×2×2 矩阵期望值（jk/ij/ik/col 四格式逐体素等价）──
EXPECTED = {
    "bins_x": [49.0, 51.0],
    "bins_y": [-10.0, 0.0, 10.0],
    "bins_z": [90.0, 100.0, 110.0],
    "bins_energy": [1.0e-3, 1.0e36],
    "bins_time": [],
    # frame[0, i, j, k]：k=z bin、j=y bin、i=x bin（只有 1 个 x bin）
    "frame": {
        (0, 0, 0): 1.48185e-05,   # x=50 y=-5 z=95
        (0, 1, 0): 1.51877e-05,   # x=50 y= 5 z=95
        (0, 0, 1): 1.49623e-05,   # x=50 y=-5 z=105
        (0, 1, 1): 1.24125e-05,   # x=50 y= 5 z=105
    },
    "error": {
        (0, 0, 0): 0.11487,
        (0, 1, 0): 0.11171,
        (0, 0, 1): 0.11346,
        (0, 1, 1): 0.13166,
    },
    "scalar_range": (1.24125e-05, 1.51877e-05),
}


def _assert_common_single_frame(t, exp):
    assert t.number == 14
    assert t.particle == "p"
    assert t.geom == "xyz"
    assert t.bins_x == pytest.approx(exp["bins_x"])
    assert t.bins_y == pytest.approx(exp["bins_y"])
    assert t.bins_z == pytest.approx(exp["bins_z"])
    assert t.bins_energy == pytest.approx(exp["bins_energy"])
    assert t.bins_time == pytest.approx(exp["bins_time"])
    # 单能量单时间 → 恰 1 帧
    assert len(t.data) == 1 and len(t.error) == 1
    (e, tm), frame = next(iter(t.data.items()))
    assert (e, tm) == (0, 0)
    assert frame.shape == (1, 2, 2)
    errframe = t.error[(0, 0)]
    for (i, j, k), val in exp["frame"].items():
        assert frame[i, j, k] == pytest.approx(val, rel=1e-4), f"frame[{i},{j},{k}]"
    for (i, j, k), val in exp["error"].items():
        assert errframe[i, j, k] == pytest.approx(val, rel=1e-4), f"err[{i},{j},{k}]"
    lo, hi = t.scalar_range
    assert lo == pytest.approx(exp["scalar_range"][0], rel=1e-4)
    assert hi == pytest.approx(exp["scalar_range"][1], rel=1e-4)


# ── 1. 用户真实 out=jk 文件（Bug 2 直接回归样本）──────────────────────
def test_real_meshtal_jk_parses():
    """用户真实 out=jk 文件 → 矩阵解析成功，数据与 col 等价。"""
    _require_module()
    mf = parse_meshtal(_fixture("real_meshtal_jk.meshtal"))
    assert mf.code == "mcnp"
    assert mf.histories == pytest.approx(100000.0)
    assert len(mf.tallies) == 1
    t = mf.tallies[0]
    _assert_common_single_frame(t, EXPECTED)


# ── 2. out=ij / out=ik（同结构矩阵，不同固定轴）─────────────────────
def test_real_meshtal_ij_parses():
    """out=ij（Z 固定，X across / Y down）→ 与 col 同数据。"""
    _require_module()
    mf = parse_meshtal(_fixture("real_meshtal_ij.meshtal"))
    assert len(mf.tallies) == 1
    _assert_common_single_frame(mf.tallies[0], EXPECTED)


def test_real_meshtal_ik_parses():
    """out=ik（Y 固定，X across / Z down）→ 与 col 同数据。"""
    _require_module()
    mf = parse_meshtal(_fixture("real_meshtal_ik.meshtal"))
    assert len(mf.tallies) == 1
    _assert_common_single_frame(mf.tallies[0], EXPECTED)


# ── 3. 跨格式等价：col（含单能量 Energy 列）≡ jk 矩阵 ────────────────
def test_col_and_jk_equivalent():
    """同一计数 out=col（Energy 列 + 单能量 bin）与 out=jk 逐体素数据一致。"""
    _require_module()
    mf_col = parse_meshtal(_fixture("real_meshtal_col.meshtal"))
    mf_jk = parse_meshtal(_fixture("real_meshtal_jk.meshtal"))
    t_col, t_jk = mf_col.tallies[0], mf_jk.tallies[0]
    assert len(t_col.data) == 1 and len(t_jk.data) == 1
    assert t_col.data[(0, 0)].shape == t_jk.data[(0, 0)].shape == (1, 2, 2)
    # 两种布局打印精度不同（col 误差 6 位有效数字、矩阵 4 位）→ 用 1e-3 相对容差
    assert t_col.data[(0, 0)] == pytest.approx(t_jk.data[(0, 0)], rel=1e-4)
    assert t_col.error[(0, 0)] == pytest.approx(t_jk.error[(0, 0)], rel=1e-3)
    assert t_col.bins_energy == pytest.approx(t_jk.bins_energy)


# ── 4. 多能量 × 多时间 out=jk：4 帧 + Total 聚合段跳过 ────────────────
def test_real_meshtal_jk_multi_energy_time_frames():
    """2 能量 × 2 时间 out=jk：恰 4 帧；Total Time/Energy Bin 聚合段不重复计数。"""
    _require_module()
    mf = parse_meshtal(_fixture("real_meshtal_jk_multi.meshtal"))
    assert len(mf.tallies) == 1
    t = mf.tallies[0]
    assert t.bins_energy == pytest.approx([0.0, 1.0e-3, 0.5])
    assert t.bins_time == pytest.approx([-1.0e36, 0.0, 2.0])
    assert len(t.data) == 2 * 2 == 4
    assert set(t.data.keys()) == {(0, 0), (0, 1), (1, 0), (1, 1)}
    for (e, tm), frame in t.data.items():
        assert frame.shape == (1, 2, 2)
    # 只有能量 bin 1 × 时间 bin 1 非零（粒子在能量 <0.5MeV 且时间 0-2 shakes）
    f = t.data[(1, 1)]
    assert f[0, 0, 0] == pytest.approx(4.08101e-06, rel=1e-4)   # y=-5 z=95
    assert f[0, 1, 0] == pytest.approx(3.18320e-06, rel=1e-4)   # y= 5 z=95
    assert f[0, 0, 1] == pytest.approx(1.13455e-06, rel=1e-4)   # y=-5 z=105
    assert f[0, 1, 1] == pytest.approx(1.69206e-06, rel=1e-4)   # y= 5 z=105
    for (e, tm) in ((0, 0), (0, 1), (1, 0)):
        assert t.data[(e, tm)].max() == pytest.approx(0.0, abs=1e-30)
    # 相对误差矩阵同步
    e = t.error[(1, 1)]
    assert e[0, 0, 0] == pytest.approx(0.21568, rel=1e-3)
    assert e[0, 1, 0] == pytest.approx(0.24443, rel=1e-3)
    assert e[0, 0, 1] == pytest.approx(0.37764, rel=1e-3)
    assert e[0, 1, 1] == pytest.approx(0.33045, rel=1e-3)
    # scalar_range 含全零帧 → lo=0.0
    lo, hi = t.scalar_range
    assert lo == pytest.approx(0.0, abs=1e-30)
    assert hi == pytest.approx(4.08101e-06, rel=1e-4)
