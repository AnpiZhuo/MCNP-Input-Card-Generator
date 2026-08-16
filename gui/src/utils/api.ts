/**
 * api — 后端地址单一常量
 *
 * 全部前端 fetch 收敛到 127.0.0.1 直连 IPv4，规避 Chrome 对 `localhost`
 * 先试 ::1（IPv6）→ 连接拒绝 → Happy Eyeballs 回退 IPv4 的 ~300-500ms/请求
 * 惩罚（影响全部 25 端点）。后端绑定 0.0.0.0 不变，CORS 已 `*` 覆盖。
 */
export const API_BASE = "http://127.0.0.1:5001";

/** 拼后端接口路径：apiUrl("/api/preview-3d") => "http://127.0.0.1:5001/api/preview-3d" */
export const apiUrl = (p: string): string => API_BASE + p;

/* ── meshtal 网格计数（契约 meshtal-visualization.md §3，F4 hint 优先）── */

/** F4：错误响应优先显示 hint（友好中文），其次 message（原始异常） */
export function errorHint(j: any, fallback = "请求失败"): string {
  if (j && typeof j === "object") {
    if (j.hint) return String(j.hint);
    if (j.message) return String(j.message);
  }
  return fallback;
}

async function postJson<T = any>(path: string, body: unknown): Promise<T> {
  const r = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  return (await r.json()) as T;
}

export interface MeshtalDetectFile {
  path: string;
  name: string;
  size: number;
  mtime: string;
}

export interface MeshtalDetectResult {
  status?: string;
  files: MeshtalDetectFile[];
  outputDir?: string;
}

export interface MeshtalTallyMeta {
  number: number;
  particle: string;
  geom: string;
  unsupportedGeom: boolean;
  dims: { ni: number; nj: number; nk: number; energyBins: number; timeBins: number; nVoxels: number };
  binEdges: { x: number[]; y: number[]; z: number[]; energy: number[]; time: number[] };
  range: { min: number; max: number; count: number };
}

export interface MeshtalMatch {
  matched: boolean;
  overlapFraction: number;
  centerOffsetFrac: number;
  reason: string;
  message: string;
}

export interface MeshtalParseResult {
  status?: string;
  file?: { path: string; size: number; mtime: string };
  header?: { code: string; version: string; histories: number };
  grid_bounds?: { min: [number, number, number]; max: [number, number, number] };
  match?: MeshtalMatch | null;
  tallies: MeshtalTallyMeta[];
  warnings: string[];
}

export interface MeshtalTextureFrame {
  resolution: [number, number, number];
  worldBox: { min: [number, number, number]; max: [number, number, number] };
  binIndices: { energy: number; time: number };
  scalarRange: { min: number; max: number };
  dataBase64: string;
  bytes: number;
  nVoxels: number;
  downsampled: boolean;
  avgFactor: number[];
  particle: string;
  tallyNumber: number;
  scalarMin: number;
  scalarMax: number;
}

export interface MeshtalTextureResult {
  status?: string;
  frame?: MeshtalTextureFrame;
}

/** POST /api/meshtal-detect：扫描 output_dir 自动探测 meshtal* / MSHT*（A1.1） */
export async function meshtalDetect(outputDir: string): Promise<MeshtalDetectResult> {
  return postJson<MeshtalDetectResult>("/api/meshtal-detect", { outputDir });
}

/** POST /api/meshtal-parse：解析 meshtal 元数据 + deck↔meshtal 匹配（A1.2） */
export async function meshtalParse(path: string, modelData?: { surfaces?: string; cells?: any[]; tr_cards?: string }): Promise<MeshtalParseResult> {
  return postJson<MeshtalParseResult>("/api/meshtal-parse", {
    path,
    ...(modelData ? { surfaces: modelData.surfaces || "", cells: modelData.cells || [], tr_cards: modelData.tr_cards || "" } : {}),
  });
}

/** POST /api/meshtal-texture：取 (energy,time) 帧标量体积（Uint8 base64） */
export async function meshtalTexture(payload: {
  path: string;
  tallyNumber: number;
  energyBin?: number;
  timeBin?: number;
  resolution?: number;
}): Promise<MeshtalTextureResult> {
  return postJson<MeshtalTextureResult>("/api/meshtal-texture", payload);
}

/** POST /api/preview-3d：取几何外壳 STL（体积窗口复用，缓存命中快） */
export async function fetchPreview3dStl(cells: any[], surfaces: string, trCards: string): Promise<Record<string, string>> {
  const j: any = await postJson("/api/preview-3d", {
    surfaces: surfaces || "",
    cells,
    tr_cards: trCards || "",
  });
  return (j && j.stl_data) || {};
}

/* ── PTRAC 粒子径迹（契约 ptrac-visualization.md §3/§4）── */

/** 单条径迹：一个源粒子的历史（nps）+ 事件点序列 */
export interface PtracTrack {
  nps: number;
  /** 粒子类型 "n" | "p" | "e" | ""（L 表驱动提取，缺失为空串） */
  particle: string;
  /** 事件点 [x, y, z, type, energy]（energy 取不到记 0） */
  points: number[][];
}

/** /api/ptrac-parse 响应（status 由 _ok 包裹；错误响应带 hint） */
export interface PtracParseResult {
  status?: string;
  header?: { code: string; title: string };
  tracks: PtracTrack[];
  worldBox: { min: [number, number, number]; max: [number, number, number] };
  stats: {
    nps: number;
    events: number;
    points: number;
    truncated: boolean;
    particles: { n: number; p: number; e: number };
  };
  truncated: boolean;
}

/** POST /api/ptrac-detect：扫描 output_dir 自动探测 PTRAC 径迹文件（ptrac / ptrac.*） */
export async function ptracDetect(outputDir: string): Promise<MeshtalDetectResult> {
  return postJson<MeshtalDetectResult>("/api/ptrac-detect", { outputDir });
}

/** POST /api/ptrac-parse：解析 ASCII PTRAC 径迹文件（maxTracks/maxPoints 可选） */
export async function ptracParse(path: string, maxTracks?: number, maxPoints?: number): Promise<PtracParseResult> {
  const body: Record<string, unknown> = { path };
  if (maxTracks != null) body.maxTracks = maxTracks;
  if (maxPoints != null) body.maxPoints = maxPoints;
  return postJson<PtracParseResult>("/api/ptrac-parse", body);
}
