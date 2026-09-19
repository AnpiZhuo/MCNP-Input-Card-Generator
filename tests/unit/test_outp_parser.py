"""outp_parser 单测：MCNP6.1 紧凑布局 / 能量仓布局 / total 行 / nps 提取 / KCODE 周期表。"""
from pathlib import Path

import pytest

from app.mctal_parser import parse_mctal
from app.outp_parser import parse_keff_cycles, parse_outp


def _sample():
    return """          Code Name & Version = MCNP6, 1.0
1mcnp     version 6     ld=05/08/13                     08/19/26 00:45:20
1problem summary
     run terminated when       10000  particle histories were done.
1tally        4        nps =       10000
           tally type 4    track length estimate of particle flux.      units   1/cm**2
           particle(s): neutrons

           volumes
                   cell:       1
                         4.18879E+03

 cell  1
                 3.36115E-03 0.0071

 ===================================================================================================================================

           results of 10 statistical checks for the estimated answer for the tally fluctuation chart (tfc) bin of tally        4
"""


def test_compact_single_bin_layout():
    """MCNP6.1 单栅元单能仓：cell 行后直接两列 flux/error，无 energy 列、无 total 行。"""
    tallies, nps, warnings = parse_outp(_sample())
    assert nps == 10000
    assert set(tallies.keys()) == {"4"}
    t = tallies["4"]
    assert t["type"] == 4
    assert t["rows"] == [{"energy": "", "flux": "3.36115E-03", "error": "0.0071"}]
    assert t["total"] == {"energy": "total", "flux": "", "error": ""}
    assert warnings == []


def test_energy_bins_with_total_row():
    """能量仓布局：energy/flux/error 三列 + total 行。"""
    text = """1tally        4        nps =       50000
           tally type 4    track length estimate of particle flux.      units   1/cm**2
           particle(s): neutrons
 cell  1
      energy     flux     error
   1.0000E-01   1.234E-03   0.0050
   2.0000E-01   2.345E-03   0.0060
      total       3.579E-03   0.0040
 ===================================================================================================================================
"""
    tallies, nps, _ = parse_outp(text)
    assert nps == 50000
    t = tallies["4"]
    assert t["rows"] == [
        {"energy": "1.0000E-01", "flux": "1.234E-03", "error": "0.0050"},
        {"energy": "2.0000E-01", "flux": "2.345E-03", "error": "0.0060"},
    ]
    assert t["total"] == {"energy": "total", "flux": "3.579E-03", "error": "0.0040"}


def test_multi_cell_flat_collect_last_total():
    """多栅元：数据行扁平收集，total 取最后一行。"""
    text = """1tally        4        nps =       1000
           tally type 4
           particle(s): neutrons
 cell  1
   1.0   1.0E-03   0.01
      total       1.0E-03   0.01
 cell  2
   1.0   2.0E-03   0.02
      total       3.0E-03   0.01
 ===================================================================================================================================
"""
    tallies, _, _ = parse_outp(text)
    t = tallies["4"]
    assert len(t["rows"]) == 2
    assert t["total"]["flux"] == "3.0E-03"


def test_fatal_error_collected_as_warning():
    text = (" fatal error. something\n"
            "1tally        4        nps =       100\n cell  1\n 1.0 2.0 0.1\n")
    tallies, nps, warnings = parse_outp(text)
    assert nps == 100
    assert tallies["4"]["rows"] == [{"energy": "1.0", "flux": "2.0", "error": "0.1"}]
    assert any("fatal error" in w for w in warnings)


def test_f1_surface_layout():
    """F1（面电流）：surface 块标记 + 两列数值（MCNP6.1 紧凑布局）。"""
    text = """1tally        1        nps =       10000
           tally type 1    number of particles crossing a surface.      units   1
           particle(s): neutrons

           surfaces:                       2
     2.1    0.00    2.2    1.00

 surface  2.1
                 1.234E-03 0.0050

 ===================================================================================================================================
"""
    tallies, _, _ = parse_outp(text)
    assert "1" in tallies
    assert tallies["1"]["type"] == 1
    assert tallies["1"]["rows"] == [{"energy": "", "flux": "1.234E-03", "error": "0.0050"}]


def test_f5_detector_layout():
    """F5（点探测器）：detector 块标记 + energy/flux/error 三列 + total。"""
    text = """1tally        5        nps =       10000
           tally type 5    point detector tally.      units   1/cm**2
           particle(s): neutrons
           detector  1
      energy     flux     error
   1.0000E-01   1.234E-03   0.0050
   2.0000E-01   2.345E-03   0.0060
      total       3.579E-03   0.0040
 ===================================================================================================================================
"""
    tallies, _, _ = parse_outp(text)
    assert "5" in tallies
    t = tallies["5"]
    assert t["type"] == 5
    assert t["rows"] == [
        {"energy": "1.0000E-01", "flux": "1.234E-03", "error": "0.0050"},
        {"energy": "2.0000E-01", "flux": "2.345E-03", "error": "0.0060"},
    ]
    assert t["total"]["flux"] == "3.579E-03"


# ── KCODE 逐周期 keff（print table 175）────────────────────────────────────────
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_keff_cycles_from_real_outp():
    """真实 MCNP6 outp（ZEUS-1 case 1，600 周期）：周期表 + 结果段最终组合值。

    该文件同时含表 175 单行式（``cycle N k(collision) ...``）与
    "individual and average keff estimator results by cycle" 表；取后者（3 个估计量）。
    """
    text = (FIXTURES / "real_kcode_zeus1.o").read_text(encoding="utf-8", errors="replace")
    h = parse_keff_cycles(text)
    assert h is not None
    assert len(h["cycles"]) == 600
    assert h["cycles"][0] == 1 and h["cycles"][-1] == 600
    assert h["mean"][0] == pytest.approx(1.04435)
    assert h["mean"][-1] == pytest.approx(1.00217)
    assert h["std"] == []                       # outp 不逐周期写 σ
    assert h["combined"]["mean"] == pytest.approx(0.99277)
    assert h["combined"]["std"] == pytest.approx(0.00036)


def test_keff_cycles_outp_matches_mctal_fixture():
    """同一算例的 .o 与 mctal 给出同一条逐周期序列（口径 = k(collision)）。

    容差 1e-5：outp 的周期表只印 5 位小数，mctal 的 kcode 块印 6 位有效数字。
    """
    outp = parse_keff_cycles(
        (FIXTURES / "real_kcode_zeus1.o").read_text(encoding="utf-8", errors="replace"))
    mctal = parse_mctal(
        (FIXTURES / "real_kcode_zeus1.mctal").read_text(encoding="utf-8"))
    assert outp["cycles"] == mctal["keff"]["cycles"]
    assert outp["mean"] == pytest.approx(mctal["keff"]["mean"], abs=1e-5)


def test_keff_cycles_single_line_form_fallback():
    """无估计量周期表时回落到表 175 单行式（``cycle N k(collision) X``）。"""
    text = (
        "1estimated keff results by cycle                       print table 175\n"
        "\n"
        " cycle     1    k(collision)  1.044348    prompt removal lifetime(abs)  "
        "2.0068E+02    source points generated  10469\n"
        " cycle     2    k(collision)  0.993455    prompt removal lifetime(abs)  "
        "1.9538E+02    source points generated   9541\n"
        "1keff results for: test\n"
        " | the final estimated combined collision/absorption/track-length keff = "
        "0.99277 with an estimated standard deviation of 0.00036   |\n"
    )
    h = parse_keff_cycles(text)
    assert h["cycles"] == [1, 2]
    assert h["mean"] == pytest.approx([1.044348, 0.993455])
    assert h["combined"]["mean"] == pytest.approx(0.99277)


def test_keff_cycles_none_without_cycle_table():
    """非临界算例的输出（无周期表）→ None（不误判别的表）。"""
    assert parse_keff_cycles("1tally        4        nps =       10000\n") is None
    assert parse_keff_cycles("") is None


def test_keff_cycles_ignores_skip_cycles_table():
    """相邻的"不同跳过周期数"表（表头措辞不同、行首无 cycle/histories 对齐）不得混入。"""
    text = (
        "1individual and average keff estimator results by cycle\n\n"
        "  cycle   histories   k(coll)  k(abs)  k(track)\n\n"
        "     1       10000 | 1.04435  1.04378  1.04013  | \n"
        "     2       10469 | 0.99345  0.99593  0.99674  | \n"
        " -------------------------------------------------------------------\n"
        "1individual and collision/absorption/track-length keffs for different "
        "numbers of inactive cycles skipped\n\n"
        "  skip  active     active\n"
        " cycles cycles   neutrons\n\n"
        "     0    600      5998960| 0.9928 0.0003  0.9929 0.0003  0.9932 0.0004 |\n"
    )
    h = parse_keff_cycles(text)
    assert h["cycles"] == [1, 2]
    assert h["mean"] == pytest.approx([1.04435, 0.99345])

