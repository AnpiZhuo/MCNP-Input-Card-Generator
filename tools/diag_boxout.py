# -*- coding: utf-8 -*-
"""For root-lattice cells, check grid-cell-box distance to origin vs shell r=187.96.
Grid-cell-box: pitch 21.5 square (half-width 10.75). A cell whose box nearest-point to
origin > shell_r is fully OUTSIDE the cylindrical core (belongs to cell 344+ not 343)."""
import json, sys, math, urllib.request, urllib.error
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
deck = p.get("deck", {}); cells = deck.get("cells", [])
payload = {"surfaces": deck.get("surfaces",""), "tr_cards": deck.get("tr_cards",""),
    "cells": [{"number": int(c.get("cell",{}).get("num","0") or 0), "material": c.get("cell",{}).get("material",""),
               "density": c.get("cell",{}).get("density",""),
               "surface_expr": c.get("cell",{}).get("surfaces","") or c.get("cell",{}).get("surface_expr",""),
               "u": c.get("cell",{}).get("u","") or "", "fill": c.get("cell",{}).get("fill","") or "",
               "lat": c.get("cell",{}).get("lat","") or "", "trcl": c.get("cell",{}).get("trcl","") or "",
               "render": c.get("cell",{}).get("render") is not False, "fill_grid": c.get("cell",{}).get("fill_grid","") or ""}
              for c in cells if c.get("kind") != "raw"]}
st2, j = post("/api/preview-lattice", payload)
leaves = j.get("leafInstances", [])
outer_r = 187.96
half = 10.75  # 根格阵格元盒半宽（pitch 21.5 / 2）

def box_nearest(cx, cy):
    # 格元盒 [cx-half, cx+half]×[cy-half, cy+half] 到原点最近距离
    nx = max(0.0, abs(cx) - half)
    ny = max(0.0, abs(cy) - half)
    return math.hypot(nx, ny)

# 根格阵 leaf (depth=1) 中，格元盒完全在圆柱外的
outside = []
for l in leaves:
    d = box_nearest(l.get("x",0), l.get("y",0))
    if d > outer_r:
        outside.append(l)
print("root cells whose grid-box fully OUTSIDE shell (nearest>187.96):", len(outside))
from collections import Counter
print("u hist:", dict(Counter(str(l.get("u")) for l in outside)))
# 那些之前圆心>187.96 但格元盒仍有部分在圆柱内（应保留并按圆柱裁剪）的格位
partly = []
for l in leaves:
    if l.get("depth") != 1:
        continue
    cx, cy = l.get("x",0), l.get("y",0)
    cent = math.hypot(cx, cy)
    nearest = box_nearest(cx, cy)
    if cent > outer_r and nearest <= outer_r:
        partly.append((cent, nearest, l.get("u")))
print("cells with center>187.96 but box PARTLY inside (retain):", len(partly))
for c in partly[:15]:
    print("   cent=%.0f nearest=%.0f u=%s" % (c[0], c[1], c[2]))
