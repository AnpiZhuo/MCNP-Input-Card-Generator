// @vitest-environment jsdom
/**
 * LatticeCanvas 2D 涂色画布 DOM 测试。
 *
 * 覆盖：矩形 grid 渲染 + 点击涂色；六棱柱蜂窝渲染 + 点击涂色；
 * 条目流 ≠ dims 乘积 → 非阻塞警告横幅（QA 建议3）。
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import LatticeCanvas from "../src/components/LatticeCanvas";
import { initialHexCells, initialRectCells } from "../src/utils/lattice";

afterEach(() => cleanup());

const palette = { "1": "#111111", "2": "#222222" };

describe("LatticeCanvas 矩形 (lat=1)", () => {
  it("渲染 2×2 格位，点击涂 selectedU", () => {
    const onCellChange = vi.fn();
    const cells = initialRectCells(2, 2, 1, "1");
    render(React.createElement(LatticeCanvas, {
      lat: "1", dims: [2, 2, 1], cells, palette, selectedU: "2", onCellChange,
    }));
    expect(screen.getAllByTestId(/^lcell-/)).toHaveLength(4);
    fireEvent.click(screen.getByTestId("lcell-2"));
    expect(onCellChange).toHaveBeenCalledWith(2, "2");
  });

  it("disabled 时不触发 onCellChange", () => {
    const onCellChange = vi.fn();
    const cells = initialRectCells(2, 2, 1, "1");
    render(React.createElement(LatticeCanvas, {
      lat: "1", dims: [2, 2, 1], cells, palette, selectedU: "2", onCellChange, disabled: true,
    }));
    fireEvent.click(screen.getByTestId("lcell-0"));
    expect(onCellChange).not.toHaveBeenCalled();
  });
});

describe("LatticeCanvas 六棱柱 (lat=2)", () => {
  it("环形蜂窝：3×3 盒 9 格位，点击涂 selectedU", () => {
    const onCellChange = vi.fn();
    const cells = initialHexCells(1, 1, "1");
    render(React.createElement(LatticeCanvas, {
      lat: "2", dims: [3, 3, 1], cells, palette, selectedU: "1", onCellChange,
    }));
    expect(screen.getAllByTestId(/^lcell-/)).toHaveLength(9);
    fireEvent.click(screen.getByTestId("lcell-4"));
    expect(onCellChange).toHaveBeenCalledWith(4, "1");
  });
});

describe("LatticeCanvas 条目流不匹配警告（QA 建议3）", () => {
  it("cells.length ≠ dims 乘积 → 非阻塞横幅", () => {
    const cells = Array(7).fill({ u: "1", dx: "", dy: "", dz: "" });
    render(React.createElement(LatticeCanvas, {
      lat: "1", dims: [3, 3, 1], cells, palette, selectedU: "1", onCellChange: () => {},
    }));
    expect(screen.getByText(/条目数与格阵尺寸不匹配/)).toBeTruthy();
  });

  it("匹配时无警告", () => {
    const cells = initialRectCells(2, 2, 1, "1");
    render(React.createElement(LatticeCanvas, {
      lat: "1", dims: [2, 2, 1], cells, palette, selectedU: "1", onCellChange: () => {},
    }));
    expect(screen.queryByText(/条目数与格阵尺寸不匹配/)).toBeNull();
  });
});
