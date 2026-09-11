"""
技术债联动测试（P0-5）—— **已全部清偿，当前应全绿**（2026-09-10 更正）。

F#1  raw_overrides 8 key 字符化 + 1145 门控 → 见 tests/unit/test_generator_overrides.py
F#3/F#7  AST 扫描：FunctionDef 内无 import json/re/sys；pymcnp 须模块导入期 fail-fast
F#4      单源 Dn 分支含扩展字段 vs 普通分支不含、公共字段两分支等价
F#5/F#6  概率归一化表驱动（unit）+ kitchen-sink 多源全字段在 SDEF 或 SI 各出现一次

⚠️ **历史提示（原文已过时，勿照旧理解）**：本文件初版写"这些测试断言的是【重构后应达成】的状态，
当前应为 RED（红 = 符合预期）"。**该表述已作废**：F#1~F#7 与 F-A~F-D 均已清偿，各用例现在应当
**GREEN**。读到"当前应为 RED"之类的旧注释时，一律以**代码现状**为准——
**红灯就是真红灯，不是"预期红"，不要容忍**（审计 TD-09）。
"""
import ast
import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
INP_GEN = PROJECT_DIR / "app" / "generator" / "inp_generator.py"
PARSERS_CORE = PROJECT_DIR / "app" / "generator" / "parsers" / "core.py"
PARSERS_INIT = PROJECT_DIR / "app" / "generator" / "parsers" / "__init__.py"


# ── AST 辅助 ─────────────────────────────────────────────
def function_level_imports(file_path: Path, mod_name: str) -> list[str]:
    """返回 (行号, import 语句) 列表：在 FunctionDef 内部的 mod_name 导入。"""
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Import):
                for alias in child.names:
                    if alias.name == mod_name or alias.name.startswith(mod_name + "."):
                        hits.append((child.lineno, f"import {alias.name}"))
            elif isinstance(child, ast.ImportFrom):
                if child.module and (child.module == mod_name or
                                     child.module.startswith(mod_name + ".")):
                    hits.append((child.lineno, f"from {child.module} import ..."))
    return hits


def module_level_pymcnp_import(file_path: Path) -> list[int]:
    """返回模块顶层（非函数内）的 pymcnp import 行号。"""
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    lines = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pymcnp" or alias.name.startswith("pymcnp."):
                    lines.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module == "pymcnp" or node.module.startswith("pymcnp.")):
                lines.append(node.lineno)
    return lines


# ── F#3：FunctionDef 内 import json/re/sys（已清偿 → 应 GREEN）──────
def test_f3_no_function_level_import_json_in_inp_generator():
    """inp_generator.py 函数内不得 import json（模块级已有）。

    P1 F#3（commit c774e56）已清偿：`_generate_kcode`、`_generate_structured_distributions`
    的 `import json as _json` 已删除，改用模块级 json。当前应为 GREEN。
    """
    hits = function_level_imports(INP_GEN, "json")
    assert hits == [], f"inp_generator.py 函数内 import json: {hits}"


def test_f3_no_function_level_import_sys_in_parsers():
    """parsers/core.py 与 __init__.py 函数内不得 import sys。

    P1 F#3（commit c774e56）已清偿：core.py `_parse_card_with_continuation`、
    `parse_data_cards` 与 __init__.py `parse_inp_text` 的函数内 import sys 已删除
    （连带 [E0DBG] 调试 print）。当前应为 GREEN。
    """
    core_hits = function_level_imports(PARSERS_CORE, "sys")
    init_hits = function_level_imports(PARSERS_INIT, "sys")
    assert core_hits == [], f"parsers/core.py 函数内 import sys: {core_hits}"
    assert init_hits == [], f"parsers/__init__.py 函数内 import sys: {init_hits}"


def test_f3_no_function_level_import_re_in_inp_generator():
    """inp_generator.py 函数内不得 import re（模块级已有）。当前应为 GREEN。"""
    hits = function_level_imports(INP_GEN, "re")
    assert hits == [], f"inp_generator.py 函数内 import re: {hits}"


# ── F#7：pymcnp 须在模块导入期 fail-fast（已清偿 → 应 GREEN）────────
def test_f7_pymcnp_imported_at_module_level():
    """inp_generator.py 的 pymcnp 导入必须在模块顶层（导入期 fail-fast）。

    P1 F#7（commit bf0a2c7）已清偿：`from pymcnp import inp as pymcnp_inp` 已在模块顶部
    （banners import 之后），导入期即检测 pymcnp 缺失。当前应为 GREEN。
    """
    module_lines = module_level_pymcnp_import(INP_GEN)
    assert module_lines, (
        "inp_generator.py 无模块顶层 pymcnp 导入（当前在 _generate_basic 函数内）"
    )


def test_f7_pymcnp_function_level_import_absent():
    """inp_generator.py 函数内不得 import pymcnp。P1 F#7 已清偿，当前 GREEN。"""
    hits = function_level_imports(INP_GEN, "pymcnp")
    assert hits == [], f"inp_generator.py 函数内 pymcnp import: {hits}"


# ── F#4：单源 Dn 分支 vs 普通分支（已清偿 → 应 GREEN）────────────────
def test_f4_extended_fields_only_in_dn_branch():
    """Dn/扩展分支（247-281）含 6 扩展字段，普通分支（283-301）不含。

    用 AST 断言：`if has_d_or_extra:` 分支（Dn 分支）中 SUR/NRM/TR/CCC/ARA/RATE
    各出现一次；else 普通分支不出现。
    """
    from app.generator.inp_generator import _generate_single_source
    from app.models import SourceData

    ext = SourceData(number=1, erg="D1", pos_x="0", pos_y="0", pos_z="0",
                     sur="1", nrm="1", tr="1", ccc="1", ara="1.0", rate="1e6")
    plain = SourceData(number=1, erg="14.0", pos_x="0", pos_y="0", pos_z="0")
    ext_text = " ".join(_generate_single_source(ext))
    plain_text = " ".join(_generate_single_source(plain))
    for tok in ("SUR=1", "NRM=1", "TR=1", "CCC=1", "ARA=1.0", "RATE=1e6"):
        assert tok in ext_text, f"Dn 分支应含扩展字段 {tok}"
        assert tok not in plain_text, f"普通分支不应含扩展字段 {tok}"


def test_f4_common_fields_equivalent_across_branches():
    """两分支共享的公共字段（除触发分支的字段外）输出应逐 token 一致。"""
    from app.generator.inp_generator import _generate_single_source
    from app.models import SourceData

    # srcB 用 Dn 引用触发 has_d_or_extra → Dn 分支；srcA 走普通分支
    common = dict(par="1", wgt="1.0", cel="1", tme="0.0", vec="0 0 1",
                  axs="0 0 1", rad="0.5", ext="0.0", pos_x="0", pos_y="0", pos_z="0")
    src_a = SourceData(number=1, erg="14.0", **common)
    src_b = SourceData(number=1, erg="D1", **common)
    text_a = _generate_single_source(src_a)[0]
    text_b = _generate_single_source(src_b)[0]

    def tokens(text):
        return {t.split("=")[0]: t for t in text.split() if "=" in t}

    ta, tb = tokens(text_a), tokens(text_b)
    for key in ("PAR", "WGT", "CEL", "TME", "VEC", "AXS", "RAD", "EXT", "POS"):
        assert ta.get(key) == tb.get(key), f"公共字段 {key} 两分支不一致: {ta.get(key)} vs {tb.get(key)}"


# ── F#5/F#6：概率归一化（unit 已覆盖）+ 多源全字段覆盖 ───
def test_f6_kitchen_sink_multi_source_all_fields_present():
    """多源 kitchen-sink：每个 SDEF 字段名在输出（SDEF 或 SI 卡）各出现一次。"""
    from app.generator.inp_generator import _generate_multi_source
    from app.models import SourceData

    srcs = [
        SourceData(number=1, par="1", erg="14.0", pos_x="0", pos_y="0", pos_z="0",
                   dir_="1", wgt="1.0", cel="1", tme="0.0", vec="0 0 1",
                   axs="0 0 1", rad="0.5", ext="0.0", sur="1", nrm="1",
                   tr="1", ccc="1", ara="1.0", rate="1e6"),
        SourceData(number=2, par="1", erg="2.0", pos_x="1", pos_y="1", pos_z="1",
                   dir_="-1", wgt="0.5", cel="2", tme="1.0", vec="1 0 0",
                   axs="1 0 0", rad="1.0", ext="1.0", sur="2", nrm="-1",
                   tr="2", ccc="2", ara="2.0", rate="2e6"),
    ]
    lines = _generate_multi_source(srcs)
    text = "\n".join(lines)
    # 每个字段名应出现（在 SDEF 或 SI 卡中）
    for field in ("PAR", "ERG", "DIR", "WGT", "CEL", "TME", "VEC", "AXS",
                  "RAD", "EXT", "SUR", "NRM", "TR", "CCC", "ARA", "RATE", "POS"):
        assert field in text, f"多源输出缺少字段 {field}\n{text}"
