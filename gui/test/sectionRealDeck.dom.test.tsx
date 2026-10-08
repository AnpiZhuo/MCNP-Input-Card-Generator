// @vitest-environment jsdom
/**
 * 真 deck 金样本：把**后端对用户那张卡在 Z=0 的真实响应**
 * （`fixtures/section_real_z0.json`）喂进真实组件，锁住用户实测过的几件事。
 *
 * 数据关键事实（可核对）：
 *   栅元 1（M3 不锈钢）3 环；栅元 2（M1 石墨）2 环 = 环带 4.5<ρ<5；栅元 6（M2 水）2 环 = 大块 + ρ<6 内孔；
 *   栅元 3/4/5 被后端**按定义**剔除（z=0 正是卡里面 112 `PZ 0.000` 的位置，这三个栅元以它为界），
 *   响应里带 3 条 warnings 说明这件事。
 * 投影：切割平面 Z=0 ⇒ 屏幕局部坐标 = (−x, y)。
 *
 * 用户口径（2026-10-08）：**「空腔就应该是空的」** —— 石墨环里那块 ρ<4.5 的空腔，
 * 不许画任何标注（上一版画了"空隙"点纹，用户看到的是"莫名其妙的东西 + 悬停无显示"）。
 */
import { describe, it, expect } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import React from "react";
import fs from "node:fs";
import path from "node:path";
import CrossSectionView from "../src/components/CrossSectionView";
import { getMatColor } from "../src/utils/materialColors";
import { paintedAt } from "./svgPaint";

const payload = JSON.parse(
  fs.readFileSync(path.resolve(__dirname, "fixtures/section_real_z0.json"), "utf-8"),
) as {
  plane: { A: number; B: number; C: number; D: number };
  slices: { number: number; material: string; polygons: { x: number; y: number; z: number }[][] }[];
  warnings?: string[];
};

const WATER = getMatColor("2");      // 栅元 6 · M2
const STEEL = getMatColor("3");      // 栅元 1 · M3
const GRAPHITE = getMatColor("1");   // 栅元 2 · M1

/** 卡片坐标 (x,y) → 屏幕/局部坐标（Z=0 平面：u=−X, v=+Y） */
const screen = (x: number, y: number) => ({ x: -x, y });

describe("真数据（用户卡 · Z=0）", () => {
  function mount() {
    (globalThis as any).DOMPoint = (globalThis as any).DOMPoint || class {
      constructor(public x: number, public y: number) {}
      matrixTransform(m: any) { return new (this.constructor as any)(this.x + m.e, this.y + m.f); }
    };
    const r = render(React.createElement(CrossSectionView, {
      slices: payload.slices as any,
      plane: payload.plane,
      onClose: () => {},
      cellComments: payload.slices.map((s) => ({ number: s.number, comment: "" })),
      warnings: payload.warnings,
    }));
    const svg = r.container.querySelector("svg") as SVGSVGElement;
    const g = svg.querySelector("g") as SVGGElement;
    (g as any).getScreenCTM = () => ({ inverse: () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 }) });
    return { container: r.container, svg };
  }

  it("水不得涂进自己的孔里；石墨环/不锈钢带读数正确（不再报'外部材料'）", () => {
    const { container, svg } = mount();

    // 对照：ρ=8 在水体真区域内 ⇒ 有水色、悬停报 6 · M2
    const out = screen(0, 42);
    expect(paintedAt(container, WATER, out)).toBe(true);
    fireEvent.mouseMove(svg, { clientX: out.x, clientY: out.y, button: 0, buttons: 0 });
    expect(container.textContent || "").toContain("6 · M2 ·");

    // ρ=3 在栅元 6 的**孔**里 ⇒ 不得有水色，也不得报 6 · M2
    const inn = screen(0, 47);
    expect(paintedAt(container, WATER, inn)).toBe(false);
    fireEvent.mouseMove(svg, { clientX: inn.x, clientY: inn.y, button: 0, buttons: 0 });
    expect(container.textContent || "").not.toContain("6 · M2 ·");

    // 石墨环带 ρ=4.75 ⇒ 石墨色可见、悬停报 2 · M1
    const ring = screen(0, 45.25);
    expect(paintedAt(container, GRAPHITE, ring)).toBe(true);
    fireEvent.mouseMove(svg, { clientX: ring.x, clientY: ring.y, button: 0, buttons: 0 });
    expect(container.textContent || "").toContain("2 · M1 ·");

    // 不锈钢带 (49.5, 0.5) ⇒ 报 1 · M3
    const steel = screen(49.5, 0.5);
    expect(paintedAt(container, STEEL, steel)).toBe(true);
    fireEvent.mouseMove(svg, { clientX: steel.x, clientY: steel.y, button: 0, buttons: 0 });
    expect(container.textContent || "").toContain("1 · M3 ·");

    cleanup();
  });

  it("★空腔（石墨环里 ρ<4.5）不许画任何东西：没有冲突标注、也不编提示框", () => {
    const { container, svg } = mount();
    // 图上不该有任何冲突层（无重叠；空白不标）
    expect(container.querySelectorAll("[data-conflict]").length).toBe(0);

    // 悬停到空腔中心：那里没有栅元 ⇒ 不给读数（也不再编一个"空隙"解释出来）
    const cavity = screen(0, 47);
    fireEvent.mouseMove(svg, { clientX: cavity.x, clientY: cavity.y, button: 0, buttons: 0 });
    expect(container.querySelector("[data-hover-tip]")).toBeNull();
    cleanup();
  });

  it("后端 warnings 必须显示在界面上（解释'这个平面上为什么少了几个栅元'）", () => {
    const { container } = mount();
    const box = container.querySelector('[data-section-warnings="1"]');
    expect(box).toBeTruthy();
    expect(box!.textContent).toContain("只沿边界面接触");
    expect(box!.textContent).toContain("栅元 3");
    cleanup();
  });
});
