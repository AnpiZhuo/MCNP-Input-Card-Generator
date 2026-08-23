import type { CellData } from "../components/CellEditDialog";

/**
 * 批量编辑栅元：单个栅元编辑弹窗的聚合版本。
 *
 * 约定：
 * - 除 surfaceAppend 外，所有字段为「空字符串 = 不改该项」；
 * - 曲面表达式永远只做「追加」，绝不覆盖/删除已有表达式（见 user 需求「无法批量更改曲面表达式，只可添加」）。
 */
export interface BatchCellEditValues {
  mat?: string;
  density?: string;
  impN?: string;
  impP?: string;
  impE?: string;
  vol?: string;
  pwt?: string;
  ext?: string;
  fcl?: string;
  u?: string;
  fill?: string;
  lat?: string;
  trcl?: string;
  tmp?: string;
  otherParams?: string;
  /** 追加到勾选栅元曲面表达式之后的内容（如 "3 -4"），只会追加不覆盖 */
  surfaceAppend?: string;
}

/** 空值 = 不改该项 */
function pick(current: string, value?: string): string {
  if (value === undefined || value === "") return current;
  return value;
}

/** 把批量编辑值应用到单个栅元，返回新栅元（不改原对象） */
export function applyBatchCellEdit(cell: CellData, values: BatchCellEditValues): CellData {
  const next: CellData = {
    ...cell,
    mat: pick(cell.mat, values.mat),
    density: pick(cell.density, values.density),
    impN: pick(cell.impN, values.impN),
    impP: pick(cell.impP, values.impP),
    impE: pick(cell.impE, values.impE),
    vol: pick(cell.vol, values.vol),
    pwt: pick(cell.pwt, values.pwt),
    ext: pick(cell.ext, values.ext),
    fcl: pick(cell.fcl, values.fcl),
    u: pick(cell.u, values.u),
    fill: pick(cell.fill, values.fill),
    lat: pick(cell.lat, values.lat),
    trcl: pick(cell.trcl, values.trcl),
    tmp: pick(cell.tmp, values.tmp),
    otherParams: pick(cell.otherParams, values.otherParams),
  };
  if (values.surfaceAppend && values.surfaceAppend.trim()) {
    const append = values.surfaceAppend.trim();
    next.surfaces = (cell.surfaces ? cell.surfaces + " " : "") + append;
  }
  return next;
}

/** 判断批量编辑是否没有任何实际写操作（含曲面追加）——用于禁用「确认」*/
export function batchEditEmpty(values: BatchCellEditValues): boolean {
  const keys: (keyof BatchCellEditValues)[] = [
    "mat", "density", "impN", "impP", "impE",
    "vol", "pwt", "ext", "fcl", "u", "fill", "lat", "trcl", "tmp", "otherParams",
    "surfaceAppend",
  ];
  return keys.every((k) => {
    const v = values[k];
    if (k === "surfaceAppend") return v === undefined || v.trim() === "";
    return v === undefined || v === "";
  });
}

/* ── 勾选状态存「栅元 num」（T1 修复）──────────────────────
 *
 * 旧实现 selectedCells 存数组下标：moveCellRow（拖拽重排）/删除行会改 cells 顺序，
 * 下标移位后点「⚡ 批量编辑」会按错位下标静默改错栅元（材料/密度/IMP/高级参数写错，
 * 无 undo）。改为存栅元 num，apply 时按 num 解析到当前行——重排/删除/同步行后仍正确。
 * 这些纯函数即 GeometryTab 的勾选状态机，DOM 交互直接调用（集成测试 pin 住）。
 */

/** 本地栅元行判别联合（与 GeometryTab 一致） */
export type LocalCellRow =
  | { kind: "cell"; cell: CellData }
  | { kind: "raw"; text: string };

/** 勾选切换（按栅元 num）：重复 toggle 取消勾选 */
export function toggleCellNum(selected: string[], num: string): string[] {
  return selected.includes(num) ? selected.filter(n => n !== num) : [...selected, num];
}

/** 按栅元 num 解析勾选集 → 实际要编辑的栅元（已删除/原始条件行自动失效） */
export function selectedCellsFromNums(cells: LocalCellRow[], selectedNums: string[]): CellData[] {
  const numSet = new Set(selectedNums);
  return cells
    .filter((r): r is { kind: "cell"; cell: CellData } => r.kind === "cell" && numSet.has(r.cell.num))
    .map(r => r.cell);
}

/** 按栅元 num 把批量值应用到匹配行（不改原数组；原始条件行原样保留） */
export function applyBatchEditToRows(cells: LocalCellRow[], selectedNums: string[], values: BatchCellEditValues): LocalCellRow[] {
  const numSet = new Set(selectedNums);
  return cells.map(r =>
    r.kind === "cell" && numSet.has(r.cell.num) ? { ...r, cell: applyBatchCellEdit(r.cell, values) } : r,
  );
}

/** 清理勾选集中已不存在的栅元 num（删除/同步行后；重排不影响，因存的是 num） */
export function pruneSelectedNums(selectedNums: string[], cells: LocalCellRow[]): string[] {
  const live = new Set(cells.filter(r => r.kind === "cell").map(r => r.cell.num));
  return selectedNums.filter(n => live.has(n));
}
