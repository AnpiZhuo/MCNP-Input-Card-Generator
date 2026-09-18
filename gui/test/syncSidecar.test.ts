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

  it("缺整个 _internal 目录（旧 sidecar 只剩 exe）→ missing 覆盖全树", () => {
    const src = mk({ "python.exe": "exe", "_internal/app/a.py": "x", "_internal/app/b.py": "y" });
    const dst = mk({ "python.exe": "exe" });
    const r = compareTrees(src, dst);
    expect(r.same).toBe(false);
    expect(r.missing.sort()).toEqual(["_internal/app/a.py", "_internal/app/b.py"]);
    expect(r.extra).toEqual([]);
  });
});

describe("sync-sidecar 的 --require-target 语义（构建后自检用）", () => {
  it("build:app 的收尾步骤必须带 --require-target（否则首次/失败构建会被静默放过）", async () => {
    const pkg = (await import("../package.json")) as { default: { scripts: Record<string, string> } };
    const chain = pkg.default.scripts["build:app"];
    expect(chain).toContain("tauri build");
    // 关键：同步必须出现在 tauri build **之后**（构建期 tauti 会用 binaries\ 覆盖 _internal
    // 但**不覆盖 python.exe**，实测构建后 python.exe 仍是旧版）
    expect(chain.indexOf("sync-sidecar.mjs --require-target")).toBeGreaterThan(chain.indexOf("tauri build"));
  });
});

describe("坑 6.7/6.8：sidecar 产物缺失时必须中止，绝不把旧副本铺出去", () => {
  it("PyInstaller 产物目录不存在 → 退出码 1 且提示先跑 PyInstaller", async () => {
    /**
     * 事故复盘（2026-09-18/19 实测，两次都打成"版本号新、后端旧"的包）：
     * ① `vite build` 清空 `gui/dist/`，而 PyInstaller 默认产物也在 `gui/dist/python/`
     *    ⇒ "先 PyInstaller → 再 build:app"会把新 sidecar 删掉；
     * ② `gui/build/mcnp_sidecar/` 的增量缓存会让 PyInstaller 复用**旧模块字节码**
     *    （改了 `inputcard_mcp/server.py`，产物 PYZ 里仍是 09-12 的旧代码）。
     * 两种情况都会让同步把 `binaries/` 里上一次的 python.exe 铺进 target/release，
     * 还报"✅ 已是最新"。所以"产物缺失即中止"这条必须一直守住。
     *
     * 产物落点现在是 `gui/dist_sidecar/python`（spec 里刻意与 vite 的 dist 分开）。
     */
    const { renameSync, existsSync } = await import("node:fs");
    const gui = join(__dirname, "..");
    const out = join(gui, "dist_sidecar", "python");
    const hidden = join(gui, "dist_sidecar", "python_guard_test");

    if (!existsSync(out)) {
      // 没跑过 PyInstaller 的环境：产物本来就不存在，守卫同样应当拦住
      const r = runSync();
      expect(r.code).toBe(1);
      expect(r.err).toContain("PyInstaller 产物不存在");
      return;
    }
    renameSync(out, hidden);
    try {
      const r = runSync();
      expect(r.code).toBe(1);
      expect(r.err).toContain("PyInstaller 产物不存在");
      expect(r.err).toContain("mcnp_sidecar.spec");
    } finally {
      renameSync(hidden, out);
    }
  });

  it("spec 不设 distpath（COLLECT 无该属性，赋值会被静默忽略）——落点只能靠命令行参数", async () => {
    const { readFileSync } = await import("node:fs");
    const spec = readFileSync(join(__dirname, "..", "mcnp_sidecar.spec"), "utf8");
    // 防止有人"修"成 spec 里赋值：那会静默失效，产物又回到 dist/ 被 vite 清掉
    expect(spec).not.toMatch(/^\s*coll\.distpath\s*=/m);
  });
});

/** 跑一次 sync-sidecar --check，收集退出码与输出 */
function runSync(): { code: number; err: string } {
  const { spawnSync } = require("node:child_process") as typeof import("node:child_process");
  const r = spawnSync(process.execPath, [join(__dirname, "..", "scripts", "sync-sidecar.mjs"), "--check"], {
    encoding: "utf8",
  });
  return { code: r.status ?? -1, err: `${r.stdout || ""}${r.stderr || ""}` };
}
