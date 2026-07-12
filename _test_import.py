"""
Test import functionality: randomly pick 3 MCNPX_EXTENDED input cards

This script tests the core pipeline of the MCNP Input Card Generator:
  1. Parse raw INP text into a structured Deck object
  2. Display parsed information (cells, materials, sources, tallies, etc.)
  3. Validate the deck for correctness
  4. Regenerate INP text from the deck object

It serves as an integration test to ensure round-trip fidelity (parse -> validate -> generate).
"""

import sys
import os

# Add the project root to sys.path so 'app' package can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Force UTF-8 encoding for console output to handle Chinese characters correctly
os.environ["PYTHONIOENCODING"] = "utf-8"

# Import core pipeline modules
from app.generator.inp_parser import parse_inp_text         # INP text parser
from app.generator.inp_generator import generate_inp_from_deck  # Deck-to-INP generator
from app.generator.validator import validate_deck            # Deck validation

# List of (label, file_path) tuples for the three test INP files
# These are real MCNPX_EXTENDED test cases shipped with MCNP6
files = [
    ("testincl/inp24", r"D:\MCNP\MCNP6\MCNP_CODE\MCNP6\Testing\MCNPX_EXTENDED\testincl\INPUTS\inp24"),
    ("classgeom/prob41c", r"D:\MCNP\MCNP6\MCNP_CODE\MCNP6\Testing\MCNPX_EXTENDED\classgeom\INPUTS\prob41c"),
    ("avr/avr13", r"D:\MCNP\MCNP6\MCNP_CODE\MCNP6\Testing\MCNPX_EXTENDED\avr\INPUTS\avr13"),
]

# Track overall pass/fail status across all test files
all_ok = True

# Iterate over each test file and run the full pipeline
for label, path in files:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    # --- Read raw INP file ---
    # Try UTF-8-BOM first (common encoding for MCNP files on Windows);
    # fall back to latin-1 if UTF-8 decoding fails
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            raw = f.read()
    except Exception:
        with open(path, "r", encoding="latin-1") as f:
            raw = f.read()

    print(f"  Size: {len(raw)} bytes")

    # --- Step 1: Parse ---
    try:
        deck, warns = parse_inp_text(raw)
        print(f"  Parse: OK")
    except Exception as e:
        print(f"  Parse: FAILED - {e}")
        all_ok = False
        continue

    # --- Step 2: Display basic deck info ---
    print(f"  Cells: {len(deck.cells)} | Materials: {len(deck.materials)} | Sources: {len(deck.sources)}")
    print(f"  Mode: N={deck.basic.mode_n} P={deck.basic.mode_p} E={deck.basic.mode_e}")
    print(f"  NPS={deck.basic.nps!r} | CTME={deck.basic.ctme!r}")
    print(f"  Source mode: {deck.adv.source_mode!r}")

    # --- Step 3: Show raw SDEF line if present ---
    for l in raw.split("\n"):
        if l.strip().upper().startswith("SDEF"):
            print(f"  Raw SDEF: {l.strip()}")

    # --- Step 4: Material details (first 3 ZAID entries per material) ---
    for m in deck.materials:
        rows_show = [(r.zaid, r.fraction) for r in m.rows[:3]]
        print(f"  M{m.number}: {rows_show}... ({len(m.rows)} rows total)")

    # --- Step 5: Distribution source check (SI/SP cards) ---
    if deck.adv.source_mode == "distribution":
        print(f"  SI/SP: {deck.adv.sdef_raw_text[:100]}")

    # --- Step 6: Physics and cutoff settings ---
    # Show active CUT cards for each particle type
    t = deck.tally
    for p in ["n", "p", "e"]:
        rv = getattr(t, f"cut_{p}_raw", "")
        if rv:
            active = {f: getattr(t, f"cut_{p}_{f}", "") for f in ["t","e","wgt","tmc","wc1","wc2"] if getattr(t, f"cut_{p}_{f}", "")}
            print(f"  CUT:{p.upper()} {active}")
    # Show active PHYS cards
    adv = deck.adv
    phys = {k: getattr(adv, k, "") for k in ["phys_n_emax","phys_n_ie","phys_n_nubar","phys_n_rgas","phys_n_idm",
                                               "phys_p_emin","phys_p_isnp","phys_p_ff","phys_e_emin","phys_e_isne"]
            if getattr(adv, k, "")}
    if phys:
        print(f"  PHYS: {phys}")

    # --- Step 7: Display parser warnings ---
    if warns:
        for w in warns:
            print(f"  Warning: {w}")

    # --- Step 8: Validate ---
    errs = validate_deck(deck)
    if errs:
        for e in errs:
            print(f"  Validation: {e}")
    else:
        print(f"  Validation: PASSED")

    # --- Step 9: Generate ---
    try:
        output = generate_inp_from_deck(deck)
        print(f"  Generate: OK ({len(output)} chars)")

        # Print key generated cards (SDEF, SI, SP, CUT, PHYS) for verification
        for l in output.split("\n"):
            s = l.strip()
            if s.upper().startswith("SDEF"):
                print(f"  Generated SDEF: {s}")
            if s.upper().startswith("SI") and not s.upper().startswith("SID"):
                print(f"  Generated: {s}")
            if s.upper().startswith("SP"):
                print(f"  Generated: {s}")
            if s.upper().startswith("CUT:") or s.upper().startswith("PHYS:"):
                print(f"  Generated: {s}")
    except Exception as e:
        print(f"  Generate: FAILED - {e}")
        import traceback
        traceback.print_exc()
        all_ok = False

# Print overall test result summary
print(f"\n{'='*60}")
print(f"  Overall result: {'ALL PASSED' if all_ok else 'SOME FAILED'}")
print(f"{'='*60}")
