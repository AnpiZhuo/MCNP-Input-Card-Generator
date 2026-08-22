"""参数扫描（批量改参数跑 MCNP）——纯 stdlib 可单测核心，借鉴 OWEN sweepCore.ts。

本模块只做确定性、无副作用的部分：笛卡尔组合、文本替换、k-eff 提取、
清单与汇总 TSV。执行编排（子进程、目录布局）在 api_server 端点里。

约定：
- ``SweepParameter``: ``{"name", "pattern", "values"}``——pattern 为正则，
  组 1 是被替换的值（保留组 1 前后文本），如 ``r"(NPS\\s+)(\\d+)"``。
- ``apply_parameters`` 每个参数只替换首个匹配；组合之间互不影响（作用于原文本）。
"""

from __future__ import annotations

import re

try:
    from mctal_parser import parse_mctal
except ImportError:  # 测试/直接 import app 包时在 app/ 下
    from app.mctal_parser import parse_mctal

_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_KEFF_FINAL_RE = re.compile(
    r"final\s+estimated\s+combined\s+collision\s*/\s*absorption\s*/\s*track[\s-]"
    r"length\s+keff[^=:\d]*[=:]?\s*(" + _NUM + r")",
    re.IGNORECASE,
)
_KEFF_OPENMC_RE = re.compile(r"combined\s+k-?effective\s*=\s*(" + _NUM + r")", re.IGNORECASE)
_KEFF_FALLBACK_RE = re.compile(r"\bk-?eff\s*[=:]\s*(" + _NUM + r")", re.IGNORECASE)


def parse_keff(text: str) -> float | None:
    """从模拟输出（mctal/outp/stdout）提取 k-eff；找不到返回 None。

    顺序：mctal combined keff → mctal 最后周期均值 → OWEN 式
    final estimated / OpenMC combined / 兜底 k-eff=。
    """
    try:
        r = parse_mctal(text)
        if r.get("keff"):
            comb = r["keff"].get("combined")
            if comb and comb.get("mean") is not None:
                return float(comb["mean"])
            means = r["keff"].get("mean") or []
            if means:
                return float(means[-1])
    except Exception:
        pass
    for re_ in (_KEFF_FINAL_RE, _KEFF_OPENMC_RE, _KEFF_FALLBACK_RE):
        m = re_.search(text)
        if m:
            try:
                v = float(m.group(1))
                return v
            except ValueError:
                return None
    return None


def cartesian(parameters: list[dict]) -> list[dict]:
    """参数值列表的笛卡尔积 → 每组合一个 dict。"""
    if not parameters:
        return [{}]
    head, *tail = parameters
    rest = cartesian(tail)
    out = []
    for v in head.get("values", []):
        for r in rest:
            combo = {head["name"]: v}
            combo.update(r)
            out.append(combo)
    return out


def apply_parameters(text: str, params: dict, schema: list[dict]) -> str:
    """把一组参数替换进文本：每参数首个正则匹配，组 1 换成值，保留上下文。"""
    out = text
    for p in schema:
        value = str(params.get(p["name"], ""))
        try:
            re_ = re.compile(p["pattern"])
        except re.error:
            continue
        out = re_.sub(lambda m: _substitute(m, value), out, count=1)
    return out


def _substitute(m: re.Match, value: str) -> str:
    if m.lastindex is None or m.lastindex < 1:
        return value
    group = m.group(1)
    idx = m.group(0).index(group)
    return m.group(0)[:idx] + value + m.group(0)[idx + len(group):]


def run_dir_name(index: int) -> str:
    """运行目录名：run_001 / run_010。"""
    return f"run_{index:03d}"


def build_manifest(base_file: str, language: str, parameters: list[dict],
                   records: list[dict]) -> dict:
    return {
        "baseFile": base_file,
        "language": language,
        "parameters": parameters,
        "runs": records,
    }


def build_summary_tsv(parameters: list[dict], records: list[dict]) -> str:
    """汇总 TSV：index + 各参数 + exit + keff；缺失记 n/a，无结尾换行。"""
    header = ["index"] + [p["name"] for p in parameters] + ["exit", "keff"]
    lines = ["\t".join(header)]
    for rec in records:
        row = [str(rec.get("index", ""))]
        for p in parameters:
            row.append(str(rec.get("parameters", {}).get(p["name"], "n/a")))
        row.append("n/a" if rec.get("exitCode") is None else str(rec.get("exitCode")))
        k = rec.get("keff")
        row.append("n/a" if k is None else f"{k:.6f}")
        lines.append("\t".join(row))
    return "\n".join(lines)


__all__ = [
    "parse_keff", "cartesian", "apply_parameters", "run_dir_name",
    "build_manifest", "build_summary_tsv",
]
