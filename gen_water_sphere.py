"""
gen_water_sphere.py — Water Sphere MCNP Input Deck Generator

This script generates a complete MCNP input file (.INP) and a Windows batch
launcher (.bat) for a simple water-sphere benchmark problem.

Problem description:
  - A 250 cm radius water sphere (density 1.0 g/cm3) with a 14 MeV neutron
    point source at the center.
  - Tallies: F4 (avg flux), F2 (surface flux), F6 (energy deposition).
  - 200 logarithmic energy bins from 0.001 to 14 MeV shared by all tallies.
  - 10000 particle histories (NPS).

Output files are written to the same directory as this script.
"""

import math
import os

# --- Build logarithmic energy grid: 200 bins from 0.001 to 14 MeV ---
log_min = math.log10(0.001)            # log10(0.001) = -3
log_max = math.log10(14)               # log10(14) ~ 1.146
n_bins = 200                            # Number of energy bins
# Generate (n_bins + 1) energy grid points evenly spaced in log space
energies = [10 ** (log_min + i * (log_max - log_min) / n_bins) for i in range(n_bins + 1)]

# --- Format the E0 card (energy bin specification) ---
# MCNP line continuation: cards use '&' to continue, with continuation line indented
e0_parts = [f'{e:.6e}' for e in energies]  # e.g. "1.000000e-03"
e0_lines = []
line = 'E0  '                         # Start of E0 card
for val in e0_parts:
    # If the next value would exceed the 80-column limit, wrap to next line
    if len(line + ' ' + val) > 75:
        e0_lines.append(line.rstrip() + ' &')
        line = '     ' + val           # Standard continuation indentation
    else:
        line += ' ' + val
e0_lines.append(line.rstrip())        # Last line (no continuation marker)

# --- Assemble the full INP file content ---
inp = f"""Water Sphere with Central Neutron Source - F4 F2 F6 Tallies
C  ===== Cell Cards =====
1   1  -1.0  -1  IMP:N=1   $ Water sphere, r=250cm
2   0         1  IMP:N=0   $ Outside world (void)

C  ===== Surface Cards =====
1  SPH  0 0 0  250   $ Sphere radius 250cm (5m diam)

C  ===== Data Cards =====
MODE  N
SDEF  PAR=1  POS=0 0 0  ERG=14  WGT=1
M1  1001.80c  -0.1119  8016.80c  -0.8881   $ H2O density -1.0 g/cm3
CUT:N  0  0.001  0  0  0   $ Energy cutoff 0.001 MeV
NPS  10000

C  Tallies
F4:N  1   $ Avg neutron flux in water sphere (particle/cm2)
F2:N  1   $ Neutron surface flux on sphere surface
F6:N  1   $ Energy deposition in water (MeV/g)

C  Energy bins: 200 log intervals, 0.001 to 14 MeV
{chr(10).join(e0_lines)}
C  F4 F2 F6 share the same energy mesh
"""

# --- Write the INP file to the script's directory ---
output_dir = os.path.dirname(os.path.abspath(__file__))
inp_path = os.path.join(output_dir, 'water_sphere.INP')
with open(inp_path, 'w', encoding='ascii') as f:
    f.write(inp)

# --- Write the Windows batch launcher ---
bat = '@echo off\ncall mcnp6.exe inp=water_sphere.INP outp=outp.o\npause\n'
bat_path = os.path.join(output_dir, 'water_sphere.bat')
with open(bat_path, 'w', encoding='ascii') as f:
    f.write(bat)

print(f'OK - {inp_path} 和 {bat_path} 已生成')  # "Generated successfully"
