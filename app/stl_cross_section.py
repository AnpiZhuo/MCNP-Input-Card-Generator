"""
从 STL 切平面 — numpy 纯 Python 实现（不依赖 FreeCAD）。

3D 预览已为每个栅元生成 STL（含 #n 补集挖洞后的实体），截面直接读 STL
与平面求交得到多边形，返回结构与旧 FreeCAD CSG 截面一致：
    [{number, material, polygons: [{x,y,z}[]]}]

STL 是三角网格：每个三角形与平面相交最多得一条线段；全部线段按端点
相邻连接成闭合环（截面是封闭曲线）。真空/未勾选栅元的 STL 不传入。
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


def slice_stl_segments(tris: np.ndarray, A: float, B: float, C: float, D: float) -> list:
    """平面 Ax+By+Cz=D 与每个三角形求交 → 线段列表 [(p0, p1), ...]

    每个三角形 3 条边，符号变化的边产生交点；0 或 2 个交点组成 1 条线段。
    """
    nrm = np.array([A, B, C], dtype=np.float64)
    nl = np.linalg.norm(nrm)
    if nl < 1e-12:
        return []
    nv = nrm / nl
    dist = tris @ nv - (D / nl)  # (N,3) 有符号距离
    sgn = np.sign(dist)
    segs: list = []
    for i in range(tris.shape[0]):
        d = dist[i]
        sg = sgn[i]
        ints = []
        for a in range(3):
            b = (a + 1) % 3
            if sg[a] == 0:
                continue
            if sg[a] == sg[b]:
                continue
            t = d[a] / (d[a] - d[b])
            p = tris[i][a] + t * (tris[i][b] - tris[i][a])
            ints.append((float(p[0]), float(p[1]), float(p[2])))
        if len(ints) == 2:
            segs.append((ints[0], ints[1]))
    return segs


def _join_loops(segments):
    """把线段连成闭合环。每段 (p,q)，按共享端点连接；返回环列表（各环为点列表）。

    截面与封闭 STL 相交得到的是闭合折线。使用「最近未用端点优先」的贪心：
    从任一线段出发，当前端点找未用线段中端点距离最近的接上（避免在共享
    顶点/交叉处走错分支），延伸直到回到起点。
    """
    if not segments:
        return []
    # 线段索引 → 两个端点
    seg_ends = [list(s) for s in segments]
    used_seg = [False] * len(segments)
    loops = []

    def _dist(a, b):
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2

    for i in range(len(segments)):
        if used_seg[i]:
            continue
        used_seg[i] = True
        chain = [seg_ends[i][0], seg_ends[i][1]]
        cur = seg_ends[i][1]
        start = seg_ends[i][0]
        # 沿 cur 方向延伸
        while True:
            best = None
            best_d = None
            best_next = None
            for j in range(len(segments)):
                if used_seg[j]:
                    continue
                a, b = seg_ends[j]
                for cand in (a, b):
                    d = _dist(cand, cur)
                    if best_d is None or d < best_d:
                        best_d = d
                        best = j
                        best_next = b if cand is a else a
            if best is None:
                break
            used_seg[best] = True
            cur = best_next
            chain.append(cur)
            if _dist(cur, start) < 1e-9:
                break
        # 去重首尾
        while len(chain) >= 3 and chain[0] == chain[-1]:
            chain.pop()
        if len(chain) >= 3:
            loops.append(chain)
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
