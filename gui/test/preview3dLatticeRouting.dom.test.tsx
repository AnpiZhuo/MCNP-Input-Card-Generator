// @vitest-environment jsdom
/**
 * Preview3D 路由 DOM 测试（用户要求：唯一 3D 预览，格阵装配融进主场景）。
 *
 * - fill/fill_grid 存在 → 仍渲染主 3D 预览（不再切换独立格阵视图）；universe 栅元
 *   从 preview-3d 排除、装配由 preview-lattice 实例化（jsdom 无 WebGL → 装配 effect
 *   早退，仅验证主视图 DOM 仍在）。
 * - 无任何 fill / fill_grid → 单 cell preview-3d 路径。
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import Preview3D from "../src/components/Preview3D";
import { DeckProvider } from "../src/utils/DeckContext";

let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetchMock = vi.fn(async () => ({ json: async () => ({ status: "ok", stl_data: {}, count: 0 }) }));
  vi.stubGlobal("fetch", fetchMock);
  // jsdom 无 ResizeObserver：Preview3D 单 cell 路径的 panelHeight effect 需要（no-op 桩）
  class RO {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  vi.stubGlobal("ResizeObserver", RO);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderPreview(cells: any[]) {
  return render(
    React.createElement(DeckProvider, null,
      React.createElement(Preview3D, {
        cells,
        surfaces: "",
        trCards: "",
        onClose: () => {},
        materials: [],
      }),
    ),
  );
}

describe("Preview3D 唯一 3D 预览（格阵装配融进主场景）", () => {
  it("fill_grid 非空 → 主 3D 预览渲染（不切换独立格阵视图）", () => {
    renderPreview([{ num: "20", mat: "0", surfaces: "-1", fill_grid: '{"lat":"1","kind":"lattice","dims":[2,2,1],"range":["0:1","0:1","0:0"],"cells":[{"u":"1"},{"u":"1"},{"u":"1"},{"u":"1"}],"raw":""}' }]);
    expect(screen.getByText(/3D 预览/)).toBeTruthy();
  });

  it("fill 单值 ≠0 → 主 3D 预览；fill=0 → 不算装配", () => {
    renderPreview([{ num: "30", mat: "0", surfaces: "-9", fill: "10" }]);
    expect(screen.getByText(/3D 预览/)).toBeTruthy();
    cleanup();
    renderPreview([{ num: "31", mat: "0", surfaces: "9", fill: "0" }]);
    expect(screen.getByText(/3D 预览/)).toBeTruthy();
  });

  it("无任何 fill/fill_grid → 单 cell preview-3d 路径（无格阵装配）", () => {
    renderPreview([{ num: "1", mat: "1", surfaces: "-1" }]);
    expect(screen.getByText(/3D 预览/)).toBeTruthy();
  });

  it("hasLattice → 色块总览 toggle 在控制面板（与半透明查看同区）；无 lattice → 不渲染 (项1/项2)", () => {
    renderPreview([{ num: "40", mat: "0", surfaces: "-1", fill_grid: '{"lat":"1","kind":"lattice","dims":[2,2,1],"range":["0:1","0:1","0:0"],"cells":[{"u":"1"},{"u":"1"},{"u":"1"},{"u":"1"}],"raw":""}' }]);
    expect(screen.getByText("色块总览")).toBeTruthy();
    expect(screen.getByText("半透明查看")).toBeTruthy();
    cleanup();
    renderPreview([{ num: "41", mat: "1", surfaces: "-1" }]);
    expect(screen.queryByText("色块总览")).toBeNull();
  });
});
