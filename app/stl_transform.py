"""二进制 STL 的刚体变换与包围盒（纯 numpy/stdlib，不依赖 FreeCAD）。

## 为什么需要它
STEP 方向预览的目标是"**边看边选上轴**"（用户 2026-10-08：给个按钮，点一下先用 STEP 生成
预览，方便做选择）。若每次切换朝向都重跑一次 FreeCAD 子进程（读 STEP + 镶嵌），一次 1–3 s，
体验很差。所以拆成两步：

1. **一次性**：FreeCAD 子进程把 STEP 镶嵌成 STL（原始坐标系，见 `_freecad_step_preview_worker.py`）；
2. **每次切换**：本模块在**主进程**里对那份 STL 施加旋转/平移 —— 纯矩阵运算，毫秒级。

变换用的矩阵来自 `app/cad_orientation.py` 这个单一来源（与真正导入时 FreeCAD 侧施加的
旋转一致；两者等价性由 `tests/unit/test_cad_orientation.py` 的矩阵断言锁住）。

STL 只有三角形与顶点，**法向按变换后的绕向重算**（旋转保绕向，所以法向随之一致）。
"""

from __future__ import annotations

import struct

import numpy as np

_HEADER = b"mcnp-input-card-generator step preview"


def parse_binary_stl(data: bytes) -> np.ndarray:
    """二进制 STL → (N,3,3) 顶点数组（每三角形三顶点）。"""
    n = struct.unpack("<I", data[80:84])[0]
    tris = np.zeros((n, 3, 3), dtype=np.float64)
    off = 84
    for i in range(n):
        tris[i] = np.frombuffer(data[off + 12:off + 48], dtype="<f4").reshape(3, 3)
        off += 50
    return tris


def write_binary_stl(tris: np.ndarray) -> bytes:
    """(N,3,3) 顶点 → 二进制 STL（法向由绕向重算）。"""
    out = bytearray(_HEADER.ljust(80, b"\0")[:80])
    out += struct.pack("<I", int(tris.shape[0]))
    for tri in tris:
        e1 = tri[1] - tri[0]
        e2 = tri[2] - tri[0]
        nrm = np.cross(e1, e2)
        ln = float(np.linalg.norm(nrm))
        nrm = nrm / ln if ln > 1e-12 else np.zeros(3)
        out += struct.pack("<3f", *(float(v) for v in nrm))
        for v in tri:
            out += struct.pack("<3f", *(float(x) for x in v))
        out += b"\0\0"
    return bytes(out)


def bbox_of(tris: np.ndarray):
    """(N,3,3) → ``((xmin,ymin,zmin), (xmax,ymax,zmax))``；空网格返回 None。"""
    if tris.size == 0:
        return None
    lo = tris.reshape(-1, 3).min(axis=0)
    hi = tris.reshape(-1, 3).max(axis=0)
    return (tuple(float(v) for v in lo), tuple(float(v) for v in hi))


def transform(data: bytes, matrix, translate=(0.0, 0.0, 0.0)) -> bytes:
    """对二进制 STL 施加 ``p' = M @ p + t``（M 为 3×3，整数旋转矩阵即可）。"""
    tris = parse_binary_stl(data)
    if tris.size == 0:
        return write_binary_stl(tris)
    m = np.asarray(matrix, dtype=np.float64).reshape(3, 3)
    t = np.asarray(translate, dtype=np.float64).reshape(3)
    moved = tris.reshape(-1, 3) @ m.T + t
    return write_binary_stl(moved.reshape(-1, 3, 3))


__all__ = ["parse_binary_stl", "write_binary_stl", "bbox_of", "transform"]
