# -*- coding: utf-8 -*-
"""从**官方 mcnp6 输出**抽取 SDEF 源抽样的裁判数字（禁手抄）。

用途（本次大重构的验收门禁数据源）
--------------------------------
官方 VALIDATION_SHIELDING 三算例（`photon_kerma` / `fns_config1_neutron_onaxis` /
`lps_water`）已用官方 `mcnp6.exe` 各跑一遍 nps=3000，输出 `.out` 里含权威数字：

* `probability distribution N for source variable X` 表头后的
  `unbiased discrete` / `unbiased histogram` / `unbiased interpolated` /
  `biased interpolated` / `power law 21 … k = …` / `distribution is dependent on dir`；
* `the mean of source distribution N is …`；
* `range of sampled source weights = lo to hi`；
* 打印表 170 `source distribution frequency tables` 的
  `n / source value / sampled / expected / sampled/expected / sampled weight / expected weight`
  （**expected 列 = 官方给的期望概率/期望权重**，本脚本只取这些列）。

产出（提交进仓库，几百字节级；400KB 的 `.out` **不入库**）
--------------------------------------------------------
1. `tests/fixtures/sdef_official/<deck>.sdef`
   —— 从官方 `.inp` **逐字**抽出的「SDEF 卡（含续行）+ 紧随其后的全部
   SI/SP/SB/DS/SC 行（含 C 注释行原样）」卡片块。不重排、不补默认值。
2. `tests/fixtures/sdef_official/<deck>.expected.json`
   —— 上面那些官方数字的结构化版本：
   `{distributions: {id: {var, kind, mean|null, wmult_range|null}},
     freq: {id: [{value, expected_prob, expected_weight}]},
     weight_range: [lo, hi]}`

用法（纯 stdlib，regex 解析；不进 pytest，属**工具**不属测试）
------------------------------------------------------------
    python tools/extract_sdef_official_expected.py \
        --inp  "D:\\MCNP\\MCNP6\\MCNP_CODE\\MCNP6\\Testing\\VALIDATION_SHIELDING\\Inputs" \
        --out  "D:\\AItool\\.tmp\\sdef_audit"

两个参数都有默认值（本机路径），无参直接跑即可。`--check` 只校验
「仓库里的 .expected.json 与 .out 一致」（重构后裁判数字若被改动，这里立刻红）。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
FIXTURE_DIR = PROJECT_DIR / "tests" / "fixtures" / "sdef_official"

#: 三个官方算例（顺序即夹具生成顺序）
DECKS = ["photon_kerma", "fns_config1_neutron_onaxis", "lps_water"]

DEFAULT_INP_DIR = Path(
    r"D:\MCNP\MCNP6\MCNP_CODE\MCNP6\Testing\VALIDATION_SHIELDING\Inputs")
DEFAULT_OUT_DIR = Path(r"D:\AItool\.tmp\sdef_audit")

#: SDEF 卡片块里允许紧随其后的卡名（其余卡即块结束）
_BLOCK_CARD = re.compile(r"^\s*(si|sp|sb|ds|sc)\s*\d", re.IGNORECASE)
_SDEF_CARD = re.compile(r"^\s*sdef\b", re.IGNORECASE)
_COMMENT_CARD = re.compile(r"^\s*c\b", re.IGNORECASE)


# ── 1. 从官方 .inp 抽 SDEF 卡片块（逐字） ────────────────────
def extract_sdef_block(inp_text: str) -> str:
    """官方 .inp 文本 → SDEF 卡片块**逐字**文本（含结尾换行）。

    规则：定位 `sdef` 卡；把它**所有续行**（下一张卡之前、以空白开头的行，
    或紧跟在续行后的行——MCNP 的续行判定是"第 6 列起非空"，这里按官方三算例
    实测的两种续行形态处理：首列空白即续行）收进来；随后继续收 SI/SP/SB/DS/SC
    行与其续行、以及夹在其中的 `c` 注释行；遇到其它卡即止。
    """
    lines = inp_text.splitlines()
    start = next(i for i, ln in enumerate(lines) if _SDEF_CARD.match(ln))

    block = [lines[start]]
    i = start + 1
    # SDEF 自身的续行
    while i < len(lines) and _is_continuation(lines[i], lines[i - 1]):
        block.append(lines[i])
        i += 1
    # 其后的 SI/SP/SB/DS/SC（+ 夹在其中的注释行）
    while i < len(lines):
        ln = lines[i]
        if _BLOCK_CARD.match(ln) or _COMMENT_CARD.match(ln):
            block.append(ln)
            i += 1
            while i < len(lines) and _is_continuation(lines[i], lines[i - 1]):
                block.append(lines[i])
                i += 1
            continue
        break
    # 去掉块尾多余的纯注释行（官方把材料段前的空 `c` 也留在了源段尾部）
    while block and _COMMENT_CARD.match(block[-1]) and not block[-1].strip()[1:].strip():
        block.pop()
    return "\n".join(block) + "\n"


def _is_continuation(line: str, prev: str) -> bool:
    """MCNP 续行判定：本行第 1 列是空白（且本行非空、上一行非注释）。"""
    if not line.strip():
        return False
    if _COMMENT_CARD.match(prev):
        return False
    return line[:1] in (" ", "\t")


# ── 2. 从官方 .out 抽裁判数字 ────────────────────────────────
# 注意：官方 .out 是 CRLF；`$` 在 Python 里会**吃掉**尾随的 `\r` 吗？
# 不会——`$` 只匹配串尾或 `\n` 之前，`\r` 会让 `…\s*$` 之外的写法失配。
# 因此这里统一 `\s*$` + MULTILINE 全文匹配（逐行匹配时行尾已无 `\r`，
# 但全文 finditer 必须开 MULTILINE，否则整篇只算一个"行"）。
_DIST_HEAD = re.compile(
    r"^\s*probability distribution\s+(\d+)\s+for source variable\s+(\w+)\s*$",
    re.IGNORECASE | re.MULTILINE)
_MEAN_LINE = re.compile(
    r"^\s*the mean of source distribution\s+(\d+)\s+is\s+([-+0-9.EeDd]+)\s*$",
    re.IGNORECASE | re.MULTILINE)
_WEIGHT_RANGE = re.compile(
    r"range of sampled source weights\s*=\s*([-+0-9.EeDd]+)\s+to\s+([-+0-9.EeDd]+)",
    re.IGNORECASE)
_FREQ_HEAD = re.compile(
    r"^\s*source distribution\s+(\d+)\s+for\s+(\w+)\s*$", re.IGNORECASE | re.MULTILINE)
_POWER_LAW = re.compile(r"power law\s+(\d+):.*?k\s*=\s*([-+0-9.EeDd]+)", re.IGNORECASE)
_NUM = re.compile(r"^[-+]?(?:\d+\.?\d*|\.\d+)(?:[EeDd][-+]?\d+)?$")


def _f(tok: str) -> float:
    """MCNP 输出里的浮点（含 Fortran 的 D 指数）。"""
    return float(tok.replace("D", "E").replace("d", "e"))


def _is_num(tok: str) -> bool:
    return bool(_NUM.match(tok))


def parse_distributions(out_text: str) -> dict:
    """`.out` → `{id: {var, kind, mean|null, wmult_range|null, si:[...]}}`。

    * `kind`：`unbiased discrete distribution` / `power law 21 … k = …` /
      `distribution is dependent on dir` 这一类**标题行原文**（去首尾空格）；
    * `mean`：官方 `the mean of source distribution N is …`；官方没打就是 ``None``；
    * `wmult_range`：biased 表里 `weight multiplier` 列的最小/最大值
      （`unbiased` 分布官方不给该列 ⇒ ``None``）；
    * `si`：该分布表里 `source value` 列（连续型是分箱边界，离散型是取值）。
    """
    lines = out_text.splitlines()
    dists: dict[int, dict] = {}
    # 先标出所有区块头位置（含表 170 的 `source distribution … for …`）：每块的
    # 扫描范围 = [本块头, 下一个块头)，避免"跳空行跳到下一块里"这类越界。
    heads = [k for k, ln in enumerate(lines)
             if _DIST_HEAD.match(ln) or _FREQ_HEAD.match(ln)]
    i = 0
    for hidx, hpos in enumerate(heads):
        if not _DIST_HEAD.match(lines[hpos]):
            continue
        m = _DIST_HEAD.match(lines[hpos])
        did, var = int(m.group(1)), m.group(2)
        block_end = heads[hidx + 1] if hidx + 1 < len(heads) else len(lines)
        kind = lines[hpos + 1].strip() if hpos + 1 < len(lines) else ""
        # 内置函数标题折成一行（`power law 21: f(x)=… k = 1.0` → `power law 21 k=1.0`），
        # 原始行仍留在 170 表里可追溯。
        pm = _POWER_LAW.match(kind)
        if pm:
            kind = f"power law {pm.group(1)} k={pm.group(2)}"
        dists[did] = {"var": var, "kind": kind, "mean": None,
                      "wmult_range": None, "si": []}
        i = hpos + 2
        # 跳过区块头的空行
        while i < block_end and not lines[i].strip():
            i += 1
        # 表头最多两行（`source source cumulative …` / `entry value …`）；
        # **无表体的分布**（内置函数 `power law 21` / `distribution is dependent on X`）
        # 第一行就不是表头 ⇒ 一格都不收，直接进下一块。
        header_lines = 0
        while (i < block_end and header_lines < 2 and not _is_num_row(lines[i])
               and lines[i].strip()):
            header_lines += 1
            i += 1
        entry = dists[did]
        has_wmult = False
        while i < block_end:
            ln = lines[i]
            if not ln.strip():
                i += 1
                continue
            if not _is_num_row(ln):
                break
            toks = ln.split()
            if not entry["si"]:
                # 列数最难缠：表头是固定列宽、split() 后丢位置信息。改用**首行数据**
                # 的 token 数判列：6 列 = n / value / cumulative probability /
                # biased cumulative / (biased) probability density /
                # weight multiplier ⇒ 末列即 weight multiplier；`unbiased` 系列
                # 只有 4 列（无该列）。
                has_wmult = len(toks) >= 6
            entry["si"].append(_f(toks[1]))
            if has_wmult:
                w = _f(toks[-1])
                lo, hi = entry["wmult_range"] or (w, w)
                entry["wmult_range"] = (min(lo, w), max(hi, w))
            i += 1

    # 均值行（可能出现在表后任意位置）
    for m in _MEAN_LINE.finditer(out_text):
        did = int(m.group(1))
        if did in dists:
            dists[did]["mean"] = _f(m.group(2))
    return dists


def _is_num_row(line: str) -> bool:
    """数据行判定：首 token 是整数序号、**第 2、3 token 都是数字**。

    ⚠️ 第 3 个 token 必须也是数字这条不能省：`probability distribution 1 for
    source variable dir` 的头两个 token 恰好是（数字序号候选）"1" 与 "for"
    —— 不查第 3 个 token 就会把**区块头**当数据行，整个区块被跳过（fns 的
    D1/dir 就是这么丢的）。查了之后顺带把"曲面清单"行（`1  1  pz  …`）也排除了。
    """
    toks = line.split()
    return len(toks) >= 3 and toks[0].isdigit() and _is_num(toks[1]) and _is_num(toks[2])


def parse_frequency_table(out_text: str) -> dict:
    """打印表 170 → `{id: [{value, expected_prob, expected_weight}, …]}`。

    只取 `expected`（期望概率）与 `expected weight`（期望权重）两列；
    官方对"依赖链太复杂"的分布会写 `prsdft does not yet do expected values …`
    并**不打这张表** ⇒ 该分布号在此字典里缺席（缺席 ≠ 0，见契约 §5）。
    """
    lines = out_text.splitlines()
    freq: dict[int, list[dict]] = {}
    i = next((k for k, ln in enumerate(lines)
              if "source distribution frequency tables" in ln), None)
    if i is None:
        return freq
    while i < len(lines):
        m = _FREQ_HEAD.match(lines[i])
        if not m:
            i += 1
            continue
        did = int(m.group(1))
        i += 1
        rows: list[dict] = []
        while i < len(lines):
            ln = lines[i]
            # 下一个分布块开始 / 表结束（官方表结束于非数字、非表头的正文）
            if _FREQ_HEAD.match(ln):
                break
            if ln.strip().startswith("total"):
                i += 1
                break
            if _is_num_row(ln):
                toks = ln.split()
                # n value sampled expected ratio sampled_w expected_w ratio → ≥8 token
                if len(toks) >= 8:
                    try:
                        rows.append({
                            "value": _f(toks[1]),
                            "expected_prob": _f(toks[3]),
                            "expected_weight": _f(toks[6]),
                        })
                    except ValueError:
                        pass
            i += 1
        if rows:
            freq[did] = rows
    return freq


def parse_weight_range(out_text: str) -> list[float] | None:
    """`range of sampled source weights = lo to hi` → `[lo, hi]`（官方没打则 None）。"""
    m = _WEIGHT_RANGE.search(out_text)
    return [_f(m.group(1)), _f(m.group(2))] if m else None


# ── 3. 组装 .expected.json ───────────────────────────────────
_BLOCK_CARD_LINE = re.compile(r"^(SI|SP|SB|DS|SC)(\d+)\b(.*)$", re.IGNORECASE)
_OPTION_LETTERS = {"H", "L", "A", "S", "D", "C", "V", "T", "Q"}


def parse_sdef_binding(block: str) -> dict:
    """SDEF 卡块 → `{"vars": {变量名: 分布号}, "cards": {分布号: [卡名]}}`。

    * `vars`：变量名 → 分布号。包含三类来源：SDEF 卡上的 `var=Dn` / `var=Fvar' Dn`、
      `DSn Q` 图右侧的子分布号（继承父变量名）、`DD` 卡引用的分布号（变量 DAT）；
    * `cards`：某分布号有哪些卡（`SI2`/`SP2`/`SB2`…）。

    用途：官方 `.out` 的打印选项可能**不含源分布表**（`lps_water` 就是
    `print -10 -30 -110`，整张表被关掉）。那种情况下 `distributions` 里的
    `var` 只能从**卡片块本身**推（`kind` 标 `from deck`，均值一律 `null`），
    否则「分布号齐全」这条闸门会因为裁判数据缺失而没法判。
    """
    merged: list[str] = []
    for raw in block.splitlines():
        s = raw.strip()
        if not s or s[:1].lower() == "c":
            continue
        if raw[:1] in (" ", "\t") and merged:
            merged[-1] += " " + s
        else:
            merged.append(s)

    cards: dict[int, list[str]] = {}
    for card in merged:
        m = _BLOCK_CARD_LINE.match(card)
        if m:
            cards.setdefault(int(m.group(2)), []).append(m.group(1).upper())

    # 变量 → 分布号：SDEF 卡 token 形如 `erg=d2` / `erg=fdir=d2` / `dir=d1`
    # 等号连写里 `fvar` = 值取自父变量 var 的**变量名**（C810 p.3-55），
    # 所以 `erg=fdir=d2` 里 erg 的值是 **D2**（父变量 DIR 的分布号另有 `dir=d1`）：
    # 只看**形如 `dN` 的那一段**，别把 `fdir` 当分布引用。
    vars_map: dict[str, int] = {}
    for card in merged:
        if not card.lower().startswith("sdef"):
            continue
        toks = card.split()[1:]
        for k, tok in enumerate(toks):
            if "=" not in tok:
                continue
            var = tok.split("=")[0].lower()
            # `dir=` 后面接一个独立 token（`dir= d3`）时把值取回来
            refs = [p for p in tok.split("=")[1:] if p]
            if not refs and k + 1 < len(toks):
                refs = [toks[k + 1]]
            dids = [int(r[1:]) for r in refs if r[:1].lower() == "d" and r[1:].isdigit()]
            if dids:
                vars_map[var] = dids[-1]
        break

    # `DSn Q 父值1 子分布号1 …`：Q 图右侧的每个子分布号**继承**父变量的变量名
    # （官方 fns 算例的 DS2 把 dir 的 39 个区间映到 180/175/…/5，全是 erg）。
    # 注意这份映射的方向是 **分布号 → 变量名**（与 vars_map 相反），单独存。
    child_var: dict[int, str] = {}
    for card in merged:
        m = _BLOCK_CARD_LINE.match(card)
        if not m or m.group(1).upper() != "DS":
            continue
        parent_did = int(m.group(2))
        parent_var = next((v for v, d in vars_map.items() if d == parent_did), "")
        toks = m.group(3).split()
        if toks and toks[0].upper() in _OPTION_LETTERS:
            toks = toks[1:]
        for j in range(1, len(toks), 2):
            if toks[j].lstrip("-").isdigit():
                child = int(toks[j])
                if 0 < child and parent_var:
                    child_var.setdefault(child, parent_var)
    # Table 3.3：`DD`（延迟裂变）引用的分布号属于变量 DAT
    for card in merged:
        if card.lower().startswith("dd"):
            for tok in card.split()[1:]:
                if tok.lstrip("-").isdigit() and 0 < int(tok):
                    child_var.setdefault(int(tok), "dat")
    return {"vars": vars_map, "childVars": child_var, "cards": cards}


def build_expected(out_text: str, block: str = "") -> dict:
    dists = parse_distributions(out_text)
    freq = parse_frequency_table(out_text)
    binding = parse_sdef_binding(block) if block else {"vars": {}, "childVars": {}, "cards": {}}
    # {分布号: 变量名}：SDEF 卡的绑定 + DS Q 图继承下来的子分布变量名
    var_of = {did: var for var, did in binding["vars"].items()}
    var_of.update(binding["childVars"])
    # 官方输出里没有分布表的分布号（lps_water：print 卡关掉了该表）：
    # 只填「卡片块能证明的」var，kind 标 `from deck`，均值留 null ——
    # 靠 `_notes` 说明来源，绝不臆造数字。
    for did in sorted(set(int(k) for k in freq) | set(binding["cards"])):
        if did not in dists:
            dists[did] = {"var": var_of.get(did, ""), "kind": "from deck",
                          "mean": None, "wmult_range": None, "si": []}
    for did, var in var_of.items():
        if did in dists and var and not dists[did]["var"]:
            dists[did]["var"] = var
    return {
        "_source": "官方 mcnp6.exe 输出（tools/extract_sdef_official_expected.py 生成，禁手改）",
        "_notes": [
            "kind/mean/wmult_range 逐字来自 .out 的 'probability distribution N for "
            "source variable X' 表与 'the mean of source distribution N is …' 行；",
            "kind == 'from deck' 表示官方 .out 的 print 选择**没有**打印该分布表"
            "（lps_water 的 `print -10 -30 -110`），var 由 .sdef 卡片块推出，数字一律缺省；",
            "freq 逐字来自打印表 170 的 expected / expected weight 两列；"
            "官方对该分布不打表时该 id 缺席（缺席 ≠ 0）。",
        ],
        "distributions": {
            str(did): {
                "var": d["var"],
                "kind": d["kind"],
                "mean": d["mean"],
                "wmult_range": list(d["wmult_range"]) if d["wmult_range"] else None,
            }
            for did, d in sorted(dists.items())
        },
        "freq": {str(did): rows for did, rows in sorted(freq.items())},
        "weight_range": parse_weight_range(out_text),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inp", type=Path, default=DEFAULT_INP_DIR,
                    help="官方 VALIDATION_SHIELDING/Inputs 目录")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR,
                    help="官方 mcnp6.exe 输出目录（*.out 与 *.inp 同名）")
    ap.add_argument("--fixtures", type=Path, default=FIXTURE_DIR, help="夹具输出目录")
    ap.add_argument("--check", action="store_true",
                    help="只校验仓库内 .expected.json 与 .out 一致（不写文件）")
    args = ap.parse_args()

    args.fixtures.mkdir(parents=True, exist_ok=True)
    bad = []
    for deck in DECKS:
        inp_path = args.inp / f"{deck}.inp"
        out_path = args.out / f"{deck}.out"
        if not inp_path.is_file() or not out_path.is_file():
            print(f"[跳过] {deck}：缺输入或输出（{inp_path} / {out_path}）")
            bad.append(deck)
            continue
        block = extract_sdef_block(inp_path.read_text(encoding="utf-8", errors="replace"))
        expected = build_expected(
            out_path.read_text(encoding="utf-8", errors="replace"), block)
        sdef_path = args.fixtures / f"{deck}.sdef"
        json_path = args.fixtures / f"{deck}.expected.json"
        if args.check:
            old = json_path.read_text(encoding="utf-8") if json_path.is_file() else ""
            same_json = old.strip() == json.dumps(
                expected, indent=2, ensure_ascii=False).strip()
            same_sdef = (sdef_path.is_file()
                         and sdef_path.read_text(encoding="utf-8") == block)
            flag = "一致" if (same_json and same_sdef) else "**不一致**"
            print(f"[check] {deck}: .sdef {flag} / .expected.json {flag}")
            if not (same_json and same_sdef):
                bad.append(deck)
            continue
        sdef_path.write_text(block, encoding="utf-8", newline="")
        json_path.write_text(json.dumps(expected, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8", newline="")
        print(f"[生成] {sdef_path.name}: {len(block.splitlines())} 行卡片块；"
              f"{json_path.name}: 分布 {len(expected['distributions'])} 个 / "
              f"频率表 {len(expected['freq'])} 个 / 权重范围 {expected['weight_range']}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
