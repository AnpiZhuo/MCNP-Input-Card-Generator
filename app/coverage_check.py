"""格阵覆盖完整性检测（universe 未编辑外部 → 红框预防）。

判断 universe `U` 的栅元集合是否完整覆盖格元盒：在格元盒内均匀采样，
逐点解析判定该点是否落在 `U` 的**任一**栅元内；不落在任何栅元内的采样点占比
超过 ``COVERAGE_TOL`` → 判定「未覆盖」（即只定义内部、没定义外部，填进 lattice
后格元盒边缘会出现红色未定义区）。

纯 stdlib + numpy，复用 ``voxel_csg.surface_fn / eval_cell_field / _surface_tr``。
输入的是**栅元 AST JSON**（``["intersect"/"union"/"unary"/"surf", ...]``）——
由调用方（``/api/validate-universe-coverage``）用 pymcnp 构造并做 ``#n`` 补集展开；
本模块只负责采样判定与结论分类，不做 AST 解析。

坐标系假设：universe 栅元与格元盒同坐标系（未还原格阵级 TRCL 平移/旋转；单曲面
的 ``*TRn`` 已由 ``surfaces_by_num`` 携带 transform 在 ``surface_fn`` 内处理）。
"""

from __future__ import annotations

import numpy as np

try:
    from voxel_csg import surface_fn, eval_cell_field, _surface_tr, _ast_surf_nums
except ImportError:  # 测试/直接 import app 包时 voxel_csg 在 app/ 下
    from app.voxel_csg import surface_fn, eval_cell_field, _surface_tr, _ast_surf_nums


# 未覆盖占比超 1% → 判定未覆盖（边界点落在曲面附近有采样误差，留裕量）
COVERAGE_TOL = 0.01
# 每轴采样点数（16³ ≈ 4096 点，毫秒级）
DEFAULT_RES = 16
# 无界轴（如 2D 延伸的 z）的默认采样厚度（相对格元中心，单位同格元盒）
DEFAULT_UNBOUNDED_SPAN = 1.0
# 采样点从格元盒表面内缩的相对步长：避免采样点恰落在盒面平面上
# （格元盒面常与 universe 栅元的边界曲面共面，落在面上会因 `>=0` 的
#  正侧语义被误判为「未定义」→ 空盒误报未覆盖）。0.5% span 相对内缩。
EDGE_INSET_REL = 0.005


def _sampling_domain(box: dict | None, default_span: float = DEFAULT_UNBOUNDED_SPAN,
                     inset_rel: float = EDGE_INSET_REL):
    """格元盒 extent → 采样域 ``(lo3, hi3)``（numpy 数组）。

    ``box`` 形如 ``{x_min,x_max,y_min,y_max,z_min,z_max}``（``lattice_cell_extent``
    输出）；某轴无界（None）时用默认厚度（相对中心 0）。无法确定采样域 → None。
    有界轴按 ``inset_rel`` 相对内缩（默认 0.5%），采样点避开盒面平面。
    """
    if not box:
        return None
    lo = []
    hi = []
    for ax in ("x", "y", "z"):
        mn = box.get(ax + "_min")
        mx = box.get(ax + "_max")
        if mn is None or mx is None:
            lo.append(-default_span / 2.0)
            hi.append(default_span / 2.0)
        else:
            try:
                mn = float(mn)
                mx = float(mx)
            except (TypeError, ValueError):
                return None
            span = mx - mn
            if span <= 0:
                return None
            inset = span * inset_rel
            lo.append(mn + inset)
            hi.append(mx - inset)
    if any(hi[i] <= lo[i] for i in range(3)):
        return None
    return np.asarray(lo, dtype=float), np.asarray(hi, dtype=float)


def _resolve_cell_ast(ast, surfaces_by_num, tr_cards):
    """单个栅元 AST → 布尔场函数（True = 在栅元内）。失败返回 None。

    允许引用的曲面类型由 ``voxel_csg.surface_fn`` 支持集决定（平面/球/柱/锥/
    GQ/SQ/RPP/SPH）；BOX/RHP/HEX 等宏体暂不支持 → 返回 None，由调用方降级。
    """
    try:
        nums = _ast_surf_nums(ast)
    except Exception:
        return None
    if not nums:
        return None
    fns = {}
    for num in nums:
        s = surfaces_by_num.get(num)
        if s is None:
            return None  # 引用未定义曲面 → 无法判定该栅元
        try:
            fns[num] = surface_fn(
                s.get("type", ""), s.get("params", []) or [],
                _surface_tr(s, tr_cards))
        except Exception:
            return None  # 不支持的曲面类型
    if not fns:
        return None

    def field(X, Y, Z):
        try:
            return eval_cell_field(ast, fns, X, Y, Z)
        except Exception:
            return None

    return field


def universe_coverage(box: dict | None, asts_json: list, surfaces_by_num: dict,
                      tr_cards: dict, res: int = DEFAULT_RES) -> dict:
    """判定 universe 栅元集合是否完整覆盖格元盒。

    参数：
        box: ``lattice_cell_extent`` 输出（格元盒范围），None → 无法解析。
        asts_json: universe `U` 的全部**叶栅元** AST JSON（已排除 fill 容器、已做 #n 展开）。
        surfaces_by_num: ``{num: {type, params, transform}}``，供 surface_fn 构造。
        tr_cards: TR 卡 dict（``parse_tr_cards`` 输出），供带 TR 曲面。

    返回 ``{kind, covered, uncoveredFraction, sampleCount, detailViable,
            unsupportedCells, message}``。

    ``kind``：
        - ``"empty"``：`U` 无栅元定义（无法判定）。
        - ``"leaf"``  ：叶 universe，执行采样判定。
        - ``"lattice"``：`U` 含嵌套格阵栅元，由子层保证（调用方判定后传入，本层仅透传）。
    ``detailViable=False``：格元盒无法解析 / 全部栅元几何无法求值 → 不误判、不标记覆盖。
    """
    # 嵌套格阵 / 无定义：由调用方决定 kind，这里直接透传包装（本函数不改 kind 语义）
    kind = "leaf"

    if not asts_json:
        return {"kind": "empty", "covered": False, "uncoveredFraction": 1.0,
                "sampleCount": 0, "detailViable": False, "unsupportedCells": 0,
                "message": "该 universe 尚无栅元定义，无法判定覆盖"}

    domain = _sampling_domain(box)
    if domain is None:
        return {"kind": kind, "covered": False, "uncoveredFraction": 1.0,
                "sampleCount": 0, "detailViable": False, "unsupportedCells": 0,
                "message": "无法解析格元盒范围（含 #/: 或曲面未定义）"}

    lo, hi = domain
    res = max(2, int(res))
    xs = np.linspace(lo[0], hi[0], res)
    ys = np.linspace(lo[1], hi[1], res)
    zs = np.linspace(lo[2], hi[2], res)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")

    covered = np.zeros(X.shape, dtype=bool)
    unsupported = 0
    evaluated = 0
    for ast in asts_json:
        field = _resolve_cell_ast(ast, surfaces_by_num, tr_cards)
        if field is None:
            unsupported += 1
            continue
        box_field = field(X, Y, Z)
        if box_field is None:
            unsupported += 1
            continue
        covered |= box_field
        evaluated += 1

    if evaluated == 0:
        return {"kind": kind, "covered": False, "uncoveredFraction": 1.0,
                "sampleCount": 0, "detailViable": False,
                "unsupportedCells": unsupported,
                "message": "全部栅元几何无法解析（宏体/复杂曲面）"}

    uncovered_frac = float((~covered).mean())
    # 未覆盖占比较高或存在无法求值栅元 → 可靠性下降
    detail_viable = unsupported == 0
    covered_ok = uncovered_frac <= COVERAGE_TOL
    if covered_ok:
        msg = f"U 已覆盖格元盒（未定义区域 {uncovered_frac * 100:.1f}%）"
    else:
        msg = (f"U 未完整覆盖格元盒（约 {uncovered_frac * 100:.0f}% 区域无栅元定义，"
               "可能出现红框）")
    if unsupported > 0:
        msg += f"；{unsupported} 个栅元几何无法解析，判定可能不完整"

    return {"kind": kind, "covered": covered_ok, "uncoveredFraction": uncovered_frac,
            "sampleCount": int(X.size), "detailViable": detail_viable,
            "unsupportedCells": unsupported, "message": msg}


__all__ = ["universe_coverage", "COVERAGE_TOL", "DEFAULT_RES"]
