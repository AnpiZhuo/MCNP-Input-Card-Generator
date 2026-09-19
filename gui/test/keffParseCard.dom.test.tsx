// @vitest-environment jsdom
/**
 * KeffParseCard DOM 测试：玻璃卡的两个子按钮 —— 「解析 mctal」/「解析 .o」。
 *
 * 关键口径（易回归的三点）：
 * 1. 两个按钮各自发**不同的 kind**（mctal / outp）—— 服务端据此给不同默认过滤
 *    （mctal 默认"无后缀"，见 `app/file_dialog.py`）；
 * 2. `withContent:false` —— 只要路径，别把几百 MB 的 outp 读回 JSON；
 * 3. 取消（cancelled）必须**静默**：不回调开窗、也不报错。
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import KeffParseCard from "../src/components/KeffParseCard";

const MCTAL = "D:/MCNP/run/mctal";
const OUTP = "D:/MCNP/run/sweep-001.o";

let fetchMock: any;
let calls: Array<{ url: string; body: any }>;

function stubFetch(chooseResponse: any) {
  calls = [];
  fetchMock = vi.fn(async (url: unknown, opts: unknown) => {
    let body: any = {};
    try { body = JSON.parse((opts as any)?.body || "{}"); } catch { /* ignore */ }
    calls.push({ url: String(url), body });
    return { json: async () => chooseResponse };
  });
  vi.stubGlobal("fetch", fetchMock);
}

beforeEach(() => { stubFetch({ status: "ok", path: MCTAL, cancelled: false }); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("KeffParseCard（keff 解析玻璃卡）", () => {
  it("渲染成玻璃卡，两个子按钮都在", () => {
    const { container } = render(<KeffParseCard onOpen={() => {}} />);
    expect(container.querySelector(".glass-card")).toBeTruthy();
    expect(screen.getByText("keff 解析")).toBeTruthy();
    expect(screen.getByRole("button", { name: /解析 mctal/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /解析 \.o/ })).toBeTruthy();
  });

  it("「解析 mctal」→ kind=mctal + withContent=false，选中后回传路径", async () => {
    const onOpen = vi.fn();
    render(<KeffParseCard onOpen={onOpen} />);
    fireEvent.click(screen.getByRole("button", { name: /解析 mctal/ }));
    await waitFor(() => expect(onOpen).toHaveBeenCalledWith(MCTAL));
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toContain("/api/choose-file");
    expect(calls[0].body).toEqual({ kind: "mctal", withContent: false });
  });

  it("「解析 .o」→ kind=outp（同一卡片、另一套默认过滤）", async () => {
    stubFetch({ status: "ok", path: OUTP, cancelled: false });
    const onOpen = vi.fn();
    render(<KeffParseCard onOpen={onOpen} />);
    fireEvent.click(screen.getByRole("button", { name: /解析 \.o/ }));
    await waitFor(() => expect(onOpen).toHaveBeenCalledWith(OUTP));
    expect(calls[0].body.kind).toBe("outp");
  });

  it("取消选择 → 静默：不开窗、不报错", async () => {
    stubFetch({ status: "ok", path: "", cancelled: true });
    const onOpen = vi.fn();
    render(<KeffParseCard onOpen={onOpen} />);
    fireEvent.click(screen.getByRole("button", { name: /解析 mctal/ }));
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(onOpen).not.toHaveBeenCalled();
    expect(screen.queryByText(/失败/)).toBeNull();
  });

  it("选择器报错 → 卡内提示，不开窗", async () => {
    stubFetch({ status: "error", message: "无法打开系统文件选择器: no display" });
    const onOpen = vi.fn();
    render(<KeffParseCard onOpen={onOpen} />);
    fireEvent.click(screen.getByRole("button", { name: /解析 mctal/ }));
    await waitFor(() => expect(screen.getByText(/no display/)).toBeTruthy());
    expect(onOpen).not.toHaveBeenCalled();
  });
});
