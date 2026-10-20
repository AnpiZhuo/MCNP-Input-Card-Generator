/**
 * openVolume3DWindow — 「3D 结果」（体积可视化）独立窗口的共享开窗逻辑
 * （契约 meshtal-visualization.md §4.7 / §12 F3/F4；入口统一到「输出」标签页）
 *
 * FMeshForm 与 OutputTab 共用：openVolume3D 数据桥 + 非 Tauri fallback 提示。
 * 行为逐字节保持原 FMeshForm.openWindow（含 #/volume 提示文案、errorHint 错误处理）。
 */
import { errorHint, fetchPreview3dStl, type MeshtalTallyMeta, type MeshtalParseResult } from "../utils/api";
import { openVolume3D } from "../utils/windows";
import type { FmeshRow } from "./fmeshState";

/** 从工作区读取 outputDir（App 把 outputPath 存进 mcnp_workspace_v1；原 FMeshForm 实现） */
export function readOutputDir(): string {
  try {
    const s = JSON.parse(localStorage.getItem("mcnp_workspace_v1") || "null");
    if (s && s.outputPath) return s.outputPath;
  } catch {}
  return "D:/MCNP/new";
}

/** 几何外壳模型数据（无模型时不取 STL；桥数据栅元视图由 cells 派生） */
export interface Volume3DModel {
  cells: {
    num: string;
    mat: string;
    comment?: string;
    density?: string;
    surfaces?: string;
    surface_expr?: string;
  }[];
  surfaces: string;
  trCards: string;
}

export interface OpenVolume3DWindowParams {
  /** meshtal 文件路径（后端可访问） */
  path: string;
  /** 目标 tally（xyz 矩形网格） */
  tally: MeshtalTallyMeta;
  /** 分辨率（128 默认 / 256 显式） */
  resolution: number;
  /** 几何外壳模型（照原 openWindow：cells 非空或 surfaces 非空才取 STL） */
  model?: Volume3DModel | null;
  /** 解析结果元数据（worldBox / match） */
  parseResult?: MeshtalParseResult | null;
  /** 当前 deck 的 FMESH 行（判定能量沉积 *fmesh：tally.number 匹配 fn_prefix="*" → MeV/g） */
  fmesh?: FmeshRow[];
}

export type OpenVolume3DWindowOutcome =
  | { ok: true }
  /** 非 Tauri：桥数据已写 localStorage，提示可访问 #/volume 调试入口 */
  | { ok: false; kind: "fallback"; message: string }
  /** 异常（errorHint 优先显示 hint） */
  | { ok: false; kind: "error"; message: string };

/**
 * 判定某 meshtal tally 是否为能量沉积（*fmesh，MeV/g）：
 * 当前 deck 的 fmesh 行里，卡号匹配本 tally.number 且 fn_prefix="*" → 能量沉积。
 * 纯函数（vitest 可测）；这是最可靠来源（用户自建 *fmesh 卡）。
 */
export function isDepositionTally(fmesh: FmeshRow[] | undefined, tallyNumber: number): boolean {
  return (fmesh || []).some(
    (r) => String(r.number) === String(tallyNumber) && r.fn_prefix === "*",
  );
}

/**
 * 开窗：只把**几何描述**放进桥（几何外壳 STL 由子窗口自己调 /api/preview-3d 取）→ openVolume3D。
 *
 * ⚠️ 2026-10-21：旧实现把整份 base64 STL 写进 localStorage 桥（18 栅元 deck 实测 21,142,374 字符），
 * 超过 localStorage 配额（≈5M 字符）⇒ setItem 抛 QuotaExceededError ⇒ 子窗口读不到桥，只显示
 * 「没有 3D 结果数据」。「3D 径迹」窗口同源缺陷已随本批修复，这里同口径处理：
 *   - 桥里只放 cells/surfaces/trCards（几十 KB）；
 *   - 主窗口仍预热一次 /api/preview-3d（为子窗口命中 deck 指纹缓存），但**结果不进桥**。
 */
export async function openVolume3DWindow(params: OpenVolume3DWindowParams): Promise<OpenVolume3DWindowOutcome> {
  const { path, tally, resolution, model, parseResult, fmesh } = params;
  try {
    const hasModel = !!(model?.cells && model.cells.length) || !!model?.surfaces;
    const cellsForBackend = (model?.cells || []).map((c) => ({
      number: parseInt(c.num, 10) || 0,
      material: c.mat,
      density: c.density || "",
      surface_expr: c.surfaces || c.surface_expr || "",
    }));
    const bridgeModel = hasModel
      ? { cells: cellsForBackend, surfaces: model?.surfaces || "", trCards: model?.trCards || "" }
      : null;
    if (bridgeModel) {
      // 只预热后端缓存（结果丢弃：进桥会超 localStorage 配额）；失败不阻断，子窗口会再取一次
      try {
        await fetchPreview3dStl(bridgeModel.cells, bridgeModel.surfaces, bridgeModel.trCards);
      } catch (e) {
        console.warn("volume3d 外壳预热失败（子窗口将重试）", e);
      }
    }
    const energyOptions = buildBinOptions(tally.binEdges?.energy || []);
    const timeOptions = buildBinOptions(tally.binEdges?.time || []);
    // 能量沉积（*fmesh）判定：当前 deck 的 fmesh 行里，卡号匹配本 tally 且 fn_prefix="*" → MeV/g。
    // 这是最可靠来源（用户自建 *fmesh 卡）；meshtal 头无能量沉积标志也能正确显示单位。
    const isDeposition = isDepositionTally(fmesh, tally.number);
    const unit = isDeposition ? "MeV/g（能量沉积）" : "归一化计数";
    const opened = await openVolume3D({
      model: bridgeModel,
      cells: (model?.cells || []).map((c) => ({ num: String(c.num), mat: c.mat, comment: c.comment || "" })),
      meshtal: {
        path,
        tallyNumber: tally.number,
        resolution,
        particle: tally.particle,
        geom: tally.geom,
      },
      energyOptions,
      timeOptions,
      worldBox: parseResult?.grid_bounds || null,
      scalarRange: { min: tally.range.min, max: tally.range.max },
      match: parseResult?.match || null,
      unit,
    });
    if (!opened) {
      // 非 Tauri（浏览器模式）：桥数据已写 localStorage，提示可用 #/volume 调试入口
      return { ok: false, kind: "fallback", message: "已写入 3D 结果数据（浏览器模式无法自动开窗，可访问 #/volume 查看）" };
    }
    return { ok: true };
  } catch (e: any) {
    return { ok: false, kind: "error", message: errorHint(e, "打开 3D 结果窗口失败") };
  }
}

/** 能量/时间 bin 边界 → 下拉选项（原 FMeshForm.buildBinOptions） */
export function buildBinOptions(edges: number[]): { index: number; label: string }[] {
  if (!edges || edges.length < 2) return [];
  const opts: { index: number; label: string }[] = [];
  for (let i = 0; i < edges.length - 1; i++) {
    opts.push({ index: i, label: fmtBound(edges[i]) + " → " + fmtBound(edges[i + 1]) });
  }
  return opts;
}

function fmtBound(v: number): string {
  if (v === 1e36) return "∞";
  if (Number.isInteger(v)) return String(v);
  return String(Math.round(v * 1000) / 1000);
}
