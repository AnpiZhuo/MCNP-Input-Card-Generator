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
const KEY_QUICK_CELL = "mcnp_win_quick_cell";
const KEY_SOURCE_DEMO = "mcnp_win_source_demo";
const KEY_TALLY_CHART = "mcnp_win_tally_chart";

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

/**
 * 开子窗口：Tauri 环境走 Rust command；**浏览器环境降级为 window.open(hash)**
 * （2026-09-10 加，为"浏览器端测试"提供能力——不必每次打包即可验收）。
 *
 * 前提（均已具备）：① 子窗口路由已由 `App.tsx` 按 `location.hash` 分派
 * （`#/preview3d` `#/cross_section` `#/volume` `#/ptrac` `#/source-demo`）；
 * ② 数据桥走 localStorage（同源共享，`window.open` 打开的是同源同 localStorage）。
 * 注意：必须**先写桥再开窗**（调用方顺序已如此），否则同源新窗口读不到数据。
 */
async function openChildWindow(cmd: string, hash: string): Promise<boolean> {
  const ok = await invoke(cmd);
  if (ok) return true;
  if (typeof window !== "undefined" && typeof window.open === "function") {
    try {
      const url = window.location.origin + window.location.pathname + "#/" + hash;
      window.open(url, "_blank");
      return true;
    } catch (e) {
      console.warn("window.open fallback failed:", hash, e);
    }
  }
  return false;
}

/** 主窗口：打开 3D 预览独立窗口（先写数据桥再开窗） */
export async function openPreview3D(data: {
  cells: any[];
  surfaces: string;
  trCards: string;
  /** 旧签名：带 deck 时从中取材料表（新调用方可直接用 materials） */
  deck?: DeckData;
  /** 材料表（{number, comment, density}）——独立窗口没有 deck，必须显式给 */
  materials?: { number: number; comment?: string; density?: string }[];
  /**
   * **预置网格**（STEP 方向预览，2026-10-08）：给了就让独立窗口直接渲染这份
   * {栅元号: base64 STL}，不再调 `/api/preview-3d`。
   * 于是方向预览与正常 3D 预览**开的是同一个独立窗口、同一套渲染**。
   */
  preloadedStl?: Record<string, string>;
  /** 预置网格版本号（变了就重新挂网格） */
  preloadToken?: string;
  /** 预置模式下的窗口标题 */
  titleOverride?: string;
}): Promise<boolean> {
  try {
    localStorage.setItem(KEY_PREVIEW3D, JSON.stringify({
      cells: data.cells,
      surfaces: data.surfaces,
      trCards: data.trCards,
      materials: data.materials
        ?? (data.deck ? (data.deck.materials || []).map((m) => ({ number: m.number, comment: m.comment, density: m.density })) : []),
      preloadedStl: data.preloadedStl,
      preloadToken: data.preloadToken,
      titleOverride: data.titleOverride,
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
  /** 材料页材料表（{number, comment}）：材料图例注释来源（与 3D 预览同口径） */
  materials?: { number: number; comment?: string }[];
  /** 后端 `/api/cross-section` 的 warnings（"只沿边界面接触，已剔除伪影"等）——界面必须解释这些 */
  warnings?: string[];
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
  cells: any[]; surfaces: string; trCards: string;
  materials: { number: number; comment?: string; density?: string }[];
  preloadedStl?: Record<string, string>;
  preloadToken?: string;
  titleOverride?: string;
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

/** 主窗口：打开「3D 结果」（体积可视化）独立窗口（先写数据桥再开窗）。桥写不进去则抛错。 */
export async function openVolume3D(data: Record<string, any>): Promise<boolean> {
  writeBridge(KEY_VOLUME3D, data, "3D 结果");
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

/**
 * 桥数据体积硬上限（字符数）。
 *
 * Chromium/WebView2 单 origin 的 localStorage 配额实测 ≈**5,000,000 字符**（10 MB UTF-16，
 * 2026-10-21 用随包固定版内核 Edg/154 实测：4,000,000 字符通过、5,500,000 抛 QuotaExceededError）。
 * 留 1M 余量做上限：超过就**不要写**，直接报错。
 *
 * 为什么必须有这道闸（2026-10-21 用户实测缺陷）：旧版「3D 径迹」桥把整份几何外壳 STL（base64，
 * 18 栅元 deck 实测 21,142,374 字符）塞进 localStorage ⇒ setItem 抛 QuotaExceededError ⇒
 * 被 `console.warn` 吞掉后照样 invoke 开窗 ⇒ 子窗口读不到桥，只显示
 * 「没有 3D 径迹数据（请从主窗口「输出」标签页解析 PTRAC 后打开）」——**症状误导成"你没解析"**。
 */
const BRIDGE_MAX_CHARS = 4_000_000;

/**
 * 写 localStorage 数据桥：**写不进去就抛错**，绝不静默开一个读不到数据的窗口。
 *
 * 调用方（openPtracWindow / openVolume3D 的使用者）都把异常转成界面提示（`errorHint`），
 * 让用户看到「数据过大 / 写入失败」，而不是一个空窗口。
 */
function writeBridge(key: string, data: unknown, what: string): void {
  let payload: string;
  try {
    payload = JSON.stringify(data);
  } catch (e) {
    throw new Error(`${what}数据序列化失败：${e instanceof Error ? e.message : String(e)}`);
  }
  if (payload.length > BRIDGE_MAX_CHARS) {
    const mb = payload.length / 1024 / 1024;
    throw new Error(
      `${what}数据过大（${mb.toFixed(1)} M 字符，超过浏览器 localStorage 配额上限 ${BRIDGE_MAX_CHARS / 1_000_000} M 字符），`
      + "无法传送到子窗口。请反馈开发者：桥里不应携带几何网格（STL），应由子窗口自行向后端获取。",
    );
  }
  try {
    localStorage.setItem(key, payload);
  } catch (e) {
    throw new Error(
      `${what}数据写入失败（localStorage 配额不足或存储被禁用）：${e instanceof Error ? e.message : String(e)}`,
    );
  }
}

/** 主窗口：打开「3D 径迹」（PTRAC）独立窗口（先写数据桥再开窗）。桥写不进去则抛错。 */
export async function openPtracWindow(data: Record<string, any>): Promise<boolean> {
  writeBridge(KEY_PTRAC, data, "3D 径迹");
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

/** 主窗口：打开「Tally 通量图」独立窗口（先写数据桥再开窗） */
export async function openTallyChart(data: Record<string, any>): Promise<boolean> {
  try {
    localStorage.setItem(KEY_TALLY_CHART, JSON.stringify(data));
  } catch (e) {
    console.warn("tally-chart bridge write failed", e);
  }
  return openChildWindow("open_tally_chart_window", "tally_chart");
}

/** 读取「Tally 通量图」桥数据（新窗口一次性消费） */
export function readTallyChartData(): Record<string, any> | null {
  try {
    const raw = localStorage.getItem(KEY_TALLY_CHART);
    if (!raw) return null;
    const j = JSON.parse(raw);
    localStorage.removeItem(KEY_TALLY_CHART);
    return j;
  } catch {
    return null;
  }
}

/** 主窗口：打开「演示源」独立窗口（先写数据桥再开窗）。particles 已由主窗口抽样。 */
export async function openSourceDemo(data: Record<string, any>): Promise<boolean> {
  try {
    localStorage.setItem(KEY_SOURCE_DEMO, JSON.stringify(data));
  } catch (e) {
    console.warn("source-demo bridge write failed", e);
  }
  return openChildWindow("open_source_demo_window", "source-demo");
}

/** 读取「演示源」桥数据（新窗口一次性消费） */
export function readSourceDemoData(): Record<string, any> | null {
  try {
    const raw = localStorage.getItem(KEY_SOURCE_DEMO);
    if (!raw) return null;
    const j = JSON.parse(raw);
    localStorage.removeItem(KEY_SOURCE_DEMO);
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
  materials?: { number: number; comment?: string }[];
  warnings?: string[];
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

/** 3D 窗口 → 主窗口：材料改号和密度回写（localStorage + storage 事件） */
export function emitMaterialChange(cellNum: string, newMat: string, density: string): void {
  try {
    localStorage.setItem(KEY_MAT_CHANGE, JSON.stringify({ cellNum, newMat, density, ts: Date.now() }));
  } catch (e) {
    console.warn("material-change emit failed", e);
  }
}

/** 主窗口：监听其它窗口发来的材料改号和密度事件 */
export function onMaterialChange(cb: (cellNum: string, newMat: string, density: string) => void): () => void {
  const handler = (e: StorageEvent) => {
    if (e.key !== KEY_MAT_CHANGE || !e.newValue) return;
    try {
      const j = JSON.parse(e.newValue);
      if (j && j.cellNum != null) cb(String(j.cellNum), String(j.newMat), String(j.density ?? ""));
    } catch {}
  };
  window.addEventListener("storage", handler);
  return () => window.removeEventListener("storage", handler);
}

/** 独立窗口：关闭自身（复用 Rust close_window 命令） */
export async function closeCurrentWindow(): Promise<boolean> {
  return invoke("close_window");
}

/** 独立 3D 预览窗口 → 主窗口：快捷建栅元生成结果回写（localStorage + storage 事件） */
export function emitQuickCellGenerate(result: any): void {
  try {
    localStorage.setItem(KEY_QUICK_CELL, JSON.stringify({ result, ts: Date.now() }));
  } catch (e) {
    console.warn("quick-cell emit failed", e);
  }
}

/** 主窗口：监听独立 3D 预览窗口发来的快捷建栅元结果 */
export function onQuickCellGenerate(cb: (result: any) => void): () => void {
  const handler = (e: StorageEvent) => {
    if (e.key !== KEY_QUICK_CELL || !e.newValue) return;
    try {
      const j = JSON.parse(e.newValue);
      if (j && j.result) cb(j.result);
    } catch {}
  };
  window.addEventListener("storage", handler);
  return () => window.removeEventListener("storage", handler);
}

/** 通知后端删除 STL 会话目录（关 3D 预览窗口 / 主界面清空时调用） */
export function clearStlSession(): void {
  fetch(apiUrl("/api/clear-stl"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  }).catch(() => {});
}
