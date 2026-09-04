import { afterEach, describe, expect, it, vi } from "vitest";
import {
  normalizeEntry, mergeLibrary, builtinToEntries, materialToEntry,
  migrateLegacyUserPresets, LEGACY_UP_KEY,
} from "../src/data/materialLibrary";
import type { LibraryEntry } from "../src/data/materialLibrary";

function entry(over: Partial<LibraryEntry>): LibraryEntry {
  return normalizeEntry({
    key: "", name: "x", category: "", formula: "", desc: "",
    density: "", options: "", mtCard: "", origin: "custom", rows: [], ...over,
  });
}

describe("normalizeEntry", () => {
  it("fills defaults and generates key when missing", () => {
    const e = normalizeEntry({ name: "Fe", rows: [] });
    expect(e.key).toBe("fe");
    expect(e.origin).toBe("custom");
    expect(e.options).toBe("");
    expect(e.mtCard).toBe("");
  });

  it("keeps raw rows as-is", () => {
    const e = normalizeEntry({
      name: "x", rows: [{ kind: "raw", text: "#ifdef ENDF7" }, { kind: "nuclide", zaid: "1001", fraction: "-1" }],
    });
    expect(e.rows[0]).toEqual({ kind: "raw", text: "#ifdef ENDF7" });
    expect(e.rows[1].kind).toBe("nuclide");
  });
});

describe("mergeLibrary", () => {
  it("override replaces builtin at same key, custom appended", () => {
    const builtins = [
      entry({ key: "water", name: "水", origin: "builtin" }),
      entry({ key: "air", name: "空气", origin: "builtin" }),
    ];
    const file = [
      entry({ key: "water", name: "我的水", origin: "override", density: "-1.1", mtCard: "lwtr.10t" }),
      entry({ key: "mymat", name: "自定义", origin: "custom" }),
    ];
    const merged = mergeLibrary(builtins, file);
    expect(merged.map((e) => e.key)).toEqual(["water", "air", "mymat"]);
    // override 的值生效
    expect(merged[0].name).toBe("我的水");
    expect(merged[0].mtCard).toBe("lwtr.10t");
    expect(merged[0].origin).toBe("override");
  });

  it("keeps builtin when no override", () => {
    const builtins = [entry({ key: "air", name: "空气", origin: "builtin" })];
    const merged = mergeLibrary(builtins, []);
    expect(merged[0].origin).toBe("builtin");
  });
});

describe("builtinToEntries", () => {
  it("converts and carries options/mtCard", () => {
    const cats: [string, any[]][] = [["分类", [
      { key: "k", name: "n", formula: "H2O:1", desc: "", density: "-1", options: "nlib=.66c", mtCard: "lwtr.10t", rows: [["1001", "-0.11"]] },
    ]]];
    const out = builtinToEntries(cats);
    expect(out[0].origin).toBe("builtin");
    expect(out[0].options).toBe("nlib=.66c");
    expect(out[0].mtCard).toBe("lwtr.10t");
    expect(out[0].rows[0]).toEqual({ kind: "nuclide", zaid: "1001", fraction: "-0.11" });
  });
});

describe("materialToEntry", () => {
  it("maps a deck material with origin", () => {
    const e = materialToEntry({
      key: "uo2", origin: "custom",
      material: { name: "UO2", density: "-10.96", options: "gas=1", mtCard: "", nuclides: [
        { kind: "nuclide", zaid: "92235", fraction: "-0.026" },
      ] },
    });
    expect(e.key).toBe("uo2");
    expect(e.name).toBe("UO2");
    expect(e.options).toBe("gas=1");
  });

  it("generates key when pool.key empty", () => {
    const e = materialToEntry({ key: "", origin: "custom", material: { name: "My Mat", density: "", options: "", mtCard: "", nuclides: [] } });
    expect(e.key).toBe("my_mat");
  });
});

// ── 迁移（原 JSON 优先：文件已存在的 key 跳过，只新增） ──────────────
describe("migrateLegacyUserPresets", () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  function makeFetch(existing: Record<string, unknown>, saved: string[]) {
    return vi.fn(async (url: unknown, opts?: any) => {
      const entry = opts?.body ? JSON.parse(opts.body).entry : null;
      if (String(url).includes("/api/material-library/save")) {
        saved.push(entry.key);
        return { json: async () => ({ entry, warnings: [] }) };
      }
      // GET /api/material-library（list）
      return { json: async () => ({ materials: existing, path: "" }) };
    });
  }

  function makeStorage(init?: Record<string, string>) {
    const store = new Map(Object.entries(init ?? {}));
    return {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => { store.set(k, String(v)); },
      removeItem: (k: string) => { store.delete(k); },
      _store: store,
    };
  }

  it("skips the legacy key that already exists in file (原 JSON 优先)", async () => {
    const existing = { water: normalizeEntry({ key: "water", name: "文件水", origin: "custom" }) };
    const saved: string[] = [];
    vi.stubGlobal("fetch", makeFetch(existing, saved));
    const storage = makeStorage({
      [LEGACY_UP_KEY]: JSON.stringify([
        { key: "water", name: "旧水", formula: "H2O:1", rows: [["1001", "-0.11"]] },
        { key: "mynew", name: "新材料", rows: [["92235", "-0.05"]] },
      ]),
    });
    vi.stubGlobal("localStorage", storage);

    const done = await migrateLegacyUserPresets();
    expect(done).toBe(1);
    expect(saved).toEqual(["mynew"]); // water 被跳过（保留文件原条目）
    expect(storage._store.has(LEGACY_UP_KEY)).toBe(false); // 迁移后清 localStorage
  });

  it("migrates all when the file is empty", async () => {
    const saved: string[] = [];
    vi.stubGlobal("fetch", makeFetch({}, saved));
    const storage = makeStorage({
      [LEGACY_UP_KEY]: JSON.stringify([
        { key: "a", name: "A", rows: [["1001", "-1"]] },
        { key: "b", name: "B", rows: [["1002", "-1"]] },
      ]),
    });
    vi.stubGlobal("localStorage", storage);

    const done = await migrateLegacyUserPresets();
    expect(done).toBe(2);
    expect(saved).toEqual(["a", "b"]);
  });

  it("does nothing when there are no legacy presets", async () => {
    const saved: string[] = [];
    vi.stubGlobal("fetch", makeFetch({}, saved));
    vi.stubGlobal("localStorage", makeStorage({}));

    const done = await migrateLegacyUserPresets();
    expect(done).toBe(0);
    expect(saved).toEqual([]);
  });
});
