"""MCNP OUTP 输出 tally 解析（纯 stdlib，可单测）。

后端 /api/parse-outp 的兜底解析器。内置 pymcnp（0.9.1.dev4，editable 安装自
D:\\MCNP\\PyMCNP\\src）的 Tally_4 正则只认 MCNP6.2 系布局（`cell  N` + `energy` 表头
+ `total` 行），不认 MCNP6.1 单栅元单能仓的紧凑布局——`cell  N` 后直接两列数值
（`flux error`，无 energy 列、无 total 行）。本解析器对两类布局都容错：

- tally 块头 `1tally 4 nps = N`（块号可任意，不区分 tally 类型）
- 数据块标记泛化：`cell N`（F4/F6/F7/F8 等）、`surface N`（F1/F2）、`detector N`（F5）
  （volumes/surfaces 段的 `cell:`/`surfaces:` 带冒号不匹配）
- 数据表有/无 energy 列（3 列 = energy/通量/error，2 列 = 通量/error）
- 有/无 total 行；多栅元扁平收集，total 取最后一行（MCNP 总 total 在末尾）
- nps 优先取 problem summary 的 "run terminated when N particle histories were done"

已知边界：F1/F2 的角度分仓等多维表按前 3 列 best-effort 映射；
MCNP6.2 系输出优先走内置 pymcnp（Outp.from_mcnp().to_dataframe()）。
"""

import re

_TALLY_HEAD_RE = re.compile(r'^\d+tally\s+(\d+)\s+nps\s*=\s*(\d+)', re.IGNORECASE)
_TALLY_TYPE_RE = re.compile(r'tally type\s+(\d+)', re.IGNORECASE)
_BLOCK_DATA_RE = re.compile(r'^(cell|surface|detector)\s+\S+\s*$', re.IGNORECASE)  # 无冒号=数据段（cell:/surfaces: 带冒号不匹配）
_NUM_RE = re.compile(r'^[+-]?(?:\d+\.?\d*|\.\d+)(?:[Ee][+-]?\d+)?$')
_HEADER_RE = re.compile(r'^(energy|flux|value|counts|errors|cell)\b', re.IGNORECASE)
_NPS_DONE_RE = re.compile(r'run terminated when\s+(\d+)\s+particle histories were done', re.IGNORECASE)

# ── KCODE 逐周期 keff（print table 175）────────────────────────────────────────
_NUM = r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?'
# 表头锚点：整张周期表只认这一句（"skip 周期"表与"batch size"表表头措辞不同，天然排除）
_KEFF_CYCLE_TABLE_RE = re.compile(
    r'individual and average keff estimator results by cycle', re.IGNORECASE)
# 表行：``cycle  histories | k(coll)  k(abs)  k(track) | <累计平均...>``（累计平均段可缺）
_KEFF_CYCLE_ROW_RE = re.compile(
    r'^\s*(\d+)\s+\d+\s*\|\s*(' + _NUM + r')\s+(' + _NUM + r')\s+(' + _NUM + r')\s*\|')
# 表 175 前段的单行式：``cycle  1  k(collision)  1.044348  prompt removal lifetime(abs) ...``
_KEFF_CYCLE_LINE_RE = re.compile(
    r'^\s*cycle\s+(\d+)\s+k\(collision\)\s+(' + _NUM + r')', re.IGNORECASE)
# 结果段最终值：``the final estimated combined collision/absorption/track-length keff = X
# with an estimated standard deviation of Y``
_KEFF_FINAL_COMBINED_RE = re.compile(
    r'final estimated combined collision/absorption/track-length keff\s*=\s*(' + _NUM +
    r')\s+with an estimated standard deviation of\s+(' + _NUM + r')', re.IGNORECASE)


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
            if _BLOCK_DATA_RE.match(s):
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


def parse_keff_cycles(text: str) -> dict | None:
    """OUTP（``.o``）逐周期 keff 序列 → ``{cycles, mean, std, combined}``；无则 None。

    两条来源，命中任一即可：

    1. print table 175 的
       ``1individual and average keff estimator results by cycle`` 表：
       ``cycle  histories | k(coll)  k(abs)  k(track) | <累计平均与 σ ...>``
       （实测 600 行，每 10 行一条 ``---`` 分隔线）。取 **k(collision)** 作为序列。
    2. 表 175 前段的单行式
       ``cycle  N  k(collision) X  prompt removal lifetime(abs) ...``（同样是逐周期
       k(collision)）。

    两条来源取的都是 k(collision)，与真实 mctal 的 ``kcode`` 块第 1 列同口径，
    因此同一算例的 ``.o`` 与 ``mctal`` 解析结果应逐值相等（见单测交叉校验）。

    ``std`` 恒为空列表 —— MCNP 不逐周期写 σ；最终值与其 σ 取
    ``combined``（"final estimated combined ... keff = X with an estimated
    standard deviation of Y"）。
    """
    lines = text.splitlines()
    cycles: list[int] = []
    mean: list[float] = []

    start = None
    for i, line in enumerate(lines):
        if _KEFF_CYCLE_TABLE_RE.search(line):
            start = i + 1
            break
    if start is not None:
        for line in lines[start:]:
            s = line.strip()
            if not s:
                if cycles:
                    break
                continue
            if s.startswith(('---', '===')):     # 表内分隔线
                continue
            m = _KEFF_CYCLE_ROW_RE.match(line)
            if not m:
                if cycles:                        # 数据行之后的非数据行 = 表尾
                    break
                continue                          # 表头/列说明行
            cycles.append(int(m.group(1)))
            mean.append(float(m.group(2)))

    if not mean:                                  # 单行式兜底
        for line in lines:
            m = _KEFF_CYCLE_LINE_RE.match(line)
            if m:
                cycles.append(int(m.group(1)))
                mean.append(float(m.group(2)))

    if not mean:
        return None

    combined = None
    m = _KEFF_FINAL_COMBINED_RE.search(text)
    if m:
        combined = {"mean": float(m.group(1)), "std": float(m.group(2))}
    return {"cycles": cycles, "mean": mean, "std": [], "combined": combined}
