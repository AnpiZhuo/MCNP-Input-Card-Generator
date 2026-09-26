// @vitest-environment jsdom
/**
 * CrossSectionView 拖动 DOM 回归 —— 锁"组件真的按 sectionView 的算法在动"。
 *
 * 用户报告（2026-09-26）：「截面拖动时，如果截面有进行过旋转，拖动行为就会变得很怪异」。
 * 纯函数层已在 `sectionView.test.ts` 锁死（任意旋转角下内容必须跟手）；
 * 这里补组件层：拖动后**渲染出来的 viewBox / transform** 必须与算法一致 ——
 * 否则纯函数再对，组件里接错线（旧代码就是就地手写换算）也是白搭。
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/react";
import CrossSectionView from "../src/components/CrossSectionView";
import { panAfterDrag, sliceGroupTransform, sliceViewBoxString, type SliceViewState } from "../src/utils/sectionView";

afterEach(() => cleanup());

const SLICES = [{
  number: 1, material: "1",
  polygons: [[
    { x: 0, y: 0, z: 0 }, { x: 10, y: 0, z: 0 }, { x: 10, y: 10, z: 0 }, { x: 0, y: 10, z: 0 },
  ]],
}];
const PLANE = { A: 0, B: 0, C: 1, D: 0 };
const RECT = { width: 600, height: 400, left: 0, top: 0, right: 600, bottom: 400, x: 0, y: 0, toJSON: () => ({}) };

function mount(rect: DOMRect = RECT as DOMRect) {
  const r = render(React.createElement(CrossSectionView, {
    slices: SLICES, plane: PLANE, onClose: () => {},
  }));
  const svg = r.container.querySelector("svg") as SVGSVGElement;
  // jsdom 不做布局：getBoundingClientRect 恒为 0，而拖动换算要用真实像素尺寸
  svg.getBoundingClientRect = () => rect;
  // jsdom 也没有 SVG 几何 API（getScreenCTM / DOMPoint）—— 悬停命中检测在这里跑不了，
  // 补最小桩让"拖动"这条链路能走完（悬停命中本身由 sectionHit 的单测覆盖）。
  const g = r.container.querySelector("g") as SVGGElement;
  (g as any).getScreenCTM = () => ({ inverse: () => ({}) });
  (globalThis as any).DOMPoint = (globalThis as any).DOMPoint || class {
    x: number; y: number;
    constructor(x: number, y: number) { this.x = x; this.y = y; }
    matrixTransform() { return { x: this.x, y: this.y }; }
  };
  return { ...r, svg };
}

/** 当前渲染出的视口状态（viewBox 尺寸/缩放由挂载时自动取景决定，这里按已知值写死） */
const FITTED = { x: -11, y: -1, w: 12, h: 12 };
const ZOOM = 0.9;

function viewState(pan: { x: number; y: number }, rotation: number): SliceViewState {
  return { viewBox: FITTED, zoom: ZOOM, pan, rotation };
}

describe("CrossSectionView 拖动平移", () => {
  it("拖动 Δ 像素 ⇒ 内容正好移动 Δ 像素（渲染出的 viewBox 与算法一致）", () => {
    const { svg } = mount();
    const before = svg.getAttribute("viewBox");
    expect(before).toBe(sliceViewBoxString(viewState({ x: 0, y: 0 }, 0)));

    fireEvent.mouseDown(svg, { button: 0, clientX: 200, clientY: 150 });
    fireEvent.mouseMove(svg, { clientX: 300, clientY: 200 });
    fireEvent.mouseUp(svg);

    // 等比缩放 k = min(600/13.333, 400/13.333) = 30 ⇒ pan = (100/30, 50/30)
    const expectedPan = panAfterDrag({ x: 0, y: 0 }, 100, 50, viewState({ x: 0, y: 0 }, 0), RECT);
    expect(expectedPan.x).toBeCloseTo(100 / 30, 6);
    expect(expectedPan.y).toBeCloseTo(50 / 30, 6);
    expect(svg.getAttribute("viewBox")).toBe(sliceViewBoxString(viewState(expectedPan, 0)));
    // 旧实现按"X 用宽、Y 用高"各算一套 ⇒ pan.x 只有 100*(12/0.9)/600 = 2.22（拖不动）
    expect(expectedPan.x).not.toBeCloseTo(100 * (12 / 0.9) / RECT.width, 3);
  });

  it("旋转过之后，拖动仍然是 1:1（旋转中心不随平移漂移）", () => {
    const { svg } = mount();
    const rotInput = svg.ownerDocument!.querySelector('input[aria-label="截面旋转角度"]') as HTMLInputElement;
    fireEvent.change(rotInput, { target: { value: "30" } });

    const g = svg.querySelector("g") as SVGGElement;
    const t0 = g.getAttribute("transform");
    expect(t0).toBe(sliceGroupTransform(viewState({ x: 0, y: 0 }, 30)));

    fireEvent.mouseDown(svg, { button: 0, clientX: 100, clientY: 100 });
    fireEvent.mouseMove(svg, { clientX: 180, clientY: 40 });
    fireEvent.mouseUp(svg);

    // 平移后旋转圆心必须**没变**（旧实现：圆心 = 拟合中心 − pan ⇒ 这里会左移 2.67、上移 2）
    expect(g.getAttribute("transform")).toBe(sliceGroupTransform(viewState({ x: 80 / 30, y: -60 / 30 }, 30)));
    expect(g.getAttribute("transform")).not.toContain(`rotate(30 ${-11 + 12 / 0.9 / 2 - 80 / 30}`);
  });

  it("滚轮缩放后拖动仍按等比缩放换算（不随 zoom 跑偏）", () => {
    const { svg } = mount();
    fireEvent.wheel(svg, { deltaY: -100 });          // 放大 1/1.15
    const zoom = 0.9 * (1 / 1.15);
    fireEvent.mouseDown(svg, { button: 0, clientX: 10, clientY: 10 });
    fireEvent.mouseMove(svg, { clientX: 110, clientY: 10 });
    fireEvent.mouseUp(svg);
    // 期望值由算法给出（缩放后每像素对应的用户单位变了，拖动距离必须跟着变）
    const pan = panAfterDrag({ x: 0, y: 0 }, 100, 0,
      { viewBox: FITTED, zoom, pan: { x: 0, y: 0 }, rotation: 0 }, RECT);
    expect(pan.x).toBeCloseTo(100 / (400 * zoom / 12), 9);   // 高度受限 ⇒ k = 400·zoom/12
    expect(svg.getAttribute("viewBox")).toBe(sliceViewBoxString({ viewBox: FITTED, zoom, pan, rotation: 0 }));
  });

  it("视口尺寸为 0（隐藏/未布局）时不崩、不动", () => {
    const zero = { width: 0, height: 0, left: 0, top: 0, right: 0, bottom: 0, x: 0, y: 0, toJSON: () => ({}) } as DOMRect;
    const { svg } = mount(zero);
    const before = svg.getAttribute("viewBox");
    const spy = vi.spyOn(console, "error");
    fireEvent.mouseDown(svg, { button: 0, clientX: 10, clientY: 10 });
    fireEvent.mouseMove(svg, { clientX: 60, clientY: 10 });
    fireEvent.mouseUp(svg);
    expect(svg.getAttribute("viewBox")).toBe(before);
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });
});
