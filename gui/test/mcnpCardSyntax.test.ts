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
  ghostForLine,
  languageId,
  surfaceTokenizer,
  trTokenizer,
} from "../src/components/mcnpCardSyntax";

// 类型要对准**实际导入的那个入口**（裁剪的 editor.api，不含 lsp/css/html/json/typescript）
let monaco: typeof import("monaco-editor/editor/editor.api.js");

/** 每行 → [{ 列, token 种类 }]，种类已去掉 monaco 追加的语言后缀。 */
function tokenize(text: string, mode: "surface" | "tr") {
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
  monaco.languages.setMonarchTokensProvider(languageId("surface"), surfaceTokenizer());
  monaco.languages.setMonarchTokensProvider(languageId("tr"), trTokenizer());
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
});

describe("TR 卡语法", () => {
  it("多行都拿得到 tr-id", () => {
    const lines = tokenize("TR1 0 0 0 30 60 90\n*TR2 1 2 3\nC 注释", "tr");
    expect(firstKind(lines[0])).toBe("tr-id");
    expect(firstKind(lines[1])).toBe("tr-id");
    expect(lines[2].map((t) => t.kind)).toContain("comment");
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
