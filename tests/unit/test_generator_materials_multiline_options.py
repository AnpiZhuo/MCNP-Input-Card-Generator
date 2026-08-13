"""生成器单测：材料 options（"其他"框）多行换行支持。

反馈 #5：材料 nlib/gas/plib 框改名"其他"，输入框放大支持换行。前端把 input
改 textarea，MaterialData.options 字符串可含 \n。后端生成器必须按 \n 拆分：
- 首段仍内联 M{n} 后（无换行时输出字节不变，F-D pin 不回归）
- 其余段作为 M 卡续行（行首 5 空格缩进），否则 MCNP 会把 gas=/plib= 当新卡解析

另验证 _wrap_long_lines（80 列 & 续行）与多行 options 的交互，防止续行被二次
拆分污染；回放经解析器拍平成单空格属语义保留（点 5 接受行为）。
"""
from app.generator.inp_generator import _generate_materials, generate_inp_from_deck
from app.generator.parsers import parse_inp_text
from app.models import MaterialData, MaterialRow, DeckData, BasicSettings
from app.models import TallySettings, AdvancedSettings, SourceData, CellRow, CellData


def _mat(**kw):
    base = dict(number=1, rows=[MaterialRow(zaid="92235.06c", fraction="-0.05")])
    base.update(kw)
    return MaterialData(**base)


# ── 生成器直测：多行 options 续行格式 ─────────────────────
def test_multiline_options_continuation_format():
    mat = _mat(options="nlib=.66c\ngas=1\nplib=.21p")
    lines = _generate_materials([mat])
    assert lines == [
        "M1  nlib=.66c\n     gas=1\n     plib=.21p\n     92235.06c  -0.05"
    ], "多行 options 应内联首段 + 5 空格续行其余段"


def test_multiline_options_cont_before_nuclides():
    """options 续行必须排在核素续行之前（紧贴 M 头），保持 M 卡 options 语义。"""
    mat = _mat(options="nlib=.66c\ngas=1")
    text = "\n".join(_generate_materials([mat]))
    assert text.index("nlib=.66c") < text.index("gas=1") < text.index("92235.06c")
    # 每段 options 都带 5 空格缩进
    assert "\n     gas=1" in text
    assert "\n     92235.06c  -0.05" in text


def test_single_line_options_byte_identical_fd_pin():
    """F-D pin：options 无换行时输出必须与改动前逐字节一致。"""
    mat = _mat(options="nlib=.66c")
    lines = _generate_materials([mat])
    assert lines == ["M1  nlib=.66c\n     92235.06c  -0.05"], "无换行时字节回归"


def test_no_options_byte_identical():
    mat = _mat(options="")
    assert _generate_materials([mat]) == ["M1\n     92235.06c  -0.05"]


def test_multiline_options_crlf_normalized():
    """Windows \r\n 换行应归一化为 \n（textarea 可能回传 \r\n）。"""
    mat = _mat(options="nlib=.66c\r\ngas=1\r")
    lines = _generate_materials([mat])
    assert lines == ["M1  nlib=.66c\n     gas=1\n     92235.06c  -0.05"]
    assert "\r" not in "\n".join(lines)


def test_multiline_options_blank_lines_skipped():
    """options 中空行/纯空白段应跳过，不产生悬空续行。"""
    mat = _mat(options="nlib=.66c\n\n   \ngas=1\n\n")
    lines = _generate_materials([mat])
    assert lines == ["M1  nlib=.66c\n     gas=1\n     92235.06c  -0.05"]


# ── 全管线（generate_inp_from_deck → _wrap_long_lines）───
def _deck_with_options(options: str) -> DeckData:
    return DeckData(
        basic=BasicSettings(title="t", mode_n=True, nps="100"),
        surfaces="1  rcc  0 0 0  0 10 0  2",
        cells=[CellRow(kind="cell", cell=CellData(
            number=1, material="1", density="-1.0", surface_expr="-1"))],
        materials=[_mat(options=options)],
        sources=[SourceData(number=1, erg="14.0", pos_x="0", pos_y="0", pos_z="0")],
        tally=TallySettings(),
        adv=AdvancedSettings(source_mode="fixed"),
    )


def _material_section_lines(out: str) -> list[str]:
    """提取输出中 M1 卡起始到下一数据卡前的一行行列表。"""
    lines = out.split("\n")
    idx = next(i for i, l in enumerate(lines) if l.startswith("M1"))
    section = []
    for l in lines[idx:]:
        stripped = l.strip()
        if section and (stripped.startswith(("SDEF", "MODE", "NPS", "C  ===== Data"))):
            break
        section.append(l)
    return section


def test_full_pipeline_multiline_options_format():
    out = generate_inp_from_deck(_deck_with_options("nlib=.66c\ngas=1\nplib=.21p"))
    section = _material_section_lines(out)
    assert section[0] == "M1  nlib=.66c"
    assert "     gas=1" in section
    assert "     plib=.21p" in section
    assert "     92235.06c  -0.05" in section


def test_full_pipeline_no_newline_byte_identical():
    """全管线：options 无换行时 M 卡段与改动前一致（F-D pin 端到端）。"""
    out = generate_inp_from_deck(_deck_with_options("nlib=.66c"))
    section = _material_section_lines(out)
    assert section[0] == "M1  nlib=.66c"
    assert "     92235.06c  -0.05" in section


def test_wrap_long_lines_interaction_no_secondary_split():
    """超长 options 行触发 _wrap_long_lines & 拆分后：全部行 ≤80 列，
    且 M 卡续行保持合法（5 空格缩进或行尾 &），不产生无缩进裸行（防新卡误判）。"""
    long_opt = ("nlib=.66c  gas=1  plib=.21p  estep=10  hlib=12c  elib=4c  ") * 3
    out = generate_inp_from_deck(_deck_with_options("nlib=.66c\n" + long_opt))
    lines = out.split("\n")
    assert max(len(l) for l in lines) <= 80, "存在 >80 列行"

    # 材料卡段内每行：要么 5+ 空格缩进，要么行尾 & 续行（首行 M1 例外）
    in_mat = False
    for l in lines:
        if l.startswith("M1"):
            in_mat = True
            continue
        if in_mat:
            if l.strip().startswith(("SDEF", "MODE", "NPS")):
                break
            assert len(l) - len(l.lstrip()) >= 5 or l.rstrip().endswith("&"), \
                f"M 卡续行非法（无缩进非 & 行）: {l!r}"


def test_roundtrip_multiline_options_semantics_preserved():
    """回放：多行 options 经解析器拍平成单空格（点 5 接受），核素行保留。"""
    out = generate_inp_from_deck(_deck_with_options("nlib=.66c\ngas=1\nplib=.21p"))
    deck2, _warns = parse_inp_text(out)
    m2 = deck2.materials[0]
    assert [r.zaid for r in m2.rows] == ["92235.06c"]
    assert [r.fraction for r in m2.rows] == ["-0.05"]
    for kw in ("nlib=.66c", "gas=1", "plib=.21p"):
        assert kw in m2.options, f"回放后 options 丢失关键字 {kw}: {m2.options!r}"
