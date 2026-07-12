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
    nps: str = ""         # Number of histories (NPS card) / NPS 历史数
    ctme: str = ""        # Computation time limit in minutes (CTME card) / 计算时间限制（分钟）
    phys_fis: bool = True # True = fission enabled; False = outputs NONU card to disable fission / True=开启裂变, False=输出 NONU 卡关闭裂变


@dataclass
class TallySettings:
    """
    Tally card settings.

    Controls MCNP tally definitions (F1 through F8), energy binning
    (E card), and time/energy cutoff cards (CUT:N, CUT:P, CUT:E,
    CUT:H, CUT:HE).

    Each Fn tally has an enabled flag and a surface/cell parameter string.
    Energy bins can be set via min/max/count/log scale or custom text.

    计数卡设置
    """
    # F1 tally — surface current / F1 计数 — 面电流
    f1_enabled: bool = False
    f1_surface: str = ""   # Surface number for F1 / F1 曲面号
    # F2 tally — surface flux / F2 计数 — 面通量
    f2_enabled: bool = False
    f2_surface: str = ""   # Surface number for F2 / F2 曲面号
    # F4 tally — cell flux / F4 计数 — 体通量
    f4_enabled: bool = False
    f4_cell: str = ""      # Cell number for F4 / F4 栅元号
    # F5 tally — point detector / F5 计数 — 点探测器
    f5_enabled: bool = False
    f5_x: str = ""
    f5_y: str = ""
    f5_z: str = ""
    # F6 tally — energy deposition / F6 计数 — 能量沉积
    f6_enabled: bool = False
    f6_cell: str = ""      # Cell number for F6 / F6 栅元号
    # F7 tally — fission energy deposition / F7 计数 — 裂变能沉积
    f7_enabled: bool = False
    f7_cell: str = ""      # Cell number for F7 / F7 栅元号
    # F8 tally — pulse height / F8 计数 — 脉冲高度
    f8_enabled: bool = False
    f8_cell: str = ""      # Cell number for F8 / F8 栅元号

    # Energy bin parameters (E card) / 能量网格参数（E卡）
    e_min: str = ""
    e_max: str = ""
    e_bins: int = 0        # Number of energy bins / 能量网格数
    e_log: bool = False    # Logarithmic energy grid / 对数网格
    e_custom_enabled: bool = False    # Enable custom energy grid text / 自定义网格开关
    e_custom_text: str = ""           # Custom energy grid text / 自定义网格文本

    # CUT:N — neutron cutoff / CUT:N 中子截断
    cut_n_t: str = ""                 # Time cutoff (shakes) / 中子时间截断 (shake)
    cut_n_e: str = ""                 # Energy cutoff (MeV) / 中子能量截断 (MeV)
    cut_n_raw: str = ""               # Raw parameter string (for j-skip syntax, etc.) / CUT:N 原始参数串（用于 j 跳转语法等）
    cut_n_wgt: str = ""               # Weight cutoff / CUT:N 权重截断
    cut_n_tmc: str = ""               # Collision time cutoff / CUT:N 碰撞时间截断
    cut_n_wc1: str = ""               # Weight ratio 1 / CUT:N 权重比 1
    cut_n_wc2: str = ""               # Weight ratio 2 / CUT:N 权重比 2
    # CUT:P — photon cutoff / CUT:P 光子截断
    cut_p_t: str = ""                 # Time cutoff / CUT:P 光子时间截断
    cut_p_e: str = ""                 # Energy cutoff / CUT:P 光子能量截断
    cut_p_raw: str = ""               # Raw parameter string / CUT:P 原始参数串
    cut_p_wgt: str = ""               # Weight cutoff / CUT:P 权重截断
    cut_p_tmc: str = ""               # Collision time cutoff / CUT:P 碰撞时间截断
    cut_p_wc1: str = ""               # Weight ratio 1 / CUT:P 权重比 1
    cut_p_wc2: str = ""               # Weight ratio 2 / CUT:P 权重比 2
    # CUT:E — electron cutoff / CUT:E 电子截断
    cut_e_t: str = ""                 # Time cutoff / CUT:E 电子时间截断
    cut_e_e: str = ""                 # Energy cutoff / CUT:E 电子能量截断
    cut_e_raw: str = ""               # Raw parameter string / CUT:E 原始参数串
    cut_e_wgt: str = ""               # Weight cutoff / CUT:E 权重截断
    cut_e_tmc: str = ""               # Collision time cutoff / CUT:E 碰撞时间截断
    cut_e_wc1: str = ""               # Weight ratio 1 / CUT:E 权重比 1
    cut_e_wc2: str = ""               # Weight ratio 2 / CUT:E 权重比 2
    # CUT:H — proton cutoff / CUT:H — 质子
    cut_h_t: str = ""
    cut_h_e: str = ""
    cut_h_raw: str = ""
    cut_h_wgt: str = ""
    cut_h_tmc: str = ""
    cut_h_wc1: str = ""
    cut_h_wc2: str = ""
    # CUT:HE — heavy ion cutoff / CUT:HE — 重离子
    cut_he_t: str = ""
    cut_he_e: str = ""
    cut_he_raw: str = ""
    cut_he_wgt: str = ""
    cut_he_tmc: str = ""
    cut_he_wc1: str = ""
    cut_he_wc2: str = ""


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

    # PHYS:N parameters (emax, ie, nubar, rgas, idm) / PHYS:N 参数
    phys_n_emax: str = ""
    phys_n_ie: str = ""
    phys_n_nubar: str = ""
    phys_n_rgas: str = ""
    phys_n_idm: str = ""

    # PHYS:P parameters (emin, isnp, ff) / PHYS:P 参数
    phys_p_emin: str = ""
    phys_p_isnp: str = ""
    phys_p_ff: str = ""

    # PHYS:E parameters (emin, isne) / PHYS:E 参数
    phys_e_emin: str = ""
    phys_e_isne: str = ""

    # PHYS:H parameters (emax, ie, ipr, rgas, emin, ecut) / PHYS:H 参数
    phys_h_emax: str = ""
    phys_h_ie: str = ""
    phys_h_ipr: str = ""
    phys_h_rgas: str = ""
    phys_h_emin: str = ""
    phys_h_ecut: str = ""

    # PHYS:HE parameters (emax, ie, ipr, rgas, emin, ecut) / PHYS:HE 参数
    phys_he_emax: str = ""
    phys_he_ie: str = ""
    phys_he_ipr: str = ""
    phys_he_rgas: str = ""
    phys_he_emin: str = ""
    phys_he_ecut: str = ""

    # SDEF mode toggle: "fixed" = point source, "distribution" = distributed source
    # SDEF 模式切换（固定点源/分布源）
    source_mode: str = "fixed"       # "fixed" | "distribution"

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
    cells: list[CellData] = field(default_factory=list)               # Cell definitions / 栅元定义列表
    materials: list[MaterialData] = field(default_factory=list)       # Material definitions / 材料定义列表
    sources: list[SourceData] = field(default_factory=list)           # Source definitions / 源定义列表
    tally: TallySettings | None = None                                # Tally settings (optional) / 计数设置（可选）
    adv: AdvancedSettings = field(default_factory=AdvancedSettings)   # Advanced card settings / 高级卡片设置
