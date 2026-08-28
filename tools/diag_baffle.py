# -*- coding: utf-8 -*-
"""Dump baffle leaf (x,y) positions by universe to verify the 围板 ring is complete."""
import json, os, urllib.request, urllib.error
from collections import defaultdict

BASE = os.environ.get("MCNP_DIAG_BASE", "http://127.0.0.1:5999")
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
print("count", j.get("count"))

baffle = [l for l in leaves if str(l.get("u")) in
          ("700","701","702","703","704","705","706","707","708","709","710","711")]
print("baffle leaves:", len(baffle))
by_u = defaultdict(list)
for l in baffle:
    by_u[str(l.get("u"))].append((round(l.get("x",0),1), round(l.get("y",0),1), l.get("cellNum")))
for u in ["700","701","702","703","704","705","706","707","708","709","710","711"]:
    arr = by_u.get(u, [])
    print(" u=%s (%d):" % (u, len(arr)))
    for a in sorted(arr):
        print("   x=%6.1f y=%6.1f cell=%s" % a)
