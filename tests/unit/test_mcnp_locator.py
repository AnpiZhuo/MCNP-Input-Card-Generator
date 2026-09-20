# -*- coding: utf-8 -*-
"""MCNP 定位/选择（`app/mcnp_locator.py`）单测。

**不依赖本机是否装 MCNP**：四个搜索来源全部 monkeypatch 掉，只验逻辑本身。
真实安装布局用 tmp_path 造（MCNP6 的 `<root>\\MCNP_CODE\\bin` 与 MCNP5 的 `<root>\\bin`
两种都造），因为"逐候选推断自带 xsdir"正是这个模块存在的理由之一。

背景（为什么值得这么多用例）：改造前 `api_server._find_mcnp_exe()` 找到第一个就 return，
装了 MCNP5 + MCNP6 的用户**永远只能看到一个**，且版本标签靠"文件名里有 5 就是 MCNP5"猜。
"""
import os

import pytest

import app.mcnp_locator as ml
import app.user_config as uc


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """把 config.json 指到临时文件（**绝不碰真实 %APPDATA%**），并在用例前后清缓存。"""
    p = tmp_path / "config.json"
    monkeypatch.setattr(ml.user_config, "path", lambda: str(p))
    ml.reset_cache()
    yield p
    ml.reset_cache()


def _fake_install(tmp_path, kind: str):
    """造一棵真实布局的假安装，返回 (exe, xsdir)。"""
    root = tmp_path / kind
    if kind == "mcnp6":
        exe = root / "MCNP_CODE" / "bin" / "mcnp6.exe"
        xsdir = root / "MCNP_DATA" / "xsdir"
    else:  # mcnp5：可执行在 <root>/bin，数据在 <root>/DATA
        exe = root / "bin" / "mcnp5.exe"
        xsdir = root / "DATA" / "xsdir"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text("", encoding="utf-8")
    xsdir.parent.mkdir(parents=True, exist_ok=True)
    xsdir.write_text("", encoding="utf-8")
    return exe, xsdir


def _only_sources(monkeypatch, *paths):
    """只让 PATH 这一条来源返回给定路径，其余来源置空（隔离真实机器环境）。"""
    monkeypatch.setattr(ml, "_from_path_env", lambda: [str(p) for p in paths])
    monkeypatch.setattr(ml, "_from_registry", lambda: [])
    monkeypatch.setattr(ml, "_from_common_roots", lambda: [])


# ── 版本标签 ────────────────────────────────────────────────
def test_label_for_reads_basename_only():
    assert ml.label_for(r"D:\MCNP\MCNP6\MCNP_CODE\bin\mcnp6.exe") == "MCNP6"
    assert ml.label_for(r"D:\MCNP5\bin\mcnp5.exe") == "MCNP5"
    assert ml.label_for(r"C:\x\MCNP6.2.exe") == "MCNP6"
    assert ml.label_for("") == "MCNP?"
    assert ml.label_for(r"C:\x\runmcnp.exe") == "MCNP?"


def test_label_for_ignores_version_digits_in_directory_names():
    """目录名里有 5 不算数 —— 只看文件名（否则 `D:\\MCNP5\\...\\mcnp6.exe` 会被判成 MCNP5）。"""
    assert ml.label_for(r"D:\MCNP5\bin\mcnp6.exe") == "MCNP6"


# ── 逐候选自带 xsdir ────────────────────────────────────────
def test_xsdir_for_mcnp6_layout(tmp_path):
    """MCNP6：<root>\\MCNP_CODE\\bin\\mcnp6.exe → <root>\\MCNP_DATA\\xsdir（上溯 2 层）。"""
    exe, xsdir = _fake_install(tmp_path, "mcnp6")
    assert ml.xsdir_for(str(exe)) == str(xsdir)


def test_xsdir_for_mcnp5_DATA_layout(tmp_path):
    """MCNP5：<root>\\bin\\mcnp5.exe → <root>\\DATA\\xsdir（大写 DATA）。"""
    exe, xsdir = _fake_install(tmp_path, "mcnp5")
    assert ml.xsdir_for(str(exe)) == str(xsdir)


def test_xsdir_for_sibling_file(tmp_path):
    """个别安装把 xsdir 直接放 exe 同级。"""
    d = tmp_path / "flat"
    d.mkdir()
    exe = d / "mcnp6.exe"
    exe.write_text("", encoding="utf-8")
    (d / "xsdir").write_text("", encoding="utf-8")
    assert ml.xsdir_for(str(exe)) == str(d / "xsdir")


def test_xsdir_for_returns_none_instead_of_guessing(tmp_path):
    """推断不到就回 None（**不猜**）：猜错会让 ZAID 校验按错误的库作答，比"没找到"更难查。"""
    d = tmp_path / "bare"
    d.mkdir()
    exe = d / "mcnp6.exe"
    exe.write_text("", encoding="utf-8")
    assert ml.xsdir_for(str(exe)) is None
    assert ml.xsdir_for("") is None


# ── 候选枚举 ────────────────────────────────────────────────
def test_detect_all_collects_both_versions(cfg, tmp_path, monkeypatch):
    """**核心用例**：MCNP5 与 MCNP6 都装了 ⇒ 两个都要在（原实现只回第一个）。"""
    p5, xs5 = _fake_install(tmp_path, "mcnp5")
    p6, xs6 = _fake_install(tmp_path, "mcnp6")
    _only_sources(monkeypatch, p5, p6)

    got = ml.detect_all()
    assert [c["label"] for c in got] == ["MCNP6", "MCNP5"], got
    assert {c["exe"] for c in got} == {str(p6), str(p5)}
    # 每个候选各自带出自己的 xsdir（MCNP5/MCNP6 的库互不通用）
    assert {c["exe"]: c["xsdir"] for c in got} == {str(p6): str(xs6), str(p5): str(xs5)}


def test_detect_all_dedupes_across_sources(cfg, tmp_path, monkeypatch):
    """同一份 exe 被多条来源命中 ⇒ 只留一条，且保留**先到（更可信）**的来源。"""
    p6, _ = _fake_install(tmp_path, "mcnp6")
    monkeypatch.setattr(ml, "_from_path_env", lambda: [str(p6)])
    monkeypatch.setattr(ml, "_from_registry", lambda: [])
    monkeypatch.setattr(ml, "_from_common_roots", lambda: [str(p6)])

    got = ml.detect_all()
    assert len(got) == 1 and got[0]["source"] == "PATH", got


def test_detect_all_dedupes_case_insensitively(cfg, tmp_path, monkeypatch):
    p6, _ = _fake_install(tmp_path, "mcnp6")
    monkeypatch.setattr(ml, "_from_path_env", lambda: [str(p6)])
    monkeypatch.setattr(ml, "_from_registry", lambda: [str(p6).upper()])
    monkeypatch.setattr(ml, "_from_common_roots", lambda: [])
    assert len(ml.detect_all()) == 1


def test_detect_all_skips_nonexistent_and_files_only(cfg, tmp_path, monkeypatch):
    """来源返回不存在的路径/目录 ⇒ 一律不入选（搜索来源不可信，落盘才算数）。"""
    d = tmp_path / "adir"
    d.mkdir()
    _only_sources(monkeypatch, tmp_path / "ghost" / "mcnp6.exe", d)
    assert ml.detect_all() == []


def test_detect_all_is_cached_until_force(cfg, monkeypatch):
    """缓存：一次请求内不重复 `os.walk(D:\\MCNP)`（实测冷扫 2.5 s）；force 才重扫。"""
    calls = []

    def _spy():
        calls.append(1)
        return []

    monkeypatch.setattr(ml, "_from_path_env", _spy)
    monkeypatch.setattr(ml, "_from_registry", lambda: [])
    monkeypatch.setattr(ml, "_from_common_roots", lambda: [])

    ml.detect_all()
    ml.detect_all()
    assert len(calls) == 1
    ml.detect_all(force=True)
    assert len(calls) == 2


def test_detect_all_returns_copies(cfg, tmp_path, monkeypatch):
    """调用方改返回值不该污染缓存（避免"界面改了一下，后面全是错的"）。"""
    p6, _ = _fake_install(tmp_path, "mcnp6")
    _only_sources(monkeypatch, p6)
    got = ml.detect_all()
    got[0]["label"] = "改坏了"
    assert ml.detect_all()[0]["label"] == "MCNP6"


# ── 选择与持久化 ────────────────────────────────────────────
def test_selected_prefers_saved_then_first_detected(cfg, tmp_path, monkeypatch):
    p5, _ = _fake_install(tmp_path, "mcnp5")
    p6, _ = _fake_install(tmp_path, "mcnp6")
    _only_sources(monkeypatch, p5, p6)

    assert ml.selected() == str(p6)          # 没选过 → 自动检测第一个（MCNP6 在前）
    ml.save(str(p5))
    assert ml.saved() == str(p5)
    assert ml.selected() == str(p5)          # 选过 → 用用户选的

    p5.unlink()                              # 用户卸载了 MCNP5
    assert ml.saved() is None                # 指向不存在的文件 ⇒ 视为没选
    assert ml.selected() == str(p6)          # 回落到自动检测，不报错


def test_save_empty_string_clears_choice(cfg, tmp_path, monkeypatch):
    p6, _ = _fake_install(tmp_path, "mcnp6")
    _only_sources(monkeypatch, p6)
    ml.save(str(p6))
    assert ml.selected() == str(p6)
    ml.save("")
    assert ml.saved() is None
    # "清除选择"与"从没选过"必须给同一个答案（不留 "mcnp_exe": "" 这种假选择）
    assert "mcnp_exe" not in uc.load()


def test_save_accepts_raw_path_with_quotes(cfg, tmp_path, monkeypatch):
    """用户从资源管理器复制路径常带引号 —— 存进去要能读回来。"""
    p6, _ = _fake_install(tmp_path, "mcnp6")
    _only_sources(monkeypatch, p6)
    ml.save(f'"{p6}"')
    assert ml.saved() == str(p6)


def test_resolve_prefers_hint_only_if_it_exists(cfg, tmp_path, monkeypatch):
    p6, _ = _fake_install(tmp_path, "mcnp6")
    _only_sources(monkeypatch, p6)

    assert ml.resolve(str(p6)) == str(p6)
    # 陈旧 hint（localStorage 里存着一个已卸载的版本）不采信，落到检测结果
    ghost = tmp_path / "gone" / "mcnp6.exe"
    assert ml.resolve(str(ghost)) == str(p6)
    assert ml.resolve("") == str(p6)


def test_resolve_empty_when_nothing_found(cfg, monkeypatch):
    monkeypatch.setattr(ml, "_from_path_env", lambda: [])
    monkeypatch.setattr(ml, "_from_registry", lambda: [])
    monkeypatch.setattr(ml, "_from_common_roots", lambda: [])
    assert ml.selected() is None
    assert ml.resolve("") == ""
    assert ml.resolve(str(ml.os.path.join("Z:", "nope", "mcnp6.exe"))) == ""


def test_saved_user_choice_appears_as_first_candidate(cfg, tmp_path, monkeypatch):
    """手动指定后它必须作为候选出现（来源标"用户选择"），否则下拉里看不到自己选的那个。"""
    manual = tmp_path / "custom" / "myMcnp.exe"
    manual.parent.mkdir(parents=True)
    manual.write_text("", encoding="utf-8")
    ml.save(str(manual))
    monkeypatch.setattr(ml, "_from_path_env", lambda: [])
    monkeypatch.setattr(ml, "_from_registry", lambda: [])
    monkeypatch.setattr(ml, "_from_common_roots", lambda: [])

    got = ml.detect_all()
    assert got and got[0]["exe"] == os.path.abspath(str(manual))
    assert got[0]["source"] == "用户选择"
    assert got[0]["label"] == "MCNP?"      # 非标准文件名 → 判不出版本，但照样记住
