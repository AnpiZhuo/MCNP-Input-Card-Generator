// @vitest-environment jsdom
/**
 * 冲突层 DOM 回归 —— **只标重叠**；空白一律不画。
 *
 * 用户口径沿革：
 * · 2026-10-07：「重叠/空隙现在靠'谁后声明谁盖住'，这是把问题藏起来」⇒ 重叠要标出来；
 * · 2026-10-08：**「空腔就应该是空的」** ⇒ 上一版把"被材料围住的空白"标成"空隙"（橙点纹），
 *   正好把用户卡里本该为空的空腔涂上标记 ⇒ 他看到"空腔里有个莫名其妙的东西、悬停又没读数"。
 *   本文件把两条都钉住：重叠要标 + 空白一格都不许画。
 */
import { describe, it, expect } from "vitest";
import { render, cleanup, fireEvent } from "@testing-library/react";
import React from "react";
import CrossSectionView from "../src/components/CrossSectionView";

function disk3d(cx: number, cy: number, r: number, n = 64) {
  const pts: { x: number; y: number; z: number }[] = [];
  for (let i = 0; i < n; i++) {
    const t = (2 * Math.PI * i) / n;
    pts.push({ x: 0, y: cx + r * Math.cos(t), z: cy + r * Math.sin(t) });
  }
  return pts;
}

function mount(slices: any[], warnings?: string[]) {
  (globalThis as any).DOMPoint = (globalThis as any).DOMPoint || class {
    constructor(public x: number, public y: number) {}
    matrixTransform(m: any) { return new (this.constructor as any)(this.x + m.e, this.y + m.f); }
  };
  const r = render(React.createElement(CrossSectionView, {
    slices, plane: { A: 1, B: 0, C: 0, D: 0 }, onClose: () => {}, warnings,
  }));
  const svg = r.container.querySelector("svg") as SVGSVGElement;
  const g = svg.querySelector("g") as SVGGElement;
  if (g) (g as any).getScreenCTM = () => ({ inverse: () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 }) });
  return { container: r.container, svg };
}

describe("CrossSectionView 冲突层", () => {
  it("两个栅元区域重叠 ⇒ 画出重叠层（红斜纹）+ 面积提示 + 图例", () => {
    const { container } = mount([
      { number: 1, material: "1", polygons: [disk3d(0, 0, 5)] },
      { number: 2, material: "2", polygons: [disk3d(0, 0, 3)] },
    ]);
    expect(container.querySelector('[data-conflict="overlap"]')).toBeTruthy();
    expect(container.querySelector('[data-conflict-count="1"]')).toBeTruthy();
    expect(container.querySelector('[data-conflict-legend="1"]')).toBeTruthy();
    expect(container.textContent).toContain("重叠");
    cleanup();
  });

  it("悬停到重叠区 ⇒ 说明「重叠」，并把同时认领的栅元一并列出", () => {
    const { container, svg } = mount([
      { number: 1, material: "1", polygons: [disk3d(0, 0, 5)] },
      { number: 2, material: "2", polygons: [disk3d(0, 0, 3)] },
    ]);
    // 圆心在 (0,0)：屏幕局部 = (−x, y) ⇒ (0,0) 即两盘重叠中心
    fireEvent.mouseMove(svg, { clientX: 0, clientY: 0, button: 0, buttons: 0 });
    const tip = container.querySelector('[data-hover-tip="overlap"]');
    expect(tip).toBeTruthy();
    expect(tip!.textContent).toContain("重叠");
    expect(tip!.textContent).toContain("1 · M1");
    expect(tip!.textContent).toContain("2 · M2");
    cleanup();
  });

  it("★环带的空腔里没有别的栅元 ⇒ **一格都不画**（空腔就应该是空的）", () => {
    const { container } = mount([
      { number: 1, material: "1", polygons: [disk3d(0, 0, 5), disk3d(0, 0, 3)] },
    ]);
    expect(container.querySelectorAll("[data-conflict]").length).toBe(0);
    expect(container.querySelector('[data-conflict-count="1"]')).toBeNull();
    cleanup();
  });

  it("单个实心盘（无重叠）⇒ 不画任何冲突层", () => {
    const { container } = mount([{ number: 1, material: "1", polygons: [disk3d(0, 0, 5)] }]);
    expect(container.querySelectorAll("[data-conflict]").length).toBe(0);
    cleanup();
  });

  it("后端 warnings ⇒ 界面上必须解释（'该平面上它不存在'不能只留在响应里）", () => {
    const { container } = mount(
      [{ number: 1, material: "1", polygons: [disk3d(0, 0, 5)] }],
      ["栅元 3：与切割平面只沿边界面接触（该平面上它不存在），已剔除切出的边界伪影"],
    );
    const box = container.querySelector('[data-section-warnings="1"]');
    expect(box).toBeTruthy();
    expect(box!.textContent).toContain("只沿边界面接触");
    cleanup();
  });
});
