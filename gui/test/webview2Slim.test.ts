/**
 * `slim-webview2.mjs`（随包 WebView2 运行时的裁剪）门禁。
 *
 * ## 为什么必须有这条闸门
 * 这份运行时是"没有 Edge 的机器能不能打开界面"的唯一依赖，而裁剪是**删文件**——
 * 删错一个（比如 `ffmpeg.dll` 是 `msedge.dll` 的静态导入）的后果不是"少个功能"，
 * 而是**用户双击没反应**，且**只在他的机器上才暴露**（开发机通常有系统 WebView2 兜底）。
 * 所以这里把三件事钉死：
 *   1. 规则表**不碰**核心件（REQUIRED_CORE ∌ 任何规则命中项）——纯不变量，比逐条枚举更硬；
 *   2. `stageWebView2` 真的按规划落盘，且**缺核心件时抛错**（不是静默铺一份残缺运行时）；
 *   3. 两条构建链路都挂了这一步，且**在 `tauri build` 之后**（目录是它建的）。
 */
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, describe, expect, it } from "vitest";
// @ts-expect-error 打包脚本是 .mjs（无类型声明），这里只测其导出
import { DEFAULT_PROFILE, KEEP_LOCALES, MIN_EXPECTED_SAVING_BYTES, REQUIRED_CORE, SLIM_PROFILES, applyAppContainerAcl, assertRequiredCore, matchRule, planSlim, stageWebView2 } from "../scripts/slim-webview2.mjs";

const GUI = resolve(fileURLToPath(new URL(".", import.meta.url)), "..");
const tmps: string[] = [];

function mkTmp(): string {
  const d = mkdtempSync(join(tmpdir(), "slim-wv2-"));
  tmps.push(d);
  return d;
}

afterAll(() => {
  for (const d of tmps) rmSync(d, { recursive: true, force: true });
});

function e(rel: string, size = 1024) {
  return { rel, isDir: false, size };
}

describe("裁剪规则：只删与本程序无关的（黑名单语义）", () => {
  it("语言包只留 zh-CN + en-US，其余 166 个删", () => {
    expect(matchRule("Locales/en-US.pak")).toBeNull();
    expect(matchRule("Locales/zh-CN.pak")).toBeNull();
    for (const drop of ["Locales/ja.pak", "Locales/ml.pak", "Locales/bn-IN.pak"]) {
      expect(matchRule(drop)?.id).toBe("locales");
    }
    expect(KEEP_LOCALES).toEqual(["en-US.pak", "zh-CN.pak"]);
  });

  it("点名了那些大头（每条对应一份实测）：Widevine / PDF / Copilot / ONNX / 遥测 / IE 模式 / 32 位宿主", () => {
    const cases: Array<[string, string]> = [
      ["WidevineCdm/_platform_specific/win_x64/widevinecdm.dll", "widevine"],
      ["mspdf.dll", "pdf"],
      ["PdfPreview/pdf_preview.js", "pdf"],
      ["copilotapp.exe", "copilot"],
      ["mscopilot.exe", "copilot"],
      ["onnxruntime.dll", "ai-onnx"],
      ["mip_core_gn.dll", "ai-onnx"],
      ["oneauth.dll", "oneauth"],
      ["elevated_tracing_service.exe", "telemetry-helpers"],
      ["dual_engine_adapter_x64.dll", "ie-mode"],
      ["EBWebView/x86/EmbeddedBrowserWebView.dll", "host-x86"],
      ["Installer/setup.exe", "installer-dirs"],
      ["msedge_200_percent.pak", "ui-scale-paks"],
    ];
    for (const [rel, id] of cases) expect(matchRule(rel)?.id, rel).toBe(id);
  });

  it("★核心件绝不被任何规则碰（比逐条枚举更硬的不变量）", () => {
    const hit = REQUIRED_CORE.filter((rel: string) => matchRule(rel, "max") !== null);
    expect(hit, `这些核心件被规则命中了，会导致用户双击没反应：${hit.join(", ")}`).toEqual([]);
  });

  it("缩放资源包只删 200% 那份（100% 走 AddDataPackFromPath 必需，200% 才是 optional）", () => {
    expect(matchRule("msedge_100_percent.pak"), "100% 那份不能删").toBeNull();
    expect(matchRule("msedge_200_percent.pak")?.id).toBe("ui-scale-paks");
    expect(REQUIRED_CORE).toContain("msedge_100_percent.pak");
  });

  it("Widevine 只删平台 DLL，LICENSE / manifest 必须留（EULA §3(c)：不得移除声明文件）", () => {
    expect(matchRule("WidevineCdm/LICENSE"), "声明文件不能删").toBeNull();
    expect(matchRule("WidevineCdm/manifest.json")).toBeNull();
    expect(matchRule("WidevineCdm/_platform_specific/win_x64/widevinecdm.dll")?.id).toBe("widevine");
  });

  it("引擎本体与 C 运行库一律保留", () => {
    for (const rel of ["msedge.dll", "msedge_elf.dll", "ffmpeg.dll", "d3dcompiler_47.dll",
                       "resources.pak", "icudtl.dat", "v8_context_snapshot.bin",
                       "msvcp140.dll", "vcruntime140.dll", "msedgewebview2.exe"]) {
      expect(matchRule(rel), rel).toBeNull();
    }
  });

  it("default 档 = safe；safe 留 DXC 与软件 Vulkan，max 才删（跨机型证据不足 ⇒ 不当默认）", () => {
    expect(DEFAULT_PROFILE).toBe("safe");
    expect(SLIM_PROFILES).toContain("max");
    for (const rel of ["dxcompiler.dll", "dxil.dll", "vk_swiftshader.dll", "vulkan-1.dll"]) {
      expect(matchRule(rel, "safe"), `safe 不该删 ${rel}`).toBeNull();
      expect(matchRule(rel, "max")?.id, `max 该删 ${rel}`).toBeTruthy();
    }
  });

  it("未知档位直接抛错（别静默按 safe 跑）", () => {
    expect(() => matchRule("msedge.dll", "tiny")).toThrow(/未知档位/);
  });

  it("源运行时新增的未知文件会被**保留**（换版本时宁多勿缺）", () => {
    expect(matchRule("SomeFutureFeature.dll")).toBeNull();
    expect(matchRule("Locales/xx-XX.pak")?.id).toBe("locales");   // 语言包例外：多语言一律不留
  });
});

describe("planSlim：体积账要算得出来", () => {
  it("保留/删除两侧的文件数与字节数一致（不重不漏）", () => {
    const entries = [e("msedge.dll", 300), e("Locales/ja.pak", 50), e("WidevineCdm/x.dll", 20), e("ffmpeg.dll", 10)];
    const plan = planSlim(entries, "safe");
    expect(plan.keep.map((x: { rel: string }) => x.rel).sort()).toEqual(["ffmpeg.dll", "msedge.dll"]);
    expect(plan.remove.map((x: { rel: string }) => x.rel).sort()).toEqual(["Locales/ja.pak", "WidevineCdm/x.dll"]);
    expect(plan.keptBytes).toBe(310);
    expect(plan.removedBytes).toBe(70);
    expect(plan.keep.length + plan.remove.length).toBe(entries.length);
  });
});

describe("stageWebView2：真的落盘，且缺核心件必须抛错", () => {
  /** 造一份"迷你运行时"：核心件齐全 + 若干臃肿件 */
  function makeSrc(withCore = true): string {
    const src = mkTmp();
    const files: Array<[string, number]> = [
      ["msedgewebview2.exe", 10], ["msedge.dll", 100], ["msedge_elf.dll", 5], ["ffmpeg.dll", 5],
      ["resources.pak", 20], ["icudtl.dat", 8], ["v8_context_snapshot.bin", 4],
      ["d3dcompiler_47.dll", 6], ["msedge_100_percent.pak", 2],
      ["EBWebView/x64/EmbeddedBrowserWebView.dll", 9],
      ["Locales/en-US.pak", 3], ["Locales/zh-CN.pak", 3],
      ["Locales/ja.pak", 3], ["WidevineCdm/_platform_specific/win_x64/widevinecdm.dll", 7],
      ["dxcompiler.dll", 11], ["vk_swiftshader.dll", 4], ["copilotapp.exe", 2],
    ];
    for (const [rel, size] of files) {
      if (!withCore && rel === "msedge.dll") continue;      // 故意缺一个核心件
      const p = join(src, rel);
      mkdirSync(join(p, ".."), { recursive: true });
      writeFileSync(p, Buffer.alloc(size, 1));
    }
    return src;
  }

  it("按规划铺出去：臃肿件不在、核心件在（safe 档）", () => {
    const src = makeSrc();
    const dst = mkTmp();
    const st = stageWebView2(src, dst, { profile: "safe", log: () => {} });
    expect(existsSync(join(dst, "msedge.dll"))).toBe(true);
    expect(existsSync(join(dst, "Locales/zh-CN.pak"))).toBe(true);
    expect(existsSync(join(dst, "Locales/ja.pak"))).toBe(false);
    expect(existsSync(join(dst, "WidevineCdm"))).toBe(false);
    expect(existsSync(join(dst, "copilotapp.exe"))).toBe(false);
    expect(existsSync(join(dst, "dxcompiler.dll")), "safe 档要留 DXC").toBe(true);
    expect(st.files).toBe(14);                              // 17 个源文件 - 3 个臃肿件（ja.pak / widevinecdm / copilotapp）
    // 迷你源太小 ⇒ 必须给出"规则可能过期"的告警，而不是静默当作没事
    expect(st.warnings.length).toBe(1);
    expect(MIN_EXPECTED_SAVING_BYTES).toBeGreaterThan(0);
  });

  it("max 档连 DXC / 软件 Vulkan 一并删", () => {
    const src = makeSrc();
    const dst = mkTmp();
    stageWebView2(src, dst, { profile: "max", log: () => {} });
    expect(existsSync(join(dst, "dxcompiler.dll"))).toBe(false);
    expect(existsSync(join(dst, "vk_swiftshader.dll"))).toBe(false);
  });

  it("源缺 msedge.dll ⇒ 抛错（绝不铺一份残缺运行时给用户）", () => {
    const src = makeSrc(false);
    const dst = mkTmp();
    expect(() => stageWebView2(src, dst, { profile: "safe", log: () => {} }))
      .toThrow(/核心件缺失[\s\S]*msedge\.dll/);
  });

  it("源不像固定版运行时（缺 msedgewebview2.exe）⇒ 立刻抛错", () => {
    const src = mkTmp();
    writeFileSync(join(src, "hello.txt"), "x");
    expect(() => stageWebView2(src, mkTmp(), { profile: "safe", log: () => {} })).toThrow(/不像 WebView2/);
  });

  it("assertRequiredCore 把缺的件全列出来", () => {
    const dst = mkTmp();
    expect(() => assertRequiredCore(dst)).toThrow(/msedge\.dll/);
    mkdirSync(join(dst, "Locales"), { recursive: true });
    for (const rel of REQUIRED_CORE) {
      const p = join(dst, rel);
      mkdirSync(join(p, ".."), { recursive: true });
      writeFileSync(p, "x");
    }
    expect(() => assertRequiredCore(dst)).not.toThrow();
  });
});

describe("构建链路接线", () => {
  it("build:release 走 stageWebView2，且**在 tauri build 之后**（顺序铁律）", async () => {
    const { readFileSync } = await import("node:fs");
    const text = readFileSync(join(GUI, "scripts", "build-release.mjs"), "utf8");
    const tauri = text.indexOf('["tauri", "build"]');
    const stage = text.indexOf("stageWebView2(WEBVIEW2_SRC");
    expect(tauri).toBeGreaterThan(-1);
    expect(stage).toBeGreaterThan(-1);
    expect(stage).toBeGreaterThan(tauri);
    // 不许退回"整目录 cpSync"（那就是 668 MB 撑爆交付包的老做法）
    expect(text).not.toMatch(/cpSync\(WEBVIEW2_SRC/);
    // Win10 需要 AppContainer ACL（官方分发文档 Step 6）——挂在铺设之后
    expect(text).toContain("applyAppContainerAcl(dst");
    expect(text.indexOf("applyAppContainerAcl(dst")).toBeGreaterThan(stage);
  });
});

describe("AppContainer ACL（Win10 需要，Win11 不需要）", () => {
  it("对存在的目录调用不抛错、返回 {applied, detail}（本机 Win11 ⇒ 断言只锁「不炸」）", () => {
    const dir = mkTmp();
    const r = applyAppContainerAcl(dir, { log: () => {} });
    expect(typeof r.applied).toBe("boolean");
    expect(typeof r.detail).toBe("string");
  });

  it("目录不存在 ⇒ applied=false 且说明原因（不抛错，构建不该因它失败）", () => {
    const r = applyAppContainerAcl(join(mkTmp(), "nope"), { log: () => {} });
    expect(r.applied).toBe(false);
    expect(r.detail).toMatch(/目录不存在|非 Windows/);
  });
});
