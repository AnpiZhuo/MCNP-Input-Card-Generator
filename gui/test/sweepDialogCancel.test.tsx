// @vitest-environment jsdom
/**
 * T3：SweepDialog doRun 取消/超时/预算拒绝（免正则「选中即参数」版）。
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import SweepDialog from "../src/components/SweepDialog";
import { DeckProvider } from "../src/utils/DeckContext";

const DECK = "title\nSweep smoke\nNPS 1000\n1 1 -1.0 -1\n2 0 1\n1 so 5\n";

/** /api/sweep-run 挂起（直到 signal abort），用于验证取消/超时 */
function hangingSweepRun() {
  let sig: AbortSignal | null = null;
  const mock = vi.fn(async (url: unknown, opts: unknown) => {
    const u = String(url);
    if (u.includes("/api/generate")) return { json: async () => ({ status: "ok", inp: DECK }) };
    if (u.includes("/api/sweep-run")) {
      sig = (opts as any)?.signal as AbortSignal;
      return new Promise((_resolve, reject) => {
        sig?.addEventListener("abort", () => {
          const reason = (sig as any)?.reason;
          reject(reason || new DOMException("aborted", "AbortError"));
        });
      });
    }
    return { json: async () => ({ status: "error", message: "未 mock: " + u }) };
  });
  return { mock, getSignal: () => sig };
}

/** 在基准 INP 里框选 "1000" → 设为扫描参数 */
async function addParamFromSelection(): Promise<void> {
  const area = (await screen.findByDisplayValue(/NPS 1000/)) as HTMLTextAreaElement;
  const idx = area.value.indexOf("1000");
  expect(idx).toBeGreaterThanOrEqual(0);
  act(() => { area.setSelectionRange(idx, idx + 4); });
  fireEvent.select(area);
  fireEvent.click(screen.getByRole("button", { name: /设为扫描参数/ }));
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

describe("SweepDialog doRun 超时 + 取消（T3）", () => {
  it("点击开始扫描后出现「取消」按钮，点击取消中止请求并提示", async () => {
    const { mock, getSignal } = hangingSweepRun();
    vi.stubGlobal("fetch", mock);
    render(React.createElement(DeckProvider, null,
      React.createElement(SweepDialog, { onClose: () => {} })));
    await addParamFromSelection();
    fireEvent.click(screen.getByRole("button", { name: /开始扫描/ }));
    // 进行中 → 出现「取消」按钮，且扫描按钮禁用（忙碌态）
    expect(screen.getByRole("button", { name: "取消" })).toBeTruthy();
    expect((screen.getByRole("button", { name: /扫描中/ }) as HTMLButtonElement).disabled).toBe(true);
    // 点击取消 → 请求 signal 被 abort，提示已取消
    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    await waitFor(() => expect(getSignal()?.aborted).toBe(true));
    expect(await screen.findByText(/扫描已取消/)).toBeTruthy();
    await waitFor(() => expect((screen.getByRole("button", { name: /开始扫描/ }) as HTMLButtonElement).disabled).toBe(false));
    await waitFor(() => expect(screen.queryByRole("button", { name: "取消" })).toBeNull());
  });

  it("sweep-run 超时后自动中止并提示（120s backstop）", async () => {
    vi.useFakeTimers();
    const { mock, getSignal } = hangingSweepRun();
    vi.stubGlobal("fetch", mock);
    render(React.createElement(DeckProvider, null,
      React.createElement(SweepDialog, { onClose: () => {} })));
    // 等待基准 INP 生成（fetch mock 为微任务，act flush 后完成）
    await act(async () => {});
    // 假时钟下不能 waitFor：同步完成框选 → 设为扫描参数
    const area = screen.getByDisplayValue(/NPS 1000/) as HTMLTextAreaElement;
    const idx = area.value.indexOf("1000");
    act(() => { area.setSelectionRange(idx, idx + 4); });
    fireEvent.select(area);
    fireEvent.click(screen.getByRole("button", { name: /设为扫描参数/ }));
    fireEvent.click(screen.getByRole("button", { name: /开始扫描/ }));
    expect(screen.getByRole("button", { name: "取消" })).toBeTruthy();
    // 推进 120s → 触发超时 abort
    await act(async () => { vi.advanceTimersByTime(120001); });
    expect(getSignal()?.aborted).toBe(true);
    expect(screen.getByText(/超时（120s），已中止/)).toBeTruthy();
    vi.useRealTimers();
  });

  it("后端拒绝超预算请求时显示后端错误消息（不吞错）", async () => {
    const fetchMock = vi.fn(async (url: unknown) => {
      const u = String(url);
      if (u.includes("/api/generate")) return { json: async () => ({ status: "ok", inp: DECK }) };
      if (u.includes("/api/sweep-run")) return { json: async () => ({ status: "error", message: "组合数超预算（>50），已拒绝" }) };
      return { json: async () => ({ status: "error", message: "未 mock" }) };
    });
    vi.stubGlobal("fetch", fetchMock);
    render(React.createElement(DeckProvider, null,
      React.createElement(SweepDialog, { onClose: () => {} })));
    await addParamFromSelection();
    fireEvent.click(screen.getByRole("button", { name: /开始扫描/ }));
    expect(await screen.findByText(/组合数超预算/)).toBeTruthy();
  });
});