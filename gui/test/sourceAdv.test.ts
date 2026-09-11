import { describe, it, expect } from "vitest";
import type { DistEntry } from "../src/utils/DeckContext";
import {
  uiModeFromAdv,
  canonicalSourceMode,
  vocabForUi,
  parseDistributions,
  serializeDistributions,
  parseKsrc,
  serializeKsrc,
  readExtraToken,
  setExtraToken,
  migrateLegacySourceKeys,
} from "../src/utils/sourceAdv";

describe("uiModeFromAdv（adv.source_mode → 面板，受控派生）", () => {
  it("kcode / surface 原样；distribution/sdef/fixed/空 → sdef", () => {
    expect(uiModeFromAdv({ source_mode: "kcode" }, false)).toBe("kcode");
    expect(uiModeFromAdv({ source_mode: "surface" }, false)).toBe("surface");
    expect(uiModeFromAdv({ source_mode: "distribution" }, false)).toBe("sdef");
    expect(uiModeFromAdv({ source_mode: "sdef" }, false)).toBe("sdef");
    expect(uiModeFromAdv({ source_mode: "fixed" }, false)).toBe("sdef");
    expect(uiModeFromAdv({}, false)).toBe("sdef");
    expect(uiModeFromAdv(undefined, false)).toBe("sdef");
  });
  it("文本模式优先于 source_mode", () => {
    expect(uiModeFromAdv({ source_mode: "kcode" }, true)).toBe("text");
  });
});

describe("canonicalSourceMode / vocabForUi（规范词汇）", () => {
  it("kcode/surface 原样；其余一律 distribution", () => {
    expect(canonicalSourceMode({ source_mode: "kcode" })).toBe("kcode");
    expect(canonicalSourceMode({ source_mode: "surface" })).toBe("surface");
    expect(canonicalSourceMode({ source_mode: "distribution" })).toBe("distribution");
    expect(canonicalSourceMode({ source_mode: "sdef" })).toBe("distribution");
    expect(canonicalSourceMode({ source_mode: "fixed" })).toBe("distribution");
    expect(canonicalSourceMode({})).toBe("distribution");
  });
  it("面板 → 写回词汇", () => {
    expect(vocabForUi("kcode")).toBe("kcode");
    expect(vocabForUi("surface")).toBe("surface");
    expect(vocabForUi("sdef")).toBe("distribution");
  });
});

describe("分布 / ksrc JSON 序列化往返", () => {
  it("空分布 → ''（避免 '[]' truthy 误走分布生成）；非空可解析", () => {
    expect(serializeDistributions([])).toBe("");
    const ds: DistEntry[] = [{ id: 1, paramRef: "ERG", auto: true, si: { type: "L", values: ["14"] }, sp: { type: "D", values: [], fnCode: "", fnParams: [] }, sb: null, ds: null }];
    expect(parseDistributions(serializeDistributions(ds))).toEqual(ds);
    expect(parseDistributions("")).toEqual([]);
    expect(parseDistributions("not-json")).toEqual([]);
  });
  it("ksrc 坐标 number/string 统一成 string 往返", () => {
    expect(parseKsrc("")).toEqual([]);
    expect(parseKsrc("not-json")).toEqual([]);
    expect(parseKsrc('[{"x":1.26,"y":0,"z":"0"}]')).toEqual([{ x: "1.26", y: "0", z: "0" }]);
    const pts = [{ x: "1.26", y: "0", z: "0" }];
    expect(parseKsrc(serializeKsrc(pts))).toEqual(pts);
  });
});

describe("sdef_extra 记号辅助（sdef_eff 折叠位）", () => {
  it("读写/移除 EFF 记号且保留其它记号", () => {
    const extra = setExtraToken("", "EFF", "0.01");
    expect(extra).toBe("EFF=0.01");
    const extra2 = setExtraToken(extra + " CEL=1", "EFF", "0.02");
    expect(readExtraToken(extra2, "EFF")).toBe("0.02");
    expect(readExtraToken(extra2, "CEL")).toBe("1");
    expect(setExtraToken(extra2, "EFF", "")).toBe("CEL=1");
  });
});

describe("migrateLegacySourceKeys（旧顶层中间态 → adv，幂等且不覆盖权威值）", () => {
  it("sourceMode kcode + kcodeFields/ksrcPoints 折叠进 adv，删顶层键", () => {
    const out = migrateLegacySourceKeys({
      basic: { title: "t" },
      sources: [],
      sourceMode: "kcode",
      kcodeFields: { kcode_nsrc: "5000", kcode_ikz: "30", hsrc_enabled: "1", hsrc_text: "10 -1 1 10 -1 1 10 -1 1" },
      ksrcPoints: '[{"x":"1.26","y":"0","z":"0"}]',
      rawOverrides: {},
      textMode: {},
    });
    expect(out.adv.source_mode).toBe("kcode");
    expect(out.adv.kcode_nsrc).toBe("5000");
    expect(out.adv.hsrc_enabled).toBe(true); // 字符串 "1" → bool
    expect(out.adv.hsrc_text).toContain("10 -1 1");
    expect(out.adv.ksrc_points).toBe('[{"x":"1.26","y":"0","z":"0"}]');
    expect(out.sourceMode).toBeUndefined();
    expect(out.kcodeFields).toBeUndefined();
    expect(out.ksrcPoints).toBeUndefined();
  });

  it("'sdef' 词规范化成 'distribution'；sdefFields → adv.sdef_*", () => {
    const out = migrateLegacySourceKeys({
      sourceMode: "sdef",
      sdefFields: { sdef_erg: "14", sdef_pos_x: "0", sdef_pos_y: "0", sdef_pos_z: "0" },
    });
    expect(out.adv.source_mode).toBe("distribution");
    expect(out.adv.sdef_erg).toBe("14");
    expect(out.adv.sdef_pos_x).toBe("0");
    expect(out.sdefFields).toBeUndefined();
  });

  it("sdefFields 里有 sdef_eff → 折叠进 adv.sdef_extra 的 EFF 记号（后端无此字段）", () => {
    const out = migrateLegacySourceKeys({
      sourceMode: "distribution",
      sdefFields: { sdef_eff: "0.05" },
    });
    expect(out.adv.sdef_eff).toBeUndefined();
    expect(readExtraToken(out.adv.sdef_extra, "EFF")).toBe("0.05");
  });

  it("surface 模式只折叠 SSW/SSR（不折跨模式的 SDEF 残留）", () => {
    const out = migrateLegacySourceKeys({
      sourceMode: "surface",
      sswFields: { surf: "2", sym: "", pty: "", cel: "" },
      ssrFields: { surf: "3", mode: "old", cel: "", pty: "", col: "", wgt: "", tr: "", psc: "" },
      sdefFields: { sdef_erg: "14" }, // 跨模式残留：不折，避免污染
    });
    expect(out.adv.source_mode).toBe("surface");
    expect(out.adv.ssw_surf).toBe("2");
    expect(out.adv.ssr_surf).toBe("3");
    expect(out.adv.ssr_mode).toBe("old");
    expect(out.adv.sdef_erg).toBeUndefined();
    expect(out.sswFields).toBeUndefined();
    expect(out.ssrFields).toBeUndefined();
    expect(out.sdefFields).toBeUndefined();
  });

  it("SDEF 族（distribution）折叠 sdefRawText / distributions / sdef_eff 进 adv", () => {
    const out = migrateLegacySourceKeys({
      sourceMode: "distribution",
      sdefFields: { sdef_eff: "0.05", sdef_erg: "14" },
      distributions: [{ id: 1, paramRef: "ERG", auto: true, si: { type: "L", values: ["14"] }, sp: { type: "D", values: [], fnCode: "", fnParams: [] }, sb: null, ds: null }],
      sdefRawText: "SDEF ERG=D1\nSI1 L 14",
    });
    expect(out.adv.source_mode).toBe("distribution");
    expect(out.adv.sdef_erg).toBe("14");
    expect(out.adv.sdef_eff).toBeUndefined();
    expect(readExtraToken(out.adv.sdef_extra, "EFF")).toBe("0.05");
    expect(out.adv.sdef_distributions).toContain('"id":1');
    expect(out.sdefFields).toBeUndefined();
    expect(out.distributions).toBeUndefined();
    expect(out.sdefRawText).toBeUndefined();
  });

  it("TD-23 迁移：旧 sdefRawText 的 SI/SP 原文行 → adv.sdef_distributions（不再写死字段）", () => {
    const out = migrateLegacySourceKeys({
      sourceMode: "distribution",
      sdefRawText: "SDEF ERG=D1\nSI1 L 14\nSP1 1\nSI2 H 0 1",
    });
    // 死字段 sdef_raw_text 不得再出现（后端已退役该字段）
    expect(out.adv.sdef_raw_text).toBeUndefined();
    const dists = JSON.parse(out.adv.sdef_distributions);
    // 两条分布、按 id 升序（首次出现顺序），原文逐字保留
    expect(dists.map((d: any) => d.id)).toEqual([1, 2]);
    expect(dists[0].editMode).toBe("raw");
    expect(dists[0].rawText).toBe("SI1 L 14\nSP1 1");
    expect(dists[1].rawText).toBe("SI2 H 0 1");
    // 结构化字段同步派生；SDEF 卡本体行不进条目
    expect(dists[0].si).toEqual({ type: "L", values: ["14"] });
    expect(dists[1].si).toEqual({ type: "H", values: ["0", "1"] });
    expect(out.sdefRawText).toBeUndefined();
  });

  it("TD-23 迁移：已有 distributions 权威时，不覆盖 sdefRawText 的兜底解析", () => {
    const out = migrateLegacySourceKeys({
      sourceMode: "distribution",
      distributions: [{ id: 7, paramRef: "ERG", auto: true, si: { type: "L", values: ["14"] }, sp: null, sb: null, ds: null }],
      sdefRawText: "SI1 L 99",
    });
    const dists = JSON.parse(out.adv.sdef_distributions);
    expect(dists.map((d: any) => d.id)).toEqual([7]);
  });

  it("TD-23 迁移：sdefRawText 里没有分布卡行时保持空（不塞 '[]'）", () => {
    const out = migrateLegacySourceKeys({
      sourceMode: "distribution",
      sdefRawText: "SDEF ERG=14 POS=0 0 0",
    });
    expect(out.adv.sdef_distributions).toBeUndefined();
  });

  it("adv 已有权威值时不被中间态覆盖（如 parse 已产出的 adv）", () => {
    const out = migrateLegacySourceKeys({
      sourceMode: "surface",
      adv: { source_mode: "kcode", kcode_nsrc: "5000" },
      kcodeFields: { kcode_nsrc: "9999" },
      sdefFields: { sdef_erg: "14" },
    });
    expect(out.adv.source_mode).toBe("kcode");
    expect(out.adv.kcode_nsrc).toBe("5000");
    expect(out.adv.sdef_erg).toBeUndefined();
  });

  it("legacy fixed + sources 列表 → distribution（仍走 _generate_sdef(sources)，输出不变）", () => {
    const out = migrateLegacySourceKeys({
      sourceMode: "fixed",
      sources: [{ number: 1, erg: "14" }],
    });
    expect(out.adv.source_mode).toBe("distribution");
    expect(out.sources).toHaveLength(1);
  });
});
