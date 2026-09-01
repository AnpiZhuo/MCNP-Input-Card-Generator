"""
材料库深化 —— app/material_library.py 单元测试（TDD：先红后绿）。

覆盖：
- 库路径回落（MCNP_MATERIAL_DIR 优先 → D:\MCNP\material → %APPDATA%\MCNP\material）
- CRUD 往返（save / list / get / delete，custom 与 override 并存）
- JSON 无损 import/export（含 options/mtCard/raw 行）
- CSV 长格式多材料（按 key 分组、key 缺失回退 name、行交错、scalar 取首个非空）
- import 冲突三选（skip / overwrite / rename），需 existing_keys
- validate_entry（ZAID 格式、份额非空/格式、正负号、S(α,β) 需含氢、密度格式）
- check_zaids_xsdir（缺库 missing / 后缀不匹配 suffix）
"""
import os
import pytest
import app.material_library as ml


@pytest.fixture(autouse=True)
def _isolate_path(tmp_path, monkeypatch):
    """把库路径钉在临时目录，避免污染真实 D 盘 / %APPDATA%。"""
    monkeypatch.setattr(ml, "_custom_dir", None)
    monkeypatch.setenv("MCNP_MATERIAL_DIR", str(tmp_path))
    return tmp_path


# ── 基础 CRUD ──
def test_library_path_uses_env(tmp_path):
    assert ml.library_path() == os.path.join(str(tmp_path), "material_library.json")


def test_save_list_get_delete_roundtrip():
    e = {
        "key": "my_poly", "name": "我的聚乙烯", "category": "自定义",
        "formula": "C2H4: 1", "desc": "用户新建", "density": "-0.93",
        "options": "nlib=.66c", "mtCard": "poly.10t",
        "rows": [{"kind": "nuclide", "zaid": "1001", "fraction": "-0.142857"}],
        "origin": "custom",
    }
    ml.save_material(e)
    lib = ml.list_materials()
    assert lib["my_poly"]["mtCard"] == "poly.10t"
    assert lib["my_poly"]["options"] == "nlib=.66c"
    got = ml.get_material("my_poly")
    assert got["rows"][0]["zaid"] == "1001"
    # override 与 custom 并存
    ov = dict(e, key="uo2", origin="override", name="改过的二氧化铀")
    ml.save_material(ov)
    lib = ml.list_materials()
    assert lib["uo2"]["origin"] == "override"
    # 删除
    assert ml.delete_material("my_poly") is True
    assert ml.delete_material("my_poly") is False
    assert "my_poly" not in ml.list_materials()


def test_save_creates_file_atomically():
    e = {"key": "k1", "name": "n", "category": "", "formula": "", "desc": "",
         "density": "", "options": "", "mtCard": "", "rows": [], "origin": "custom"}
    ml.save_material(e)
    path = ml.library_path()
    assert os.path.isfile(path)
    assert not os.path.exists(path + ".tmp")  # 防半写：临时文件已 rename


# ── JSON import/export（无损往返） ──
def test_export_import_json_lossless():
    entries = [
        {"key": "a", "name": "A", "category": "c1", "formula": "H2O:1", "desc": "",
         "density": "-1", "options": "nlib=.66c", "mtCard": "lwtr.10t",
         "rows": [{"kind": "nuclide", "zaid": "1001", "fraction": "-0.11"}], "origin": "custom"},
    ]
    text = ml.export_json(entries)
    parsed = ml.parse_import(text, "json")
    assert parsed == entries


# ── CSV 长格式 ──
def test_parse_csv_multiple_materials_by_key():
    text = (
        "key,name,category,formula,desc,density,options,mtCard,zaid,fraction\n"
        "uo2,二氧化铀,燃料,UO2,, -10.96,,,8016,-0.118212\n"
        "uo2,二氧化铀,燃料,UO2,, -10.96,,,92235,-0.026444\n"
        "water,水,常见化合物,H2O: 1,, -1.00,,lwtr.10t,1001,-0.111898\n"
        "water,水,常见化合物,H2O: 1,, -1.00,,lwtr.10t,8016,-0.888102\n"
    )
    entries = ml.parse_import(text, "csv")
    keys = [e["key"] for e in entries]
    assert keys == ["uo2", "water"]
    by_key = {e["key"]: e for e in entries}
    assert len(by_key["uo2"]["rows"]) == 2
    assert by_key["water"]["mtCard"] == "lwtr.10t"


def test_parse_csv_keeps_first_nonempty_scalar():
    # 只在第一行填 options/mtCard，后续核素行为空 → 取首个非空
    text = (
        "key,name,category,formula,desc,density,options,mtCard,zaid,fraction\n"
        "m1,M1,,formula,, -1.0,nlib=.66c,lwtr.10t,1001,-0.5\n"
        "m1,M1,,formula,, -1.0,,,1002,-0.5\n"
    )
    entries = ml.parse_import(text, "csv")
    e = entries[0]
    assert e["options"] == "nlib=.66c"
    assert e["mtCard"] == "lwtr.10t"
    assert len(e["rows"]) == 2


def test_parse_csv_key_missing_falls_back_to_name():
    text = (
        "key,name,category,formula,desc,density,options,mtCard,zaid,fraction\n"
        ",水,H2O: 1,, -1.0,,,1001,-0.11\n"
    )
    entries = ml.parse_import(text, "csv")
    e = entries[0]
    assert e["key"]  # 自动生成
    assert e["name"] == "水"


def test_parse_csv_interleaved_rows_grouped_by_key():
    # 两个材料行交错，仍按 key 正确分组
    text = (
        "key,name,category,formula,desc,density,options,mtCard,zaid,fraction\n"
        "a,A,,,, -1.0,,,1001,-0.5\n"
        "b,B,,,, -2.0,,,6012,-0.5\n"
        "a,A,,,, -1.0,,,8016,-0.5\n"
        "b,B,,,, -2.0,,,8016,-0.5\n"
    )
    entries = ml.parse_import(text, "csv")
    by_key = {e["key"]: e for e in entries}
    assert len(by_key["a"]["rows"]) == 2
    assert len(by_key["b"]["rows"]) == 2


def test_export_csv_flat_line_per_nuclide():
    entries = [{
        "key": "uo2", "name": "UO2", "category": "fuel", "formula": "UO2",
        "desc": "", "density": "-10.96", "options": "", "mtCard": "",
        "rows": [{"kind": "nuclide", "zaid": "8016", "fraction": "-0.118"},
                 {"kind": "nuclide", "zaid": "92235", "fraction": "-0.026"}],
        "origin": "custom",
    }]
    text = ml.export_csv(entries)
    lines = text.strip().split("\n")
    assert lines[0].startswith("key,name,category")
    assert len(lines) == 3  # 表头 + 2 核素行
    assert "uo2" in lines[1] and "uo2" in lines[2]


# ── import 冲突三选 ──
_EXISTING = ["water", "uo2"]  # 模拟库中已有 key


def test_import_conflict_skip():
    entries = [
        {"key": "water", "name": "水2", "category": "", "formula": "", "desc": "",
         "density": "", "options": "", "mtCard": "", "rows": [], "origin": "custom"},
        {"key": "new1", "name": "新", "category": "", "formula": "", "desc": "",
         "density": "", "options": "", "mtCard": "", "rows": [], "origin": "custom"},
    ]
    res = ml.apply_import(entries, conflict="skip", existing_keys=_EXISTING)
    assert res["skipped"] == ["water"]
    assert res["imported"] == ["new1"]
    assert res["overwritten"] == []


def test_import_conflict_overwrite():
    entries = [{"key": "water", "name": "水2", "category": "", "formula": "",
                "desc": "", "density": "", "options": "", "mtCard": "",
                "rows": [], "origin": "custom"}]
    res = ml.apply_import(entries, conflict="overwrite", existing_keys=_EXISTING)
    assert res["overwritten"] == ["water"]
    assert res["imported"] == []


def test_import_conflict_rename():
    entries = [{"key": "water", "name": "水2", "category": "", "formula": "",
                "desc": "", "density": "", "options": "", "mtCard": "",
                "rows": [], "origin": "custom"}]
    res = ml.apply_import(entries, conflict="rename", existing_keys=_EXISTING)
    assert res["renamed"] == ["water"]  # 改名后 key 不再冲突
    assert not res["imported"]  # 原 key 冲突，改名后以新 key 入库（归入 imported 或 renamed 一列）


def test_import_identical_content_auto_skip():
    # 材料与已有条目「内容完全一致」→ 自动跳过（identical），不走冲突三选
    existing = [
        {"key": "water", "name": "水", "category": "", "formula": "H2O:1", "desc": "",
         "density": "-1.0", "options": "nlib=.66c", "mtCard": "lwtr.10t", "origin": "custom",
         "rows": [{"kind": "nuclide", "zaid": "1001", "fraction": "-0.11"}]},
    ]
    incoming = [
        # 内容与 existing[0] 完全一致（仅 key 不同）→ identical
        {"key": "water2", "name": "水", "category": "", "formula": "H2O:1", "desc": "",
         "density": "-1.0", "options": "nlib=.66c", "mtCard": "lwtr.10t", "origin": "custom",
         "rows": [{"kind": "nuclide", "zaid": "1001", "fraction": "-0.11"}]},
        # 内容不同（密度不同）→ 新导入
        {"key": "newm", "name": "新材料", "category": "", "formula": "", "desc": "",
         "density": "-2.0", "options": "", "mtCard": "", "origin": "custom",
         "rows": [{"kind": "nuclide", "zaid": "8016", "fraction": "-1"}]},
    ]
    res = ml.apply_import(incoming, conflict="skip", existing_keys=["water"],
                          existing_entries=existing)
    assert res["identical"] == ["water2"]
    assert res["imported"] == ["newm"]
    assert res["skipped"] == []


def test_import_identical_without_existing_entries_still_conflict():
    # 未传 existing_entries → 退化为只看 existing_keys（无内容去重，同名仍走冲突）
    entries = [{"key": "water", "name": "水", "category": "", "formula": "",
                "desc": "", "density": "", "options": "", "mtCard": "", "rows": []}]
    res = ml.apply_import(entries, conflict="skip", existing_keys=["water"])
    assert res["skipped"] == ["water"]
    assert res["identical"] == []


# ── validate_entry ──
def test_validate_entry_ok():
    e = {"key": "k", "name": "n", "category": "", "formula": "", "desc": "",
         "density": "-1.0", "options": "", "mtCard": "",
         "rows": [{"kind": "nuclide", "zaid": "92235.80c", "fraction": "-0.05"}],
         "origin": "custom"}
    assert ml.validate_entry(e) == []


def test_validate_entry_zaid_format():
    e = {"key": "k", "name": "n", "category": "", "formula": "X", "desc": "",
         "density": "", "options": "", "mtCard": "",
         "rows": [{"kind": "nuclide", "zaid": "ABC", "fraction": "-0.05"}],
         "origin": "custom"}
    errs = ml.validate_entry(e)
    assert any("格式" in x for x in errs)


def test_validate_entry_sign_mixed():
    e = {"key": "k", "name": "n", "category": "", "formula": "", "desc": "",
         "density": "", "options": "", "mtCard": "",
         "rows": [{"kind": "nuclide", "zaid": "1001", "fraction": "-0.05"},
                  {"kind": "nuclide", "zaid": "8016", "fraction": "0.95"}],
         "origin": "custom"}
    errs = ml.validate_entry(e)
    assert any("正负号" in x for x in errs)


def test_validate_entry_sab_requires_hydrogen():
    e = {"key": "k", "name": "n", "category": "", "formula": "", "desc": "",
         "density": "", "options": "", "mtCard": "lwtr.10t",
         "rows": [{"kind": "nuclide", "zaid": "8016", "fraction": "-1.0"}],
         "origin": "custom"}
    errs = ml.validate_entry(e)
    assert any("S(α,β)" in x for x in errs)


def test_validate_entry_density_format():
    e = {"key": "k", "name": "n", "category": "", "formula": "", "desc": "",
         "density": "abc", "options": "", "mtCard": "",
         "rows": [{"kind": "nuclide", "zaid": "1001", "fraction": "-1.0"}],
         "origin": "custom"}
    errs = ml.validate_entry(e)
    assert any("密度" in x for x in errs)


def test_validate_entry_no_rows_no_formula_error():
    e = {"key": "k", "name": "n", "category": "", "formula": "", "desc": "",
         "density": "", "options": "", "mtCard": "", "rows": [], "origin": "custom"}
    errs = ml.validate_entry(e)
    assert any("组成" in x for x in errs)


# ── check_zaids_xsdir ──
class _FakeDB:
    loaded = True
    zaids = {"1001.80c": [], "92235.80c": [], "92238.00c": []}


def test_check_zaids_xsdir_missing(monkeypatch):
    monkeypatch.setattr(ml, "xsdir_db", _FakeDB())
    e = {"key": "k", "name": "n", "category": "", "formula": "", "desc": "",
         "density": "", "options": "", "mtCard": "", "rows": [
             {"kind": "nuclide", "zaid": "8016", "fraction": "-1.0"}],
         "origin": "custom"}
    issues = ml.check_zaids_xsdir(e)
    assert any(i["type"] == "missing" for i in issues)


def test_check_zaids_xsdir_suffix_mismatch(monkeypatch):
    monkeypatch.setattr(ml, "xsdir_db", _FakeDB())
    e = {"key": "k", "name": "n", "category": "", "formula": "", "desc": "",
         "density": "", "options": "", "mtCard": "", "rows": [
             {"kind": "nuclide", "zaid": "92235.70c", "fraction": "-1.0"}],
         "origin": "custom"}
    issues = ml.check_zaids_xsdir(e)
    assert any(i["type"] == "suffix" and "available" in i for i in issues)


def test_check_zaids_xsdir_ok(monkeypatch):
    monkeypatch.setattr(ml, "xsdir_db", _FakeDB())
    e = {"key": "k", "name": "n", "category": "", "formula": "", "desc": "",
         "density": "", "options": "", "mtCard": "", "rows": [
             {"kind": "nuclide", "zaid": "1001.80c", "fraction": "-1.0"}],
         "origin": "custom"}
    assert ml.check_zaids_xsdir(e) == []
