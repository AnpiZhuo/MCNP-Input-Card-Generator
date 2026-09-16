"""
distributions — SI/SP/SB/DS/SC 分布子系统的深度模块（codebase-design）。

设计（设计文档 design_hybrid_sisp_interface.md 的落地形态，按用户拍板调整）：
  每条分布（Dn 家族）持有「结构化字段 + 原文 rawText」双态，按 editMode 决定权威侧：
    - editMode == "raw"        → 发射时 rawText 逐字直通（导入文件的直接形态，round-trip 字节级一致）
    - editMode == "structured" → 发射时由结构化字段规范重建（默认/新建的规范形态）
  同步：sync_entry / entry_to_raw_lines 在两侧之间转换；结构化解析器保证
  无字母 SI 记 type=""（不再回填 "L"，MCNP 缺省为 H——根因 #L-default）。

本模块是解析器（core.py）与生成器（inp_generator.py）共用的唯一语法知识源；
外部（AI / MCP / 前端）只把 sdef_distributions 当不透明 JSON 字符串传递，
schema 的唯二真实消费者是 parse 侧（写入）与 generate 侧（读取）。

v2 schema（adv.sdef_distributions 内 JSON 串，数组 = 按 id 升序的条目列表）：
    [
      {
        "id": 2,
        "paramRef": "EXT",          // 引用该 Dn 的 SDEF 变量（UI 展示用）
        "auto": false,
        "editMode": "raw",          // "raw" | "structured"；缺失/空 = structured
        "rawText": "SI2 -5.5 5.5\nSP2 0 1",   // 原文行（editMode=raw 时权威）
        "si":  {"type": "",  "values": ["-5.5", "5.5"]} | null,
        "sp":  {"type": "",  "values": ["0", "1"], "fnCode": "", "fnParams": []} | null,
        "sb":  {"type": "D", "values": [...]} | null,
        "ds":  {"type": "S", "param": "...", "distributionIds": [...]} | null,
        "sc":  "源注释卡文字" | null
      }, ...
    ]
  旧 v1 条目（无 editMode/rawText）仍被接受：按 structured 处理（emit 走规范重建）。
"""

from __future__ import annotations

import math
import random
import re
from typing import Any

import numpy as np

# ── 卡语法词表（唯一事实；源分布卡说明.md 三/四节 + C810 p.3-63~3-67）──
# C810 3-63 原文（SI option）：omitted or H = bin boundaries for a histogram distribution；
# L = discrete source variable values；A = **points where a probability density distribution
# is defined**；S = **distribution numbers**。
# ⚠ 2026-09-16 修正：旧注释/报错文案写作「H 直方图/L 离散/A **三角**/S **对数**」——
# 「三角」「对数」在 C810 正文里**不存在**，会让用户把 A（概率密度定义点，点间线性插值）
# 与 S（分布号，可嵌套约 20 层）理解错。
_SI_LETTERS = ("L", "H", "A", "S")
_SP_LETTERS = ("D", "C", "V")
_DS_LETTERS = ("H", "L", "S", "T", "Q")
_SB_FN_CODES = ("-21", "-31")
_KIND_RE = re.compile(r"^(SI|SP|SB|DS|SC)(\d+)")


class SourceSamplingError(ValueError):
    """源/分布语义错误（MCNP 语义错误；调用方捕获后转 error 提示，不静默降级）。

    TD-24（t5）：类定义上移到词表之后——parse 侧（`_parse_si`）也要用它报"非法 SI 类型"，
    原先定义在文件下半部分（采样小节），语义上不该只属于采样。
    """


# ────────────────────────────────────────────────────────────────────────────
# 逐行结构化解析（供 parse 侧 + 前端原文→表单切换共用）
# ────────────────────────────────────────────────────────────────────────────

def _strip_inline_comment(line: str) -> str:
    """剥 $ 注释（MCNP $ 后为注释，不参与分布值）。"""
    if "$" in line:
        line = line.split("$", 1)[0]
    return line.strip()


_LEGACY_SI_LETTERS = ("V",)  # TD-24（t5）：仅解析容忍、非 C810 合法类型，见 _parse_si


def _parse_si(toks: list[str]) -> dict:
    """SI 行 → {"type", "values"}。无字母 = ""（MCNP 缺省 H）——L-default 修复点。

    TD-24（t5，两段处置）：
    1. **合法类型收紧为 H/L/A/S**（`_SI_LETTERS` 已同步收紧，C810 权威）。此前未知首 token
       会被**当成数值**塞进 values，后续 `_floats` 抛"分布值无法解析为数值"——归因错误
       （真问题是非法 SI 类型）。现对"纯字母且不在白名单"直接明确报错；`D1/D2` 这类分布
       引用含数字、非字母-only，不受影响（仍按无字母 SI 处理）。
    2. **`V` 仅作历史输入的解析容忍**（TD-35 已于 2026-09-10 修复生成侧）：旧版本生成器曾对
       POS_VEC 发 `SI{di}  V  <平坦值>`（`inp_generator._build_multi_sisp_cards`），
       若在这里直接 raise，**旧输入卡**的 生成→解析→再生成 往返会当场崩。
       现 **`V` 仍解析通过**（type="V"，旧卡往返语义不变），但语义上不是 C810 合法类型 ——
       **抽样侧 `_sample_entry` 仍会对它报"SI 类型 无效"**（即"越界使用仍会失败"）。
       ⚠️ **生成侧已改发合法 `L`**（2026-09-10 用户裁决）：POS_VEC 是位置向量列表，
       按 C810 用 `L` 才对；故**新生成的卡不再含 `V`**，本容忍分支只为旧文件保留。
    """
    typ = ""
    vals = toks
    if toks and toks[0].upper() in _SI_LETTERS:
        typ = toks[0].upper()
        vals = toks[1:]
    elif toks and toks[0].upper() in _LEGACY_SI_LETTERS:
        typ = toks[0].upper()   # 解析容忍（仓库自身生成物），非合法类型；抽样仍会报错
        vals = toks[1:]
    elif toks and re.match(r"^[A-Za-z]{1,3}$", toks[0]):
        raise SourceSamplingError(
            f"SI 类型 {toks[0]!r} 非法：C810 3-63 只允许 H（直方图分箱边界）/L（离散源变量值）"
            "/A（概率密度定义点）/S（分布号）——省略即 H")
    return {"type": typ, "values": vals}


def _parse_sp(toks: list[str]) -> dict:
    """SP 行 → {"type","values","fnCode","fnParams"}。默认 type=""（= MCNP 的 D）。"""
    sp: dict[str, Any] = {"type": "", "values": [], "fnCode": "", "fnParams": []}
    if toks and re.match(r"^-\d+$", toks[0]):
        sp["fnCode"] = toks[0]
        sp["fnParams"] = toks[1:]
    elif toks and toks[0].upper() in _SP_LETTERS:
        sp["type"] = toks[0].upper()
        sp["values"] = toks[1:]
    else:
        sp["values"] = toks
    return sp


def _parse_sb(toks: list[str]) -> dict:
    sb: dict[str, Any] = {"type": "D", "values": toks}
    if toks and toks[0] in _SB_FN_CODES:
        sb["type"] = toks[0]
        sb["values"] = toks[1:]
    elif toks and toks[0].upper() == "D":
        sb["type"] = "D"
        sb["values"] = toks[1:]
    return sb


def _parse_ds(toks: list[str]) -> dict:
    """DS 行 → {"type", "param", "distributionIds"}。

    MCNP 形态（app/docs/源分布卡说明.md:171-178，源自 C810 p.3-63）：
      DSn H J1 ... Jk       （直方图 J 列表）
      DSn L J1 ... Jk       （离散 J 列表）
      DSn S S1 ... Sk       （分布编号列表）
      DSn T                 （匹配模式，无数据；若带数据按 I1 J1 … 对）
      DSn Q V1 S1 V2 S2 ... （分段区间 → 分布编号）

    **数据统一落在 `distributionIds`**（前端 DsEntry 也是这个字段，避免双字段漂移）：
      - S：全是分布编号
      - H/L/Q/T：全是数据 token（J 列表 / V-S 对 / I-J 对）

    `param` 仅在**首 token 非数值**时保留（兼容 DS2 S ERG 3 4 这类带变量名的写法）；
    首 token 是数值时**不再吞掉它**——历史 bug：`DS1 S 2 3` 曾把 2 当 param、ids 变 ["3"]，
    取索引 0 得到分布 3（应为 2），使真实导入的 DS 依赖链整体右移一位。
    """
    ds: dict[str, Any] = {"type": "S", "param": "", "distributionIds": []}
    if toks and toks[0].upper() in _DS_LETTERS:
        ds["type"] = toks[0].upper()
        toks = toks[1:]
    if toks and not _is_number_tok(toks[0]):
        ds["param"] = toks[0]
        toks = toks[1:]
    ds["distributionIds"] = toks
    return ds


_NUM_TOK_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


def _is_number_tok(tok: str) -> bool:
    """token 是否为纯数值（用于区分 DS 的 param（变量名）与数据起点）。"""
    return bool(_NUM_TOK_RE.match(str(tok).strip()))


def _family_lines_to_structured(raw_lines: list[str], eid: int) -> dict:
    """一个家族的全部原文行 → 结构化字段 dict（{"si","sp","sb","ds","sc"}，缺失为 None）。

    raw_lines 的行首必须带 SI{n}/SP{n}/… 前缀（行内 $ 注释被剥，不参与值）。
    """
    out: dict[str, Any] = {"si": None, "sp": None, "sb": None, "ds": None, "sc": None}
    for line in raw_lines:
        s = line.strip()
        if not s:
            continue
        upper = s.split()[0].upper() if s.split() else ""
        m = re.match(r"^(SI|SP|SB|DS|SC)(\d+)", upper)
        if not m:
            continue
        kind, num = m.group(1), int(m.group(2))
        if num != eid:
            continue
        rest = _strip_inline_comment(s[m.end():]).split()
        if kind == "SI":
            out["si"] = _parse_si(rest)
        elif kind == "SP":
            out["sp"] = _parse_sp(rest)
        elif kind == "SB":
            out["sb"] = _parse_sb(rest)
        elif kind == "DS":
            out["ds"] = _parse_ds(rest)
        elif kind == "SC":
            # SCn 源注释卡：卡名后整段文字（含 $ 视为内容一部分，不复用注释剥离）
            out["sc"] = s[m.end():].strip()
    return out


def parse_distribution_lines(lines: list[str]) -> list[dict]:
    """SI/SP/SB/DS/SC 原文行 → v2 条目列表（editMode="raw"，rawText 逐字保留）。

    按行首数字 id 分组、组内保持原文出现顺序；条目按 id 首次出现顺序排列。
    每条的 si/sp/sb/ds/sc 结构化字段**同时**由原文派生（供 UI/编辑/链检测，
    权威发射仍以 rawText 为准）。
    """
    entries: dict[int, dict] = {}
    order: list[int] = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        upper = s.split()[0].upper() if s.split() else ""
        m = _KIND_RE.match(upper)
        if not m:
            continue
        eid = int(m.group(2))
        if eid not in entries:
            entries[eid] = {
                "id": eid, "paramRef": "", "auto": False,
                "editMode": "raw", "rawText": "",
                "si": None, "sp": None, "sb": None, "ds": None, "sc": None,
            }
            order.append(eid)
        entries[eid]["rawText"] += (s + "\n")
    out = []
    for eid in order:
        e = entries[eid]
        e["rawText"] = e["rawText"].rstrip("\n")
        structured = _family_lines_to_structured(e["rawText"].split("\n"), eid)
        for k, v in structured.items():
            e[k] = v
        out.append(e)
    return out


# ────────────────────────────────────────────────────────────────────────────
# 结构化 → 规范文本（供 generate 侧 structured 分支 + 前端表单→原文切换共用）
# ────────────────────────────────────────────────────────────────────────────

def _format_entry_cards(entry: dict) -> list[str]:
    """单条分布的 structured 字段 → 规范 MCNP 卡行（SC/SI/SP/SB/DS 序）。

    语义与旧 `_generate_structured_distributions` 单条目一致：
      - SI type="" → 不带字母（MCNP 缺省 H）；type 有值 → "SI{idx}  {type}  values"
      - SP fnCode → "SP{idx}  {fn}  params"；type C/V → 带字母；其余 → 裸 values
      - SB -21/-31 或 D；DS 带 type/param/refs（T 无 param）
    """
    lines: list[str] = []
    idx = entry.get("id", 1)
    sc = (entry.get("sc") or "").strip()
    if sc:
        lines.append(f"SC{idx}  {sc}")
    si = entry.get("si") or {}
    si_type = (si.get("type") or "").strip()
    si_vals = [str(v) for v in (si.get("values") or []) if str(v).strip()]
    if si_vals:
        head = f"SI{idx}"
        if si_type:
            head += f"  {si_type}"
        lines.append(head + "  " + "  ".join(si_vals))
    sp = entry.get("sp") or {}
    sp_type = (sp.get("type") or "").strip()
    fn = (sp.get("fnCode") or "").strip()
    fn_params = [str(v) for v in (sp.get("fnParams") or []) if str(v).strip()]
    vals = [str(v) for v in (sp.get("values") or []) if str(v).strip()]
    if fn:
        lines.append(f"SP{idx}  {fn}" + (f"  {'  '.join(fn_params)}" if fn_params else ""))
    elif sp_type in ("C", "V"):
        lines.append(f"SP{idx}  {sp_type}" + (f"  {'  '.join(vals)}" if vals else ""))
    elif vals:
        lines.append(f"SP{idx}  {'  '.join(vals)}")
    sb = entry.get("sb")
    if sb:
        sb_type = str(sb.get("type") or "D")
        sb_vals = [str(v) for v in (sb.get("values") or []) if str(v).strip()]
        if sb_type in _SB_FN_CODES:
            lines.append(f"SB{idx}  {sb_type}" + (f"  {'  '.join(sb_vals)}" if sb_vals else ""))
        elif sb_vals:
            lines.append(f"SB{idx}  D  {'  '.join(sb_vals)}")
    ds = entry.get("ds")
    if ds:
        ds_type = str(ds.get("type") or "S").upper()
        param = (ds.get("param") or "").strip()
        refs = [str(r) for r in (ds.get("distributionIds") or []) if str(r).strip()]
        if ds_type == "T":
            # T 可带 I1 J1 … Ik Jk 匹配对（resolve_ds_t 消费 distributionIds），一并回放
            lines.append(f"DS{idx}  T" + ("  " + "  ".join(refs) if refs else ""))
        else:
            head = f"DS{idx}  {ds_type}"
            if param:
                head += f"  {param}"
            if refs:
                head += "  " + "  ".join(refs)
            lines.append(head)
    return lines


# ────────────────────────────────────────────────────────────────────────────
# 双态同步 + 发射（generate 侧统一入口）
# ────────────────────────────────────────────────────────────────────────────

def sync_entry(entry: dict) -> dict:
    """让非权威侧与权威侧一致（返回新 dict）。

    editMode=raw    → 权威是 rawText：由原文重派 structured（structured 字段可能被
                      前端/旧数据改过，一律以原文为准）。
    editMode=structured（或缺省）→ 权威是 structured：由字段重建 rawText（供切到原文时预填）。
    """
    e = dict(entry)
    mode = (e.get("editMode") or "structured").strip() or "structured"
    eid = e.get("id", 1)
    if mode == "raw":
        raw_lines = (e.get("rawText") or "").split("\n")
        e["rawText"] = "\n".join(x.strip() for x in raw_lines if x.strip())
        for k, v in _family_lines_to_structured(e["rawText"].split("\n"), eid).items():
            e[k] = v
    else:
        e["editMode"] = "structured"
        cards = _format_entry_cards(e)
        e["rawText"] = "\n".join(cards) if cards else ""
    return e


def entry_to_raw_lines(entry: dict) -> list[str]:
    """条目 → 原文行列表（按权威侧；structured 条目先规范重建，供 UI 预填原文）。"""
    e = sync_entry(entry)
    return (e.get("rawText") or "").split("\n") if (e.get("rawText") or "").strip() else []


def emit_distribution_entries(entries: list[dict]) -> list[str]:
    """v2 条目列表 → MCNP 卡行（发射唯一入口）。

    - editMode=raw 且 rawText 非空 → rawText 逐字直通（round-trip 字节级一致）
    - 否则 → 结构化规范重建（含 L-default 修复：无字母 SI 不再被打印成 L）
    """
    out: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        mode = (entry.get("editMode") or "").strip()
        raw_text = (entry.get("rawText") or "").strip()
        if mode == "raw" and raw_text:
            for line in raw_text.split("\n"):
                if line.strip():
                    out.append(line.rstrip())
        else:
            out.extend(_format_entry_cards(entry))
    return out


# ────────────────────────────────────────────────────────────────────────────
# 合并（SSR 面源逐行并入，D-01）
# ────────────────────────────────────────────────────────────────────────────

def merge_distribution_entry(existing: list[dict], new_entry: dict) -> list[dict]:
    """把单个条目并入已有列表（按 id 合并，与旧 core._merge_sisp_entry 语义对齐）。

    结构化字段（si/sp/sb/ds/sc）仅在 new 侧非 None 时覆盖；rawText 家族行追加
    （round-trip 不丢行）；paramRef/auto/editMode 不因单卡行合并而改动。
    返回新列表（不就地修改）。existing 可为旧 v1 条目（缺 editMode/rawText）。
    """
    out = [dict(e) for e in existing]
    eid = new_entry.get("id")
    for i, e in enumerate(out):
        if e.get("id") == eid:
            merged = dict(e)
            for k in ("si", "sp", "sb", "ds", "sc"):
                if new_entry.get(k) is not None:
                    merged[k] = new_entry[k]
            if new_entry.get("rawText"):
                cur = (e.get("rawText") or "").rstrip("\n")
                merged["rawText"] = (cur + "\n" if cur else "") + new_entry["rawText"]
            out[i] = merged
            return out
    out.append(dict(new_entry))
    return out


# ────────────────────────────────────────────────────────────────────────────
# 多源 D1 键控链检测（原 inp_generator._multi_source_comment_reemit 迁入）
# ────────────────────────────────────────────────────────────────────────────

def has_d1_probability_chain(entries: list[dict]) -> bool:
    """存在 SP 卡为 D1 引用（sp.values == ["D1"]）且条目数 ≥ 2 → 多源概率键控链。"""
    if not isinstance(entries, list) or len(entries) < 2:
        return False
    return any((e.get("sp") or {}).get("values") == ["D1"] for e in entries)


def multi_source_probability_count(entries: list[dict]) -> int:
    """首张含数值 SP 卡的 values 长度（多源概率键控注释的 n）。无则 0。"""
    for e in entries:
        sp_vals = (e.get("sp") or {}).get("values") or []
        if sp_vals and sp_vals != ["D1"]:
            return len(sp_vals)
    return 0


# ────────────────────────────────────────────────────────────────────────────
# 抽样（source-demo-visualization 契约 §1 模块 A：深模块）
# ────────────────────────────────────────────────────────────────────────────

# TD-24（t5）：`SourceSamplingError` 已上移到文件顶部词表之后（parse 侧 `_parse_si` 也用它），
# 此处不再重复定义。

# C810 Table 3.4 融合谱常数（b=-1 → D-T，b=-2 → D-D）
_DT_ENERGY = 14.08
_DD_ENERGY = 2.45


def _pick(weights: list[float], rng: random.Random) -> int:
    """按权重列表选索引（权重不需归一化，可含负数视为 0）。全非正 → 抛错。"""
    ws = [max(0.0, float(w)) for w in weights]
    total = sum(ws)
    if total <= 0:
        raise SourceSamplingError("概率之和为零，无法抽样")
    r = rng.uniform(0.0, total)
    acc = 0.0
    for i, w in enumerate(ws):
        acc += w
        if r < acc:
            return i
    return len(ws) - 1


class DistributionSampler:
    """v2 分布列表 → 可反复抽样的对象（深模块：小接口 + 深实现）。

    接口：
        DistributionSampler(entries)                        # 编译（按 id 索引）
        .sample(eid, rng) -> float                          # 从分布 eid 抽一个标量值
        .resolve_ds(eid, parent_value, parent_si=None) -> dict
            # DS 卡查表：{"value": v} / {"distribution": d} / {"default": True}

    抽样覆盖（C810 §3.3.2 SI/SP/SB/DS）：
        SI H（默认）/L/A/S；SP D/C/内置函数（-2~-6/-21/-31/-41）；
        SB 表概率偏倚（权重补偿经 ``weight_factor``）；DS H/L/S/T/Q。
    """

    def __init__(self, entries):
        self._by_id: dict[int, dict] = {}
        for e in entries or []:
            if isinstance(e, dict) and e.get("id") is not None:
                try:
                    self._by_id[int(e["id"])] = e
                except (TypeError, ValueError):
                    continue

    def _entry(self, eid) -> dict:
        e = self._by_id.get(int(eid))
        if e is None:
            raise SourceSamplingError(f"分布 D{int(eid)} 未定义")
        return e

    # ── 主接口 ──────────────────────────────────────────────
    def sample(self, eid, rng: random.Random, var: str = "", cel: bool = False,
               axs: bool = False, sdef_fields: dict | None = None,
               cell_volumes: dict | None = None) -> float:
        """从分布 eid 抽一个标量。

        ``var`` = 该分布服务的源变量名（ERG/DIR/RAD/EXT/TME/X/Y/Z/CEL…，C810 Table 3.3）。
        它决定三件 MCNP 语义：① ``SP V`` 是否合法（仅 CEL，C810 3-64，由 ``cel`` 判定
        源是否为栅元源）；② 内置函数在「SI 单值」下的**对称默认**（C810 3-66 特殊默认
        3/4/5：DIR/EXT 的 ``SI x`` ⇒ 等价 ``SI −x x``；RAD 的 ``SI x`` ⇒ 等价 ``SI 0 x``）；
        ③ ``SP −21`` 不给参数 a 时的**变量默认值**（DIR=1；RAD=2，但 ``axs`` 为真或
        JSU≠0 时为 1；EXT=0）。

        ``sdef_fields`` / ``cell_volumes``：分别供 ``SI S`` 里分布号 0（= 该变量默认值，
        C810 3-64）与 ``SP V``（概率 ∝ 栅元体积，C810 3-64）使用；缺省则按"拿不到就
        明确报错/退回等概率"，不静默给错值。
        """  # noqa: D401
        return self._sample_entry(self._entry(eid), rng, 0, var=var, cel=cel, axs=axs,
                                  sdef_fields=sdef_fields, cell_volumes=cell_volumes)

    @staticmethod
    def _default_power(var, axs: bool = False) -> float:
        """C810 3-66：SP −21 的 a 默认值随变量（DIR=1；RAD=2，定义 AXS 或 JSU≠0 时 1；EXT=0）。"""
        key = (var or "").strip().upper()
        if key == "DIR":
            return 1.0
        if key == "RAD":
            return 1.0 if axs else 2.0
        if key == "EXT":
            return 0.0
        return 2.0   # 未知变量按 RAD 语义（体积均匀）兜底

    def resolve_ds(self, eid, parent_value, parent_si=None) -> dict:
        ds = self._entry(eid).get("ds")
        if not ds:
            return {"default": True}
        return self._resolve_ds(ds, float(parent_value), parent_si)

    def weight_factor(self, eid, value) -> float:
        """SB 偏倚的权重补偿（真概率 / 偏倚概率）。无 SB → 1.0。"""
        e = self._entry(eid)
        sb = e.get("sb")
        if not sb:
            return 1.0
        sp = e.get("sp") or {}
        if (sp.get("fnCode") or "").strip() or (sb.get("fnCode") or "").strip():
            return 1.0  # 内置函数偏倚（罕见）不补偿
        si = e.get("si") or {}
        si_type = (si.get("type") or "").strip().upper()
        si_vals = self._floats(si.get("values"))
        n = len(si_vals) - 1 if si_type in ("", "H") else len(si_vals)
        p_true = self._probs_of(sp, n)
        p_bias = self._probs_of(sb, n)
        i = self._index_of(value, si_type, si_vals)
        if i is None:
            return 1.0
        if p_bias[i] <= 0:
            return 1.0
        return p_true[i] / p_bias[i] if p_true[i] > 0 else 1.0

    # ── 内部：单条目抽样 ────────────────────────────────────
    def _sample_entry(self, e, rng, depth, var="", cel=False, axs=False,
                      sdef_fields=None, cell_volumes=None):
        if depth > 20:
            raise SourceSamplingError("SI S 嵌套深度超限（MCNP 上限约 20）")
        si = e.get("si") or {}
        sp = e.get("sp") or {}
        sb = e.get("sb")
        si_type = (si.get("type") or "").strip().upper()
        # ⚠ SI 的 S 类型里存的是**分布号**（可带 D 前缀），不能先过 _floats：
        # 旧顺序在 `SI1 S D2 D3` 上直接抛"分布值无法解析为数值: D2"（C810 3-64 允许 D 前缀）。
        si_vals = ([] if si_type == "S" else self._floats(si.get("values")))
        fn = (sp.get("fnCode") or "").strip()
        has_axs = bool(axs or e.get("_axs"))
        self._check_sp_v(sp, sb, var, cel)

        if fn:
            return self._sample_builtin(fn, sp, si_vals, rng, var=var, axs=has_axs)

        if si_type == "S":
            # C810 3-64：S 选项的每个分布号**可带 D 前缀**（D 可省）——
            # 旧实现直接 float('D3') → ValueError（不是 SourceSamplingError，
            # 会被兜底成"源抽样失败: could not convert string to float"）。
            ids = [self._dist_ref(v, e) for v in (si.get("values") or [])]
            sp_type = (sp.get("type") or "D").strip().upper() or "D"
            sp_vals = self._floats(sp.get("values"))
            probs = self._probs(sp_type, sp_vals, len(ids), sb, var=var,
                                si_vals=ids, cel=cel, sdef_fields=sdef_fields,
                                cell_volumes=cell_volumes)
            idx = _pick(probs, rng)
            if ids[idx] == 0:
                # C810 3-64：分布号为 0 ⇒ 该变量用**默认值**（按 SDEF 卡上的写法定，
                # 见 `_var_default`）——不是"报错"也不是"给 0"。
                return self._var_default(var, e, sdef_fields)
            return self._sample_entry(self._entry(ids[idx]), rng, depth + 1, var=var,
                                      cel=cel, axs=axs, sdef_fields=sdef_fields,
                                      cell_volumes=cell_volumes)

        if si_type in ("", "H"):
            if len(si_vals) < 2:
                raise SourceSamplingError(f"分布 D{e.get('id')} 直方图边界不足（需 ≥2）")
            n_bins = len(si_vals) - 1
            probs = self._probs((sp.get("type") or "D").strip().upper() or "D",
                                self._floats(sp.get("values")), n_bins, sb,
                                allow_leading_zero=True, var=var, si_vals=si_vals,
                                cel=cel, sdef_fields=sdef_fields,
                                cell_volumes=cell_volumes)
            idx = _pick(probs, rng)
            lo, hi = si_vals[idx], si_vals[idx + 1]
            if hi < lo:
                raise SourceSamplingError(f"分布 D{e.get('id')} 直方图边界非单调递增")
            return lo + rng.uniform(0.0, 1.0) * (hi - lo)

        if si_type == "L":
            probs = self._probs((sp.get("type") or "D").strip().upper() or "D",
                                self._floats(sp.get("values")), len(si_vals), sb,
                                var=var, si_vals=si_vals, cel=cel,
                                sdef_fields=sdef_fields, cell_volumes=cell_volumes)
            return si_vals[_pick(probs, rng)]

        if si_type == "A":
            return self._sample_A(si_vals, self._floats(sp.get("values")), rng)

        raise SourceSamplingError(f"SI 类型 {si_type or '空'} 无效（MCNP 仅支持 H/L/A/S）")

    # ── 概率解析 ────────────────────────────────────────────
    @staticmethod
    def _floats(vals) -> list[float]:
        out = []
        for v in (vals or []):
            try:
                out.append(float(v))
            except (TypeError, ValueError):
                raise SourceSamplingError(f"分布值无法解析为数值: {v}")
        return out

    def _probs(self, sp_type, sp_vals, n, sb=None, allow_leading_zero=False, *,
               var="", si_vals=None, cel=False, sdef_fields=None,
               cell_volumes=None) -> list[float]:
        """按 SP 类型把 SP 值解析成 n 个权重。

        - `sb` 非空 → 用 SB（偏倚）概率（C810 3-64：SB 全部规则同 SP 第一种形态）。
        - **`V` 选项**（C810 3-64）：`Probability is proportional to cell volume
          (times Pi if the Pi are present)` —— 只有源变量是 CEL 时合法，权重 =
          逐栅元体积（给了 Pi 再乘 Pi）。逐栅元体积由 `cell_volumes` 提供；
          任何用到的栅元缺体积 → **明确报错**（对应 MCNP 的 FATAL），不静默退化。
        """
        if sb is not None and not (sb.get("fnCode") or "").strip():
            sb_vals = self._floats(sb.get("values"))
            if sb_vals:
                sb_type = (sb.get("type") or "D").strip().upper() or "D"
                if sb_type == "V":
                    return self._resolve_v_probs(sb_vals, si_vals, cell_volumes,
                                                 allow_leading_zero)
                return self._resolve_probs(sb_type, sb_vals, n, allow_leading_zero)
        if (sp_type or "").strip().upper() == "V":
            return self._resolve_v_probs(sp_vals, si_vals, cell_volumes,
                                         allow_leading_zero)
        return self._resolve_probs(sp_type, sp_vals, n, allow_leading_zero)

    def _resolve_v_probs(self, sp_vals, si_vals, cell_volumes, allow_leading_zero=False):
        """`SP V`：权重 = 栅元体积（给了 Pi 再乘 Pi）——C810 3-64。

        SI 为 `L` 时列出栅元号；缺任何一个栅元的体积 → `SourceSamplingError`
        （对应 MCNP「MCNP cannot calculate the volume … you have a FATAL error」）。
        """
        cells = [int(float(v)) for v in (si_vals or [])]
        if not cells:
            raise SourceSamplingError("SP V 需要 SI L 给出栅元号列表（按体积加权）")
        vols = cell_volumes or {}
        out = []
        for c in cells:
            v = vols.get(c, vols.get(str(c)))
            if not v or float(v) <= 0:
                raise SourceSamplingError(
                    f"SP V 需要栅元 {c} 的体积，但几何里拿不到（C810 3-64：MCNP 算不出"
                    "体积且无 VOL 卡时是 FATAL）——请确认该栅元几何可解析，或改用 SP D/C")
            out.append(float(v))
        if sp_vals:  # 给了 Pi → 概率 ∝ 体积 × Pi
            pis = self._pad(list(sp_vals), len(cells), allow_leading_zero)
            out = [w * float(p) for w, p in zip(out, pis)]
        return out

    def _resolve_probs(self, sp_type, sp_vals, n, allow_leading_zero=False) -> list[float]:
        if n <= 0:
            return []
        if not sp_vals:
            return [1.0] * n  # 省略 SP → 等概率
        if sp_type == "C":
            # 累积概率：差分（c_i − c_{i−1}，c_0=0）为 bin 概率
            diffs = [sp_vals[0]]
            for i in range(1, len(sp_vals)):
                diffs.append(sp_vals[i] - sp_vals[i - 1])
            return self._pad(diffs, n, allow_leading_zero)
        # D / V / 其它 → 直接用值（V 的体积语义由 source_sampler 层处理）
        return self._pad(sp_vals, n, allow_leading_zero)

    @staticmethod
    def _pad(vals, n, allow_leading_zero=False) -> list[float]:
        if len(vals) == n:
            return list(vals)
        # MCNP H/C 分布：首条目可为 0 占位（H 直方图对应首个 bin 边界 / C 累积首 0）
        if allow_leading_zero and len(vals) == n + 1:
            return list(vals[1:])
        if len(vals) > n:
            return list(vals[:n])
        raise SourceSamplingError(f"SP 概率个数（{len(vals)}）与 SI 值个数不匹配（需 {n}）")

    # ── SI A 概率密度点（线性插值逆 CDF）────────────────────
    def _sample_A(self, xs, densities, rng):
        k = len(xs)
        if k < 2:
            raise SourceSamplingError("SI A 概率密度点不足（需 ≥2）")
        if len(densities) != k:
            raise SourceSamplingError(f"SI A 密度点数（{len(densities)}）与值点数（{k}）不匹配")
        for i in range(1, k):
            if xs[i] < xs[i - 1]:
                raise SourceSamplingError("SI A 密度点非单调递增")
        masses = []
        total = 0.0
        for i in range(k - 1):
            m = (densities[i] + densities[i + 1]) * 0.5 * (xs[i + 1] - xs[i])
            if m < 0:
                m = 0.0
            masses.append(m)
            total += m
        if total <= 0:
            raise SourceSamplingError("SI A 概率密度积分为零，无法抽样")
        r = rng.uniform(0.0, total)
        for i in range(k - 1):
            if r < masses[i]:
                x0, x1 = xs[i], xs[i + 1]
                d0, d1 = densities[i], densities[i + 1]
                dx = x1 - x0
                s = (d1 - d0) / dx if dx > 0 else 0.0
                # 解 s/2 t² + d0 t - r = 0（段内累积质量 = r）
                if abs(s) < 1e-15:
                    t = r / d0 if d0 > 0 else 0.0
                else:
                    disc = d0 * d0 + 2.0 * s * r
                    t = (-d0 + math.sqrt(max(0.0, disc))) / s
                return x0 + min(max(t, 0.0), dx)
            r -= masses[i]
        return xs[k - 1]

    # ── SP V 校验 / 分布号解析 / 变量默认值 ──────────────────
    #: SP V（按体积加权）只在源变量是 CEL 时有意义（C810 3-64）
    _V_ONLY_VARS = ("CEL",)
    #: 变量默认值（C810 Table 3.3）：SI S 里分布号 0 时使用
    _VAR_DEFAULTS = {"ERG": 14.0, "TME": 0.0, "WGT": 1.0, "RAD": 0.0, "EXT": 0.0,
                     "DIR": 0.0, "XYZ": 0.0, "CEL": 1.0}

    @staticmethod
    def _check_sp_v(sp, sb, var, cel=False) -> None:
        """`SP V`（或 `SB V`）仅对 **CEL 源**合法（C810 3-64：V = for cell distributions only）。

        判定用两个条件之一：① 源变量本身就是 `CEL`（`CEL=Dn` 那种写法）；
        ② 本次抽样来自栅元源（`cel=True`，编排层给出）。二者都不是才报错 ——
        因为 V 的语义是"按**栅元**体积加权"，与"这个分布挂在哪个变量上"无关。
        """
        vname = (var or "").strip().upper()
        for card, obj in (("SP", sp), ("SB", sb)):
            if not obj:
                continue
            typ = (obj.get("type") or "").strip().upper()
            if typ == "V" and vname != "CEL" and not cel:
                raise SourceSamplingError(
                    f"{card} V（按体积加权）只能用于 CEL 源（C810 3-64："
                    "V−for cell distributions only）——当前既不是 CEL 源变量"
                    f"（{var or '（未标注）'}），源也不是栅元源")

    @staticmethod
    def _var_default(var, e, sdef_fields=None):
        """SI S 中分布号 0 → **该变量的默认值**（C810 3-64）。

        优先读 SDEF 卡本身写的字面值（Table 3.3：ERG=14、TME=0、WGT=1、RAD/EXT/DIR=0、
        X/Y/Z=0、CEL 由位置定），拿不到才退回 Table 3.3 的静态默认。
        """
        key = (var or "").strip().upper()
        field = {"ERG": "sdef_erg", "TME": "sdef_tme", "WGT": "sdef_wgt",
                 "RAD": "sdef_rad", "EXT": "sdef_ext", "DIR": "sdef_dir"}.get(key)
        if field and sdef_fields:
            raw = str(sdef_fields.get(field) or "").strip()
            if raw and not raw.upper().startswith("F") and "D" != raw[:1].upper():
                try:
                    return float(raw.split()[0])
                except (TypeError, ValueError):
                    pass
        if key in ("X", "Y", "Z"):
            return 0.0
        return DistributionSampler._VAR_DEFAULTS.get(key, 0.0)

    def _dist_ref(self, tok, e) -> int:
        """SI S 的分布号 token → int；**D 前缀可选**（C810 3-64）。"""
        s = str(tok).strip().upper()
        if s.startswith("D"):
            s = s[1:]
        try:
            return int(float(s))
        except (TypeError, ValueError):
            raise SourceSamplingError(
                f"SI S 的分布号 {tok!r} 无法解析为整数（C810 3-64：分布号可带 D 前缀或省略）")

    # ── 内置函数（C810 Table 3.4）───────────────────────────
    def _sample_builtin(self, fn, sp, si_vals, rng, var="", axs=False):
        params = self._floats(sp.get("fnParams") or [])
        if fn == "-2":
            self._need(params, 0, 1, "-2")
            a = params[0] if params else 1.2895
            return a * (-math.log(rng.uniform(1e-15, 1.0)) + 0.5 * rng.gauss(0, 1) ** 2)
        if fn == "-5":
            self._need(params, 0, 1, "-5")
            a = params[0] if params else 1.2895
            return -a * math.log(rng.uniform(1e-15, 1.0) * rng.uniform(1e-15, 1.0))
        if fn == "-3":
            self._need(params, 0, 2, "-3")
            a = params[0] if len(params) > 0 else 0.965
            b = params[1] if len(params) > 1 else 2.29
            return self._inverse_cdf(lambda E: math.exp(-E / a) * math.sinh(math.sqrt(b * E)),
                                     lo=0.0, hi=max(20.0, 12.0 * a), rng=rng,
                                     key=("watt", float(a), float(b)))
        if fn == "-4":
            self._need(params, 0, 2, "-4")
            a = abs(params[0]) if params else 0.01
            b = params[1] if len(params) > 1 else -1
            b = self._fusion_energy(b)
            return self._trunc_gauss(b, a / math.sqrt(2.0), rng)
        if fn == "-6":
            self._need(params, 0, 2, "-6")
            a = abs(params[0]) if params else 0.01
            b = params[1] if len(params) > 1 else -1
            b = self._fusion_energy(b)
            v = rng.gauss(math.sqrt(max(b, 0.0)), a / math.sqrt(2.0))
            return max(0.0, v) ** 2
        if fn == "-21":
            # C810 3-66：`Default depends on the variable. For DIR, a = 1. For RAD, a = 2,
            # **unless AXS is defined or JSU ≠ 0**, in which case a = 1. For EXT, a = 0.`
            self._need(params, 0, 1, "-21")
            a = params[0] if params else self._default_power(var, axs=bool(axs))
            lo, hi = self._range(si_vals, (0.0, 1.0), var)
            return self._power_law(a, lo, hi, rng)
        if fn == "-31":
            # C810 3-66：指数分布默认 a = 0（退化为区间内均匀）
            self._need(params, 0, 1, "-31")
            a = params[0] if params else 0.0
            lo, hi = self._range(si_vals, (-1.0, 1.0), var)
            return self._exponential(a, lo, hi, rng)
        if fn == "-41":
            self._need(params, 2, 2, "-41")
            a, b = params[0], params[1]
            sigma = a / math.sqrt(8.0 * math.log(2.0))
            return rng.gauss(b, sigma)
        raise SourceSamplingError(f"内置函数 {fn} 不支持抽样")

    @staticmethod
    def _need(params, lo, hi, fn):
        if not (lo <= len(params) <= hi):
            raise SourceSamplingError(f"内置函数 {fn} 参数个数错误（需 {lo}~{hi}，实 {len(params)}）")

    @staticmethod
    def _fusion_energy(b):
        if b == -1:
            return _DT_ENERGY
        if b == -2:
            return _DD_ENERGY
        return b

    @staticmethod
    def _range(si_vals, default, var=""):
        """内置函数的取样区间（C810 3-66「Special defaults」规则 3/4/5）。

        - 无 SI ⇒ 该函数的默认区间（−21 的 DIR ⇒ [0,1]、−31 的 DIR/EXT ⇒ [−1,1]）。
        - **SI 单值 x**：DIR/EXT ⇒ [−x, x]（规则 5：`If SI x and SP −21 or SP −31 are
          present for EXT, the SI is treated as if it were SI −x x`）；RAD ⇒ [0, x]
          （规则 4：`If SI x and SP −21 are present for RAD … SI 0 x`）。
        - SI 双值 ⇒ 原样 [I1, I2]。
        ⚠ 2026-09-16 修正：旧实现不分变量一律 (0, x)，导致 EXT/DIR 上的
        `SI1 5 / SP1 −31 1.5` 只在 [0,5] 抽（负半轴整段丢失，实测 0/400 负值）。
        """
        vals = list(si_vals or [])
        if not vals:
            return default
        if len(vals) == 1:
            x = vals[0]
            if (var or "").strip().upper() in ("DIR", "EXT"):
                return (min(-abs(x), abs(x)), max(-abs(x), abs(x)))
            return (0.0, x)
        return (vals[0], vals[1])

    @staticmethod
    def _power_law(a, lo, hi, rng):
        # p(x)=c|x|^a。数值逆 CDF 统一处理同号/跨零区间（避免负数小数次方）。
        if hi <= lo:
            raise SourceSamplingError("幂律范围无效（hi<=lo）")
        return DistributionSampler._inverse_cdf(
            lambda x: abs(x) ** a, lo, hi, rng,
            key=("pl", float(a), float(lo), float(hi)))

    @staticmethod
    def _exponential(a, lo, hi, rng):
        if hi <= lo:
            raise SourceSamplingError("指数范围无效（hi<=lo）")
        u = rng.uniform(0.0, 1.0)
        if abs(a) < 1e-15:
            return lo + u * (hi - lo)
        ea_lo, ea_hi = math.exp(a * lo), math.exp(a * hi)
        return (1.0 / a) * math.log(ea_lo + u * (ea_hi - ea_lo))

    @staticmethod
    def _trunc_gauss(mean, sigma, rng):
        for _ in range(100):
            x = rng.gauss(mean, sigma)
            if x > 0:
                return x
        return max(mean, 0.0)

    # 数值逆 CDF 的网格缓存：`_inverse_cdf` 每次调用都要重算 4096 点的梯形积分
    # （实测 4.2 ms/次）——抽样 500 粒子时它是最主要的开销，缓存后同一分布降到 ~10 µs。
    # 键必须**结构化**（函数号 + 参数 + 区间），**不能用 id(pdf)**：临时 lambda 被回收后
    # id 会被复用，会把别的分布的概率网格当成本次的结果（实测 DIR 均值从 0.667 漂到 0.709）。
    _CDF_CACHE: dict = {}

    @staticmethod
    def _inverse_cdf(pdf, lo, hi, rng, n=4096, key=None):
        """数值逆 CDF：pdf 在 [lo,hi] 上梯形积分 → 查表线性插值（网格按 ``key`` 缓存）。"""
        cache_key = key if key is not None else (id(pdf), float(lo), float(hi), int(n))
        entry = DistributionSampler._CDF_CACHE.get(cache_key)
        if entry is None:
            xs = np.linspace(lo, hi, n + 1)
            ys = np.array([max(0.0, pdf(float(x))) for x in xs])
            cdf = np.zeros(n + 1)
            for i in range(1, n + 1):
                cdf[i] = cdf[i - 1] + 0.5 * (ys[i - 1] + ys[i]) * (xs[i] - xs[i - 1])
            total = float(cdf[n])
            if total <= 0:
                raise SourceSamplingError("内置函数概率密度积分为零")
            if len(DistributionSampler._CDF_CACHE) > 64:
                DistributionSampler._CDF_CACHE.clear()
            entry = (xs, cdf, total)
            DistributionSampler._CDF_CACHE[cache_key] = entry
        xs, cdf, total = entry

        def draw():
            u = rng.uniform(0.0, total)
            i = int(np.searchsorted(cdf, u)) - 1
            i = max(0, min(i, n - 1))
            seg = float(cdf[i + 1] - cdf[i])
            frac = (u - float(cdf[i])) / seg if seg > 0 else 0.0
            return float(xs[i]) + frac * (float(xs[i + 1]) - float(xs[i]))
        return draw()

    # ── DS 卡查表（C810 DS 卡 H/L/S/T/Q）────────────────────
    def _resolve_ds(self, ds, parent_value, parent_si) -> dict:
        ds_type = (ds.get("type") or "").strip().upper()
        if ds_type == "T":
            return {"default": True}  # T 需独立离散值匹配，source_sampler 用 resolve_ds_t 处理
        vals = ds.get("distributionIds") or []  # 数据统一落 distributionIds（见 _parse_ds 文档串）
        if ds_type == "Q":
            # Q: V1 S1 V2 S2 ...（V 上界 + S 分布编号）
            pairs = list(zip(vals[0::2], vals[1::2])) if len(vals) >= 2 else []
            for v, s in pairs:
                if parent_value <= float(v):
                    sid = int(float(s))
                    return {"default": True} if sid == 0 else {"distribution": sid}
            return {"default": True}
        ids = ds.get("distributionIds") or []
        if ds_type == "S":
            # S: 分布编号列表，按独立变量的离散索引直接取（J[idx]）
            idx = int(parent_value)
            if idx < 0 or idx >= len(ids):
                return {"default": True}
            sid = int(float(ids[idx]))
            return {"default": True} if sid == 0 else {"distribution": sid}
        if ds_type == "L":
            idx = int(parent_value)
            if idx < 0 or idx >= len(vals):
                return {"default": True}
            return {"value": float(vals[idx])}
        if ds_type in ("", "H"):
            # H: 连续插值（J0..Jn，对应 parent_si 的 bin 边界）
            si = self._floats(parent_si) if parent_si else []
            if len(si) < 2 or len(vals) < len(si):
                return {"default": True}
            i = self._bin_of(parent_value, si)
            lo, hi = si[i], si[i + 1]
            f = (parent_value - lo) / (hi - lo) if hi > lo else 0.0
            f = min(max(f, 0.0), 1.0)
            j0, j1 = float(vals[i]), float(vals[i + 1])
            return {"value": j0 + f * (j1 - j0)}
        raise SourceSamplingError(f"DS 类型 {ds_type or '空'} 无效（MCNP 仅支持 H/L/S/T/Q）")

    def resolve_ds_t(self, eid, parent_value) -> dict:
        """DS T 匹配模式（source_sampler 专用）：I1 J1 ... Ik Jk 成对匹配。"""
        ds = self._entry(eid).get("ds") or {}
        vals = ds.get("distributionIds") or []  # 同 _resolve_ds：数据统一落 distributionIds
        pairs = list(zip(vals[0::2], vals[1::2])) if len(vals) >= 2 else []
        for iv, jv in pairs:
            if abs(float(iv) - float(parent_value)) < 1e-12:
                return {"value": float(jv)}
        return {"default": True}

    @staticmethod
    def _ds_index(parent_value, parent_si):
        """独立变量值 → 离散索引（parent_si 为独立变量的 SI 离散值）。"""
        if not parent_si:
            return None
        for i, v in enumerate(parent_si):
            try:
                if abs(float(v) - float(parent_value)) < 1e-9:
                    return i
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _bin_of(v, si):
        for i in range(len(si) - 1):
            if si[i] <= v <= si[i + 1]:
                return i
        return 0 if v <= si[0] else len(si) - 2

    @staticmethod
    def _index_of(value, si_type, si_vals):
        if si_type in ("", "H"):
            for i in range(len(si_vals) - 1):
                if si_vals[i] <= value <= si_vals[i + 1]:
                    return i
            return None
        for i, v in enumerate(si_vals):
            if abs(v - value) < 1e-9:
                return i
        return None
