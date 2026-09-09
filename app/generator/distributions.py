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

import re
from typing import Any

# ── 卡语法词表（唯一事实；源分布卡说明.md 三/四节 + MCNP5 Manual Vol II p.3-62~64）──
_SI_LETTERS = ("L", "H", "A", "S", "Q", "T", "F", "V")
_SP_LETTERS = ("D", "C", "V")
_DS_LETTERS = ("H", "L", "S", "T", "Q")
_SB_FN_CODES = ("-21", "-31")
_KIND_RE = re.compile(r"^(SI|SP|SB|DS|SC)(\d+)")


# ────────────────────────────────────────────────────────────────────────────
# 逐行结构化解析（供 parse 侧 + 前端原文→表单切换共用）
# ────────────────────────────────────────────────────────────────────────────

def _strip_inline_comment(line: str) -> str:
    """剥 $ 注释（MCNP $ 后为注释，不参与分布值）。"""
    if "$" in line:
        line = line.split("$", 1)[0]
    return line.strip()


def _parse_si(toks: list[str]) -> dict:
    """SI 行 → {"type", "values"}。无字母 = ""（MCNP 缺省 H）——L-default 修复点。"""
    typ = ""
    vals = toks
    if toks and toks[0].upper() in _SI_LETTERS:
        typ = toks[0].upper()
        vals = toks[1:]
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
    ds: dict[str, Any] = {"type": "S", "param": "", "distributionIds": []}
    if toks and toks[0].upper() in _DS_LETTERS:
        ds["type"] = toks[0].upper()
        toks = toks[1:]
    if ds["type"] == "T":
        pass  # DS T 无 param/refs
    elif toks:
        ds["param"] = toks[0]
        ds["distributionIds"] = toks[1:]
    return ds


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
            lines.append(f"DS{idx}  T")
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
