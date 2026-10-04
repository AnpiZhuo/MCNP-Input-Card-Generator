/**
 * build-release.mjs — **一次跑对顺序**的完整发布构建（sidecar + 前端 + 外壳 + 校验）。
 *
 * ## 用法
 *     cd gui && npm run build:release
 * 失败即非零退出，不会留下"半新半旧"的产物。
 *
 * ## 它根除的四个坑（前三者 2026-09-18/19 实测；**坑 D 2026-09-26 实测并修复**）
 *
 * **坑 A｜落点冲突**：PyInstaller 默认写 `gui/dist/python/`，而 `vite build` 会**清空
 * `gui/dist/`**。于是"先 PyInstaller → 再 build:app"会把刚打好的 sidecar 删掉，
 * `sync-sidecar` 随后把 `binaries/` 里**上一次的 python.exe** 铺进 target/release，
 * 还报"✅ 已是最新"。⇒ 本脚本用 `--distpath dist_sidecar` 把两者物理分开。
 *
 * **坑 B｜增量缓存**：`gui/build/mcnp_sidecar/`（PyInstaller 默认 workpath）与
 * `gui/build_sidecar/`（手册第 4 步 `--workpath build_sidecar` 用的那个）**都可能残留上次的
 * Analysis 结果**，PyInstaller 据此**复用旧模块字节码**。实测：`inputcard_mcp/server.py` 明明改了，
 * 新产物的 PYZ 里仍是 09-12 的旧代码；**只有删掉 workpath 才真正重编**。
 * ⇒ 本脚本显式用 `--workpath build_sidecar`，并在构建前**把两个目录都清掉**（口径统一，勿再分叉；
 *    2026-09-26 之前脚本清的是 `build/mcnp_sidecar` 而自己跑的是默认 workpath，见 §6 记录）。
 *
 * **坑 C｜binaries 是同步的源**：`sync-sidecar` 比对的是 `src-tauri/binaries/` 与
 * `target/release/`，**它不会自动去 `dist_sidecar/` 取新产物**。所以必须显式把
 * PyInstaller 产物覆盖进 `binaries/`（本脚本第 ② 步），否则比对"一致"的是两份旧货。
 *
 * **坑 D｜顺序自噬（2026-09-26 修复，本次打 v1.7.7 首次即踩）**：旧版把 `vite build + tauri build`
 * 排在最前，而 `tauri.conf.json` 的 `beforeBuildCommand` = `npm run build && npm run sync-sidecar`，
 * 后者看到 `dist_sidecar/python` 不存在就**直接 exit 1**（这正是它该做的事：宁可中止，也不把旧 sidecar 铺出去）：
 *
 *     [sync-sidecar] ❌ PyInstaller 产物不存在：…\gui\dist_sidecar\python
 *        没有新产物时继续同步，只会把 binaries/ 里上一次的旧 sidecar 铺出去 … 已中止。
 *     Error beforeBuildCommand `npm run build && npm run sync-sidecar` failed with exit code 1
 *     [build-release] ❌ tauri build（含 beforeBuildCommand 的预同步） 失败（退出码 1）— 已中止
 *
 * ⇒ **干净工作区（没有 `dist_sidecar/`）上整条 `build:release` 必然自我中断**，只能退回手册手工顺序。
 * **修法 = 把 sidecar 生产挪到最前**。为什么以前不敢挪：PyInstaller 默认落 `gui/dist/python`，
 * 而 `vite build` 会清空 `gui/dist` —— 但本脚本早已用 `--distpath dist_sidecar` 把两者物理分开（坑 A），
 * 所以"sidecar 先行"不再有任何冲突。**现行顺序：sidecar → binaries → vite → tauri → WebView2 → 同步 → 自检。**
 *
 * **坑 E｜没有 Edge 的机器打不开（2026-09-29 实测加修）**：界面是 WebView2 渲染的，
 * 而 WebView2 平时跟着 Edge 装；精简版 Windows 删掉 Edge 就连带没有它 ⇒ **双击 exe 没反应**。
 * ⇒ 现在随包分发微软官方「固定版运行时」到 `<exe 同级>\WebView2`（由 `main.rs` 的
 * `prefer_bundled_webview2()` 用官方环境变量 `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER` 接管，
 * **有则用、无则退**系统运行时）。**顺序：必须在 `tauri build` 之后**（`target/release` 是它建的），
 * 且运行时源目录缺失时**直接中止**（理由见第 ③.5 步注释：这是唯一只在用户机器上暴露的差异）。
 *
 * **坑 F｜整份运行时 668 MB，交付包被它撑到 419 MB（2026-10-02 实测加修）**：官方
 * FixedVersionRuntime 是"整份 Edge"（168 个语言包、Widevine、内置 PDF、Copilot/ONNX、
 * 遥测辅助进程、IE 模式适配器、32 位宿主 DLL……），与本程序无关。⇒ 铺进去时改走
 * `slim-webview2.mjs`（黑名单裁剪 + 核心件兜底校验）：**668.4 → 432.8 MB（safe 档）**，
 * 交付 zip 约 419 → 305 MB。裁剪依据是"自建最小 WebView2 宿主 + 真 WebGL2 像素校验 +
 * 进程归属取证"的实测（D3D11 / D3D11on12 / WARP / SwiftShader 四条路径全绿），
 * 详见该模块头部注释与 `docs/手动打包方法.md` §6.5。档位用 `WEBVIEW2_SLIM_PROFILE` 切换。
 * **顺序同样是 `tauri build` 之后**；核心件缺任何一个都**中止**（不产出半成品）。
 *
 * ## 顺序铁律（改本文件时务必保持，否则又会出现"版本号新、后端旧"或链路自我中断）
 *   ① PyInstaller 必须在 `tauri build` **之前**（它的产物是 beforeBuildCommand 里 sync-sidecar 的前提）；
 *   ② `binaries/` 覆盖必须在 `tauri build` **之前**（tauri 编译期拿它铺 `_internal`）；
 *   ③ `sync-sidecar --check --require-target` 必须在 `tauri build` **之后**（tauri 只刷新 `_internal`，
 *      **不刷新 `python.exe`** —— 实测过多次）；
 *   ③.5 `WebView2\` 铺进 `target/release` 也必须在 `tauri build` **之后**（同上，目录是它建的），
 *      且**铺进去的那份要裁剪**（坑 F：整份 668 MB 会把交付包撑到 419 MB）；
 *   ④ `stage-selftest` **先写**、`stage-selftest --check` **后查**（反了在干净/首次构建上必报缺失并 exit 1）。
 */
import { spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { DEFAULT_PROFILE as WEBVIEW2_DEFAULT_PROFILE, SLIM_PROFILES, applyAppContainerAcl, stageWebView2 } from "./slim-webview2.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const GUI = resolve(HERE, "..");
/** PyInstaller 产物落点（与 vite 的 dist/ 分开 → 坑 A） */
const SIDECAR_DIST = join(GUI, "dist_sidecar");
/** PyInstaller 工作/缓存目录：本脚本显式 `--workpath build_sidecar`，并把它清掉（坑 B） */
const SIDECAR_WORK = join(GUI, "build_sidecar");
/** 历史上另一个可能的缓存落点（默认 workpath），一并清，防"清缓存对不上"（坑 B） */
const SIDECAR_WORK_LEGACY = join(GUI, "build", "mcnp_sidecar");
/** Tauri 约定的 sidecar 源目录（同步的比较源 → 坑 C） */
const BINARIES = join(GUI, "src-tauri", "binaries");
const SIDECAR_SRC_NAME = "python-x86_64-pc-windows-msvc.exe";

/** tauri build 的产物目录（exe + 前端资源都在这里） */
const RELEASE_DIR = join(GUI, "src-tauri", "target", "release");

/**
 * WebView2「固定版运行时」—— 随包分发，**没有 Edge 的机器也能开界面**（2026-09-29 起）。
 *
 * 背景：界面是 WebView2 渲染的，而 WebView2 平时由 Edge 附带安装。精简版 Windows 删掉
 * Edge 就连带没有它 ⇒ 双击 exe 没反应/一闪就没（用户报的"打不开"就是这个）。
 *
 * 落点为什么是 `<exe 同级>\WebView2`：`gui\src-tauri\src\main.rs` 的
 * `prefer_bundled_webview2()` 就是按这个**固定目录名**去找 `msedgewebview2.exe` 的，
 * 找到才把 `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER` 指过去。改名 = 自带运行时形同没有。
 *
 * 来源路径可用环境变量 `WEBVIEW2_FIXED_RUNTIME` 覆盖（默认指向本机的解压产物）。
 * 取得方式：微软官方 FixedVersionRuntime cab → `expand -F:* <cab> <dir>`，
 * 解压出来的那一层（**直接含 msedgewebview2.exe**）就是这里要的目录。
 */
const WEBVIEW2_DIR = "WebView2";
const WEBVIEW2_SRC = process.env.WEBVIEW2_FIXED_RUNTIME
  || "D:\\MCNP\\webview2-fixed\\extracted\\Microsoft.WebView2.FixedVersionRuntime.154.0.4258.37.x64";
/**
 * 裁剪档位（见 `slim-webview2.mjs`）：
 *   safe（默认）= 删与本程序无关的 235.6 MB（语言包/DRM/PDF/Copilot/ONNX/遥测/IE 模式/32 位宿主…）；
 *   max         = safe 之上再删 DXC(21 MB) 与软件 Vulkan(5.4 MB)——本机实测可用，但跨机型证据不足。
 */
const WEBVIEW2_PROFILE = process.env.WEBVIEW2_SLIM_PROFILE || WEBVIEW2_DEFAULT_PROFILE;
if (!SLIM_PROFILES.includes(WEBVIEW2_PROFILE)) {
  console.error(`[build-release] ❌ 未知的 WEBVIEW2_SLIM_PROFILE=${WEBVIEW2_PROFILE}（可选 ${SLIM_PROFILES.join(" / ")}）`);
  process.exit(2);
}

function run(label, cmd, args) {
  console.log(`\n[build-release] ▶ ${label}`);
  const r = spawnSync(cmd, args, { cwd: GUI, stdio: "inherit", shell: process.platform === "win32" });
  if (r.status !== 0) {
    console.error(`[build-release] ❌ ${label} 失败（退出码 ${r.status}）— 已中止，不产出半成品`);
    process.exit(r.status ?? 1);
  }
}

const npx = process.platform === "win32" ? "npx.cmd" : "npx";
const t0 = Date.now();

// ── ① Python sidecar：**必须先于 tauri build**（否则 beforeBuildCommand 里的 sync-sidecar 必中止 → 坑 D）
//      先清缓存（坑 B）→ 写到独立目录（坑 A）
for (const dir of [SIDECAR_WORK, SIDECAR_WORK_LEGACY]) {
  if (existsSync(dir)) {
    console.log(`[build-release] ▶ 清 PyInstaller 增量缓存（否则可能复用旧字节码）：${dir}`);
    rmSync(dir, { recursive: true, force: true });
  }
}
if (existsSync(SIDECAR_DIST)) rmSync(SIDECAR_DIST, { recursive: true, force: true });
run("PyInstaller（生成 sidecar）", "python", [
  "-m", "PyInstaller", "--noconfirm",
  "--distpath", "dist_sidecar", "--workpath", "build_sidecar",
  "mcnp_sidecar.spec",
]);

const builtExe = join(SIDECAR_DIST, "python", "python.exe");
const builtInternal = join(SIDECAR_DIST, "python", "_internal");
if (!existsSync(builtExe) || !existsSync(builtInternal)) {
  console.error(`[build-release] ❌ PyInstaller 未产出 ${builtExe} 或 _internal`);
  process.exit(1);
}

// ── ② 覆盖进 binaries（坑 C：binaries 才是 sync 的比较源）—— 必须在 tauri build 之前
//    `src-tauri/binaries/` 是 **gitignore 掉的构建产物目录** ⇒ 干净检出上并不存在，
//    必须先 recursive 建出来（手册第 5 步的 `mkdir` 就是这个作用），否则 cpSync 直接 ENOENT。
console.log("\n[build-release] ▶ 覆盖 src-tauri/binaries/（sync 的比较源）");
mkdirSync(BINARIES, { recursive: true });
cpSync(builtExe, join(BINARIES, SIDECAR_SRC_NAME));
rmSync(join(BINARIES, "_internal"), { recursive: true, force: true });
cpSync(builtInternal, join(BINARIES, "_internal"), { recursive: true });

// ── ③ 前端 + Rust 外壳（vite 会清空 gui/dist，但 sidecar 已在 dist_sidecar ⇒ 互不干扰）
run("vite build（清空并重建 dist/）", npx, ["vite", "build"]);
run("tauri build（含 beforeBuildCommand 的预同步，此时 dist_sidecar 已就绪）", npx, ["tauri", "build"]);

// ── ③.5 WebView2 固定版运行时 → `<exe 同级>\WebView2`（2026-09-29 加，坑 E）
//    顺序：必须在 tauri build **之后**（target/release 是它建的，先铺会被覆盖/落空）。
//    为什么缺了要**中止**而不是警告：这一目录就是"没有 Edge 的机器能不能打开"的唯一区别，
//    而它只在用户机器上才暴露 —— 打出个没带运行时的包，等于白跑一遍全链路还发出去。
if (!existsSync(join(WEBVIEW2_SRC, "msedgewebview2.exe"))) {
  console.error(
    `[build-release] ❌ 找不到 WebView2 固定版运行时：${WEBVIEW2_SRC}\n` +
    `  该目录下必须有 msedgewebview2.exe。取得方式（微软官方，可再分发形态）：\n` +
    `    1) 下载 FixedVersionRuntime 的 x64 cab（见 docs/手动打包方法.md 第 7.1 节）\n` +
    `    2) expand -F:* <cab> <解压目录>    ← 解压出的那一层直接含 msedgewebview2.exe\n` +
    `    3) 用 WEBVIEW2_FIXED_RUNTIME=<解压目录> 覆盖默认路径，或把它放到默认路径。\n` +
    `  不产出半成品：已中止（没带运行时的包，在精简版 Windows 上照样打不开）。`);
  process.exit(1);
}
console.log(`\n[build-release] ▶ 铺 WebView2 固定版运行时（裁剪档 ${WEBVIEW2_PROFILE}）→ ${join(RELEASE_DIR, WEBVIEW2_DIR)}`);
{
  const dst = join(RELEASE_DIR, WEBVIEW2_DIR);
  try {
    const st = stageWebView2(WEBVIEW2_SRC, dst, { profile: WEBVIEW2_PROFILE });
    for (const w of st.warnings) console.warn(`[build-release] ⚠️  ${w}`);
    // 复核：目录名/落点错了 main.rs 就找不到它，而那时机器上可能正好没有系统运行时
    //（stageWebView2 内部已按 REQUIRED_CORE 兜底校验，这里是第二道，防"改了函数忘了校验"）
    if (!existsSync(join(dst, "msedgewebview2.exe"))) {
      console.error(`[build-release] ❌ 铺完复核失败：${join(dst, "msedgewebview2.exe")} 不存在`);
      process.exit(1);
    }
    const srcMB = (st.keptBytes + st.removedBytes) / 1048576;
    console.log(`[build-release]   ✅ 运行时已就位（${WEBVIEW2_DIR}\\msedgewebview2.exe）：` +
      `${st.files} 文件 / ${(st.keptBytes / 1048576).toFixed(1)} MB` +
      `（源 ${srcMB.toFixed(1)} MB，删掉 ${st.removedFiles} 文件 / ${(st.removedBytes / 1048576).toFixed(1)} MB）`);
    // Win10 需要 AppContainer ACL（官方分发文档 Step 6）；失败只告警，不阻断构建。
    // ⚠️ 第 7 步 xcopy 到交付目录后要重跑（xcopy 不复制显式 ACE），见手册 §6.5.3。
    applyAppContainerAcl(dst, { log: (m) => console.log(`[build-release]   ${m.replace("[slim-webview2] ", "")}`) });
  } catch (e) {
    console.error(`[build-release] ❌ WebView2 运行时铺/裁剪失败：${e.message}\n` +
      `  不产出半成品：已中止（这份运行时就是"没有 Edge 的机器能不能打开"的唯一区别）。`);
    process.exit(1);
  }
}

// ── ④ 镜像进 target/release + 严格自检（必须在 tauri build 之后：它不刷新 python.exe）
run("sync-sidecar（镜像 binaries → target/release）", process.execPath, ["scripts/sync-sidecar.mjs"]);
run("sync-sidecar --require-target（构建后严格自检）", process.execPath, ["scripts/sync-sidecar.mjs", "--check", "--require-target"]);

// ── ⑤ 用户自助诊断脚本 `自检.bat` 落到 target/release（与 exe 同级）
//    —— 第 7 步手工拷贝时它自然跟着走；漏了它，用户就只剩"python.exe 一闪就没"可看。
//    **顺序铁律：先写、后查。** 反过来（先 --check）在干净/首次构建上必报"缺失"
//    并 process.exit(1) 中止整条链路 —— 那时 target/release 里还没有它（实测：本批
//    第一次接线就踩了，只因先前手工铺过一次才没暴露）。
run("stage-selftest（写入并复核）", process.execPath, ["scripts/stage-selftest.mjs"]);
run("stage-selftest --check（收尾自检）", process.execPath, ["scripts/stage-selftest.mjs", "--check"]);

console.log(`\n[build-release] ✅ 完成（${Math.round((Date.now() - t0) / 1000)} s）`);
console.log("[build-release] 产物：gui/src-tauri/target/release/（exe + python.exe + _internal + WebView2\\ + 自检.bat）");
console.log("[build-release] 部署按 docs/手动打包方法.md 第 7 步：**只拷五件 + README + AI接入.md**，");
console.log("                 （五件 = exe / python.exe / _internal / WebView2 / 自检.bat；");
console.log("                   漏 WebView2 ⇒ 精简版 Windows（无 Edge）上双击打不开）；");
console.log("                 不要 robocopy /MIR 整个 target/release（会把 deps/.fingerprint/mcnp_ui.pdb");
console.log("                 等 Rust 构建中间物灌进交付目录，且会覆盖掉 AI接入.md）。");
