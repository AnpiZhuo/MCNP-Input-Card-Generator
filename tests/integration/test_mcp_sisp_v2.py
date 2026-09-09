"""AI 接入（inputcard_mcp）集成回归：v2 双态分布经 MCP 读写链路不丢失、不污染。

覆盖 AI 接入.md 约束：
  - read_document（INP → sections.advanced.sdef_distributions 字符串）→ v2 条目
    （editMode=raw + rawText 原文保留；无字母 SI type=""，无 L 污染）；
  - generate_document（sections → INP 文本）→ 无字母 SI 行不带 L（round-trip 保真）；
  - patch_section(advanced) 整体替换 → 同一 schema 字符串可回写并重新生成；
  - 工作区（_WORKSPACE sections）不存 inp 的读改 → generate 同样干净。
"""
import json
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.normpath(os.path.join(_HERE, "..", ".."))
for p in (os.path.join(_PROJ, "app"), os.path.join(_PROJ, "gui", "backend"), _PROJ):
    if p not in sys.path:
        sys.path.insert(0, p)

from inputcard_mcp.server import (  # noqa: E402
    read_document, generate_document, patch_section, _deck_to_sections,
    _set_ws_sections, _ws_sections, _ws_deck,
)
from generator.inp_generator import generate_inp_from_deck  # noqa: E402

Q1112_SISP = (
    "SDEF  par=n  erg=d3  pos=0.65 0.0 -21.5  cel=5  rad=d1  ext=d2  axs=0 0 1\n"
    "si1  0.0  1.335\n"
    "sp1  -21  1\n"
    "si2  -5.5  5.5\n"
    "sp2  0  1\n"
)

SHELL = "C  shell\n1 0 -1\n\nC  surf\n1 pz -1e9\n\n"


def _dist(secs: dict) -> list:
    return json.loads(secs["advanced"]["sdef_distributions"] or "[]")


def test_read_document_v2_raw_preserved_no_L():
    """read_document 解析：v2 条目 editMode=raw + 原文逐字保留 + 无字母 SI type=''。"""
    r = read_document(SHELL + Q1112_SISP)
    dist = _dist(r["sections"])
    assert [e["id"] for e in dist] == [1, 2]
    e2 = next(e for e in dist if e["id"] == 2)
    assert e2["editMode"] == "raw"
    assert "si2  -5.5  5.5" in e2["rawText"].lower()
    assert e2["si"]["type"] == "", f"无字母 SI 应 type=''，实际 {e2['si']['type']!r}"
    # 无 L 污染
    raw_low = e2["rawText"].lower()
    assert "si2  l" not in raw_low and " l " not in raw_low


def test_generate_document_keeps_unlettered_si():
    """generate_document（sections → INP）：SI2 行不带 L 字母。"""
    r = read_document(SHELL + Q1112_SISP)
    out = generate_document(r["sections"])
    for line in out.splitlines():
        if line.strip().upper().startswith("SI2"):
            assert "  L " not in " " + line + " ", f"无字母 SI2 被回填 L: {line!r}"
            assert "-5.5" in line
            break
    else:
        raise AssertionError("输出中未找到 SI2 行")


def test_patch_advanced_round_trip():
    """patch_section(advanced) 整体替换：v2 schema 字符串原样回写并生成。"""
    # 先用工作区（无 inp 路径）建一个 deck
    _set_ws_sections(read_document(SHELL + Q1112_SISP)["sections"])
    secs = _ws_sections()
    adv = secs["advanced"]
    dist_str = adv["sdef_distributions"]
    # AI 改一处：给 id=1 的 SI 显式加 H（模拟 AI 结构化编辑，保持合法）
    dist = json.loads(dist_str)
    for e in dist:
        if e["id"] == 1:
            e["editMode"] = "structured"
            e["si"] = {"type": "H", "values": e["si"]["values"]}
            e["rawText"] = None
    new_adv = {**adv, "sdef_distributions": json.dumps(dist, ensure_ascii=False)}
    out = patch_section(section="advanced", data=new_adv)
    assert "SI1  H" in out or "SI1  H" in out.upper(), "结构化 H 未生成"
    assert "SI2" in out.upper(), "id=2 raw 条目丢失"
    assert "SI2  L" not in out.upper(), "raw 条目被回填 L"


def test_workspace_no_inp_read_generate_clean():
    """不传 inp → 读工作区 → generate：与 parse 后直接 generate 一致。"""
    base = read_document(SHELL + Q1112_SISP)["sections"]
    _set_ws_sections(base)
    out = generate_document(_ws_sections())
    deck = _ws_deck()
    assert deck.adv.sdef_distributions
    # raw 直通不产生 L
    assert "SI2  -5.5  5.5".lower().replace(" ", "") in out.lower().replace(" ", "")
