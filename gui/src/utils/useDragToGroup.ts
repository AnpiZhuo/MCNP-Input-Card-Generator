/**
 * useDragToGroup — 指针式行拖动（复用 useRowDrag 骨架）+ 拖到组头改 u。
 *
 * 在栅元行上按下 → 移到目标（普通行高亮 / 组头高亮）→ 松开：
 *   - 落在组头（groupHandlers 的 onMouseUp）→ onDropOnGroup(from, u)
 *   - 落在普通栅元行 → onMove(from, to)（保持行重排）
 *   - 松手落在非目标元素（组间隙/表头/空白）→ window 级 mouseup 按「最后悬停目标」
 *     结算（用 refs），避免拖拽丢失（真实浏览器常见：用户实测「拖拽后 U 未改动」根因之一）。
 * 判定逻辑纯函数在 universeGroups.resolveDrop（可测）。
 */
import { useEffect, useRef, useState } from "react";
import type React from "react";
import { resolveDrop } from "./universeGroups";

export function useDragToGroup(opts: {
  onMove: (from: number, to: number) => void;
  onDropOnGroup: (from: number, u: number) => void;
}) {
  const [fromIdx, setFromIdx] = useState<number | null>(null);
  const [overIdx, setOverIdx] = useState<number | null>(null);
  const [overU, setOverU] = useState<number | null>(null);
  // refs：事件期间读取最新悬停目标（window 级结算用）
  const optsRef = useRef(opts);
  optsRef.current = opts;
  const fromRef = useRef<number | null>(null);
  fromRef.current = fromIdx;
  const overIdxRef = useRef<number | null>(null);
  overIdxRef.current = overIdx;
  const overURef = useRef<number | null>(null);
  overURef.current = overU;
  // 已由 per-element onMouseUp 结算 → window 监听跳过（防双结算）
  const resolvedRef = useRef(false);

  const finish = () => {
    setFromIdx(null);
    setOverIdx(null);
    setOverU(null);
  };

  // window 级 mouseup：松手在任意位置都按最后悬停目标结算（防拖拽丢失）
  useEffect(() => {
    if (fromIdx === null) return;
    const onWindowUp = () => {
      if (resolvedRef.current) {
        resolvedRef.current = false;
        return;
      }
      const from = fromRef.current;
      if (from !== null) {
        const u = overURef.current;
        const to = overIdxRef.current;
        if (u != null) optsRef.current.onDropOnGroup(from, u);
        else if (to != null && to !== from) optsRef.current.onMove(from, to);
      }
      setFromIdx(null);
      setOverIdx(null);
      setOverU(null);
    };
    window.addEventListener("mouseup", onWindowUp);
    return () => window.removeEventListener("mouseup", onWindowUp);
  }, [fromIdx]);

  /** 栅元行：按下开始拖动；移过高亮；松开按判定落点（组头优先） */
  const cellHandlers = (i: number) => ({
    onMouseDown: (e: React.MouseEvent) => {
      if (e.button !== 0) return;
      const t = e.target as HTMLElement;
      if (t.closest && t.closest("input, textarea, select, button, a, label")) return;
      resolvedRef.current = false;
      setFromIdx(i);
      setOverIdx(null);
      setOverU(null);
      e.preventDefault();
    },
    onMouseMove: () => {
      if (fromRef.current === null) return;
      setOverIdx(i);
      setOverU(null);
    },
    onMouseUp: () => {
      if (fromRef.current !== null) {
        const d = resolveDrop(
          fromRef.current,
          overURef.current != null
            ? { kind: "group", u: overURef.current }
            : { kind: "cell", to: i },
        );
        if (d.kind === "regroup") optsRef.current.onDropOnGroup(d.from, d.u);
        else if (d.from !== d.to) optsRef.current.onMove(d.from, d.to);
      }
      resolvedRef.current = true;
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
      if (fromRef.current === null) return;
      setOverU(u);
      setOverIdx(null);
    },
    onMouseUp: () => {
      if (fromRef.current !== null) optsRef.current.onDropOnGroup(fromRef.current, u);
      resolvedRef.current = true;
      finish();
    },
  });

  const groupStyle = (u: number): React.CSSProperties =>
    overU === u ? { boxShadow: "inset 0 2px 0 0 var(--accent)" } : {};

  return { cellHandlers, cellStyle, groupHandlers, groupStyle, dragging: fromIdx !== null };
}
