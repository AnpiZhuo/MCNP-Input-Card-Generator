# -*- coding: utf-8 -*-
"""Print every lattice entry's dims/pitch/height + fidelity, full chain (real _resolved_extent)."""
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
print("preview count", j.get("count"), "fidelity", j.get("fidelity"))
# min pitch across all lattices (OWEN subPitch = min over latUniverses)
pitch_min = 1e9
for lt in j.get("lattices", []):
    pit = lt.get("pitch", [])
    px, py = pit[0] if len(pit)>0 else 1, pit[1] if len(pit)>1 else 1
    print("  lat num=%s dims=%s pitch=(%.4f,%.4f,%.4f) height=%.3f" % (
        lt.get("num"), lt.get("dims"), pit[0] if len(pit)>0 else 0, pit[1] if len(pit)>1 else 0,
        pit[2] if len(pit)>2 else 0, lt.get("height",0)))
    if px>0 and py>0:
        pitch_min = min(pitch_min, px, py)
print("min pitch across lattices (subPitch):", round(pitch_min,4))
# leaf u histogram (universe of every disc)
from collections import Counter
uc = Counter(str(l.get("u")) for l in j.get("leafInstances", []))
print("leaf u histogram top10:", dict(list(uc.most_common(10))))
