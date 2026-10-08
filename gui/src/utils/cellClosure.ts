/**
 * 栅元封闭性检测 — 纯类型 & 纯函数（零 React 依赖，可单测）
 *
 * 深模块 behind a small interface:
 *    interface = closureMeta(status) → {icon, color, label, allowed, title}
 *    depth     = 把后端 closure_report 的 6 种状态→前端展示的逻辑全藏在这里
 *
 * 调用方（useCellClosure hook / 直接测）只关心状态字符串，不关心怎么渲染。
 */

// ── 类型 ──

/** 单个栅元的封闭性检测结果 */
export interface ClosureEntry {
  status: "closed" | "infinite" | "semi_infinite" | "empty" | "voxel" | "unresolvable";
  volume?: number | null;
  aabb?: {
    xmin: number; xmax: number;
    ymin: number; ymax: number;
    zmin: number; zmax: number;
  } | null;
  infinite_axes?: string[];
}

/** 后端 /api/check-cell-closure 完整响应 */
export interface ClosureReport {
  [cellNum: string]: ClosureEntry;
}

/** 前端展示元数据 */
export interface ClosureMeta {
  icon: string;       // "✓" | "!" | "❌"
  color: string;      // CSS 颜色
  label: string;      // 中文标签
  allowed: boolean;   // true=允许（正常封闭/外无限），false=需修复
  title: string;      // hover 提示
}

// ── 纯函数（可单测）──

const _META: Record<string, ClosureMeta> = {
  closed:          { icon: "✓",  color: "#2e7d32", label: "封闭",     allowed: true,  title: "封闭有界" },
  infinite:        { icon: "!",  color: "#f9a825", label: "外无限",   allowed: true,  title: "外无限（曲面外空间，如 graveyard）" },
  semi_infinite:   { icon: "!",  color: "#f9a825", label: "部分无限", allowed: true,  title: "在某轴延伸到包围盒边界" },
  empty:           { icon: "❌", color: "#e53935", label: "空/退化", allowed: false, title: "体积≈0，检查几何定义" },
  voxel:           { icon: "❌", color: "#e53935", label: "体素网格", allowed: false, title: "GQ/SQ 体素，无法判定" },
  unresolvable:    { icon: "❌", color: "#e53935", label: "未解析",   allowed: false, title: "几何解析失败" },
};

/** 状态字符串 → 展示元数据；未知状态返回 fallback */
export function closureMeta(status: string): ClosureMeta {
  return _META[status]
    ?? { icon: "?", color: "var(--text-tertiary)", label: status, allowed: false, title: "未知状态" };
}

/**
 * 生成前封闭性复核的提示文案 —— **纯函数**，唯一来源。
 *
 * 用户 2026-10-08 报：「生成时的警告…没实时更新」。
 * 根因（读码定位）：`App.tsx` 的生成路径先读 `deck.cellClosureReport`，**有缓存就永不重算**
 * （而那份缓存没有任何失效机制），并且只有 `bad.length` 时才 `setClosureGenerateWarn(...)`
 * —— 几何变干净后旧警告留在屏幕上不走。两条都属于"陈旧"。
 * 现在：文案只由本函数产出，**干净就返回 null**（调用方无条件写入 ⇒ 必然清空），
 * 且生成路径不再复用旧报告（改为按当前几何重算）。
 */
export function closureWarnText(report: ClosureReport | null | undefined): string | null {
  if (!report) return null;
  const bad: string[] = [];
  for (const [num, info] of Object.entries(report)) {
    const st = (info as ClosureEntry | undefined)?.status;
    if (st === "infinite" || st === "semi_infinite") bad.push(`栅元 ${num}（外无限）`);
    else if (st === "empty") bad.push(`栅元 ${num}（空/退化）`);
    else if (st === "unresolvable") bad.push(`栅元 ${num}（未解析）`);
    else if (st === "voxel") bad.push(`栅元 ${num}（体素网格，无法判定）`);
  }
  if (!bad.length) return null;
  return `⚠ 生成前封闭性自检发现：${bad.join("、")}。` +
    "外无限栅元若为模型边界（imp=0 包围）属正常；空/未解析栅元请检查几何。";
}

/** 复核进行中的提示（生成时立即替换旧警告，让"是否已按当前几何更新"可见） */
export const CLOSURE_WARN_PENDING = "⏳ 正在按当前几何复核栅元封闭性…";
