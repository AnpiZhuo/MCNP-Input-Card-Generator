"""
Cross-section helper — 调 FreeCAD 子进程（_freecad_cross_section_worker.py）做 CSG 截面。
不走 STL + PyVista，直接在 FreeCAD 中用 common(thin_box) 提取截面多边形。
"""
import sys, os, json, subprocess

_here = os.path.dirname(__file__)
# 打包后：helper 与 worker 同在 _internal/app/ 同级目录
# 开发时：helper 在 gui/backend/，worker 在 ../../app/
_candidate = os.path.join(_here, "_freecad_cross_section_worker.py")
_APP_DIR = _here if os.path.isfile(_candidate) else os.path.join(_here, "..", "..", "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from step_importer import StepImporter
from freecad_preview import (_pymcnp_surf_to_dict, _geometry_ast_to_json,
                             resolve_cell_complements, parenthesize_unions)
import pymcnp.inp as _pi

_SURF_CLASSES = {}
for _name in dir(_pi):
    _obj = getattr(_pi, _name)
    if hasattr(_obj, '_KEYWORD') and hasattr(_obj, 'from_mcnp') and isinstance(_obj, type):
        _kw = (_obj._KEYWORD or '').upper()
        if _kw:
            _SURF_CLASSES[_kw] = _obj


def parse_tr_cards(tr_text: str) -> dict:
    """TRn / *TRn 卡解析 —— 转发给 ``api_server.parse_tr_cards``（**唯一实现**）。

    本文件曾内联**第二份**实现（`docs/audit/t2-backend-debt.md` BE-15）：那份同样不认
    ``*TRn`` 的角度、``$`` 行内注释、5/3 值退化与 ``M`` 字段，且与权威版各自演进 ⇒
    同一个 deck 在 preview-3d 与 cross-section 两条通道下会解析出**不同几何**，用户侧
    表现为"截面预览与 3D 预览对不上"，且没有任何报错。改为转发后只有一处实现。

    **惰性 import**：不在导入期把 api_server（重模块；冻结版里还是 sidecar 的主模块）
    拉进来 —— helper 会被打进 ``_internal/app``，导入期多拉一个模块就多一份启动成本。
    """
    _backend = os.path.dirname(os.path.abspath(__file__))
    if _backend not in sys.path:
        sys.path.insert(0, _backend)
    from api_server import parse_tr_cards as _authoritative  # noqa: PLC0415 — 见 docstring

    return _authoritative(tr_text)


def get_cross_section(data: dict) -> dict:
    surf_text = data.get("surfaces", "")
    cell_list = data.get("cells", [])
    tr_text = data.get("tr_cards", "")
    plane = data.get("plane", {"A": 0, "B": 0, "C": 1, "D": 0})

    freecad_bin = StepImporter.detect_freecad()
    if not freecad_bin:
        return {"slices": [], "message": "需要 FreeCAD"}
    # 便携版（免安装）FreeCAD：python.exe 可能在 bin/ 子目录
    python_exe = os.path.join(freecad_bin, "python.exe")
    if not os.path.isfile(python_exe):
        alt = os.path.join(freecad_bin, "bin", "python.exe")
        if os.path.isfile(alt):
            python_exe = alt
        else:
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

    # 3. 栅元 AST JSON（含 void：真空栅元参与 #n 补集解析，截面仍要画边界）
    from pymcnp.types.Geometry import Geometry
    # 第一遍：收集所有栅元（含 void）的 AST，供 #n 引用解析
    parsed = []
    for cell in cell_list:
        expr = str(cell.get("surface_expr", "")).strip()
        if not expr:
            continue
        try:
            g = Geometry.from_mcnp(parenthesize_unions(expr))
        except Exception:
            continue
        parsed.append((cell.get("number", 0), cell.get("material", "0"), g.ast))
    cells_by_num = {num: node for num, _, node in parsed}
    cells_json = []
    for num, mat, node in parsed:
        try:
            resolved = resolve_cell_complements(node, cells_by_num)
            ast = _geometry_ast_to_json(resolved)
            cells_json.append({"number": num, "material": mat, "ast": ast})
        except Exception:
            pass

    if not surf_dicts or not cells_json:
        return {"slices": [], "message": "缺少有效曲面或栅元"}

    # 4. TR 卡：走 api_server 的唯一实现（BE-15；本文件不再维护第二份解析器）
    tr_cards = parse_tr_cards(tr_text)

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
        # TD-26（t5）：把 worker 收集到的逐曲面构造失败一起透传（无则省略该键），
        # 让"截面缺块"能归因到具体曲面而不是消失在裸 except 里。
        out = {"slices": slices, "count": len(slices)}
        surface_errors = result.get("surfaceErrors") or []
        if surface_errors:
            out["surfaceErrors"] = surface_errors
        return out
    except subprocess.TimeoutExpired:
        return {"slices": [], "message": "FreeCAD 超时"}
    except json.JSONDecodeError:
        return {"slices": [], "message": "FreeCAD 输出解析失败"}
    except Exception as e:
        return {"slices": [], "message": str(e)}
