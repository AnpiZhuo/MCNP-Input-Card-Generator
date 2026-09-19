/**
 * quantityLabels — 图片里"量名称 / 量符号 / 单位"的**单一权威**（面向中文期刊）。
 *
 * ## 为什么单独一个模块
 * GB 3100~3102（量和单位）对出版物插图的要求是硬性的：
 *   - 坐标轴要给出**量名称**（中文）、**量符号**（斜体）与**单位**（正体）；
 *   - 单位用**负指数**，或"**斜线 + 负指数**"，但**不得在同一组合单位里又用斜线又用负指数**
 *     （`J/(kg·K)` 可以，`J/kg/K` 与 `J/(kg/K)` 都不行）；
 *   - 只写单位不写量名称（如轴标只写 "MeV"）不合规。
 * 这些字符串原先散在各图的调用点（屏幕文案直接拿来当轴标），语义混杂、改不全。
 * 收敛到这里之后，**改一次全图一致**，也便于单测逐条锁住格式。
 *
 * ## 排版口径（本模块统一决定）
 * 轴标 = `量名称 + " " + 量符号 + "/" + 单位`，例如：
 *   - `长度 L/mm`
 *   - `中子通量密度 φ/(cm⁻²·s⁻¹)`
 * 复杂单位一律**把负指数放进括号、括号外只有一个斜线** ⇒ 既合规划版，也不必上 MathML。
 * 单位里的次幂用 Unicode 上标字符（`⁻¹` `⁻²` `⁻³`）：PNG 是画进 canvas 的，
 * **不解析 `<sup>`/MathML**，用 Unicode 是唯一能一次画对的写法。
 */

/** 一条量的标注定义 */
export interface QuantitySpec {
  /** 量名称（中文），如「长度」 */
  name: string;
  /** 量符号（拉丁/希腊字母），如 `L`；**排版时应为斜体**（PNG 里以正体呈现，见模块末尾说明） */
  symbol: string;
  /** 单位（正体），可为空串（无量纲/计数类） */
  unit: string;
}

/** 单位里的上标（canvas 不解析 HTML，只能用 Unicode） */
const SUP: Record<string, string> = {
  "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
  "-": "⁻", "0": "⁰",
};

/** 把 `cm-2` 这种写法转成 `cm⁻²`（只处理单位后缀里的幂，不动数字本身） */
export function superscriptUnit(unit: string): string {
  return unit.replace(/([A-Za-z%°]+)(-?\d+)/g, (_m, base: string, exp: string) =>
    base + [...exp].map((c) => SUP[c] ?? c).join(""),
  );
}

/**
 * 量的字典（按用途命名，键是"我们在代码里怎么称呼它"）。
 *
 * ⚠️ 加新条目时请一并想清楚三件事：**量名称用哪个规范名**、**符号是否斜体惯例**、**单位是否负指数写法**。
 * 拿不准的宁可不写（留 `unit: ""`），也别编一个不合规的。
 */
export const QUANTITIES = {
  /** 长度/位置 */
  length: { name: "长度", symbol: "L", unit: "cm" },
  /** 能量（中子/光子能量） */
  energy: { name: "能量", symbol: "E", unit: "MeV" },
  /** 时间 */
  time: { name: "时间", symbol: "t", unit: "s" },
  /** 计数（无量纲，期刊惯例给"计数"作单位位置） */
  counts: { name: "计数", symbol: "N", unit: "计数" },
  /** 网格计数结果（MCNP 归一化计数，无量纲） */
  meshTally: { name: "网格计数", symbol: "N", unit: "归一化计数" },
  /** 能量沉积（*FMESH 的 MeV/g） */
  energyDeposition: { name: "比释动能", symbol: "K", unit: "MeV·g⁻¹" },
  /** 面通量（F2，cm⁻²） */
  surfaceFlux: { name: "面通量", symbol: "Φ", unit: "cm⁻²" },
  /** 体通量（F4，cm⁻²） */
  cellFlux: { name: "体通量", symbol: "Φ", unit: "cm⁻²" },
  /** 通量密度（按能量，F4 + E 分箱，cm⁻²·MeV⁻¹）——轴标写"每单位能量"，这里给出规范组合单位 */
  fluxPerEnergy: { name: "通量密度", symbol: "φ", unit: "cm⁻²·MeV⁻¹" },
  /** 通量密度（按时间） */
  fluxPerTime: { name: "通量密度", symbol: "φ", unit: "cm⁻²·s⁻¹" },
  /** 相对统计误差（MCNP 输出的 R，无量纲，百分数） */
  relError: { name: "相对误差", symbol: "R", unit: "%" },
  /** 有效增殖因子 */
  keff: { name: "有效增殖因子", symbol: "k", unit: "" },
  /** 概率密度（源分布） */
  probability: { name: "概率密度", symbol: "p", unit: "" },
  /** 立体角/角度 */
  angle: { name: "角度", symbol: "θ", unit: "°" },
} satisfies Record<string, QuantitySpec>;

export type QuantityKey = keyof typeof QUANTITIES;

/**
 * 分母写法：**带幂或带多个因子的单位一律加括号**（`cm⁻²` → `(cm⁻²)`，`g·cm⁻³` → `(g·cm⁻³)`）。
 *
 * 依据：GB 3100 允许"斜线 + 负指数"，但**同一组合单位里不得又用斜线又用负指数**；
 * 并且斜线后面**只能有一个因子**，多于一个必须加括号（`J/(kg·K)`，不是 `J/kg·K`）。
 * 实现上取最保守的读法：**只要单位里出现幂或乘点就加括号** ——
 * `φ/(cm⁻²)` 与 `φ/(cm⁻²·MeV⁻¹)` 都无歧义，而 `φ/cm⁻²` 在部分编辑眼里就是"斜线接了幂"的坏写法。
 * 代价是简单单位也要带括号，但 `L/cm` 这类不带幂的仍然不加 —— 版面不至于到处是括号。
 */
export function unitDenominator(unit: string): string {
  const u = superscriptUnit(unit);
  if (!u) return "";
  const needsParen = /[·\u00b7]/.test(u) || /[⁻⁰¹²³⁴⁵⁶⁷⁸⁹]/.test(u);
  return needsParen ? `(${u})` : u;
}

/**
 * 把一条量排成轴标：`量名称 量符号/单位`；单位为空时只到符号。
 *
 * 例：`长度 L/mm`、`通量密度 φ/(cm⁻²·MeV⁻¹)`、`有效增殖因子 k`
 */
export function axisLabel(key: QuantityKey | QuantitySpec): string {
  const q: QuantitySpec = typeof key === "string" ? QUANTITIES[key] : key;
  const den = unitDenominator(q.unit || "");
  const head = [q.name, q.symbol].filter(Boolean).join(" ");
  return den ? `${head}/${den}` : head;
}

/**
 * 带数值与单位的字符串（如刻度、图注里的数值）。
 *
 * 国标要求**数值与单位之间留一空格**（`12.3 MeV`），除非单位是角度符号（`30°`）或百分号（`5%`）。
 */
export function withUnit(value: string, unit: string): string {
  const noSpace = unit === "" || unit === "%" || unit === "°";
  const u = superscriptUnit(unit);
  if (noSpace) return `${value}${u}`;
  return `${value} ${u}`;
}

/**
 * ⚠️ **当前实现的已知缺口（写在这里，别以为是做完了）**：
 * GB 3100 要求**量符号用斜体**（`L`、`φ`）；而 PNG 是画进 canvas 的，
 * canvas 的 `fillText` 只能整段用一个字体风格 —— 想把同一行里的 `φ` 变斜体，
 * 必须**分段测量并逐段绘制**（`ctx.measureText` 切段 + 两套 font）。
 * 这一步尚未做：目前轴标整行正体。要补的话在 `figureCanvas.drawAxisLabel`
 * 里按"量名称 / 量符号 / 单位"三段分别绘制，并让 SVG 侧同步（那里可用 `<tspan font-style>`）。
 */
export const ITALIC_SYMBOL_PENDING = true;
