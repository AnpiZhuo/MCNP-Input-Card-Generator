/**
 * trackColors — PTRAC 径迹粒子类型基色 + 能量深浅渐变（契约 ptrac-visualization.md §4）
 *
 * 用户敲定三色：n=蓝(#3b82f6) / p=红(#ef4444) / e=黄(#eab308)，其余灰(#9ca3af)。
 * trackShade(color, energy01)：把基色在 HSL 空间做 lightness 插值——低能浅、高能深
 * （energy01∈[0,1]，0=低能→浅、1=高能→深），供径迹顶点色逐点着色。
 */

export type ParticleKey = "n" | "p" | "e";

/** 粒子类型 → 基色（用户敲定三色） */
export const TRACK_COLORS: Record<string, string> = {
  n: "#3b82f6", // 中子 · 蓝
  p: "#ef4444", // 光子 · 红
  e: "#eab308", // 电子 · 黄
};

/** 其余粒子类型（未识别/未知）→ 灰 */
export const TRACK_FALLBACK_COLOR = "#9ca3af";

/** 粒子类型中文标签（面板勾选/图例） */
export const TRACK_PARTICLE_LABELS: Record<string, string> = {
  n: "中子",
  p: "光子",
  e: "电子",
};

/** 能量深浅图例常量：低能浅 → 高能深 的 HSL lightness 区间（0..1） */
export const SHADE_LIGHT = 0.78; // 低能（浅）
export const SHADE_DARK = 0.32;  // 高能（深）

/** 面板图例列表（三色 + 中文标签，顺序固定 n/p/e） */
export const TRACK_LEGEND: { key: ParticleKey; label: string; color: string }[] = [
  { key: "n", label: TRACK_PARTICLE_LABELS.n, color: TRACK_COLORS.n },
  { key: "p", label: TRACK_PARTICLE_LABELS.p, color: TRACK_COLORS.p },
  { key: "e", label: TRACK_PARTICLE_LABELS.e, color: TRACK_COLORS.e },
];

/** 粒子类型 → 基色（未知 → 灰） */
export function trackColor(particle: string): string {
  return TRACK_COLORS[particle] ?? TRACK_FALLBACK_COLOR;
}

/** 能量归一化到 [0,1]（全局 min/max；退化区间/非有限值 → 0） */
export function normalizeEnergy01(energy: number, range: { min: number; max: number }): number {
  if (!Number.isFinite(energy) || !Number.isFinite(range.min) || !Number.isFinite(range.max)) return 0;
  if (range.max <= range.min) return 0;
  const t = (energy - range.min) / (range.max - range.min);
  return Math.min(1, Math.max(0, t));
}

/**
 * 全体径迹点的能量区间（点第 5 元 energy，缺/非正/非有限忽略）。
 * 无有效能量 → { min: 0, max: 1 }（全浅色）。
 * 供归一化 + 能量深浅图例共用（单一权威）。
 */
export function energyRangeOfTracks(tracks: { points: number[][] }[]): { min: number; max: number } {
  let min = Infinity;
  let max = -Infinity;
  for (const t of tracks || []) {
    for (const p of t.points || []) {
      const e = Number(p[4]);
      if (!Number.isFinite(e) || e <= 0) continue;
      if (e < min) min = e;
      if (e > max) max = e;
    }
  }
  if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) return { min: 0, max: 1 };
  return { min, max };
}

/** hex（#rrggbb）→ { h, s, l }（0..1） */
function hexToHsl(hex: string): { h: number; s: number; l: number } {
  const c = (hex || "#9ca3af").replace("#", "");
  const r = parseInt(c.slice(0, 2), 16) / 255 || 0;
  const g = parseInt(c.slice(2, 4), 16) / 255 || 0;
  const b = parseInt(c.slice(4, 6), 16) / 255 || 0;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  if (max === min) return { h: 0, s: 0, l };
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h: number;
  if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
  else if (max === g) h = (b - r) / d + 2;
  else h = (r - g) / d + 4;
  h /= 6;
  return { h, s, l };
}

/** { h, s, l }（0..1）→ hex（#rrggbb） */
function hslToHex(h: number, s: number, l: number): string {
  const hue2rgb = (p: number, q: number, t: number): number => {
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
  };
  let r: number, g: number, b: number;
  if (s === 0) {
    r = g = b = l;
  } else {
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    const p = 2 * l - q;
    r = hue2rgb(p, q, h + 1 / 3);
    g = hue2rgb(p, q, h);
    b = hue2rgb(p, q, h - 1 / 3);
  }
  const toHex = (v: number): string =>
    Math.round(Math.min(1, Math.max(0, v)) * 255).toString(16).padStart(2, "0");
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

/**
 * 基色 + 能量归一值 → 深浅色（低能浅、高能深）。
 * lightness 在 [SHADE_DARK, SHADE_LIGHT] 内随 energy01 线性插值，hue/sat 保持基色不变。
 */
export function trackShade(color: string, energy01: number): string {
  const t = Math.min(1, Math.max(0, energy01));
  const { h, s } = hexToHsl(color);
  const l = SHADE_LIGHT + (SHADE_DARK - SHADE_LIGHT) * t; // t=0 浅、t=1 深
  return hslToHex(h, s, l);
}
