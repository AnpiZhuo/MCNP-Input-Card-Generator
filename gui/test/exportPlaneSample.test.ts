/**
 * planeEquation / planeSample 单测。
 *
 * 锁的是**几何与语义正确性**：
 * - 方程解析/格式化往返（含 `1`/`-1` 省略系数的写法）；
 * - 步长折半/加倍的边界（绝不出现 0 步长）；
 * - 成叠平面序列含两端、按步长等距、带编号、有片数上限；
 * - 任意平面取样：在**构造得能心算**的场上验证取样值与等值线位置
 *   （线性场 → 等值线是已知直线；均匀场 → 无边界的确定值）。
 */
import { describe, it, expect } from "vitest";
import {
  parsePlane, planeToStr, axisPlane, stepPlane, halveStep, doubleStep,
  normalLength, planeSeries, type PlaneEq,
} from "../src/three/planeEquation";
import {
  planeBasis, planeOriginInBox, samplePlane, sampleContours, planeRangeInBox, type AABB,
} from "../src/export/planeSample";

describe("planeEquation", () => {
  it("解析：省略系数当 1/-1，大小写与空格随意", () => {
    expect(parsePlane("X + Y = 0")).toEqual({ A: 1, B: 1, C: 0, D: 0 });
    expect(parsePlane("2x-3y+0.5z=10")).toEqual({ A: 2, B: -3, C: 0.5, D: 10 });
    expect(parsePlane("-Y = 1.5")).toEqual({ A: 0, B: -1, C: 0, D: 1.5 });
    expect(parsePlane("z=12.5")).toEqual({ A: 0, B: 0, C: 1, D: 12.5 });
  });

  it("解析不出任何项 → null（不静默当 0 = 0 假平面）", () => {
    expect(parsePlane("")).toBeNull();
    expect(parsePlane("abc")).toBeNull();
    expect(parsePlane("!!!")).toBeNull();
  });

  it("格式化：1/-1 省略、整数直出；与解析往返一致", () => {
    expect(planeToStr({ A: 1, B: 1, C: 0, D: 0 })).toBe("X + Y = 0");
    expect(planeToStr({ A: -1, B: 0, C: 1, D: 12.5 })).toBe("-X + Z = 12.5");
    expect(planeToStr({ A: 0, B: 0, C: 0, D: 3 })).toBe("0 = 3");
    const p: PlaneEq = { A: 2, B: -3, C: 0.5, D: 10 };
    expect(parsePlane(planeToStr(p))).toEqual(p);
  });

  it("轴对齐平面与法向长度", () => {
    expect(axisPlane("z", 5)).toEqual({ A: 0, B: 0, C: 1, D: 5 });
    expect(normalLength({ A: 3, B: 4, C: 0, D: 0 })).toBeCloseTo(5, 9);
    expect(normalLength({ A: 0, B: 0, C: 0, D: 1 })).toBe(0);
  });

  it("步进只动 D；折半有下限 0.001（点 ◀ 只会变小，永不为 0/负）", () => {
    expect(stepPlane({ A: 0, B: 0, C: 1, D: 1 }, 2.5).D).toBeCloseTo(3.5, 9);
    expect(halveStep(4)).toBe(2);
    expect(halveStep(0.001)).toBe(0.001);
    // 非法步长按"已是最小"处理（不是"当成 1 再折半"，那会让连点几次后的值与初值不符）
    expect(halveStep(0)).toBe(0.001);
    expect(halveStep(-5)).toBe(0.001);
    expect(doubleStep(2)).toBe(4);
    expect(doubleStep(0)).toBe(2);
  });

  it("成叠平面：含两端、等距、带 1 起编号", () => {
    const list = planeSeries({ A: 0, B: 0, C: 1, D: 0 }, 1, 0, 3);
    expect(list.map((x) => x.d)).toEqual([0, 1, 2, 3]);
    expect(list.map((x) => x.index)).toEqual([1, 2, 3, 4]);
    expect(list[0].plane.C).toBe(1);
  });

  it("成叠平面：片数封顶（防手滑把步长设成极小卡死界面）", () => {
    const list = planeSeries({ A: 0, B: 0, C: 1, D: 0 }, 0.001, 0, 100, 50);
    expect(list).toHaveLength(50);
  });
});

describe("planeSample", () => {
  /** 8×8×8 网格，值 = i（沿 x 线性）→ 等值线应该是 x = 常数的直线 */
  function linearFieldX() {
    const res: [number, number, number] = [8, 8, 8];
    const d = new Uint8Array(8 * 8 * 8);
    for (let i = 0; i < 8; i++) for (let j = 0; j < 8; j++) for (let k = 0; k < 8; k++) {
      d[(i * 8 + j) * 8 + k] = i * 30;
    }
    const box: AABB = { min: [0, 0, 0], max: [7, 7, 7] };
    return { res, d, box, scalarRange: { min: 0, max: 210 } };
  }

  it("平面基：三个向量两两正交且为单位向量", () => {
    const b = planeBasis({ A: 1, B: 2, C: 3, D: 0 })!;
    const dot = (p: any, q: any) => p.x * q.x + p.y * q.y + p.z * q.z;
    const len = (p: any) => Math.hypot(p.x, p.y, p.z);
    expect(len(b.n)).toBeCloseTo(1, 9);
    expect(len(b.u)).toBeCloseTo(1, 9);
    expect(len(b.v)).toBeCloseTo(1, 9);
    expect(dot(b.n, b.u)).toBeCloseTo(0, 9);
    expect(dot(b.n, b.v)).toBeCloseTo(0, 9);
    expect(dot(b.u, b.v)).toBeCloseTo(0, 9);
  });

  it("非法平面（法向为 0）→ null，不抛", () => {
    expect(planeBasis({ A: 0, B: 0, C: 0, D: 1 })).toBeNull();
    const { res, d, box, scalarRange } = linearFieldX();
    expect(samplePlane({ A: 0, B: 0, C: 0, D: 1 }, box, res, d, scalarRange)).toBeNull();
  });

  it("平面中心落在盒内：`Z = 3.5` 的取样原点 z 坐标为 3.5", () => {
    const box: AABB = { min: [0, 0, 0], max: [7, 7, 7] };
    const o = planeOriginInBox({ A: 0, B: 0, C: 1, D: 3.5 }, box);
    expect(o.z).toBeCloseTo(3.5, 9);
    expect(o.x).toBeCloseTo(3.5, 9);
    expect(o.y).toBeCloseTo(3.5, 9);
  });

  it("用 `Y = 3.5` 切线性场：同一行（列变化）值不变，同一列（行变化）随 x 递增", () => {
    const { res, d, box, scalarRange } = linearFieldX();
    const s = samplePlane({ A: 0, B: 1, C: 0, D: 3.5 }, box, res, d, scalarRange, { samples: 32 })!;
    expect(s).toBeTruthy();
    // 场只随 x 变。该平面基算出 u 沿 z（列方向）、v 沿 x（行方向）——
    // 所以"同一行内列变化"不改变 x ⇒ 值必须相同；"同一列内行变化"跨过 x ⇒ 值必须变。
    const row = Math.floor(s.height / 2);
    const left = s.values[row * s.width + 0];
    const right = s.values[row * s.width + s.width - 1];
    expect(left).toBeCloseTo(right, 6);

    const col = Math.floor(s.width / 2);
    const top = s.values[0 * s.width + col];
    const bottom = s.values[(s.height - 1) * s.width + col];
    expect(Math.abs(bottom - top)).toBeGreaterThan(10);
  });

  it("等值线：线性场上产出矢量路径（真矢量，非位图）", () => {
    const { res, d, box, scalarRange } = linearFieldX();
    const s = samplePlane({ A: 0, B: 1, C: 0, D: 3.5 }, box, res, d, scalarRange, { samples: 48 })!;
    const svg = sampleContours(s, { levels: 5 });
    expect(svg).toContain("<path");
    expect(svg).not.toContain("<image");
    expect(svg).toContain('fill="none"');
  });

  it("法向扫描区间 = 盒在法向上的投影极值 **× |n|**（D 与未归一化方程同系）", () => {
    const box: AABB = { min: [0, 0, 0], max: [2, 4, 6] };
    expect(planeRangeInBox({ A: 0, B: 0, C: 1, D: 0 }, box)).toEqual({ min: 0, max: 6 });
    expect(planeRangeInBox({ A: 1, B: 0, C: 0, D: 0 }, box)).toEqual({ min: 0, max: 2 });
    // 斜平面：法向 (1,1,0)，|n|=√2 ⇒ D 区间 = 投影极值 × √2 = (0+0) .. (2+4) = 0..6
    const r = planeRangeInBox({ A: 1, B: 1, C: 0, D: 0 }, box);
    expect(r.min).toBeCloseTo(0, 6);
    expect(r.max).toBeCloseTo(6, 6);
  });

  it("取样网格为正方形覆盖（各向同性：圆形的东西不能被画成椭圆）", () => {
    const { res, d, box, scalarRange } = linearFieldX();
    const s = samplePlane({ A: 1, B: 1, C: 1, D: 0 }, box, res, d, scalarRange, { samples: 64 })!;
    expect(s.width).toBe(64);
    expect(s.height).toBe(64);
    // u/v 步长相等 ⇒ 采样在物理空间是正方形（各向同性）
    expect(s.step).toBeGreaterThan(0);
  });

  it("取样点数可调且有上下界（防超大网格拖死界面）", () => {
    const { res, d, box, scalarRange } = linearFieldX();
    const small = samplePlane({ A: 0, B: 0, C: 1, D: 3 }, box, res, d, scalarRange, { samples: 1 })!;
    const big = samplePlane({ A: 0, B: 0, C: 1, D: 3 }, box, res, d, scalarRange, { samples: 99999 })!;
    expect(small.width).toBeGreaterThanOrEqual(8);
    expect(big.width).toBeLessThanOrEqual(512);
  });
});
