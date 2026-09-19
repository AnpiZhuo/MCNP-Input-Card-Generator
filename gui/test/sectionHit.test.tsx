// @vitest-environment jsdom
/**
 * 截面悬停读数（2026-09-19 用户实测：**图形正常但材料号不对**）。
 *
 * 真实现象（q1112 卡，X=0 平面）：栅元 2（水，r≤1）与栅元 3（钢，r≤4）在中心重叠，
 * 图上**后声明的钢盘盖住水芯**，悬停却报 `2 · M1` —— 因为旧命中检测从数组头
 * 找"第一个包含点的多边形"，而第一个正是最先声明、视觉上被盖住的那个。
 *
 * 本文件锁两条不变量：
 *  1. `topMostHit` 返回的是**绘制次序里最后**（= 视觉最上层）那个包含点的栅元；
 *  2. `topMostHit` 报的那个栅元，与**渲染出来的 SVG 里最后一个覆盖该点的 `<polygon>`**
 *     所属栅元一致 —— 即"读数与图形同源"，改绘制次序时读数自动跟随。
 */
import { describe, it, expect } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import React from "react";
import CrossSectionView from "../src/components/CrossSectionView";
import { paintOrder, pointInPolygon, topMostHit } from "../src/utils/sectionHit";

/** 生成一个以 (cx,cy) 为心、半径 r 的正 n 边形（2D） */
function disk(cx: number, cy: number, r: number, n = 64) {
  const pts: { x: number; y: number }[] = [];
  for (let i = 0; i < n; i++) {
    const t = (2 * Math.PI * i) / n;
    pts.push({ x: cx + r * Math.cos(t), y: cy + r * Math.sin(t) });
  }
  return pts;
}

describe("sectionHit 纯函数", () => {
  it("paintOrder 按声明次序排（不改入参）", () => {
    const cells = [{ number: 12 }, { number: 2 }, { number: 3 }];
    const out = paintOrder(cells, [2, 3, 12]);
    expect(out.map((c) => c.number)).toEqual([2, 3, 12]);
    expect(cells.map((c) => c.number)).toEqual([12, 2, 3]); // 入参未被改
  });

  it("声明次序缺失时保持原相对次序（稳定）", () => {
    const cells = [{ number: 7 }, { number: 8 }];
    expect(paintOrder(cells, []).map((c) => c.number)).toEqual([7, 8]);
    expect(paintOrder(cells, [99]).map((c) => c.number)).toEqual([7, 8]);
  });

  it("pointInPolygon 基本正确（含边界外）", () => {
    const sq = [{ x: 0, y: 0 }, { x: 2, y: 0 }, { x: 2, y: 2 }, { x: 0, y: 2 }];
    expect(pointInPolygon(sq, 1, 1)).toBe(true);
    expect(pointInPolygon(sq, 3, 1)).toBe(false);
  });

  it("★回归：中心点同时落在两个盘里时，报**最后**（最上层）那个", () => {
    // 数组次序 = 绘制次序：cell2 画在下面，cell3 画在上面
    const cells = [
      { number: 2, material: "1", poly: disk(0, 0, 1.0) },   // 水芯
      { number: 3, material: "2", poly: disk(0, 0, 4.0) },   // 钢盘（盖住水芯）
    ];
    const hit = topMostHit(cells, (c) => [c.poly], 0, 0);
    expect(hit?.number).toBe(3);
    expect(hit?.material).toBe("2");
    // 水芯旁边（钢盘内、水芯外）仍然只能报钢
    expect(topMostHit(cells, (c) => [c.poly], 2, 0)?.number).toBe(3);
    // 两个盘都够不着 → null
    expect(topMostHit(cells, (c) => [c.poly], 9, 9)).toBeNull();
  });

  it("★红能力证明：旧实现（从头找第一个命中）在中心报 2，新实现报 3", () => {
    const cells = [
      { number: 2, poly: disk(0, 0, 1.0) },
      { number: 3, poly: disk(0, 0, 4.0) },
    ];
    /** 旧实现原样复刻（2026-09-19 修改前的 CrossSectionView 内联逻辑） */
    const oldHit = (px: number, py: number) => {
      for (const cd of cells) {
        if (pointInPolygon(cd.poly, px, py)) return cd.number;
      }
      return null;
    };
    expect(oldHit(0, 0)).toBe(2);                                   // 旧：报被盖住的水芯
    expect(topMostHit(cells, (c) => [c.poly], 0, 0)?.number).toBe(3); // 新：报画在上面的钢盘
  });

  it("不被更早声明的盘抢答（旧实现就是被它抢的）", () => {
    const cells = [
      { number: 3, material: "2", poly: disk(0, 0, 4.0) },
      { number: 2, material: "1", poly: disk(0, 0, 1.0) }, // 后声明 ⇒ 画在上面 ⇒ 该报它
    ];
    expect(topMostHit(cells, (c) => [c.poly], 0, 0)?.number).toBe(2);
  });
});

describe("CrossSectionView 悬停读数与图形同源", () => {
  /** q1112 卡在 X=0 平面上"中间那截"的极简复刻：钢盘 M2 盖住水芯 M1 */
  const slices = [
    { number: 2, material: "1", polygons: [disk3d(0, 0, 1.0)] },
    { number: 3, material: "2", polygons: [disk3d(0, 0, 4.0)] },
  ];
  function disk3d(cy: number, cz: number, r: number, n = 64) {
    const pts: { x: number; y: number; z: number }[] = [];
    for (let i = 0; i < n; i++) {
      const t = (2 * Math.PI * i) / n;
      pts.push({ x: 0, y: cy + r * Math.cos(t), z: cz + r * Math.sin(t) });
    }
    return pts;
  }

  /**
   * jsdom 里 `getScreenCTM()` 返回 null，而悬停处理**必须**它才能把屏幕坐标换回 SVG
   * 本地坐标（见组件注释）。组件读的是**内层 `<g>`** 的 CTM（那里含 scale(1,-1) 与
   * viewBox 缩放），所以桩要打在 `<g>` 上。
   * 这里给恒等映射：屏幕坐标 = 本地坐标（测试里的多边形本来就用本地坐标定义）。
   */
  function stubCtm(g: SVGGElement) {
    (g as any).getScreenCTM = () => ({
      inverse: () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 }),
    });
  }

  it("悬停在重叠区中心 → 报**图上盖在上面**的那个栅元（3 · M2，不是 2 · M1）", () => {
    // 保证 DOMPoint 存在（组件用 new DOMPoint(...)）
    (globalThis as any).DOMPoint = (globalThis as any).DOMPoint || class {
      constructor(public x: number, public y: number) {}
      matrixTransform(m: any) { return new (this.constructor as any)(this.x + m.e, this.y + m.f); }
    };

    const { container } = render(
      React.createElement(CrossSectionView, {
        slices: slices as any,
        plane: { A: 1, B: 0, C: 0, D: 0 },
        onClose: () => {},
        cellComments: [{ number: 2, comment: "水" }, { number: 3, comment: "钢" }],
      }),
    );
    const svg = container.querySelector("svg") as SVGSVGElement;
    expect(svg).toBeTruthy();

    // 先确认"图形"这一侧的次序：多边形按 slice 数组次序画 ⇒ 最后一个覆盖中心的应是 cell3
    const polys = Array.from(svg.querySelectorAll("polygon"));
    expect(polys.length).toBe(2);
    const localPolys = polys.map((el) =>
      el.getAttribute("points")!.trim().split(/\s+/).map((s) => {
        const [x, y] = s.split(",").map(Number);
        return { x, y };
      }),
    );
    // 画在最后的多边形 = 视觉最上层；让它就是"覆盖中心"的那个
    const topPolyIdx = localPolys.length - 1;
    expect(pointInPolygon(localPolys[topPolyIdx], 0, 0)).toBe(true);
    const expectedTopCell = slices[topPolyIdx].number; // 渲染次序与 slice 次序一致

    const g = svg.querySelector("g") as SVGGElement;
    expect(g).toBeTruthy();
    stubCtm(g);
    // 悬停到中心：屏幕坐标 == SVG 本地坐标（恒等映射）
    fireEvent.mouseMove(svg, { clientX: 0, clientY: 0, button: 0, buttons: 0 });

    const tip = container.textContent || "";
    expect(tip).toContain(`${expectedTopCell} · M`);
    expect(tip).not.toContain("2 · M1 · ");
    cleanup();
  });
});
