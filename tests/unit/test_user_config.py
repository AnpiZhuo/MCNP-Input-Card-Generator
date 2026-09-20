# -*- coding: utf-8 -*-
"""用户级 config.json 的唯一读写口（`app/user_config.py`）单测。

**这个文件存在的理由本身就是一条缺陷**：原来 `freecad_locator.save()` 是
`json.dump({"freecad_path": path})` —— **整份覆盖**。于是只要再加第二个设置
（本批就是 `mcnp_exe`），后存的就会把先存的抹掉。这里把"共享文件、只改自己的键"
钉成回归用例：先选 FreeCAD 再选 MCNP（以及反过来）都必须两键俱在。
"""
import json

import pytest

import app.user_config as uc


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    p = tmp_path / "config.json"
    monkeypatch.setattr(uc, "path", lambda: str(p))
    return p


def test_set_values_only_touches_given_keys(cfg):
    uc.set_values(freecad_path=r"D:\FreeCAD\FreeCAD.exe")
    uc.set_values(mcnp_exe=r"D:\MCNP\MCNP6\MCNP_CODE\bin\mcnp6.exe")
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data == {
        "freecad_path": r"D:\FreeCAD\FreeCAD.exe",
        "mcnp_exe": r"D:\MCNP\MCNP6\MCNP_CODE\bin\mcnp6.exe",
    }


def test_empty_or_none_deletes_the_key(cfg):
    uc.set_values(a="1", b="2")
    uc.set_values(a="", b=None)
    assert uc.load() == {}


def test_missing_or_corrupt_file_reads_as_empty(cfg):
    assert uc.load() == {}                       # 文件不存在
    cfg.write_text("{ this is not json", encoding="utf-8")
    assert uc.load() == {}                       # 损坏
    cfg.write_text("[1,2,3]", encoding="utf-8")
    assert uc.load() == {}                       # 不是对象
    # 坏配置不该让"写"也失败
    uc.set_values(mcnp_exe="x")
    assert uc.load() == {"mcnp_exe": "x"}


def test_value_helper_strips_quotes_and_blank(cfg):
    uc.set_values(mcnp_exe='  "D:\\a b\\mcnp6.exe"  ')
    assert uc._value("mcnp_exe") == r"D:\a b\mcnp6.exe"
    uc.set_values(mcnp_exe="   ")
    assert uc._value("mcnp_exe") is None


def test_freecad_and_mcnp_choices_coexist(cfg, tmp_path, monkeypatch):
    """**回归**：两个定位模块先后保存，谁都不能把对方从 config.json 里抹掉。"""
    import app.freecad_locator as fl
    import app.mcnp_locator as ml

    # 三个模块必须看到同一份配置（共用同一个 path 覆盖）
    monkeypatch.setattr(fl.user_config, "path", uc.path)
    monkeypatch.setattr(ml.user_config, "path", uc.path)

    fc = tmp_path / "FreeCAD.exe"
    fc.write_text("", encoding="utf-8")
    mc = tmp_path / "mcnp6.exe"
    mc.write_text("", encoding="utf-8")

    fl.save(str(fc))
    ml.save(str(mc))
    assert uc.get("freecad_path") == str(fc)
    assert uc.get("mcnp_exe") == str(mc)

    # 反过来再存一次 FreeCAD：MCNP 的选择必须还在（原实现这一步会抹掉它）
    fl.save(str(fc))
    assert uc.get("mcnp_exe") == str(mc)
    # 且两边读回来的都还是自己那个
    assert fl.saved() == str(fc)
    assert ml.saved() == str(mc)
