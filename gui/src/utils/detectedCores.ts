/**
 * detectedCores — 本机 CPU 核数检测（**单一权威**，SweepDialog / PreviewDialog 共用）。
 *
 * 此前 `DETECTED_CORES` 在 `SweepDialog.tsx` 与 `PreviewDialog.tsx` 里**各复制了一份**
 * （同一行代码两处），本模块消除该重复。
 *
 * ⚠️ `navigator.hardwareConcurrency` 给的是**逻辑核**（含 SMT 超线程），而实测
 * **MCNP 的 `tasks` 取物理核数最优** —— 本机 AMD Ryzen 7 4800H（8 物理核 / 16 逻辑核）：
 *
 *   | tasks | 墙钟  | CPU 时间 | CPU/墙钟 |
 *   | 1     | 22.35s| 22.22s   | 0.99     |
 *   | 4     |  8.38s| 33.2s    | 3.96     |
 *   | 8     |  8.36s| 65.5s    | 7.83 ← 最优 |
 *   | 16    | 15.06s| 205.73s  | 13.66 ← 最差（超订）|
 *
 * 16 个线程挤进 8 个物理核，SMT 对计算密集型无吞吐收益，205s CPU 里大半是自旋等待。
 * 前端拿不到物理核，故以 `ceil(逻辑核 / 2)`（SMT 通常 ×2）作为**推荐值**，
 * 但**默认值保持既有行为**（`min(8, 逻辑核)`），避免在无 SMT 的机器上反而降级。
 *
 * 另注：C810（页 875）规定 `DBCN(2,3,4)` / `SSW` / `SSR` / `PTRAC` **与 `tasks > 1`
 * 不兼容（FATAL error）** —— 后端 `_handle_run_mcnp` 会扫卡拦截，见该处注释。
 */

const LOGICAL = Math.max(
  1,
  (typeof navigator !== "undefined" && navigator.hardwareConcurrency) || 4,
);

/** 逻辑核数（含超线程）—— 滑杆上限 */
export const DETECTED_CORES = LOGICAL;

/** 默认并发/线程数（**保持既有行为**：min(8, 逻辑核)） */
export const DEFAULT_WORKERS = Math.max(1, Math.min(8, LOGICAL));

/** 物理核估计（SMT 通常为逻辑核的一半）—— MCNP `tasks` 的推荐值 */
export const SUGGESTED_WORKERS = Math.max(1, Math.ceil(LOGICAL / 2));

/** 把任意输入夹到合法线程数区间 [1, DETECTED_CORES] */
export function clampWorkers(v: number): number {
  return !Number.isFinite(v) ? 1 : Math.max(1, Math.min(DETECTED_CORES, Math.round(v)));
}
