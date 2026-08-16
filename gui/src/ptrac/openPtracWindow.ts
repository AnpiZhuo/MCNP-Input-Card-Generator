/**
 * openPtracWindow — 「3D 径迹」（PTRAC）独立窗口的共享开窗逻辑（契约 ptrac-visualization.md §4）
 *
 * OutputTab 入口统一用：组装桥数据（stlData/cells/ptracPath/maxTracks/maxPoints）→
 * openPtracWindow（windows.ts 桥写 + Rust 开窗）→ 非 Tauri fallback 提示 #/ptrac。
 * 照 openVolume3DWindow 范式，行为一致。
 */
import { errorHint, fetchPreview3dStl } from "../utils/api";
import { openPtracWindow } from "../utils/windows";

/** 几何外壳模型数据（无模型时不取 STL；桥数据 cells 由 cells 派生） */
export interface PtracModel {
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

export interface OpenPtracWindowParams {
  /** ptrac 文件路径（后端可访问） */
  path: string;
  /** 几何外壳模型（cells 非空或 surfaces 非空才取 STL；无模型则无外壳） */
  model?: PtracModel | null;
  maxTracks?: number;
  maxPoints?: number;
}

export type OpenPtracWindowOutcome =
  | { ok: true }
  /** 非 Tauri：桥数据已写 localStorage，提示可访问 #/ptrac 调试入口 */
  | { ok: false; kind: "fallback"; message: string }
  /** 异常（errorHint 优先显示 hint） */
  | { ok: false; kind: "error"; message: string };

/**
 * 开窗：取 STL 外壳（有模型时）→ 组装桥数据 → openPtracWindow → 非 Tauri fallback 提示。
 */
export async function openPtrac3DWindow(params: OpenPtracWindowParams): Promise<OpenPtracWindowOutcome> {
  // maxTracks 上限给足：WRITE=SOURCE 时每粒子 1 点、10 万粒子 → 10 万条径迹，
  // 单点径迹在渲染器里合并成一个 Points 云（一次 draw call），可流畅显示全部。
  // 多事件径迹（WRITE=EVENT/ALL）由 maxPoints 兜底抽稀，密度抽样滑杆可进一步降采样。
  const { path, model, maxTracks = 100000, maxPoints = 200000 } = params;
  try {
    const hasModel = !!(model?.cells && model.cells.length) || !!model?.surfaces;
    const cellsForBackend = (model?.cells || []).map((c) => ({
      number: parseInt(c.num, 10) || 0,
      material: c.mat,
      density: c.density || "",
      surface_expr: c.surfaces || c.surface_expr || "",
    }));
    const stlData = hasModel
      ? await fetchPreview3dStl(cellsForBackend, model?.surfaces || "", model?.trCards || "")
      : {};
    const opened = await openPtracWindow({
      stlData,
      cells: (model?.cells || []).map((c) => ({ num: String(c.num), mat: c.mat, comment: c.comment || "" })),
      ptracPath: path,
      maxTracks,
      maxPoints,
    });
    if (!opened) {
      // 非 Tauri（浏览器模式）：桥数据已写 localStorage，提示可用 #/ptrac 调试入口
      return { ok: false, kind: "fallback", message: "已写入 3D 径迹数据（浏览器模式无法自动开窗，可访问 #/ptrac 查看）" };
    }
    return { ok: true };
  } catch (e: any) {
    return { ok: false, kind: "error", message: errorHint(e, "打开 3D 径迹窗口失败") };
  }
}
