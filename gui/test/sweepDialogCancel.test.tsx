// @vitest-environment jsdom
/**
 * T3：SweepDialog doRun 无 AbortSignal.timeout 也无可取消按钮 → 大组合 fetch 无限挂起。
 * 修法：doRun 加超时（后端拒绝超预算请求时显示后端错误消息）+ 「取消」按钮（点击 abort
 * 进行中的请求，中止后清理状态）。
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
          // 模拟真实 fetch：以 signal.reason（abort 时传入的原因）reject
          // 注：jsdom 里 DOMException 不是 Error 实例，不能 instanceof 判型，直接透传 reason
          const reason = (sig as any)?.reason;
          reject(reason || new DOMException("aborted", "AbortError"));
        });
      });
    }
    return { json: async () => ({ status: "error", message: "未 mock: " + u }) };
  });
  return { mock, getSignal: () => sig };
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

describe("SweepDialog doRun 超时 + 取消（T3）", () => {
  it("点击开始扫描后出现「取消」按钮，点击取消中止请求并提示", async () => {
    const { mock, getSignal } = hangingSweepRun();
    vi.stubGlobal("fetch", mock);
    render(React.createElement(DeckProvider, null, React.createElement(SweepDialog, { onClose: () => {} })));
    await waitFor(() => expect(screen.getByDisplayValue(/已生成/)).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /开始扫描/ }));
    // 进行中 → 出现「取消」按钮，且扫描按钮禁用（忙碌态文字为「扫描中…」）
    expect(screen.getByRole("button", { name: "取消" })).toBeTruthy();
    expect((screen.getByRole("button", { name: /扫描中/ }) as HTMLButtonElement).disabled).toBe(true);
    // 点击取消 → 请求 signal 被 abort，提示已取消，状态清理
    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    await waitFor(() => expect(getSignal()?.aborted).toBe(true));
    expect(await screen.findByText(/扫描已取消/)).toBeTruthy();
    await waitFor(() => expect((screen.getByRole("button", { name: /开始扫描/ }) as HTMLButtonElement).disabled).toBe(false));
    // 取消按钮消失
    await waitFor(() => expect(screen.queryByRole("button", { name: "取消" })).toBeNull());
  });

  it("sweep-run 超时后自动中止并提示（120s backstop）", async () => {
    vi.useFakeTimers();
    const { mock, getSignal } = hangingSweepRun();
    vi.stubGlobal("fetch", mock);
    render(React.createElement(DeckProvider, null, React.createElement(SweepDialog, { onClose: () => {} })));
    // 等待基准 INP 生成（fetch mock 为微任务，act flush 后完成）
    await act(async () => {});
    expect(screen.getByDisplayValue(/已生成/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /开始扫描/ }));
    expect(screen.getByRole("button", { name: "取消" })).toBeTruthy();
    // 推进 120s → 触发超时 abort（setTimeout 被 fake timers 接管）
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
    render(React.createElement(DeckProvider, null, React.createElement(SweepDialog, { onClose: () => {} })));
    await waitFor(() => expect(screen.getByDisplayValue(/已生成/)).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /开始扫描/ }));
    expect(await screen.findByText(/组合数超预算/)).toBeTruthy();
  });
});
