// @vitest-environment jsdom
/**
 * appScale — 纯函数 + portal 根测试（TD-30）。
 *
 * `computeAppScale` 只读 `window.innerWidth/innerHeight`，属**纯函数**（jsdom 可直测），
 * 但此前全仓 `gui/test/**` 对它零命中。它决定每个窗口的整页缩放比：
 * 算错 → 内容超出可用视口、右上角按钮被裁（历史上正是这个用户可见问题）。
 *
 * 覆盖：内层 min 语义（等比、只缩小）、上下限钳制（MIN_SCALE 0.3 / 上限 1）、
 * 视口为 0 的兜底、默认设计基准 1200×800、`getAppPortalRoot` 的命中与回退。
 */
import { describe, it, expect, afterEach } from "vitest";
import { computeAppScale, getAppPortalRoot, DESIGN_WIDTH, DESIGN_HEIGHT } from "../src/utils/appScale";

function setViewport(w: number, h: number): void {
  Object.defineProperty(window, "innerWidth", { value: w, configurable: true, writable: true });
  Object.defineProperty(window, "innerHeight", { value: h, configurable: true, writable: true });
}

afterEach(() => {
  document.body.innerHTML = "";
  setViewport(1024, 768);
});

describe("appScale.computeAppScale（等比缩放比）", () => {
  it("设计基准常量：1200×800", () => {
    expect(DESIGN_WIDTH).toBe(1200);
    expect(DESIGN_HEIGHT).toBe(800);
  });

  it("视口 >= 设计基准 → 1（只缩小、不放大）", () => {
    setViewport(1200, 800);
    expect(computeAppScale()).toBe(1);
    setViewport(2000, 1500);
    expect(computeAppScale()).toBe(1);
  });

  it("取两轴较小值（等比）：宽受限 vs 高受限", () => {
    setViewport(600, 800);   // 600/1200 = 0.5 < 800/800 = 1
    expect(computeAppScale()).toBeCloseTo(0.5, 9);
    setViewport(1200, 400);  // 400/800 = 0.5 < 1
    expect(computeAppScale()).toBeCloseTo(0.5, 9);
    // 两轴同时减半
    setViewport(600, 400);
    expect(computeAppScale()).toBeCloseTo(0.5, 9);
  });

  it("按窗口传入各自的 designWidth/designHeight（子窗口 1300×820 / 1000×700）", () => {
    setViewport(650, 410);
    expect(computeAppScale(1300, 820)).toBeCloseTo(0.5, 9);
    setViewport(500, 350);
    expect(computeAppScale(1000, 700)).toBeCloseTo(0.5, 9);
  });

  it("下限钳制：极端小视口不低于 0.3（内容小到不可用之上仍可点）", () => {
    setViewport(10, 10);
    expect(computeAppScale()).toBe(0.3);
    setViewport(359, 239); // 359/1200 ≈ 0.299 < 0.3
    expect(computeAppScale()).toBe(0.3);
  });

  it("兜底：视口宽或高为 0 → 返回 1（不产生 0/NaN 缩放）", () => {
    setViewport(0, 768);
    expect(computeAppScale()).toBe(1);
    setViewport(1024, 0);
    expect(computeAppScale()).toBe(1);
    setViewport(0, 0);
    expect(computeAppScale()).toBe(1);
  });

  it("结果恒在 [0.3, 1] 闭区间内（扫一批视口，含边界）", () => {
    for (const [w, h] of [[0, 0], [1, 1], [200, 150], [1200, 800], [1300, 820], [4000, 3000]] as const) {
      setViewport(w, h);
      const s = computeAppScale();
      expect(s).toBeGreaterThanOrEqual(0.3);
      expect(s).toBeLessThanOrEqual(1);
    }
  });
});

describe("appScale.getAppPortalRoot（缩放容器内 portal 根）", () => {
  it("存在 #app-portal-root → 返回该节点", () => {
    const el = document.createElement("div");
    el.id = "app-portal-root";
    document.body.appendChild(el);
    expect(getAppPortalRoot()).toBe(el);
  });

  it("不存在 → 回退 document.body（保证不抛错）", () => {
    expect(getAppPortalRoot()).toBe(document.body);
  });
});
