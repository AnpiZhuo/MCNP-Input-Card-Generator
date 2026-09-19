/**
 * colorize — 天气图式色阶 LUT + CPU 上色（契约 meshtal-visualization.md §4.3 / §4.3.1 / §12 A2.2）
 *
 * 与后端 `app/meshtal/colormap.py` 逐字节一致：
 * - WEATHER_STOPS 锚点单一事实来源（**viridis 8 锚点**：深紫→蓝→青绿→黄绿→亮黄）
 * - `weatherLut()` 256 项 RGBA 的 sha256 **必须等于**
 *   `446949045f119ffa16f5e836cd39c400cd67836db0d5e17cb4b66af18ea74cdc`
 *   （跨语言防漂移，t=i/(n-1) 线性插值，round-half-even）
 * - `colorizeScalar`：v < displayMin（色阶下限=显示阈值）→ alpha 0；线性映射到 LUT
 *
 * ⚠️ **2026-09-19 换表**：原"蓝→青→黄→橙→红"在**黑白打印下会塌**（蓝与红亮度接近）。
 * 现用 **viridis**（感知均匀、色盲友好）：亮度沿 t 单调递增（0.019→0.782，灰阶 42→228），
 * 打印/复印后仍能读高低；换表连带改了 python 端与两个 golden sha256。
 *
 * 标量帧来自后端 `frame.dataBase64`（Uint8 归一化 [0,255]，numpy (x,y,z) 扁平），
 * 输出 RGBA 保持同一布局（上传时由 VolumeRenderer 按 DataTexture3D dims 处理）。
 */
export type RGBA = [number, number, number, number];

/** §4.3.1 配色锚点（python colormap.WEATHER_STOPS 镜像，禁止漂移；viridis，亮度单调） */
export const WEATHER_STOPS: [number, RGBA][] = [
  [0.0, [0x44, 0x01, 0x54, 255]], // 深紫
  [0.14, [0x41, 0x44, 0x87, 255]],
  [0.29, [0x2a, 0x78, 0x8e, 255]],
  [0.43, [0x22, 0xa8, 0x84, 255]],
  [0.57, [0x55, 0xc6, 0x67, 255]],
  [0.71, [0xa5, 0xdb, 0x37, 255]],
  [0.86, [0xdf, 0xe3, 0x18, 255]],
  [1.0, [0xfd, 0xe7, 0x25, 255]], // 亮黄
];

/** Python round() 语义（round-half-even），JS Math.round 是 round-half-away，必须自实现 */
export function roundHalfEven(x: number): number {
  const f = Math.floor(x);
  const frac = x - f;
  if (frac < 0.5) return f;
  if (frac > 0.5) return f + 1;
  return f % 2 === 0 ? f : f + 1;
}

/** t ∈ [0,1] → RGBA（锚点区间内线性插值，round-half-even） */
function interpT(t: number): RGBA {
  for (let k = 0; k < WEATHER_STOPS.length - 1; k++) {
    const [p0, c0] = WEATHER_STOPS[k];
    const [p1, c1] = WEATHER_STOPS[k + 1];
    if (t <= p1) {
      const frac = p1 === p0 ? 0 : (t - p0) / (p1 - p0);
      return [
        roundHalfEven(c0[0] + (c1[0] - c0[0]) * frac),
        roundHalfEven(c0[1] + (c1[1] - c0[1]) * frac),
        roundHalfEven(c0[2] + (c1[2] - c0[2]) * frac),
        roundHalfEven(c0[3] + (c1[3] - c0[3]) * frac),
      ];
    }
  }
  return WEATHER_STOPS[WEATHER_STOPS.length - 1][1];
}

/**
 * 天气图 LUT（默认 256 项），返回 RGBA 拼连 Uint8Array（长度 n*4）。
 * sha256 必须命中 golden `36770ae2…`（与 python weather_lut() 逐字节一致）。
 */
export function weatherLut(n = 256): Uint8Array {
  if (n <= 1) {
    if (n === 1) {
      const c = WEATHER_STOPS[0][1];
      return new Uint8Array(c);
    }
    return new Uint8Array(0);
  }
  const out = new Uint8Array(n * 4);
  for (let i = 0; i < n; i++) {
    const [r, g, b, a] = interpT(i / (n - 1));
    out[i * 4] = r;
    out[i * 4 + 1] = g;
    out[i * 4 + 2] = b;
    out[i * 4 + 3] = a;
  }
  return out;
}

export interface ScalarRange {
  min: number;
  max: number;
}

/**
 * 自适应色阶下限（默认显示阈值，纯函数）：
 * MCNP meshtal 虚空体素 = **精确 0** 通量（背景）。数据最小值恰为 0 时，
 * 阈值取 `minPositive * 0.5`——只隐去纯零背景，**所有正结构全部保留**
 * （用户实测：sqrt(minPositive×max) 切得过狠，200cm 粗光束只剩 1 体素宽的
 * "一个面"观感、光晕体素被误杀；纹理是线性 u8，比噪声更小的值本就量化为 0，
 * 无需再靠阈值切噪声）。无 minPositive 信息时保守兜底 max*1e-6；
 * 最小值 > 0（无零背景）→ 保持数据最小值（自适应色阶既有行为）；
 * 全零/负最小值（异常数据）→ 原样返回 min。
 */
export function defaultDisplayMin(scalarRange: ScalarRange, minPositive?: number): number {
  const { min, max } = scalarRange;
  if (min === 0 && max > 0) {
    if (minPositive !== undefined && minPositive > 0 && Number.isFinite(minPositive)) {
      return minPositive * 0.5;
    }
    return max * 1e-6;
  }
  return min;
}

/**
 * 标量帧字节的最小正值（float 重建，纯函数）：
 * 后端纹理为线性归一化 u8（f = u8*(max-min)/255 + min），0 字节 = 0 通量背景。
 * 返回最小的非零重建值；全零帧 → undefined。
 */
export function minPositiveOfBytes(bytes: Uint8Array, sr: ScalarRange): number | undefined {
  const scale = (sr.max - sr.min) / 255;
  const offset = sr.min;
  let best = Infinity;
  for (let i = 0; i < bytes.length; i++) {
    if (bytes[i] === 0) continue;
    const f = bytes[i] * scale + offset;
    if (f > 0 && f < best) best = f;
  }
  return best === Infinity ? undefined : best;
}

/**
 * 标量 u8 [0,255] → RGBA Uint8Array（长度 = scalar.length*4，布局与输入一致）。
 *
 * - 默认 `range` = 标量源范围（frame.scalarRange）→ 自适应数据范围（A2.2），
 *   用户手改上下限前即显示正确渐变。
 * - `displayMin`（色阶下限=显示阈值）：v 对应 float 值 < displayMin → alpha 0（不显示）。
 * - `scalarRange`：后端归一化源范围，用于把 u8 值重建回 float 单位做阈值/映射。
 */
export function colorizeScalar(
  scalar: Uint8Array,
  lut: Uint8Array,
  range: ScalarRange,
  displayMin: number,
  scalarRange?: ScalarRange,
): Uint8Array {
  const sr = scalarRange ?? { min: 0, max: 255 };
  const n = Math.max(lut.length >> 2, 1);
  const hi = range.max;
  const lo = range.min;
  const out = new Uint8Array(scalar.length * 4);
  // 预计算系数（热路径避免每体素除法）：f = scalar[i] * scale + offset
  const scale = (sr.max - sr.min) / 255;
  const offset = sr.min;
  const hasRange = hi > lo;
  const lutMul = n - 1;
  const invRange = hasRange ? 1 / (hi - lo) : 0;
  const base4 = 4;
  const len = scalar.length;
  for (let i = 0; i < len; i++) {
    const f = scalar[i] * scale + offset;
    if (f < displayMin) {
      // 色阶下限 = 显示阈值：低于不显示
      out[i * base4 + 3] = 0;
      continue;
    }
    let base = 0;
    if (hasRange) {
      let idx = Math.floor((f - lo) * invRange * lutMul);
      if (idx < 0) idx = 0;
      else if (idx > lutMul) idx = lutMul;
      base = idx * base4;
    }
    out[i * base4] = lut[base];
    out[i * base4 + 1] = lut[base + 1];
    out[i * base4 + 2] = lut[base + 2];
    out[i * base4 + 3] = 255;
  }
  return out;
}
