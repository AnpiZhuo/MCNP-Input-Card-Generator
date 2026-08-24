/**
 * lattice 深模块纯函数测试（含跨语言 golden 断言）。
 *
 * golden = gui/src/utils/__golden__/latticeGolden.json（单一权威数据集，
 * Python test_lattice.py 与 TS 读同一 JSON 断言）。
 */
import { describe, expect, it } from "vitest";
import {
  autoGenerateSurfaces,
  buildUniversePalette,
  cellsToRaw,
  estimateLatticeExtent,
  getUniverseColor,
  hexCenter,
  hexGrid,
  hexRingCellCount,
  hexRingRows,
  initialHexCells,
  initialRectCells,
  latticeMismatchMessage,
  maxSurfaceNumber,
  parseFillGrid,
  rectGrid,
  rangeFromDims,
  resizeLatticeCells,
  serializeFillGrid,
  UNIVERSE_GRAY,
  UNIVERSE_PALETTE_12,
} from "../src/utils/lattice";
import golden from "../src/utils/__golden__/latticeGolden.json";

describe("parseFillGrid / serializeFillGrid（镜像 Python to_json/from_json）", () => {
  it("round-trip 键序与结构一致", () => {
    const fg = {
      lat: "1",
      kind: "lattice",
      range: ["0:16", "0:16", "0:0"],
      dims: [17, 17, 1],
      cells: [{ u: "1", dx: "", dy: "", dz: "" }, { u: "2", dx: "9", dy: "0", dz: "9" }],
      raw: "0:16 0:16 0:0 1 2 (9 0 9)",
    };
    const json = serializeFillGrid(fg);
    // 键序与 Python to_json 逐字一致（lat/kind/range/dims/cells/raw）
    expect(Object.keys(JSON.parse(json))).toEqual(["lat", "kind", "range", "dims", "cells", "raw"]);
    const back = parseFillGrid(json);
    expect(back).toEqual(fg);
  });

  it("脏 JSON → null", () => {
    expect(parseFillGrid("")).toBeNull();
    expect(parseFillGrid("not-json")).toBeNull();
    expect(parseFillGrid("null")).toBeNull();
    expect(parseFillGrid("[1,2]")).toBeNull();
    expect(parseFillGrid("")).toBeNull();
  });

  it("cells 反算覆盖 raw（range token 前置）", () => {
    const fg = {
      lat: "1", kind: "lattice", range: ["0:1", "0:1", "0:0"], dims: [2, 2, 1],
      cells: [{ u: "1", dx: "", dy: "", dz: "" }, { u: "2", dx: "9", dy: "0", dz: "9" }, { u: "1", dx: "", dy: "", dz: "" }, { u: "2", dx: "", dy: "", dz: "" }],
      raw: "",
    };
    expect(cellsToRaw(fg)).toBe("0:1 0:1 0:0 1 2 (9 0 9) 1 2");
  });
});

describe("rectGrid（行主序 i 最快）", () => {
  const g = golden.rectGrid;
  it("count = dims 乘积", () => {
    expect(rectGrid(g.dims).count).toBe(2 * 3 * 4);
  });
  it("golden idxOf 查询一致", () => {
    const rg = rectGrid(g.dims);
    for (const q of g.queries) {
      expect(rg.idxOf(q.i, q.j, q.k)).toBe(q.expectedIdx);
    }
  });
  it("coordsOf 是 idxOf 逆映射", () => {
    const rg = rectGrid([3, 4, 5]);
    for (let idx = 0; idx < rg.count; idx++) {
      const [i, j, k] = rg.coordsOf(idx);
      expect(rg.idxOf(i, j, k)).toBe(idx);
    }
  });
});

describe("hexRingRows（蜂窝环行长）", () => {
  it("golden 行模式与总和一致", () => {
    for (const c of golden.hexRingRows) {
      const rows = hexRingRows(c.rings);
      expect(rows).toEqual(c.rows);
      expect(rows.reduce((a, b) => a + b, 0)).toBe(c.total);
      expect(hexRingCellCount(c.rings)).toBe(c.total);
    }
  });
});

describe("hexCenter（pointy-top 顶点朝 +X，画布与阶段3共用）", () => {
  it("golden 坐标一致", () => {
    for (const c of golden.hexCenter) {
      const p = hexCenter(c.col, c.row, c.pitch);
      expect(p.x).toBeCloseTo(c.x, 9);
      expect(p.y).toBeCloseTo(c.y, 9);
    }
  });
  it("奇数行 +x 偏置 pitch/2", () => {
    expect(hexCenter(0, 1, 2).x).toBeCloseTo(1, 9);
    expect(hexCenter(2, 1, 2).x).toBeCloseTo(5, 9);
  });
});

describe("hexGrid（矩形交错蜂窝）", () => {
  it("2×2 阵列（fixtures/hex_lattice.inp dims=[2,2,1]）位置对齐", () => {
    const cells = hexGrid([2, 2, 1], 2);
    expect(cells).toHaveLength(4);
    expect(cells[0]).toMatchObject({ idx: 0, col: 0, row: 0, x: 0, y: 0 });
    expect(cells[1]).toMatchObject({ idx: 1, col: 1, row: 0, x: 2, y: 0 });
    expect(cells[2].idx).toBe(2);
    expect(cells[2].x).toBeCloseTo(1, 9); // row1 偏置
    expect(cells[3]).toMatchObject({ idx: 3, col: 1, row: 1 });
  });
  it("行主序 i 最快：idx 与 (col,row,layer) 一致", () => {
    const cells = hexGrid([3, 2, 2], 1);
    expect(cells).toHaveLength(12);
    cells.forEach((c) => {
      const expected = c.col + 3 * (c.row + 2 * c.layer);
      expect(c.idx).toBe(expected);
    });
  });
});

describe("宇宙调色板", () => {
  it("u 数值升序取 12 色板；排除 void(0)/空", () => {
    const p = buildUniversePalette(["10", "0", "", "2", "10", "1"]);
    expect(Object.keys(p)).toEqual(["1", "2", "10"]);
    expect(p["1"]).toBe(UNIVERSE_PALETTE_12[0]);
    expect(p["2"]).toBe(UNIVERSE_PALETTE_12[1]);
    expect(p["10"]).toBe(UNIVERSE_PALETTE_12[2]);
  });
  it("getUniverseColor 未命中回退灰", () => {
    const p = { "1": "#123456" };
    expect(getUniverseColor("1", p)).toBe("#123456");
    expect(getUniverseColor("99", p)).toBe(UNIVERSE_GRAY);
  });
});

describe("estimateLatticeExtent", () => {
  it("矩形按 dims（单位 pitch）", () => {
    const fg = parseFillGrid(serializeFillGrid({ lat: "1", kind: "lattice", range: ["0:16", "0:16", "0:0"], dims: [17, 17, 1], cells: [], raw: "" }))!;
    expect(estimateLatticeExtent(fg)).toEqual({ x: 17, y: 17, z: 1 });
  });
  it("六棱柱取蜂窝外沿", () => {
    const fg = parseFillGrid(serializeFillGrid({ lat: "2", kind: "lattice", range: ["0:2", "0:2", "0:0"], dims: [3, 3, 1], cells: [], raw: "" }))!;
    const e = estimateLatticeExtent(fg);
    expect(e.x).toBeCloseTo(3.0, 9); // maxX=2.5（row1 col2 偏置）+ 0.5 半格距
    expect(e.y).toBeCloseTo(1.7320508075688772 + 0.8660254037844386, 9);
  });
  it("null / translated 兜底", () => {
    expect(estimateLatticeExtent(null)).toEqual({ x: 0, y: 0, z: 0 });
  });
});

describe("初始格位 + 尺寸保持", () => {
  it("initialRectCells 行主序填 defaultU", () => {
    const cells = initialRectCells(2, 2, 1, "3");
    expect(cells).toHaveLength(4);
    expect(cells.every((c) => c.u === "3")).toBe(true);
  });
  it("initialHexCells 环形角位补 void(0)", () => {
    const cells = initialHexCells(1, 1, "1");
    expect(cells).toHaveLength(9); // 3×3 盒
    expect(cells[2].u).toBe("0"); // 角位
    expect(cells[8].u).toBe("0");
    expect(cells[0].u).toBe("1"); // 环内
    expect(cells[4].u).toBe("1");
  });
  it("resizeLatticeCells 保持已涂色格位", () => {
    const prev = [{ u: "9", dx: "", dy: "", dz: "" }, { u: "8", dx: "", dy: "", dz: "" }];
    const fresh = initialRectCells(3, 1, 1, "1");
    const next = resizeLatticeCells(prev, fresh);
    expect(next).toHaveLength(3);
    expect(next[0].u).toBe("9");
    expect(next[1].u).toBe("8");
    expect(next[2].u).toBe("1");
  });
  it("rangeFromDims 与 maxSurfaceNumber", () => {
    expect(rangeFromDims([17, 17, 1])).toEqual(["0:16", "0:16", "0:0"]);
    expect(maxSurfaceNumber("1 px -5\n2 px 5\n")).toBe(2);
  });
});

describe("autoGenerateSurfaces（自动生成平面）", () => {
  it("矩形：6 平面 PX/PY/PZ，盒内 +低 -高", () => {
    const r = autoGenerateSurfaces("1", { rect: { L: 20, W: 20, H: 10, cx: 0, cy: 0, cz: 0 } }, "");
    expect(r.lines).toHaveLength(6);
    expect(r.surfaceExpr).toBe("+1 -2 +3 -4 +5 -6");
    expect(r.surfacesText).toContain("1  px  -10");
    expect(r.surfacesText).toContain("2  px  10");
  });
  it("六棱柱：6 侧 P 全负 + 顶 PZ 负 + 底 PZ 正（backend 校验一正一负）", () => {
    const r = autoGenerateSurfaces("2", { hex: { side: 2, H: 2, cx: 0, cy: 0, cz: 0 } }, "");
    expect(r.lines).toHaveLength(8);
    expect(r.surfaceExpr).toBe("-1 -2 -3 -4 -5 -6 -7 +8");
    expect(r.surfacesText).toContain("7  pz  1");
    expect(r.surfacesText).toContain("8  pz  -1");
  });
  it("编号从既有曲面卡最大号顺延", () => {
    const r = autoGenerateSurfaces("1", { rect: { L: 2, W: 2, H: 2, cx: 0, cy: 0, cz: 0 } }, "10 rpp -1 1 -1 1 -1 1");
    expect(r.surfaceExpr).toBe("+11 -12 +13 -14 +15 -16");
  });
});

describe("latticeMismatchMessage（QA 建议3 提示）", () => {
  it("条目流≠dims 乘积时给警告", () => {
    expect(latticeMismatchMessage([3, 3, 1], Array(7).fill({ u: "1" }))).toContain("3×3×1");
    expect(latticeMismatchMessage([2, 2, 1], Array(4).fill({ u: "1" }))).toBeNull();
  });
});

describe("跨语言 golden validate 段（backend 权威规则，TS 结构 + 非法字符判定）", () => {
  it("数组非空、结构完整", () => {
    const v = golden.validate as any[];
    expect(v.length).toBeGreaterThan(0);
    for (const s of v) {
      expect(["1", "2"]).toContain(s.lat);
      expect(typeof s.surfaceExpr).toBe("string");
      expect(typeof s.expectedOk).toBe("boolean");
      if (typeof s.surfacesText !== "undefined") expect(typeof s.surfacesText).toBe("string");
      if (s.expectedOk) expect(s.expectedMsg).toBe("");
    }
  });
  it("surfaceExpr 含 # / : / 括号 → expectedOk 必为 false", () => {
    for (const s of golden.validate as any[]) {
      if (/[#:()]/.test(s.surfaceExpr)) {
        expect(s.expectedOk).toBe(false);
      }
    }
  });
});
