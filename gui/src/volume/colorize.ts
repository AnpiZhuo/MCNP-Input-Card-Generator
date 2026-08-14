/**
 * colorize — 天气图式色阶 LUT + CPU 上色（契约 meshtal-visualization.md §4.3 / §4.3.1 / §12 A2.2）
 *
 * 与后端 `app/meshtal/colormap.py` 逐字节一致：
 * - WEATHER_STOPS 锚点单一事实来源（蓝→青→黄→橙→红）
 * - `weatherLut()` 256 项 RGBA 的 sha256 **必须等于**
 *   `36770ae2b9cd2a2ac3b6e6a08de45d522261dfced960c0c1db49bc515358c038`
 *   （跨语言防漂移，t=i/(n-1) 线性插值，round-half-even）
 * - `colorizeScalar`：v < displayMin（色阶下限=显示阈值）→ alpha 0；线性映射到 LUT
 *
 * 标量帧来自后端 `frame.dataBase64`（Uint8 归一化 [0,255]，numpy (x,y,z) 扁平），
 * 输出 RGBA 保持同一布局（上传时由 VolumeRenderer 按 DataTexture3D dims 处理）。
 */
export type RGBA = [number, number, number, number];

/** §4.3.1 配色锚点（python colormap.WEATHER_STOPS 镜像，禁止漂移） */
export const WEATHER_STOPS: [number, RGBA][] = [
  [0.0, [0x3b, 0x4c, 0xc0, 255]], // 蓝
  [0.33, [0x00, 0xe5, 0xff, 255]], // 青
  [0.55, [0xfd, 0xe0, 0x47, 255]], // 黄
  [0.75, [0xf9, 0x73, 0x16, 255]], // 橙
  [1.0, [0xdc, 0x26, 0x26, 255]], // 红
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
