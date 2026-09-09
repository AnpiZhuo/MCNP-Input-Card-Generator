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

/** 从 closure_report 中提取某个栅元的状态（不存在返回 undefined） */
export function getClosureStatus(
  report: ClosureReport | null | undefined,
  cellNum: number | string,
): ClosureEntry | undefined {
  return report?.[String(cellNum)];
}