// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { openPtracWindow, openVolume3D } from "../../src/utils/windows";

/**
 * localStorage 桥写入失败的显式上报（2026-10-21 缺陷回归）
 *
 * 缺陷实录（部署版 CDP）：主窗口 console 打 `ptrac bridge write failed QuotaExceededError …`，
 * 但 `openPtracWindow` 把异常吞进 console.warn 后照样 invoke 开窗 ⇒ 子窗口读不到桥，
 * 用户只看到「没有 3D 径迹数据（请从主窗口「输出」标签页解析 PTRAC 后打开）」——
 * 症状指向「你没解析」，实际是「数据太大写不进 localStorage」。
 *
 * 契约：桥写不进去必须**当场失败**（抛错 → 调用方把 hint 显示在输出页），
 * 绝不允许「开一个读不到数据的空窗口」。
 */
function quotaError() {
  return new DOMException("Setting the value exceeded the quota.", "QuotaExceededError");
}

afterEach(() => { vi.restoreAllMocks(); });

describe("桥写入失败必须抛错", () => {
  it("ptrac：setItem 抛 QuotaExceededError → openPtracWindow rejects（不静默开窗）", async () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw quotaError(); });
    await expect(openPtracWindow({ ptracPath: "D:/x/ptrac" })).rejects.toThrow(/配额|写入失败|过大/);
  });

  it("ptrac：序列化后超过配额上限 → 不尝试写入、直接 rejects 并说明体积", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    await expect(openPtracWindow({ big: "x".repeat(5_000_000) })).rejects.toThrow(/过大/);
    expect(setItem).not.toHaveBeenCalled();
  });

  it("volume：setItem 抛 QuotaExceededError → openVolume3D rejects（同一根因，3D 结果窗口同样会中招）", async () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw quotaError(); });
    await expect(openVolume3D({ cells: [] })).rejects.toThrow(/配额|写入失败|过大/);
  });

  it("正常体积的桥照旧写入成功（不误伤）", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    // jsdom 无 Tauri：invoke 必然失败 → 返回 false（浏览器模式 fallback），但写入必须已发生
    const ok = await openPtracWindow({ ptracPath: "D:/x/ptrac", maxTracks: 10 });
    expect(ok).toBe(false);
    expect(setItem).toHaveBeenCalledTimes(1);
    expect(String(setItem.mock.calls[0][1])).toContain("D:/x/ptrac");
  });
});
