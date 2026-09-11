import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, relative, sep } from "node:path";

/**
 * T4：Preview3D.tsx 死代码清理 ——
 * ① `dbgLog` state + `log()` 助手从未被调用/从未渲染（死代码）；
 * ② `console.log("[3D] initScene entry/start/done …")` 生产残留。
 * 修法：删死代码；调试日志移除（真实错误 console.error 保留）。
 *
 * ★加固（T3 FE-15）：原守卫**只读 Preview3D.tsx 单文件**，故"别处又加了调试 console.log / dbgLog"
 * 它管不到——回潮窗口敞开。现改为**扫描 `gui/src` 全树**：
 *   1) 全树禁止 `dbgLog` / `setDbgLog` 等调试态标识；
 *   2) 全树禁止调试用 `console.log(...)`，白名单只放行启动/进程日志（见 ALLOWED_CONSOLE_LOG）；
 *   3) Preview3D.tsx 的真实错误日志（console.error）仍保留（原断言不回退）。
 */
const HERE = dirname(fileURLToPath(import.meta.url)); // gui/test
const SRC_DIR = join(HERE, "../src");
const PREVIEW3D = readFileSync(join(SRC_DIR, "components/Preview3D.tsx"), "utf-8");

/** 递归收集 gui/src 下所有 .ts/.tsx */
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

/**
 * `console.log` 白名单：只允许**进程/启动生命周期**日志（非 UI 调试残留）。
 * 新增白名单必须在此写明为何不是调试日志。
 */
const ALLOWED_CONSOLE_LOG: Record<string, string> = {
  // Tauri sidecar（Python 后端 / MCP over HTTP）的启动与子进程 stdout 转发，
  // 属"把子进程日志显示出来"的运维日志，不是界面调试残留。
  "utils/backend.ts": "sidecar 启动/子进程 stdout 转发（运维日志）",
};

describe("T4：生产调试残留守卫（已扩展为全 gui/src 扫描）", () => {
  it("扫描范围有效：gui/src 下确实收集到源文件（防路径写错导致空扫假绿）", () => {
    expect(SOURCE_FILES.length).toBeGreaterThan(50);
    expect(SOURCE_FILES.some((f) => f.endsWith("Preview3D.tsx"))).toBe(true);
    expect(SOURCE_FILES.some((f) => f.endsWith("backend.ts"))).toBe(true);
  });

  it("全 gui/src 无 dbgLog / setDbgLog 调试态残留", () => {
    const hits: string[] = [];
    for (const f of SOURCE_FILES) {
      const src = readFileSync(f, "utf-8");
      if (src.includes("dbgLog") || src.includes("setDbgLog")) {
        hits.push(relative(SRC_DIR, f).split(sep).join("/"));
      }
    }
    expect(hits, `以下文件仍含 dbgLog 调试态：${hits.join(", ")}`).toEqual([]);
  });

  it("全 gui/src 无调试 console.log（白名单外一律红）", () => {
    const offenders: string[] = [];
    for (const f of SOURCE_FILES) {
      const rel = relative(SRC_DIR, f).split(sep).join("/");
      if (ALLOWED_CONSOLE_LOG[rel]) continue;
      const src = readFileSync(f, "utf-8");
      // 逐行判定并跳过注释行，避免注释/文档里提到 console.log 造成误报
      const line = src
        .split("\n")
        .find((l: string) => {
          const t = l.trim();
          if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) return false;
          return /\bconsole\.log\s*\(/.test(l);
        });
      if (line) offenders.push(rel);
    }
    expect(offenders, `以下文件含调试 console.log：${offenders.join(", ")}`).toEqual([]);
  });

  it("白名单本身不得过期（条目必须仍存在且确实含 console.log）", () => {
    for (const rel of Object.keys(ALLOWED_CONSOLE_LOG)) {
      const src = readFileSync(join(SRC_DIR, rel), "utf-8");
      expect(src.includes("console.log"), `${rel} 已无 console.log，请从白名单移除`).toBe(true);
    }
  });

  it("Preview3D.tsx 死代码已删（dbgLog state 与 log() 助手）", () => {
    expect(PREVIEW3D).not.toContain("dbgLog");
    expect(PREVIEW3D).not.toContain("setDbgLog");
    expect(PREVIEW3D).not.toContain("console.log('[3Ddbg]'");
  });

  it("Preview3D.tsx 生产 console.log 调试残留已移除（initScene entry/start/done）", () => {
    expect(PREVIEW3D).not.toContain("console.log(\"[3D] initScene");
    expect(PREVIEW3D).not.toContain("initScene entry");
    expect(PREVIEW3D).not.toContain("initScene start");
    expect(PREVIEW3D).not.toContain("initScene done");
  });

  it("真实错误日志保留（init error / STL load error / overlap check failed）", () => {
    expect(PREVIEW3D).toContain("console.error(\"[3D] init error:");
    expect(PREVIEW3D).toContain("console.error(\"STL load error for cell\"");
    expect(PREVIEW3D).toContain("console.error(\"overlap check failed\"");
  });
});
