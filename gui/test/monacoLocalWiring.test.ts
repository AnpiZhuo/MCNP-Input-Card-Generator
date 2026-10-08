// @vitest-environment jsdom
/**
 * Monaco 本地化接线的**行为**断言（纯文本的源码守卫在 `monacoOffline.test.ts`）。
 *
 * 为什么需要这一条：产物里**必然**留着 `@monaco-editor/loader` 自带的默认 CDN 地址字符串 ——
 * 那是它的内置默认值，我们改不掉（`loader.config` 只是让 `init()` 不再走那条路）。所以
 * 「grep 产物里没有 jsdelivr」这条根本查不了。能查的是**行为**：
 *   loader 是否已经拿到我们交给它的 monaco 实例 —— 拿到了，`init()` 就直接 resolve 它、
 *   永远不会去注入那个 `<script>`。
 *
 * monaco 与 worker 入口都桩掉：这里要验的是接线，不是 monaco 本身。
 */
import { describe, expect, it, vi } from "vitest";

// 全局 setup（test/setup/monacoLocalStub.ts）为了不拖累那些渲染几何页的 dom 用例，把
// monacoLocal 整个桩掉了。本文件恰恰要验它的**真实行为**，所以这里取消那个桩。
vi.unmock("../src/components/monacoLocal");

vi.mock("monaco-editor", () => ({ editor: { create: () => ({}) }, languages: {} }));
vi.mock("monaco-editor/editor/editor.worker.js?worker", () => ({ default: class FakeWorker {} }));

import { loader } from "@monaco-editor/react";
import "../src/components/monacoLocal";

const getInstance = () =>
  (loader as unknown as { __getMonacoInstance(): unknown }).__getMonacoInstance();
const env = () => (self as unknown as { MonacoEnvironment?: { getWorker(): unknown } }).MonacoEnvironment;

describe("Monaco 本地化接线", () => {
  it("loader 已拿到随包的 monaco 实例（⇒ init 不会去取 CDN 默认地址）", () => {
    expect(getInstance()).toBeTruthy();
  });

  it("没有往文档里注入任何外部 script", () => {
    expect(document.querySelectorAll("script[src]")).toHaveLength(0);
  });

  it("MonacoEnvironment.getWorker 已接管（worker 由随包产物提供）", () => {
    expect(typeof env()?.getWorker).toBe("function");
    expect(() => env()!.getWorker()).not.toThrow();
  });
});
