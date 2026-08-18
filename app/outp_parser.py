"""MCNP OUTP 输出 tally 解析（纯 stdlib，可单测）。

后端 /api/parse-outp 的兜底解析器。内置 pymcnp（0.9.1.dev4，editable 安装自
D:\\MCNP\\PyMCNP\\src）的 Tally_4 正则只认 MCNP6.2 系布局（`cell  N` + `energy` 表头
+ `total` 行），不认 MCNP6.1 单栅元单能仓的紧凑布局——`cell  N` 后直接两列数值
（`flux error`，无 energy 列、无 total 行）。本解析器对两类布局都容错：

- tally 块头 `1tally 4 nps = N`（块号可任意）
- 数据表有/无 energy 列（3 列 = energy/flux/error，2 列 = flux/error）
- 有/无 total 行；多栅元扁平收集，total 取最后一行（MCNP 总 total 在末尾）
- nps 优先取 problem summary 的 "run terminated when N particle histories were done"
"""

import re

_TALLY_HEAD_RE = re.compile(r'^\d+tally\s+(\d+)\s+nps\s*=\s*(\d+)', re.IGNORECASE)
_TALLY_TYPE_RE = re.compile(r'tally type\s+(\d+)', re.IGNORECASE)
_CELL_DATA_RE = re.compile(r'^cell\s+\d+\s*$', re.IGNORECASE)  # 无冒号=数据段（volumes 的 cell: 带冒号不匹配）
_NUM_RE = re.compile(r'^[+-]?(?:\d+\.?\d*|\.\d+)(?:[Ee][+-]?\d+)?$')
_HEADER_RE = re.compile(r'^(energy|flux|value|counts|errors|cell)\b', re.IGNORECASE)
_NPS_DONE_RE = re.compile(r'run terminated when\s+(\d+)\s+particle histories were done', re.IGNORECASE)


def parse_outp(text: str) -> tuple[dict, int | None, list[str]]:
    """返回 (tallies, nps, warnings)。tallies: {tnum: {type, rows, total}}。"""
    tallies: dict = {}
    nps: int | None = None
    warnings: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        m = _TALLY_HEAD_RE.match(s)
        if not m:
            nm = _NPS_DONE_RE.search(lines[i])
            if nm and nps is None:
                nps = int(nm.group(1))
            if re.search(r'\bfatal error\b', lines[i], re.IGNORECASE):
                warnings.append(s)
            i += 1
            continue

        tnum = int(m.group(1))
        t_nps = int(m.group(2))
        if nps is None:
            nps = t_nps
        i += 1

        tally_type = None
        rows: list[dict] = []
        total = None
        in_cell_data = False
        while i < len(lines):
            s = lines[i].strip()
            if not s:
                i += 1
                continue
            # tally 表结束标记
            if s.startswith('=') or s.startswith('results of') or s.startswith('tfc bin'):
                break
            tm = _TALLY_TYPE_RE.search(s)
            if tm:
                tally_type = int(tm.group(1))
                i += 1
                continue
            if _CELL_DATA_RE.match(s):
                in_cell_data = True
                i += 1
                continue
            if in_cell_data:
                if s.startswith('total'):
                    parts = s.split()
                    total = {
                        "energy": "total",
                        "flux": parts[1] if len(parts) > 1 else "",
                        "error": parts[2] if len(parts) > 2 else "",
                    }
                    i += 1
                    continue
                if _HEADER_RE.match(s):
                    i += 1
                    continue
                parts = s.split()
                if len(parts) >= 2 and _NUM_RE.match(parts[0]) and _NUM_RE.match(parts[1]):
                    if len(parts) >= 3 and _NUM_RE.match(parts[2]):
                        rows.append({"energy": parts[0], "flux": parts[1], "error": parts[2]})
                    else:
                        rows.append({"energy": "", "flux": parts[0], "error": parts[1]})
                    i += 1
                    continue
            i += 1

        if rows or total is not None:
            tallies[str(tnum)] = {
                "type": tally_type or 0,
                "rows": rows,
                "total": total or {"energy": "total", "flux": "", "error": ""},
            }
    return tallies, nps, warnings
