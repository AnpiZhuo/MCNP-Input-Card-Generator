"""
Practice3 完整 3D 预览测试
读取 E:\download\Practice3 的全部曲面/TR/栅元，
用 pyvista 离屏渲染生成截图验证。
"""
import sys, os, re as _re
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, 'D:/MCNP/PyMCNP/src')
sys.path.insert(0, '.')

import numpy as np
from app.tabs.geometry_tab import _parse_surface_line, _lazy_register
_lazy_register()
import pymcnp
from pymcnp.inp.Cell import Cell as PyCell
from pymcnp.inp.cell.Imp import Imp
from pymcnp.types.Geometry import Geometry

# ===== 1. 从 Practice3 提取曲面卡和 TR 卡 =====
surf_text = """101 rpp -7.5 7.5 -10 10 50 80
201 rpp -150 150 -150 150 0 300
202 rcc 0 0 300 0 0 100 50
203 rpp -250 250 -250 250 0 428
301 rcc 0 150 65 0 80 0 15
302 rcc 0 230 65 0 20 0 25
401 rcc 0 0 400 0 0 5 50
402 rcc 0 0 405 0 0 2 50
403 rcc 0 0 407 0 0 2 100
404 rcc 0 0 409 0 0 5 100
405 2 cy 3
406 3 cy 3
407 4 cy 3
408 5 cy 3
501 pz 400
502 pz 407
503 pz 414
601 rpp -350 350 -350 350 0 528"""

tr_text = """TR2 0 20 400   1 0 0   0 0.8660254 -0.5   0 0.5 0.8660254
TR3 0 20 400   1 0 0   0 0.8660254 0.5   0 -0.5 0.8660254
TR4 0 20 414   1 0 0   0 0.8660254 -0.5   0 0.5 0.8660254
TR5 0 20 414   1 0 0   0 0.8660254 0.5   0 -0.5 0.8660254"""

# ===== 2. 解析曲面 =====
surfs = []
for line in surf_text.strip().split('\n'):
    obj, warn = _parse_surface_line(line)
    if obj: surfs.append(obj)
    if warn: print(f'WARN: {warn}')

print(f'曲面解析完成: {len(surfs)} 个')

# ===== 3. 解析 TR 卡 =====
tr_map = {}
for line in tr_text.strip().split('\n'):
    m = _re.match(r'^(\*)?TR(\d+)', line.upper())
    if not m: continue
    tr_num = int(m.group(2))
    vals = line.split()[1:]
    floats = [float(v) for v in vals]
    tr_map[tr_num] = {
        'translate': floats[0:3],
        'rotate': [[floats[3],floats[4],floats[5]],
                   [floats[6],floats[7],floats[8]],
                   [floats[9],floats[10],floats[11]]],
    }
print(f'TR 卡解析完成: {list(tr_map.keys())}')

# ===== 4. 构建栅元 =====
# Practice3 的栅元定义（从文件中提取）
cells_data = [
    (1, 1, -8.22, '-101'),
    (21, 2, -0.001205, '101 -201'),
    (22, 2, -0.001205, '-202'),
    (3, 3, -3.35, '-203 201 202 301 302 401 402 403 404'),
    (41, 4, -6.22, '-301'),
    (42, 2, -0.001205, '-302'),
    (51, 5, -11.34, '-402 -403 405 406 407 408'),
    (52, 6, -7.8, '-401 -404 405 406 407 408'),
    (61, 4, -6.22, '-405 501 -502'),
    (62, 4, -6.22, '-406 501 -502'),
    (63, 4, -6.22, '-407 502 -503'),
    (64, 4, -6.22, '-408 502 -503'),
    (7, 2, -0.001205, '203 -601'),
    (8, 0, None, '601'),
]

cells_pymcnp = []
for num, mat, dens, expr in cells_data:
    try:
        geometry = Geometry.from_mcnp(expr)
        opts = [Imp(designator='n', importance=1)]
        cells_pymcnp.append(PyCell(
            number=num, material=mat, density=dens,
            geometry=geometry, options=opts
        ))
    except Exception as e:
        print(f'栅元 {num} 构建失败: {e}')

print(f'栅元构建完成: {len(cells_pymcnp)} 个')

# ===== 5. 构建 Inp 及 surf_map =====
inp = pymcnp.Inp(title='Practice3 Preview', cells=cells_pymcnp, surfaces=surfs, data=[])

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

# ===== 5.5 裁剪无限曲面到模型包围盒 =====
clip_bbox = None
for s in surfs:
    box = None
    if hasattr(s, 'xmin'):  # RPP
        box = (float(s.xmin), float(s.xmax), float(s.ymin), float(s.ymax), float(s.zmin), float(s.zmax))
    elif hasattr(s, 'vx') and hasattr(s, 'r') and hasattr(s, 'hx') and not getattr(s, 'transform', None):
        v = np.array([float(s.vx), float(s.vy), float(s.vz)])
        h = np.array([float(s.hx), float(s.hy), float(s.hz)])
        r = float(s.r)
        if np.linalg.norm(h) > 0:
            h_n = h / np.linalg.norm(h); v_end = v + h
            pts = [v, v_end]
            for ax in [np.array([1,0,0]), np.array([0,1,0]), np.array([0,0,1])]:
                perp = ax - np.dot(ax, h_n) * h_n
                if np.linalg.norm(perp) > 1e-10:
                    perp = perp / np.linalg.norm(perp)
                    pts.append(v + perp * r); pts.append(v_end + perp * r)
            pts = np.array(pts)
            box = (pts[:,0].min(), pts[:,0].max(), pts[:,1].min(), pts[:,1].max(), pts[:,2].min(), pts[:,2].max())
    if box is not None:
        if clip_bbox is None: clip_bbox = list(box)
        else:
            clip_bbox[0] = min(clip_bbox[0], box[0]); clip_bbox[1] = max(clip_bbox[1], box[1])
            clip_bbox[2] = min(clip_bbox[2], box[2]); clip_bbox[3] = max(clip_bbox[3], box[3])
            clip_bbox[4] = min(clip_bbox[4], box[4]); clip_bbox[5] = max(clip_bbox[5], box[5])

if clip_bbox:
    dx = (clip_bbox[1] - clip_bbox[0]) * 0.025
    dy = (clip_bbox[3] - clip_bbox[2]) * 0.025
    dz = (clip_bbox[5] - clip_bbox[4]) * 0.025
    clip_bbox = [clip_bbox[0]-dx, clip_bbox[1]+dx, clip_bbox[2]-dy, clip_bbox[3]+dy, clip_bbox[4]-dz, clip_bbox[5]+dz]
    import pyvista as _pv
    for key in list(surf_map.keys()):
        try:
            surf_map[key].surface = surf_map[key].surface.clip_box(bounds=clip_bbox, invert=False)
        except Exception:
            pass
    print(f'\n裁剪包围盒: x=[{clip_bbox[0]:.1f},{clip_bbox[1]:.1f}] y=[{clip_bbox[2]:.1f},{clip_bbox[3]:.1f}] z=[{clip_bbox[4]:.1f},{clip_bbox[5]:.1f}]')

# ===== 6. 验证关键表面位置 =====
print('\n=== 关键表面位置验证 ===')
key_surfaces = [
    ('101', '源RPP', None),
    ('201', '内层空气RPP', None),
    ('202', '内层空气RCC', None),
    ('203', '混凝土RPP', None),
    ('401', '盖板底RCC', None),
    ('403', '盖板顶RCC', None),
    ('405', '出气孔TR2', 400),
    ('406', '出气孔TR3', 400),
    ('407', '出气孔TR4', 414),
    ('408', '出气孔TR5', 414),
    ('501', 'PZ400', 400),
    ('503', 'PZ414', 414),
    ('601', '外空气RPP', None),
]
for num, desc, exp_z in key_surfaces:
    shape = surf_map[num]
    pts = shape.surface.points
    z_min, z_max = pts[:,2].min(), pts[:,2].max()
    cz = (z_min + z_max) / 2
    y_min, y_max = pts[:,1].min(), pts[:,1].max()
    x_min, x_max = pts[:,0].min(), pts[:,0].max()
    if exp_z is not None:
        ok = 'OK' if abs(cz - exp_z) < 50 else 'FAIL'
        print(f'  #{num:3s} {desc:12s} z=[{z_min:8.1f},{z_max:8.1f}] z中心={cz:6.1f} 预期={exp_z} [{ok}]')
    else:
        print(f'  #{num:3s} {desc:12s} x=[{x_min:8.1f},{x_max:8.1f}] y=[{y_min:8.1f},{y_max:8.1f}] z=[{z_min:8.1f},{z_max:8.1f}]')

# ===== 7. 离屏渲染 =====
try:
    import pyvista
    plot = pyvista.Plotter(off_screen=True, window_size=[1400, 1000])
    plot.add_axes()

    # 颜色映射（同 geometry_tab.py）
    _COLORS = [
        None,
        (0.12, 0.47, 0.71),    # 1: 蓝
        (0.85, 0.37, 0.01),    # 2: 橙
        (0.20, 0.63, 0.17),    # 3: 绿
        (0.74, 0.13, 0.13),    # 4: 红
        (0.44, 0.18, 0.66),    # 5: 紫
        (0.00, 0.58, 0.58),    # 6: 青
    ]
    def _mat_color(mat):
        mat_int = int(mat)
        return _COLORS[mat_int] if mat_int < len(_COLORS) else (0.7, 0.7, 0.7)

    cell_shapes = {}
    for cell in inp.cells:
        if isinstance(cell, PyCell):
            shape = cell.to_show(surf_map, cell_shapes)
            cell_shapes[str(cell.number)] = shape
            color = _mat_color(cell.material)
            if color:
                plot.add_mesh(shape.surface, color=color, opacity=0.85)

    screenshot_path = 'D:/MCNP/输入卡生成器源码/practice3_preview.png'
    plot.show(screenshot=screenshot_path)
    print(f'\n截图已保存: {screenshot_path}')
    print('请在文件浏览器中打开查看渲染效果')
except Exception as e:
    print(f'\n渲染失败: {e}')
    import traceback
    traceback.print_exc()
