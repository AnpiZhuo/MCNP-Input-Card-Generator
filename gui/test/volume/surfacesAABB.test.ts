import { describe, it, expect } from "vitest";
import { computeSurfacesAABB, aabbToFmeshValues, formatCoord } from "../../src/volume/surfacesAABB";

/**
 * 按几何自动填充（PM 指令 2026-08-14：傻瓜友好改造）。
 * computeSurfacesAABB(surfaces[, trCards]) → {min,max} | null：
 * - 解析曲面卡（平面/球/圆柱/宏体）取模型 x/y/z 最大范围（AABB）；
 * - 解不出（空/仅无限曲面/仅不可解类型/TR 未提供）返回 null，UI 提示。
 * aabbToFmeshValues 把 AABB 转成 ORIGIN + IMESH/JMESH/KMESH 填表值。
 */

describe("computeSurfacesAABB · 平面 → 正确 AABB", () => {
  it("PX/PY/PZ 六面界定盒", () => {
    const text = [
      "1 PX -10", "2 PX 10",
      "3 PY -20", "4 PY 20",
      "5 PZ -5", "6 PZ 5",
    ].join("\n");
    expect(computeSurfacesAABB(text)).toEqual({
      min: { x: -10, y: -20, z: -5 }, max: { x: 10, y: 20, z: 5 },
    });
  });

  it("带 */+ 前缀的反射/白边界平面同样解析", () => {
    const text = "*1 PX -10\n+2 PX 10\n*3 PY -20\n4 PY 20\n5 PZ -5\n6 PZ 5";
    expect(computeSurfacesAABB(text)).toEqual({
      min: { x: -10, y: -20, z: -5 }, max: { x: 10, y: 20, z: 5 },
    });
  });
});

describe("computeSurfacesAABB · 球面", () => {
  it("SO 原点球 ±R", () => {
    expect(computeSurfacesAABB("1 SO 30")).toEqual({
      min: { x: -30, y: -30, z: -30 }, max: { x: 30, y: 30, z: 30 },
    });
  });

  it("一般球面 S cx cy cz R", () => {
    expect(computeSurfacesAABB("1 S 10 20 30 5")).toEqual({
      min: { x: 5, y: 15, z: 25 }, max: { x: 15, y: 25, z: 35 },
    });
  });

  it("SX/SY/SZ 轴上球", () => {
    expect(computeSurfacesAABB("1 SX 10 5")).toEqual({
      min: { x: 5, y: -5, z: -5 }, max: { x: 15, y: 5, z: 5 },
    });
  });
});

describe("computeSurfacesAABB · 圆柱", () => {
  it("CZ 圆柱 + PZ 端盖 → x/y 限半径，z 限端盖", () => {
    const text = "1 CZ 8\n2 PZ -5\n3 PZ 5";
    expect(computeSurfacesAABB(text)).toEqual({
      min: { x: -8, y: -8, z: -5 }, max: { x: 8, y: 8, z: 5 },
    });
  });

  it("C/Z 偏移圆柱 + PZ 端盖", () => {
    const text = "1 C/Z 2 3 4\n2 PZ -5\n3 PZ 5";
    // C/Z 2 3 4：x ∈ [-2,6], y ∈ [-1,7]，z 自由；PZ ±5 限 z
    expect(computeSurfacesAABB(text)).toEqual({
      min: { x: -2, y: -1, z: -5 }, max: { x: 6, y: 7, z: 5 },
    });
  });

  it("CX/CY/CZ 单轴柱 + 两侧端盖", () => {
    const text = "1 CY 3\n2 PX -2\n3 PX 2\n4 PY -5\n5 PY 5";
    // CY 3：x/z 限 ±3，y 自由；PX ±2 限 x；PY ±5 限 y
    expect(computeSurfacesAABB(text)).toEqual({
      min: { x: -3, y: -5, z: -3 }, max: { x: 3, y: 5, z: 3 },
    });
  });
});

describe("computeSurfacesAABB · 宏体", () => {
  it("RPP 直接取角点", () => {
    expect(computeSurfacesAABB("1 RPP -1 2 -3 4 -5 6")).toEqual({
      min: { x: -1, y: -3, z: -5 }, max: { x: 2, y: 4, z: 6 },
    });
  });

  it("SPH 宏体球", () => {
    expect(computeSurfacesAABB("1 SPH 0 0 5 10")).toEqual({
      min: { x: -10, y: -10, z: -5 }, max: { x: 10, y: 10, z: 15 },
    });
  });

  it("RCC 圆柱宏体（底面 + 轴矢量 + 半径）", () => {
    const text = "1 RCC 0 -5 0  0 10 0  4";
    expect(computeSurfacesAABB(text)).toEqual({
      min: { x: -4, y: -9, z: -4 }, max: { x: 4, y: 9, z: 4 },
    });
  });
});

describe("computeSurfacesAABB · 混合合并取最大范围", () => {
  it("平面 + 圆柱合并", () => {
    const text = "1 PX -10\n2 PX 10\n3 CZ 20\n4 PZ -5\n5 PZ 5";
    expect(computeSurfacesAABB(text)).toEqual({
      min: { x: -20, y: -20, z: -5 }, max: { x: 20, y: 20, z: 5 },
    });
  });
});

describe("computeSurfacesAABB · 无法解出 → null", () => {
  it("空文本 / 纯注释 → null", () => {
    expect(computeSurfacesAABB("")).toBeNull();
    expect(computeSurfacesAABB("   \nC comment line\n")).toBeNull();
  });

  it("只有一般平面（无限）→ null", () => {
    expect(computeSurfacesAABB("1 P 1 0 0 -5")).toBeNull();
  });

  it("只有 GQ/SQ（二次型系数非坐标）→ null", () => {
    expect(computeSurfacesAABB("1 GQ 1 1 1 0 0 0 0 0 0 -1")).toBeNull();
  });

  it("单独无限圆柱（某轴无界）→ null", () => {
    expect(computeSurfacesAABB("1 CZ 8")).toBeNull();
  });

  it("引用了未提供 TR 卡的曲面 → 跳过 → null", () => {
    expect(computeSurfacesAABB("1 7 PX 5")).toBeNull();
  });

  it("非法数值曲面 → 跳过 → null", () => {
    expect(computeSurfacesAABB("1 SO abc")).toBeNull();
  });
});

describe("computeSurfacesAABB · TR 变换", () => {
  it("带 TR 平移的六面盒正确平移", () => {
    const text = [
      "1 7 PX -10", "2 7 PX 10",
      "3 7 PY -20", "4 7 PY 20",
      "5 7 PZ -5", "6 7 PZ 5",
    ].join("\n");
    const trCards = "TR7 10 0 0";
    expect(computeSurfacesAABB(text, trCards)).toEqual({
      min: { x: 0, y: -20, z: -5 }, max: { x: 20, y: 20, z: 5 },
    });
  });

  it("*TR 角度模式旋转不崩溃且给出有界结果", () => {
    const text = "1 7 PX 5";
    const trCards = "*TR7 10 20 30  45 90 90  90 45 90  90 90 45";
    const aabb = computeSurfacesAABB(text, trCards);
    expect(aabb).not.toBeNull();
    const p = aabb!.max;
    expect([p.x, p.y, p.z].every(Number.isFinite)).toBe(true);
  });
});

describe("formatCoord / aabbToFmeshValues", () => {
  it("formatCoord 去掉多余尾零", () => {
    expect(formatCoord(-100)).toBe("-100");
    expect(formatCoord(10)).toBe("10");
    expect(formatCoord(2.5)).toBe("2.5");
    expect(formatCoord(0)).toBe("0");
  });

  it("aabbToFmeshValues → ORIGIN + IMESH/JMESH/KMESH 填表值", () => {
    const v = aabbToFmeshValues({ min: { x: -10, y: -20, z: -5 }, max: { x: 10, y: 20, z: 5 } });
    expect(v.origin).toBe("-10 -20 -5");
    expect(v.imesh).toBe("10");
    expect(v.jmesh).toBe("20");
    expect(v.kmesh).toBe("5");
  });
});
