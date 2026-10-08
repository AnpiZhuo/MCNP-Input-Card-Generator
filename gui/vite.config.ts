import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { readdirSync } from "node:fs";
import { join } from "node:path";

/**
 * 丢掉 monaco 自带的「语言定义 + 语言服务」（实测省 ~10 MB）。
 *
 * 为什么安全：我们只注册自制 Monarch 语法（`src/components/mcnpCardSyntax.ts`），
 * **一个语言服务都没用**（没有 typescriptDefaults / jsonDefaults / css / html），补全与幽灵提示都走
 * 主线程的 `editor/contrib/**` —— 那些**不动**。要裁的两处都只在 monaco 的两个聚合入口里被引用：
 *   - `languages/definitions/**` 是**副作用导入**（import '../languages/definitions/abap/register.js'）；
 *   - `languages/features/**` 是**命名空间再导出**（`import * as X …; export { X as css }`）——
 *     换成空模块后 `X` 只是空命名空间对象，语法上完全合法。
 *
 * 为什么必须裁：`languages/features/<服务>/workerManager.js` 里有
 * `new Worker(new URL('ts.worker.js', import.meta.url), { type: "module" })`，**Vite 会静态识别并
 * 直接产出 worker chunk**（实测 9.2 MB：ts.worker 7.0 MB + css 1.06 MB + html 718 KB + json 408 KB）。
 * 这跟我们在 `MonacoEnvironment` 里覆写 `getWorker` **无关** —— 那是另一条创建路径。
 *
 * ⚠️ 本裁剪依赖 monaco 的目录约定，改了就会**静默失效**（包悄悄胖 10 MB）。因此 closeBundle 里加了
 * 一道构建期闸门：`dist/assets` 里除 `editor.worker` 外出现任何语言服务 worker 就直接失败。
 */
function dropMonacoLanguageServices() {
  const STUB = "\0monaco-languages-dropped";
  const LANG_DIRS = /[/\\]languages[/\\](features|definitions)[/\\]/;
  const SERVICE_WORKER = /^(ts|css|html|json)\.worker-.*\.js$/;
  let assetsDir = "";

  return {
    name: "drop-monaco-language-services",
    enforce: "pre" as const,
    configResolved(config: { root: string; build: { outDir: string } }) {
      assetsDir = join(config.root, config.build.outDir, "assets");
    },
    resolveId(source: string) {
      return LANG_DIRS.test(source) ? STUB : null;
    },
    load(id: string) {
      return id === STUB ? "export {};" : null;
    },
    closeBundle() {
      let leftovers: string[];
      try {
        leftovers = readdirSync(assetsDir).filter((f) => SERVICE_WORKER.test(f));
      } catch {
        return; // 没产出 assets（例如只跑 dev）就没什么可查的
      }
      if (leftovers.length) {
        throw new Error(
          "[drop-monaco-language-services] 裁剪失效：产物里出现了语言服务 worker " +
            `${leftovers.join(", ")}（多半是 monaco-editor 改了目录约定，` +
            `本插件现按 ${LANG_DIRS} 匹配）。请核对后更新本插件，否则交付包会多背约 10 MB。`,
        );
      }
    },
  };
}

export default defineConfig(async () => ({
  plugins: [react(), dropMonacoLanguageServices()],
  clearScreen: false,
  // vitest 也读这份配置（此前项目里没有任何 vitest 配置）。setupFiles 里唯一一件事是把
  // Monaco 本地化模块桩掉 —— 否则渲染到编辑器的 dom 用例会被 jsdom 缺的布局 API 带红，
  // 详见 test/setup/monacoLocalStub.ts。
  test: {
    setupFiles: ["test/setup/monacoLocalStub.ts"],
  },
  server: { port: 1420, strictPort: true },
  envPrefix: ["VITE_", "TAURI_"],
  resolve: {
    alias: {
      /**
       * ⚠️ `svg2pdf.js` 的 package.json 没写 `exports`，Vite 会按 `main` 取到
       * **UMD** 构建（`dist/svg2pdf.umd.min.js`）——那份在 ESM 里加载即崩：
       * `TypeError: Cannot read properties of undefined (reading 'jsPDF')`
       * （它指望外面有个全局 `jspdf`）。实测 2026-09-17：同一个探测用例走 UMD **红**、
       * 走 ES 构建 **绿**（正常产出 `%PDF-` 头）。所以这里把裸导入钉到 ES 构建：
       * 裸导入与 `dist/svg2pdf.es.min.js` 都指向同一份文件，两条路都不会再踩。
       */
      "svg2pdf.js": "svg2pdf.js/dist/svg2pdf.es.min.js",
    },
  },
}));
