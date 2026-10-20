import { describe, it, expect, vi, beforeEach } from "vitest";
import { isDepositionTally } from "../../src/volume/openVolume3DWindow";
import { cardTextToFmesh } from "../../src/volume/fmeshState";

/**
 * 「3D 结果」（体积窗口）桥载荷契约（2026-10-21，与 PTRAC 同源缺陷的回归闸门）
 *
 * 同源缺陷：旧实现把整份 base64 STL 写进 localStorage 桥（18 栅元 deck 实测 21,142,374 字符），
 * 超过 localStorage 配额（实测 ≈5,000,000 字符）⇒ QuotaExceededError ⇒ 子窗口读不到桥 ⇒
 * 「没有 3D 结果数据（请从主窗口「计数」标签页解析 MESHTAL 后打开）」。
 *
 * 契约：桥里只放几何描述（model.cells/surfaces/trCards）+ meshtal 元数据，**不放 STL**；
 * 外壳由子窗口自己调 /api/preview-3d 取（主窗口只预热后端 deck 指纹缓存）。
 */
const HUGE_B64 = "A".repeat(7_000_000);

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
    openVolume3D: vi.fn(async (data: any) => {
      (globalThis as any).__volumeBridge = data;
      return true;
    }),
  };
});

import { openVolume3DWindow } from "../../src/volume/openVolume3DWindow";
import type { MeshtalTallyMeta } from "../../src/utils/api";

const MODEL = {
  cells: [
    { num: "1", mat: "4", density: "-2.70", surface_expr: "1 18 -20", comment: "最内壁" },
    { num: "2", mat: "2", density: "-8.00", surface_expr: "1 28 -30" },
  ],
  surfaces: "1 CY 0.5\n18 SO 1.8\n20 SO 2.0\n28 SO 2.8\n30 SO 3.0",
  trCards: "",
};

const TALLY: MeshtalTallyMeta = {
  number: 4,
  particle: "n",
  geom: "xyz",
  unsupportedGeom: false,
  dims: { ni: 5, nj: 5, nk: 5, energyBins: 2, timeBins: 2, nVoxels: 125 },
  binEdges: { x: [-100, 100], y: [-100, 100], z: [-150, -50], energy: [0, 3, 14], time: [-1e36, 2, 3] },
  range: { min: 0, max: 1.06, count: 125 },
};

describe("openVolume3DWindow 桥载荷（不得携带 STL）", () => {
  beforeEach(() => { (globalThis as any).__volumeBridge = null; vi.clearAllMocks(); });

  it("★桥 JSON 必须远小于 localStorage 配额，且不含 stlData", async () => {
    const out = await openVolume3DWindow({ path: "D:/MCNP/new/meshtal", tally: TALLY, resolution: 128, model: MODEL });
    expect(out.ok).toBe(true);
    const payload = JSON.stringify((globalThis as any).__volumeBridge);
    expect(payload.length).toBeLessThan(200_000);
    expect(payload).not.toContain("stlData");
  });

  it("几何描述随桥下行（子窗口自取外壳）+ meshtal 元数据原样传递", async () => {
    await openVolume3DWindow({ path: "D:/MCNP/new/meshtal", tally: TALLY, resolution: 128, model: MODEL });
    const bridge = (globalThis as any).__volumeBridge;
    expect(bridge.meshtal).toMatchObject({ path: "D:/MCNP/new/meshtal", tallyNumber: 4, resolution: 128 });
    expect(bridge.model).toBeTruthy();
    expect(bridge.model.surfaces).toContain("CY 0.5");
    expect(bridge.model.cells[0]).toMatchObject({ number: 1, material: "4", surface_expr: "1 18 -20" });
  });

  it("无模型 → model=null，不取 STL", async () => {
    const api = await import("../../src/utils/api");
    await openVolume3DWindow({ path: "D:/MCNP/new/meshtal", tally: TALLY, resolution: 128, model: null });
    expect((globalThis as any).__volumeBridge.model ?? null).toBeNull();
    expect(api.fetchPreview3dStl).not.toHaveBeenCalled();
  });
});

describe("isDepositionTally — *fmesh 能量沉积判定", () => {
  it("卡号匹配且 fn_prefix='*' → 能量沉积", () => {
    const fmesh = cardTextToFmesh([
      "*fmesh14:N GEOM=XYZ ORIGIN=0 0 0",
      "     IMESH=10 IINTS=2",
      "     JMESH=10 JINTS=2",
    ].join("\n"));
    expect(isDepositionTally(fmesh, 14)).toBe(true);
  });

  it("卡号匹配但无 *（普通 fefm）→ 非能量沉积", () => {
    const fmesh = cardTextToFmesh("FMESH14:N GEOM=XYZ ORIGIN=0 0 0\n     IMESH=10 IINTS=2");
    expect(isDepositionTally(fmesh, 14)).toBe(false);
  });

  it("卡号不匹配 → 非能量沉积；空列表 → false", () => {
    const fmesh = cardTextToFmesh("*fmesh14:N GEOM=XYZ ORIGIN=0 0 0\n     IMESH=10 IINTS=2");
    expect(isDepositionTally(fmesh, 15)).toBe(false);
    expect(isDepositionTally([], 14)).toBe(false);
    expect(isDepositionTally(undefined, 14)).toBe(false);
  });
});
