"""源抽样模型层单测：`app/generator/source_spec.py`（契约 source-sampling-model.md §1/§2）。

覆盖三条硬线：

1. ``parse_var_ref`` —— C810 p.3-55 的三种形态（显式值 / ``Dn`` / ``Fvar' Dn``）都要认，
   认不出的（``fdir=x``、``F``、``D0``、空串、多 token）都要**抛错**（契约 §4 取消静默兜底）；
2. ``normalize_sdef_fields`` —— ``fdir=d2`` / ``fdir d2`` / ``FDIR=D2`` / ``erg=fdir=d2``
   四种写法归一到同一个结果，且**不就地修改**入参（纯函数）；
3. ``VAR_SPEC`` —— 覆盖 C810 Table 3.3 的全部源变量、默认值逐条对表（带页码注释）、
   每个语义值都有落在 ``ANCHOR_IDS`` 里的锚点（用户 2026-09-20 的硬要求：
   语义来源必须可机检，禁止「凭记忆的转述」）。

本文件**不触碰**抽样引擎（`source_sampler.py`）—— 引擎重写是契约的第二阶段。
"""
import ast
import inspect
import pathlib
import subprocess
import sys

import pytest

from app.generator.distributions import SourceSamplingError
from app.generator import source_spec as ss

# ────────────────────────────────────────────────────────────────────────────
# 夹具/常量
# ────────────────────────────────────────────────────────────────────────────

#: C810 Table 3.3（p.3-55 ~ p.3-57）列出的 20 个源变量 + 手册正文出现、仓库也在用的两个
#: （JSU：p.3-55 变量清单；RATE：仓库既有 sdef_rate 字段）—— 共 22 个。
#: ⚠ 二者都不在 Table 3.3 里：JSU 记「未决」，RATE 已于 2026-09-28 **定案为
#: 「C810 没有这个源变量」**（见 NOT_A_C810_VARIABLE）。
TABLE_3_3_VARS = frozenset({
    "CEL", "SUR", "ERG", "TME", "DIR", "VEC", "NRM", "POS", "RAD", "EXT",
    "AXS", "X", "Y", "Z", "CCC", "ARA", "WGT", "EFF", "PAR", "TR",
}) | frozenset({"JSU", "RATE"})

#: **有字面默认值**的变量 → (默认值, 页码注释用的锚点页)。
#: 逐条对照 C810 Table 3.3 的 Default 列原文：
#:   p.3-55  SUR(Surface)=Zero / ERG(Energy)=14 MeV / TME(Time)=0
#:   p.3-56  DIR=体源各向同性·面源余弦（不是一个数）/ VEC=面法线（面源）/ NRM=+1 /
#:           POS=0,0,0 / RAD=0 / EXT=0 / AXS=无方向 / X,Y,Z=No X/Y/Z /
#:           CCC=无 / ARA=None / WGT=1 / EFF=.01 / PAR=由 MODE 卡定 / TR=None
#: p.3-56 的 PAR 行原文：「The default is the lowest of these three that corresponds to an
#: actual or default entry on the MODE card」⇒ 不是常数，模型层记 None。
TABLE_DEFAULTS = {
    "SUR": 0.0, "ERG": 14.0, "TME": 0.0, "NRM": 1.0, "RAD": 0.0, "EXT": 0.0,
    "WGT": 1.0, "EFF": 0.01,
}

#: Table 3.3 里**没有单一数值默认**的变量（None 是「由位置/面/MODE 定」，不是「忘了填」）。
NO_SCALAR_DEFAULT = frozenset({
    "CEL", "DIR", "VEC", "POS", "AXS", "X", "Y", "Z", "CCC", "ARA", "PAR", "TR",
})

#: 手册正文有、Table 3.3 没有 ⇒ 按硬要求「不写数值，anchor=None，记未决」。
UNDECIDED_NO_ANCHOR = frozenset({"JSU"})

#: **已定案**为「C810 根本没有这个源变量」的字段（anchor=None，但不再是"未决"）。
#: RATE（2026-09-28 定案）：Table 3.3 变量列无此行，说明书全文检索 RATE 的 57 处命中
#: 全是普通英文（convergence/sampling/dose/energy loss rate）；字段只为兼容旧数据保留。
NOT_A_C810_VARIABLE = frozenset({"RATE"})

#: 「没有字面默认值」的**登记口径**：Table 3.3 说"由位置/面/MODE 定"的 12 个
#: + 正文有、表里没有的 JSU（未决）+ C810 里根本没有的 RATE（定案不实现）。
NO_LITERAL_DEFAULT = NO_SCALAR_DEFAULT | UNDECIDED_NO_ANCHOR | NOT_A_C810_VARIABLE

_SPEC_PATH = pathlib.Path(ss.__file__)


# ────────────────────────────────────────────────────────────────────────────
# 1. 模块卫生：纯 stdlib、不 import 重家伙（契约「模块顶层保持轻量」）
# ────────────────────────────────────────────────────────────────────────────

def test_module_source_imports_are_pure_stdlib():
    """模型层自己的 import 只允许 re/dataclasses/typing + 同包 distributions。

    （只按 AST 判 import，不拿全文匹配字符串 —— 文档字符串里必然会提到
    ``pymcnp`` / ``api_server`` 这些"不许 import 的东西"，按文本搜会自我误报。）
    """
    tree = ast.parse(_SPEC_PATH.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(("." * node.level) + (node.module or ""))
    allowed = {"re", "dataclasses", "typing", "from __future__", ".distributions"}
    real = [m for m in imported if m != "__future__"]
    assert set(real) <= allowed, f"模型层引入了计划外的依赖: {sorted(set(real) - allowed)}"
    assert ".distributions" in real, "SourceSamplingError 必须复用分布子系统的异常"


def test_import_does_not_pull_pymcnp_or_api_server():
    """import 模型层不得把 pymcnp / gui.backend.api_server 拉进进程。

    必须在**子进程**里查：整套 pytest 跑起来后，别的测试早把 pymcnp 装进共享的
    ``sys.modules`` 了，在进程内断言会得到与自己无关的红灯。

    （numpy 会经 `distributions` 间接进来 —— 那是分布子系统的既成事实，不是本模块的依赖；
    上面那条 AST 断言才是「本模块不 import 重家伙」的证据。）
    """
    code = (
        "import sys;"
        "sys.path.insert(0, r'" + str(_SPEC_PATH.parents[2]) + "');"
        "import app.generator.source_spec;"
        "bad=[k for k in sys.modules if k.startswith('pymcnp')"
        " or k=='gui.backend.api_server'];"
        "print(','.join(bad))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         encoding="utf-8", timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip() == "", f"import 模型层拉进了: {out.stdout.strip()}"


def test_public_interface_is_small_and_stable():
    """接口签名冻结：参数名/个数被刻意改小，防止第二阶段把引擎细节漏进模型层。"""
    assert list(inspect.signature(ss.parse_var_ref).parameters) == ["token"]
    assert list(inspect.signature(ss.normalize_sdef_fields).parameters) == ["fields"]
    assert list(inspect.signature(ss.var_field_key).parameters) == ["name"]
    assert list(inspect.signature(ss.parent_field_key).parameters) == ["parent"]
    assert issubclass(ss.SourceSamplingError, ValueError)
    # 复用的是分布子系统的异常类型，不是另立一个
    assert ss.SourceSamplingError is SourceSamplingError


# ────────────────────────────────────────────────────────────────────────────
# 2. parse_var_ref：三种形态（C810 p.3-55）
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("token,expected", [
    # ── 形态 1：显式值（手册：「explicit value」）
    ("14", {"kind": "const", "value": "14"}),
    ("0", {"kind": "const", "value": "0"}),
    ("-3.5", {"kind": "const", "value": "-3.5"}),
    (".5", {"kind": "const", "value": ".5"}),            # MCNP 允许省前导 0
    ("1e-3", {"kind": "const", "value": "1e-3"}),
    ("1-3", {"kind": "const", "value": "1-3"}),          # MCNP 隐含指数速记 ≡ 1e-3
    ("1.5-3", {"kind": "const", "value": "1.5-3"}),
    ("  14  ", {"kind": "const", "value": "14"}),        # 两侧空白
    # ── 形态 2：Dn（手册：「a distribution number prefixed by a D」）
    ("d2", {"kind": "dist", "did": 2}),
    ("D2", {"kind": "dist", "did": 2}),
    ("D1", {"kind": "dist", "did": 1}),
    (" d999 ", {"kind": "dist", "did": 999}),
    # ── 形态 3：Fvar' Dn（手册：「the name of another variable prefixed by an F, followed
    #    by a distribution number prefixed by a D」）；官方算例实测有等号连写形态
    ("FDIR D2", {"kind": "dep", "parent": "DIR", "did": 2}),
    ("fdir d2", {"kind": "dep", "parent": "DIR", "did": 2}),      # 全小写
    ("fdir=d2", {"kind": "dep", "parent": "DIR", "did": 2}),      # 等号连写
    ("FDIR=D2", {"kind": "dep", "parent": "DIR", "did": 2}),      # 等号 + 全大写
    ("fdir = d2", {"kind": "dep", "parent": "DIR", "did": 2}),    # 等号两侧带空格
    ("  FDIR   D2  ", {"kind": "dep", "parent": "DIR", "did": 2}),  # 多空白
    ("fpos d1", {"kind": "dep", "parent": "POS", "did": 1}),
    ("fjsu d3", {"kind": "dep", "parent": "JSU", "did": 3}),
])
def test_parse_var_ref_three_forms(token, expected):
    assert ss.parse_var_ref(token) == expected


@pytest.mark.parametrize("token", [
    "fdir=x",        # 父变量写了、分布号写错
    "fdir",          # 只有父变量，没有 Dn
    "F",             # 只有 F 前缀（F 后必须跟变量名）
    "F D2",          # F 后是空的变量名
    "fxx d2",        # 父变量 X 写成 xx ⇒ 表里没有
    "D0",            # 分布号 0 越界（手册：n = 1,999）
    "D1000",         # 分布号超上限
    "",              # 空串
    "   ",           # 纯空白
    None,            # 缺失值
    "=d2",           # 等号左侧空缺（半截等号不是合法形态）
    "=d2 ",          # 同上，带尾空白
    "fdir=",         # 等号右侧空缺
    "abc",           # 既不是数也不是引用
    "D1 D2",         # 多 token（不是一个值）
    "14 15",         # 多 token
    "erg=fdir=d2",   # 变量名 + 依赖连写：整行写法，不是一个值
    "D1-2",          # 拼出来的四不像
    "2D2",           # 前缀错位
])
def test_parse_var_ref_rejects_bad_values(token):
    with pytest.raises(SourceSamplingError):
        ss.parse_var_ref(token)


def test_parse_var_ref_error_messages_point_at_the_rule():
    """报错文案要指向真因（这是"取消静默兜底"的可诊断性要求，不是措辞洁癖）。"""
    with pytest.raises(SourceSamplingError, match="Fvar"):
        ss.parse_var_ref("fdir=x")
    with pytest.raises(SourceSamplingError, match="1,999"):
        ss.parse_var_ref("D0")
    with pytest.raises(SourceSamplingError, match="为空"):
        ss.parse_var_ref("")
    with pytest.raises(SourceSamplingError, match="PID"):  # 不存在的变量名
        ss.parse_var_ref("fpid d2")


# ────────────────────────────────────────────────────────────────────────────
# 3. normalize_sdef_fields：四种写法归一到同一结果、纯函数
# ────────────────────────────────────────────────────────────────────────────

NORMALIZE_VARIANTS = [
    {"sdef_erg": "fdir d2"},       # 空格小写
    {"sdef_erg": "FDIR D2"},       # 空格大写（归一后的目标形态）
    {"sdef_erg": "fdir=d2"},       # 等号连写小写
    {"sdef_erg": "FDIR=D2"},       # 等号连写大写
]


@pytest.mark.parametrize("fields", NORMALIZE_VARIANTS)
def test_normalize_sdef_fields_four_spellings_agree(fields):
    assert ss.normalize_sdef_fields(fields) == {"sdef_erg": "FDIR D2"}


def test_normalize_sdef_fields_does_not_mutate_input():
    """纯函数：入参逐字不动（调用方可能还要拿原值做别的判断）。"""
    fields = {"sdef_erg": "fdir=d2", "sdef_dir": "d1"}
    snapshot = dict(fields)
    out = ss.normalize_sdef_fields(fields)
    assert fields == snapshot, "入参被就地修改了"
    assert out is not fields
    assert out == {"sdef_erg": "FDIR D2", "sdef_dir": "d1"}


def test_normalize_sdef_fields_leaves_non_variable_keys_alone():
    """只有 SDEF 变量字段被归一；分布 JSON、extra、以及非 sdef_ 键逐字不动。"""
    fields = {
        "sdef_distributions": '[{"id": 2, "rawText": "si2 0 1"}]',
        "sdef_extra": "EFF=0.01 TR=2",
        "sdef_raw_text": "erg=fdir=d2",
        "sdefEff": "fdir=d2",          # 不是 sdef_ 前缀（驼峰）⇒ 不算变量键
        "other": "fdir=d2",
        "n": 3,
        "none": None,
        "sdef_sur": "12",              # SUR 是变量，但它的值不是依赖引用 ⇒ 原样
    }
    out = ss.normalize_sdef_fields(fields)
    assert out == fields, "不该动这些键"
    # sdef_eff 是变量字段（VAR_SPEC 有 EFF），但值不是依赖引用 ⇒ 原样
    assert ss.normalize_sdef_fields({"sdef_eff": "0.01"}) == {"sdef_eff": "0.01"}
    # 反过来：确属变量字段且值确属依赖写法 ⇒ 必须归一（不是「只认 erg」）
    assert ss.normalize_sdef_fields({"sdef_sur": "fpos d2"}) == {"sdef_sur": "FPOS D2"}


def test_normalize_sdef_fields_leaves_invalid_values_for_parse_var_ref_to_reject():
    """归一化只管"改写法"，不负责合法性判定（非法值原样留着，抽样时报错）。"""
    for bad in ("fdir=x", "F", "abc"):
        assert ss.normalize_sdef_fields({"sdef_erg": bad}) == {"sdef_erg": bad}
        with pytest.raises(SourceSamplingError):
            ss.parse_var_ref(bad)


def test_normalize_sdef_fields_covers_triplet_fields_and_preserves_key_order():
    fields = {
        "sdef_pos_x": "d1",            # X 分量引用
        "sdef_vec": "0 0 1",           # 三元组：含空格，不能被当成依赖引用
        "sdef_axs": "AXS=D1",          # AXS 不是 F 形态 ⇒ 原样
        "sdef_cel": "fcel d2",         # CEL 自己当父变量（表里没有 F CEL 的合法用法）
    }
    out = ss.normalize_sdef_fields(fields)
    assert out == {
        "sdef_pos_x": "d1",
        "sdef_vec": "0 0 1",
        "sdef_axs": "AXS=D1",
        "sdef_cel": "FCEL D2",
    }
    assert list(out) == list(fields), "键序必须保持"


def test_normalize_sdef_fields_passes_non_dict_through():
    assert ss.normalize_sdef_fields(None) is None
    assert ss.normalize_sdef_fields([1, 2]) == [1, 2]
    assert ss.normalize_sdef_fields({}) == {}


def test_normalize_output_is_accepted_by_parse_var_ref():
    """模型的往返性质：normalize 的产物必须能被 parse_var_ref 解析成 dep。

    （这正是旧实现的病根：`fdir=d2` 归一后没人能完整解析 —— 现在两个入口共用一套判定。）
    """
    for variant in NORMALIZE_VARIANTS:
        value = ss.normalize_sdef_fields(variant)["sdef_erg"]
        assert ss.parse_var_ref(value) == {"kind": "dep", "parent": "DIR", "did": 2}


def test_normalize_sdef_fields_handles_empty_and_whitespace_values():
    assert ss.normalize_sdef_fields({"sdef_erg": ""}) == {"sdef_erg": ""}
    assert ss.normalize_sdef_fields({"sdef_erg": "   "}) == {"sdef_erg": "   "}


# ────────────────────────────────────────────────────────────────────────────
# 4. VAR_SPEC：覆盖 Table 3.3、默认值对表、锚点可机检
# ────────────────────────────────────────────────────────────────────────────

def test_var_spec_covers_every_table_3_3_variable():
    assert set(ss.VAR_SPEC) == set(TABLE_3_3_VARS)
    assert len(ss.VAR_SPEC) == 22


def test_every_var_spec_declares_a_default():
    """每个变量都要显式声明 default —— 契约 §1.4：默认值只许来自 VAR_SPEC 表。

    ``None`` 是**声明过的**"没有单一数值默认"（由位置/面/MODE 定），不是漏填：
    它必须出现在 NO_LITERAL_DEFAULT（表 3.3 的 12 个 + JSU 未决 + RATE 不实现）里。
    """
    for name, spec in ss.VAR_SPEC.items():
        assert hasattr(spec, "default"), name
        assert spec.default is not None or name in NO_LITERAL_DEFAULT, (
            f"{name} 的 default 是 None，但没有登记为「无单一数值默认」")


@pytest.mark.parametrize("name,expected", [
    # C810 Table 3.3（p.3-55）：ERG / Energy (MeV) / 14 MeV
    ("ERG", 14.0),
    # C810 Table 3.3（p.3-55）：TME / Time (shakes) / 0
    ("TME", 0.0),
    # C810 Table 3.3（p.3-56）：WGT / Particle weight / 1
    ("WGT", 1.0),
    # C810 Table 3.3（p.3-56）：RAD / Radial distance of the position from POS or AXS / 0
    ("RAD", 0.0),
    # C810 Table 3.3（p.3-56）：EXT / Cell case: distance from POS along AXS / 0
    ("EXT", 0.0),
    # C810 Table 3.3（p.3-56）：DIR 默认 = 体源 µ 均匀 −1..1（各向同性）/ 面源 p(µ)=2µ
    #   ⇒ 取决于源型，不是一个数（表里就是两种取值）
    ("DIR", None),
    # C810 Table 3.3（p.3-56）：X / x-coordinate of position / No X（Y、Z 同理）
    ("X", None),
    ("Y", None),
    ("Z", None),
    # C810 Table 3.3（p.3-55）：CEL / Cell / Determined from XXX, YYY, ZZZ and possibly UUU,
    #   VVV, WWW ⇒ 由位置定
    ("CEL", None),
    # C810 Table 3.3（p.3-56）：NRM / Sign of the surface normal / + 1
    ("NRM", 1.0),
    # C810 Table 3.3（p.3-56）：EFF / Rejection efficiency criterion for position sampling / .01
    ("EFF", 0.01),
])
def test_table_3_3_defaults(name, expected):
    assert ss.VAR_SPEC[name].default == expected


def test_literal_defaults_match_the_table_map():
    """TABLE_DEFAULTS 是上一条的"全量版" —— 防止有人加了新默认值却漏了对表断言。"""
    for name, expected in TABLE_DEFAULTS.items():
        assert ss.VAR_SPEC[name].default == expected, name


def test_no_scalar_default_set_is_exactly_what_table_3_3_says():
    """None 的集合必须**恰好**等于手册能解释的那批（多一个 = 悄悄丢了默认值）。"""
    none_vars = {n for n, s in ss.VAR_SPEC.items() if s.default is None}
    assert none_vars == NO_LITERAL_DEFAULT


def test_var_spec_field_keys_point_back_to_the_variable():
    """字段键 ↔ 变量名双向可查（引擎层靠它把 SDEF 字段翻成变量）。"""
    for name, spec in ss.VAR_SPEC.items():
        if not spec.field_keys:
            continue
        assert ss.var_field_key(name) == spec.field_keys[0]
        for key in spec.field_keys:
            assert ss.parent_name_for_field_key(key) is not None
    # POS/X/Y/Z 共用三个分量字段（解析层把 POS 拆进它们）：**主键优先**，
    # 反查稳定地给 X/Y/Z；POS 自身用正向查（否则字典顺序一变结果就漂）。
    assert ss.VAR_SPEC["POS"].field_keys == ("sdef_pos_x", "sdef_pos_y", "sdef_pos_z")
    assert ss.VAR_SPEC["X"].field_keys == ("sdef_pos_x",)
    assert ss.var_field_key("POS") == "sdef_pos_x"
    assert ss.var_for_field_key("sdef_pos_x") == "X"
    assert ss.var_for_field_key("sdef_pos_z") == "Z"
    assert ss.var_for_field_key("sdef_erg") == "ERG"
    assert ss.var_for_field_key("SDEF_ERG") == "ERG"      # 键名大小写不敏感
    # JSU 只在手册正文出现，没有 SDEF 字段键 ⇒ 正向查要报错（不是给个假键）
    assert ss.VAR_SPEC["JSU"].field_keys == ()
    with pytest.raises(SourceSamplingError):
        ss.var_field_key("JSU")


def test_field_key_helpers_reject_non_variable_keys():
    for key in ("sdef_distributions", "sdef_extra", "sdef_raw_text", "sdef_effx", "erg"):
        with pytest.raises(SourceSamplingError):
            ss.var_for_field_key(key)
        assert ss.parent_name_for_field_key(key) is None


def test_parent_field_key_maps_dependency_parents():
    assert ss.parent_field_key("POS") == "sdef_pos_x"
    assert ss.parent_field_key("pos") == "sdef_pos_x"
    assert ss.parent_field_key("DIR") == "sdef_dir"
    # JSU 在 SDEF 卡上以 SUR 表达（C810 p.3-55：JSU = 粒子起始所在的曲面号）
    assert ss.parent_field_key("JSU") == "sdef_sur"
    # 不是变量 ⇒ None（由调用方给出带上下文的报错）
    assert ss.parent_field_key("PID") is None
    assert ss.parent_field_key("") is None


def test_spec_for_rejects_unknown_variables():
    assert ss.spec_for("erg") is ss.VAR_SPEC["ERG"]
    with pytest.raises(SourceSamplingError):
        ss.spec_for("PID")
    with pytest.raises(SourceSamplingError):
        ss.spec_for("")


def test_builtins_declared_per_table_3_4():
    """内置函数配对（Table 3.4，p.3-65~3-66）：函数只能用在表里指定的变量上。"""
    # 能量谱 −2..−6（−7 是 spare，契约 §6 显式不支持）
    assert set(ss.builtins_for("ERG")) == {"-2", "-3", "-4", "-5", "-6", "-7"}
    assert ss.builtins_for("DIR") == ("-21", "-31")
    assert ss.builtins_for("EXT") == ("-21", "-31")
    assert ss.builtins_for("RAD") == ("-21",)
    assert ss.builtins_for("TME") == ("-41",)
    for axis in ("X", "Y", "Z"):
        assert ss.builtins_for(axis) == ("-41",)
    # 表里没列的变量不能带内置函数
    for name in ("SUR", "CEL", "VEC", "AXS", "NRM", "CCC", "ARA", "WGT", "EFF", "PAR", "TR"):
        assert ss.builtins_for(name) == (), name
    # −31 不在 Table 3.4 的 RAD 行里（RAD 只有 −21）
    assert "-31" not in ss.builtins_for("RAD")
    with pytest.raises(SourceSamplingError):
        ss.builtins_for("PID")


def test_dep_parent_candidates_cover_documented_dependencies():
    """能当依赖父（Fvar' Dn 的 var'）的变量必须是被文档点过名的那些。"""
    assert set(ss.DEP_PARENT_NAMES) == {"CEL", "SUR", "ERG", "TME", "VEC", "RAD", "EXT", "WGT"}
    for name in ss.DEP_PARENT_NAMES:
        assert ss.VAR_SPEC[name].parents, name
    # 官方算例用到的两个父（POS / DIR）都在候选里（POS=Dn 多点源 / ERG=FDIR D2）
    assert "DIR" in ss.VAR_SPEC["ERG"].parents
    assert "POS" in ss.VAR_SPEC["ERG"].parents
    # 笛卡尔位置源：CEL/SUR 让 X/Y/Z 当父（`X=Dn` 那类写法里的依赖方向）
    assert {"X", "Y", "Z"} <= set(ss.VAR_SPEC["CEL"].parents)
    assert "POS" in ss.VAR_SPEC["SUR"].parents
    # 不能当父的变量
    assert "EFF" not in ss.DEP_PARENT_NAMES and "PAR" not in ss.DEP_PARENT_NAMES


def test_every_semantic_value_has_a_page_reference_and_notes():
    """每个变量都要有人读页码 + 机检锚点（或明确记为未决 / 明确记为"手册没这个变量"）。"""
    for name, spec in ss.VAR_SPEC.items():
        assert spec.source_page.startswith("C810") or spec.source_page.startswith("未在 C810"), name
        if name in UNDECIDED_NO_ANCHOR:
            assert spec.anchor is None
            assert "未决" in spec.notes, name
        elif name in NOT_A_C810_VARIABLE:
            # 定案：手册里没有这个源变量 ⇒ 不写数值、不实现；notes 要说清依据，
            # 且**不许**再挂"未决"（未决会让下一个人以为还能等锚点表给答案）。
            assert spec.anchor is None
            assert "C810" in spec.notes and "未决" not in spec.notes, name
        else:
            assert spec.anchor == "#C810-3-56-TABLE-3-3", name


# ────────────────────────────────────────────────────────────────────────────
# 5. 锚点表：语义来源可机检（用户 2026-09-20 硬要求）
# ────────────────────────────────────────────────────────────────────────────

def test_anchor_ids_is_a_frozen_set_of_wellformed_ids():
    assert isinstance(ss.ANCHOR_IDS, frozenset)
    # 22 = 18 条 SDEF/分布家族锚点 + 2 条 TR 变换卡锚点（3-30 的 M、3-31 的 B 矩阵模式）
    #      + 1 条 CEL 层级路径锚点（3-60，登记"本程序未实现"这一差异的出处）+ 1 条 PAR 表尾正文锚点（3-56，4/F = 正电子与"不许分布"的出处）。
    # 改这里的数字前，先确认 docs/authority/c810-sdef.md 与 tools/c810_extract.py 同步改了
    # （tests/unit/test_c810_anchors.py 的冻结清单是第三处，三处一起改才绿）。
    assert len(ss.ANCHOR_IDS) == 22
    for anchor in ss.ANCHOR_IDS:
        # 形态 `#C810-<印刷页>-<TAG>`：`3-55` / `3-4` / `3-66` 这样的印刷页 + 大写 TAG
        body = anchor.removeprefix("#C810-")
        assert body != anchor, anchor
        page, _, tag = body.partition("-")
        assert page == "3", anchor
        assert tag and tag == tag.upper(), anchor
        assert anchor.count("#") == 1 and " " not in anchor


def test_every_used_anchor_is_in_the_anchor_table():
    """硬要求：VAR_SPEC 里用到的每个 anchor 都必须在 ANCHOR_IDS 里。"""
    used = ss.anchors_used()
    assert used, "一个锚点都没用上"
    assert used <= ss.ANCHOR_IDS, f"锚点表里没有: {sorted(used - ss.ANCHOR_IDS)}"


def test_anchors_used_excludes_undecided_entries():
    used = ss.anchors_used()
    assert None not in used
    assert "#C810-3-56-TABLE-3-3" in used


def test_anchor_less_entries_are_exactly_the_known_ones():
    """没有锚点的变量必须**显式**登记：JSU（未决，待锚点表给答案）
    + RATE（已定案"手册没这个变量"，不留待办）。多一个 = 有人加了变量却没给出处。"""
    assert {n for n, s in ss.VAR_SPEC.items() if s.anchor is None} == (
        UNDECIDED_NO_ANCHOR | NOT_A_C810_VARIABLE)


def test_anchor_table_contains_the_distribution_family_tags():
    """锚点表要覆盖契约 §1.2/§1.3 的分布家族（第二阶段引擎层会逐条引用）。"""
    for tag in (
        "#C810-3-55-VAR-FORMS", "#C810-3-55-SAMPLING-ORDER", "#C810-3-55-ONE-LEVEL",
        "#C810-3-56-TABLE-3-3", "#C810-3-63-SI-OPTIONS", "#C810-3-63-SP-OPTIONS",
        "#C810-3-63-H-FIRST-ZERO", "#C810-3-64-BUILTIN-FORM", "#C810-3-64-SB-RULES",
        "#C810-3-64-SI-S", "#C810-3-64-SP-V", "#C810-3-65-TABLE-3-4",
        "#C810-3-66-BUILTIN-VARS", "#C810-3-66-TRUNC-WEIGHT",
        "#C810-3-66-SPECIAL-DEFAULTS", "#C810-3-66-DS-CARD",
        "#C810-3-4-COMMENTS", "#C810-3-4-CONTINUATION",
    ):
        assert tag in ss.ANCHOR_IDS, tag
