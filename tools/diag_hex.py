# -*- coding: utf-8 -*-
"""Analyze a hexagonal (lat=2) lattice INP via the running backend preview-lattice.

Reads P:\\dekstop\\u233-comp-therm-001-case-6.i, parses, and prints the lattice
structure + leaf instances + fidelity so we can see how the 3D preview renders it.
"""
import json, os, time, urllib.request, urllib.error
from collections import Counter

BASE = os.environ.get("MCNP_DIAG_BASE", "http://127.0.0.1:5001")
INP_PATH = r"P:\dekstop\u233-comp-therm-001-case-6.i"

def post(path, payload, timeout=240):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE+path, data=data, headers={"Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, {"_raw": e.read().decode("utf-8","replace")[:600]}

def main():
    inp = open(INP_PATH, encoding="utf-8").read()
    st, p = post("/api/parse-inp", {"inp": inp})
    print("parse", st, p.get("status"), p.get("message","")[:100])
    deck = p.get("deck", {}); cells = deck.get("cells", [])
    print("cells", len(cells))
    payload = {"surfaces": deck.get("surfaces",""), "tr_cards": deck.get("tr_cards",""),
        "cells": [{"number": int(c.get("cell",{}).get("num","0") or 0), "material": c.get("cell",{}).get("material",""),
                   "density": c.get("cell",{}).get("density",""),
                   "surface_expr": c.get("cell",{}).get("surfaces","") or c.get("cell",{}).get("surface_expr",""),
                   "u": c.get("cell",{}).get("u","") or "", "fill": c.get("cell",{}).get("fill","") or "",
                   "lat": c.get("cell",{}).get("lat","") or "", "trcl": c.get("cell",{}).get("trcl","") or "",
                   "render": c.get("cell",{}).get("render") is not False, "fill_grid": c.get("cell",{}).get("fill_grid","") or ""}
                  for c in cells if c.get("kind") != "raw"]}
    t0=time.time()
    st2, j = post("/api/preview-lattice", payload)
    print("preview-lattice", st2, "t=%.1fs" % (time.time()-t0))
    if j.get("status")=="error":
        print("ERR", str(j.get("message"))[:400]); return
    print("count", j.get("count"), "detailViable", j.get("detailViable"), "fidelity", j.get("fidelity"))
    print("limit", j.get("limit"), "outer_bound", j.get("outer_bound"))
    lattices = j.get("lattices", [])
    print("---- lattices:", len(lattices))
    for lt in lattices:
        print("  lat num=%s lat=%s kind=%s dims=%s pitch=%s height=%s trcl=%s" % (
            lt.get("num"), lt.get("lat"), lt.get("kind"), lt.get("dims"),
            lt.get("pitch"), lt.get("height"), lt.get("trclRotationDeg")))
        posu = Counter(str(p.get("u")) for p in lt.get("positions", []))
        print("     positions count=%d  u histogram=%s" % (len(lt.get("positions",[])), dict(posu)))
        print("     universes STL keys=%s" % sorted(lt.get("universes", {}).keys()))
    leaves = j.get("leafInstances", [])
    print("---- leafInstances=%d" % len(leaves))
    uc = Counter(str(l.get("u")) for l in leaves)
    print("leaf u histogram:", dict(uc))
    # sample the first ~40 leaf positions (hex centers) for u=1 (seed) to see hex layout
    s1 = [l for l in leaves if str(l.get("u"))=="1" or str(l.get("u"))=="2"]
    print("seed/blanket leaves:", len(s1))
    for l in s1[:24]:
        print("   u=%s x=%7.2f y=%7.2f z=%7.2f cell=%s" % (l.get("u"), l.get("x"), l.get("y"), l.get("z"), l.get("cellNum")))
    # x/y range
    if leaves:
        xs=[l.get("x",0) for l in leaves]; ys=[l.get("y",0) for l in leaves]; zs=[l.get("z",0) for l in leaves]
        print("x %.2f..%.2f  y %.2f..%.2f  z %.2f..%.2f" % (min(xs),max(xs),min(ys),max(ys),min(zs),max(zs)))

if __name__=="__main__":
    main()
