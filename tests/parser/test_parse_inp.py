"""解析管线单测：parse_inp_text 总入口（DeckData 组装）。"""
from app.generator.parsers import parse_inp_text


MINIMAL = (
    "test deck\n"
    "1 1 -1.0 -1 imp:n=1\n"
    "2 0 -2 imp:n=0\n"
    "\n"
    "1 rcc 0 0 0 0 10 0 2\n"
    "2 pz 10\n"
    "\n"
    "mode n\n"
    "m1 92235 -0.05\n"
    "sdef pos 0 0 0 erg=14\n"
    "nps 100000\n"
)


def test_parse_inp_text_returns_deck_and_warnings():
    deck, warnings = parse_inp_text(MINIMAL)
    assert isinstance(warnings, list)
    assert deck.basic.title == "test deck"
    assert deck.basic.mode_n is True
    assert deck.basic.nps == "100000"
    assert len(deck.cells) == 2
    assert len(deck.surfaces.splitlines()) == 2
    assert len(deck.materials) == 1
    assert len(deck.sources) == 1
    assert deck.sources[0].erg == "14"


def test_parse_inp_text_sdef_pos():
    deck, _ = parse_inp_text(MINIMAL)
    s = deck.sources[0]
    assert s.pos_x == "0" and s.pos_y == "0" and s.pos_z == "0"


def test_parse_inp_text_imp_applied_by_cell_number():
    deck, _ = parse_inp_text(MINIMAL)
    cells = [c.cell for c in deck.cells if c.kind == "cell"]
    cells.sort(key=lambda c: c.number)
    assert cells[0].imp_n == "1"
    assert cells[1].imp_n == "0"


def test_parse_inp_text_tr_cards():
    text = (
        "t\n1 1 -1\n\n1 pz 0\n\n"
        "mode n\ntr1 1 0 0 0 1 0 0 0 1 5 0 0\n"
    )
    deck, _ = parse_inp_text(text)
    assert "tr1" in deck.tr_cards.lower()


def test_parse_inp_text_returns_warnings_on_malformed():
    deck, warnings = parse_inp_text("title\n\n\nmode n\n")
    assert isinstance(warnings, list)
