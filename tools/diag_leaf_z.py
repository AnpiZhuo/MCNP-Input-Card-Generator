# -*- coding: utf-8 -*-
"""Print leaf z distribution for key universes + compare to STL local z span."""
import json, os, urllib.request, urllib.error
from collections import Counter

BASE = os.environ.get("MCNP_DIAG_BASE", "http://127.0.0.1:5001")
def post(path, payload, timeout=240):
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
print("count", j.get("count"), "fidelity", j.get("fidelity"))

# z distribution grouped by universe
def zstats(us):
    zz = [l.get("z",0) for l in leaves if str(l.get("u")) in us and str(l.get("u")) != "708"]
    if not zz: 
        print("  no leaves for", us); return
    c = Counter(round(z,1) for z in zz)
    print("  z values:", dict(sorted(c.items())))
    print("  z min/max: %.2f / %.2f  count=%d" % (min(zz), max(zz), len(zz)))

print("== u in [1,3] (fuel pins):")
zstats({"1","3"})
print("== u in [12] (guide):")
zstats({"12"})
print("== u in [700,703] (baffle/reflector):")
zstats({"700","703"})
# x/y range
xy = [(l.get("x",0), l.get("y",0)) for l in leaves]
if xy:
    print("x range %.2f..%.2f  y range %.2f..%.2f" % (
        min(x[0] for x in xy), max(x[0] for x in xy),
        min(x[1] for x in xy), max(x[1] for x in xy)))
