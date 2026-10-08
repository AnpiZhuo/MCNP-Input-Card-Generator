// @vitest-environment jsdom
/**
 * 3D 预览数据桥 · 预置网格（STEP 方向预览）回归 —— 2026-10-08 用户要求「要新窗口」。
 *
 * 契约：方向预览复用**同一个独立窗口**（label `preview3d`，不再新增窗口类型），
 * 于是 `windows.ts` 的桥必须能把"预置网格 + 标题"带过去：
 *   · 新窗口据此直接渲染（`Preview3DWindow` → `Preview3D` 预置模式），**不再调后端**；
 *   · 兼容旧签名（传 deck 取材料表），避免影响既有「3D 预览」调用。
 */
import { beforeEach, describe, expect, it } from "vitest";
import { openPreview3D, readPreview3DData } from "../src/utils/windows";

beforeEach(() => localStorage.clear());

describe("3D 预览数据桥 · 预置网格", () => {
  it("★预置网格 / 标题随桥往返（新窗口据此渲染）", async () => {
    const opened = await openPreview3D({
      cells: [{ num: "1", mat: "1", comment: "STEP 模型（已按当前方向约定转好）", render: true }],
      surfaces: "",
      trCards: "",
      materials: [],
      preloadedStl: { "1": "AAA" },
      preloadToken: "t1",
      titleOverride: "📐 STEP 方向预览 — 上轴 Y 朝上",
    });
    // jsdom 里没有 Tauri ⇒ invoke 失败返回 false（调用方据此回退到窗内浮层）
    expect(opened).toBe(false);

    const d = readPreview3DData();
    expect(d).toBeTruthy();
    expect(d!.preloadedStl).toEqual({ "1": "AAA" });
    expect(d!.preloadToken).toBe("t1");
    expect(d!.titleOverride).toContain("STEP 方向预览");
    expect(d!.cells).toHaveLength(1);
    // 一次性消费
    expect(readPreview3DData()).toBeNull();
  });

  it("旧签名仍可用（传 deck ⇒ 材料表进桥），且不带预置网格", async () => {
    await openPreview3D({
      cells: [{ num: "1", mat: "1", render: true }],
      surfaces: "1 pz 0",
      trCards: "",
      deck: { materials: [{ number: 1, comment: "M1" }, { number: 2, comment: "" }] } as any,
    });
    const d = readPreview3DData()!;
    expect(d.materials).toEqual([{ number: 1, comment: "M1" }, { number: 2, comment: "" }]);
    expect(d.preloadedStl).toBeUndefined();
    expect(d.titleOverride).toBeUndefined();
  });
});
