"""
CY + TRn 变换测试
创建一个盖板（RCC）+ 4个倾斜出气孔（CY+TR）的简化场景
用 pyvista 离屏渲染截图验证位置
"""
import sys, os, numpy as np

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, 'D:/MCNP/PyMCNP/src')
sys.path.insert(0, '.')

from app.tabs.geometry_tab import _parse_surface_line, _lazy_register
_lazy_register()
import pymcnp
import pymcnp.inp as pi
from pymcnp.inp.cell.Imp import Imp
from pymcnp.inp.Cell import Cell as PyCell
from pymcnp.types.Geometry import Geometry

# ===== 1. 构建表面 =====
# 盖板 (RCC)
# 401: 底部钢板 z=400-405, R=50
# 402: 中间钢板 z=405-407, R=50
# 403: 顶部钢板 z=407-409, R=100
# 404: 顶板 z=409-414, R=100
# 出气孔 (CY + TR)
# 405: TR2, y=20, z=400, -30°绕X (向右下倾斜)
# 406: TR3, y=20, z=400, +30°绕X (向右上倾斜)
# 407: TR4, y=20, z=414, -30°绕X
# 408: TR5, y=20, z=414, +30°绕X
# PZ平面裁剪
# 501: z=400
# 502: z=407
# 503: z=414

surf_text = """401 rcc 0 0 400 0 0 5 50
402 rcc 0 0 405 0 0 2 50
403 rcc 0 0 407 0 0 2 100
404 rcc 0 0 409 0 0 5 100
405 2 cy 3
406 3 cy 3
407 4 cy 3
408 5 cy 3
501 pz 400
502 pz 407
503 pz 414"""

tr_text = """TR2 0 20 400   1 0 0   0 0.8660254 -0.5   0 0.5 0.8660254
TR3 0 20 400   1 0 0   0 0.8660254 0.5   0 -0.5 0.8660254
TR4 0 20 414   1 0 0   0 0.8660254 -0.5   0 0.5 0.8660254
TR5 0 20 414   1 0 0   0 0.8660254 0.5   0 -0.5 0.8660254"""

# 解析表面
surfs = []
for line in surf_text.strip().split('\n'):
    obj, warn = _parse_surface_line(line)
    if obj: surfs.append(obj)
    if warn: print(f'WARN: {warn}')

# 解析TR卡
import re as _re
tr_map = {}
for line in tr_text.strip().split('\n'):
    m = _re.match(r'^(\*)?TR(\d+)', line.upper())
    if not m: continue
    tr_num = int(m.group(2))
    vals = line.split()[1:]
    floats = [float(v) for v in vals]
    tr_map[tr_num] = {'translate': floats[0:3], 'rotate': [
        [floats[3],floats[4],floats[5]],
        [floats[6],floats[7],floats[8]],
        [floats[9],floats[10],floats[11]],
    ]}

# ===== 2. 构建栅元 =====
# 盖板中间层（铅）: -402 -403 405 406 407 408
# 盖板上下层（不锈钢）: -401 -404 405 406 407 408
# 出气孔下段: -405 501 -502
# 出气孔上段: -407 502 -503

cells_data = [
    (51, 5, -1.0, '-402 -403 405 406 407 408'),   # 铅
    (52, 6, -1.0, '-401 -404 405 406 407 408'),   # 不锈钢
    (61, 2, -0.001, '-405 501 -502'),              # 出气孔405
    (62, 2, -0.001, '-406 501 -502'),              # 出气孔406
    (63, 2, -0.001, '-407 502 -503'),              # 出气孔407
    (64, 2, -0.001, '-408 502 -503'),              # 出气孔408
]

cells_pymcnp = []
for num, mat, dens, expr in cells_data:
    try:
        geometry = Geometry.from_mcnp(expr)
        cells_pymcnp.append(pi.Cell(
            number=num, material=mat, density=dens,
            geometry=geometry, options=[Imp(designator='n', importance=1)]
        ))
    except Exception as e:
        print(f'Cell {num} error: {e}')

# ===== 3. 构建 Inp 并生成 surf_map =====
inp = pymcnp.Inp(title='CY+TR Test', cells=cells_pymcnp, surfaces=surfs, data=[])

# 构建 surf_map（同 _preview_3d 逻辑）
surf_map = {}
for surf in inp.surfaces:
    shape = surf.to_show()
    tn = getattr(surf, 'transform', None)
    if tn is not None and tr_map:
        tn_int = int(tn)
        if tn_int in tr_map:
            tr = tr_map[tn_int]
            t, r = tr['translate'], tr['rotate']
            M = np.array([
                [r[0][0], r[1][0], r[2][0], t[0]],
                [r[0][1], r[1][1], r[2][1], t[1]],
                [r[0][2], r[1][2], r[2][2], t[2]],
                [0, 0, 0, 1],
            ], dtype=float)
            shape.surface.transform(M, inplace=True)
    surf_map[str(surf.number)] = shape

# ===== 4. 验证关键位置 =====
print("="*60)
print("CY + TRn 变换测试 - 位置验证")
print("="*60)

for num, expected_desc, expected_z_center in [
    ('401', '盖板底 R=50', 402.5),
    ('403', '盖板顶 R=100', 408),
    ('405', '出气孔 405 (TR2, -30°)', 400),
    ('406', '出气孔 406 (TR3, +30°)', 400),
    ('407', '出气孔 407 (TR4, -30°)', 414),
    ('408', '出气孔 408 (TR5, +30°)', 414),
    ('501', 'PZ 400', 400),
    ('503', 'PZ 414', 414),
]:
    shape = surf_map[num]
    pts = shape.surface.points
    cz = (pts[:,2].min() + pts[:,2].max()) / 2
    ok = abs(cz - expected_z_center) < 50
    mark = 'OK' if ok else 'FAIL'
    print(f'  #{num} {expected_desc}:')
    print(f'    z范围=[{pts[:,2].min():.1f}, {pts[:,2].max():.1f}] z中心={cz:.1f} 预期={expected_z_center} [{mark}]')

# ===== 5. 验证出气孔倾斜方向 =====
print("\n出气孔倾斜方向验证 (从变换矩阵直接计算):")
for num, tr_key in [('405', 2), ('406', 3), ('407', 4), ('408', 5)]:
    shape = surf_map[num]
    pts = shape.surface.points
    center = np.mean(pts, axis=0)
    # 从变换矩阵获取 y_local 方向 = M 的列1（M[:,1]）
    tr = tr_map[tr_key]
    t, r = tr['translate'], tr['rotate']
    M = np.array([
        [r[0][0], r[1][0], r[2][0], t[0]],
        [r[0][1], r[1][1], r[2][1], t[1]],
        [r[0][2], r[1][2], r[2][2], t[2]],
        [0, 0, 0, 1],
    ], dtype=float)
    y_local_dir = M[:3, 1]  # column 1 = y_local direction in global
    y_local_dir = y_local_dir / np.linalg.norm(y_local_dir)
    # 预期: TR2/TR4 = -30° around X → y'=(0,0.866,-0.5)
    #        TR3/TR5 = +30° around X → y'=(0,0.866,0.5)
    expected_y = 0.8660254
    expected_z = -0.5 if tr_key in (2, 4) else 0.5
    y_ok = abs(abs(y_local_dir[1]) - expected_y) < 0.01
    z_ok = abs(y_local_dir[2] - expected_z) < 0.01
    mark = 'OK' if (y_ok and z_ok) else 'FAIL'
    print(f'  #{num} (TR{tr_key}): center=({center[0]:.1f},{center[1]:.1f},{center[2]:.1f}) '
          f'y_local方向=({y_local_dir[0]:.4f},{y_local_dir[1]:.4f},{y_local_dir[2]:.4f}) [{mark}]')

# ===== 6. 离屏渲染 =====
try:
    import pyvista
    plot = pyvista.Plotter(off_screen=True, window_size=[1200, 800])
    plot.add_axes()

    # 颜色映射
    COLORS = {
        2: (0.12, 0.47, 0.71),   # 空气-蓝
        5: (0.85, 0.37, 0.01),   # 铅-橙
        6: (0.44, 0.18, 0.66),   # 不锈钢-紫
    }

    cell_shapes = {}
    for cell in inp.cells:
        if isinstance(cell, pi.Cell):
            shape = cell.to_show(surf_map, cell_shapes)
            cell_shapes[str(cell.number)] = shape
            color = COLORS.get(int(cell.material), (0.7, 0.7, 0.7))
            plot.add_mesh(shape.surface, color=color, opacity=0.85)

    screenshot_path = 'D:/MCNP/输入卡生成器源码/test_cy_trn.png'
    plot.show(screenshot=screenshot_path)
    print(f"\n截图已保存到: {screenshot_path}")
except Exception as e:
    print(f"\n离屏渲染失败 (预期之内，无显示器环境): {e}")
    print("请手动运行该脚本在有显示器的环境查看结果")
