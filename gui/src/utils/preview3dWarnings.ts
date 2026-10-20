import type { ClosureReport } from "./cellClosure";

export function preview3dWarnings(result: {
  closure_report?: ClosureReport;
  parse_errors?: string[];
  skipped_cells?: { number?: number; reason?: string }[];
}): string[] {
  const warnings: string[] = [];
  for (const [num, entry] of Object.entries(result.closure_report || {})) {
    if (entry.status === "infinite" || entry.status === "semi_infinite") {
      warnings.push(`栅元 ${num} 无界，当前几何按包围盒裁剪显示，可能看起来像方块`);
    } else if (entry.status === "empty") {
      warnings.push(`栅元 ${num} 为空或退化`);
    } else if (entry.status === "unresolvable") {
      warnings.push(`栅元 ${num} 无法解析，未生成可靠几何`);
    }
  }
  for (const error of result.parse_errors || []) warnings.push(error);
  for (const skipped of result.skipped_cells || []) {
    if (skipped.number != null && skipped.reason) {
      warnings.push(`栅元 ${skipped.number}：${skipped.reason}`);
    }
  }
  return warnings;
}
