# -*- coding: utf-8 -*-
"""Check depth=1 leaves (root-granule edge cells like u=30/700) distance vs outer shell r=187.96."""
import json, sys, time, urllib.request, urllib.error, math
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
# depth=1 leaves = 根格阵直接 fill 的格位（周边水/反射/baffle）
d1 = [l for l in leaves if l.get("depth") == 1]
print("depth=1 leaves:", len(d1))
over = []
from collections import Counter
for l in d1:
    d = math.hypot(l.get("x",0), l.get("y",0))
    flag = "OVER" if d > outer_r else "ok"
    if d > outer_r:
        over.append(l)
print("depth=1 OVER-shell count:", len(over))
for l in over[:30]:
    print("  u=%s cellNum=%s x=%.1f y=%.1f r=%.1f %s" % (l.get("u"), l.get("cellNum"), l.get("x"), l.get("y"),
          math.hypot(l.get("x",0), l.get("y",0)), "OVER"))
# u histogram of over
print("over u histogram:", dict(Counter(str(l.get("u")) for l in over)))
# x/y range of ALL leaves over shell
allover = [l for l in leaves if math.hypot(l.get("x",0), l.get("y",0)) > outer_r]
print("ALL leaves over-shell:", len(allover), "u hist:", dict(Counter(str(l.get("u")) for l in allover)))
