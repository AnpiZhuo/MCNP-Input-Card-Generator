#!/usr/bin/env python3
"""单变量实验：逐项还原程序版相对原生版的 SDEF/SI/SP 改动，找出元凶。
"""
import os, re, subprocess, shutil

MCNP_EXE = r"D:\MCNP\MCNP6\MCNP_CODE\bin\mcnp6.exe"
SRC_DIR = r"D:\MCNP\new\q1112_repro"
BASE = r"D:\MCNP\new\q1112_bisect"
NPS = 3000

native_text = open(os.path.join(SRC_DIR, "dsh_native_q1112.txt"), encoding="utf-8").read()
prog_text = open(os.path.join(SRC_DIR, "dsh_prog_q1112.txt"), encoding="utf-8").read()

# 注意 native 原文（q1112.txt）里是 CRLF；此处读入已被转成 \n（newline='' 写回的文件是 \n）

variants = {}

# E1: prog 去掉 SI 插值码 + 恢复 sp3 d
t = prog_text
t = t.replace("SI1  L  0.0  1.335", "si1 0.0 1.335")
t = t.replace("SI2  L  -5.5  5.5", "si2 -5.5 5.5")
t = t.replace("SI3  H", "si3 h")
t = t.replace("SP3  0  0.03696", "sp3 d 0 0.03696")
variants["E1_prog_nocode_plus_d"] = t

# E2: native 只加 si1/si2 的 L 码
t = native_text.replace("si1 0.0 1.335", "si1 L 0.0 1.335").replace("si2 -5.5 5.5", "si2 L -5.5 5.5")
variants["E2_native_plus_L_codes"] = t

# E3: native 只去掉 sp3 的 d
t = native_text.replace("sp3 d 0 0.03696", "sp3 0 0.03696")
variants["E3_native_minus_d"] = t

# E4: prog 只恢复 sp3 d（SI 码保留）
t = prog_text.replace("SP3  0  0.03696", "SP3  d  0  0.03696")
variants["E4_prog_plus_d"] = t

# E5: native 把 sdef/si/sp 整段换成 prog 的写法（除了 & 续行尽量接近）
t = native_text
t = t.replace("sdef par=n erg=d3 pos=0.65 0.0 -21.5 cel=5 rad=d1 ext=d2 axs=0 0 1",
              "SDEF  POS=0.65 0.0 -21.5  PAR=n  ERG=d3  CEL=5  AXS=0 0 1  RAD=d1  EXT=d2")
t = t.replace("si1 0.0 1.335", "SI1  L  0.0  1.335")
t = t.replace("si2 -5.5 5.5", "SI2  L  -5.5  5.5")
variants["E5_native_full_sdef_rewrite"] = t

def run(tag, text):
    d = os.path.join(BASE, tag)
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    text = re.sub(r"(?im)^\s*(nps|NPS)\s+\d+.*$", f"nps {NPS}", text)
    inp = os.path.join(d, "inp.i")
    with open(inp, "w", encoding="utf-8") as f:
        f.write(text)
    bat = os.path.join(d, "run.bat")
    with open(bat, "w", encoding="utf-8") as f:
        f.write(f'@echo off\r\ncall "{MCNP_EXE}" inp=inp.i outp=inp.o\r\n')
    subprocess.run(["cmd.exe", "/c", bat], cwd=d, capture_output=True, text=True, timeout=240)
    o = ""
    if os.path.exists(os.path.join(d, "inp.o")):
        o = open(os.path.join(d, "inp.o"), encoding="utf-8", errors="replace").read()
    lost = "particles got lost" in o
    srcwarn = o.count("source point is not in the source cell")
    done = "run terminated when" in o
    print(f"{tag:38s} lost={lost!s:5s} srcWarn={srcwarn:2d} done={done}")
    return o

for tag, text in variants.items():
    run(tag, text)
print("\n对照: native 应 done 无 lost；prog 应 lost")
