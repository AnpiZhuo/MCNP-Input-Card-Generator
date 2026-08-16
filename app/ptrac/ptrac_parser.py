"""PTRAC 粒子径迹文件解析（契约 ptrac-visualization.md v2 §2）。

纯 stdlib 行解析，不依赖 numpy/pymcnp（模块顶只 stdlib）。

文件格式（MCNP PTRAC 表 I.1/I.3/I.4/I.5，实核 example_02.ptrac）：
  头：① `   -1`；② code(8)/version(25)/code_date(9)/run_datetime(18)；③ 标题(80)；
      ④ V 行（问题常数，可能多行）；⑤ N 行（20 个事件变量个数）；⑥ L 行（变量 ID 表）。
  历史：`      NPS      1000`（恰 2 个整数字段）→ 事件两行一组（字段行 + 位置行 x y z）。

L 表（变量 ID 表）驱动能量/粒子类型提取。变量 ID（MCNP PTRAC 表 I.4）：
  1=NPS 2=首事件类型 7=下一事件类型 8=NODE 9=NSR 10=NXS(2,IEX)=能量
  11=NTYN(反应类型) 12=NSF 13=过面角 14=NTER(终止类型) 15=branch
  16=IPT(粒子类型) 17=NCL(栅元) 18=MAT(材料) 19=NCP
  20/21/22=x/y/z 26=ERG(能量，WRITE=all 位置行)。

事件类型 → N/L 分组（表 I.5）：src=1000(仅 I 行 I2 指示) bnk=±(2000+l) sur=3000
col=4000 ter=5000 flag=9000（flag 复用 ter 布局，是历史末标记）。
注：历史首事件（源粒子初始事件）恒用 src 布局（n2 字段），其 J1 事件类型码
可能是 3000(面源)/4000(碰撞源)/5000(终止源)；首事件之后按 J1 码分派布局。
"""
from __future__ import annotations

# 能量变量 ID：10 = NXS(2,IEX)（碰撞/入银行事件字段行）；26 = ERG（WRITE=all 位置行）。
_ENERGY_IDS = (10, 26)
# 粒子类型变量 ID：16 = IPT。
_IPT_ID = 16

# IPT → 前端粒子类型（n=中子 / p=光子 / e=电子 / ""=其余）。
_PARTICLE_MAP = {1: "n", 2: "p", 3: "e"}


class PTRACFormatError(ValueError):
    """非 PTRAC 文件或格式不合法（第 1 行非 "-1" 或行数 <8）。"""


def _is_int(tok: str) -> bool:
    try:
        int(tok)
        return True
    except ValueError:
        return False


def _event_group(etype: int) -> str | None:
    """事件类型 → N/L 分组（表 I.5）。flag(9000) 复用 ter 布局。"""
    if etype == 1000:
        return "src"
    if 2000 <= etype <= 2999 or -2999 <= etype <= -2000:
        return "bnk"
    if etype == 3000:
        return "sur"
    if etype == 4000:
        return "col"
    if etype in (5000, 9000):
        return "ter"
    return None


def _parse_n_line(line: str) -> list[int]:
    """N 行 → 20 个整数（事件变量个数）。"""
    toks = line.split()
    if len(toks) != 20 or not all(_is_int(t) for t in toks):
        raise PTRACFormatError("不是有效的 PTRAC 文件（未找到 N 行）")
    return [int(t) for t in toks]


def _parse_l_ids(lines: list[str], n_line_idx: int, total: int) -> tuple[list[int], int]:
    """N 行之后的 L 行（变量 ID 表）→ (恰好 total 个整数 ID, 首个历史行下标)。"""
    ids: list[int] = []
    i = n_line_idx + 1
    while len(ids) < total and i < len(lines):
        for t in lines[i].split():
            if len(ids) >= total:
                break
            try:
                ids.append(int(t))
            except ValueError:
                continue
        i += 1
    if len(ids) < total:
        raise PTRACFormatError("L 行变量 ID 表不完整")
    return ids, i


def _split_l(ids: list[int], n: list[int]) -> dict:
    """按 N 行计数切分 L 表 → {src/bnk/sur/col/ter: (j_ids, p_ids)}。"""
    i = 0
    groups = {}

    def take(k: int) -> list[int]:
        nonlocal i
        seg = ids[i:i + k]
        i += k
        return seg

    take(n[0])  # I 行（NPS 行）变量 ID，本版不建模
    # 每组事件各占两个计数：1st 事件行（字段行）+ 2nd 事件行（位置行）
    # N 行顺序：n2/n3(src) n4/n5(bnk) n6/n7(sur) n8/n9(col) n10/n11(ter)
    for k, name in enumerate(("src", "bnk", "sur", "col", "ter")):
        j = take(n[1 + 2 * k])  # n2, n4, n6, n8, n10
        p = take(n[2 + 2 * k])  # n3, n5, n7, n9, n11
        groups[name] = (j, p)
    return groups


def _map_particle(ipt) -> str:
    if ipt is None:
        return ""
    return _PARTICLE_MAP.get(int(ipt), "")


def _extract_point(field_toks: list[str], pos_toks: list[str], j_ids: list[int],
                   p_ids: list[int], n12: int) -> tuple:
    """字段行 + 位置行 → (x, y, z, 事件类型, 能量, IPT)。"""
    etype = int(field_toks[0]) if field_toks and _is_int(field_toks[0]) else 0
    x = float(pos_toks[0]) if len(pos_toks) >= 1 else 0.0
    y = float(pos_toks[1]) if len(pos_toks) >= 2 else 0.0
    z = float(pos_toks[2]) if len(pos_toks) >= 3 else 0.0

    energy = 0.0
    ipt = None

    # 字段行按 ID 定位能量（ID 10）
    for fid, val in zip(j_ids, field_toks):
        if fid in _ENERGY_IDS:
            try:
                energy = float(val)
            except ValueError:
                energy = 0.0
            break
    # 位置行按 ID 定位能量（ID 26 = ERG，WRITE=all）
    if energy == 0.0:
        for fid, val in zip(p_ids, pos_toks):
            if fid in _ENERGY_IDS:
                try:
                    energy = float(val)
                except ValueError:
                    energy = 0.0
                break
    # 粒子类型（ID 16 = IPT）
    for fid, val in zip(j_ids, field_toks):
        if fid == _IPT_ID:
            try:
                ipt = int(float(val))
            except ValueError:
                ipt = None
            break
    if ipt is None and n12 != 0:
        ipt = n12

    return x, y, z, etype, energy, ipt


def _decimate_points(points: list, budget: int) -> list:
    """均匀抽稀保持首尾：points 均匀抽取至不超过 budget 个点（首尾必留）。"""
    n = len(points)
    if n <= budget or budget <= 0:
        return points
    if budget == 1:
        return [points[0], points[-1]] if n > 1 else points
    step = (n - 1) / (budget - 1)
    out = [points[0]]
    for k in range(1, budget - 1):
        idx = int(round(k * step))
        if idx >= n - 1:
            break
        if out[-1] != points[idx]:
            out.append(points[idx])
    out.append(points[-1])
    return out


def parse_ptrac(path: str, max_tracks: int = 500, max_points: int = 200000) -> dict:
    """解析 PTRAC ASCII 文件 → {header, tracks, world_box, stats, truncated}。

    契约 v2 §2：
    - header = {code, title}
    - tracks = [{nps, particle, points: [[x,y,z,type,energy], …]}]
    - world_box = {min:[x,y,z], max:[x,y,z]}
    - stats = {nps, events, points, truncated, particles:{n,p,e}}
    - max_tracks 截断历史数并标 truncated；max_points 均匀抽稀保持首尾。
    - 第 1 行非 "-1" 或行数 <8 → PTRACFormatError；文件缺失 → FileNotFoundError。
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    lines = text.splitlines()

    if len(lines) < 8:
        raise PTRACFormatError("不是有效的 PTRAC 文件（行数不足 8）")
    if lines[0].strip() != "-1":
        raise PTRACFormatError("不是有效的 PTRAC 文件（首行不是 -1，请用 FILE=ASC 生成）")

    code = lines[1].split()[0] if lines[1].split() else ""
    title = lines[2].strip()

    # 定位 N 行（20 个整数）；其前为 V 行（问题常数，10 浮点/行）
    n_line_idx = None
    n = None
    for i in range(3, len(lines)):
        toks = lines[i].split()
        if len(toks) == 20 and all(_is_int(t) for t in toks):
            n = _parse_n_line(lines[i])
            n_line_idx = i
            break
    if n is None or n_line_idx is None:
        raise PTRACFormatError("不是有效的 PTRAC 文件（未找到 N 行）")

    n12 = n[11]
    total_ids = sum(n[0:11])
    l_ids, hist_start = _parse_l_ids(lines, n_line_idx, total_ids)
    groups = _split_l(l_ids, n)

    # 解析历史
    tracks = []
    current = None
    pending_field = None  # 等待位置行的字段行 tokens
    pending_first = False  # 该字段行是否为历史首事件（源粒子初始事件，用 src 布局）
    first_of_history = False  # 当前是否在期待历史首事件
    for ln in lines[hist_start:]:
        toks = ln.split()
        if not toks:
            continue
        if pending_field is not None:
            # 位置行：x y z（3 个浮点）
            try:
                pos = [toks[0], toks[1], toks[2]]
                float(pos[0]), float(pos[1]), float(pos[2])
            except (ValueError, IndexError):
                pending_field = None
                continue
            etype = int(pending_field[0]) if _is_int(pending_field[0]) else 0
            # 历史首事件恒为源粒子初始事件（src 布局），其 J1 事件类型码可能是
            # 3000(面源)/4000(碰撞源)/5000(终止源)；后续事件按 J1 码分派布局。
            if pending_first:
                gname = "src"
            else:
                gname = _event_group(etype)
            j_ids, p_ids = groups.get(gname, ([], [])) if gname else ([], [])
            x, y, z, etype, energy, ipt = _extract_point(pending_field, pos, j_ids, p_ids, n12)
            if current is not None:
                current["points"].append([x, y, z, etype, energy])
                if current["particle"] is None:
                    current["particle"] = _map_particle(ipt)
            pending_field = None
            pending_first = False
            continue
        # 历史起始行：恰 2 个整数字段
        if len(toks) == 2 and _is_int(toks[0]) and _is_int(toks[1]):
            current = {"nps": int(toks[0]), "particle": None, "points": []}
            tracks.append(current)
            first_of_history = True
            continue
        # 字段行：首字段为整数事件类型
        if _is_int(toks[0]):
            pending_field = toks
            pending_first = first_of_history
            first_of_history = False
            continue
        # 其它行（续行等）忽略

    # max_tracks 截断
    truncated = len(tracks) > max_tracks
    if truncated:
        tracks = tracks[:max_tracks]

    total_events = sum(len(t["points"]) for t in tracks)
    nps_count = len(tracks)

    # max_points 均匀抽稀（按轨预算比例）
    if max_points > 0 and total_events > max_points:
        for t in tracks:
            if not t["points"]:
                continue
            budget = max(1, int(max_points * len(t["points"]) / total_events))
            t["points"] = _decimate_points(t["points"], budget)

    # world_box
    xs = [p[0] for t in tracks for p in t["points"]]
    ys = [p[1] for t in tracks for p in t["points"]]
    zs = [p[2] for t in tracks for p in t["points"]]
    world_box = {
        "min": [min(xs) if xs else 0.0, min(ys) if ys else 0.0, min(zs) if zs else 0.0],
        "max": [max(xs) if xs else 0.0, max(ys) if ys else 0.0, max(zs) if zs else 0.0],
    }

    # 粒子类型计数
    particles = {"n": 0, "p": 0, "e": 0}
    for t in tracks:
        key = t.get("particle")
        if key in particles:
            particles[key] += 1

    points_after = sum(len(t["points"]) for t in tracks)
    return {
        "header": {"code": code, "title": title},
        "tracks": tracks,
        "world_box": world_box,
        "stats": {
            "nps": nps_count,
            "events": total_events,
            "points": points_after,
            "truncated": truncated,
            "particles": particles,
        },
        "truncated": truncated,
    }
