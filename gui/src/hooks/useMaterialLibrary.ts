/**
 * 材料库 React hook —— 加载合并库（内置 ⊕ 文件）、一次性迁移旧 localStorage、
 * 保存/删除后自动刷新，并让多个组件共享同一份缓存。
 *
 * 纯数据逻辑在 ../data/materialLibrary.ts，这里只做 React 状态接线。
 */
import { useEffect, useReducer, useState } from "react";
import {
  builtinToEntries, mergeLibrary, normalizeEntry,
  listLibrary, saveLibraryEntry, deleteLibraryEntry, migrateLegacyUserPresets,
} from "../data/materialLibrary";
import type { LibraryEntry } from "../data/materialLibrary";
import { PRESET_CATEGORIES } from "../components/MaterialPresets";

const builtins = builtinToEntries(PRESET_CATEGORIES);

// 模块级共享缓存：多个组件（编辑对话框 / 管理面板）复用，避免重复拉取。
let _cache: LibraryEntry[] | null = null;
const _listeners = new Set<() => void>();
function notify() { _listeners.forEach((l) => l()); }

async function load(force = false): Promise<LibraryEntry[]> {
  if (_cache && !force) return _cache;
  try {
    const res = await listLibrary();
    const file = Object.values(res.materials || {}).map(normalizeEntry);
    _cache = mergeLibrary(builtins, file);
  } catch {
    // 后端不可用：优雅降级为仅内置
    _cache = [...builtins];
  }
  notify();
  return _cache;
}

export interface MaterialLibraryApi {
  entries: LibraryEntry[];
  loaded: boolean;
  reload: () => Promise<LibraryEntry[]>;
  save: (entry: LibraryEntry) => Promise<void>;
  remove: (key: string) => Promise<void>;
}

export function useMaterialLibrary(): MaterialLibraryApi {
  const [, force] = useReducer((x: number) => x + 1, 0);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    _listeners.add(force);
    if (!_cache) {
      load()
        .then(() => migrateLegacyUserPresets().then(() => load(true)))
        .finally(() => setLoaded(true));
    } else {
      setLoaded(true);
    }
    return () => { _listeners.delete(force); };
  }, []);

  // 注意：不能 useMemo 缓存 entries —— entries 依赖模块级 _cache（不在 React deps 里），
  // save/remove 后 _cache 更新 + notify 触发重渲染时，须每次读最新 _cache 才能即时刷新。
  return {
    entries: _cache ?? builtins,
    loaded,
    reload: () => load(true),
    save: async (entry: LibraryEntry) => { await saveLibraryEntry(entry); await load(true); },
    remove: async (key: string) => { await deleteLibraryEntry(key); await load(true); },
  };
}
