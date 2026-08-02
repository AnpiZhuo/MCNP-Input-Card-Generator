/**
 * GridState 深模块 — E0/En/T0/Tn 网格的单一权威状态
 *
 * 把"卡体文本 ↔ 结构化网格"的所有解析/序列化逻辑收进这里，
 * GridEditor 只做受控渲染，导入/生成都通过这两个转换函数进出。
 *
 * 后端契约字段（e_min / e_log / e_custom_text / e_cards_text / t0_* / t_cards_text）
 * 在这里与 deck.grids 双向互转，保证生成载荷逐字段一致。
 */
import type { TallyDef } from "./DeckContext";

export type GridMode = "linear" | "log" | "custom";

export interface GridValue {
  mode: GridMode;
  min: string;   // 线性/对数下限（原文保留）
  max: string;   // 上限
  bins: string;  // 区间数（原文保留，生成时转 int）
  log: boolean;  // log 为 true（仅 mode=log 时用；mode 本身也表达，保留冗余兼容）
  custom: string; // 自定义卡体（原文，可为多行）
}

export const emptyGrid = (): GridValue => ({ mode: "custom", min: "", max: "", bins: "", log: false, custom: "" });

/** MCNP 参数化正则：a m i|lin|log b（整串恰好这个形态才命中） */
const PARAM_RE = /^([\d.eE+-]+)\s+(\d+)(i|lin|log)\s+([\d.eE+-]+)$/i;

/** 参数化检测：纯 "a m i|lin|log b" → {min,max,bins,log}；否则 null */
export function parseParametric(body: string): { min: string; max: string; bins: string; log: boolean } | null {
  const m = body.trim().match(PARAM_RE);
  if (!m) return null;
  return { min: m[1], max: m[4], bins: m[2], log: m[3].toLowerCase() === "log" };
}

/**
 * 卡体 → GridValue：
 * - 纯参数化 "1 3log 10" → log 模式参数
 * - 纯数值 / 混合 / 多行 → custom 原文（原样保留，后端负责拆行）
 */
export function setFromBody(body: string): GridValue {
  const p = parseParametric(body);
  if (p) return { mode: p.log ? "log" : "linear", min: p.min, max: p.max, bins: p.bins, log: p.log, custom: "" };
  return { mode: "custom", min: "", max: "", bins: "", log: false, custom: body.trim() };
}

/** GridValue → 卡体（按 mode） */
export function getBody(gv: GridValue): string {
  if (gv.mode === "custom") return gv.custom;
  const syntax = gv.mode === "log" ? "log" : "i";
  return `${gv.min} ${gv.bins || 0}${syntax} ${gv.max}`.trim();
}

/**
 * 导入：后端 parse-inp 返回的 tally 字典 → grids 表
 *   e_custom_text/e_min → grids["e"]；e_cards_text 逐行 → grids["e25"]...
 *   支持多行续行卡（续行并入上一张卡体）
 */
export function buildGridsFromTally(tally: Record<string, any>): Record<string, GridValue> {
  const grids: Record<string, GridValue> = {};

  // E0 / T0 全局网格
  if (tally?.e_custom_text) grids["e"] = setFromBody(tally.e_custom_text);
  else if (tally?.e_min)
    grids["e"] = { mode: tally.e_log ? "log" : "linear", min: String(tally.e_min), max: String(tally.e_max || ""), bins: String(tally.e_bins || ""), log: !!tally.e_log, custom: "" };

  if (tally?.t0_custom_text) grids["t"] = setFromBody(tally.t0_custom_text);
  else if (tally?.t0_min)
    grids["t"] = { mode: tally.t0_log ? "log" : "linear", min: String(tally.t0_min), max: String(tally.t0_max || ""), bins: String(tally.t0_bins || ""), log: !!tally.t0_log, custom: "" };

  // En / Tn 逐计数卡（支持续行）
  const collect = (text: string, letter: "E" | "T") => {
    const bodies: Record<string, string[]> = {};
    let current = "";
    for (const raw of (text || "").split("\n")) {
      const line = raw.trim();
      if (!line) continue;
      const m = line.match(new RegExp(`^${letter}(\\d+)(?:\\s+(.*))?$`, "i"));
      if (m) {
        current = `${letter}${m[1]}`;
        bodies[current] = [m[2] || ""];
      } else if (current) {
        bodies[current].push(line); // 续行
      }
    }
    for (const [key, parts] of Object.entries(bodies)) {
      grids[key.toLowerCase()] = setFromBody(parts.join("\n"));
    }
  };
  collect(tally?.e_cards_text || "", "E");
  collect(tally?.t_cards_text || "", "T");

  return grids;
}

/**
 * 生成：grids 表 + tallies → 后端契约载荷（E0/T0 全局 + En/Tn 逐计数卡文本）
 * 逐字段对齐 handleGenerate 现有输出，后端 _tally_from_dict 无需改动。
 */
export function buildTallyFromGrids(grids: Record<string, GridValue>, tallies: TallyDef[]): Record<string, any> {
  const g = (prefix: string): GridValue => grids[prefix] || emptyGrid();
  const eg = g("e");
  const tg = g("t");

  const enCards: string[] = [];
  const tnCards: string[] = [];
  for (const t of tallies || []) {
    if (t.enableEn) {
      const body = getBody(g(`e${t.number}`));
      if (body) enCards.push(`E${t.number}  ${body}`);
    }
    if (t.enableTn) {
      const body = getBody(g(`t${t.number}`));
      if (body) tnCards.push(`T${t.number}  ${body}`);
    }
  }

  return {
    e_min: eg.mode !== "custom" ? eg.min : "",
    e_max: eg.mode !== "custom" ? eg.max : "",
    e_bins: eg.mode !== "custom" ? (parseInt(eg.bins) || 0) : 0,
    e_log: eg.mode === "log",
    e_custom_enabled: eg.mode === "custom",
    e_custom_text: eg.mode === "custom" ? eg.custom : "",
    t0_min: tg.mode !== "custom" ? tg.min : "",
    t0_max: tg.mode !== "custom" ? tg.max : "",
    t0_bins: tg.mode !== "custom" ? (parseInt(tg.bins) || 0) : 0,
    t0_log: tg.mode === "log",
    t0_custom_enabled: tg.mode === "custom",
    t0_custom_text: tg.mode === "custom" ? tg.custom : "",
    e_cards_text: enCards.join("\n"),
    t_cards_text: tnCards.join("\n"),
  };
}
