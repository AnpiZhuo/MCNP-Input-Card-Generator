/**
 * universeGroups 纯函数测试：按 U 分组 + 组头文案 + 拖拽判定（落组头改 u / 落普通行重排）。
 */
import { describe, expect, it } from "vitest";
import { groupByUniverse, groupHeaderLabel, resolveDrop } from "../src/utils/universeGroups";
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

  it("空 u / 非数值 u 不进组", () => {
    const rows: LocalCellRow[] = [mkCell(""), mkCell("abc"), mkCell("2", "5")];
    expect(groupByUniverse(rows).map((g) => g.u)).toEqual([2]);
  });

  it("空列表 → 空分组", () => {
    expect(groupByUniverse([])).toEqual([]);
  });
});

describe("groupHeaderLabel", () => {
  it("U=n · N 栅元", () => {
    expect(groupHeaderLabel(3, 5)).toBe("U=3 · 5 栅元");
  });
});

describe("resolveDrop（拖拽判定）", () => {
  it("落组头 → regroup 改 u", () => {
    expect(resolveDrop(2, { kind: "group", u: 5 })).toEqual({ kind: "regroup", from: 2, u: 5 });
  });
  it("落普通行 → reorder 行重排", () => {
    expect(resolveDrop(2, { kind: "cell", to: 7 })).toEqual({ kind: "reorder", from: 2, to: 7 });
  });
});
