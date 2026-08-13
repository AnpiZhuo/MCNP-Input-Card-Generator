"""回归测试：cell 卡文本模式→表单模式数据丢失（用户反馈 #6，P0 最严重）。

根因（已修，2026-08-13）：
  gui/backend/api_server.py:714 _handle_text_to_section 对 section=="cells" 用独立 shell，
  把用户 cell 文本放入【栅元段】（而非 shell 尾部数据段）——
  原 shell `C  shell\n1 0 -1\n\nC  surf\n1 pz -1e9\n\n{text}\n` 把 {text} 追加在曲面段之后，
  split_sections 全部分到 data_lines，用户栅元字段全丢（只剩 shell 假栅元 "1 0 -1"）。
  修复：cells 分支 shell = `{text}\n\nC  surf\n1 pz -1e9\n\nMODE N\n`，parse_cells 字段解析完整。
对照：materials/tally 分支保持原 shell（本属数据段，解析正常）——两个对照用例确认不回归。
"""
import dataclasses

from app.generator.parsers import parse_inp_text


def _deck_to_cells(deck) -> list:
    """复刻 api_server.py:444 _deck_to_frontend_dict 的 cells 序列化。"""

    def to_dict(o):
        if dataclasses.is_dataclass(o):
            return {k: to_dict(v) for k, v in dataclasses.asdict(o).items()}
        if isinstance(o, list):
            return [to_dict(x) for x in o]
        return o

    d = to_dict(deck)
    for c in d.get("cells", []):
        if c.get("kind") == "raw":
            continue
        cell = c.get("cell") or {}
        cell["num"] = str(cell.get("number", ""))
        cell["surfaces"] = cell.get("surface_expr", "")
        cell["impN"] = cell.get("imp_n", "")
        cell["impP"] = cell.get("imp_p", "")
        cell["impE"] = cell.get("imp_e", "")
    return d.get("cells", [])


def _shell_wrap_cells(text: str) -> str:
    """复刻 api_server.py:714 _handle_text_to_section 修复后 cells 分支的 shell 包裹（cell 文本入栅元段）。"""
    return f"{text}\n\nC  surf\n1 pz -1e9\n\nMODE N\n"


def _shell_wrap_data(text: str) -> str:
    """复刻 api_server.py:714 materials/tally 分支的 shell 包裹（数据段，保持原行为）。"""
    return f"C  shell\n1 0 -1\n\nC  surf\n1 pz -1e9\n\n{text}\n"


def test_cell_text_to_section_preserves_user_cells():
    """多栅元（material/density/surface_expr/imp/vol/tmp/pwt/comment）文本 → 表单：字段全保留。"""
    text = (
        "1 1 -2.7 -1 2 imp:n=1 vol=3.14 tmp=2.53e-8 $ fuel rod\n"
        "2 0 3 #1 imp:n=0 $ void\n"
        "3 2 -2.7 -4 3 imp:n=1 pwt=1.0"
    )
    deck, _warnings = parse_inp_text(_shell_wrap_cells(text))
    cells = _deck_to_cells(deck)

    # 用户 3 个栅元全部保留，无 shell 假栅元混入
    assert len(cells) == 3
    c1 = cells[0]["cell"]
    assert (c1["number"], c1["material"], c1["density"], c1["surface_expr"], c1["imp_n"]) == (
        1, "1", "-2.7", "-1 2", "1",
    )
    assert (c1["vol"], c1["tmp"], c1["comment"]) == ("3.14", "2.53e-8", "fuel rod")
    c2 = cells[1]["cell"]
    assert (c2["number"], c2["material"], c2["surface_expr"], c2["imp_n"], c2["comment"]) == (
        2, "0", "3 #1", "0", "void",
    )
    c3 = cells[2]["cell"]
    assert (c3["number"], c3["material"], c3["pwt"]) == (3, "2", "1.0")

    # 用户 cell 行不再落入 other_cards
    other = deck.adv.other_cards
    assert "imp:n=1 vol=3.14" not in other
    assert "3 2 -2.7 -4 3" not in other


def test_control_materials_and_tally_unaffected_by_shell():
    """对照：materials/tally 本属数据段，经原 shell 解析正常——仅 cells 受损（已修）。"""
    # materials
    deck_m, _ = parse_inp_text(_shell_wrap_data("M1 1001 1.0\nM2 92235 0.05 1001 0.95"))
    assert [(m.number, len(m.rows)) for m in deck_m.materials] == [(1, 1), (2, 2)]
    # tally
    deck_t, _ = parse_inp_text(_shell_wrap_data("F4:N 1 2\nE4 0.1 1 10"))
    assert len(deck_t.tally.tallies) == 1
    td = deck_t.tally.tallies[0]
    assert (td.type, td.number, td.particles, td.params, td.generate_en) == (
        "F4", 4, ["n"], "1 2", True,
    )


def test_control_parse_cells_itself_preserves_fields():
    """对照：cell 文本置于正确栅元段时，parse_cells 字段解析完整（字段丢失非 parse_cells 之过）。"""
    text = "1 1 -2.7 -1 2 imp:n=1 vol=3.14 tmp=2.53e-8 pwt=1.0 fcl=0.5"
    deck, _ = parse_inp_text(f"C  shell\n{text}\n\nC  surf\n1 pz -1e9\n\nMODE N\n")
    assert len(deck.cells) == 1
    c = deck.cells[0].cell
    assert (c.number, c.material, c.density, c.surface_expr, c.imp_n) == (1, "1", "-2.7", "-1 2", "1")
    assert (c.vol, c.tmp, c.pwt, c.fcl) == ("3.14", "2.53e-8", "1.0", "0.5")
