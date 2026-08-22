"""参数扫描纯函数测试（对齐 OWEN sweepCore.ts 语义，纯 stdlib）。"""

from app.sweep import (
    apply_parameters, build_summary_tsv, cartesian, parse_keff, run_dir_name,
)


def test_cartesian():
    params = [
        {"name": "nps", "values": [1000, 10000]},
        {"name": "keff_guess", "values": [1.0, 1.1]},
    ]
    combos = cartesian(params)
    assert combos == [
        {"nps": 1000, "keff_guess": 1.0},
        {"nps": 1000, "keff_guess": 1.1},
        {"nps": 10000, "keff_guess": 1.0},
        {"nps": 10000, "keff_guess": 1.1},
    ]
    assert cartesian([]) == [{}]


def test_apply_parameters_preserves_context():
    text = "NPS    1000\nkcode 1000 1.0 50 100\n"
    schema = [
        {"name": "nps", "pattern": r"NPS\s+(\d+)"},
        {"name": "rkk", "pattern": r"kcode \d+ ([\d.]+)"},
    ]
    out = apply_parameters(text, {"nps": "5000", "rkk": "1.2"}, schema)
    assert "NPS    5000" in out
    assert "kcode 1000 1.2 50 100" in out
    # 未涉及的文本保持不动
    assert "50 100" in out


def test_apply_parameters_only_first_match():
    text = "m1 1001 -0.5 1001 -0.5\n"
    schema = [{"name": "hfrac", "pattern": r"1001 (-[\d.]+)"}]
    out = apply_parameters(text, {"hfrac": "-0.4"}, schema)
    assert out == "m1 1001 -0.4 1001 -0.5\n"


def test_parse_keff_from_mctal():
    text = "ktally 1 nps=100\nk  eff (c) 1.00000 0.00200\ncombined keff = 1.00150 0.00090\n"
    assert parse_keff(text) == 1.0015


def test_parse_keff_fallbacks():
    assert parse_keff("final estimated combined collision/absorption/track-length keff = 1.12345") == 1.12345
    assert parse_keff("Combined k-effective = 0.98765") == 0.98765
    assert parse_keff("k-eff = 1.0123") == 1.0123
    assert parse_keff("no keff here") is None


def test_run_dir_name_and_summary_tsv():
    assert run_dir_name(3) == "run_003"
    params = [{"name": "nps", "values": [1]}]
    records = [
        {"index": 1, "parameters": {"nps": 1000}, "exitCode": 0, "keff": 1.001},
        {"index": 2, "parameters": {"nps": 2000}, "exitCode": None, "keff": None},
    ]
    tsv = build_summary_tsv(params, records)
    lines = tsv.split("\n")
    assert lines[0] == "index\tnps\texit\tkeff"
    assert lines[1] == "1\t1000\t0\t1.001000"
    assert lines[2] == "2\t2000\tn/a\tn/a"
