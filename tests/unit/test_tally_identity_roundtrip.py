# -*- coding: utf-8 -*-
"""回归：计数卡**身份字段**（`fn_prefix` / `number_suffix`）必须过得了「前后端缝」。

用户报告（2026-09-26，GUI 实测两条）：
  ① 「计数卡的前缀，`*` 号，解析时无法传入」—— 导入 `*F4:N 1` 后界面「前缀」列仍显示"无"；
  ② 「自己点选后，点生成时也没有」—— 在界面里选了 `*`、点生成，INP 里仍是 `F4:N`。

根因不在引擎里，而在**前后端缝**的两个映射函数上（两头都漏同一对字段）：
  · `api_server._deck_to_frontend_dict`（后端 → 前端回显）漏 `fn_prefix` / `number_suffix`
    ⇒ 前端永远读不到，前缀下拉框恒为"无"；
  · `api_server._tally_from_dict`（前端 → 后端）也漏 ⇒ 用户选了 `*` 也传不上来，
    连"传上来了但被丢"都看不出来（全程无报错）。
引擎侧本来是对的（`parse_f_tally` 收、`_generate_tallies` 放），
`tests/parser/test_regress_fm_prefix.py` 只测了引擎侧，所以这个缝一直是绿的。

顺带同一类缺陷：`number_suffix`（`F5X:N` 环探测器）——漏了它，环探测器会静默退化成点探测器。

本文件锁死：导入保真、界面选择保真、端到端往返保真（含 `+F8` 与 F5 成像 `FIC5`）。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
for _p in (ROOT, os.path.join(ROOT, "app"), os.path.join(ROOT, "gui", "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from api_server import deck_from_json, deck_to_frontend_dict  # noqa: E402
from app.generator.inp_generator import generate_inp_from_deck  # noqa: E402
from app.generator.parsers import parse_inp_text  # noqa: E402

INP = (
    "tally identity\n"
    "1 0 -1 imp:n=1\n"
    "\n"
    "1 so 10\n"
    "\n"
    "MODE N\n"
    "*F4:N 1\n"
    "F5X:N 0 0 0 1\n"
    "F6:P 1\n"
    "NPS 1000\n"
)


def _frontend_payload(deck):
    """前端 App.tsx handleGenerate 的真实载荷形状：tally.tallies（snake/camel 混合口径）。"""
    fe = deck_to_frontend_dict(deck, include_frontend_aliases=True)
    return {"basic": fe["basic"], "surfaces": fe["surfaces"], "cells": fe["cells"],
            "materials": fe["materials"], "sources": fe["sources"],
            "tally": {"tallies": fe["tallies"]}, "adv": fe["adv"]}


# ── ① 解析侧：后端 → 前端回显必须带身份字段 ──

def test_parse_to_frontend_dict_carries_identity_fields():
    deck, _w = parse_inp_text(INP)
    back = {(t.type, t.number): t for t in deck.tally.tallies}
    assert back[("F4", 4)].fn_prefix == "*", "引擎侧应已收到 *F4"
    assert back[("F5", 5)].number_suffix == "X", "引擎侧应已收到 F5X"
    fe = deck_to_frontend_dict(deck)
    got = {(t["type"], t["number"]): t for t in fe["tallies"]}
    assert got[("F4", 4)]["fn_prefix"] == "*", f"回显丢了 *：{got[('F4', 4)]}"
    assert got[("F5", 5)]["number_suffix"] == "X", f"回显丢了 X：{got[('F5', 5)]}"
    assert got[("F6", 6)]["fn_prefix"] == "" and got[("F6", 6)]["number_suffix"] == ""


# ── ② 生成侧：前端传上来的身份字段必须被收下并回放 ──

def test_deck_from_json_reads_identity_fields():
    deck = deck_from_json({"tallies": [
        {"type": "F4", "number": 4, "particle": "n", "params": "1",
         "enableEn": False, "enableTn": False, "fn_prefix": "*", "number_suffix": ""},
        {"type": "F5", "number": 5, "particle": "n", "params": "0 0 0 1",
         "enableEn": False, "enableTn": False, "fnPrefix": "+", "numberSuffix": "y"},
    ]})
    t4, t5 = deck.tally.tallies
    assert t4.fn_prefix == "*" and t4.number_suffix == ""
    # camelCase 也认（外部接入/旧前端两种写法都收）
    assert t5.fn_prefix == "+" and t5.number_suffix == "y"


def test_generate_replays_ui_selected_prefix_and_suffix():
    """用户「自己点选 * 之后点生成」的真实路径：deck.tallies → 生成。"""
    body = {"basic": {"title": "t", "mode_n": True, "nps": "1000"},
            "tallies": [{"type": "F4", "number": 4, "particle": "n", "params": "1 2",
                         "enableEn": False, "enableTn": False,
                         "fn_prefix": "*", "number_suffix": ""},
                        {"type": "F5", "number": 5, "particle": "n", "params": "0 0 0 1",
                         "enableEn": False, "enableTn": False,
                         "fn_prefix": "", "number_suffix": "X"}]}
    out = generate_inp_from_deck(deck_from_json(body))
    assert "*F4:N  1 2" in out, f"界面选的 * 没落到 INP：\n{out}"
    assert "F5X:N  0 0 0 1" in out, f"环探测器后缀没落到 INP：\n{out}"


# ── ③ 端到端：导入 → 前端回显 → 回存 → 生成 → 再解析（身份字段逐代不丢）──

def test_full_seam_roundtrip_keeps_star_and_ring_suffix():
    deck, _w = parse_inp_text(INP)
    fe = deck_to_frontend_dict(deck, include_frontend_aliases=True)
    front_deck = deck_from_json(_frontend_payload(deck))   # 前端原样回存
    out = generate_inp_from_deck(front_deck)
    assert "*F4:N  1" in out, f"往返后 * 丢了：\n{out}"
    assert "F5X:N  0 0 0 1" in out, f"往返后 X 丢了：\n{out}"
    # 前端回显里这两个键要在（否则界面下拉框永远显示"无"）
    assert fe["tallies"][0]["fn_prefix"] == "*"
    # 再解析一代：仍然是 *F4 / F5X
    deck2, _w2 = parse_inp_text(out)
    ident = {(t.type, t.number): (t.fn_prefix, t.number_suffix) for t in deck2.tally.tallies}
    assert ident[("F4", 4)] == ("*", "")
    assert ident[("F5", 5)] == ("", "X")


# ── ④ 其它前缀形态：`+F8` 与 F5 成像 `FIC5` ──

def test_plus_prefix_and_imaging_prefix_survive_seam():
    body = {"basic": {"title": "t"}, "tallies": [
        {"type": "F8", "number": 8, "particle": "p", "params": "1",
         "enableEn": False, "enableTn": False, "fn_prefix": "+"},
        {"type": "F5", "number": 5, "particle": "n", "params": "1 2",
         "enableEn": False, "enableTn": False, "fn_prefix": "FIC"},
    ]}
    out = generate_inp_from_deck(deck_from_json(body))
    assert "+F8:P  1" in out, f"+ 前缀丢失：\n{out}"
    assert "FIC5:N  1 2" in out, f"成像前缀丢失：\n{out}"
    # 回显也要带（前端下拉框靠它决定显示哪一项）
    fe = deck_to_frontend_dict(deck_from_json(body))
    assert [t["fn_prefix"] for t in fe["tallies"]] == ["+", "FIC"]
