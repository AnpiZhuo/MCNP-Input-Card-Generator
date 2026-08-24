/**
 * universeGroups — 栅元按 U 分组（显示视图纯函数）+ 拖拽落点判定。
 *
 * 分组仅作用于显示（GeometryTab「按 U 分组显示」toggle），底层 cells 顺序不变：
 * raw 行不进组、组间插分隔头行（复用 raw 行分隔样式）。
 */
import type { LocalCellRow } from "./cellBridge";

export interface UniverseGroup {
  /** 宇宙号（数值） */
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
 * 按 u 数值升序分组；raw 行 / 无有效 u 的栅元不进组。
 */
export function groupByUniverse(rows: LocalCellRow[]): UniverseGroup[] {
  const map = new Map<number, UniverseGroup>();
  rows.forEach((r, i) => {
    if (r.kind !== "cell") return;
    const uStr = (r.cell.u ?? "").trim();
    if (!uStr) return;
    const u = Number(uStr);
    if (!Number.isFinite(u)) return;
    const g = map.get(u);
    if (g) {
      g.rows.push(r);
      g.indices.push(i);
      g.count++;
    } else {
      map.set(u, { u, rows: [r], indices: [i], start: i, count: 1 });
    }
  });
  return Array.from(map.values()).sort((a, b) => a.u - b.u);
}

/** 组头文案：U=1 · 5 栅元 */
export function groupHeaderLabel(u: number, count: number): string {
  return `U=${u} · ${count} 栅元`;
}

/* ── 拖拽判定（拖到组头→改 u；拖到普通行→保持行重排）── */

export type DropTarget = { kind: "cell"; to: number } | { kind: "group"; u: number };

export type DropDecision =
  | { kind: "regroup"; from: number; u: number }
  | { kind: "reorder"; from: number; to: number };

/** 纯函数判定：落组头 → 改 u；落普通行 → 行重排 */
export function resolveDrop(from: number, target: DropTarget): DropDecision {
  return target.kind === "group"
    ? { kind: "regroup", from, u: target.u }
    : { kind: "reorder", from, to: target.to };
}
