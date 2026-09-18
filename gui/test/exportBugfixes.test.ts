// @vitest-environment jsdom
/**
 * 出图 bug 回归（2026-09-17 review 抓到的那批）。
 *
 * 每条都对应一个**真实踩过的缺陷**，锁住"改回去就会红"：
 *  1. `splitSvg` 必须保留 viewBox —— 否则截面（用户坐标、负原点）导出被当成像素，缩成墨点；
 *  2. `panelTransform` 必须把负原点平移进框内，且等比；
 *  3. `planeRangeInBox` 必须按**未归一化**法向换算 —— 否则斜平面成叠只扫 1/|n| 的范围；
 *  4. 取样必须按**体素边界**口径（0.5 偏移）—— 否则自由平面与轴对齐切面错半格；
 *  5. `snapshotSvg` 不能把根节点的视觉样式清掉 —— 否则导出图默认黑填充。
 */
import { describe, it, expect } from "vitest";
import { splitSvg, panelTransform, buildVectorFigure } from "../src/export/vectorFigure";
import { planeRangeInBox, samplePlane, type AABB } from "../src/export/planeSample";
import { snapshotSvg } from "../src/export/captureFrame";

describe("splitSvg / panelTransform（viewBox 不可丢）", () => {
  it("保留 viewBox（截面那种「用户坐标 + 负原点」的 SVG）", () => {
    const p = splitSvg(`<svg viewBox="-5 -4 10 8"><polygon points="0,0 1,1"/></svg>`);
    expect(p.viewBox).toEqual([-5, -4, 10, 8]);
    expect(p.width).toBe(10);
    expect(p.height).toBe(8);
  });

  it("无 viewBox 时退回 width/height，且 viewBox 为 null", () => {
    const p = splitSvg(`<svg width="120" height="80"><g/></svg>`);
    expect(p.viewBox).toBeNull();
    expect(p.width).toBe(120);
    expect(p.height).toBe(80);
  });

  it("负原点被平移进框内（不丢原点的旧实现会把内容画到框外）", () => {
    const parts = splitSvg(`<svg viewBox="-5 -4 10 8"><g/></svg>`);
    const tf = panelTransform(parts, 200, 160);
    // 等比：10×8 放进 200×160 → scale=20，居中后 translate 恰为 +100/+80（把 -5,-4 挪到 0,0）
    expect(tf.scale).toBeCloseTo(20, 9);
    expect(tf.tx).toBeCloseTo(100, 9);
    expect(tf.ty).toBeCloseTo(80, 9);
  });

  it("等比：宽高比不同也不拉伸（取较小缩放）", () => {
    const tf = panelTransform(splitSvg(`<svg viewBox="0 0 100 10"><g/></svg>`), 200, 200);
    expect(tf.scale).toBeCloseTo(2, 9); // 受宽度限制
  });

  it("组合进图后：含 viewBox 的面板不会退化成几像素（宽度按用户坐标长宽比给）", () => {
    const fig = buildVectorFigure({
      panels: [{ svg: `<svg viewBox="-5 -5 10 10"><polygon points="0,0 1,1"/></svg>` }],
      contentHeight: 300,
    });
    // 10×10 的用户坐标 → 正方形面板，宽度应≈内容高度（旧实现会当成 10px 宽）
    const m = /<g transform="translate\(([-\d.]+),([-\d.]+)\) scale\(([\d.]+)\)">/.exec(fig.svg);
    expect(m).toBeTruthy();
    expect(Number(m![3])).toBeCloseTo(30, 6); // 300 / 10
  });
});

describe("planeRangeInBox（未归一化法向）", () => {
  const box: AABB = { min: [0, 0, 0], max: [2, 2, 2] };

  it("轴对齐：|n|=1，区间就是坐标范围", () => {
    expect(planeRangeInBox({ A: 0, B: 0, C: 1, D: 0 }, box)).toEqual({ min: 0, max: 2 });
  });

  it("斜平面 X+Y+Z=0（|n|=√3）：区间必须乘 |n|，否则只扫到 1/√3", () => {
    const r = planeRangeInBox({ A: 1, B: 1, C: 1, D: 0 }, box);
    // 解析解：单位法向投影极值 = (2+2+2)/√3 = 2√3；乘 |n|=√3 → 6
    expect(r.min).toBeCloseTo(0, 9);
    expect(r.max).toBeCloseTo(6, 6);
  });

  it("系数放大 10 倍（D 同系放大）：区间也放大 10 倍", () => {
    const r = planeRangeInBox({ A: 10, B: 10, C: 10, D: 0 }, box);
    expect(r.max).toBeCloseTo(60, 6);
  });
});

describe("samplePlane（节点口径：与体积渲染/轴对齐切面一致）", () => {
  /**
   * 8³ 网格、字节值 = i*30（0…210）。
   * ⚠️ 标量值域必须声明成 `{0,255}`：帧是 8bit 量化，真值 = `byte*(max-min)/255 + min`。
   * 若把 min/max 声明成数据自身的 0…210，反量化后末体素会变成 172.9（=210×210/255）——
   * 这是**测试构造错**，不是取样错（第一版就是这么写错的）。
   */
  function field8() {
    const res: [number, number, number] = [8, 8, 8];
    const d = new Uint8Array(8 * 8 * 8);
    for (let i = 0; i < 8; i++) for (let j = 0; j < 8; j++) for (let k = 0; k < 8; k++) d[(i * 8 + j) * 8 + k] = i * 30;
    return { res, d, box: { min: [0, 0, 0], max: [7, 7, 7] } as AABB, scalarRange: { min: 0, max: 255 } };
  }

  it("平面落在首/末节点上时，取样值等于该节点的值（半格偏移或越界归零都会算错）", () => {
    const { res, d, box, scalarRange } = field8();
    const s0 = samplePlane({ A: 1, B: 0, C: 0, D: 0 }, box, res, d, scalarRange, { samples: 32 })!;
    const s1 = samplePlane({ A: 1, B: 0, C: 0, D: 7 }, box, res, d, scalarRange, { samples: 32 })!;
    const mid = (s: { values: Float64Array }) => s.values[Math.floor(s.values.length / 2)];
    expect(mid(s0)).toBeCloseTo(0, 6);    // 第 0 个样本
    expect(mid(s1)).toBeCloseTo(210, 6);  // 第 7 个样本（最大）
  });

  it("等值线落在解析位置：线性场里等值线是 x=常数的直线", () => {
    const { res, d, box, scalarRange } = field8();
    const s = samplePlane({ A: 0, B: 1, C: 0, D: 3 }, box, res, d, scalarRange, { samples: 64 })!;
    // 场只随 x 变；同一行（列变化，即沿 u）值应相同
    const row = Math.floor(s.height / 2);
    const left = s.values[row * s.width];
    const right = s.values[row * s.width + s.width - 1];
    expect(left).toBeCloseTo(right, 6);
  });
});

describe("snapshotSvg（根节点视觉样式不可丢）", () => {
  it("子节点样式被内联，根节点的定位样式被清掉、内容不受影响", () => {
    const host = document.createElement("div");
    host.innerHTML = `<svg width="100" height="100" viewBox="0 0 100 100" style="position:absolute;left:0"><g fill="rgb(255, 0, 0)"><rect x="1" y="2" width="3" height="4"/></g></svg>`;
    document.body.appendChild(host);
    const svg = host.querySelector("svg") as SVGSVGElement;
    const out = snapshotSvg(svg);
    host.remove();
    expect(out).toBeTruthy();
    expect(out!).toContain("<svg");
    // 子节点拿到了 fill（内联）
    expect(out!).toMatch(/fill="?rgb\(255, 0, 0\)|fill:rgb\(255, 0, 0\)/);
    // 根上的屏幕定位样式被清掉
    expect(out!).not.toContain("position:absolute");
  });

  it("CSS 变量必须解析成实际值，且不把屏幕定位样式带进导出（Recharts 场景）", () => {
    // 模拟 Recharts：颜色写成 var(--text-tertiary)，外层带屏幕定位样式
    const host = document.createElement("div");
    host.innerHTML = `
      <div style="position:absolute;left:-9999px">
        <svg width="200" height="100" viewBox="0 0 200 100" style="position:relative;display:block">
          <g stroke="var(--text-tertiary)" fill="var(--text-primary)">
            <path d="M0 0 L10 10" fill="none"/>
          </g>
        </svg>
      </div>`;
    document.body.appendChild(host);
    const svg = host.querySelector("svg") as SVGSVGElement;
    const out = snapshotSvg(svg, { background: "#ffffff" })!;
    host.remove();
    expect(out).toBeTruthy();
    // 脱离文档后 var() 会失效（没有 CSS 环境）→ 必须已经解析成具体颜色
    expect(out).not.toContain("var(--");
    // 屏幕定位样式不带进导出
    expect(out).not.toContain("position:absolute");
    expect(out).not.toContain("left:-9999px");
  });

  it("null / 非 SVG → null（不抛）", () => {
    expect(snapshotSvg(null)).toBeNull();
  });
});
