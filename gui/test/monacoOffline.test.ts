import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

/**
 * 断网可用守卫。
 *
 * 背景（2026-10-08）：本程序是**离线分发**形态（README：「不需要联网」），但有两处运行时外链
 * 一直躺在包里，直到断网才露出来：
 *   ① `McnpEditor` 走 `@monaco-editor/react`，而它背后的 `@monaco-editor/loader` 默认去 jsdelivr
 *      取 monaco 本体 ⇒ 断网时编辑器永久停在「加载中」；
 *   ② `index.html` 从 fonts.googleapis.com 拉 Inter 字体。
 * 这类东西的特点是**联网时完全看不出问题**，所以必须有尺子守着，不能靠人记得。
 *
 * 扫描范围：`gui/src` 全树 + `gui/index.html`。
 */
const HERE = dirname(fileURLToPath(import.meta.url)); // gui/test
const SRC_DIR = join(HERE, "../src");
const INDEX_HTML = readFileSync(join(HERE, "../index.html"), "utf-8");
const MONACO_LOCAL = readFileSync(join(SRC_DIR, "components/monacoLocal.ts"), "utf-8");
const MCNP_EDITOR = readFileSync(join(SRC_DIR, "components/McnpEditor.tsx"), "utf-8");

function collectSourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      out.push(...collectSourceFiles(full));
    } else if (name.endsWith(".ts") || name.endsWith(".tsx")) {
      out.push(full);
    }
  }
  return out;
}

const SOURCE_FILES = collectSourceFiles(SRC_DIR);

/** 字符串字面量里的绝对 URL（逐条抓，不做整行放行 —— 一行里可能同时有本机与远程）。 */
const QUOTED_URL = /["'`](https?:\/\/[^"'`\s>]*)/g;

/**
 * 两类**不会出网**的、长得像外链的东西。新增例外必须在此写明理由。
 */
const NOT_NETWORK: { name: string; test: RegExp; why: string }[] = [
  {
    name: "本机后端",
    test: /^https?:\/\/(127\.0\.0\.1|localhost)([:/]|$)/,
    why: "随包后端的本机接口，不出网",
  },
  {
    name: "XML/SVG 命名空间",
    test: /^https?:\/\/www\.w3\.org\//,
    why: "命名空间是标识符（如 SVG 的 2000/svg、xlink 的 1999/xlink），从不发起请求",
  },
];

/**
 * 白名单：**用户主动点击**的链接，不是运行时加载。逐条写明为什么安全。
 */
const ALLOWED: Record<string, string> = {
  "components/GeometryTab.tsx":
    "FreeCAD 官网下载页（<a href> 用户点击跳转，不加载任何资源；离线时点击无效而已）",
};

describe("断网可用：源码里不得出现运行时远程外链", () => {
  it("扫描范围有效（防路径写错导致空扫假绿）", () => {
    expect(SOURCE_FILES.length).toBeGreaterThan(50);
    expect(SOURCE_FILES.some((f) => f.endsWith("monacoLocal.ts"))).toBe(true);
    expect(SOURCE_FILES.some((f) => f.endsWith("McnpEditor.tsx"))).toBe(true);
  });

  it("gui/src 全树无运行时远程外链", () => {
    const offenders: string[] = [];
    for (const file of SOURCE_FILES) {
      const rel = file.slice(SRC_DIR.length + 1).split("\\").join("/");
      if (ALLOWED[rel]) continue;
      readFileSync(file, "utf-8")
        .split("\n")
        .forEach((line, i) => {
          for (const m of line.matchAll(QUOTED_URL)) {
            if (NOT_NETWORK.some((n) => n.test.test(m[1]))) continue;
            offenders.push(`${rel}:${i + 1}  ${m[1]}`);
          }
        });
    }
    expect(offenders).toEqual([]);
  });

  it("index.html 不含任何 https:// （字体外链等）", () => {
    expect(INDEX_HTML).not.toContain("https://");
    expect(INDEX_HTML).not.toContain("fonts.googleapis.com");
  });
});

describe("断网可用：Monaco 本地化接线必须还在", () => {
  it("monacoLocal 把随包的 monaco 交给 loader（切断 loader 的 CDN 默认值）", () => {
    expect(MONACO_LOCAL).toContain("loader.config(");
  });

  it("monacoLocal 自带 worker（否则 monaco 退化成主线程 worker）", () => {
    expect(MONACO_LOCAL).toContain("?worker");
    expect(MONACO_LOCAL).toContain("MonacoEnvironment");
  });

  it("McnpEditor 仍然副作用导入 monacoLocal（防止接线被静默删掉）", () => {
    expect(MCNP_EDITOR).toMatch(/import\s+"\.\/monacoLocal"/);
  });
});
