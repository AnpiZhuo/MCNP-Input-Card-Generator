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
    // 四种结论都要在脚本里出现：漏一种，用户就会拿到"看不懂"而不是"分流结论"
    for (const verdict of [
      "PKG-INCOMPLETE-OR-BLOCKED", "PKG-INCOMPLETE",
      "BACKEND-RUNNING", "PACKAGE-OK-BACKEND-NOT-UP",
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
