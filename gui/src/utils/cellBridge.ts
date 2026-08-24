import type { CellData } from "../components/CellEditDialog";

/**
 * cellBridge — 栅元行双向桥接纯函数（GeometryTab local 状态 ↔ deck.cells 单一权威）。
 *
 * 命名约定：local 侧其余字段 camelCase（num/mat/surfaces/impN...），deck 侧其余字段
 * snake_case（number/material/surface_expr/imp_n...）；`fill_grid` 两侧均保持 snake_case
 * （后端契约固定，前后端统一，见格阵 fill 阶段1）。
 *
 * 新增/修改字段必须 local↔deck 两处同步 + 类型三处同步（CellEditDialog / DeckContext / 本文件）。
 */

/** GeometryTab 本地栅元行：真正的栅元(camelCase) 或原样条件行 */
export type LocalCellRow =
  | { kind: "cell"; cell: CellData }
  | { kind: "raw"; text: string };

/** local 栅元行 → deck cell 对象（snake_case，/api/generate 请求契约） */
export function localToDeckCells(cells: LocalCellRow[]): any[] {
  return cells.map(c => c.kind === "raw"
    ? { kind: "raw", text: c.text }
    : { kind: "cell", cell: {
        number: parseInt(c.cell.num) || 0,
        material: c.cell.mat,
        density: c.cell.density,
        surface_expr: c.cell.surfaces,
        imp_n: c.cell.impN,
        imp_p: c.cell.impP,
        imp_e: c.cell.impE,
        vol: c.cell.vol,
        pwt: c.cell.pwt,
        ext: c.cell.ext,
        fcl: c.cell.fcl,
        u: c.cell.u,
        fill: c.cell.fill,
        lat: c.cell.lat,
        trcl: c.cell.trcl,
        tmp: c.cell.tmp,
        other_params: c.cell.otherParams,
        render: c.cell.render,
        fill_grid: c.cell.fill_grid,
        comment: c.cell.comment,
      } });
}

/** deck cell（snake_case，parse/text-to-section/STEP 导入产物）→ local 栅元行（camelCase） */
export function deckToLocalCells(cells: any[]): LocalCellRow[] {
  return (cells || []).map((c: any) => {
    if (c?.kind === "raw") return { kind: "raw" as const, text: c.text };
    // CellRow（嵌套 cell）或旧平铺格式（STEP 导入）都兼容
    const cell = c?.kind === "cell" ? c.cell : c;
    return { kind: "cell" as const, cell: {
      num: String(cell?.number ?? cell?.num ?? ""),
      mat: cell?.material ?? cell?.mat ?? "",
      density: cell?.density ?? "",
      surfaces: cell?.surface_expr ?? cell?.surfaces ?? "",
      impN: cell?.imp_n ?? cell?.impN ?? "",
      impP: cell?.imp_p ?? cell?.impP ?? "",
      impE: cell?.imp_e ?? cell?.impE ?? "",
      vol: cell?.vol ?? "",
      pwt: cell?.pwt ?? "",
      ext: cell?.ext ?? "",
      fcl: cell?.fcl ?? "",
      u: cell?.u ?? "",
      fill: cell?.fill ?? "",
      lat: cell?.lat ?? "",
      trcl: cell?.trcl ?? "",
      tmp: cell?.tmp ?? "",
      otherParams: cell?.other_params ?? cell?.otherParams ?? "",
      render: cell?.render !== false,
      fill_grid: cell?.fill_grid ?? "",
      comment: cell?.comment ?? "",
    } };
  });
}
