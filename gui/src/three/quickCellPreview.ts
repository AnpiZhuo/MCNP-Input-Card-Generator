/**
 * 快捷建栅元弹窗的线框预览构建器（纯 THREE 场景对象，输入变重建，毫秒级）
 *
 * 只画：形状线框 + 切分线 + 局部坐标轴（X 红 / Y 绿 / Z 蓝）。
 * 不请求后端、不加载 STL；配合弹窗的按需渲染，实时跟手不卡。
 */
import * as THREE from "three";
import type { RccConfig, RppConfig, SphConfig, QuickShape } from "../utils/quickCell";

const AXIS_X = new THREE.Vector3(1, 0, 0);
const AXIS_Y = new THREE.Vector3(0, 1, 0);
const AXIS_Z = new THREE.Vector3(0, 0, 1);

export interface QuickCellPreview {
  group: THREE.Group;
  dispose(): void;
}

function sub(a: number[], b: number[]): number[] {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function add(a: number[], b: number[]): number[] {
  return [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
}

function len(a: number[]): number {
  return Math.hypot(a[0], a[1], a[2]);
}

function unit(a: number[]): number[] {
  const l = len(a);
  return l > 1e-12 ? [a[0] / l, a[1] / l, a[2] / l] : [0, 0, 0];
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
  const [v0, v1, v2, v3, v4, v5, v6, v7] = c.points;
  const a = sub(v1, v0);
  const b = sub(v3, v0);
  const cc = sub(v4, v0);
  const la = len(a), lb = len(b), lc = len(cc);
  const u = unit(a), v = unit(b), w = unit(cc);
  const P = (arr: number[]) => new THREE.Vector3(arr[0], arr[1], arr[2]);

  // 12 条棱
  const edges: [THREE.Vector3, THREE.Vector3][] = [
    [P(v0), P(v1)], [P(v1), P(v2)], [P(v2), P(v3)], [P(v3), P(v0)],
    [P(v4), P(v5)], [P(v5), P(v6)], [P(v6), P(v7)], [P(v7), P(v4)],
    [P(v0), P(v4)], [P(v1), P(v5)], [P(v2), P(v6)], [P(v3), P(v7)],
  ];
  edges.forEach(([p, q]) => addLine(group, [p, q], 0x88aaff, 0.9));

  // 切分平面（沿三条边方向）
  const rect = (origin: THREE.Vector3, e1: THREE.Vector3, e2: THREE.Vector3, color: number) => {
    addLoop(group, [
      origin, origin.clone().add(e1), origin.clone().add(e1).add(e2), origin.clone().add(e2),
    ], color, 0.5);
  };
  const uVec = P(u), vVec = P(v), wVec = P(w);
  const baseP = P(v0);
  for (let i = 1; i < c.nx; i++) rect(baseP.clone().addScaledVector(uVec, (la * i) / c.nx), vVec.clone().multiplyScalar(lb), wVec.clone().multiplyScalar(lc), 0x66ccff);
  for (let j = 1; j < c.ny; j++) rect(baseP.clone().addScaledVector(vVec, (lb * j) / c.ny), uVec.clone().multiplyScalar(la), wVec.clone().multiplyScalar(lc), 0x66ccff);
  for (let k = 1; k < c.nz; k++) rect(baseP.clone().addScaledVector(wVec, (lc * k) / c.nz), uVec.clone().multiplyScalar(la), vVec.clone().multiplyScalar(lb), 0x66ccff);

  const s = Math.max(la, lb, lc, 0.3) * 0.35;
  addAxes(group, baseP, uVec.clone().multiplyScalar(s), vVec.clone().multiplyScalar(s), wVec.clone().multiplyScalar(s));
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
