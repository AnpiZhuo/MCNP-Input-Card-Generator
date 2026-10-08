"""相切退化修复的**判定逻辑**（纯函数，可离线测；FreeCAD 侧的几何操作在 geouned_worker 里）。

## 问题（2026-10-08 用户实机 + 受控实验，已定位到根因）
GEOUNED 在把「**圆柱被一个同轴、同半径的球面切掉**」这种实体转成 CSG 时**会丢一个定界面**，
产出的栅元沿轴向无限延伸。用户文件 `筒子1.STEP` 实测：

| 实体 | 同轴同半径球/柱对 | 转换结果 |
|---|---|---|
| #1 零件11 / #2 最外球壳 / #5 源入棒 / #6 水体 | 0 | ✔ 与 CAD 实体吻合 |
| **#3 把柄 / #4 入棒** | **各 4 对**（球 r=50 = 柱 r=50，轴距 0） | ✘ 体积大 7.8 / 8.1 倍，且 3∩4、3∩5 重叠 |

受控实验（自造"圆柱 r=50 减同轴球"）：球 r **= 50** → 只出 3 个面、丢边界（25664 vs 实体 3665）；
球 r = 49.95 或 50.05（差 0.1%）→ 4 个面、体积正确（3664.8 / 3663.3）。

## 修法
把该球面**沿径向外移 0.1%**（`new = old ∪ (球_R − 球_{R(1−ε)})`，用实体包围盒裁剪），
即"少切掉一层薄壳"，从而破除相切退化；体积只变化约 0.02%。

## 纪律
* 只在**半径相等且同轴**时动手（其余一律不碰）；
* 同一个球面只修一次（球心+半径去重）；
* 体积变化超过 `VOL_GATE` 就**放弃**该处（宁可保持原样，也不悄悄改坏几何）；
* 做了什么必须回报到导入提示里（用户有权知道几何被动了 0.1%）。
"""

from __future__ import annotations

import math

#: 球面沿径向外移的相对量（0.1%）
EPS = 0.001
#: 单个实体允许的体积变化上限；超过就放弃修复（安全闸门）
VOL_GATE = 0.005
#: 半径/同轴比较的相对容差
REL_TOL = 1e-6


def _rel_close(a: float, b: float, rel_tol: float = REL_TOL) -> bool:
    """相对相等（同轴度/半径相等都用它；绝对量级随几何尺度变，所以用相对）。"""
    scale = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / scale <= rel_tol


def is_tangent_pair(sphere_r: float, cyl_r: float, axis_distance: float,
                    rel_tol: float = REL_TOL) -> bool:
    """球面与圆柱面是否构成"同半径 + 同轴"的退化相切对（GEOUNED 会因此丢边界）。"""
    if not (_rel_close(sphere_r, cyl_r, rel_tol)):
        return False
    # 轴距按球半径归一化（同轴 ⇔ 球心在柱轴上）
    return abs(axis_distance) <= rel_tol * max(abs(sphere_r), 1.0)


def shift_amount(sphere_r: float, eps: float = EPS) -> float:
    """该球面要外移多少（绝对长度，与模型单位一致）。"""
    return abs(sphere_r) * eps


def is_safe(dvol: float, gate: float = VOL_GATE) -> bool:
    """体积变化是否在安全闸门内（`dvol` 为相对变化，正负均可）。"""
    return math.isfinite(dvol) and abs(dvol) <= gate


def dedupe_spheres(pairs):
    """同一球面（球心 + 半径）只保留一次 —— 球面会被多个柱面重复匹配成多对。

    `pairs` 元素：(sphere_center（可取 3 元组）, sphere_r, cyl_r[, axis_distance])
    返回按输入顺序去重后的列表。
    """
    seen = set()
    out = []
    for p in pairs:
        center, rs = p[0], float(p[1])
        key = (round(float(center[0]), 6), round(float(center[1]), 6),
               round(float(center[2]), 6), round(rs, 6))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def describe_actions(actions) -> str:
    """把已实施的修复写成一句中文提示（进导入结果 warnings）。"""
    if not actions:
        return ""
    parts = []
    for a in actions:
        parts.append(f"实体 {a.get('solid')}：球 r={a.get('sphereR'):.4f} 外移 {a.get('shift'):.4f}"
                     f"（体积变化 {abs(a.get('dvol', 0.0)) * 100:.4f}%）")
    return ("检测到 GEOUNED 会丢边界的退化相切（球面与同轴圆柱面半径相等），已自动把球面沿径向"
            "外移 " + f"{EPS * 100:.1f}% 以规避：" + "；".join(parts)
            + "。这只改动一根头发丝的尺度，如不接受可在导入设置里关闭「相切退化自动修复」。")
