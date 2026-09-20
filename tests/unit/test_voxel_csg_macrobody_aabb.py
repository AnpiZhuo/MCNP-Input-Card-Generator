# -*- coding: utf-8 -*-
"""C810 宏体紧盒（`voxel_csg.surface_aabb` / `cell_aabb`）—— CEL 拒绝采样的前提。

## 为什么单独立这一条
`source_sampler.sample_cell` 在栅元紧盒内做拒绝采样；紧盒缺失时 `cell_aabb` 返回 None，
调用方退回 **±1e3 大盒**（体积 8e9）⇒ 接受率 ~1e-8 ⇒ `SDEF CEL=n` **必然**报
「拒绝采样失败」。2026-09-20 实测：SPH/RPP 有盒，其余 8 类宏体全是 None。

## C810 依据（CCC-810 印刷页）
- **p.3-21**「The following geometry bodies are available」= **BOX / RPP / SPH / RCC /
  RHP(HEX) / REC / TRC / ELL / WED / ARB**（10 类）；各类卡项定义紧随其后。
- **p.3-20/3-21 手册示例**：本文件的参数直接取手册示例（BOX/RCC/RHP/REC/TRC/ELL/WED）。
- **p.3-22**「BOX and RPP can be infinite in a dimension, in which case those two facets are
  skipped… RHP can be infinite in the axial dimension」。

## 断言口径（不接受"没报错就算过"）
期望紧盒**不调用被测公式**，而是按几何定义在用例里独立写出：
  1. `cell_aabb(["unary",["surf",1],"neg"])` 非 None 且**三轴有界**；
  2. 紧盒各轴边界 == 用例独立算出的期望值（容差 1e-9 相对）；
  3. `cell_volume`（用同一紧盒做 MC）与解析体积相对误差 ≤ 15%；
  4. 紧盒体积 / 解析体积 ≤ 5（**紧**是拒绝采样效率的前提，不是可选修饰）。
"""
import math

import pytest

import app.voxel_csg as vc

PI = math.pi
SQRT3 = math.sqrt(3.0)

# 名称、类型、卡项、解析体积、独立算出的期望紧盒（lo, hi）、已知在体内的点
CASES = [
    ("SPH 球", "SPH", [0, 0, 0, 5],
     4 / 3 * PI * 125, ((-5, -5, -5), (5, 5, 5)), [(0, 0, 0), (3, 0, 0)]),

    ("RPP 长方体", "RPP", [-1, 1, -1, 1, -1, 1],
     8.0, ((-1, -1, -1), (1, 1, 1)), [(0, 0, 0), (0.9, -0.9, 0.5)]),

    # C810 示例：a cube centered at the origin, 2 cm on a side
    ("BOX 正交盒", "BOX", [-1, -1, -1, 2, 0, 0, 0, 2, 0, 0, 0, 2],
     8.0, ((-1, -1, -1), (1, 1, 1)), [(0, 0, 0), (0.9, 0.9, 0.9)]),

    # C810 示例：a 10-cm high can about the y-axis, base y=-5, R=4
    ("RCC 正圆柱", "RCC", [0, -5, 0, 0, 10, 0, 4],
     PI * 16 * 10, ((-4, -5, -4), (4, 5, 4)), [(0, 0, 0), (3.9, 4.5, 0)]),

    # C810 例题卡（`RHP 0 0 -4  0 0 8  0 2 0`），但期望值按**现行 surface_fn 的口径**算：
    # 它把 r 当**顶点矢量**（不是 C810 说的 facet 中心），故顶点半径 = |r| = 2、
    # 六边形边心距 = 2·cos30° = √3 ⇒ x = ±2·cos30° = ±√3、y = ±2、z = ±4。
    # 「r 该是边心距」这条 C810 偏差另案留档（见文件末 xfail 用例），本批不偷偷改。
    ("RHP 六棱柱", "RHP", [0, 0, -4, 0, 0, 8, 0, 2, 0],
     (3 * SQRT3 / 2) * 4 * 8,
     ((-SQRT3, -2, -4), (SQRT3, 2, 4)), [(0, 0, 0), (0, 0, 3.5)]),

    # C810 示例（10 项式）：major radius 4 in x, minor radius 2 in z（方向 = H×V1）
    ("REC 椭圆柱", "REC", [0, -5, 0, 0, 10, 0, 4, 0, 0, 2],
     PI * 4 * 2 * 10, ((-4, -5, -2), (4, 5, 2)), [(0, 0, 0), (3.9, 0, 0)]),

    # C810 示例：x 轴、高 10、R1=4（x=-5）、R2=2（x=5）
    ("TRC 截锥", "TRC", [-5, 0, 0, 10, 0, 0, 4, 2],
     PI * 10 / 3 * (16 + 8 + 4), ((-5, -4, -4), (5, 4, 4)), [(-4, 0, 0), (4, 1, 1)]),

    # C810 示例 `ELL 0 0 -2  0 0 2  6`：Rm>0 ⇒ V1/V2 是**焦点**、Rm 是**长轴长**
    # ⇒ a=3（沿 z）、c=2 ⇒ b=√(a²−c²)=√5（沿 x/y）
    ("ELL 椭球 Rm>0", "ELL", [0, 0, -2, 0, 0, 2, 6],
     4 / 3 * PI * 3 * 5, ((-math.sqrt(5), -math.sqrt(5), -3), (math.sqrt(5), math.sqrt(5), 3)),
     [(0, 0, 0), (0, 0, 2.9)]),

    # C810 示例 `ELL 0 0 0  0 0 3  -2`：Rm<0 ⇒ V1 是中心、V2 是长轴矢量（长=长半径）、
    # |Rm| 是短半径 ⇒ a=3（z）、b=2（x/y）
    ("ELL 椭球 Rm<0", "ELL", [0, 0, 0, 0, 0, 3, -2],
     4 / 3 * PI * 3 * 4, ((-2, -2, -3), (2, 2, 3)), [(0, 0, 0), (0, 0, 2.9)]),

    # C810 示例：vertex (0,0,-6)，底三角形 4×3，高 12 ⇒ 体积 = ½·4·3·12
    ("WED 楔", "WED", [0, 0, -6, 4, 0, 0, 0, 3, 0, 0, 0, 12],
     0.5 * 4 * 3 * 12, ((0, 0, -6), (4, 3, 6)), [(0.5, 0.5, -5), (1, 1, 0)]),

    # ARB：8 个角点（单位立方）+ 6 个四位面号（1-2-3-4 / 5-6-7-8 / 1-2-6-5 / …）
    ("ARB 立方", "ARB",
     [0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1,
      1234, 5678, 1265, 2376, 3487, 4158],
     1.0, ((0, 0, 0), (1, 1, 1)), [(0.5, 0.5, 0.5), (0.1, 0.9, 0.9)]),
]


def _geom(t: str, p: list):
    return {1: {"type": t, "params": [float(v) for v in p]}}


@pytest.mark.parametrize("name,typ,params,vol,expect,_pts",
                         CASES, ids=[c[0] for c in CASES])
def test_macrobody_negative_aabb_is_tight_and_bounded(name, typ, params, vol, expect, _pts):
    """栅元 `-1`（宏体内部）必须有**三轴有界**的紧盒，且与独立算出的期望一致。"""
    box = vc.cell_aabb(["unary", ["surf", 1], "neg"], _geom(typ, params), 1e6)
    assert box is not None, f"{name}: cell_aabb 返回 None（⇒ 源抽样退回 ±1e3 大盒，必失败）"
    lo, hi, axes = box
    assert all(axes), f"{name}: 期望三轴有界，实得 axes={axes}"

    elo, ehi = expect
    for i in range(3):
        assert lo[i] == pytest.approx(elo[i], rel=1e-9, abs=1e-9), f"{name}: lo[{i}]={lo[i]} 期望 {elo[i]}"
        assert hi[i] == pytest.approx(ehi[i], rel=1e-9, abs=1e-9), f"{name}: hi[{i}]={hi[i]} 期望 {ehi[i]}"


@pytest.mark.parametrize("name,typ,params,vol,expect,pts",
                         CASES, ids=[c[0] for c in CASES])
def test_macrobody_volume_matches_analytic(name, typ, params, vol, expect, pts):
    """MC 体积（用同一紧盒）与解析体积一致；且紧盒足够紧（体积比 ≤ 5）。

    `cell_volume` 走分层 MC（固定 seed 12345）⇒ 本断言是确定性的。
    """
    g = _geom(typ, params)
    box = vc.cell_aabb(["unary", ["surf", 1], "neg"], g, 1e6)
    assert box is not None, name
    lo, hi, _axes = box
    fns = {1: vc.surface_fn(typ, params)}
    ast = ["unary", ["surf", 1], "neg"]
    got = vc.cell_volume(ast, fns, 1e6, aabb=box)
    assert got is not None and got > 0, f"{name}: 体积估计 = {got}"
    assert got == pytest.approx(vol, rel=0.15), f"{name}: MC 体积 {got:.4g} vs 解析 {vol:.4g}"

    box_vol = (hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2])
    assert box_vol / vol <= 5.0, f"{name}: 紧盒/体积 = {box_vol / vol:.2f}（>5 说明盒太松，拒绝采样效率会塌）"


@pytest.mark.parametrize("name,typ,params,vol,expect,pts",
                         CASES, ids=[c[0] for c in CASES])
def test_known_inside_points_are_inside_and_in_box(name, typ, params, vol, expect, pts):
    """已知在体内的点：场判在内，且落在紧盒里（场与盒必须自洽）。"""
    import numpy as np
    f = vc.surface_fn(typ, params)
    box = vc.cell_aabb(["unary", ["surf", 1], "neg"], _geom(typ, params), 1e6)
    lo, hi, _ = box
    for p in pts:
        # C810：宏体内部对其"master"曲面为**负侧** ⇒ 场 f<0 视为在内
        fv = float(np.asarray(f(np.asarray([p[0]]), np.asarray([p[1]]), np.asarray([p[2]]))).ravel()[0])
        assert fv < 0, f"{name}: 点 {p} 场值 {fv} ≥ 0（不在体内？）"
        for i in range(3):
            assert lo[i] - 1e-9 <= p[i] <= hi[i] + 1e-9, f"{name}: 点 {p} 落在紧盒外"


def test_bare_positive_side_of_macrobody_stays_unbounded():
    """**反向**不许松：宏体的**正侧**（外面）无界 —— 必须仍返回 None。

    先例（`test_bare_positive_surface_aabb_is_unbounded`）：裸球正侧若返回球自身 AABB，
    壳/外部栅元会被裁到球内 ⇒ 实测 288k 三角形。
    """
    for typ, params in [("BOX", [-1, -1, -1, 2, 0, 0, 0, 2, 0, 0, 0, 2]),
                        ("RCC", [0, -5, 0, 0, 10, 0, 4]),
                        ("SPH", [0, 0, 0, 5]),
                        ("RPP", [-1, 1, -1, 1, -1, 1])]:
        assert vc.cell_aabb(["surf", 1], _geom(typ, params), 1e6) is None, typ
        assert vc._surface_positive_aabb(typ, [float(v) for v in params]) is None, typ


def test_box_infinite_dimension_is_unbounded_on_that_axis():
    """C810 p.3-22：BOX 可某维无限（那一维的边向量为 0 ⇒ 该维 facet 被跳过）。

    此时紧盒必须把**那一轴**标成无界（axes[i]=False），而不是假装有界。
    """
    # 三条边向量都不含 x 分量 ⇒ 立方体在 x 方向不限 ⇒ 该维 facet 被跳过（C810 p.3-22）
    box = vc.surface_aabb("BOX", [-1, -1, -1, 0, 2, 0, 0, 0, 2, 0, 0, 0])
    assert box is not None
    lo, hi, axes = box
    assert axes == (False, True, True), f"实得 {axes}（x 应无界）"
    assert lo[1] == pytest.approx(-1) and hi[2] == pytest.approx(1)


@pytest.mark.xfail(
    reason="C810 p.3-21：r = 「vector from the axis to the middle of the first facet」（边心距）；"
           "现行 surface_fn 把 r 当**顶点矢量**（base = v±r1±r2±r3）⇒ 同一张卡的边心距只有 "
           "|r|·cos30° = √3 而不是 2，六边形整体小 1/cos30°。修它会改变所有六棱柱卡的尺寸，"
           "波及 UI「六棱柱快捷卡」与 hex 格阵预览 ⇒ 须产品裁决，本批只留档不改。",
    strict=False)
def test_rhp_r_should_be_facet_center_per_c810():
    """**C810 偏差留档**（当前应失败；它是留档，不是回归）。

    C810 p.3-21 例题 `RHP 0 0 -4  0 0 8  0 2 0`：首个 facet「normal to the y-axis **at y=2**」
    ⇒ 边心距 = 2 ⇒ 沿该 facet 法向 1.99 处应在**体内**。
    现行实现把 r 当顶点 ⇒ 边心距仅 √3 ≈ 1.732 ⇒ 1.99 已在**体外**。
    """
    import numpy as np
    f = vc.surface_fn("RHP", [0.0, 0.0, -4.0, 0.0, 0.0, 8.0, 0.0, 2.0, 0.0])

    def inside(pt):
        return float(np.asarray(f(*[np.asarray([c]) for c in pt])).ravel()[0]) < 0

    # 该 facet 的法向 = 顶点 (0,2,0) 与 (−√3,1,0) 的中垂方向 ⇒ 120°
    nx, ny = -0.5, math.sqrt(3) / 2
    assert inside((nx * 1.99, ny * 1.99, 0.0)), (
        "C810 说该 facet 在 y=2（边心距 2）⇒ 1.99 应在体内；现行实现边心距只有 √3")
