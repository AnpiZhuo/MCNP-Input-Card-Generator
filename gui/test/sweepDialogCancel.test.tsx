// @vitest-environment jsdom
/**
 * SweepDialog doRun —— 显式计算（2026-10-20 用户口径）：
 *   - 每个组合弹一个可见 MCNP 控制台窗口，**程序不设超时**；
 *   - 用户关窗口 = 中止该组合，程序不主动 abort、不杀进程；
 *   - 后端拒绝（组合数超上限）时显示后端错误消息（不吞错）。
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import SweepDialog from "../src/components/SweepDialog";
import { DeckProvider } from "../src/utils/DeckContext";

const DECK = "title\nSweep smoke\nNPS 1000\n1 1 -1.0 -1\n2 0 1\n1 so 5\n";

/** /api/sweep-run 挂起（永不 resolve），用于验证「不超时、不中止」 */
function hangingSweepRun() {
  let opts: any = null;
  const mock = vi.fn(async (url: unknown, o: unknown) => {
    const u = String(url);
    if (u.includes("/api/generate")) return { json: async () => ({ status: "ok", inp: DECK }) };
    if (u.includes("/api/sweep-run")) {
      opts = o;
      return new Promise(() => { /* 永不结束：模拟 MCNP 窗口一直开着 */ });
    }
    return { json: async () => ({ status: "error", message: "未 mock: " + u }) };
  });
  return { mock, getOpts: () => opts };
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

describe("SweepDialog doRun 显式计算（无超时、无取消）", () => {
  it("请求不带 AbortSignal、没有「取消」按钮；推进 10 分钟也不会自动中止", async () => {
    vi.useFakeTimers();
    const { mock, getOpts } = hangingSweepRun();
    vi.stubGlobal("fetch", mock);
    render(React.createElement(DeckProvider, null,
      React.createElement(SweepDialog, { onClose: () => {} })));
    // 等待基准 INP 生成（fetch mock 为微任务，act flush 后完成）
    await act(async () => {});
    const area = screen.getByDisplayValue(/NPS 1000/) as HTMLTextAreaElement;
    const idx = area.value.indexOf("1000");
    act(() => { area.setSelectionRange(idx, idx + 4); });
    fireEvent.select(area);
    fireEvent.click(screen.getByRole("button", { name: /设为扫描参数/ }));
    fireEvent.click(screen.getByRole("button", { name: /开始扫描/ }));

    // 显式计算：没有取消按钮（中止 MCNP 的唯一方式是关掉那个控制台窗口）
    expect(screen.queryByRole("button", { name: "取消" })).toBeNull();
    // fetch 不传 signal ⇒ 前端没有任何自动 abort 的途径
    expect(getOpts()?.signal).toBeUndefined();
    // 忙碌态（等窗口关完）
    expect((screen.getByRole("button", { name: /扫描中/ }) as HTMLButtonElement).disabled).toBe(true);

    // 旧的 120s 兜底已删除：推进 10 分钟，既不报超时也不退出忙碌态
    await act(async () => { vi.advanceTimersByTime(10 * 60 * 1000); });
    expect(screen.queryByText(/扫描超时（120s）/)).toBeNull();
    expect(screen.queryByText(/已中止/)).toBeNull();
    expect((screen.getByRole("button", { name: /扫描中/ }) as HTMLButtonElement).disabled).toBe(true);
    vi.useRealTimers();
  });

  it("后端拒绝组合数超上限时显示后端错误消息（不吞错）", async () => {
    const fetchMock = vi.fn(async (url: unknown) => {
      const u = String(url);
      if (u.includes("/api/generate")) return { json: async () => ({ status: "ok", inp: DECK }) };
      if (u.includes("/api/sweep-run")) return { json: async () => ({ status: "error", message: "组合数 51 超上限 50，请缩小参数范围" }) };
      return { json: async () => ({ status: "error", message: "未 mock" }) };
    });
    vi.stubGlobal("fetch", fetchMock);
    render(React.createElement(DeckProvider, null,
      React.createElement(SweepDialog, { onClose: () => {} })));
    await addParamFromSelection();
    fireEvent.click(screen.getByRole("button", { name: /开始扫描/ }));
    expect(await screen.findByText(/超上限 50/)).toBeTruthy();
    await waitFor(() => expect((screen.getByRole("button", { name: /开始扫描/ }) as HTMLButtonElement).disabled).toBe(false));
  });
});
