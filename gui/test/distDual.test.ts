import { describe, it, expect } from "vitest";
import type { DistEntry } from "../src/utils/DeckContext";
import {
  rawToStructured, structuredToRawLines, linesToRaw,
  isRawMode, switchToRaw, switchToStructured, withStructuredEdit,
} from "../src/utils/distDual";

/* distDual 是 app/generator/distributions.py 的 TS 镜像——断言必须与后端单测
 * (tests/unit/test_distributions.py) 的黄金行为一致：
 *   无字母 SI → type ""（不再回填 L）；type "" 发射不带字母（MCNP 缺省 H）。 */

function mk(partial: Partial<DistEntry>): DistEntry {
  return {
    id: 1, paramRef: "ERG", auto: false,
    si: { type: "", values: ["0", "14"] },
    sp: { type: "D", values: ["0.5", "0.5"], fnCode: "", fnParams: [] },
    sb: null, ds: null,
    ...partial,
  } as DistEntry;
}

describe("rawToStructured（原文 → 结构化字段，镜像后端）", () => {
  it("无字母 SI → type ''（L-default 修复：绝不回填 L）", () => {
    const p = rawToStructured("SI1  0 14\nSP1  0.5 0.5", 1);
    expect(p.si).toEqual({ type: "", values: ["0", "14"] });
    expect(p.sp).toEqual({ type: "", values: ["0.5", "0.5"], fnCode: "", fnParams: [] });
  });

  it("显式字母 L/A/H 保持原样；大小写不敏感", () => {
    expect(rawToStructured("SI5  l  4 5", 5).si).toEqual({ type: "L", values: ["4", "5"] });
    expect(rawToStructured("SI2  A -5 5", 2).si).toEqual({ type: "A", values: ["-5", "5"] });
  });

  it("SP 内置函数码 / C / V 解析", () => {
    expect(rawToStructured("SP1  -3  0.965  2.29", 1).sp).toEqual(
      { type: "", values: [], fnCode: "-3", fnParams: ["0.965", "2.29"] });
    expect(rawToStructured("SP4  V", 4).sp).toEqual(
      { type: "V", values: [], fnCode: "", fnParams: [] });
  });

  it("SB/DS/SC 各分支 + 只认 id 匹配行", () => {
    const p = rawToStructured(
      "SB2  1 2\nDS2  S  ERG  3  4\nSC2  comment here\nSI9  9 9", 2);
    expect(p.sb).toEqual({ type: "D", values: ["1", "2"] });
    expect(p.ds).toEqual({ type: "S", param: "ERG", distributionIds: ["3", "4"] });
    expect(p.sc).toBe("comment here");
    expect(p.si).toBeNull(); // SI9 不属 id=2
  });

  it("$ 内联注释被剥（不进值）", () => {
    expect(rawToStructured("SI2  -5.5  5.5  $ uniform ext", 2).si)
      .toEqual({ type: "", values: ["-5.5", "5.5"] });
  });
});

describe("structuredToRawLines（表单 → 规范卡行，镜像后端）", () => {
  it("SI type='' → 不带字母；显式 L → 带字母", () => {
    const bare = structuredToRawLines(mk({ id: 2, si: { type: "", values: ["-5.5", "5.5"] } }));
    expect(bare.some(l => /^SI2/.test(l))).toBe(true);
    const l = bare.find(x => x.startsWith("SI2"))!;
    expect(l).not.toContain("L");
    const lettered = structuredToRawLines(mk({ si: { type: "L", values: ["14", "2"] } }));
    expect(lettered.some(l => l.startsWith("SI1  L"))).toBe(true);
  });

  it("SC 先于 SI 回放；SP D 裸值", () => {
    const lines = structuredToRawLines(mk({
      sc: "position comment", si: { type: "A", values: ["-5", "5"] },
    }));
    expect(lines[0]).toBe("SC1  position comment");
    expect(lines[1]).toBe("SI1  A  -5  5");
    expect(lines.some(l => /^SP1\s+0\.5\s+0\.5/.test(l))).toBe(true);
  });

  it("fnCode / C / V 分支", () => {
    const fn = structuredToRawLines(mk({ sp: { type: "", values: [], fnCode: "-3", fnParams: ["0.965", "2.29"] } }));
    expect(fn.some(l => /^SP1\s+-3\s+0\.965\s+2\.29/.test(l))).toBe(true);
    const cv = structuredToRawLines(mk({ sp: { type: "V", values: [], fnCode: "", fnParams: [] } }));
    expect(cv.some(l => /^SP1\s+V/.test(l))).toBe(true);
  });
});

describe("形态切换（输出与语义一致）", () => {
  it("structured → raw → structured 往返不丢字段、不引入 L", () => {
    const e = mk({ id: 2, si: { type: "", values: ["-5.5", "5.5"] }, sc: "note" });
    const raw = switchToRaw(e);
    expect(isRawMode(raw)).toBe(true);
    expect(raw.rawText).toContain("SI2");
    expect(raw.rawText).not.toContain("L");
    const back = switchToStructured(raw);
    expect(back.editMode).toBe("structured");
    expect(back.si).toEqual({ type: "", values: ["-5.5", "5.5"] });
    expect(back.sc).toBe("note");
  });

  it("raw → structured（解析字段权威）→ raw（规范重建）输出一致", () => {
    const e = mk({ editMode: "raw", rawText: "SI3  -5  5\nSP3  0  1", id: 3 });
    const form = switchToStructured(e);
    expect(form.si!.type).toBe("");
    const raw2 = switchToRaw(form);
    expect(raw2.rawText!.replace(/\s+/g, " ").trim()).toBe("SI3 -5 5 SP3 0 1");
  });

  it("结构化编辑自动回 structured 形态（raw 为导入直通专属）", () => {
    const rawE = mk({ editMode: "raw", rawText: "SI1  0 1" });
    const edited = withStructuredEdit(rawE, { si: { type: "L", values: ["0", "1"] } });
    expect(edited.editMode).toBe("structured");
    expect(edited.si!.type).toBe("L");
  });
});

describe("辅助", () => {
  it("linesToRaw 过滤空行", () => {
    expect(linesToRaw(["SI1  0 1", "", "SP1  0.5"])).toBe("SI1  0 1\nSP1  0.5");
  });
  it("isRawMode 缺省 = structured", () => {
    expect(isRawMode(mk({}))).toBe(false);
    expect(isRawMode(mk({ editMode: "raw" }))).toBe(true);
  });
});
