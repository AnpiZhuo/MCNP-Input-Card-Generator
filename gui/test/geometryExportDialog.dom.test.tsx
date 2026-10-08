// @vitest-environment jsdom
/**
 * 几何页「导出 STEP」入口的 DOM 测试（用户 2026-10-08 反馈驱动）。
 *
 * 用户原话：「这三个键不要出现在这个页面」—— 指几何页工具栏那一行里多出来的
 * 「上轴 Z（不旋转）」下拉、「原点：按原本建模」下拉、「👁 预览导出方向」按钮。
 *
 * 锁死的契约：
 *   1. 工具栏那一行**不再**出现上轴/原点/方向预览三个键（只留「📐 导出 STEP」）；
 *   2. 点「📐 导出 STEP」弹出对话框，三个键（上轴 / 原点 / 预览方向）都在**对话框里**；
 *   3. 该对话框与导入侧共用同一份持久化约定（localStorage 三键）。
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import GeometryTab from "../src/components/GeometryTab";
import { DeckProvider, useDeck, type DeckData } from "../src/utils/DeckContext";

afterEach(() => cleanup());
beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  // FreeCAD 检测等网络请求一律给"没有"的答复，测试只关心界面结构
  vi.stubGlobal("fetch", vi.fn(async () => ({ json: async () => ({ status: "ok" }) })) as any);
});

function seedDeck(loadDeck: (d: DeckData) => void) {
  loadDeck({
    basic: { title: "", mode_n: true, mode_p: false, mode_e: false, nps: "", ctme: "", phys_fis: true },
    surfaces: "1 pz 0\n",
    tr_cards: "",
    cells: [{ kind: "cell", cell: { number: 1, material: "1", density: "-1.0", surface_expr: "-1", imp_n: "", imp_p: "", imp_e: "", vol: "", pwt: "", ext: "", fcl: "", u: "", fill: "", lat: "", trcl: "", tmp: "", other_params: "", render: true, fill_grid: "", comment: "" } }],
    materials: [{ number: 1, comment: "M1", density: "1.0", nuclides: [], options: "", mt_card: "" }],
    sources: [], tallies: [], tally: {}, grids: {}, adv: {},
    sourceTemplate: "free", rawOverrides: {}, textMode: {},
  });
}

function Seed() {
  const { loadDeck } = useDeck();
  React.useEffect(() => { seedDeck(loadDeck); }, [loadDeck]);
  return React.createElement(GeometryTab, { pendingCellFromMaterial: undefined });
}

const mount = () => render(React.createElement(DeckProvider, null, React.createElement(Seed)));

const UP_AXIS_OPT = /Y 朝上 —— SolidWorks/;
const ORIGIN_OPT = /按原本建模（不平移/;
const PREVIEW_BTN = /预览方向（看导出后的样子）/;

describe("几何页 · 导出 STEP 入口", () => {
  it("★工具栏那一行不再出现上轴 / 原点 / 方向预览三个键", () => {
    mount();
    expect(screen.queryByText(UP_AXIS_OPT)).toBeNull();
    expect(screen.queryByText(ORIGIN_OPT)).toBeNull();
    expect(screen.queryByText(PREVIEW_BTN)).toBeNull();
    // 导出入口本身还在
    expect(screen.getByText(/导出 STEP/)).toBeTruthy();
  });

  it("★点「📐 导出 STEP」⇒ 三个键出现在对话框里", () => {
    mount();
    fireEvent.click(screen.getByText(/导出 STEP/));
    expect(screen.getByText(UP_AXIS_OPT)).toBeTruthy();
    expect(screen.getByText(ORIGIN_OPT)).toBeTruthy();
    expect(screen.getByText(PREVIEW_BTN)).toBeTruthy();
    expect(screen.getByText(/导出方向预览|预览方向/)).toBeTruthy();
  });

  it("对话框里的选择写进 localStorage（与导入侧共用同一份约定）", () => {
    mount();
    fireEvent.click(screen.getByText(/导出 STEP/));
    const selects = Array.from(document.querySelectorAll("select"));
    const upSel = selects.find((s) => Array.from(s.options).some((o) => o.value === "Y/0")) as HTMLSelectElement;
    expect(upSel).toBeTruthy();
    fireEvent.change(upSel, { target: { value: "Y/0" } });
    expect(localStorage.getItem("mcnp_cadUp_v1")).toBe("Y");
    expect(localStorage.getItem("mcnp_cadAz_v1")).toBe("0");
  });
});
