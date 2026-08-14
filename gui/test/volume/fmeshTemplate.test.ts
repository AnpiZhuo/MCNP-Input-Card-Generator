import { describe, it, expect } from "vitest";
import {
  emptyFmeshRow,
  fmeshTemplates,
  fmeshToCardText,
  cardTextToFmesh,
  validateFmeshRow,
  gridCellCount,
  FMESH_MEMORY_WARNING_THRESHOLD,
  type FmeshRow,
} from "../../src/volume/fmeshState";

/**
 * FMESH 通用模板一键填充（PM 指令：通用模板两档，纯函数镜像后端契约）。
 *
 * apply 语义：
 * - 只覆盖网格字段（origin/imesh/iints/jmesh/jints/kmesh/kints）；
 * - geom/particle/number 仅在未填时给默认（XYZ / N / 4）；
 * - 其余字段（emesh/emints/tmesh/tmints/mat/out/axs/vec/tr/raw/kind）保持用户已填值不变。
 */

function row(partial: Partial<FmeshRow>): FmeshRow {
  return { ...emptyFmeshRow(), ...partial };
}

describe("fmeshTemplates · 结构（两档，id/label/hint/apply）", () => {
  it("导出两档模板，字段齐备", () => {
    expect(fmeshTemplates.length).toBe(2);
    for (const t of fmeshTemplates) {
      expect(typeof t.id).toBe("string");
      expect(typeof t.label).toBe("string");
      expect(typeof t.hint).toBe("string");
      expect(typeof t.apply).toBe("function");
      expect(t.id.length).toBeGreaterThan(0);
      expect(t.label.length).toBeGreaterThan(0);
    }
    const ids = fmeshTemplates.map((t) => t.id);
    expect(ids).toContain("minimal");
    expect(ids).toContain("starter");
  });
});

describe("fmeshTemplates · 两档网格字段值", () => {
  it("最小可用档：1×1×1 单网格（先验证卡能跑通）", () => {
    const r = fmeshTemplates.find((t) => t.id === "minimal")!.apply(row({}));
    expect(r.origin).toBe("-100 -100 -150");
    expect(r.imesh).toBe("100");
    expect(r.iints).toBe("1");
    expect(r.jmesh).toBe("100");
    expect(r.jints).toBe("1");
    expect(r.kmesh).toBe("50");
    expect(r.kints).toBe("1");
    expect(gridCellCount(r)).toBe(1);
  });

  it("通用起步档：20×20×10 = 4000 单元", () => {
    const r = fmeshTemplates.find((t) => t.id === "starter")!.apply(row({}));
    expect(r.origin).toBe("-100 -100 -150");
    expect(r.imesh).toBe("100");
    expect(r.iints).toBe("20");
    expect(r.jmesh).toBe("100");
    expect(r.jints).toBe("20");
    expect(r.kmesh).toBe("50");
    expect(r.kints).toBe("10");
    expect(gridCellCount(r)).toBe(4000);
  });
});

describe("fmeshTemplates · apply 语义", () => {
  it("空行 apply：number 默认 4、particle 默认 N、geom 默认 XYZ，kind 保持 FMESH", () => {
    for (const t of fmeshTemplates) {
      const r = t.apply(emptyFmeshRow());
      expect(r.number).toBe("4");
      expect(r.particle).toBe("N");
      expect(r.geom).toBe("XYZ");
      expect(r.kind).toBe("FMESH");
    }
  });

  it("保留用户已填非网格字段（emesh/emints/tmesh/tmints/mat/out/axs/vec/tr/raw）", () => {
    const filled = row({
      number: "7",
      particle: "P",
      geom: "CYL",
      emesh: "1e-6 1 14", emints: "2 2",
      tmesh: "1 10", tmints: "2",
      mat: "3",
      out: "CF",
      axs: "0 0 1",
      vec: "1 0 0",
      tr: "5",
      raw: "FMESH7:P GEOM=CYL",
    });
    for (const t of fmeshTemplates) {
      const r = t.apply(filled);
      // 已填编号/粒子/几何保留（不覆盖用户数据）
      expect(r.number).toBe("7");
      expect(r.particle).toBe("P");
      expect(r.geom).toBe("CYL");
      expect(r.emesh).toBe("1e-6 1 14");
      expect(r.emints).toBe("2 2");
      expect(r.tmesh).toBe("1 10");
      expect(r.tmints).toBe("2");
      expect(r.mat).toBe("3");
      expect(r.out).toBe("CF");
      expect(r.axs).toBe("0 0 1");
      expect(r.vec).toBe("1 0 0");
      expect(r.tr).toBe("5");
      expect(r.raw).toBe("FMESH7:P GEOM=CYL");
      expect(r.kind).toBe("FMESH");
      // 网格字段仍被模板覆盖
      expect(r.imesh).toBe("100");
      expect(r.kints).toBe(t.id === "minimal" ? "1" : "10");
    }
  });

  it("apply 不修改入参行（纯函数，不原地改）", () => {
    const input = row({ emesh: "1 14", emints: "2", out: "COL" });
    const snapshot = JSON.stringify(input);
    fmeshTemplates[0].apply(input);
    fmeshTemplates[1].apply(input);
    expect(JSON.stringify(input)).toBe(snapshot);
  });
});

describe("fmeshTemplates · 结果通过 validateFmeshRow", () => {
  it("两档 apply 后无 error/warning（单元格数 ≤ 128³ 阈值）", () => {
    for (const t of fmeshTemplates) {
      const r = t.apply(emptyFmeshRow());
      expect(validateFmeshRow(r)).toEqual([]);
      const cells = gridCellCount(r);
      expect(cells).not.toBeNull();
      expect(cells!).toBeLessThanOrEqual(FMESH_MEMORY_WARNING_THRESHOLD);
    }
  });

  it("对已填非网格字段的行 apply 后，网格相关校验仍干净", () => {
    const tpl = fmeshTemplates.find((t) => t.id === "starter")!;
    // emesh 2 个边界值 ↔ emints 2 个条目数（token 数须一一对应，镜像 validateFmeshRow 规则）
    const r = tpl.apply(row({
      emesh: "1 14", emints: "2 2",
      out: "CF", mat: "0",
    }));
    expect(validateFmeshRow(r)).toEqual([]);
  });
});

describe("fmeshTemplates · 卡体 round-trip", () => {
  it("apply 结果生成合法卡体（5 空格续行），可解析回同字段", () => {
    for (const t of fmeshTemplates) {
      const r = t.apply(emptyFmeshRow());
      const text = fmeshToCardText([r]);
      // 卡头 + 5 空格续行格式（合法 MCNP 卡体）
      expect(text).toContain("FMESH4:N GEOM=XYZ ORIGIN=-100 -100 -150");
      expect(text).toMatch(/^     IMESH=100/m);
      expect(text).toMatch(/^     IINTS=/m);
      expect(text).toMatch(/^     JMESH=100/m);
      expect(text).toMatch(/^     JINTS=/m);
      expect(text).toMatch(/^     KMESH=50/m);
      expect(text).toMatch(/^     KINTS=/m);
      // 解析回同字段
      const back = cardTextToFmesh(text);
      expect(back.length).toBe(1);
      const b = back[0];
      expect(b.number).toBe("4");
      expect(b.particle).toBe("N");
      expect(b.geom).toBe("XYZ");
      expect(b.origin).toBe("-100 -100 -150");
      expect(b.imesh).toBe(r.imesh);
      expect(b.iints).toBe(r.iints);
      expect(b.jmesh).toBe(r.jmesh);
      expect(b.jints).toBe(r.jints);
      expect(b.kmesh).toBe(r.kmesh);
      expect(b.kints).toBe(r.kints);
    }
  });

  it("带已填非网格字段 apply 后 round-trip 保留这些字段", () => {
    const tpl = fmeshTemplates.find((t) => t.id === "starter")!;
    const r = tpl.apply(row({ emesh: "1e-6 1 14", emints: "2 2", mat: "3", out: "CF" }));
    const back = cardTextToFmesh(fmeshToCardText([r]))[0];
    expect(back.emesh).toBe("1e-6 1 14");
    expect(back.emints).toBe("2 2");
    expect(back.mat).toBe("3");
    expect(back.out).toBe("CF");
    expect(back.imesh).toBe("100");
    expect(back.iints).toBe("20");
  });
});
