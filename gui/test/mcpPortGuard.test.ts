// @vitest-environment jsdom
/**
 * 8100 端口守卫：本机已有 MCP over HTTP 在跑时**不得**再 spawn 第二个实例。
 *
 * 为什么单独锁死：`startMcpHttp` 原先没有任何探测（而同文件里 5001 有守卫），
 * 残留旧进程占着 8100 时新进程 bind 失败即退，前端却以为自己在用新实例、
 * 实际读写旧进程里的旧工作区 ⇒ 界面莫名回弹且无任何报错（2026-09-17 实证）。
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { isLocalPortServing } from "../src/utils/backend";

afterEach(() => { vi.restoreAllMocks(); });

describe("isLocalPortServing", () => {
  it("端口有服务（任何响应，含 404/405）→ true", async () => {
    const f = vi.fn(async () => ({ ok: false, status: 404 }));
    (globalThis as any).fetch = f;
    expect(await isLocalPortServing(8100)).toBe(true);
    const [url, init] = f.mock.calls[0] as any;
    // 走 CSP 允许的 http 环回地址，且不吃缓存
    expect(url).toBe("http://127.0.0.1:8100/");
    expect(init.cache).toBe("no-store");
  });

  it("端口没人监听（连接被拒）→ false", async () => {
    (globalThis as any).fetch = vi.fn(async () => { throw new TypeError("Failed to fetch"); });
    expect(await isLocalPortServing(8100)).toBe(false);
  });

  it("超时/中止 → false（不抛，让调用方照常拉起 sidecar）", async () => {
    (globalThis as any).fetch = vi.fn(async () => { throw new DOMException("timeout", "TimeoutError"); });
    expect(await isLocalPortServing(8100)).toBe(false);
  });
});
