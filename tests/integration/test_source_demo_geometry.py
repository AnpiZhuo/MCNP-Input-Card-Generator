"""源演示几何准备（`api_server.MCNPHandler._prepare_source_geometry`）的回归。

本文件覆盖两个**只在真实后端路径上才暴露**的缺陷（单测里用手写 geometry dict 全绿，
所以长期没被发现）：

1. `vc._surface_transform(tr_data)` 被误传两个参数 → `TypeError` → 被 except 吞掉
   → `surfaces` 恒为空 → **任何 `SDEF SUR=` 面源都报「曲面未定义」**。
2. MCNP 的**轴对齐圆柱缩写** `CX/CY/CZ`（≡ `C/X` 等）pymcnp 解析不了 → 被静默丢弃
   → 同样表现为「曲面未定义」，且 3D 预览/截面/STEP 导出同时受影响。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = PROJECT_DIR / "gui" / "backend"
for p in (str(PROJECT_DIR), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

api_server = pytest.importorskip("api_server", reason="需要 gui/backend 可导入（pymcnp）")


def _prep(surfaces_text: str, tr_text: str = "", cells: list | None = None):
    return api_server.MCNPHandler._prepare_source_geometry(None, surfaces_text,
                                                           cells or [], tr_text)


def test_plane_surface_ready_for_source_sampling():
    """`5 PX 5` 必须出现在 surfaces 里（旧实现 surface_fn 调用即抛错 → 面源全废）。"""
    g = _prep("5 PX 5")
    assert g["geometryErrors"] == [], g["geometryErrors"]
    s = g["surfaces"].get(5)
    assert s is not None, "PX 曲面未进入 surfaces（SDEF SUR=5 必然报'曲面未定义'）"
    assert s["type"] == "PX" and s["params"] == [5.0]
    assert callable(s["field"])


def test_sphere_surface_ready_and_normal_available():
    g = _prep("6 S 0 0 0 10")
    assert g["geometryErrors"] == []
    s = g["surfaces"].get(6)
    assert s is not None and s["type"] == "S"
    # api_server 侧补了 TR 的 rotate/origin（面源位置/法线要在世界系里）
    assert tuple(s["origin"]) == (0.0, 0.0, 0.0)


@pytest.mark.parametrize("text,expect_type", [
    ("7 CX 0 0 3", "C/X"),
    ("8 CY 1 2 3", "C/Y"),
    ("9 CZ 0 0 5", "C/Z"),
])
def test_axis_aligned_cylinder_abbrev_not_dropped(text, expect_type):
    """`CX/CY/CZ` 三项式缩写必须被改写成 `C/X` 等（pymcnp 对 CX/CY 什么都不认）。"""
    g = _prep(text)
    num = int(text.split()[0])
    s = g["surfaces"].get(num)
    assert s is not None, f"{text} 被丢弃"
    assert s["type"] == expect_type


def test_cz_two_item_short_form_is_kept_verbatim():
    """`CZ R`（两项式，MCNP 允许且 pymcnp 认）**不得**被改写成 `C/Z R`。

    2026-09-17 回归：把 `CZ` 无条件改写成 `C/Z` 后 `7 cz 0.3` 少两个参数 →
    pymcnp 抛 InpError → 被静默丢弃 → `test_api_contract.py` 的格元覆盖
    （其 COV_SURF 用的就是 `7 cz 0.3`）两例转红。
    """
    g = _prep("7 cz 0.3")
    assert g["geometryErrors"] == []
    s = g["surfaces"].get(7)
    assert s is not None, "CZ R 两项式被丢弃"
    assert s["type"] == "CZ" and s["params"] == [0.3]


def test_tr_cards_passed_through_for_sdef_tr():
    """SDEF TR=n 需要在 geometry 里拿到 TR 卡数据。"""
    g = _prep("5 PX 5", "TR2 0 0 100")
    assert "trCards" in g and "2" in g["trCards"]
    assert g["trCards"]["2"]["translate"] == [0.0, 0.0, 100.0]


def test_star_trn_angles_are_converted_to_cosines():
    """C810 3-30：`*TRn` 的 B1~B9 是**角度**（度）而非方向余弦。

    同一组旋转写成角度（`*TRn`，90°/0°）与写成余弦（`TRn`，0/1）必须得到**同一**
    rotate —— 旧实现忽略星号，把 90 度当成余弦值 90 用 ⇒ 旋转矩阵完全错误。
    角度矩阵 `90 90 0 | 0 90 90 | 90 0 90`（x′=z、y′=x、z′=y）。
    """
    star = _prep("5 PX 5", "*TR3 0 0 0  90 90 0  0 90 90  90 0 90")
    plain = _prep("5 PX 5", "TR3 0 0 0  0 0 1  1 0 0  0 1 0")
    assert star["geometryErrors"] == [], star["geometryErrors"]
    rot_star = star["trCards"]["3"]["rotate"]
    rot_plain = plain["trCards"]["3"]["rotate"]
    # pytest.approx 不吃嵌套 list ⇒ 逐行比
    for got, want in zip(rot_star, rot_plain):
        assert got == pytest.approx(want, abs=1e-12), (
            f"*TRn 角度未转余弦：{rot_star} 应为 {rot_plain}")
    assert rot_star[0] == pytest.approx([0.0, 0.0, 1.0], abs=1e-12)


def test_star_trn_keeps_translation_unchanged():
    """星号只作用于 B 矩阵：平移量 O1O2O3 读数不受 `*` 影响（C810 3-30 原文只提 Bi）。

    角度形式的单位矩阵是 `0 90 90 | 90 0 90 | 90 90 0`（不是 `1 0 0 …`：星号下 1 表示 1°）。
    """
    g = _prep("5 PX 5", "*TR4 7 8 9  0 90 90  90 0 90  90 90 0")
    assert g["trCards"]["4"]["translate"] == [7.0, 8.0, 9.0]
    identity = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    for got, want in zip(g["trCards"]["4"]["rotate"], identity):
        assert got == pytest.approx(want, abs=1e-12)


def test_tr_card_inline_comment_not_dropped():
    """行内 `$` 之后是注释 —— 旧实现整行 `float()` ⇒ 带注释的 TR 卡整条丢失。"""
    g = _prep("5 PX 5", "TR2 0 0 100 $ shift up")
    assert "2" in g["trCards"], "带 $ 注释的 TR 卡被丢弃"
    assert g["trCards"]["2"]["translate"] == [0.0, 0.0, 100.0]


def test_tr_card_six_value_mode_uses_cross_product():
    """C810 3-31 模式 #2：给出两个矢量（6 值），第三个由叉积生成。"""
    g = _prep("5 PX 5", "TR5 0 0 0  1 0 0  0 1 0")
    rot = g["trCards"]["5"]["rotate"]
    assert rot[0] == [1.0, 0.0, 0.0] and rot[1] == [0.0, 1.0, 0.0]
    assert rot[2] == pytest.approx([0.0, 0.0, 1.0], abs=1e-12)


def test_tr_card_partial_rotation_is_reported_not_silently_identity():
    """5 值（模式 #3）/3 值（模式 #4）由 MCNP 内部补全、手册未给公式 ⇒ 必须报出原因。

    旧实现静默退化成单位矩阵（= 只平移不旋转），用户拿到的是错几何却无任何提示。
    """
    # 3 个平移 + **5** 个 B 值 = 8 个数字（写 9 个就是模式 #2 的 6 值，不会走本条）
    g = _prep("5 PX 5", "TR6 0 0 0  0 0 1  1 0")
    assert "6" not in g["trCards"], "5 值模式不应被静默当成单位矩阵"
    assert any("TR6" in e for e in g["geometryErrors"]), g["geometryErrors"]


# ── TR 卡的 M（第 13 个参数，C810 3-30）─────────────────────────────────────
#
# 手册原文（锚点 #C810-3-30-TR-CARD，PDF p555 = 印刷 3-30）：
#   M = 1 (the default) means that the displacement vector is the location of the origin
#       of the auxiliary coordinate system, defined in the main system.
#     = -1 means that the displacement vector is the location of the origin of the main
#       coordinate system, defined in the auxiliary system.
# 本程序的消费口径是 `p_global = Rᵀ·p_local + o`（R 的每行 = 一个辅系轴在主系的分量，
# 手册 3-31 的 Axes 轴对表）⇒ M=-1 时 o = −Rᵀ·O。旧实现无条件按 M=1 处理。

#: 绕 z 轴 90°：x′=(0,1,0)、y′=(−1,0,0)、z′=(0,0,1)（行 = 辅系轴在主系的分量）。
_ROT_Z90 = [[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
#: 该旋转 + O=(10,0,0) 在 M=-1 下的等效平移 = −Rᵀ·O = (0,−10,0)。
_TR_M_MINUS_ONE_TRANSLATE = (0.0, -10.0, 0.0)


def test_tr_card_m_minus_one_reads_displacement_in_auxiliary_system():
    """`M=-1` ⇒ 位移矢量是主系原点在**辅系**里的位置 ⇒ 主系等效平移为 −Rᵀ·O。

    取 R = 绕 z 90°、O = (10,0,0)：辅系里的 (10,0,0) 正是主系原点，故主系里的辅系原点
    落在 (0,−10,0)。旧实现把 O 直接当平移 ⇒ 位置整体错 10（且方向对不上）。
    """
    g = _prep("5 PX 5", "TR7 10 0 0  0 1 0  -1 0 0  0 0 1  -1")
    assert g["geometryErrors"] == [], g["geometryErrors"]
    card = g["trCards"]["7"]
    for got, want in zip(card["rotate"], _ROT_Z90):
        assert got == pytest.approx(want, abs=1e-12), card["rotate"]
    assert card["translate"] == pytest.approx(_TR_M_MINUS_ONE_TRANSLATE, abs=1e-12)


def test_tr_card_m_invariant_keeps_displacement_vector_as_is():
    """`M=1`（显式写出）与整个 M 省略都必须与旧行为一致：平移 = O 本身。"""
    explicit = _prep("5 PX 5", "TR8 10 0 0  0 1 0  -1 0 0  0 0 1  1")
    omitted = _prep("5 PX 5", "TR8 10 0 0  0 1 0  -1 0 0  0 0 1")
    for g in (explicit, omitted):
        assert g["geometryErrors"] == [], g["geometryErrors"]
        assert g["trCards"]["8"]["translate"] == pytest.approx([10.0, 0.0, 0.0])


def test_tr_card_m_minus_one_after_six_value_pattern():
    """6 值模式（两矢量 + 叉积）后面跟的 M 同样要被读出来。

    `TR9 10 0 0  0 1 0  -1 0 0  -1` = O + 6 个 B + M（共 10 个数字，条目数上唯一可判）。
    """
    g = _prep("5 PX 5", "TR9 10 0 0  0 1 0  -1 0 0  -1")
    assert g["geometryErrors"] == [], g["geometryErrors"]
    card = g["trCards"]["9"]
    for got, want in zip(card["rotate"], _ROT_Z90):
        assert got == pytest.approx(want, abs=1e-12), card["rotate"]
    assert card["translate"] == pytest.approx(_TR_M_MINUS_ONE_TRANSLATE, abs=1e-12)


def test_tr_card_invalid_m_is_reported_not_ignored():
    """M 只能是 1 或 −1（C810 3-30）⇒ 别的值必须报出来，不许当成第 13 个 B 项吃掉。"""
    g = _prep("5 PX 5", "TR10 0 0 0  0 1 0  -1 0 0  0 0 1  5")
    assert "10" not in g["trCards"]
    assert any("TR10" in e and "M" in e for e in g["geometryErrors"]), g["geometryErrors"]


def test_tr_card_six_values_ending_in_pm_one_reports_ambiguity():
    """手册未给判别规则的一处：O 之后给 6 项且末项恰为 ±1 时，「6 值」与「5 值 + M」都合法。

    本程序按 6 值（叉积）读、卡照常生效，但必须把歧义写进 ``geometryErrors`` —— 不静默选边。
    末项不是 ±1 时（`TR12 … 0`）两种读法只有一种成立，不得产生噪声。
    """
    ambiguous = _prep("5 PX 5", "TR11 0 0 0  1 0 0  0 0 1")
    assert "11" in ambiguous["trCards"], "6 值模式必须仍然生效"
    assert ambiguous["trCards"]["11"]["rotate"][2] == pytest.approx([0.0, -1.0, 0.0])
    assert any("TR11" in e for e in ambiguous["geometryErrors"]), ambiguous["geometryErrors"]

    plain = _prep("5 PX 5", "TR12 0 0 0  1 0 0  0 1 0")
    assert plain["geometryErrors"] == [], plain["geometryErrors"]


def test_sdef_tr_m_minus_one_actually_moves_sampled_positions():
    """整链（TR 卡文本 → parse_tr_cards → sample_source 的粒子位置）：M 必须真的到位。

    辅系里的点源 POS=(0,0,0) 经 M=-1 的变换后应落在主系 (0,−10,0)，而不是 O=(10,0,0)。
    """
    from app.generator.source_sampler import sample_source

    g = _prep("5 PX 5", "TR7 10 0 0  0 1 0  -1 0 0  0 0 1  -1")
    r = sample_source(
        {"sdef_pos_x": "0", "sdef_pos_y": "0", "sdef_pos_z": "0",
         "sdef_tr": "7", "sdef_erg": "14"},
        [], geometry={"trCards": g["trCards"]}, n_particles=5, seed=1)
    assert r["status"] == "ok", r.get("error")
    for p in r["particles"]:
        assert (p["x"], p["y"], p["z"]) == pytest.approx(_TR_M_MINUS_ONE_TRANSLATE, abs=1e-9)


def test_cell_volumes_available_for_sp_v():
    """`SP V`（C810 3-64 概率 ∝ 栅元体积）需要 geometry 给出逐栅元体积。

    立方体 −1..1 ⇒ 8；球 SO 2 ⇒ 33.51。旧实现根本没算体积 ⇒ SP V 无从实现。
    """
    cube = _prep("1 px -1\n2 px 1\n3 py -1\n4 py 1\n5 pz -1\n6 pz 1",
                 cells=[{"number": 1, "material": "1", "density": "-1",
                         "surface_expr": "1 -2 3 -4 5 -6", "imp_n": "1", "render": True}])
    assert cube["geometryErrors"] == [], cube["geometryErrors"]
    assert abs(cube["cellVolumes"][1] - 8.0) < 0.1, cube["cellVolumes"]

    sphere = _prep("1 so 2", cells=[{"number": 1, "material": "1", "density": "-1",
                                     "surface_expr": "-1", "imp_n": "1", "render": True}])
    v = sphere["cellVolumes"][1]
    assert abs(v - 4.0 / 3.0 * 3.141592653589793 * 8.0) / v < 0.03, v
