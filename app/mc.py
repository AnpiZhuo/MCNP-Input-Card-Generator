"""纯 numpy marching cubes（无 vtk / FreeCAD 依赖）。

实现说明
--------
* 提取规则采用 256 项 case 查找表；该表在模块导入期由立方体的 Kuhn
  六四面体剖分一次性生成（每个 case 的三角形由 6 个四面体的线性等值面
  片段合并）。这种剖分对相邻立方体的共面限制一致，因此输出网格按构造
  水密。
* 三角形顶点取四面体边（12 条立方体棱 + 面/体对角线）的 0/1 中点；
  共享边两侧计算得到完全相同的浮点坐标，提取后按「半网格量化整数 key」
  焊接（结构化 1D unique），保证「每条无向边恰被 2 个三角形使用」。
* 朝向修复分两步（不依赖微小探针，对任意水密网格鲁棒）：
  1. 按连通分量沿共享边传播一致绕序（相邻三角形共享边必须反向遍历）；
  2. 每分量有向体积取符号：负 → 整体翻转（法向指向区域外侧）。
  仅当分量体积退化（≈0）时，才用 ``inside_fn`` 探针兜底。

API
---
``marching_cubes(field, x, y, z, inside_fn=None) -> (vertices, triangles)``
* ``field``：``(nx, ny, nz)`` 布尔数组，True=区域内部。
* ``x, y, z``：三轴网格节点坐标（长度必须等于 field 对应维）。
* ``vertices``：``(N, 3)`` float64。
* ``triangles``：``(M, 3)`` int64，顶点索引。
"""

from __future__ import annotations

import numpy as np

# 立方体顶点编号（bit 0 = 顶点 0）：
#   0:(0,0,0)  1:(1,0,0)  2:(1,1,0)  3:(0,1,0)
#   4:(0,0,1)  5:(1,0,1)  6:(1,1,1)  7:(0,1,1)

# 立方体的 Kuhn 六四面体剖分（固定坐标序 x≤y≤z 的 6 个单形）。
# 每个四面体都含体对角线 0-6；限制到任意立方体面上只有一条固定对角线，
# 因此相邻立方体在公共面上的三角剖分一致 → 网格水密。
_KUHN_TETS = (
    (0, 1, 2, 6),
    (0, 3, 2, 6),
    (0, 3, 7, 6),
    (0, 4, 7, 6),
    (0, 4, 5, 6),
    (0, 1, 5, 6),
)
_TET_EDGE_PAIRS = (
    (0, 1), (0, 2), (0, 3),
    (1, 2), (1, 3), (2, 3),
)
_TET_FACES = (
    (0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3),
)

# 8 个立方体顶点间的全部 28 条无向边（12 条立方体棱 + 面/体对角线）。
# 每个 case 的三角形顶点可落在四面体的任意边上（面/体对角线也参与），
# 相邻四面体/立方体共享同一条边时按相同公式取中点，焊点后天然水密。
_PAIR_LIST = tuple((u, v) for u in range(8) for v in range(u + 1, 8))
_PAIR_A = np.asarray([p[0] for p in _PAIR_LIST], dtype=np.intp)
_PAIR_B = np.asarray([p[1] for p in _PAIR_LIST], dtype=np.intp)
_PAIR_ID = {(u, v): i for i, (u, v) in enumerate(_PAIR_LIST)}
_PAIR_ID.update({(v, u): i for i, (u, v) in enumerate(_PAIR_LIST)})


def _build_case_table():
    """由 Kuhn 四面体剖分生成 256 项 MC case 表。

    返回 ``(case_triangles, case_counts, max_tris)``：
    * ``case_triangles`` 形状 ``(256, max_tris, 3)``，-1 为填充。
    * 三角形顶点存的是 ``_PAIR_LIST`` 索引（两条立方体顶点配对 → 边中点）。
    * 顶点顺序仅为拓扑（排序后的配对索引），朝向由
      ``_orient_triangles`` 在运行时按分量统一修复。
    """
    tri_by_case = []
    for case in range(256):
        inside = [(case >> v) & 1 for v in range(8)]
        tris = set()
        for a, b, c, d in _KUHN_TETS:
            crossing = []
            for pa, pb in _TET_EDGE_PAIRS:
                va, vb = (a, b, c, d)[pa], (a, b, c, d)[pb]
                if inside[va] != inside[vb]:
                    crossing.append(_PAIR_ID[(va, vb)])

            if len(crossing) == 3:
                tris.add(tuple(sorted(crossing)))
                continue
            if len(crossing) != 4:
                continue

            # 4 个交点构成平面四边形。先按四面体的四个三角面找出四边形的
            # 四条边界边，再拼成环后对半三角化（两条对角线任选其一都在
            # 同一等值面平面上，拓扑等价）。
            segs = []
            for f in _TET_FACES:
                fv = set((a, b, c, d)[k] for k in f)
                on_face = []
                for e in crossing:
                    u, v = _PAIR_LIST[e]
                    if u in fv and v in fv:
                        on_face.append(e)
                if len(on_face) == 2:
                    segs.append(tuple(on_face))
            if len(segs) != 4:
                raise RuntimeError("marching cubes LUT 生成失败：四边形边数异常")

            adj = {e: [] for e in crossing}
            for u, v in segs:
                adj[u].append(v)
                adj[v].append(u)
            cur = crossing[0]
            prev = None
            cycle = []
            while True:
                cycle.append(cur)
                nxt = [x for x in adj[cur] if x != prev][0]
                prev, cur = cur, nxt
                if cur == cycle[0]:
                    break
            if len(cycle) != 4:
                raise RuntimeError("marching cubes LUT 生成失败：四边形环异常")
            tris.add(tuple(sorted((cycle[0], cycle[1], cycle[2]))))
            tris.add(tuple(sorted((cycle[0], cycle[2], cycle[3]))))
        tri_by_case.append(list(tris))

    max_tris = max(len(t) for t in tri_by_case)
    table = np.full((256, max_tris, 3), -1, dtype=np.int16)
    counts = np.zeros(256, dtype=np.int16)
    for case, tris in enumerate(tri_by_case):
        counts[case] = len(tris)
        for ti, tri in enumerate(tris):
            table[case, ti] = tri
    return table, counts, max_tris


_CASE_TABLE, _CASE_COUNTS, _MAX_TRIS = _build_case_table()


def _probe_orient(vertices, triangles, inside_fn, spacing):
    """逐三角形探针兜底：沿法向偏移采样 ``inside_fn``，法向指向区域外侧。

    仅用于退化分量（有向体积≈0）或非流形网格，探针位移取 0.25×spacing
    （覆盖 Kuhn 三角形质心到等值面的最大偏移，避免过小探针判不出朝向）。
    """
    if inside_fn is None or len(triangles) == 0:
        return triangles
    v0 = vertices[triangles[:, 0]]
    v1 = vertices[triangles[:, 1]]
    v2 = vertices[triangles[:, 2]]
    nrm = np.cross(v1 - v0, v2 - v0)
    lengths = np.linalg.norm(nrm, axis=1)
    good = lengths > 1e-30
    if not np.any(good):
        return triangles
    delta = max(spacing * 0.25, 1e-9)
    centroids = (v0 + v1 + v2) / 3.0
    good_idx = np.flatnonzero(good)
    unit = nrm[good] / lengths[good, None]
    probes = centroids[good] + unit * delta
    inside = np.asarray(
        inside_fn(probes[:, 0], probes[:, 1], probes[:, 2]), dtype=bool
    ).ravel()
    out = triangles.copy()
    flip = good_idx[inside]
    if flip.size:
        out[flip] = out[flip][:, ::-1]
    return out


def _orient_triangles(vertices, triangles, inside_fn, spacing):
    """统一三角形朝向：分量内传播一致绕序 + 分量有向体积定外/内。

    1. 构建「无向边 → 两三角形」邻接；对每条共享边，两个三角形必须
       反向遍历（一个 u→v、一个 v→u）。沿连通分量 BFS 传播翻转位。
    2. 每分量按有向体积符号定全局方向：负体积分量整体翻转（法向向外）。
    3. 退化分量（|有向体积|≈0）回退 ``_probe_orient`` 探针。
    """
    n = len(triangles)
    if n == 0:
        return triangles

    nv = len(vertices)
    # 注意：e 是「先全部 (0,1)、再全部 (1,2)、再全部 (2,0)」的块状拼接，
    # 因此 t_ids 必须用 tile（每块内 0..n-1），slots 用 repeat（每块一个槽位）。
    e = np.concatenate([
        triangles[:, [0, 1]],
        triangles[:, [1, 2]],
        triangles[:, [2, 0]],
    ], axis=0)  # (3n, 2) 有向边
    t_ids = np.tile(np.arange(n, dtype=np.int64), 3)
    slots = np.repeat(np.arange(3, dtype=np.int64), n)
    lo = np.minimum(e[:, 0], e[:, 1])
    hi = np.maximum(e[:, 0], e[:, 1])
    sgn = (e[:, 0] == lo).astype(np.int8)  # 1 = 沿排序方向遍历
    key = lo * nv + hi
    order = np.argsort(key, kind="stable")
    sk = key[order]
    pairs = sk.reshape(-1, 2)
    ok = pairs[:, 0] == pairs[:, 1]

    neighbor = np.full((n, 3), -1, dtype=np.int64)
    parity = np.zeros((n, 3), dtype=np.int8)
    if not ok.all():
        # 非水密（理论不出现）：退化为逐三角形探针兜底
        return _probe_orient(vertices, triangles, inside_fn, spacing)

    ta = t_ids[order].reshape(-1, 2)[:, 0]
    tb = t_ids[order].reshape(-1, 2)[:, 1]
    sa = slots[order].reshape(-1, 2)[:, 0]
    sb = slots[order].reshape(-1, 2)[:, 1]
    da = sgn[order].reshape(-1, 2)[:, 0]
    db = sgn[order].reshape(-1, 2)[:, 1]
    p = (da == db).astype(np.int8)
    neighbor[ta, sa] = tb
    parity[ta, sa] = p
    neighbor[tb, sb] = ta
    parity[tb, sb] = p

    flip = np.zeros(n, dtype=bool)
    visited = np.zeros(n, dtype=bool)
    comp = np.full(n, -1, dtype=np.int64)
    wave_seen = np.zeros(n, dtype=bool)
    ncomp = 0
    for seed in range(n):
        if visited[seed]:
            continue
        frontier = np.array([seed], dtype=np.int64)
        visited[seed] = True
        comp[seed] = ncomp
        while frontier.size:
            nbr = neighbor[frontier]
            par = parity[frontier]
            nv_bits = (flip[frontier][:, None] ^ par).ravel()
            fn = nbr.ravel()
            unvis = (fn >= 0) & ~visited[fn]
            idx = np.flatnonzero(unvis)
            if idx.size == 0:
                break
            tgt = fn[idx]
            visited[tgt] = True
            flip[tgt] = nv_bits[idx]
            comp[tgt] = ncomp
            # 同一三角形可能经多个父节点在同波内被多次加入：用临时 bool
            # 数组去重（分配一次、按位复位，避免每波 np.unique），防止
            # 波前指数膨胀（实测 frontier 可膨胀到 4 千万+）。
            wave_seen[tgt] = True
            frontier = np.flatnonzero(wave_seen)
            wave_seen[tgt] = False
        ncomp += 1

    out = triangles.copy()
    if flip.any():
        out[flip] = out[flip][:, ::-1]

    # 分量有向体积定全局方向（法向指向区域外侧 → 体积为正）
    v0 = vertices[out[:, 0]]
    v1 = vertices[out[:, 1]]
    v2 = vertices[out[:, 2]]
    tet = np.einsum("ij,ij->i", v0, np.cross(v1, v2)) / 6.0
    vol = np.bincount(comp, weights=tet)
    neg = np.flatnonzero(vol < 0)
    if neg.size:
        mask = np.isin(comp, neg)
        out[mask] = out[mask][:, ::-1]

    degen = np.flatnonzero(
        np.abs(vol) <= 1e-14 * max(1.0, float(np.abs(vol).max()))
    )
    if degen.size and inside_fn is not None:
        mask = np.isin(comp, degen)
        out[mask] = _probe_orient(vertices, out[mask], inside_fn, spacing)
    return out


def _min_spacing(coords):
    if coords.size < 2:
        return 1.0
    d = np.diff(coords)
    d = d[np.abs(d) > 1e-300]
    if d.size == 0:
        return 1.0
    return float(np.min(np.abs(d)))


def marching_cubes(field, x, y, z, inside_fn=None):
    """二值场 → 水密三角形网格（纯 numpy）。

    参数
    ----
    field:
        ``(nx, ny, nz)`` 布尔数组，True=区域内部。
    x, y, z:
        三轴网格节点坐标，长度分别为 nx/ny/nz。
    inside_fn:
        可选 ``f(x, y, z) -> bool 数组``，仅退化分量兜底时使用。

    返回
    ----
    ``(vertices, triangles)``：空网格为 ``(shape(0,3), shape(0,3))``。
    """
    field = np.asarray(field) > 0
    if field.ndim != 3:
        raise ValueError("field 必须是 3 维数组")
    nx, ny, nz = field.shape
    if min(nx, ny, nz) < 2:
        return np.empty((0, 3), dtype=float), np.empty((0, 3), dtype=np.int64)

    xs = np.asarray(x, dtype=float).ravel()
    ys = np.asarray(y, dtype=float).ravel()
    zs = np.asarray(z, dtype=float).ravel()
    if xs.size != nx or ys.size != ny or zs.size != nz:
        raise ValueError("x/y/z 长度必须与 field 维度一致")

    dx_c = np.array([0, 1, 1, 0, 0, 1, 1, 0], dtype=np.intp)
    dy_c = np.array([0, 0, 1, 1, 0, 0, 1, 1], dtype=np.intp)
    dz_c = np.array([0, 0, 0, 0, 1, 1, 1, 1], dtype=np.intp)

    ii = np.arange(nx - 1)
    jj = np.arange(ny - 1)
    ix, iy = np.meshgrid(ii, jj, indexing="ij")
    ixf = ix.ravel()
    iyf = iy.ravel()
    n_xy = ixf.size
    if n_xy == 0:
        return np.empty((0, 3), dtype=float), np.empty((0, 3), dtype=np.int64)

    # 每个 (x,y) 立方体位置预先算好 8 个角点的 x/y 坐标；z 按层分块叠加。
    cell_xy = np.empty((n_xy, 8, 2), dtype=float)
    cell_xy[:, :, 0] = xs[ixf[:, None] + dx_c[None, :]]
    cell_xy[:, :, 1] = ys[iyf[:, None] + dy_c[None, :]]

    bits = np.array([1, 2, 4, 8, 16, 32, 64, 128], dtype=np.int16)
    point_parts = []
    chunk = 4  # 每批处理 4 个 z 层，控制内存（res=128 时 4×127² 立方体）
    nz1 = nz - 1
    for k0 in range(0, nz1, chunk):
        k1 = min(k0 + chunk, nz1)
        ks = np.arange(k0, k1, dtype=np.intp)
        nk = ks.size
        # 8 个角点布尔值 → (n_xy, nk, 8) → (nk*n_xy, 8)
        cube = np.stack(
            [field[ixf[:, None] + dx_c[c], iyf[:, None] + dy_c[c],
                   ks[None, :] + dz_c[c]]
             for c in range(8)],
            axis=-1,
        )
        cube = np.moveaxis(cube, 1, 0).reshape(nk * n_xy, 8)
        cases = (cube.astype(np.int16) * bits[None, :]).sum(axis=1)
        counts = _CASE_COUNTS[cases]
        active = counts > 0
        if not active.any():
            continue

        # 只处理含边界三角形的活跃栅元（球面约占 1/3，省 2/3 计算）
        sub = np.flatnonzero(active)
        k_sub = sub // n_xy
        xy_sub = sub % n_xy
        corners = np.empty((sub.size, 8, 3), dtype=float)
        corners[:, :, :2] = cell_xy[xy_sub]
        zc = zs[ks[:, None] + dz_c[None, :]]  # (nk, 8)
        corners[:, :, 2] = zc[k_sub]

        # 28 条顶点配对的中点（共享配对在相邻四面体/立方体间逐位一致）
        pair_pts = (
            corners[:, _PAIR_A, :] + corners[:, _PAIR_B, :]
        ) * 0.5  # (S, 28, 3)

        tri_flat = _CASE_TABLE[cases[sub]].reshape(sub.size * _MAX_TRIS, 3)
        valid = tri_flat[:, 0] >= 0
        tri_flat = tri_flat[valid]
        cids = np.repeat(np.arange(sub.size), _MAX_TRIS)[valid]

        v0 = pair_pts[cids, tri_flat[:, 0]]
        v1 = pair_pts[cids, tri_flat[:, 1]]
        v2 = pair_pts[cids, tri_flat[:, 2]]
        layer_tris = np.stack([v0, v1, v2], axis=1)  # (m, 3, 3)
        point_parts.append(layer_tris)

    if not point_parts:
        return np.empty((0, 3), dtype=float), np.empty((0, 3), dtype=np.int64)

    all_points = np.concatenate(point_parts, axis=0).reshape(-1, 3)
    # 顶点都是两网格点的中点：相对于网格原点的坐标 = (i+j)/2×spacing，
    # 乘以 2/间距后是精确整数 → 每轴 12 位打包成单个 int64 key 焊接
    # （1D int64 unique 远快于 2D float / 结构化 unique）。
    dx_s = _min_spacing(xs)
    dy_s = _min_spacing(ys)
    dz_s = _min_spacing(zs)
    ix2 = np.rint((all_points[:, 0] - xs[0]) / dx_s * 2.0).astype(np.int64)
    iy2 = np.rint((all_points[:, 1] - ys[0]) / dy_s * 2.0).astype(np.int64)
    iz2 = np.rint((all_points[:, 2] - zs[0]) / dz_s * 2.0).astype(np.int64)
    key = (ix2 << 24) | (iy2 << 12) | iz2
    _uniq, first, inverse = np.unique(key, return_index=True, return_inverse=True)
    vertices = all_points[first]
    triangles = inverse.reshape(-1, 3).astype(np.int64)

    spacing = min(_min_spacing(xs), _min_spacing(ys), _min_spacing(zs))
    triangles = _orient_triangles(vertices, triangles, inside_fn, spacing)
    return vertices, triangles


__all__ = ["marching_cubes"]
