"""体积数据构建测试 —— app/meshtal/volume_builder.py（契约 meshtal-visualization.md §4.2 / §8 KPI）。

现状（2026-08-14，功能未实现 → 红基线）：`app/meshtal/volume_builder.py` 不存在 → ImportError → 全部红。

红基线 pin（按契约 §4.2 / §9.1）：
  1. 稀疏索引→稠密切片：(e,t) 切片构建 Frame；native 更小保 native、avg_factor=1、downsampled=False —— RED
  2. world_box 来自 meshtal bin 边界（降采样不改世界坐标）—— RED
  3. energy/time 切片语义：不同 bin 取不同帧；越界 bin → 明确错误 —— RED
  4. box-average 均值降采样正确性（已知值断言块均值，如 4→2 块均值 0.5/2.5）—— RED
  5. 归一化在降采样之后做（scalar_range 反映降采样后数组范围）—— RED
  6. 标量帧 dtype=uint8、值域 [0,255] —— RED

纪律：只 import app/meshtal 纯模块 + numpy（已就位），不 import gui.backend.api_server / FreeCAD。
"""
from __future__ import annotations  # 模块缺失时函数注解不求值（红基线守卫先行）

import numpy as np
import pytest

try:
    from app.meshtal.downsample_plan import GPU_BUDGET_BYTES
    from app.meshtal.meshtal_parser import MeshTally, MeshtalFile, parse_meshtal
    from app.meshtal.volume_builder import Frame, build_frame
    _MISSING = None
except ImportError as _e:  # pragma: no cover - 红基线：功能未实现
    _MISSING = _e


def _require_module():
    """模块缺失守卫：app/meshtal 任一模块缺失 → 本用例红（pin 缺口，非崩溃断言）。"""
    assert _MISSING is None, f"app/meshtal 模块缺失（红基线，功能未实现）: {_MISSING}"


def _fixture(name: str) -> str:
    """读取 tests/fixtures/<name>（vendored meshtal 样例）。"""
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent / "fixtures" / name
    if not path.is_file():
        raise FileNotFoundError(f"fixture 缺失: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def _mesh_tally(data: np.ndarray, bins, number=1) -> MeshTally:
    """按契约 §2.2 构造 MeshTally。data 键 (e,t)→稠密数组 (ni,nj,nk)。"""
    return MeshTally(
        number=number, particle="n", geom="xyz",
        bins_x=bins["x"], bins_y=bins["y"], bins_z=bins["z"],
        bins_energy=bins.get("energy", [0.0, 1e36]),
        bins_time=bins.get("time", []),
        data={(0, 0): data},
        error={(0, 0): np.zeros_like(data)},
        scalar_range=(float(data.min()), float(data.max())),
    )


def _file(*tallies, histories=1e7) -> MeshtalFile:
    return MeshtalFile(
        path="/tmp/fake.meshtal", mtime=0, code="mcnp",
        histories=histories, tallies=list(tallies), warnings=[],
    )


# ── 1. native 保 native + 标量帧类型 ────────────────────────────
def test_build_frame_native_preserved_uint8():
    """minimal 2×2×2 网格 + 目标 128 → 保 native，avg_factor=(1,1,1)，downsampled=False。"""
    _require_module()
    data = np.arange(8, dtype=np.float64).reshape(2, 2, 2)
    mf = _file(_mesh_tally(data, {"x": [0, 1, 2], "y": [0, 1, 2], "z": [0, 0.5, 1.0]}))
    frame = build_frame(mf, tally_number=1, energy_bin=0, time_bin=0,
                        resolution=128, budget_bytes=GPU_BUDGET_BYTES)
    assert isinstance(frame, Frame)
    assert tuple(frame.resolution) == (2, 2, 2)
    assert frame.scalar.dtype == np.uint8
    assert frame.scalar.shape == (2, 2, 2)
    assert tuple(frame.avg_factor) == (1, 1, 1)
    assert frame.downsampled is False
    assert frame.scalar.min() >= 0 and frame.scalar.max() <= 255


# ── 2. world_box 来自 bin 边界 ──────────────────────────────────
def test_build_frame_world_box_from_bin_edges():
    """world_box 永远来自 meshtal bin 边界（契约 §3.3：降采样不改世界坐标）。"""
    _require_module()
    data = np.zeros((2, 2, 2))
    mf = _file(_mesh_tally(data, {"x": [0, 1, 2], "y": [0, 1, 2], "z": [0, 0.5, 1.0]}))
    frame = build_frame(mf, tally_number=1, energy_bin=0, time_bin=0,
                        resolution=128, budget_bytes=GPU_BUDGET_BYTES)
    assert frame.world_box == {
        "min": [0.0, 0.0, 0.0],
        "max": [2.0, 2.0, 1.0],
    }


def test_build_frame_world_box_valid38():
    """valid_38 网格 world_box == 契约 §3.2 grid_bounds 示例值。"""
    _require_module()
    mf = parse_meshtal(_fixture("valid_38.meshtal"))
    frame = build_frame(mf, tally_number=4, energy_bin=0, time_bin=0,
                        resolution=128, budget_bytes=GPU_BUDGET_BYTES)
    assert frame.world_box == {
        "min": [-100.0, -100.0, -150.0],
        "max": [100.0, 100.0, -50.0],
    }


# ── 3. energy/time 切片语义 ─────────────────────────────────────
def test_build_frame_energy_time_slices_differ():
    """valid_40（2 能量 × 2 时间）：不同 (e,t) 帧取不同标量。"""
    _require_module()
    mf = parse_meshtal(_fixture("valid_40.meshtal"))
    f00 = build_frame(mf, tally_number=4, energy_bin=0, time_bin=0,
                      resolution=128, budget_bytes=GPU_BUDGET_BYTES)
    f11 = build_frame(mf, tally_number=4, energy_bin=1, time_bin=1,
                      resolution=128, budget_bytes=GPU_BUDGET_BYTES)
    assert tuple(f00.resolution) == (4, 4, 4)
    assert tuple(f11.resolution) == (4, 4, 4)
    # 至少一个体素不同（两帧数据不同）
    assert not np.array_equal(f00.scalar, f11.scalar), "不同 (e,t) 帧不应产出相同标量"


def test_build_frame_invalid_bin_raises():
    """tallyNumber 不存在 / energyBin / timeBin 越界 → 明确错误（契约 §3.3 guard 语义）。"""
    _require_module()
    data = np.zeros((2, 2, 2))
    mf = _file(_mesh_tally(data, {"x": [0, 1, 2], "y": [0, 1, 2], "z": [0, 0.5, 1.0]}))
    with pytest.raises((KeyError, IndexError, ValueError)):
        build_frame(mf, tally_number=99, energy_bin=0, time_bin=0,
                    resolution=128, budget_bytes=GPU_BUDGET_BYTES)
    with pytest.raises((IndexError, ValueError)):
        build_frame(mf, tally_number=1, energy_bin=5, time_bin=0,
                    resolution=128, budget_bytes=GPU_BUDGET_BYTES)


# ── 4. box-average 均值降采样正确性（已知值）────────────────────
def test_box_average_known_block_means():
    """4×4×4 网格（值=x 索引）降采样到 2×2×2：块均值 0.5（x∈{0,1}）/ 2.5（x∈{2,3}）。

    归一化后 min→0、max→255，精确断言块均值（0.5→0、2.5→255）。
    """
    _require_module()
    arr = np.zeros((4, 4, 4))
    for i in range(4):
        arr[i, :, :] = float(i)
    mf = _file(_mesh_tally(arr, {"x": [0, 1, 2, 3, 4], "y": [0, 1, 2, 3, 4],
                                 "z": [0, 1, 2, 3, 4]}))
    frame = build_frame(mf, tally_number=1, energy_bin=0, time_bin=0,
                        resolution=2, budget_bytes=GPU_BUDGET_BYTES)
    assert tuple(frame.resolution) == (2, 2, 2)
    assert tuple(frame.avg_factor) == (2, 2, 2)
    assert frame.downsampled is True
    # 归一化在降采样之后做：scalar_range 反映降采样后数组范围 (0.5, 2.5)
    lo, hi = frame.scalar_range
    assert lo == pytest.approx(0.5, abs=1e-6)
    assert hi == pytest.approx(2.5, abs=1e-6)
    # 块均值精确：x∈{0,1} 块均值 0.5 = min → 0；x∈{2,3} 块均值 2.5 = max → 255
    assert int(frame.scalar[0, 0, 0]) == 0
    assert int(frame.scalar[1, 0, 0]) == 255
    assert frame.scalar.shape == (2, 2, 2)


# ── 5. 归一化顺序（降采样后）───────────────────────────────────
def test_normalization_applied_after_downsample():
    """若先归一化再求均值会失真（(0+255)/2=127.5），本契约要求先降采样再归一化。"""
    _require_module()
    # 输入块均值 0.5/2.5 → 归一化后端点 0/255；若先归一化则块均值 (0+255)/2=127.5 ≠ 0/255
    arr = np.zeros((4, 4, 4))
    for i in range(4):
        arr[i, :, :] = float(i)
    mf = _file(_mesh_tally(arr, {"x": [0, 1, 2, 3, 4], "y": [0, 1, 2, 3, 4],
                                 "z": [0, 1, 2, 3, 4]}))
    frame = build_frame(mf, tally_number=1, energy_bin=0, time_bin=0,
                        resolution=2, budget_bytes=GPU_BUDGET_BYTES)
    assert int(frame.scalar[0, 0, 0]) != 127, "先归一化后均值会得到 127.5，本契约应为 0"
