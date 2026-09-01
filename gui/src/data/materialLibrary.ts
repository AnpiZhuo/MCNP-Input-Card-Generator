/**
 * 材料库深化 —— 前端数据模块（纯 TS，无 React 依赖，可独立单测）。
 *
 * 职责：
 * - LibraryEntry 类型（统一三态 origin：builtin / custom / override）
 * - 内置预设 → entry 转换；内置 ⊕ 文件合并（同名 key 用 override 覆盖，保序）
 * - 后端 /api/material-library* 封装（list/save/delete/import/export）
 * - 旧 localStorage 用户预设（mcnp_user_presets）一次性迁移到后端库
 *
 * 与后端 app/material_library.py 对应：库文件只存 custom+override（不含内置）。
 */
import type { MaterialRow } from "../utils/DeckContext";
import type { PresetItem } from "../components/MaterialPresets";
import { apiUrl } from "../utils/api";

export type LibraryOrigin = "builtin" | "custom" | "override";

export interface LibraryEntry {
  key: string;
  name: string;
  category: string;
  formula: string;
  desc: string;
  density: string;
  options: string;
  mtCard: string;
  origin: LibraryOrigin;
  rows: MaterialRow[];
}

/** 旧版 MaterialEditDialog 的用户预设 localStorage 键（历史存法，用于一次性迁移） */
export const LEGACY_UP_KEY = "mcnp_user_presets";

/** 内置预设 → LibraryEntry（origin="builtin"） */
export function builtinToEntries(categories: [string, PresetItem[]][]): LibraryEntry[] {
  const out: LibraryEntry[] = [];
  for (const [category, items] of categories) {
    for (const item of items) {
      out.push({
        key: item.key,
        name: item.name,
        category,
        formula: item.formula ?? "",
        desc: item.desc ?? "",
        density: item.density ?? "",
        options: item.options ?? "",
        mtCard: item.mtCard ?? "",
        origin: "builtin",
        rows: (item.rows ?? []).map(([zaid, fraction]) => ({ kind: "nuclide", zaid, fraction })),
      });
    }
  }
  return out;
}

/** 归一化：字段补默认、key 缺失时生成。 */
export function normalizeEntry(e: Partial<LibraryEntry>): LibraryEntry {
  const key = (e.key ?? "").trim() || genKey(e.name ?? "");
  return {
    key,
    name: e.name ?? "",
    category: e.category ?? "",
    formula: e.formula ?? "",
    desc: e.desc ?? "",
    density: e.density ?? "",
    options: e.options ?? "",
    mtCard: e.mtCard ?? "",
    origin: e.origin ?? "custom",
    rows: (e.rows ?? []).map((r) =>
      r.kind === "raw" ? { kind: "raw", text: r.text } : { kind: "nuclide", zaid: r.zaid, fraction: r.fraction }),
  };
}

function genKey(name: string): string {
  const slug = name.replace(/[^0-9A-Za-z]+/g, "_").replace(/^_|_$/g, "").toLowerCase();
  if (slug) return slug;
  let h = 0;
  for (let i = 0; i < name.length; i++) h = ((h << 5) - h + name.charCodeAt(i)) | 0;
  return "m_" + Math.abs(h).toString(16);
}

/**
 * 内置 ⊕ 文件 合并（保序）：
 * - override 同名替换内置位；custom 追加末尾；builtin 首见保留。
 * - 后端文件只含 custom/override；内置由调用方经 builtinToEntries 传入。
 */
export function mergeLibrary(builtins: LibraryEntry[], file: LibraryEntry[]): LibraryEntry[] {
  const order: LibraryEntry[] = [];
  const idx = new Map<string, number>();
  for (const raw of [...builtins, ...file]) {
    const e = normalizeEntry(raw);
    if (e.origin === "override") {
      const i = idx.get(e.key);
      if (i !== undefined) order[i] = e;
      else { idx.set(e.key, order.length); order.push(e); }
    } else if (!idx.has(e.key)) {
      idx.set(e.key, order.length);
      order.push(e);
    }
  }
  return order;
}

/** 把当前 deck 一个材料转为 LibraryEntry（origin 默认 custom） */
export function materialToEntry(
  pool: { key: string; origin: LibraryOrigin; material: { name: string; density: string; options: string; mtCard: string; nuclides: MaterialRow[] } } = {
    key: "", origin: "custom",
    material: { name: "", density: "", options: "", mtCard: "", nuclides: [] },
  },
): LibraryEntry {
  return normalizeEntry({
    key: pool.key || undefined,
    name: pool.material.name,
    category: "",
    formula: "",
    desc: "",
    density: pool.material.density,
    options: pool.material.options,
    mtCard: pool.material.mtCard,
    origin: pool.origin,
    rows: pool.material.nuclides,
  });
}

/* ── 后端封装 ── */
async function post(path: string, body: unknown): Promise<any> {
  const r = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  return r.json();
}

export interface LibraryListResult { materials: Record<string, LibraryEntry>; path: string }
export interface LibrarySaveResult { entry: LibraryEntry; warnings: string[] }
export interface LibraryDeleteResult { deleted: boolean; key: string }
export interface LibraryImportResult {
  result: { imported: string[]; skipped: string[]; overwritten: string[]; renamed: string[]; identical: string[]; dry_run: boolean };
  preview: { key: string; name: string; errors: string[]; xsdir: { type: string; zaid: string; available?: string[] }[] }[];
  dry_run: boolean;
  format: string;
}

export async function listLibrary(): Promise<LibraryListResult> {
  return post("/api/material-library", {});
}
export async function saveLibraryEntry(entry: LibraryEntry): Promise<LibrarySaveResult> {
  return post("/api/material-library/save", { entry });
}
export async function deleteLibraryEntry(key: string): Promise<LibraryDeleteResult> {
  return post("/api/material-library/delete", { key });
}
export async function importLibrary(payload: {
  format: "json" | "csv"; content: string; conflict: "skip" | "overwrite" | "rename";
  existingKeys: string[]; existingEntries: LibraryEntry[]; dryRun: boolean;
}): Promise<LibraryImportResult> {
  return post("/api/material-library/import", {
    format: payload.format, content: payload.content, conflict: payload.conflict,
    existing_keys: payload.existingKeys, existing_entries: payload.existingEntries, dry_run: payload.dryRun,
  });
}
export async function exportLibrary(format: "json" | "csv", entries: LibraryEntry[]): Promise<{ format: string; content: string }> {
  return post("/api/material-library/export", { format, entries });
}

/** 一次性迁移旧 localStorage 用户预设 → 后端库（成功后才清 localStorage）。 */
export async function migrateLegacyUserPresets(): Promise<number> {
  let legacy: PresetItem[] = [];
  try { legacy = JSON.parse(localStorage.getItem(LEGACY_UP_KEY) || "[]"); } catch { legacy = []; }
  if (!legacy.length) return 0;
  let done = 0;
  for (const it of legacy) {
    if (!it || !it.key) continue;
    const entry = normalizeEntry({
      key: it.key, name: it.name, category: "我的材料", formula: it.formula ?? "",
      desc: it.desc ?? "", density: it.density ?? "", options: it.options ?? "",
      mtCard: it.mtCard ?? "", origin: "custom", rows: (it.rows ?? []).map(([zaid, f]) => ({ kind: "nuclide", zaid, fraction: f })),
    });
    // eslint-disable-next-line no-await-in-loop
    await saveLibraryEntry(entry);
    done++;
  }
  localStorage.removeItem(LEGACY_UP_KEY);
  return done;
}
