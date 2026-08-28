/**
 * lattice 深模块纯函数测试（含跨语言 golden 断言）。
 *
 * golden = gui/src/utils/__golden__/latticeGolden.json（单一权威数据集，
 * Python test_lattice.py 与 TS 读同一 JSON 断言）。
 * Wave 2b：hexCenter 权威公式（项5 L1）+ 项2 dirCounts + 项3 macrobody +
 * 项4 rhpMacro + 项7 collectFillUniverses + 项12 compressRaw + 项13 cycle。
 */
import { describe, expect, it } from "vitest";
import {
  autoGenMacrobody,
  autoGenerateSurfaces,
  buildUniversePalette,
  cellsToRaw,
  collectFillUniverses,
  compressRaw,
  detectFillCycle,
  dirCountsFromRange,
  estimateLatticeExtent,
  getUniverseColor,
  hexCenter,
  hexGrid,
  hexLatticePitch,
  hexPrismCircumradius,
  hexRingCellCount,
  hexRingRows,
  inHexRing,
  initialHexCells,
  initialRectCells,
  latticeMismatchMessage,
  maxSurfaceNumber,
  parseFillGrid,
  rangeFromDirCounts,
  rectGrid,
  rangeFromDims,
  resizeLatticeCells,
  rhpCard,
  rhpFromCenterRadiusHeight,
  rhpFromThreePoints,
  rhpModeAError,
  serializeFillGrid,
  UNIVERSE_GRAY,
  UNIVERSE_PALETTE_12,
} from "../src/utils/lattice";
import golden from "../src/utils/__golden__/latticeGolden.json";

/** parse_fill_entries nR 展开（TS 测试镜像，验证 compressRaw 生产侧与后端消费侧等价） */
function expandRawTokens(tokens: string[]): string[] {
  const out: string[] = [];
  let prev = "";
  for (const t of tokens) {
    const m = t.match(/^(-?\d+)r$/);
    if (m) {
      const n = parseInt(m[1], 10);
      for (let i = 0; i < n; i++) out.push(prev);
    } else {
      out.push(t);
      prev = t;
    }
  }
  return out;
}

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

describe("hexRingRows（蜂窝环行长，项5 L2 语义=+30° 共线方向）", () => {
  it("golden 行模式与总和一致", () => {
    for (const c of golden.hexRingRows) {
      const rows = hexRingRows(c.rings);
      expect(rows).toEqual(c.rows);
      expect(rows.reduce((a, b) => a + b, 0)).toBe(c.total);
      expect(hexRingCellCount(c.rings)).toBe(c.total);
    }
  });
});

describe("hexCenter（项5 权威公式：顶点+X flat-top，x=i·p·√3/2, y=j·p+(i%2)·p/2）", () => {
  it("golden 坐标一致", () => {
    for (const c of golden.hexCenter) {
      const p = hexCenter(c.col, c.row, c.pitch);
      expect(p.x).toBeCloseTo(c.x, 9);
      expect(p.y).toBeCloseTo(c.y, 9);
    }
  });
  it("MCNP LAT=2 映射：x=(col+row/2)·pitch, y=row·pitch·√3/2", () => {
    expect(hexCenter(1, 0, 2).x).toBeCloseTo(2, 9); // (1+0)·2
    expect(hexCenter(1, 0, 2).y).toBeCloseTo(0, 9);
    expect(hexCenter(0, 1, 2).x).toBeCloseTo(1, 9); // (0+0.5)·2
    expect(hexCenter(0, 1, 2).y).toBeCloseTo(Math.sqrt(3), 9); // 1·2·√3/2
  });
  it("相邻格位边缘共享（真实蜂窝自洽）", () => {
    const d01 = Math.hypot(hexCenter(1, 0, 2).x - hexCenter(0, 0, 2).x, hexCenter(1, 0, 2).y - hexCenter(0, 0, 2).y);
    const d10 = Math.hypot(hexCenter(0, 1, 2).x - hexCenter(0, 0, 2).x, hexCenter(0, 1, 2).y - hexCenter(0, 0, 2).y);
    const d1m1 = Math.hypot(hexCenter(1, -1, 2).x - hexCenter(0, 0, 2).x, hexCenter(1, -1, 2).y - hexCenter(0, 0, 2).y);
    expect(d01).toBeCloseTo(2, 9);
    expect(d10).toBeCloseTo(2, 9);
    expect(d1m1).toBeCloseTo(2, 9);
  });
});

describe("hexGrid（矩形交错蜂窝，项5 新公式）", () => {
  it("2×2 阵列（fixtures/hex_lattice.inp dims=[2,2,1]）位置对齐", () => {
    const cells = hexGrid([2, 2, 1], 2);
    expect(cells).toHaveLength(4);
    // 居中偏移 (i-(nx-1)/2, j-(ny-1)/2)：nx=2 → co=0.5, ro=0.5
    expect(cells[0]).toMatchObject({ idx: 0, col: 0, row: 0, x: -1.5, y: -0.8660254037844386 });
    expect(cells[1]).toMatchObject({ idx: 1, col: 1, row: 0 });
    expect(cells[1].x).toBeCloseTo(0.5, 9); // (0.5+(-0.5)·0.5)·2
    expect(cells[1].y).toBeCloseTo(-0.8660254037844386, 9);
    expect(cells[2].idx).toBe(2);
    expect(cells[2].x).toBeCloseTo(-0.5, 9); // ((-0.5)+0.5·0.5)·2
    expect(cells[2].y).toBeCloseTo(0.8660254037844386, 9); // 0.5·2·√3/2
    expect(cells[3]).toMatchObject({ idx: 3, col: 1, row: 1, x: 1.5, y: 0.8660254037844386 });
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

describe("inHexRing（项5 蜂窝环内判定，替代旧 i<rowLens[j] 横向行）", () => {
  it("rings=1 六边形 = 7 格（水平行长 [2,3,2]，与 hexRingRows 一致）", () => {
    const inside: [number, number][] = [];
    for (let j = 0; j < 3; j++) {
      for (let i = 0; i < 3; i++) {
        if (inHexRing(i, j, 1)) inside.push([i, j]);
      }
    }
    expect(inside).toHaveLength(7);
    expect(new Set(inside.map(([a, b]) => `${a},${b}`))).toEqual(new Set(["0,1", "0,2", "1,0", "1,1", "1,2", "2,0", "2,1"]));
  });
  it("rings=2 六边形 = 19 格", () => {
    let n = 0;
    for (let j = 0; j < 5; j++) {
      for (let i = 0; i < 5; i++) {
        if (inHexRing(i, j, 2)) n++;
      }
    }
    expect(n).toBe(19);
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
  it("六棱柱取蜂窝外沿（项5 新公式 + 格元半宽/半高余量）", () => {
    const fg = parseFillGrid(serializeFillGrid({ lat: "2", kind: "lattice", range: ["0:2", "0:2", "0:0"], dims: [3, 3, 1], cells: [], raw: "" }))!;
    const e = estimateLatticeExtent(fg);
    // MCNP LAT=2：maxX=3（(2,2)）、maxY=√3（(*,2)）；x+=半宽 pitch/√3、y+=半高 pitch/2
    expect(e.x).toBeCloseTo(3 + 1 / Math.sqrt(3), 9);
    expect(e.y).toBeCloseTo(Math.sqrt(3) + 0.5, 9);
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
  it("initialHexCells 环形角位补 void(0)（项5 inHexRing，角位=(0,0)/(2,2)）", () => {
    const cells = initialHexCells(1, 1, "1");
    expect(cells).toHaveLength(9); // 3×3 盒
    expect(cells[0].u).toBe("0"); // 角位 (0,0)
    expect(cells[8].u).toBe("0"); // 角位 (2,2)
    expect(cells[2].u).toBe("1"); // (2,0) 环内
    expect(cells[4].u).toBe("1"); // 中心
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

describe("方向块数 → -N:M（项2 跨语言 L3）", () => {
  it("golden dirCounts 段一致（range 正向 + 反派生 + dims）", () => {
    for (const c of golden.dirCounts as any[]) {
      expect(rangeFromDirCounts(c.neg, c.pos)).toBe(c.range);
      const back = dirCountsFromRange(c.range);
      expect(back.neg).toBe(c.neg);
      expect(back.pos).toBe(c.pos);
      expect(back.dims).toBe(c.dims);
    }
  });
  it("rangeFromDims 保留（编辑旧 deck 反派生用）", () => {
    expect(rangeFromDims([17, 17, 1])).toEqual(["0:16", "0:16", "0:0"]);
  });
  it("非法 token 兜底 {0,0,1}", () => {
    expect(dirCountsFromRange("abc")).toEqual({ neg: 0, pos: 0, dims: 1 });
    expect(dirCountsFromRange("1:2:3")).toEqual({ neg: 0, pos: 0, dims: 1 });
  });
});

describe("autoGenMacrobody（项3 宏体自动生成，跨语言 L4）", () => {
  it("golden macrobody 段一致（编号 maxSurfaceNumber+1 顺延）", () => {
    const baseSurf = "1 px -5\n2 px 5\n3 py -5\n4 py 5\n5 pz 0";
    for (const c of golden.macrobody as any[]) {
      const params = c.lat === "2" ? { hex: c.params } : { rect: c.params };
      const r = autoGenMacrobody(c.lat, params, baseSurf);
      expect(r.card).toBe(c.expectedSurface);
      expect(r.surfaceExpr).toBe(c.expr);
      expect(r.line).toBe(`6 ${c.expectedSurface}`);
      expect(r.surfacesText).toContain(`6 ${c.expectedSurface}`);
    }
  });
  it("编号从既有曲面卡最大号顺延", () => {
    const r = autoGenMacrobody("1", { rect: { L: 2, W: 2, H: 2, cx: 0, cy: 0, cz: 0 } }, "10 rpp -1 1 -1 1 -1 1");
    expect(r.line).toBe("11 rpp -1 1 -1 1 -1 1");
    expect(r.surfaceExpr).toBe("-11");
  });
});

describe("autoGenerateSurfaces（旧 6 平面 / 6P 路径保留为「手动」可选项）", () => {
  it("矩形：6 平面 PX/PY/PZ，盒内 +低 -高", () => {
    const r = autoGenerateSurfaces("1", { rect: { L: 20, W: 20, H: 10, cx: 0, cy: 0, cz: 0 } }, "");
    expect(r.lines).toHaveLength(6);
    expect(r.surfaceExpr).toBe("+1 -2 +3 -4 +5 -6");
  });
  it("六棱柱：6 侧 P 全负 + 顶 PZ 负 + 底 PZ 正（backend 校验一正一负）", () => {
    const r = autoGenerateSurfaces("2", { hex: { side: 2, H: 2, cx: 0, cy: 0, cz: 0 } }, "");
    expect(r.lines).toHaveLength(8);
    expect(r.surfaceExpr).toBe("-1 -2 -3 -4 -5 -6 -7 +8");
  });
});

describe("RHP 宏体参数（项4 权威模式 B，跨语言 L4）", () => {
  it("golden rhpMacro 段：rhpFromCenterRadiusHeight + rhpCard", () => {
    for (const c of golden.rhpMacro as any[]) {
      const p = rhpFromCenterRadiusHeight(c.input.C, c.input.R, c.input.H);
      expect(rhpCard(p)).toBe(c.expectedCard);
    }
  });
  it("模式 A：三点 + 高度 → RHP（H=T−V，R1=M−V），校验通过", () => {
    const p = rhpFromThreePoints([0, 0, 0], [0, 0, 10], [0.866, 0.5, 0]);
    expect(rhpCard(p)).toBe("rhp 0 0 0  0 0 10  0.866 0.5 0");
    expect(rhpModeAError([0, 0, 0], [0, 0, 10], [0.866, 0.5, 0], 10)).toBeNull();
  });
  it("模式 A 校验：|T−V|≠h 报错；R1 不 ⊥H 报错", () => {
    expect(rhpModeAError([0, 0, 0], [0, 0, 8], [0.866, 0.5, 0], 10)).toContain("≠ 高度");
    expect(rhpModeAError([0, 0, 0], [0, 0, 10], [1, 0, 5], 10)).toContain("不垂直于轴向");
  });
  it("项16 方向：模式 B 第一面法向 0°（R1 ∥ a1，原 30° 几何错）", () => {
    const p = rhpFromCenterRadiusHeight([0, 0, 0], 2, 10);
    expect(p.r1[0]).toBeCloseTo(2 * Math.cos(Math.PI / 6), 9); // apothem 沿 +x
    expect(p.r1[1]).toBeCloseTo(0, 9);
    expect(p.r1[2]).toBeCloseTo(0, 9);
    expect(rhpCard(p)).toBe("rhp 0 0 -5  0 0 10  1.732 0 0");
  });
});

describe("项16：宏体尺寸随格阵（OWEN 模式：包住 fill 平行四边形全部格位）", () => {
  it("hexPrismCircumradius 恰好包住格阵四角 + 单格外接半径", () => {
    // i/j ±8，格距 2：角格 (8,8) 距 = hypot(2·8+8, 8·√3) = hypot(24, 13.856)=27.713
    const R = hexPrismCircumradius(-8, 8, -8, 8, 2);
    expect(R).toBeCloseTo(Math.hypot(24, 8 * Math.sqrt(3)) + 2 / Math.sqrt(3), 9);
  });
  it("R→格距→R 往返自洽（六棱柱面切最外圈格子外缘）", () => {
    const R0 = hexPrismCircumradius(-8, 8, -8, 8, 2);
    const p = hexLatticePitch((R0 * Math.sqrt(3)) / 2, -8, 8, -8, 8);
    const R1 = hexPrismCircumradius(-8, 8, -8, 8, p);
    expect(R1).toBeCloseTo(R0, 6);
  });
  it("六棱柱面法向 0°/60°/120°（autoGenerateSurfaces 对齐 a1）", () => {
    const r = autoGenerateSurfaces("2", { hex: { side: 2, H: 2, cx: 0, cy: 0, cz: 0 } }, "");
    const nx = r.lines.slice(0, 6).map((l) => l.split(/\s+/)[2]);
    expect(nx[0]).toBe("1"); // 面 1 法向 (1,0) = 0°
    expect(nx[1]).toBe("0.5"); // 面 2 法向 60°
    expect(nx[2]).toBe("-0.5"); // 面 3 法向 120°
  });
});

describe("collectFillUniverses（项7 调色板来源合并）", () => {
  it("golden 段一致（17×17 合并 → [0,1,2,3,10] / 空 deck / 脏 JSON）", () => {
    for (const c of golden.collectFillUniverses as any[]) {
      expect(collectFillUniverses(c.deckCells)).toEqual(c.expected);
    }
  });
  it("deck u= 去重 + void 恒首位 + fill_grid cells[].u 并入", () => {
    const fg = serializeFillGrid({ lat: "1", kind: "lattice", range: ["0:1", "0:1", "0:0"], dims: [2, 2, 1], cells: [{ u: "2", dx: "", dy: "", dz: "" }, { u: "3", dx: "", dy: "", dz: "" }], raw: "" });
    expect(collectFillUniverses([{ u: "10" }, { u: "2" }, { u: "10" }, { u: "0" }, { u: "", fill_grid: fg }])).toEqual(["0", "2", "3", "10"]);
  });
});

describe("compressRaw（项12 nR 压缩，跨语言 L8）", () => {
  it("golden compressRaw 段一致（runs → u nR；幂等不动点）", () => {
    for (const c of golden.compressRaw as any[]) {
      expect(compressRaw(c.tokens)).toBe(c.expected);
    }
  });
  it("连续 run 回缩 + parse 往返等价（与 parse_fill_entries 的 nR=再重复 n 次一致）", () => {
    const first = compressRaw(["1", "1", "1", "2", "2"]);
    expect(first).toBe("1 2r 2 1r");
    expect(compressRaw(first)).toBe("1 2r 2 1r"); // 再压缩 = 同串（幂等不动点）
    expect(expandRawTokens(first.split(" "))).toEqual(["1", "1", "1", "2", "2"]);
  });
});

describe("detectFillCycle（项13 循环嵌套检测，跨语言 L6）", () => {
  it("golden cycle 段一致（cycle_a_b_a / no_cycle_tree）", () => {
    for (const c of golden.cycle as any[]) {
      expect(detectFillCycle(c.sub_by_u)).toEqual(c.expected);
    }
  });
  it("自环 A→A 判环", () => {
    const r = detectFillCycle({ "1": [{ cellNum: 1, material: "0", fill: "1", fill_grid: null }] });
    expect(r.cycle).toBe(true);
    expect(r.chain).toEqual(["1", "1"]);
  });
  it("fill_grid cells[].u 引用判环（U1 格阵填 U2，U2 单值填 U1）", () => {
    const fg = serializeFillGrid({ lat: "1", kind: "lattice", range: ["0:0", "0:0", "0:0"], dims: [1, 1, 1], cells: [{ u: "2", dx: "", dy: "", dz: "" }], raw: "" });
    const r = detectFillCycle({
      "1": [{ cellNum: 5, material: "0", fill: "", fill_grid: fg }],
      "2": [{ cellNum: 6, material: "0", fill: "1", fill_grid: null }],
    });
    expect(r.cycle).toBe(true);
    expect(r.chain).toEqual(["1", "2", "1"]);
  });
  it("fill=0 / 空 不构成边；三元环判出", () => {
    expect(detectFillCycle({ "1": [{ cellNum: 1, material: "0", fill: "0", fill_grid: null }] })).toEqual({ cycle: false, chain: [] });
    const r = detectFillCycle({
      "1": [{ cellNum: 1, material: "0", fill: "2", fill_grid: null }],
      "2": [{ cellNum: 2, material: "0", fill: "3", fill_grid: null }],
      "3": [{ cellNum: 3, material: "0", fill: "1", fill_grid: null }],
    });
    expect(r.cycle).toBe(true);
    expect(r.chain).toEqual(["1", "2", "3", "1"]);
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
  it("宏体样例 expectedOk=true（lat1_rpp_macro / lat2_rhp_macro）", () => {
    const rpp = (golden.validate as any[]).find((s) => s.id === "lat1_rpp_macro");
    const rhp = (golden.validate as any[]).find((s) => s.id === "lat2_rhp_macro");
    expect(rpp.expectedOk).toBe(true);
    expect(rhp.expectedOk).toBe(true);
  });
});
