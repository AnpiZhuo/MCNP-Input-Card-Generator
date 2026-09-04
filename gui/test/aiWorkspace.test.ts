// @vitest-environment jsdom
/**
 * aiWorkspace 纯函数：MCP over HTTP 的工作区通道（同步 PUT / 回显 GET 的 URL 与请求封装）。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { aiMcpUrl, aiWorkspaceUrl, putWorkspace, getWorkspace } from "../src/utils/aiWorkspace";

beforeEach(() => { (globalThis as any).fetch = vi.fn(); });
afterEach(() => { vi.restoreAllMocks(); });

describe("aiWorkspace", () => {
  it("URL 指向 MCP over HTTP 本机环回端口", () => {
    expect(aiMcpUrl()).toBe("http://127.0.0.1:8100/mcp");
    expect(aiWorkspaceUrl()).toBe("http://127.0.0.1:8100/workspace");
  });

  it("putWorkspace 成功时返回 revision", async () => {
    (globalThis as any).fetch.mockResolvedValue({ ok: true, json: async () => ({ ok: true, revision: 7 }) });
    const r = await putWorkspace({ cells: [] });
    expect(r.ok).toBe(true);
    expect(r.revision).toBe(7);
    // 以 { deck } 形式 PUT
    const [url, init] = (globalThis as any).fetch.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8100/workspace");
    expect(JSON.parse(init.body).deck).toEqual({ cells: [] });
  });

  it("putWorkspace/getWorkspace 网络失败 → ok:false / null（不抛）", async () => {
    (globalThis as any).fetch.mockRejectedValue(new Error("down"));
    expect(await putWorkspace({})).toEqual({ ok: false, revision: 0 });
    expect(await getWorkspace()).toBeNull();
  });
});
