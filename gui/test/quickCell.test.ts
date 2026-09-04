import { describe, it, expect } from "vitest";
import {
  appendCardText,
  applyQuickAddChoice,
  generatedCellToRow,
  generateQuickCell,
  nextCellNumber,
  nextSurfaceNumber,
  nextTrNumber,
  quickCellCounts,
  parseAngleExpr,
  trBFromAngles,
  validateQuickCell,
  densityForMaterial,
  type RccConfig,
  type RppConfig,
  type SphConfig,
  type HexConfig,
  type TetConfig,
} from "../src/utils/quickCell";

const emptyCtx = { surfacesText: "", trCardsText: "", cellNumbers: [] };

describe("编号规则", () => {
  it("曲面：无输入 101 起，有输入取最大+1", () => {
    expect(nextSurfaceNumber("")).toBe(101);
    expect(nextSurfaceNumber("1 px -9\n12 py 3 $ 注释\nc 注释行")).toBe(13);
    expect(nextSurfaceNumber("101 rpp 0 1 0 1 0 1")).toBe(102);
  });

  it("TR：无输入 1 起，有输入取最大+1（含 *TR 形式）", () => {
    expect(nextTrNumber("")).toBe(1);
    expect(nextTrNumber("TR1 0 0 0 1 0 0 0 1 0 0 0 1")).toBe(2);
    expect(nextTrNumber("TR3 0 0 0 1 0 0 0 1 0 0 0 1\n*TR7 1 2 3 0 1 0 -1 0 0 0 0 1")).toBe(8);
  });

  it("cell：无输入 1 起，有输入取最大+1", () => {
    expect(nextCellNumber([])).toBe(1);
    expect(nextCellNumber([5, 42])).toBe(43);
  });
});

describe("校验", () => {
  it("RCC 非法输入报错", () => {
    expect(validateQuickCell("rcc", { center: [0, 0, 0], axis: [0, 0, 1], radius: 0, rings: 2, segments: 2 })).toMatch(/半径/);
    expect(validateQuickCell("rcc", { center: [0, 0, 0], axis: [0, 0, 0], radius: 1, rings: 2, segments: 2 })).toMatch(/轴向向量/);
    expect(validateQuickCell("rcc", { center: [0, 0, 0], axis: [0, 0, 1], radius: 1, rings: 0, segments: 2 })).toMatch(/环数/);
    expect(validateQuickCell("rcc", { center: [0, 0, 0], axis: [0, 0, 1], radius: 1, rings: 2, segments: 1.5 })).toMatch(/段数/);
  });

  it("SPH 非法输入报错", () => {
    expect(validateQuickCell("sph", { center: [0, 0, 0], radius: -1, shells: 2 })).toMatch(/半径/);
    expect(validateQuickCell("sph", { center: [0, 0, 0], radius: 5, shells: 0 })).toMatch(/球壳数/);
  });

  it("RPP 尺寸/中心/角度/份数校验", () => {
    const good = { size: [2, 2, 2] as [number, number, number], center: [0, 0, 0] as [number, number, number], angles: [0, 0, 0] as [number, number, number], nx: 1, ny: 1, nz: 1 };
    expect(validateQuickCell("rpp", { ...good, size: [0, 2, 2] } as any)).toMatch(/长\/宽\/高/);
    expect(validateQuickCell("rpp", { ...good, size: [2, -1, 2] } as any)).toMatch(/长\/宽\/高/);
    expect(validateQuickCell("rpp", { ...good, center: [NaN, 0, 0] } as any)).toMatch(/中心坐标/);
    expect(validateQuickCell("rpp", { ...good, angles: [0, Infinity, 0] } as any)).toMatch(/倾斜角度/);
    expect(validateQuickCell("rpp", { ...good, nx: 0 } as any)).toMatch(/X 方向/);
    expect(validateQuickCell("rpp", { ...good, ny: 1.5 } as any)).toMatch(/Y 方向/);
    expect(validateQuickCell("rpp", good)).toBeNull();
  });
});

describe("RCC 生成", () => {
  const cfg: RccConfig = { center: [0, 0, 0], axis: [0, 0, 10], radius: 2, rings: 2, segments: 3 };

  it("曲面卡：N 个 RCC + M-1 个轴向 P 平面，编号从 101 起", () => {
    const r = generateQuickCell("rcc", cfg, emptyCtx);
    expect(r.surfacesText).toContain("101 rcc 0 0 0 0 0 10 1");
    expect(r.surfacesText).toContain("102 rcc 0 0 0 0 0 10 2");
    expect(r.surfacesText).toContain("103 p 0 0 1 3.333333");
    expect(r.surfacesText).toContain("104 p 0 0 1 6.666667");
    expect(r.trCardsText).toBe("");
    expect(r.surfaceCount).toBe(4);
    expect(r.cellCount).toBe(6);
  });

  it("栅元：核心环 -RCC，外环 +内 -外；轴向段首段 -P、末段 +P、中段 +P -P", () => {
    const r = generateQuickCell("rcc", cfg, emptyCtx);
    const exprs = r.cells.map((c) => c.surfaces);
    expect(exprs).toEqual([
      "-101 -103",
      "-101 +103 -104",
      "-101 +104",
      "+101 -102 -103",
      "+101 -102 +103 -104",
      "+101 -102 +104",
    ]);
    expect(r.cells[0].num).toBe("1");
    expect(r.cells[5].num).toBe("6");
    expect(r.cells[5].comment).toBe("RCC 环2/2 段3/3");
    expect(r.cells[0].mat).toBe("0"); // 默认真空
    expect(r.cells[0].density).toBe("");
  });

  it("用户已有曲面/cell 时编号顺延", () => {
    const r = generateQuickCell("rcc", cfg, {
      surfacesText: "200 rcc 0 0 0 0 0 5 1\n201 pz 3",
      trCardsText: "",
      cellNumbers: [10, 11],
    });
    expect(r.surfacesText).toContain("202 rcc 0 0 0 0 0 10 1");
    expect(r.cells[0].num).toBe("12");
  });
});

describe("SPH 生成", () => {
  const cfg: SphConfig = { center: [1, 2, 3], radius: 6, shells: 3 };

  it("K 个同心球面 + K 个球壳栅元", () => {
    const r = generateQuickCell("sph", cfg, emptyCtx);
    expect(r.surfacesText).toContain("101 sph 1 2 3 2");
    expect(r.surfacesText).toContain("102 sph 1 2 3 4");
    expect(r.surfacesText).toContain("103 sph 1 2 3 6");
    expect(r.cells.map((c) => c.surfaces)).toEqual(["-101", "+101 -102", "+102 -103"]);
    expect(r.cells.map((c) => c.comment)).toEqual(["SPH 壳1/3", "SPH 壳2/3", "SPH 壳3/3"]);
    expect(r.cellCount).toBe(3);
  });
});

describe("HEX 六棱柱生成（RHP 宏体）", () => {
  const cfg: HexConfig = { center: [0, 0, 0], axis: [0, 0, 10], radius: 2, rings: 2, segments: 3 };

  it("RHP 宏体（V H R1，轴 +Z → R1 沿 +X=apothem）+ 轴向 P 平面", () => {
    const r = generateQuickCell("hex", cfg, emptyCtx);
    // apothem = radius·√3/2 ≈ 1.732051；环1 apothem/rings、环2 apothem（同心递增，同 RCC 环）
    expect(r.surfacesText).toContain("101 rhp 0 0 0  0 0 10  0.866025 0 0");
    expect(r.surfacesText).toContain("102 rhp 0 0 0  0 0 10  1.732051 0 0");
    expect(r.surfacesText).toContain("103 p 0 0 1 3.333333");
    expect(r.surfacesText).toContain("104 p 0 0 1 6.666667");
    expect(r.trCardsText).toBe("");
    expect(r.surfaceCount).toBe(4);
    expect(r.cellCount).toBe(6);
  });

  it("栅元表达式与 RCC 同构（核心环 -RHP，外环 +内 -外；段首 -P、末 +P、中 +P -P）", () => {
    const r = generateQuickCell("hex", cfg, emptyCtx);
    expect(r.cells.map((c) => c.surfaces)).toEqual([
      "-101 -103",
      "-101 +103 -104",
      "-101 +104",
      "+101 -102 -103",
      "+101 -102 +103 -104",
      "+101 -102 +104",
    ]);
    expect(r.cells[5].comment).toBe("RHP 环2/2 段3/3");
  });

  it("校验：radius/轴向/环/段", () => {
    expect(validateQuickCell("hex", { center: [0, 0, 0], axis: [0, 0, 1], radius: -1, rings: 2, segments: 2 })).toMatch(/半径/);
    expect(validateQuickCell("hex", { center: [0, 0, 0], axis: [0, 0, 0], radius: 1, rings: 2, segments: 2 })).toMatch(/轴向向量/);
    expect(validateQuickCell("hex", { center: [0, 0, 0], axis: [0, 0, 1], radius: 1, rings: 0, segments: 2 })).toMatch(/环数/);
    expect(validateQuickCell("hex", { center: [0, 0, 0], axis: [0, 0, 1], radius: 1, rings: 2, segments: 1.5 })).toMatch(/段数/);
  });
});

describe("TET 四面体生成（4 顶点）", () => {
  // 单位四面体：A(0,0,0) B(1,0,0) C(0,1,0) D(0,0,1)
  const cfg: TetConfig = {
    p1: [0, 0, 0], p2: [1, 0, 0], p3: [0, 1, 0], p4: [0, 0, 1],
  };

  it("4 个 P 平面，法向朝向体内；栅元 = +p1 +p2 +p3 +p4", () => {
    const r = generateQuickCell("tet", cfg, emptyCtx);
    expect(r.surfaceCount).toBe(4);
    expect(r.cellCount).toBe(1);
    // 面 ABC(法向 z 朝上 +)，ABD(法向 +Y)，ACD(法向 +X)，BCD(法向 −(1,1,1))
    expect(r.surfacesText).toContain("101 p 0 0 1 0");
    expect(r.surfacesText).toContain("102 p 0 1 0 0");
    expect(r.surfacesText).toContain("103 p 1 0 0 0");
    expect(r.surfacesText).toContain("104 p -0.57735 -0.57735 -0.57735 -0.57735"); // 法向归一化 (−1,−1,−1)/√3
    expect(r.cells[0].surfaces).toBe("+101 +102 +103 +104");
    expect(r.cells[0].comment).toBe("TET 四面体");
  });

  it("校验：非有限坐标 / 四点共面（退化）", () => {
    expect(validateQuickCell("tet", { p1: [0, 0, 0], p2: [1, 0, 0], p3: [0, 1, 0], p4: [NaN, 0, 0] })).toMatch(/有效数字/);
    // 四点共面（z 全 0 → 体积 0）
    expect(validateQuickCell("tet", { p1: [0, 0, 0], p2: [1, 0, 0], p3: [0, 1, 0], p4: [1, 1, 0] })).toMatch(/共面\/退化/);
    expect(validateQuickCell("tet", cfg)).toBeNull();
  });
});

describe("RPP 生成", () => {
  it("轴对齐：RPP + 内部 PX/PY/PZ，无 TR", () => {
    const r = generateQuickCell("rpp", { size: [2, 2, 2], center: [0, 0, 0], angles: [0, 0, 0], nx: 2, ny: 2, nz: 1 }, emptyCtx);
    expect(r.surfacesText).toContain("101 rpp -1 1 -1 1 -1 1");
    expect(r.surfacesText).toContain("102 px 0");
    expect(r.surfacesText).toContain("103 py 0");
    expect(r.trCardsText).toBe("");
    expect(r.cells.map((c) => c.surfaces)).toEqual([
      "-101 -102 -103",
      "-101 -102 +103",
      "-101 +102 -103",
      "-101 +102 +103",
    ]);
    expect(r.cells.map((c) => c.comment)).toEqual([
      "RPP 1/2 1/2 1/1",
      "RPP 1/2 2/2 1/1",
      "RPP 2/2 1/2 1/1",
      "RPP 2/2 2/2 1/1",
    ]);
    expect(r.cellCount).toBe(4);
  });

  it("倾斜（Yaw 90°）：6 个局部平面 + *TRn + TR 卡（B 矩阵行=局部轴方向余弦）", () => {
    const r = generateQuickCell("rpp", { size: [2, 2, 2], center: [10, 0, 0], angles: [0, 0, Math.PI / 2], nx: 2, ny: 1, nz: 1 }, emptyCtx);
    expect(validateQuickCell("rpp", { size: [2, 2, 2], center: [10, 0, 0], angles: [0, 0, Math.PI / 2], nx: 2, ny: 1, nz: 1 })).toBeNull();
    expect(r.trCardsText).toContain("TR1 10 0 0 0 1 0 -1 0 0 0 0 1");
    expect(r.surfacesText).toContain("101 px -1 *TR1");
    expect(r.surfacesText).toContain("102 px 1 *TR1");
    expect(r.surfacesText).toContain("103 py -1 *TR1");
    expect(r.surfacesText).toContain("104 py 1 *TR1");
    expect(r.surfacesText).toContain("105 pz -1 *TR1");
    expect(r.surfacesText).toContain("106 pz 1 *TR1");
    expect(r.surfacesText).toContain("107 px 0 *TR1");
    expect(r.surfacesText).not.toContain("rpp");
    expect(r.cells.map((c) => c.surfaces)).toEqual([
      "+101 -107 +103 -104 +105 -106",
      "+107 -102 +103 -104 +105 -106",
    ]);
    expect(r.cellCount).toBe(2);
    expect(r.surfaceCount).toBe(7);
  });

  it("用户已有 TR 时编号顺延", () => {
    const r = generateQuickCell("rpp", { size: [2, 2, 2], center: [0, 0, 0], angles: [0, 0, 1], nx: 1, ny: 1, nz: 1 }, {
      surfacesText: "", trCardsText: "TR4 1 0 0 0 1 0 0 0 1 0 0 0", cellNumbers: [],
    });
    expect(r.trCardsText).toContain("TR5 ");
  });
});

describe("角度解析与 TR B 矩阵", () => {
  it("parseAngleExpr：支持 π 表达式与普通数字", () => {
    expect(parseAngleExpr("π/2")).toBeCloseTo(Math.PI / 2);
    expect(parseAngleExpr("2π")).toBeCloseTo(2 * Math.PI);
    expect(parseAngleExpr("π")).toBeCloseTo(Math.PI);
    expect(parseAngleExpr("45")).toBe(45);
    expect(parseAngleExpr("1.5")).toBe(1.5);
    expect(parseAngleExpr("")).toBeNull();
    expect(parseAngleExpr("abc")).toBeNull();
    expect(parseAngleExpr("π/")).toBeNull();
  });

  it("trBFromAngles：行 = 局部轴方向余弦（R 的列）", () => {
    const round = (v: number[]) => v.map((x) => Math.round(x * 1e9) / 1e9);
    expect(round(trBFromAngles([0, 0, 0]))).toEqual([1, 0, 0, 0, 1, 0, 0, 0, 1]);
    // Yaw 90°（绕 Z）：局部 X→全局 Y，局部 Y→全局 −X
    expect(round(trBFromAngles([0, 0, Math.PI / 2]))).toEqual([0, 1, 0, -1, 0, 0, 0, 0, 1]);
    // Roll 90°（绕 X）：局部 Y→全局 Z，局部 Z→全局 −Y
    expect(round(trBFromAngles([Math.PI / 2, 0, 0]))).toEqual([1, 0, 0, 0, 0, 1, 0, -1, 0]);
  });
});

describe("材料/密度/imp", () => {
  it("选材料且有密度 → 自动带出；材料无密度 → 留空", () => {
    const ctx = {
      surfacesText: "", trCardsText: "", cellNumbers: [],
      materials: [{ number: 1, density: "-7.87" }, { number: 2, density: "" }],
      material: "1",
    };
    const r = generateQuickCell("sph", { center: [0, 0, 0], radius: 1, shells: 1 }, ctx);
    expect(r.cells[0].density).toBe("-7.87");
    expect(densityForMaterial("2", ctx.materials)).toBe("");
  });

  it("imp 填数值写 IMP:N=值（含 0），留空按基础页模式填 1", () => {
    const r = generateQuickCell("sph", { center: [0, 0, 0], radius: 1, shells: 1 }, {
      ...emptyCtx, material: "0", impN: "0", impP: "", impE: "0",
      modeN: false, modeP: true, modeE: true,
    });
    // 填了 0 → 写 0
    expect(r.cells[0].impN).toBe("0");
    expect(r.cells[0].impE).toBe("0");
    // 留空 + 基础页启用该粒子 → 1
    expect(r.cells[0].impP).toBe("1");
  });

  it("imp 留空且基础页未启用该粒子 → 留空", () => {
    const r = generateQuickCell("sph", { center: [0, 0, 0], radius: 1, shells: 1 }, {
      ...emptyCtx, material: "0", impN: "", impP: "", impE: "",
      modeN: true, modeP: false, modeE: false,
    });
    expect(r.cells[0].impN).toBe("1");
    expect(r.cells[0].impP).toBe("");
    expect(r.cells[0].impE).toBe("");
  });
});

describe("数量预览", () => {
  it("quickCellCounts 与生成一致", () => {
    expect(quickCellCounts("rcc", { center: [0, 0, 0], axis: [0, 0, 1], radius: 1, rings: 4, segments: 3 }))
      .toEqual({ surfaceCount: 6, cellCount: 12 });
    expect(quickCellCounts("sph", { center: [0, 0, 0], radius: 1, shells: 5 }))
      .toEqual({ surfaceCount: 5, cellCount: 5 });
    expect(quickCellCounts("rpp", { size: [2, 2, 2], center: [0, 0, 0], angles: [0, 0, 0], nx: 2, ny: 3, nz: 4 }))
      .toEqual({ surfaceCount: 1 + 1 + 2 + 3, cellCount: 24 });
    expect(quickCellCounts("rpp", { size: [2, 2, 2], center: [0, 0, 0], angles: [0, 0, 1], nx: 2, ny: 3, nz: 4 }))
      .toEqual({ surfaceCount: 6 + 1 + 2 + 3, cellCount: 24 });
    expect(quickCellCounts("hex", { center: [0, 0, 0], axis: [0, 0, 1], radius: 1, rings: 4, segments: 3 }))
      .toEqual({ surfaceCount: 6, cellCount: 12 });
    expect(quickCellCounts("tet", { p1: [0, 0, 0], p2: [1, 0, 0], p3: [0, 1, 0], p4: [0, 0, 1] }))
      .toEqual({ surfaceCount: 4, cellCount: 1 });
  });
});

describe("applyQuickAddChoice 重合决策（含多栅元）", () => {
  const existing = [
    { num: 5, mat: "1", surfaces: "-1" },
    { num: 7, mat: "2", surfaces: "-2" },
    { num: 9, mat: "0", surfaces: "-3" },   // 真空
  ];

  function mkResult(newCells: { num: string; surfaces: string }[]): any {
    return {
      surfacesText: "", trCardsText: "", surfaceCount: 0, cellCount: newCells.length,
      cells: newCells.map(c => ({ num: c.num, mat: "1", density: "-1", surfaces: c.surfaces, comment: "" })),
    };
  }

  it("new_hole：新栅元追加 # 全部重合已有栅元（多栅元各自追加）", () => {
    const r = mkResult([{ num: "10", surfaces: "-10" }, { num: "11", surfaces: "-11" }]);
    const out = applyQuickAddChoice(r, [
      { a: 10, b: 5 }, { a: 11, b: 7 }, { a: 11, b: 9 },
    ], existing, "new_hole");
    expect(out.cells[0].surfaces).toBe("-10 #5");
    expect(out.cells[1].surfaces).toBe("-11 #7 #9");
    expect(out.existingExprPatch).toBeUndefined();
  });

  it("existing_hole：全部被侵占栅元（含真空）让位 # 新栅元", () => {
    const r = mkResult([{ num: "10", surfaces: "-10" }]);
    const out = applyQuickAddChoice(r, [{ a: 10, b: 5 }, { a: 10, b: 9 }], existing, "existing_hole");
    expect(out.cells[0].surfaces).toBe("-10");
    expect(out.existingExprPatch).toEqual([
      { num: "5", surfaces: "-1 #10" },
      { num: "9", surfaces: "-3 #10" },
    ]);
  });

  it("void_only：真空栅元让位 # 新；新栅元只 # 非真空", () => {
    const r = mkResult([{ num: "10", surfaces: "-10" }, { num: "11", surfaces: "-11" }]);
    const out = applyQuickAddChoice(r, [
      { a: 10, b: 5 }, { a: 10, b: 9 }, { a: 11, b: 9 },
    ], existing, "void_only");
    expect(out.cells[0].surfaces).toBe("-10 #5");   // 只 # 材料 5
    expect(out.cells[1].surfaces).toBe("-11");       // 只与真空 9 重合 → 不加 #
    expect(out.existingExprPatch).toEqual([
      { num: "9", surfaces: "-3 #10 #11" },          // 真空 9 让位给 10、11
    ]);
  });

  it("none：不改动", () => {
    const r = mkResult([{ num: "10", surfaces: "-10" }]);
    const out = applyQuickAddChoice(r, [{ a: 10, b: 5 }], existing, "none");
    expect(out.cells[0].surfaces).toBe("-10");
    expect(out.existingExprPatch).toBeUndefined();
  });
});

describe("填入逻辑（曲面/TR 文本追加 + 栅元行映射）", () => {
  it("appendCardText：两块之间只保留一个换行，空块不追加", () => {
    expect(appendCardText("", "101 px 0\n")).toBe("101 px 0\n");
    expect(appendCardText("101 px 0\n", "TR1 0 0 0 1 0 0 0 1 0 0 0 1\n"))
      .toBe("101 px 0\nTR1 0 0 0 1 0 0 0 1 0 0 0 1\n");
    expect(appendCardText("101 px 0", "102 py 1\n")).toBe("101 px 0\n102 py 1\n");
    expect(appendCardText("101 px 0", "")).toBe("101 px 0");
    expect(appendCardText("101 px 0\n\n", "102 py 1\n")).toBe("101 px 0\n102 py 1\n");
  });

  it("generatedCellToRow：映射为本地行（高级参数留空、render true）", () => {
    const row = generatedCellToRow({
      num: "3", mat: "1", density: "-7.87", surfaces: "-101 +102",
      impN: "1", impP: "", impE: "1", comment: "RPP 1/1 1/1 1/1",
    });
    expect(row.kind).toBe("cell");
    expect(row.cell.num).toBe("3");
    expect(row.cell.mat).toBe("1");
    expect(row.cell.density).toBe("-7.87");
    expect(row.cell.surfaces).toBe("-101 +102");
    expect(row.cell.impN).toBe("1");
    expect(row.cell.impP).toBe("");
    expect(row.cell.impE).toBe("1");
    expect(row.cell.comment).toBe("RPP 1/1 1/1 1/1");
    expect(row.cell.render).toBe(true);
    expect(row.cell.vol).toBe("");
    expect(row.cell.pwt).toBe("");
    expect(row.cell.trcl).toBe("");
    expect(row.cell.otherParams).toBe("");
  });
});
