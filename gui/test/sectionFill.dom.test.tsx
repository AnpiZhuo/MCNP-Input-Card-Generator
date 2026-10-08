// @vitest-environment jsdom
/**
 * 截面「内孔被当成实心填充」的回归回路（Phase 1 反馈回路）
 *
 * ## 用户实测症状（本轮原话）
 * "计算时，中间有某块实际上是其他材料，但被材料覆盖了，两者共同显示颜色，
 *  鼠标悬停时只显示外部材料的名称。"
 *
 * ## 这个场景为什么是最小忠实复刻
 * 后端对「带孔实体」返回的就是**两个独立环**（外环 + 内孔环），有单测为证：
 * `tests/unit/test_stl_cross_section.py::test_frame_mid_cut_two_loops`。
 * 于是本图只需两个栅元：水芯（M1，栅元 1）与「带水孔的钢」（M2，栅元 3，两环）。
 *
 * ## 本回路只问用户看得见的两件事
 *  A. **图形**：孔内不得被外部材料着色 —— 对**真实渲染出来的** `<polygon>/<path>`
 *     按 SVG 自己的填充规则（`fill-rule`，缺省 nonzero）逐点求值，而不是断言 DOM 结构；
 *     这样无论是"一条 path + evenodd"还是"环定向 + nonzero"的修法，它都成立。
 *  B. **读数**：孔内悬停必须报孔里的那个栅元（孔不是该栅元的一部分）。
 * 另加两条**对照**（现在就该绿），防"把图删空"这种假绿。
 */
import { describe, it, expect } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import React from "react";
import CrossSectionView from "../src/components/CrossSectionView";
import { getMatColor } from "../src/utils/materialColors";
import { paintedAt, type P2 } from "./svgPaint";

const WATER = "1";   // 栅元 1 · M1
const STEEL = "2";   // 栅元 3 · M2（带水孔的钢）

/** 以 (cy,cz) 为心、半径 r 的正 n 边形，全部落在 x=0 平面上 */
function disk3d(cy: number, cz: number, r: number, n = 64) {
  const pts: { x: number; y: number; z: number }[] = [];
  for (let i = 0; i < n; i++) {
    const t = (2 * Math.PI * i) / n;
    pts.push({ x: 0, y: cy + r * Math.cos(t), z: cz + r * Math.sin(t) });
  }
  return pts;
}

describe("截面：栅元的内孔（内环）不得被该栅元自己的材料填充", () => {
  /** 水芯 M1（栅元 1，先声明）+ 带水孔的钢 M2（栅元 3，后声明 ⇒ 画在上面） */
  const slices = [
    { number: 1, material: WATER, polygons: [disk3d(0, 0, 1.0)] },
    { number: 3, material: STEEL, polygons: [disk3d(0, 0, 4.0), disk3d(0, 0, 1.0)] },
  ];

  function mount() {
    (globalThis as any).DOMPoint = (globalThis as any).DOMPoint || class {
      constructor(public x: number, public y: number) {}
      matrixTransform(m: any) { return new (this.constructor as any)(this.x + m.e, this.y + m.f); }
    };
    const r = render(
      React.createElement(CrossSectionView, {
        slices: slices as any,
        plane: { A: 1, B: 0, C: 0, D: 0 },
        onClose: () => {},
        cellComments: [{ number: 1, comment: "水" }, { number: 3, comment: "钢" }],
      }),
    );
    const svg = r.container.querySelector("svg") as SVGSVGElement;
    const g = svg.querySelector("g") as SVGGElement;
    // jsdom 无 getScreenCTM：给恒等映射 ⇒ 屏幕坐标 == SVG 本地坐标
    (g as any).getScreenCTM = () => ({ inverse: () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 }) });
    return { container: r.container, svg };
  }

  const hole: P2 = { x: 0, y: 0 };   // 水孔中心
  const ring: P2 = { x: 0, y: 2 };   // 钢环上（孔外、钢内）

  it("图形：孔内不得被外部材料 M2 着色（对照：孔外钢环确是钢、孔内确是水）", () => {
    const { container } = mount();

    /* ── 对照 1（现在就该绿）：孔外钢环处确实是钢、且不是水 ── */
    expect(paintedAt(container, getMatColor(STEEL), ring)).toBe(true);
    expect(paintedAt(container, getMatColor(WATER), ring)).toBe(false);

    /* ── 对照 2（现在就该绿）：孔内确实是水 ── */
    expect(paintedAt(container, getMatColor(WATER), hole)).toBe(true);

    /* ── 症状：孔内不得被钢色覆盖 ── */
    expect(paintedAt(container, getMatColor(STEEL), hole)).toBe(false);

    cleanup();
  });

  it("读数：孔内悬停必须报孔里的 1 · M1（对照：钢环上报 3 · M2）", () => {
    const { container, svg } = mount();

    fireEvent.mouseMove(svg, { clientX: ring.x, clientY: ring.y, button: 0, buttons: 0 });
    expect(container.textContent || "").toContain("3 · M2 ·");

    fireEvent.mouseMove(svg, { clientX: hole.x, clientY: hole.y, button: 0, buttons: 0 });
    const tip = container.textContent || "";
    expect(tip).toContain("1 · M1 ·");
    expect(tip).not.toContain("3 · M2 ·");

    cleanup();
  });
});
