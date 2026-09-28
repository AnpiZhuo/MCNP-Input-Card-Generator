"""source_spec — 源抽样**模型层**（契约 `docs/contracts/source-sampling-model.md` §1/§2 的落地）。

本模块只放「MCNP 源变量长什么样」的**声明式事实**，不含任何抽样逻辑：

* ``VarSpec`` / ``VAR_SPEC``：C810 **Table 3.3**（印刷页 p.3-56，含 p.3-55/3-57 的续注）逐行镜像
  —— 每个源变量的默认值、允许的内置函数（Table 3.4，p.3-65~3-66）、可作为它依赖父的变量候选
  （p.3-55）、它在位置语义里扮演的角色。
* ``parse_var_ref``：C810 p.3-55 的**三种赋值形态**（显式值 / ``Dn`` / ``Fvar' Dn``）唯一解析入口。
* ``normalize_sdef_fields``：把解析侧可能留下的 ``fdir=d2`` / ``fdir d2`` / ``FDIR=D2``
  一律归一成 ``FDIR D2``（解析层与抽样层共用的同一份语法知识）。

**为什么要有这一层**（契约开头记的教训）：同一个语义原先散在
``source_sampler._erg`` / ``_direction`` / ``_radial_value`` / ``_axial_value`` /
``_default_power_law`` 五处，解析层还有三套独立 tokenizer，于是新写法只在其中一路被支持
（``fdir=d2`` 只在 ERG、``sp3 d -21 1`` 只在 SP），且认不出时**静默兜底**
（``_num(v, 14.0)``）⇒ 缺陷长得像「跑得对」。把形态判定与默认值收进一张表后，
引擎层只做「查表 + 报错」，不允许再各写各的默认值（契约 §4）。

**语义来源必须可机检**（用户 2026-09-20 拍板）：``VarSpec`` 的每个语义字段（尤其 ``default``）
都带 ``anchor``，取值必须落在 ``ANCHOR_IDS`` 里；权威表正文在 `docs/authority/c810-sdef.md`。
找不到手册出处的值**不写数值**，写 ``anchor=None`` + ``notes`` 记「未决」，由人工定案。

约束（有意为之）：

  * 纯 stdlib（``re`` / ``dataclasses`` / ``typing``），模块顶层保持轻量；
  * **不** import ``gui.backend.api_server``、**不** import ``pymcnp``、**不** import numpy；
  * ``SourceSamplingError`` 从分布子系统复用，不另立异常类型（契约 §4 的报错口径）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .distributions import SourceSamplingError

__all__ = [
    "VarSpec",
    "VAR_SPEC",
    "ANCHOR_IDS",
    "SourceSamplingError",
    "parse_var_ref",
    "normalize_sdef_fields",
    "var_field_key",
    "var_for_field_key",
    "parent_field_key",
    "parent_name_for_field_key",
    "builtins_for",
    "spec_for",
    "DEP_PARENT_NAMES",
]

# C810 分布号范围（SIn/SPn/SBn/DSn/SCn 卡原文：n = distribution number (n = 1,999)，p.3-63）；
# 同时也对齐 `DistributionSampler` 的既有拒收口径。
_MIN_DID = 1
_MAX_DID = 999

# 数值字面量：普通浮点（`.5` ≡ `0.5`）+ MCNP 的**隐含指数**速记 `1-3` ≡ `1e-3`
# （MCNP 浮点项允许用符号代替 E；源变量值里 `1-3` 这类写法在旧卡里真实存在，不认就会
# 把合法值判成非法）。单值上下文不存在「额外 digit = 加号」的歧义 —— 整串值就是一个数。
_NUM_TOKEN_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+|[+-]\d+)?$")


# ────────────────────────────────────────────────────────────────────────────
# 权威锚点表：每个语义/默认值都必须指回 C810 的**可机检**出处
# ────────────────────────────────────────────────────────────────────────────
#
# 硬要求（用户拍板 2026-09-20）：语义来源必须可机检，禁止「凭记忆的转述」。
# 权威表正文由 `docs/authority/c810-sdef.md` 承载（另一子任务生成）。
# ⚠ 这里内联一份 id 集合（而不是运行时去读那个 md）有两点理由：
#   ① 模块顶层保持纯 stdlib、不碰文件系统、不引入「文档缺失」这一失败模式；
#   ② 单测断言「用到的每个 anchor 都在 ANCHOR_IDS 里」时，两边**同时**改动才会绿，
#      避免出现「文档缺行 ⇒ 校验自动放行」的假绿。
# 页号已按 `D:\AItool\.tmp\c810_dump` 的 dump 逐条核对（PDF 页 − 525 ≈ 印刷页）。
ANCHOR_IDS: frozenset[str] = frozenset({
    # 卡格式（第 3 章开头，印刷页 3-4）
    "#C810-3-4-COMMENTS",           # 注释卡可出现在 INP 任意位置
    "#C810-3-4-CONTINUATION",       # 列 1-5 为空 = 续行
    # TR 变换卡（SDEF TR=n 引用的变换本体；印刷页 3-30 ~ 3-31）
    "#C810-3-30-TR-CARD",           # TRn 形式；M=1/−1 决定位移矢量是「辅系原点在主系」还是反向
    "#C810-3-31-TR-B-MATRIX",       # B 矩阵轴对表 + 5 种可接受写法（6 值由叉积补全等）
    # 重复结构里的 CEL 路径（SDEF CEL 的层级写法；印刷页 3-60 ~ 3-61，见 §4.2 已知差异）
    "#C810-3-60-CEL-PATH",          # CEL = ( cn < … < c0 ) 路径；pds level 与格元指标
    # SDEF 源变量模型（p.3-55 ~ p.3-56）
    "#C810-3-55-VAR-FORMS",         # 三种形态：显式值 / Dn / Fvar' Dn
    "#C810-3-55-SAMPLING-ORDER",    # 依赖变量必须在父变量之后抽样
    "#C810-3-55-ONE-LEVEL",         # 只允许一级依赖；一个分布只能服务一个变量
    "#C810-3-56-TABLE-3-3",         # 源变量与默认值表
    # 分布家族（p.3-63 ~ p.3-66）
    "#C810-3-63-SI-OPTIONS",        # SI：空/H、L、A、S
    "#C810-3-63-SP-OPTIONS",        # SP：空=D、D、C、V；A 型 SI 时 SP 给密度
    "#C810-3-63-H-FIRST-ZERO",      # H 选项 SP 首项必须为 0
    "#C810-3-64-BUILTIN-FORM",      # SP 第二形态：首项为负 = 内置函数
    "#C810-3-64-SB-RULES",          # SB 同 SP 第一形态规则 + 权重补偿
    "#C810-3-64-SI-S",              # SI S：分布号可带 D；0 = 该变量默认值
    "#C810-3-64-SP-V",              # SP V：仅 CEL，按栅元体积
    "#C810-3-65-TABLE-3-4",         # 内置函数清单、参数与默认参数
    "#C810-3-66-BUILTIN-VARS",      # 内置函数只能用于 Table 3.4 指定的变量
    "#C810-3-66-TRUNC-WEIGHT",      # SI 截断的权重补偿；−21/−31 豁免
    "#C810-3-66-SPECIAL-DEFAULTS",  # 特殊默认 1–5
    "#C810-3-66-DS-CARD",           # DS 卡 H/L/S/T/Q 形态
})

#: Table 3.3 那一行的锚点（22 个源变量里 20 个的默认值都在它名下）。
_ANCHOR_TABLE_3_3 = "#C810-3-56-TABLE-3-3"
#: Table 3.4（内置函数清单与默认参数）。
_ANCHOR_TABLE_3_4 = "#C810-3-65-TABLE-3-4"
#: 内置函数与变量的配对规则（p.3-66 正文）。
_ANCHOR_BUILTIN_VARS = "#C810-3-66-BUILTIN-VARS"


@dataclass(frozen=True)
class VarSpec:
    """一个源变量的**声明**（契约 §2 的 ``VarSpec``）。

    字段含义：

    ``name``
        C810 变量名（大写，如 ``"ERG"``）；SDEF 字段键里的变量名就是它的小写形态。
    ``default``
        默认值。标量变量是 ``float`` / ``str``；**位置组合语义**的变量用 ``None`` 明确表示
        「Table 3.3 里没有单一数值默认」（如 ``POS`` = 原点三元组、``VEC`` = 面法线、
        ``CEL`` = 由位置定），调用方**必须**按位置层规则处理，而不是当 0 用 ——
        「取默认值」式静默降级是契约 §4 明令禁止的。
    ``builtins``
        允许作用在该变量上的内置函数（Table 3.4 配对表）；不在表里的函数用上来就是语义错误。
    ``parents``
        它能作为谁的依赖父（``Fvar' Dn`` 的 var' 候选）；空元组 = 不能作父。
    ``position_role``
        位置语义中的角色：``point``（参考点）/ ``axis``（参考轴或坐标轴）/ ``scalar``（其它）。
    ``field_keys``
        该变量在 SDEF 字段字典里的键（顺序 = 三元组分量顺序）；``field_keys[0]`` 是「主键」。
    ``value_type``
        ``"int"`` / ``"float"`` / ``"str"``，给上层做类型提示（本模块不做转换）。
    ``source_page``
        C810 页码出处（人读；逐条标页，便于回查手册）。
    ``anchor``
        **机检**出处：``ANCHOR_IDS`` 里的锚点 id（``#C810-<印刷页>-<TAG>``）。
        ``default`` / ``builtins`` / ``parents`` 这些语义值都必须能指回一个 anchor；
        在 C810 原文里找不到出处时**不写数值**，写 ``anchor=None`` + ``notes`` 记「未决」
        （单测会把 ``anchor is None`` 的条目挑出来，交人工对锚点表定案）。
    ``notes``
        手册原文里必须一起看的限定条件（如「必须是显式值，不允许分布」）。
    """

    name: str
    default: float | str | None
    builtins: tuple[str, ...] = ()
    parents: tuple[str, ...] = ()
    position_role: str = "scalar"
    field_keys: tuple[str, ...] = ()
    value_type: str = "float"
    source_page: str = "C810 Table 3.3, p.3-55~3-57"
    anchor: str | None = None
    notes: str = ""


# ────────────────────────────────────────────────────────────────────────────
# Table 3.3 镜像（C810 p.3-55 ~ p.3-57；逐条标页）
# ────────────────────────────────────────────────────────────────────────────
#
# 表 3.3 的列次序：CEL SUR ERG TME →（p.3-56 续）DIR VEC NRM POS RAD EXT AXS X Y Z
# CCC ARA WGT EFF PAR TR。本表按该次序排列（PAR/TR 的说明跨到 p.3-56 右列与表尾），
# 每条的 default 取表里那一行 Default 列的原文。
#
# p.3-55 表头原文：「The default is a 14-MeV isotropic point source at position 0,0,0
# at time 0 with weight 1 (all defaults).」—— 即「表 3.3 全部默认值同时生效」的整源默认。

VAR_SPEC: dict[str, VarSpec] = {
    # p.3-55：「CEL / Cell / Determined from XXX, YYY, ZZZ and possibly UUU, VVV, WWW」
    # ⇒ CEL 没有字面默认值：由位置（乃至方向）反推。位置层负责，模型层只标 None。
    "CEL": VarSpec(
        "CEL", None, (), ("POS", "X", "Y", "Z", "ERG", "TME", "WGT"),
        "position_selector", ("sdef_cel",), "str",
        "C810 Table 3.3, p.3-55", _ANCHOR_TABLE_3_3,
        "CEL 的默认值是「由位置定」，不是某个数；另 p.3-60 规定重复结构里 CEL 是带括号的"
        "层级路径 `( cn < … < c0 )`（可含 0/Dm/负号与格元指标 `ci[j1 j2 j3]`，见锚点 "
        "#C810-3-60-CEL-PATH）—— 本程序的源演示几何层只有平铺栅元、没有 universe/FILL/LAT "
        "层级，故该写法在抽样前就被明确拒绝（不静默当单栅元用），见契约 §4.2 已知差异。",
    ),
    # p.3-55：「SUR / Surface / Zero (means cell source)」；p.3-57：「The value of the
    # variable SUR is nonzero for a distribution on a surface」。
    "SUR": VarSpec(
        "SUR", 0.0, (), ("POS", "ERG", "TME", "WGT"),
        "surface_selector", ("sdef_sur",), "str",
        "C810 Table 3.3, p.3-55", _ANCHOR_TABLE_3_3,
        "SUR=0 表示体源（不是「没有面」）；非 0 走面源分支。",
    ),
    # p.3-55：「ERG / Energy (MeV) / 14 MeV」。
    "ERG": VarSpec(
        "ERG", 14.0, ("-2", "-3", "-4", "-5", "-6", "-7"), ("DIR", "POS", "TME", "WGT"),
        "scalar", ("sdef_erg",), "str",
        "C810 Table 3.3, p.3-55", _ANCHOR_TABLE_3_3,
        "−7 是 spare（Table 3.4 明写它只是留给你自己加谱的框架），契约 §6 显式不支持；"
        "写进 builtins 是为了让「配对错」的报错来自同一张表，而不是在引擎里散着判断"
        f"（配对规则锚点 {_ANCHOR_BUILTIN_VARS}）。",
    ),
    # p.3-55：「TME / Time (shakes) / 0」。
    "TME": VarSpec(
        "TME", 0.0, ("-41",), ("POS", "ERG", "WGT"), "scalar", ("sdef_tme",), "str",
        "C810 Table 3.3, p.3-55", _ANCHOR_TABLE_3_3,
        "内置函数 −41（Table 3.4：TME、X、Y、Z 上的高斯）。",
    ),
    # p.3-56：「DIR / µ, the cosine of the angle between VEC and UUU,VVV,WWW（方位角恒均匀
    # 0~360°）/ Volume case: µ is sampled uniformly in −1 to 1 (isotropic); Surface case:
    # p(µ) = 2µ in 0 to 1 (cosine distribution)」⇒ 默认值取决于源型，不是一个数。
    "DIR": VarSpec(
        "DIR", None, ("-21", "-31"), (), "scalar", ("sdef_dir",), "str",
        "C810 Table 3.3, p.3-56", _ANCHOR_TABLE_3_3,
        "默认：体源各向同性（µ 均匀 −1..1）/ 面源余弦 p(µ)=2µ。p.3-59 另注 DIR=1 = 沿 VEC 单向源。",
    ),
    # p.3-56：「VEC / Reference vector for DIR / Volume case: required unless isotropic;
    # Surface case: vector normal to the surface with sign determined by NRM」。
    "VEC": VarSpec(
        "VEC", None, (), ("DIR",), "axis", ("sdef_vec",), "str",
        "C810 Table 3.3, p.3-56", _ANCHOR_TABLE_3_3,
        "体源默认「无」（各向同性时不需要）；面源默认 = 面法线（符号由 NRM 定）⇒ None。",
    ),
    # p.3-56：「NRM / Sign of the surface normal / + 1」。
    "NRM": VarSpec(
        "NRM", 1.0, (), (), "scalar", ("sdef_nrm",), "str",
        "C810 Table 3.3, p.3-56", _ANCHOR_TABLE_3_3,
    ),
    # p.3-56：「POS / Reference point for position sampling / 0,0,0」。
    "POS": VarSpec(
        "POS", None, (), (), "point", ("sdef_pos_x", "sdef_pos_y", "sdef_pos_z"), "str",
        "C810 Table 3.3, p.3-56", _ANCHOR_TABLE_3_3,
        "默认是三元组 (0,0,0)；解析层把 POS 拆进三个分量字段，故 default 记 None，由位置层"
        "按 (0,0,0) 起算。POS=Dn 时三分量同引用（p.3-57：SI 上用 L 型 POS 是「多个点源」的标准写法）。",
    ),
    # p.3-56：「RAD / Radial distance of the position from POS or AXS / 0」。
    "RAD": VarSpec(
        "RAD", 0.0, ("-21",), ("POS", "ERG", "TME", "WGT"), "scalar", ("sdef_rad",), "str",
        "C810 Table 3.3, p.3-56", _ANCHOR_TABLE_3_3,
        "p.3-57/3-58：球体源的 RAD 默认幂律 a=2、平面/柱体源 a=1（体积/面积均匀）；"
        "只有 SI 卡时等价于 SP −21（p.3-66 特殊默认 2 与 4）。",
    ),
    # p.3-56：「EXT / Cell case: distance from POS along AXS; Surface case: Cosine of angle
    # from AXS / 0」。
    "EXT": VarSpec(
        "EXT", 0.0, ("-21", "-31"), ("POS", "ERG", "TME", "WGT"), "scalar", ("sdef_ext",), "str",
        "C810 Table 3.3, p.3-56", _ANCHOR_TABLE_3_3,
        "同一个变量在体源是「沿 AXS 的距离」、在面源（球面）是「与 AXS 夹角余弦」（p.3-58）。",
    ),
    # p.3-56：「AXS / Reference vector for EXT and RAD / No direction」。
    "AXS": VarSpec(
        "AXS", None, (), (), "axis", ("sdef_axs",), "str",
        "C810 Table 3.3, p.3-56", _ANCHOR_TABLE_3_3,
        "默认「无方向」⇒ None；AXS 的存在还会改变 SP −21 的默认 a（RAD 从 2 变 1，p.3-66）。",
    ),
    # p.3-56：「X / x-coordinate of position / No X」（Y/Z 同理）。
    "X": VarSpec(
        "X", None, ("-41",), (), "axis", ("sdef_pos_x",), "str",
        "C810 Table 3.3, p.3-56", _ANCHOR_TABLE_3_3,
        "默认「No X」= 未给（不是 0）：X/Y/Z 三者齐给才是点源（p.3-57）。",
    ),
    "Y": VarSpec(
        "Y", None, ("-41",), (), "axis", ("sdef_pos_y",), "str",
        "C810 Table 3.3, p.3-56", _ANCHOR_TABLE_3_3, "同上（No Y）。",
    ),
    "Z": VarSpec(
        "Z", None, ("-41",), (), "axis", ("sdef_pos_z",), "str",
        "C810 Table 3.3, p.3-56", _ANCHOR_TABLE_3_3, "同上（No Z）。",
    ),
    # p.3-56：「CCC / Cookie-cutter cell / No cookie-cutter cell」。
    "CCC": VarSpec(
        "CCC", None, (), (), "scalar", ("sdef_ccc",), "str",
        "C810 Table 3.3, p.3-56", _ANCHOR_TABLE_3_3,
        "默认无 cookie-cutter；有 CCC 时位置按「落在 CCC 内才接受」再抽（p.3-58），"
        "效率判据同 CEL（EFF，p.3-59）。",
    ),
    # p.3-56：「ARA / Area of surface (required only for direct contributions to point
    # detectors from plane surface source.) / None」。
    "ARA": VarSpec(
        "ARA", None, (), (), "scalar", ("sdef_ara",), "str",
        "C810 Table 3.3, p.3-56", _ANCHOR_TABLE_3_3,
    ),
    # p.3-56：「WGT / Particle weight / 1」。
    "WGT": VarSpec(
        "WGT", 1.0, (), ("POS", "ERG", "TME"), "scalar", ("sdef_wgt",), "str",
        "C810 Table 3.3, p.3-56", _ANCHOR_TABLE_3_3,
        "p.3-56 原文：「The specification of WGT, EFF and PAR must be only an explicit value. "
        "A distribution is not allowed.」⇒ 这三个变量上写 Dn 是语义错误；WGT 的依赖父只是"
        "声明（真实 SDEF 里 WGT 不能是依赖变量）。",
    ),
    # p.3-56：「EFF / Rejection efficiency criterion for position sampling / .01」。
    "EFF": VarSpec(
        "EFF", 0.01, (), (), "scalar", ("sdef_eff",), "str",
        "C810 Table 3.3, p.3-56", _ANCHOR_TABLE_3_3,
        "同上：必须是显式值。判据原文在 p.3-59：MAX(successes,10) < EFF × tries ⇒ 终止问题。",
    ),
    # p.3-56：「PAR / Particle type source will emit / 1=neutron if MODE N or N P or N P E /
    # 2=photon if MODE P or P E / 3=electron if MODE E」⇒ 默认由 MODE 卡定，不是一个固定数。
    "PAR": VarSpec(
        "PAR", None, (), (), "scalar", ("sdef_par",), "str",
        "C810 Table 3.3, p.3-56", _ANCHOR_TABLE_3_3,
        "默认值 = MODE 卡里最低的那一种（原文「The default is the lowest of these three that "
        "corresponds to an actual or default entry on the MODE card」）；特殊写法 4/F = 正电子。"
        "必须是显式值，不允许分布。",
    ),
    # p.3-56 表尾：「TR / Source particle transformation TR=n or distribution of
    # transformations TR=Dn / None」。
    "TR": VarSpec(
        "TR", None, (), (), "scalar", ("sdef_tr",), "str",
        "C810 Table 3.3, p.3-56（正文 p.3-59）", _ANCHOR_TABLE_3_3,
        "两种形态都要支持：TR=n 固定变换 / TR=Dn 变换分布（p.3-59：TR=Dn 时要自带 SIn/SPn，"
        "且 SI 必须用 L 列出 TR 编号）—— 故 TR 上的 Dn 是合法值，不是错误。",
    ),
    # RATE：**C810 里没有这个源变量**（已定案，2026-09-28）。
    # 依据：① Table 3.3（p.3-55 ~ p.3-57）的变量列里没有 RATE 行（原文块机检：无该词）；
    #      ② 说明书**全文**检索 ``\bRATE\b`` 共 57 处，全部是普通英文（convergence rate /
    #         sampling rate / dose rate / energy loss rate…），无一处与 SDEF 有关。
    # ⇒ 按"找不到出处就不写语义"的规矩：不写数值、anchor=None、**不实现**；
    #   引擎侧给出值就明确拒绝（source_sampler._UNSUPPORTED_VARS）。
    # 仓库仍保留 `sdef_rate` 字段只为**兼容旧数据**（前端模板已标"非标准"），
    # 它不构成 C810 语义，也不允许被静默当成"某个默认值"。
    "RATE": VarSpec(
        "RATE", None, (), (), "scalar", ("sdef_rate",), "str",
        "未在 C810 找到：Table 3.3 无此行，全文检索 RATE 只作普通英文出现", None,
        "已定案（2026-09-28）：C810 没有 RATE 这个 SDEF 源变量 —— Table 3.3（p.3-56）"
        "变量列无此行，说明书全文检索 RATE（57 处）全是普通英文（convergence/sampling/"
        "dose/energy loss rate），无一处属源变量语义。故不写默认值、不实现；"
        "源演示里给了 RATE= 值即**明确报错**（契约 §4：认不出就报错，不静默当默认值）。"
        "字段 `sdef_rate` 仅为兼容旧数据而保留（前端已标注「非标准」）。",
    ),
    # JSU 只在手册正文出现（p.3-55 的 MCNP 变量清单：「JSU = the surface where the particle
    # started, or zero if the starting point is not on any surface」；p.3-66 的 SP −21 默认 a
    # 「unless AXS is defined or JSU ≠ 0」），Table 3.3 里没有它。
    # 采样侧用 `sdef_sur` 表达同一件事（见 `parent_field_key`）。
    # ⚠ 同上：Table 3.3 里没有 ⇒ 不写数值、anchor=None、记未决。
    "JSU": VarSpec(
        "JSU", None, (), (), "surface_selector", (), "str",
        "未在 C810 Table 3.3 印刷行（正文 p.3-55 / p.3-66）", None,
        "未决：Table 3.3 无此行。p.3-55 变量清单写「JSU = the surface where the particle "
        "started, or zero if the starting point is not on any surface」（读作默认 0），"
        "p.3-66 的 SP −21 默认 a 又依赖「JSU ≠ 0」；采样侧以 SUR 表达，故无字段键。",
    ),
}

#: 可作依赖父（``Fvar' Dn`` 的 var'）的变量名集合 —— 契约 §2 的抽样序拓扑会用到。
DEP_PARENT_NAMES: tuple[str, ...] = tuple(
    name for name, spec in VAR_SPEC.items() if spec.parents
)

#: 字段键 → 变量名 的索引（一次建好，纯查表）。
#: ⚠ **主键优先**：`sdef_pos_x` 既是 POS 的分量键、又是 X 的主键，反查必须稳定地给 X
#: （POS 自身请用 `var_field_key("POS")` 正向查）。否则「同名键谁最后写谁赢」，
#: 字典构造顺序一变，POS 与 X 的反查结果就会互换。
_FIELD_KEY_INDEX: dict[str, str] = {}
for _name, _spec in VAR_SPEC.items():
    for _i, _key in enumerate(_spec.field_keys):
        if _i == 0 or _key not in _FIELD_KEY_INDEX:
            _FIELD_KEY_INDEX[_key] = _name
del _name, _spec, _i, _key

# SDEF 变量字段键的形状：`sdef_<变量名小写>`（三元组变量拆成 `sdef_pos_x` 这类后缀形式）。
# 判定用「键必须能反查到 VAR_SPEC」而不是靠正则硬匹配 —— 这样 `sdef_distributions`
# / `sdef_extra` / `sdef_raw_text` 这些**非变量**键天然不会被误归一。
_FIELD_KEY_RE = re.compile(r"^sdef_([a-z0-9_]+)$")

# 依赖引用 `Fvar' Dn`（= F + 变量名 + 分布号）/ 纯引用 `Dn`。允许 =、大小写、空白。
# ⚠ 变量名段**只收字母**：写成 `[a-z][a-z0-9]*` 时 `[a-z0-9]*` 会吞掉分布号的 D，
# 使 `fdird2`（= `fdir=d2` 去掉分隔符）匹配失败 —— 这正是「归一化产物没人能解析」的病根。
_DEP_REF_RE = re.compile(r"^f([a-z]+)d(\d+)$")
_DIST_REF_RE = re.compile(r"^d(\d+)$")

#: 分布号越界时的统一提示（C810 p.3-63：n = distribution number (n = 1,999)）。
_DID_HINT = f"分布号必须是 {_MIN_DID}~{_MAX_DID} 的整数（C810 p.3-63：n = 1,999）"


# ────────────────────────────────────────────────────────────────────────────
# 查表助手（接口保持小：只做「名字 ↔ 字段键」的翻译）
# ────────────────────────────────────────────────────────────────────────────

def spec_for(name: str) -> VarSpec:
    """变量名（大小写不敏感）→ ``VarSpec``；不在 Table 3.3 里 ⇒ ``SourceSamplingError``。

    「未知变量一律报错」是契约 §4 的要求（不能猜、不能给默认值）。
    """
    key = str(name or "").strip().upper()
    spec = VAR_SPEC.get(key)
    if spec is None:
        raise SourceSamplingError(
            f"未知源变量 {name!r}：C810 Table 3.3（p.3-55~3-57）里没有这个变量")
    return spec


def var_field_key(name: str) -> str:
    """变量名 → SDEF 字段主键（``"ERG"`` → ``"sdef_erg"``）；无字段键的变量 ⇒ 报错。"""
    spec = spec_for(name)
    if not spec.field_keys:
        raise SourceSamplingError(
            f"源变量 {spec.name} 没有对应的 SDEF 字段（只在手册正文出现的中间量）")
    return spec.field_keys[0]


def var_for_field_key(field_key: str) -> str:
    """SDEF 字段键 → 变量名（``"sdef_pos_x"`` → ``"X"``）；不是变量字段 ⇒ 报错。"""
    text = str(field_key or "").strip().lower()
    name = _FIELD_KEY_INDEX.get(text)
    if name is None:
        raise SourceSamplingError(f"{field_key!r} 不是 SDEF 源变量字段（无对应 C810 变量）")
    return name


def parent_field_key(parent: str) -> str | None:
    """依赖父变量名 → 它在 SDEF 字段里的键；拿不到就返回 ``None``（调用方决定怎么报）。

    ``POS``/``X``/``Y``/``Z`` 有多个分量字段，这里给**主键**（``sdef_pos_x``）；
    ``JSU`` 在 SDEF 卡上以 ``SUR`` 表达（p.3-55：JSU = 粒子起始所在的曲面号）。
    """
    key = str(parent or "").strip().upper()
    if key == "JSU":
        return "sdef_sur"
    spec = VAR_SPEC.get(key)
    if spec is None or not spec.field_keys:
        return None
    return spec.field_keys[0]


def parent_name_for_field_key(field_key: Any) -> str | None:
    """SDEF 变量字段键 → 它能充当的依赖父变量名；不是变量字段就返回 ``None``。

    与 ``var_for_field_key`` 的区别只在语义：本函数是「引擎问『这个字段能当谁的父』」，
    拿不到不报错（返回 None），以便调用方给出带上下文的错误。
    """
    return _FIELD_KEY_INDEX.get(str(field_key or "").strip().lower())


def builtins_for(var: str) -> tuple[str, ...]:
    """该变量允许的内置函数（Table 3.4 配对表）；未知变量 ⇒ 报错。"""
    return spec_for(var).builtins


def anchors_used() -> frozenset[str]:
    """``VAR_SPEC`` 里用到的全部 anchor（``None`` 不计入，交由单测单列未决项）。"""
    return frozenset(s.anchor for s in VAR_SPEC.values() if s.anchor)


# ────────────────────────────────────────────────────────────────────────────
# 形态解析（C810 p.3-55 的三种形态）
# ────────────────────────────────────────────────────────────────────────────

def parse_var_ref(token: str) -> dict[str, Any]:
    """源变量值 token → 三种形态之一（C810 p.3-55）。

    形态（手册原文：「The specification of a source variable has one of these three forms:
    1. explicit value, 2. a distribution number prefixed by a D, or 3. the name of another
    variable prefixed by an F, followed by a distribution number prefixed by a D.」）::

        "14"        → {"kind": "const", "value": "14"}
        "d2"        → {"kind": "dist",  "did": 2}
        "fdir=d2"   → {"kind": "dep",   "parent": "DIR", "did": 2}

    接受「等号与空白混杂」的写法（官方算例实测有 ``erg=fdir=d2`` 这种等号连写，归一后
    等价 ``FDIR D2``）；``fdir=x``（父变量写了、分布号写错）、``F`` 后面不带变量名、
    ``D0`` 这类越界分布号、空串 —— 一律抛 ``SourceSamplingError``（契约 §4：认不出即报错，
    不允许静默兜底）。

    返回 ``{"kind": "const", "value": str}`` / ``{"kind": "dist", "did": int}`` /
    ``{"kind": "dep", "parent": str, "did": int}``。
    """
    raw = "" if token is None else str(token)
    parts = _ref_parts(raw)
    if not parts:
        raise SourceSamplingError(
            "源变量值为空：C810 p.3-55 要求三种形态之一（显式值 | Dn | Fvar′ Dn）")
    if len(parts) > 2 or (len(parts) == 2 and parts[0][:1] != "f"):
        raise SourceSamplingError(
            f"源变量值 {raw.strip()!r} 含多个 token（{parts!r}）："
            "本函数只解析**单个**变量值 —— 三元组请由调用方按分量拆开，"
            "两 token 写法只接受 `Fvar′ Dn`（如 'FDIR D2' / 'fdir=d2'）")
    if len(parts) == 2:
        # 归一化的空格形态 `Fvar′ Dn`（normalize_sdef_fields 的产物）：把第二个 token
        # 粘回第一个，走同一条 `_DEP_REF_RE` 判定，避免两种分隔符各有一条判定路径。
        tok = parts[0] + parts[1]
    else:
        tok = parts[0]

    m = _DEP_REF_RE.match(tok)
    if m:
        parent = m.group(1).upper()
        if parent not in VAR_SPEC:
            raise SourceSamplingError(
                f"依赖引用的父变量 {parent!r} 不是 C810 Table 3.3 的源变量（值 {raw.strip()!r}）")
        return {"kind": "dep", "parent": parent, "did": _check_did(int(m.group(2)), raw)}

    m = _DIST_REF_RE.match(tok)
    if m:
        return {"kind": "dist", "did": _check_did(int(m.group(1)), raw)}

    # 半截引用要单独认出来，否则会掉进下面「不是数值」的兜底里 —— 报错文案就指不到真因
    # （`fdir=x`：父变量写了，分布号写错；`F`：只有前缀没变量名）。
    if tok[:1] == "f":
        raise SourceSamplingError(
            f"依赖引用写法非法：{raw.strip()!r}。C810 p.3-55 的第三种形态是 `Fvar′ Dn`"
            "（父变量名以 F 打头，后跟以 D 打头的分布号），例如 `FDIR D2` / `fdir=d2`")
    if tok[:1] == "d" and tok[1:].isdigit():
        raise SourceSamplingError(f"分布号非法：{raw.strip()!r}（{_DID_HINT}）")

    if _NUM_TOKEN_RE.match(tok):
        return {"kind": "const", "value": tok}

    raise SourceSamplingError(
        f"源变量值 {raw.strip()!r} 既不是数值、也不是 Dn 分布引用、也不是 Fvar′ Dn 依赖引用"
        "（C810 p.3-55 的三种形态）")


def _check_did(did: int, raw: Any) -> int:
    """分布号范围校验（``D0`` / ``D1000`` 这类「看着像引用其实指不到分布」的写法必须报错）。"""
    if not (_MIN_DID <= did <= _MAX_DID):
        raise SourceSamplingError(f"分布号 D{did}（来自 {str(raw).strip()!r}）越界：{_DID_HINT}")
    return did


def _ref_parts(token: str) -> list[str]:
    """引用 token → 小写、去空白、按 ``=`` 与空白切开的片段列表。

    ``"="`` 与空白在这里**同一件事**（手册 p.3-55：「The equal signs are optional.」），
    所以先整体把 ``=`` 当分隔符再切空白::

        "d2"         → ["d2"]
        "fdir d2"    → ["fdir", "d2"]
        "fdir=d2"    → ["fdir", "d2"]
        "fdir = d2"  → ["fdir", "d2"]
        "erg=fdir=d2"→ ["erg", "fdir", "d2"]   ← 3 段，调用方据此报「多个 token」

    两侧留空的 ``=``（``"=d2"`` / ``"fdir="``）说明有一半没写，直接按非法报错 ——
    SDEF 卡上 ``ERG=`` 那层等号由解析层消费，进到本函数时不该再有"半截等号"。
    """
    text = "" if token is None else str(token).strip()
    if not text:
        return []
    if text.startswith("=") or text.endswith("="):
        raise SourceSamplingError(
            f"源变量值 {text!r} 的等号两侧有空缺（C810 p.3-55 的三种形态里，等号只是"
            "可选分隔符，两侧都要有内容）")
    return [p for p in text.lower().replace("=", " ").split() if p]


# ────────────────────────────────────────────────────────────────────────────
# SDEF 字段归一化（解析侧与抽样侧共用的唯一写法）
# ────────────────────────────────────────────────────────────────────────────

def normalize_sdef_fields(fields: dict) -> dict:
    """把 SDEF 变量字段的依赖写法统一成 ``FDIR D2``；其它键原样带过（**纯函数**）。

    归一化的四种写法（第四种来自官方算例的等号连写，p.3-55 的 ``Var Fvar' Dn``）::

        {"sdef_erg": "fdir d2"}      → {"sdef_erg": "FDIR D2"}
        {"sdef_erg": "FDIR D2"}      → {"sdef_erg": "FDIR D2"}
        {"sdef_erg": "fdir=d2"}      → {"sdef_erg": "FDIR D2"}
        {"sdef_erg": "erg=fdir=d2"}  → {"sdef_erg": "FDIR D2"}

    行为约定：

    * **不就地修改入参**，返回新字典（键序保持）；非 dict 入参原样返回；
    * 只处理「键能反查到 ``VAR_SPEC``」的变量字段（``sdef_erg`` / ``sdef_pos_x`` …），
      ``sdef_distributions`` / ``sdef_extra`` / 任意其它键（含非字符串值）**逐字不动**；
    * 只归一 ``Fvar' Dn`` 形态；值本身非法（如 ``fdir=x``）**不在这里报错** ——
      归一化是「改写法」，合法性判定归 ``parse_var_ref``（调用方在抽样时拿到明确错误）；
    * 三元组变量（VEC/AXS/POS）的值含空格，不会被误当依赖引用。
    """
    if not isinstance(fields, dict):
        return fields
    out = dict(fields)
    for key, value in fields.items():
        if not isinstance(value, str):
            continue
        if _var_name_for_field_key(key) is None:
            continue
        out[key] = _normalize_dep_value(value)
    return out


def _var_name_for_field_key(key: Any) -> str | None:
    """字段键 → 变量名；不是变量字段键就返回 ``None``（调用方跳过）。"""
    text = str(key or "").strip().lower()
    if not _FIELD_KEY_RE.match(text):
        return None
    return _FIELD_KEY_INDEX.get(text)


def _normalize_dep_value(value: str) -> str:
    """单个字段值 → ``Fvar′ Dn`` 规范写法；不是依赖引用就**原样返回**。

    ``"="`` 与空白同等看待（p.3-55：等号可选），所以先把等号换成空白再匹配 ——
    这样 ``fdir=d2`` / ``fdir d2`` / ``fdir = d2`` 走同一条判定，与 ``_ref_parts`` 一致。
    """
    text = value.strip()
    if not text:
        return value
    m = _DEP_REF_RE.match(text.lower().replace("=", " ").replace(" ", ""))
    if not m:
        return value
    return f"F{m.group(1).upper()} D{int(m.group(2))}"
