/**
 * mcnpSelect — 顶栏「MCNP 下拉」的纯逻辑（可单测，不碰 DOM / 不碰 fetch）
 *
 * 为什么要单独抽出来：装 MCNP5 又装 MCNP6 的用户要能**选**跑哪个，而"选哪个"这件事
 * 有三处容易错、且都不该靠肉眼在界面上验：
 *   1. 后端 `/api/mcnp-detect` 的响应可能来自**旧后端**（没有 candidates 字段）——
 *      降级成"单候选"而不是把下拉渲染成空的；
 *   2. 同名 exe 装了两份（D:\MCNP5 与 D:\MCNP6 都叫 mcnp6.exe）时，选项文案必须能区分，
 *      否则用户看到两个一模一样的 "MCNP6" 无从选；
 *   3. 选中后本地要把 `exe`/`label`/`found` **一起**改 —— 只改 exe 会让下拉显示与
 *      状态标签互相打架（"下拉是 MCNP5，旁边还写着 MCNP6"）。
 */
import type { McnpCandidate } from "./api";

export interface McnpState {
  found: boolean;
  exe: string;
  label: string;
  candidates: McnpCandidate[];
  /** 上一次选择后端回的话（xsdir 是否跟着切了），做 tooltip 用 */
  note?: string;
}

export const EMPTY_MCNP_STATE: McnpState = {
  found: false, exe: "", label: "MCNP?", candidates: [],
};

/** `/api/mcnp-detect` 响应 → 下拉所需状态（缺 candidates/selected 时按单候选降级）。 */
export function normalizeMcnpDetect(j: any): McnpState {
  const raw = Array.isArray(j?.candidates) ? j.candidates : [];
  const candidates: McnpCandidate[] = raw
    .filter((c: any) => c && typeof c.exe === "string" && c.exe)
    .map((c: any) => ({
      exe: c.exe,
      label: c.label || "MCNP?",
      source: c.source || "",
      xsdir: c.xsdir || "",
    }));
  // 旧后端（只有 found/exe/label）：也给出一个候选，否则下拉是空的、用户以为"没装 MCNP"
  if (!candidates.length && j && j.found && typeof j.exe === "string" && j.exe) {
    candidates.push({ exe: j.exe, label: j.label || "MCNP?", source: "", xsdir: "" });
  }
  const want = String(j?.selected || j?.exe || "");
  // 选中项必须在候选里：否则 <select value> 与 option 对不上，浏览器会**静默显示第一项**
  const exe = candidates.some((c) => c.exe === want) ? want : (candidates[0]?.exe || "");
  return {
    found: !!exe,
    exe,
    label: candidates.find((c) => c.exe === exe)?.label || j?.label || "MCNP?",
    candidates,
  };
}

/** 选项文案：同标签多份时带上上层目录（`MCNP6 — MCNP_CODE\bin\mcnp6.exe`）以便区分。 */
export function optionText(c: McnpCandidate, all: McnpCandidate[]): string {
  const sameLabel = all.filter((x) => x.label === c.label);
  if (sameLabel.length <= 1) return c.label;
  const parts = c.exe.split(/[\\/]/).filter(Boolean);
  const tail = parts.slice(-3, -1).join("\\");
  return tail ? `${c.label} — ${tail}` : c.label;
}

/** 选中后本地更新：exe / label / found 一起改，避免"下拉换了、旁边标签没换"。 */
export function applyMcnpSelection(state: McnpState, exe: string, note?: string): McnpState {
  const c = state.candidates.find((x) => x.exe === exe);
  return {
    ...state,
    exe,
    label: c?.label || state.label,
    found: !!exe,
    note: note !== undefined ? note : state.note,
  };
}

/** 悬停提示：完整路径 + 来源 + 该版本自带 xsdir（"选错版本/截面库没切"一眼可查）。 */
export function mcnpTooltip(state: McnpState): string {
  const c = state.candidates.find((x) => x.exe === state.exe);
  if (!c) return "未检测到 MCNP：请检查安装，或点下拉里的“手动指定 MCNP…”";
  const lines = [c.exe];
  if (c.source) lines.push(`来源：${c.source}`);
  lines.push(c.xsdir ? `截面库：${c.xsdir}` : "截面库：该安装未找到自带 xsdir（沿用当前）");
  if (state.note) lines.push(state.note);
  return lines.join("\n");
}

/* ── 下拉选项（含"手动指定…"）── */

/** "手动指定…"那一项的哨兵值（真 exe 路径不可能等于它） */
export const BROWSE_VALUE = "__browse__";

export interface McnpOption {
  value: string;
  text: string;
}

/**
 * 下拉的全部选项 = 检测到的候选 + 末尾一项"手动指定…"。
 *
 * 为什么**永远**带上那一项：自动检测在"装在非常规目录 / 检测路径全不命中"时会给出
 * 空列表，而那恰恰是最需要手动指定的场景 —— 若这时把 <select> 置灰，用户就彻底没有出路。
 * 一个候选都没有时，这一项顺带承担"未检测到"的提示（不另占一行）。
 */
export function mcnpOptions(state: McnpState): McnpOption[] {
  const opts: McnpOption[] = state.candidates.map((c) => ({
    value: c.exe,
    text: optionText(c, state.candidates),
  }));
  opts.push({
    value: BROWSE_VALUE,
    text: opts.length ? "手动指定 MCNP…" : "未检测到 MCNP · 手动指定…",
  });
  return opts;
}

/**
 * 手动指定的 exe 并入候选列表：同路径替换（`<option>` 不能重复），
 * 排序与后端 `mcnp_locator._sort_key` 同口径（MCNP6 → MCNP5 → 其它，再按路径），
 * 免得"手动指定完，它跳到列表中间/末尾"看起来像没生效。
 */
export function upsertCandidate(list: McnpCandidate[], c: McnpCandidate): McnpCandidate[] {
  const rank = (label: string) => (label === "MCNP6" ? 0 : label === "MCNP5" ? 1 : 2);
  return [...list.filter((x) => x.exe !== c.exe), c].sort(
    (a, b) => rank(a.label) - rank(b.label) || a.exe.toLowerCase().localeCompare(b.exe.toLowerCase()),
  );
}
