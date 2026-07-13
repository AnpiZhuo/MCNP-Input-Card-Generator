"""测试导入功能：随机3个MCNPX_EXTENDED输入卡"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PYTHONIOENCODING"] = "utf-8"

from app.generator.inp_parser import parse_inp_text
from app.generator.inp_generator import generate_inp_from_deck
from app.generator.validator import validate_deck

files = [
    ("testincl/inp24", r"D:\MCNP\MCNP6\MCNP_CODE\MCNP6\Testing\MCNPX_EXTENDED\testincl\INPUTS\inp24"),
    ("classgeom/prob41c", r"D:\MCNP\MCNP6\MCNP_CODE\MCNP6\Testing\MCNPX_EXTENDED\classgeom\INPUTS\prob41c"),
    ("avr/avr13", r"D:\MCNP\MCNP6\MCNP_CODE\MCNP6\Testing\MCNPX_EXTENDED\avr\INPUTS\avr13"),
]

all_ok = True
for label, path in files:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            raw = f.read()
    except Exception:
        with open(path, "r", encoding="latin-1") as f:
            raw = f.read()

    print(f"  大小: {len(raw)} 字节")

    # 1. 解析
    try:
        deck, warns = parse_inp_text(raw)
        print(f"  解析: OK")
    except Exception as e:
        print(f"  解析: 失败 - {e}")
        all_ok = False
        continue

    # 2. 基本信息
    print(f"  栅元: {len(deck.cells)} | 材料: {len(deck.materials)} | 源: {len(deck.sources)}")
    print(f"  模式: N={deck.basic.mode_n} P={deck.basic.mode_p} E={deck.basic.mode_e}")
    print(f"  NPS={deck.basic.nps!r} | CTME={deck.basic.ctme!r}")
    print(f"  源模式: {deck.adv.source_mode!r}")

    # 3. 原始 SDEF
    for l in raw.split("\n"):
        if l.strip().upper().startswith("SDEF"):
            print(f"  原始SDEF: {l.strip()}")

    # 4. 材料明细
    for m in deck.materials:
        rows_show = [(r.zaid, r.fraction) for r in m.rows[:3]]
        print(f"  M{m.number}: {rows_show}... (共{len(m.rows)}行)")

    # 5. 分布源检验
    if deck.adv.source_mode == "distribution":
        print(f"  SI/SP: {deck.adv.sdef_raw_text[:100]}")

    # 6. PHYS / CUT
    t = deck.tally
    for p in ["n", "p", "e"]:
        rv = getattr(t, f"cut_{p}_raw", "")
        if rv:
            active = {f: getattr(t, f"cut_{p}_{f}", "") for f in ["t","e","wgt","tmc","wc1","wc2"] if getattr(t, f"cut_{p}_{f}", "")}
            print(f"  CUT:{p.upper()} {active}")
    adv = deck.adv
    phys = {k: getattr(adv, k, "") for k in ["phys_n_emax","phys_n_ie","phys_n_nubar","phys_n_rgas","phys_n_idm",
                                               "phys_p_emin","phys_p_isnp","phys_p_ff","phys_e_emin","phys_e_isne"]
            if getattr(adv, k, "")}
    if phys:
        print(f"  PHYS: {phys}")

    # 7. 警告
    if warns:
        for w in warns:
            print(f"  警告: {w}")

    # 8. 校验
    errs = validate_deck(deck)
    if errs:
        for e in errs:
            print(f"  校验: {e}")
    else:
        print(f"  校验: 通过")

    # 9. 生成
    try:
        output = generate_inp_from_deck(deck)
        print(f"  生成: OK ({len(output)} 字符)")

        # 生成结果中的关键卡
        for l in output.split("\n"):
            s = l.strip()
            if s.upper().startswith("SDEF"):
                print(f"  生成SDEF: {s}")
            if s.upper().startswith("SI") and not s.upper().startswith("SID"):
                print(f"  生成: {s}")
            if s.upper().startswith("SP"):
                print(f"  生成: {s}")
            if s.upper().startswith("CUT:") or s.upper().startswith("PHYS:"):
                print(f"  生成: {s}")
    except Exception as e:
        print(f"  生成: 失败 - {e}")
        import traceback
        traceback.print_exc()
        all_ok = False

print(f"\n{'='*60}")
print(f"  总体结果: {'全部通过' if all_ok else '有失败项'}")
print(f"{'='*60}")
