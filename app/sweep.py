"""参数扫描（批量改参数跑 MCNP）——纯 stdlib 可单测核心，借鉴 OWEN sweepCore.ts。

本模块只做确定性、无副作用的部分：笛卡尔组合、文本替换、k-eff 提取、
清单与汇总 TSV。执行编排（子进程、目录布局）在 api_server 端点里。

约定：
- ``SweepParameter``: ``{"name", "pattern"|("anchor"+"context"), "values"}``。
  - 正则模式：pattern 为正则，组 1 是被替换的值（保留组 1 前后文本），
    如 ``r"(NPS\\s+)(\\d+)"``。
  - 锚点模式（免正则，GUI「选中即参数」产出）：``anchor`` 是用户选中的原文
    （如 ``1000000``），``context`` 是选中处所在的整行（如 ``nps 1000000``）；
    替换时找含 context 的首行、行内替换首个 anchor。
- ``apply_parameters`` 每个参数只替换首个匹配；组合之间互不影响（作用于原文本）。
- 锚点模式下多个参数在同一份原始文本上统一定位后一起替换，支持同参数行多值。
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile

try:
    from mctal_parser import parse_mctal
except ImportError:  # 测试/直接 import app 包时在 app/ 下
    from app.mctal_parser import parse_mctal

logger = logging.getLogger(__name__)

_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
SWEEP_MAX_COMBOS = 50               # 组合数上限（对齐 api.yaml）
SWEEP_PER_RUN_TIMEOUT = 300         # 秒：单组合 MCNP 执行超时
SWEEP_TOTAL_BUDGET = 1800           # 秒：总时长预算（30 分钟，命令硬性超时纪律）
# sweep 摘要（manifest + TSV）持久化根目录；临时 run 目录清理后仍可被
# sweep-dashboard / 前端下载引用（每个 sweep 一个 <stamp> 子目录，小文件）。
SWEEP_SUMMARY_ROOT = os.path.join(tempfile.gettempdir(), "mcnp_sweep_summaries")
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
    except Exception as e:
        # 分层兜底设计：mctal 解析失败不阻断，走正则继续；但不再静默。
        logger.warning("parse_keff: parse_mctal 解析失败，回退正则兜底（%s）", e)
    for re_ in (_KEFF_FINAL_RE, _KEFF_OPENMC_RE, _KEFF_FALLBACK_RE):
        m = re_.search(text)
        if m:
            try:
                v = float(m.group(1))
                return v
            except ValueError:
                return None
    return None


def parse_keff_history(text: str) -> dict | None:
    """提取逐周期 keff 收敛序列（供仪表盘画收敛小图）。

    输入可以是 mctal 文件全文或包含 k-eff 周期行的输出文本；
    找不到周期序列返回 None。输出 {cycles, mean, std} 与 OWEN
    RunResults.keff 的收敛字段对齐（缺 combined 不阻断）。
    """
    try:
        r = parse_mctal(text)
        k = r.get("keff")
        if k and k.get("mean"):
            return {
                "cycles": k.get("cycles") or [],
                "mean": [float(v) for v in k["mean"]],
                "std": [float(v) for v in (k.get("std") or [])],
            }
    except Exception:
        pass
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
    """把一组参数替换进文本。

    两种参数模式（不混用）：
    - 锚点模式（anchor + context）：免正则，由「选中即参数」产出；在同一份原始文本上
      统一定位、原地替换（多参数同一行也能互不干扰）。
    - 正则模式（pattern）：兼容旧数据/内部调用。
    """
    # 检测锚点模式
    if any("anchor" in p for p in schema):
        return _apply_anchors(text, schema, params)
    # 正则模式（兼容）
    out = text
    for p in schema:
        value = str(params.get(p["name"], ""))
        try:
            re_ = re.compile(p["pattern"])
        except re.error:
            continue
        out = re_.sub(lambda m: _substitute(m, value), out, count=1)
    return out


def _apply_anchors(text: str, schema: list[dict], params: dict) -> str:
    """锚点多参数同时替换：所有参数基于同一份原始文本定位，从后往前原地替换。

    定位规则：找到包含 context 的首行，在该行内找到首个 anchor 出现位置；
    context 为空则全文搜首个 anchor。
    """
    edits = []  # (start, end, value)
    for p in schema:
        value = str(params.get(p["name"], ""))
        anchor = p.get("anchor", "")
        context = p.get("context", "")
        start = _anchor_pos(text, anchor, context)
        if start is None:
            continue
        edits.append((start, start + len(anchor), value))
    if not edits:
        return text
    edits.sort(key=lambda e: e[0], reverse=True)  # 从后往前防止偏移错位
    out = text
    for start, end, val in edits:
        out = out[:start] + str(val) + out[end:]
    return out


def _anchor_pos(text: str, anchor: str, context: str) -> int | None:
    """返回 anchor 在 text 中的起始位置，或 None。

    用法：若 context 非空，在包含 context 的首行内搜索 anchor；
    否则全文本搜索首个 anchor。
    """
    idx = 0
    for line in text.splitlines(keepends=True):
        if context:
            if context in line:
                rel = line.find(anchor)
                if rel >= 0:
                    return idx + rel
        else:
            rel = text.find(anchor)
            return rel if rel >= 0 else None
        idx += len(line)
    return None


def _substitute(m: re.Match, value: str) -> str:
    if m.lastindex is None or m.lastindex < 1:
        return value
    # 用 m.start(1)/m.end(1) 精确定位组 1（相对 group(0) 的偏移 = 绝对偏移 − m.start(0)），
    # 避免 group(0) 中更早出现的同文本被 .index() 命中而错位
    # （如模式 r"\d(\d+)cm" 匹配 "55cm" 时 group(1) 是第二个 5）。
    g0_start = m.start(0)
    start = m.start(1) - g0_start
    end = m.end(1) - g0_start
    return m.group(0)[:start] + value + m.group(0)[end:]


def run_dir_name(index: int) -> str:
    """运行目录名：run_001 / run_010。"""
    return f"run_{index:03d}"


def sweep_budget_status(num_combos, per_run_timeout=SWEEP_PER_RUN_TIMEOUT,
                        total_budget=SWEEP_TOTAL_BUDGET, workers=1):
    """检查 sweep-run 是否超出总时长预算（命令硬性超时纪律）。

    预算 = ceil(组合数 / 并行数) × 单次超时。组合数超上限或预计总耗时超过预算 → 返回
    ``{"code": "budget_exceeded", "message": ...}``（含当前组合数/预算说明）；
    可执行返回 ``None``。
    """
    if num_combos > SWEEP_MAX_COMBOS:
        message = f"组合数 {num_combos} 超上限 {SWEEP_MAX_COMBOS}，请缩小参数范围"
    else:
        batches = (num_combos + workers - 1) // workers  # ceil 取整
        expected = batches * per_run_timeout
        if expected <= total_budget:
            return None
        message = (
            f"组合数 {num_combos}，同时跑 {workers} 个 ≈ {batches} 批 × "
            f"单次超时 {per_run_timeout}s = 预计耗时 {expected}s"
            f"（{expected // 60} 分钟），超过总预算 "
            f"{total_budget}s（{total_budget // 60} 分钟）。"
            f"请缩小参数范围、增加并行数或缩短单次运行时间。"
        )
    return {"code": "budget_exceeded", "message": message}


def persist_sweep_summary(base_dir, manifest, summary_tsv):
    """把 sweep 摘要（manifest + TSV）拷贝到稳定摘要目录。

    摘要落在 ``SWEEP_SUMMARY_ROOT/<base_dir 名>/``（小文件）；调用方随后
    ``cleanup_sweep_dir(base_dir)`` 删除含 run_XXX 子目录与大文件的临时目录。
    返回 ``(summary_base, manifest_path, tsv_path)``。
    """
    stamp = os.path.basename(base_dir) or "sweep"
    summary_base = os.path.join(SWEEP_SUMMARY_ROOT, stamp)
    os.makedirs(summary_base, exist_ok=True)
    manifest_path = os.path.join(summary_base, "sweep-manifest.json")
    tsv_path = os.path.join(summary_base, "sweep-summary.tsv")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    with open(tsv_path, "w", encoding="utf-8") as f:
        f.write(summary_tsv)
    return summary_base, manifest_path, tsv_path


def cleanup_sweep_dir(base_dir):
    """递归删除 sweep 临时目录（含 run_XXX 子目录与 MCNP 大文件）。失败忽略。"""
    import shutil
    shutil.rmtree(base_dir, ignore_errors=True)


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
    "parse_keff", "parse_keff_history", "cartesian", "apply_parameters", "run_dir_name",
    "build_manifest", "build_summary_tsv",
    "sweep_budget_status", "persist_sweep_summary", "cleanup_sweep_dir",
]
