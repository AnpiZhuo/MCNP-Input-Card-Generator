#!/usr/bin/env python3
"""受控实验：native 与 prog 各自在全新独立目录跑，排除 runtpe/顺序污染。
"""
import os, subprocess, shutil, sys

MCNP_EXE = r"D:\MCNP\MCNP6\MCNP_CODE\bin\mcnp6.exe"
SRC_DIR = r"D:\MCNP\new\q1112_repro"
BASE = r"D:\MCNP\new\q1112_iso"

def run_iso(inp_src, tag, nps_override=None):
    d = os.path.join(BASE, tag)
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    text = open(inp_src, encoding="utf-8").read()
    if nps_override:
        import re
        text = re.sub(r"(?i)nps\s+\d+", f"nps {nps_override}", text)
    inp = os.path.join(d, "inp.i")
    with open(inp, "w", encoding="utf-8") as f:
        f.write(text)
    bat = os.path.join(d, "run.bat")
    with open(bat, "w", encoding="utf-8") as f:
        f.write(f'@echo off\r\ncall "{MCNP_EXE}" inp=inp.i outp=inp.o\r\n')
    r = subprocess.run(["cmd.exe", "/c", bat], cwd=d, capture_output=True, text=True, timeout=240)
    o = ""
    if os.path.exists(os.path.join(d, "inp.o")):
        o = open(os.path.join(d, "inp.o"), encoding="utf-8", errors="replace").read()
    print(f"\n===== {tag}  rc={r.returncode}  .o={len(o)} chars =====")
    for kw in ("source point is not in the source cell",
               "particles got lost",
               "run terminated when",
               "problem complete",
               "fatal error"):
        import re as _re
        hits = [m.start() for m in _re.finditer(_re.escape(kw), o, _re.I)]
        if hits:
            for h in hits[:2]:
                seg = o[max(0, h - 120): h + 160].replace("\n", " | ")
                print(f"   [{kw}] x{len(hits)} ...{seg}...")
        else:
            print(f"   [{kw}] none")
    return o

run_iso(os.path.join(SRC_DIR, "dsh_native_q1112.inp"), "native", nps_override=2000)
run_iso(os.path.join(SRC_DIR, "dsh_prog_q1112.inp"), "prog", nps_override=2000)
print("\ndone")
