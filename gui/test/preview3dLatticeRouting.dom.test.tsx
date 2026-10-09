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
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import Preview3D from "../src/components/Preview3D";
import { DeckProvider } from "../src/utils/DeckContext";

let fetchMock: any;
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

describe("/api/preview-3d 请求载荷必须带语义字段（回归：墓地会被画出来）", () => {
  /**
   * 2026-10-10 实测：此前只发 number/material/density/surface_expr 四个字段，而后端
   * `build_cells_data` 的 item-14 跳过规则（imp=0 ⇒ 墓地不渲染 / fill、fill_grid ⇒ 装配容器
   * 不渲染 / render:false ⇒ 跳过）**全靠被剥掉的那些字段**判断 ⇒ 规则全失效。用户真实 deck
   * （`筒子1`）端到端实测：只发 4 字段时 9 个栅元全出 STL，其中 `Graveyard`（球外无界）
   * 被裁成 1000³、`Graveyard_in` 180³，而模型本体最大仅 102 单位 ⇒ 相机被撑开、模型缩成针尖
   * （= 2026-09-24 修过的「3D 预览一坨」在这条链上复活）。这条测试把字段口径钉死。
   */
  const previewBody = async () => {
    await waitFor(() => {
      expect(fetchMock.mock.calls.some((c: any[]) => String(c[0]).includes("/api/preview-3d"))).toBe(true);
    });
    const call = fetchMock.mock.calls.find((c: any[]) => String(c[0]).includes("/api/preview-3d"))!;
    return JSON.parse(call[1].body);
  };

  it("墓地的 imp 与注释、render、fill 都必须发出去", async () => {
    renderPreview([{
      num: "9", mat: "0", density: "", surfaces: "124", comment: "Graveyard",
      render: true, impN: "0", impP: "0", impE: "", u: "", fill: "", lat: "", trcl: "", fill_grid: "",
    }]);
    const body = await previewBody();
    expect(body.cells[0]).toMatchObject({
      number: 9, material: "0", surface_expr: "124",
      imp_n: "0", imp_p: "0", comment: "Graveyard", render: true,
      u: "", fill: "", fill_grid: "",
    });
  });

  it("render:false 与 fill 容器同样要能传到后端（否则跳过规则失效）", async () => {
    renderPreview([{ num: "20", mat: "0", surfaces: "-1", render: false, fill: "10", fill_grid: '{"a":1}' }]);
    const body = await previewBody();
    expect(body.cells[0]).toMatchObject({ render: false, fill: "10", fill_grid: '{"a":1}' });
  });

  it("格阵 deck 仍然把 u 非空栅元排除在 preview-3d 之外（既有行为不变）", async () => {
    renderPreview([
      { num: "1", mat: "0", surfaces: "-1", u: "1", fill_grid: '{"lat":"1","kind":"lattice","dims":[2,2,1],"range":["0:1","0:1","0:0"],"cells":[{"u":"1"},{"u":"1"},{"u":"1"},{"u":"1"}],"raw":""}' },
      { num: "2", mat: "0", surfaces: "-2", u: "1" },
    ]);
    const body = await previewBody();
    expect(body.cells).toEqual([]); // 两个都是 universe 栅元 ⇒ 全被排除，装配走 preview-lattice
  });
});
