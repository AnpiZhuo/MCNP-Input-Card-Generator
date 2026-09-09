// @vitest-environment jsdom
/**
 * SweepDialog DOM 交互测试（jsdom + @testing-library/react，用户批准的新增开发依赖）。
 *
 * 覆盖（免正则「选中即参数」版）：打开后自动生成基准 INP；框选 → 设为扫描参数 →
 * 按钮可用/组合数更新；规划预览（/api/sweep-plan）→ 预览文本；开始扫描
 * （/api/sweep-run）→ 结果表 + TSV 下载；错误路径提示；关闭回调。
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import SweepDialog from "../src/components/SweepDialog";
import { DeckProvider } from "../src/utils/DeckContext";


const DECK = "title\nSweep smoke\nNPS 1000\n1 1 -1.0 -1\n2 0 1\n1 so 5\n";

function makeFetch(handlers: Record<string, (body: any) => any>) {
  return vi.fn(async (url: unknown, opts: unknown) => {
    const u = String(url);
    let body: any = {};
    try { body = JSON.parse((opts as any)?.body || "{}"); } catch { /* ignore */ }
    for (const [key, fn] of Object.entries(handlers)) {
      if (u.includes(key)) return { json: async () => fn(body) };
    }
    return { json: async () => ({ status: "error", message: "未 mock: " + u }) };
  });
}

let fetchMock: ReturnType<typeof makeFetch>;

beforeEach(() => {
  fetchMock = makeFetch({
    "/api/generate": () => ({ status: "ok", inp: DECK }),
    "/api/sweep-plan": () => ({
      status: "ok",
      count: 2,
      combos: [{ nps: 1000 }, { nps: 2000 }],
      previews: ["preview-1000", "preview-2000"],
    }),
    "/api/sweep-run": () => ({
      status: "ok",
      baseDir: "C:/tmp/mcnp_sweep_x",
      records: [
        { index: 1, parameters: { nps: 1000 }, exitCode: 0, keff: 1.001 },
        { index: 2, parameters: { nps: 2000 }, exitCode: 1, keff: null },
      ],
      summaryTsv: "index\tnps\texit\tkeff\n1\t1000\t0\t1.001000\n2\t2000\t1\tn/a",
    }),
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderDialog(): void {
  render(React.createElement(DeckProvider, null,
    React.createElement(SweepDialog, { onClose: () => {} })));
}

/** 等 /api/generate 完成 → 在基准 INP 里框选 sel → 点「设为扫描参数」 */
async function addParamFromSelection(sel = "1000"): Promise<void> {
  const area = (await screen.findByDisplayValue(/NPS 1000/)) as HTMLTextAreaElement;
  const idx = area.value.indexOf(sel);
  expect(idx).toBeGreaterThanOrEqual(0);
  act(() => { area.setSelectionRange(idx, idx + sel.length); });
  fireEvent.select(area);
  fireEvent.click(screen.getByRole("button", { name: /设为扫描参数/ }));
}

describe("SweepDialog DOM 交互（选中即参数）", () => {
  it("打开后自动生成基准 INP；未选参数前按钮禁用；框选后可用", async () => {
    renderDialog();
    await waitFor(() => expect(screen.getByDisplayValue(/NPS 1000/)).toBeTruthy());
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/generate"), expect.anything());
    // 还没选参数 → 两个执行按钮禁用
    expect((screen.getByRole("button", { name: /规划预览/ }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: /开始扫描/ }) as HTMLButtonElement).disabled).toBe(true);
    // 框选 NPS 的 1000 → 参数行出现，按钮可用
    await addParamFromSelection();
    const runBtn = screen.getByRole("button", { name: /开始扫描（1 组合/ }) as HTMLButtonElement;
    const planBtn = screen.getByRole("button", { name: /规划预览/ }) as HTMLButtonElement;
    expect(runBtn.disabled).toBe(false);
    expect(planBtn.disabled).toBe(false);
  });

  it("改取值后组合数更新", async () => {
    renderDialog();
    await waitFor(() => expect(screen.getByDisplayValue(/NPS 1000/)).toBeTruthy());
    await addParamFromSelection();
    const valuesInput = screen.getByPlaceholderText(/取值列表/);
    fireEvent.change(valuesInput, { target: { value: "1000 2000" } });
    expect(screen.getByRole("button", { name: /开始扫描（2 组合/ })).toBeTruthy();
  });

  it("规划预览：调用 /api/sweep-plan 并展示预览文本", async () => {
    renderDialog();
    await waitFor(() => expect(screen.getByDisplayValue(/NPS 1000/)).toBeTruthy());
    await addParamFromSelection();
    fireEvent.click(screen.getByRole("button", { name: /规划预览/ }));
    expect(await screen.findByText(/^preview-1000$/)).toBeTruthy();
    expect(await screen.findByText(/^preview-2000$/)).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/sweep-plan"), expect.anything());
  });

  it("开始扫描：调用 /api/sweep-run 并渲染结果表与下载按钮", async () => {
    renderDialog();
    await waitFor(() => expect(screen.getByDisplayValue(/NPS 1000/)).toBeTruthy());
    await addParamFromSelection();
    fireEvent.click(screen.getByRole("button", { name: /开始扫描/ }));
    expect(await screen.findByText(/k-eff vs/)).toBeTruthy();   // 默认视图=仪表盘
    fireEvent.click(screen.getByRole("button", { name: "结果表" }));
    expect(await screen.findByText("1.001000")).toBeTruthy();   // keff 列
    expect(screen.getByText("n/a")).toBeTruthy();               // 第 2 组合 keff 缺失
    expect(screen.getByRole("button", { name: "下载 TSV" })).toBeTruthy();
    expect(screen.getByText(/mcnp_sweep_x/)).toBeTruthy();      // 运行目录提示
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/sweep-run"), expect.anything());
  });

  it("后端返回错误时显示错误信息", async () => {
    fetchMock = makeFetch({
      "/api/generate": () => ({ status: "ok", inp: DECK }),
      "/api/sweep-plan": () => ({ status: "error", message: "plan boom" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    renderDialog();
    await waitFor(() => expect(screen.getByDisplayValue(/NPS 1000/)).toBeTruthy());
    await addParamFromSelection();
    fireEvent.click(screen.getByRole("button", { name: /规划预览/ }));
    expect(await screen.findByText(/plan boom/)).toBeTruthy();
  });

  it("关闭按钮触发 onClose", async () => {
    const onClose = vi.fn();
    render(React.createElement(DeckProvider, null,
      React.createElement(SweepDialog, { onClose })));
    fireEvent.click(screen.getByRole("button", { name: "关闭" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
