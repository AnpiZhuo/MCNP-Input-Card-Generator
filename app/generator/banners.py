"""
生成器节头词汇 —— C 注释节头的单一事实来源（深模块）
Frozen banner vocabulary for generator-emitted C-comment section headers.

生成器在 INP 输出里用 C 注释行作节头（用户可见的 INP 输出风格）。解析器在
`split_sections` 处拦截这些精确节头，不把它们吸收进结构化字段（否则
R1 不动点会被逐代膨胀破坏：cell.comment / deck.surfaces / other_cards 复利增长）。

词汇冻结在本文（方案 C）：生成器与解析器共享同一来源，词汇漂移 → R1 立刻 RED
（R1 测试套件是漂移的兜底网）。

界面约定：
- 精确节头用模块级常量（如 DATA_CARDS_BANNER）。
- 动态计数节头用构造器（如 cell_cards_banner(n)）。
- 生成器【禁止】内联节头字符串，一律调用本模块。
- 解析器用 is_generator_banner(line) 判断某 C 行是否为生成器节头（仅匹配精确词汇，
  不碰用户任意 C 注释）。
"""
import re

# ── 精确节头常量（生成器与解析器共享的冻结词汇）──────────────
DATA_CARDS_BANNER        = "C  ===== Data Cards ====="
TALLIES_BANNER           = "C  Tallies"
TR_BANNER                = "C  TR Transformations"
KSRC_BANNER              = "C  KSRC Initial Fission Points"
HSRC_BANNER              = "C  HSRC Shannon Entropy Mesh"
KCODE_BANNER             = "C  KCODE Criticality Source Parameters"
KCODE_SKIPPED_BANNER     = "C  KCODE skipped — NSRC not set"
KSRC_FAILED_BANNER       = "C  KSRC points: failed to parse"
FISSION_OFF_BANNER       = "C  Fission turned off via NONU card"
RAW_CELL_BANNER          = "C  Cell Cards (raw text mode)"
RAW_SURF_BANNER          = "C  Surface Cards (raw text mode)"
RAW_MAT_BANNER           = "C  Materials (raw text mode)"
RAW_SDEF_BANNER          = "C  Source Definition (raw text mode)"
RAW_PHYS_BANNER          = "C  PHYS Cards (raw text mode)"
RAW_TALLY_BANNER         = "C  Tally Cards (raw text mode)"
RAW_E0_BANNER            = "C  Energy mesh (raw text mode)"
RAW_CUT_BANNER           = "C  Particle Cutoffs (raw text mode)"
ADDITIONAL_CARDS_BANNER  = "C  ===== Additional Cards (from Advanced tab) ====="
PER_TALLY_EN_BANNER      = "C  Per-tally energy grids (En cards)"
PER_TALLY_TN_BANNER      = "C  Per-tally time grids (Tn cards)"
ENERGY_MESH_SKIP_BANNER  = "C  Energy mesh: custom grid skipped — need at least 2 energy values"
ENERGY_MESH_INVALID_BANNER = "C  Energy mesh: invalid parameters, skipped"
TIME_MESH_SKIP_BANNER    = "C  Time mesh: custom grid skipped — need at least 2 time values"
TIME_MESH_INVALID_BANNER = "C  Time mesh: invalid parameters, skipped"


# ── 动态节头构造器（生成器侧调用，禁止内联）──────────────────
def cell_cards_banner(n: int) -> str:
    """C  Cell Cards: {n} cells defined"""
    return f"C  Cell Cards: {n} cells defined"


def surface_cards_banner(n: int) -> str:
    """C  Surface Cards: {n} surfaces defined"""
    return f"C  Surface Cards: {n} surfaces defined"


def energy_mesh_banner(n_bins, type_label: str, lo, hi) -> str:
    """C  Energy mesh: {n_bins} {type_label} intervals, {lo} to {hi} MeV"""
    return f"C  Energy mesh: {n_bins} {type_label} intervals, {lo} to {hi} MeV"


def energy_mesh_custom_banner(n: int) -> str:
    """C  Energy mesh: {n} user-defined points"""
    return f"C  Energy mesh: {n} user-defined points"


def time_mesh_banner(n_bins, type_label: str, lo, hi) -> str:
    """C  Time mesh: {n_bins} {type_label} intervals, {lo} to {hi} shakes"""
    return f"C  Time mesh: {n_bins} {type_label} intervals, {lo} to {hi} shakes"


def time_mesh_custom_banner(n: int) -> str:
    """C  Time mesh: {n} user-defined points"""
    return f"C  Time mesh: {n} user-defined points"


def skipped_card_banner(kind: str, content: str) -> str:
    """C  SKIPPED (not a valid {kind} card): {content}"""
    return f"C  SKIPPED (not a valid {kind} card): {content}"


def multi_source_comment_banner(n: int) -> str:
    """C  {n} sources, probability keyed to D1（多源概率键控注释）"""
    return f"C  {n} sources, probability keyed to D1"


# ── 识别：判断一行 C 注释是否为生成器节头 ────────────────────
# 精确节头集合（大小写不敏感，锚定全行，防误伤用户注释如 "C  Cell Cards are useful"）
_EXACT_BANNERS = (
    DATA_CARDS_BANNER,
    TALLIES_BANNER,
    TR_BANNER,
    KSRC_BANNER,
    HSRC_BANNER,
    KCODE_BANNER,
    KCODE_SKIPPED_BANNER,
    KSRC_FAILED_BANNER,
    FISSION_OFF_BANNER,
    RAW_CELL_BANNER,
    RAW_SURF_BANNER,
    RAW_MAT_BANNER,
    RAW_SDEF_BANNER,
    RAW_PHYS_BANNER,
    RAW_TALLY_BANNER,
    RAW_E0_BANNER,
    RAW_CUT_BANNER,
    ADDITIONAL_CARDS_BANNER,
    PER_TALLY_EN_BANNER,
    PER_TALLY_TN_BANNER,
    ENERGY_MESH_SKIP_BANNER,
    ENERGY_MESH_INVALID_BANNER,
    TIME_MESH_SKIP_BANNER,
    TIME_MESH_INVALID_BANNER,
)
_EXACT_UPPER = frozenset(b.upper() for b in _EXACT_BANNERS)

# 动态节头模式（生成器构造器输出形状；构造器与识别器同源，漂移 → R1 RED）
_DYNAMIC_PATTERNS = [
    re.compile(r"^C\s+Cell Cards: \d+ cells defined$", re.IGNORECASE),
    re.compile(r"^C\s+Surface Cards: \d+ surfaces defined$", re.IGNORECASE),
    re.compile(r"^C\s+Energy mesh: \d+ \w+ intervals, .+ to .+ MeV$", re.IGNORECASE),
    re.compile(r"^C\s+Energy mesh: \d+ user-defined points$", re.IGNORECASE),
    re.compile(r"^C\s+Time mesh: \d+ \w+ intervals, .+ to .+ shakes$", re.IGNORECASE),
    re.compile(r"^C\s+Time mesh: \d+ user-defined points$", re.IGNORECASE),
    re.compile(r"^C\s+SKIPPED \(not a valid [ET]n card\): .*$", re.IGNORECASE),
    re.compile(r"^C\s+\d+ sources, probability keyed to D1$", re.IGNORECASE),
]


def is_generator_banner(line: str) -> bool:
    """判断一行是否为生成器 C 注释节头（仅精确词汇，不碰用户任意 C 注释）。"""
    s = line.strip()
    if not s or not re.match(r"^C\s", s, re.IGNORECASE):
        return False
    if s.upper() in _EXACT_UPPER:
        return True
    return any(p.match(s) for p in _DYNAMIC_PATTERNS)
