import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(async () => ({
  plugins: [react()],
  clearScreen: false,
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
