"""
从 STL 切平面 — numpy 纯 Python 实现（不依赖 FreeCAD）。

3D 预览已为每个栅元生成 STL（含 #n 补集挖洞后的实体），截面直接读 STL
与平面求交得到多边形，返回结构与旧 FreeCAD CSG 截面一致：
    [{number, material, polygons: [{x,y,z}[]]}]

STL 是三角网格：每个三角形与平面相交最多得一条线段；全部线段按端点
相邻连接成闭合环（截面是封闭曲线）。真空/未勾选栅元的 STL 不传入。

2026-08-18 修复（用户实测：3D 预览切截面部分实体切错）：
1. 切割平面与实体面重合（face-coincident）时，on-plane 顶点不再被跳过，
   共面三角面贡献其外轮廓边，返回正确的面轮廓环；
2. 环连接改为容差吸附邻接表走环：多环截面（带孔/多连通实体）不会因
   最近点贪心而被串接成错误折线。
"""
import struct
import numpy as np


def parse_binary_stl(data: bytes) -> np.ndarray:
    """解析二进制 STL → (N,3,3) 顶点数组（每三角形三顶点）"""
    n = struct.unpack("<I", data[80:84])[0]
    tris = np.zeros((n, 3, 3), dtype=np.float64)
    off = 84
    for i in range(n):
        # 跳过法向(12B)，取 3 顶点(36B)，跳过属性(2B)
        tris[i] = np.frombuffer(data[off + 12:off + 48], dtype="<f4").reshape(3, 3)
        off += 50
    return tris


def parse_stl_file(path: str) -> np.ndarray:
    with open(path, "rb") as f:
        data = f.read()
    return parse_binary_stl(data)


def _scale_epsilon(tris: np.ndarray) -> float:
    """按网格尺度取“在平面上”的容差（相对 1e-6，下限 1e-9）。"""
    if tris.size == 0:
        return 1e-9
    return max(1e-9, 1e-6 * max(1.0, float(np.max(np.abs(tris)))))


def slice_stl_segments(tris: np.ndarray, A: float, B: float, C: float, D: float) -> list:
    """平面 Ax+By+Cz=D 与三角形网格求交 → 线段列表 [(p0, p1), ...]

    - 跨平面三角形：符号变化的边产生交点；恰在平面上的顶点也作为交点
      （此前 `sg[a] == 0: continue` 会丢掉面重合切割的全部线段）；
    - 整面落在平面上的共面三角形：只贡献出现 1 次的外轮廓边（内部共享
      边出现 2 次，丢弃），再经 _join_loops 全局去重。
    """
    nrm = np.array([A, B, C], dtype=np.float64)
    nl = np.linalg.norm(nrm)
    if nl < 1e-12:
        return []
    nv = nrm / nl
    dist = tris @ nv - (D / nl)  # (N,3) 有符号距离
    eps = _scale_epsilon(tris)
    sgn = np.where(dist > eps, 1, np.where(dist < -eps, -1, 0))  # 1 / -1 / 0(on)
    segs: list = []
    coplanar_edge_count: dict = {}
    for i in range(tris.shape[0]):
        d = dist[i]
        sg = sgn[i]
        tri = tris[i]
        if sg[0] == 0 and sg[1] == 0 and sg[2] == 0:
            # 面整体落在切割平面上：累计共面边（外轮廓出现 1 次）
            for a in range(3):
                b = (a + 1) % 3
                key = (tuple(tri[a]), tuple(tri[b]))
                if key[0] > key[1]:
                    key = (key[1], key[0])
                coplanar_edge_count[key] = coplanar_edge_count.get(key, 0) + 1
            continue
        ints = []
        for a in range(3):
            b = (a + 1) % 3
            if sg[a] == sg[b]:
                continue
            if sg[a] == 0:
                p = tri[a]
            elif sg[b] == 0:
                p = tri[b]
            else:
                t = d[a] / (d[a] - d[b])
                p = tri[a] + t * (tri[b] - tri[a])
            ints.append(p)
        # 三角形内容差去重（共享顶点/边交点可能重复收集）
        uniq = []
        for p in ints:
            if not any(np.linalg.norm(p - q) < eps for q in uniq):
                uniq.append(p)
        if len(uniq) >= 2:
            segs.append((tuple(uniq[0]), tuple(uniq[1])))
    # 共面面外轮廓边（出现 1 次的边）
    for (a, b), cnt in coplanar_edge_count.items():
        if cnt == 1:
            segs.append((a, b))
    return segs


def _join_loops(segments, tol: float = None):
    """把线段连成闭合环。每段 (p,q)，按共享端点连接；返回环列表（各环为点列表）。

    截面与封闭 STL 相交得到的是闭合折线。先把端点按容差吸附去重，再沿
    邻接表走环：正常封闭网格中每个截面环上的端点度数恰为 2，从任一边
    出发沿未用边走即可闭合，环与环互不串接。开放链（非水密 STL 或退化
    输入）直接丢弃，不产出错误折线。
    """
    if not segments:
        return []
    if tol is None:
        scale = 0.0
        for a, b in segments:
            for p in (a, b):
                for v in p:
                    scale = max(scale, abs(v))
        tol = max(1e-9, 1e-6 * max(1.0, scale))

    snap_pts: dict = {}

    def snap(p) -> tuple:
        k = (round(p[0] / tol), round(p[1] / tol), round(p[2] / tol))
        if k not in snap_pts:
            snap_pts[k] = (float(p[0]), float(p[1]), float(p[2]))
        return k

    # 全局线段去重（端点无序）：共面外轮廓边与跨平面三角形可能重复贡献同一段
    edge_map: dict = {}
    for a, b in segments:
        ka, kb = snap(a), snap(b)
        if ka == kb:
            continue
        key = (ka, kb) if ka < kb else (kb, ka)
        edge_map[key] = (ka, kb)
    edges = list(edge_map.values())
    if not edges:
        return []

    adj: dict = {}
    for idx, (ka, kb) in enumerate(edges):
        adj.setdefault(ka, []).append((idx, kb))
        adj.setdefault(kb, []).append((idx, ka))

    used = [False] * len(edges)
    loops = []
    for i in range(len(edges)):
        if used[i]:
            continue
        ka, kb = edges[i]
        used[i] = True
        chain = [ka, kb]
        while True:
            tail = chain[-1]
            nxt = None
            for ei, other in adj.get(tail, []):
                if not used[ei]:
                    nxt = (ei, other)
                    break
            if nxt is None:
                break
            used[nxt[0]] = True
            chain.append(nxt[1])
            if nxt[1] == chain[0]:
                break
        # 只保留闭合环（≥3 个不同点），开放链丢弃
        if len(chain) >= 4 and chain[0] == chain[-1]:
            chain.pop()
            loops.append([snap_pts[k] for k in chain])
    return loops


def cross_section_from_stl(stl_path: str, A: float, B: float, C: float, D: float) -> list:
    """读 STL 文件，切平面，返回多边形顶点列表（[{x,y,z}[]] 兼容前端格式）。"""
    try:
        tris = parse_stl_file(stl_path)
    except Exception:
        return []
    segs = slice_stl_segments(tris, A, B, C, D)
    loops = _join_loops(segs)
    out = []
    for loop in loops:
        # 只保留非共线的点，去重闭合首尾
        pts = [{"x": p[0], "y": p[1], "z": p[2]} for p in loop]
        if len(pts) >= 3:
            out.append(pts)
    return out
