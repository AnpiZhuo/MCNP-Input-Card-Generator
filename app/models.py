"""
Data Models — Edit State for Each Tab Page
============================================

Defines all Pydantic-style dataclass models used throughout the MCNP Input Card
Generator application. These models represent the structured data for every major
section of an MCNP input deck: cells (geometry), materials, sources, basic settings,
tallies, and advanced options.

Each dataclass corresponds directly to a tab in the GUI and is used for:
  - Holding intermediate editing state before INP generation.
  - Serialization/deserialization to/from JSON project files.
  - Passing structured data to the INP generator.

数据模型：保存各标签页的编辑状态
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CellData:
    """
    Cell (geometry) card data.

    Represents a single MCNP CELL card describing a geometric region bounded by
    surfaces, optionally filled with a material.

    Each cell is defined by a unique number, a material specification (material
    number or "0" for void), a density, and a Boolean surface expression.
    Various optional MCNP keywords (IMP, VOL, PWT, EXT, FCL, U, FILL, LAT, TRCL)
    can also be specified.

    栅元卡数据
    """
    number: int          # Cell number (e.g. 1, 2, 3...) / 栅元号
    material: str        # Material number (e.g. "M1" or "0" for void) / 材料号（如 "M1" 或 "0" 表示 void）
    density: str         # Density (e.g. "-11.34"; leave blank for void) / 密度（如 "-11.34"，void 时留空）
    surface_expr: str    # Surface Boolean expression (e.g. "-10 20 -30 40") / 曲面表达式（如 "-10 20 -30 40"）
    imp_n: str = ""      # IMP:N — neutron importance (blank = not generated) / IMP:N（留空不生成）
    imp_p: str = ""      # IMP:P — photon importance (blank = not generated) / IMP:P（留空不生成）
    imp_e: str = ""      # IMP:E — electron importance (blank = not generated) / IMP:E（留空不生成）
    vol: str = ""        # VOL — cell volume (leave blank for MCNP to calculate) / VOL 体积（留空让 MCNP 自己算）
    pwt: str = ""        # PWT — photon production weight / PWT — 光子产生权重
    ext: str = ""        # EXT — exponential transform / EXT — 指数变换
    fcl: str = ""        # FCL — forced collision / FCL — 强制碰撞
    u: str = ""          # U — universe number / U — 宇宙号
    fill: str = ""       # FILL — fill universe number / FILL — 填充的宇宙号
    lat: str = ""        # LAT — lattice type (1 = hexahedron, 2 = hexagonal prism) / LAT — 格阵（1=六面体，2=六棱柱）
    trcl: str = ""       # TRCL — coordinate transformation / TRCL — 坐标变换
    comment: str = ""    # Inline comment for this cell / 注释


@dataclass
class MaterialRow:
    """
    A single ZAID + fraction entry within a material card.

    Each row represents one nuclide in an MCNP material definition (Mm card),
    consisting of a ZAID identifier (e.g. "92235.06c") and its atomic or
    weight fraction (e.g. "-0.05" for a negative weight fraction).

    材料卡中一行 ZAID + 份额
    """
    zaid: str            # ZAID identifier, e.g. "92235.06c" / 如 "92235.06c"
    fraction: str        # Atomic or weight fraction, e.g. "-0.05" / 如 "-0.05"


@dataclass
class MaterialData:
    """
    Material card data (Mm card: nuclide composition only, no density).

    Represents one MCNP material definition containing a list of nuclide
    entries (MaterialRow), an optional chemical formula string for the
    formula-based input mode, and additional MCNP options (e.g. nlib, gas).

    Note: Density is entered on the CELL card, not here.

    材料卡数据 (Mm 卡：只含核素组成，不含密度)
    """
    number: int          # Material number / 材料号
    rows: List[MaterialRow] = field(default_factory=list)  # List of ZAID + fraction rows / ZAID+份额行列表
    comment: str = ""    # Material comment / 注释
    formula: str = ""    # Raw chemical formula (saved for formula input mode, used to repopulate UI) / 化学式原文（化学式模式下保存，用于回填UI）
    options: str = ""    # Extra MCNP options (e.g. nlib=.66c gas=...) / 额外选项（如 nlib=.66c gas=...）
    mt_card: str = ""    # Thermal neutron S(alpha,beta) card (e.g. "lwtr.10t") / 热中子 MT 卡（如 "lwtr.10t"）


@dataclass
class SourceData:
    """
    Single SDEF (general source definition) source entry.

    Defines one source in the MCNP SDEF card. Multiple SourceData entries
    can be combined for multi-source problems using the SP (probability)
    distribution.

    Each field corresponds to an SDEF keyword parameter. Empty strings
    mean the parameter is omitted from the generated card.

    SDEF 单个源数据
    """
    number: int          # Source number (for display purposes) / 源编号（用于显示）
    par: str = ""        # Particle type (blank = not generated) / 粒子类型（留空不生成 PAR）
    erg: str = ""        # Energy in MeV (blank = not generated) / 能量 MeV（留空不生成 ERG）
    pos_x: str = ""      # Position X / 位置 X
    pos_y: str = ""      # Position Y / 位置 Y
    pos_z: str = ""      # Position Z / 位置 Z
    dir_: str = ""       # Direction (blank = isotropic) / 方向（留空=各向同性）
    wgt: str = ""        # Weight (blank = not generated) / 权重（留空不生成 WGT）
    probability: str = ""  # Probability fraction (corresponds to SP card) / 概率份额（对应 SP）
    cel: str = ""        # Source cell (blank = anywhere) / 源所在栅元（留空不限）
    tme: str = ""        # Emission time / 发射时间
    vec: str = ""        # Direction vector / 方向向量
    axs: str = ""        # Axis vector / 轴向量
    rad: str = ""        # Radial distance / 径向距离
    ext: str = ""        # Axial distance / 轴向距离
    sur: str = ""        # Surface source (SUR keyword) / 曲面源（SUR）
    nrm: str = ""        # Surface normal (NRM keyword) / 曲面法线（NRM）
    tr: str = ""         # Transformation (TR keyword) / 变换（TR）
    ccc: str = ""        # Cookie-cutter (CCC keyword) / Cookie-cutter（CCC）
    ara: str = ""        # Point detector normalization (ARA keyword) / 点探测器归一化（ARA）
    rate: str = ""       # Source strength (RATE keyword) / 源强度（RATE）
    sdef_extra: str = "" # Extra SDEF parameters (preserved verbatim) / 额外SDEF参数（原样保留）


@dataclass
class BasicSettings:
    """
    Basic problem settings.

    Contains the title card, particle mode flags (MODE card), and run
    control parameters (NPS, CTME). The PHYS:FIS flag controls whether
    fission is enabled (True) or disabled via the NONU card (False).

    基本设置
    """
    title: str = ""      # Problem title card / 标题卡
    mode_n: bool = False  # Neutron mode enabled / 中子模式
    mode_p: bool = False  # Photon mode enabled / 光子模式
    mode_e: bool = False  # Electron mode enabled / 电子模式
    mode_h: bool = False  # Proton mode enabled / 质子 (Proton)
    mode_he: bool = False # Heavy ion mode enabled / 重离子 (Heavy Ion)
    mode_d: bool = False  # Deuteron mode enabled / 氘核 (Deuteron)
    mode_t: bool = False  # Triton mode enabled / 氚核 (Triton)
    mode_a: bool = False  # Alpha mode enabled / α粒子 (Alpha)
    nps: str = ""         # Number of histories (NPS card) / NPS 历史数
    ctme: str = ""        # Computation time limit in minutes (CTME card) / 计算时间限制（分钟）
    phys_fis: bool = True # True = fission enabled; False = outputs NONU card to disable fission / True=开启裂变, False=输出 NONU 卡关闭裂变


@dataclass
class TallyDefinition:
    """
    单个计数定义，覆盖所有 Fn 类型。

    TallyDefinition — deep module for the tally system: a small interface
    (4 fields) covering all tally types (F1–F8, including F15/F25 variants).
    Callers iterate over a list of these; the formatting logic is hidden
    inside the generator.

    Fields:
        type:      "F1" | "F2" | "F4" | "F5" | "F6" | "F7" | "F8"
        number:    tally number suffix (e.g. 1, 2, 5, 15, 25…)
        particles: list of particle designators ["n"], ["n", "p", "e"], …
        params:    parameter string — surface/cell numbers for F1/F2/F4/F6/F7/F8,
                   "x y z R0 …" (multi-point) for F5.

    单个计数定义
    """
    type: str            # "F1" | "F2" | "F4" | "F5" | "F6" | "F7" | "F8"
    number: int          # 1, 2, 4, 5, 15, 25 …
    particles: list[str] = field(default_factory=lambda: ["n"])
    params: str = ""     # 参数串（取决于类型）
    generate_en: bool = False  # 是否自动生成该计数对应的 En 能量卡（默认不勾选）


@dataclass
class TallySettings:
    """
    Tally card settings.

    Controls MCNP tally definitions (list[TallyDefinition]), energy binning
    (E card), and time/energy cutoff cards (CUT:N, CUT:P, CUT:E,
    CUT:H, CUT:HE).

    Energy bins can be set via min/max/count/log scale or custom text.

    计数卡设置
    """
    # Tallies defined as a dynamic list of TallyDefinition / 计数定义列表
    tallies: list[TallyDefinition] = field(default_factory=list)

    # Energy bin parameters (E card) / 能量网格参数（E卡）
    e_min: str = ""
    e_max: str = ""
    e_bins: int = 0        # Number of energy bins / 能量网格数
    e_log: bool = False    # Logarithmic energy grid / 对数网格
    e_custom_enabled: bool = False    # Enable custom energy grid text / 自定义网格开关
    e_custom_text: str = ""           # Custom energy grid text / 自定义网格文本
    e_cards_text: str = ""            # En energy cards text (one card per line) / En 能量卡文本（每行一条）

    # CUT:N — neutron cutoff / CUT:N 中子截断 (C810: T E WC1 WC2 SWTM)
    cut_n_t: str = ""                 # Time cutoff (shakes)
    cut_n_e: str = ""                 # Energy cutoff (MeV)
    cut_n_raw: str = ""               # Raw parameter string (for round-trip)
    cut_n_wc1: str = ""               # Weight ratio 1 / 权重比 1
    cut_n_wc2: str = ""               # Weight ratio 2 / 权重比 2
    cut_n_swtm: str = ""              # Swarm flag / 群标志
    # CUT:P — photon cutoff / CUT:P 光子截断 (C810: T E WC1 WC2 SWTM)
    cut_p_t: str = ""                 # Time cutoff
    cut_p_e: str = ""                 # Energy cutoff
    cut_p_raw: str = ""               # Raw parameter string
    cut_p_wc1: str = ""               # Weight ratio 1
    cut_p_wc2: str = ""               # Weight ratio 2
    cut_p_swtm: str = ""              # Swarm flag
    # CUT:E — electron cutoff (C810: T E WC1 WC2 SWTM)
    cut_e_t: str = ""                 # Time cutoff
    cut_e_e: str = ""                 # Energy cutoff
    cut_e_raw: str = ""               # Raw parameter string
    cut_e_wc1: str = ""               # Weight ratio 1
    cut_e_wc2: str = ""               # Weight ratio 2
    cut_e_swtm: str = ""              # Swarm flag
    # CUT:H — proton cutoff (C810: T E WC1 WC2 SWTM)
    cut_h_t: str = ""
    cut_h_e: str = ""
    cut_h_raw: str = ""
    cut_h_wc1: str = ""
    cut_h_wc2: str = ""
    cut_h_swtm: str = ""
    # CUT:HE — heavy ion cutoff (C810: T E WC1 WC2 SWTM)
    cut_he_t: str = ""
    cut_he_e: str = ""
    cut_he_raw: str = ""
    cut_he_wc1: str = ""
    cut_he_wc2: str = ""
    cut_he_swtm: str = ""
    # CUT:D — deuteron cutoff
    cut_d_t: str = ""
    cut_d_e: str = ""
    cut_d_raw: str = ""
    cut_d_wc1: str = ""
    cut_d_wc2: str = ""
    cut_d_swtm: str = ""
    # CUT:T — triton cutoff
    cut_t_t: str = ""
    cut_t_e: str = ""
    cut_t_raw: str = ""
    cut_t_wc1: str = ""
    cut_t_wc2: str = ""
    cut_t_swtm: str = ""
    # CUT:A — alpha cutoff
    cut_a_t: str = ""
    cut_a_e: str = ""
    cut_a_raw: str = ""
    cut_a_wc1: str = ""
    cut_a_wc2: str = ""
    cut_a_swtm: str = ""


@dataclass
class AdvancedSettings:
    """
    Advanced MCNP card settings.

    Contains parameters described in the MCNP manual that are not exposed
    as dedicated UI elements. Includes PHYS card parameters for each
    particle type (N, P, E, H, HE), distribution source mode settings,
    and a raw text field for user-defined additional cards.

    高级设置：说明书中有但界面未单独列出的卡片
    """
    # User-defined additional MCNP cards (preserved verbatim)
    other_cards: str = ""     # 用户手动输入的其他 MCNP 卡片

    # PHYS:N (C810: EMAX, EMCNF, IUNR, DNB, FISNU)
    phys_n_emax: str = ""   # 中子能量上限(MeV), 默认=极大
    phys_n_emcnf: str = ""  # 俘获方式转变能(MeV), 默认=0.0
    phys_n_iunr: str = ""   # 未分辨共振概率表: 0=打开(默认), 1=关闭
    phys_n_dnb: str = ""    # 缓发中子处理: 0=常态(默认), -n=选代, >n=每个中子
    phys_n_fisnu: str = ""  # <0=用-fisnu高斯宽度, 0=整数采样(默认), 1=推荐高斯, 2=原始Terrell

    # PHYS:P (C810: EMCPF, IDES, NOCOH, ISPN, NODOP)
    phys_p_emcpf: str = ""  # 详细/简单分界能量(MeV), 默认=100
    phys_p_ides: str = ""   # 0=光子产生电子(默认), 1=不产生
    phys_p_nocoh: str = ""  # 0=含相干散射(默认), 1=关闭
    phys_p_ispn: str = ""   # 0=光核作用打开, -1=关闭(默认)
    phys_p_nodop: str = ""  # 0=含Doppler展宽(默认), 1=关闭

    # PHYS:E (C810: EMAX, IDES, IPHOT, IBAD, ISTRG, BNUM, XNUM, RNOK, ENUM, NUMB)
    phys_e_emax: str = ""   # 电子能量上限(MeV), 默认=100
    phys_e_ides: str = ""   # 0=光子产生电子(默认), 1=不产生
    phys_e_iphoto: str = "" # 0=电子产生光子(默认), 1=不产生
    phys_e_ibad: str = ""   # 0=轫致辐射角分布使用Koch-Motz(默认), 1=使用简单近似
    phys_e_istrg: str = ""  # 0=连续减慢(默认), 1=大步长
    phys_e_bnum: str = ""   # 轫致辐射光子数缩放因子, 默认=1
    phys_e_xnum: str = ""   # 电子步长缩放因子
    phys_e_rnok: str = ""   # 电子/光子转换: 0=Knock-on电子产生光子(默认), 1=关闭
    phys_e_enum: str = ""   # 电子能量离散化点数
    phys_e_numb: str = ""   # 轫致辐射每子步控制: >0=每子步产生, 0=常态默认

    # PHYS:H (MCNP6, 不在C810中)
    phys_h_emax: str = ""
    phys_h_ie: str = ""
    phys_h_ipr: str = ""
    phys_h_rgas: str = ""
    phys_h_emin: str = ""
    phys_h_ecut: str = ""

    # PHYS:HE (MCNP6, 不在C810中)
    phys_he_emax: str = ""
    phys_he_ie: str = ""
    phys_he_ipr: str = ""
    phys_he_rgas: str = ""
    phys_he_emin: str = ""
    phys_he_ecut: str = ""

    # KCODE 临界源参数（source_mode="kcode" 时使用）
    # KCODE/KSRC — Criticality source / 临界源
    kcode_nsrc: str = ""   # 每代粒子数/Number of source histories per generation
    kcode_rkk: str = ""    # 初始 keff 估计/Initial keff guess
    kcode_ikz: str = ""    # 非活跃代数/Number of inactive generations
    kcode_kct: str = ""    # 总代数/Number of active generations
    kcode_knrm: str = ""   # 归一化选项 (0=normalize to NSRC, 1=normalize to actual)/Normalization option
    ksrc_points: str = ""  # KSRC 坐标点 JSON: [{"x":0,"y":0,"z":0}, ...] / KSRC coordinate points as JSON

    # SDEF mode toggle: "fixed" = point source, "distribution" = distributed source
    # SDEF 模式切换（固定点源/分布源）
    source_mode: str = "distribution"       # "fixed" | "distribution" | "kcode"

    # Distribution source mode: SDEF field values
    # 分布源模式：SDEF 字段值
    sdef_par: str = ""
    sdef_erg: str = ""
    sdef_pos_x: str = ""
    sdef_pos_y: str = ""
    sdef_pos_z: str = ""
    sdef_wgt: str = ""
    sdef_dir: str = ""
    sdef_cel: str = ""
    sdef_tme: str = ""
    sdef_vec: str = ""
    sdef_axs: str = ""
    sdef_rad: str = ""
    sdef_ext: str = ""
    sdef_sur: str = ""     # Surface source / 曲面源
    sdef_nrm: str = ""     # Surface normal / 曲面法线
    sdef_tr: str = ""      # Transformation / 变换
    sdef_ccc: str = ""     # Cookie-cutter / Cookie-cutter
    sdef_ara: str = ""     # Point detector normalization / 点探测器归一化
    sdef_rate: str = ""    # Source strength / 源强度
    sdef_extra: str = ""   # Extra SDEF fields (preserved verbatim) / SDEF 额外字段（原样保留）

    # Distribution source mode: SI/SP pair serialized text (each pair separated by \n---\n)
    # 分布源模式：SI/SP 对序列化文本（每个对用 \n---\n 分隔）
    sdef_raw_text: str = ""


@dataclass
class DeckData:
    """
    Aggregate data for the entire INP input deck.

    This is the root data model that holds all sections of an MCNP input
    deck: basic settings, surface definitions, cell definitions, material
    definitions, source definitions, tally settings, and advanced settings.

    It is passed as a single object to the generator and validator to
    avoid parameter list bloat.

    整个 INP 输入卡的聚合数据。
    统一传递给生成器、校验器，避免参数列表膨胀。
    """
    basic: BasicSettings = field(default_factory=BasicSettings)       # Title, mode, NPS, CTME / 标题、模式、NPS、CTME
    surfaces: str = ""                                                # Surface cards as raw text / 曲面卡片原始文本
    tr_cards: str = ""                                                 # TR transformation cards as raw text / TR 变换卡原始文本
    cells: list[CellData] = field(default_factory=list)               # Cell definitions / 栅元定义列表
    materials: list[MaterialData] = field(default_factory=list)       # Material definitions / 材料定义列表
    sources: list[SourceData] = field(default_factory=list)           # Source definitions / 源定义列表
    tally: TallySettings | None = None                                # Tally settings (optional) / 计数设置（可选）
    adv: AdvancedSettings = field(default_factory=AdvancedSettings)   # Advanced card settings / 高级卡片设置
