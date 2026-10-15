/**
 * frameBox 取景口径回归：① 不可见栅元不参与取景；② 真空即便勾选也不参与（「不影响实体查看」）。
 * 原缺陷：frameCamera 对所有 mesh 求并集而不看 visible ⇒ 画不出来的巨型外围壳（500 cm）
 * 照样把相机撑开、模型缩成一点。红证：去掉 `visible === false` 判断 → 3 条变红；
 * 把 `if (c.solid)` 改成恒真 → 2 条变红（两条口径各自实测过）。
 */
import { describe, expect, it } from "vitest";
import { computeFrameBox, type BoxLike } from "../src/three/frameBox";

/** 以原点为中心的立方盒，半边长 r */
const cube = (r: number): BoxLike => ({ min: [-r, -r, -r], max: [r, r, r] });

describe("computeFrameBox — 取景只按可见实体", () => {
  it("不可见的巨型外围壳不得参与取景（用户取消勾选了大壳 → 相机必须贴合模型）", () => {
    const r = computeFrameBox([
      { box: cube(250), visible: false, solid: true },  // 被取消勾选的大壳：画不出来，却曾把相机撑到 ±250
      { box: cube(52), visible: true, solid: true },    // 模型本体（外层屏蔽 104 cm 见方）
    ]);
    expect(r).not.toBeNull();
    expect(r!.size).toEqual([104, 104, 104]);
    expect(r!.center).toEqual([0, 0, 0]);
  });

  it("真空壳即便被勾选可见，也不得参与取景（不影响实体查看）", () => {
    const r = computeFrameBox([
      { box: cube(250), visible: true, solid: false }, // 用户勾上了真空显示（真半透明档）
      { box: cube(52), visible: true, solid: true },
    ]);
    expect(r!.size).toEqual([104, 104, 104]);
    expect(r!.model).toEqual(cube(52));
  });

  it("全部不可见（且无 extra）→ 不取景", () => {
    expect(computeFrameBox([{ box: cube(250), visible: false, solid: true }])).toBeNull();
  });

  it("纯真空 deck（没有实体可看）→ 回退到可见并集，仍取景", () => {
    const r = computeFrameBox([{ box: cube(250), visible: true, solid: false }]);
    expect(r).not.toBeNull();
    expect(r!.size).toEqual([500, 500, 500]);
  });

  it("无可见栅元但有 extra（格阵装配路径）→ 仍以 extra 取景", () => {
    const r = computeFrameBox([], { extra: cube(10) });
    expect(r).not.toBeNull();
    expect(r!.size).toEqual([20, 20, 20]);
    expect(r!.center).toEqual([0, 0, 0]);
  });

  it("extra（线框/装配）只撑 frame 尺寸，不改 center", () => {
    const r = computeFrameBox([{ box: cube(1), visible: true, solid: true }], { extra: cube(10) });
    expect(r!.center).toEqual([0, 0, 0]);
    expect(r!.size).toEqual([20, 20, 20]);
    expect(r!.model).toEqual(cube(1));
  });

  it("包围盒缺失（geometry 未算 bbox）的候选跳过，不污染取景", () => {
    const r = computeFrameBox([
      { box: null, visible: true, solid: true },
      { box: cube(3), visible: true, solid: true },
    ]);
    expect(r!.size).toEqual([6, 6, 6]);
  });

  it("includeOrigin:false 时 frame 不含原点（默认含）", () => {
    const off = computeFrameBox(
      [{ box: { min: [10, 10, 10], max: [12, 12, 12] }, visible: true, solid: true }],
      { includeOrigin: false });
    expect(off!.size).toEqual([2, 2, 2]);
    const on = computeFrameBox([{ box: { min: [10, 10, 10], max: [12, 12, 12] }, visible: true, solid: true }]);
    expect(on!.size).toEqual([12, 12, 12]); // 原点并入后从 0 到 12
  });

  it("多个可见实体取并集（不可见的、真空的都被排除）", () => {
    const r = computeFrameBox([
      { box: { min: [-1, -1, -1], max: [1, 1, 1] }, visible: true, solid: true },
      { box: { min: [0, 0, 0], max: [4, 4, 4] }, visible: true, solid: true },
      { box: cube(500), visible: true, solid: false },
      { box: cube(600), visible: false, solid: true },
    ]);
    expect(r!.model).toEqual({ min: [-1, -1, -1], max: [4, 4, 4] });
  });
});
