// @vitest-environment jsdom
/**
 * STEP 方向预览 DOM 测试 —— 「点一下先用 STEP 生成预览，方便选上轴」（用户 2026-10-08）。
 *
 * 契约：
 *   1. 没选文件时按钮禁用（不知道拿什么生成预览）；
 *   2. 选了文件点按钮 ⇒ POST `/api/step-preview`，body 里带**当前的上轴/方位/原点约定**
 *      与所选文件的 base64（后端就按这个约定把网格转好 ⇒ "看着切"是准的）；
 *   3. 改了上轴/原点且预览已开 ⇒ **自动重取**（不必再点一次）。
 *
 * 注意：预览改用**真正的 3D 预览窗口**（Preview3D，预置网格模式；用户 2026-10-08：
 * 「不如直接用 3D 预览的窗口那一套」）。jsdom 里没有 WebGL，这里把它替换成占位 div ——
 * 本用例只锁"请求发对了 + 窗口被打开"，渲染由 Preview3D 自己负责（它有既有测试与实机验证）。
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("../src/components/Preview3D", () => ({
  default: (props: any) => React.createElement("div", { "data-preview3d-mock": "1" },
    `title=${props.titleOverride || ""};cells=${(props.cells || []).length};stl=${props.preloadedStl ? "YES" : "NO"}`),
}));

// 独立窗口开关：默认 mock 成"开窗失败"（走窗内浮层回退路径，便于断言）；需要时改成 true
const openPreview3DMock = vi.fn(async (_data?: any): Promise<boolean> => false);
vi.mock("../src/utils/windows", () => ({
  openPreview3D: (data: any) => openPreview3DMock(data),
}));

import StepImportDialog from "../src/components/StepImportDialog";

afterEach(() => cleanup());
beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  openPreview3DMock.mockReset();
  openPreview3DMock.mockResolvedValue(false);   // 默认：开窗失败 ⇒ 走窗内浮层回退
});

function mount() {
  return render(React.createElement(StepImportDialog, {
    onImport: vi.fn(),
    onClose: vi.fn(),
  }));
}

function pickFile(name = "box.step") {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  const file = new File(["ISO-10303-21;\nENDSEC;\n"], name, { type: "application/step" });
  fireEvent.change(input, { target: { files: [file] } });
  return file;
}

function previewBtn() {
  return document.querySelector('[data-step-preview="1"]') as HTMLButtonElement;
}

/** 伪 fetch：只认 /api/step-preview，回一个最小可用响应 */
function mockPreview(ok = true) {
  const calls: any[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init: any) => {
    calls.push({ url: String(url), body: init?.body ? JSON.parse(init.body) : null });
    return {
      json: async () => (ok
        ? { status: "ok", stl: "AAA", bbox: [[0, 0, 0], [1, 1, 1]], notes: ["已按导入约定处理：上轴 Y 朝上"] }
        : { status: "error", message: "需要 FreeCAD" }),
    } as any;
  }));
  return calls;
}

describe("StepImportDialog · STEP 方向预览", () => {
  it("未选文件时按钮禁用", () => {
    mount();
    expect(previewBtn()).toBeTruthy();
    expect(previewBtn().disabled).toBe(true);
  });

  it("选了文件点预览 ⇒ 请求带当前约定 + 文件内容，并渲染出画布", async () => {
    const calls = mockPreview();
    mount();
    pickFile();
    expect(previewBtn().disabled).toBe(false);

    fireEvent.click(previewBtn());
    await waitFor(() => expect(calls.length).toBe(1));
    expect(calls[0].url).toContain("/api/step-preview");
    expect(calls[0].body.cad_orientation).toEqual({ up: "Z", azimuthDeg: 0, origin: "keep" });
    expect(typeof calls[0].body.data).toBe("string");
    expect(calls[0].body.data.length).toBeGreaterThan(0);

    await waitFor(() => expect(document.querySelector("[data-preview3d-mock]")).toBeTruthy());
    expect(document.body.textContent).toContain("title=📐 STEP 方向预览");
    expect(document.body.textContent).toContain("stl=YES");
  });

  it("★改了上轴 ⇒ 预览自动重取（不必再点一次），且请求里是新的上轴", async () => {
    const calls = mockPreview();
    mount();
    pickFile();
    fireEvent.click(previewBtn());
    await waitFor(() => expect(calls.length).toBe(1));

    // 上轴改成 Y（SolidWorks 类）
    const upSel = Array.from(document.querySelectorAll("select"))
      .find((s) => Array.from(s.options).some((o) => o.value === "Y")) as HTMLSelectElement;
    expect(upSel).toBeTruthy();
    fireEvent.change(upSel, { target: { value: "Y" } });

    await waitFor(() => expect(calls.length).toBe(2));
    expect(calls[1].body.cad_orientation.up).toBe("Y");
  });

  it("后端报错 ⇒ 显示消息，不开预览窗口", async () => {
    mockPreview(false);
    mount();
    pickFile();
    fireEvent.click(previewBtn());
    await waitFor(() => expect(document.body.textContent).toContain("需要 FreeCAD"));
    expect(document.querySelector("[data-preview3d-mock]")).toBeNull();
  });

  /**
   * ★开新窗口（用户 2026-10-08：「生成的预览窗口页怎么不是新的窗口？」）。
   *
   * 契约：点预览 ⇒ 走 `openPreview3D` 这条**与「3D 预览」完全相同**的独立窗口桥
   * （预置网格随桥带过去，窗口里不再调后端）；开窗成功时**不**在主窗口里再画浮层。
   */
  it("★开窗成功 ⇒ 走独立窗口桥（带预置网格），主窗口不留浮层", async () => {
    openPreview3DMock.mockResolvedValueOnce(true);
    const calls = mockPreview();
    mount();
    pickFile();
    fireEvent.click(previewBtn());
    await waitFor(() => expect(calls.length).toBe(1));
    await waitFor(() => expect(openPreview3DMock).toHaveBeenCalledTimes(1));
    const arg: any = openPreview3DMock.mock.calls[0]?.[0] || {};
    expect(arg.preloadedStl && Object.keys(arg.preloadedStl).length).toBe(1);   // 网格随桥过去
    expect(arg.titleOverride).toContain("STEP 方向预览");
    expect(arg.materials).toEqual([]);
    await waitFor(() => expect(document.querySelector("[data-preview3d-mock]")).toBeNull());
  });

  /**
   * ★双滚动条回归（用户 2026-10-08：「这个页面怎么有两个条」）。
   *
   * 根因：设置列表曾用 `maxHeight: calc(85vh - 190px)` 自己估算"除列表外的 chrome 高度"，
   * 参数一多（本批新增坐标约定/原点口径/预览块）估算就被吃穿 ⇒ 外层 FloatingDialog 的 body
   * （flex:1 + overflow:auto）与列表同时出条。
   * 契约：设置列表**只能**由 flex 链决定高度（flex:1 + minHeight:0），不得再出现 vh 估算。
   */
  it("★设置列表只留一个滚动区：不再用 vh 估算高度", () => {
    mount();
    const scrolls = document.querySelectorAll("[data-step-settings-scroll]");
    expect(scrolls.length).toBe(1);
    const el = scrolls[0] as HTMLElement;
    expect(el.style.overflowY).toBe("auto");
    expect(el.style.flexGrow).toBe("1");
    expect(el.style.flexBasis).toBe("0%");
    expect(el.style.minHeight).toBe("0px");
    expect(el.style.maxHeight).toBe("");
    // 中间层必须是 flex 列容器（高度由对话框给，不再自己算）
    const wrap = el.parentElement as HTMLElement;
    expect(wrap.style.display).toBe("flex");
    expect(wrap.style.flexDirection).toBe("column");
    expect(wrap.style.maxHeight).toBe("");
    // 列表内部也不得再有 vh 形式的 maxHeight（那正是"第二条"的来源）
    const inner = Array.from(el.querySelectorAll<HTMLElement>('[style*="vh"]'))
      .filter((n) => (n.style.maxHeight || "").includes("vh"));
    expect(inner.map((n) => n.tagName)).toEqual([]);
  });
});


