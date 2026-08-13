"""回归测试：FM 计数乘子卡（FMn）导入识别（用户反馈 #1，P0 优先）。

参考样例：D:\\MCNP\\MCNP6\\MCNP_CODE\\MCNP6\\Testing\\
          VALIDATION_SHIELDING\\Inputs\\photon_skyshine.inp
          L87  f5z:p   100.  5000.  99.
          L127 fm5     8.65061E10  1 -5 -6

根因（已修，2026-08-13）：
  入口门（app/generator/parsers/core.py:1001-1003）正则扩 `^[*+]?FM\\d+`（FM 卡无粒子设计符）；
  parse_f_tally（core.py）新增 FM 分支 —— 乘子参数串附加到同 number 的 TallyDefinition.multiplier
  （FMn 乘在 Fn 计数上；Fn 未先行时建占位 type=""，保证不丢）；
  TallyDefinition（app/models.py）新增 multiplier 字段；
  生成器 _generate_tallies（inp_generator.py）在对应 F 卡之后输出 FM 卡；
  api_server 序列化把 multiplier 带出到前端 tallies 每项（导入→导出不丢）。
"""
import re

from app.generator.inp_generator import _generate_tallies
from app.generator.parsers.core import parse_data_cards, parse_f_tally
from app.models import TallySettings


def _entry_gate_matches(first: str) -> bool:
    """逐字复刻 core.py 入口门正则（含 FM 分支）。"""
    return bool(
        re.match(r'^[*+]?F\d+:', first) or re.match(r'^[*+]?F\d+$', first)
        or re.match(r'^[*+]?FM\d+$', first)
        or re.match(r'^[*+]?F(?:IP|IR|IC)\d+:', first)
        or re.match(r'^[*+]?F(?:IP|IR|IC)\d+$', first)
        or re.match(r'^[*+]?F\d+[XYZ]:', first)
        or re.match(r'^[*+]?F\d+[XYZ][NPEHAS]$', first)
    )


def test_entry_gate_recognizes_fm5():
    """FM 乘子卡（F 后是 M 非数字）现在被入口门识别为计数卡。"""
    assert _entry_gate_matches("FM5") is True
    assert _entry_gate_matches("FM4") is True


def test_parse_f_tally_attaches_multiplier():
    """parse_f_tally 处理 FM5 返回 True，multiplier 附加到同 number 的 TallyDefinition。
    覆盖两种顺序：F 卡先行（附加）；FM 卡先行（建占位 → F 卡解析时吸收，multiplier 并入真实卡）。
    """
    # 场景一：先 F5Z:P 后 FM5（F 卡先行）
    tally_defs = []
    handled = parse_f_tally(["F5Z:P", "100.", "5000.", "99."], tally_defs)
    assert handled is True
    handled = parse_f_tally(["FM5", "8.65061E10", "1", "-5", "-6"], tally_defs)
    assert handled is True
    assert len(tally_defs) == 1
    td = tally_defs[0]
    assert td.type == "F5" and td.number == 5 and td.number_suffix == "Z"
    assert td.multiplier == "8.65061E10 1 -5 -6"
    # 场景二：先 FM4 后 F4:N（FM 卡先行 → 占位吸收）
    tally_defs2 = []
    parse_f_tally(["FM4", "1", "1", "-6"], tally_defs2)
    assert len(tally_defs2) == 1 and tally_defs2[0].type == "" and tally_defs2[0].number == 4
    parse_f_tally(["F4:N", "1", "2"], tally_defs2)
    assert len(tally_defs2) == 1
    assert tally_defs2[0].type == "F4" and tally_defs2[0].number == 4
    assert tally_defs2[0].multiplier == "1 1 -6"


def test_fm5_absorbed_into_tally_and_generator_replays():
    """F5Z:P + FM5 → 乘子被吸收进 tally 结构（不进 other_cards），生成器在 F 卡后回放 FM 卡。"""
    result = parse_data_cards([
        "MODE P",
        "F5Z:P  100. 5000. 99.",
        "FM5  8.65061E10  1 -5 -6",
        "NPS 100000",
    ])
    assert len(result["tally_defs"]) == 1
    td = result["tally_defs"][0]
    assert td.type == "F5" and td.number == 5
    assert td.particles == ["p"]
    assert td.params == "100. 5000. 99."
    assert td.number_suffix == "Z"
    assert td.multiplier == "8.65061E10 1 -5 -6"
    # FM5 不再落入 other_cards（乘子不丢）
    assert not any(c.startswith("FM5") for c in result["other_cards"])
    # 生成器在对应 F 卡之后回放 FM 卡
    lines = _generate_tallies(TallySettings(tallies=[td]))
    f_idx = next(i for i, l in enumerate(lines) if l.strip().startswith("F5Z:P"))
    fm_idx = next(i for i, l in enumerate(lines) if l.strip().startswith("FM5"))
    assert fm_idx == f_idx + 1
    assert lines[fm_idx].strip() == "FM5  8.65061E10 1 -5 -6"
