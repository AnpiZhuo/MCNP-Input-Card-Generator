/**
 * sweepHighlight — 参数扫描的**局部高亮**配色（按字符区间，不是整行）。
 *
 * ## 为什么按区间高亮
 *
 * 参数扫描的替换是文本级的：删掉框架选中的那几个字符、插入新值。所以界面上要标出来的
 * 也应该是**那几个字符**。原实现是"整行铺一条色底"（textarea 背后垫色条），用户 2026-10-11
 * 要求改成"所框选内容的局部高亮" —— 现在走 Monaco 的 decoration（见 `McnpEditor`）。
 *
 * ## 颜色怎么给 Monaco
 *
 * Monaco 的 `inlineClassName` 只认 **CSS 类名**，不能直接喂颜色值，所以这里把调色板
 * 一次性注入成 6 个类（`sweep-hl-0..5`），并在 Monaco 主题之外统一维护：
 * 调色板与类名在**同一份数据**里，不会出现"CSS 里改了颜色、TS 里还是旧的"这种漂移。
 */
export const SWEEP_COLORS = [
  "#facc15", "#22d3ee", "#4ade80", "#fb923c", "#c084fc", "#f472b6",
];

export const sweepHighlightClass = (i: number): string =>
  `sweep-hl-${((i % SWEEP_COLORS.length) + SWEEP_COLORS.length) % SWEEP_COLORS.length}`;

function rgba(hex: string, a: number): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

/** 幂等注入高亮样式（重复调用无副作用）。 */
export function ensureSweepHighlightStyles(): void {
  if (typeof document === "undefined") return;      // SSR / 测试环境无 document
  if (document.getElementById("sweep-hl-styles")) return;
  const css = SWEEP_COLORS.map((c, i) =>
    `.sweep-hl-${i}{background:${rgba(c, 0.30)};border-bottom:2px solid ${c};border-radius:2px;}`,
  ).join("");
  const el = document.createElement("style");
  el.id = "sweep-hl-styles";
  el.textContent = css;
  document.head.appendChild(el);
}
