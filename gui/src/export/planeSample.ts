/**
 * planeSample — 在**任意方向平面**上取样体积标量场，并提等值线。
 *
 * ## 为什么放在前端而不是后端
 * 整块标量帧（`dataBase64`，8-bit 量化）本来就在前端（体积渲染要上传纹理）。
 * 加一条后端端点意味着：大数组再走一次 HTTP、后端要重建平面取样代码、
 * 还要补端点契约测试闸门 —— 而**取样公式很短**（三线性插值）、**纯函数好测**。
 * 所以就近做在前端：改一次平面方程即时重算，零网络往返。
 *
 * ## 与「几何截面」的区别（别混淆）
 * `app/analytic_slice.py` 切的是**几何**：对每个栅元判"点在不在里面"（二值场）提轮廓。
 * 这里切的是**计数标量场**：要的是等值线（连续值取等值面）。
 * 共用的是"平面基向量 + 2D marching squares"这一层思想，场与语义不同。
 *
 * ## 平面方程与网格坐标的关系
 * 方程 `A X + B Y + C Z = D` 里的 `(X,Y,Z)` 就是体积网格的世界坐标
 * （`worldBox` 同系）。`offsetPlaneForStl` 那套"显示系→原始系"的换算只属于
 * 几何截面（它的 STL 曾被平移），**不要**把它套到这里，否则平面会整体偏一个模型中心。
 */
import { contourSvgPath, fieldFromArray, type ScalarField } from "./contour";
import { rgbaToPngDataUrl } from "./captureFrame";
import { weatherLut } from "../volume/colorize";
import type { PlaneEq } from "../three/planeEquation";

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

export interface AABB {
  min: [number, number, number];
  max: [number, number, number];
}

/** 平面在体积盒内的一张取样网格（含 2D↔3D 映射所需信息） */
export interface PlaneSample {
  /** 平面上一点（世界坐标） */
  origin: Vec3;
  /** 平面内两个正交单位向量（u 对应列方向，v 对应行方向） */
  u: Vec3;
  v: Vec3;
  /** 取样步长（世界单位/格） */
  step: number;
  /** 列数、行数（≥2） */
  width: number;
  height: number;
  /** 行主序标量值（长度 width*height） */
  values: Float64Array;
  min: number;
  max: number;
}

/** 单位化（长度 0 → 返回 null，调用方据此判定"这不是个平面"） */
function normalize(v: Vec3): Vec3 | null {
  const L = Math.hypot(v.x, v.y, v.z);
  if (!(L > 1e-12)) return null;
  return { x: v.x / L, y: v.y / L, z: v.z / L };
}

/** 平面基：法向 n + 平面内正交单位向量 u、v（与 `analytic_slice._plane_basis` 同思路） */
export function planeBasis(plane: PlaneEq): { n: Vec3; u: Vec3; v: Vec3 } | null {
  const n = normalize({ x: plane.A, y: plane.B, z: plane.C });
  if (!n) return null;
  const ref: Vec3 = Math.abs(n.x) < 0.9 ? { x: 1, y: 0, z: 0 } : { x: 0, y: 1, z: 0 };
  const u0 = normalize({
    x: n.y * ref.z - n.z * ref.y,
    y: n.z * ref.x - n.x * ref.z,
    z: n.x * ref.y - n.y * ref.x,
  });
  if (!u0) return null;
  const v0 = normalize({
    x: n.y * u0.z - n.z * u0.y,
    y: n.z * u0.x - n.x * u0.z,
    z: n.x * u0.y - n.y * u0.x,
  });
  if (!v0) return null;
  return { n, u: u0, v: v0 };
}

/** 平面与体积盒的相交中心（无交点时退回盒中心 —— 至少给出一张在盒内的图） */
export function planeOriginInBox(plane: PlaneEq, box: AABB): Vec3 {
  const c: Vec3 = {
    x: (box.min[0] + box.max[0]) / 2,
    y: (box.min[1] + box.max[1]) / 2,
    z: (box.min[2] + box.max[2]) / 2,
  };
  const { n } = planeBasis(plane) ?? { n: { x: 0, y: 0, z: 1 } as Vec3 };
  // 把盒中心沿法向滑到平面上：center + n * (D - n·center)/|n|²（n 已单位化）
  const dot = n.x * c.x + n.y * c.y + n.z * c.z;
  const t = plane.D - dot;
  return { x: c.x + n.x * t, y: c.y + n.y * t, z: c.z + n.z * t };
}

/**
 * 平面上取样标量场（三线性插值）。
 *
 * @param d 量化字节（行主序 idx = ((i*nj)+j)*nk+k，与 `VolumeFrame` 一致）
 */
export function samplePlane(
  plane: PlaneEq,
  box: AABB,
  res: [number, number, number],
  d: Uint8Array,
  scalarRange: { min: number; max: number },
  opts: { samples?: number } = {},
): PlaneSample | null {
  const basis = planeBasis(plane);
  if (!basis) return null;
  const { u, v } = basis;
  const [ni, nj, nk] = res;
  if (ni < 1 || nj < 1 || nk < 1) return null;

  const origin = planeOriginInBox(plane, box);
  // 取样范围：先把盒投影到 u/v 求半宽，再取**正方形覆盖**（半宽取两者较大者）。
  // 取正方形而不是各自的投影半宽，是因为投影半宽在两个方向上通常不等
  // （例如 n=(1,1,1)：u 向 33.9、v 向 39.2）——那会让采样区变成竖长矩形，
  // 视觉上把圆形的东西画成椭圆。正方形覆盖多采一点边角，换来各向同性。
  const halfU0 = Math.max(
    Math.abs(u.x) * (box.max[0] - box.min[0]), Math.abs(u.y) * (box.max[1] - box.min[1]), Math.abs(u.z) * (box.max[2] - box.min[2]),
  ) / 2;
  const halfV0 = Math.max(
    Math.abs(v.x) * (box.max[0] - box.min[0]), Math.abs(v.y) * (box.max[1] - box.min[1]), Math.abs(v.z) * (box.max[2] - box.min[2]),
  ) / 2;
  const half = Math.max(halfU0, halfV0, 1e-9);

  const n = Math.max(8, Math.min(512, Math.round(opts.samples ?? 128)));
  const width = n;
  const height = n;
  const stepU = (half * 2) / (width - 1 || 1);
  const stepV = (half * 2) / (height - 1 || 1);

  const cx = origin.x, cy = origin.y, cz = origin.z;
  /**
   * ⚠️ 取样下标用**节点口径** `(wx - min) / pitch`，其中 `pitch = (max-min)/(size-1)`。
   *
   * 为什么不是"体素中心"口径（`(wx-min)/pitch - 0.5`，pitch=(max-min)/size）：
   * 体素场的实际约定是**首个样本落在 min、末个样本落在 max**（`fieldFromQuantized` 的
   * `data[i]` 就是被 min/max 夹住的那个数组），体积渲染器的纹理映射与轴对齐切面
   * （`sliceFrame` 直接按 i 取体素）也都按这个口径。若改成体素中心口径，自由平面会与
   * 3D 体积、轴对齐切面**错开半格并压缩 (size-1)/size**（实测：末体素 210 被算成 172.9）。
   * 结论：统一用节点口径；`worldBox` 的边界语义差异在校准步长里体现（见 axisInfoOf）。
   */
  const sx = (box.max[0] - box.min[0]) / Math.max(1, ni - 1);
  const sy = (box.max[1] - box.min[1]) / Math.max(1, nj - 1);
  const sz = (box.max[2] - box.min[2]) / Math.max(1, nk - 1);
  const span0 = (scalarRange.max - scalarRange.min) / 255;

  const values = new Float64Array(width * height);
  let vmin = Infinity, vmax = -Infinity;
  for (let r = 0; r < height; r++) {
    const dv = (r - (height - 1) / 2) * stepV;
    for (let c = 0; c < width; c++) {
      const du = (c - (width - 1) / 2) * stepU;
      const wx = cx + u.x * du + v.x * dv;
      const wy = cy + u.y * du + v.y * dv;
      const wz = cz + u.z * du + v.z * dv;
      // 世界 → 节点下标（与场数组的下标语义一致）
      const fi = (wx - box.min[0]) / sx;
      const fj = (wy - box.min[1]) / sy;
      const fk = (wz - box.min[2]) / sz;
      const val = trilinear(d, ni, nj, nk, fi, fj, fk);
      const f = val * span0 + scalarRange.min;
      values[r * width + c] = f;
      if (isFinite(f)) {
        if (f < vmin) vmin = f;
        if (f > vmax) vmax = f;
      }
    }
  }
  if (!isFinite(vmin)) { vmin = scalarRange.min; vmax = scalarRange.max; }
  return {
    origin, u, v, step: Math.max(stepU, stepV),
    width, height, values, min: vmin, max: vmax,
  };
}

/**
 * 三线性插值（**总是返回数值**：越界位置按边界值夹取，不返回 0）。
 *
 * ⚠️ 曾经对"超出 ±0.5 个节点"的位置直接返回 0，结果**盒内靠近边界的取样被算成 0**：
 * 过 `x = max` 的平面上，沿另一轴的取样点会落到末节点稍外侧（如 6.99），
 * 于是那一列的值被拉低（实测：末体素 210 被算成 172.9）。
 * 正确做法：先把浮点下标**夹取**到 [0, size-1] 再插值 —— 平面与盒相交处本来就该取边界值，
 * 而不是当成"没数据"。
 */
function trilinear(d: Uint8Array, ni: number, nj: number, nk: number, fi: number, fj: number, fk: number): number {
  const ci = Math.max(0, Math.min(ni - 1, fi));
  const cj = Math.max(0, Math.min(nj - 1, fj));
  const ck = Math.max(0, Math.min(nk - 1, fk));
  const i0 = Math.floor(ci);
  const j0 = Math.floor(cj);
  const k0 = Math.floor(ck);
  const i1 = Math.min(ni - 1, i0 + 1);
  const j1 = Math.min(nj - 1, j0 + 1);
  const k1 = Math.min(nk - 1, k0 + 1);
  const ti = ci - i0;
  const tj = cj - j0;
  const tk = ck - k0;
  const at = (i: number, j: number, k: number) => d[(i * nj + j) * nk + k] ?? 0;
  const c00 = at(i0, j0, k0) * (1 - ti) + at(i1, j0, k0) * ti;
  const c10 = at(i0, j1, k0) * (1 - ti) + at(i1, j1, k0) * ti;
  const c01 = at(i0, j0, k1) * (1 - ti) + at(i1, j0, k1) * ti;
  const c11 = at(i0, j1, k1) * (1 - ti) + at(i1, j1, k1) * ti;
  const c0 = c00 * (1 - tj) + c10 * tj;
  const c1 = c01 * (1 - tj) + c11 * tj;
  return c0 * (1 - tk) + c1 * tk;
}

/** 取样网格 → 标量场（供 `contour` 提等值线） */
export function sampleField(s: PlaneSample): ScalarField {
  return fieldFromArray(s.values, s.width, s.height);
}

/** 取样网格 → RGBA 热图（与体积渲染同一 weather 色带；低于 displayMin 透明） */
export function sampleHeatRgba(s: PlaneSample, displayMin: number, cell = 2): { rgba: Uint8ClampedArray; width: number; height: number } {
  const lut = weatherLut(256);
  const lutMul = (lut.length >> 2) - 1;
  const width = s.width * cell;
  const height = s.height * cell;
  const rgba = new Uint8ClampedArray(width * height * 4);
  const span = s.max - s.min || 1;
  for (let r = 0; r < s.height; r++) {
    for (let c = 0; c < s.width; c++) {
      const f = s.values[r * s.width + c];
      if (!isFinite(f) || f < displayMin) continue;
      const frac = Math.max(0, Math.min(1, (f - s.min) / span));
      const idx = Math.max(0, Math.min(lutMul, Math.floor(frac * lutMul)));
      const base = idx * 4;
      for (let dy = 0; dy < cell; dy++) {
        for (let dx = 0; dx < cell; dx++) {
          const p = ((r * cell + dy) * width + c * cell + dx) * 4;
          rgba[p] = lut[base]; rgba[p + 1] = lut[base + 1]; rgba[p + 2] = lut[base + 2]; rgba[p + 3] = 255;
        }
      }
    }
  }
  return { rgba, width, height };
}

/** 取样网格 → 热图 PNG（无 canvas 环境返回 null，调用方只画矢量等值线） */
export function sampleHeatPng(s: PlaneSample, displayMin: number, cell = 2): string | null {
  const { rgba, width, height } = sampleHeatRgba(s, displayMin, cell);
  return rgbaToPngDataUrl(rgba, width, height);
}

/** 取样网格 → 等值线 SVG 片段（坐标已按 cell 放大） */
export function sampleContours(s: PlaneSample, opts: { levels?: number; cell?: number; color?: string; minValue?: number } = {}): string {
  return contourSvgPath(sampleField(s), s.min, s.max, {
    levels: opts.levels ?? 8,
    cell: opts.cell ?? 2,
    color: opts.color ?? "#1a1a1a",
    strokeWidth: 1.1,
    minValue: opts.minValue,
    opacity: 0.8,
  });
}

/**
 * 平面沿法向在体积盒内的 D 取值范围（成叠导出的扫描区间）。
 *
 * 做法：把盒的 8 个角点投影到**单位法向**上取极值 —— 这正是平面与盒相交的 D 区间。
 */
export function planeRangeInBox(plane: PlaneEq, box: AABB): { min: number; max: number } {
  const n = normalize({ x: plane.A, y: plane.B, z: plane.C });
  if (!n) return { min: plane.D, max: plane.D };
  const dots: number[] = [];
  for (const x of [box.min[0], box.max[0]]) {
    for (const y of [box.min[1], box.max[1]]) {
      for (const z of [box.min[2], box.max[2]]) dots.push(n.x * x + n.y * y + n.z * z);
    }
  }
  /**
   * ⚠️ 上面是**单位法向**的投影区间，但方程里的 D 是 `A X + B Y + C Z`（法向未归一化）。
   * 二者差一个 `|n|`；不乘回去的话，`X + Y + Z = 0`（|n|=√3）的成叠只会扫过盒中心
   * 1/√3 的范围，而且"步长 1"实际走的几何距离是 1/√3。乘 `|n|` 后：D 区间与用户写的方程同系，
   * 步长也就是法向增量（与 3D 预览的步进语义一致）。
   */
  const scale = normalLength(plane);
  return { min: Math.min(...dots) * scale, max: Math.max(...dots) * scale };
}

/** 法向量长度（未归一化方程的 |(A,B,C)|） */
function normalLength(p: PlaneEq): number {
  return Math.hypot(p.A, p.B, p.C);
}
