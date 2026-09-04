# -*- coding: utf-8 -*-
"""回归：inputcard-mcp 的「当前工作区」会话——工具不传 inp 时读写它（程序所有标签页的 deck）。

配合 /workspace(前端同步) 与 /mcp(MCP over HTTP)：前端把整个工作区推到 _WORKSPACE，
AI 经工具读/改的就是这份「当前工作区」，改后 revision 递增、前端可见。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
for _p in (ROOT, os.path.join(ROOT, "app"), os.path.join(ROOT, "gui", "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from inputcard_mcp import server  # noqa: E402


def _reset_ws():
    server._WORKSPACE["sections"] = None
    server._WORKSPACE["revision"] = 0


def test_list_section_reads_upstream_workspace():
    _reset_ws()
    sections = {
        "basic": {"title": "ws", "mode_n": True, "nps": "1000"},
        "surfaces": "1 pz 0\n", "tr_cards": "", "universe_comments": {},
        "cells": [{"kind": "cell", "cell": {"number": 1, "material": "1", "density": "-1.0", "surface_expr": "-1"}}],
        "materials": [], "sources": [], "tally": {}, "advanced": {},
    }
    server._set_ws_sections(sections)
    # 不传 inp → 读当前工作区
    assert server.list_section(section="cells")[0]["cell"]["number"] == 1
    assert server.list_section(section="basic")["title"] == "ws"


def test_patch_section_updates_workspace_and_revision():
    _reset_ws()
    sections = {"basic": {"title": "ws", "mode_n": True, "nps": "1000"}, "cells": [], "materials": [],
                "sources": [], "tally": {}, "advanced": {}, "surfaces": "", "tr_cards": "", "universe_comments": {}}
    server._set_ws_sections(sections)
    rev0 = server._WORKSPACE["revision"]
    out = server.patch_section(section="basic", data={"title": "AI-edited", "mode_n": True, "nps": "2000"})
    assert "AI-edited" in out
    assert server._WORKSPACE["revision"] == rev0 + 1
    assert server._ws_sections()["basic"]["title"] == "AI-edited"
    assert server._ws_sections()["basic"]["nps"] == "2000"


def test_inp_still_works_as_before():
    # 传 inp → 仍走无状态文档路径，不动 workspace
    _reset_ws()
    inp = "t\n1 1 -1.0 -1\n\n1 pz 0\n"
    r = server.list_section(inp=inp, section="cells")
    assert r and r[0]["cell"]["material"] == "1"
    # workspace 未被触碰（仍是空默认）
    assert server._ws_sections()["cells"] == []
