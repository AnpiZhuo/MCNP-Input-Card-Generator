#!/usr/bin/env python3
"""细分：si1 L 单独 vs si2 L 单独 哪个破坏。
"""
import os, re, subprocess, shutil

MCNP_EXE = r"D:\MCNP\MCNP6\MCNP_CODE\bin\mcnp6.exe"
SRC_DIR = r"D:\MCNP\new\q1112_repro"
BASE = r"D:\MCNP\new\q1112_bisect2"
NPS = 3000

native_text = open(os.path.join(SRC_DIR, "dsh_native_q1112.txt"), encoding="utf-8").read()

variants = {
    "E6_native_only_si1_L": native_text.replace("si1 0.0 1.335", "si1 L 0.0 1.335"),
    "E7_native_only_si2_L": native_text.replace("si2 -5.5 5.5", "si2 L -5.5 5.5"),
    "E8_native_lower_l_both": native_text.replace("si1 0.0 1.335", "si1 l 0.0 1.335")
                                   .replace("si2 -5.5 5.5", "si2 l -5.5 5.5"),
}

def run(tag, text):
    d = os.path.join(BASE, tag)
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    text = re.sub(r"(?im)^\s*(nps|NPS)\s+\d+.*$", f"nps {NPS}", text)
    with open(os.path.join(d, "inp.i"), "w", encoding="utf-8") as f:
        f.write(text)
    with open(os.path.join(d, "run.bat"), "w", encoding="utf-8") as f:
        f.write(f'@echo off\r\ncall "{MCNP_EXE}" inp=inp.i outp=inp.o\r\n')
    subprocess.run(["cmd.exe", "/c", bat := os.path.join(d, "run.bat")], cwd=d, capture_output=True, text=True, timeout=240)
    o = ""
    fp = os.path.join(d, "inp.o")
    if os.path.exists(fp):
        o = open(fp, encoding="utf-8", errors="replace").read()
    lost = "particles got lost" in o
    srcwarn = o.count("source point is not in the source cell")
    done = "run terminated when" in o
    print(f"{tag:28s} lost={lost!s:5s} srcWarn={srcwarn:2d} done={done}")
    # 若 broken，打出前 2 个丢粒子源坐标
    if lost:
        for m in list(re.finditer(r"lost particle no\.", o))[:1]:
            i = m.start()
            print("   ctx:", o[max(0,i-420):i+260].replace("\n"," | "))
    return o

for tag, text in variants.items():
    run(tag, text)
