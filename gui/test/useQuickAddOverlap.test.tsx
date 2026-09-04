// @vitest-environment jsdom
/**
 * useQuickAddOverlap — 深模块接口测试（seam = 公开返回：quickCheck/runCheck/applyChoice）。
 *
 * 三个场景直接通过接口驱动，验证「后端契约 + 补集决策 + 失败非静默」都被藏进实现：
 *   ① 无重叠 → onApplyResult 直接写回，quickCheck 保持 null
 *   ② 有重叠 → quickCheck 置位；applyChoice → onApplyResult 收到 overlapHandled+existingExprPatch
 *   ③ 请求失败 → onCheckFail（非阻塞警告）+ onApplyResult 仍写回（T2 不静默）
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useQuickAddOverlap } from "../src/utils/useQuickAddOverlap";
import type { QuickCellResult } from "../src/utils/quickCell";

function mkResult(num = "2"): QuickCellResult {
  return {
    surfacesText: `2 pz 5\n`,
    trCardsText: "",
    cells: [{ num, mat: "0", density: "", surfaces: "-2", impN: "0", impP: "", impE: "", comment: "TET" }],
    surfaceCount: 1,
    cellCount: 1,
  };
}

beforeEach(() => {
  (globalThis as any).fetch = vi.fn();
});
afterEach(() => {
  vi.restoreAllMocks();
});

describe("useQuickAddOverlap（深模块接口）", () => {
  it("无重叠 → onApplyResult 直接写回，quickCheck 保持 null", async () => {
    (globalThis as any).fetch.mockResolvedValue({ json: async () => ({ status: "ok", overlaps: [] }) });
    const onApply = vi.fn();
    const { result } = renderHook(() => useQuickAddOverlap({
      getExistingCells: () => [{ num: 1, mat: "0", surfaces: "-1" }],
      getSurfaces: () => "1 pz 0\n",
      getTrCards: () => "",
      onApplyResult: onApply,
    }));
    await act(async () => { await result.current.runCheck(mkResult()); });
    expect(onApply).toHaveBeenCalledTimes(1);
    expect(result.current.quickCheck).toBeNull();
  });

  it("有重叠 → quickCheck 置位；applyChoice(existing_hole) → 写回带 overlapHandled + 补集补丁", async () => {
    (globalThis as any).fetch.mockResolvedValue({ json: async () => ({
      status: "ok", overlaps: [{ a: 2, b: 1 }], recommended: "new_hole", zero_volume: [],
    }) });
    const onApply = vi.fn();
    const { result } = renderHook(() => useQuickAddOverlap({
      getExistingCells: () => [{ num: 1, mat: "0", surfaces: "-1" }],
      getSurfaces: () => "1 pz 0\n",
      getTrCards: () => "",
      onApplyResult: onApply,
    }));
    await act(async () => { await result.current.runCheck(mkResult()); });
    expect(result.current.quickCheck).not.toBeNull();
    expect(result.current.quickCheck!.existingNums).toEqual([1]);
    expect(result.current.quickCheck!.recommended).toBe("new_hole");

    await act(async () => { result.current.applyChoice("existing_hole"); });
    expect(onApply).toHaveBeenCalledTimes(1);
    const arg = onApply.mock.calls[0][0] as QuickCellResult;
    expect(arg.overlapHandled).toBe(true);
    expect(arg.existingExprPatch).toEqual([{ num: "1", surfaces: "-1 #2" }]);
    expect(arg.cells[0].surfaces).toBe("-2"); // 新栅元自身表达式不变
    expect(result.current.quickCheck).toBeNull();
  });

  it("请求失败 → onCheckFail 警告 + onApplyResult 仍写回（T2 非静默）", async () => {
    (globalThis as any).fetch.mockRejectedValue(new Error("backend boom"));
    const onApply = vi.fn();
    const onFail = vi.fn();
    const { result } = renderHook(() => useQuickAddOverlap({
      getExistingCells: () => [{ num: 1, mat: "0", surfaces: "-1" }],
      getSurfaces: () => "1 pz 0\n",
      getTrCards: () => "",
      onApplyResult: onApply,
      onCheckFail: onFail,
    }));
    await act(async () => { await result.current.runCheck(mkResult()); });
    expect(onFail).toHaveBeenCalledTimes(1);   // 非阻塞警告
    expect(onApply).toHaveBeenCalledTimes(1);  // 仍写回栅元
    expect(result.current.quickCheck).toBeNull();
  });
});
