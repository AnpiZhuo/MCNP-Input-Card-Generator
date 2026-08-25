// @vitest-environment jsdom
/**
 * T1 集成测试（DOM）：栅元列表批量编辑 —— 勾选若干行 → 拖拽重排 → 应用批量编辑，
 * 断言改到的是「原勾选栅元」而不是「重排后的下标错位行」。
 *
 * 旧 bug：selectedCells 存数组下标；moveCellRow（拖拽重排）改 cells 顺序后，
 * 点「⚡ 批量编辑」按旧下标静默改错栅元（无 undo）。修复：勾选存栅元 num，
 * apply 按 num 解析到当前行。
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor, within } from "@testing-library/react";
import GeometryTab from "../src/components/GeometryTab";
import { DeckProvider, useDeck, type DeckData } from "../src/utils/DeckContext";

function seedDeck(loadDeck: (d: DeckData) => void) {
  loadDeck({
    basic: { title: "", mode_n: true, mode_p: false, mode_e: false, nps: "", ctme: "", phys_fis: true },
    surfaces: "1 pz 0\n",
    tr_cards: "",
    cells: [
      { kind: "cell", cell: { number: 1, material: "1", density: "-1.0", surface_expr: "-1", imp_n: "", imp_p: "", imp_e: "", vol: "", pwt: "", ext: "", fcl: "", u: "", fill: "", lat: "", trcl: "", tmp: "", other_params: "", render: true, comment: "a" } },
      { kind: "cell", cell: { number: 2, material: "1", density: "-1.0", surface_expr: "-1", imp_n: "", imp_p: "", imp_e: "", vol: "", pwt: "", ext: "", fcl: "", u: "", fill: "", lat: "", trcl: "", tmp: "", other_params: "", render: true, comment: "b" } },
      { kind: "cell", cell: { number: 3, material: "1", density: "-1.0", surface_expr: "-1", imp_n: "", imp_p: "", imp_e: "", vol: "", pwt: "", ext: "", fcl: "", u: "", fill: "", lat: "", trcl: "", tmp: "", other_params: "", render: true, comment: "c" } },
    ],
    materials: [{ number: 5, comment: "测试材料", density: "5.0", nuclides: [], options: "", mt_card: "" }],
    sources: [], tallies: [], tally: {}, grids: {}, adv: {},
    sourceMode: "fixed", sdefFields: {}, sdefRawText: "", sourceTemplate: "free", distributions: [],
    sswFields: { surf: "", sym: "", pty: "", cel: "" },
    ssrFields: { surf: "", mode: "", cel: "", pty: "", col: "", wgt: "", tr: "", psc: "" },
    kcodeFields: {}, ksrcPoints: "", rawOverrides: {}, textMode: {},
  });
}

function SeedAndTab({ onLoad }: { onLoad?: (load: (d: DeckData) => void) => void }) {
  const { loadDeck } = useDeck();
  React.useEffect(() => { seedDeck(loadDeck); }, [loadDeck]);
  return React.createElement(GeometryTab, { pendingCellFromMaterial: undefined });
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  // 项 8：分组默认开启（localStorage mcnp_groupbyu_v1 初始 true）——本测试验证批量编辑×拖拽重排，
  // 显式关闭分组，保持「扁平行 = 每个栅元一行」的既有行结构断言（组头行会额外占一行）。
  localStorage.clear();
  localStorage.setItem("mcnp_groupbyu_v1", "false");
  fetchMock = vi.fn(async (url: unknown, opts: unknown) => {
    const u = String(url);
    if (u.includes("/api/check-freecad")) return { json: async () => ({ status: "ok", found: true }) };
    return { json: async () => ({ status: "error", message: "未 mock: " + u }) };
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

/** tbody 里每行的勾选框（索引 0..n-1 对应渲染顺序） */
function rowCheckboxes(container: HTMLElement): HTMLInputElement[] {
  return Array.from(container.querySelectorAll<HTMLInputElement>("tbody input[type=checkbox]"));
}

/** 按栅元 num（第 2 列）读取该行材料号（mat-cell-btn 文本）；只按 num 列匹配，避免撞上材料值 */
function matOf(container: HTMLElement, num: string): string {
  const rows = Array.from(container.querySelectorAll<HTMLElement>("tbody tr"));
  const row = rows.find(r => r.querySelector("td:nth-child(2)")?.textContent?.trim() === num);
  const btn = row?.querySelector<HTMLElement>(".mat-cell-btn");
  return btn?.textContent?.trim() ?? "";
}

describe("栅元列表批量编辑 × 拖拽重排（T1 集成）", () => {
  it("勾选 cell1+cell3 → 重排 cell1 移到底 → 批量编辑改材料 → 改到原勾选栅元", async () => {
    const { container } = render(
      React.createElement(DeckProvider, null, React.createElement(SeedAndTab, null)),
    );
    // 等待 deck.cells 同步进本地栅元表（3 行）
    await waitFor(() => {
      expect(container.querySelectorAll("tbody tr").length).toBe(3);
    }, { timeout: 3000 });

    // 勾选 cell1（行0）与 cell3（行2）
    const boxes = rowCheckboxes(container);
    fireEvent.click(boxes[0]);
    fireEvent.click(boxes[2]);

    // 拖拽重排：行0（cell1）拖到行2
    const rowsBefore = Array.from(container.querySelectorAll<HTMLElement>("tbody tr"));
    fireEvent.mouseDown(rowsBefore[0], { button: 0 });
    fireEvent.mouseMove(rowsBefore[2], { button: 0 });
    fireEvent.mouseUp(rowsBefore[2], { button: 0 });
    // 重排后顺序应为 cell2, cell3, cell1（第 2 列是栅元号）
    await waitFor(() => {
      const nums = Array.from(container.querySelectorAll<HTMLElement>("tbody tr td:nth-child(2)"))
        .map(td => td.textContent?.trim());
      expect(nums).toEqual(["2", "3", "1"]);
    });

    // 点「⚡ 批量编辑」→ 弹窗 → 选材料 5 → 确认
    fireEvent.click(screenGetBatchButton(container));
    await waitFor(() => expect(document.body.textContent).toContain("批量编辑栅元（已勾选 2 个）"));
    const matSelect = Array.from(document.body.querySelectorAll<HTMLSelectElement>("select"))
      .find(s => Array.from(s.options).some(o => o.value === "5"));
    if (!matSelect) throw new Error("批量编辑弹窗未找到材料下拉（含 5 选项）");
    fireEvent.change(matSelect, { target: { value: "5" } });
    // 填材料后「确认」应可用
    await waitFor(() => {
      const btn = within(document.body).getByRole("button", { name: "确认" }) as HTMLButtonElement;
      expect(btn.disabled).toBe(false);
    });
    fireEvent.click(within(document.body).getByRole("button", { name: "确认" }));
    // 应用后弹窗应关闭
    await waitFor(() => expect(document.body.textContent).not.toContain("批量编辑栅元"));

    // 断言：改到的是原勾选栅元 1 与 3；栅元 2 不受影响
    await waitFor(() => {
      expect(matOf(container, "1")).toBe("5");
      expect(matOf(container, "3")).toBe("5");
      expect(matOf(container, "2")).toBe("1");
    });
  });
});

/** ⚡ 批量编辑按钮（class btn btn-primary btn-xs，文本含「批量编辑」） */
function screenGetBatchButton(container: HTMLElement): HTMLElement {
  const btn = Array.from(container.querySelectorAll<HTMLElement>("button"))
    .find(b => b.textContent?.includes("批量编辑"));
  if (!btn) throw new Error("未找到批量编辑按钮");
  return btn;
}
