"""§6.3 bound 位移参数修正 —— 从真实大尺寸 fixture 解析曲面 dict，断言 bound 落契约区间。

铁律：不 import gui.backend.api_server（其模块级 pyvista/FreeCAD 探测污染纯引擎测试）；
不 import FreeCAD。freecad_preview.py 顶层仅 stdlib，pymcnp 延迟导入。

解析逻辑镜像 api_server.parse_surfaces（TR 引用提取 + 曲面号/关键词索引检测 +
from_mcnp），仅用 pymcnp 构建表面对象，再经 _pymcnp_surf_to_dict 转 dict——
测试走的是与生产完全相同的曲面序列化管线。
"""
import re
from pathlib import Path

import pymcnp.inp as _pi

from app.freecad_preview import _compute_bound_from_surfaces, _pymcnp_surf_to_dict, model_extent_unpadded

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

# 镜像 api_server 的 _SURF_CLASSES（pymcnp.inp 中带 _KEYWORD/from_mcnp 的表面类）
_SURF_CLASSES = {}
for _name in dir(_pi):
    _obj = getattr(_pi, _name)
    if hasattr(_obj, "_KEYWORD") and hasattr(_obj, "from_mcnp") and isinstance(_obj, type):
        _kw = (_obj._KEYWORD or "").upper()
        if _kw:
            _SURF_CLASSES[_kw] = _obj


def _parse_fixture_surfaces(name: str) -> list:
    """读取 fixture，把曲面卡解析为 surf dict（_pymcnp_surf_to_dict 输出格式）。"""
    text = (FIXTURES / name).read_text(encoding="utf-8")
    surfs = []
    for _line in text.strip().splitlines():
        _l = _line.strip()
        if not _l or _l.startswith("C") or _l.startswith("c"):
            continue
        _l = _l.split("$")[0].strip()  # 行内注释
        if not _l:
            continue
        m_tr = re.search(r"\s*\*\s*TR\s*(\d+)\s*$", _l, re.IGNORECASE)
        if m_tr:
            _l = _l[:m_tr.start()].rstrip()
        else:
            m_star = re.match(r"^(\d+)\s*\*\s*", _l)
            if m_star:
                _l = _l[m_star.end():].lstrip()
        _p = _l.split()
        if len(_p) < 2:
            continue
        _kw_idx = 1
        if len(_p) > 2 and _SURF_CLASSES.get(_p[2].upper()):
            _kw_idx = 2
        _cls = _SURF_CLASSES.get(_p[_kw_idx].upper())
        if _cls is None:
            continue
        try:
            surfs.append(_cls.from_mcnp(_l))
        except Exception:
            continue  # 与生产 parse_surfaces 一致：非曲面行静默跳过
    return [_pymcnp_surf_to_dict(s) for s in surfs]


def _fixture_bound(name: str) -> float:
    return _compute_bound_from_surfaces(_parse_fixture_surfaces(name))


# ── 契约区间断言（§6.3 验收表）──────────────────────────────
def test_shield_20m_bound():
    """shield_20m：RCC h=(0,0,4000) 是轴长非坐标 → bound ≈2700（旧实现 5300）。"""
    b = _fixture_bound("preview_shield_20m.inp")
    assert 2600 <= b <= 2800, f"shield_20m bound={b:.2f} 应≈2700（旧实现 5300）"


def test_stress_bunker_bound():
    """stress_bunker：外盒 ±1500 → bound ≈2050。"""
    b = _fixture_bound("preview_stress_bunker.inp")
    assert 2000 <= b <= 2100, f"stress_bunker bound={b:.2f} 应≈2050"


def test_inp01_bound():
    """inp01：pz 0..10000 → bound ≈13100。"""
    b = _fixture_bound("preview_inp01_m100.inp")
    assert abs(b - 13100) / 13100 <= 0.05, f"inp01 bound={b:.2f} 应≈13100"


def test_inp09_bound():
    """inp09：±2742 → bound ≈3665。"""
    b = _fixture_bound("preview_inp09_m27.inp")
    assert abs(b - 3665) / 3665 <= 0.05, f"inp09 bound={b:.2f} 应≈3665"


# ── 根因定点（§6.3）────────────────────────────────────────
def test_rcc_axis_length_not_treated_as_coord():
    """shield_20m 的 1009 rcc：h=(0,0,4000) 是轴长，只取端点 v+h=(0,0,2000)。"""
    dicts = [
        {"type": "RCC", "number": 1009,
         "params": [0, 0, -2000, 0, 0, 4000, 180], "transform": None},
        {"type": "PZ", "number": 6, "params": [2000], "transform": None},
    ]
    b = _compute_bound_from_surfaces(dicts)
    assert abs(b - 2700) < 1e-9, f"RCC 轴长不应当坐标，bound={b:.2f} 应=2700"


def test_macrobody_corner_composition_not_direction_only():
    """WED 方向向量 v3=(0,0,4000) 是轴长：与基点合成端点 v+v3=(0,0,2000)。

    旧实现把 4000 当坐标 → bound=5300；修正后 max=2000 → bound=2700。
    """
    dicts = [
        {"type": "WED", "number": 3,
         "params": [0, 0, -2000, 1000, 0, 0, 0, 1000, 0, 0, 0, 4000],
         "transform": None},
    ]
    b = _compute_bound_from_surfaces(dicts)
    assert abs(b - 2700) < 1e-9, f"WED 轴长不应当坐标，bound={b:.2f} 应=2700"


def test_box_far_corner_composition():
    """BOX：方向向量与基点合成对角最远角点 v+a1+a2+a3，不单独取模。"""
    dicts = [
        {"type": "BOX", "number": 3,
         "params": [0, 0, 0, 100, 0, 0, 0, 100, 0, 0, 0, 100], "transform": None},
        {"type": "PZ", "number": 9, "params": [1000], "transform": None},
    ]
    b = _compute_bound_from_surfaces(dicts)
    # 对角角点 (100,100,100) 不参与 max，max=1000（PZ）→ 1000*1.3+100 = 1400
    assert abs(b - 1400) < 1e-9, f"BOX 方向向量不单独撑 bound，bound={b:.2f} 应=1400"


# ── GQ/SQ 跳过（§6.3 验收）─────────────────────────────────
def test_gq_sq_skipped_do_not_inflate_bound():
    """GQ/SQ 二次型系数（含大常数项）不是坐标，必须跳过，不撑 bound。"""
    dicts = _parse_fixture_surfaces("preview_inp01_m100.inp")
    assert dicts, "inp01 应解析出曲面"
    dicts.append({"type": "GQ", "number": 999, "params": [1e6] * 10, "transform": None})
    dicts.append({"type": "SQ", "number": 998, "params": [1e6] * 10, "transform": None})
    b = _compute_bound_from_surfaces(dicts)
    assert abs(b - 13100) / 13100 <= 0.05, f"GQ/SQ 系数不应当撑大 bound，bound={b:.2f}"


# ── A1.2 匹配检测用模型范围（无 padding）────────────────────
def test_model_extent_unpadded_real_geometry_range():
    """model_extent_unpadded：真实范围 max-abs，无 *1.3+100 / 500 兜底（A1.2 绝不静默错位）。"""
    dicts = [
        {"type": "RPP", "number": 1, "params": [-1, 1, -1, 1, 0, 1], "transform": None},
    ]
    e = model_extent_unpadded(dicts)
    assert abs(e - 1.0) < 1e-9, f"RPP 小板范围应=1（旧 bound 兜底会到 500），得到 {e}"


def test_model_extent_unpadded_skips_gq_sq_and_empty():
    """GQ/SQ 系数跳过；空输入 → 0.0。"""
    dicts = [
        {"type": "RPP", "number": 1, "params": [-1, 1, -1, 1, 0, 1], "transform": None},
        {"type": "GQ", "number": 999, "params": [1e6] * 10, "transform": None},
        {"type": "SQ", "number": 998, "params": [1e6] * 10, "transform": None},
    ]
    assert abs(model_extent_unpadded(dicts) - 1.0) < 1e-9
    assert model_extent_unpadded([]) == 0.0
