"""回归测试：SDEF 裸参数（无 = 号）静默丢值（词条审计 D-07，P2）。

缺陷（当前工作树，2026-08-13）：
  app/generator/parsers/core.py parse_sdef_simple 裸分支（:571-592）
  白名单只有 POS / PAR / SUR / NRM / TR / CCC / ARA / RATE；
  裸 `ERG 14` / `WGT 1` / `CEL 2` / `TME 0` / `EFF 0.5` / `X 5` / `AXS 0 0 1` / `DIR 1`
  → `ti += 1` 跳过，**静默丢值**。

触发场景（当前红，修复后转绿为验收基准）：
  ① 单裸参数：SDEF ERG 14 / WGT 1 / CEL 2 / TME 0 / EFF 0.5 / X 5 / AXS 0 0 1 / DIR 1；
  ② 组合裸参数：SDEF ERG 14 X 5 AXS 0 0 1；
  ③ 混合 = 与裸参数：SDEF POS=0 0 0 ERG 14 WGT 1（POS 续值收集会吞掉裸 ERG/WGT）。

期望修复后行为（验收基准）：
  裸分支白名单补 ERG/WGT/CEL/TME/EFF/X/Y/Z/RAD/EXT/AXS/VEC/DIR（复用 _apply_sdef_param），
  AXS 等多值参数整体收集 → 值进对应字段（EFF 进 sdef_extra）。

对照（不回归）：
  EFF=0.5 等号形式已保留（sdef_extra），不应回归。
"""
from app.generator.inp_generator import generate_inp_from_deck
from app.generator.parsers import parse_inp_text
from app.generator.parsers.core import parse_sdef_simple


def _sdef(card_text: str) -> object:
    """解析单行 SDEF 卡文本 → 第一个 SourceData。"""
    return parse_sdef_simple(card_text.split())[0]


# ---- ① 单裸参数 ------------------------------------------------------------

def test_sdef_bare_erg_kept():
    src = _sdef("SDEF ERG 14")
    assert src.erg == "14", f"裸 ERG 静默丢值，src.erg={src.erg!r}"


def test_sdef_bare_wgt_kept():
    src = _sdef("SDEF WGT 1")
    assert src.wgt == "1", f"裸 WGT 静默丢值，src.wgt={src.wgt!r}"


def test_sdef_bare_cel_kept():
    src = _sdef("SDEF CEL 2")
    assert src.cel == "2", f"裸 CEL 静默丢值，src.cel={src.cel!r}"


def test_sdef_bare_tme_kept():
    src = _sdef("SDEF TME 0")
    assert src.tme == "0", f"裸 TME 静默丢值，src.tme={src.tme!r}"


def test_sdef_bare_eff_kept():
    src = _sdef("SDEF EFF 0.5")
    assert "EFF=0.5" in src.sdef_extra, f"裸 EFF 静默丢值，src.sdef_extra={src.sdef_extra!r}"


def test_sdef_bare_x_kept():
    src = _sdef("SDEF X 5")
    assert src.pos_x == "5", f"裸 X 静默丢值，src.pos_x={src.pos_x!r}"


def test_sdef_bare_axs_kept():
    src = _sdef("SDEF AXS 0 0 1")
    assert src.axs == "0 0 1", f"裸 AXS 静默丢值，src.axs={src.axs!r}"


def test_sdef_bare_dir_kept():
    src = _sdef("SDEF DIR 1")
    assert src.dir_ == "1", f"裸 DIR 静默丢值，src.dir_={src.dir_!r}"


# ---- ② 组合裸参数 -----------------------------------------------------------

def test_sdef_bare_combined_erg_x_axs_kept():
    """组合裸参数 `SDEF ERG 14 X 5 AXS 0 0 1` → ERG/X/AXS 全部保留。"""
    src = _sdef("SDEF ERG 14 X 5 AXS 0 0 1")
    assert src.erg == "14", f"组合裸 ERG 静默丢值，src.erg={src.erg!r}"
    assert src.pos_x == "5", f"组合裸 X 静默丢值，src.pos_x={src.pos_x!r}"
    assert src.axs == "0 0 1", f"组合裸 AXS 静默丢值，src.axs={src.axs!r}"


# ---- ③ 混合 = 与裸参数 ------------------------------------------------------

def test_sdef_mixed_pos_erg_wgt_kept():
    """混合 `SDEF POS=0 0 0 ERG 14 WGT 1` → POS 续值收集不得吞掉裸 ERG/WGT。"""
    src = _sdef("SDEF POS=0 0 0 ERG 14 WGT 1")
    assert (src.pos_x, src.pos_y, src.pos_z) == ("0", "0", "0"), "POS 位置应保留"
    assert src.erg == "14", f"混合裸 ERG 被 POS 续值吞掉，src.erg={src.erg!r}"
    assert src.wgt == "1", f"混合裸 WGT 被 POS 续值吞掉，src.wgt={src.wgt!r}"


# ---- 对照：EFF=val 等号形式不回归 --------------------------------------------

def test_control_sdef_eff_equals_form_kept():
    """对照：EFF=0.5 等号形式已保留进 sdef_extra，不应回归。"""
    src = _sdef("SDEF EFF=0.5")
    assert "EFF=0.5" in src.sdef_extra, f"等号 EFF 回归丢失，src.sdef_extra={src.sdef_extra!r}"


# ---- round-trip：裸参数值经 parse→generate 后不丢 -----------------------------

def _shell_wrap_data(text: str) -> str:
    """数据卡文本放入数据段（cells/surfaces 之后），供 parse_inp_text 全链路 round-trip。"""
    return f"C  shell\n1 0 -1\n\nC  surf\n1 pz -1e9\n\n{text}\n"


def test_sdef_bare_values_round_trip_kept():
    """组合 SDEF 裸参数 round-trip 后输出仍含 ERG/WGT/CEL/TME/AXS/DIR 值。"""
    sdef_card = "SDEF POS=0 0 0 ERG 14 WGT 1 CEL 2 TME 0 AXS 0 0 1 DIR 1"
    deck, _warnings = parse_inp_text(_shell_wrap_data(sdef_card))
    out = generate_inp_from_deck(deck)
    for needle in ("ERG=14", "WGT=1", "CEL=2", "TME=0", "AXS=0 0 1", "DIR=1"):
        assert needle in out, f"round-trip 输出丢失裸参数值 {needle!r}。输出:\n{out}"
