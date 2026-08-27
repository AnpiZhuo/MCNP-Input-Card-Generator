/**
 * latticeInstances — 格阵 3D 实例化深模块测试（阶段3）。
 *
 * 覆盖：
 *  - parseTrclDeg（rect mod 90 / hex mod 60 离散归一）
 *  - composeNestedPositions（rect 基本 + 嵌套 fill 递归 10 叶绝对坐标）
 *  - buildLatticeInstances（详细模式按 (u,cellNum) 分组 / M0 透明 / 总览模式单色块）
 *  - instanceIndexAt（点击实例 id → 格位索引，void 过滤语义）
 *  - 跨语言 golden positions 段（后端产出后自动生效；未产出 skip）
 */
import { describe, expect, it } from "vitest";
import * as THREE from "three";
import {
  buildLatticeInstances,
  composeNestedPositions,
  DETAIL_MAX_INSTANCES,
  instanceIndexAt,
  nonVoidFrameLeaves,
  parseTrclDeg,
} from "../src/three/latticeInstances";
import type { LatticeComposeNode, LatticeInstance } from "../src/three/latticeInstances";
import { hexCenter } from "../src/utils/lattice";
import golden from "../src/utils/__golden__/latticeGolden.json";

function boxGeo(w = 2, h = 2, d = 2): THREE.BoxGeometry {
  const g = new THREE.BoxGeometry(w, h, d);
  g.computeBoundingSphere();
  return g;
}

/* ── parseTrclDeg（TRCL 离散 90°/60° 绕 Z） ── */

describe("parseTrclDeg", () => {
  it("rect(lat=1) 绕 Z mod 90：90°/270° → 0", () => {
    expect(parseTrclDeg("0 0 90", "1")).toBe(0);
    expect(parseTrclDeg("0 0 270", "1")).toBe(0);
    expect(parseTrclDeg("0 0 45", "1")).toBe(45);
    expect(parseTrclDeg("0 0 180", "1")).toBe(0);
  });
  it("hex(lat=2) 绕 Z mod 60：120°/300° → 0，90° → 30", () => {
    expect(parseTrclDeg("0 0 120", "2")).toBe(0);
    expect(parseTrclDeg("0 0 300", "2")).toBe(0);
    expect(parseTrclDeg("0 0 90", "2")).toBe(30);
    expect(parseTrclDeg("0 0 60", "2")).toBe(0);
  });
  it("单/双 token 取末位；空串/无 lat 走 mod 360 原角", () => {
    expect(parseTrclDeg("90")).toBe(90);          // 无 lat → 原角
    expect(parseTrclDeg("30 60 45")).toBe(45);     // 取第 3 个（Z 角）
    expect(parseTrclDeg("")).toBe(0);
    expect(parseTrclDeg(undefined)).toBe(0);
    expect(parseTrclDeg("abc")).toBe(0);
  });
  it("负角归一", () => {
    expect(parseTrclDeg("0 0 -90", "1")).toBe(0);   // -90 mod 90 = 0
    expect(parseTrclDeg("0 0 -30", "2")).toBe(30);  // -30 mod 60 = 30
  });
});

/* ── composeNestedPositions：rect 基本 ── */

describe("composeNestedPositions（rect 基本）", () => {
  const node: LatticeComposeNode = {
    lat: "1",
    dims: [2, 2, 1],
    cellSize: { x: 4, y: 4, z: 2 },
    cells: [
      { u: "5", dx: 0, dy: 0, dz: 0, inst: [{ cellNum: "1", mat: "1" }] },
      { u: "6", dx: 1, dy: 0, dz: 0, inst: [{ cellNum: "2", mat: "2" }] },
      { u: "0", dx: 0, dy: 0, dz: 0, inst: [{ cellNum: "3", mat: "1" }] },
      { u: "5", dx: 0, dy: 0, dz: 0, inst: [{ cellNum: "1", mat: "1" }] },
    ],
  };

  it("默认居中 origin：cell(0,0,0) 中心 = (-2,-2,0)，行主序", () => {
    const { leafInstances } = composeNestedPositions(node);
    expect(leafInstances).toHaveLength(3); // void(0) 格位不产生叶
    expect(leafInstances[0]).toMatchObject({ path: "0", u: "5", cellNum: "1", x: -2, y: -2, z: 0, depth: 0 });
    // 条目 (dx dy dz) 偏移应用
    expect(leafInstances[1]).toMatchObject({ path: "1", u: "6", cellNum: "2", x: 2 + 1, y: -2, z: 0 });
    expect(leafInstances[2]).toMatchObject({ path: "3", u: "5", cellNum: "1", x: 2, y: 2, z: 0 });
  });

  it("NESTED 根盒 = 全部格元盒并集", () => {
    const { nested } = composeNestedPositions(node);
    expect(nested.box.min).toEqual([-4, -4, -1]);
    expect(nested.box.max).toEqual([4, 4, 1]);
    expect(nested.leaves).toHaveLength(3);
    expect(nested.nested).toHaveLength(0);
  });
});

/* ── composeNestedPositions：嵌套 fill 递归（2×2 外 pitch4 内嵌 2×2 pitch2，10 叶） ── */

describe("composeNestedPositions（嵌套 fill 递归）", () => {
  const inner: LatticeComposeNode = {
    lat: "1",
    dims: [2, 2, 1],
    cellSize: { x: 2, y: 2, z: 2 },
    cells: [
      { u: "5", dx: 0, dy: 0, dz: 0, inst: [{ cellNum: "1", mat: "1" }] },
      { u: "5", dx: 0, dy: 0, dz: 0, inst: [{ cellNum: "1", mat: "1" }] },
      { u: "5", dx: 0, dy: 0, dz: 0, inst: [{ cellNum: "1", mat: "1" }] },
      { u: "5", dx: 0.5, dy: 0.5, dz: 0, inst: [{ cellNum: "1", mat: "1" }] },
    ],
  };
  const node: LatticeComposeNode = {
    lat: "1",
    dims: [2, 2, 1],
    cellSize: { x: 4, y: 4, z: 2 },
    cells: [
      { u: "", dx: 0, dy: 0, dz: 0, child: inner }, // 外 idx0 → 子格阵
      { u: "5", dx: 0, dy: 0, dz: 0, inst: [{ cellNum: "1", mat: "1" }] }, // 直接
      { u: "5", dx: 0, dy: 0, dz: 0, inst: [{ cellNum: "1", mat: "1" }] }, // 直接
      { u: "", dx: 0, dy: 0, dz: 0, child: inner }, // 外 idx3 → 子格阵
    ],
  };

  it("10 叶绝对坐标（DFS 序：idx0 子格 4 → idx1/idx2 直接 → idx3 子格 4）", () => {
    const { leafInstances } = composeNestedPositions(node);
    expect(leafInstances).toHaveLength(10);
    const byPath = new Map(leafInstances.map((l) => [l.path, l]));
    // 契约（Python compose_lattice_tree 对齐）：子格阵整体居中于父格位中心——
    // child origin = 父格位中心 + 子格默认居中偏移（子格 cell(0,0,0) = 父中心 − 子 pitch·(nx−1)/2）
    // 外 idx0（父格位中心 (-2,-2,0) + 子默认 (-1,-1) = child origin (-3,-3,0)）
    expect(byPath.get("0.0")).toMatchObject({ u: "5", x: -3, y: -3, z: 0, depth: 1 });
    expect(byPath.get("0.1")).toMatchObject({ x: -1, y: -3, z: 0, depth: 1 });
    expect(byPath.get("0.2")).toMatchObject({ x: -3, y: -1, z: 0, depth: 1 });
    // 条目偏移应用（dx=0.5, dy=0.5）
    expect(byPath.get("0.3")).toMatchObject({ x: -0.5, y: -0.5, z: 0, depth: 1 });
    // 直接叶
    expect(byPath.get("1")).toMatchObject({ x: 2, y: -2, z: 0, depth: 0 });
    expect(byPath.get("2")).toMatchObject({ x: -2, y: 2, z: 0, depth: 0 });
    // 外 idx3（父格位中心 (2,2,0) + 子默认 (-1,-1) = child origin (1,1,0)）
    expect(byPath.get("3.0")).toMatchObject({ x: 1, y: 1, z: 0, depth: 1 });
    expect(byPath.get("3.3")).toMatchObject({ x: 2 + 1 + 0.5, y: 2 + 1 + 0.5, z: 0, depth: 1 });
  });

  it("NESTED 树：根含 2 子节点（各 4 叶）+ 2 直接叶，child box 平移到父格位", () => {
    const { nested } = composeNestedPositions(node);
    expect(nested.leaves).toHaveLength(2);
    expect(nested.nested).toHaveLength(2);
    // 外 idx0 子格阵 box（child origin = 父格位中心 + 子默认居中 = (-3,-3,0)；cellSize 2 半延展 1 → [-4,-4,-1]..[0,0,1]）
    const c0 = nested.nested[0];
    expect(c0.leaves).toHaveLength(4);
    expect(c0.box.min).toEqual([-4, -4, -1]);
    expect(c0.box.max).toEqual([0, 0, 1]);
    // 根盒 = 外层格元盒并集
    expect(nested.box.min).toEqual([-4, -4, -1]);
    expect(nested.box.max).toEqual([4, 4, 1]);
  });
});

/* ── buildLatticeInstances：详细 / 总览 ── */

function simplePositions(): LatticeInstance[] {
  return [
    { path: "0", u: "5", cellNum: "1", mat: "1", x: 0, y: 0, z: 0, depth: 0 },
    { path: "1", u: "5", cellNum: "1", mat: "1", x: 1, y: 0, z: 0, depth: 0 },
    { path: "2", u: "6", cellNum: "2", mat: "0", x: 2, y: 0, z: 0, depth: 0 },
  ];
}

describe("buildLatticeInstances（详细模式）", () => {
  const positions = simplePositions();
  const universeStl = { "5": { "1": boxGeo() }, "6": { "2": boxGeo() } };
  const cellMaterials = { "5": { "1": "1" }, "6": { "2": "0" } };
  const palette = { "5": "#ff0000", "6": "#00ff00" };

  it("按 (u, cellNum) 分组：5:1 一个 InstancedMesh（2 实例）+ 6:2 一个（1 实例）", () => {
    const { group } = buildLatticeInstances({ positions, universeStl, cellMaterials, palette });
    const meshes = group.userData.instancedMeshes as THREE.InstancedMesh[];
    expect(meshes).toHaveLength(2);
    expect(meshes[0].count).toBe(2);
    expect(meshes[1].count).toBe(1);
  });

  it("色 = getMatColor；M0 透明（opacity 0 / depthWrite false）", () => {
    const { group } = buildLatticeInstances({ positions, universeStl, cellMaterials, palette });
    const meshes = group.userData.instancedMeshes as THREE.InstancedMesh[];
    const m0 = meshes[0].material as THREE.MeshStandardMaterial;
    const m1 = meshes[1].material as THREE.MeshStandardMaterial;
    // mat=1 → getMatColor("1") = COLORS[1] = #00C853
    expect(m0.color.getHex()).toBe(new THREE.Color("#00C853").getHex());
    expect(m0.transparent).toBe(false);
    // mat=0 → 透明
    expect(m1.transparent).toBe(true);
    expect(m1.opacity).toBe(0);
    expect(m1.depthWrite).toBe(false);
  });

  it("void 格位（u=0）不实例化", () => {
    const withVoid = [
      { path: "0", u: "5", cellNum: "1", mat: "1", x: 0, y: 0, z: 0, depth: 0 },
      { path: "1", u: "0", cellNum: "1", mat: "1", x: 1, y: 0, z: 0, depth: 0 },
      { path: "2", u: "6", cellNum: "2", mat: "0", x: 2, y: 0, z: 0, depth: 0 },
    ];
    const { group } = buildLatticeInstances({ positions: withVoid, universeStl, cellMaterials, palette });
    const meshes = group.userData.instancedMeshes as THREE.InstancedMesh[];
    expect(meshes.reduce((a, m) => a + m.count, 0)).toBe(2);
  });

  it("dispose 释放几何/材质并清空 group", () => {
    const handle = buildLatticeInstances({ positions, universeStl, cellMaterials, palette });
    handle.dispose();
    expect(handle.group.children).toHaveLength(0);
    expect(handle.group.userData.instancedMeshes).toHaveLength(0);
  });
});

describe("buildLatticeInstances（总览模式）", () => {
  const positions = simplePositions();
  const palette = { "5": "#ff0000", "6": "#00ff00" };

  it("单 InstancedMesh，色 = getUniverseColor，count = 非 void 数", () => {
    const { group } = buildLatticeInstances({
      positions,
      universeStl: {},
      cellMaterials: {},
      palette,
      overviewMode: true,
      blockSize: { x: 2, y: 2, z: 2, hex: false },
    });
    const meshes = group.userData.instancedMeshes as THREE.InstancedMesh[];
    expect(meshes).toHaveLength(1);
    expect(meshes[0].count).toBe(3);
    const c = new THREE.Color();
    meshes[0].getColorAt(0, c);
    expect(c.getHex()).toBe(new THREE.Color("#ff0000").getHex());
    meshes[0].getColorAt(2, c);
    expect(c.getHex()).toBe(new THREE.Color("#00ff00").getHex());
  });

  it("总览 trclRotationDeg 作用到 group.rotation.z", () => {
    const { group } = buildLatticeInstances({
      positions,
      universeStl: {},
      cellMaterials: {},
      palette,
      overviewMode: true,
      trclRotationDeg: 30,
      blockSize: { x: 2, y: 2, z: 2, hex: false },
    });
    expect(group.rotation.z).toBeCloseTo((30 * Math.PI) / 180, 9);
  });

  it("DETAIL_MAX_INSTANCES = 1000000000（超限自动切总览的阈值常量，与后端一致）", () => {
    expect(DETAIL_MAX_INSTANCES).toBe(1000000000);
  });
});

/* ── instanceIndexAt：点击实例 id → 格位索引（void 过滤语义） ── */

describe("instanceIndexAt", () => {
  it("命中最近实例，返回 positions 过滤 void 后的下标", () => {
    const positions: LatticeInstance[] = [
      { path: "0", u: "5", cellNum: "1", mat: "1", x: 0, y: 0, z: 0, depth: 0 },
      { path: "1", u: "0", cellNum: "1", mat: "1", x: 2, y: 0, z: 0, depth: 0 }, // void 不实例化
      { path: "2", u: "5", cellNum: "1", mat: "1", x: 4, y: 0, z: 0, depth: 0 },
    ];
    const universeStl = { "5": { "1": boxGeo(2, 2, 2) } };
    const cellMaterials = { "5": { "1": "1" } };
    const { group } = buildLatticeInstances({ positions, universeStl, cellMaterials, palette: {} });
    const meshes = group.userData.instancedMeshes as THREE.InstancedMesh[];

    // 射线从 x=-10 沿 +X → 命中最近的格位（原 idx0 → 过滤后下标 0）
    const ray0 = new THREE.Raycaster(new THREE.Vector3(-10, 0, 0), new THREE.Vector3(1, 0, 0));
    expect(instanceIndexAt(ray0, meshes)).toBe(0);

    // 射线从 x=2 沿 +X → 越过 idx0（盒 -1..1）命中 idx2 → 过滤后下标 1
    const ray1 = new THREE.Raycaster(new THREE.Vector3(2, 0, 0), new THREE.Vector3(1, 0, 0));
    expect(instanceIndexAt(ray1, meshes)).toBe(1);

    // 反向射线（未命中任何实例）→ null
    const rayMiss = new THREE.Raycaster(new THREE.Vector3(10, 0, 0), new THREE.Vector3(1, 0, 0));
    expect(instanceIndexAt(rayMiss, meshes)).toBeNull();
  });
});

/* ── nonVoidFrameLeaves（项15：void 叶不计入取景 bbox，防巨型边界 void 撑大取景） ── */

describe("nonVoidFrameLeaves（项15 取景过滤）", () => {
  it("mat='0' 的 void 叶被滤除，实体叶保留", () => {
    const leaves: LatticeInstance[] = [
      { path: "0", u: "10", cellNum: "1", mat: "1", x: 0, y: 0, z: 0, depth: 0 },
      { path: "1", u: "10", cellNum: "2", mat: "0", x: 1000, y: 1000, z: 1000, depth: 0 }, // 巨型边界 void（so 1000）
      { path: "2", u: "10", cellNum: "3", mat: "0", x: 0, y: 0, z: 0, depth: 0 },            // 普通 void 叶
      { path: "3", u: "20", cellNum: "4", mat: "2", x: 5, y: 5, z: 0, depth: 1 },
    ];
    const frame = nonVoidFrameLeaves(leaves);
    expect(frame.map((p) => p.cellNum)).toEqual(["1", "4"]);
  });
  it("全 void → 空数组（取景兜底 0..1）", () => {
    const leaves: LatticeInstance[] = [
      { path: "0", u: "10", cellNum: "1", mat: "0", x: 10, y: 10, z: 10, depth: 0 },
    ];
    expect(nonVoidFrameLeaves(leaves)).toEqual([]);
  });
});

/* ── 跨语言 golden：positions / nested 段（backend expand_positions / compose_lattice_tree 双端锁死） ── */

/** expand_positions 参考实现（镜像 Python app/lattice.py：rect 居中 / hex 蜂窝 + TRCL 绕 Z） */
function expandPositionsRef(s: any): { idx: number; x: number; y: number; z: number }[] {
  const dims = s.dims as number[];
  const nx = Math.max(1, dims[0] ?? 1);
  const ny = Math.max(1, dims[1] ?? 1);
  const nz = Math.max(1, dims[2] ?? 1);
  const span = (ax: string): number => {
    const lo = s.extent?.[`${ax}_min`];
    const hi = s.extent?.[`${ax}_max`];
    if (lo != null && hi != null && hi - lo > 0) return hi - lo;
    return 1;
  };
  let px = span("x");
  let py = span("y");
  const pz = span("z");
  if (s.lat === "2") {
    // 面法向 0°/60°/120°：格距 = 平面对边距 = x 跨度（镜像 Python _lattice_pitch 修复）
    const hp = px > 0 ? px : py > 0 ? py : 1;
    px = hp;
    py = hp;
  }
  const theta = ((s.trclDeg ?? 0) * Math.PI) / 180;
  const cosT = Math.cos(theta);
  const sinT = Math.sin(theta);
  const out: { idx: number; x: number; y: number; z: number }[] = [];
  for (let k = 0; k < nz; k++) {
    for (let j = 0; j < ny; j++) {
      for (let i = 0; i < nx; i++) {
        const idx = i + nx * (j + ny * k);
        let hx: number;
        let hy: number;
        if (s.lat === "2") {
          const h = hexCenter(i, j, px); // 复用画布/阶段3共用权威蜂窝公式（golden 锁死）
          hx = h.x;
          hy = h.y;
        } else {
          hx = (i - (nx - 1) / 2) * px;
          hy = (j - (ny - 1) / 2) * py;
        }
        const cz = (k - (nz - 1) / 2) * pz;
        out.push({ idx, x: hx * cosT - hy * sinT, y: hx * sinT + hy * cosT, z: cz });
      }
    }
  }
  return out;
}

describe("跨语言 golden positions/nested/composeCases（backend expand_positions / compose_lattice_tree 双端锁死）", () => {
  // golden 实际键名：positions = 数组（id/lat/dims/extent/trclDeg/expected）；
  // nested = 对象（outerLat/innerLat/outerExtent/innerExtent/universeCells/leafCount/leaves）；
  // composeCases = 数组（TS LatticeComposeNode 输入样例，与 nested 段同源）。
  // 后端未产出阶段3 golden 时跳过；产出后本用例真正跑起来（消除 skip）。
  const positions = (golden as any).positions as any[] | undefined;
  const nested = (golden as any).nested as any;
  const composeCases = (golden as any).composeCases as any[] | undefined;
  const hasGolden =
    Array.isArray(positions) && positions.length > 0 &&
    !!nested && Array.isArray(nested.leaves) && nested.leaves.length > 0 &&
    Array.isArray(composeCases) && composeCases.length > 0 && !!composeCases[0].node;

  it.skipIf(!hasGolden)("positions 格位中心 + composeNestedPositions 输出 === nested.leaves（双端逐位锁死）", () => {
    // positions 段：expand_positions 输出，expected 与 rect/hex+TRCL 参考重算逐位一致
    for (const s of positions!) {
      const recomputed = expandPositionsRef(s);
      for (const exp of s.expected) {
        const got = recomputed.find((p) => p.idx === exp.idx)!;
        expect(got.x).toBeCloseTo(exp.x, 9);
        expect(got.y).toBeCloseTo(exp.y, 9);
        expect(got.z).toBeCloseTo(exp.z, 9);
      }
    }

    // nested 段：composeNestedPositions(composeCases[].node) 的 FLAT 叶绝对坐标
    // === nested.leaves（Python tests/unit/test_lattice.py test_nested_golden_cross_language
    // 对同一 golden 数据双端逐位一致，2×2 外 pitch4 内嵌 2×2 pitch2 共 10 叶）
    expect(nested.leafCount).toBe(10);
    expect(nested.leaves).toHaveLength(nested.leafCount);
    const expLeaves = nested.leaves.map((l: any) => `${l.cellNum}@${l.x},${l.y},${l.z}`);
    for (const cc of composeCases!) {
      const { leafInstances } = composeNestedPositions(cc.node as LatticeComposeNode);
      expect(leafInstances).toHaveLength(nested.leaves.length);
      const got = leafInstances.map((l) => `${l.cellNum}@${l.x},${l.y},${l.z}`);
      expect(got).toHaveLength(expLeaves.length); // 无重复
      expect(new Set(got)).toEqual(new Set(expLeaves)); // 双向一致
    }
  });
});
