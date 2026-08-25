/**
 * universeGroups — 栅元按 U 分组（显示视图纯函数）+ 拖拽落点判定。
 *
 * 分组仅作用于显示（GeometryTab「按 U 分组显示」toggle），底层 cells 顺序不变：
 * raw 行不进组、组间插分隔头行（复用 raw 行分隔样式）。
 *
 * 「未分组」：u 为空 / 空白 / 非有限数值的栅元进「未分组」兜底组（哨兵 u=UNGROUPED_U=-1，
 * 数值升序时排最前）。拖拽栅元到「未分组」组头 = 清空该栅元的 u（交互自然：未分组=无宇宙）。
 */
import type { LocalCellRow } from "./cellBridge";

/** 「未分组」兜底组的哨兵宇宙号。真实 MCNP U 为非负整数，-1 绝不冲突。 */
export const UNGROUPED_U = -1;

export interface UniverseGroup {
  /** 组标识：UNGROUPED_U 表示「未分组」，否则为真实宇宙号 */
  u: number;
  /** 组内栅元行（均为 kind==="cell"，保持原相对顺序） */
  rows: LocalCellRow[];
  /** 组内每行在 cells 中的原始下标（拖拽改 u 用原始下标定位） */
  indices: number[];
  /** 该组在 cells 中的首个栅元行下标（供显示插入头行定位） */
  start: number;
  count: number;
}

/**
 * 按 u 数值升序分组；「未分组」（u 空/空白/非有限）以哨兵 UNGROUPED_U 排最前。
 * raw 行不进组。
 */
export function groupByUniverse(rows: LocalCellRow[]): UniverseGroup[] {
  const map = new Map<number, UniverseGroup>();
  rows.forEach((r, i) => {
    if (r.kind !== "cell") return;
    const uStr = (r.cell.u ?? "").trim();
    const u = uStr ? Number(uStr) : NaN;
    const key = Number.isFinite(u) ? u : UNGROUPED_U;
    const g = map.get(key);
    if (g) {
      g.rows.push(r);
      g.indices.push(i);
      g.count++;
    } else {
      map.set(key, { u: key, rows: [r], indices: [i], start: i, count: 1 });
    }
  });
  return Array.from(map.values()).sort((a, b) => a.u - b.u);
}

/**
 * 组头文案：未分组 →「未分组 · N 栅元」，普通组 →「U=n · N 栅元」。
 * 可选 comment（项9 组头自定义文字）：有则追加「· 「text」」（未分组组无宇宙不追加）。
 */
export function groupHeaderLabel(u: number, count: number, comment?: string): string {
  const base = u === UNGROUPED_U ? `未分组 · ${count} 栅元` : `U=${u} · ${count} 栅元`;
  if (u !== UNGROUPED_U && comment && comment.trim()) return `${base} · 「${comment.trim()}」`;
  return base;
}

/** 该组头是否代表「未分组」（拖拽到此 = 清空该栅元的 u） */
export function isUngroupedU(u: number): boolean {
  return u === UNGROUPED_U;
}

/* ── 拖拽判定（拖到组头→改 u；拖到普通行→保持行重排）── */

export type DropTarget = { kind: "cell"; to: number } | { kind: "group"; u: number };

export type DropDecision =
  | { kind: "regroup"; from: number; u: number }
  | { kind: "reorder"; from: number; to: number };

/** 纯函数判定：落组头 → 改 u；落普通行 → 行重排。
 *  regroup.u === UNGROUPED_U 时表示「清空 u」（拖到未分组组头）。 */
export function resolveDrop(from: number, target: DropTarget): DropDecision {
  return target.kind === "group"
    ? { kind: "regroup", from, u: target.u }
    : { kind: "reorder", from, to: target.to };
}

/**
 * 应用拖拽归组结果：把 rows 中 from 行的 u 设为 u（UNGROUPED_U → 清空 u）。不可变返回新数组。
 * 组件侧用其同时驱动 setCells 与 patch deck，保证「本地显示」与「deck 单一权威」单一事实来源。
 */
export function applyRegroupToRows(rows: LocalCellRow[], from: number, u: number): LocalCellRow[] {
  const nextU = u === UNGROUPED_U ? "" : String(u);
  return rows.map((c, i) => (i === from && c.kind === "cell" ? { ...c, cell: { ...c.cell, u: nextU } } : c));
}
