# -*- coding: utf-8 -*-
"""Full-chain leaf dump over HTTP (uses real _resolved_extent)."""
import json, sys, time, urllib.request, urllib.error
BASE = "http://127.0.0.1:5001"
def post(path, payload, timeout=300):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE+path, data=data, headers={"Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, {"_raw": e.read().decode("utf-8","replace")[:400]}

inp = open(r"D:\MCNP\输入卡生成器源码\gui\public\examples\beavrs_fullcore_mcnp.i", encoding="utf-8").read()
st, p = post("/api/parse-inp", {"inp": inp})
deck = p.get("deck", {})
cells = deck.get("cells", [])
payload = {"surfaces": deck.get("surfaces",""), "tr_cards": deck.get("tr_cards",""),
    "cells": [{"number": int(c.get("cell",{}).get("num","0") or 0),
               "material": c.get("cell",{}).get("material",""), "density": c.get("cell",{}).get("density",""),
               "surface_expr": c.get("cell",{}).get("surfaces","") or c.get("cell",{}).get("surface_expr",""),
               "u": c.get("cell",{}).get("u","") or "", "fill": c.get("cell",{}).get("fill","") or "",
               "lat": c.get("cell",{}).get("lat","") or "", "trcl": c.get("cell",{}).get("trcl","") or "",
               "render": c.get("cell",{}).get("render") is not False, "fill_grid": c.get("cell",{}).get("fill_grid","") or ""}
              for c in cells if c.get("kind") != "raw"]}
t0=time.time(); st2, j = post("/api/preview-lattice", payload); dt=time.time()-t0
print("preview", st2, "t=%.1fs"%dt, "count", j.get("count"), "detail", (j.get("fidelity") or {}).get("detail"))

# 每个 lattice 的绝对定位：positions 是相对自身原点，但嵌套格阵由父格位定位。
# 这里打印 leafInstances 绝对坐标分布（前端真正渲染的）。
leaves = j.get("leafInstances", [])
if not leaves:
    print("no leafInstances (auto overview)")
    for lt in j.get("lattices", []) or []:
        pos = lt.get("positions", [])
        zs=[p.get("z") for p in pos if p.get("z") is not None]
        print("  lat num=%s npos=%d zrange=(%s,%s) pitch=%s" % (lt.get("num"), len(pos),
              min(zs) if zs else None, max(zs) if zs else None, lt.get("pitch")))
else:
    xs=[l.get("x") for l in leaves]; ys=[l.get("y") for l in leaves]; zs=[l.get("z") for l in leaves]
    print("LEAF n=%d xrange=(%.1f,%.1f) yrange=(%.1f,%.1f) zrange=(%.1f,%.1f)" % (
        len(leaves), min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
    # z 分布桶
    zb={}
    for l in leaves: zb[round(l.get("z",0),1)]=zb.get(round(l.get("z",0),1),0)+1
    print("LEAF z buckets (z:count):", sorted(zb.items(), key=lambda kv:-kv[1])[:10])
    # depth 分布
    print("LEAF depth histogram:", dict((str(d), sum(1 for l in leaves if l.get("depth")==d)) for d in sorted(set(l.get("depth") for l in leaves))))
    # 每个 component lattice 的绝对 z 参考：leaf x/y 唯一值分布
    print("LEAF distinct x:", len(set(round(x,2) for x in xs)), "distinct y:", len(set(round(y,2) for y in ys)), "distinct z:", len(set(round(z,2) for z in zs)))
    # 按 (x,y) 网格分析：2D 平面上多少不同列/行位置（验证 pin 是否 17x17 铺开而非塌缩成几排）
    grid = {}
    for l in leaves:
        grid[(round(l["x"],2), round(l["y"],2))] = grid.get((round(l["x"],2), round(l["y"],2)), 0) + 1
    print("LEAF distinct (x,y) positions:", len(grid))
    # 按 y 值分桶看每"行"的 x 数量（诊断是否横向塌缩）
    yb = {}
    for l in leaves:
        yb[round(l["y"],2)] = yb.get(round(l["y"],2), 0) + 1
    print("LEAF y rows (y:count) top:", sorted(yb.items(), key=lambda kv:-kv[1])[:8])
