"""校验器材料级规则测试（交叉核对 OWEN rules.ts validateMCNP 后新增）。"""

from app.generator.validator import validate_all
from app.models import AdvancedSettings, BasicSettings, MaterialData, MaterialRow


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
