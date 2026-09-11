// @vitest-environment jsdom
/**
 * 项9 UI：U 组头文字可编辑 → 双击内联 input → 失焦 patch({universeComments})
 * （与后端 universe_group_banner 配合：生成 INP 时每 U 组前输出 C 注释）。
 * 复用 geometryGroupDrag 的 DeckProvider + seedDeck 模式。
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import GeometryTab from "../src/components/GeometryTab";
import { DeckProvider, useDeck, type DeckData } from "../src/utils/DeckContext";

let deckRef: DeckData | null = null;

function Probe() {
  const { deck } = useDeck();
  deckRef = deck;
  return null;
}

function seedDeck(loadDeck: (d: DeckData) => void) {
  loadDeck({
    basic: { title: "", mode_n: true, mode_p: false, mode_e: false, nps: "", ctme: "", phys_fis: true },
    surfaces: "1 pz 0\n",
    tr_cards: "",
    cells: [
      { kind: "cell", cell: { number: 1, material: "1", density: "-1.0", surface_expr: "-1", imp_n: "", imp_p: "", imp_e: "", vol: "", pwt: "", ext: "", fcl: "", u: "", fill: "", lat: "", trcl: "", tmp: "", other_params: "", render: true, fill_grid: "", comment: "a" } },
      { kind: "cell", cell: { number: 2, material: "1", density: "-1.0", surface_expr: "-1", imp_n: "", imp_p: "", imp_e: "", vol: "", pwt: "", ext: "", fcl: "", u: "", fill: "", lat: "", trcl: "", tmp: "", other_params: "", render: true, fill_grid: "", comment: "b" } },
      { kind: "cell", cell: { number: 3, material: "1", density: "-1.0", surface_expr: "-1", imp_n: "", imp_p: "", imp_e: "", vol: "", pwt: "", ext: "", fcl: "", u: "10", fill: "", lat: "", trcl: "", tmp: "", other_params: "", render: true, fill_grid: "", comment: "c" } },
    ],
    materials: [],
    sources: [], tallies: [], tally: {}, grids: {}, adv: {},
    sourceTemplate: "free", rawOverrides: {}, textMode: {},
    universeComments: {},
  });
}

function SeedAndTab() {
  const { loadDeck } = useDeck();
  React.useEffect(() => { seedDeck(loadDeck); }, [loadDeck]);
  return React.createElement(GeometryTab, { pendingCellFromMaterial: undefined });
}

function renderTab() {
  return render(
    React.createElement(DeckProvider, null,
      React.createElement(React.Fragment, null,
        React.createElement(Probe, null),
        React.createElement(SeedAndTab, null),
      )),
  );
}

function groupHeader(container: HTMLElement, label: string): HTMLElement {
  const r = Array.from(container.querySelectorAll<HTMLElement>("tbody tr"))
    .find((row) => row.querySelector("td[colspan]")?.textContent?.includes(label));
  if (!r) throw new Error("未找到组头 " + label);
  return r;
}

beforeEach(() => {
  localStorage.clear();
  deckRef = null;
  vi.stubGlobal("fetch", vi.fn(async () => ({ json: async () => ({ status: "ok", found: true }) })));
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("项9：U 组头文字双击内联编辑", () => {
  it("双击组头 → 内联 input；输入 + 失焦 → deck.universeComments['10'] 更新 + 组头文案并入", async () => {
    const { container } = renderTab();
    await waitFor(() => {
      expect(container.textContent).toContain("U=10");
    }, { timeout: 10000 });

    const hdr = groupHeader(container, "U=10");
    expect(hdr.textContent).not.toContain("「");
    fireEvent.doubleClick(hdr.querySelector("td[colspan]")!);
    const input = hdr.querySelector<HTMLInputElement>("input[data-testid='group-comment-10']");
    expect(input).toBeTruthy();
    fireEvent.change(input!, { target: { value: "燃料棒" } });
    fireEvent.blur(input!);
    await waitFor(() => {
      expect(deckRef?.universeComments?.["10"]).toBe("燃料棒");
      expect(groupHeader(container, "U=10").textContent).toContain("「燃料棒」");
    }, { timeout: 10000 });
  });

  it("清空输入 → universeComments 删除该键；未分组组头不可编辑", async () => {
    const { container } = renderTab();
    await waitFor(() => {
      expect(container.textContent).toContain("未分组");
    }, { timeout: 10000 });
    // 预置注释后编辑清空
    const hdr = groupHeader(container, "未分组");
    expect(hdr.textContent).not.toContain("编辑");
    // 编辑 U=10 并清空
    const u10 = groupHeader(container, "U=10");
    fireEvent.doubleClick(u10.querySelector("td[colspan]")!);
    const input = u10.querySelector<HTMLInputElement>("input[data-testid^='group-comment-']");
    expect(input).toBeTruthy();
    fireEvent.change(input!, { target: { value: "待删除" } });
    fireEvent.blur(input!);
    await waitFor(() => {
      expect(deckRef?.universeComments?.["10"]).toBe("待删除");
    });
    const hdr2 = groupHeader(container, "待删除");
    fireEvent.doubleClick(hdr2.querySelector("td[colspan]")!);
    const input2 = hdr2.querySelector<HTMLInputElement>("input[data-testid^='group-comment-']");
    fireEvent.change(input2!, { target: { value: "" } });
    fireEvent.blur(input2!);
    await waitFor(() => {
      expect(deckRef?.universeComments?.["10"]).toBeUndefined();
    });
  });
});
