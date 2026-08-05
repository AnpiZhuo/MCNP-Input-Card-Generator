"""
STEP → MCNP 转换：封装 GEOUNED（FreeCAD 转换器）调用 + 输出解析。

使用方法：
    from app.step_importer import StepImporter

    # FreeCAD 检测（用于 3D 预览和 STEP 导出）
    bin_path = StepImporter.detect_freecad()

    # GEOUNED STEP 导入
    deck = StepImporter.import_step("模型.stp", "SS", -7.93)
注：GEOUNED 以 Python 包形式随程序分发，运行时经 FreeCAD Python 调用。
"""

import os
import sys
import json
import re
import subprocess
import tempfile
import winreg

from pathlib import Path
from PyQt5.QtCore import QSettings


# ===================================================================
# 曲面数字格式化 — 科学计数法 → 干净十进制（GQ/SQ 保留精度）
# ===================================================================

_SURF_MNE = set("P PX PY PZ SO S SX SY SZ C/X C/Y C/Z CX CY CZ "
                "K/X K/Y K/Z KX KY KZ SQ GQ TX TY TZ "
                "RPP RCC RHP HEX ARB BOX SPH REC TRC WED ELL".split())
_NUM_RE = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


def _fmt_num_token(match, prec: int = 3) -> str:
    """数值 token：浮点 → prec 位小数；整数（曲面号/栅元引用）保持原样。"""
    tok = match.group(0)
    if re.fullmatch(r"[+-]?\d+", tok):
        return tok
    try:
        v = float(tok)
    except ValueError:
        return tok
    return format(v, f".{prec}f")


def _format_surface_numbers(text: str) -> str:
    """把 MCNP 曲面文本的数字整理成 3 位小数（跳过注释行与 $ 注释）。"""
    lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if not stripped or stripped[0].lower() == "c" or stripped[0] == "$":
            lines.append(line)
            continue
        body, sep, comment = line.partition("$")
        parts = body.split()
        if len(parts) >= 2 and parts[1].upper() in _SURF_MNE:
            if parts[1].upper() in ("GQ", "SQ"):
                lines.append(line)  # GQ/SQ 系数保留原始精度（几何定义）
            else:
                lines.append(_NUM_RE.sub(lambda m: _fmt_num_token(m, 3), body)
                             + (sep + comment if sep else ""))
        else:
            lines.append(line)
    return "\n".join(lines)


def _strip_data_cards(text: str) -> str:
    """只保留栅元 + 曲面段，截掉数据卡段（MODE/NPS/SDEF 等）。

    数据卡是首列非缩进、以字母开头的行；栅元/曲面卡以数字开头，
    注释以 C/$ 开头，续行缩进开头。
    """
    lines = text.splitlines()
    cut = len(lines)
    for i, line in enumerate(lines):
        if i == 0:
            continue  # 首行是 MCNP 标题
        s = line.lstrip()
        if not s or s[0].lower() in ("c", "$"):
            continue
        if re.match(r"^\*?TR\d+\s", s, re.IGNORECASE):
            continue  # TR 卡单独保留
        if not line[:1].isspace() and s[0].isalpha():
            cut = i
            break
    return "\n".join(lines[:cut])


def geometry_deck_response(surfaces_text: str, tr_cards_text: str,
                           cells_list: list) -> dict:
    """STEP 导入响应的几何 deck JSON —— surfaces/tr_cards/cells 三件套。"""
    return {
        "surfaces": surfaces_text or "",
        "tr_cards": tr_cards_text or "",
        "cells": cells_list or [],
    }


# ===================================================================
# run_step_converter — GEOUNED 转换
# ===================================================================

def run_step_converter(name: str, step_path: str, material: str,
                       density: float, settings: dict,
                       freecad_bin: str | None = None) -> str | None:
    """运行 STEP→MCNP 转换（当前仅 GEOUNED），返回 MCNP 文件路径；失败返回 None。"""
    if name == "geouned":
        try:
            from step_importer_geouned import GeoUnedConverter
            conv = GeoUnedConverter(freecad_bin=freecad_bin)
            if not conv.is_available():
                return None
            work_dir = tempfile.mkdtemp(prefix="geouned_")
            return conv.run(step_path, material, density, work_dir, settings)
        except Exception:
            return None
    return None


# ===================================================================
# StepImporter — 公共接口
# ===================================================================

class StepImporter:
    """STEP 导入器。封装 GEOUNED 外部转换器的调用和输出解析。"""

    # --- FreeCAD 检测 ---

    @classmethod
    def detect_freecad(cls) -> str | None:
        """检测 FreeCAD 可执行文件路径。返回 bin 目录或 None。"""
        return _cached_detect()

    @classmethod
    def save_freecad_path(cls, exe_path: str) -> None:
        """保存 FreeCAD 路径到 QSettings。"""
        settings = QSettings("MCNPGen", "MCNPGenerator")
        settings.setValue("freecad_path", exe_path)

    # --- GEOUNED 导入 ---

    @classmethod
    def import_step(cls, step_path: str, material: str = "MAT",
                    density: float = -1.0,
                    settings: dict | None = None) -> "DeckData | None":
        """STEP → GEOUNED 转换 → 解析 .mcnp → DeckData。"""
        if settings is None:
            settings = {}
        mcnp_path = run_step_converter("geouned", step_path, material,
                                       density, settings)
        if not mcnp_path:
            raise RuntimeError("GEOUNED 不可用或转换失败")
        return MCNPOutputParser.parse(mcnp_path, post_settings=settings)


# ===================================================================
# MCNPOutputParser — 解析 GEOUNED 生成的 MCNP 文件
# ===================================================================

class MCNPOutputParser:
    """解析 GEOUNED 生成的 .mcnp，提取栅元、曲面、TR 卡。

    使用方式：
        parser = MCNPOutputParser()
        deck = parser.parse("csg.mcnp")
    """

    @staticmethod
    def parse(mcnp_path: str,
              post_settings: dict | None = None) -> "DeckData | None":
        from app.generator.parsers import parse_inp_text
        from app.models import DeckData

        if not os.path.isfile(mcnp_path):
            return None

        with open(mcnp_path, "r", encoding="utf-8-sig") as f:
            text = f.read()

        # 预处理：取消注释材料卡，跳过注释掉的栅元（如体积计算卡）
        lines = text.splitlines()
        processed = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.match(r"^\s*c\s+M(\d+)\s*$", line, re.IGNORECASE):
                mat_num = re.match(
                    r"^\s*c\s+M(\d+)\s*$", line, re.IGNORECASE).group(1)
                processed.append(f"c M{mat_num}  $ TODO: add ZAID + fraction")
            elif re.match(r"^\s*c\s+\d+", line, re.IGNORECASE):
                # 注释掉的栅元（如体积计算卡 c 24 ...），跳过
                pass
            else:
                processed.append(line)
            i += 1

        modified_text = "\n".join(processed)

        # 分离 TR 卡
        tr_lines = []
        surf_lines = []
        for line in modified_text.splitlines():
            if re.match(r"^\s*\*?TR\d+\s", line, re.IGNORECASE):
                tr_lines.append(line)
            else:
                surf_lines.append(line)
        # 只识别曲面 + 栅元，截掉数据卡段（MODE/NPS/SDEF 等）
        surf_text = _strip_data_cards("\n".join(surf_lines))
        tr_text = "\n".join(tr_lines)
        surf_text = _format_surface_numbers(surf_text)

        deck, warnings = parse_inp_text(surf_text)

        # parse_inp_text 会用科学计数法重写曲面文本，这里再清一次
        if deck:
            deck.surfaces = _format_surface_numbers(deck.surfaces or "")

        # TR 卡放到 deck.tr_cards
        if tr_text and deck:
            deck.tr_cards = tr_text

        # 应用后处理设置（如 TMP）
        if post_settings and deck and deck.cells:
            tmp_val = post_settings.get("tmp", "")
            if tmp_val:
                for cell in deck.cells:
                    cell.tmp = tmp_val
            else:
                for cell in deck.cells:
                    cell.tmp = ""

        return deck


# ===================================================================
# StandardSurfaceConverter — 用 FreeCAD OCC 将 STEP 转成标准 MCNP 曲面
# ===================================================================

class StandardSurfaceConverter:
    """读取（分解后的）STEP 文件，用 FreeCAD OCC 生成标准 MCNP 曲面卡（无 GQ）。"""

    CONVERTER_SCRIPT = os.path.join(
        os.path.dirname(__file__), "step_to_standard.py")

    @classmethod
    def convert(cls, step_path: str, start_surf: int = 1,
                freecad_bin: str | None = None) -> "tuple[dict, list] | None":
        if freecad_bin is None:
            freecad_bin = StepImporter.detect_freecad()
        if not freecad_bin:
            raise RuntimeError("FreeCAD 未找到")

        python_exe = os.path.join(freecad_bin, "python.exe")
        if not os.path.isfile(python_exe):
            raise RuntimeError(f"FreeCAD Python 未找到: {python_exe}")

        cmd = [python_exe, cls.CONVERTER_SCRIPT,
               step_path, str(start_surf)]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
            env=os.environ,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"FreeCAD 转换失败:\n{result.stderr[:500]}")

        try:
            data = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            raise RuntimeError(
                f"FreeCAD 输出解析失败:\n{result.stdout[:500]}")

        if "error" in data:
            raise RuntimeError(f"FreeCAD 错误: {data['error']}")

        surfaces = {int(k): v for k, v in data.get("surfaces", {}).items()}
        tr_cards = {int(k): v for k, v in data.get("tr_cards", {}).items()}
        cells = data.get("cells", [])
        return surfaces, tr_cards, cells


# ===================================================================
# FreeCAD 检测
# ===================================================================

def _reg_query(key_path: str, value_name: str = "",
               wow64_flag: int = 0) -> str | None:
    """读取 Windows 注册表字符串值，返回 None 表示未找到。"""
    try:
        access = winreg.KEY_READ | wow64_flag if wow64_flag else winreg.KEY_READ
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, access) as k:
            return winreg.QueryValueEx(k, value_name)[0]
    except OSError:
        return None

def _find_freecad_from_registry() -> str | None:
    """尝试从注册表定位 FreeCAD.exe，同时检查 64/32 位视图。"""
    path = _reg_query(
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\FreeCAD.exe",
        wow64_flag=winreg.KEY_WOW64_64KEY,
    )
    if path and os.path.isfile(path):
        return path
    path = _reg_query(
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\FreeCAD.exe",
        wow64_flag=winreg.KEY_WOW64_32KEY,
    )
    if path and os.path.isfile(path):
        return path
    return None

def _find_freecad_from_common_dirs() -> str | None:
    """在常见安装目录下搜索 FreeCAD.exe。"""
    _SEARCH_BASES = [
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "D:\\",
        os.path.expanduser("~"),
    ]
    for base in _SEARCH_BASES:
        try:
            for name in os.listdir(base):
                if "FreeCAD" not in name:
                    continue
                freecad_dir = os.path.join(base, name)
                exe = os.path.join(freecad_dir, "bin", "FreeCAD.exe")
                if os.path.isfile(exe):
                    return exe
                try:
                    for subname in os.listdir(freecad_dir):
                        if "FreeCAD" in subname:
                            exe = os.path.join(freecad_dir, subname, "bin", "FreeCAD.exe")
                            if os.path.isfile(exe):
                                return exe
                except PermissionError:
                    continue
        except (FileNotFoundError, PermissionError, NotADirectoryError):
            continue
    return None

_freecad_cache_state: int = 0
_freecad_cache_path: str | None = None

def _cached_detect() -> str | None:
    """带缓存的 FreeCAD 检测。"""
    global _freecad_cache_state, _freecad_cache_path
    if _freecad_cache_state == 0:
        settings = QSettings("MCNPGen", "MCNPGenerator")
        saved = settings.value("freecad_path", "")
        if saved and os.path.isfile(saved):
            _freecad_cache_state = 1
            _freecad_cache_path = saved
            return os.path.dirname(saved)
        exe = _find_freecad_from_registry()
        if not exe:
            exe = _find_freecad_from_common_dirs()
        if exe and os.path.isfile(exe):
            settings.setValue("freecad_path", exe)
            _freecad_cache_state = 1
            _freecad_cache_path = exe
            return os.path.dirname(exe)
        _freecad_cache_state = -1
        _freecad_cache_path = None
    if _freecad_cache_state == 1 and _freecad_cache_path:
        return os.path.dirname(_freecad_cache_path)
    return None
