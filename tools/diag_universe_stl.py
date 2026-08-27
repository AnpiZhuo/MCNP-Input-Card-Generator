# -*- coding: utf-8 -*-
"""Decode every universe STL from the RUNNING backend preview-lattice response.

For each lattice, for each universe, decode (base64) STL and report:
  ntri  = triangle count
  bbox  = (minx,miny,minz)-(maxx,maxy,maxz)
This is exactly the geometry the frontend renders as InstancedMesh (disc mode
uses universeStl[u][cellNum], clipped to cell box AND container cell).
"""
import json, sys, time, urllib.request, urllib.error, base64, struct
from collections import Counter

import os
BASE = os.environ.get("MCNP_DIAG_BASE", "http://127.0.0.1:5001")

def post(path, payload, timeout=300):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE+path, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, {"_raw": e.read().decode("utf-8", "replace")[:500]}

def stl_bbox(raw: bytes):
    """Parse binary STL (FreeCAD): 80-byte header, uint32 ntri, then 50 bytes/tri.
    Return (ntri, minpt, maxpt)."""
    if len(raw) < 84:
        return (0, None, None)
    ntri = struct.unpack("<I", raw[80:84])[0]
    mn = [float("inf")]*3
    mx = [-float("inf")]*3
    off = 84
    for _ in range(ntri):
        if off + 50 > len(raw):
            break
        # normal(3f) + v1(3f) v2(3f) v3(3f) + attr(2B) = 50 bytes
        v = struct.unpack_from("<9f", raw, off+12)  # 3 vertex coords = 9 floats
        for k in range(9):
            a = v[k]
            if a < mn[k % 3]:
                mn[k % 3] = a
            if a > mx[k % 3]:
                mx[k % 3] = a
        off += 50
    return (ntri, mn, mx)

def main():
    # load BEAVRS inp
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
    t0 = time.time()
    st2, j = post("/api/preview-lattice", payload)
    print("preview-lattice", st2, "t=%.1fs" % (time.time()-t0))
    if j.get("status") == "error":
        print("ERR", j.get("message")); return
    print("count", j.get("count"), "fidelity", j.get("fidelity"))
    lattices = j.get("lattices", [])
    print("---- lattices:", len(lattices))
    for lt in lattices:
        print("  lat num=%s kind=%s dims=%s pitch=%s" % (
            lt.get("num"), lt.get("kind"), lt.get("dims"), lt.get("pitch")))
        upos = Counter(str(p.get("u")) for p in lt.get("positions", []))
        print("     positions.u histogram:", dict(upos))
        print("     universes STL keys:", sorted(lt.get("universes", {}).keys()))
        for u in lt.get("universes", {}):
            stls = lt["universes"][u]
            for cn, b64 in stls.items():
                raw = base64.b64decode(b64)
                ntri, mn, mx = stl_bbox(raw)
                if mn is None:
                    print("    u=%s cell=%s ntri=%d (NO BBOX)" % (u, cn, ntri)); continue
                dim = [mx[k]-mn[k] for k in range(3)]
                print("    u=%-3s cell=%-4s ntri=%-5d  bbox=(%7.2f,%7.2f,%7.2f)-(%7.2f,%7.2f,%7.2f)  dim=(%.3f,%.3f,%.3f)" % (
                    u, cn, ntri, mn[0], mn[1], mn[2], mx[0], mx[1], mx[2], dim[0], dim[1], dim[2]))
    # leaf universe histogram full
    uc = Counter(str(l.get("u")) for l in j.get("leafInstances", []))
    print("---- leafInstances by universe (full):", dict(uc))

if __name__ == "__main__":
    main()
