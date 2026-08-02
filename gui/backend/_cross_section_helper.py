"""
Cross-section helper — 调 FreeCAD 子进程（_freecad_cross_section_worker.py）做 CSG 截面。
不走 STL + PyVista，直接在 FreeCAD 中用 common(thin_box) 提取截面多边形。
"""
import sys, os, json, re, subprocess

_APP_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from step_importer import StepImporter
from freecad_preview import _pymcnp_surf_to_dict, _geometry_ast_to_json
import pymcnp.inp as _pi

_SURF_CLASSES = {}
for _name in dir(_pi):
    _obj = getattr(_pi, _name)
    if hasattr(_obj, '_KEYWORD') and hasattr(_obj, 'from_mcnp') and isinstance(_obj, type):
        _kw = (_obj._KEYWORD or '').upper()
        if _kw:
            _SURF_CLASSES[_kw] = _obj


def get_cross_section(data: dict) -> dict:
    surf_text = data.get("surfaces", "")
    cell_list = data.get("cells", [])
    tr_text = data.get("tr_cards", "")
    plane = data.get("plane", {"A": 0, "B": 0, "C": 1, "D": 0})

    freecad_bin = StepImporter.detect_freecad()
    if not freecad_bin:
        return {"slices": [], "message": "需要 FreeCAD"}
    python_exe = os.path.join(freecad_bin, "python.exe")
    if not os.path.isfile(python_exe):
        return {"slices": [], "message": "FreeCAD Python 未找到"}

    # 1. 解析曲面（同 preview-3d）
    pymcnp_surfs = []
    for _line in surf_text.strip().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("C") or _line.startswith("c"):
            continue
        if "$" in _line[:5]:
            _line = _line.split("$")[0].strip()
        if not _line:
            continue
        _parts = _line.split()
        if len(_parts) < 2:
            continue
        _kw_idx = 1
        if len(_parts) > 2 and _SURF_CLASSES.get(_parts[2].upper()):
            _kw_idx = 2
        _cls = _SURF_CLASSES.get(_parts[_kw_idx].upper())
        if _cls is None:
            continue
        try:
            pymcnp_surfs.append(_cls.from_mcnp(_line))
        except Exception:
            pass

    # 2. 序列化曲面 dict
    surf_dicts = []
    for s in pymcnp_surfs:
        try:
            surf_dicts.append(_pymcnp_surf_to_dict(s))
        except Exception:
            pass

    # 3. 栅元 AST JSON（跳过 void）
    from pymcnp.types.Geometry import Geometry
    cells_json = []
    for cell in cell_list:
        expr = cell.get("surface_expr", "").strip()
        if not expr:
            continue
        raw_mat = str(cell.get("material", "")).strip().split()[0] if cell.get("material") else ""
        if raw_mat == "0":
            continue
        try:
            g = Geometry.from_mcnp(expr)
            ast = _geometry_ast_to_json(g.ast)
            cells_json.append({
                "number": cell.get("number", 0),
                "material": cell.get("material", "0"),
                "ast": ast,
            })
        except Exception:
            pass

    if not surf_dicts or not cells_json:
        return {"slices": [], "message": "缺少有效曲面或栅元"}

    # 4. TR 卡
    tr_cards = {}
    for _line in tr_text.strip().splitlines():
        _ls = _line.strip()
        if not _ls:
            continue
        m = re.match(r'^\*?TR(\d+)', _ls.upper())
        if not m:
            continue
        try:
            tn = int(m.group(1))
            if str(tn) in tr_cards:
                continue
            vals = [float(v) for v in _ls.split()[1:]]
            translate = vals[:3] if len(vals) >= 3 else [0, 0, 0]
            rotate = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
            if len(vals) >= 9:
                import numpy as np
                rotate = [[vals[3], vals[4], vals[5]], [vals[6], vals[7], vals[8]]]
                if len(vals) >= 12:
                    rotate.append([vals[9], vals[10], vals[11]])
                else:
                    rotate.append(np.cross(rotate[0], rotate[1]).tolist())
            tr_cards[str(tn)] = {"translate": translate, "rotate": rotate}
        except Exception:
            pass

    # 5. 序列化 worker 输入（bound 随曲面最大坐标自适应，大几何不被裁剪）
    _maxc = 0.0
    for _s in surf_dicts:
        for _v in (_s.get("params") or []):
            try:
                _f = float(_v)
            except (TypeError, ValueError):
                continue
            if abs(_f) > _maxc:
                _maxc = abs(_f)
    worker_input = {
        "surfaces": surf_dicts,
        "tr_cards": tr_cards,
        "cells": cells_json,
        "bound": max(_maxc * 1.3 + 100, 5000),
        "plane": plane,
    }

    # 6. 调 FreeCAD 子进程
    worker_path = os.path.join(_APP_DIR, "_freecad_cross_section_worker.py")
    try:
        proc = subprocess.run(
            [python_exe, worker_path],
            input=json.dumps(worker_input),
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            return {"slices": [], "message": "FreeCAD 进程错误"}
        result = json.loads(proc.stdout)
        if result.get("status") != "ok":
            return {"slices": [], "message": result.get("message", "截面失败")}
        slices = result.get("slices", [])
        return {"slices": slices, "count": len(slices)}
    except subprocess.TimeoutExpired:
        return {"slices": [], "message": "FreeCAD 超时"}
    except json.JSONDecodeError:
        return {"slices": [], "message": "FreeCAD 输出解析失败"}
    except Exception as e:
        return {"slices": [], "message": str(e)}
