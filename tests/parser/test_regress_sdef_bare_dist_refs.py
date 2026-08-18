"""回归测试：SDEF 裸参数（无 =）分布引用丢失（inp02.i 实卡运行暴露，P0）。

现象（用户实测）：导入 inp02.i → 生成 → MCNP 运行：
  生成 SDEF 只剩 `SDEF  ERG=1`，`cel d4  x d1  y d2  z d3` 全丢 →
  MCNP 源变量表 cel/pos/x/y/z 全默认 + "source distribution 1/2/3/4 is not used"
  + "fatal error. v option on non-cell source distribution 4"。

根因：
  parse_sdef_fields 裸参数分支（core.py ~747）白名单只有
  PAR/SUR/NRM/TR/CCC/ARA/RATE —— CEL/X/Y/Z 裸参数（`cel d4`、`x d1`）落
  `ti += 1` 静默跳过 → adv.sdef_cel/sdef_pos_x/y/z 为空 → 生成器只发 ERG=1。
  （D-07 曾修 parse_sdef_simple 的白名单，parse_sdef_fields 未同步。）

期望修复后行为：
  裸 `CEL d4` / `X d1` / `Y d2` / `Z d3` 解析进 adv.sdef_cel / sdef_pos_x/y/z；
  生成器回放 `SDEF ... CEL=d4 X=d1 Y=d2 Z=d3 ERG=1`；MCNP 不再报
  "distribution not used" / "v option on non-cell source distribution"。
"""
import json
import re

from app.generator.inp_generator import generate_inp_from_deck
from app.generator.parsers import parse_inp_text
from app.generator.parsers.core import parse_data_cards
from tests.conftest import load_sample


SDEF_BARE = (
    "SDEF  CEL D4  X D1  Y D2  Z D3  ERG=1\n"
    "SI1  -5 5\n"
    "SP1  0 1\n"
    "SI4  L 1\n"
    "SP4  V\n"
)


def _shell_wrap(text: str) -> str:
    return f"C  shell\n1 0 -1\n\nC  surf\n1 pz -1e9\n\n{text}\n"


def test_bare_sdef_dist_refs_parsed_into_fields():
    r = parse_data_cards(SDEF_BARE.splitlines())
    assert (r.get("sdef_cel") or "").lower() == "d4", f"sdef_cel 丢失: {r.get('sdef_cel')!r}"
    assert (r.get("sdef_pos_x") or "").lower() == "d1", f"sdef_pos_x 丢失: {r.get('sdef_pos_x')!r}"
    assert (r.get("sdef_pos_y") or "").lower() == "d2", f"sdef_pos_y 丢失: {r.get('sdef_pos_y')!r}"
    assert (r.get("sdef_pos_z") or "").lower() == "d3", f"sdef_pos_z 丢失: {r.get('sdef_pos_z')!r}"
    assert r.get("sdef_erg") == "1"


def test_bare_sdef_round_trip_keeps_dist_refs():
    deck, _w = parse_inp_text(_shell_wrap(SDEF_BARE))
    out = generate_inp_from_deck(deck)
    sdef_line = next((l for l in out.splitlines() if l.strip().upper().startswith("SDEF")), "")
    for token in ("CEL=d4", "X=d1", "Y=d2", "Z=d3", "ERG=1"):
        assert token.lower() in sdef_line.lower(), f"SDEF 行缺 {token}: {sdef_line!r}"


def test_inp02_full_roundtrip_sdef_refs_preserved():
    text = load_sample("inp02.i")
    deck, _w = parse_inp_text(text)
    assert deck.adv.sdef_cel.strip().lower() == "d4", f"sdef_cel: {deck.adv.sdef_cel!r}"
    assert deck.adv.sdef_pos_x.strip().lower() == "d1", f"sdef_pos_x: {deck.adv.sdef_pos_x!r}"
    out = generate_inp_from_deck(deck)
    sdef_line = next((l for l in out.splitlines() if l.strip().upper().startswith("SDEF")), "")
    low = sdef_line.lower()
    for token in ("cel=d4", "x=d1", "y=d2", "z=d3", "erg=1"):
        assert token in low, f"inp02.i 生成 SDEF 缺 {token}: {sdef_line!r}"
    # 分布引用齐全 → MCNP 不再报 "distribution not used" 类致命错（引用了 D1~D4）
    assert re.search(r"cel=d4", low)
