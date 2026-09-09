/**
 * useCellClosure — 栅元封闭性检测 hook（深模块）
 *
 * 接口（很小）:
 *   useCellClosure(getDeck, refreshKey?) → { report, statusOf(num), loading, refresh }
 *
 * 实现（藏在内部）:
 *   - 从后端 /api/check-cell-closure 拉取全栅元封闭性报告
 *   - 按 deck 指纹做缓存（同 deck 不重复请求，FreeCAD 子进程只跑一次）
 *   - 支持手动 refresh（如 3D 预览按钮点击后刷新）
 *   - 失败静默降级（report 为空，不打扰用户）
 *
 * 调用方只需要知道：
 *   - 传一个 getDeck() 拿当前曲面/栅元/TR 文本
 *   - statusOf(cellNum) → ClosureEntry | undefined（undefined=未检测/检测中）
 */
import { useEffect, useRef, useState, useCallback } from "react";
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
  /** 强制重新检测（3D 预览 / 用户操作后调用） */
  refresh(): void;
}

/** 简单指纹：deck 三要素 + JSON 字符串长度（足够区分意图改动） */
function deckFingerprint(d: CellClosureDeck): string {
  try {
    return `${d.surfaces.length}:${JSON.stringify(d.cells).length}:${d.tr_cards.length}`;
  } catch {
    return "";
  }
}

export function useCellClosure(
  getDeck: () => CellClosureDeck,
  refreshKey?: number | string,
): UseCellClosure {
  const [report, setReport] = useState<ClosureReport | null>(null);
  const [loading, setLoading] = useState(false);
  const lastFpRef = useRef<string>("");
  const getDeckRef = useRef(getDeck);
  getDeckRef.current = getDeck;

  const load = useCallback(async () => {
    const deck = getDeckRef.current();
    const fp = deckFingerprint(deck);
    // 同 deck 已检测过 → 不重复请求（保持已展示结果）
    if (fp && fp === lastFpRef.current && report) return;
    lastFpRef.current = fp || "";
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
      // 后端不可用 → 静默保留上次结果（若存在）
    } finally {
      setLoading(false);
    }
  }, [report]);

  // 挂载 + refreshKey 变化时检测
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  const refresh = useCallback(() => {
    lastFpRef.current = ""; // 强制重跑（忽略缓存）
    setReport(null);
    load();
  }, [load]);

  const statusOf = useCallback((num: number | string): ClosureEntry | undefined => {
    return report?.[String(num)];
  }, [report]);

  return { report, loading, statusOf, refresh };
}
