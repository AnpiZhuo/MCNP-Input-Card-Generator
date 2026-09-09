/**
 * useCellClosure — 栅元封闭性检测 hook（深模块，惰性）
 *
 * 接口（很小）:
 *   useCellClosure(getDeck) → { statusOf(num), loading, refresh }
 *
 * 实现（藏在内部）:
 *   - 惰性：不自动请求（避免无谓 FreeCAD 子进程）。只有调用 refresh()
 *     （几何页点「3D 预览」按钮后）才向后端 /api/check-cell-closure 拉报告
 *   - 同 deck 指纹缓存：重复 refresh 同 deck 不重复请求
 *   - 失败静默降级（report 为空不打扰用户）
 *
 * 调用方只需要知道：
 *   - getDeck() 拿当前曲面/栅元/TR 文本
 *   - statusOf(cellNum) → ClosureEntry | undefined（undefined=未检测）
 */
import { useRef, useState, useCallback } from "react";
import { apiUrl } from "./api";
import type { ClosureEntry, ClosureReport } from "./cellClosure";

export interface CellClosureDeck {
  surfaces: string;
  cells: any[];
  tr_cards: string;
}

interface UseCellClosure {
  report: ClosureReport | null;
  loading: boolean;
  /** 取某个栅元的检测结果（undefined = 未检测 / 检测中） */
  statusOf(num: number | string): ClosureEntry | undefined;
  /** 拉取/刷新报告（3D 预览按钮点击后调用） */
  refresh(): void;
}

/** 简单指纹：deck 三要素 JSON 长度（足够区分意图改动） */
function deckFingerprint(d: CellClosureDeck): string {
  try {
    return `${d.surfaces.length}:${JSON.stringify(d.cells).length}:${d.tr_cards.length}`;
  } catch {
    return "";
  }
}

export function useCellClosure(getDeck: () => CellClosureDeck): UseCellClosure {
  const [report, setReport] = useState<ClosureReport | null>(null);
  const [loading, setLoading] = useState(false);
  const getDeckRef = useRef(getDeck);
  getDeckRef.current = getDeck;
  const fpRef = useRef<string>("");

  const refresh = useCallback(async () => {
    const deck = getDeckRef.current();
    const fp = deckFingerprint(deck);
    // 同 deck 已检测过 → 保留展示（几何未改，结果仍有效）
    if (fp && fp === fpRef.current && report) return;
    fpRef.current = fp || "";
    setLoading(true);
    try {
      const r = await fetch(apiUrl("/api/check-cell-closure"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          surfaces: deck.surfaces || "",
          cells: deck.cells || [],
          tr_cards: deck.tr_cards || "",
        }),
      });
      const j = await r.json();
      if (j.status === "ok") setReport(j.closure_report || {});
    } catch {
      // 后端不可用 → 静默保留上次结果
    } finally {
      setLoading(false);
    }
  }, [report]);

  const statusOf = useCallback((num: number | string): ClosureEntry | undefined => {
    return report?.[String(num)];
  }, [report]);

  return { report, loading, statusOf, refresh };
}
