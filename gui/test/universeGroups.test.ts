/**
 * universeGroups 纯函数测试：按 U 分组 + 组头文案 + 拖拽判定（落组头改 u / 落普通行重排）。
 * 项 10：无 U 的 cell 进「未分组」兜底组（哨兵 UNGROUPED_U=-1，排最前）；拖到未分组组头=清空 u。
 */
import { describe, expect, it } from "vitest";
import { applyRegroupToRows, groupByUniverse, groupHeaderLabel, isUngroupedU, resolveDrop, UNGROUPED_U } from "../src/utils/universeGroups";
import type { LocalCellRow } from "../src/utils/cellBridge";

const mkCell = (u: string, num = "1"): LocalCellRow => ({
  kind: "cell",
  cell: {
    num, mat: "0", density: "", surfaces: "", impN: "", impP: "", impE: "",
    vol: "", pwt: "", ext: "", fcl: "", u, fill: "", lat: "", trcl: "",
    tmp: "", otherParams: "", render: true, fill_grid: "", comment: "",
  },
});

describe("groupByUniverse", () => {
  it("按 u 数值升序分组，raw 行不进组，indices 记录原始下标", () => {
    const rows: LocalCellRow[] = [
      mkCell("3", "1"),
      { kind: "raw", text: "#ifdef X" },
      mkCell("1", "2"),
      mkCell("3", "3"),
      mkCell("2", "4"),
    ];
    const groups = groupByUniverse(rows);
    expect(groups.map((g) => g.u)).toEqual([1, 2, 3]);
    expect(groups[0].count).toBe(1);
    expect(groups[0].indices).toEqual([2]);
    expect(groups[0].start).toBe(2);
    expect(groups[2].count).toBe(2);
    expect(groups[2].indices).toEqual([0, 3]);
    // raw 行不进组
    expect(groups.every((g) => g.rows.every((r) => r.kind === "cell"))).toBe(true);
  });

  it("项10：空 u / 空白 u / 非数值 u 进「未分组」兜底组（哨兵 UNGROUPED_U=-1，排最前）", () => {
    const rows: LocalCellRow[] = [
      mkCell("", "1"),
      mkCell("  ", "2"),
      mkCell("abc", "3"),
      mkCell("2", "4"),
      mkCell("1", "5"),
    ];
    const groups = groupByUniverse(rows);
    expect(groups.map((g) => g.u)).toEqual([UNGROUPED_U, 1, 2]);
    const ug = groups[0];
    expect(ug.count).toBe(3);
    expect(ug.indices).toEqual([0, 1, 2]);
    expect(ug.rows.map((r) => (r as { kind: "cell"; cell: { num: string } }).cell.num)).toEqual(["1", "2", "3"]);
  });

  it("全部有效 u → 无「未分组」组（兜底组不空渲染）", () => {
    const groups = groupByUniverse([mkCell("1"), mkCell("2", "2")]);
    expect(groups.map((g) => g.u)).toEqual([1, 2]);
  });

  it("空列表 → 空分组", () => {
    expect(groupByUniverse([])).toEqual([]);
  });
});

describe("groupHeaderLabel", () => {
  it("U=n · N 栅元", () => {
    expect(groupHeaderLabel(3, 5)).toBe("U=3 · 5 栅元");
  });
  it("项10：未分组 →「未分组 · N 栅元」", () => {
    expect(groupHeaderLabel(UNGROUPED_U, 4)).toBe("未分组 · 4 栅元");
  });
  it("项9：可选 comment → 追加「· 「text」」", () => {
    expect(groupHeaderLabel(3, 5, "燃料棒")).toBe("U=3 · 5 栅元 · 「燃料棒」");
    expect(groupHeaderLabel(3, 5, "  ")).toBe("U=3 · 5 栅元"); // 空白 comment 不追加
    expect(groupHeaderLabel(UNGROUPED_U, 4, "不应显示")).toBe("未分组 · 4 栅元");
  });
});

describe("isUngroupedU", () => {
  it("UNGROUPED_U 判定为未分组，真实宇宙号不是", () => {
    expect(isUngroupedU(UNGROUPED_U)).toBe(true);
    expect(isUngroupedU(0)).toBe(false);
    expect(isUngroupedU(10)).toBe(false);
  });
});

describe("applyRegroupToRows（应用归组结果，不可变）", () => {
  it("把 from 行 u 设为目标值，其余行不变", () => {
    const rows = [mkCell("", "1"), mkCell("2", "2"), mkCell("", "3")];
    const next = applyRegroupToRows(rows, 0, 10);
    expect(next[0].kind).toBe("cell");
    if (next[0].kind === "cell") expect(next[0].cell.u).toBe("10");
    expect(next[1]).toBe(rows[1]); // 未受影响行保持原引用（不可变）
    expect(next[2]).toBe(rows[2]);
    expect(rows[0]).toBe(rows[0]); // 原数组不变
  });

  it("项10：UNGROUPED_U → 清空 u；非 cell 行（raw）不受影响", () => {
    const rows: LocalCellRow[] = [mkCell("10", "1"), { kind: "raw", text: "#ifdef X" }, mkCell("7", "3")];
    const next = applyRegroupToRows(rows, 0, UNGROUPED_U);
    if (next[0].kind === "cell") expect(next[0].cell.u).toBe("");
    expect(next[1]).toEqual({ kind: "raw", text: "#ifdef X" });
    if (next[2].kind === "cell") expect(next[2].cell.u).toBe("7");
  });
});

describe("resolveDrop（拖拽判定）", () => {
  it("落组头 → regroup 改 u", () => {
    expect(resolveDrop(2, { kind: "group", u: 5 })).toEqual({ kind: "regroup", from: 2, u: 5 });
  });
  it("项10：落未分组组头 → regroup 携带 UNGROUPED_U（清空 u 语义）", () => {
    expect(resolveDrop(2, { kind: "group", u: UNGROUPED_U })).toEqual({ kind: "regroup", from: 2, u: UNGROUPED_U });
  });
  it("落普通行 → reorder 行重排", () => {
    expect(resolveDrop(2, { kind: "cell", to: 7 })).toEqual({ kind: "reorder", from: 2, to: 7 });
  });
});
