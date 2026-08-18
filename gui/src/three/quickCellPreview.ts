/**
 * 快捷建栅元弹窗的线框预览构建器（纯 THREE 场景对象，输入变重建，毫秒级）
 *
 * 只画：形状线框 + 切分线 + 局部坐标轴（X 红 / Y 绿 / Z 蓝）。
 * 不请求后端、不加载 STL；配合弹窗的按需渲染，实时跟手不卡。
 */
import * as THREE from "three";
import { eulerRotation, type RccConfig, type RppConfig, type SphConfig, type QuickShape } from "../utils/quickCell";

const AXIS_X = new THREE.Vector3(1, 0, 0);
const AXIS_Y = new THREE.Vector3(0, 1, 0);
const AXIS_Z = new THREE.Vector3(0, 0, 1);

export interface QuickCellPreview {
  group: THREE.Group;
  dispose(): void;
}

function len(a: number[]): number {
  return Math.hypot(a[0], a[1], a[2]);
}

function addLine(group: THREE.Group, pts: THREE.Vector3[], color: number, opacity = 1): void {
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = new THREE.LineBasicMaterial({ color, transparent: opacity < 1, opacity });
  group.add(new THREE.Line(geo, mat));
}

function addLoop(group: THREE.Group, pts: THREE.Vector3[], color: number, opacity = 1): void {
  const closed = [...pts, pts[0]];
  addLine(group, closed, color, opacity);
}

/** 以 normal 为法向、center 为圆心的圆环点列 */
function circlePoints(center: THREE.Vector3, radius: number, normal: THREE.Vector3, segments = 48): THREE.Vector3[] {
  const n = normal.clone().normalize();
  const u = new THREE.Vector3();
  if (Math.abs(n.x) < 0.9) u.crossVectors(AXIS_X, n); else u.crossVectors(AXIS_Y, n);
  if (u.lengthSq() < 1e-12) u.copy(AXIS_Y);
  u.normalize();
  const v = new THREE.Vector3().crossVectors(n, u).normalize();
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i <= segments; i++) {
    const a = (i / segments) * Math.PI * 2;
    pts.push(center.clone().addScaledVector(u, Math.cos(a) * radius).addScaledVector(v, Math.sin(a) * radius));
  }
  return pts;
}

function addAxes(group: THREE.Group, origin: THREE.Vector3, x: THREE.Vector3, y: THREE.Vector3, z: THREE.Vector3): void {
  const mk = (dir: THREE.Vector3, color: number) => {
    addLine(group, [origin.clone(), origin.clone().add(dir)], color, 0.9);
  };
  mk(x, 0xff4444);
  mk(y, 0x44ff44);
  mk(z, 0x4488ff);
}

function buildRcc(group: THREE.Group, c: RccConfig): void {
  const base = new THREE.Vector3(...c.center);
  const ax = new THREE.Vector3(...c.axis);
  const top = base.clone().add(ax);
  const n = ax.clone().normalize();
  const R = c.radius;

  // 外形：两端圆 + 轴向母线
  addLoop(group, circlePoints(base, R, n), 0x88aaff, 0.9);
  addLoop(group, circlePoints(top, R, n), 0x88aaff, 0.9);
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2;
    const u = new THREE.Vector3();
    if (Math.abs(n.x) < 0.9) u.crossVectors(AXIS_X, n); else u.crossVectors(AXIS_Y, n);
    u.normalize();
    const v = new THREE.Vector3().crossVectors(n, u).normalize();
    const p0 = base.clone().addScaledVector(u, Math.cos(a) * R).addScaledVector(v, Math.sin(a) * R);
    addLine(group, [p0, p0.clone().add(ax)], 0x88aaff, 0.7);
  }

  // 环切分：每个半径在每个轴段边界（含两端）画一圈
  for (let li = 0; li <= c.segments; li++) {
    const pos = base.clone().addScaledVector(n, (len(c.axis) * li) / c.segments);
    for (let k = 1; k <= c.rings; k++) {
      addLoop(group, circlePoints(pos, (R * k) / c.rings, n), 0x66ccff, 0.55);
    }
  }
  // 轴向切分平面（半径 R 的圆）
  for (let k = 1; k < c.segments; k++) {
    const pos = base.clone().addScaledVector(n, (len(c.axis) * k) / c.segments);
    addLoop(group, circlePoints(pos, R, n), 0x66ccff, 0.55);
  }

  addAxes(group, base, new THREE.Vector3(1, 0, 0).multiplyScalar(Math.max(R, 0.3)), AXIS_Y.clone().multiplyScalar(Math.max(R, 0.3)), AXIS_Z.clone().multiplyScalar(Math.max(R, 0.3)));
}

function buildSph(group: THREE.Group, c: SphConfig): void {
  const center = new THREE.Vector3(...c.center);
  for (let k = 1; k <= c.shells; k++) {
    const r = (c.radius * k) / c.shells;
    const color = k === c.shells ? 0x88aaff : 0x66ccff;
    const op = k === c.shells ? 0.9 : 0.55;
    addLoop(group, circlePoints(center, r, AXIS_X), color, op);
    addLoop(group, circlePoints(center, r, AXIS_Y), color, op);
    addLoop(group, circlePoints(center, r, AXIS_Z), color, op);
  }
  const r = Math.max(c.radius, 0.3);
  addAxes(group, center, AXIS_X.clone().multiplyScalar(r), AXIS_Y.clone().multiplyScalar(r), AXIS_Z.clone().multiplyScalar(r));
}

function buildRpp(group: THREE.Group, c: RppConfig): void {
  const [L, W, H] = c.size;
  const [cx0, cy0, cz0] = c.center;
  const R = eulerRotation(c.angles);
  const center = new THREE.Vector3(cx0, cy0, cz0);

  // 局部角点 → 全局：p_global = center + R·p_local（R 行主序）
  const toGlobal = (p: number[]) => new THREE.Vector3(
    cx0 + R[0][0] * p[0] + R[0][1] * p[1] + R[0][2] * p[2],
    cy0 + R[1][0] * p[0] + R[1][1] * p[1] + R[1][2] * p[2],
    cz0 + R[2][0] * p[0] + R[2][1] * p[1] + R[2][2] * p[2],
  );
  const local = [
    [-L / 2, -W / 2, -H / 2], [L / 2, -W / 2, -H / 2], [L / 2, W / 2, -H / 2], [-L / 2, W / 2, -H / 2],
    [-L / 2, -W / 2, H / 2], [L / 2, -W / 2, H / 2], [L / 2, W / 2, H / 2], [-L / 2, W / 2, H / 2],
  ];
  const P = local.map(toGlobal);

  // 12 条棱（底面 0-1-2-3、顶面 4-5-6-7、竖棱 0-4 等）
  const edges: [number, number][] = [
    [0, 1], [1, 2], [2, 3], [3, 0],
    [4, 5], [5, 6], [6, 7], [7, 4],
    [0, 4], [1, 5], [2, 6], [3, 7],
  ];
  edges.forEach(([a, b]) => addLine(group, [P[a], P[b]], 0x88aaff, 0.9));

  // 局部轴全局方向 = R 的列
  const u = new THREE.Vector3(R[0][0], R[1][0], R[2][0]);
  const v = new THREE.Vector3(R[0][1], R[1][1], R[2][1]);
  const w = new THREE.Vector3(R[0][2], R[1][2], R[2][2]);
  const rect = (origin: THREE.Vector3, e1: THREE.Vector3, e2: THREE.Vector3) => {
    addLoop(group, [
      origin, origin.clone().add(e1), origin.clone().add(e1).add(e2), origin.clone().add(e2),
    ], 0x66ccff, 0.5);
  };
  for (let i = 1; i < c.nx; i++) rect(center.clone().addScaledVector(u, -L / 2 + (L * i) / c.nx), v.clone().multiplyScalar(W), w.clone().multiplyScalar(H));
  for (let j = 1; j < c.ny; j++) rect(center.clone().addScaledVector(v, -W / 2 + (W * j) / c.ny), u.clone().multiplyScalar(L), w.clone().multiplyScalar(H));
  for (let k = 1; k < c.nz; k++) rect(center.clone().addScaledVector(w, -H / 2 + (H * k) / c.nz), u.clone().multiplyScalar(L), v.clone().multiplyScalar(W));

  const s = Math.max(L, W, H, 0.3) * 0.35;
  addAxes(group, center, u.clone().multiplyScalar(s), v.clone().multiplyScalar(s), w.clone().multiplyScalar(s));
}

export function buildQuickCellPreview(shape: QuickShape, config: RccConfig | RppConfig | SphConfig): QuickCellPreview {
  const group = new THREE.Group();
  if (shape === "rcc") buildRcc(group, config as RccConfig);
  else if (shape === "sph") buildSph(group, config as SphConfig);
  else buildRpp(group, config as RppConfig);
  return {
    group,
    dispose() {
      group.traverse((obj) => {
        const anyObj = obj as any;
        anyObj.geometry?.dispose?.();
        anyObj.material?.dispose?.();
      });
      group.clear();
    },
  };
}
