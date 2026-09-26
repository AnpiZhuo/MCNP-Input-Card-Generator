import { describe, it, expect } from "vitest";
import {
  panAfterDrag, sliceContentToScreen, sliceGroupTransform, sliceRotationCenter,
  sliceScreenScale, sliceViewBoxString, sliceViewportSize, type SliceRect, type SliceViewState,
} from "../src/utils/sectionView";

/*
 * sectionView —— 二维截面的视口/变换（纯函数）。
 *
 * 用户报告（2026-09-26）：「截面拖动时，如果截面有进行过旋转，拖动行为就会变得很怪异」。
 *
 * 根因（数学 + 源码双向确认）：旧实现把旋转中心写成 `(viewBox.x - pan.x) + w/zoom/2`
 * —— 旋转中心跟着平移走。`<g transform="scale(1,-1) rotate(θ cx cy)">` 里 cx 一旦含 pan，
 * 平移量就被卷进旋转矩阵 ⇒ 拖动 Δ 时内容沿 **Δ 旋转 θ** 之后的方向走（拖↑它往←走）。
 * θ=0 时旋转矩阵是单位矩阵，所以这个 bug 只在"转过角度之后"才露头。
 *
 * 本文件的中心不变量：**任意旋转角/缩放/留白下，拖动 Δ 像素 ⇒ 内容正好移动 Δ 像素**。
 */

const RECT: SliceRect = { width: 620, height: 480 };

const state = (over: Partial<SliceViewState> = {}): SliceViewState => ({
  viewBox: { x: -12, y: -8, w: 30, h: 20 },
  zoom: 1.4,
  pan: { x: 3, y: -5 },
  rotation: 0,
  ...over,
});

/** 旧实现（旋转中心含 pan）——只为在下面做反向对照，正式代码里已不存在 */
function legacyContentToScreen(p: { x: number; y: number }, s: SliceViewState, rect: SliceRect) {
  const vbW = s.viewBox.w / s.zoom, vbH = s.viewBox.h / s.zoom;
  const bx = s.viewBox.x - s.pan.x, by = s.viewBox.y - s.pan.y;
  const k = Math.min(rect.width / vbW, rect.height / vbH);
  const offX = (rect.width - vbW * k) / 2, offY = (rect.height - vbH * k) / 2;
  const cx = bx + vbW / 2, cy = by + vbH / 2;          // ← bug 原址：中心含 pan
  const rad = s.rotation * Math.PI / 180, c = Math.cos(rad), sn = Math.sin(rad);
  const dx = p.x - cx, dy = p.y - cy;
  const rx = cx + dx * c - dy * sn, ry = cy + dx * sn + dy * c;
  return { x: (rx - bx) * k + offX, y: (-ry - by) * k + offY };
}

const DRAG = { dx: 63, dy: -41 };
const POINT = { x: 4, y: 3 };

describe("拖动必须跟手（内容沿鼠标方向移动，且距离 1:1）", () => {
  it.each([0, 15, 37, -25, 90, 180, 270])("旋转 %s° 时拖动 Δ ⇒ 内容移动 Δ", (rotation) => {
    const s = state({ rotation });
    const before = sliceContentToScreen(POINT, s, RECT);
    const after = sliceContentToScreen(POINT, { ...s, pan: panAfterDrag(s.pan, DRAG.dx, DRAG.dy, s, RECT) }, RECT);
    expect(after.x - before.x).toBeCloseTo(DRAG.dx, 6);
    expect(after.y - before.y).toBeCloseTo(DRAG.dy, 6);
  });

  it("在缩放、平移、留白都不同的若干组合下同样跟手", () => {
    const rects: SliceRect[] = [RECT, { width: 300, height: 800 }, { width: 1000, height: 300 }];
    for (const rect of rects) {
      for (const zoom of [0.2, 0.9, 3, 12]) {
        for (const rotation of [0, 33, 120]) {
          const s = state({ zoom, rotation, pan: { x: -17, y: 9 } });
          const before = sliceContentToScreen(POINT, s, rect);
          const after = sliceContentToScreen(POINT, { ...s, pan: panAfterDrag(s.pan, DRAG.dx, DRAG.dy, s, rect) }, rect);
          expect([rect.width, zoom, rotation, after.x - before.x]).toEqual([rect.width, zoom, rotation, expect.closeTo(DRAG.dx, 6)]);
          expect(after.y - before.y).toBeCloseTo(DRAG.dy, 6);
        }
      }
    }
  });

  it("反向对照（旧实现）：旋转中心含 pan ⇒ 拖动位移被旋转矩阵污染（θ=0 时看不出来）", () => {
    // 旧实现屏幕映射：screen = k·( S(c + M(u−c)) − b )，其中 b = viewBox 原点 − pan，
    // 而 c = b + 半视口（跟着 pan 走）⇒ 展开后 d(screen)/d(pan) = k·(I − S + S·M)。
    // 也就是说：拖动 Δ 得到的是 (I − S + S·M)·Δ —— **既转了方向又改了长度**；
    // θ=0 ⇒ M=I ⇒ (I − S + S)Δ = Δ（正确），这就是"平时看不出来、转过才怪"。
    const rad = 37 * Math.PI / 180;
    const c = Math.cos(rad), s = Math.sin(rad);
    const expected = {
      x: DRAG.dx - DRAG.dx + (c * DRAG.dx - s * DRAG.dy),          // (I − S + S·M)·Δ 的 x 分量
      y: 2 * DRAG.dy + (-s * DRAG.dx - c * DRAG.dy),               // 其 y 分量（含 S 的翻转）
    };
    const s37 = state({ rotation: 37 });
    const before = legacyContentToScreen(POINT, s37, RECT);
    const after = legacyContentToScreen(POINT,
      { ...s37, pan: panAfterDrag(s37.pan, DRAG.dx, DRAG.dy, s37, RECT) }, RECT);
    expect(after.x - before.x).toBeCloseTo(expected.x, 6);
    expect(after.y - before.y).toBeCloseTo(expected.y, 6);
    // 症状量化：位移方向与鼠标方向差 ~16°、长度还放大 1.53 倍
    const angleDiff = Math.atan2(after.y - before.y, after.x - before.x) - Math.atan2(DRAG.dy, DRAG.dx);
    expect(Math.abs(angleDiff)).toBeGreaterThan(0.2);
    expect(Math.hypot(after.x - before.x, after.y - before.y)).toBeGreaterThan(1.4 * Math.hypot(DRAG.dx, DRAG.dy));
    // θ=0 时旧实现是对的 —— 正是"平时看不出来、转过才怪"的原因
    const s0 = state({ rotation: 0 });
    const b0 = legacyContentToScreen(POINT, s0, RECT);
    const a0 = legacyContentToScreen(POINT, { ...s0, pan: panAfterDrag(s0.pan, DRAG.dx, DRAG.dy, s0, RECT) }, RECT);
    expect(a0.x - b0.x).toBeCloseTo(DRAG.dx, 6);
    expect(a0.y - b0.y).toBeCloseTo(DRAG.dy, 6);
  });
});

describe("旋转中心必须只由内容视口决定", () => {
  it("平移不改变旋转中心（旧实现里它跟着 pan 跑）", () => {
    const s = state();
    const c0 = sliceRotationCenter(s);
    const c1 = sliceRotationCenter({ ...s, pan: { x: 999, y: -999 } });
    expect(c1).toEqual(c0);
    expect(c0).toEqual({ cx: -12 + (30 / 1.4) / 2, cy: -8 + (20 / 1.4) / 2 });
  });

  it("`<g>` 的 transform 里 rotate 的圆心因此与 pan 无关", () => {
    const a = sliceGroupTransform(state({ rotation: 30, pan: { x: 0, y: 0 } }));
    const b = sliceGroupTransform(state({ rotation: 30, pan: { x: 123, y: -45 } }));
    expect(a).toBe(b);
    expect(a).toBe(`scale(1,-1) rotate(30 ${sliceRotationCenter(state()).cx} ${sliceRotationCenter(state()).cy})`);
  });
});

describe("viewBox / 缩放 / 留白", () => {
  it("viewBox 含平移与缩放，可见尺寸 = 内容尺寸 / zoom", () => {
    const s = state();
    expect(sliceViewportSize(s)).toEqual({ w: 30 / 1.4, h: 20 / 1.4 });
    expect(sliceViewBoxString(s)).toBe(`${-12 - 3} ${-8 + 5} ${30 / 1.4} ${20 / 1.4}`);
  });

  it("等比缩放取 min(视口/内容)，长宽比不匹配时留白", () => {
    const s = state();
    // 视口比内容"矮胖"(620/480 < 30/20) ⇒ 宽度受限、上下留白
    expect(sliceScreenScale(s, RECT)).toBeCloseTo(RECT.width / (30 / 1.4), 9);
    // 视口比内容"瘦高" ⇒ 高度受限、左右留白
    const tall: SliceRect = { width: 900, height: 400 };
    expect(sliceScreenScale(s, tall)).toBeCloseTo(tall.height / (20 / 1.4), 9);
    // 旧实现按"X 用宽、Y 用高"各算一套：高度受限时 X 方向就偏小 ⇒ 拖 100px 只动 ~67px
    const legacyKx = (s.viewBox.w / s.zoom) / tall.width;
    const correct = 1 / sliceScreenScale(s, tall);
    expect(legacyKx).not.toBeCloseTo(correct, 3);
    expect(legacyKx / correct).toBeCloseTo(0.667, 2);
  });

  it("视口尺寸为 0（未挂载/隐藏）时不产生 NaN，pan 原样返回", () => {
    const s = state();
    expect(panAfterDrag(s.pan, 10, 10, s, { width: 0, height: 0 })).toEqual(s.pan);
    expect(sliceScreenScale(s, { width: 0, height: 0 })).toBe(0);
  });
});
