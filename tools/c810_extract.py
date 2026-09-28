#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""c810_extract — 从权威手册 C810.pdf **脚本抽取**语义锚点原文（禁止手抄）。

背景（本项目真实事故）：SDEF 的语义曾被"凭记忆转述手册"，于是同一段规则长出了三种解释
（RHP 的 ``r``）、``fdir=d2`` 静默取默认值、注释卡被当成家族终止符。本脚本把
「锚点 id → (PDF 页区间, 起始正则, 结束正则, 关键短语)」做成脚本内的**数据表**，
从 PDF 抽出原文，生成 ``docs/authority/c810-sdef.md``；任何实现里的语义都必须引用
一个**存在且原文含关键短语**的锚点（由 ``tests/unit/test_c810_anchors.py`` 机检）。

用法（workdir = 仓库根）::

    python tools/c810_extract.py            # 从 PDF 生成/刷新 docs/authority/c810-sdef.md
    python tools/c810_extract.py --check    # 只校验，md 与 PDF 不一致 ⇒ 非零退出
    python tools/c810_extract.py --dump     # 打印锚点 → (PDF 页, 印刷页, 原文首行) 速查表

约定：

* PDF 页 − 525 = 印刷页 3-x（例：PDF 591 = 印刷 3-66；页码就印在页面上，脚本会**核对**）；
* 正文**按词的几何位置**重建阅读序（甩掉页眉页脚、按行聚词、行内按 x 排），再在
  「起始正则 → 结束正则（不含）」之间切出片段：实词逐字不改，但版式（分栏/表格格）
  会被重排成线性文本，**不是**排版的影印；
* 关键短语按「词序」机检（空白折叠、排版字符归一），全部命中才肯生成；
* 幂等：同一份 PDF 重复运行产出逐字节相同；``--check`` 就地重算比对，不写文件。

只读 PDF，不修改它；纯 stdlib + PyMuPDF（``fitz``）。
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

# ────────────────────────────────────────────────────────────────────────────
# 路径与常量
# ────────────────────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = Path(r"D:\MCNP\MCNP6\C810.pdf")
OUT_PATH = _REPO_ROOT / "docs" / "authority" / "c810-sdef.md"

#: PDF 页 ↔ 印刷页 3-x 的偏移（印刷 x = PDF 页 − 525）。
PDF_TO_PRINTED_OFFSET = 525

HEADER_MARK = "本文件由 tools/c810_extract.py 从 C810.pdf 生成，勿手改"

#: 锚点表（id 已冻结，见契约 §1 / app/generator/source_spec.py::ANCHOR_IDS）。
#:
#: 每项：
#:   ``pages``   (PDF 起始页, PDF 结束页)，1-based 含两端；
#:   ``start``   起始正则（在页区间拼接后的正文里找）；
#:   ``end``     结束正则（**不含**在结果里；``None`` = 抽到页区间末尾）；
#:   ``phrases`` 关键短语元组（按 :func:`phrase_key` 的空白归一后做子串比较）。
#:
#: 划界原则：**锚点之间尽量不重叠**，且每段落在印刷页上自洽 —— 正文按「起止句」切，
#: 切不动时才把页边距的卡名标题包进来（此时页区间会往前扩一页，见 SI/SP 两条的注释）。
#: 结束正则取「下一段正文的首句」，这样跨页时即使段落被页脚/页眉分开也切不断。
ANCHORS: dict[str, dict] = {
    # ── 卡格式（第 3 章 D 节，印刷 p.3-4）────────────────────────────────
    "#C810-3-4-COMMENTS": {
        "pages": (529, 529),
        "start": r"Comment cards can be used anywhere",
        # 收在下一小节标题「1. Horizontal Input Format」上：词级重建会把小节号「1.」并进
        # 标题行，所以用「数字 + 标题」一起切（只切标题会留下一个孤零零的「1.」）。
        "end": r"\d+\.\s+Horizontal Input Format",
        "phrases": (
            "Comment cards can be used anywhere in the INP",
            "after the problem title card and before the last blank terminator card",
            "must have a C anywhere in columns 1-5 followed by at least one blank",
            "Comment cards are printed only with the input file listing",
        ),
    },
    "#C810-3-4-CONTINUATION": {
        "pages": (529, 529),
        "start": r"Blanks in the",
        "end": r"Five features incorporated in the code",
        # ⚠ 「Blanks in the」后面就折行了：整句跨行，只能靠 phrase_key 的空白归一来匹配。
        "phrases": (
            "Blanks in the first five columns indicate a continuation of the data from the last named card",
            "Data on this continuation card can be in columns 1-80",
            "Completely blank cards are",
        ),
    },
    # ── TR 变换卡（印刷 p.3-30 ~ p.3-31；SDEF TR=n 引用的变换本体）──────────
    "#C810-3-30-TR-CARD": {
        "pages": (555, 555),
        "start": r"5\. TRn Coordinate Transformation Card",
        # 收在「Use: Optional」上（卡描述的第 3 行固定字段）；Default 行在它之前，故进 span。
        "end": r"Use: Optional",
        "phrases": (
            "Form: TRn O1 O2 O3 B1 B2 B3 B4 B5 B6 B7 B8 B9 M",
            "M = 1 (the default) means that the displacement vector is the location of the"
            " origin of the auxiliary coordinate system, defined in the main system",
            # ⚠ 手册第二行以「= -1 means …」起头（M 承前省略）；− 是 U+2212，归一成 ASCII。
            "= -1 means that the displacement vector is the location of the origin of the"
            " main coordinate system, defined in the auxiliary system",
            "Default: TRn 0 0 0 1 0 0 0 1 0 0 0 1 1",
        ),
    },
    "#C810-3-31-TR-B-MATRIX": {
        "pages": (556, 556),
        "start": r"The B matrix specifies the relationship",
        # 收在下一段正文首句上：把 5 种写法与「Pattern #5 用于纯平移」一并切进来。
        "end": r"Coordinate transformations in MCNP are used to simplify",
        "phrases": (
            "Element B1 B2 B3 B4 B5 B6 B7 B8 B9",
            "Axes x,x' y,x' z,x' x,y' y,y' z,y' x,z' y,z' z,z'",
            # M 只改位移矢量的读法，不改 B 的含义 —— 本程序据此把 M 折进 translate。
            "The meanings of the Bi do not depend on M",
            "2. Two of the three vectors either way in the matrix (6 values)."
            " MCNP will create the third vector by cross product",
            "3. One vector each way in the matrix (5 values)."
            " The component in common must be less than 1."
            " MCNP will fill out the matrix by the Eulerian angles scheme",
            "4. One vector (3 values). MCNP will create the other two vectors in some arbitrary way",
            "5. None. MCNP will create the identity matrix",
        ),
    },
    # ── 源变量模型（印刷 p.3-55 ~ p.3-56）────────────────────────────────
    "#C810-3-60-CEL-PATH": {
        # 跨页：正文（路径格式 + pds level 表）在 3-60，格元抽样与"接受/拒绝"表在 3-61
        # ⇒ 页区间取 585-586，id 的主印张页按 **3-60** 冻结（与 TABLE-3-3 同口径）。
        "pages": (585, 586),
        "start": r"Source cell path for repeated structures or lattices",
        "end": r"Note that the format of the CEL Source Path is the same as for tally cards",
        "phrases": (
            "CEL must have a value that is a path, enclosed in parentheses, from level n to level 0",
            # ⚠ 路径公式 `( cn < cn - 1 < .... < c0 )` 只在**词级重建**里可见：PyMuPDF 的
            # get_text("text") 在 p585 上漏掉这一行（实测 grep 全库 0 命中），而
            # test_c810_anchors.test_phrases_come_from_the_real_pdf 是按**原始页文本**机检的
            # ⇒ 不能把它写成关键短语（写成短语会让那条机检永远红）。改用同一句里的实词。
            "where level n is not necessarily the bottom",
            "Each entry in the source path represents a geometry level",
            "ci is a cell in the universe that fills cell ci-1, or is zero,"
            " or is Dm for a distribution of cells in the repeated structure case",
            "If ci is one specific element in a lattice, it is indicated as",
            "The coordinate system for position and direction sampling (pds) is the coordinate"
            " system of the first negative or zero ci in the source path",
            "CEL Source Path Cell of pds Level pds Level",
            "Lattice cell elements that are defined using the expanded FILL card",
        ),
    },
    "#C810-3-55-VAR-FORMS": {
        "pages": (580, 580),
        "start": r"The equal signs are optional\.",
        "end": r"The above scheme translates into three levels",
        "phrases": (
            "The specification of a source variable has one of these three forms",
            "explicit value",
            "a distribution number prefixed by a D",
            "the name of another variable prefixed by an F, followed by a distribution number",
            "Var = Dn means that the value of source variable var is sampled from distribution n",
            # ′ 是 U+2032 PRIME（手册原样），不是 ASCII 撇号。
            "Var Fvar\u2032 Dn means that var is sampled from distribution n that depends on the variable var\u2032",
        ),
    },
    "#C810-3-55-SAMPLING-ORDER": {
        "pages": (580, 580),
        "start": r"MCNP samples the source variables in an order set up",
        "end": r"a message will be printed",
        "phrases": (
            "MCNP samples the source variables in an order set up according to the needs of the particular problem",
            "Each dependent variable must be sampled after the variable it depends on has been sampled",
        ),
    },
    "#C810-3-55-ONE-LEVEL": {
        "pages": (580, 580),
        "start": r"Only one level of dependence is allowed\.",
        "end": r"The above scheme translates into three levels",
        "phrases": (
            "Only one level of dependence is allowed",
            "Each distribution may be used for only one source variable",
        ),
    },
    "#C810-3-56-TABLE-3-3": {
        "pages": (580, 581),
        "start": r"Table 3\.3: Source Variables",
        # 3-56 页首重复了一次表标题（表格续页的表头），要的是 3-55 页底那次：用「表头 + 第一行
        # 数据 CEL」定位，避免 start_after 的「取最后一次」落到续页标题上（那会把前 4 行切掉）。
        "start_after": r"Table 3\.3: Source Variables[\s\S]{0,200}?CEL Cell Determined from XXX",
        # 表体在 p.3-55~3-56 跨页；p.3-56 上表体后面接着讲 WGT/EFF/PAR 必须是显式值，
        # 那句不属于表，用来收尾。
        "end": r"The specification of WGT, EFF and PAR must be only an explicit value",
        "phrases": (
            "Table 3.3: Source Variables",
            "Determined from XXX, YYY, ZZZ",
            "Zero (means cell source)",
            "Energy (MeV)",
            "14 MeV",
            "Time (shakes)",
            "Reference vector for DIR",
            "Sign of the surface normal",
            # ⚠ 表格里「含义」栏折行、而同一行的「默认值」栏只占一行：词序上会被那个默认值
            # （0）截断。这类跨栏短语按原文的词序分段写（不硬凑成一整句），否则永远匹配不上。
            "Radial distance of the position from",
            "POS or AXS",
            "Cell case: distance from POS along",
            "Reference vector for EXT and RAD",
            "Particle weight",
            "Rejection efficiency criterion for",
            "position sampling",
            ".01",
            "Particle type source will emit",
            "distribution of transformations TR=Dn",
        ),
    },
    # ── 分布家族（印刷 p.3-62 ~ p.3-64）──────────────────────────────────
    "#C810-3-63-SI-OPTIONS": {
        # 卡名清单（「2. SIn / Source Information Card」）印在 3-62 页底、SI 卡正文从它下面
        # 开始（延续到 3-63）：起点用「SIn 卡正文之前最后一次出现卡名标题」，页区间必须
        # 从 p587（3-62）起，否则卡名标题够不着。
        "pages": (587, 588),
        "start": r"SIn\s+Source Information Card",
        "start_after": r"Form: SIn",
        "end": r"Form: SPn",
        "phrases": (
            "Source Information Card",
            "distribution number (n = 1,999)",
            "how the Ii's are to be interpreted. Allowed values are",
            "omitted or H-bin boundaries for a histogram distribution",
            "L-discrete source variable values",
            "A-points where a probability density distribution is defined",
            "S-distribution numbers",
            "source variable values or distribution numbers",
        ),
    },
    "#C810-3-63-SP-OPTIONS": {
        # 同理：「3. SPn / Source Probability Card」是 3-62 页底的清单项，而 SP 卡正文（Form）
        # 在 3-63 —— 取 SP 正文之前最后一次出现的卡名标题，既不重复 SI 卡正文，也不漏卡名。
        "pages": (587, 589),
        "start": r"SPn\s+Source Probability Card",
        "start_after": r"Form: SPn",
        # 收在下一段正文（SP 第一形态的说明）之前：卡格式（Form/选项表/默认）到此为止。
        "end": r"The first form of the SP card",
        "phrases": (
            "Source Probability Card",
            "or: SPn f a b",
            "how the Pi are to be interpreted. Allowed values are",
            "omitted-same as D for an H or L distribution",
            "density for an A distribution on SI card",
            "D-bin probabilities for an H or L distribution on SI card",
            "This is the default.",
            "C-cumulative bin probabilities for an H or L distribution",
            "V-for cell distributions only. Probability is proportional to cell volume",
            "designator (negative number) for a built-in function",
        ),
    },
    "#C810-3-63-H-FIRST-ZERO": {
        # SP 第一形态（H/A/L 三种选项）的正文在 p.3-63 底~p.3-64 顶整段连排，从「首项必须为 0」
        # 的 H 规则起步、跨页到 A 型密度与 L 离散值；H/A/L 之间没有可切的段界，故整段收在本条：
        #   * H：SP 首项必须为 0（本 anchor 的主检项）；
        #   * A：SI 给密度定义点 + SP 给**概率密度**（SP-OPTIONS 里点名、契约 §1.2 要求的那条语义）；
        #   * L：SI 是离散值（与 SI-OPTIONS 的 L 说明呼应）。
        "pages": (588, 589),
        "start": r"The first form of the SP card",
        "end": r"The S option allows sampling among distributions",
        "phrases": (
            "The first form of the SP card, where the first entry is positive or nonnumeric",
            "the numerical entries on the SI card are bin boundaries and must be monotonically increasing",
            "The first numerical entry on the SP card must be zero",
            "the following entries are bin probabilities or cumulative bin probabilities",
            "The probabilities need not be normalized",
            "When the A option is used, the entries on the SI card are values of the source variable",
            "The numerical entries on the SP card are values of the probability density corresponding",
            "the probability density is linearly interpolated between the specified values",
            "When the L option is used, the numerical entries on the SI card are discrete values",
        ),
    },
    "#C810-3-64-BUILTIN-FORM": {
        "pages": (588, 589),
        "start": r"The second form of the SP card, where the first entry is negative",
        "end": r"Built-in functions can be used only for scalar variables",
        "phrases": (
            "The second form of the SP card, where the first entry is negative",
            "indicates that a built-in analytic function is to be used to generate a continuous probability density function",
        ),
    },
    "#C810-3-64-SB-RULES": {
        "pages": (588, 589),
        "start": r"The SB card is used to provide a probability distribution for sampling",
        "end": r"The second form of the SP card",
        "phrases": (
            "The weight of each source particle is adjusted to compensate for the bias",
            "All rules that apply to the first form of the SP card apply to the SB card",
        ),
    },
    "#C810-3-64-SI-S": {
        "pages": (588, 589),
        "start": r"The S option allows sampling among distributions",
        "end": r"The V option on the SP card",
        "phrases": (
            "The S option allows sampling among distributions, one of which is chosen for further sampling",
            "Each distribution number on the SI card can be prefixed with a D, or the D can be omitted",
            "If a distribution number is zero, the default value for the variable is used",
            "a distribution cannot be used for more than one source variable",
        ),
    },
    "#C810-3-64-SP-V": {
        "pages": (588, 589),
        "start": r"The V option on the SP card is a special case used only when the source variable is CEL",
        "end": r"The SB card is used to provide a probability distribution for sampling",
        "phrases": (
            "The V option on the SP card is a special case used only when the source variable is CEL",
            "when the cell volume is a factor in the probability of particle emission",
            "you have a FATAL error",
        ),
    },
    # ── 内置函数与依赖（印刷 p.3-65 ~ p.3-67）────────────────────────────
    "#C810-3-65-TABLE-3-4": {
        # 表 3.4 印在 3-65：表头 + 六行「变量/函数号/说明」并排版；紧接着 3-65 页底到 3-66
        # 是各函数的正文定义（f=-2..-7）与参数默认（f=-21/-31/-41）。这些都属「表 3.4 的
        # 正文」，一并收在本锚点里；3-66 的 BUILTIN-VARS 从下一句起另开一条。
        "pages": (590, 591),
        "start": r"Table 3\.4: Built-In Functions",
        "end": r"The built-in functions can be used only for the variables shown in Table 3\.3",
        "phrases": (
            "Table 3.4: Built-In Functions for Source Probability and Bias Specification",
            "Maxwell fission energy spectrum",
            "Watt fission energy spectrum",
            "Gaussian fusion energy spectrum",
            "Evaporation energy spectrum",
            "Muir velocity Gaussian fusion energy spectrum",
            "Spare energy spectrum",
            "Power law p(x) = c|x|a",
            "Exponential: p(µ) = ceaµ",
            "Gaussian distribution of time t or",
            "Default: a = 1.2895 MeV",
            "a = 0.965 MeV, b = 2.29 MeV",
            "a = -0.01 MeV, b = -1 (DT fusion at 10 keV)",
            "For DIR, a = 1",
            "For RAD, a = 2, unless AXS is defined or JSU",
            "For EXT, a = 0",
            "f = -31 Exponential",
            "Default: a = 0.",
        ),
    },
    "#C810-3-66-BUILTIN-VARS": {
        "pages": (591, 591),
        "start": r"The built-in functions can be used only for the variables shown in Table 3\.3",
        "end": r"A built-in function on an SP card can be biased or truncated",
        "phrases": (
            "The built-in functions can be used only for the variables shown in Table 3.3",
            "only -21 and -31 can be used on SB cards",
            "only that same function can be used on the corresponding SP card",
            "The combination of a regular table on the SI and SP cards with a function on the SB card is not allowed",
        ),
    },
    "#C810-3-66-TRUNC-WEIGHT": {
        "pages": (591, 591),
        # 「偏倚/截断」整段（含 300 组近似）都是这条权重补偿规则的上下文，一并收进来。
        "start": r"A built-in function on an SP card can be biased or truncated",
        "end": r"Special defaults are available for distributions that use built-in functions",
        "phrases": (
            "The biasing affects only the probabilities of the bins, not the shape of the function within each bin",
            "the product of n and the number of bins is as large as possible but not over 300",
            "Unless the function is -21 or -31, the weight of the source particle is adjusted to compensate for truncation of the function by the entries on the SI card",
        ),
    },
    "#C810-3-66-SPECIAL-DEFAULTS": {
        "pages": (591, 591),
        "start": r"Special defaults are available for distributions that use built-in functions\.",
        # 原文规则 1~5 之后紧接着 DS 卡的「5. DSn」（原著这里编号重了一次）；连编号一起切掉，
        # 只切 DSn 会在段落尾巴留下一个孤零零的「5.」。
        "end": r"\d+\.\s+DSn\b",
        "phrases": (
            "Special defaults are available for distributions that use built-in functions",
            "If SB f is present and SP f is not, an SP f with default input parameters",
            "If only an SI card is present for RAD or EXT, an SP -21 with default input parameters",
            "If only SP -21 or SP -31 is present for DIR or EXT, an SI 0 1, for -21, or SI -1 1",
            "If SI x and SP -21 are present for RAD, the SI is treated as if it were SI 0 x",
            "If SI x and SP -21 or SP -31 are present for EXT, the SI is treated as if it were SI -x x",
        ),
    },
    "#C810-3-66-DS-CARD": {
        "pages": (591, 592),
        "start": r"Dependent Source Distribution Card",
        "end": r"No SP or SB card is used",
        "phrases": (
            "Dependent Source Distribution Card",
            "how the Ji are to be interpreted",
            "blank or H-source variable values in a continuous distribution",
            "L-discrete source variable values",
            "S-distribution numbers",
            "values of the dependent variable follow values of the independent variable",
            "distribution numbers follow values of the independent variable",
            "monotonically increasing set of values of the independent variable",
            "distribution numbers for the dependent variable",
        ),
    },
}

#: 锚点表里唯一允许的 id 形状（TAG 半段已冻结）。
ANCHOR_ID_RE = re.compile(r"^#C810-\d+-\d+-[A-Z0-9-]+$")


# ────────────────────────────────────────────────────────────────────────────
# 文本抽取与归一化
# ────────────────────────────────────────────────────────────────────────────

# PDF 抽取常见的排版字符 → ASCII（**只**处理抽取产物，不改手册用词）。
_CHAR_FIXES = {
    "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl",
    "\ufb03": "ffi", "\ufb04": "ffl", "\ufb05": "st", "\ufb06": "st",
    "\u00ad": "",            # 软连字符
    "\u2212": "-",           # 数学减号 U+2212（手册里印刷成 −）
    "\u2010": "-", "\u2011": "-", "\u2012": "-",
    "\u2013": "-", "\u2014": "-", "\u2015": "-",
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u00a0": " ", "\u2007": " ", "\u202f": " ", "\u2028": "\n", "\u2029": "\n",
    "\u200b": "", "\ufeff": "",
}

_LIGATURE_RE = re.compile("[\ufb00-\ufb06]")
_WS_COLLAPSE_RE = re.compile(r"[ \t\f\v]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    """PDF 抽取文本 → 统一形态（连字、软连字符、特殊空格、空白折叠）。

    归一化是**逐字抽取**的必要配套：同一份手册在不同 PyMuPDF 版本/不同字体子集下，
    ``ﬁ`` 可能被抽成 ``fi`` 或保留连字、``−`` 可能是 U+2212 或 ASCII，软连字符时有时无。
    归一化只碰**控制/排版字符**与空白，不动任何实词，因此「原文逐字」仍然成立。
    """
    return _normalize_soft(_normalize_hard(text))


def _normalize_hard(text: str) -> str:
    """硬归一：空白折叠（改行结构）—— 匹配前用得到。"""
    if not text:
        return ""
    lines = [_WS_COLLAPSE_RE.sub(" ", ln).strip() for ln in text.split("\n")]
    return _BLANK_LINES_RE.sub("\n\n", "\n".join(lines)).strip()


def _normalize_soft(text: str) -> str:
    """软归一：只碰排版字符（不动空白结构）—— 页号核对前用得到。"""
    if not text:
        return ""
    # 控制字符（除 \n \t）一律去掉：PDF 里混进的 \x00 之类会让 md 变成二进制噪声。
    text = "".join(ch for ch in text if ch >= " " or ch in "\n\t")
    text = unicodedata.normalize("NFC", text)
    for src, dst in _CHAR_FIXES.items():
        text = text.replace(src, dst)
    return _LIGATURE_RE.sub(lambda m: _CHAR_FIXES.get(m.group(0), m.group(0)), text)


# 页眉页脚的高度门限（pt）：页脚印页码「3-66」，页眉印章名；两者都不属于正文。
_FOOTER_TOP_PT = 745.0
_HEADER_BOTTOM_PT = 60.0

# 词级重建的两个门限：同一行上下两条文字的中心距超过它就算两行；同一行内两个词的空隙
# 小于它就用空格连起来（同一句话被 PDF 切成两段），大间隙（表格两格之间 250pt 量级）保持断开。
_LINE_TOL_PT = 4.0
_JOIN_GAP_PT = 12.0


def _reading_lines(page) -> list[str]:
    """一页正文 → **阅读序行**列表（页眉页脚剔除）。

    为什么不用 ``page.get_text()``：它的输出顺序随页而异 —— 有的页把页脚印页码排在正文**之前**，
    有的页后半段先出（实测：SI 选项段被截成 30 字符）。这里改成按**词**重建：

    1. 丢掉页眉页脚（印章行/页码行不属于正文）；
    2. 词按 ``y`` 聚成行（同一视觉行的各栏/各表格格都落在同一行里）；
    3. 行内按 ``x`` 排序，空隙小的相邻词用空格相连 —— 表格一行里「变量 / 函数号 / 说明」三格
       因此各成一串、彼此不粘（block 级的 ``..``+``..`` 拼法会把
       ``Maxwell fission`` 和 ``energy spectrum`` 拆到两行去）。

    正文一个字不改：只是把「流的顺序」换成「纸面上的顺序」，让跨页/跨栏的锚点正则有唯一的
    左右关系可依。
    """
    words = []
    for word in page.get_text("words"):
        x0, y0, _x1, y1, text = word[0], word[1], word[2], word[3], word[4]
        if y1 <= _HEADER_BOTTOM_PT or y0 >= _FOOTER_TOP_PT:
            continue
        text = (text or "").strip()
        if not text:
            continue
        words.append((y0, y1, x0, text))
    if not words:
        return []

    tokens = []
    for y0, y1, x0, text in words:
        center = (y0 + y1) / 2.0
        for token in tokens:
            if abs(token["center"] - center) <= _LINE_TOL_PT:
                token["items"].append((x0, text))
                break
        else:
            tokens.append({"center": center, "items": [(x0, text)]})
    tokens.sort(key=lambda token: token["center"])

    rendered: list[str] = []
    for token in tokens:
        parts: list[str] = []
        prev_x1 = None
        for x0, text in sorted(token["items"]):
            if parts and prev_x1 is not None and x0 - prev_x1 <= _JOIN_GAP_PT:
                parts[-1] = f"{parts[-1]} {text}"
            else:
                parts.append(text)
            prev_x1 = x0 + len(text) * _AVG_CHAR_PT
        rendered.append(" ".join(parts))
    return rendered


# 字符均宽估计（pt）：把词宽折算成 x 终点，用于判断相邻词是同一句还是不同格。
_AVG_CHAR_PT = 5.4


def read_pages(doc, first: int, last: int) -> str:
    """读 PDF 页 ``first..last``（1-based，含两端），页间用 ``\\n\\n`` 拼接。"""
    chunks = [
        normalize_text("\n".join(_reading_lines(doc[i - 1])))
        for i in range(first, last + 1)
    ]
    return "\n\n".join(chunks)


def extract_span(
    text: str,
    start_re: str,
    end_re: str | None,
    anchor_id: str,
    anchor_re: str | None = None,
) -> str:
    """在（已归一化的）页区间文本里，按「起始正则 → 结束正则（不含）」切出原文。

    ``anchor_re``（可选）：起始正则若在正文前后各命中一次（典型是「卡名标题」在上一页底的
    卡名清单里出现一次、又在卡正文前出现一次），用它定位卡正文，再取**它之前最后一次**命中
    的起始正则 —— 这样卡名标题跟着正文走，而不会把上一张卡的正文圈进来。
    """
    anchor_m = re.search(anchor_re, text, re.MULTILINE) if anchor_re else None
    if anchor_re is not None and anchor_m is None:
        raise LookupError(
            f"锚点 {anchor_id} 的定位正则没命中：{anchor_re!r}"
            "（PDF 版本不同或页号漂移；请核对 PDF_PATH 与 ANCHORS 里的页区间）")
    # 定位正则只管「正文从哪儿起」：起点正则可命中它的**起点或其内部**（卡名标题就在定位
    # 正则的头部时，起点只能落在 anchor_m.start() 上，所以上限取 anchor_m.end()）。
    limit = anchor_m.end() if anchor_m else len(text)
    start_m = None
    for candidate in re.finditer(start_re, text[:limit], re.MULTILINE):
        start_m = candidate
    if start_m is None:
        raise LookupError(
            f"锚点 {anchor_id} 的起始正则没命中：{start_re!r}"
            "（PDF 版本不同或页号漂移；请核对 PDF_PATH 与 ANCHORS 里的页区间）")
    begin = start_m.start()
    if end_re is None:
        return text[begin:].strip()
    end_m = re.search(end_re, text[start_m.end():], re.MULTILINE)
    if end_m is None:
        raise LookupError(
            f"锚点 {anchor_id} 的结束正则没命中：{end_re!r}（起始正则命中于 offset {begin}）")
    return text[begin:start_m.end() + end_m.start()].strip()


def first_line(span: str) -> str:
    """原文首行（速查表用）。"""
    for ln in span.split("\n"):
        if ln.strip():
            return ln.strip()
    return ""


# ────────────────────────────────────────────────────────────────────────────
# 关键短语机检（脚本自带，生成时即校验一遍；测试文件里再独立实现一遍）
# ────────────────────────────────────────────────────────────────────────────

_WS_RUN_RE = re.compile(r"\s+")


def phrase_key(text: str) -> str:
    """关键短语的**比较键**：小写 + 空白折叠成单空格。

    PDF 原文按版面折行，短语常跨行（``\\n`` 处就是断行）；比较前把连续空白压成一个空格，
    短语就能按「词序」匹配，而不是按「版面折行位置」匹配。连字符**保留**：
    ``columns 1−5`` 里的 ``−`` 已由 :func:`normalize_text` 归成 ASCII ``-``，
    是手册的实义标点，抹掉会让 ``1-5`` 与 ``15`` 混同。
    """
    return _WS_RUN_RE.sub(" ", str(text or "")).strip().lower()


def missing_phrases(span: str, phrases) -> list[str]:
    """返回 ``span`` 里**找不到**的关键短语。

    比较口径：短语按**词序**匹配 —— 短语里的空白换成 ``\\s+``，其它字符原样（小写化）。
    这样「按版面折行」不会造成假阴性：表格里 ``distance from POS along`` 与 ``AXS`` 在版面上
    是两行（一格折行），在词序上仍是同一句。连字符不抹：``columns 1-5`` 的 ``-`` 是实义标点。
    """
    return [p for p in phrases if phrase_pattern(p).search(span) is None]


def phrase_pattern(phrase: str) -> re.Pattern:
    """关键短语 → 容空白变体的正则（词序匹配）。"""
    tokens = [re.escape(tok) for tok in str(phrase or "").split()]
    return re.compile(r"\s+".join(tokens), re.IGNORECASE)


def validate_phrases(anchor_id: str, span: str, phrases) -> None:
    """关键短语是锚点的**存在意义**：抽不到就立刻炸，不允许生成一份软锚点表。"""
    missing = missing_phrases(span, phrases)
    if missing:
        detail = "; ".join(repr(p) for p in missing)
        raise LookupError(
            f"锚点 {anchor_id} 抽出的原文里找不到关键短语：{detail}"
            "（页区间/正则漂了，或短语抄错了手册用词）")


# ────────────────────────────────────────────────────────────────────────────
# 页号核对（PDF 页 − 525 = 印刷 3-x，页码就印在页面上）
# ────────────────────────────────────────────────────────────────────────────

def printed_label(pdf_page: int) -> str:
    """PDF 页 → 印刷页标签（``3-66``）。"""
    return f"3-{pdf_page - PDF_TO_PRINTED_OFFSET}"


def verify_page_number(doc, pdf_page: int) -> None:
    """核对「PDF 页 − 525 = 印刷 3-x」：印刷页码必须真的印在该页上。

    页码印在页脚（有的页在页首出现，取决于 PDF 流序），所以这里在**整页**文本里找，
    而不是在重建过阅读序的正文里找 —— 正文已经剔掉页眉页脚。
    """
    label = printed_label(pdf_page)
    page_text = normalize_text(doc[pdf_page - 1].get_text())
    if not re.search(rf"(?m)^{re.escape(label)}\s*$", page_text):
        raise LookupError(
            f"PDF 第 {pdf_page} 页上没有印着页码 {label}（偏移 {PDF_TO_PRINTED_OFFSET} 不成立）")


def pdf_page_label(first: int, last: int) -> str:
    """页区间 → 展示用标签。"""
    if first == last:
        return f"p{first}"
    return f"p{first}-{last}"


def printed_page_label(first: int, last: int) -> str:
    """页区间 → 印刷页标签。"""
    if first == last:
        return printed_label(first)
    return f"{printed_label(first)} ~ {printed_label(last)}"


# ────────────────────────────────────────────────────────────────────────────
# 生成 / 校验
# ────────────────────────────────────────────────────────────────────────────

def build_report(doc) -> tuple[str, list[dict]]:
    """从 PDF 生成 md 全文 + 锚点元数据表（纯函数式：不写文件）。"""
    blocks: list[str] = []
    meta: list[dict] = []

    blocks.append(f"# C810 语义锚点表（SDEF / 分布家族）\n")
    blocks.append(
        f"> **{HEADER_MARK}。**\n"
        f">\n"
        f"> 权威手册：`{PDF_PATH}`（PDF 页 − {PDF_TO_PRINTED_OFFSET} = 印刷页 3-x，页码由脚本逐页核对）。\n"
        f"> 原文由 `tools/c810_extract.py` 按「锚点 id → (PDF 页, 起始正则, 结束正则, 关键短语)」\n"
        f"> 表**脚本抽取**（不手抄）；原文里的连字（`ﬁ`）、软连字符、`−`(U+2212) 等排版字符\n"
        f"> 会被归一成 ASCII，实词逐字未改。\n"
        f">\n"
        f"> 机检：`tests/unit/test_c810_anchors.py` 断言每个锚点在原文里**确实包含**其关键短语，\n"
        f"> 且 `app/generator/source_spec.py` 引用的每个 `#C810-…` id 都在本表里。\n"
    )

    for anchor_id, spec in ANCHORS.items():
        first, last = spec["pages"]
        verify_page_number(doc, first)
        verify_page_number(doc, last)
        span = extract_span(
            read_pages(doc, first, last), spec["start"], spec.get("end"), anchor_id,
            spec.get("start_after"))
        validate_phrases(anchor_id, span, spec["phrases"])
        blocks.append(f"\n## {anchor_id}\n")
        blocks.append(
            f"来源：C810.pdf PDF {pdf_page_label(first, last)} = 印刷 {printed_page_label(first, last)}\n")
        blocks.append("原文：\n")
        blocks.append("```text\n" + span + "\n```\n")
        blocks.append("关键短语：\n")
        for phrase in spec["phrases"]:
            blocks.append(f"- `{phrase}`\n")
        meta.append({
            "id": anchor_id,
            "pdf_page": pdf_page_label(first, last),
            "printed": printed_page_label(first, last),
            "first_line": first_line(span),
            "span": span,
            "phrases": list(spec["phrases"]),
        })

    return "\n".join(blocks).rstrip("\n") + "\n", meta


def load_pdf():
    """打开 C810.pdf（只读）。签名的 ``fitz`` / 缺文件都给出可读错误。"""
    try:
        import fitz  # noqa: PLC0415 — 只在真正要读 PDF 时 import
    except ImportError as exc:  # pragma: no cover - 环境问题
        raise SystemExit(f"需要 PyMuPDF（import fitz）：{exc}") from exc
    if not PDF_PATH.exists():
        raise SystemExit(f"找不到权威手册：{PDF_PATH}")
    return fitz.open(str(PDF_PATH))


def cmd_generate() -> int:
    """生成/刷新 md（幂等）。"""
    doc = load_pdf()
    content, meta = build_report(doc)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(content, encoding="utf-8", newline="\n")
    print(f"[c810_extract] 已生成 {OUT_PATH}：{len(meta)} 个锚点，{len(content)} 字符")
    for item in meta:
        print(f"  {item['id']:<32} {item['pdf_page']:<10} 印刷 {item['printed']:<14} {item['first_line'][:60]}")
    return 0


def cmd_check() -> int:
    """只校验：已生成的 md 与从 PDF 现算的内容是否逐字节一致。"""
    doc = load_pdf()
    content, _meta = build_report(doc)
    if not OUT_PATH.exists():
        print(f"[c810_extract] CHECK FAIL：{OUT_PATH} 不存在（先跑 python tools/c810_extract.py）")
        return 1
    actual = OUT_PATH.read_text(encoding="utf-8")
    if actual == content:
        print(f"[c810_extract] CHECK OK：{OUT_PATH} 与 C810.pdf 一致（{len(content)} 字符）")
        return 0
    print(f"[c810_extract] CHECK FAIL：{OUT_PATH} 与 C810.pdf 不一致")
    for idx, (a, b) in enumerate(zip(actual.split("\n"), content.split("\n")), start=1):
        if a != b:
            print(f"  首个差异在第 {idx} 行：")
            print(f"    md : {a[:160]!r}")
            print(f"    pdf: {b[:160]!r}")
            break
    else:
        print(f"  差异是长度：md {len(actual)} 字符 / pdf {len(content)} 字符")
    return 1


def cmd_dump() -> int:
    """打印锚点 → (PDF 页, 印刷页, 原文首行)，便于人工复核页号。"""
    doc = load_pdf()
    _content, meta = build_report(doc)
    print(f"{'锚点 id':<32} {'PDF 页':<10} {'印刷页':<16} 原文首行")
    for item in meta:
        print(f"{item['id']:<32} {item['pdf_page']:<10} {item['printed']:<16} {item['first_line'][:70]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="从 C810.pdf 脚本抽取 SDEF/分布家族语义锚点原文，生成 docs/authority/c810-sdef.md")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="只校验 md 与 PDF 是否一致（不一致非零退出）")
    group.add_argument("--dump", action="store_true", help="打印锚点页号/首行速查表，不写文件")
    args = parser.parse_args(argv)

    # 锚点表自检：id 形状 + 短语非空（改表时立刻炸，而不是等到测试阶段）
    for anchor_id, spec in ANCHORS.items():
        if not ANCHOR_ID_RE.match(anchor_id):
            raise SystemExit(f"锚点 id 形状非法：{anchor_id!r}")
        if not spec["phrases"]:
            raise SystemExit(f"锚点 {anchor_id} 没有关键短语（机检就失去意义）")
        if spec["pages"][0] > spec["pages"][1]:
            raise SystemExit(f"锚点 {anchor_id} 的页区间反了：{spec['pages']!r}")

    if args.check:
        return cmd_check()
    if args.dump:
        return cmd_dump()
    return cmd_generate()


if __name__ == "__main__":
    sys.exit(main())
