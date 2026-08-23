import { describe, it, expect } from "vitest";
import { applyExistingExprPatch } from "../src/utils/quickCell";

/**
 * P0 修复的纯函数 seam：Preview3DWindow 快捷建栅元时应用 existingExprPatch，
 * 让被侵占栅元表达式与主窗口一致（`...#新`），避免预览侧旧快照报陈旧重合。
 */

const cells: { num: string; mat: string; surfaces: string }[] = [
  { num: "1", mat: "0", surfaces: "1 -2" },
  { num: "2", mat: "0", surfaces: "-1" },
  { num: "3", mat: "1", surfaces: "2" },
];

describe("applyExistingExprPatch（P0：预览窗口快捷建栅元补集决策）", () => {
  it("num 命中 patch 的栅元 surfaces 被替换（真空栅元 # 新），未命中不变", () => {
    const out = applyExistingExprPatch(cells, [{ num: "2", surfaces: "-1 #4" }]);
    expect(out[1].surfaces).toBe("-1 #4");
    expect(out[0].surfaces).toBe("1 -2");
    expect(out[2].surfaces).toBe("2");
  });

  it("多个 patch 一次性应用，且不改原数组", () => {
    const out = applyExistingExprPatch(cells, [
      { num: "1", surfaces: "1 -2 #4" },
      { num: "3", surfaces: "2 #4" },
    ]);
    expect(out[0].surfaces).toBe("1 -2 #4");
    expect(out[2].surfaces).toBe("2 #4");
    expect(cells[0].surfaces).toBe("1 -2"); // 原数组不变
  });

  it("空 patch 原样返回（同引用）；无命中时元素不变", () => {
    expect(applyExistingExprPatch(cells, [])).toBe(cells);
    const out = applyExistingExprPatch(cells, [{ num: "99", surfaces: "x" }]);
    expect(out[0]).toBe(cells[0]); // 未命中元素同引用
  });

  it("num 数字/字符串混用也能命中", () => {
    const mixed: { num: string | number; surfaces: string }[] = [{ num: 2, surfaces: "-1" }];
    const out = applyExistingExprPatch(mixed, [{ num: "2", surfaces: "-1 #4" }]);
    expect(out[0].surfaces).toBe("-1 #4");
  });
});
