"""校验器材料级规则测试（交叉核对 OWEN rules.ts validateMCNP 后新增）。"""

from app.generator.validator import validate_all, _check_surfaces_text, _collect_surface_numbers
from app.models import AdvancedSettings, BasicSettings, MaterialData, MaterialRow, CellData


def _nuclide(zaid: str, fraction: str) -> MaterialRow:
    return MaterialRow(kind="nuclide", zaid=zaid, fraction=fraction)


def _mat(number: int, rows, mt_card: str = "") -> MaterialData:
    return MaterialData(number=number, rows=rows, mt_card=mt_card)


def _mat_errors(materials) -> list[str]:
    errs = validate_all(
        BasicSettings(title="t", mode_n=True, nps="1000"),
        "1 pz 0",
        [],
        materials,
        [],
        None,
        AdvancedSettings(),
    )
    return [e for e in errs if "材料 M" in e]


def test_valid_zaid_and_fraction_no_material_error():
    m = _mat(1, [_nuclide("1001", "-0.111897"), _nuclide("8016", "-0.888103")])
    assert _mat_errors([m]) == []


def test_invalid_zaid_format():
    # 缺库字母（92235.8 而不是 92235.80c）与非法字符都应报格式错误
    m1 = _mat(1, [_nuclide("92235.8", "-0.05")])
    m2 = _mat(2, [_nuclide("abcd", "-0.05")])
    e1 = _mat_errors([m1])
    e2 = _mat_errors([m2])
    assert any("格式不正确" in e for e in e1), e1
    assert any("格式不正确" in e for e in e2), e2


def test_mixed_fraction_signs_error():
    m = _mat(1, [_nuclide("1001", "-0.1"), _nuclide("8016", "0.9")])
    e = _mat_errors([m])
    assert any("正负号混用" in x for x in e), e


def test_non_numeric_fraction_error():
    m = _mat(1, [_nuclide("1001", "abc")])
    e = _mat_errors([m])
    assert any("格式不正确" in x for x in e), e


def test_sab_target_present_ok():
    # lwtr 需要氢（Z=1）：材料含 H-1 → 通过
    m = _mat(1, [_nuclide("1001", "-0.11"), _nuclide("8016", "-0.89")],
             mt_card="lwtr.10t")
    assert _mat_errors([m]) == []


def test_sab_target_missing_error():
    # grph 需要碳（Z=6）：材料只有 U-238 → 报错（MCNP 会忽略该表）
    m = _mat(1, [_nuclide("92238", "-1.0")], mt_card="grph.10t")
    e = _mat_errors([m])
    assert any("S(α,β)" in x for x in e), e


def test_unknown_sab_table_ignored():
    m = _mat(1, [_nuclide("92238", "-1.0")], mt_card="xyz.10t")
    assert _mat_errors([m]) == []


# ── 曲面文本规则：宏体参数个数 / 行长度（OWEN mcnp.macrobody / mcnp.line-length）──

def test_macrobody_correct_param_count_ok():
    # RPP 6 参数 → 无错误
    errs = _check_surfaces_text("1  RPP  -5 5 -5 5 -5 5")
    assert not [e for e in errs if "参数个数" in e], errs


def test_macrobody_wrong_param_count_error():
    # RPP 缺 2 个参数 → 报参数个数错误
    errs = _check_surfaces_text("1  RPP  -5 5 -5 5")
    assert any("RPP" in e and "参数个数" in e for e in errs), errs


def test_macrobody_rhp_legal_param_variants_ok():
    # RHP 支持 9/12/15/18 → 9 参与 12 参都不报个数错
    errs9 = _check_surfaces_text("2  RHP  0 0 0 0 0 10 5 0 0")
    errs12 = _check_surfaces_text("2  RHP  0 0 0 0 0 10 5 0 0 2.5 4.33 0")
    assert not [e for e in errs9 if "参数个数" in e], errs9
    assert not [e for e in errs12 if "参数个数" in e], errs12


def test_macrobody_rhp_illegal_param_count_error():
    errs = _check_surfaces_text("2  RHP  0 0 0 0 0 10 5")
    assert any("RHP" in e and "参数个数" in e for e in errs), errs


def test_macrobody_with_trailing_trn_ok_and_truncated_error():
    # 行尾 *TRn 属曲面变换引用，不计入参数个数 → 参数足够时不报错
    ok_errs = _check_surfaces_text("3  SPH  0 0 0 2  *TR1")
    assert not [e for e in ok_errs if "参数个数" in e], ok_errs
    # 但参数不足（只有 3 个数值）仍应报错
    bad_errs = _check_surfaces_text("3  SPH  0 0 0  *TR1")
    assert any("SPH" in e and "参数个数" in e for e in bad_errs), bad_errs


def test_surface_line_over_128_cols_error():
    # 数据部分超过 128 列 → 报 >128 截断错误。用很多参数填到>128字。
    line = "1  RPP  " + " ".join(str(i) for i in range(80))  # 参数填到爆 128 列
    errs = _check_surfaces_text(line)
    assert any("128" in e and "列" in e for e in errs), errs


def test_surface_line_over_80_under_128_warning():
    # 80–128 列之间 → 警告
    # "1  PX  0" = 8 列，剩下填到约 85 列
    line = "1  PX  0  " + " ".join(str(i) for i in range(30))
    errs = _check_surfaces_text(line)
    assert any("80" in e and "列" in e for e in errs), errs


def test_surface_line_short_ok():
    errs = _check_surfaces_text("6  PZ  1")
    assert not [e for e in errs if "列" in e], errs


# ── 未定义曲面引用检查 ──

def _cell(number: int, surface_expr: str) -> CellData:
    return CellData(number=number, material="0", density="", surface_expr=surface_expr)


def _geo_errors(surfaces: str, cells) -> list[str]:
    errs = validate_all(
        BasicSettings(title="t", mode_n=True, nps="1000"),
        surfaces, cells, [], [], None, AdvancedSettings(),
    )
    return errs


def test_defined_surface_reference_ok():
    errs = _geo_errors("1  PX  0\n2  PZ  0\n", [_cell(1, "-1 2"), _cell(2, "1 -2")])
    assert not [e for e in errs if "未定义的曲面" in e], errs


def test_undefined_surface_reference_error():
    errs = _geo_errors("1  PX  0\n", [_cell(1, "-1 2"), _cell(2, "1 99")])
    assert any("未定义的曲面 99" in e for e in errs), errs


def test_collect_surface_numbers():
    assert _collect_surface_numbers("1  PX  0\nC comment\n3  PZ  5\n") == {1, 3}


def test_material_only_density_still_validated():
    m = _mat(1, [_nuclide("1001", "-1.0")])
    cell = CellData(number=1, material="1", density="-1.0", surface_expr="-1")
    errs = validate_all(
        BasicSettings(title="t", mode_n=True, nps="1000"),
        "1  SPH  0 0 0  1", [cell], [m], [], None, AdvancedSettings(),
    )
    assert not [e for e in errs if "未定义的曲面" in e], errs
