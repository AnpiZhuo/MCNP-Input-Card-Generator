import { describe, it, expect } from "vitest";
import { fmeshKindControl } from "../../src/volume/FMeshForm";

/**
 * FMeshForm kind 控件降级（2026-08-14 用户决定：TMESH 计数卡创建/选择入口 UI 隐藏）。
 * FMESH → 可编辑下拉；TMESH（仅来自 INP 导入/后端 parse）→ 只读徽标，数据路径保留。
 */
describe("fmeshKindControl（kind 非 FMESH 的 UI 降级）", () => {
  it("FMESH → select（可编辑下拉）", () => {
    const c = fmeshKindControl("FMESH", "xyz");
    expect(c.control).toBe("select");
    expect(c.note).toBe("");
  });

  it("TMESH → badge（只读徽标）+ 数据原样保留说明", () => {
    const c = fmeshKindControl("TMESH", "xyz");
    expect(c.control).toBe("badge");
    expect(c.note).toContain("数据原样保留");
  });

  it("TMESH + geom=cyl → badge + cyl 不进入体积可视化说明", () => {
    const c = fmeshKindControl("TMESH", "cyl");
    expect(c.control).toBe("badge");
    expect(c.note).toContain("cyl");
    expect(c.note).toContain("不进入体积可视化");
  });
});
