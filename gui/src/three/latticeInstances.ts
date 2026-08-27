/**
 * latticeInstances — 格阵 3D 实例化深模块（阶段3：universe 实例化方案）。
 *
 * 方案镜像 MCNP：每 universe 一份 STL（后端按格元盒裁剪构建），按 fill 位置
 * 前端 InstancedMesh 复用。本模块只做「位置组合 + 实例化」，纯 THREE 场景构建
 * （InstancedMesh / BufferGeometry / Color / Matrix4 均可 node 无头构造，不依赖
 * WebGL），不碰 React；STL 解码（base64→BufferGeometry）由调用方（
 * Preview3DLattice）用 STLLoader 完成。
 *
 * 与 Python app/lattice.py 阶段3扩展 compose_lattice_tree 的 NESTED/FLAT 双形态
 * 逐位一致（跨语言 golden：gui/src/utils/__golden__/latticeGolden.json 的
 * positions/nested 段，后端产出后 TS/Python 双端断言；未产出时测试 skip）。
 *
 * 位置约定（与阶段2画布/子预览锁定一致）：
 *   - rect(lat=1)：格位中心 = origin + (i·px, j·py, k·pz)，默认 origin 使格阵居中
 *     （cell(0,0,0) 中心 = (-(nx-1)/2·px, -(ny-1)/2·py, -(nz-1)/2·pz)）。
 *   - hex(lat=2)：格位中心 = origin + hexCenter(i,j,pitch)，默认 origin=[0,0,0]
 *     （hexCenter 为画布与阶段3共用权威公式，golden 锁死）。
 *   - 格元盒（裁剪 bound）= {x: cellSize.x, y: (rect=cellSize.y / hex=cellSize.x), z: cellSize.z}。
 */
import * as THREE from "three";
import { getUniverseColor, hexCenter } from "../utils/lattice";
import { getMatColor } from "../utils/materialColors";

/* ── 数据模型（镜像 Python compose_lattice_tree 的 NESTED/FLAT 双形态）── */

/** FLAT 叶实例（绝对坐标；InstancedMesh 直食） */
export interface LatticeInstance {
  /** 从根到叶的格位路径：外层格阵第3格→子格阵第1格 = "3.1"（根格阵内 = "3"） */
  path: string;
  /** universe（格位引用的宇宙号） */
  u: string;
  /** universe 内栅元号（STL key；该格位 universe 的直接可见栅元） */
  cellNum: string;
  /** 材料号（M0=真空透明） */
  mat: string;
  /** 绝对坐标（格位中心 + 条目 (dx dy dz) 偏移） */
  x: number;
  y: number;
  z: number;
  /** 嵌套深度（0 = 根格阵格位） */
  depth: number;
}

/** 裁剪盒（绝对坐标） */
export interface LatticeClipBox {
  min: [number, number, number];
  max: [number, number, number];
}

/** 单个格位（compose 输入）：u + 条目偏移 + 该 universe 的直接栅元 / 嵌套子格阵 */
export interface LatticeComposeCell {
  u: string;
  dx: number;
  dy: number;
  dz: number;
  /** 该格位 universe 的直接可见栅元列表（无嵌套时）；每个产生一个叶实例 */
  inst?: { cellNum: string; mat: string }[];
  /** 嵌套子格阵（该格位 universe 本身是格阵，递归展开） */
  child?: LatticeComposeNode;
}

/** 格阵节点（compose 输入）：dimensions + 格元盒尺寸 + origin */
export interface LatticeComposeNode {
  /** "1" 矩形 | "2" 六棱柱 */
  lat: string;
  /** [cols, rows, layers]，行主序（i 最快） */
  dims: number[];
  /** 格元盒尺寸：rect = {x: pitchX, y: pitchY, z: 高度}；hex = {x: pitch, z: 高度}（y 忽略） */
  cellSize: { x: number; y: number; z: number };
  /** 第 0 格位 (i=0,j=0,k=0) 的中心（绝对坐标）；默认：rect 居中 / hex [0,0,0] */
  origin?: [number, number, number];
  cells: LatticeComposeCell[];
}

/** NESTED 形态节点：本格阵裁剪盒 + 直接叶 + 嵌套子格阵 */
export interface NestedLatticeNode {
  box: LatticeClipBox;
  leaves: LatticeInstance[];
  nested: NestedLatticeNode[];
}

export interface ComposeResult {
  /** NESTED 形态（递归树 + 盒） */
  nested: NestedLatticeNode;
  /** FLAT 形态（DFS 序叶实例，绝对坐标，InstancedMesh 直食） */
  leafInstances: LatticeInstance[];
}

/* ── 位置组合（TS 镜像 Python compose_lattice_tree）── */

function nodeDims(node: LatticeComposeNode): [number, number, number] {
  const nx = Math.max(1, node.dims[0] ?? 1);
  const ny = Math.max(1, node.dims[1] ?? 1);
  const nz = Math.max(1, node.dims[2] ?? 1);
  return [nx, ny, nz];
}

function defaultOrigin(node: LatticeComposeNode, dims: [number, number, number]): [number, number, number] {
  if (node.lat === "2") return [0, 0, 0];
  const [nx, ny, nz] = dims;
  return [
    (-(nx - 1) / 2) * node.cellSize.x,
    (-(ny - 1) / 2) * node.cellSize.y,
    (-(nz - 1) / 2) * node.cellSize.z,
  ];
}

/** 格位中心（绝对坐标；rect 居中 / hex 原始蜂窝公式，与阶段2锁定一致） */
function gridCenter(
  node: LatticeComposeNode,
  idx: number,
  origin: [number, number, number],
  dims: [number, number, number],
): [number, number, number] {
  const [nx, ny] = dims;
  const i = idx % nx;
  const j = Math.floor(idx / nx) % ny;
  const k = Math.floor(idx / (nx * ny));
  if (node.lat === "2") {
    const h = hexCenter(i, j, node.cellSize.x);
    return [origin[0] + h.x, origin[1] + h.y, origin[2] + k * node.cellSize.z];
  }
  return [
    origin[0] + i * node.cellSize.x,
    origin[1] + j * node.cellSize.y,
    origin[2] + k * node.cellSize.z,
  ];
}

/** 格元盒（裁剪 bound）：hex 用 pitch×pitch（y 取 cellSize.x），rect 用 cellSize.x/y */
function cellHalfExtents(node: LatticeComposeNode): [number, number, number] {
  const y = node.lat === "2" ? node.cellSize.x : node.cellSize.y;
  return [node.cellSize.x / 2, y / 2, node.cellSize.z / 2];
}

function cellBox(node: LatticeComposeNode, c: [number, number, number]): LatticeClipBox {
  const [hx, hy, hz] = cellHalfExtents(node);
  return {
    min: [c[0] - hx, c[1] - hy, c[2] - hz],
    max: [c[0] + hx, c[1] + hy, c[2] + hz],
  };
}

function latticeBox(
  node: LatticeComposeNode,
  origin: [number, number, number],
  dims: [number, number, number],
): LatticeClipBox {
  const [nx, ny, nz] = dims;
  const box: LatticeClipBox = {
    min: [Infinity, Infinity, Infinity],
    max: [-Infinity, -Infinity, -Infinity],
  };
  for (let k = 0; k < nz; k++) {
    for (let j = 0; j < ny; j++) {
      for (let i = 0; i < nx; i++) {
        const idx = i + nx * (j + ny * k);
        const c = gridCenter(node, idx, origin, dims);
        const b = cellBox(node, c);
        for (let a = 0; a < 3; a++) {
          box.min[a] = Math.min(box.min[a], b.min[a]);
          box.max[a] = Math.max(box.max[a], b.max[a]);
        }
      }
    }
  }
  if (!Number.isFinite(box.min[0])) return { min: [0, 0, 0], max: [0, 0, 0] };
  return box;
}

function composeNode(
  node: LatticeComposeNode,
  origin: [number, number, number],
  depth: number,
  pathPrefix: string,
  out: LatticeInstance[],
): NestedLatticeNode {
  const dims = nodeDims(node);
  const [nx, ny] = dims;
  const leaves: LatticeInstance[] = [];
  const nested: NestedLatticeNode[] = [];
  for (let idx = 0; idx < node.cells.length; idx++) {
    const cell = node.cells[idx];
    const path = pathPrefix ? `${pathPrefix}.${idx}` : String(idx);
    const c = gridCenter(node, idx, origin, dims);
    if (cell.child) {
      // 与 Python compose_lattice_tree 逐位一致：子格阵整体居中于父格位中心——
      // child origin = 父格位中心 + 条目偏移 + 子格阵默认居中偏移
      // （rect：child cell(0,0,0) 中心 = 父格位中心 − 子 pitch·(nx−1)/2；hex 默认偏移 0）
      const childDims = nodeDims(cell.child);
      const childDefault = defaultOrigin(cell.child, childDims);
      const childCenter: [number, number, number] = [
        c[0] + cell.dx + childDefault[0],
        c[1] + cell.dy + childDefault[1],
        c[2] + cell.dz + childDefault[2],
      ];
      const childNode = composeNode(cell.child, childCenter, depth + 1, path, out);
      nested.push(childNode);
      continue;
    }
    if (!cell.u || cell.u === "0") continue; // void 格位不产生叶实例
    const insts = cell.inst && cell.inst.length ? cell.inst : [];
    for (const inst of insts) {
      const leaf: LatticeInstance = {
        path,
        u: cell.u,
        cellNum: inst.cellNum,
        mat: inst.mat,
        x: c[0] + cell.dx,
        y: c[1] + cell.dy,
        z: c[2] + cell.dz,
        depth,
      };
      leaves.push(leaf);
      out.push(leaf);
    }
  }
  return { box: latticeBox(node, origin, dims), leaves, nested };
}

/**
 * 组合格阵实例位置（NESTED/FLAT 双形态）。
 *
 * 嵌套 fill：外层格阵元素 universe 含子格阵时递归展开子格阵，子元素裁各自
 * 格元盒（box 挂在 NESTED 节点）平移到父格位——child 的 origin = 父格位中心
 * + 条目偏移 + 子格阵默认居中偏移（子格阵整体居中于父格位中心，与 Python
 * compose_lattice_tree 逐位一致），再整体裁外层盒；FLAT leafInstances 为 DFS
 * 序绝对坐标。
 */
export function composeNestedPositions(node: LatticeComposeNode): ComposeResult {
  const leafInstances: LatticeInstance[] = [];
  const dims = nodeDims(node);
  const origin = node.origin ?? defaultOrigin(node, dims);
  const nested = composeNode(node, origin, 0, "", leafInstances);
  return { nested, leafInstances };
}

/* ── TRCL 离散旋转（rect mod 90° / hex mod 60°，绕 Z）── */

/**
 * 解析 TRCL 旋转角（绕 Z，度）。TRCL = a1 a2 a3（绕 X/Y/Z 三个角）：
 * 取第 3 个（Z 轴）角；单/双 token 时取末位。
 * lat="1" → mod 90（矩形格阵绕 Z 旋转 90° 自同构）；lat="2" → mod 60
 * （六棱柱 60° 自同构）；无 lat → mod 360（原角）。
 */
export function parseTrclDeg(trclStr?: string, lat?: string): number {
  if (!trclStr) return 0;
  const toks = trclStr
    .trim()
    .split(/\s+/)
    .map((t) => parseFloat(t))
    .filter((n) => Number.isFinite(n));
  if (!toks.length) return 0;
  const z = toks.length >= 3 ? toks[2] : toks[toks.length - 1];
  const step = lat === "2" ? 60 : lat === "1" ? 90 : 360;
  return ((z % step) + step) % step;
}

/* ── InstancedMesh 构建 ── */

/**
 * 取景叶过滤（项 15）：void 叶（mat="0"）不计入相机包围盒（防巨型边界 void 如
 * so 1000 撑大包围盒拉远相机——「针尖」）。纯函数，可测。
 */
export function nonVoidFrameLeaves(leaves: LatticeInstance[]): LatticeInstance[] {
  return leaves.filter((p) => p.mat !== "0");
}

export interface LatticeInstancesOptions {
  /** FLAT 叶实例（绝对坐标；u="0"/空自动跳过不实例化） */
  positions: LatticeInstance[];
  /** universe → {cellNum: BufferGeometry}（STL 已解码；详细模式用） */
  universeStl: Record<string, Record<string, THREE.BufferGeometry>>;
  /** universe → {cellNum: 材料号}（详细模式取色；叶 mat 为空时的兜底） */
  cellMaterials: Record<string, Record<string, string>>;
  /** universe → 颜色（总览色块 / materialMode=false 时取色） */
  palette: Record<string, string>;
  /** true=按材料取色（getMatColor），false=按 universe 取色（默认 true） */
  materialMode?: boolean;
  /** 绕 Z 旋转角（度，TRCL 离散 90°/60° 已在 parseTrclDeg 归一） */
  trclRotationDeg?: number;
  /** true=单 InstancedMesh 色块总览（rect box / hex prism），默认 false */
  overviewMode?: boolean;
  /** 总览色块尺寸（格元盒）；hex: true 用六棱柱块 */
  blockSize?: { x: number; y: number; z: number; hex?: boolean };
}

export interface LatticeInstancesHandle {
  group: THREE.Group;
  dispose(): void;
}

/** 详细模式实例数上限：超出自动切总览（BEAVRS 全堆芯 ~30-60 万叶） */
export const DETAIL_MAX_INSTANCES = 2000000;

function colorToNumber(c: string): number {
  if (!c || c === "transparent") return 0x888888;
  const n = parseInt(c.replace("#", ""), 16);
  return Number.isFinite(n) ? n : 0x888888;
}

/** pointy-top 六棱柱实心几何（顶点朝 +X，轴向 +Z；外接半径 R，宽(对边)≈2R·cos30°） */
function buildHexPrismGeometry(circumradius: number, height: number): THREE.BufferGeometry {
  const R = Math.max(circumradius, 1e-6);
  const half = height / 2;
  const pos: number[] = [];
  const idx: number[] = [];
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2;
    pos.push(Math.cos(a) * R, Math.sin(a) * R, half);
  }
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2;
    pos.push(Math.cos(a) * R, Math.sin(a) * R, -half);
  }
  pos.push(0, 0, half, 0, 0, -half); // 顶/底中心 = 12, 13
  for (let i = 0; i < 6; i++) idx.push(12, i, (i + 1) % 6); // 顶盖
  for (let i = 0; i < 6; i++) idx.push(13, (i + 1) % 6, i); // 底盖
  for (let i = 0; i < 6; i++) {
    const n = (i + 1) % 6;
    idx.push(i, n, n + 6, i, n + 6, i + 6); // 侧面
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  geo.setIndex(idx);
  geo.computeVertexNormals();
  return geo;
}

/**
 * 构建格阵实例组。
 * 详细模式：每 (u, cellNum) 一个 InstancedMesh（色=getMatColor，M0 透明）；
 * 总览模式：单 InstancedMesh 色块（rect box / hex prism，色=getUniverseColor）。
 * 实例矩阵顺序与 positions（过滤 void 后）顺序一致 → instanceIndexAt 返回
 * 该顺序下标。实例网格挂在 group.userData.instancedMeshes。
 */
export function buildLatticeInstances(opts: LatticeInstancesOptions): LatticeInstancesHandle {
  const group = new THREE.Group();
  const disposers: (() => void)[] = [];
  const instancedMeshes: THREE.InstancedMesh[] = [];
  const overview = opts.overviewMode ?? false;
  const rotationDeg = opts.trclRotationDeg ?? 0;
  if (rotationDeg) group.rotation.z = (rotationDeg * Math.PI) / 180;

  const nonVoid = opts.positions.filter((p) => p.u && p.u !== "0");

  if (overview) {
    const block = opts.blockSize ?? { x: 1, y: 1, z: 1, hex: false };
    const geometry = block.hex
      ? buildHexPrismGeometry(block.x / Math.sqrt(3), block.z)
      : new THREE.BoxGeometry(block.x, block.y, block.z);
    const material = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.6, metalness: 0.0 });
    const mesh = new THREE.InstancedMesh(geometry, material, Math.max(1, nonVoid.length));
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    const m = new THREE.Matrix4();
    for (let i = 0; i < nonVoid.length; i++) {
      const p = nonVoid[i];
      m.makeTranslation(p.x, p.y, p.z);
      mesh.setMatrixAt(i, m);
      mesh.setColorAt(i, new THREE.Color(getUniverseColor(p.u, opts.palette)));
    }
    mesh.userData.baseIndex = 0;
    instancedMeshes.push(mesh);
    group.add(mesh);
    disposers.push(() => {
      geometry.dispose();
      material.dispose();
    });
  } else {
    // 按 (u, cellNum) 分组 → 每组分一个 InstancedMesh
    const groups: { u: string; cellNum: string; items: LatticeInstance[] }[] = [];
    const byKey = new Map<string, { u: string; cellNum: string; items: LatticeInstance[] }>();
    for (const p of nonVoid) {
      const key = `${p.u} ${p.cellNum}`;
      let g = byKey.get(key);
      if (!g) {
        g = { u: p.u, cellNum: p.cellNum, items: [] };
        byKey.set(key, g);
        groups.push(g);
      }
      g.items.push(p);
    }
    const materialMode = opts.materialMode ?? true;
    let base = 0;
    for (const g of groups) {
      const matStr = opts.cellMaterials?.[g.u]?.[g.cellNum] ?? g.items[0].mat ?? "";
      const isVoid = matStr === "0";
      const geometry = opts.universeStl?.[g.u]?.[g.cellNum] ?? new THREE.BoxGeometry(1, 1, 1);
      // 元素填充格（水/慢化剂）：STL 包围盒 x/y ≈ 整个格元盒 → 半透明。z 高度全长后，
      // 不透明水盒会遮挡后排阵格（用户看到「有的阵格显示、有的不显示」）。
      let transparent = isVoid;
      if (!transparent && opts.blockSize) {
        try {
          geometry.computeBoundingBox();
          const bb = geometry.boundingBox;
          if (bb) {
            const sz = bb.getSize(new THREE.Vector3());
            if (sz.x >= opts.blockSize.x * 0.9 && sz.y >= opts.blockSize.y * 0.9) {
              transparent = true;
            }
          }
        } catch (e) { /* 包围盒失败保持不透明 */ }
      }
      const color = materialMode ? getMatColor(matStr) : getUniverseColor(g.u, opts.palette);
      const material = new THREE.MeshStandardMaterial({
        color: colorToNumber(color),
        roughness: 0.4,
        metalness: 0.0,
        transparent: transparent,
        opacity: isVoid ? 0 : (transparent ? 0.35 : 1),
        depthWrite: !transparent,
        side: THREE.FrontSide,
      });
      const mesh = new THREE.InstancedMesh(geometry, material, g.items.length);
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      const m = new THREE.Matrix4();
      for (let i = 0; i < g.items.length; i++) {
        const p = g.items[i];
        m.makeTranslation(p.x, p.y, p.z);
        mesh.setMatrixAt(i, m);
      }
      mesh.userData.baseIndex = base;
      instancedMeshes.push(mesh);
      group.add(mesh);
      base += g.items.length;
      disposers.push(() => {
        geometry.dispose();
        material.dispose();
      });
    }
  }

  group.userData.instancedMeshes = instancedMeshes;

  return {
    group,
    dispose() {
      for (const d of disposers) d();
      group.clear();
      group.userData.instancedMeshes = [];
    },
  };
}

/* ── 点击实例 id → 格位索引 ── */

/**
 * 射线拾取：对每个 InstancedMesh 取最近交点，返回全局格位索引
 * （= positions 过滤 void 后的下标；null = 未命中）。
 */
export function instanceIndexAt(
  raycaster: THREE.Raycaster,
  instancedMeshes: THREE.InstancedMesh[],
): number | null {
  let best: number | null = null;
  let bestDist = Infinity;
  for (const mesh of instancedMeshes) {
    const hits = raycaster.intersectObject(mesh, false);
    for (const h of hits) {
      if (h.instanceId != null && h.distance < bestDist) {
        bestDist = h.distance;
        best = (mesh.userData.baseIndex as number) + h.instanceId;
      }
    }
  }
  return best;
}
