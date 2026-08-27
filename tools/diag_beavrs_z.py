import json, sys, urllib.request, urllib.error, time
BASE = "http://127.0.0.1:5001"
def post(path, payload, timeout=300):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE+path, data=data, headers={"Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, {"_raw": e.read().decode("utf-8","replace")[:500]}
    except Exception as e:
        return None, {"_err": str(e)}

inp = open(r"D:\MCNP\输入卡生成器源码\gui\public\examples\beavrs_fullcore_mcnp.i", encoding="utf-8").read()
st, p = post("/api/parse-inp", {"inp": inp})
print("parse", st, p.get("status"), p.get("message",""))
deck = p.get("deck", {})
cells = deck.get("cells", [])
print("n_cells", len(cells))
# preview-lattice payload 同 Preview3D.tsx（c["cell"] 已是展平 cell）
payload = {
    "surfaces": deck.get("surfaces",""),
    "tr_cards": deck.get("tr_cards",""),
    "cells": [
        {
            "number": int(c.get("cell",{}).get("num","0") or 0),
            "material": c.get("cell",{}).get("material",""),
            "density": c.get("cell",{}).get("density",""),
            "surface_expr": c.get("cell",{}).get("surfaces","") or c.get("cell",{}).get("surface_expr",""),
            "u": c.get("cell",{}).get("u","") or "",
            "fill": c.get("cell",{}).get("fill","") or "",
            "lat": c.get("cell",{}).get("lat","") or "",
            "trcl": c.get("cell",{}).get("trcl","") or "",
            "render": c.get("cell",{}).get("render") is not False,
            "fill_grid": c.get("cell",{}).get("fill_grid","") or "",
        }
        for c in cells if c.get("kind") != "raw"
    ],
}
t0 = time.time()
st2, j = post("/api/preview-lattice", payload)
dt = time.time()-t0
print("preview", st2, "t=%.1fs"%dt)
print("limit", j.get("limit"), "count", j.get("count"), "detailViable", j.get("detailViable"))
print("outer_bound", j.get("outer_bound"))
lattices = j.get("lattices", [])
print("n_lattices", len(lattices))
if lattices:
    lt = lattices[0]
    print("primary lat:", lt.get("num"), "lat", lt.get("lat"), "dims", lt.get("dims"),
          "pitch", lt.get("pitch"), "height", lt.get("height"))
    print("primary extent:", lt.get("extent"))
    pos = lt.get("positions", [])
    zs = [pp.get("z") for pp in pos if pp.get("z") is not None]
    print("positions n", len(pos), "z range", (min(zs), max(zs)) if zs else None,
          "z first few", zs[:3], "z mid", (min(zs)+max(zs))/2 if zs else None)
    ymin = min((pp.get("y") for pp in pos if pp.get("y") is not None), default=None)
    ymax = max((pp.get("y") for pp in pos if pp.get("y") is not None), default=None)
    xmin = min((pp.get("x") for pp in pos if pp.get("x") is not None), default=None)
    xmax = max((pp.get("x") for pp in pos if pp.get("x") is not None), default=None)
    print("x range", (round(xmin,2),round(xmax,2)) if xmin is not None else None,
          "y range", (round(ymin,2),round(ymax,2)) if ymin is not None else None)
leaf = j.get("leafInstances", [])
lzs = [ll.get("z") for ll in leaf if ll.get("z") is not None]
print("leafInstances n", len(leaf), "z range", (round(min(lzs),2), round(max(lzs),2)) if lzs else None)
