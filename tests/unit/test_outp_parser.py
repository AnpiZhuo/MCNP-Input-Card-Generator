"""outp_parser 单测：MCNP6.1 紧凑布局 / 能量仓布局 / total 行 / nps 提取。"""
from app.outp_parser import parse_outp


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
