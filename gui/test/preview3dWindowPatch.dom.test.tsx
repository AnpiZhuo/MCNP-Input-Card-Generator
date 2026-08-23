// @vitest-environment jsdom
/**
 * P0 用户实测：3D 预览窗口内快捷建栅元 + 补集决策后，真空栅元仍显示重合；
 * 关闭重开预览才正常。根因 = Preview3DWindow.handleQuickCellGenerate 只 append
 * 新栅元、丢掉 result.existingExprPatch（被侵占栅元表达式没改成 `...#新`）→ 预览侧
 * 旧快照 POST /api/check-overlap 返回旧重合（真空只是最常见受害者）。
 *
 * 修法：追加新栅元之前先应用 existingExprPatch（照 GeometryTab.tsx:211-216 主窗口逻辑）。
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render } from "@testing-library/react";
import Preview3DWindow from "../src/components/Preview3DWindow";

/** 捕获 Preview3D 收到的 props（deckCells 变化据此断言） */
let captured: any = null;
vi.mock("../src/components/Preview3D", () => ({
  __esModule: true,
  default: (props: any) => {
    captured = props;
    return React.createElement("div", { "data-testid": "mock-preview3d" });
  },
}));

let emitted: any[] = [];
vi.mock("../src/utils/windows", () => ({
  readPreview3DData: () => ({
    cells: [
      { num: "1", mat: "0", surfaces: "1 -2" },
      { num: "2", mat: "0", surfaces: "-1" },
      { num: "3", mat: "1", surfaces: "2" },
    ],
    surfaces: "1 pz 0\n",
    trCards: "",
    materials: [],
  }),
  closeCurrentWindow: () => Promise.resolve(true),
  clearStlSession: () => {},
  emitQuickCellGenerate: (result: any) => { emitted.push(result); },
}));

beforeEach(() => { captured = null; emitted = []; });
afterEach(() => { cleanup(); captured = null; emitted = []; });

describe("P0：Preview3DWindow 快捷建栅元应用 existingExprPatch", () => {
  it("收到带 existingExprPatch 的 quickCellGenerate → deckCells 命中 patch 的栅元 surfaces 被替换后再追加新栅元", async () => {
    render(React.createElement(Preview3DWindow));
    expect(captured).toBeTruthy();
    // 触发快捷建栅元 + 补集决策（existing_hole：被侵占真空栅元 2 → 表达式追加 #4）
    const result = {
      surfacesText: "4 pz 5\n",
      trCardsText: "",
      cells: [{ num: "4", mat: "0", surfaces: "-4", comment: "new" }],
      existingExprPatch: [{ num: "2", surfaces: "-1 #4" }],
      overlapHandled: true,
    };
    await act(async () => { captured.onQuickCellGenerate(result); });
    // 断言：真空栅元 2 的 surfaces 已改为带 #4（与主窗口一致），其余不变，新栅元 4 追加
    const cells = captured.cells as { num: string; surfaces: string }[];
    expect(cells.find(c => c.num === "2")!.surfaces).toBe("-1 #4");
    expect(cells.find(c => c.num === "1")!.surfaces).toBe("1 -2");
    expect(cells.find(c => c.num === "3")!.surfaces).toBe("2");
    expect(cells.find(c => c.num === "4")!.surfaces).toBe("-4");
    // 回写主窗口的 emitQuickCellGenerate 仍带完整 result
    await act(async () => {});
    expect(emitted.length).toBe(1);
  });
});
