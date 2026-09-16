/**
 * sidecar 同步/校验脚本的单测（打包手册 6.2 坑的守卫）。
 *
 * 用真实临时目录跑 `manifest` / `compareTrees`：证明它真的能看出
 * 「缺文件 / 多文件 / 大小不符」三种陈旧形态，而不是碰巧返回 same。
 */
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
// @ts-expect-error 打包脚本是 .mjs（无类型声明），这里只测其纯函数
import { compareTrees, manifest } from "../scripts/sync-sidecar.mjs";

const roots: string[] = [];
function mk(files: Record<string, string>): string {
  const root = mkdtempSync(join(tmpdir(), "sidecar-test-"));
  roots.push(root);
  for (const [rel, content] of Object.entries(files)) {
    const p = join(root, rel);
    mkdirSync(join(p, ".."), { recursive: true });
    writeFileSync(p, content);
  }
  return root;
}

afterAll(() => {
  for (const r of roots) rmSync(r, { recursive: true, force: true });
});

describe("sync-sidecar 的目录比较", () => {
  it("manifest 递归列出相对路径 + 字节数（正斜杠）", () => {
    const root = mk({ "a.txt": "123", "_internal/b/c.py": "12345" });
    expect(manifest(root)).toEqual([
      ["_internal/b/c.py", 5],
      ["a.txt", 3],
    ]);
  });

  it("两棵树一致 → same=true", () => {
    const files = { "python.exe": "exe-bytes", "_internal/app/x.py": "print(1)" };
    expect(compareTrees(mk(files), mk(files)).same).toBe(true);
  });

  it("旧 sidecar 缺新模块 → same=false 且 missing 指到具体文件", () => {
    const src = mk({ "python.exe": "exe", "_internal/app/new_module.py": "x" });
    const dst = mk({ "python.exe": "exe" });
    const r = compareTrees(src, dst);
    expect(r.same).toBe(false);
    expect(r.missing).toEqual(["_internal/app/new_module.py"]);
  });

  it("旧 sidecar 多出已删模块 → same=false 且 extra 非空", () => {
    const src = mk({ "python.exe": "exe" });
    const dst = mk({ "python.exe": "exe", "_internal/app/removed.py": "x" });
    const r = compareTrees(src, dst);
    expect(r.same).toBe(false);
    expect(r.extra).toEqual(["_internal/app/removed.py"]);
  });

  it("同名但内容/大小不同 → same=false 且 sizeDiff 给出两侧字节数", () => {
    const src = mk({ "python.exe": "NEW-EXE-SIDECAR" });
    const dst = mk({ "python.exe": "old" });
    const r = compareTrees(src, dst);
    expect(r.same).toBe(false);
    expect(r.sizeDiff).toHaveLength(1);
    expect(r.sizeDiff[0]).toContain("python.exe");
  });
});
