/**
 * stage-selftest.mjs — 把仓库根的 `自检.bat` 铺进交付产物目录（**与 exe 同级**）。
 *
 * ## 为什么要有这一步
 * `自检.bat` 是给**最终用户**用的：后端没起来时双击一次，就能把
 * "python.exe 一闪就没"变成一段可读日志 + 一个 ASCII 结论（见脚本内 [RESULT]）。
 * 但它必须**躺在被交付的那个目录里**（和 `MCNP 输入卡生成器.exe`、`python.exe`、
 * `_internal\` 同级）才有意义 —— 用户不会去源码仓库里找它。
 *
 * 而本项目的交付是**手工拷贝**（`docs/手动打包方法.md` 第 7 步：
 * "只拷三件套 + README + AI接入.md"）。手写清单最容易漏新文件，
 * 所以这里把它做成构建的一步：先烙进 `target/release/`，
 * 第 7 步拷 `target/release` 时它自然跟着走，`build:release` 也会显式跑一遍。
 *
 * ## 语义
 *     node scripts/stage-selftest.mjs              # 拷贝 + 复核（默认）
 *     node scripts/stage-selftest.mjs --check      # 只校验，不写盘（不一致即退出码 1）
 *
 * 源缺失 / 目标缺失（且非首次构建）/ 拷完字节不一致 一律**非零退出**：
 * 这个文件是"用户唯一能自助取证"的东西，静默漏掉等于又回到"让用户猜"。
 */
import { copyFileSync, existsSync, mkdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const GUI = resolve(HERE, "..");
const REPO = resolve(GUI, "..");
const DST_DIR = join(GUI, "src-tauri", "target", "release");

/** 源（仓库根，与 README.md / AI接入.md 同处 —— 那两份也是这么交付的）与产物名 */
export const SELFTEST_SRC = join(REPO, "自检.bat");
export const SELFTEST_NAME = "自检.bat";
export { DST_DIR as SELFTEST_DST_DIR };

/**
 * 自检脚本必须含的关键判据（防止它被改坏/改空还"看起来在跑"）。
 * 这些字符串就是脚本对外承诺的契约：引导错误识别、引导探针、端口探测、结论标记。
 */
export const REQUIRED_MARKERS = [
  "Failed to load Python DLL",   // 缺 _internal 的判定串
  "--meshtal-worker",            // 引导探针（不占端口）
  "5001",                        // 后端端口
  "[RESULT]",                    // 机器可读结论标记
  "MCNP自检报告.txt",             // 报告文件名 —— 用户被要求"把这个文件发回"，
                                 // 改名就等于让收件人找不到附件
  "环境变量",                    // 报告必须带环境变量（PATH/DATAPATH 是判"版本装在哪/吃哪套库"的关键）
];

/** 校验源文件存在且内容含全部关键判据；返回读到的文本。 */
export function assertSourceOk(src = SELFTEST_SRC) {
  if (!existsSync(src)) {
    throw new Error(
      `自检脚本源缺失：${src}\n` +
      `  它必须留在仓库根（会被拷进交付目录，与 exe 同级）。`);
  }
  const text = readFileSync(src, "utf8");
  const missing = REQUIRED_MARKERS.filter((m) => !text.includes(m));
  if (missing.length) {
    throw new Error(
      `自检脚本内容不完整，缺少关键判据：${missing.join(" / ")}\n` +
      `  （这些串是它对外的契约，删掉就等于让用户又拿不到结论）`);
  }
  return text;
}

/** 目标是否已与源一致（存在 + 字节数相同）。 */
export function isStaged(src = SELFTEST_SRC, dstDir = DST_DIR) {
  const dst = join(dstDir, SELFTEST_NAME);
  if (!existsSync(dst)) return false;
  try {
    return statSync(dst).size === statSync(src).size;
  } catch {
    return false;
  }
}

function main() {
  const checkOnly = process.argv.includes("--check");
  let text;
  try {
    text = assertSourceOk();
  } catch (e) {
    console.error(`[stage-selftest] ❌ ${e.message}`);
    process.exit(1);
  }

  const dst = join(DST_DIR, SELFTEST_NAME);
  if (isStaged()) {
    console.log(`[stage-selftest] ✅ ${SELFTEST_NAME} 已在 ${DST_DIR}（${statSync(dst).size} B，与源一致）`);
    return;
  }

  if (checkOnly) {
    console.error(
      `[stage-selftest] ❌ ${DST_DIR}\\${SELFTEST_NAME} 缺失或与源不一致（--check 模式不写盘）\n` +
      `  修法：node scripts/stage-selftest.mjs`);
    process.exit(1);
  }

  if (!existsSync(DST_DIR)) {
    // 首次构建 / 还没跑 tauri build：不是错误，只是没地方可铺
    console.log(`[stage-selftest] 目标目录不存在，跳过：${DST_DIR}\n` +
                `  （首次构建正常：tauri build 之后本步会真正落地）`);
    return;
  }

  mkdirSync(DST_DIR, { recursive: true });
  copyFileSync(SELFTEST_SRC, dst);
  if (!isStaged()) {
    console.error(`[stage-selftest] ❌ 拷贝后复核不一致：${dst}\n` +
                  `  交付目录缺了它，用户就没法自助定位"后端起不来"。`);
    process.exit(1);
  }
  console.log(`[stage-selftest] → 已铺 ${SELFTEST_NAME} 到 ${DST_DIR}（${text.length} 字符，复核一致 ✅）`);
  console.log("[stage-selftest]   部署时它会跟着 target/release 一起进交付目录（与 exe 同级）");
}

// 仅在被直接执行时跑 main（被测试 import 时不产生副作用）
if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  main();
}
