/// <reference types="vite/client" />

// 加这行的直接原因：`monacoLocal.ts` 用 Vite 的 `?worker` 后缀导入 worker 入口
// （`monaco-editor/editor/editor.worker.js?worker`），这个后缀的模块声明由 vite/client 提供，
// 否则 tsc 会报「找不到模块」。它同时带来 `import.meta.env` 与静态资源（css/图片）的类型声明。
