/**
 * build-release.mjs — **一次跑对顺序**的完整发布构建（前端 + 外壳 + sidecar + 校验）。
 *
 * ## 用法
 *     cd gui && npm run build:release
 * 失败即非零退出，不会留下"半新半旧"的产物。
 *
 * ## 它根除的三个坑（2026-09-18/19 实测，症状都是"版本号新、后端旧"= 修复不生效）
 *
 * **坑 A｜落点冲突**：PyInstaller 默认写 `gui/dist/python/`，而 `vite build` 会**清空
 * `gui/dist/`**。于是"先 PyInstaller → 再 build:app"会把刚打好的 sidecar 删掉，
 * `sync-sidecar` 随后把 `binaries/` 里**上一次的 python.exe** 铺进 target/release，
 * 还报"✅ 已是最新"。⇒ 本脚本用 `--distpath dist_sidecar` 把两者物理分开。
 *
 * **坑 B｜增量缓存**：`gui/build/mcnp_sidecar/` 会残留上一次的 Analysis 结果，
 * PyInstaller 据此**复用旧模块字节码**。实测：`inputcard_mcp/server.py` 明明改了，
 * 新产物的 PYZ 里仍是 09-12 的旧代码；**只有删掉 `build/mcnp_sidecar` 才真正重编**。
 * ⇒ 本脚本每次构建前强制清缓存（这是"改了代码但没生效"的头号原因）。
 *
 * **坑 C｜binaries 是同步的源**：`sync-sidecar` 比对的是 `src-tauri/binaries/` 与
 * `target/release/`，**它不会自动去 `dist_sidecar/` 取新产物**。所以必须显式把
 * PyInstaller 产物覆盖进 `binaries/`（本脚本第 ③ 步），否则比对"一致"的是两份旧货。
 */
import { spawnSync } from "node:child_process";
import { cpSync, existsSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const GUI = resolve(HERE, "..");
/** PyInstaller 产物落点（与 vite 的 dist/ 分开 → 坑 A） */
const SIDECAR_DIST = join(GUI, "dist_sidecar");
/** PyInstaller 增量缓存（必须清 → 坑 B） */
const SIDECAR_BUILD = join(GUI, "build", "mcnp_sidecar");
/** Tauri 约定的 sidecar 源目录（同步的比较源 → 坑 C） */
const BINARIES = join(GUI, "src-tauri", "binaries");
const SIDECAR_SRC_NAME = "python-x86_64-pc-windows-msvc.exe";

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

// ① 前端 + Rust 外壳：**会清空 gui/dist**，所以必须排在 sidecar 之前
run("vite build（清空并重建 dist/）", npx, ["vite", "build"]);
run("tauri build（含 beforeBuildCommand 的预同步）", npx, ["tauri", "build"]);

// ② Python sidecar：清缓存（坑 B）→ 写到独立目录（坑 A）
if (existsSync(SIDECAR_BUILD)) {
  console.log(`[build-release] ▶ 清 PyInstaller 增量缓存（否则可能复用旧字节码）：${SIDECAR_BUILD}`);
  rmSync(SIDECAR_BUILD, { recursive: true, force: true });
}
if (existsSync(SIDECAR_DIST)) rmSync(SIDECAR_DIST, { recursive: true, force: true });
run("PyInstaller（生成 sidecar）", "python", [
  "-m", "PyInstaller", "--noconfirm", "--distpath", "dist_sidecar", "mcnp_sidecar.spec",
]);

const builtExe = join(SIDECAR_DIST, "python", "python.exe");
const builtInternal = join(SIDECAR_DIST, "python", "_internal");
if (!existsSync(builtExe) || !existsSync(builtInternal)) {
  console.error(`[build-release] ❌ PyInstaller 未产出 ${builtExe} 或 _internal`);
  process.exit(1);
}

// ③ 覆盖进 binaries（坑 C：binaries 才是 sync 的比较源）
console.log("\n[build-release] ▶ 覆盖 src-tauri/binaries/（sync 的比较源）");
cpSync(builtExe, join(BINARIES, SIDECAR_SRC_NAME));
rmSync(join(BINARIES, "_internal"), { recursive: true, force: true });
cpSync(builtInternal, join(BINARIES, "_internal"), { recursive: true });

// ④ 镜像进 target/release + 严格自检
run("sync-sidecar（镜像 binaries → target/release）", process.execPath, ["scripts/sync-sidecar.mjs"]);
run("sync-sidecar --require-target（构建后严格自检）", process.execPath, ["scripts/sync-sidecar.mjs", "--check", "--require-target"]);

// ⑤ 用户自助诊断脚本 `自检.bat` 落到 target/release（与 exe 同级）
//    —— 第 7 步手工拷贝时它自然跟着走；漏了它，用户就只剩"python.exe 一闪就没"可看。
//    **顺序铁律：先写、后查。** 反过来（先 --check）在干净/首次构建上必报"缺失"
//    并 process.exit(1) 中止整条链路 —— 那时 target/release 里还没有它（实测：本批
//    第一次接线就踩了，只因先前手工铺过一次才没暴露）。
run("stage-selftest（写入并复核）", process.execPath, ["scripts/stage-selftest.mjs"]);
run("stage-selftest --check（收尾自检）", process.execPath, ["scripts/stage-selftest.mjs", "--check"]);

console.log(`\n[build-release] ✅ 完成（${Math.round((Date.now() - t0) / 1000)} s）`);
console.log("[build-release] 产物：gui/src-tauri/target/release/（exe + python.exe + _internal + 自检.bat）");
console.log("[build-release] 部署按 docs/手动打包方法.md 第 7 步：**只拷四件套 + README + AI接入.md**，");
console.log("                 不要 robocopy /MIR 整个 target/release（会把 deps/.fingerprint/mcnp_ui.pdb");
console.log("                 等 Rust 构建中间物灌进交付目录，且会覆盖掉 AI接入.md）。");
