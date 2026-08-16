import { describe, it, expect } from "vitest";
import {
  emptyPtracState, ptracFromDict, ptracToCardText, cardTextToPtrac,
  PTRAC_FILE_OPTIONS, PTRAC_WRITE_OPTIONS, PTRAC_TYPE_OPTIONS,
} from "../../src/ptrac/ptracState";

/**
 * 计数标签页 PTRAC 表单状态 round-trip（契约 ptrac-visualization.md §4.5）
 * deck.tally.ptrac ↔ `PTRAC FILE=ASC WRITE=ALL MAX=… TYPE=…` 卡体往返。
 */

describe("emptyPtracState 默认值（§4.5）", () => {
  it("FILE=ASC / WRITE=ALL / MAX 留空 / 其余空", () => {
    const s = emptyPtracState();
    expect(s.enabled).toBe(false);
    expect(s.file).toBe("ASC");
    expect(s.write).toBe("ALL");
    expect(s.max).toBe("");
    expect(s.types).toEqual([]);
    expect(s.nps).toBe("");
    expect(s.cell).toBe("");
    expect(s.surface).toBe("");
    expect(s.value).toBe("");
    expect(s.event).toBe("");
  });

  it("下拉/多选选项齐备", () => {
    expect(PTRAC_FILE_OPTIONS).toEqual(["ASC", "BIN"]);
    expect(PTRAC_WRITE_OPTIONS).toEqual(["ALL", "SOURCE", "EVENT"]);
    expect(PTRAC_TYPE_OPTIONS).toEqual(["N", "P", "E"]);
  });
});

describe("ptracToCardText（状态 → 卡体）", () => {
  it("enabled=false → 空串（不生成 PTRAC 卡）", () => {
    expect(ptracToCardText(emptyPtracState())).toBe("");
  });

  it("常用 7 项 + 高级 2 项全部回放", () => {
    const s = { ...emptyPtracState(), enabled: true, file: "ASC", write: "ALL", max: "500", types: ["N", "P"], nps: "100", cell: "1 2", surface: "5", value: "0.5", event: "TER" };
    const text = ptracToCardText(s);
    expect(text).toContain("PTRAC");
    expect(text).toContain("FILE=ASC");
    expect(text).toContain("WRITE=ALL");
    expect(text).toContain("MAX=500");
    expect(text).toContain("TYPE=N P");
    expect(text).toContain("NPS=100");
    expect(text).toContain("CELL=1 2");
    expect(text).toContain("SURFACE=5");
    expect(text).toContain("VALUE=0.5");
    expect(text).toContain("EVENT=TER");
  });

  it("TYPE 为空 → 不输出 TYPE 关键字", () => {
    const s = { ...emptyPtracState(), enabled: true };
    const text = ptracToCardText(s);
    expect(text).not.toContain("TYPE=");
    expect(text).toContain("FILE=ASC");
    expect(text).not.toContain("MAX="); // MAX 留空 → 不输出（MCNP 默认 100）
  });
});

describe("cardTextToPtrac（卡体 → 状态）", () => {
  it("KEY=value 形式解析全部字段", () => {
    const s = cardTextToPtrac("PTRAC FILE=ASC WRITE=ALL MAX=500 TYPE=N P NPS=100 CELL=1 2 SURFACE=5 VALUE=0.5 EVENT=TER");
    expect(s.enabled).toBe(true);
    expect(s.file).toBe("ASC");
    expect(s.write).toBe("ALL");
    expect(s.max).toBe("500");
    expect(s.types).toEqual(["N", "P"]);
    expect(s.nps).toBe("100");
    expect(s.cell).toBe("1 2");
    expect(s.surface).toBe("5");
    expect(s.value).toBe("0.5");
    expect(s.event).toBe("TER");
  });

  it("空格分隔（KEY value）形式同样解析", () => {
    const s = cardTextToPtrac("PTRAC FILE ASC WRITE ALL MAX -1 TYPE N CELL 3");
    expect(s.file).toBe("ASC");
    expect(s.write).toBe("ALL");
    expect(s.max).toBe("-1");
    expect(s.types).toEqual(["N"]);
    expect(s.cell).toBe("3");
  });

  it("大小写不敏感（file=asc → ASC）", () => {
    const s = cardTextToPtrac("ptrac file=asc write=all max=-1 type=n p");
    expect(s.file).toBe("ASC");
    expect(s.write).toBe("ALL");
    expect(s.types).toEqual(["N", "P"]);
  });

  it("空文本 → enabled=false", () => {
    expect(cardTextToPtrac("").enabled).toBe(false);
  });
});

describe("round-trip（状态 → 卡体 → 状态）", () => {
  it("全字段往返稳定", () => {
    const s = { ...emptyPtracState(), enabled: true, file: "BIN", write: "SOURCE", max: "10", types: ["N", "E"], nps: "5", cell: "1", surface: "2", value: "1e-3", event: "SRC COL" };
    const back = cardTextToPtrac(ptracToCardText(s));
    expect(back.enabled).toBe(true);
    expect(back.file).toBe("BIN");
    expect(back.write).toBe("SOURCE");
    expect(back.max).toBe("10");
    expect(back.types).toEqual(["N", "E"]);
    expect(back.nps).toBe("5");
    expect(back.cell).toBe("1");
    expect(back.surface).toBe("2");
    expect(back.value).toBe("1e-3");
    expect(back.event).toBe("SRC COL");
  });

  it("enabled=false 往返：空卡体 → disabled（不残留）", () => {
    const back = cardTextToPtrac(ptracToCardText(emptyPtracState()));
    expect(back.enabled).toBe(false);
  });
});

describe("ptracFromDict（后端 parse 返回 dict → 状态，缺 key 容忍）", () => {
  it("完整 dict 映射 + 归一化", () => {
    const s = ptracFromDict({ enabled: true, file: "asc", write: "all", max: 500, types: ["n", "p"], nps: 10, cell: 1, surface: 2, value: "0.5", event: "TER" });
    expect(s.enabled).toBe(true);
    expect(s.file).toBe("ASC");
    expect(s.write).toBe("ALL");
    expect(s.max).toBe("500");
    expect(s.types).toEqual(["N", "P"]);
    expect(s.nps).toBe("10");
    expect(s.cell).toBe("1");
  });

  it("undefined → 默认禁用状态", () => {
    const s = ptracFromDict(undefined);
    expect(s.enabled).toBe(false);
    expect(s.file).toBe("ASC");
  });

  it("types 过滤非法值（只保留 N/P/E）", () => {
    const s = ptracFromDict({ enabled: true, types: ["n", "x", "p"] });
    expect(s.types).toEqual(["N", "P"]);
  });
});
