# -*- coding: utf-8 -*-
"""`prune_unbounded_union_branches` 单测（纯函数，不需要 FreeCAD）。

锁死的契约：
  1. **纯平面且约束数 ≤3** 的并集分支必须被剔除（3 平面在 3D 里必然无界）；
  2. **含曲面的**分支不剔（3 个曲面可能围出有界体）；
  3. **≥4 个平面**的分支不剔（可以围出有界体，如四面体）；
  4. **单约束栅元**（顶层不是 union，如 graveyard 的 `277`）一律不动 —— 半空间栅元
     本来就是无界的合法栅元；
  5. 剔完一个不剩时**原样返回**（宁可不动，也不产出空栅元）；
  6. 返回的 AST 结构仍是合法的 union 链。
"""
import json
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR / "app"))

from freecad_preview import prune_unbounded_union_branches  # noqa: E402

# 曲面号 → 类型（模拟 GEOUNED deck：144/190 是斜置平面 P_0，180 是 PY）
TYPES = {100: "PX", 101: "PY", 102: "PZ", 144: "P_0", 190: "P_0", 180: "PY",
         277: "S", 280: "C/Z", 300: "P_1"}


def surf(n):
    return ["surf", n]


def neg(n):
    return ["unary", ["surf", n], "neg"]


def inter(*items):
    node = items[0]
    for x in items[1:]:
        node = ["intersect", node, x]
    return node


def union(*items):
    node = items[0]
    for x in items[1:]:
        node = ["union", node, x]
    return node


def branches_of(node):
    """把结果展平成分支列表（用于断言保留了几支）。"""
    if node[0] != "union":
        return [node]
    return branches_of(node[1]) + branches_of(node[2])


def test_drops_three_plane_branch_the_real_bug():
    """用户实测的那个退化项：144(P_0) -190(P_0) -180(PY) 必须被剔除。"""
    ast = union(inter(surf(100), neg(101), surf(102), neg(180)),   # 4 平面 → 保留
                inter(surf(144), neg(190), neg(180)),              # ← 3 平面，必然无界
                inter(surf(100), neg(102), surf(180), neg(144)))   # 4 平面 → 保留
    out, dropped = prune_unbounded_union_branches(ast, TYPES)
    assert dropped == 1
    kept = branches_of(out)
    assert len(kept) == 2
    assert inter(surf(144), neg(190), neg(180)) not in kept


def test_drops_one_and_two_plane_branches_too():
    """1 个 / 2 个平面的交同样必然无界（只要不是整个栅元）。"""
    ast = union(surf(277), neg(100), inter(surf(100), neg(101)),
                inter(surf(100), neg(101), surf(102), neg(180)))
    out, dropped = prune_unbounded_union_branches(ast, TYPES)
    # surf(277) 是球（曲面，不剔）；neg(100)/两个平面 都剔
    assert dropped == 2
    assert len(branches_of(out)) == 2


def test_keeps_branch_with_a_curved_surface():
    """含柱/球/锥的分支不剔 —— 3 个曲面可能围出有界体。"""
    ast = union(inter(surf(277), neg(280), neg(100)),      # 球 + 柱 + 平面：不剔
                inter(surf(100), neg(101), surf(102), neg(180)))
    out, dropped = prune_unbounded_union_branches(ast, TYPES)
    assert dropped == 0
    assert out is ast


def test_keeps_four_plane_branch():
    """4 个平面可以围出有界体（四面体）⇒ 不剔。"""
    ast = union(inter(surf(100), neg(101), surf(102), neg(180)),
                inter(surf(144), neg(190), neg(180), surf(100)))
    out, dropped = prune_unbounded_union_branches(ast, TYPES)
    assert dropped == 0 and out is ast


def test_single_constraint_cell_untouched():
    """单约束栅元（顶层不是 union）一律不动 —— graveyard 的 `277` 就是无界的合法栅元。"""
    for ast in (surf(277), neg(100), inter(surf(100), neg(101))):
        out, dropped = prune_unbounded_union_branches(ast, TYPES)
        assert dropped == 0 and out is ast


def test_all_branches_degenerate_returns_original():
    """剔完一个不剩 ⇒ 原样返回（不能产出空栅元）。"""
    ast = union(neg(100), inter(surf(101), neg(102)))
    out, dropped = prune_unbounded_union_branches(ast, TYPES)
    assert dropped == 0 and out is ast


def test_group_complement_branch_is_not_dropped():
    """含组补集（unary 包着 intersect）的分支不判、不剔。"""
    grp = ["unary", inter(surf(100), neg(101)), "neg"]
    ast = union(inter(surf(100), neg(101), surf(102)), grp)
    out, dropped = prune_unbounded_union_branches(ast, TYPES)
    # 第一支 3 平面被剔；组补集那支保留 ⇒ 结果只剩它
    assert dropped == 1
    assert branches_of(out) == [grp]


def test_unknown_surface_type_is_conservative():
    """曲面号不在表里 ⇒ 类型取不到 ⇒ 不剔（保守放行，避免误伤）。"""
    ast = union(inter(surf(999), neg(998), surf(997)),
                inter(surf(100), neg(101), surf(102), neg(180)))
    out, dropped = prune_unbounded_union_branches(ast, TYPES)
    assert dropped == 0 and out is ast


def test_result_is_valid_union_chain():
    """剔完后的 AST 仍是合法的 union 链（可被 eval_ast 递归消费）。"""
    ast = union(surf(277), neg(100), inter(surf(101), neg(102)),
                inter(surf(100), neg(101), surf(102), neg(180)))
    out, dropped = prune_unbounded_union_branches(ast, TYPES)
    assert dropped == 2

    def walk(n, depth=0):
        assert isinstance(n, list) and n[0] in ("union", "intersect", "unary", "surf", "facet")
        if n[0] in ("union", "intersect"):
            walk(n[1], depth + 1)
            walk(n[2], depth + 1)
        elif n[0] == "unary":
            walk(n[1], depth + 1)

    walk(out)
    assert json.dumps(out)      # 可序列化
