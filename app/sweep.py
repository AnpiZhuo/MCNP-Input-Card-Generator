"""参数扫描（批量改参数跑 MCNP）——纯 stdlib 可单测核心，借鉴 OWEN sweepCore.ts。

本模块只做确定性、无副作用的部分：笛卡尔组合、文本替换、k-eff 提取、
清单与汇总 TSV。执行编排（子进程、目录布局）在 api_server 端点里。

约定：
- ``SweepParameter``: ``{"name", "key"?, "pattern"|("anchor"+"context"[+"start"+"end"]), "values"}``。
  - ``name`` = **给人看的标签**（GUI 里就是用户框选到的原文，可以重复）。
  - ``key`` = 取值的**内部键**（可重复名时用来区分；缺省回落 ``name``，兼容 MCP/旧数据）。
    用户 2026-10-11：名称只显示框选内容本身，**不要**在界面上挂 `#1`/`#2` 这种后缀。
  - 正则模式：pattern 为正则，组 1 是被替换的值（保留组 1 前后文本），
    如 ``r"(NPS\\s+)(\\d+)"``。
  - 锚点模式（GUI「选中即参数」产出）：``anchor`` 是用户选中的原文、
    ``context`` 是选中处所在的整行、``start``/``end`` 是选区在 deck 文本里的
    **字符偏移**（前端算好一起发来）。
    **给了 start/end 就只认这个区间**：删掉那段、原样插入新值，长度不限
    （用户 2026-10-11 口径：「我划了这些文字，你就把这些文字删掉，用我另外给出的
    文字替换」—— 像 Word 里删掉再键入，不是"整段删掉"，也不要求等长）。
    区间内容对不上（用户重新生成过输入卡）⇒ **不改任何字符**并报错（非静默），
    绝不回落到"从头找第一个像的"。
  - 没给 start/end 时（MCP / 旧数据 / 手工构造）回落到旧口径：找含 context 的首行、
    行内替换首个 anchor —— 这条是**猜**，同一个字出现两次就会改错地方，仅作兼容。
- ``apply_parameters`` 每个参数只替换一处；组合之间互不影响（作用于原文本）。
- 锚点模式下多个参数在同一份原始文本上统一定位后一起替换，支持同参数行多值；
  替换长度自由（从后往前应用，前一处变长/变短不会让后一处错位）。
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time

try:                                   # 源码树 / 打包后 app/ 在 sys.path 上
    from mctal_parser import parse_mctal
except ImportError:                    # 包内导入（import app.sweep）
    from app.mctal_parser import parse_mctal
try:
    from outp_parser import parse_keff_cycles
except ImportError:
    from app.outp_parser import parse_keff_cycles

logger = logging.getLogger(__name__)

_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
SWEEP_MAX_COMBOS = 50               # 组合数上限（对齐 api.yaml）
SWEEP_PER_RUN_TIMEOUT = 300         # 秒：单组合 MCNP 执行超时
SWEEP_TOTAL_BUDGET = 1800           # 秒：总时长预算（30 分钟，命令硬性超时纪律）
# sweep 摘要（manifest + TSV）持久化根目录；临时 run 目录清理后仍可被
# sweep-dashboard / 前端下载引用（每个 sweep 一个 <stamp> 子目录，小文件）。
SWEEP_SUMMARY_ROOT = os.path.join(tempfile.gettempdir(), "mcnp_sweep_summaries")

# ── 结果保留（2026-10-15 用户要求：「让 11 个输出文件都保留」）──────────────
# 每个组合的 MCNP 产物**留在硬盘上**，目录：
#   <用户输出目录 或 SWEEP_RESULTS_DEFAULT_ROOT>/sweep_<时间戳>/run_XXX/
# 实测单组合产物（用户算例 304-CH2，1e5 中子，单核 14.8s）：
#   sweep-001.o    49 KB   ← **结果全在这里**（F6 计数 / keff / 收敛表）
#   sweep-001.r  37.9 MB   ← MCNP 二进制重启文件（runtpe），看图看数都用不上
#   sweep.i       2.3 KB   ← 该组合实际用的输入卡（可复算）
# ⇒ 默认丢弃 ``*.r``（50 组合全留会写掉 ~1.9GB 且越扫越多）；
#   要一并保留（例如打算用 MCNP 的 continue 续算）把 SWEEP_KEEP_RESTART 置 True。
SWEEP_RESULTS_DEFAULT_ROOT = "D:/MCNP/new"   # 与 /api/run-mcnp 的默认输出目录同源
SWEEP_KEEP_RESTART = False                   # 是否保留 37.9MB/组合 的二进制重启文件
SWEEP_RESTART_SUFFIXES = (".r",)             # ``name=sweep-001.`` 前缀下即 sweep-001.r
SWEEP_RESTART_NAMES = ("runtpe",)            # 没给 name= 时 MCNP 的默认名（照样是那个大文件）
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

    输入可以是 mctal（OWEN 式 ``k eff (c)`` 行，或**真实 MCNP6 ``kcode`` 块**）
    或 outp（``.o``，print table 175 周期表）全文；找不到周期序列返回 None。
    输出 ``{cycles, mean, std, combined}`` —— ``combined`` 是最终组合 keff 与其 σ
    （可能为 None）。真实 MCNP 的 mctal/outp **都不逐周期写 σ** ⇒ 此时 ``std``
    为空列表，最终值看 ``combined``。
    """
    try:
        r = parse_mctal(text)
        k = r.get("keff")
        if k and k.get("mean"):
            return {
                "cycles": k.get("cycles") or [],
                "mean": [float(v) for v in k["mean"]],
                "std": [float(v) for v in (k.get("std") or [])],
                "combined": k.get("combined"),
            }
    except Exception:
        pass
    try:
        h = parse_keff_cycles(text)          # outp(.o) 兜底
        if h and h.get("mean"):
            return h
    except Exception:
        pass
    return None


def history_keff_std(hist: dict | None) -> float | None:
    """从 ``parse_keff_history`` 结果里取"最终值的 σ"。

    逐周期 σ（``std``）只在 OWEN 式 mctal 里有；真实 MCNP 的 mctal/outp 只有
    最终组合值的 σ（``combined.std``）⇒ 逐周期为空时回落到它。
    """
    if not hist:
        return None
    std = hist.get("std") or []
    if std:
        return float(std[-1])
    combined = hist.get("combined") or {}
    return None if combined.get("std") is None else float(combined["std"])


def scan_run_dir(run_dir: str) -> dict:
    """扫描一次运行目录里的 MCNP 结果文件 → ``{"path","text","keff","history"}``。

    MCNP 把 keff / 收敛序列写在结果文件里（``mctal``，或 ``name=`` 前缀下的
    outp ``*.o``），**stdout 只有少量提示行** ⇒ 取 keff 必须读文件（早先只解析
    ``proc.stdout`` 时，扫描汇总表的 keff 恒为 ``n/a``）。

    按 mctal → outp 的顺序取第一个"能解出 keff 或收敛序列"的文件；都解不出
    （超时/崩溃/未跑）时返回全空结构。
    """
    import glob
    empty = {"path": None, "text": "", "keff": None, "history": None}
    if not run_dir or not os.path.isdir(run_dir):
        return empty
    seen: set[str] = set()
    first_text = ""
    for pattern in ("mctal*", "*mctal*", "outp*", "*.o"):
        for path in sorted(glob.glob(os.path.join(run_dir, pattern))):
            if path in seen or not os.path.isfile(path):
                continue
            seen.add(path)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            if not text.strip():
                continue
            if not first_text:
                first_text = text
            keff = parse_keff(text)
            hist = parse_keff_history(text)
            if keff is not None or hist:
                return {"path": path, "text": text, "keff": keff, "history": hist}
    return {**empty, "text": first_text}


def cartesian(parameters: list[dict]) -> list[dict]:
    """参数值列表的笛卡尔积 → 每组合一个 dict（键 = 参数的 ``key``，缺省用 ``name``）。"""
    if not parameters:
        return [{}]
    head, *tail = parameters
    rest = cartesian(tail)
    out = []
    for v in head.get("values", []):
        for r in rest:
            combo = {_param_key(head): v}
            combo.update(r)
            out.append(combo)
    return out


def _param_key(p: dict) -> str:
    """参数的**取值键**：``key`` 优先，缺省回落 ``name``（兼容 MCP / 旧数据）。

    为什么名与键要分开：``name`` 是给人看的标签（GUI 里 = 用户框选到的原文，允许重复），
    而 ``combos`` / ``records[].parameters`` 需要唯一键。用户 2026-10-11 明确不要界面上
    出现 `#1`/`#2` 之类的重名后缀 —— 所以唯一性放在这个看不见的键上。
    """
    return str(p.get("key") or p.get("name") or "")


def apply_parameters(text: str, params: dict, schema: list[dict],
                     errors: list | None = None) -> str:
    """把一组参数替换进文本。

    两种参数模式（不混用）：
    - 锚点模式（anchor + context [+ start/end]）：由「选中即参数」产出；在同一份原始文本上
      统一定位、原地替换（多参数同一行也能互不干扰）。给了 start/end 就**只认那个字符区间**。
    - 正则模式（pattern）：兼容旧数据/内部调用。

    ``errors`` 非 None 时，把定位失败的原因追加进去（**非静默**：位置失效绝不改到别处）。
    """
    # 检测锚点模式
    if any("anchor" in p for p in schema):
        return _apply_anchors(text, schema, params, errors)
    # 正则模式（兼容）
    out = text
    for p in schema:
        value = str(params.get(_param_key(p), ""))
        try:
            re_ = re.compile(p["pattern"])
        except re.error:
            continue
        out = re_.sub(lambda m: _substitute(m, value), out, count=1)
    return out


def _apply_anchors(text: str, schema: list[dict], params: dict,
                   errors: list | None = None) -> str:
    """锚点多参数同时替换：所有参数基于同一份原始文本定位，从后往前原地替换。

    定位规则见 ``_resolve_span``：有 start/end 只认那个区间；没有才回落到"首个匹配"。
    替换长度不限（前一处变长/变短都不会让后一处错位 —— 从后往前应用）。
    """
    edits = []  # (start, end, value)
    for p in schema:
        name = p.get("name") or p.get("anchor") or "参数"
        value = str(params.get(_param_key(p), ""))
        anchor = p.get("anchor", "")
        context = p.get("context", "")
        span = _resolve_span(text, anchor, context, p.get("start"), p.get("end"))
        if span is None:
            if errors is not None:
                if p.get("start") is not None or p.get("end") is not None:
                    errors.append(
                        f"参数「{name}」的位置已失效：输入卡内容变了（框选的是「{anchor}」，"
                        "该位置现在不是这段文字）—— 请重新生成后重新框选")
                else:
                    errors.append(f"参数「{name}」在输入卡里找不到「{anchor}」")
            continue
        edits.append((span[0], span[1], value))
    if not edits:
        return text
    edits.sort(key=lambda e: e[0], reverse=True)  # 从后往前防止偏移错位
    out = text
    for start, end, val in edits:
        out = out[:start] + str(val) + out[end:]
    return out


def _resolve_span(text: str, anchor: str, context: str,
                  start=None, end=None) -> tuple[int, int] | None:
    """要删掉的字符区间 ``(start, end)``；定位不了返回 None。

    ① 给了 start/end（前端框选的精确位置）⇒ **只认它**：
       · 该区间内容 == anchor → 用它；
       · 区间两端多带了空白（前端只把去空白后的内容当 anchor）→ 收窄到真正内容；
       · 对不上（输入卡变了）→ None，调用方报错，**绝不改到别处**。
    ② 没给 ⇒ 回落到旧口径：含 context 的首行内首个 anchor（兼容 MCP/旧数据）。
    """
    if start is not None or end is not None:
        if (not isinstance(start, int) or not isinstance(end, int)
                or isinstance(start, bool) or isinstance(end, bool)):
            return None
        if not 0 <= start <= end <= len(text):
            return None
        seg = text[start:end]
        if seg == anchor:
            return (start, end)
        stripped = seg.strip()
        if stripped and stripped == anchor.strip():
            lead = len(seg) - len(seg.lstrip())
            return (start + lead, start + lead + len(stripped))
        return None
    pos = _anchor_pos(text, anchor, context)
    return None if pos is None else (pos, pos + len(anchor))


def _anchor_pos(text: str, anchor: str, context: str) -> int | None:
    """旧口径（无字符偏移时的兼容路径）：返回 anchor 在 text 中的起始位置，或 None。

    若 context 非空，在包含 context 的首行内搜索**首个** anchor；否则全文本搜首个 anchor。
    ⚠️ 这是"猜"：同一个字在同一行/同一文件出现两次就会改错地方 —— 只在下游拿不到
    选区偏移时使用（见 ``_resolve_span``）。
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


def _stamp(now=None) -> str:
    """结果目录用的时间戳 ``YYYYmmdd_HHMMSS``（本地时间）。"""
    t = time.localtime() if now is None else time.localtime(now)
    return time.strftime("%Y%m%d_%H%M%S", t)


def prepare_results_dir(output_dir: str = "", stamp: str = "") -> tuple[str, bool]:
    """为一次扫描准备**保留型**结果目录，返回 ``(目录, 是否保留型)``。

    保留型 = ``<output_dir 或 SWEEP_RESULTS_DEFAULT_ROOT>/sweep_<时间戳>/``：跑完
    **不清理**，各组合的 ``run_XXX/sweep-00N.o`` 留在盘上给用户看（用户 2026-10-15
    要求）。同一秒内的第二次扫描自动加 ``_2``/``_3`` 后缀，绝不覆盖前一次的结果。

    用户目录建不出来（盘不存在 / 无权限）→ 退回 ``tempfile.mkdtemp``，此时
    ``persistent=False``，调用方应照旧在跑完后 ``cleanup_sweep_dir`` 清理
    （宁可结果落临时目录，也不能因为写不了 D:/MCNP/new 就整个扫描失败）。
    """
    root = (output_dir or "").strip() or SWEEP_RESULTS_DEFAULT_ROOT
    root = os.path.normpath(root)        # D:/MCNP/new → D:\MCNP\new（界面上别出现混用分隔符）
    name = f"sweep_{stamp or _stamp()}"
    try:
        os.makedirs(root, exist_ok=True)
    except OSError:
        return tempfile.mkdtemp(prefix="mcnp_sweep_"), False
    # 逐个试后缀（而不是先 exists 再 makedirs）：同一秒内连点两次、或两个前端实例
    # 同时开扫都不会互相覆盖 —— 撞名走 FileExistsError 再换一个，不误判成"写不进去"。
    for n in range(1, 50):
        path = os.path.join(root, name if n == 1 else f"{name}_{n}")
        try:
            os.makedirs(path)
            return path, True
        except FileExistsError:
            continue
        except OSError:
            break
    return tempfile.mkdtemp(prefix="mcnp_sweep_"), False


def list_run_files(run_dir: str) -> list[dict]:
    """列出组合目录里的产物 ``[{"name", "size"}]``（体积降序）；目录不存在 → ``[]``。"""
    try:
        names = sorted(os.listdir(run_dir))
    except OSError:
        return []
    out = []
    for name in names:
        p = os.path.join(run_dir, name)
        if os.path.isfile(p):
            try:
                out.append({"name": name, "size": os.path.getsize(p)})
            except OSError:
                continue
    out.sort(key=lambda f: (-f["size"], f["name"]))
    return out


def _is_restart_file(name: str) -> bool:
    """是不是 MCNP 的二进制重启文件（``sweep-00N.r`` / 没给 ``name=`` 时的 ``runtpe``）。"""
    low = name.lower()
    return low.endswith(SWEEP_RESTART_SUFFIXES) or low in SWEEP_RESTART_NAMES


def finalize_run_dir(run_dir: str, keep_restart: bool = SWEEP_KEEP_RESTART) -> dict:
    """组合跑完后规整它的目录：默认丢弃 MCNP 二进制重启文件，其余原样保留。

    ``keep_restart=False``（默认）删掉 ``sweep-00N.r``（没给 ``name=`` 时叫 ``runtpe``）
    —— 实测 37.9MB/组合，而结果全在 49KB 的 ``sweep-00N.o`` 里；``True`` 则一个都不删。

    返回 ``{"kept": [{"name","size"}], "removed": [名字], "keptBytes": N,
    "droppedBytes": N}``（前端/清单据此如实报告"留了什么、丢了什么"，不静默）。
    """
    removed: list[str] = []
    dropped = 0
    if not keep_restart:
        for f in list_run_files(run_dir):
            if _is_restart_file(f["name"]):
                try:
                    os.remove(os.path.join(run_dir, f["name"]))
                except OSError:
                    continue
                removed.append(f["name"])
                dropped += f["size"]
    kept = list_run_files(run_dir)
    return {"kept": kept, "removed": removed,
            "keptBytes": sum(f["size"] for f in kept), "droppedBytes": dropped}


def write_summary_files(dirpath: str, manifest, summary_tsv) -> tuple[str, str]:
    """把 manifest + 汇总 TSV 写进指定目录（结果目录借它自描述：run_XXX ↔ 参数取值）。

    返回 ``(manifest_path, tsv_path)``。
    """
    os.makedirs(dirpath, exist_ok=True)
    manifest_path = os.path.join(dirpath, "sweep-manifest.json")
    tsv_path = os.path.join(dirpath, "sweep-summary.tsv")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    with open(tsv_path, "w", encoding="utf-8") as f:
        f.write(summary_tsv)
    return manifest_path, tsv_path


def persist_sweep_summary(base_dir, manifest, summary_tsv):
    """把 sweep 摘要（manifest + TSV）拷贝到稳定摘要目录。

    摘要落在 ``SWEEP_SUMMARY_ROOT/<base_dir 名>/``（小文件）；结果目录被清理时
    （退回临时目录的分支）摘要也还在。返回 ``(summary_base, manifest_path, tsv_path)``。
    """
    stamp = os.path.basename(base_dir) or "sweep"
    summary_base = os.path.join(SWEEP_SUMMARY_ROOT, stamp)
    manifest_path, tsv_path = write_summary_files(summary_base, manifest, summary_tsv)
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
    """汇总 TSV：index + 各参数 + exit + keff；缺失记 n/a，无结尾换行。

    TD-26（t5）：`exitCode == "timeout"`（api_server 在 `subprocess.TimeoutExpired` 时置，
    另有 `timedOut: True` 标记）原样输出 ``timeout`` 而不是 ``n/a``——否则"超时"与
    "MCNP 没产生输出"在落盘摘要里不可区分。
    """
    header = ["index"] + [p["name"] for p in parameters] + ["exit", "keff"]
    lines = ["\t".join(header)]
    for rec in records:
        row = [str(rec.get("index", ""))]
        for p in parameters:
            row.append(str(rec.get("parameters", {}).get(_param_key(p), "n/a")))
        if rec.get("timedOut") or rec.get("exitCode") == "timeout":
            row.append("timeout")
        else:
            row.append("n/a" if rec.get("exitCode") is None else str(rec.get("exitCode")))
        k = rec.get("keff")
        row.append("n/a" if k is None else f"{k:.6f}")
        lines.append("\t".join(row))
    return "\n".join(lines)


__all__ = [
    "parse_keff", "parse_keff_history", "history_keff_std", "scan_run_dir",
    "cartesian", "apply_parameters", "run_dir_name",
    "build_manifest", "build_summary_tsv",
    "sweep_budget_status", "persist_sweep_summary", "cleanup_sweep_dir",
    "prepare_results_dir", "finalize_run_dir", "list_run_files",
    "write_summary_files",
]
