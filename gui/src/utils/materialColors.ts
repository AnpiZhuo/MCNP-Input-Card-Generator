/**
 * 材料颜色单一权威 — 3D 预览与二维截面共用同一调色板
 * 高饱和、色相均匀分布的 12 色，确保相邻材料号颜色可区分。
 */
const COLORS = [
  "#FF5252", "#00C853", "#2979FF", "#FFEA00", "#AA00FF", "#00E5FF",
  "#FF6D00", "#FF4081", "#76FF03", "#6200EA", "#1DE9B6", "#FFAB40",
];

/** 材料号 → 颜色（材料 0 为真空/不关注区域，取第 0 个颜色） */
export function getMatColor(mat: string): string {
  const n = parseInt(mat) || 0;
  return COLORS[Math.abs(n) % COLORS.length];
}
