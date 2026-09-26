import type { TallyDef } from "./DeckContext";

/**
 * tallyBridge — 计数卡行双向桥接纯函数（TallyTab 本地工作副本 ↔ deck.tallies 单一权威）。
 *
 * 为什么单独成模块：卡片**身份字段**（`fn_prefix` / `number_suffix`）此前只在
 * TallyTab 组件内部的闭包里映射，两处 map 谁漏一个字段都没有任何测试能看见 ——
 * 2026-09-26 用户实测的两条症状正是从这里漏出去的：
 *   ① 导入 `*F4:N 1` → 前端前缀下拉框永远显示"无"（解析侧带不出）；
 *   ② 在界面上选了 `*` 再点生成 → 生成的还是 `F4:N`（生成侧带不上）。
 *
 * 命名约定（照 cellBridge / fmeshState 先例）：
 *   - 后端词汇 snake_case：`fn_prefix`（"" / "*" / "+" / "FIP" / "FIR" / "FIC"）、
 *     `number_suffix`（F5 环探测器轴字母 X/Y/Z）；这两个字段前后端同名，不再另起 camelCase。
 *   - 本地编辑态用 `prefix` / `suffix`（短名，只在本文件与 TallyTab 出现）。
 *
 * 不变量（useDeckSynced 判等价靠它）：`toDeck(fromDeck(x)) ≡ x`（后端回显字段名）。
 */

/** 计数卡前缀修饰："" = 通量（默认）/ "*" = 能量沉积 / "+"（MCNP 前缀修饰）；
 *  另有 F5 成像家族 "FIP"/"FIR"/"FIC"（解析器把它们放在同一字段里）。 */
export const TALLY_PREFIX_OPTIONS = ["", "*", "+"] as const;

/** TallyTab 本地计数行：稳定 id（React key，不进 deck）+ 可编辑字段 */
export interface TallyRow {
  id: number;
  /** 前端 deck 键 `fn_prefix`："" / "*" / "+" / "FIP" / "FIR" / "FIC" */
  prefix: string;
  /** "F1"…"F8" */
  type: string;
  /** 卡号（字符串形态便于编辑中途的空值/半成品） */
  number: string;
  /** 前端 deck 键 `number_suffix`：F5 环探测器轴字母，其余类型为空 */
  suffix: string;
  particle: string;
  params: string;
  multiplier: string;
  enableEn: boolean;
  enableTn: boolean;
}

/** 无 id 的行（deck → 本地时再由调用方按位置补稳定 id） */
export type TallyRowFields = Omit<TallyRow, "id">;

/** deck.tallies（后端 `_deck_to_frontend_dict` 口径）→ 本地行字段 */
export function deckTalliesToRows(tallies: any[] | undefined | null): TallyRowFields[] {
  return (tallies || []).map((t: any) => ({
    prefix: t?.fn_prefix ?? t?.fnPrefix ?? "",
    type: String(t?.type ?? ""),
    number: t?.number === undefined || t?.number === null ? "" : String(t.number),
    suffix: t?.number_suffix ?? t?.numberSuffix ?? "",
    particle: t?.particle ?? "n",
    params: t?.params ?? "",
    multiplier: t?.multiplier ?? "",
    enableEn: !!t?.enableEn,
    enableTn: !!t?.enableTn,
  }));
}

/** 本地行 → deck.tallies（后端 `_tally_from_dict` 口径；含卡片身份字段）。
 *  键序**照抄后端 `_deck_to_frontend_dict` 的回显顺序** —— `useDeckSynced` 用 JSON 串判等价，
 *  键序不同会被判成"不等价"而白拉一次回显（不致命，但没必要）。 */
export function rowsToDeckTallies(rows: TallyRow[]): TallyDef[] {
  return (rows || []).map((r) => ({
    type: r.type,
    number: parseInt(r.number) || 0,
    particle: r.particle || "n",
    params: r.params,
    enableEn: r.enableEn,
    enableTn: r.enableTn,
    multiplier: r.multiplier,
    fn_prefix: r.prefix || "",
    number_suffix: r.suffix || "",
  }));
}

/** 卡号输入里的后缀字母（MCNP：F5X/F5Y/F5Z 环探测器、F5 成像 IC/IR/IP 另算）。
 *  返回 { number, suffix }：`25X` → { number:"25", suffix:"X" }；`25` → { number:"25", suffix:"" }。 */
export function splitTallyNumber(raw: string): { number: string; suffix: string } {
  const trimmed = (raw ?? "").trim();
  const m = trimmed.match(/^(.*?)([XYZxyz])$/);
  if (!m) return { number: trimmed, suffix: "" };
  return { number: m[1].replace(/^[Ff]/, ""), suffix: m[2].toUpperCase() };
}
