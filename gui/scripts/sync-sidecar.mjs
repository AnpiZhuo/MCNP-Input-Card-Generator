/**
 * sidecar 时效同步 / 校验（打包手册 6.2 坑的根治）。
 *
 * ## 为什么要这一步
 * `tauri build` 是**增量编译**：它重建主 exe，但**不保证**把 `binaries/` 里最新的
 * sidecar（`python.exe` + `_internal/`）刷新进 `target/release/`。历史上每次打包都中：
 * `target/release/python.exe` / `_internal/` 停留在上一版 ⇒ 步骤 7 复制出去的就是
 * **旧后端**，产物"版本号新、后端旧"（缺本次修复）。
 *
 * ## 为什么放在 `beforeBuildCommand` 而不是"构建之后再同步"
 * sidecar 是**编译期**被 Rust 侧拷进 `target/release/` 的（随后可能删除 `binaries/`
 * 源）。所以"构建后再同步"= 又一个人工步骤（就是原来的 6.2）。改成**构建前先对齐**：
 * `tauri build` 无论走哪条路径，源与目标都已一致 ⇒ 6.2 从"每次都踩"降级为"几乎不用查"。
 *
 * ## 用法（在 gui/ 下）
 *     node scripts/sync-sidecar.mjs           # 同步 + 校验（默认，afterBuildCommand 调用）
 *     node scripts/sync-sidecar.mjs --check   # 只校验，不写盘（不一致则退出码 1）
 *
 * 无 `target/release`（首次打包）→ 跳过：此时不可能有旧产物。
 */
import { existsSync, mkdirSync, readdirSync, statSync, copyFileSync, rmSync } from "node:fs";
import { dirname, join, resolve, relative } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
export const TAURI_DIR = resolve(HERE, "..", "src-tauri");
export const SRC_DIR = join(TAURI_DIR, "binaries");
export const DST_DIR = join(TAURI_DIR, "target", "release");
/** sidecar 源文件名（Tauri 的 target triple 命名）与构建产物中的名字 */
export const SIDECAR_SRC = "python-x86_64-pc-windows-msvc.exe";
export const SIDECAR_DST = "python.exe";

/** 递归列出 (相对路径 → 字节数)，排序后便于比较。忽略目录本身。 */
export function manifest(root) {
  const out = [];
  const walk = (dir) => {
    for (const ent of readdirSync(dir, { withFileTypes: true })) {
      const p = join(dir, ent.name);
      if (ent.isDirectory()) walk(p);
      else if (ent.isFile()) out.push([relative(root, p).replace(/\\/g, "/"), statSync(p).size]);
    }
  };
  walk(root);
  return out.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
}

/**
 * 比较两个目录树。返回 {same, missing, extra, sizeDiff, nSrc, nDst}。
 * 只比"路径集合 + 大小"——字节级比对 3 万个文件太慢，而 sidecar 每次是整体重建，
 * 大小不同足以判定陈旧（实测两版 python.exe 大小确实不同）。
 */
export function compareTrees(srcRoot, dstRoot) {
  const src = manifest(srcRoot);
  const dst = manifest(dstRoot);
  const dstMap = new Map(dst);
  const srcMap = new Map(src);
  const missing = src.filter(([p]) => !dstMap.has(p)).map(([p]) => p);
  const extra = dst.filter(([p]) => !srcMap.has(p)).map(([p]) => p);
  const sizeDiff = src
    .filter(([p, n]) => dstMap.has(p) && dstMap.get(p) !== n)
    .map(([p, n]) => `${p} (src ${n} B / dst ${dstMap.get(p)} B)`);
  return {
    same: missing.length === 0 && extra.length === 0 && sizeDiff.length === 0,
    missing, extra, sizeDiff, nSrc: src.length, nDst: dst.length,
  };
}

/** 把 srcRoot 完整镜像到 dstRoot（先删 dst 的 sidecar 文件与 _internal，再整树复制）。 */
export function mirrorSidecar(srcRoot, dstRoot) {
  for (const name of [SIDECAR_DST]) {
    const p = join(dstRoot, name);
    if (existsSync(p)) rmSync(p, { force: true });
  }
  const dstInternal = join(dstRoot, "_internal");
  if (existsSync(dstInternal)) rmSync(dstInternal, { recursive: true, force: true });
  mkdirSync(dstRoot, { recursive: true });
  copyFileSync(join(srcRoot, SIDECAR_SRC), join(dstRoot, SIDECAR_DST));
  copyTree(join(srcRoot, "_internal"), dstInternal);
}

function copyTree(src, dst) {
  mkdirSync(dst, { recursive: true });
  for (const ent of readdirSync(src, { withFileTypes: true })) {
    const s = join(src, ent.name);
    const d = join(dst, ent.name);
    if (ent.isDirectory()) copyTree(s, d);
    else if (ent.isFile()) copyFileSync(s, d);
  }
}

function main(argv) {
  const checkOnly = argv.includes("--check");
  if (!existsSync(SRC_DIR) || !existsSync(join(SRC_DIR, SIDECAR_SRC))) {
    console.log(`[sync-sidecar] 源不存在，跳过：${SRC_DIR}\\${SIDECAR_SRC}`);
    console.log("[sync-sidecar] （首次打包时正常：先跑第 4/5 步生成 sidecar）");
    return 0;
  }
  if (!existsSync(DST_DIR)) {
    console.log(`[sync-sidecar] 目标不存在，跳过：${DST_DIR}（首次打包正常）`);
    return 0;
  }
  const srcSidecar = statSync(join(SRC_DIR, SIDECAR_SRC)).size;
  const dstExe = join(DST_DIR, SIDECAR_DST);
  const dstInternal = join(DST_DIR, "_internal");
  const srcInternal = join(SRC_DIR, "_internal");

  if (!existsSync(dstExe) || !existsSync(dstInternal)) {
    console.log("[sync-sidecar] target/release 缺 sidecar → 复制新 sidecar（6.2 坑命中）");
    if (!checkOnly) mirrorSidecar(SRC_DIR, DST_DIR);
    return 0;
  }
  const cmp = compareTrees(srcInternal, dstInternal);
  const exeSame = statSync(dstExe).size === srcSidecar;
  if (exeSame && cmp.same) {
    console.log(`[sync-sidecar] ✅ sidecar 已是最新（${cmp.nSrc} 个文件，python.exe ${srcSidecar} B）`);
    return 0;
  }
  console.log("[sync-sidecar] ⚠️ target/release 的 sidecar 陈旧（tauri 增量编译坑）——");
  if (!exeSame) console.log(`    python.exe 大小不符`);
  if (cmp.missing.length) console.log(`    缺 ${cmp.missing.length} 个文件，如：${cmp.missing.slice(0, 3).join(", ")}`);
  if (cmp.extra.length) console.log(`    多 ${cmp.extra.length} 个文件，如：${cmp.extra.slice(0, 3).join(", ")}`);
  if (cmp.sizeDiff.length) console.log(`    大小不符 ${cmp.sizeDiff.length} 个，如：${cmp.sizeDiff.slice(0, 3).join("; ")}`);
  if (checkOnly) {
    console.log("[sync-sidecar] --check 模式：不写盘，退出码 1");
    return 1;
  }
  mirrorSidecar(SRC_DIR, DST_DIR);
  const after = compareTrees(srcInternal, dstInternal);
  const ok = after.same && statSync(dstExe).size === srcSidecar;
  console.log(`[sync-sidecar] → 已用 binaries/ 覆盖 target/release：${ok ? "复核一致 ✅" : "复核仍不一致 ❌"}`);
  return ok ? 0 : 1;
}

// 仅在直接执行时跑 main（被 import 时不跑，便于单测复用 compareTrees/manifest）
const invoked = process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));
if (invoked) process.exit(main(process.argv.slice(2)));
