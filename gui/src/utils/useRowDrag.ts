/**
 * useRowDrag — 指针式行拖动排序（mousedown/mousemove/mouseup）。
 *
 * 为什么不用 HTML5 原生 DnD：在表格行（<tr>）上 Chromium 常不启动拖拽
 * （光标变 grab 但抓不住），且无视觉反馈。指针式实现可靠、可控：
 *   按下某行 → 移到目标行（高亮） → 松开 → onMove(from, to)。
 *
 * 用法：
 *   const drag = useRowDrag(moveRow);
 *   rows.map((r, i) => <tr {...drag.rowHandlers(i)} style={{...drag.rowStyle(i)}}>)
 */
import { useState } from "react";

export function useRowDrag(onMove: (from: number, to: number) => void) {
  const [fromIdx, setFromIdx] = useState<number | null>(null);
  const [overIdx, setOverIdx] = useState<number | null>(null);

  const rowHandlers = (i: number) => ({
    onMouseDown: (e: React.MouseEvent) => {
      if (e.button !== 0) return;
      // 交互元素（输入框/按钮/下拉/链接）不触发拖动，保留正常编辑/点击
      const t = e.target as HTMLElement;
      if (t.closest && t.closest("input, textarea, select, button, a, label")) return;
      setFromIdx(i);
      setOverIdx(null);
      e.preventDefault(); // 阻止文本选择/图片拖动干扰
    },
    onMouseMove: (e: React.MouseEvent) => {
      if (fromIdx === null) return;
      if (overIdx !== i) setOverIdx(i);
    },
    onMouseUp: () => {
      if (fromIdx !== null && fromIdx !== i) onMove(fromIdx, i);
      setFromIdx(null);
      setOverIdx(null);
    },
  });

  const rowStyle = (i: number): React.CSSProperties => ({
    cursor: "grab",
    opacity: fromIdx === i ? 0.4 : 1,
    boxShadow: overIdx === i ? "inset 0 2px 0 0 var(--accent)" : "none",
  });

  return { rowHandlers, rowStyle };
}
