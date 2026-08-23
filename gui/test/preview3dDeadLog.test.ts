import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

/**
 * T4：Preview3D.tsx 死代码清理——
 * ① `dbgLog` state + `log()` 助手从未被调用/从未渲染（死代码）；
 * ② `console.log("[3D] initScene entry/start/done …")` 生产残留。
 * 修法：删死代码；调试日志移除（真实错误 console.error 保留）。
 */
const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = readFileSync(join(HERE, "../src/components/Preview3D.tsx"), "utf-8");

describe("T4：Preview3D 死代码 / 生产 console.log 清理", () => {
  it("dbgLog state 与 log() 助手已删除（从未被调用/渲染）", () => {
    expect(SRC).not.toContain("dbgLog");
    expect(SRC).not.toContain("setDbgLog");
    expect(SRC).not.toContain("console.log('[3Ddbg]'");
  });

  it("生产 console.log 调试残留已移除（initScene entry/start/done）", () => {
    expect(SRC).not.toContain("console.log(\"[3D] initScene");
    expect(SRC).not.toContain("initScene entry");
    expect(SRC).not.toContain("initScene start");
    expect(SRC).not.toContain("initScene done");
  });

  it("真实错误日志保留（init error / STL load error / overlap check failed）", () => {
    expect(SRC).toContain("console.error(\"[3D] init error:");
    expect(SRC).toContain("console.error(\"STL load error for cell\"");
    expect(SRC).toContain("console.error(\"overlap check failed\"");
  });
});
