"""相切退化修复判定逻辑的单元测试（纯函数，不需要 FreeCAD）。

背景见 app/tangent_fix.py：用户文件里**唯一**含「同轴同半径球面/圆柱面」的两个实体被
GEOUNED 转错（体积大 7.8/8.1 倍 + 互相重叠），把球面沿径向外移 0.1% 即修复。
本测试锁住"只在退化相切时动手""同一球面只修一次""体积闸门""提示写清做了什么"。
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "app"))

from tangent_fix import (  # noqa: E402
    EPS, VOL_GATE, dedupe_spheres, describe_actions, is_safe, is_tangent_pair, shift_amount,
)


def test_tangent_pair_requires_equal_radius_and_coaxial():
    # 用户实机案例：#3/#4 是 球 r=50 与 柱 r=50、轴距 0
    assert is_tangent_pair(50.0, 50.0, 0.0) is True
    assert is_tangent_pair(50.0, 50.0, 1e-9) is True
    # 半径不等 ⇒ 不动（合成实验 B/C：49.95 / 50.05 本来就能正确转换）
    assert is_tangent_pair(49.95, 50.0, 0.0) is False
    assert is_tangent_pair(50.05, 50.0, 0.0) is False
    # 半径相等但不同轴 ⇒ 不动
    assert is_tangent_pair(50.0, 50.0, 0.001) is False
    # 相对容差：小尺度几何（r=0.05）也按相对量判
    assert is_tangent_pair(0.05, 0.05, 1e-9) is True
    assert is_tangent_pair(0.05, 0.05, 1e-4) is False
    # 用户文件里 #1/#2/#5/#6 这类"有球有柱但半径不等"的实体不得被误伤
    assert is_tangent_pair(50.0, 50.0, 0.0) is True
    assert is_tangent_pair(4.5, 5.0, 0.0) is False


def test_shift_amount_is_relative():
    assert shift_amount(50.0) == 50.0 * EPS
    assert math.isclose(shift_amount(50.0), 0.05, rel_tol=1e-12)   # 50 → 外移 0.05
    assert shift_amount(-50.0) == 50.0 * EPS                       # 半径取绝对值


def test_volume_gate_rejects_unsafe_and_nan():
    assert is_safe(0.0) is True
    assert is_safe(0.0002) is True          # 实机修复实测 0.0215% ⇒ 通过
    assert is_safe(-0.0002) is True
    assert is_safe(VOL_GATE) is True
    assert is_safe(VOL_GATE * 1.0001) is False
    assert is_safe(float("nan")) is False
    assert is_safe(float("inf")) is False


def test_dedupe_spheres_keeps_one_per_sphere():
    # 2 个球面 × 2 个柱面 = 4 对，但只有 2 个不同的球面要修（实机 #3/#4 正是各 4 对）
    pairs = [
        ([0.0, 50.0, 0.0], 50.0, 50.0),
        ([0.0, 50.0, 0.0], 50.0, 50.0),
        ([0.0, 50.0, 0.0], 50.0, 50.0),
        ([0.0, 50.0, 0.0], 50.0, 50.0),
        ([0.0, 50.0, 100.0], 50.0, 50.0),
    ]
    got = dedupe_spheres(pairs)
    assert len(got) == 2
    assert [p[0][2] for p in got] == [0.0, 100.0]      # 顺序保持
    # 同球心不同半径算两次
    assert len(dedupe_spheres([([0, 0, 0], 50.0, 50.0), ([0, 0, 0], 50.05, 50.05)])) == 2


def test_describe_actions_reports_what_was_done():
    """用户有权知道几何被动了 0.1% —— 提示必须写出实体号、外移量与体积变化。"""
    txt = describe_actions([
        {"solid": 3, "sphereR": 50.0, "cylR": 50.0, "shift": 0.05, "dvol": 0.0002152},
        {"solid": 4, "sphereR": 50.0, "cylR": 50.0, "shift": 0.05, "dvol": 0.0002162},
    ])
    assert "实体 3" in txt and "实体 4" in txt
    assert "0.0500" in txt
    assert "0.0215" in txt                      # 体积变化百分比
    assert "相切退化自动修复" in txt             # 告知可关闭
    assert describe_actions([]) == ""
