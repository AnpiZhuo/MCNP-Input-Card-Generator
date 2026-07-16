"""
FreeCAD CSG 引擎 — 主进程侧封装。

在 app 主进程中运行。通过子进程调用 FreeCAD Python 执行 _freecad_csg_worker.py，
处理 pymcnp 对象的序列化和 JSON 协议。
"""

import json
import os
import subprocess
import tempfile
import shutil
import threading

# pymcnp Geometry AST 节点类型，在 freecad_preview 中延迟导入
_Intersection = None
_Union = None
_Unary = None
_Paren = None
_Digit = None


def _lazy_import_geometry():
    """延迟导入 pymcnp Geometry AST 类型"""
    global _Intersection, _Union, _Unary, _Paren, _Digit
    if _Intersection is None:
        from pymcnp.types.Geometry import (
            _Intersection, _Union, _Unary, _Paren, _Digit
        )


def _geometry_ast_to_json(node):
    """递归遍历 pymcnp Geometry AST → JSON 列表"""
    _lazy_import_geometry()

    if isinstance(node, _Intersection):
        return ["intersect", _geometry_ast_to_json(node.left),
                _geometry_ast_to_json(node.right)]
    if isinstance(node, _Union):
        return ["union", _geometry_ast_to_json(node.left),
                _geometry_ast_to_json(node.right)]
    if isinstance(node, _Unary):
        signs = {"+": "pos", "-": "neg", "#": "complement"}
        return ["unary", _geometry_ast_to_json(node.operand),
                signs[node.operator]]
    if isinstance(node, _Paren):
        return _geometry_ast_to_json(node.ast)  # 括号不额外编码
    if isinstance(node, _Digit):
        return ["surf", int(node.value)]

    raise ValueError(f"未知 AST 节点: {type(node).__name__}")


def _pymcnp_surf_to_dict(surf):
    """从 pymcnp 表面对象提取 type/params/transform"""
    info = {"number": int(surf.number)}
    tr = getattr(surf, 'transform', None)
    info["transform"] = int(tr) if tr is not None else None
    kw = surf._KEYWORD.upper()

    # ── 单参数 ──
    if kw in ("PX", "PY", "PZ"):           p = [float(surf.d)]
    elif kw in ("SO", "CX", "CY", "CZ"):   p = [float(surf.r)]

    # ── 双参数 ──
    elif kw == "SX":   p = [float(surf.x), float(surf.r)]
    elif kw == "SY":   p = [float(surf.y), float(surf.r)]
    elif kw == "SZ":   p = [float(surf.z), float(surf.r)]

    # ── 球 ──
    elif kw == "S":    p = [float(surf.x), float(surf.y), float(surf.z), float(surf.r)]

    # ── 平行轴圆柱 ──
    elif kw == "C/X":  p = [float(surf.y), float(surf.z), float(surf.r)]
    elif kw == "C/Y":  p = [float(surf.x), float(surf.z), float(surf.r)]
    elif kw == "C/Z":  p = [float(surf.x), float(surf.y), float(surf.r)]

    # ── 圆锥 ──
    elif kw == "KX":   p = [float(surf.x), float(surf.t_squared), float(surf.plusminus_1)]
    elif kw == "KY":   p = [float(surf.y), float(surf.t_squared), float(surf.plusminus_1)]
    elif kw == "KZ":   p = [float(surf.z), float(surf.t_squared), float(surf.plusminus_1)]
    elif kw == "K/X":  p = [float(surf.x), float(surf.y), float(surf.z), float(surf.t_squared), float(surf.plusminus_1)]
    elif kw == "K/Y":  p = [float(surf.x), float(surf.y), float(surf.z), float(surf.t_squared), float(surf.plusminus_1)]
    elif kw == "K/Z":  p = [float(surf.x), float(surf.y), float(surf.z), float(surf.t_squared), float(surf.plusminus_1)]

    # ── 环面 ──
    elif kw in ("TX", "TY", "TZ"):  p = [float(surf.x), float(surf.y), float(surf.z), float(surf.a), float(surf.b), float(surf.c)]

    # ── 平面 ──
    elif kw == "P":
        if hasattr(surf, 'd'):
            p = [float(surf.a), float(surf.b), float(surf.c), float(surf.d)]
            kw = "P_0"
        else:
            p = [float(surf.x1), float(surf.y1), float(surf.z1),
                 float(surf.x2), float(surf.y2), float(surf.z2),
                 float(surf.x3), float(surf.y3), float(surf.z3)]
            kw = "P_1"

    # ── RPP ──
    elif kw == "RPP":  p = [float(surf.xmin), float(surf.xmax), float(surf.ymin), float(surf.ymax), float(surf.zmin), float(surf.zmax)]

    # ── Macrobody ──
    elif kw == "SPH":  p = [float(surf.vx), float(surf.vy), float(surf.vz), float(surf.r)]
    elif kw == "RCC":  p = [float(surf.vx), float(surf.vy), float(surf.vz), float(surf.hx), float(surf.hy), float(surf.hz), float(surf.r)]
    elif kw == "TRC":  p = [float(surf.vx), float(surf.vy), float(surf.vz), float(surf.hx), float(surf.hy), float(surf.hz), float(surf.r1), float(surf.r2)]
    elif kw == "REC":  p = [float(surf.vx), float(surf.vy), float(surf.vz), float(surf.hx), float(surf.hy), float(surf.hz), float(surf.v1x), float(surf.v1y), float(surf.v1z), float(surf.v2x), float(surf.v2y), float(surf.v2z)]
    elif kw == "ELL":  p = [float(surf.v1x), float(surf.v1y), float(surf.v1z), float(surf.v2x), float(surf.v2y), float(surf.v2z), float(surf.rm)]
    elif kw == "WED":  p = [float(surf.vx), float(surf.vy), float(surf.vz), float(surf.v1x), float(surf.v1y), float(surf.v1z), float(surf.v2x), float(surf.v2y), float(surf.v2z), float(surf.v3x), float(surf.v3y), float(surf.v3z)]
    elif kw == "BOX":  p = [float(surf.vx), float(surf.vy), float(surf.vz), float(surf.a1x), float(surf.a1y), float(surf.a1z), float(surf.a2x), float(surf.a2y), float(surf.a2z), float(surf.a3x), float(surf.a3y), float(surf.a3z)]
    elif kw in ("RHP", "HEX"):  p = [float(surf.vx), float(surf.vy), float(surf.vz), float(surf.hx), float(surf.hy), float(surf.hz), float(surf.r1), float(surf.r2), float(surf.r3), float(surf.s1), float(surf.s2), float(surf.s3), float(surf.t1), float(surf.t2), float(surf.t3)]
    elif kw == "ARB":  p = [float(surf.ax), float(surf.ay), float(surf.az), float(surf.bx), float(surf.by), float(surf.bz), float(surf.cx), float(surf.cy), float(surf.cz), float(surf.dx), float(surf.dy), float(surf.dz), float(surf.ex), float(surf.ey), float(surf.ez), float(surf.fx), float(surf.fy), float(surf.fz), float(surf.gx), float(surf.gy), float(surf.gz), float(surf.hx), float(surf.hy), float(surf.hz), float(surf.n1), float(surf.n2), float(surf.n3), float(surf.n4), float(surf.n5), float(surf.n6)]

    # ── GQ / SQ ──
    elif kw == "GQ":  p = [float(surf.a), float(surf.b), float(surf.c), float(surf.d), float(surf.e), float(surf.f), float(surf.g), float(surf.h), float(surf.j), float(surf.k)]
    elif kw == "SQ":  p = [float(surf.a), float(surf.b), float(surf.c), float(surf.d), float(surf.e), float(surf.f), float(surf.g), float(surf.x), float(surf.y), float(surf.z)]

    # ── 点定义旋转体 ──
    elif kw in ("X", "Y", "Z"):
        pm = {"X": "x", "Y": "y", "Z": "z"}
        pf = pm[kw]
        p = []
        for i in range(1, 4):
            ai = getattr(surf, f"{pf}{i}", None)
            ri = getattr(surf, f"r{i}", None)
            if ai is not None and ri is not None:
                p += [float(ai), float(ri)]

    else:
        raise ValueError(f"未知曲面类型: {kw} (曲面 {info['number']})")

    info.update({"type": kw, "params": p})
    return info


class FreeCADEngine:
    """FreeCAD CSG 几何引擎封装。

    通过子进程调用 FreeCAD Python 执行布尔几何运算。
    主进程负责 pymcnp 对象的序列化和结果收集。
    """

    def __init__(self, freecad_bin: str):
        """
        Args:
            freecad_bin: FreeCAD 的 bin 目录路径 (StepImporter.detect_freecad() 返回值)
        """
        self._freecad_bin = freecad_bin
        self._tmpdir_obj = None

    def build_geometry(self, pymcnp_surfaces: list, cells_data: list,
                       tr_cards: dict, bound: float = 500,
                       fmt: str = "stl") -> dict[int, str]:
        """从 pymcnp 对象和栅元数据构建各栅元的 CSG 几何。

        Args:
            pymcnp_surfaces: _parse_surface_line() 返回的 pymcnp 表面对象列表
            cells_data: [{number, ast (Geometry 节点), material, density}]
            tr_cards: {"1": {"translate": [...], "rotate": [[...],...]}}
            bound: 半空间包围盒半边长 (BOUND)
            fmt: 输出格式 ("stl" | "step")

        Returns:
            {cell_number: 输出文件路径}

        Raises:
            RuntimeError: FreeCAD 进程失败或输出解析失败
        """
        # 1. 序列化 pymcnp 对象
        surf_dicts = []
        for s in pymcnp_surfaces:
            try:
                surf_dicts.append(_pymcnp_surf_to_dict(s))
            except (ValueError, AttributeError) as e:
                raise RuntimeError(f"曲面 {getattr(s, 'number', '?')} 序列化失败: {e}")

        # 2. 序列化 Geometry AST
        cell_dicts = []
        for c in cells_data:
            try:
                ast_json = _geometry_ast_to_json(c["ast"].ast)
            except (ValueError, AttributeError) as e:
                raise RuntimeError(f"栅元 {c['number']} AST 序列化失败: {e}")
            cell_dicts.append({
                "number": c["number"],
                "ast": ast_json,
            })

        # 3. 准备临时目录
        tmp_dir = self._tmpdir()
        input_json = {
            "surfaces": surf_dicts,
            "tr_cards": tr_cards,
            "cells": cell_dicts,
            "bound": bound,
            "output_dir": tmp_dir,
            "format": fmt,
        }

        # 4. 子进程调用 FreeCAD
        result_data = self._run_freecad_script(input_json)

        # 5. 收集输出
        result = {}
        for cell_num_str, filename in result_data.get("files", {}).items():
            result[int(cell_num_str)] = os.path.join(tmp_dir, filename)

        # 如果有警告，记录但不中断
        # warnings 可通过返回结构传递，但保持接口简单
        return result

    def export_stl(self, pymcnp_surfaces: list, cells_data: list,
                   tr_cards: dict, out_dir: str) -> list[str]:
        """导出每个栅元的 STL 文件"""
        result = self.build_geometry(pymcnp_surfaces, cells_data,
                                     tr_cards, fmt="stl")
        files = []
        for cell_num, src_path in result.items():
            dst = os.path.join(out_dir, f"cell_{cell_num}.stl")
            if os.path.abspath(src_path) != os.path.abspath(dst):
                shutil.copy2(src_path, dst)
            files.append(dst)
        return files

    def export_step(self, pymcnp_surfaces: list, cells_data: list,
                    tr_cards: dict, out_dir: str) -> list[str]:
        """导出每个栅元的 STEP 文件"""
        result = self.build_geometry(pymcnp_surfaces, cells_data,
                                     tr_cards, fmt="step")
        files = []
        for cell_num, src_path in result.items():
            dst = os.path.join(out_dir, f"cell_{cell_num}.step")
            if os.path.abspath(src_path) != os.path.abspath(dst):
                shutil.copy2(src_path, dst)
            files.append(dst)
        return files

    def _run_freecad_script(self, input_data: dict) -> dict:
        """写入临时 JSON → spawn FreeCAD Python → 收集输出"""
        python_exe = os.path.join(self._freecad_bin, "python.exe")
        if not os.path.isfile(python_exe):
            raise RuntimeError(f"FreeCAD Python 未找到: {python_exe}")

        script_path = self._worker_script_path()

        proc = subprocess.run(
            [python_exe, script_path],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            timeout=120,
        )

        if proc.returncode != 0:
            stderr_tail = proc.stderr[-500:] if proc.stderr else "无错误输出"
            stdout_tail = proc.stdout[-300:] if proc.stdout else ""
            raise RuntimeError(
                f"FreeCAD 进程退出码 {proc.returncode}\n"
                f"stderr: {stderr_tail}\n"
                f"stdout: {stdout_tail}"
            )

        # 解析 stdout JSON
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"FreeCAD 输出解析失败: {e}\n"
                f"stdout: {proc.stdout[:500]}"
            )

        if result.get("status") != "ok":
            raise RuntimeError(result.get("message", "FreeCAD 返回未知错误"))

        # 如果有警告，这里可以处理
        # for w in result.get("warnings", []):
        #     logger.warning(w)

        return result

    def _worker_script_path(self) -> str:
        """定位 _freecad_csg_worker.py"""
        return os.path.join(os.path.dirname(__file__), "_freecad_csg_worker.py")

    def _tmpdir(self) -> str:
        """创建并返回临时目录。每个引擎实例一个临时目录。"""
        if self._tmpdir_obj is None:
            self._tmpdir_obj = tempfile.mkdtemp(prefix="freecad_csg_")
        return self._tmpdir_obj

    def cleanup(self):
        """删除临时文件"""
        if self._tmpdir_obj is not None and os.path.isdir(self._tmpdir_obj):
            shutil.rmtree(self._tmpdir_obj, ignore_errors=True)
            self._tmpdir_obj = None

    def __del__(self):
        self.cleanup()
