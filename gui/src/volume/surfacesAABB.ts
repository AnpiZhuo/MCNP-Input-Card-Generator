/**
 * surfacesAABB — 从曲面卡文本计算模型 x/y/z 包围盒（AABB），供 FMESH「按几何自动填充」。
 *
 * PM 指令 2026-08-14（傻瓜友好改造）：解析曲面卡算模型 AABB，一键把 ORIGIN + IMESH/JMESH/KMESH
 * 填入（网格自动覆盖模型）。纯函数、零依赖、vitest 可测 seam。
 *
 * 设计：
 * - `computeSurfacesAABB(surfaces[, trCards]) → {min,max} | null`：
 *   - 支持平面（PX/PY/PZ）、球（SO/S/SX/SY/SZ/SPH）、圆柱（CX/CY/CZ/C/X/C/Y/C/Z）、
 *     宏体（RPP/RCC/TRC/REC/WED/BOX/RHP/HEX/ELL/ARB）、环面（保守球包）；
 *   - 一般平面 P / 一般二次曲面 GQ/SQ / 锥面 K* 无限不可解 → 跳过；
 *   - 曲面引用 TRn：有 trCards 且可解析 → 平移/旋转后取有界盒；否则跳过（容错）；
 *   - 任一轴无曲面提供有界范围（模型无限）→ 返回 null（UI 提示"解不出"）。
 * - `aabbToFmeshValues` 把 AABB 转成填表值（ORIGIN=min、IMESH/JMESH/KMESH=max）。
 *
 * 保守方向：合并取并集（min 取最小 / max 取最大），保证网格覆盖模型；个别曲面
 * 超估只会让网格偏大（安全），不会漏盖。
 */

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

export interface AABB {
  min: Vec3;
  max: Vec3;
}

/** 单个曲面贡献的有界盒：axes[i] = 该轴是否有界（否则 lo/hi 该轴被忽略） */
interface MiniBox {
  lo: Vec3;
  hi: Vec3;
  axes: [boolean, boolean, boolean];
}

interface Transform {
  o: number[];
  rot: number[][];
}

const NUM_RE = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/;
const TR_HEAD_RE = /^\*?TR(\d+)$/i;

/* ── 有界盒构造助手 ── */

function boxAll(cx: number, cy: number, cz: number, rx: number, ry: number, rz: number): MiniBox {
  return {
    lo: { x: cx - rx, y: cy - ry, z: cz - rz },
    hi: { x: cx + rx, y: cy + ry, z: cz + rz },
    axes: [true, true, true],
  };
}

function boxPoint(x: number, y: number, z: number): MiniBox {
  return { lo: { x, y, z }, hi: { x, y, z }, axes: [true, true, true] };
}

/** 单轴有界（平面），其余轴无限（axes 标记 false，lo/hi 填 0 占位被忽略） */
function boxAxis(axis: 0 | 1 | 2, value: number): MiniBox {
  const lo: Vec3 = { x: 0, y: 0, z: 0 };
  const hi: Vec3 = { x: 0, y: 0, z: 0 };
  if (axis === 0) { lo.x = value; hi.x = value; }
  else if (axis === 1) { lo.y = value; hi.y = value; }
  else { lo.z = value; hi.z = value; }
  const axes: [boolean, boolean, boolean] = [false, false, false];
  axes[axis] = true;
  return { lo, hi, axes };
}

/** 半径 r，自由轴用 0（axes 标 false） */
function boxRadial(cx: number, cy: number, cz: number, rx: number, ry: number, rz: number,
                   freeX: boolean, freeY: boolean, freeZ: boolean): MiniBox {
  return {
    lo: { x: cx - rx, y: cy - ry, z: cz - rz },
    hi: { x: cx + rx, y: cy + ry, z: cz + rz },
    axes: [!freeX, !freeY, !freeZ],
  };
}

function boxFromCorners(corners: Vec3[]): MiniBox {
  const xs = corners.map((c) => c.x);
  const ys = corners.map((c) => c.y);
  const zs = corners.map((c) => c.z);
  return {
    lo: { x: Math.min(...xs), y: Math.min(...ys), z: Math.min(...zs) },
    hi: { x: Math.max(...xs), y: Math.max(...ys), z: Math.max(...zs) },
    axes: [true, true, true],
  };
}

/* ── 曲面类型 → 有界盒 ── */

/** 按 mnemonic 与参数返回有界盒；无限/不可解返回 null（跳过该曲面） */
function surfaceMiniBox(mnemonic: string, p: number[]): MiniBox | null {
  switch (mnemonic) {
    // 平面：截距轴有界
    case "PX": return boxAxis(0, p[0]);
    case "PY": return boxAxis(1, p[0]);
    case "PZ": return boxAxis(2, p[0]);
    case "P": return null; // 一般平面无限
    // 球面
    case "SO": return boxAll(0, 0, 0, p[0], p[0], p[0]);
    case "S": return boxAll(p[0], p[1], p[2], p[3], p[3], p[3]);
    case "SX": return boxAll(p[0], 0, 0, p[1], p[1], p[1]);
    case "SY": return boxAll(0, p[0], 0, p[1], p[1], p[1]);
    case "SZ": return boxAll(0, 0, p[0], p[1], p[1], p[1]);
    // 柱面：径向有界，轴向自由
    case "CX": return boxRadial(0, 0, 0, 0, p[0], p[0], true, false, false);
    case "CY": return boxRadial(0, 0, 0, p[0], 0, p[0], false, true, false);
    case "CZ": return boxRadial(0, 0, 0, p[0], p[0], 0, false, false, true);
    case "C/X": return boxRadial(0, p[0], p[1], 0, p[2], p[2], true, false, false);
    case "C/Y": return boxRadial(p[0], 0, p[1], p[2], 0, p[2], false, true, false);
    case "C/Z": return boxRadial(p[0], p[1], 0, p[2], p[2], 0, false, false, true);
    // 锥面：无限，跳过
    case "KX": case "KY": case "KZ":
    case "K/X": case "K/Y": case "K/Z":
      return null;
    // 一般二次曲面：系数非坐标，跳过
    case "GQ": case "SQ": return null;
    // 环面：保守球包（外半径 = 次半径 max(|A|,|B|) + 主半径 |C|）
    case "TX": case "TY": case "TZ": {
      const tube = Math.max(Math.abs(p[3]), Math.abs(p[4]));
      const r = tube + Math.abs(p[5]);
      return boxAll(p[0], p[1], p[2], r, r, r);
    }
    // 宏体
    case "RPP": {
      const lo = { x: p[0], y: p[2], z: p[4] };
      const hi = { x: p[1], y: p[3], z: p[5] };
      return { lo, hi, axes: [true, true, true] };
    }
    case "SPH": return boxAll(p[0], p[1], p[2], p[3], p[3], p[3]);
    case "RCC": return cylinderBox(p.slice(0, 3), p.slice(3, 6), p[6], p[6]);
    case "TRC": return cylinderBox(p.slice(0, 3), p.slice(3, 6), Math.max(p[6], p[7]), Math.max(p[6], p[7]));
    case "REC": {
      const v = [p[0], p[1], p[2]];
      const h = [p[3], p[4], p[5]];
      const v1 = [p[6], p[7], p[8]];
      const v2 = [p[9], p[10], p[11]];
      return cylinderBox(v, h, Math.hypot(v1[0], v1[1], v1[2]), Math.hypot(v2[0], v2[1], v2[2]));
    }
    case "WED": return boxFromCorners(wedCorners(p));
    case "BOX": return boxFromCorners(boxCorners(p));
    case "RHP": case "HEX": return boxFromCorners(rhpCorners(p));
    case "ELL": return ellBox(p);
    case "ARB": return boxFromCorners(arbCorners(p));
    default: return null;
  }
}

/** 圆柱/锥台/椭圆柱：沿轴向有界 [min(v,v+h), max(v,v+h)] ± 半径 */
function cylinderBox(v: number[], h: number[], r0: number, r1: number): MiniBox {
  const r = Math.max(r0, r1);
  const lo: Vec3 = {
    x: Math.min(v[0], v[0] + h[0]) - r,
    y: Math.min(v[1], v[1] + h[1]) - r,
    z: Math.min(v[2], v[2] + h[2]) - r,
  };
  const hi: Vec3 = {
    x: Math.max(v[0], v[0] + h[0]) + r,
    y: Math.max(v[1], v[1] + h[1]) + r,
    z: Math.max(v[2], v[2] + h[2]) + r,
  };
  return { lo, hi, axes: [true, true, true] };
}

function add(v: number[], w: number[]): number[] {
  return [v[0] + w[0], v[1] + w[1], v[2] + w[2]];
}

function wedCorners(p: number[]): Vec3[] {
  const v = [p[0], p[1], p[2]];
  const v1 = [p[3], p[4], p[5]];
  const v2 = [p[6], p[7], p[8]];
  const v3 = [p[9], p[10], p[11]];
  const pts = [
    v, add(v, v1), add(v, v2), add(add(v, v1), v2),
    add(v, v3), add(add(v, v1), v3), add(add(v, v2), v3), add(add(add(v, v1), v2), v3),
  ];
  return pts.map((q) => ({ x: q[0], y: q[1], z: q[2] }));
}

function boxCorners(p: number[]): Vec3[] {
  const v = [p[0], p[1], p[2]];
  const a = [p[3], p[4], p[5]];
  const b = [p[6], p[7], p[8]];
  const c = [p[9], p[10], p[11]];
  const pts: number[][] = [];
  for (const sa of [0, 1]) for (const sb of [0, 1]) for (const sc of [0, 1]) {
    pts.push(add(add(add(v, a.map((x) => x * sa)), b.map((x) => x * sb)), c.map((x) => x * sc)));
  }
  return pts.map((q) => ({ x: q[0], y: q[1], z: q[2] }));
}

function rhpCorners(p: number[]): Vec3[] {
  const v = [p[0], p[1], p[2]];
  const h = [p[3], p[4], p[5]];
  const r = [p[6], p[7], p[8]];
  const s = [p[9], p[10], p[11]];
  const t = [p[12], p[13], p[14]];
  const pts: number[][] = [];
  for (const sr of [0, 1]) for (const ss of [0, 1]) for (const st of [0, 1]) {
    const base = add(add(add(v, r.map((x) => x * (sr ? 1 : -1))), s.map((x) => x * (ss ? 1 : -1))), t.map((x) => x * (st ? 1 : -1)));
    pts.push(base, add(base, h));
  }
  return pts.map((q) => ({ x: q[0], y: q[1], z: q[2] }));
}

function arbCorners(p: number[]): Vec3[] {
  const pts: number[][] = [];
  for (let i = 0; i < 8; i++) pts.push([p[i * 3], p[i * 3 + 1], p[i * 3 + 2]]);
  return pts.map((q) => ({ x: q[0], y: q[1], z: q[2] }));
}

function ellBox(p: number[]): MiniBox {
  const [x1, y1, z1, x2, y2, z2, rm] = p;
  let cx: number, cy: number, cz: number;
  let ux: number, uy: number, uz: number;
  let major: number, minor: number;
  if (rm > 0) {
    // 焦点定义：V1/V2 为两焦点，Rm 为长轴长度
    const dx = x2 - x1, dy = y2 - y1, dz = z2 - z1;
    const d = Math.hypot(dx, dy, dz) || 1;
    cx = (x1 + x2) / 2; cy = (y1 + y2) / 2; cz = (z1 + z2) / 2;
    ux = dx / d; uy = dy / d; uz = dz / d;
    major = rm / 2;
    const half = d / 2;
    minor = Math.sqrt(Math.max(major * major - half * half, 0));
  } else {
    // 中心矢量定义：V1 为中心，V2 为长轴矢量，Rm 为短半径
    const d = Math.hypot(x2, y2, z2) || 1;
    cx = x1; cy = y1; cz = z1;
    ux = x2 / d; uy = y2 / d; uz = z2 / d;
    major = d;
    minor = Math.abs(rm);
  }
  const ext = (i: number): number => {
    const u = [ux, uy, uz][i];
    return major * Math.abs(u) + minor;
  };
  const lo = { x: cx - ext(0), y: cy - ext(1), z: cz - ext(2) };
  const hi = { x: cx + ext(0), y: cy + ext(1), z: cz + ext(2) };
  return { lo, hi, axes: [true, true, true] };
}

/* ── TRn 变换卡 ── */

function isIdentityMatrix(r: number[][]): boolean {
  const eps = 1e-9;
  for (let i = 0; i < 3; i++) {
    for (let j = 0; j < 3; j++) {
      if (Math.abs(r[i][j] - (i === j ? 1 : 0)) > eps) return false;
    }
  }
  return true;
}

/** 解析 tr_cards 文本 → Map<n, Transform>；模式 2/3/4（简写旋转）未实现则跳过该变换 */
function parseTrCards(trText: string): Map<string, Transform> {
  const map = new Map<string, Transform>();
  for (const raw of trText.split(/\r?\n/)) {
    const body = (raw.split("$")[0] || "").trim();
    if (!body) continue;
    const toks = body.split(/\s+/);
    const head = toks[0];
    const isAngle = head.startsWith("*");
    const m = (head.match(TR_HEAD_RE) || [])[1];
    if (!m) continue;
    const nums: number[] = [];
    for (const t of toks.slice(1)) {
      if (!NUM_RE.test(t)) break; // 遇非数值停靠（保护尾随注释/脏数据）
      nums.push(parseFloat(t));
    }
    const o = nums.slice(0, 3);
    const rest = nums.slice(3);
    let rot: number[][];
    if (rest.length === 0) {
      rot = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
    } else if (rest.length >= 9) {
      const b = rest.slice(0, 9);
      rot = [[b[0], b[3], b[6]], [b[1], b[4], b[7]], [b[2], b[5], b[8]]];
    } else {
      continue; // 模式 2/3/4（6/5/3 项旋转）不实现，跳过该变换
    }
    if (isAngle) rot = rot.map((row) => row.map((deg) => Math.cos((deg * Math.PI) / 180)));
    map.set(m, { o, rot });
  }
  return map;
}

/** 平移/旋转有界盒：纯平移保轴有界性；旋转按 8 角点变换、全轴视为有界（保守） */
function applyTransform(box: MiniBox, t: Transform): MiniBox {
  if (isIdentityMatrix(t.rot)) {
    return {
      lo: { x: box.lo.x + t.o[0], y: box.lo.y + t.o[1], z: box.lo.z + t.o[2] },
      hi: { x: box.hi.x + t.o[0], y: box.hi.y + t.o[1], z: box.hi.z + t.o[2] },
      axes: box.axes,
    };
  }
  const r = t.rot;
  const corners: Vec3[] = [];
  for (const x of [box.lo.x, box.hi.x]) {
    for (const y of [box.lo.y, box.hi.y]) {
      for (const z of [box.lo.z, box.hi.z]) {
        corners.push({
          x: t.o[0] + r[0][0] * x + r[0][1] * y + r[0][2] * z,
          y: t.o[1] + r[1][0] * x + r[1][1] * y + r[1][2] * z,
          z: t.o[2] + r[2][0] * x + r[2][1] * y + r[2][2] * z,
        });
      }
    }
  }
  const b = boxFromCorners(corners);
  return { ...b, axes: [true, true, true] };
}

/** 解析单行曲面卡 → { mnemonic, params, tr }；非曲面卡返回 null */
function parseSurfaceLine(toks: string[]): { mnemonic: string; params: string[]; tr: string | null } | null {
  if (toks.length === 0) return null;
  const id = toks[0].replace(/^[+*]/, "");
  if (!/^\d+$/.test(id)) return null; // 注释/非曲面卡
  let idx = 1;
  let tr: string | null = null;
  if (idx < toks.length && /^-?\d+$/.test(toks[idx])) {
    const n = parseInt(toks[idx], 10);
    if (n > 0) tr = String(n);
    else if (n < 0) return null; // 周期性曲面（负数变换）跳过
    idx += 1;
  }
  if (idx >= toks.length) return null;
  const mnemonic = toks[idx].toUpperCase();
  return { mnemonic, params: toks.slice(idx + 1), tr };
}

/**
 * 从曲面卡文本计算模型 AABB。
 * @param surfaces 曲面卡文本（deck.surfaces，每行一张卡）
 * @param trCards TRn 变换卡文本（deck.tr_cards，可选；曲面引用未提供的 TR 则跳过该曲面）
 * @returns {min,max}；任一轴无界 / 无可解曲面 / 输入为空 → null
 */
export function computeSurfacesAABB(surfaces: string, trCards?: string): AABB | null {
  const trs = parseTrCards(trCards || "");
  const lo = [Infinity, Infinity, Infinity];
  const hi = [-Infinity, -Infinity, -Infinity];
  const bounded = [false, false, false];

  // 合并续行（MCNP 续行 = 行首 5 空格），逐曲面解析
  const logical: string[][] = [];
  for (const raw of (surfaces || "").split(/\r?\n/)) {
    const s = raw.split("$")[0].replace(/\r$/, "");
    if (/^\s{5,}/.test(s) && logical.length > 0) {
      logical[logical.length - 1].push(...s.trim().split(/\s+/));
    } else if (s.trim()) {
      logical.push(s.trim().split(/\s+/));
    }
  }

  for (const toks of logical) {
    const parsed = parseSurfaceLine(toks);
    if (!parsed) continue;
    const params = parsed.params.map(parseFloat);
    let box = surfaceMiniBox(parsed.mnemonic, params);
    if (!box) continue;
    if (![box.lo.x, box.lo.y, box.lo.z, box.hi.x, box.hi.y, box.hi.z].every(Number.isFinite)) continue;
    if (parsed.tr) {
      const t = trs.get(parsed.tr);
      if (!t) continue; // TR 未解析 → 跳过该曲面（容错）
      box = applyTransform(box, t);
    }
    for (let i = 0; i < 3; i++) {
      if (!box.axes[i]) continue;
      bounded[i] = true;
      const arrLo = [box.lo.x, box.lo.y, box.lo.z];
      const arrHi = [box.hi.x, box.hi.y, box.hi.z];
      lo[i] = Math.min(lo[i], arrLo[i]);
      hi[i] = Math.max(hi[i], arrHi[i]);
    }
  }

  if (!bounded[0] || !bounded[1] || !bounded[2]) return null; // 有轴无界 → 解不出
  if (![lo[0], lo[1], lo[2], hi[0], hi[1], hi[2]].every(Number.isFinite)) return null;
  return {
    min: { x: lo[0], y: lo[1], z: lo[2] },
    max: { x: hi[0], y: hi[1], z: hi[2] },
  };
}

/** 坐标格式化：去多余尾零（-100 → "-100"，2.5 → "2.5"） */
export function formatCoord(n: number): string {
  if (!Number.isFinite(n)) return "";
  return parseFloat(n.toPrecision(12)).toString();
}

/** AABB → FMESH 填表值：ORIGIN=min，IMESH/JMESH/KMESH=max（网格自动覆盖模型） */
export function aabbToFmeshValues(aabb: AABB): { origin: string; imesh: string; jmesh: string; kmesh: string } {
  return {
    origin: `${formatCoord(aabb.min.x)} ${formatCoord(aabb.min.y)} ${formatCoord(aabb.min.z)}`,
    imesh: formatCoord(aabb.max.x),
    jmesh: formatCoord(aabb.max.y),
    kmesh: formatCoord(aabb.max.z),
  };
}
