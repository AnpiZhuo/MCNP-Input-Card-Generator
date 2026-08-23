import { describe, it, expect } from "vitest";
import {
  applyBatchEditToRows, toggleCellNum, selectedCellsFromNums, pruneSelectedNums,
  type LocalCellRow,
} from "../src/utils/batchCellEdit";

/**
 * T1 回归（勾选存数组下标 → 拖拽重排/删除后下标移位静默改错栅元）。
 *
 * 修法（推荐方案 ①）：勾选状态存「栅元 num」，apply 时按 num 解析到当前行，
 * 重排/删除/同步行后仍改到原勾选栅元（而不是按旧下标错位）。
 *
 * 集成场景：勾选若干行 → 拖拽重排 → 应用批量编辑 → 断言改到的是原勾选栅元。
 */

const cell = (num: string, mat: string): LocalCellRow => ({
  kind: "cell",
  cell: {
    num, mat, density: "-1.0", surfaces: "-1", impN: "", impP: "", impE: "",
    vol: "", pwt: "", ext: "", fcl: "", u: "", fill: "", lat: "",
    trcl: "", tmp: "", otherParams: "", render: true, comment: "",
  },
});

/** 与 GeometryTab.moveCellRow 完全一致的拖拽重排逻辑 */
function moveRow(cells: LocalCellRow[], from: number, to: number): LocalCellRow[] {
  const c = [...cells];
  const [m] = c.splice(from, 1);
  c.splice(to, 0, m);
  return c;
}

describe("批量编辑勾选存栅元 num（T1：重排后仍改对栅元）", () => {
  it("勾选 → 拖拽重排 → 应用批量编辑：改到原勾选栅元而非下标错位", () => {
    let rows: LocalCellRow[] = [cell("1", "1"), cell("2", "1"), cell("3", "1")];
    // 勾选 cell 1 与 cell 3（初始位于第 0、2 行）
    let sel = toggleCellNum([], "1");
    sel = toggleCellNum(sel, "3");
    expect(sel).toEqual(["1", "3"]);
    // 拖拽重排：把 cell1 从行 0 移到行 2 → [cell2, cell3, cell1]
    rows = moveRow(rows, 0, 2);
    expect(rows.map(r => (r as { kind: "cell"; cell: { num: string } }).cell.num)).toEqual(["2", "3", "1"]);
    // 应用批量编辑（材料 → 5）
    const out = applyBatchEditToRows(rows, sel, { mat: "5" });
    // 断言：改到的是原勾选栅元 1 与 3，栅元 2 不受影响
    expect(out.find(r => r.kind === "cell" && r.cell.num === "1")!.cell.mat).toBe("5");
    expect(out.find(r => r.kind === "cell" && r.cell.num === "3")!.cell.mat).toBe("5");
    expect(out.find(r => r.kind === "cell" && r.cell.num === "2")!.cell.mat).toBe("1");
  });

  it("重排后按 num 解析勾选集仍返回原勾选栅元（selectedCellsFromNums）", () => {
    const rows = moveRow([cell("1", "1"), cell("2", "1"), cell("3", "1")], 0, 2);
    const selected = selectedCellsFromNums(rows, ["1", "3"]);
    expect(selected.map(c => c.num).sort()).toEqual(["1", "3"]);
  });

  it("删除栅元后失效的勾选 num 被清理（pruneSelectedNums）", () => {
    const rows = [cell("1", "1"), cell("3", "1")]; // cell2 已删
    expect(pruneSelectedNums(["1", "2", "3"], rows)).toEqual(["1", "3"]);
  });

  it("勾选切换：重复 toggle 取消勾选；原始条件行不计入", () => {
    expect(toggleCellNum(toggleCellNum([], "1"), "1")).toEqual([]);
    const rows: LocalCellRow[] = [cell("1", "1"), { kind: "raw", text: "#ifdef X" }];
    expect(selectedCellsFromNums(rows, ["1"])).toHaveLength(1);
  });

  it("重排后应用其它字段（IMP:N）同样改到原勾选栅元", () => {
    let rows: LocalCellRow[] = [cell("1", "1"), cell("2", "1"), cell("3", "1")];
    const sel = toggleCellNum(toggleCellNum([], "1"), "2");
    rows = moveRow(rows, 2, 0); // [cell3, cell1, cell2]
    const out = applyBatchEditToRows(rows, sel, { impN: "7" });
    expect(out.find(r => r.kind === "cell" && r.cell.num === "1")!.cell.impN).toBe("7");
    expect(out.find(r => r.kind === "cell" && r.cell.num === "2")!.cell.impN).toBe("7");
    expect(out.find(r => r.kind === "cell" && r.cell.num === "3")!.cell.impN).toBe("");
  });
});
