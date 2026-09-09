#!/usr/bin/env python3
"""重现 q1112.txt 两遍跑：原生 vs 程序导入-生成，交给 MCNP 对比结果。

用法: python _repro_q1112.py
输出目录: D:\\MCNP\\new\\q1112_repro\\  (全新子目录，不碰现有文件)
"""
import sys, os, subprocess

PROJ = r"D:\MCNP\输入卡生成器源码"
for p in [os.path.join(PROJ, "app"), os.path.join(PROJ, "gui", "backend")]:
    if p not in sys.path:
        sys.path.insert(0, p)

MCNP_EXE = r"D:\MCNP\MCNP6\MCNP_CODE\bin\mcnp6.exe"
SCRATCH = r"D:\MCNP\new\q1112_repro"
os.makedirs(SCRATCH, exist_ok=True)

SRC = r"P:\dekstop\q1112.txt"
raw = open(SRC, "r", encoding="utf-8").read()
print(f"[read] {SRC} {len(raw)} 字符")

# ---------- 1. 原生：仅把 nps 1e8 -> 1e4，其余逐字节保留 ----------
native_text = raw.replace("nps 100000000", "nps 10000")
assert "nps 100000000" not in native_text and "nps 10000" in native_text
with open(os.path.join(SCRATCH, "dsh_native_q1112.inp"), "w", encoding="utf-8", newline="") as f:
    f.write(native_text)

# ---------- 2. 程序链路：parse -> deck -> generate_inp_from_deck ----------
from generator.parsers import parse_inp_text
from generator.inp_generator import generate_inp_from_deck

deck, warnings = parse_inp_text(raw)
print(f"[parse] OK, warnings={len(warnings)}")
for w in warnings:
    print("   warn:", w)

prog_text = generate_inp_from_deck(deck, {})
print(f"[generate] OK, {len(prog_text)} 字符")
# 同样把 nps 改成 1e4（跑得快）
prog_text = prog_text.replace("nps 100000000", "nps 10000")
if "nps 10000" not in prog_text:
    prog_text = prog_text.replace("NPS 100000000", "NPS 10000")
with open(os.path.join(SCRATCH, "dsh_prog_q1112.inp"), "w", encoding="utf-8", newline="") as f:
    f.write(prog_text)

# ---------- 落盘两个文本便于人工 diff ----------
with open(os.path.join(SCRATCH, "dsh_native_q1112.txt"), "w", encoding="utf-8") as f:
    f.write(native_text)
with open(os.path.join(SCRATCH, "dsh_prog_q1112.txt"), "w", encoding="utf-8") as f:
    f.write(prog_text)

# ---------- 运行 MCNP（cmd /c bat，与程序 _handle_run_mcnp 相同姿势） ----------
def run_mcnp(inp):
    base = inp[:-4]
    bat = os.path.join(SCRATCH, base + ".bat")
    with open(bat, "w", encoding="utf-8") as f:
        f.write('@echo off\r\nset CUDA_VISIBLE_DEVICES=1\r\nset DATAPATH=D:\\MCNP\\MCNP6\\MCNP_DATA\r\n'
                f'call "{MCNP_EXE}" inp={inp} outp={base}.o\r\n')
    print(f"[run] {inp}  (cwd={SCRATCH})")
    r = subprocess.run(["cmd.exe", "/c", bat], cwd=SCRATCH, capture_output=True, text=True, timeout=180)
    print(f"   rc={r.returncode}")
    out = (r.stdout or "") + (r.stderr or "")
    # cmd /c bat 的 stdout 来自控制台，通常为空；关键看 .o
    print(f"   console stdout len={len(r.stdout or '')} stderr len={len(r.stderr or '')}")

run_mcnp("dsh_native_q1112.inp")
run_mcnp("dsh_prog_q1112.inp")

print("\n================ 结果 ================")
for base in ("dsh_native_q1112", "dsh_prog_q1112"):
    fp = os.path.join(SCRATCH, base + ".o")
    if not os.path.exists(fp):
        print(f"{base}.o 不存在!")
        continue
    content = open(fp, "r", encoding="utf-8", errors="replace").read()
    sz = len(content)
    print(f"\n--- {base}.o  ({sz} 字符) ---")
    for kw in ("fatal error", "bad trouble", "lost particles", "run terminated",
               "dump no.", "no particles", "problem complete", "  error", "warning"):
        hits = []
        lo = 0
        low = content.lower()
        kl = kw.lower()
        while True:
            i = low.find(kl, lo)
            if i < 0:
                break
            hits.append(i)
            lo = i + 1
        if hits:
            for i in hits[:3]:
                seg = content[max(0, i - 100): i + 250].replace("\n", " | ")
                print(f"  [{kw}] x{len(hits)} ...{seg}...")
