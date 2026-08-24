/**
 * useDragToGroup — 指针式行拖动（复用 useRowDrag 骨架）+ 拖到组头改 u。
 *
 * 在栅元行上按下 → 移到目标（普通行高亮 / 组头高亮）→ 松开：
 *   - 落在组头（groupHandlers 的 onMouseUp）→ onDropOnGroup(from, u)
 *   - 落在普通栅元行 → onMove(from, to)（保持行重排）
 * 判定逻辑纯函数在 universeGroups.resolveDrop（可测）。
 */
import { useState } from "react";
import type React from "react";
import { resolveDrop } from "./universeGroups";

export function useDragToGroup(opts: {
  onMove: (from: number, to: number) => void;
  onDropOnGroup: (from: number, u: number) => void;
}) {
  const [fromIdx, setFromIdx] = useState<number | null>(null);
  const [overIdx, setOverIdx] = useState<number | null>(null);
  const [overU, setOverU] = useState<number | null>(null);

  const finish = () => {
    setFromIdx(null);
    setOverIdx(null);
    setOverU(null);
  };

  /** 栅元行：按下开始拖动；移过高亮；松开按判定落点（组头优先） */
  const cellHandlers = (i: number) => ({
    onMouseDown: (e: React.MouseEvent) => {
      if (e.button !== 0) return;
      const t = e.target as HTMLElement;
      if (t.closest && t.closest("input, textarea, select, button, a, label")) return;
      setFromIdx(i);
      setOverIdx(null);
      setOverU(null);
      e.preventDefault();
    },
    onMouseMove: () => {
      if (fromIdx === null) return;
      setOverIdx(i);
      setOverU(null);
    },
    onMouseUp: () => {
      if (fromIdx !== null) {
        const d = resolveDrop(fromIdx, overU != null ? { kind: "group", u: overU } : { kind: "cell", to: i });
        if (d.kind === "regroup") opts.onDropOnGroup(d.from, d.u);
        else if (d.from !== d.to) opts.onMove(d.from, d.to);
      }
      finish();
    },
  });

  const cellStyle = (i: number): React.CSSProperties => ({
    cursor: "grab",
    opacity: fromIdx === i ? 0.4 : 1,
    boxShadow: overIdx === i ? "inset 0 2px 0 0 var(--accent)" : "none",
  });

  /** 组头行：仅作为拖拽落点（落 u） */
  const groupHandlers = (u: number) => ({
    onMouseDown: (e: React.MouseEvent) => {
      if (fromIdx !== null) e.preventDefault();
    },
    onMouseMove: () => {
      if (fromIdx === null) return;
      setOverU(u);
      setOverIdx(null);
    },
    onMouseUp: () => {
      if (fromIdx !== null) opts.onDropOnGroup(fromIdx, u);
      finish();
    },
  });

  const groupStyle = (u: number): React.CSSProperties =>
    overU === u ? { boxShadow: "inset 0 2px 0 0 var(--accent)" } : {};

  return { cellHandlers, cellStyle, groupHandlers, groupStyle, dragging: fromIdx !== null };
}
