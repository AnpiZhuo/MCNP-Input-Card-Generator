/**
 * 回归锁（2026-10-20 用户口径）：参数扫描是「显式计算」——
 * 每个组合由后端开一个可见 MCNP 控制台窗口，**前端不得再有任何自动中止途径**
 * （关窗口 = 中止该组合，程序不 abort、不杀进程、不判超时）。
 *
 * 为什么扫源码而不是渲染组件：PreviewDialog 依赖 Monaco（jsdom 里起不来），
 * SweepDialog 是旧入口；两处都只需锁「没有 120s 定时 abort / 请求不带 signal」。
 * 与 `tests/unit/test_tech_debt.py` 的 AST 扫描是同一种"锁事实"思路。
 */
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const FILES = ["src/components/PreviewDialog.tsx", "src/components/SweepDialog.tsx"];

function readSrc(rel: string): string {
  return readFileSync(new URL(`../${rel}`, import.meta.url), "utf8");
}

describe("参数扫描不再自动中止（显式计算）", () => {
  it.each(FILES)("%s 不含 120s 超时 / AbortController / 取消中止文案", (rel) => {
    const src = readSrc(rel);
    expect(src).not.toContain("120000");
    expect(src).not.toContain("扫描超时（120s）");
    expect(src).not.toContain("扫描已取消");
    expect(src).not.toContain("AbortController");
  });

  it.each(FILES)("%s 的 /api/sweep-run 请求不带 signal", (rel) => {
    const src = readSrc(rel);
    const call = src.match(/\/api\/sweep-run[\s\S]{0,400}/);
    expect(call).toBeTruthy();
    expect(call![0]).not.toContain("signal");
  });
});
