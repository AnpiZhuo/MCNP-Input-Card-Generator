/**
 * useQuickAddOverlap — 快捷建栅元「重合检测 + 补集决策」深模块。
 *
 * 把 GeometryTab 与 Preview3D 之间几乎逐行重复的逻辑抽到一起，接口只暴露
 * 「喂数据 + 统一写回」，把后端契约藏进实现：
 *   - 后端请求体组装（/api/quick-add-check 的 surfaces/cells/tr_cards/new_cells 结构）
 *   - appendCardText 拼接新栅元的曲面/TR 卡
 *   - applyQuickAddChoice 补集决策（new_hole/existing_hole/void_only/none）
 *   - 失败非静默（console.warn + 可选 onCheckFail 警告）
 * 宿主差异（数据来源、deck 写回动作）通过 3 个 getter + 1 个回调注入，不在此硬编码。
 */
import { useState } from "react";
import { apiUrl } from "./api";
import {
  appendCardText,
  applyQuickAddChoice,
  type QuickAddChoice,
  type QuickCellResult,
} from "./quickCell";

export interface QuickAddOverlapState {
  overlaps: any[];
  existingNums: number[];
  zeroVolume: number[];
  recommended: "new_hole" | "existing_hole";
  result: QuickCellResult;
}

/** 宿主现有栅元（中性结构；hook 内部再映射成后端 cell payload） */
export interface QuickAddCellSource {
  num: number;
  mat: string;
  density?: string;
  surfaces?: string;
  surface_expr?: string;
  u?: string;
  fill?: string;
  lat?: string;
  trcl?: string;
  render?: boolean;
  fill_grid?: string;
  impN?: string;
  impP?: string;
  impE?: string;
}

export interface UseQuickAddOverlapArg {
  /** 宿主现有栅元（每次调用读最新；请求体与补集决策都用它） */
  getExistingCells: () => QuickAddCellSource[];
  /** 宿主已有曲面卡文本（新栅元追加**前**） */
  getSurfaces: () => string;
  /** 宿主已有 TR 卡文本（新栅元追加**前**） */
  getTrCards: () => string;
  /** 写回（直接 / 决策 / 已处理统一走这里；result 已带 existingExprPatch 与 overlapHandled） */
  onApplyResult: (r: QuickCellResult) => void;
  /** 请求失败 → 非阻塞警告（可选；仅 GeometryTab 弹窗，Preview3D 省略） */
  onCheckFail?: (e: unknown) => void;
}

/** 中性栅元 → 后端 /api/quick-add-check 的 cells 项 */
function toCellPayload(c: QuickAddCellSource): any {
  return {
    kind: "cell",
    cell: {
      number: c.num,
      material: c.mat,
      density: c.density || "",
      surface_expr: c.surfaces ?? c.surface_expr ?? "",
      u: c.u || "",
      fill: c.fill || "",
      lat: c.lat || "",
      trcl: c.trcl || "",
      render: c.render !== false,
      fill_grid: c.fill_grid || "",
      imp_n: c.impN || "",
      imp_p: c.impP || "",
      imp_e: c.impE || "",
    },
  };
}

export function useQuickAddOverlap(arg: UseQuickAddOverlapArg) {
  const { getExistingCells, getSurfaces, getTrCards, onApplyResult, onCheckFail } = arg;
  const [quickCheck, setQuickCheck] = useState<QuickAddOverlapState | null>(null);
  const [busy, setBusy] = useState(false);

  const runCheck = async (r: QuickCellResult) => {
    setBusy(true);
    try {
      const req = {
        surfaces: appendCardText(getSurfaces(), r.surfacesText),
        cells: getExistingCells().map(toCellPayload),
        tr_cards: appendCardText(getTrCards(), r.trCardsText),
        new_cells: r.cells.map((c) => ({
          number: parseInt(c.num, 10) || 0,
          material: c.mat,
          density: c.density,
          surface_expr: c.surfaces,
        })),
      };
      const res = await fetch(apiUrl("/api/quick-add-check"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
        signal: AbortSignal.timeout(60000),
      });
      const j = await res.json();
      if (j.status !== "error" && j.overlaps && j.overlaps.length > 0) {
        const newNums = new Set(req.new_cells.map((c) => c.number));
        const existingNums = Array.from(new Set<number>(
          j.overlaps
            .filter((o: any) => newNums.has(o.a) !== newNums.has(o.b))
            .map((o: any) => Number(newNums.has(o.a) ? o.b : o.a)),
        ));
        setQuickCheck({
          overlaps: j.overlaps,
          existingNums,
          zeroVolume: j.zero_volume || [],
          recommended: j.recommended === "existing_hole" ? "existing_hole" : "new_hole",
          result: r,
        });
        setBusy(false);
        return;
      }
      onApplyResult(r);
    } catch (e) {
      // T2：检测失败仍写回栅元，但记录原因并允许宿主弹非阻塞警告（不再静默跳过）
      console.warn("[quick-add-check] 重合检测失败，未校验与已有栅元重叠:", e);
      onCheckFail?.(e);
      onApplyResult(r);
    } finally {
      setBusy(false);
    }
  };

  const applyChoice = (choice: QuickAddChoice) => {
    const qc = quickCheck;
    if (!qc) return;
    const existing = getExistingCells().map((c) => ({
      num: c.num,
      mat: String(c.mat),
      surfaces: c.surfaces ?? c.surface_expr ?? "",
    }));
    const patched = applyQuickAddChoice(qc.result, qc.overlaps, existing, choice);
    patched.overlapHandled = true;
    setQuickCheck(null);
    onApplyResult(patched);
  };

  return { quickCheck, busy, runCheck, applyChoice };
}
