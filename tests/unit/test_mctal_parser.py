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
