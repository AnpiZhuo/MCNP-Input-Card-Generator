"""FMESH/TMESH 卡体 ↔ FmeshDefinition 结构化解析（契约 §5.3 / §6）。

- FMESH 语法：`FMESHn:N/P/E GEOM=xyz ORIGIN=x0 y0 z0`（续行 IMESH=/IINTS/…）。
- TMESH 语法：`TMESHn`（标题行）+ 子卡 `RMESHn:…`（rect）/ `CMESHn:…`（cyl）。
- 边界值以原文字符串保存（不数值化），生成回放逐字（保 R1 不动点）。
- structured 字段为空时回放 `raw`（round-trip 兜底，照 D-10 raw_line 先例）。
"""
from __future__ import annotations

import re

from app.models import FmeshDefinition

_FAMILY_RE = re.compile(
    r'^(FMESH|TMESH|RMESH|CMESH)(\d*):?([NPEHAS]?)$', re.IGNORECASE
)
_KEY_RE = re.compile(r'^([A-Za-z]+)=(.*)$')

_KEYS = {
    "GEOM": "geom", "ORIGIN": "origin", "IMESH": "imesh", "IINTS": "iints",
    "JMESH": "jmesh", "JINTS": "jints", "KMESH": "kmesh", "KINTS": "kints",
    "EMESH": "emesh", "EMINTS": "emints", "EINTS": "emints",  # EINTS/EMINTS 容错
    "TMESH": "tmesh", "TMINTS": "tmints", "TINTS": "tmints",  # TINTS/TMINTS 容错
    "AXS": "axs", "VEC": "vec", "TR": "tr",
    "MAT": "mat", "OUT": "out", "FACTOR": "factor",
}


def _has_structured(fd: FmeshDefinition) -> bool:
    """是否有可回放的结构化字段（否则回放 raw）。"""
    for attr in ("origin", "imesh", "iints", "jmesh", "jints", "kmesh", "kints",
                 "emesh", "emints", "tmesh", "tmints", "mat", "out",
                 "factor", "axs", "vec", "tr"):
        if getattr(fd, attr):
            return True
    return False


def parse_fmesh_lines(lines) -> list:
    """FMESH/TMESH 卡体行 → list[FmeshDefinition]。"""
    tokens = []
    for ln in lines:
        s = ln.strip()
        if s:
            tokens.extend(s.split())

    defs = []
    current = None
    pending_tmesh_number = None

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        m = _FAMILY_RE.match(tok)
        if m:
            family = m.group(1).upper()
            number_str = m.group(2)
            particle = m.group(3) or ""
            if family == "TMESH":
                # TMESHn 标题行（不建定义，仅记录卡号供后续 RMESHn/CMESHn 子卡）
                pending_tmesh_number = int(number_str) if number_str else None
                i += 1
                continue
            # FMESH / RMESH / CMESH：建定义
            number = int(number_str) if number_str else (pending_tmesh_number or 0)
            kind = "FMESH" if family == "FMESH" else "TMESH"
            geom = "xyz" if family in ("FMESH", "RMESH") else "cyl"
            current = FmeshDefinition(
                number=number, kind=kind, particle=particle, geom=geom,
            )
            defs.append(current)
            i += 1
            continue
        km = _KEY_RE.match(tok)
        if km:
            key = km.group(1).upper()
            attr = _KEYS.get(key)
            if attr is None or current is None:
                i += 1
                continue
            vals = [km.group(2)] if km.group(2) else []
            j = i + 1
            while j < len(tokens):
                nt = tokens[j]
                if _FAMILY_RE.match(nt) or _KEY_RE.match(nt):
                    break
                vals.append(nt)
                j += 1
            if attr == "geom":
                # GEOM 值必须单 token（`GEOM=X Y Z` 非法，MCNP 只认 GEOM=XYZ/CYL）；
                # 只取首值，防御空格拆开。
                value = vals[0] if vals else ""
            else:
                value = " ".join(v for v in vals if v)
            setattr(current, attr, value)
            i = j
            continue
        i += 1

    # raw 兜底：结构化字段为空时保 raw 原文
    cleaned = [ln.rstrip() for ln in lines if ln.strip()]
    joined_raw = "\n".join(cleaned)
    for fd in defs:
        if not _has_structured(fd) and not fd.raw:
            fd.raw = joined_raw

    # CMESH(cyl)：v1 渲染不支持 → round-trip 保留 raw（AXS/VEC 等非结构化字段不丢，
    # 且不得把 CMESH 回放成 RMESH）。清结构化字段，emit 走 raw 回放。
    for fd in defs:
        if fd.kind == "TMESH" and (fd.geom or "").lower() != "xyz":
            fd.raw = _extract_subcard_raw(cleaned, "CMESH", fd.number) or fd.raw
            fd.origin = fd.imesh = fd.iints = fd.jmesh = fd.jints = ""
            fd.kmesh = fd.kints = fd.emesh = fd.emints = fd.tmesh = ""
            fd.tmints = fd.mat = fd.out = fd.factor = ""
            fd.axs = fd.vec = fd.tr = ""

    if not defs and pending_tmesh_number is None and tokens:
        # 无法识别为结构化 → 兜底 raw 单条
        first = _FAMILY_RE.match(tokens[0])
        if first:
            number = int(first.group(2)) if first.group(2) else 0
            fd = FmeshDefinition(number=number,
                                 kind="FMESH" if first.group(1).upper() == "FMESH" else "TMESH",
                                 raw=joined_raw)
            defs.append(fd)
    return defs


def fmesh_defs_to_lines(defs) -> list:
    """list[FmeshDefinition] → 卡体行（structured 或 raw 回放）。"""
    out = []
    for fd in defs:
        if fd.kind == "TMESH":
            # TMESH 恒带标题行
            out.append(f"TMESH{fd.number}")
            if (fd.geom or "xyz").lower() != "xyz" and fd.raw:
                # CMESH(cyl)：原样回放 raw（保留 AXS/VEC 等非结构化字段）
                for ln in fd.raw.split("\n"):
                    if ln.strip():
                        out.append(ln.rstrip())
            elif _has_structured(fd):
                out.extend(_card_lines(fd, sub="RMESH"))
            elif fd.raw:
                # TMESH raw 兜底（结构化空但非 CMESH）
                for ln in fd.raw.split("\n"):
                    if ln.strip():
                        out.append(ln.rstrip())
            continue
        if not _has_structured(fd):
            raw = fd.raw
            if raw:
                for ln in raw.split("\n"):
                    if ln.strip():
                        out.append(ln.rstrip())
            continue
        out.extend(_card_lines(fd, sub="FMESH" if fd.kind == "FMESH" else "RMESH"))
    return out


def _extract_subcard_raw(cleaned: list, prefix: str, number: int) -> str:
    """从原始行提取某子卡（如 CMESHn）卡体原文（含后续 5 空格续行）。"""
    out = []
    started = False
    for ln in cleaned:
        if re.match(rf'^{prefix}{number}(?::|\s)', ln, re.IGNORECASE):
            started = True
            out.append(ln)
            continue
        if started:
            if len(ln) - len(ln.lstrip()) >= 5:
                out.append(ln)
            else:
                break
    return "\n".join(out)


def _card_lines(fd: FmeshDefinition, sub: str) -> list:
    particle = f":{fd.particle}" if fd.particle else ""
    # GEOM 值连写：只取首 token（`GEOM=XYZ`/`GEOM=CYL`），避免 `GEOM=X Y Z` 非法输出。
    geom_raw = (fd.geom or "").strip()
    geom_token = geom_raw.split()[0] if geom_raw else "xyz"
    head = f"{sub}{fd.number}{particle} GEOM={geom_token}"
    if fd.origin:
        head += f" ORIGIN={fd.origin}"
    lines = [head]
    for k, v in (("IMESH", fd.imesh), ("IINTS", fd.iints), ("JMESH", fd.jmesh),
                 ("JINTS", fd.jints), ("KMESH", fd.kmesh), ("KINTS", fd.kints),
                 ("EMESH", fd.emesh), ("EMINTS", fd.emints), ("TMESH", fd.tmesh),
                 ("TMINTS", fd.tmints), ("MAT", fd.mat), ("OUT", fd.out),
                 ("FACTOR", fd.factor), ("AXS", fd.axs), ("VEC", fd.vec),
                 ("TR", fd.tr)):
        if v:
            lines.append(f"     {k}={v}")
    return lines
