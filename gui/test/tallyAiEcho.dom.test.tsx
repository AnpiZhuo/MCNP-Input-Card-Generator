// @vitest-environment jsdom
/**
 * 回归：AI 接入（MCP /workspace）回显不得清空计数卡。
 *
 * 用户症状（2026-09-17）：打包版「计数卡界面手动改动后都会变回初始状态」。
 * 机制：`useAiWorkspace` 每 2s GET /workspace，revision 前进就 `loadDeck` 整份覆盖工作区；
 * 而假后端此前把前端推上来的 `deck.tallies` 丢了（后端 bug，已修），回显空列表
 * ⇒ `useDeckSynced` 整份采纳 ⇒ 计数卡被清空。
 *
 * 本测试用「照真实 PUT/GET 契约的假后端」跑完整回路：用户改动必须活过回显周期。
 * 配套后端回归：tests/unit/test_mcp_workspace_tallies_roundtrip.py
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render } from "@testing-library/react";
import TallyTab from "../src/components/TallyTab";
import { DeckProvider, useDeck } from "../src/utils/DeckContext";
import { useAiWorkspace } from "../src/hooks/useAiWorkspace";

/** 照真实契约的假 MCP 工作区：PUT 存 deck / GET 回显 deck + revision */
const backend = {
  revision: 0,
  deck: {
    basic: {}, surfaces: "", tr_cards: "", cells: [], materials: [], sources: [],
    tallies: [{ type: "F4", number: 4, particle: "n", params: "1", multiplier: "", enableEn: false, enableTn: false }],
    tally: {}, grids: {}, adv: {}, rawOverrides: {}, textMode: {},
  } as any,
};

function Harness() {
  const { deck, loadDeck } = useDeck();
  useAiWorkspace(deck, (aiDeck: any) => loadDeck({ ...deck, ...aiDeck }));
  return React.createElement(TallyTab, null);
}

/** 灌入用户已有工作区（编号 4） */
function Seed() {
  const { loadDeck } = useDeck();
  React.useEffect(() => { loadDeck(JSON.parse(JSON.stringify(backend.deck))); }, []);
  return null;
}

beforeEach(() => {
  vi.useFakeTimers();
  backend.revision = 0;
  backend.deck = {
    basic: {}, surfaces: "", tr_cards: "", cells: [], materials: [], sources: [],
    tallies: [{ type: "F4", number: 4, particle: "n", params: "1", multiplier: "", enableEn: false, enableTn: false }],
    tally: {}, grids: {}, adv: {}, rawOverrides: {}, textMode: {},
  };
  (globalThis as any).fetch = vi.fn(async (url: string, init?: any) => {
    if (String(url).includes("/workspace")) {
      if (init?.method === "PUT") {
        backend.revision += 1;
        backend.deck = JSON.parse(init.body).deck;   // 真实后端：存下前端推上来的 deck
        // TEMP-REVERT-a4f2：模拟修复前后端把顶层 tallies 丢掉的行为
        if ((globalThis as any).__DROP_TALLIES__ === true) backend.deck = { ...backend.deck, tallies: [] };
        return { ok: true, json: async () => ({ ok: true, revision: backend.revision }) };
      }
      return { ok: true, json: async () => ({ revision: backend.revision, deck: backend.deck }) };
    }
    return { ok: false, json: async () => ({}) };
  });
  localStorage.clear();
});

afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); });

describe("计数卡 vs AI 回显", () => {
  it("手动改编号后，多轮回显仍保持用户输入（不被盖回初始状态）", async () => {
    render(React.createElement(DeckProvider, null,
      React.createElement(Seed, null), React.createElement(Harness, null)));

    const inputs = () => Array.from(document.querySelectorAll("table input.form-input")) as HTMLInputElement[];
    const tick = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

    expect(inputs()[0].value).toBe("4");
    await tick(400);                       // 初次同步（防抖 300ms）推给后端
    fireEvent.change(inputs()[0], { target: { value: "14" } });
    expect(inputs()[0].value).toBe("14");

    await tick(6000);                      // 跨 3 轮 2s 回显
    expect(inputs()[0].value, "回显把计数卡盖回初始状态了").toBe("14");
    expect((backend.deck.tallies as any[]).map(t => t.number)).toEqual([14]);

    fireEvent.change(inputs()[0], { target: { value: "24" } });
    await tick(6000);
    expect(inputs()[0].value, "第二次数改动也被盖回").toBe("24");
  });
});
