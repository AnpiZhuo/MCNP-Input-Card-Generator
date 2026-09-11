/**
 * 材料颜色单一权威 — 3D 预览与二维截面共用同一调色板
 * 高饱和、色相均匀分布的 12 色，确保相邻材料号颜色可区分。
 */
const COLORS = [
  "#FF5252", "#00C853", "#2979FF", "#FFEA00", "#AA00FF", "#00E5FF",
  "#FF6D00", "#FF4081", "#76FF03", "#6200EA", "#1DE9B6", "#FFAB40",
];

/** 未知/缺材料号的中性色。⛔ 不得用 "transparent"——那是 M0 真空的专用语义 */
const UNKNOWN_MAT_COLOR = "#888888";

/**
 * 材料号 → 颜色（M0 定义为真空，透明色）。
 *
 * ⚠️ 必须把「M0 真空」与「材料号缺失/非法」分开：
 * 旧实现 `const n = parseInt(mat); if (!n) return "transparent";` 把两者混为一谈 ——
 * `parseInt("")` 是 NaN 而 `!NaN` 为真，于是**空材料号也返回 "transparent"**；
 * 下游 `buildCellMaterial` 以 `color === "transparent"` 判定真空，直接给 `opacity: 0`
 * ⇒ 整个几何外壳变成全透明不可见（2026-09-11 实测：演示源 13 个栅元全部看不见）。
 */
export function getMatColor(mat: string): string {
  const s = String(mat ?? "").trim();
  if (s === "") return UNKNOWN_MAT_COLOR;        // 材料号缺失 → 中性灰（可见）
  const n = parseInt(s, 10);
  if (!Number.isFinite(n)) return UNKNOWN_MAT_COLOR; // 非法材料号 → 中性灰
  if (n === 0) return "transparent";             // M0 = 真空 → 透明
  return COLORS[Math.abs(n) % COLORS.length];
}
