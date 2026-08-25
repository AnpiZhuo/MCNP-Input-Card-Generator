// @vitest-environment jsdom
/**
 * LatticeEditDialog DOM 集成测试（Wave 2b）：
 *  - 项1/6：4 步状态机（类型尺寸→材料曲面→画布涂色→保存）+ 第 0 步六个方向层数空恒显示
 *    （无「2D 平面/3D 体积」toggle；六棱柱 x/y 层数取环数）
 *  - 项6/7：调色板与画布同屏（void 恒首位 + U 色块），点选涂色笔 → 画布涂色
 *  - 项12：大格阵保存摘要显示体积告警（cells>8000）
 *  - 项13：保存前 detectFillCycle 命中 → 阻止保存 + 提示
 *
 * 3D 子预览（LatticePreview3D / MacrobodyPreview）用 WebGL，jsdom 无 WebGL → mock。
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import LatticeEditDialog from "../src/components/LatticeEditDialog";
import type { CellData } from "../src/components/CellEditDialog";

vi.mock("../src/components/LatticePreview3D", () => ({
  __esModule: true,
  default: () => React.createElement("div", { "data-testid": "mock-lattice-preview3d" }),
}));
vi.mock("../src/components/MacrobodyPreview", () => ({
  __esModule: true,
  default: () => React.createElement("div", { "data-testid": "mock-macrobody" }),
}));

function mkCell(over: Partial<CellData> = {}): CellData {
  return {
    num: "1", mat: "0", density: "", surfaces: "", impN: "", impP: "", impE: "",
    vol: "", pwt: "", ext: "", fcl: "", u: "", fill: "", lat: "", trcl: "", tmp: "",
    otherParams: "", render: true, fill_grid: "", comment: "",
    ...over,
  };
}

function renderDialog(deckCells: CellData[], initialCell?: CellData | null) {
  const onSave = vi.fn();
  const onClose = vi.fn();
  const utils = render(React.createElement(LatticeEditDialog, {
    surfacesText: "",
    deckCells,
    initialCell: initialCell ?? null,
    nextCellNum: 50,
    onSave,
    onClose,
  }));
  return { ...utils, onSave, onClose };
}

/** numField 的 label（如 "x 向左"）→ 其父容器内 input */
function numInput(labelText: string): HTMLInputElement {
  const labels = Array.from(document.querySelectorAll("label"));
  const label = labels.find((l) => l.textContent === labelText);
  if (!label) throw new Error("label not found: " + labelText);
  const input = label.parentElement?.querySelector("input");
  if (!input) throw new Error("input not found for " + labelText);
  return input as HTMLInputElement;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("项1：4 步状态机 + 第 0 步六个方向层数空恒显示", () => {
  it("4 步指示器 + footer step<3 下一步 / step===3 保存；六个 x/y/z 负正层数空恒显示（无 2D/3D toggle）", () => {
    renderDialog([mkCell({ u: "10" })]);
    expect(screen.getByText("类型与尺寸")).toBeTruthy();
    expect(screen.getByText("材料与曲面")).toBeTruthy();
    expect(screen.getByText("画布涂色")).toBeTruthy();
    expect(screen.getByText("保存")).toBeTruthy();
    // 六个方向层数空恒显示（z 也在），footer 无「保存并写入」
    expect(numInput("x 向左")).toBeTruthy();
    expect(numInput("x 向右")).toBeTruthy();
    expect(numInput("y 向前")).toBeTruthy();
    expect(numInput("y 向后")).toBeTruthy();
    expect(numInput("z 向下")).toBeTruthy();
    expect(numInput("z 向上")).toBeTruthy();
    expect(screen.queryByText("保存并写入栅元卡")).toBeNull();
    // 无 2D/3D toggle、无单独轴向层数 k
    expect(screen.queryByText("2D 平面")).toBeNull();
    expect(screen.queryByText("3D 体积")).toBeNull();
    expect(screen.queryByText("轴向层数 k")).toBeNull();
    // 切六棱柱 → 水平/斜向（a1/a2 格矢）层数取环数（从矩形 8/8 派生 → 8），轴向 k 仍在
    fireEvent.click(screen.getByText("六棱柱 (lat=2)"));
    expect(numInput("水平 向左").value).toBe("8");
    expect(numInput("水平 向右").value).toBe("8");
    expect(numInput("斜向 向左下").value).toBe("8");
    expect(numInput("斜向 向右上").value).toBe("8");
    expect(numInput("轴向 向下")).toBeTruthy();
  });

  it("下一步 x3 → 保存步出现「保存并写入栅元卡」，上一步回退", () => {
    renderDialog([mkCell({ u: "10" })]);
    fireEvent.click(screen.getByText("下一步"));
    expect(screen.getByText("自动生成宏体")).toBeTruthy(); // step 1 材料与曲面
    fireEvent.click(screen.getByText("下一步"));
    expect(screen.getByText(/调色板/)).toBeTruthy(); // step 2 画布涂色 + 调色板同屏
    fireEvent.click(screen.getByText("下一步"));
    expect(screen.getByText("保存并写入栅元卡")).toBeTruthy(); // step 3 保存摘要
    fireEvent.click(screen.getByText("上一步"));
    expect(screen.getByText(/调色板/)).toBeTruthy();
  });
});

describe("项2：第 0 步方向块数 -N:M", () => {
  it("x/y/z 负正方向块数输入存在（非列数/行数）", () => {
    renderDialog([]);
    expect(numInput("x 向左")).toBeTruthy();
    expect(numInput("x 向右")).toBeTruthy();
    expect(numInput("y 向前")).toBeTruthy();
    expect(numInput("y 向后")).toBeTruthy();
    expect(screen.queryByText("列数 (i)")).toBeNull();
    expect(screen.queryByText("行数 (j)")).toBeNull();
  });
});

describe("项6/7：调色板与画布同屏 + void 恒首位", () => {
  it("调色板含 void(0)+U=10；点 void 色块 → 涂色笔切换 → 画布涂 void", () => {
    renderDialog([mkCell({ u: "10" })]);
    fireEvent.click(screen.getByText("画布涂色"));
    expect(screen.getByTestId("palette-0")).toBeTruthy(); // void 恒首位
    expect(screen.getByTestId("palette-10")).toBeTruthy();
    const cell0 = screen.getByTestId("lcell-0");
    expect(cell0.getAttribute("aria-label")).toBe("格位 0 U=10"); // 默认涂色笔 U=10
    fireEvent.click(screen.getByTestId("palette-0")); // 切到 void 笔
    fireEvent.click(screen.getByTestId("lcell-0"));
    expect(screen.getByTestId("lcell-0").getAttribute("aria-label")).toBe("格位 0 U=0");
  });

  it("调色板来源合并：deck u= ∪ fill_grid cells[].u（17×17 样例 → 0/1/2/3/10）", () => {
    const fg = JSON.stringify({
      lat: "1", kind: "lattice", range: ["0:16", "0:16", "0:0"], dims: [17, 17, 1],
      cells: [{ u: "1", dx: "", dy: "", dz: "" }, { u: "2", dx: "", dy: "", dz: "" }, { u: "3", dx: "", dy: "", dz: "" }, { u: "0", dx: "", dy: "", dz: "" }],
      raw: "",
    });
    renderDialog([mkCell({ u: "10", fill_grid: fg })]);
    fireEvent.click(screen.getByText("画布涂色"));
    for (const u of ["0", "1", "2", "3", "10"]) {
      expect(screen.getByTestId(`palette-${u}`)).toBeTruthy();
    }
    expect(screen.queryByTestId("palette-5")).toBeNull();
  });
});

describe("项3/4：自动生成宏体互斥 + RHP 双模式", () => {
  it("自动模式显示宏体参数 + RHP 模式 B/A 切换 + 生成只读表达式", () => {
    renderDialog([]);
    fireEvent.click(screen.getByText("六棱柱 (lat=2)")); // step 0 选六棱柱
    fireEvent.click(screen.getByText("下一步")); // step 0 → step 1 材料与曲面
    expect(screen.getByText("自动生成宏体")).toBeTruthy();
    expect(screen.getByText("手动填写曲面")).toBeTruthy();
    expect(screen.getByText("模式 B：中心+外接半径+高")).toBeTruthy();
    expect(screen.getByText("模式 A：三点+高度")).toBeTruthy();
    fireEvent.click(screen.getByText("模式 A：三点+高度"));
    expect(numInput("Vx")).toBeTruthy();
    expect(numInput("Mz")).toBeTruthy();
  });
});

describe("项12：大格阵体积告警（保存摘要非阻塞提示）", () => {
  it("x 向右 99 + y 向后 99 → 10000 格位 → 保存摘要显示「格阵体积过大」", () => {
    renderDialog([mkCell({ u: "10" })]);
    fireEvent.change(numInput("x 向右"), { target: { value: "99" } });
    fireEvent.change(numInput("y 向后"), { target: { value: "99" } });
    fireEvent.click(screen.getByText("保存"));
    expect(screen.getByText(/格阵体积过大/)).toBeTruthy();
  });
});

describe("项13：保存前循环嵌套检测 → 阻止保存", () => {
  it("deck cells 存在 U=1→U=2→U=1 循环 → alert + onSave 不调用", () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    const { onSave } = renderDialog([
      mkCell({ num: "11", u: "1", fill: "2" }),
      mkCell({ num: "21", u: "2", fill: "1" }),
    ]);
    fireEvent.click(screen.getByText("保存")); // 跳保存摘要步
    fireEvent.click(screen.getByText("保存并写入栅元卡"));
    expect(alertSpy).toHaveBeenCalledWith(expect.stringContaining("循环嵌套"));
    expect(onSave).not.toHaveBeenCalled();
    alertSpy.mockRestore();
  });

  it("无环 deck → 保存正常回调 onSave", () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    const { onSave } = renderDialog([mkCell({ u: "10" })]);
    fireEvent.click(screen.getByText("保存"));
    fireEvent.click(screen.getByText("保存并写入栅元卡"));
    expect(alertSpy).not.toHaveBeenCalled();
    expect(onSave).toHaveBeenCalledTimes(1);
    alertSpy.mockRestore();
  });
});
