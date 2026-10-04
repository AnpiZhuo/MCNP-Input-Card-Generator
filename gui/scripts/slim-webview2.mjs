/**
 * slim-webview2.mjs — 把微软 WebView2「固定版运行时」铺进产物目录时**顺手削到最小**。
 *
 * ## 为什么要有这一步（2026-09-29 定策，2026-10-02 定案）
 * 没有 Edge 的机器能不能开界面，全看随包的 `WebView2\`（见 `main.rs::prefer_bundled_webview2`）。
 * 但官方 FixedVersionRuntime 解压出来是 **668.4 MB / 257 文件**，而这份运行时的绝大部分与
 * 本程序无关：168 个语言包（128.3 MB）、Widevine DRM（21.7 MB）、内置 PDF 阅读器（18.0 MB）、
 * Copilot/ONNX 一套（约 30 MB）、遥测与辅助进程、IE 模式适配器、32 位宿主 DLL……
 *
 * 本模块就是"剪掉这些"的那把刀，且**只剪经过实测的**：
 *   实测方法（可复现）：自建最小 WebView2 宿主（wry 0.24）开真窗口 → 页面里建 WebGL2 上下文、
 *   画三角形、`readPixels` 校验像素、并把 UA/渲染器/版本回执到本机 127.0.0.1；
 *   同时用 `Get-CimInstance Win32_Process` 确认渲染进程的可执行文件**确实**来自被裁剪的那份运行时。
 *   裁剪后跑通 4 条 GPU 路径：D3D11 硬件（ANGLE AMD）、D3D11on12、WARP 软件
 *   （Microsoft Basic Render Driver）、SwiftShader（Vulkan）——**全部 WEBGL-OK**。
 *   再用**真实交付 exe**（Tauri 外壳 + 真后端）做端到端：窗口起、后端连上、进程归属正确。
 *
 * ## 两档口径
 *   safe（默认，随包发的就是这一档）：**668.4 → 433.8 MB（省 234.6 MB，35.1%）**
 *       删：语言包（留 en-US + zh-CN）、Widevine 平台 DLL（**LICENSE/manifest 保留**）、
 *           PDF 阅读器、Copilot/AI/ONNX 一套、oneauth、遥测与辅助进程、IE 模式适配器、
 *           32 位宿主 DLL、安装器/扩展目录、200% 缩放资源包、两个 .dat 配置。
 *       留：dxcompiler/dxil（21.4 MB）、vk_swiftshader/vulkan-1（5.4 MB）、
 *           d3dcompiler_47（**WebGL 命脉**）、msedge_100_percent.pak（**必需**）、
 *           Locales/en-US.pak（**缺失即启动崩溃**）—— 见下面"来源"。
 *   max：**407.6 MB（省 260.8 MB，39.0%）**，即在 safe 之上再删
 *       ① `dxcompiler.dll` + `dxil.dll`（= Dawn/D3D12 的 DXC 着色器编译器），
 *       ② `vk_swiftshader.dll` + `vulkan-1.dll` + `vk_swiftshader_icd.json`（软件 Vulkan 回退）。
 *       实测二者删掉后本机 4 条路径仍全绿，但**跨机型证据不足**，因此不作为默认档：
 *         · DXC：ANGLE 的 D3D 后端**只用 FXC**（`LoadLibraryA(D3DCOMPILER_DLL_A)` + `D3DCompile`），
 *           DXC 只被 Dawn 的 D3D12 后端用（`EnsureDXCLibraries`），而 Dawn 明示**不做探测、不回退 FXC**
 *           ⇒ 删它 WebGL2 安全（实测 4 条路径全绿），但 **WebGPU/Graphite 会硬失败**；
 *           本程序只用 three.js WebGL2（不用 `navigator.gpu`），故仍可接受，但没必要冒险。
 *         · SwiftShader：自动回退 `kAllowSwiftShaderFallback` 已是 DISABLED_BY_DEFAULT，Windows 软件回退
 *           优先走**系统自带 WARP**（`kAllowD3D11WarpFallback` = ENABLED_BY_DEFAULT，实测生效）；
 *           且 WebView2 官方 flags 清单不提供 `use-angle`/`enable-unsafe-swiftshader`
 *           ⇒ 删的实际风险低，但只值 5.4 MB，留作兜底更划算。
 *
 * ## 来源（2026-10-02 联网核对 Chromium/ANGLE/Dawn 源码 + 本机 Edge/WebView2 154 二进制只读扫描）
 *   · ANGLE HLSL 编译：`src/libANGLE/renderer/d3d/HLSLCompiler.cpp`（只有 FXC）
 *   · Dawn 的 DXC 依赖：`src/dawn/native/d3d12/PlatformFunctionsD3D12.cpp::EnsureDXCLibraries`
 *   · locale 回退链与必崩条件：`ui/base/l10n/l10n_util.cc` + `ui/base/resource/resource_bundle.cc`
 *     （`LoadLocaleResources` 失败即 `NOTREACHED()`；**en-US 是回退终点**）
 *   · SwiftShader/WARP 默认值：`ui/gl/gl_features.cc`
 *   · 官方分发要求：learn.microsoft.com「Distribute your app and the WebView2 Runtime」
 *     —— 原文是 *Include **all** of the decompressed Fixed Version binaries*；**没有**官方"最小文件集"。
 *     ⇒ 裁剪有"真实但非致命"的许可风险（EULA §3(a) 禁止绕过技术限制；§2(b)(iv) 的免责仅覆盖 unmodified code），
 *       本项目仍按用户 2026-10-02 的明确决定采用裁剪档，并保留全部声明文件。
 *   · **Win10 部署必做**：固定版 ≥120 需对运行时目录补 AppContainer ACL
 *     （`icacls <dir> /grant *S-1-15-2-2:(OI)(CI)(RX)` 与 `*S-1-15-2-1:(OI)(CI)(RX)`），
 *     否则 Renderer 进不了 App Container —— 见 `applyAppContainerAcl()`（本模块落盘后自动跑，尽力而为）。
 *
 * ## 口径：黑名单，不白名单
 * 规则只点名"要删的"，**其它一律保留**。将来换运行时版本时，新增的文件会默认被留下
 * （宁多勿缺：多带几 MB 只是体积，少带一个文件就是"用户双击没反应"）。
 * 同时用 `REQUIRED_CORE` 兜底：铺完必须存在，缺一个就**非零退出**，绝不产出半成品。
 *
 * ## 用法
 *     node scripts/slim-webview2.mjs <源运行时目录> <目标目录> [--profile safe|max] [--dry-run]
 *     被 build-release.mjs 第 ③.5 步直接 import 调用（`stageWebView2`）。
 */
import { copyFileSync, existsSync, mkdirSync, readdirSync, rmSync, statSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join, posix, resolve } from "node:path";
import { fileURLToPath } from "node:url";

/** 落点目录名写死在 `gui/src-tauri/src/main.rs::prefer_bundled_webview2()`，改名 = 自带运行时形同没有。 */
export const WEBVIEW2_DIR_NAME = "WebView2";

/** Chromium 至少要有一个界面语言包；这两个是中文用户实际会命中的（zh-CN 优先、en-US 兜底）。 */
export const KEEP_LOCALES = ["en-US.pak", "zh-CN.pak"];

/** 铺完必须存在的核心件；缺任何一个都说明裁剪剪错了，必须中止（不能发出去让用户双击没反应）。 */
export const REQUIRED_CORE = [
  "msedgewebview2.exe",                              // 运行时入口（main.rs 就是认它来判断"自带运行时在不在"）
  "msedge.dll",                                      // Chromium 内核本体（333 MB，唯一的大头）
  "msedge_elf.dll",                                  // msedgewebview2.exe 的静态导入（PE 导入表实证）
  "ffmpeg.dll",                                      // msedge.dll 的静态导入（PE 导入表实证）
  "resources.pak",                                   // 渲染进程资源包
  "icudtl.dat",                                      // ICU 国际化数据
  "v8_context_snapshot.bin",                         // V8 启动快照
  "d3dcompiler_47.dll",                              // ★WebGL 的命脉：ANGLE 的 D3D 后端只用 FXC（D3DCompile），不是 DXC
  "msedge_100_percent.pak",                          // Chromium 走 AddDataPackFromPath（**必需**）；200% 那份才是 AddOptionalDataPackFromPath
  "EBWebView/x64/EmbeddedBrowserWebView.dll",        // 64 位宿主 DLL（Tauri 加载的就是它）
  "Locales/en-US.pak",                               // ★回退链的终点：连它都没有 → LoadLocaleResources 直接 NOTREACHED 崩
  "Locales/zh-CN.pak",
];

/**
 * 删除规则。`test(rel)` 收到 POSIX 风格的相对路径（目录本身也会被逐个测试，
 * 命中目录即整棵子树不拷）。`profile` = 该规则只在哪一档生效。
 * 每条都写清"为什么敢删"。
 */
export const SLIM_RULES = [
  {
    id: "locales",
    profile: "safe",
    why: "168 个界面语言包占 128.3 MB；只留 zh-CN + en-US（实测渲染/WebGL 无影响）",
    test: (rel) => rel.startsWith("Locales/") && rel.endsWith(".pak")
      && !KEEP_LOCALES.includes(posix.basename(rel)),
  },
  {
    id: "widevine",
    profile: "safe",
    why: "Widevine CDM 的平台 DLL（21.7 MB）是 DRM 视频解密用的；本程序不放受 DRM 保护的流媒体。" +
      "**LICENSE 与 manifest.json 必须留**（EULA §3(c) 禁止移除微软及其供应商的声明文件）",
    test: (rel) => rel.startsWith("WidevineCdm/")
      && !["WidevineCdm/LICENSE", "WidevineCdm/manifest.json"].includes(rel),
  },
  {
    id: "pdf",
    profile: "safe",
    why: "内置 PDF 阅读器（mspdf.dll 18.0 MB + PdfPreview/ + pdfpreviewhandler.dll）；本程序只**导出** PDF，不在窗口里看 PDF",
    test: (rel) => ["mspdf.dll", "pdfpreviewhandler.dll", "PdfPreview"].includes(rel)
      || rel.startsWith("PdfPreview/"),
  },
  {
    id: "copilot",
    profile: "safe",
    why: "Copilot/侧边栏一套（copilotapp.exe、mscopilot.exe、copilot_overlay_*.pak、Copilot.dat、copilot_setup.exe），与 MCNP 建模无关",
    test: (rel) => /^copilot|^mscopilot\.exe$|^Copilot\.dat$/i.test(rel),
  },
  {
    id: "ai-onnx",
    profile: "safe",
    why: "浏览器内置 AI 推理（onnxruntime 10.6 MB + mip_core_gn 8.3 MB + learning_tools + onramp），本程序不用",
    test: (rel) => ["onnxruntime.dll", "mip_core_gn.dll", "learning_tools.dll", "onramp.dll"].includes(rel),
  },
  {
    id: "oneauth",
    profile: "safe",
    why: "微软账号登录（oneauth.dll 6.2 MB + oneds.dll 3.4 MB）；本程序不登录、不同步",
    test: (rel) => ["oneauth.dll", "oneds.dll"].includes(rel),
  },
  {
    id: "telemetry-helpers",
    profile: "safe",
    why: "遥测/辅助进程与外壳集成（elevated_tracing_service、platform_experiences_helper、notification_helper、telclient、microsoft_shell_integration、wdag、prefs_enclave_x64、eventlog_provider、msedge_wer），共约 15.9 MB",
    test: (rel) => [
      "elevated_tracing_service.exe", "platform_experiences_helper.exe", "notification_helper.exe",
      "telclient.dll", "microsoft_shell_integration.dll", "wdag.dll", "prefs_enclave_x64.dll",
      "eventlog_provider.dll", "msedge_wer.dll",
    ].includes(rel),
  },
  {
    id: "ie-mode",
    profile: "safe",
    why: "IE 模式（双引擎）适配器 dual_engine_adapter_x64.dll 5.2 MB；本程序是标准 Chromium 页面，不用 IE 模式",
    test: (rel) => rel === "dual_engine_adapter_x64.dll",
  },
  {
    id: "host-x86",
    profile: "safe",
    why: "EBWebView\\x86 是 32 位宿主 DLL（5.5 MB）；本产品 exe / sidecar 都是 x64",
    test: (rel) => rel === "EBWebView/x86" || rel.startsWith("EBWebView/x86/"),
  },
  {
    id: "installer-dirs",
    profile: "safe",
    why: "安装器/扩展/预载/信任列表/反馈等空壳目录，运行时不需要",
    test: (rel) => ["Installer", "Extensions", "MEIPreload", "Trust Protection Lists",
      "AdSelectionAttestationsPreloaded", "edge_feedback"].includes(rel)
      || /^(Installer|Extensions|MEIPreload|Trust Protection Lists|AdSelectionAttestationsPreloaded|edge_feedback)\//.test(rel),
  },
  {
    id: "ui-scale-paks",
    profile: "safe",
    why: "只删 **200%** 缩放资源包（1.0 MB）：Chromium 对 200% 那份走 AddOptionalDataPackFromPath（可选），" +
      "而 100% 那份走 AddDataPackFromPath（**必需**）⇒ 100% 已进 REQUIRED_CORE，" +
      "本规则与「规则不得命中 REQUIRED_CORE」的不变量测试共同保证它不被误删",
    test: (rel) => rel === "msedge_200_percent.pak",
  },
  {
    id: "misc-config",
    profile: "safe",
    why: "Edge 特性配置文件与第三方许可脚本（合计约 30 KB），运行时不需要",
    test: (rel) => ["Edge.dat", "EdgeWebView.dat", "textInputMethod.sccd",
      "show_third_party_software_licenses.bat"].includes(rel),
  },
  {
    id: "dxc",
    profile: "max",
    why: "DXC 着色器编译器（dxcompiler 19.5 MB + dxil 1.4 MB）：D3D12/Graphite/WebGPU 路径用；" +
      "实测本机 4 条路径删后全绿（ANGLE 会退回 FXC/d3dcompiler_47），但跨 GPU/驱动机型证据不足 ⇒ 只在 max 档删",
    test: (rel) => ["dxcompiler.dll", "dxil.dll"].includes(rel),
  },
  {
    id: "swiftshader",
    profile: "max",
    why: "软件 Vulkan 回退（vk_swiftshader 4.5 MB + vulkan-1 0.95 MB + ICD 清单）：实测删后 WARP(D3D11) 仍能兜住软件渲染，" +
      "但无 GPU / 远程桌面机型上它是 Chromium 的常规回退 ⇒ 只在 max 档删",
    test: (rel) => ["vk_swiftshader.dll", "vk_swiftshader_icd.json", "vulkan-1.dll"].includes(rel),
  },
];

export const SLIM_PROFILES = ["safe", "max"];
export const DEFAULT_PROFILE = "safe";

/**
 * 源目录明显变小/变味时（比如换了一份精简过的运行时），静默"什么都没删"最危险：
 * 体积会悄悄涨回去而没人发现。省得少于此值就在日志里点名。
 */
export const MIN_EXPECTED_SAVING_BYTES = 150 * 1024 * 1024;

/** 某个相对路径是否命中删除规则；返回命中的规则对象或 null。 */
export function matchRule(rel, profile = DEFAULT_PROFILE) {
  const p = rel.replace(/\\/g, "/").replace(/\/+$/, "");
  const idx = SLIM_PROFILES.indexOf(profile);
  if (idx < 0) throw new Error(`未知档位：${profile}（可选 ${SLIM_PROFILES.join(" / ")}）`);
  for (const rule of SLIM_RULES) {
    // safe 档 = profile 为 safe 的规则；max 档 = 全部规则
    if (profile === "safe" && rule.profile !== "safe") continue;
    if (rule.test(p)) return rule;
  }
  return null;
}

/**
 * 纯规划：给定条目表，算出要拷哪些、删哪些。不碰磁盘（因此可单测）。
 * @param {{rel:string, isDir:boolean, size:number}[]} entries
 */
export function planSlim(entries, profile = DEFAULT_PROFILE) {
  const keep = [];
  const remove = [];
  for (const e of entries) {
    const rule = matchRule(e.rel, profile);
    if (rule) remove.push({ ...e, rule: rule.id, why: rule.why });
    else keep.push(e);
  }
  const sum = (xs) => xs.reduce((a, b) => a + (b.size || 0), 0);
  return { keep, remove, keptBytes: sum(keep), removedBytes: sum(remove) };
}

/** 递归列目录（只列文件与目录，不跟软链），rel 用 POSIX 分隔符。 */
export function listEntries(root) {
  const out = [];
  const walk = (dir, prefix) => {
    for (const name of readdirSync(dir, { withFileTypes: true })) {
      const full = join(dir, name.name);
      const rel = prefix ? `${prefix}/${name.name}` : name.name;
      const isDir = name.isDirectory();
      out.push({ rel, isDir, size: isDir ? 0 : statSync(full).size });
      if (isDir) walk(full, rel);
    }
  };
  walk(root, "");
  return out;
}

/** 铺完的兜底校验：核心件必须在。缺件就把缺的列出来（绝不静默通过）。 */
export function assertRequiredCore(dstDir, required = REQUIRED_CORE) {
  const missing = required.filter((rel) => !existsSync(join(dstDir, rel)));
  if (missing.length) {
    throw new Error(
      `裁剪后核心件缺失：\n    ${missing.join("\n    ")}\n` +
      `  这些是启动必需件（PE 导入表 + Chromium 源码 + 实测共同确定），缺一个用户就是"双击没反应"。\n` +
      `  多半是 SLIM_RULES 里某条规则误伤了，或源运行时版本变了。`);
  }
}

/**
 * Win10 上固定版运行时（≥120）必须把运行时目录授权给 AppContainer，否则 Renderer 进程
 * 进不了 App Container（官方分发文档 Step 6 明写：对运行时目录跑
 * `icacls <dir> /grant *S-1-15-2-2:(OI)(CI)(RX)` 与 `*S-1-15-2-1:(OI)(CI)(RX)`）。
 *
 * 诚实标注：**本机是 Win11（26200），Win11 不需要这两条 ACE，因此本函数的效果在本机无法证伪/证实**；
 * 它按官方要求尽力而为，失败只告警、绝不阻断构建（icacls 不存在 / 权限不足都不该让打包失败）。
 * ⚠️ 注意：ACL 落在**目录**上，第 7 步 xcopy 到交付目录后**要重跑一次**
 * （xcopy 不复制显式 ACE，新目录只继承父目录的 ACE）—— 见 docs/手动打包方法.md §6.5.3。
 */
export function applyAppContainerAcl(dir, { log = () => {} } = {}) {
  if (process.platform !== "win32") return { applied: false, detail: "非 Windows，跳过" };
  if (!existsSync(dir)) return { applied: false, detail: `目录不存在：${dir}` };
  const r = spawnSync("icacls", [
    dir,
    "/grant", "*S-1-15-2-2:(OI)(CI)(RX)",
    "/grant", "*S-1-15-2-1:(OI)(CI)(RX)",
    "/T", "/C", "/Q",
  ], { encoding: "utf8", windowsHide: true });
  const detail = `${r.status === 0 ? "ok" : `icacls 退出码 ${r.status}`}` +
    (r.stderr ? ` / ${String(r.stderr).trim().slice(0, 200)}` : "");
  const applied = r.status === 0;
  log(`[slim-webview2] ${applied ? "✅" : "⚠️ "} AppContainer ACL（Win10 需要）：${detail}`);
  return { applied, detail };
}

/**
 * 真正落盘：按规划从 src 拷到 dst（只拷保留下来的文件），然后校验核心件。
 * @returns {{files:number, keptBytes:number, removedBytes:number, removedFiles:number, profile:string, warnings:string[]}}
 */
export function stageWebView2(src, dst, { profile = DEFAULT_PROFILE, dryRun = false, log = console.log } = {}) {
  if (!existsSync(join(src, "msedgewebview2.exe"))) {
    throw new Error(`源目录不像 WebView2 固定版运行时（缺 msedgewebview2.exe）：${src}`);
  }
  const entries = listEntries(src);
  const files = entries.filter((e) => !e.isDir);
  const totalBytes = files.reduce((a, b) => a + b.size, 0);
  // 目录条目命中规则 ⇒ 它的子树一并不拷；文件条目再按规则逐条判定
  const removedDirs = entries.filter((e) => e.isDir && matchRule(e.rel, profile)).map((e) => e.rel);
  const inRemovedDir = (rel) => removedDirs.some((d) => rel === d || rel.startsWith(d + "/"));
  const plan = planSlim(files.filter((e) => !inRemovedDir(e.rel)), profile);
  const keptSet = new Set(plan.keep.map((e) => e.rel));
  const removedFiles = files.length - plan.keep.length;
  const removedBytes = totalBytes - plan.keptBytes;
  const byRule = new Map();
  for (const e of files) {
    if (keptSet.has(e.rel)) continue;
    const id = matchRule(e.rel, profile)?.id ?? `目录:${e.rel.split("/")[0]}`;
    byRule.set(id, (byRule.get(id) ?? 0) + e.size);
  }
  const warnings = [];
  if (removedBytes < MIN_EXPECTED_SAVING_BYTES) {
    warnings.push(
      `只省了 ${(removedBytes / 1048576).toFixed(1)} MB（预期 ≥ ${(MIN_EXPECTED_SAVING_BYTES / 1048576).toFixed(0)} MB）：` +
      `源运行时可能换了版本、文件名对不上 SLIM_RULES —— 请核对后更新规则`);
  }

  log(`[slim-webview2] ▶ 档位 ${profile}：源 ${files.length} 文件 / ${(totalBytes / 1048576).toFixed(1)} MB`);
  log(`[slim-webview2]   保留 ${plan.keep.length} 文件 ${(plan.keptBytes / 1048576).toFixed(1)} MB；` +
      `删除 ${removedFiles} 文件 ${(removedBytes / 1048576).toFixed(1)} MB`);
  const top = [...byRule.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6)
    .map(([id, sz]) => `${id} ${(sz / 1048576).toFixed(1)}MB`).join("、");
  if (top) log(`[slim-webview2]   省在哪：${top}`);

  if (dryRun) return { files: plan.keep.length, keptBytes: plan.keptBytes, removedBytes, removedFiles, profile, warnings };

  rmSync(dst, { recursive: true, force: true });
  mkdirSync(dst, { recursive: true });
  for (const e of plan.keep) {
    const target = join(dst, e.rel);
    mkdirSync(dirname(target), { recursive: true });
    copyFileSync(join(src, e.rel), target);
  }
  assertRequiredCore(dst);

  // 复核：实际落盘体积与规划一致（防"少拷了文件却当成功"）
  const staged = listEntries(dst).filter((e) => !e.isDir);
  const stagedBytes = staged.reduce((a, b) => a + b.size, 0);
  if (staged.length !== plan.keep.length || stagedBytes !== plan.keptBytes) {
    throw new Error(
      `落盘复核失败：规划 ${plan.keep.length} 文件 / ${plan.keptBytes} B，实际 ${staged.length} 文件 / ${stagedBytes} B`);
  }
  return { files: staged.length, keptBytes: stagedBytes, removedBytes, removedFiles, profile, warnings };
}

/** CLI：手工铺一份（调试/手工打包手册用） */
function main() {
  const args = process.argv.slice(2);
  const profileArg = args.indexOf("--profile");
  const profile = profileArg >= 0 ? args[profileArg + 1] : DEFAULT_PROFILE;
  const dryRun = args.includes("--dry-run");
  const positional = args.filter((a, i) => !a.startsWith("--") && args[i - 1] !== "--profile");
  const [src, dst] = positional;
  if (!src || !dst) {
    console.error("用法: node scripts/slim-webview2.mjs <源运行时目录> <目标目录> [--profile safe|max] [--dry-run]");
    process.exit(2);
  }
  try {
    const st = stageWebView2(resolve(src), resolve(dst), { profile, dryRun });
    for (const w of st.warnings) console.warn(`[slim-webview2] ⚠️  ${w}`);
    if (!dryRun) applyAppContainerAcl(resolve(dst), { log: console.log });
    console.log(`[slim-webview2] ✅ ${dryRun ? "（dry-run，未落盘）" : ""}` +
      `${st.files} 文件 / ${(st.keptBytes / 1048576).toFixed(1)} MB（删 ${st.removedFiles} 文件 / ${(st.removedBytes / 1048576).toFixed(1)} MB）`);
  } catch (e) {
    console.error(`[slim-webview2] ❌ ${e.message}`);
    process.exit(1);
  }
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  main();
}
