// @vitest-environment jsdom
/**
 * StepImportDialog DOM 测试 —— 点「📥 导入」即刻自我关闭。
 *
 * 用户反馈（2026-09-12，部署版真机）：「导入按钮有用，只是这个界面不会自己关」。
 * 旧行为：窗口一直开着等 `/api/import-step` 回来（GEOUNED 转换小件 3~4 s、真实
 * CAD 装配体可达分钟级），转换完弹完 alert 才关 —— 观感就是"点了没反应"。
 *
 * 契约（本次锁死）：
 *   1. 未选文件点导入 → 弹 alert 提示、**不**关窗、不调用 onImport；
 *   2. 选了文件点导入 → **同步**把 (settings, file) 交给 onImport 并立刻 onClose，
 *      **不等** onImport 的 Promise 落地（转换在后台跑，结果由 alert 告知）；
 *   3. 设置项原样透传给 onImport。
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import StepImportDialog from "../src/components/StepImportDialog";

afterEach(() => cleanup());

/** 复刻 GeometryTab 的父子关系：onClose → 卸载对话框。 */
function Harness({ onImport }: { onImport: (s: any, f: File) => void }) {
  const [open, setOpen] = React.useState(true);
  return React.createElement(React.Fragment, null,
    React.createElement("div", null, open ? "OPEN" : "CLOSED"),
    open ? React.createElement(StepImportDialog, {
      onImport, onClose: () => setOpen(false),
    }) : null);
}

/** onImport 的 mock：显式声明 (settings, file) 签名，否则 mock.calls[i][1] 类型越界。 */
function importSpy(impl?: (s: any, f: File) => unknown) {
  return vi.fn((s: any, f: File) => (impl ? impl(s, f) : undefined));
}

function pickFile(name = "box.step") {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  const file = new File(["ISO-10303-21;\nENDSEC;\n"], name, { type: "application/step" });
  fireEvent.change(input, { target: { files: [file] } });
  return file;
}

const btn = () => screen.getByRole("button", { name: /导入/ }) as HTMLButtonElement;

describe("StepImportDialog 点导入即关窗", () => {
  let alertSpy: any;
  beforeEach(() => { alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {}); });
  afterEach(() => { alertSpy.mockRestore(); });

  it("未选文件：提示且不关窗、不触发导入", () => {
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    // 初始「导入」禁用（未选文件）
    expect(btn().disabled).toBe(true);
    fireEvent.click(btn());
    expect(onImport).not.toHaveBeenCalled();
    expect(screen.getByText("OPEN")).toBeTruthy();
    expect(screen.getByText(/GEOUNED 导入设置/)).toBeTruthy();
  });

  it("选了文件：onImport 后立刻关窗（不等转换完成）", () => {
    // 永不 resolve —— 模拟"转换还在跑"
    const onImport = importSpy(() => new Promise<void>(() => {}));
    render(React.createElement(Harness, { onImport }));
    const file = pickFile("part.step");
    expect(btn().disabled).toBe(false);

    fireEvent.click(btn());

    // 同步即可断言：文件已交出去，窗口已关
    expect(onImport).toHaveBeenCalledTimes(1);
    expect(onImport.mock.calls[0][1]).toBe(file);
    expect(screen.getByText("CLOSED")).toBeTruthy();
    expect(screen.queryByText(/GEOUNED 导入设置/)).toBeNull();
  });

  it("设置项原样透传（材料名 / 密度 / 起始栅元与曲面号）", () => {
    const onImport = importSpy();
    render(React.createElement(Harness, { onImport }));
    pickFile();
    fireEvent.change(screen.getByDisplayValue("MAT"), { target: { value: "SS316" } });
    fireEvent.change(screen.getByDisplayValue("-1.0"), { target: { value: "-7.93" } });
    fireEvent.change(screen.getByDisplayValue("100"), { target: { value: "500" } });
    fireEvent.click(btn());
    expect(onImport.mock.calls[0][0]).toMatchObject({
      materialName: "SS316", density: "-7.93", startSurfNum: 500, voidGeneration: true,
    });
  });
});
