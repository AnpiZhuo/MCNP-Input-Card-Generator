"""生成水球 MCNP 输入卡"""
import math, os

log_min = math.log10(0.001)
log_max = math.log10(14)
n_bins = 200
energies = [10 ** (log_min + i * (log_max - log_min) / n_bins) for i in range(n_bins + 1)]

e0_parts = [f'{e:.6e}' for e in energies]
e0_lines = []
line = 'E0  '
for val in e0_parts:
    if len(line + ' ' + val) > 75:
        e0_lines.append(line.rstrip() + ' &')
        line = '     ' + val
    else:
        line += ' ' + val
e0_lines.append(line.rstrip())

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

# 输出到当前脚本所在目录
output_dir = os.path.dirname(os.path.abspath(__file__))
inp_path = os.path.join(output_dir, 'water_sphere.INP')
with open(inp_path, 'w', encoding='ascii') as f:
    f.write(inp)

bat = '@echo off\ncall mcnp6.exe inp=water_sphere.INP outp=outp.o\npause\n'
bat_path = os.path.join(output_dir, 'water_sphere.bat')
with open(bat_path, 'w', encoding='ascii') as f:
    f.write(bat)

print(f'OK - {inp_path} 和 {bat_path} 已生成')
