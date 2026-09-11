/*
 * sourceAdv — 源项状态深度模块（codebase-design）
 *
 * 源项的全部状态以 `deck.adv`（后端模型 adv，即 MCP / generate / /workspace 的权威）
 * 为唯一存储点；本模块提供这一侧的纯函数：显示态派生、规范词汇、键清单、JSON 序列化，
 * 以及把旧版 deck 顶层中间态（sourceMode/sdefFields/kcodeFields/…）迁移进 adv 的唯一入口。
 *
 * 不再存在 `deck.sourceMode / sdefFields / kcodeFields / ksrcPoints /
 * sswFields / ssrFields / distributions / sdefRawText` 顶层副本。
 */
import type { DistEntry } from "./DeckContext";
import { parseDistributionLines } from "./distDual";

/* ── 判别量词汇 ── */
/** 后端/生成器规范 source_mode 值域（app/models.py:438；parse 亦产出 surface） */
export type SourceModeVocab = "fixed" | "distribution" | "kcode" | "surface";
/** 源项页 UI 可切换面板 */
export type UiSourceMode = "sdef" | "surface" | "kcode" | "text";

export interface KsrcPoint { x: string; y: string; z: string }

/* ── 键清单（单一事实；取代 App.tsx 与 contract.ts 手写表）── */
/** SDEF 表单字段（adv 键；sdef_eff 无后端字段，经 sdef_extra 走，见 SDEF_EFF_KEY） */
export const SDEF_FORM_KEYS = [
  "sdef_par", "sdef_erg", "sdef_pos_x", "sdef_pos_y", "sdef_pos_z", "sdef_wgt",
  "sdef_dir", "sdef_cel", "sdef_tme", "sdef_vec", "sdef_axs", "sdef_rad",
  "sdef_ext", "sdef_sur", "sdef_nrm", "sdef_tr", "sdef_ccc", "sdef_ara", "sdef_rate",
] as const;

/** sdef_eff 无后端模型字段（app/models.py AdvancedSettings 无）→ 折叠进 adv.sdef_extra 的 EFF 记号 */
export const SDEF_EFF_KEY = "sdef_eff";

/** KCODE 表单字段（adv 键；kcode_nsrc…kcode_kc8） */
export const KCODE_FORM_KEYS = [
  "kcode_nsrc", "kcode_rkk", "kcode_ikz", "kcode_kct",
  "kcode_knrm", "kcode_msrk", "kcode_mrkp", "kcode_kc8",
] as const;

/** SSW 表单槽 → adv 键（adv 展开式扁平，无独立对象） */
export const SSW_ADV_KEYS: Record<"surf" | "sym" | "pty" | "cel", string> = {
  surf: "ssw_surf", sym: "ssw_sym", pty: "ssw_pty", cel: "ssw_cel",
};
/** SSR 表单槽 → adv 键 */
export const SSR_ADV_KEYS: Record<"surf" | "mode" | "cel" | "pty" | "col" | "wgt" | "tr" | "psc", string> = {
  surf: "ssr_surf", mode: "ssr_mode", cel: "ssr_cel", pty: "ssr_pty",
  col: "ssr_col", wgt: "ssr_wgt", tr: "ssr_tr", psc: "ssr_psc",
};

/* ── 显示态派生（受控：每次 render 从 adv 计算，不落本地 state）── */
/** adv.source_mode（后端词汇）→ 源项页面板。kcode/surface 原样；distribution/sdef/fixed/空一律 SDEF。 */
export function uiModeFromAdv(adv: Record<string, any> | undefined, sdefTextOn: boolean | undefined): UiSourceMode {
  if (sdefTextOn) return "text";
  const sm = adv?.source_mode;
  if (sm === "kcode") return "kcode";
  if (sm === "surface") return "surface";
  return "sdef";
}

/** 规范 source_mode：kcode/surface 原样；其余（sdef/fixed/空/未知）一律收敛为 distribution。 */
export function canonicalSourceMode(adv: Record<string, any> | undefined): SourceModeVocab {
  const sm = adv?.source_mode;
  if (sm === "kcode") return "kcode";
  if (sm === "surface") return "surface";
  return "distribution";
}

/** 展示面板 → 要写入 adv.source_mode 的规范词汇（text 不写判别量，仅 textMode.sdef）。 */
export function vocabForUi(mode: Exclude<UiSourceMode, "text">): SourceModeVocab {
  if (mode === "kcode") return "kcode";
  if (mode === "surface") return "surface";
  return "distribution";
}

/* ── 序列化（adv 存字符串，UI 用结构）── */

/** adv.sdef_distributions(JSON 字符串) → DistEntry[]；空/坏 JSON → []。 */
export function parseDistributions(str: string | undefined): DistEntry[] {
  if (!str) return [];
  try {
    const v = JSON.parse(str);
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}

/** DistEntry[] → adv.sdef_distributions；空数组 → ""（沿用 App.tsx:366 语义，避免 "[]" truthy 误走分布生成）。 */
export function serializeDistributions(list: DistEntry[]): string {
  return list && list.length ? JSON.stringify(list) : "";
}

/** adv.ksrc_points(JSON 字符串) → KsrcPoint[]（坐标统一字符串，兼容 number/string）。 */
export function parseKsrc(str: string | undefined): KsrcPoint[] {
  if (!str) return [];
  try {
    const v = JSON.parse(str);
    if (!Array.isArray(v)) return [];
    return v.map((p: any) => ({
      x: String(p?.x ?? ""),
      y: String(p?.y ?? ""),
      z: String(p?.z ?? ""),
    }));
  } catch {
    return [];
  }
}

/** KsrcPoint[] → adv.ksrc_points(JSON 字符串)。 */
export function serializeKsrc(list: KsrcPoint[]): string {
  return JSON.stringify(list);
}

/* ── sdef_extra 记号辅助（sdef_eff 折叠位）── */

/** 从 adv.sdef_extra（空格分隔的 KEY=value 记号串）读取某记号值。 */
export function readExtraToken(extra: string | undefined, name: string): string {
  const pre = name + "=";
  for (const tok of (extra || "").split(/\s+/)) {
    if (tok.startsWith(pre)) return tok.slice(pre.length);
  }
  return "";
}

/** 设置/移除某记号，返回新的 sdef_extra 串（value 为空则移除该记号）。 */
export function setExtraToken(extra: string | undefined, name: string, value: string): string {
  const pre = name + "=";
  const rest = (extra || "").split(/\s+/).filter((t) => t && !t.startsWith(pre)).join(" ");
  const v = value.trim();
  return v ? (rest ? rest + " " : "") + pre + v : rest;
}

/* ── 旧存档迁移（唯一入口：DeckContext.loadDeck 前置调用，幂等）── */

/** 顶层旧中间态键名（迁移后一律删除，收窄 PUT /workspace 载荷；deck_from_json 本就忽略它们）。 */
export const LEGACY_SOURCE_KEYS = [
  "sourceMode", "sdefFields", "sdefRawText", "distributions",
  "sswFields", "ssrFields", "kcodeFields", "ksrcPoints",
] as const;

/**
 * 把旧版 deck 顶层中间态折叠进 deck.adv（仅当 adv 缺对应值才取中间态，避免覆盖
 * AI / parse 已写入的权威值），随后删除顶层中间态键。
 *
 * 语义：按「最终 source_mode 所属组」折叠对应中间态（kcode→KCODE+HSRC+KSRC；
 * surface→SSW/SSR；SDEF 族 distribution/fixed/sdef→SDEF 字段/分布/raw）。旧 UI 里
 * 顶层 sourceMode 反映用户最后选的模式，其余模式的中间态是跨模式残留，不折叠以免污染权威 adv。
 */
export function migrateLegacySourceKeys(deck: any): any {
  if (!deck || typeof deck !== "object") return deck;
  const d = deck as Record<string, any>;
  const adv: Record<string, any> = { ...(d.adv || {}) };
  const old = (d as Record<string, any>);

  const sf = old.sdefFields || {};
  const ssw = old.sswFields || {};
  const ssr = old.ssrFields || {};
  const kcf = old.kcodeFields || {};
  const hasKcodeLegacy = Object.keys(kcf).some((k) => kcf[k] !== undefined && kcf[k] !== "") || !!old.ksrcPoints;
  const hasSurfaceLegacy = Object.keys(ssw).some((k) => ssw[k]) || Object.keys(ssr).some((k) => ssr[k]);
  const hasSdefLegacy = SDEF_FORM_KEYS.some((k) => sf[k]) || !!old.sdefRawText || (Array.isArray(old.distributions) && old.distributions.length > 0);

  // 定组：adv.source_mode 权威优先；否则顶层 sourceMode；都没有则按存在的残留推断
  const rawSm = adv.source_mode !== undefined && adv.source_mode !== "" ? adv.source_mode : old.sourceMode;
  let group: "kcode" | "surface" | "sdef" | null = null;
  if (rawSm === "kcode") group = "kcode";
  else if (rawSm === "surface") group = "surface";
  else if (rawSm !== undefined && rawSm !== "") group = "sdef"; // distribution/fixed/sdef
  else if (hasKcodeLegacy) group = "kcode";
  else if (hasSurfaceLegacy) group = "surface";
  else if (hasSdefLegacy) group = "sdef";

  if (group) {
    adv.source_mode = group === "kcode" ? "kcode" : group === "surface" ? "surface" : "distribution";
    if (group === "kcode") {
      for (const k of KCODE_FORM_KEYS) if (!adv[k] && kcf[k]) adv[k] = kcf[k];
      if (adv.hsrc_enabled === undefined && kcf.hsrc_enabled !== undefined) adv.hsrc_enabled = !!kcf.hsrc_enabled;
      if (!adv.hsrc_text && kcf.hsrc_text) adv.hsrc_text = kcf.hsrc_text;
      if (!adv.ksrc_points && old.ksrcPoints) adv.ksrc_points = old.ksrcPoints;
    } else if (group === "surface") {
      for (const slot of Object.keys(SSW_ADV_KEYS) as (keyof typeof SSW_ADV_KEYS)[]) {
        const ak = SSW_ADV_KEYS[slot];
        if (!adv[ak] && ssw[slot]) adv[ak] = ssw[slot];
      }
      for (const slot of Object.keys(SSR_ADV_KEYS) as (keyof typeof SSR_ADV_KEYS)[]) {
        const ak = SSR_ADV_KEYS[slot];
        if (!adv[ak] && ssr[slot]) adv[ak] = ssr[slot];
      }
    } else {
      for (const k of SDEF_FORM_KEYS) if (!adv[k] && sf[k]) adv[k] = sf[k];
      if (sf[SDEF_EFF_KEY] && !readExtraToken(adv.sdef_extra, "EFF")) {
        adv.sdef_extra = setExtraToken(adv.sdef_extra, "EFF", sf[SDEF_EFF_KEY]);
      }
      if (!adv.sdef_distributions && Array.isArray(old.distributions) && old.distributions.length) {
        adv.sdef_distributions = serializeDistributions(old.distributions);
      }
      // TD-23：后端 sdef_raw_text 字段已整条退役 —— 旧存档的 sdefRawText 不再有对应
      // adv 字段可搬，只能把其中的 SI/SP/SB/DS/SC 原文行**解析成 v2 分布**迁进
      // sdef_distributions（否则旧存档的源分布静默丢失）。仅当上面没有权威结构时兜底，
      // 避免覆盖旧存档里已有的 distributions。
      if (!adv.sdef_distributions && typeof old.sdefRawText === "string" && old.sdefRawText.trim()) {
        const migrated = parseDistributionLines(old.sdefRawText);
        if (migrated.length) adv.sdef_distributions = serializeDistributions(migrated);
      }
    }
  }

  const out: Record<string, any> = { ...d, adv };
  for (const k of LEGACY_SOURCE_KEYS) delete out[k];
  return out;
}
