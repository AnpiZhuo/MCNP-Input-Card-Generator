"""MCNP ``mctal`` 输出解析（纯 stdlib，容错；无新依赖）。

对齐 OWEN ``src/results/parsers/mcnp.ts`` 的解析目标（k-eff 历史 / tally 表），
并覆盖真实 mctal 的结构（``version`` 行、``ktally``/``tally`` 块、nps、
能量网格、逐探测器结果与相对误差）。同 ``outp_parser`` 一样采用
「能解析多少算多少 + warnings」的容错策略。

支持两种真实文件形态（同一份 keff 语义）：

1. **OWEN 简化 mctal**（``k eff (c) <mean> <std>`` 逐周期行 + ``combined keff = ...``），
   逐周期带 σ。
2. **真实 MCNP6 mctal**：头部 ``mcnp <ver> ...`` / ``ntal <n>``，KCODE 问题的结果在文末
   ``kcode <总周期> <跳过周期> <每周期值数>`` 裸数值块里（**无字段名，只能按列定位**，
   见 ``_parse_kcode_series``）。该块**不逐周期写 σ** ⇒ ``std`` 为空列表，最终值取累计
   平均列（与 outp 的 "final estimated combined ... keff" 一致）。

返回::
    {
      "status": "ok",
      "version": float | None,
      "nps": int | None,
      "keff": {
        "cycles": [int], "mean": [float], "std": [float],
        "combined": {"mean": float, "std": float} | None,
      } | None,
      "tallies": [
        {
          "id": str, "nps": int | None,
          "energy_bins": [float] | None,
          "rows": [[float]],           # 块内数值行（结果/相对误差按出现顺序）
          "spectrum": [{"e": float, "flux": float}] | None,  # OWEN 简化两列格式
        },
      ],
      "warnings": [str],
    }
"""

from __future__ import annotations

import re

_NUM = r"[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?"

# 真实 MCNP6 mctal 的 kcode 块头：``kcode <总周期数> <跳过周期数> <每周期值数>``。
# 实测（MCNP6.1，ZEUS-1 10 Uniform Units HEU-MET-INTER-006 case 1，
# 输入 ``KCODE 10000 1.0 100 600``）为 ``kcode  600  100   19``：其后
# 600×19 个裸数值（每行 5 个，共 4 行/周期），**无字段名**。
_KCODE_HEAD_RE = re.compile(r"^kcode\s+(\d+)\s+(\d+)\s+(\d+)\b", re.IGNORECASE)

# kcode 块每周期的列（1-based）—— 对照同一算例的 .o 逐列核验得出：
#   1-3   k(collision) / k(absorption) / k(track length)，逐周期（= print table 175
#         的 "k(coll) k(abs) k(track)" 表，600 行逐个吻合）
#   4-5   prompt removal lifetime（逐周期；第 5 列 = table 175 的 lifetime(abs)）
#   6-13  活跃周期累计平均：k(coll)±σ, k(abs)±σ, k(trk)±σ, k(c/a/t)±σ
#         （第 6 列末值 0.99269 = .o "average keff estimators" 表末行 k(coll)）
#   14-15 组合 k(c/a/t) 均值±σ（"跳过前 N-1 个周期"口径：第 1/2/3 周期的
#         0.99292/0.99284/0.99283 与 .o 的 skip 0/1/2 行逐位吻合）
#   16-17 平均寿命 ± σ（末值 194.89 shake = .o 的 1.9489E-06 s）
#   18    每周期源点数（末值 10008/10131/9916 = .o neutron histories 列）
#   19    fom（末值 77699 = .o fom 列）
_KCODE_COL_KEFF = range(0, 3)      # 逐周期三个估计量（0-based）
_KCODE_COL_AVG_CAT_MEAN = 11       # 累计平均组合 k(c/a/t) 均值
_KCODE_COL_AVG_CAT_STD = 12        # 累计平均组合 k(c/a/t) σ


def _is_num(tok: str) -> bool:
    return re.fullmatch(_NUM, tok.strip()) is not None


def _parse_num_row(line: str):
    toks = line.split()
    if not toks or not all(_is_num(t) for t in toks):
        return None
    try:
        return [float(t) for t in toks]
    except ValueError:
        return None


def _parse_kcode_series(lines: list[str]) -> dict | None:
    """真实 MCNP6 mctal 的 ``kcode`` 块 → 逐周期 keff 序列；无该块返回 None。

    列语义见上方 ``_KCODE_COL_*`` 注释（按列定位，无字段名可依赖）：

    - ``mean`` = 第 1 列 k(collision) 逐周期序列（与 .o 的 table 175 同口径，
      可与 ``outp_parser.parse_keff_cycles`` 交叉校验）；
    - ``std`` = ``[]`` —— **mctal 不逐周期写 σ**（只写累计平均的 σ）；
    - ``combined`` = 第 12/13 列最后一组非零累计平均（实测
      0.99277 ± 0.00036，与 .o 的 "final estimated combined ... keff" 逐位一致）。

    容错：``每周期值数`` 或周期数与实际数值个数不符（截断运行 / 早期版本）时，
    按实际可分组的周期数截断解析；不足一个周期则返回 None。
    """
    head = None
    for i, line in enumerate(lines):
        m = _KCODE_HEAD_RE.match(line.strip())
        if m:
            head = (i, int(m.group(1)), int(m.group(2)), int(m.group(3)))
            break
    if head is None:
        return None
    start, ncyc, _nskip, nvals = head
    if ncyc <= 0 or nvals <= 0:
        return None

    vals: list[float] = []
    for line in lines[start + 1:]:
        row = _parse_num_row(line)
        if row is None:
            if vals:          # 块内只应有数值行；出现别的行即块结束
                break
            continue          # 块头与数据之间的空行
        vals.extend(row)
    if len(vals) < nvals:     # 一个完整周期都凑不齐
        return None
    ncyc = min(ncyc, len(vals) // nvals)
    rows = [vals[i * nvals:(i + 1) * nvals] for i in range(ncyc)]

    mean = [r[0] for r in rows]
    combined = None
    if nvals > _KCODE_COL_AVG_CAT_STD:
        for r in reversed(rows):
            if r[_KCODE_COL_AVG_CAT_MEAN] != 0.0:
                combined = {"mean": r[_KCODE_COL_AVG_CAT_MEAN],
                            "std": r[_KCODE_COL_AVG_CAT_STD]}
                break
    return {
        "cycles": list(range(1, ncyc + 1)),
        "mean": mean,
        "std": [],            # mctal 无逐周期 σ（见 docstring）
        "combined": combined,
    }


def parse_mctal(text: str) -> dict:
    """解析 mctal 文本 → dict（结构见模块 docstring）。"""
    warnings: list[str] = []
    lines = text.splitlines()

    # 版本行：真实 mctal 首行为 "mcnp <ver> <date> ..."（MCNP6 文件里的实际写法）、
    # "version <n>" 或 OWEN 简化件的 "<n> mctal"
    version = None
    for line in lines[:5]:
        t = line.strip()
        m = re.match(r"^mcnp\s+([\d.]+)", t, re.IGNORECASE)
        if m:
            version = float(m.group(1))
            break
        m = re.match(r"version\s+([\d.]+)", t, re.IGNORECASE)
        if m:
            version = float(m.group(1))
            break
        m = re.match(r"^([\d.]+)\s+mctal", t, re.IGNORECASE)
        if m:
            version = float(m.group(1))
            break

    # k-eff 逐周期：k  eff (c) <mean> <std>
    cycles: list[int] = []
    mean: list[float] = []
    std: list[float] = []
    keff_re = re.compile(
        r"k\s*eff\s*\([a-z]\)\s+(" + _NUM + r")\s+(" + _NUM + r")", re.IGNORECASE
    )
    idx = 0
    for line in lines:
        for m in keff_re.finditer(line):
            idx += 1
            cycles.append(idx)
            mean.append(float(m.group(1)))
            std.append(float(m.group(2)))

    # combined keff
    combined = None
    comb_re = re.compile(
        r"combined\s+keff\s*=?\s*(" + _NUM + r")\s+(" + _NUM + r")", re.IGNORECASE
    )
    for line in lines:
        m = comb_re.search(line)
        if m:
            combined = {"mean": float(m.group(1)), "std": float(m.group(2))}
            break

    # tally / ktally 块
    block_re = re.compile(r"^(?:1?tally|ktally)\s+(\d+)", re.IGNORECASE)

    # 顶层 nps：从 mctal 头部（第一个 tally/ktally 块之前）解析；
    # 头部无 nps 则不输出该键（不再硬编码死字段 None）。
    top_nps = None
    for header_line in lines:
        if block_re.match(header_line.strip()):
            break
        nps_m = re.search(r"nps\s*=\s*(\d+)", header_line, re.IGNORECASE)
        if nps_m:
            top_nps = int(nps_m.group(1))

    blocks: list[dict] = []
    cur: dict | None = None
    for line in lines:
        m = block_re.match(line.strip())
        if m:
            cur = {"id": m.group(1), "nps": None, "rows": [],
                   "energy_bins": None, "spectrum": None}
            blocks.append(cur)
            nps_m = re.search(r"nps\s*=\s*(\d+)", line, re.IGNORECASE)
            if nps_m:
                cur["nps"] = int(nps_m.group(1))
            continue
        if _KCODE_HEAD_RE.match(line.strip()):
            # 真实 mctal 把 KCODE 结果放在所有 tally 块之后：先收尾，否则
            # kcode 块的裸数值会被灌进最后一个 tally 的 rows（污染 tally 表）。
            break
        if cur is None:
            continue
        nps_m = re.search(r"nps\s*=\s*(\d+)", line, re.IGNORECASE)
        if nps_m:
            cur["nps"] = int(nps_m.group(1))
            continue
        row = _parse_num_row(line)
        if row is not None:
            cur["rows"].append(row)

    # 后处理每个块：能量网格（首行严格递增且 ≥3 列）与 OWEN 两列通量谱
    for b in blocks:
        rows = b["rows"]
        if not rows:
            continue
        first = rows[0]
        if (len(first) >= 3 and all(first[i] < first[i + 1] for i in range(len(first) - 1))):
            b["energy_bins"] = first
            b["rows"] = rows[1:]
        elif len(first) == 2 and rows and all(len(r) == 2 for r in rows):
            b["spectrum"] = [{"e": r[0], "flux": r[1]} for r in rows]
            b["rows"] = []

    # 真实 MCNP6 mctal：KCODE 结果在文末 kcode 裸数值块里（OWEN 简化件没有该块）
    kcode_keff = _parse_kcode_series(lines)

    keff = None
    if mean:
        # OWEN 式逐周期行（带 σ）优先；真实 mctal 不会有这种行
        keff = {
            "cycles": cycles,
            "mean": mean,
            "std": std,
            "combined": combined,
        }
    elif kcode_keff is not None:
        keff = kcode_keff

    if version is None and not mean and not blocks:
        warnings.append("未识别到 mctal 结构（无 version/tally/ktally 标记）")

    result = {
        "status": "ok",
        "version": version,
        "keff": keff,
        "tallies": blocks,
        "warnings": warnings,
    }
    if top_nps is not None:
        result["nps"] = top_nps
    return result


__all__ = ["parse_mctal"]
