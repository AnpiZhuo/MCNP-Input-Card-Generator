"""参数扫描纯函数测试（对齐 OWEN sweepCore.ts 语义，纯 stdlib）。"""

import json
import os
import tempfile
from pathlib import Path

import pytest

import app.sweep as sweep_mod
from app.sweep import (
    apply_parameters, build_summary_tsv, cartesian, cleanup_sweep_dir,
    finalize_run_dir, history_keff_std, list_run_files, parse_keff,
    parse_keff_history, persist_sweep_summary, prepare_results_dir,
    run_dir_name, scan_run_dir, sweep_budget_status, write_summary_files,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


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


# ── 真实 MCNP 结果文件的 keff 序列（mctal kcode 块 / outp(.o) 周期表）──────
def test_parse_keff_history_from_real_kcode_mctal():
    """真实 mctal 的 kcode 块 → 600 周期序列 + combined（std 为空：不逐周期写 σ）。"""
    text = (FIXTURES / "real_kcode_zeus1.mctal").read_text(encoding="utf-8")
    h = parse_keff_history(text)
    assert h is not None
    assert len(h["cycles"]) == 600
    assert h["mean"][0] == pytest.approx(1.04435)
    assert h["std"] == []
    assert h["combined"]["mean"] == pytest.approx(0.99277, abs=1e-5)
    assert parse_keff(text) == pytest.approx(0.99277, abs=1e-5)


def test_parse_keff_history_from_real_outp_file():
    """outp（.o）也能给序列 —— /api/parse-keff 与扫描侧因此不限于 mctal。"""
    text = (FIXTURES / "real_kcode_zeus1.o").read_text(encoding="utf-8", errors="replace")
    h = parse_keff_history(text)
    assert h is not None
    assert len(h["cycles"]) == 600
    assert h["mean"][0] == pytest.approx(1.04435)
    assert h["combined"]["std"] == pytest.approx(0.00036)


def test_history_keff_std_prefers_cycle_std_then_combined():
    """σ 取值口径：OWEN 式逐周期 σ 优先；真实文件只有 combined.std。"""
    assert history_keff_std({"std": [0.002, 0.0019], "combined": {"std": 0.001}}) == 0.0019
    assert history_keff_std({"std": [], "combined": {"std": 0.00036}}) == 0.00036
    assert history_keff_std({"std": [], "combined": None}) is None
    assert history_keff_std(None) is None


def test_scan_run_dir_reads_outp_when_no_mctal(tmp_path):
    """运行目录里只有 outp（``name=`` 前缀的 sweep-001.o）时也能拿到 keff。"""
    (tmp_path / "sweep-001.o").write_text(
        (FIXTURES / "real_kcode_zeus1.o").read_text(encoding="utf-8", errors="replace"),
        encoding="utf-8")
    res = scan_run_dir(str(tmp_path))
    assert res["path"].endswith("sweep-001.o")
    assert res["keff"] == pytest.approx(0.99277)
    assert len(res["history"]["cycles"]) == 600
    assert history_keff_std(res["history"]) == pytest.approx(0.00036)


def test_scan_run_dir_prefers_mctal(tmp_path):
    """mctal 与 outp 同时存在 → mctal 优先（体积小且含 combined）。"""
    (tmp_path / "mctal").write_text(
        (FIXTURES / "real_kcode_zeus1.mctal").read_text(encoding="utf-8"),
        encoding="utf-8")
    (tmp_path / "sweep-001.o").write_text("1tally 4 nps = 100\n", encoding="utf-8")
    assert scan_run_dir(str(tmp_path))["path"].endswith("mctal")


def test_scan_run_dir_empty_or_missing(tmp_path):
    """空目录 / 不存在目录 / 无结果文件 → 全空结构（扫描表由此判 n/a 而不是崩）。"""
    for d in (str(tmp_path), str(tmp_path / "不存在"), ""):
        res = scan_run_dir(d)
        assert res["keff"] is None and res["history"] is None and res["path"] is None
    (tmp_path / "sweep.i").write_text("t\n", encoding="utf-8")
    assert scan_run_dir(str(tmp_path))["keff"] is None


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


# ── 锚点模式（GUI「选中即参数」产出，免正则）──
def test_apply_anchor_mode_basic():
    """anchor+context：替换含 context 的首行内的 anchor，行内其余文本保留。"""
    text = "NPS    1000\nkcode 1000 1.0 50 100\n"
    schema = [
        {"name": "nps", "anchor": "1000", "context": "NPS    1000"},
        {"name": "rkk", "anchor": "1.0", "context": "kcode 1000 1.0 50 100"},
    ]
    out = apply_parameters(text, {"nps": "5000", "rkk": "1.2"}, schema)
    assert out == "NPS    5000\nkcode 1000 1.2 50 100\n"


def test_apply_anchor_same_line_multi_values():
    """同一行多个参数：基于同一份原始文本定位，两个数都能同时替换。"""
    text = "kcode 1000 1.0 50 100\n"
    schema = [
        {"name": "cyc", "anchor": "1000", "context": "kcode 1000 1.0 50 100"},
        {"name": "rkk", "anchor": "1.0", "context": "kcode 1000 1.0 50 100"},
    ]
    out = apply_parameters(text, {"cyc": "500", "rkk": "1.2"}, schema)
    assert out == "kcode 500 1.2 50 100\n"


def test_apply_anchor_empty_context_whole_text_first():
    """context 为空 → 全文首个 anchor 命中替换（仅一次）。"""
    text = "1.0 1.0\n"
    schema = [{"name": "v", "anchor": "1.0", "context": ""}]
    out = apply_parameters(text, {"v": "2.0"}, schema)
    assert out == "2.0 1.0\n"


def test_apply_anchor_only_target_line():
    """context 唯一锁定目标行：别处相同的数字不受影响。"""
    text = "1 0 -1\n2 1 1.0 -1\nm1 1001 1.0\n"
    schema = [{"name": "d", "anchor": "1.0", "context": "2 1 1.0 -1"}]
    out = apply_parameters(text, {"d": "0.5"}, schema)
    assert out == "1 0 -1\n2 1 0.5 -1\nm1 1001 1.0\n"


# ══════════════════════════════════════════════════════════════════════
# 文本级精确替换（2026-10-11 用户口径，逐字确认过两次）：
#   「我划了这些文字，你就把这些文字删掉，用我另外给出的文字替换」
#   「不是整段删掉，是只把我划中的部分删掉」
#   ⇒ 前端把选区的 **start/end 字符偏移** 一起发过来；后端**只认这个区间**，
#     删掉那段、插入新内容，**长度不限**（更长/更短都行）。
#   ⇒ 旧口径「含 context 的首行 + 行内首个 anchor」是**猜**，同一个字出现两次就改错地方
#     （实测：`SO 1 2323255 6` 划第二个 5 → 改了第一个）。
# ══════════════════════════════════════════════════════════════════════

def test_text_span_replace_exact_offsets_same_char_twice():
    """同一行里同一个字出现两次：只改划中的那一个（旧口径改的是第一个）。"""
    text = "SO 1 2323255 6\n"
    # 用户划中第二个 '5'（行内第 11 个字符，0-based）→ 只删这一个字符
    schema = [{"name": "p", "anchor": "5", "context": "SO 1 2323255 6",
               "start": 11, "end": 12}]
    assert apply_parameters(text, {"p": "9"}, schema) == "SO 1 2323259 6\n"


def test_text_span_replace_length_is_free():
    """替换长度不受选区长度限制：划 2 个字符可以换成 1 个或 7 个（像 Word 里删掉再键入）。"""
    text = "SO 1 2323255 6\n"
    schema = [{"name": "p", "anchor": "55", "context": "SO 1 2323255 6",
               "start": 10, "end": 12}]
    assert apply_parameters(text, {"p": "7"}, schema) == "SO 1 232327 6\n"
    assert apply_parameters(text, {"p": "12345"}, schema) == "SO 1 2323212345 6\n"


def test_text_span_replace_only_selected_part_removed():
    """只删划中的部分：整个数、整行其余内容都必须原样保留。"""
    text = "SO 1 2323255 6\n"
    schema = [{"name": "p", "anchor": "2323255", "context": "SO 1 2323255 6",
               "start": 5, "end": 12}]
    assert apply_parameters(text, {"p": "88"}, schema) == "SO 1 88 6\n"


def test_text_span_replace_second_occurrence_line():
    """文件里两行一模一样：划的是第二行就只改第二行（旧口径改第一行）。"""
    text = "c header\nnps 1000000\nc mid\nnps 1000000\n"
    second = text.rindex("1000000")
    schema = [{"name": "nps", "anchor": "1000000", "context": "nps 1000000",
               "start": second, "end": second + 7}]
    out = apply_parameters(text, {"nps": "2000000"}, schema)
    assert out == "c header\nnps 1000000\nc mid\nnps 2000000\n"


def test_text_span_replace_multi_params_shift_safe():
    """同一份文本里多处替换：前面的替换变长/变短都不能让后面的错位。"""
    text = "SO 1 2323255 6\nNPS 1000\n"
    schema = [
        {"name": "a", "anchor": "55", "context": "SO 1 2323255 6", "start": 10, "end": 12},
        {"name": "b", "anchor": "1000", "context": "NPS 1000", "start": 19, "end": 23},
    ]
    out = apply_parameters(text, {"a": "123456789", "b": "5"}, schema)
    assert out == "SO 1 23232123456789 6\nNPS 5\n"


def test_text_span_replace_stale_offsets_reports_and_does_not_edit():
    """基准文本变了（位置对不上）→ **明确报错**，且绝不改到别处（旧口径会静默改错地方）。"""
    text = "SO 1 2323255 6\n"
    schema = [{"name": "p", "anchor": "55", "context": "SO 1 2323255 6",
               "start": 10, "end": 12}]
    errors: list[str] = []
    # 这一份文本里已经不再有 "2323255"（等价于用户重新生成过输入卡）
    out = apply_parameters("SO 1 99999 6\n", {"p": "7"}, schema, errors)
    assert out == "SO 1 99999 6\n", "位置失效时不得改动任何字符"
    assert errors and "重新" in errors[0]


def test_text_span_replace_offsets_tolerate_surrounding_whitespace():
    """偏移范围两端带空白（前端只把去空白后的内容当 anchor）→ 收窄到真正内容再替换。"""
    text = "SO 1 2323255 6\n"
    schema = [{"name": "p", "anchor": "55", "context": "SO 1 2323255 6",
               "start": 10, "end": 13}]      # 实际覆盖 "55 "（多含一个空格）
    assert apply_parameters(text, {"p": "@"}, schema) == "SO 1 23232@ 6\n"


# ══════════════════════════════════════════════════════════════════════
# 名（给人看）与键（内部用）分开 —— 用户 2026-10-11：
#   「那个 # 加数字，不要给我显示成颜色号」（界面上不许出现 `#1`/`#2` 这种重名后缀）
# ⇒ 参数名恒等于**框选到的内容**（允许重复），唯一性放在看不见的 `key` 上。
# ══════════════════════════════════════════════════════════════════════

def test_same_name_params_use_distinct_keys():
    """两个参数划到同样的内容（name 重复）→ 靠 key 各改各的，不串值。"""
    text = "1 0 -1\n2 0 -1\n"
    schema = [
        {"name": "-1", "key": "p1", "anchor": "-1", "context": "1 0 -1", "start": 4, "end": 6},
        {"name": "-1", "key": "p2", "anchor": "-1", "context": "2 0 -1", "start": 11, "end": 13},
    ]
    assert apply_parameters(text, {"p1": "-7", "p2": "-9"}, schema) == "1 0 -7\n2 0 -9\n"


def test_cartesian_uses_key_when_names_repeat():
    """笛卡尔积的组合字典以 key 为键（同名参数不会互相覆盖）。"""
    params = [
        {"name": "-1", "key": "p1", "values": ["a", "b"]},
        {"name": "-1", "key": "p2", "values": ["x"]},
    ]
    assert cartesian(params) == [{"p1": "a", "p2": "x"}, {"p1": "b", "p2": "x"}]


def test_summary_tsv_header_uses_name_values_use_key():
    """汇总表表头写字给看的 name，取值按 key 查。"""
    parameters = [{"name": "-1", "key": "p1"}, {"name": "-1", "key": "p2"}]
    records = [{"index": 1, "parameters": {"p1": "-7", "p2": "-9"},
                "exitCode": 0, "keff": 1.0}]
    header, row = build_summary_tsv(parameters, records).split("\n")
    assert header == "index\t-1\t-1\texit\tkeff"
    assert row.split("\t")[1:3] == ["-7", "-9"]


def test_key_defaults_to_name_for_legacy_payloads():
    """没给 key 的旧载荷（MCP / 旧前端）照旧按 name 取键，行为不变。"""
    text = "NPS 1000\n"
    schema = [{"name": "nps", "anchor": "1000", "context": "NPS 1000", "start": 4, "end": 8}]
    assert apply_parameters(text, {"nps": "5000"}, schema) == "NPS 5000\n"
    assert cartesian([{"name": "nps", "values": ["1", "2"]}]) == [{"nps": "1"}, {"nps": "2"}]


# ══════════════════════════════════════════════════════════════════════
# 结果保留（2026-10-15 用户要求）：
#   「让 11 个输出文件都保留呗」
# 旧行为：所有组合跑在 %TEMP% 的 mcnp_sweep_<随机> 里，跑完 rmtree ⇒ 用户
# 只能拿到 185 字节的汇总表，11 个 sweep-00N.o 全被删（他自己那三次扫描的
# 结果目录实测 `已被删除`）。现在默认落到
# <outputDir 或 D:/MCNP/new>/sweep_<时间戳>/run_XXX/ 并**保留**。
# ══════════════════════════════════════════════════════════════════════

def test_prepare_results_dir_under_user_dir_and_never_overwrites(tmp_path):
    """保留型目录 = <用户目录>/sweep_<时间戳>/；同一时间戳第二次自动加后缀。"""
    parent = tmp_path / "out"
    d1, p1 = prepare_results_dir(str(parent), stamp="20261015_120000")
    d2, p2 = prepare_results_dir(str(parent), stamp="20261015_120000")
    assert p1 is True and p2 is True
    assert d1 == str(parent / "sweep_20261015_120000")
    assert d2 == str(parent / "sweep_20261015_120000_2")   # 不覆盖上一次
    assert os.path.isdir(d1) and os.path.isdir(d2)


def test_prepare_results_dir_defaults_to_mcnp_new(tmp_path, monkeypatch):
    """不给 outputDir → 默认根（与 /api/run-mcnp 的 D:/MCNP/new 同源）。"""
    monkeypatch.setattr(sweep_mod, "SWEEP_RESULTS_DEFAULT_ROOT", str(tmp_path / "new"))
    d, persistent = prepare_results_dir("", stamp="20261015_130000")
    assert persistent is True
    assert d == str(tmp_path / "new" / "sweep_20261015_130000")


def test_prepare_results_dir_falls_back_to_temp_when_unwritable(tmp_path, monkeypatch):
    """用户目录写不了（父路径是文件）→ 退回临时目录且 persistent=False（跑完照旧清理）。"""
    blocker = tmp_path / "不是目录.txt"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(sweep_mod, "SWEEP_RESULTS_DEFAULT_ROOT", str(blocker))
    d, persistent = prepare_results_dir(str(blocker))
    try:
        assert persistent is False
        assert os.path.isdir(d)
        assert os.path.basename(d).startswith("mcnp_sweep_")
    finally:
        cleanup_sweep_dir(d)


def test_finalize_run_dir_keeps_results_drops_only_huge_restart_file(tmp_path):
    """默认只丢 37.9MB 的二进制重启文件（sweep-00N.r）；结果 outp / 输入卡留下。"""
    outp = tmp_path / "sweep-001.o"
    inp = tmp_path / "sweep.i"
    outp.write_text("1tally 6 nps = 100\n", encoding="utf-8")
    (tmp_path / "sweep-001.r").write_bytes(b"\x00" * 4096)
    inp.write_text("t\n", encoding="utf-8")
    out = finalize_run_dir(str(tmp_path))
    assert {f["name"] for f in out["kept"]} == {"sweep-001.o", "sweep.i"}
    assert out["removed"] == ["sweep-001.r"]
    # 按**实际落盘字节数**比（Windows 文本模式把 \n 写成 \r\n，不写死数字）
    assert out["keptBytes"] == outp.stat().st_size + inp.stat().st_size
    assert out["droppedBytes"] == 4096
    assert not (tmp_path / "sweep-001.r").exists()
    assert outp.exists()


def test_finalize_run_dir_keep_restart_true_keeps_everything(tmp_path):
    """SWEEP_KEEP_RESTART=True 语义：一个都不删（要留整个留）。"""
    (tmp_path / "sweep-001.o").write_text("x", encoding="utf-8")
    (tmp_path / "sweep-001.r").write_bytes(b"\x01" * 10)
    out = finalize_run_dir(str(tmp_path), keep_restart=True)
    assert out["removed"] == []
    assert {f["name"] for f in out["kept"]} == {"sweep-001.o", "sweep-001.r"}


def test_finalize_run_dir_also_drops_default_named_runtpe(tmp_path):
    """没给 ``name=`` 时 MCNP 写默认名 ``runtpe``（同样是那个 37.9MB 大文件）⇒ 也要丢。"""
    (tmp_path / "sweep-001.o").write_text("x", encoding="utf-8")
    (tmp_path / "runtpe").write_bytes(b"\x00" * 2048)
    out = finalize_run_dir(str(tmp_path))
    assert out["removed"] == ["runtpe"]
    assert {f["name"] for f in out["kept"]} == {"sweep-001.o"}
    assert out["droppedBytes"] == 2048


def test_finalize_run_dir_missing_dir_is_empty_not_crash():
    """目录不存在（组合没跑起来）→ 空结构，不抛异常。"""
    out = finalize_run_dir(os.path.join(tempfile.gettempdir(), "mcnp_sweep_没有这个目录_"))
    assert out == {"kept": [], "removed": [], "keptBytes": 0, "droppedBytes": 0}


def test_list_run_files_sorted_by_size_desc_skips_dirs(tmp_path):
    (tmp_path / "a.o").write_text("x" * 5, encoding="utf-8")
    (tmp_path / "b.o").write_text("x" * 50, encoding="utf-8")
    os.makedirs(tmp_path / "sub")
    assert [f["name"] for f in list_run_files(str(tmp_path))] == ["b.o", "a.o"]


def test_write_summary_files_lands_in_results_dir(tmp_path):
    """结果目录自描述：manifest + 汇总 TSV 跟着结果走（run_XXX ↔ 参数取值）。"""
    manifest = {"baseFile": "sweep.i", "runs": [{"index": 1}]}
    tsv = "index\texit\tkeff\n1\t0\tn/a\n"
    mp, tp = write_summary_files(str(tmp_path), manifest, tsv)
    assert os.path.isfile(mp) and os.path.isfile(tp)
    with open(mp, encoding="utf-8") as f:
        assert json.load(f)["runs"][0]["index"] == 1
    with open(tp, encoding="utf-8") as f:
        assert f.read() == tsv
