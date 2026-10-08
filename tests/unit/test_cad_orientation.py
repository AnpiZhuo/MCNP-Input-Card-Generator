"""CAD ↔ MCNP 上轴/方位约定单元测试（纯 stdlib，不 import FreeCAD/GEOUNED）。

锁住 2026-10-08 用户实测那条：**STEP 文件没有"上轴"字段**，差别来自源软件的默认坐标系；
本程序（与 MCNP）Z 朝上、SolidWorks/Inventor 类 Y 朝上 ⇒ 导入导出都必须按显式约定旋转，
且两者**互为逆**（否则往返一趟翻 90°）。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "app"))

from app.cad_orientation import (  # noqa: E402
    describe, freecad_steps, is_identity, matrix_cad_to_mcnp, matrix_mcnp_to_cad, parse,
    parse_origin, translation_for, translation_for_spec,
)

IDENT = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
ALL_SPECS = [{"up": up, "azimuthDeg": az} for up in ("Z", "Y") for az in (0, 90, 180, 270)]


def _apply(m, v):
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))


def _det(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def test_default_is_identity():
    """默认/空/字符串/非法值 ⇒ 不旋转（= 与旧行为逐字节一致）。"""
    for spec in (None, {}, "Z", "z", {"up": "X"}, {"up": "Y", "azimuthDeg": 45}, 123):
        p = parse(spec)
        assert p["up"] in ("Z", "Y") and p["azimuthDeg"] == 0, (spec, p)
        assert p["origin"] == "keep", (spec, p)
    assert is_identity(None) and is_identity({}) and is_identity({"up": "Z"})
    assert matrix_cad_to_mcnp(None) == IDENT
    assert not is_identity({"up": "Y"})
    assert parse("y") == {"up": "Y", "azimuthDeg": 0, "origin": "keep"}
    assert parse({"up": "y", "azimuthDeg": "90"}) == {"up": "Y", "azimuthDeg": 90, "origin": "keep"}
    # 360/720 归一化回 0；非 90 倍数退回默认
    assert parse({"azimuthDeg": 360})["azimuthDeg"] == 0
    assert parse({"azimuthDeg": 45})["azimuthDeg"] == 0


def test_y_up_maps_cad_up_to_mcnp_z():
    """up=Y 的那一步：CAD 的 +Y（上）→ MCNP 的 +Z（上）；CAD 的 +Z → MCNP 的 −Y。"""
    m = matrix_cad_to_mcnp({"up": "Y"})
    assert _apply(m, (0, 1, 0)) == (0, 0, 1)
    assert _apply(m, (0, 0, 1)) == (0, -1, 0)
    assert _apply(m, (1, 0, 0)) == (1, 0, 0)


def test_azimuth_keeps_the_up_axis():
    """绕上轴转方位角**不该动上轴**（这正是"上轴 + 方位角"这种参数化好用的原因）。"""
    for az in (0, 90, 180, 270):
        m = matrix_cad_to_mcnp({"up": "Y", "azimuthDeg": az})
        assert _apply(m, (0, 1, 0)) == (0, 0, 1), az
        mz = matrix_cad_to_mcnp({"up": "Z", "azimuthDeg": az})
        assert _apply(mz, (0, 0, 1)) == (0, 0, 1), az


def test_round_trip_is_identity_for_all_orientations():
    """导出（mncp2cad）与导入（cad2mcnp）必须互为逆 —— 否则往返一趟翻 90°。"""
    for spec in ALL_SPECS:
        fwd = matrix_cad_to_mcnp(spec)
        inv = matrix_mcnp_to_cad(spec)
        prod = tuple(tuple(sum(inv[i][k] * fwd[k][j] for k in range(3)) for j in range(3))
                     for i in range(3))
        assert prod == IDENT, spec


def test_no_mirroring():
    """全是**旋转**（行列式 +1），没有反射 —— 反射会把手性搞反，那是另一件事。"""
    for spec in ALL_SPECS:
        assert _det(matrix_cad_to_mcnp(spec)) == 1, spec
        assert _det(matrix_mcnp_to_cad(spec)) == 1, spec


def test_freecad_steps_order_and_signs():
    """FreeCAD 侧逐步旋转与矩阵推导一一对应（导入 +90 绕 X；导出反向且顺序相反）。"""
    assert freecad_steps({"up": "Z"}, "cad2mcnp") == []
    assert freecad_steps({"up": "Y"}, "cad2mcnp") == [((1.0, 0.0, 0.0), 90.0)]
    assert freecad_steps({"up": "Y", "azimuthDeg": 90}, "cad2mcnp") == [
        ((1.0, 0.0, 0.0), 90.0), ((0.0, 0.0, 1.0), 90.0)]
    assert freecad_steps({"up": "Y", "azimuthDeg": 90}, "mcnp2cad") == [
        ((0.0, 0.0, 1.0), -90.0), ((1.0, 0.0, 0.0), -90.0)]
    with pytest.raises(ValueError):
        freecad_steps({}, "sideways")


def test_describe_says_what_happened():
    """结果提示里必须能看出"按哪种约定转过"（否则拿到一份 deck 无从判断）。"""
    assert "未旋转" in describe(None, "cad2mcnp")
    txt = describe({"up": "Y", "azimuthDeg": 90}, "cad2mcnp")
    assert "导入" in txt and "Y 朝上" in txt and "90" in txt
    assert "导出" in describe({"up": "Y"}, "mcnp2cad")


# ─────────────── 原点口径（用户 2026-10-08：体心 / 坐在底面 / 按原本建模） ───────────────

def test_origin_parse_defaults_to_keep():
    """缺省/非法 ⇒ keep（不平移）—— 不静默挪动用户的几何。"""
    assert parse(None)["origin"] == "keep"
    assert parse({"up": "Y"})["origin"] == "keep"
    assert parse({"origin": "CENTER"})["origin"] == "center"
    assert parse_origin({"origin": "bogus"}) == "keep"
    assert parse_origin("bottom") == "bottom"


def test_origin_translations():
    """体心 / 底面两种口径的平移量（底面跟随**目标坐标系**的上轴）。"""
    bbox = ((10.0, 30.0, 50.0), (20.0, 40.0, 60.0))
    assert translation_for(bbox, "keep") == (0.0, 0.0, 0.0)
    assert translation_for(bbox, "center") == (-15.0, -35.0, -55.0)
    # Z 朝上的目标（导入到 MCNP / Z 朝上的 CAD）：坐在 z=0
    assert translation_for(bbox, "bottom", "Z") == (-15.0, -35.0, -50.0)
    # Y 朝上的目标 CAD：坐在 y=0
    assert translation_for(bbox, "bottom", "Y") == (-15.0, -30.0, -55.0)
    # 没有竖直方向的"底"可坐时不会瞎动（退化包围盒）
    flat = ((1.0, 2.0, 3.0), (1.0, 2.0, 3.0))
    assert translation_for(flat, "center") == (-1.0, -2.0, -3.0)
    assert translation_for(flat, "bottom", "Z") == (-1.0, -2.0, -3.0)


def test_origin_applied_via_spec_uses_target_up_axis():
    """`translation_for_spec` 用**目标**上轴：导出到 Y 朝上 CAD 时"底面"是 y=0。"""
    bbox = ((10.0, 30.0, 50.0), (20.0, 40.0, 60.0))
    assert translation_for_spec(bbox, {"up": "Z", "origin": "bottom"}) == (-15.0, -35.0, -50.0)
    assert translation_for_spec(bbox, {"up": "Y", "origin": "bottom"}) == (-15.0, -30.0, -55.0)
    assert translation_for_spec(bbox, {"up": "Y", "origin": "keep"}) == (0.0, 0.0, 0.0)
