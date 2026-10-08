/**
 * 生成前封闭性复核提示的回归测试（用户 2026-10-08：「生成时的警告…没实时更新」）。
 *
 * 两条根因：
 *   ① 生成路径先读 `deck.cellClosureReport`，有缓存就永不重算（缓存没有失效机制）；
 *   ② 只有发现坏栅元时才 setClosureGenerateWarn(...) ⇒ 几何变干净后旧警告留在屏上。
 * 契约：文案只由纯函数 `closureWarnText` 产出，**干净必须返回 null**（调用方无条件写入 ⇒ 必然清空）；
 * 生成路径不得再复用旧报告（源码级守卫，防回归）。
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { closureWarnText, CLOSURE_WARN_PENDING } from "../src/utils/cellClosure";

const HERE = dirname(fileURLToPath(import.meta.url));
const APP_TSX = readFileSync(join(HERE, "../src/App.tsx"), "utf-8");

describe("closureWarnText —— 生成前封闭性复核文案", () => {
  it("有坏栅元时逐条列出（外无限 / 空 / 未解析 / 体素）", () => {
    const txt = closureWarnText({
      "3": { status: "infinite" },
      "4": { status: "empty" },
      "9": { status: "unresolvable" },
      "12": { status: "voxel" },
    })!;
    expect(txt).toContain("栅元 3（外无限）");
    expect(txt).toContain("栅元 4（空/退化）");
    expect(txt).toContain("栅元 9（未解析）");
    expect(txt).toContain("栅元 12（体素网格，无法判定）");
    expect(txt).toContain("imp=0");   // 边界说明（graveyard 属正常）
  });

  it("★几何变干净 ⇒ 返回 null（调用方据此清空旧警告，不再挂一条陈旧提示）", () => {
    expect(closureWarnText({ "1": { status: "closed" }, "2": { status: "closed" } })).toBeNull();
    // 全封闭但含"外无限合法"边界：仍然要提示（用户可见），但它不是错误
    const withBoundary = closureWarnText({ "9": { status: "infinite" } })!;
    expect(withBoundary).toContain("栅元 9（外无限）");
    expect(closureWarnText(null)).toBeNull();
    expect(closureWarnText(undefined)).toBeNull();
    expect(closureWarnText({})).toBeNull();
  });

  it("未知状态不装作正常，也不当错误（不入列表）", () => {
    expect(closureWarnText({ "5": { status: "whatever" as any } })).toBeNull();
  });

  it("复核进行中的提示存在，且是进行时口径", () => {
    expect(CLOSURE_WARN_PENDING).toContain("复核");
  });
});

describe("App.tsx 生成路径的源码级守卫（防陈旧警告回归）", () => {
  // 取 runGenerateClosureCheck 的函数体：从声明处到**下一个顶层 const**（不依赖其它函数在文中的位置）
  const start = APP_TSX.indexOf("const runGenerateClosureCheck");
  const nextDecl = APP_TSX.slice(start + 1).indexOf("\n  const ");
  const fn = APP_TSX.slice(start, nextDecl >= 0 ? start + 1 + nextDecl : undefined);

  it("守卫自检：真的抽到了函数体（防空对空假绿）", () => {
    expect(start).toBeGreaterThan(0);
    expect(fn.length).toBeGreaterThan(200);
    expect(fn).toContain('apiUrl("/api/check-cell-closure")');
  });

  it("★不再复用 deck 里的旧报告（有缓存就永不重算的写法必须消失）", () => {
    expect(fn).not.toContain("cellClosureReport || null");
    expect(fn).not.toMatch(/if \(!report \|\| Object\.keys\(report\)/);
    expect(fn).toContain('apiUrl("/api/check-cell-closure")');   // 每次都真的去查
  });

  it("★文案一律经纯函数写入（干净 ⇒ null ⇒ 清空），且开头先给复核中", () => {
    expect(fn).toContain("setClosureGenerateWarn(closureWarnText(report))");
    expect(fn).toContain("setClosureGenerateWarn(CLOSURE_WARN_PENDING)");
    // 不得再出现"只在 bad.length 时设置"的老写法
    expect(fn).not.toContain("if (bad.length)");
  });

  it("后端不可用 ⇒ 清掉提示（不留来路不明的旧警告）", () => {
    expect(fn).toMatch(/catch \{[\s\S]*setClosureGenerateWarn\(null\)/);
  });
});

