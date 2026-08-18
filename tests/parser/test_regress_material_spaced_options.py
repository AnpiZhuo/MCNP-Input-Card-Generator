"""回归测试：材料 options 空格写法（`nlib .03d`）重解析时值被误当 ZAID（inp02.i m3 实卡）。

根因：
  _parse_material 对独立关键词（NLIB/GAS/PLIB/...）只收关键词本身、不收其值；
  生成器把 options 发射在 M{n} 卡头（`M3  nlib .03d` + 续行核素对），
  重解析拍平成一行后 `.03d` 落在核素对前面 → 被当 ZAID 与 `5010.0` 配对，
  第二代输出漂移（options 变 `nlib .750`、核素行错位）→ inp02.i 全文件不动点破坏。

期望修复后行为：
  独立关键词后的下一 token 若非 ZAID 形态（3 位以上数字开头），作为该关键词的
  值一并收入 options（MCNP 合法空格写法，C810 实卡依据 inp02.i m3）。
"""
from app.generator.inp_generator import generate_inp_from_deck
from app.generator.parsers import parse_inp_text
from app.generator.parsers.core import _parse_material
from tests.conftest import load_sample


def _pairs(mat) -> list[tuple[str, str]]:
    return [(r.zaid, r.fraction) for r in mat.rows]


def test_spaced_keyword_value_consumed_as_option():
    """`M3 nlib .03d 5010.0 .250 ...`：`.03d` 应为 nlib 的值，不是 ZAID。"""
    mat = _parse_material(["M3", "nlib", ".03d", "5010.0", ".250",
                           "5011.40c", ".750"], "M3")
    assert mat.options == "nlib .03d", f"options 错误: {mat.options!r}"
    assert _pairs(mat) == [("5010.0", ".250"), ("5011.40c", ".750")]


def test_spaced_keyword_value_not_swallowing_zaid():
    """关键词后紧跟真 ZAID（3+ 位数字开头）时不得吞值：`m1 nlib 92235.66c 1`。"""
    mat = _parse_material(["M1", "nlib", "92235.66c", "1"], "M1")
    assert _pairs(mat) == [("92235.66c", "1")], f"核素对被破坏: {_pairs(mat)}"
    assert "92235.66c" not in mat.options


def test_trailing_spaced_option_still_parsed():
    """原有尾部空格写法（inp02.i 原文顺序）保持正确。"""
    mat = _parse_material(["M3", "5010.0", ".250", "5011.40c", ".750",
                           "nlib", ".03d"], "M3")
    assert mat.options == "nlib .03d"
    assert _pairs(mat) == [("5010.0", ".250"), ("5011.40c", ".750")]


def test_inp02_m3_roundtrip_fixed_point():
    """inp02.i 全文件：第二代输出不得再漂移（M3 nlib 空格写法往返稳定）。"""
    text = load_sample("inp02.i")
    deck, _w = parse_inp_text(text)
    g1 = generate_inp_from_deck(deck)
    deck2, _w2 = parse_inp_text(g1)
    g2 = generate_inp_from_deck(deck2)
    m3 = next(m for m in deck2.materials if m.number == 3)
    assert m3.options == "nlib .03d", f"重解析 options 漂移: {m3.options!r}"
    assert _pairs(m3) == [("5010.0", ".250"), ("5011.40c", ".750")], \
        f"重解析核素对漂移: {_pairs(m3)}"
    assert g2 == g1, "inp02.i 全文件不动点被破坏（第二代输出漂移）"
