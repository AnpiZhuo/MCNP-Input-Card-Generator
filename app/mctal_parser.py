"""MCNP ``mctal`` 输出解析（纯 stdlib，容错；无新依赖）。

对齐 OWEN ``src/results/parsers/mcnp.ts`` 的解析目标（k-eff 历史 / tally 表），
并覆盖真实 mctal 的结构（``version`` 行、``ktally``/``tally`` 块、nps、
能量网格、逐探测器结果与相对误差）。同 ``outp_parser`` 一样采用
「能解析多少算多少 + warnings」的容错策略。

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


def parse_mctal(text: str) -> dict:
    """解析 mctal 文本 → dict（结构见模块 docstring）。"""
    warnings: list[str] = []
    lines = text.splitlines()

    # 版本行：真实 mctal 首行为 "version <n>" 或 "<n> mctal"
    version = None
    for line in lines[:5]:
        t = line.strip()
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

    keff = None
    if mean:
        keff = {
            "cycles": cycles,
            "mean": mean,
            "std": std,
            "combined": combined,
        }

    if version is None and not mean and not blocks:
        warnings.append("未识别到 mctal 结构（无 version/tally/ktally 标记）")

    return {
        "status": "ok",
        "version": version,
        "nps": None,
        "keff": keff,
        "tallies": blocks,
        "warnings": warnings,
    }


__all__ = ["parse_mctal"]
