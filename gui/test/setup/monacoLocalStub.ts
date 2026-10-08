/**
 * 测试环境里的 Monaco 桩（vitest 全局 setup，见 `vite.config.ts` 的 `test.setupFiles`）。
 *
 * 为什么需要：`McnpEditor` 通过副作用导入 `./monacoLocal` 把**随包**的 monaco 交给 loader。于是只要
 * 某个测试渲染到编辑器（渲染整个几何页的那 4 个 dom 用例就是），monaco 本体就会被加载、并真的去
 * 创建编辑器 —— 而 jsdom 缺一堆布局 API（`matchMedia`、`ResizeObserver`、真实的
 * `getBoundingClientRect`）。后果是**与编辑器毫不相干**的用例一起变红：2026-10-08 本地化后实测
 * 6 个用例失败 / 17 个错误，而且每个碰到编辑器的测试文件都要多花 10–15 秒加载 monaco。
 *
 * 只桩这一个模块就够：那些用例断言的是几何页的表格、对话框与拖拽，编辑器在它们眼里本来就该是
 * 「不必初始化」的状态（本地化之前正是如此 —— loader 去 CDN 取脚本，jsdom 不执行外链 script，
 * 编辑器永远不就绪）。
 *
 * 卡片语法本身的行为断言在 `gui/test/mcnpCardSyntax.test.ts` —— 那里**直接**调 monaco 的
 * `editor.tokenize()`，不经过本桩。
 */
import { vi } from "vitest";

vi.mock("../../src/components/monacoLocal", () => ({}));
