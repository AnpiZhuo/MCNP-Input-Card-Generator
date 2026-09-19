# -*- coding: utf-8 -*-
"""`app/file_dialog.py` 单测：原生文件选择窗口的规格（纯 stdlib，无 tkinter）。

`/api/choose-file` 本身是模态弹窗、无法在测试里跑；能被测的就是"弹什么"——
标题、文件类型过滤、**默认选哪一类**（Tk 取 filetypes[0]）、要不要读回内容。
"""

from app.file_dialog import DEFAULT_KIND, dialog_spec


def test_default_kind_is_inp_for_legacy_callers():
    """老调用方一个字段都不传（或空 body）→ 与改动前完全一致：INP 过滤。"""
    for data in (None, {}, {"kind": ""}, {"kind": None}):
        spec = dialog_spec(data)
        assert spec["kind"] == "inp" == DEFAULT_KIND
        assert spec["title"] == "选择 MCNP INP 文件"
        assert spec["filetypes"][0] == ["MCNP 输入卡", "*.inp *.i *.txt"]
        assert spec["with_content"] is True


def test_mctal_defaults_to_no_extension_filter():
    """mctal：**默认无后缀** —— 首项过滤不含任何扩展名，否则用户看不见 mctal 本体。

    MCNP 的 mctal 文件没有扩展名（运行目录下就叫 ``mctal``），若默认给
    ``*.txt``/``*.o`` 之类过滤，打开窗口时它根本不出现。
    """
    spec = dialog_spec({"kind": "mctal"})
    assert spec["kind"] == "mctal"
    label, pattern = spec["filetypes"][0]
    assert pattern == "*", f"默认类型必须无扩展名约束，实际 {pattern!r}"
    assert "*." not in pattern
    assert "mctal" in label
    assert spec["title"].startswith("选择 mctal")


def test_outp_defaults_to_o_extension():
    """outp：默认 ``*.o *.outp *.out``（`.o` 在最前）。"""
    spec = dialog_spec({"kind": "outp"})
    assert spec["kind"] == "outp"
    label, pattern = spec["filetypes"][0]
    assert pattern.split()[0] == "*.o"
    assert "输出" in label


def test_kind_is_case_insensitive_and_unknown_falls_back():
    """kind 大小写不敏感；未知 kind 回落 inp（不抛、不做半吊子过滤）。"""
    assert dialog_spec({"kind": "MCTAL"})["kind"] == "mctal"
    assert dialog_spec({"kind": " outp "})["kind"] == "outp"
    assert dialog_spec({"kind": "木星"})["kind"] == "inp"
    assert dialog_spec({"kind": 42})["kind"] == "inp"


def test_with_content_flag_only_accepts_bool():
    """``withContent``：true/false 生效；非布尔（含字符串 "false"）一律按默认 true，
    避免 ``bool("false") is True`` 这类"看着关了其实没关"的陷阱。"""
    assert dialog_spec({"withContent": False})["with_content"] is False
    assert dialog_spec({"withContent": True})["with_content"] is True
    assert dialog_spec({"withContent": "false"})["with_content"] is True
    assert dialog_spec({"withContent": 0})["with_content"] is True
    assert dialog_spec({"withContent": None})["with_content"] is True


def test_spec_is_a_copy_not_the_constant():
    """返回的 filetypes 必须是拷贝：调用方（或下游）改它不能污染模块常量。"""
    spec = dialog_spec({"kind": "outp"})
    spec["filetypes"][0][1] = "*.被改了"
    assert dialog_spec({"kind": "outp"})["filetypes"][0][1] == "*.o *.outp *.out"


def test_every_kind_has_a_fallback_entry():
    """每种 kind 都要有兜底"所有文件"，免得过滤写错时用户彻底选不到文件。"""
    for kind in ("inp", "mctal", "outp"):
        fts = dialog_spec({"kind": kind})["filetypes"]
        assert len(fts) >= 2
        assert any(p == "*.*" for _, p in fts), f"{kind} 缺「所有文件」兜底项"
        assert all(len(ft) == 2 for ft in fts)   # Tk 只接受 (label, pattern) 二元组
