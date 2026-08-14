/**
 * downsampleRequest — 分辨率决策请求（契约 meshtal-visualization.md §4.4 / §8 / §12 A2.3 / F3）
 *
 * 镜像后端 `app/meshtal/downsample_plan.py`：
 * - GPU 驻留预算 ≤256MB；128³ 默认（流畅）/ 256³ 仅显式选（A2.3）
 * - native 更小保 native（avgFactor=1）
 * - 超预算 → popup:true + 大白话弹窗文案（F3）：「要更流畅，还是要更精细？」
 *   （流畅=自动降采样 / 精细=保原精度）
 *
 * 纯逻辑，vitest 可测。
 */
export const GPU_BUDGET_BYTES = 256 * 1024 * 1024; // GPU 驻留预算 ≤256MB
export const DEFAULT_RESOLUTION = 128; // 128³ 默认（流畅）
export const MAX_RESOLUTION = 256; // 256³ 供用户显式选

/** F3 超预算弹窗文案（大白话，非技术术语） */
export const OVER_BUDGET_POPUP_COPY = "要更流畅，还是要更精细？";

/** RGBA 每体素 4B：128³=8MiB、256³=64MiB */
export function estimateTextureBytes(dims: number[]): number {
  let n = 1;
  for (const d of dims) n *= Math.max(0, Math.floor(d));
  return n * 4;
}

export interface DownsamplePlan {
  outDims: number[];
  avgFactor: number[];
  fitsBudget: boolean;
  overBudget: boolean;
}

export interface ResolutionDecision {
  resolution: number;
  popup: boolean;
  recommended: "smooth" | "precise" | "";
  popupCopy: string;
}

/** 每轴 out = min(target, native)；每轴 factor = max(1, ceil(native/out)) */
export function planDownsample(
  native: number[],
  targetRes: number,
  budgetBytes = GPU_BUDGET_BYTES,
): DownsamplePlan {
  const outDims = native.map((n) => Math.min(Math.floor(targetRes), Math.floor(n)));
  const avgFactor = native.map((n, i) => {
    const o = outDims[i];
    return Math.max(1, Math.ceil(Math.floor(n) / o));
  });
  const fits = estimateTextureBytes(outDims) <= budgetBytes;
  return { outDims, avgFactor, fitsBudget: fits, overBudget: !fits };
}

/**
 * requested=128 默认 / 256 显式；native 更小保 native；超预算 → popup 素材。
 * 默认 128³ 自动决策（A2.3）：无用户选择时自动 128，仅显式才 256。
 */
export function decideResolution(
  nativeDims: number[],
  requested?: number | null,
  budgetBytes = GPU_BUDGET_BYTES,
): ResolutionDecision {
  const target = requested == null || requested === 0 ? DEFAULT_RESOLUTION : Math.floor(requested);
  const plan = planDownsample(nativeDims, target, budgetBytes);
  return {
    resolution: target,
    popup: plan.overBudget,
    recommended: plan.overBudget ? "smooth" : "",
    popupCopy: plan.overBudget ? OVER_BUDGET_POPUP_COPY : "",
  };
}
