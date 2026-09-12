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
import re
import tempfile

try:
    from freecad_locator import bin_dir, save as save_freecad_locator
except ImportError:  # 测试/直接 import app 包时 freecad_locator 在 app/ 下
    from app.freecad_locator import bin_dir, save as save_freecad_locator


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


def flat_cell_json(row) -> dict:
    """栅元行 → STEP 导入的平铺 cell JSON（契约见 docs/contracts/api.yaml）。

    入参可以是：
      - ``CellRow``（deck.cells 的真实类型：kind="cell" 时嵌套 CellData，
        kind="raw" 时是 #ifdef 之类的原样条件行）
      - ``CellData``（平铺对象，历史调用方）
      - 上述两者的 dict 形式

    出参：
      - 栅元行 → ``{number, material, density, surface_expr, comment}``
        （平铺 snake_case，前端 cellBridge.deckToLocalCells 认这个格式）
      - 原样条件行 → ``{kind:"raw", text}`` 原样透传，不丢行。

    历史坑：这里曾经直接读 ``row.number``。deck.cells 改成 CellRow 判别联合
    后该字段不存在，STEP 导入必然 500（AttributeError）。序列化只此一处。
    """
    kind = (row.get("kind", "cell") if isinstance(row, dict)
            else getattr(row, "kind", "cell"))
    if kind == "raw":
        text = (row.get("text", "") if isinstance(row, dict)
                else getattr(row, "text", ""))
        return {"kind": "raw", "text": text or ""}

    cell = (row.get("cell") if isinstance(row, dict)
            else getattr(row, "cell", None))
    if cell is None:
        cell = row  # 平铺 CellData / 平铺 dict

    def _f(name: str, default=""):
        if isinstance(cell, dict):
            return cell.get(name, default)
        return getattr(cell, name, default)

    density = _f("density")
    return {
        "number": _f("number", ""),
        "material": str(_f("material")),
        "density": str(density) if density else "",
        "surface_expr": _f("surface_expr") or "",
        "comment": _f("comment") or "",
    }


def geometry_deck_response(surfaces_text: str, tr_cards_text: str,
                           cells_list: list) -> dict:
    """STEP 导入响应的几何 deck JSON —— surfaces/tr_cards/cells 三件套。

    cells 统一经 ``flat_cell_json`` 归一化：调用方直接传 ``deck.cells``
    （CellRow 列表）即可，不要再在 handler 里手写字段映射（漏字段/字段名
    漂移都曾在这里炸过）。
    """
    return {
        "surfaces": surfaces_text or "",
        "tr_cards": tr_cards_text or "",
        "cells": [flat_cell_json(c) for c in (cells_list or [])],
    }


# ===================================================================
# run_step_converter — GEOUNED 转换
# ===================================================================

class StepConversionError(RuntimeError):
    """STEP→MCNP 转换失败，message 可直接展示给用户。"""


def run_step_converter(name: str, step_path: str, material: str,
                       density: float, settings: dict,
                       freecad_bin: str | None = None) -> str:
    """运行 STEP→MCNP 转换（当前仅 GEOUNED），返回 MCNP 文件路径。

    失败时抛 StepConversionError（message 含具体原因，不吞异常）。
    """
    if name != "geouned":
        raise StepConversionError(f"未知转换器: {name}（当前仅支持 geouned）")
    from step_importer_geouned import GeoUnedConverter
    conv = GeoUnedConverter(freecad_bin=freecad_bin)
    reason = conv.unavailable_reason()
    if reason:
        raise StepConversionError(f"GEOUNED 不可用：{reason}")
    work_dir = tempfile.mkdtemp(prefix="geouned_")
    try:
        return conv.run(step_path, material, density, work_dir, settings)
    except StepConversionError:
        raise
    except Exception as e:
        raise StepConversionError(f"GEOUNED 转换失败：{e}") from e


# ===================================================================
# StepImporter — 公共接口
# ===================================================================

class StepImporter:
    """STEP 导入器。封装 GEOUNED 外部转换器的调用和输出解析。"""

    # --- FreeCAD 检测（统一走 freecad_locator seam）---

    @classmethod
    def detect_freecad(cls) -> str | None:
        """检测 FreeCAD 可执行文件路径。返回 bin 目录或 None。"""
        return bin_dir()

    @classmethod
    def save_freecad_path(cls, exe_path: str) -> None:
        """保存 FreeCAD 路径到 config.json（唯一持久化存储）。"""
        save_freecad_locator(exe_path)

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


