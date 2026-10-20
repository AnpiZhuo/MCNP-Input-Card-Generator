// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from "vitest";
import { openPtrac3DWindow } from "../../src/ptrac/openPtracWindow";

/**
 * PTRAC 开窗桥载荷契约（2026-10-21 用户实测缺陷的回归闸门）
 *
 * 缺陷实录（部署版 CDP 复现，主窗口 console）：
 *   `ptrac bridge write failed QuotaExceededError: … Setting the value of 'mcnp_win_ptrac' exceeded the quota.`
 *   → 子窗口照开但读不到桥 → 只显示「没有 3D 径迹数据（请从主窗口「输出」标签页解析 PTRAC 后打开）」。
 *
 * 根因：`openPtrac3DWindow` 把整份几何外壳 STL（base64，实测 18 栅元 deck = 21,142,374 字符）塞进
 * localStorage 的 `mcnp_win_ptrac`；Chromium/WebView2 单 origin localStorage 配额实测上限
 * ≈5,000,000 字符（10 MB UTF-16）⇒ setItem 必抛 QuotaExceededError。
 *
 * 契约：桥里**只准**放几何描述（cells/surfaces/trCards）+ 径迹文件路径，**不准**放 STL；
 * 外壳由子窗口自己调 /api/preview-3d 取（契约 ptrac-visualization.md §4 原本就这么写）。
 */
const HUGE_B64 = "A".repeat(7_000_000); // 实测热室卡单栅元 STL base64 ≈7.0M 字符

vi.mock("../../src/utils/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/utils/api")>();
  return {
    ...actual,
    fetchPreview3dStl: vi.fn(async () => ({ "1": HUGE_B64 })),
  };
});

vi.mock("../../src/utils/windows", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/utils/windows")>();
  return {
    ...actual,
    openPtracWindow: vi.fn(async (data: any) => {
      (globalThis as any).__ptracBridge = data;
      return true;
    }),
  };
});

import { openPtracWindow } from "../../src/utils/windows";

const MODEL = {
  cells: [
    { num: "1", mat: "4", density: "-2.70", surface_expr: "1 18 -20", comment: "最内壁" },
    { num: "2", mat: "2", density: "-8.00", surface_expr: "1 28 -30" },
  ],
  surfaces: "1 CY 0.5\n18 SO 1.8\n20 SO 2.0\n28 SO 2.8\n30 SO 3.0",
  trCards: "",
};

describe("openPtrac3DWindow 桥载荷（不得携带 STL）", () => {
  beforeEach(() => { (globalThis as any).__ptracBridge = null; vi.clearAllMocks(); });

  it("★桥 JSON 必须远小于 localStorage 配额（实测上限 ≈5M 字符）", async () => {
    const out = await openPtrac3DWindow({ path: "D:/MCNP/new/ptrac", model: MODEL });
    expect(out.ok).toBe(true);
    const bridge = (globalThis as any).__ptracBridge;
    expect(bridge).toBeTruthy();
    const payload = JSON.stringify(bridge);
    // 红证（修前）：21M 级 → 必抛 QuotaExceededError；修后只含几何描述，几十 KB 以内
    expect(payload.length).toBeLessThan(200_000);
    expect(payload).not.toContain("stlData");
  });

  it("几何描述随桥下行（子窗口据此自取外壳）+ 径迹路径/上限原样传递", async () => {
    await openPtrac3DWindow({ path: "D:/MCNP/new/ptrac", model: MODEL });
    const bridge = (globalThis as any).__ptracBridge;
    expect(bridge.ptracPath).toBe("D:/MCNP/new/ptrac");
    expect(bridge.maxTracks).toBe(100000);
    expect(bridge.maxPoints).toBe(200000);
    // 子窗口需要 surfaces/trCards + 后端形状的 cells 才能调 /api/preview-3d
    expect(bridge.model).toBeTruthy();
    expect(bridge.model.surfaces).toContain("CY 0.5");
    expect(bridge.model.cells[0]).toMatchObject({ number: 1, material: "4", surface_expr: "1 18 -20" });
    // 显示用 cells（材料色）仍保留
    expect(bridge.cells[0]).toMatchObject({ num: "1", mat: "4" });
  });

  it("无模型（空 deck）→ 桥里 model=null，不取 STL", async () => {
    const api = await import("../../src/utils/api");
    await openPtrac3DWindow({ path: "D:/MCNP/new/ptrac", model: null });
    const bridge = (globalThis as any).__ptracBridge;
    expect(bridge.model ?? null).toBeNull();
    expect(api.fetchPreview3dStl).not.toHaveBeenCalled();
  });
});

describe("openPtracWindow 调用失败时不得静默成功", () => {
  it("桥写入失败（openPtracWindow 抛错）→ outcome.kind === 'error' 且带提示", async () => {
    (openPtracWindow as any).mockRejectedValueOnce(new Error("3D 径迹数据过大（测试注入）"));
    const out = await openPtrac3DWindow({ path: "D:/MCNP/new/ptrac", model: MODEL });
    if (out.ok) throw new Error("桥写入失败时不得返回 ok:true（否则会开一个读不到数据的空窗口）");
    expect(out.kind).toBe("error");
    expect(out.message).toContain("过大");
  });
});
