"""source_sampler — SDEF 源粒子抽样编排（契约 `docs/contracts/source-sampling-model.md` 的引擎层）。

接口（小接口 + 深实现，契约 §0 对外不变量）::

    sample_source(sdef_fields, distributions, geometry=None, *, n_particles=500, seed=None) -> dict

返回 ``{"status","particles","energyRange","bounds"}``，粒子字段
``id,x,y,z,dx,dy,dz,energy,weight,particle`` 逐字不变（前端与 `api_server` 零改动）。
本引擎**只算起始状态**：位置、方向、能量、权重、粒子类型；不做输运/tally/时间轴。

## 为什么重写成「单一模型」

旧实现把**同一个语义**散在四处 —— ``_erg``（能量形态判定）/ ``_direction``（方向形态判定）/
``_radial_value``+``_axial_value``+``_default_power_law``（RAD/EXT 的量纲与默认幂律），
于是任何新写法都只在其中一路被支持（``fdir=d2`` 只在 ERG、``sp3 d -21 1`` 只在 SP），
而认不出时**静默兜底**（``_num(v, 14.0)``）⇒ 缺陷长得像"跑得对"（契约开头记的三算例教训）。

现在照 C810 的模型做，只有一条路径：

* **变量形态只有三种**（C810 p.3-55，锚点 ``#C810-3-55-VAR-FORMS``）::

      变量 = 显式值 | Dn | Fvar′ Dn

  三种形态的解析归 ``source_spec.parse_var_ref``（模型层，本模块不重复实现），
  取值归 ``_Engine._resolve`` —— **所有变量共用同一份**；认不出即抛
  ``SourceSamplingError``（契约 §4），不再有任何"取个默认值接着跑"的分支。
* **默认值只来自 ``source_spec.VAR_SPEC``**（C810 Table 3.3，锚点 ``#C810-3-56-TABLE-3-3``）；
  引擎里不再出现字面默认值。
* **抽样顺序**由**抽样层 + 少量硬依赖**决定（契约 §2 的 ``_order()``，见 ``_TIERS``/``_DEPENDENCIES``）：
  位置类（CEL/SUR/POS/X/Y/Z + AXS/VEC/RAD/EXT）先于 ``DIR``（C810 p.3-55 要求依赖变量
  必须在父变量之后抽样，锚点 ``#C810-3-55-SAMPLING-ORDER``；``DIR`` 的默认分布又依赖
  "是不是面源"这一位置层结论），``DIR`` 先于 ``ERG``（``ERG=FDIR Dn``）。

位置是**组合语义**（契约 §3），不是"一变量一值"：``SUR`` / ``POS+RAD+EXT+AXS`` / ``CEL`` /
``X-Y-Z`` 由 ``_Engine._position`` 分派，几何算法沿用既有的 ``_GeometryHelper``
（CEL 拒绝采样 + EFF 判据 / 面源平面-球面-椭球面 + NRM / 二次曲面面源，
已在 C810 上验过且是纯几何，本次重构**不动其算法**），只把 **RAD/EXT 的取值入口**
换成走通用引擎（``Dn`` / 内置函数 / 无 SP 时的默认幂律）。

权重（界面 WGT 列，契约 §0）＝ ``SDEF WGT`` 基值 × 本次抽样路径上所有补偿之积；
补偿由 ``DistributionSampler.sample_with_corrections`` 返回（SB 偏倚 C810 p.3-64
锚点 ``#C810-3-64-SB-RULES``、内置函数被 SI 截断 C810 p.3-66 锚点 ``#C810-3-66-TRUNC-WEIGHT``）。
"""

from __future__ import annotations

import heapq
import math
import random
import re

from .distributions import DistributionSampler, SourceSamplingError, _pick
from .source_spec import (
    VAR_SPEC,
    normalize_sdef_fields,
    parse_var_ref,
    spec_for,
)

# PAR → 渲染分组（与前端 trackColors.ts 的 particleGroup 对齐）
_PAR_GROUP = {
    "1": "n", "n": "n", "2": "p", "p": "p", "3": "e", "e": "e",
    "h": "h", "a": "a", "s": "s",
}

#: SDEF 字段字典里**不是源变量**的键：解析侧的第二类载荷。
#: 判定口径与 `source_spec.var_for_field_key` 的分工是——那边认"变量字段"，
#: 这边认"允许共存在同一字典里的非变量键"；两边都不认的 ``sdef_*`` 键一律报错
#: （契约 §4：认不出就说，别静默丢掉 —— 旧实现把未知字段整体忽略）。
_NON_VARIABLE_FIELDS = frozenset({
    "sdef_distributions",   # 结构化 SI/SP/SB/DS JSON（分布侧的权威载荷）
    "sdef_extra",           # 解析侧把未识别参数累加到这里（如 EFF=…）
})

#: VAR_SPEC 里有声明、但本引擎**尚未实现**的源变量（Table 3.3 有它，位置/方向层没做）。
#: 非空时必须**明确报错**而不是静默忽略：CCC 是 cookie-cutter（C810 p.3-58/3-59
#: 「positions are sampled only within the cookie-cutter cell」，会改变位置语义），
#: ARA 只服务于点探测器的直接贡献（p.3-56），本引擎不算 tally ⇒ 认了它也没意义。
_UNSUPPORTED_VARS = {
    "CCC": "cookie-cutter 栅元（C810 p.3-58/3-59：位置必须限制在裁剪栅元内）",
    "ARA": "面源面积（C810 Table 3.3 p.3-56：只用于点探测器的直接贡献，本引擎不算 tally）",
    "RATE": "RATE（未在 C810 Table 3.3 的印刷行中找到；Table 3.3 的默认值清单不含它）",
}


#: **抽样层**（层内固定次序、层间的硬依赖由 ``_DEPENDENCIES`` 声明）。
#:
#: 为什么用「层 + 少量硬依赖」而不是稠密的"变量→变量"拓扑：C810 Table 3.3 的变量之间
#: 大多是**并列**关系（``CEL``/``SUR``/``POS``/``RAD``/``EXT``/``AXS`` 谁先谁后都不违反
#: 手册），只有少数几条真的必须先后（见 ``_DEPENDENCIES``）。把并列关系写成依赖会造出
#: 环（``CEL.parents`` 含 POS，而 POS 的球/柱取样又确实要在 CEL 之前），层表让"没有依赖"
#: 这件事显式可见。
_TIERS: tuple[tuple[str, ...], ...] = (
    # 位置层：源型选择与位置组合语义（契约 §3）
    ("POS", "X", "Y", "Z", "CEL", "SUR", "RAD", "EXT", "AXS"),
    # 方向层：DIR 的**默认分布**取决于"是不是面源"（位置层结论），必须在其后
    ("DIR", "VEC"),
    # 能量层：ERG 可依赖 DIR（`ERG=FDIR Dn`）
    ("ERG",),
    # 独立层：不依赖上面任何一个（PAR 由 MODE 卡定，取值与位置/方向无关）
    ("TME", "WGT", "NRM", "EFF", "PAR"),
)

#: 抽样依赖：``边 = (先抽的变量, 后抽的变量)`` —— 只钉**手册/契约明写**的那几条。
#:
#: ⚠ 为什么不用 ``VAR_SPEC[*].parents`` 直接当边：那个字段存的是
#: **「变量 v 能作为谁的依赖父」候选集**（C810 p.3-55 ``Fvar′ Dn`` 的 var′ 候选），
#: 反过来当"v 依赖 parents 里的每个变量"会立刻造出环（CEL 的 parents 含 POS）。
_DEPENDENCIES: tuple[tuple[str, str], ...] = (
    # C810 p.3-56：「Radial distance **from POS or AXS**」「distance from POS along AXS」
    ("POS", "RAD"),
    ("POS", "EXT"),
    # DIR = 「µ, the cosine of the angle between VEC and UUU,VVV,WWW」（p.3-56）⇒ VEC 先定
    ("VEC", "DIR"),
    # DIR 的缺省 VEC = **面法线**（Table 3.3 的 VEC 行）⇒ AXS/面法线要先有
    ("AXS", "DIR"),
    # C810 p.3-55：「Each dependent variable must be sampled **after** the variable it
    # depends on」（锚点 #C810-3-55-SAMPLING-ORDER）——``ERG=FDIR Dn`` 是官方两算例的写法
    ("DIR", "ERG"),
)


def _tier_order() -> list[str]:
    """层表 → 层内保持 ``VAR_SPEC`` 声明序的扁平顺序（只用于遍历，不做拓扑）。

    ⚠ ``_TIERS`` 只覆盖**引擎真正会抽的**变量：``CCC``/``ARA``/``RATE`` 未实现（给了值
    由 ``_Engine._reject_unsupported`` 明确报错），``JSU`` 在 SDEF 卡上没有字段键
    （以 ``SUR`` 表达，锚点 ``#C810-3-55-VAR-FORMS``）—— 它们不进层表，
    也不参与抽样序。
    """
    out: list[str] = []
    for tier in _TIERS:
        for name in tier:
            if name not in VAR_SPEC:
                raise SourceSamplingError(
                    f"抽样层表引用了 C810 Table 3.3 里没有的变量 {name!r}"
                    "（模型层 VAR_SPEC 与引擎不一致）")
            out.append(name)
    if len(set(out)) != len(out):
        raise SourceSamplingError("抽样层表里有变量被登记了两次（层内/层间重复）")
    return out


def _scalar(text, var: str, eid=None) -> float:
    """显式值 token → 浮点；认不出就抛错（契约 §4 / 锚点 ``#C810-3-55-VAR-FORMS``）。

    MCNP 的浮点项允许**符号代替 E** 的隐含指数（``1-3`` ≡ ``1e-3``）——
    `source_spec.parse_var_ref` 认可这种写法，这里必须跟上，否则"解析层放行、
    引擎层崩"（旧实现用 ``float()`` 直接在 `1-3` 上抛 ValueError，
    又被 ``_num`` 静默吃成默认值）。
    """
    s = str(text or "").strip()
    try:
        return float(s)
    except (TypeError, ValueError):
        pass
    # 隐含指数：末段是带符号整数且整个 token 还能被读成 MCNP 数（`1-3` / `1.5+2`）
    m = re.fullmatch(r"([+-]?(?:\d+\.?\d*|\.\d+))([+-]\d+)", s)
    if m:
        try:
            return float(f"{m.group(1)}e{m.group(2)}")
        except ValueError:
            pass
    where = f"（来自分布 D{eid}）" if eid is not None else ""
    raise SourceSamplingError(
        f"源变量 {var} 的值 {s!r}{where} 不能解析为数值：C810 p.3-55 的三种形态里，"
        "显式值必须是数值，Dn / Fvar′ Dn 形式请按分布写法给出"
        "（锚点 #C810-3-55-VAR-FORMS）")


class _Engine:
    """一次 ``sample_source`` 调用的状态机（契约 §2 的 ``_Engine``）。

    生命周期：构造（归一化字段 + 定抽样序）→ 逐粒子 ``sample_one``。
    所有"值从哪来"的问题都走一条路径：``_resolve``。
    """

    def __init__(self, fields: dict, sampler: DistributionSampler, geometry=None):
        # 归一化交给模型层（``fdir=d2`` / ``fdir d2`` / ``FDIR=D2`` → ``FDIR D2``）：
        # 引擎侧不再自己认"F 打头"的写法（旧 `_erg_parent` 就是这么散的）。
        self.f = normalize_sdef_fields(dict(fields or {}))
        self.s = sampler
        self.geometry = geometry or {}
        self.rng: random.Random | None = None
        # 本次抽样（= 本粒子）的取值缓存；`sample_one` 每个粒子清空一次。
        # 键 = 变量名，值 = `_resolve` 的 `(值, 父值索引)` —— 同一个变量的第二次询问
        # 必须拿到**同一个**抽样结果（重复抽会打乱 RNG 流，也会让"同一粒子"自相矛盾）。
        self.vals: dict[str, float] = {}
        self._cache: dict[str, tuple[float, int | None]] = {}
        # 已经被**真正抽过**的变量（消费过随机数）——`Fvar′ Dn` 的父值必须来自这里，
        # 否则就是"依赖值缺失"（契约 §4）。
        self.sampled: set[str] = set()
        # 本粒子的权重补偿累加器：{变量名 → 补偿因子}，最后累乘进 WGT。
        self.corr: dict[str, float] = {}
        # 位置层的副产品：面源法线（带 NRM 符号）；非面源为 None
        self.surface_normal: tuple | None = None
        # 本次抽样是否为栅元源（`SP V` 的合法性判定用；C810 p.3-64 锚点 #C810-3-64-SP-V）
        self.cel_source = False
        # 最近一次方向抽样的 μ（相对 VEC/参考轴）——`ERG=FDIR Dn` 的父值
        self.last_mu: float | None = None
        # 几何判定器（惰性构造，只在 CEL/SUR 路径上需要）
        self._geom_helper: _GeometryHelper | None = None
        # 值得提醒但不致命的情形（如 DIR=Dn 但没有参考轴 ⇒ 按各向同性处理）。
        # 只挂在返回字典的附加键上，**不动**粒子字段（契约 §0）。
        self.warnings: list[str] = []
        self._check_field_keys()
        self._order = self._sampling_order()
        self._validate_specs()

    # ── 字段卫生 ─────────────────────────────────────────────
    #: 三元组变量（C810 Table 3.3）：值含空格，**不能**交给 ``parse_var_ref``
    #: 当单个变量值解析（那是 p.3-55 的三种形态判定，只面向单值变量）。
    _VECTOR_VARS = frozenset({"POS", "VEC", "AXS"})

    def _validate_specs(self) -> None:
        """**抽样前**按 ``_order`` 走一遍：凡是卡上已写出的**单值**变量先把形态判掉。

        为什么要有这一遍（契约 §4）：抽样是惰性的 —— 引擎只取"这一路用得到的"变量，
        所以 ``SDEF DIR=abc``（写法错）这类**必然错**的声明，如果只在该变量被用到时才报，
        就会表现为"换个写法才报错"的随机可诊断性。这里把"单值变量的形态非法"
        提到抽样之前 —— 只判常量形态，不消费任何随机数（分布形态照旧留到真正抽样时）。

        三元组变量（POS/VEC/AXS）在这里只按**字面三分量**校验：分量式分布
        （``POS=D1 D1 D1``）是另一条合法写法，由抽样路径专门处理
        （多点源 ``POS=Dn`` / 笛卡尔 X-Y-Z）；SDEF 卡上没有字段键的中间量
        （JSU，以 SUR 表达）跳过，由 ``_resolve`` 在依赖缺父值时兜住。
        """
        for var in self._order:
            if var in self._VECTOR_VARS:
                raw = self._raw(var)
                if raw and not re.search(r"(?i)\bd\d+\b", raw):
                    self._vec(var)
                continue
            if not spec_for(var).field_keys:
                continue
            raw = self._field(var)
            if not raw:
                continue
            ref = parse_var_ref(raw)
            if ref["kind"] == "const":
                _scalar(ref["value"], var)
            # 依赖形态（Fvar′ Dn）的父值是否到位，要等抽样时才判得准：父变量既可能是
            # 引擎统一登记的（POS 的多点档位），也可能是 SDEF 上以 SUR 表达的 JSU
            # （p.3-55：JSU = 粒子起始所在的曲面号）——静态时没有字段不等于运行时不成立，
            # 由 `_resolve` 的"父值缺失即报错"兜住（契约 §4）。

    # ── 抽样序（契约 §2 的 _order）──────────────────────────
    def _check_field_keys(self) -> None:
        """SDEF 字段字典里的每个 ``sdef_*`` 键都必须是「源变量」或已知的非变量载荷。

        旧实现对此完全沉默：多写一个 ``sdef_ergx=14`` 会被当成"没给 ERG"而静默用默认值，
        拼错的字段名就这样消失（契约 §4 要的就是这类错误浮出来）。
        """
        for key in self.f:
            text = str(key)
            if text in _NON_VARIABLE_FIELDS:
                continue
            if any(text in spec.field_keys for spec in VAR_SPEC.values()):
                continue
            if text.startswith("sdef_"):
                known = sorted({k for s in VAR_SPEC.values() for k in s.field_keys})
                raise SourceSamplingError(
                    f"SDEF 字段 {text!r} 不是源变量字段（C810 Table 3.3 里没有它）——"
                    f"合法字段：{'、'.join(known)}；"
                    "分布与其它载荷请放 sdef_distributions / sdef_extra")

    # ── 抽样序（契约 §2 的 _order）──────────────────────────
    def _sampling_order(self) -> list[str]:
        """抽样顺序 = **层序** + 层间硬依赖的拓扑修正（C810 p.3-55，契约 §2 的 ``_order()``）。

        做法：以 ``_TIERS`` 的扁平顺序为初始序，对 ``_DEPENDENCIES`` 声明的每条边做
        稳定拓扑排序（Kahn，平局取初始序靠前者）。于是

        * 没有依赖关系的变量保持层内固定次序（可复现，与字典遍历顺序无关）；
        * 真有依赖的（``VEC → DIR``、``DIR → ERG``、``POS → RAD/EXT``）被排到父之后。

        **环检测保留**（契约 §4：认不出就报错、不许猜）：一旦拓扑排不完就抛
        ``SourceSamplingError`` 并点名卡住的变量 —— 这条是给"以后有人往依赖表里加了
        新边"准备的护栏。
        """
        order = _tier_order()
        rank = {name: i for i, name in enumerate(order)}
        predecessors: dict[str, set[str]] = {name: set() for name in order}
        edges: dict[str, list[str]] = {name: [] for name in order}
        for first, second in _DEPENDENCIES:
            for name in (first, second):
                if name not in predecessors:
                    raise SourceSamplingError(
                        f"抽样依赖表引用了未登记的变量 {name!r}"
                        "（必须同时出现在抽样层表 _TIERS 里）")
            if second not in edges[first]:
                edges[first].append(second)
                predecessors[second].add(first)

        heap = [(rank[n], n) for n in order if not predecessors[n]]
        heapq.heapify(heap)
        out: list[str] = []
        while heap:
            _, name = heapq.heappop(heap)
            out.append(name)
            for child in edges[name]:
                predecessors[child].discard(name)
                if not predecessors[child]:
                    heapq.heappush(heap, (rank[child], child))
        if len(out) != len(order):
            stuck = sorted((n for n in order if n not in out), key=rank.get)
            raise SourceSamplingError(
                f"源变量的依赖关系成环，无法确定抽样顺序：{stuck}"
                "（C810 p.3-55：依赖变量必须在父变量之后抽样）")
        return out

    # ── 字段读取 ─────────────────────────────────────────────
    def _field(self, var: str) -> str:
        """变量名 → SDEF 字段原文（**主键**；POS 之类多分量变量取第一个分量字段）。

        这里不做任何默认值填充 —— "没给"与"给了 0"是两件事（Table 3.3 的
        ``No X`` 就明确是"未给"）。
        """
        spec = spec_for(var)
        if not spec.field_keys:
            raise SourceSamplingError(f"源变量 {spec.name} 在 SDEF 卡上没有对应字段")
        return str(self.f.get(spec.field_keys[0]) or "").strip()

    def _vec(self, var: str) -> tuple:
        """三元组变量（VEC/AXS/POS）→ ``(x,y,z)``；分量缺省 = 0（C810 p.3-57 的 POS 语义）。

        三种写法都要认，且判定口径与 `source_spec.parse_var_ref` 一致：

        * ``0 0 1``：三分量字面值（官方算例的常见写法）；
        * ``1``：只有一个分量 ⇒ ``(1,0,0)``（MCNP 的缺省补 0）；
        * ``Dn``：矢量分布（手册把 ``VEC``/``AXS`` 写成分量式，Dn 形态实测罕见）⇒
          **明确报错**而不是把 ``D1`` 当数值硬转（契约 §4；静默给 0 向量会让方向语义
          整体走样）。
        """
        raw = self._raw(var)
        if not raw:
            return ()
        toks = raw.replace(",", " ").replace("=", " ").split()
        for tok in toks:
            if re.fullmatch(r"[Dd]\d+", tok):
                raise SourceSamplingError(
                    f"SDEF {var}={raw!r}：矢量变量用分布（Dn）取值本引擎尚未实现 —— "
                    "C810 p.3-55 的三种形态是针对**单值变量**定义的；"
                    "请给出三分量字面值（如 `VEC=0 0 1`）或改用固定方向 DIR")
        spec = spec_for(var)
        if len(toks) > 3:
            raise SourceSamplingError(
                f"SDEF {var}={raw!r} 给了 {len(toks)} 个分量：矢量变量的分量数是 3"
                f"（{var} 的字段：{'、'.join(spec.field_keys) or '（无）'}）")
        # 分量缺省补 0（MCNP 的 VEC/AXS 允许省略后两个分量）⇒ 统一成三元组
        vals = [_scalar(t, var) for t in toks]
        return tuple(vals + [0.0] * (3 - len(vals)))

    def _field_for_key(self, key: str) -> str:
        return str(self.f.get(key) or "").strip()

    def _raw(self, var: str) -> str:
        """变量在 SDEF 上的**完整原文**（多分量变量把所有分量字段拼起来）。

        三元组变量（``POS``/``VEC``/``AXS``）在字段字典里被拆成 ``sdef_pos_x/y/z``，
        所以"这个变量写没写"必须看**全部分量**，不能只看主键：``VEC=0 0 1`` 的主键
        ``sdef_vec`` 是整串（单键），而 ``POS=1 2 3`` 是三个键、只看 ``sdef_pos_x``
        会在 ``POS= 2 3``（缺 X）时误判为"没写"。
        """
        spec = spec_for(var)
        keys = spec.field_keys or ()
        parts = [self._field_for_key(k) for k in keys]
        return " ".join(p for p in parts if p).strip()

    def _has(self, var: str) -> bool:
        """变量是否在 SDEF 上**写出来了**（"没给"与"给了 0"是两件事）。"""
        return bool(self._raw(var))

    def _axs_defined(self) -> bool:
        """``AXS`` 是否定义 —— 它决定 ``SP −21`` 在 RAD 上的默认 a（2 还是 1，C810 p.3-66）。

        手册原文是「For RAD, a = 2, **unless AXS is defined or JSU ≠ 0**」。本引擎里
        ``JSU`` 没有 SDEF 字段（以 ``SUR`` 表达，见 ``_UNSUPPORTED_VARS`` 的说明）：
        面源（``SUR`` 非 0）的粒子就起始在曲面上 ⇒ ``JSU ≠ 0`` 成立，同样要取 a=1。
        """
        return self._has("AXS") or bool(self._field("SUR") and self._field("SUR") != "0")

    def _power_arg(self) -> tuple:
        """传给 ``DistributionSampler`` 的 ``(cel, axs)``。

        - ``cel``：源是不是栅元源（决定 ``SP V`` 是否合法，C810 p.3-64）；
        - ``axs``：``AXS`` 是否定义或 ``JSU ≠ 0``（决定 ``SP −21`` 在 RAD 上的
          默认 a：2→1，C810 p.3-66 锚点 ``#C810-3-66-SPECIAL-DEFAULTS``）。
        """
        return (self.cel_source, self._axs_defined())

    # ── 分布抽样（唯一入口）─────────────────────────────────
    def _smp(self, did: int, var: str, cel=None, axs=None) -> float:
        """从分布 ``D{did}`` 抽一个标量，并把权重补偿并入本粒子的 ``corr``。

        为什么每个变量都要传 ``var``：``sample_with_corrections`` 靠它做三件 MCNP 语义 ——
        ``SP V`` 的合法性、内置函数在 SI 单值下的对称默认（p.3-66 规则 3/4/5）、
        ``SP −21`` 不给 a 时的变量默认值。旧实现里 ``X/Y/Z/TR`` 这些变量抽样时
        **不传 var**，于是它们的内置函数与默认幂律全是错的。
        """
        if cel is None:
            cel = self.cel_source
        if axs is None:
            axs = self._axs_defined()
        val, corr = self.s.sample_with_corrections(
            did, self.rng, var=var, cel=cel, axs=axs,
            sdef_fields=self.f, cell_volumes=self.cell_volumes)
        self.corr[var] = self.corr.get(var, 1.0) * corr
        return float(val)

    @property
    def cell_volumes(self) -> dict:
        """几何层给的 ``{栅元号: 体积}``（供 ``SP V``；拿不到就是空字典）。"""
        return (self.geometry or {}).get("cellVolumes") or {}

    # ── 通用取值（契约 §2 的 _resolve）──────────────────────
    def _resolve(self, var: str) -> tuple[float, int | None]:
        """变量取值 —— **所有变量共用这一份**，实现 C810 p.3-55 的三种形态。

        返回 ``(值, 父值索引)``：
        ``索引`` 只在「父变量是一个离散列表/分箱分布」时有值（``POS=Dn`` 多点源、
        ``DIR=Dn`` 的 μ 档位），供 ``ERG=FPOS/FDIR Dn`` 的 DS 查表用；其余为 ``None``。

        形态处理（锚点 ``#C810-3-55-VAR-FORMS``）：

        * ``显式值`` → 数值；**认不出即报错**（旧实现 ``_num(v, 14.0)`` 静默给 14 MeV）；
        * ``Dn`` → 分布 n 抽值（``SI S`` 递归到子分布时补偿沿路径相乘）；
        * ``Fvar′ Dn`` → 分布 n 的取值取决于父变量 var′ 的抽样值 ⇒ 走
          ``DistributionSampler.resolve_ds``（DS 卡 H/L/S/T/Q，锚点 ``#C810-3-66-DS-CARD``）。

        合同（p.3-55，锚点 ``#C810-3-55-ONE-LEVEL``）：「Only one level of dependence is
        allowed」「Each distribution may be used for only one source variable」
        「Each dependent variable must be sampled after the variable it depends on」。
        这三条在本函数里都有对应的硬检查。
        """
        if var in self._cache:
            return self._cache[var]
        result = self._resolve_uncached(var)
        self._cache[var] = result
        return result

    def _resolve_uncached(self, var: str) -> tuple[float, int | None]:
        """``_resolve`` 的实体（缓存外壳见上；分离只为让缓存口径一眼可见）。"""
        raw = self._field(var)
        if not raw:
            spec = spec_for(var)
            if spec.default is None:
                raise SourceSamplingError(
                    f"源变量 {var} 未给值，且 C810 Table 3.3（p.3-55~3-57）没有它的单一数值"
                    f"默认（{spec.notes or '由位置/面/MODE 定'}）⇒ 无法取值，请显式给出"
                    "（锚点 #C810-3-56-TABLE-3-3）")
            return float(spec.default), None
        ref = parse_var_ref(raw)
        kind = ref["kind"]
        if kind == "const":
            return _scalar(ref["value"], var), None
        if kind == "dist":
            return self._sample_dist(ref["did"], var)
        if kind != "dep":
            raise SourceSamplingError(f"源变量 {var} 的取值形态 {kind!r} 不受支持")
        # ── Fvar′ Dn：父变量必须先抽过 ──────────────────────
        parent = ref["parent"]
        if parent not in self.vals:
            raise SourceSamplingError(
                f"SDEF {var} 写成依赖形态 {raw!r}，但父变量 {parent} 本次没有被抽样"
                "（C810 p.3-55：每个依赖变量都必须在它的父变量之后抽样，"
                "且父变量本身必须是这一路会抽的源变量）")
        if parent not in self.sampled:
            raise SourceSamplingError(
                f"SDEF {var} 依赖的父变量 {parent} 本次是**常量**（没有分布），"
                "无法为 DS 卡提供取值依据（C810 p.3-55 的依赖形态要求父变量由分布抽样）")
        resolved = self.s.resolve_ds(ref["did"], float(self.vals[parent]),
                                     self._parent_si(parent))
        return self._ds_value(resolved, var, ref["did"])

    def _sample_dist(self, did: int, var: str, axs=None) -> tuple[float, int | None]:
        """``Dn`` 形态：从分布抽值，并给出"父值索引"（离散档位）。

        索引口径（旧实现只对 POS/DIR 各写一套，现在统一）：
        ``SI L`` → 档位下标；``SI H/A`` 等其他类型 → 用分布**自身的编码**去
        ``DistributionSampler.weight_factor`` 反查档位（H 型靠箱边界、A 型靠密度点），
        查不到就给 ``None``（下游 ``ERG=FPOS Dn`` 会因此拿到明确错误而不是 0）。
        """
        # 「一个分布只能服务一个变量」（p.3-55 锚点 #C810-3-55-ONE-LEVEL）：
        # 只在该分布确实带 DS 卡时硬判 —— 那种卡的存在本身就说明它是**依赖变量**的分布，
        # 挂在普通 Dn 形态上必然是写错了。
        entry = self.s._entry(did)
        if entry.get("ds"):
            raise SourceSamplingError(
                f"SDEF {var} 用 D{did} 取值，但 D{did} 带 DS 卡 ⇒ 它只能用依赖形态 "
                f"（`{var} F<父变量> D{did}`）引用（C810 p.3-55 第三种形态；"
                "锚点 #C810-3-55-ONE-LEVEL）")
        value = self._smp(did, var, axs=axs)
        index = self._index_of(did, value)
        self.vals[var] = value
        self.sampled.add(var)
        return value, index

    def _index_of(self, did: int, value: float) -> int | None:
        """抽到的值 → 它在分布里的档位下标（供 ``Fvar′ Dn`` 的父值）。"""
        entry = self.s._entry(did)
        si = entry.get("si") or {}
        vals = self.s._floats(si.get("values"))
        kind = (si.get("type") or "").strip().upper()
        if not vals:
            return None
        if kind == "L":
            for i, v in enumerate(vals):
                if abs(v - value) < 1e-9:
                    return i
            return None
        if kind in ("", "H"):
            if len(vals) < 2:
                return None
            for i in range(len(vals) - 1):
                if vals[i] - 1e-12 <= value <= vals[i + 1] + 1e-12:
                    return i
            return 0 if value <= vals[0] else len(vals) - 2
        if kind == "A":
            for i, v in enumerate(vals):
                if abs(v - value) < 1e-9:
                    return i
            return None
        return None

    def _parent_si(self, parent: str) -> list | None:
        """父变量的 ``SI`` 值（DS **H 型**连续插值需要它；拿不到就交回 ``None``）。

        父变量可能源自 ``POS=Dn``（三分量同引用）或某个分量，故候选按
        POS → X/Y/Z 的次序取第一个能读到值的字段。
        """
        spec = spec_for(parent)
        for key in spec.field_keys or ():
            raw = self._field_for_key(key)
            if not raw:
                continue
            try:
                ref = parse_var_ref(raw)
            except SourceSamplingError:
                continue
            did = ref.get("did")
            if not did:
                continue
            entry = self.s._entry(did)
            si = entry.get("si") or {}
            kind = (si.get("type") or "").strip().upper()
            if kind in ("", "H"):
                return list(si.get("values") or [])
        return None

    def _ds_value(self, resolved: dict, var: str, did: int) -> tuple[float, int | None]:
        """``DS`` 卡查表结果 → 取值。

        ``resolve_ds`` 的三种返回（C810 DS 卡 H/L/S/T/Q，锚点 ``#C810-3-66-DS-CARD``）：
        ``{"value": v}`` 直接取值 / ``{"distribution": d}`` 递归到子分布 /
        ``{"default": True}`` **查不到** —— 契约 §4 要求"依赖值缺失"必须报错，
        所以这里抛错而不是回退默认值（旧 ``_ds_value`` 就是回退 14.0）。
        """
        if "value" in resolved:
            return float(resolved["value"]), None
        if "distribution" in resolved:
            return self._sample_dist(int(resolved["distribution"]), var)
        raise SourceSamplingError(
            f"SDEF {var} 的依赖取值在分布 D{did} 的 DS 卡里查不到"
            "（父变量的抽样值落在 DS 表的覆盖范围之外，或 DS 表项数与父变量 SI 不匹配）；"
            "C810 DS 卡的 H/L/S/T/Q 都必须能覆盖父变量的全部取值"
            "（锚点 #C810-3-66-DS-CARD）")

    # ── 位置层（组合语义，契约 §3）──────────────────────────
    @property
    def geom(self) -> _GeometryHelper:
        if self._geom_helper is None:
            self._geom_helper = _GeometryHelper(self.geometry, self)
        return self._geom_helper

    def _position(self) -> tuple[tuple, int | None]:
        """位置 = **变量组合**（契约 §3）：``SUR`` / ``CEL`` / ``POS+RAD+EXT+AXS`` / ``X-Y-Z``。

        分派次序与旧实现一致（SUR → CEL → POS 多点 → X/Y/Z 笛卡尔 → POS+RAD/EXT → 点源），
        保持既有抽样序列；变化在**取值**上：全部走 ``_resolve``，
        ``RAD/EXT`` 不再有专用的 ``_radial_value``/``_axial_value``/``_default_power_law``。
        """
        sur = self._field("SUR")
        cel = self._field("CEL")
        self.surface_normal = None
        self.cel_source = bool(cel and cel not in ("0",))
        # 1. 面源 SUR（C810 p.3-58：只支持 平面/球面/椭球面）
        if sur and sur not in ("0",):
            return self._position_surface(sur), None
        # 2. 栅元均匀 CEL（拒绝采样 + EFF 判据，C810 p.3-57/3-59）
        if self.cel_source:
            return self.geom.sample_cell(self._cell_number(cel), self._eff()), None
        px, py, pz = (self._field_for_key(k) for k in ("sdef_pos_x", "sdef_pos_y", "sdef_pos_z"))
        # 3. POS=Dn 多点源（三分量同引用 = SI 每 3 个一组）
        if px and px == py == pz and parse_var_ref(px)["kind"] == "dist":
            return self._position_multi_point(parse_var_ref(px)["did"])
        # 4. X/Y/Z 笛卡尔（任一分量是分布）
        if any(v and parse_var_ref(v)["kind"] != "const" for v in (px, py, pz)):
            # POS 与 X/Y/Z 共用三个分量字段（C810 p.3-57 / 解析层把 POS 拆进 X/Y/Z）：
            #   三分量**同**一个分布号 = `POS=Dn` 多点源（上面第 3 条已接走）；
            #   各分量**不同**分布 = X/Y/Z 逐分量笛卡尔（本程序支持的既有用法）；
            # 只有"部分分量同号、部分不同"这种自相矛盾的写法才需要点出来 ——
            # 旧实现会把没给的分量静默当 0。
            same = [v for v in (px, py, pz) if v]
            distinct = {v.upper() for v in same}
            if len(distinct) > 1 and len(same) != len(distinct):
                raise SourceSamplingError(
                    f"SDEF POS={px} {py} {pz}：分量字段的分布引用不一致 —— "
                    "三个分量要么都写同一个 `Dn`（多点源，C810 p.3-57），"
                    "要么各写各的分布（笛卡尔 X/Y/Z），不要混着写")
            return (self._coord("X"), self._coord("Y"), self._coord("Z")), None
        # 5. POS + RAD/EXT（+AXS）—— 球 / 球壳 / 柱 / 圆盘 / 锥
        if self._field("RAD") or self._field("EXT"):
            return self._position_cylindrical(), None
        # 6. 点源（三分量齐给）/ 默认原点（Table 3.3：POS 默认 0,0,0）
        if px and py and pz:
            return (self._coord("X"), self._coord("Y"), self._coord("Z")), None
        return (0.0, 0.0, 0.0), None

    def _cell_number(self, raw: str) -> int:
        """``CEL`` 的栅元号：只认显式整数（CEL 由位置定，不是分布变量）。"""
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            raise SourceSamplingError(
                f"SDEF CEL={raw!r} 不是栅元号（C810 Table 3.3：CEL 由位置定，"
                "只接受显式栅元号）")

    def _position_multi_point(self, did: int) -> tuple[tuple, int]:
        """``POS=Dn`` 多点源：``SI`` 每 3 个值 = 一个位置，``SP`` 概率选位置组。

        SB 存在时**按 SB 偏倚抽样并补偿权重**（C810 p.3-64）。旧实现把这段单独写在
        ``_sample_pos_dist`` 里、连 SB 都没看；现在与其它变量共用
        ``DistributionSampler`` 的概率/偏倚解析（口径一致，不再各写各的）。
        """
        entry = self.s._entry(did)
        si_vals = self.s._floats((entry.get("si") or {}).get("values"))
        if len(si_vals) < 3 or len(si_vals) % 3 != 0:
            raise SourceSamplingError(
                f"POS=D{did} 的位置值个数（{len(si_vals)}）不是 3 的倍数："
                "C810 p.3-57 的多点源写法要求 SI 每 3 个值构成一个位置")
        n_pos = len(si_vals) // 3
        sp = entry.get("sp") or {}
        sb = entry.get("sb")
        sp_type = (sp.get("type") or "D").strip().upper() or "D"
        sp_vals = self.s._floats(sp.get("values"))
        cel, axs = self._power_arg()
        probs = self.s._probs(sp_type, sp_vals, n_pos, sb, var="POS",
                              si_vals=si_vals, cel=cel, sdef_fields=self.f,
                              cell_volumes=self.cell_volumes)
        idx = _pick(probs, self.rng)
        self._acc_corr("POS", self.s._bias_factor(
            sp_type, sp_vals, n_pos, sb, idx, var="POS", cel=cel,
            si_vals=si_vals, sdef_fields=self.f, cell_volumes=self.cell_volumes))
        pos = tuple(si_vals[idx * 3:idx * 3 + 3])
        # POS 的"值"在依赖语义里是**档位下标**（多点源的第几组点，
        # C810 p.3-57 的 `ERG=FPOS Dn` 就是按这个下标查 DS 表），不是坐标本身。
        self.vals["POS"] = float(idx)
        self.sampled.add("POS")
        return pos, idx

    def _position_cylindrical(self) -> tuple:
        """``POS`` + ``RAD`` (+ ``EXT`` + ``AXS``)：球 / 球壳 / 柱 / 圆盘 / 锥（C810 p.3-57~58）。

        - 无 ``AXS``：位置在半径 ``RAD`` 的**球面**上各向同性（体积均匀靠 RAD 的
          ``a=2`` 幂律；只有 SI 时由 C810 p.3-66 规则 2/4 自动补上的默认幂律给）；
        - 有 ``AXS``：位置在距 ``POS`` 沿轴 ``EXT``、半径 ``RAD`` 的**圆**上（``a=1``）。
        """
        cx, cy, cz = self._coord("X"), self._coord("Y"), self._coord("Z")
        axs_vec = self._vec("AXS")
        if not axs_vec or not any(axs_vec):
            radius = self._radial_value(power=2.0)
            dx, dy, dz = _isotropic(self.rng)
            return (cx + radius * dx, cy + radius * dy, cz + radius * dz)
        k = _norm(axs_vec)
        ref = (1.0, 0.0, 0.0) if abs(k[0]) < 0.9 else (0.0, 1.0, 0.0)
        u = _norm(_cross(k, ref))
        v = _cross(k, u)
        radius = self._radial_value(power=1.0)
        axial = self._axial_value()
        phi = self.rng.uniform(0.0, 2.0 * math.pi)
        return (cx + axial * k[0] + radius * (math.cos(phi) * u[0] + math.sin(phi) * v[0]),
                cy + axial * k[1] + radius * (math.cos(phi) * u[1] + math.sin(phi) * v[1]),
                cz + axial * k[2] + radius * (math.cos(phi) * u[2] + math.sin(phi) * v[2]))

    def _radial_value(self, power: float) -> float:
        """``RAD`` 取值：走通用引擎；只有 ``SI`` 没有 ``SP`` 时按默认幂律（C810 p.3-66）。"""
        did = self._dist_did("RAD")
        if did is None:
            return self._value("RAD")
        return self._default_power_law(did, power, "RAD")

    def _axial_value(self) -> float:
        """``EXT`` 取值：同 ``RAD``，默认幂律 ``a=0``（区间内均匀）。"""
        did = self._dist_did("EXT")
        if did is None:
            return self._value("EXT")
        return self._default_power_law(did, 0.0, "EXT", axs=False)

    def _dist_did(self, var: str) -> int | None:
        """变量是不是 ``Dn`` 形态 → 分布号（否则 ``None``，调用方走通用取值）。"""
        raw = self._field(var)
        if not raw:
            return None
        ref = parse_var_ref(raw)
        return ref.get("did") if ref["kind"] == "dist" else None

    def _default_power_law(self, did: int, power: float, var: str, axs=None) -> float:
        """「只有 SI、没有 SP」时 MCNP 自动补的**默认幂律**（C810 p.3-66 特殊默认 2~5）。

        ``SIn`` 给范围（``SI 0 5``；单值 x 按规则 4/5 解释成 ``0 x`` / ``−x x``），
        幂指数由**源型**定：球 ``a=2``、柱 ``a=1``、轴 ``a=0``（体积/面积均匀）。
        只要 ``SP`` 存在（哪怕只是 ``SP −21``），就交给通用内置函数路径。
        """
        cel, axs_flag = self._power_arg()
        if axs is None:
            axs = axs_flag
        entry = self.s._entry(did)
        sp = entry.get("sp") or {}
        if (sp.get("fnCode") or "").strip() or sp.get("values"):
            value = self._smp(did, var, cel=cel, axs=axs)
            self.vals[var] = value
            self.sampled.add(var)
            return value
        si_vals = self.s._floats((entry.get("si") or {}).get("values"))
        if not si_vals:
            raise SourceSamplingError(
                f"SDEF {var}=D{did} 既没有 SP（内置函数）也没有 SI 表 ⇒ 无法确定取值区间"
                "（C810 p.3-66 的默认幂律需要 SI 给出范围）")
        lo, hi = DistributionSampler._range(si_vals, (0.0, 0.0), var)
        # −21 本身按定义在 SI 区间上归一化 ⇒ C810 p.3-66 **豁免**截断补偿，因子为 1。
        if hi <= 0:
            return 0.0
        lo = max(0.0, lo)
        u = self.rng.uniform(0.0, 1.0)
        if abs(power + 1.0) < 1e-12:
            value = lo * (hi / lo) ** u if lo > 0 else hi * u
        else:
            value = (lo ** (power + 1) + u * (hi ** (power + 1) - lo ** (power + 1))) ** (
                1.0 / (power + 1))
        self.vals[var] = value
        self.sampled.add(var)
        return value

    def _position_surface(self, raw: str) -> tuple:
        """``SUR`` 面源：位置 + 面法线（法线供 ``VEC`` 缺省与 NRM 符号使用）。

        ``EXT`` 只在**球面源 + 给了 AXS** 时有语义（C810 p.3-58：那时 EXT 抽的是
        「AXS 与球心→位置矢量夹角的余弦」）。旧实现在**平面源上也先抽一遍 EXT**
        （抽了不用，白白吃掉一个随机数并可能误报分布错误）；这里只在真需要时才抽。
        """
        try:
            surf_num = int(float(raw))
        except (TypeError, ValueError):
            raise SourceSamplingError(
                f"SDEF SUR={raw!r} 不是曲面号（C810 Table 3.3：SUR 是曲面编号）")
        spec = self.geom.surf_info(surf_num)
        wants_ext = spec in ("SO", "SPH", "S", "SX", "SY", "SZ")
        axis = self._vec("AXS") if (wants_ext and self._axs_defined()) else ()
        ext = self._axial_value() if (wants_ext and axis and any(axis)) else None
        pos, normal = self.geom.sample_surface(
            surf_num, self.rng,
            px=self._coord("X"), py=self._coord("Y"), pz=self._coord("Z"),
            rad_did=self._dist_did("RAD"),
            nrm=self._value("NRM"),
            axis=axis, ext=ext)
        self.surface_normal = normal
        return pos

    # ── 方向层（C810 p.3-59 + Table 3.3）────────────────────
    def _direction(self) -> tuple:
        """方向抽样：``DIR``（Dn / 固定三分量 / 固定单值沿参考轴 / 缺省）+ ``VEC``/``NRM``。

        缺省语义（Table 3.3 的 DIR 行，锚点 ``#C810-3-56-TABLE-3-3``）：
        面源 ``p(μ)=2μ``（余弦分布，相对于 VEC；**VEC 缺省 = 面法线**，符号由 NRM 定）、
        体源各向同性（μ 在 −1..1 均匀）。方位角恒 0~360° 均匀。

        顺序上必须在 ``_position`` 之后：面源判据、面法线、``POS`` 都是位置层的产物。
        """
        axis = self._vec("VEC")
        if not (axis and any(axis)):
            axis = self.surface_normal or ()
        dref = parse_var_ref(self._field("DIR")) if self._field("DIR") else None
        if dref is not None and dref["kind"] == "dist":
            mu, _ = self._sample_dist(dref["did"], "DIR", axs=self._axs_defined())
            if not (axis and any(axis)):
                # VEC 缺省只对**面源**成立；体源没给 VEC 时 MCNP 的方向参考轴不存在
                # ⇒ 退回各向同性（并记一条提醒，别让 μ 白抽）。
                self.warnings.append(
                    "SDEF DIR 取自分布，但没有 VEC / 面法线可作参考轴 ⇒ 按体源各向同性处理")
                return _isotropic(self.rng)
            self.last_mu = mu
            return self._dir_from_mu(mu, axis)
        raw = self._field("DIR")
        if raw:
            if dref["kind"] == "dep":
                raise SourceSamplingError(
                    f"SDEF DIR={raw!r} 是依赖形态，但 Table 3.3 的 DIR 没有可作其父的变量"
                    "（DIR 在 VAR_SPEC 里 parents 为空，锚点 #C810-3-55-VAR-FORMS）")
            toks = raw.replace(",", " ").replace("=", " ").split()
            if len(toks) >= 3:
                # 固定方向余弦（u v w 三分量逐字给出）
                return tuple(_scalar(t, "DIR") for t in toks[:3])
            if axis and any(axis):
                # DIR=1（或其它单值）＝沿参考轴（VEC / 面法线）——C810 p.3-59 单向源写法
                self.last_mu = _scalar(toks[0] if toks else "0", "DIR")
                return _norm(axis)
            raise SourceSamplingError(
                "SDEF DIR 写成单值（方向余弦）但缺少参考轴：请给 VEC，或把源放在曲面上"
                "（面源的 VEC 默认 = 面法线）—— C810 Table 3.3 的 VEC 行")
        if self.surface_normal is not None:
            # 面源缺省：余弦分布 p(μ)=2μ（μ 相对 VEC/面法线，0..1）
            mu = math.sqrt(self.rng.uniform(0.0, 1.0))
            self.last_mu = mu
            return self._dir_from_mu(mu, axis)
        return _isotropic(self.rng)

    def _dir_from_mu(self, mu: float, axis) -> tuple:
        """方向余弦 ``μ``（相对参考轴）+ 绕轴均匀方位角 → 方向矢量。"""
        if not (axis and any(axis)):
            return _isotropic(self.rng)
        ax = _norm(axis)
        phi = self.rng.uniform(0.0, 2.0 * math.pi)
        mu = max(-1.0, min(1.0, float(mu)))
        perp = math.sqrt(max(0.0, 1.0 - mu * mu))
        ref = (1.0, 0.0, 0.0) if abs(ax[0]) < 0.9 else (0.0, 1.0, 0.0)
        u = _norm(_cross(ax, ref))
        v = _cross(ax, u)
        return (mu * ax[0] + perp * (math.cos(phi) * u[0] + math.sin(phi) * v[0]),
                mu * ax[1] + perp * (math.cos(phi) * u[1] + math.sin(phi) * v[1]),
                mu * ax[2] + perp * (math.cos(phi) * u[2] + math.sin(phi) * v[2]))

    # ── 其余变量 ─────────────────────────────────────────────
    def _value(self, var: str, axs=None) -> float:
        """通用变量取值（``_resolve`` 的"只要值"外壳）。

        重复取同一个变量不会重复抽样：``_resolve`` 有本粒子级的缓存 —— 否则
        ``X`` 被 ``_position`` 与 ``POS+RAD`` 两条路各取一次就会白吃两个随机数。
        """
        value, _ = self._resolve(var)
        return value

    def _coord(self, var: str) -> float:
        """**参考点坐标**（X/Y/Z）取值：未给 = 0（C810 p.3-57：POS 默认 ``0,0,0``）。

        与 ``_value`` 的区别只在"未给"的口径：``ERG``/``RAD`` 这类**标量变量**未给就是
        "没有单一数值默认"（``_resolve`` 报错），而 X/Y/Z 作为 POS 的分量，Table 3.3 的
        ``No X`` 就是"按 0 起算"（POS 的默认值 ``0,0,0``）。
        """
        if not self._has(var):
            return 0.0
        return self._value(var)

    def _eff(self) -> float:
        """``EFF``：CEL 拒绝采样的效率判据（Table 3.3 默认 .01；C810 p.3-59 的终止判据）。

        Table 3.3 原文「The specification of WGT, EFF and PAR must be only an explicit
        value. A distribution is not allowed.」⇒ 只认显式数值，且必须落在 (0,1]；
        越界不再静默回落到 0.01（旧 `_eff` 那样做会把用户的写法错误藏起来）。
        """
        eff = self._value("EFF")
        if not (0.0 < eff <= 1.0):
            raise SourceSamplingError(
                f"SDEF EFF={eff!r} 越界：C810 Table 3.3（p.3-56）规定 EFF 是拒绝采样的"
                "效率判据，取值须在 (0,1]（默认 .01）；p.3-59 的终止判据是 "
                "MAX(成功数,10) < EFF×尝试数")
        return eff

    def _par_value(self) -> float:
        """``PAR``：粒子类型。**不做任何默认填充** —— Table 3.3 规定它由 MODE 卡定，
        本引擎拿不到 MODE（见 `sample_one` 的说明）⇒ 只有写出来才认。"""
        return self._value("PAR")

    def _weight(self) -> float:
        """权重 = ``WGT`` 基值 × 本次抽样路径上所有补偿之积（契约 §0）。"""
        base = self._value("WGT")
        factor = 1.0
        for value in self.corr.values():
            factor *= value
        return base * factor

    def _acc_corr(self, var: str, factor: float) -> None:
        self.corr[var] = self.corr.get(var, 1.0) * factor

    # ── SDEF TR ──────────────────────────────────────────────
    def _sdef_trn(self):
        """SDEF ``TR=`` 的变换数据（C810 Table 3.3 p.3-56 表尾 + p.3-59）。

        两种形态：``TR=n`` 固定 TR 编号；``TR=Dn`` **变换分布**（``SI L`` 列 TR 号、
        ``SP`` 选概率），每颗粒子抽一个 TR 号再变换。取不到卡 → ``None``（按"未变换"）。
        """
        raw = self._field("TR")
        if not raw:
            return None
        cards = (self.geometry or {}).get("trCards") or {}
        ref = parse_var_ref(raw)
        if ref["kind"] == "dist":
            tr_no = int(round(self._smp(ref["did"], "TR")))
            tr = cards.get(str(tr_no)) or cards.get(tr_no)
        elif ref["kind"] == "const":
            tr = cards.get(raw) or cards.get(str(raw))
        else:
            return None
        if not tr:
            return None
        return {"origin": tuple(tr.get("translate") or (0.0, 0.0, 0.0)),
                "rotate": tr.get("rotate")}

    # ── 单粒子 ───────────────────────────────────────────────
    def sample_one(self, rng: random.Random, i: int) -> dict:
        """抽一个源粒子的起始状态（位置 / 方向 / 能量 / 权重 / 粒子类型）。

        为什么 ``DIR`` 在 ``ERG`` 之前：C810 p.3-55 要求依赖变量在父变量之后抽样；
        ``ERG=FDIR Dn`` 必须拿到本颗粒子的 μ。**非依赖**卡仍沿用既有的"先 ERG 后 DIR"
        抽样序列（见 ``_erg_depends_on_dir``）——既满足 p.3-55，也不白白改动既有 RNG 流。
        """
        self.rng = rng
        self.vals = {}
        self._cache = {}
        self.sampled = set()
        self.corr = {}
        self.surface_normal = None
        self.cel_source = False
        self.last_mu = None

        pos, pos_index = self._position()
        normal = self.surface_normal
        depends_dir = self._erg_depends_on_dir()
        if depends_dir:
            dirv = self._direction()
            erg = self._erg(pos_index)
        else:
            erg = self._erg(pos_index)
            dirv = self._direction()
        tme = self._tme()
        wgt = self._weight()
        par = self._par()
        # SDEF TR=n / TR=Dn：抽出的位置与方向都要按 TR 卡变换（源坐标系 → 世界系）
        trn = self._sdef_trn()
        if trn is not None:
            o = trn["origin"]
            dirv = _to_world_dir(dirv, trn["rotate"])
            pos = _to_world_dir(pos, trn["rotate"])
            pos = (pos[0] + o[0], pos[1] + o[1], pos[2] + o[2])
        n = math.sqrt(sum(d * d for d in dirv))
        if n < 1e-15:
            dirv = (0.0, 0.0, 1.0)
            n = 1.0
        return {
            "id": i + 1,
            "x": pos[0], "y": pos[1], "z": pos[2],
            "dx": dirv[0] / n, "dy": dirv[1] / n, "dz": dirv[2] / n,
            "energy": erg, "weight": wgt, "particle": par,
        }

    def _erg_depends_on_dir(self) -> bool:
        """``SDEF ERG`` 是不是 ``FDIR Dn``（决定 DIR 与 ERG 的先后）。"""
        raw = self._field("ERG")
        if not raw:
            return False
        ref = parse_var_ref(raw)
        return ref["kind"] == "dep" and ref["parent"] == "DIR"

    def _erg(self, pos_index: int | None) -> float:
        """能量：``Dn`` / ``Fvar′ Dn``（父值 = ``POS`` 的档位或 ``DIR`` 的 μ）/ 显式值。

        ``FDIR`` / ``FPOS`` 的父值都由 ``_resolve`` 从本粒子已抽的取值里读
        （``_sample_dist`` 会把值登记进 ``vals``）；``POS`` 是特例：多点源的父值必须是
        **档位下标**而不是坐标，故由 ``_position`` 直接给出。
        """
        raw = self._field("ERG")
        if not raw:
            return self._value("ERG")
        ref = parse_var_ref(raw)
        if ref["kind"] == "dep" and ref["parent"] == "POS" and pos_index is not None:
            # POS 的父值 = 多点源的**档位下标**（`_position_multi_point` 已登记，
            # 这里再钉一次，防止 POS 走的是 X/Y/Z 分量路径而漏登记）
            self.vals["POS"] = float(pos_index)
            self.sampled.add("POS")
        value, _ = self._resolve("ERG")
        return value

    def _tme(self) -> float:
        """时间（shakes，Table 3.3 默认 0）。

        官方 lps_water 的 ``tme=d400`` / ``sp400 -41 .5 0`` 就是走这一路（高斯展开）——
        旧实现**完全不抽 TME**（S5）。取值本身进不了粒子记录（契约 §6：TME 只参与抽样
        与权重，前端不显示），但依赖链与抽样必须发生。
        """
        raw = self._field("TME")
        if not raw:
            return float(spec_for("TME").default)
        return self._value("TME")

    def _par(self) -> str:
        """粒子类型。缺省取中子：Table 3.3 的 PAR 默认值由 **MODE 卡**定
        （「the lowest of these three that corresponds to an actual or default entry on the
        MODE card」），而本引擎只拿到 SDEF 字段、没有 MODE ⇒ 沿用既有口径按 ``n``，
        不把它伪装成"从 Table 3.3 读到的默认值"。"""
        raw = self._field("PAR")
        if not raw:
            return "n"
        text = str(raw).strip().upper()
        if text[:1] == "D" and text[1:].isdigit():
            return _PAR_GROUP.get(str(int(self._par_value())), "other")
        return _PAR_GROUP.get(text, "other")

    # ── 未实现变量的显式拒绝（契约 §4）──────────────────────
    def _reject_unsupported(self) -> None:
        for name, why in _UNSUPPORTED_VARS.items():
            spec = spec_for(name)
            for key in spec.field_keys:
                if str(self.f.get(key) or "").strip():
                    raise SourceSamplingError(
                        f"SDEF {name} 暂不支持：本引擎还没实现{why}"
                        "（它在 C810 Table 3.3 里有声明，但静默忽略会让用户以为生效了）")


def _isotropic(rng) -> tuple:
    """各向同性方向（μ 在 −1..1 均匀、方位角 0~360° 均匀）。"""
    z = rng.uniform(-1.0, 1.0)
    phi = rng.uniform(0.0, 2.0 * math.pi)
    r = math.sqrt(max(0.0, 1.0 - z * z))
    return (r * math.cos(phi), r * math.sin(phi), z)


def _norm(v) -> tuple:
    n = math.sqrt(sum(x * x for x in v))
    if n < 1e-15:
        return (0.0, 0.0, 1.0)
    return tuple(x / n for x in v)


def _cross(a, b) -> tuple:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _to_world_dir(v, rotate) -> tuple:
    """局部方向 → 世界方向：``Rᵀ · d``（只转不平移，与 `_to_world` 同约定）。"""
    if rotate is None:
        return (v[0], v[1], v[2])
    return (rotate[0][0] * v[0] + rotate[1][0] * v[1] + rotate[2][0] * v[2],
            rotate[0][1] * v[0] + rotate[1][1] * v[1] + rotate[2][1] * v[2],
            rotate[0][2] * v[0] + rotate[1][2] * v[1] + rotate[2][2] * v[2])


class _GeometryHelper:
    """CEL/SUR 几何判定（深模块内部 seam，惰性 import pymcnp + voxel_csg）。

    **本类的几何算法沿用既有实现**（已在 C810 上验过、且是纯几何）：CEL 在紧盒内
    拒绝采样并用 EFF 判据；面源只支持 平面/球面/椭球面（C810 p.3-58）。
    本次重构只改**取值入口**：``RAD``/``EXT`` 不再有专用的 ``_radial_at``，
    改为回调引擎的 ``_resolve``（``Dn`` / 内置函数 / 默认幂律三合一）。
    """

    def __init__(self, geometry, engine: _Engine):
        g = geometry or {}
        # geometry 由 api_server 层准备（复用其 parse_surfaces/Geometry.from_mcnp/
        # resolve_cell_complements/voxel_csg 构造 field 函数）：
        #   {"cells": {num: {"field": fn, "aabb": (lo3, hi3[, axes3])}},
        #    "surfaces": {num: {"type": str, "params": list, "field": fn,
        #                       "rotate": 3×3 | None, "origin": (3,)}}}
        self.cells = g.get("cells", {}) or {}
        self.surfs = g.get("surfaces", {}) or {}
        self.engine = engine
        # CEL 拒绝采样的累计计数：C810 p.3-59 的效率判据是**全栅元级**的
        # （MAX(成功数,10) < EFF×尝试数），故跨粒子累计，不能只看单个粒子。
        self._cel_tries = 0
        self._cel_hits = 0

    def surf_info(self, surf_num: int) -> str:
        """曲面号 → 类型（未定义则报错，报错文案与旧实现一致）。"""
        s = self.surfs.get(surf_num)
        if s is None:
            raise SourceSamplingError(f"SUR={surf_num} 引用的曲面未定义")
        return str(s["type"])

    # ── RAD / EXT 的取值入口（唯一）：交回引擎的通用路径 ──────
    def _radial_at(self, did, power: float) -> float:
        """面源 ``RAD``（面内半径）：走变量名感知的通用路径
        （``SI x`` + ``SP −21`` ⇒ C810 p.3-66 规则 4 的 ``SI 0 x``；无 SP ⇒ 默认幂律）。"""
        return self.engine._default_power_law(did, power, "RAD")

    def sample_cell(self, cell_num: int, eff: float) -> tuple:
        """CEL 拒绝采样（C810 p.3-57 正文 + p.3-59 的 EFF 判据）。

        **区域来源（相对 C810 的有意扩展）**：C810 p.3-57 要求由**用户**给一个完全包含该
        栅元的区域（X/Y/Z 笛卡尔 / POS+RAD 球 / POS+AXS+RAD+EXT 柱），并原话提醒「you must
        make sure that the sampling region really does contain every part of the cell
        because MCNP has no way of checking this」。本程序的 SDEF 表单里"只给 CEL"是最常见
        用法，故**用栅元紧盒（`voxel_csg.cell_aabb`）当区域** —— 用户不必自己算盒；
        代价是盒错则采样必错，所以紧盒必须对（宏体紧盒 2026-09-20 补齐）。

        **判死口径（C810 p.3-59 原文）**：「If in any source cell or cookie-cutter cell the
        acceptance rate is too low, the problem is terminated for inefficiency. The criterion
        for termination is ``MAX(number of successes, 10) < EFF * number of tries``」。
        照此判据**明确报错**；EFF 默认 0.01（Table 3.3），可用 ``sdef_eff`` 覆盖。
        """
        info = self.cells.get(cell_num)
        if info is None:
            raise SourceSamplingError(f"CEL={cell_num} 引用的栅元不存在或无法判定")
        aabb = info.get("aabb")
        if not aabb:
            raise SourceSamplingError(
                f"CEL={cell_num} 无法确定栅元包围盒（该栅元含无界曲面或未支持的几何）⇒ "
                "无法做栅元均匀抽样。请改用面源（SUR），或改用退化体源"
                "（POS + AXS + RAD + EXT）自己指定采样范围")
        # aabb 两种形态都接受：`(lo3, hi3)`（早期契约/单测夹具）与
        # `(lo3, hi3, axes3)`（`voxel_csg.cell_aabb` 的真实返回，带逐轴有界标志）。
        bounded = aabb[2] if len(aabb) > 2 else (True, True, True)
        if not all(bounded):
            raise SourceSamplingError(
                f"CEL={cell_num} 的包围盒有**无界轴**（该栅元在某个方向上延伸到无穷）⇒ "
                "无法做栅元均匀抽样。请改用面源（SUR），或改用退化体源自己指定采样范围")
        field = info.get("field")
        lo = [max(-1e6, x) for x in aabb[0]]
        hi = [min(1e6, x) for x in aabb[1]]
        if any(hi[i] <= lo[i] for i in range(3)):
            raise SourceSamplingError(f"CEL={cell_num} 包围盒退化（{lo} → {hi}）")
        import numpy as np
        rng = self.engine.rng
        for _ in range(100000):
            p = [rng.uniform(lo[i], hi[i]) for i in range(3)]
            self._cel_tries += 1
            try:
                inside = field(np.asarray([p[0]]), np.asarray([p[1]]), np.asarray([p[2]]))
            except Exception:
                continue
            if inside is not None and bool(np.asarray(inside).ravel()[0]):
                self._cel_hits += 1
                # C810 p.3-59：MAX(成功数,10) < EFF×尝试数 ⇒ 效率过低（MCNP 会终止问题）
                if max(self._cel_hits, 10) < eff * self._cel_tries:
                    raise SourceSamplingError(
                        f"CEL={cell_num} 拒绝采样效率过低：{self._cel_tries} 次尝试只接受 "
                        f"{self._cel_hits} 次（低于 EFF={eff:g}；C810 3-59 的判据 "
                        "MAX(成功数,10) < EFF×尝试数 会直接终止问题）。"
                        "通常意味着采样区域远大于栅元 —— 若该栅元几何特殊（宏体/补集/退化盒），"
                        "请改用退化体源自己指定采样范围")
                return (p[0], p[1], p[2])
        raise SourceSamplingError(
            f"CEL={cell_num} 拒绝采样失败：100000 次尝试无一命中（EFF={eff:g}；"
            f"包围盒 {['%.4g' % x for x in lo]} → {['%.4g' % x for x in hi]}）。"
            "该栅元在这套几何下几乎是空集，或包围盒远大于实心")

    def sample_surface(self, surf_num: int, rng, px: float, py: float, pz: float,
                       rad_did: int | None, nrm: float, axis=(), ext=None) -> tuple:
        """面源位置 + 面法线（C810 p.3-58 / Table 3.3）。

        - **平面**：位置 = POS + RAD·(面内单位矢量)；RAD 默认 a=1 的幂律（面内均匀）；
        - **球**：位置按面积均匀；法线 = (p − center)/|…|；
        - **椭球（GQ/SQ）**：严格面积均匀（拉回单位球 + 面元权重拒绝采样），法线 = ∇f；
        - 其余类型：按 C810「面源只能是平面/球/椭球」的语义**明确报错**并给"改用退化体源"。
        """
        s = self.surfs.get(surf_num)
        if s is None:
            raise SourceSamplingError(f"SUR={surf_num} 引用的曲面未定义")
        typ = s["type"]
        params = [float(v) for v in (s.get("params") or [])]
        rotate = s.get("rotate")
        origin = s.get("origin") or (0.0, 0.0, 0.0)
        nrm_sign = 1.0 if float(nrm) >= 0 else -1.0
        pos = (px, py, pz)

        if typ in ("PX", "PY", "PZ", "P_0", "P_1"):
            e = {"PX": (1.0, 0.0, 0.0), "PY": (0.0, 1.0, 0.0), "PZ": (0.0, 0.0, 1.0)}.get(typ)
            if e is None:
                e = self._plane_normal(typ, params)
            t1, t2 = self._tangents(e)
            if rad_did is None:
                r = self.engine._value("RAD")
            else:
                r = self._radial_at(rad_did, 1.0)
            phi = rng.uniform(0.0, 2.0 * math.pi)
            p_local = (pos[0] + r * (math.cos(phi) * t1[0] + math.sin(phi) * t2[0]),
                       pos[1] + r * (math.cos(phi) * t1[1] + math.sin(phi) * t2[1]),
                       pos[2] + r * (math.cos(phi) * t1[2] + math.sin(phi) * t2[2]))
            # 平面源：位置在面上，法线方向不随位置变
            return self._to_world(p_local, origin, rotate), \
                self._nrm_sign_vec(_to_world_dir(e, rotate), nrm_sign)

        if typ in ("SO", "SPH", "S", "SX", "SY", "SZ"):
            if typ == "SO":
                c, rr = (0.0, 0.0, 0.0), params[0]
            elif typ in ("SPH", "S"):
                c, rr = tuple(params[0:3]), params[3]
            else:
                c = {"SX": (params[0], 0.0, 0.0), "SY": (0.0, params[0], 0.0),
                     "SZ": (0.0, 0.0, params[0])}[typ]
                rr = params[1]
            ax = _norm(axis) if (axis and any(axis)) else None
            if ax is None:
                d = _isotropic(rng)                   # 未给 AXS ⇒ 按面积均匀（C810 p.3-58）
            else:
                # 给了 AXS ⇒ μ = EXT（AXS 与「球心→位置」矢量的夹角余弦），方位角均匀
                mu = max(-1.0, min(1.0, float(ext if ext is not None else 0.0)))
                t1, t2 = self._tangents(tuple(ax))
                phi = rng.uniform(0.0, 2.0 * math.pi)
                sn = math.sqrt(max(0.0, 1.0 - mu * mu))
                d = (mu * ax[0] + sn * (math.cos(phi) * t1[0] + math.sin(phi) * t2[0]),
                     mu * ax[1] + sn * (math.cos(phi) * t1[1] + math.sin(phi) * t2[1]),
                     mu * ax[2] + sn * (math.cos(phi) * t1[2] + math.sin(phi) * t2[2]))
            p_local = (c[0] + rr * d[0], c[1] + rr * d[1], c[2] + rr * d[2])
            n_local = _norm((p_local[0] - c[0], p_local[1] - c[1], p_local[2] - c[2]))
            return (self._to_world(p_local, origin, rotate),
                    self._nrm_sign_vec(_to_world_dir(n_local, rotate), nrm_sign))

        if typ in ("GQ", "SQ"):
            p_local, n_local = self._quadric_pt(s, rng)
            return (self._to_world(p_local, origin, rotate),
                    self._nrm_sign_vec(_to_world_dir(n_local, rotate), nrm_sign))

        raise SourceSamplingError(
            f"SUR={surf_num}：曲面类型 {typ} 不能作面源。C810 3-58 原文规定面源只能是"
            "平面（P/PX/PY/PZ）、球面（SO/S/SX/SY/SZ）或椭球面（GQ/SQ）——"
            "「Cylindrical surface sources must be specified as degenerate volume sources」。"
            "柱面/锥面/环面源请改用退化体源：POS + AXS + RAD + EXT（RAD 固定为该半径、"
            "EXT 给轴向范围）")

    # ── 面源辅助：TR / 切向量 / 法线 ──────────────────────────
    @staticmethod
    def _nrm_sign_vec(v, sign) -> tuple:
        """按 NRM 符号翻转面法线（C810 Table 3.3：NRM = 面法线符号，默认 +1）。"""
        return tuple(sign * x for x in v)

    @staticmethod
    def _plane_normal(typ, params) -> tuple:
        """平面法线（局部）：P_0 = A B C；P_1 = 三点 (P2−P1)×(P3−P1)（C810 3-17 正侧）。"""
        if typ == "P_0":
            if len(params) < 4:
                raise SourceSamplingError("P 卡参数不足（需 A B C D）")
            a, b, c = params[0], params[1], params[2]
            n = math.sqrt(a * a + b * b + c * c)
            if n < 1e-15:
                raise SourceSamplingError("P 卡法向量为零")
            return (a / n, b / n, c / n)
        if typ == "P_1":
            if len(params) < 9:
                raise SourceSamplingError("P 卡参数不足（需 9 个点坐标）")
            p1, p2, p3 = params[0:3], params[3:6], params[6:9]
            u = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
            v = (p3[0] - p1[0], p3[1] - p1[1], p3[2] - p1[2])
            n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
                 u[0] * v[1] - u[1] * v[0])
            m = math.sqrt(sum(x * x for x in n))
            if m < 1e-15:
                raise SourceSamplingError("P 卡三点共线，无法定法线")
            return (n[0] / m, n[1] / m, n[2] / m)
        raise SourceSamplingError(f"未知平面类型 {typ}")

    @staticmethod
    def _tangents(e) -> tuple:
        """平面内正交单位向量组（与 e 正交）。"""
        ref = (1.0, 0.0, 0.0) if abs(e[0]) < 0.9 else (0.0, 1.0, 0.0)
        t1 = _norm(_cross(e, ref))
        return t1, _norm(_cross(e, t1))

    @staticmethod
    def _to_world(p, origin, rotate) -> tuple:
        """局部点 → 世界点：``p_global = Rᵀ · p_local + o``。

        约定与 FreeCAD 侧 ``apply_trn`` 一致（`_freecad_csg_worker.py:1070-1078`：
        MCNP TR 卡的 9 个方向余弦按**行**存进 `rotate`，FreeCAD 矩阵按**列**组装 ⇒
        实际是转置作用），也与 `voxel_csg._surface_transform`（world→local 用 ``R⁻¹``）互逆。
        """
        if rotate is None:
            return (p[0] + origin[0], p[1] + origin[1], p[2] + origin[2])
        return (rotate[0][0] * p[0] + rotate[1][0] * p[1] + rotate[2][0] * p[2] + origin[0],
                rotate[0][1] * p[0] + rotate[1][1] * p[1] + rotate[2][1] * p[2] + origin[1],
                rotate[0][2] * p[0] + rotate[1][2] * p[1] + rotate[2][2] * p[2] + origin[2])

    def _quadric_pt(self, s, rng) -> tuple:
        """GQ/SQ 面源：按 C810 p.3-58 在**面上面积均匀**取点，并返回**向外**法线。

        C810 p.3-58 原文两句话是本实现的全部依据：
          ① 「If the value of SUR is the name of a spheroidal surface, the position of the
             particle is sampled **uniformly in area on the surface**」；
          ② 「A spheroid for this purpose **must have its axis parallel to one of the
             coordinate axes**」。
        所以：**只接受轴平行椭球**；斜置 GQ（有 D/E/F 交叉项）与双曲面/抛物面/柱面按原文
        明确报错，引导改用退化体源。

        采样法（严格面积均匀）：把椭球按半轴拉回单位球，单位球上的均匀方向 n 对应的面元
        ``dS ∝ √((bc·n_x)² + (ac·n_y)² + (ab·n_z)²)``，以该权重做拒绝采样即得面均匀。
        """
        from app.quadric import sq_to_gq
        coeffs = [float(v) for v in s["params"]]
        if s["type"] == "SQ":
            coeffs = sq_to_gq(coeffs)

        # GQ 形式：A x²+B y²+C z²+D xy+E yz+F zx+G x+H y+J z+K = 0（quadric.py 模块约定）
        A, B, C, D, E, F, G, H, J, K = coeffs
        scale = max(abs(A), abs(B), abs(C), 1e-30)
        if max(abs(D), abs(E), abs(F)) > 1e-9 * scale:
            raise SourceSamplingError(
                f"SUR 面采样：{s['type']} 是**斜置**二次曲面（含 xy/yz/zx 交叉项），"
                "C810 3-58 规定面源只能是轴平行椭球（spheroid）⇒ 请改用退化体源"
                "（POS + AXS + RAD + EXT）")
        if not (A * B > 0 and B * C > 0):
            raise SourceSamplingError(
                f"SUR 面采样：{s['type']} 不是椭球（A/B/C 不同号 ⇒ 双曲面/抛物面/柱面），"
                "C810 3-58 的面源只支持平面、球面、椭球面 ⇒ 请改用退化体源")

        ctr = (-G / (2 * A), -H / (2 * B), -J / (2 * C))
        fc = (A * ctr[0] ** 2 + B * ctr[1] ** 2 + C * ctr[2] ** 2
              + G * ctr[0] + H * ctr[1] + J * ctr[2] + K)
        semis = []
        for coef in (A, B, C):
            v = -fc / coef
            if v <= 0:
                raise SourceSamplingError(
                    f"SUR 面采样：{s['type']} 退化（半轴² = {v:.3g} ≤ 0），无法确定椭球面")
            semis.append(math.sqrt(v))
        a, b, c = semis
        w_max = max(b * c, a * c, a * b)
        for _ in range(5000):
            nx, ny, nz = _isotropic(rng)
            w = math.sqrt((b * c * nx) ** 2 + (a * c * ny) ** 2 + (a * b * nz) ** 2)
            if w_max > 0 and rng.uniform(0.0, 1.0) <= w / w_max:
                d = (a * nx, b * ny, c * nz)
                pt = (ctr[0] + d[0], ctr[1] + d[1], ctr[2] + d[2])
                # 椭球在 p 处的外法向 ∝ (dx/a², dy/b², dz/c²)（与系数整体符号无关，恒向外）
                return pt, _norm((d[0] / (a * a), d[1] / (b * b), d[2] / (c * c)))
        raise SourceSamplingError(f"SUR 面采样：{s['type']} 面均匀拒绝采样失败（椭球过扁？）")


def sample_source(sdef_fields, distributions, geometry=None, *, n_particles=500, seed=None) -> dict:
    """SDEF 抽样编排入口（契约 §0 的对外不变量：签名与返回结构逐字不变）。

    返回 ``{"status":"ok", particles, energyRange, bounds}`` 或 ``{"status":"error", error}``。
    语义错误（认不出的变量值 / 非法 SI/SP/SB/DS 组合 / 依赖值缺失 / 几何无法判定）
    一律变成 ``status=error``，不静默降级（契约 §4）。
    """
    try:
        sampler = DistributionSampler(distributions)
        engine = _Engine(sdef_fields or {}, sampler, geometry)
        # 未实现的已声明变量（CCC/ARA/RATE）：给了值就明确报错，不静默当没看见
        engine._reject_unsupported()
        rng = random.Random(seed)
        particles = [engine.sample_one(rng, i) for i in range(int(n_particles))]
        result = _summarize(particles)
        if engine.warnings:
            # 附加键（粒子字段与三大主键不动）：把"能跑但语义有缺口"的情形说出来
            result["warnings"] = sorted(set(engine.warnings))
        return result
    except SourceSamplingError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"源抽样失败: {e}"}


def _summarize(particles: list) -> dict:
    energies = [p["energy"] for p in particles if p["energy"] and p["energy"] > 0]
    xs = [p["x"] for p in particles]
    ys = [p["y"] for p in particles]
    zs = [p["z"] for p in particles]
    if energies:
        e_min, e_max = min(energies), max(energies)
    else:
        # 无有效能量（全部 ≤0 或缺字段）→ 中性零区间。
        # 注意：不能用 (0.0, 1.0) —— 前端以 min==max 判定「无能量」
        # （SourceDemoWindow.tsx:166），且单能 δ 分布（如 SDEF ERG=14）本就该
        # 返回 [14,14]，旧实现把 e_max<=e_min 一律改成 [0,1]，等于**丢弃真实能量**。
        e_min = e_max = 0.0
    return {
        "status": "ok",
        "particles": particles,
        "energyRange": {"min": e_min, "max": e_max},
        "bounds": {
            "min": [min(xs), min(ys), min(zs)],
            "max": [max(xs), max(ys), max(zs)],
        },
    }
