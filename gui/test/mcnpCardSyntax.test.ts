// @vitest-environment jsdom
/**
 * 卡片语法（Monarch）与幽灵提示的回归门禁。
 *
 * 为什么必须有这个文件：Monarch 的状态是**跨行保持**的，语法写错只会表现为「某几行不着色」，
 * 而 Monaco 在测试环境里要跑起来得拉起一整套 standalone 服务 —— 所以过去这种错只能靠肉眼在界面上
 * 发现。2026-10-08 用户报「曲面卡只有第一行着色」就是这类：三状态语法没在行尾回 root，第 2 行起
 * 曲面号落到 `number`、注释行失效。这里用 `monaco.editor.tokenize()` 逐行断言，把它钉死。
 *
 * ⚠️ 这个文件会加载 monaco 本体，跑起来约 10–15 秒（首次 import 最贵）。**不要**为了"提速"把它换成
 * 手写的正则模拟 —— 那样测的就不是 Monaco 的真实行为了。用的是裁剪入口 editor.api.js（只要编辑器
 * API，不拉 84 个语言定义），已经是能跑 tokenize 的最小入口。
 */
import { beforeAll, describe, expect, it } from "vitest";
import {
  deckTokenizer,
  ghostForLine,
  languageId,
  surfaceTokenizer,
  surfaceCompletionAllowed,
  trTokenizer,
} from "../src/components/mcnpCardSyntax";

// 类型要对准**实际导入的那个入口**（裁剪的 editor.api，不含 lsp/css/html/json/typescript）
let monaco: typeof import("monaco-editor/editor/editor.api.js");

/** 每行 → [{ 列, token 种类 }]，种类已去掉 monaco 追加的语言后缀。 */
function tokenize(text: string, mode: "surface" | "tr" | "deck") {
  return monaco.editor
    .tokenize(text, languageId(mode))
    .map((line) => line.map((t) => ({ offset: t.offset, kind: t.type.split(".")[0] })));
}

const firstKind = (line: { offset: number; kind: string }[]) => line[0]?.kind ?? "";

beforeAll(async () => {
  // jsdom 没实现 matchMedia，monaco 的 StandaloneThemeService 在初始化时会直接调它。
  (window as unknown as { matchMedia: unknown }).matchMedia = (query: string) => ({
    matches: false, media: query, onchange: null,
    addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {},
    dispatchEvent: () => false,
  });
  monaco = await import("monaco-editor/editor/editor.api.js");
  monaco.languages.register({ id: languageId("surface") });
  monaco.languages.register({ id: languageId("tr") });
  monaco.languages.register({ id: languageId("deck") });
  monaco.languages.setMonarchTokensProvider(languageId("surface"), surfaceTokenizer());
  monaco.languages.setMonarchTokensProvider(languageId("tr"), trTokenizer());
  monaco.languages.setMonarchTokensProvider(languageId("deck"), deckTokenizer());
}, 120_000);

describe("曲面卡语法", () => {
  // 用户 2026-10-08 报的原始场景：只有第一行着色
  const DECK = [
    "1 3 -5 10 5.0",          // 带 TR 引用的第一行
    "2 PX -9   $ X垂面",      // ← 修复前这一行行首是 number（绿）
    "C 注释行",                // ← 修复前这一行完全不着色
    "3 SO 5.0",
    "900 RPP -1 1 -1 1 -1 1",
  ].join("\n");

  it("每一行的行首曲面号都是 surface-id（不是只有第一行）", () => {
    const lines = tokenize(DECK, "surface");
    expect(lines).toHaveLength(5);
    expect(firstKind(lines[0])).toBe("surface-id");
    expect(firstKind(lines[1])).toBe("surface-id");
    expect(firstKind(lines[3])).toBe("surface-id");
    expect(firstKind(lines[4])).toBe("surface-id");
  });

  it("注释行在任意位置都着成 comment", () => {
    const lines = tokenize(DECK, "surface");
    expect(lines[2].map((t) => t.kind)).toContain("comment");
    // 行内 $ 注释同样成立
    expect(tokenize("2 PX -9 $ X垂面", "surface").flat().map((t) => t.kind)).toContain("comment");
  });

  it("曲面号后紧跟的整数仍是 tr-reference（观感不退化）", () => {
    // 这一行是「曲面号 + 变换号 + 数字」的写法，本来就没有曲面类型助记符
    const kinds = tokenize(DECK, "surface")[0].map((t) => t.kind);
    expect(kinds).toContain("surface-id");
    expect(kinds).toContain("tr-reference");
  });

  it("曲面类型识别为 type", () => {
    expect(tokenize("3 SO 5.0", "surface").flat().map((t) => t.kind)).toContain("type");
    expect(tokenize("900 RPP -1 1 -1 1 -1 1", "surface").flat().map((t) => t.kind)).toContain("type");
  });

  it("宏体/曲面关键词不分大小写（本程序自己的自动宏体就是小写）", () => {
    // 2026-10-08 用户报「宏体未能根据指定的关键词进行颜色变化」。根因：Monarch 编译规则时只取
    // `re.source`、丢弃 RegExp 的 i 标志（标志只能由语言定义的 ignoreCase 控制），而 MCNP 卡片不区分
    // 大小写、且 快捷建栅元 / 格阵自动宏体写出的全是小写 ⇒ `1 rpp …` / `1 sph …` / `1 rcc …` 全不着色。
    // 这几行是 quickCell.ts / lattice.ts 实际生成的写法，逐字取自生成器。
    const generated = [
      "1 rpp -1 1 -1 1 -1 1", // quickCell.ts RPP 六面体
      "1 rcc 0 0 0 0 0 5 2",  // quickCell.ts RCC 圆柱
      "1 sph 0 0 0 5",        // quickCell.ts SPH 球
      "1 rhp 0 0 -5 0 0 10 1 0 0", // lattice.ts 六棱柱宏体
      "1 px -9",
    ];
    for (const line of generated) {
      expect(tokenize(line, "surface").flat().map((t) => t.kind), line).toContain("type");
    }
  });
});

describe("TR 卡语法", () => {
  it("多行都拿得到 tr-id", () => {
    const lines = tokenize("TR1 0 0 0 30 60 90\n*TR2 1 2 3\nC 注释", "tr");
    expect(firstKind(lines[0])).toBe("tr-id");
    expect(firstKind(lines[1])).toBe("tr-id");
    expect(lines[2].map((t) => t.kind)).toContain("comment");
  });

  it("小写 TR 也认（同样受 Monarch 丢弃 /i 标志影响）", () => {
    const lines = tokenize("tr1 0 0 0 30 60 90\n*tr2 1 2 3", "tr");
    expect(firstKind(lines[0])).toBe("tr-id");
    expect(firstKind(lines[1])).toBe("tr-id");
  });
});

describe("不变量：语法必须只有 root 一个状态", () => {
  // 这条比"扫源码里有没有 @xxx"直接：有子状态就会在 tokenize 结果里暴露成上面那些断言失败，
  // 而这里把根因（状态机）本身钉住。Monarch 的状态跨行保持 ⇒ 子状态一旦不在行尾回 root 就会污染后续行。
  it.each([
    ["surface", surfaceTokenizer],
    ["tr", trTokenizer],
  ])("%s", (_name, build) => {
    const tokenizer = (build() as { tokenizer: Record<string, unknown> }).tokenizer;
    expect(Object.keys(tokenizer)).toEqual(["root"]);
  });
});

describe("幽灵提示（ghostForLine）", () => {
  it("曲面卡：缺参数时列出还差哪些", () => {
    expect(ghostForLine("1 PX ", "surface")).toBe("D");
    expect(ghostForLine("3 S ", "surface")).toBe("x0 y0 z0 R");
    expect(ghostForLine("4 SO ", "surface")).toBe("R");
  });

  describe("曲面类型补全边界", () => {
    it("曲面类型尚未填写时允许提示", () => {
      expect(surfaceCompletionAllowed("1 ")).toBe(true);
      expect(surfaceCompletionAllowed("1 3 ")).toBe(true);
    });

    it("曲面类型填写后不再提示类型候选", () => {
      expect(surfaceCompletionAllowed("1 S ")).toBe(false);
      expect(surfaceCompletionAllowed("1 3 S 0 0 0 5 ")).toBe(false);
      expect(surfaceCompletionAllowed("1 3 C/X ")).toBe(false);
    });
  });

  it("参数齐了给中文说明", () => {
    expect(ghostForLine("1 PX -9", "surface")).toBe("$ X垂面");
  });

  it("注释行与空行不提示", () => {
    expect(ghostForLine("C 这是注释", "surface")).toBeNull();
    expect(ghostForLine("$ 行内注释", "surface")).toBeNull();
    expect(ghostForLine("   ", "surface")).toBeNull();
  });

  it("TR 卡：按已有数字个数列剩余参数", () => {
    expect(ghostForLine("TR1 0 0", "tr")).toBe("Tz B1 B2 B3 B4 B5 B6 B7 B8 B9");
    expect(ghostForLine("TR1 0 0 0 30 60 90 1 2 3 4 5 6 7", "tr")).toBeNull();
  });

  it("$ 之后的内容不参与计数", () => {
    expect(ghostForLine("1 PX -9 $ 已写完", "surface")).toBe("$ X垂面");
  });
});

// 整张输入卡（生成预览页的文字层，2026-10-11 起与曲面卡共用 McnpEditor）
describe("整张卡语法（deck）", () => {
  const DECK = [
    "Cf252 neutron-only BPE",
    "1 0 -210 imp:n=1 $ 栅元注释",
    "C 注释行",
    "100 px -50",
    "m1 6000 -0.000124",
    "nps 10000000",
  ].join("\n");

  it("逐行独立着色：每一行都按行首/数字/注释判定（不出现'只有第一行着色'）", () => {
    const lines = tokenize(DECK, "deck");
    expect(firstKind(lines[0])).not.toBe("number");        // 标题行不是数字
    expect(firstKind(lines[1])).toBe("surface-id");        // 栅元号
    expect(firstKind(lines[2])).toBe("comment");           // C 注释行
    expect(firstKind(lines[3])).toBe("surface-id");        // 曲面号
    // 数据卡（m1 / nps）：首词不是行首号 → 不着色；卡里的数字要着色
    expect(firstKind(lines[4])).not.toBe("surface-id");
    expect(lines[4].some((t) => t.kind === "number")).toBe(true);
    expect(firstKind(lines[5])).not.toBe("surface-id");
    expect(lines[5].some((t) => t.kind === "number")).toBe(true);
  });

  it("$ 注释着色、且不影响后面的行", () => {
    const lines = tokenize("1 0 -1 imp:n=1 $ 说明\n2 0 -2\n", "deck");
    expect(lines[0].some((t) => t.kind === "comment")).toBe(true);
    expect(firstKind(lines[1])).toBe("surface-id");        // 下一行照常着色
  });

  it("整张卡不提供幽灵提示与补全（卡型太多，猜不准就不猜）", () => {
    expect(ghostForLine("nps 1000", "deck")).toBeNull();
    expect(ghostForLine("1 PX ", "deck")).toBeNull();
  });
});
