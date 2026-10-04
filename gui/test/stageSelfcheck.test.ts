/**
 * `自检.bat` 随包落地的闸门（stage-selftest）。
 *
 * ## 为什么需要这条闸门
 * 用户机器上"后端没拉起来 / `python.exe` 一闪就没"这类反馈，唯一的自助取证入口
 * 就是交付目录里的 `自检.bat`。它有三个**静默失效**的方式，都是人因、都只有发版后才发现：
 *   1. 文件被改名/删掉（仓库根没有它了）；
 *   2. 内容被改瘦（判据串没了 → 用户拿到的只有一段看不懂的输出，没有 `[RESULT]` 结论）；
 *   3. **没被铺进 `target/release`** ⇒ 第 7 步手工拷贝自然漏掉 ⇒ 交付目录里根本没有它
 *      （这正是"手工清单最容易漏新文件"的老毛病，与 6.2 sidecar 时效坑同源）。
 *
 * 所以这里把三件事都钉住：源存在且判据齐全、拷贝函数行为正确、**两条构建链路都挂了这一步**。
 */
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, describe, expect, it } from "vitest";
// @ts-expect-error 打包脚本是 .mjs（无类型声明），这里只测其导出
import { REQUIRED_MARKERS, SELFTEST_DST_DIR, SELFTEST_NAME, SELFTEST_SRC, assertSourceOk, isStaged } from "../scripts/stage-selftest.mjs";

const GUI = resolve(fileURLToPath(new URL(".", import.meta.url)), "..");
const REPO = resolve(GUI, "..");
const tmps: string[] = [];

function mkTmp(): string {
  const d = mkdtempSync(join(tmpdir(), "stage-selftest-"));
  tmps.push(d);
  return d;
}

afterAll(() => {
  for (const d of tmps) rmSync(d, { recursive: true, force: true });
});

describe("自检.bat 源文件（仓库根）", () => {
  it("存在、且判据齐全（判据串是它对用户的契约）", () => {
    expect(existsSync(SELFTEST_SRC)).toBe(true);
    const text = assertSourceOk(); // 缺判据会抛
    for (const m of REQUIRED_MARKERS) expect(text).toContain(m);
  });

  it("给的是可执行的结论标记，而不是只有一堆输出", () => {
    const text = readFileSync(SELFTEST_SRC, "utf8");
    // 五种结论都要在脚本里出现：漏一种，用户就会拿到"看不懂"而不是"分流结论"
    for (const verdict of [
      "PKG-INCOMPLETE-OR-BLOCKED", "PKG-INCOMPLETE",
      "BACKEND-RUNNING", "PACKAGE-OK-BACKEND-NOT-UP",
      "WEBVIEW2-MISSING",           // 2026-09-29：没有 Edge/WebView2 的机器双击打不开
    ]) {
      expect(text).toContain(verdict);
    }
  });

  it("命令行为 CRLF 且无 BOM（cmd 对首行 BOM / 裸 LF 会出错）", () => {
    const buf = readFileSync(SELFTEST_SRC);
    expect(buf[0]).not.toBe(0xef);                      // 无 UTF-8 BOM
    expect(buf.includes(Buffer.from("\r\n"))).toBe(true); // 有 CRLF
    const lf = buf.toString("latin1").match(/(?<!\r)\n/g) || [];
    expect(lf.length).toBe(0);                          // 没有裸 LF
  });
});

describe("assertSourceOk 的闸门语义", () => {
  it("缺判据 ⇒ 抛错（不能静默放过一个被改瘦的脚本）", () => {
    const p = join(mkTmp(), "自检.bat");
    writeFileSync(p, "@echo off\r\necho hello\r\n");
    expect(() => assertSourceOk(p)).toThrow(/关键判据|缺失/);
  });

  it("源不存在 ⇒ 抛错（并提示它必须留在仓库根）", () => {
    expect(() => assertSourceOk(join(mkTmp(), "nope.bat"))).toThrow(/缺失/);
  });
});

describe("isStaged（铺进 target/release 的判定）", () => {
  it("目标缺失 / 大小不同 / 一致 三种形态都判得对", () => {
    const src = join(mkTmp(), "自检.bat");
    writeFileSync(src, "12345");
    const dstDir = mkTmp();

    expect(isStaged(src, dstDir)).toBe(false);           // 还没铺
    writeFileSync(join(dstDir, SELFTEST_NAME), "12345");
    expect(isStaged(src, dstDir)).toBe(true);            // 一致
    writeFileSync(join(dstDir, SELFTEST_NAME), "1234");
    expect(isStaged(src, dstDir)).toBe(false);           // 陈旧（大小不符）
  });

  it("铺设目标就是 exe 所在目录（target/release）", () => {
    // 改到别处 = 交付目录里没有它 = 这一整套又白做
    expect(SELFTEST_DST_DIR.replace(/\\/g, "/")).toMatch(/src-tauri\/target\/release$/);
  });
});

describe("两条构建链路都必须挂上这一步", () => {
  it("build:release 串了 stage-selftest，且**先写后查**", () => {
    const text = readFileSync(join(GUI, "scripts", "build-release.mjs"), "utf8");
    expect(text).toContain("stage-selftest.mjs");
    // 顺序铁律：--check 在**写入之后**。反了的话干净/首次构建上 --check 必报"缺失"
    // 并 exit 1 —— 首次打包时 target/release 里还没有 自检.bat，整条链路会被自己中断。
    const write = text.indexOf('["scripts/stage-selftest.mjs"]');
    const check = text.indexOf('["scripts/stage-selftest.mjs", "--check"]');
    expect(write).toBeGreaterThan(-1);
    expect(check).toBeGreaterThan(-1);
    expect(check).toBeGreaterThan(write);
  });

  it("★build:release 必须先生产 sidecar，再 tauri build（2026-09-26 顺序自噬修复的回归锁）", () => {
    /**
     * 事故（2026-09-26 打 v1.7.7 实测）：旧版把 `vite build + tauri build` 排在 PyInstaller 之前，
     * 而 `tauri.conf.json` 的 `beforeBuildCommand` = `npm run build && npm run sync-sidecar`，
     * 后者见 `dist_sidecar/python` 不存在就**按设计 exit 1** ⇒ 干净工作区上整条 `build-release` 自我中断：
     *     [sync-sidecar] ❌ PyInstaller 产物不存在 … 已中止
     *     Error beforeBuildCommand `npm run build && npm run sync-sidecar` failed with exit code 1
     * 修法是**把 sidecar 生产前置**。本用例锁住四条顺序铁律里与"自我中断/后端旧"直接相关的三条，
     * 免得日后有人"优化顺序"又把它改回去（第一条铁律：stage-selftest 先写后查，见上一个用例）。
     */
    const text = readFileSync(join(GUI, "scripts", "build-release.mjs"), "utf8");
    const pyi = text.indexOf('"-m", "PyInstaller"');
    const bins = text.indexOf("cpSync(builtExe");
    const vite = text.indexOf('["vite", "build"]');
    const tauri = text.indexOf('["tauri", "build"]');
    const postCheck = text.indexOf('["scripts/sync-sidecar.mjs", "--check", "--require-target"]');
    for (const [idx, name] of [[pyi, "PyInstaller"], [bins, "binaries 覆盖"], [vite, "vite build"],
                               [tauri, "tauri build"], [postCheck, "--require-target"]] as const) {
      expect(idx, `build-release.mjs 里找不到 ${name}`).toBeGreaterThan(-1);
    }
    // ① sidecar 必须先于 tauri build（beforeBuildCommand 里的 sync-sidecar 在等 dist_sidecar/）
    expect(pyi).toBeLessThan(tauri);
    // ② binaries 覆盖必须先于 tauri build（tauri 编译期拿它铺 _internal）
    expect(bins).toBeLessThan(tauri);
    // ③ 收尾严格自检必须在 tauri build 之后（tauri 只刷新 _internal、不刷新 python.exe）
    expect(postCheck).toBeGreaterThan(tauri);
  });

  it("build:app 串了 stage-selftest，且**排在 tauri build 之后**", () => {
    const pkg = JSON.parse(readFileSync(join(GUI, "package.json"), "utf8"));
    const chain: string = pkg.scripts["build:app"];
    expect(chain).toContain("stage-selftest.mjs");
    // 顺序铁律：tauri build 之前 target/release 还没刷新（甚至不存在），
    // 先铺会被随后的构建覆盖/落空 —— 与 sync-sidecar 收尾自检同理。
    expect(chain.indexOf("stage-selftest.mjs")).toBeGreaterThan(chain.indexOf("tauri build"));
  });
});

describe("打包手册第 7 步（手工拷贝清单）", () => {
  it("清单里点名了 自检.bat（否则手拷必漏）", () => {
    const doc = readFileSync(
      join(REPO, "docs", "手动打包方法.md"), "utf8");
    const step7 = doc.slice(doc.indexOf("## 7. 部署到交付目录"));
    expect(step7).toContain(SELFTEST_NAME);
  });
});
