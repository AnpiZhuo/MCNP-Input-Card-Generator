import { describe, it, expect } from "vitest";
import {
  emptyFmeshRow, cardTextToFmesh, fmeshToCardText, buildFmeshPayload,
  fmeshDefsToRows, FMESH_PLACEHOLDERS,
} from "../../src/volume/fmeshState";

/**
 * FMESH/TMESH 卡体 ↔ 结构化（契约 meshtal-visualization.md §5.3 / §4.7.1）
 * 镜像后端 fmesh_parser.py：结构化字段原文保留 + raw 兜底（round-trip 保真）。
 *
 * 2026-08-14 字段对齐 MCNP6（PM 指令）：eints→emints、t_ints→tmints；
 * 新增 axs/vec/tr；GEOM 连写单 token；卡体生成发 EMINTS/TMINTS，导入容错两种拼写。
 */
describe("FMESH 卡体 → 结构化 → 回放", () => {
  it("FMESHn:N 单卡往返（GEOM=XYZ 连写）", () => {
    const text = [
      "FMESH4:N GEOM=xyz ORIGIN=-100 -100 -150",
      "     IMESH=100 IINTS=10",
      "     JMESH=100 JINTS=10",
      "     KMESH=-50 KINTS=100",
    ].join("\n");
    const rows = cardTextToFmesh(text);
    expect(rows.length).toBe(1);
    expect(rows[0].kind).toBe("FMESH");
    expect(rows[0].number).toBe("4");
    expect(rows[0].particle).toBe("N");
    expect(rows[0].geom).toBe("XYZ"); // 归一化大写单 token
    expect(rows[0].origin).toBe("-100 -100 -150");
    expect(rows[0].imesh).toBe("100");
    expect(rows[0].iints).toBe("10");
    expect(rows[0].kmesh).toBe("-50");
    expect(rows[0].kints).toBe("100");

    const back = fmeshToCardText(rows);
    expect(back).toContain("FMESH4:N GEOM=XYZ ORIGIN=-100 -100 -150");
    expect(back).toContain("IMESH=100");
    expect(back).toContain("IINTS=10");
    // GEOM 连写：GEOM 值后不得跟裸值（GEOM=X Y Z 非法）；GEOM=XYZ ORIGIN=… 合法（ORIGIN=-100 含 =）
    expect(back).not.toMatch(/GEOM=\S+\s+(?![^\s]*=)[^\s]+/);
  });

  it("多区间 IMESH=a b IINTS=2 2 保留原文", () => {
    const text = "FMESH1:P GEOM=xyz ORIGIN=0 0 0\n     IMESH=10 20 IINTS=2 2\n     JMESH=10 JINTS=2\n     KMESH=10 KINTS=2";
    const rows = cardTextToFmesh(text);
    expect(rows[0].imesh).toBe("10 20");
    expect(rows[0].iints).toBe("2 2");
    expect(rows[0].jmesh).toBe("10");
    expect(rows[0].jints).toBe("2");
  });

  it("能量/时间边界 + 解析容错 EINTS/TINTS → emints/tmints，生成发 EMINTS/TMINTS", () => {
    const text = [
      "FMESH5:N GEOM=xyz ORIGIN=0 0 0",
      "     IMESH=10 IINTS=2",
      "     JMESH=10 IINTS=2",
      "     KMESH=10 KINTS=2",
      "     EMESH=1e-6 1 14 EINTS=2 2",
      "     TMESH=1 10 TINTS=2",
      "     MAT=3",
      "     OUT=f",
    ].join("\n");
    const rows = cardTextToFmesh(text);
    expect(rows[0].emesh).toBe("1e-6 1 14");
    expect(rows[0].emints).toBe("2 2"); // EINTS 容错 → emints
    expect(rows[0].tmesh).toBe("1 10");
    expect(rows[0].tmints).toBe("2"); // TINTS 容错 → tmints
    expect(rows[0].mat).toBe("3");
    expect(rows[0].out).toBe("f");

    // 生成必须发 EMINTS/TMINTS（非 EINTS/TINTS）
    const back = fmeshToCardText(rows);
    expect(back).toContain("EMINTS=2 2");
    expect(back).toContain("TMINTS=2");
    expect(back).not.toMatch(/\bEINTS=/);
    expect(back).not.toMatch(/\bTINTS=/);
  });

  it("EMINTS/TMINTS 新拼写导入同样映射", () => {
    const text = "FMESH6:N GEOM=CYL ORIGIN=0 0 0\n     IMESH=1 IINTS=4\n     JMESH=1 JINTS=4\n     KMESH=1 KINTS=8\n     EMESH=1 14 EMINTS=2\n     TMESH=1 10 TMINTS=2";
    const rows = cardTextToFmesh(text);
    expect(rows[0].emints).toBe("2");
    expect(rows[0].tmints).toBe("2");
  });
});

describe("新字段 AXS/VEC/TR/OUT round-trip", () => {
  it("圆柱卡体 → 解析 → 再生成 → 新字段保留", () => {
    const text = [
      "FMESH2:N GEOM=CYL ORIGIN=0 0 0",
      "     IMESH=2 IINTS=4",
      "     JMESH=2 JINTS=4",
      "     KMESH=1 KINTS=8",
      "     AXS=0 0 1",
      "     VEC=1 0 0",
      "     TR=3",
      "     OUT=CF",
    ].join("\n");
    const rows = cardTextToFmesh(text);
    expect(rows.length).toBe(1);
    expect(rows[0].geom).toBe("CYL");
    expect(rows[0].axs).toBe("0 0 1");
    expect(rows[0].vec).toBe("1 0 0");
    expect(rows[0].tr).toBe("3");
    expect(rows[0].out).toBe("CF");

    const back = fmeshToCardText(rows);
    expect(back).toContain("GEOM=CYL");
    expect(back).toContain("AXS=0 0 1");
    expect(back).toContain("VEC=1 0 0");
    expect(back).toContain("TR=3");
    expect(back).toContain("OUT=CF");

    // 二次解析字段不丢（round-trip 稳定）
    const rows2 = cardTextToFmesh(back);
    expect(rows2[0].axs).toBe("0 0 1");
    expect(rows2[0].vec).toBe("1 0 0");
    expect(rows2[0].tr).toBe("3");
    expect(rows2[0].out).toBe("CF");
    expect(rows2[0].geom).toBe("CYL");
  });
});

describe("TMESH RMESHn 吸收", () => {
  it("TMESHn 标题行 + RMESHn 子卡 → TMESH kind 行", () => {
    const text = [
      "TMESH4",
      "     RMESH4:N GEOM=xyz ORIGIN=0 0 0",
      "     IMESH=10 IINTS=2",
      "     JMESH=10 IINTS=2",
      "     KMESH=10 KINTS=2",
    ].join("\n");
    const rows = cardTextToFmesh(text);
    expect(rows.length).toBe(1);
    expect(rows[0].kind).toBe("TMESH");
    expect(rows[0].number).toBe("4");
    const back = fmeshToCardText(rows);
    expect(back).toContain("TMESH4");
    expect(back).toContain("RMESH4:N GEOM=XYZ ORIGIN=0 0 0");
  });
});

describe("raw 兜底（round-trip 保真）", () => {
  it("结构化字段为空 → 回放 raw 原文", () => {
    const raw = "FMESH9:N GEOM=xyz\n     ORIGIN=1 2 3";
    const rows = cardTextToFmesh(raw);
    // ORIGIN 有值 → 结构化回放；此处测结构化为空场景
    const empty = { ...emptyFmeshRow(), kind: "FMESH" as const, number: "7", raw: "FMESH7:P GEOM=CYL" };
    const back = fmeshToCardText([empty]);
    expect(back).toContain("FMESH7:P GEOM=CYL");
    expect(rows.length).toBeGreaterThanOrEqual(1);
  });
});

describe("buildFmeshPayload（→ tally.fmesh_defs，后端 key 对齐）", () => {
  it("number 数值化 + 字段名 emints/tmints/axs/vec/tr", () => {
    const rows = cardTextToFmesh("FMESH4:N GEOM=CYL ORIGIN=0 0 0\n     IMESH=1 IINTS=4\n     JMESH=1 JINTS=4\n     KMESH=1 KINTS=8\n     EMESH=1 14 EMINTS=2\n     TMESH=1 10 TMINTS=2\n     AXS=0 0 1\n     VEC=1 0 0\n     TR=5\n     OUT=COLSC");
    const payload = buildFmeshPayload(rows);
    expect(payload[0].number).toBe(4);
    expect(payload[0].emints).toBe("2");
    expect(payload[0].tmints).toBe("2");
    expect(payload[0].axs).toBe("0 0 1");
    expect(payload[0].vec).toBe("1 0 0");
    expect(payload[0].tr).toBe("5");
    expect(payload[0].out).toBe("COLSC");
    expect(payload[0].imesh).toBe("1");
    expect(payload[0].kind).toBe("FMESH");
  });

  it("空 → 空数组", () => {
    expect(buildFmeshPayload([])).toEqual([]);
  });
});

describe("fmeshDefsToRows（后端 parse → 前端 FmeshRow）", () => {
  it("新 key emints/tmints/axs/vec/tr 映射", () => {
    const rows = fmeshDefsToRows([
      { number: 4, kind: "FMESH", particle: "N", origin: "0 0 0", emints: "2", tmints: "2", axs: "0 0 1", vec: "1 0 0", tr: "3", geom: "CYL" },
    ]);
    expect(rows[0].number).toBe("4");
    expect(rows[0].emints).toBe("2");
    expect(rows[0].tmints).toBe("2");
    expect(rows[0].axs).toBe("0 0 1");
    expect(rows[0].vec).toBe("1 0 0");
    expect(rows[0].tr).toBe("3");
    expect(rows[0].geom).toBe("CYL");
  });

  it("向后兼容旧 key eints / t_ints", () => {
    const rows = fmeshDefsToRows([
      { number: 4, kind: "FMESH", particle: "N", origin: "0 0 0", eints: "2", t_ints: "2" },
    ]);
    expect(rows[0].emints).toBe("2");
    expect(rows[0].tmints).toBe("2");
    expect(rows[0].geom).toBe("XYZ");
  });

  it("TMESH 导入行数据保留（UI 隐藏入口但代码路径保留，round-trip 不丢）", () => {
    const rows = fmeshDefsToRows([
      { number: 3, kind: "TMESH", particle: "N", geom: "cyl", origin: "0 0 0", raw: "CMESH3:N GEOM=cyl ORIGIN=0 0 0" },
    ]);
    expect(rows[0].kind).toBe("TMESH");
    expect(rows[0].geom).toBe("CYL");
    expect(rows[0].number).toBe("3");
    expect(rows[0].origin).toBe("0 0 0");
    // kind 非 FMESH 不报错、不降级为 FMESH，序列化仍走 TMESH 结构化分支（TMESH 标题 + RMESH 子卡）
    const back = fmeshToCardText(rows);
    expect(back).toContain("TMESH3");
    expect(back).toContain("RMESH3:N GEOM=CYL ORIGIN=0 0 0");
  });
});

describe("FMESH_PLACEHOLDERS 幽灵文字（F5.1）", () => {
  it("关键字作用说明齐备", () => {
    expect(FMESH_PLACEHOLDERS.origin).toContain("网格原点坐标");
    expect(FMESH_PLACEHOLDERS.imesh).toContain("网格边界");
    expect(FMESH_PLACEHOLDERS.out).toContain("COL");
    expect(FMESH_PLACEHOLDERS.mat).toContain("材料");
    expect(FMESH_PLACEHOLDERS.geom).toContain("XYZ");
    expect(FMESH_PLACEHOLDERS.axs).toContain("圆柱");
    expect(FMESH_PLACEHOLDERS.vec).toContain("不平行");
    expect(FMESH_PLACEHOLDERS.tr).toContain("变换编号");
    expect(FMESH_PLACEHOLDERS.emints).toContain("区间数");
    expect(FMESH_PLACEHOLDERS.tmints).toContain("区间数");
  });
});

/**
 * 关键字等号可选解析（2026-08-15 PM 指令，镜像后端 fmesh_parser）。
 * MCNP 允许空格分隔 `imesh 51`；等号可选。收集循环边界判定改「已知关键字/卡族头」，
 * 未知 key 带 `=`（inc= 等）跳过，裸字母词当值收集（防 `geom xyz` 的 `xyz` 被误断）。
 */
describe("FMESH 关键字等号可选解析（imesh 51）", () => {
  it("空格分隔：裸关键字进入值收集，字段不丢", () => {
    const text = [
      "FMESH4:N GEOM xyz ORIGIN -100 -100 -150",
      "     IMESH 51 IINTS 10",
      "     JMESH 100 JINTS=10",
      "     KMESH -50 KINTS=100",
    ].join("\n");
    const rows = cardTextToFmesh(text);
    expect(rows.length).toBe(1);
    expect(rows[0].geom).toBe("XYZ"); // GEOM xyz 裸关键字 + 字母值
    expect(rows[0].origin).toBe("-100 -100 -150");
    expect(rows[0].imesh).toBe("51");
    expect(rows[0].iints).toBe("10");
    expect(rows[0].jmesh).toBe("100");
    expect(rows[0].jints).toBe("10");
    expect(rows[0].kmesh).toBe("-50");
    expect(rows[0].kints).toBe("100");
  });

  it("等号形式不受影响（回归）", () => {
    const text = "FMESH4:N GEOM=xyz ORIGIN=-100 -100 -150\n     IMESH=100 IINTS=10\n     JMESH=100 JINTS=10\n     KMESH=-50 KINTS=100";
    const rows = cardTextToFmesh(text);
    expect(rows[0].imesh).toBe("100");
    expect(rows[0].iints).toBe("10");
    expect(rows[0].geom).toBe("XYZ");
    expect(rows[0].origin).toBe("-100 -100 -150");
  });

  it("混排：等号与空格分隔混合，值不串位", () => {
    const text = [
      "FMESH1:P GEOM=CYL ORIGIN 0 0 0",
      "     IMESH 1 2 IINTS 2 2",
      "     JMESH=2 JINTS=4",
      "     KMESH 1 KINTS=8",
      "     AXS=0 0 1",
      "     VEC 1 0 0",
      "     TR=3",
    ].join("\n");
    const rows = cardTextToFmesh(text);
    expect(rows.length).toBe(1);
    expect(rows[0].geom).toBe("CYL");
    expect(rows[0].origin).toBe("0 0 0");
    expect(rows[0].imesh).toBe("1 2");
    expect(rows[0].iints).toBe("2 2");
    expect(rows[0].jmesh).toBe("2");
    expect(rows[0].jints).toBe("4");
    expect(rows[0].kmesh).toBe("1");
    expect(rows[0].kints).toBe("8");
    expect(rows[0].axs).toBe("0 0 1");
    expect(rows[0].vec).toBe("1 0 0");
    expect(rows[0].tr).toBe("3");
  });

  it("未知关键字 `inc=` 跳过不报错，不污染相邻字段", () => {
    const text = "FMESH2:N GEOM=xyz IMESH=10 IINTS=2 INC=1 JMESH=10 JINTS=2";
    const rows = cardTextToFmesh(text);
    expect(rows[0].imesh).toBe("10");
    expect(rows[0].iints).toBe("2");
    expect(rows[0].jmesh).toBe("10");
    expect(rows[0].jints).toBe("2");
  });

  it("关键字大小写不敏感（小写/混合大小写均识别）", () => {
    const text = [
      "fmesh4:n geom=xyz",
      "     imesh=10 iints=2",
      "     jmesh 20 jINTS=2",
      "     kmesh=30 KINTS=2",
    ].join("\n");
    const rows = cardTextToFmesh(text);
    expect(rows.length).toBe(1);
    expect(rows[0].kind).toBe("FMESH");
    expect(rows[0].geom).toBe("XYZ");
    expect(rows[0].imesh).toBe("10");
    expect(rows[0].iints).toBe("2");
    expect(rows[0].jmesh).toBe("20");
    expect(rows[0].jints).toBe("2");
    expect(rows[0].kmesh).toBe("30");
    expect(rows[0].kints).toBe("2");
  });

  it("`geom xyz` 的字母值 xyz 不被误判截断（含能量值字母词环境）", () => {
    const text = "FMESH3:N GEOM xyz ORIGIN=0 0 0\n     IMESH=10 IINTS=2\n     EMESH=1 14 EMINTS=2";
    const rows = cardTextToFmesh(text);
    expect(rows[0].geom).toBe("XYZ");
    expect(rows[0].origin).toBe("0 0 0");
    expect(rows[0].imesh).toBe("10");
    expect(rows[0].emesh).toBe("1 14");
    expect(rows[0].emints).toBe("2");
  });

  it("round-trip：空格分隔卡体 → 结构化 → 生成（= 形式）字段保留", () => {
    const text = [
      "FMESH4:N GEOM xyz ORIGIN -100 -100 -150",
      "     IMESH 51 100 IINTS 10 5",
      "     JMESH 100 JINTS 10",
      "     KMESH -50 KINTS 100",
      "     EMESH 1 14 EMINTS 2",
      "     MAT 3",
      "     OUT f",
    ].join("\n");
    const rows = cardTextToFmesh(text);
    const back = fmeshToCardText(rows);
    expect(back).toContain("FMESH4:N GEOM=XYZ ORIGIN=-100 -100 -150");
    expect(back).toContain("IMESH=51 100");
    expect(back).toContain("IINTS=10 5");
    expect(back).toContain("JMESH=100");
    expect(back).toContain("JINTS=10");
    expect(back).toContain("KMESH=-50");
    expect(back).toContain("KINTS=100");
    expect(back).toContain("EMESH=1 14");
    expect(back).toContain("EMINTS=2");
    expect(back).toContain("MAT=3");
    expect(back).toContain("OUT=f");
    // 二次解析字段不丢（round-trip 稳定）
    const rows2 = cardTextToFmesh(back);
    expect(rows2[0].imesh).toBe("51 100");
    expect(rows2[0].iints).toBe("10 5");
    expect(rows2[0].origin).toBe("-100 -100 -150");
    expect(rows2[0].geom).toBe("XYZ");
    expect(rows2[0].emesh).toBe("1 14");
    expect(rows2[0].emints).toBe("2");
    expect(rows2[0].mat).toBe("3");
    expect(rows2[0].out).toBe("f");
  });
});

/* *FMESH 能量沉积前缀（fn_prefix="*" → MeV/g） */
describe("*FMESH 能量沉积前缀（fn_prefix）", () => {
  it("`*fmesh14:N` → fn_prefix='*'，回放带 *，payload 带 fn_prefix", () => {
    const text = [
      "*fmesh14:N GEOM=XYZ ORIGIN=-100 -100 -150",
      "     IMESH=100 IINTS=10",
      "     JMESH=100 JINTS=10",
      "     KMESH=50 KINTS=100",
    ].join("\n");
    const rows = cardTextToFmesh(text);
    expect(rows.length).toBe(1);
    expect(rows[0].fn_prefix).toBe("*"); // 能量沉积（MeV/g）
    expect(rows[0].number).toBe("14");
    expect(rows[0].imesh).toBe("100");
    const back = fmeshToCardText(rows);
    expect(back).toContain("*FMESH14:N GEOM=XYZ ORIGIN=-100 -100 -150");
    const payload = buildFmeshPayload(rows);
    expect(payload[0].fn_prefix).toBe("*");
    // 后端 parse 带 fn_prefix → rows 保留
    const rows2 = fmeshDefsToRows([{ number: 14, kind: "FMESH", particle: "N", fn_prefix: "*", origin: "-100 -100 -150" }]);
    expect(rows2[0].fn_prefix).toBe("*");
  });

  it("普通 fmesh 无 * 前缀，回放不带 *", () => {
    const rows = cardTextToFmesh("FMESH4:N GEOM=XYZ ORIGIN=0 0 0\n     IMESH=10 IINTS=2");
    expect(rows[0].fn_prefix).toBe("");
    const back = fmeshToCardText(rows);
    expect(back).toContain("FMESH4:N GEOM=XYZ");
    expect(back).not.toContain("*FMESH");
  });
});
