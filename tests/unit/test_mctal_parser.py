"""mctal 解析器单元测试（纯 stdlib，不 import vtk / FreeCAD / api_server）。"""

from pathlib import Path

import pytest

from app.mctal_parser import parse_mctal


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_owen_sample_mctal_keff_and_spectrum():
    """OWEN 简化 sample.mctal：5 周期 k-eff + tally 4 通量谱。"""
    r = parse_mctal(_load("sample.mctal"))
    assert r["status"] == "ok"
    assert r["keff"] is not None
    assert r["keff"]["mean"] == pytest.approx([0.98, 0.985, 0.99, 0.995, 1.0])
    assert r["keff"]["std"][-1] == pytest.approx(0.001)
    assert len(r["tallies"]) == 1
    t = r["tallies"][0]
    assert t["id"] == "4"
    assert t["spectrum"] is not None
    assert len(t["spectrum"]) == 5
    assert t["spectrum"][0] == {"e": 1e-05, "flux": 1.2e05}


def test_realistic_kcode_mctal():
    """真实结构 kcode mctal：version / ktally 周期 + combined / tally 能量网格。"""
    r = parse_mctal(_load("kcode_realistic.mctal"))
    assert r["status"] == "ok"
    assert r["version"] == pytest.approx(1.0)
    assert r["keff"] is not None
    assert len(r["keff"]["cycles"]) == 5
    assert r["keff"]["combined"] == {"mean": pytest.approx(1.0003),
                                     "std": pytest.approx(0.0011)}
    tallies = r["tallies"]
    assert len(tallies) == 2
    kt, t4 = tallies[0], tallies[1]
    assert kt["id"] == "1"
    assert t4["id"] == "4"
    assert t4["nps"] == 100000
    assert t4["energy_bins"] == pytest.approx(
        [1e-05, 0.1, 1.0, 10.0, 100.0])
    # 能量网格之后的数值行：cell1 值、cell1 相对误差、cell2 值、cell2 相对误差
    assert len(t4["rows"]) == 4
    assert len(t4["rows"][0]) == 5


def test_garbage_input_warns():
    """无法识别的文本 → status ok + warnings（容错不抛）。"""
    r = parse_mctal("this is not an mctal file\njust some text\n")
    assert r["status"] == "ok"
    assert r["keff"] is None
    assert r["tallies"] == []
    assert len(r["warnings"]) >= 1


def test_empty_input():
    r = parse_mctal("")
    assert r["status"] == "ok"
    assert r["keff"] is None
    assert len(r["warnings"]) >= 1


def test_top_level_nps_parsed_from_header():
    """mctal 头部含 nps → 顶层 nps 填充（不再硬编码 None）。"""
    text = (
        "1.0 mctal\n"
        "nps = 250000\n"
        "ktally 1 nps = 100000\n"
        "k  eff (c) 1.00000 0.00200\n"
        "combined keff = 1.00030 0.00110\n"
    )
    r = parse_mctal(text)
    assert r["nps"] == 250000


def test_top_level_nps_absent_when_not_in_header():
    """头部无 nps → 返回结构不含 nps 键（死字段移除）。"""
    r = parse_mctal(_load("sample.mctal"))
    assert "nps" not in r
    # 各 tally 块的 nps 解析不受影响（sample 无 nps，但结构键存在）
    assert all("nps" in t for t in r["tallies"])


# ── 真实 MCNP6 mctal（kcode 裸数值块）────────────────────────────────────────
def test_real_mcnp6_kcode_mctal_series_and_combined():
    """真实 MCNP6 mctal：``mcnp <ver>`` 头 + ``kcode`` 块 → 逐周期序列 + 最终值。

    夹具 = ZEUS-1 10 Uniform Units / HEU-MET-INTER-006 case 1（KCODE 10000 1.0 100 600，
    600 周期、无计数卡），逐列已与同算例的 .o（print table 175）核对：
    ``mean`` = 第 1 列 k(collision)，``combined`` = 累计平均列末值。
    """
    r = parse_mctal(_load("real_kcode_zeus1.mctal"))
    assert r["status"] == "ok"
    assert r["version"] == pytest.approx(6.0)
    assert r["warnings"] == []
    assert r["tallies"] == []              # ntal 0：该算例未用计数卡
    k = r["keff"]
    assert k is not None
    assert len(k["cycles"]) == 600
    assert k["cycles"][0] == 1 and k["cycles"][-1] == 600
    assert k["mean"][0] == pytest.approx(1.04435)
    assert k["mean"][-1] == pytest.approx(1.00217)
    assert k["std"] == []                  # mctal 不逐周期写 σ（只写累计平均的）
    # 最终组合 keff = .o 结果段的 "final estimated combined ... keff = 0.99277
    # with an estimated standard deviation of 0.00036"
    assert k["combined"]["mean"] == pytest.approx(0.99277, abs=1e-5)
    assert k["combined"]["std"] == pytest.approx(0.00036, abs=1e-5)


def _kcode_cycle(kc, ka, kt, avg_mean, avg_std):
    """一个周期的 19 列（kcode 块列序，见 mctal_parser._KCODE_COL_* 注释）。"""
    return [kc, ka, kt, 2.0E+02, 1.9E+02, 0, 0, 0, 0, 0, 0, avg_mean, avg_std,
            0, 0, 1.9E+02, 2.0E-01, 1.0E+04, 1.0E+03]


def _kcode_block(cycles):
    """把若干周期按真实排版（每行 5 个值）拼成 kcode 数值块。"""
    out = []
    for cols in cycles:
        for i in range(0, len(cols), 5):
            out.append(" ".join(f"{v:E}" for v in cols[i:i + 5]))
    return "\n".join(out) + "\n"


def test_real_style_kcode_block_minimal_and_truncated():
    """kcode 块最小复刻：按列定位；数值不足声明周期数（截断运行）时按可分组数截断。"""
    text = (
        "mcnp       6     09/20/26 00:07:54     2         5998960      3544647706\n"
        " ZEUS-1 minimal kcode\n"
        "ntal     0\n"
        "\n"
        "kcode  600  100   19\n"          # 声明 600 周期，实际只给 2 个（截断容错）
        + _kcode_block([_kcode_cycle(1.10, 1.09, 1.08, 0.0, 0.0),
                        _kcode_cycle(0.90, 0.91, 0.92, 0.0, 0.0)])
    )
    k = parse_mctal(text)["keff"]
    assert k["cycles"] == [1, 2]
    assert k["mean"] == pytest.approx([1.10, 0.90])   # 第 1 列 = k(collision)
    assert k["std"] == []
    assert k["combined"] is None                       # 累计平均列全 0（未进活跃周期）


def test_real_style_kcode_combined_from_last_nonzero_average():
    """最终组合 keff 取累计平均列的**最后一组非零**（第 12/13 列）。"""
    text = (
        "mcnp       6     \n ZEUS-1\nntal     0\n\nkcode  3  0   19\n"
        + _kcode_block([_kcode_cycle(1.10, 1.09, 1.08, 1.00, 1.0E-03),
                        _kcode_cycle(0.90, 0.91, 0.92, 0.95, 2.0E-03),
                        _kcode_cycle(0.95, 0.95, 0.95, 0.0, 0.0)])
    )
    k = parse_mctal(text)["keff"]
    assert k["mean"] == pytest.approx([1.10, 0.90, 0.95])
    assert k["combined"] == {"mean": pytest.approx(0.95), "std": pytest.approx(2.0e-3)}


def test_kcode_word_without_numbers_is_tolerated():
    """只有 ``kcode`` 字样、无数值块 → 不崩、keff 为 None。"""
    assert parse_mctal("kcode  600  100   19\nnot numbers\n")["keff"] is None
