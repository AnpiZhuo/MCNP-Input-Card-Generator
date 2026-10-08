/**
 * Monaco 本地化 —— **断网可用**的唯一入口。
 *
 * 背景：`@monaco-editor/react` 背后是 `@monaco-editor/loader`，而 loader 的默认 `paths.vs` 指向
 * jsdelivr 上的 monaco（即 cdn.jsdelivr.net/npm/monaco-editor@…/min/vs）—— 也就是说它会在
 * **运行时**去外网拉 monaco 本体。本程序是离线分发形态（README：「不需要联网」），断网时这条请求
 * 失败，而 `Editor` 组件失败时只 `console.error`、`isEditorReady` 永远为 false ⇒ 编辑区一片空白、
 * 中间永久停在「Loading...」，用户看不出到底怎么了。
 *
 * （本文件禁止出现带引号的外链字面量，`gui/test/monacoOffline.test.ts` 会扫。）
 *
 * 这里做两件事，缺一不可：
 *   1. 把**随包打包**的 monaco 实例交给 loader（`loader.config({ monaco })`）—— 它就不再注入任何
 *      script、不再发任何外部请求；
 *   2. 自己提供 core editor worker。monaco 的语言服务（ts/json/css/html）我们一个都没用，所以
 *      不需要它们的 worker —— 这也意味着那 9 MB 语言服务 worker **不会进包**（语言服务实现只活在
 *      worker 里，主线程的 register 模块只引 editor.api）。
 *
 * 必须以**副作用导入**在任何 `<Editor>` 挂载前执行（见 `McnpEditor.tsx` 顶部）。
 */
import * as monaco from "monaco-editor";
import editorWorker from "monaco-editor/editor/editor.worker.js?worker";
import { loader } from "@monaco-editor/react";

// 只装核心 editor worker：我们注册的是自制 Monarch 语法 + 补全/inline 补全，全在主线程。
self.MonacoEnvironment = { getWorker: () => new editorWorker() };

loader.config({ monaco });
