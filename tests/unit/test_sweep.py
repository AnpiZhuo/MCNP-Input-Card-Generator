"""参数扫描纯函数测试（对齐 OWEN sweepCore.ts 语义，纯 stdlib）。"""

import json
import os
import tempfile

import pytest

import app.sweep as sweep_mod
from app.sweep import (
    apply_parameters, build_summary_tsv, cartesian, cleanup_sweep_dir, parse_keff,
    parse_keff_history, persist_sweep_summary, run_dir_name, sweep_budget_status,
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


def test_parse_keff_history_from_mctal():
    text = (
        "ktally 1 nps=100\n"
        "k  eff (c) 1.00000 0.00200\n"
        "k  eff (c) 1.00100 0.00190\n"
        "k  eff (c) 1.00050 0.00180\n"
        "combined keff = 1.00030 0.00110\n"
    )
    h = parse_keff_history(text)
    assert h is not None
    assert h["cycles"] == [1, 2, 3]
    assert h["mean"] == [1.0, 1.001, 1.0005]
    assert h["std"] == [0.002, 0.0019, 0.0018]


def test_parse_keff_history_none_when_no_sequence():
    assert parse_keff_history("no keff here") is None
    assert parse_keff_history("") is None


# ── T3：sweep-run 总时长预算（命令硬性超时纪律）──────────────
def test_sweep_budget_within_limit_is_none():
    """组合数×单次超时 ≤ 预算 → None（可执行）。"""
    assert sweep_budget_status(0) is None
    assert sweep_budget_status(1) is None          # 300 ≤ 1800
    assert sweep_budget_status(6) is None          # 6×300=1800 = 预算，不超


def test_sweep_budget_exceeded_reports_code_and_count():
    """超预算 → code="budget_exceeded"，消息含当前组合数与预算说明。"""
    r = sweep_budget_status(7)                     # 7×300=2100 > 1800
    assert r is not None
    assert r["code"] == "budget_exceeded"
    assert "7" in r["message"]                     # 当前组合数
    assert "预算" in r["message"]


def test_sweep_budget_exceeded_combo_cap():
    """组合数超上限 50 → 拒绝。"""
    r = sweep_budget_status(51)
    assert r is not None
    assert r["code"] == "budget_exceeded"
    assert "50" in r["message"]


def test_sweep_budget_custom_limits():
    assert sweep_budget_status(10, per_run_timeout=10, total_budget=100) is None
    assert sweep_budget_status(11, per_run_timeout=10, total_budget=100) is not None


# ── T8：sweep 临时目录清理（摘要先拷贝再删）────────────────
def test_persist_summary_then_cleanup_sweep_dir(tmp_path, monkeypatch):
    """摘要（manifest+TSV）拷贝到稳定目录后 rmtree 临时目录。"""
    base_dir = tempfile.mkdtemp(prefix="mcnp_sweep_test_")
    try:
        run_dir = os.path.join(base_dir, "run_001")
        os.makedirs(run_dir)
        with open(os.path.join(run_dir, "sweep.i"), "w", encoding="utf-8") as f:
            f.write("t\n")
        manifest = {"baseFile": "sweep.i", "runs": [{"index": 1}]}
        tsv = "index\tnps\texit\tkeff\n1\t1000\t0\t1.001000\n"
        summary_root = str(tmp_path / "summaries")
        monkeypatch.setattr(sweep_mod, "SWEEP_SUMMARY_ROOT", summary_root)

        summary_base, manifest_path, tsv_path = persist_sweep_summary(
            base_dir, manifest, tsv)
        # 摘要保留、内容正确
        assert os.path.isfile(manifest_path)
        assert os.path.isfile(tsv_path)
        with open(manifest_path, encoding="utf-8") as f:
            assert json.load(f)["baseFile"] == "sweep.i"
        # 摘要目录存在（稳定位置）
        assert os.path.isdir(summary_base)

        cleanup_sweep_dir(base_dir)
        # 临时目录（含 run_XXX 子目录与大文件）已删，摘要仍在
        assert not os.path.exists(base_dir)
        assert os.path.isfile(manifest_path)
        assert os.path.isfile(tsv_path)
    finally:
        cleanup_sweep_dir(base_dir)


def test_cleanup_sweep_dir_ignores_missing():
    cleanup_sweep_dir(os.path.join(tempfile.gettempdir(), "mcnp_sweep_不存在_"))


# ── T9：_substitute 用 m.start(1)/m.end(1) 精确定位 ─────────
def test_substitute_precise_group_position():
    """group(1) 文本在匹配上下文中更早出现时，替换必须落在组精确位置。

    模式为「一位数字 + 捕获组数字 + cm」，匹配 "55cm"：group(0)="55cm"，
    group(1) 是第二个 "5"。旧实现 m.group(0).index(group) 命中第一个 "5"
    会错位；m.start(1)/m.end(1) 精确定位。
    """
    text = "半径 55cm 的栅元"
    schema = [{"name": "r", "pattern": r"\d(\d+)cm"}]
    out = apply_parameters(text, {"r": "7"}, schema)
    assert out == "半径 57cm 的栅元"


def test_substitute_simple_cm_unchanged():
    text = "长度 12cm"
    schema = [{"name": "len", "pattern": r"(\d+)cm"}]
    assert apply_parameters(text, {"len": "9"}, schema) == "长度 9cm"


# ── T14：parse_keff 静默降级 → warn 级日志（保留分层兜底）────
def test_parse_keff_warns_on_mctal_failure(caplog, monkeypatch):
    """parse_mctal 崩溃时 warn 记录原因，正则兜底仍返回。"""
    def boom(text):
        raise ValueError("模拟 mctal 解析崩溃")
    monkeypatch.setattr(sweep_mod, "parse_mctal", boom)
    with caplog.at_level("WARNING", logger="app.sweep"):
        assert parse_keff("k-eff = 1.0123") == 1.0123
    assert any("parse_keff" in rec.message for rec in caplog.records)
