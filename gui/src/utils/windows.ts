/**
 * 独立弹出窗口工具 — Tauri 多窗口 + localStorage 数据桥
 *
 * 主窗口写数据到 localStorage → 调 Rust command 开窗 → 新窗口读取 → 渲染。
 * 所有窗口同源（tauri://localhost），localStorage 天然共享。
 *
 * 用途：3D 预览 / 截面 独立窗口，主窗口可同时编辑。
 */
import type { DeckData } from "./dataCollector";
import { apiUrl } from "./api";

const KEY_PREVIEW3D = "mcnp_win_preview3d";
const KEY_CROSS = "mcnp_win_cross";
const KEY_VOLUME3D = "mcnp_win_volume3d";
const KEY_MAT_CHANGE = "mcnp_win_material_change";
const KEY_PTRAC = "mcnp_win_ptrac";

/** 当前是否运行在 Tauri 环境（浏览器模式回退主窗口覆盖层） */
export async function isTauri(): Promise<boolean> {
  try {
    const m = await import("@tauri-apps/api/window");
    m.getCurrent().label;
    return true;
  } catch {
    return false;
  }
}

/** 当前窗口 label（非 Tauri 环境返回 "main"） */
export async function currentWindowLabel(): Promise<string> {
  try {
    const m = await import("@tauri-apps/api/window");
    return m.getCurrent().label;
  } catch {
    return "main";
  }
}

async function invoke(cmd: string): Promise<boolean> {
  try {
    const m = await import("@tauri-apps/api/tauri");
    await m.invoke(cmd);
    return true;
  } catch (e) {
    console.warn("invoke failed:", cmd, e);
    return false;
  }
}

/** 主窗口：打开 3D 预览独立窗口（先写数据桥再开窗） */
export async function openPreview3D(data: {
  cells: any[];
  surfaces: string;
  trCards: string;
  deck: DeckData;
}): Promise<boolean> {
  try {
    localStorage.setItem(KEY_PREVIEW3D, JSON.stringify({
      cells: data.cells,
      surfaces: data.surfaces,
      trCards: data.trCards,
      materials: (data.deck.materials || []).map((m) => ({ number: m.number, comment: m.comment })),
    }));
  } catch (e) {
    console.warn("preview3d bridge write failed", e);
  }
  return invoke("open_preview3d_window");
}

/** 主窗口/3D 窗口：打开截面独立窗口 */
export async function openCrossSection(data: {
  slices: any[];
  plane: { A: number; B: number; C: number; D: number };
  cells: { num: string; mat: string; comment?: string }[];
  /** 勾选且非真空的栅元号（截面窗口步进时复用） */
  cellNums: number[];
  /** 原始 STL 坐标系模型中心（截面窗口步进时做显示系→原始系平面换算） */
  center?: { x: number; y: number; z: number };
}): Promise<boolean> {
  try {
    localStorage.setItem(KEY_CROSS, JSON.stringify(data));
  } catch (e) {
    console.warn("cross-section bridge write failed", e);
  }
  return invoke("open_cross_section_window");
}

/** 读取 3D 预览桥数据（新窗口一次性消费） */
export function readPreview3DData(): {
  cells: any[]; surfaces: string; trCards: string; materials: { number: number; comment?: string }[];
} | null {
  try {
    const raw = localStorage.getItem(KEY_PREVIEW3D);
    if (!raw) return null;
    const j = JSON.parse(raw);
    localStorage.removeItem(KEY_PREVIEW3D);
    return j;
  } catch {
    return null;
  }
}

/** 主窗口：打开「3D 结果」（体积可视化）独立窗口（先写数据桥再开窗） */
export async function openVolume3D(data: Record<string, any>): Promise<boolean> {
  try {
    localStorage.setItem(KEY_VOLUME3D, JSON.stringify(data));
  } catch (e) {
    console.warn("volume3d bridge write failed", e);
  }
  return invoke("open_volume3d_window");
}

/** 读取「3D 结果」桥数据（新窗口一次性消费） */
export function readVolumeData(): Record<string, any> | null {
  try {
    const raw = localStorage.getItem(KEY_VOLUME3D);
    if (!raw) return null;
    const j = JSON.parse(raw);
    localStorage.removeItem(KEY_VOLUME3D);
    return j;
  } catch {
    return null;
  }
}

/** 主窗口：打开「3D 径迹」（PTRAC）独立窗口（先写数据桥再开窗） */
export async function openPtracWindow(data: Record<string, any>): Promise<boolean> {
  try {
    localStorage.setItem(KEY_PTRAC, JSON.stringify(data));
  } catch (e) {
    console.warn("ptrac bridge write failed", e);
  }
  return invoke("open_ptrac_window");
}

/** 读取「3D 径迹」桥数据（新窗口一次性消费） */
export function readPtracData(): Record<string, any> | null {
  try {
    const raw = localStorage.getItem(KEY_PTRAC);
    if (!raw) return null;
    const j = JSON.parse(raw);
    localStorage.removeItem(KEY_PTRAC);
    return j;
  } catch {
    return null;
  }
}

/** 读取截面桥数据（新窗口一次性消费） */
export function readCrossSectionData(): {
  slices: any[]; plane: { A: number; B: number; C: number; D: number };
  cells: { num: string; mat: string; comment?: string }[];
  cellNums?: number[];
  center?: { x: number; y: number; z: number };
} | null {
  try {
    const raw = localStorage.getItem(KEY_CROSS);
    if (!raw) return null;
    const j = JSON.parse(raw);
    localStorage.removeItem(KEY_CROSS);
    return j;
  } catch {
    return null;
  }
}

/** 3D 窗口 → 主窗口：材料改号回写（localStorage + storage 事件） */
export function emitMaterialChange(cellNum: string, newMat: string): void {
  try {
    localStorage.setItem(KEY_MAT_CHANGE, JSON.stringify({ cellNum, newMat, ts: Date.now() }));
  } catch (e) {
    console.warn("material-change emit failed", e);
  }
}

/** 主窗口：监听其它窗口发来的材料改号事件 */
export function onMaterialChange(cb: (cellNum: string, newMat: string) => void): () => void {
  const handler = (e: StorageEvent) => {
    if (e.key !== KEY_MAT_CHANGE || !e.newValue) return;
    try {
      const j = JSON.parse(e.newValue);
      if (j && j.cellNum != null) cb(String(j.cellNum), String(j.newMat));
    } catch {}
  };
  window.addEventListener("storage", handler);
  return () => window.removeEventListener("storage", handler);
}

/** 独立窗口：关闭自身（复用 Rust close_window 命令） */
export async function closeCurrentWindow(): Promise<boolean> {
  return invoke("close_window");
}

/** 通知后端删除 STL 会话目录（关 3D 预览窗口 / 主界面清空时调用） */
export function clearStlSession(): void {
  fetch(apiUrl("/api/clear-stl"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  }).catch(() => {});
}
