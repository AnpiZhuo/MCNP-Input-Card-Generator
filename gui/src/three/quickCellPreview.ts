/**
 * 快捷建栅元弹窗的线框预览构建器（纯 THREE 场景对象，输入变重建，毫秒级）
 *
 * 只画：形状线框 + 切分线 + 局部坐标轴（X 红 / Y 绿 / Z 蓝）。
 * 不请求后端、不加载 STL；配合弹窗的按需渲染，实时跟手不卡。
 */
import * as THREE from "three";
import { eulerRotation, type RccConfig, type RppConfig, type SphConfig, type QuickShape } from "../utils/quickCell";
import { getMatColor } from "../utils/materialColors";

const AXIS_X = new THREE.Vector3(1, 0, 0);
const AXIS_Y = new THREE.Vector3(0, 1, 0);
const AXIS_Z = new THREE.Vector3(0, 0, 1);
const ORIGIN = new THREE.Vector3(0, 0, 0);

/** 线框颜色随所选材料（M0 真空 → 白线）；materialColors 的 M0 是透明，须特判 */
export function wireColorForMaterial(mat: string): number {
  const hex = mat === "0" ? "#ffffff" : getMatColor(mat);
  const h = parseInt(hex.replace("#", ""), 16);
  return Number.isFinite(h) ? h : 0xffffff;
}

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

/** 轴端点文字标签（X/Y/Z）；无 DOM（node 测试）时跳过 */
function makeLabel(text: string, color: number, pos: THREE.Vector3, scale: number): THREE.Sprite | null {
  try {
    if (typeof document === "undefined") return null;
    const c = document.createElement("canvas");
    c.width = 64;
    c.height = 64;
    const ctx = c.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = "#" + color.toString(16).padStart(6, "0");
    ctx.font = "Bold 44px Arial";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, 32, 34);
    const tex = new THREE.CanvasTexture(c);
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false }));
    sprite.position.copy(pos);
    sprite.scale.set(scale, scale, 1);
    return sprite;
  } catch {
    return null;
  }
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
  const mk = (dir: THREE.Vector3, color: number, label: string) => {
    addLine(group, [origin.clone(), origin.clone().add(dir)], color, 0.9);
    const tip = origin.clone().add(dir);
    const lbl = makeLabel(label, color, tip, Math.max(dir.length() * 0.55, 0.4));
    if (lbl) group.add(lbl);
  };
  mk(x, 0xff4444, "X");
  mk(y, 0x44ff44, "Y");
  mk(z, 0x4488ff, "Z");
}

/** 轴长：兼顾体尺寸与体到原点的距离，保证原点处的轴在取景里清晰可见 */
function axisLenFor(center: THREE.Vector3, extent: number): number {
  return Math.max(extent * 0.5, center.length() * 0.35, 0.5);
}

function buildRcc(group: THREE.Group, c: RccConfig, color: number): void {
  const base = new THREE.Vector3(...c.center);
  const ax = new THREE.Vector3(...c.axis);
  const top = base.clone().add(ax);
  const n = ax.clone().normalize();
  const R = c.radius;

  // 外形：两端圆 + 轴向母线
  addLoop(group, circlePoints(base, R, n), color, 0.9);
  addLoop(group, circlePoints(top, R, n), color, 0.9);
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2;
    const u = new THREE.Vector3();
    if (Math.abs(n.x) < 0.9) u.crossVectors(AXIS_X, n); else u.crossVectors(AXIS_Y, n);
    u.normalize();
    const v = new THREE.Vector3().crossVectors(n, u).normalize();
    const p0 = base.clone().addScaledVector(u, Math.cos(a) * R).addScaledVector(v, Math.sin(a) * R);
    addLine(group, [p0, p0.clone().add(ax)], color, 0.7);
  }

  // 环切分：每个半径在每个轴段边界（含两端）画一圈
  for (let li = 0; li <= c.segments; li++) {
    const pos = base.clone().addScaledVector(n, (len(c.axis) * li) / c.segments);
    for (let k = 1; k <= c.rings; k++) {
      addLoop(group, circlePoints(pos, (R * k) / c.rings, n), color, 0.55);
    }
  }
  // 轴向切分平面（半径 R 的圆）
  for (let k = 1; k < c.segments; k++) {
    const pos = base.clone().addScaledVector(n, (len(c.axis) * k) / c.segments);
    addLoop(group, circlePoints(pos, R, n), color, 0.55);
  }

  const alen = axisLenFor(base, Math.max(R * 2, len(c.axis)));
  addAxes(group, ORIGIN, AXIS_X.clone().multiplyScalar(alen), AXIS_Y.clone().multiplyScalar(alen), AXIS_Z.clone().multiplyScalar(alen));
}

function buildSph(group: THREE.Group, c: SphConfig, color: number): void {
  const center = new THREE.Vector3(...c.center);
  for (let k = 1; k <= c.shells; k++) {
    const r = (c.radius * k) / c.shells;
    const op = k === c.shells ? 0.9 : 0.55;
    addLoop(group, circlePoints(center, r, AXIS_X), color, op);
    addLoop(group, circlePoints(center, r, AXIS_Y), color, op);
    addLoop(group, circlePoints(center, r, AXIS_Z), color, op);
  }
  const alen = axisLenFor(center, c.radius * 2);
  addAxes(group, ORIGIN, AXIS_X.clone().multiplyScalar(alen), AXIS_Y.clone().multiplyScalar(alen), AXIS_Z.clone().multiplyScalar(alen));
}

function buildRpp(group: THREE.Group, c: RppConfig, color: number): void {
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
  edges.forEach(([a, b]) => addLine(group, [P[a], P[b]], color, 0.9));

  // 局部轴全局方向 = R 的列
  const u = new THREE.Vector3(R[0][0], R[1][0], R[2][0]);
  const v = new THREE.Vector3(R[0][1], R[1][1], R[2][1]);
  const w = new THREE.Vector3(R[0][2], R[1][2], R[2][2]);
  // 切分平面矩形：以切分位置为中心，跨整个截面（e1×e2 全尺寸）
  const rect = (origin: THREE.Vector3, e1: THREE.Vector3, e2: THREE.Vector3) => {
    const o = origin.clone().sub(e1.clone().multiplyScalar(0.5)).sub(e2.clone().multiplyScalar(0.5));
    addLoop(group, [
      o, o.clone().add(e1), o.clone().add(e1).add(e2), o.clone().add(e2),
    ], color, 0.55);
  };
  for (let i = 1; i < c.nx; i++) rect(center.clone().addScaledVector(u, -L / 2 + (L * i) / c.nx), v.clone().multiplyScalar(W), w.clone().multiplyScalar(H));
  for (let j = 1; j < c.ny; j++) rect(center.clone().addScaledVector(v, -W / 2 + (W * j) / c.ny), u.clone().multiplyScalar(L), w.clone().multiplyScalar(H));
  for (let k = 1; k < c.nz; k++) rect(center.clone().addScaledVector(w, -H / 2 + (H * k) / c.nz), u.clone().multiplyScalar(L), v.clone().multiplyScalar(W));

  // 世界固定轴（X 红 / Y 绿 / Z 蓝）固定在原点 (0,0,0)，不随体旋转/移动，便于看体的真实位置与倾斜姿态
  const alen = axisLenFor(center, Math.max(L, W, H));
  addAxes(group, ORIGIN, AXIS_X.clone().multiplyScalar(alen), AXIS_Y.clone().multiplyScalar(alen), AXIS_Z.clone().multiplyScalar(alen));
}

export function buildQuickCellPreview(shape: QuickShape, config: RccConfig | RppConfig | SphConfig, color = 0x66ccff): QuickCellPreview {
  const group = new THREE.Group();
  if (shape === "rcc") buildRcc(group, config as RccConfig, color);
  else if (shape === "sph") buildSph(group, config as SphConfig, color);
  else buildRpp(group, config as RppConfig, color);
  return {
    group,
    dispose() {
      group.traverse((obj) => {
        const anyObj = obj as any;
        anyObj.geometry?.dispose?.();
        const mat = anyObj.material;
        if (mat) {
          mat.map?.dispose?.();
          mat.dispose?.();
        }
      });
      group.clear();
    },
  };
}
