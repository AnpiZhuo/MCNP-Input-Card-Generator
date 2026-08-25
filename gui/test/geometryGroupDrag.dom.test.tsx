// @vitest-environment jsdom
/**
 * B 板块三项 DOM 集成测试（GeometryTab 按 U 分组显示）：
 *  - 项 8：分组默认开启 + localStorage 状态保持（键 mcnp_groupbyu_v1）
 *  - 项 11：拖拽栅元到组头 → u 更新 + 不回弹 + deck 被 patch（改 u 同时提交 deck）
 *  - 项 10：拖拽栅元到「未分组」组头 → u 被清空
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import GeometryTab from "../src/components/GeometryTab";
import { DeckProvider, useDeck, type DeckData } from "../src/utils/DeckContext";

/** 捕获 deck 当前值（断言 onDropOnGroup 是否 patch 了 deck） */
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
    // cell1/cell2 无 U（未分组）；cell3 在 U=10
    cells: [
      { kind: "cell", cell: { number: 1, material: "1", density: "-1.0", surface_expr: "-1", imp_n: "", imp_p: "", imp_e: "", vol: "", pwt: "", ext: "", fcl: "", u: "", fill: "", lat: "", trcl: "", tmp: "", other_params: "", render: true, fill_grid: "", comment: "a" } },
      { kind: "cell", cell: { number: 2, material: "1", density: "-1.0", surface_expr: "-1", imp_n: "", imp_p: "", imp_e: "", vol: "", pwt: "", ext: "", fcl: "", u: "", fill: "", lat: "", trcl: "", tmp: "", other_params: "", render: true, fill_grid: "", comment: "b" } },
      { kind: "cell", cell: { number: 3, material: "1", density: "-1.0", surface_expr: "-1", imp_n: "", imp_p: "", imp_e: "", vol: "", pwt: "", ext: "", fcl: "", u: "10", fill: "", lat: "", trcl: "", tmp: "", other_params: "", render: true, fill_grid: "", comment: "c" } },
    ],
    materials: [{ number: 5, comment: "测试材料", density: "5.0", nuclides: [], options: "", mt_card: "" }],
    sources: [], tallies: [], tally: {}, grids: {}, adv: {},
    sourceMode: "fixed", sdefFields: {}, sdefRawText: "", sourceTemplate: "free", distributions: [],
    sswFields: { surf: "", sym: "", pty: "", cel: "" },
    ssrFields: { surf: "", mode: "", cel: "", pty: "", col: "", wgt: "", tr: "", psc: "" },
    kcodeFields: {}, ksrcPoints: "", rawOverrides: {}, textMode: {},
  });
}

function SeedAndTab() {
  const { loadDeck } = useDeck();
  React.useEffect(() => { seedDeck(loadDeck); }, [loadDeck]);
  return React.createElement(GeometryTab, { pendingCellFromMaterial: undefined });
}

function renderTab() {
  const utils = render(
    React.createElement(DeckProvider, null,
      React.createElement(React.Fragment, null,
        React.createElement(Probe, null),
        React.createElement(SeedAndTab, null),
      )),
  );
  return utils;
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  localStorage.clear();
  deckRef = null;
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

/** tbody 组结构快照：header 行 → "未分组"/"U=n"，栅元行 → "cell:<num>" */
function structure(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll<HTMLElement>("tbody tr")).map((r) => {
    // 组头：含 colSpan td（组头前可能有勾选 td）
    const hdr = r.querySelector("td[colspan]");
    if (hdr) {
      const t = hdr.textContent ?? "";
      if (t.includes("未分组")) return "未分组";
      const m = t.match(/U=(\d+)/);
      if (m) return "U=" + m[1];
      return "HDR";
    }
    const num = r.querySelector("td:nth-child(2)")?.textContent?.trim();
    return "cell:" + (num ?? "?");
  });
}

function cellRow(container: HTMLElement, num: string): HTMLElement {
  const r = Array.from(container.querySelectorAll<HTMLElement>("tbody tr"))
    .find((row) => row.querySelector("td:nth-child(2)")?.textContent?.trim() === num);
  if (!r) throw new Error("未找到栅元行 " + num);
  return r;
}

function groupHeader(container: HTMLElement, label: string): HTMLElement {
  const r = Array.from(container.querySelectorAll<HTMLElement>("tbody tr"))
    .find((row) => row.querySelector("td[colspan]")?.textContent?.includes(label));
  if (!r) throw new Error("未找到组头 " + label);
  return r;
}

function groupToggle(container: HTMLElement): HTMLInputElement {
  const label = Array.from(container.querySelectorAll<HTMLElement>("label"))
    .find((l) => l.textContent?.includes("按 U 分组"));
  const input = label?.querySelector<HTMLInputElement>("input[type=checkbox]");
  if (!input) throw new Error("未找到分组 toggle");
  return input;
}

describe("项8：分组默认开启 + localStorage 状态保持", () => {
  it("默认分组视图（未分组在前、U=10 在后），localStorage 记录 true", async () => {
    const { container } = renderTab();
    await waitFor(() => {
      expect(structure(container)).toEqual(["未分组", "cell:1", "cell:2", "U=10", "cell:3"]);
    }, { timeout: 10000 });
    expect(localStorage.getItem("mcnp_groupbyu_v1")).toBe("true");
  });

  it("取消勾选 → localStorage=false；重挂载后仍保持关闭", async () => {
    const { container } = renderTab();
    await waitFor(() => {
      expect(structure(container)).toEqual(["未分组", "cell:1", "cell:2", "U=10", "cell:3"]);
    }, { timeout: 10000 });
    fireEvent.click(groupToggle(container));
    // 关闭后无组头行
    await waitFor(() => {
      const s = structure(container);
      expect(s).not.toContain("未分组");
      expect(s).not.toContain("U=10");
    });
    expect(localStorage.getItem("mcnp_groupbyu_v1")).toBe("false");
    // 重新挂载：从 localStorage 恢复为关闭
    cleanup();
    const again = renderTab();
    await waitFor(() => {
      const s = structure(again.container);
      expect(s).not.toContain("未分组");
      expect(s).toEqual(["cell:1", "cell:2", "cell:3"]);
    }, { timeout: 10000 });
  });
});

describe("项11：拖拽栅元到组头 → 改 u + 不回弹 + deck 被 patch", () => {
  it("cell1（未分组）拖到 U=10 组头 → u=10、DOM 归入 U=10 组、deck.cells 已更新", async () => {
    const { container } = renderTab();
    await waitFor(() => {
      expect(structure(container)).toEqual(["未分组", "cell:1", "cell:2", "U=10", "cell:3"]);
    }, { timeout: 10000 });

    fireEvent.mouseDown(cellRow(container, "1"), { button: 0 });
    fireEvent.mouseMove(groupHeader(container, "U=10"), { button: 0 });
    fireEvent.mouseUp(groupHeader(container, "U=10"), { button: 0 });

    // 不回弹：cell1 持续显示在 U=10 组（在 U=10 头之后、cell3 之前）
    await waitFor(() => {
      expect(structure(container)).toEqual(["未分组", "cell:2", "U=10", "cell:1", "cell:3"]);
    }, { timeout: 10000 });
    // deck 已被 patch（u=10），非仅本地 setCells
    const deckCell = deckRef?.cells.find((c) => c.kind === "cell" && (c as any).cell.number === 1) as any;
    expect(deckCell?.cell?.u).toBe("10");
  });

  it("再拖 cell3（U=10）到未分组组头 → u 清空（项10 拖拽语义）", async () => {
    const { container } = renderTab();
    await waitFor(() => {
      expect(structure(container)).toEqual(["未分组", "cell:1", "cell:2", "U=10", "cell:3"]);
    }, { timeout: 10000 });

    fireEvent.mouseDown(cellRow(container, "3"), { button: 0 });
    fireEvent.mouseMove(groupHeader(container, "未分组"), { button: 0 });
    fireEvent.mouseUp(groupHeader(container, "未分组"), { button: 0 });

    await waitFor(() => {
      expect(structure(container)).toEqual(["未分组", "cell:1", "cell:2", "cell:3"]);
    }, { timeout: 10000 });
    const deckCell = deckRef?.cells.find((c) => c.kind === "cell" && (c as any).cell.number === 3) as any;
    expect(deckCell?.cell?.u).toBe("");
  });
});
