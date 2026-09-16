/**
 * materialLegend — 图例注释来源边界（用户裁决，2026-09-16）。
 *
 * **语义锁**：材料显示接材料页，栅元信息接栅元定义 ——
 *   - 图例（● M1 - 注释）的注释**只能**来自 `MaterialData.comment`（材料页）；
 *   - 栅元列表的行尾注释来自 `cell.comment`（栅元定义），**不得**串到图例里。
 * 用户报的 bug 正是旧实现把栅元注释塞进图例注释槽
 * （`cellViews.find(cv => cv.mat === e.mat)?.comment`）⇒ 材料页注释永远读不到；
 * 且同一材料多栅元时图例会随机显示某一个栅元的注释（语义错 + 不确定）。
 *
 * 因此本测试两件事：① 材料注释解析行为；② 调用点**不得**再引入栅元注释（源码级锁）。
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { materialComment, materialLegendEntries } from "../src/utils/materialLegend";

describe("materialComment（材料页 → 图例）", () => {
  it("命中材料号 → 返回材料页注释", () => {
    expect(materialComment("1", [{ number: 1, comment: "UO2 燃料" }])).toBe("UO2 燃料");
    expect(materialComment(2, [{ number: "2", comment: "轻水" }])).toBe("轻水");
  });

  it("材料表缺该项 / 注释为空或纯空格 → undefined（图例只显示 M{n}）", () => {
    expect(materialComment("3", [{ number: 1, comment: "UO2 燃料" }])).toBeUndefined();
    expect(materialComment("1", [{ number: 1, comment: "" }])).toBeUndefined();
    expect(materialComment("1", [{ number: 1, comment: "   " }])).toBeUndefined();
    expect(materialComment("1", undefined)).toBeUndefined();
  });
});

describe("materialLegendEntries（按材料去重 + 只吃材料页）", () => {
  const mats = [
    { number: 1, comment: "UO2 燃料" },
    { number: 2, comment: "锆包壳" },
    { number: 3 },                       // 材料页没写注释
  ];

  it("去重后逐项取材料页注释；没写注释的材料项 comment 为空", () => {
    expect(materialLegendEntries(["1", "2", "1", "3"], mats)).toEqual([
      { mat: "1", comment: "UO2 燃料" },
      { mat: "2", comment: "锆包壳" },
      { mat: "3", comment: undefined },
    ]);
  });

  it("材料表为空（独立窗口未带材料表）→ 全部无注释，不抛错", () => {
    expect(materialLegendEntries(["0", "1"], undefined)).toEqual([
      { mat: "0", comment: undefined },
      { mat: "1", comment: undefined },
    ]);
  });

  it("接口不接受栅元注释：图例数据源只有 (材料号, 材料表) 两个入参", () => {
    expect(materialLegendEntries.length).toBe(2);
  });
});

describe("调用点源码锁：图例不得从栅元取注释", () => {
  const files = [
    resolve(__dirname, "../src/components/Preview3D.tsx"),
    resolve(__dirname, "../src/components/CrossSectionView.tsx"),
  ];

  /** 取 materialLegendEntries(...) 的**实参文本**（括号配平扫描），断言其中不含栅元注释源 */
  const callArgs = (src: string, name: string): string => {
    const i = src.indexOf(name + "(");
    if (i < 0) return "";
    let depth = 0;
    for (let k = i + name.length; k < src.length; k++) {
      const ch = src[k];
      if (ch === "(") depth++;
      else if (ch === ")") {
        depth--;
        if (depth === 0) return src.slice(i + name.length + 1, k);
      }
    }
    return "";
  };

  it("两处图例都走 materialLegendEntries，且实参里不出现栅元注释源", () => {
    for (const f of files) {
      const src = readFileSync(f, "utf8");
      const args = callArgs(src, "materialLegendEntries");
      expect(args, `${f} 的图例应使用 materialLegendEntries`).not.toBe("");
      expect(args, `${f} 图例实参不应含 cellViews 注释`).not.toContain("cv.mat");
      expect(args, `${f} 图例实参不应含 cd.comment`).not.toContain("cd.comment");
      expect(args, `${f} 图例实参不应含 c.comment`).not.toContain("c.comment");
      // 实参必须是"材料号序列 + 材料表"两段（材料表变量名：3D 用 matList，截面用 materials）
      expect(args).toMatch(/matList|materials/);
    }
  });

  it("栅元注释仍用于栅元列表（CellList），未被误删", () => {
    const src = readFileSync(files[1], "utf8");
    expect(src).toContain("comment: cd.comment");
  });
});
