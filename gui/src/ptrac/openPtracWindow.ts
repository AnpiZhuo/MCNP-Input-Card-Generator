/**
 * openPtracWindow — 「3D 径迹」（PTRAC）独立窗口的共享开窗逻辑（契约 ptrac-visualization.md §4）
 *
 * OutputTab 入口统一用：组装桥数据（cells/model/ptracPath/maxTracks/maxPoints）→
 * openPtracWindow（windows.ts 桥写 + Rust 开窗）→ 非 Tauri fallback 提示 #/ptrac。
 * 照 openVolume3DWindow 范式，行为一致。
 *
 * ⚠️ 2026-10-21 修复（用户实测「解析 PTRAC 后窗口显示『没有 3D 径迹数据』」）：
 * 旧实现在**主窗口**取完整 STL 并把 base64 塞进 localStorage 桥（18 栅元 deck 实测
 * 21,142,374 字符）⇒ 超过 localStorage 配额（≈5M 字符）⇒ setItem 抛 QuotaExceededError ⇒
 * 异常被吞掉但窗口照开 ⇒ 子窗口读不到桥 ⇒ 只显示兜底文案（症状误导成"你没解析"）。
 * 现在桥里**只放几何描述**（cells/surfaces/trCards，几十 KB），外壳由子窗口自己调
 * `/api/preview-3d` 取（走同一个 deck 指纹缓存，二次打开 ≤1s）——契约 §4 原本就是这么写的。
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

/** 桥里下传的几何描述（子窗口据此自取外壳；**绝不能**带 STL 网格，见文件头） */
export interface PtracBridgeModel {
  cells: { number: number; material: string; density: string; surface_expr: string }[];
  surfaces: string;
  trCards: string;
}

/**
 * 开窗：组装桥数据（几何描述 + 径迹路径）→ openPtracWindow → 非 Tauri fallback 提示。
 *
 * 有模型时**仍然在主窗口预热一次** `/api/preview-3d`，但**结果只用于预热后端 deck 指纹缓存**
 * （子窗口随后自取同一份，命中缓存），不进桥 —— 这样：
 *   ① 不会写爆 localStorage；
 *   ② 按钮上的「解析中…」语义不变，几何错误在这里就能暴露；
 *   ③ 子窗口打开后外壳 ≤1s 到位。
 */
export async function openPtrac3DWindow(params: OpenPtracWindowParams): Promise<OpenPtracWindowOutcome> {
  // maxTracks 上限给足：EVENT=src 时每粒子 1 点、10 万粒子 → 10 万条径迹，
  // 单点径迹在渲染器里合并成一个 Points 云（一次 draw call），可流畅显示全部。
  // 多事件径迹（WRITE=ALL 或 EVENT 含 sur/col/ter）由 maxPoints 兜底抽稀，密度抽样滑杆可进一步降采样。
  const { path, model, maxTracks = 100000, maxPoints = 200000 } = params;
  try {
    const hasModel = !!(model?.cells && model.cells.length) || !!model?.surfaces;
    const bridgeModel: PtracBridgeModel | null = hasModel
      ? {
          cells: (model?.cells || []).map((c) => ({
            number: parseInt(c.num, 10) || 0,
            material: c.mat,
            density: c.density || "",
            surface_expr: c.surfaces || c.surface_expr || "",
          })),
          surfaces: model?.surfaces || "",
          trCards: model?.trCards || "",
        }
      : null;

    if (bridgeModel) {
      // 只预热后端缓存：结果**丢弃**（放进桥会超 localStorage 配额 —— 见文件头 2026-10-21 缺陷）。
      // 失败不阻断：子窗口会再取一次，届时错误显示在窗口内（径迹仍可先看到）。
      try {
        await fetchPreview3dStl(bridgeModel.cells, bridgeModel.surfaces, bridgeModel.trCards);
      } catch (e) {
        console.warn("ptrac 外壳预热失败（子窗口将重试）", e);
      }
    }

    const opened = await openPtracWindow({
      model: bridgeModel,
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
