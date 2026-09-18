# -*- coding: utf-8 -*-
"""回归：MCP /workspace 往返必须保住前端计数卡（tallies）。

背景（2026-09-17 实证的真 bug）：前端 `deck.tallies`（TallyTab 的计数列表）是**顶层数组**，
而 `deck.tally` 只装网格/截断/FMESH/PTRAC。前端把整份 deck PUT 到 /workspace 时，
`deck_from_json` 只读 `data["tally"]` ⇒ 后端存下的计数列表恒为空；GET 回显
`deck.tallies = []`，前端 `useDeckSynced` 判定「deck 与本地不等价」就整份采纳空列表
⇒ **计数卡列表被清空、回到初始状态**（用户报的症状）。

本测试锁死：前端形态 deck（顶层 tallies）经「PUT 存 → GET 取」后计数不丢。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
for _p in (ROOT, os.path.join(ROOT, "app"), os.path.join(ROOT, "gui", "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from api_server import deck_from_json, deck_to_frontend_dict  # noqa: E402
from inputcard_mcp import server  # noqa: E402


def _frontend_deck():
    """前端 DeckContext 的真实形状：tallies 在顶层，tally 装网格/FMESH/PTRAC。"""
    return {
        "basic": {"title": "t", "mode_n": True, "nps": "1000"},
        "surfaces": "1 pz 0\n", "tr_cards": "",
        "cells": [], "materials": [], "sources": [],
        "tallies": [
            {"type": "F4", "number": 14, "particle": "n,p", "params": "1 2",
             "multiplier": "", "enableEn": True, "enableTn": False},
        ],
        "tally": {"fmesh": []},
        "grids": {"e": {"values": ["1", "2"], "log": False}},
        "adv": {},
        "rawOverrides": {"tally": "f4:n 1"},
        "textMode": {"tally": True},
        "sourceTemplate": "free",
    }


def _reset_ws():
    server._WORKSPACE["sections"] = None
    server._WORKSPACE["revision"] = 0
    server._WORKSPACE.pop("frontend_keys", None)


def test_deck_from_json_reads_frontend_top_level_tallies():
    """单点锁死：前端顶层 tallies 必须进 DeckData.tally.tallies。"""
    deck = deck_from_json(_frontend_deck())
    assert [(t.type, t.number) for t in deck.tally.tallies] == [("F4", 14)]
    assert deck.tally.tallies[0].particles == ["n", "p"]
    assert deck.tally.tallies[0].generate_en is True


def test_deck_from_json_tally_nested_still_wins():
    """后端口径（tally.tallies）仍然有效，不被顶层键破坏。"""
    d = _frontend_deck()
    d["tally"] = {"tallies": [{"type": "F6", "number": 6, "particles": ["n"], "params": "3"}]}
    deck = deck_from_json(d)
    assert [(t.type, t.number) for t in deck.tally.tallies] == [("F6", 6)]


def test_workspace_roundtrip_keeps_tallies():
    """端到端：前端 PUT → GET 回显，计数卡不丢（前端 loadDeck 直接吃这份 deck）。"""
    _reset_ws()
    front = _frontend_deck()
    # PUT /workspace 的真实代码路径
    server._set_ws_sections(server._deck_to_sections(deck_from_json(front)))
    got = deck_to_frontend_dict(server._ws_deck())
    assert [t["number"] for t in got["tallies"]] == [14], f"回显丢了计数卡: {got.get('tallies')}"
    assert got["tallies"][0]["params"] == "1 2"
    assert got["tallies"][0]["enableEn"] is True
    # 回显里 **不得** 再带 `tally.tallies`：前端口径里计数卡只在顶层，
    # 子对象里再带一份会让前端 deck 出现"两个权威"，后续 PUT 的新增/删除被静默丢弃
    assert "tallies" not in (got.get("tally") or {}), f"回显的 tally 子对象里不该有 tallies: {got.get('tally')}"


def _roundtrip(deck_json):
    """复刻 PUT → GET（回显）的真实链路"""
    server._set_ws_sections(server._deck_to_sections(deck_from_json(deck_json)))
    server._WORKSPACE["frontend_keys"] = server._frontend_only_keys(deck_json)
    return server._ws_frontend_deck()


def test_repeated_roundtrips_keep_user_add_and_delete():
    """**多轮往返**下用户新增/删除计数卡必须生效（单轮测不出来，2026-09-17 实证漏洞）。

    漏洞形态：回显 deck 同时含顶层 `tallies` 与 `tally.tallies` → 前端把回显并进自己 deck 后
    两处各说各话 → `deck_from_json` 见 `tally.tallies` 非空就忽略顶层
    → **用户新增的卡进不去、删掉的卡又回来**（实测：新增 F6 后仍 [14]，删 F4 后仍 [14]）。
    """
    _reset_ws()
    d1 = _frontend_deck()
    echo1 = _roundtrip(d1)
    # 前端 apply：{...local, ...echo}
    front = {**d1, **echo1}

    # 用户新增一张 F6（只改顶层 tallies）→ 再往返
    front["tallies"] = front["tallies"] + [{"type": "F6", "number": 6, "particle": "n", "params": "2"}]
    echo2 = _roundtrip(front)
    assert [t["number"] for t in echo2["tallies"]] == [14, 6], f"新增的卡被吞了: {echo2['tallies']}"

    # 用户删掉 F4 → 再往返
    front2 = {**front, **echo2}
    front2["tallies"] = [t for t in front2["tallies"] if t["number"] != 14]
    echo3 = _roundtrip(front2)
    assert [t["number"] for t in echo3["tallies"]] == [6], f"删掉的卡又回来了: {echo3['tallies']}"


def test_workspace_roundtrip_keeps_frontend_only_keys():
    """前端专用键（文本模式/网格/源模板）也必须经得住回显，否则回显会静默切回表单模式。"""
    _reset_ws()
    front = _frontend_deck()
    server._set_ws_sections(server._deck_to_sections(deck_from_json(front)))
    server._WORKSPACE["frontend_keys"] = server._frontend_only_keys(front)
    got = server._ws_frontend_deck()   # GET /workspace 用的就是这份
    assert got["textMode"] == {"tally": True}
    assert got["rawOverrides"] == {"tally": "f4:n 1"}
    assert got["grids"] == {"e": {"values": ["1", "2"], "log": False}}
    assert got["sourceTemplate"] == "free"
    # 后端建模的段仍以段为权威（AI 改动不被前端旧键盖回）
    assert [t["number"] for t in got["tallies"]] == [14]


def test_ai_patch_tally_still_works_on_workspace():
    """AI 经 patch_section 改 tally 后，工作区与回显都跟着变（修复不能破坏 AI 写路径）。"""
    _reset_ws()
    front = _frontend_deck()
    server._set_ws_sections(server._deck_to_sections(deck_from_json(front)))
    server.patch_section(section="tally", data={"tallies": [
        {"type": "F4", "number": 14, "particles": ["n"], "params": "9"}]})
    got = deck_to_frontend_dict(server._ws_deck())
    assert [t["number"] for t in got["tallies"]] == [14]
    assert got["tallies"][0]["params"] == "9"
