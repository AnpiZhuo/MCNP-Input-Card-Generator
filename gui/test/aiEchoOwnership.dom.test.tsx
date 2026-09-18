// @vitest-environment jsdom
/**
 * useAiWorkspace 两条不变量（2026-09-17「改动变回初始状态」的根因防线）：
 *  ① 只回显「自己写上去的」工作区 —— writer 不是本实例时一律不采纳（多实例隔离）；
 *  ② 回显按 getLatestDeck() 的最新 deck 合并 —— 不用渲染时闭包快照（不复活旧/已删内容）。
 *
 * 多实例场景：打包版 + dev 版同时开着，两个前端共用本机 8100 的同一份工作区；
 * 没有 ① 时，A 的编辑会把 B 的界面整份覆盖，B 上表现为"我改的全变回初始状态"且无报错。
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render } from "@testing-library/react";
import { useAiWorkspace } from "../src/hooks/useAiWorkspace";
import { CLIENT_ID } from "../src/utils/aiWorkspace";

/** 假工作区后端：revision + writer + deck */
const ws = { revision: 3, writer: "other-app-xyz", deck: { cells: [], materials: [], tallies: [] } as any };
/** 本实例「最新 deck」（模拟 App.tsx 的 deckRef） */
let latestDeck: any = { cells: [], materials: [], tallies: [{ number: 14 }], adv: { a: 1 } };
let applied: any[] = [];

function Harness() {
  // 故意把「参数 deck」传成过期快照：若 hook 用闭包快照，就会把 cells 复活
  const staleDeck = { cells: [{ number: 1 }], materials: [], tallies: [{ number: 99 }] };
  useAiWorkspace(staleDeck, (d: any) => { applied.push(d); }, { getLatestDeck: () => latestDeck });
  return null;
}

beforeEach(() => {
  vi.useFakeTimers();
  ws.revision = 3;
  ws.writer = "other-app-xyz";
  ws.deck = { cells: [], materials: [], tallies: [] };
  applied = [];
  latestDeck = { cells: [], materials: [], tallies: [{ number: 14 }], adv: { a: 1 } };
  (globalThis as any).fetch = vi.fn(async (url: string, init?: any) => {
    if (!String(url).includes("/workspace")) return { ok: false, json: async () => ({}) };
    if (init?.method === "PUT") return { ok: true, json: async () => ({ ok: true, revision: 1 }) };
    return { ok: true, json: async () => ({ revision: ws.revision, writer: ws.writer, deck: ws.deck }) };
  });
});

afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); });

const tick = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

describe("useAiWorkspace 回显隔离", () => {
  it("writer 是别的实例 → 不采纳它的工作区（界面不被覆盖）", async () => {
    render(React.createElement(Harness, null));
    await tick(2100);   // 首轮轮询
    await tick(2100);   // 再轮
    expect(applied, "不应采纳其它实例的工作区").toEqual([]);
  });

  it("writer 是本实例 + revision 前进 → 按最新 deck 合并（不复活闭包快照里的旧内容）", async () => {
    ws.writer = CLIENT_ID;
    ws.revision = 8;
    ws.deck = { tallies: [{ number: 14 }] };   // 后端回显：AI 只改了 adv
    latestDeck = { cells: [], tallies: [{ number: 14 }], adv: {} };
    render(React.createElement(Harness, null));
    await tick(2100);
    expect(applied).toHaveLength(1);
    // 合并基准必须是 latestDeck（cells: []），不是闭包里的 staleDeck（cells: [{number:1}]）
    expect(applied[0].cells).toEqual([]);
    expect(applied[0].tallies).toEqual([{ number: 14 }]);
    expect(applied[0].adv).toEqual({});
  });

  it("其它实例接管后，自己不再是主人 → 后续 revision 前进也不采纳", async () => {
    ws.writer = CLIENT_ID;
    ws.revision = 8;
    ws.deck = { tallies: [{ number: 14 }] };
    render(React.createElement(Harness, null));
    await tick(2100);
    expect(applied).toHaveLength(1);

    // 另一个实例 PUT 抢走工作区
    ws.writer = "other-app-xyz";
    ws.revision = 9;
    ws.deck = { tallies: [{ number: 999 }] };
    await tick(2100);
    expect(applied, "被接管后不得再采纳").toHaveLength(1);
  });
});
