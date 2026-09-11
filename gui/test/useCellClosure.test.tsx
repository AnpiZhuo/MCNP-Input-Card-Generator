// @vitest-environment jsdom
/**
 * useCellClosure — 深模块 hook 测试（TD-30）。
 *
 * 覆盖 seam = 公开返回：`refresh()` / `statusOf(num)` / `loading` / `report`。
 * 重点锁两条**曾经出错**的行为：
 *   ① **同长度编辑必须重发请求**（T3 FE-21c 回归锁）：指纹旧实现是「三要素 length 拼接」，
 *      内容变了但长度没变（如材料号 1→2）会命中缓存、**静默返回旧报告**。现指纹为内容 JSON，
 *      本用例用「等长但不同内容」的两份 cells 直接钉住该回归。
 *   ② **同 deck 重复 refresh 不得重复请求**（惰性 + 缓存语义，避免无谓拉起 FreeCAD 子进程）。
 *
 * 另覆盖：挂载不自动请求（惰性）、成功写回 report、statusOf 数字/字符串同键、
 * 后端非 ok / 网络异常时静默保留上次结果且 loading 复位。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useCellClosure } from "../src/utils/useCellClosure";
import type { CellClosureDeck } from "../src/utils/useCellClosure";

/** 单栅元 deck（cells 内容可换，长度保持不变以便构造「同长度编辑」） */
function deck(mat: string): CellClosureDeck {
  return {
    surfaces: "1 pz 0\n",
    cells: [{ number: 1, material: mat, density: "-1.0", surface_expr: "-1" }],
    tr_cards: "",
  };
}

function okReport(cellNum = 1) {
  return { json: async () => ({ status: "ok", closure_report: { [cellNum]: { status: "closed", volume: 1.5 } } }) };
}

let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetchMock = vi.fn(async () => okReport());
  (globalThis as unknown as { fetch: unknown }).fetch = fetchMock;
});
afterEach(() => {
  vi.restoreAllMocks();
});

describe("useCellClosure（惰性 + 指纹缓存 + 回归锁）", () => {
  it("惰性：挂载不请求（不无谓拉起后端 FreeCAD 子进程）", () => {
    renderHook(() => useCellClosure(() => deck("1")));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refresh() 后才 POST /api/check-cell-closure，body 含 surfaces/cells/tr_cards", async () => {
    const { result } = renderHook(() => useCellClosure(() => deck("1")));
    await act(async () => { await result.current.refresh(); });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(String(url)).toContain("/api/check-cell-closure");
    expect(init.method).toBe("POST");
    const body = JSON.parse(String(init.body));
    expect(body.surfaces).toBe("1 pz 0\n");
    expect(body.tr_cards).toBe("");
    expect(body.cells).toHaveLength(1);
  });

  it("成功 → report 写入 + statusOf 取到该栅元（数字与字符串同键）；loading 复位", async () => {
    const { result } = renderHook(() => useCellClosure(() => deck("1")));
    await act(async () => { await result.current.refresh(); });

    expect(result.current.loading).toBe(false);
    expect(result.current.statusOf(1)?.status).toBe("closed");
    expect(result.current.statusOf("1")?.status).toBe("closed");
    expect(result.current.statusOf(999)).toBeUndefined();
  });

  it("同 deck 重复 refresh 不重复请求（指纹缓存早退，且保留上次 report）", async () => {
    const { result } = renderHook(() => useCellClosure(() => deck("1")));
    await act(async () => { await result.current.refresh(); });
    await act(async () => { await result.current.refresh(); });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(result.current.statusOf(1)?.status).toBe("closed");
  });

  it("★回归锁：内容改变但**长度不变** → 必须重新请求（旧实现按 length 拼指纹会漏）", async () => {
    // 1 → 2 与 1 → 10 属等长；此处 material "1" → "2" 为同长度不同内容
    const first = deck("1");
    const second = deck("2");
    expect(JSON.stringify(first.cells).length).toBe(JSON.stringify(second.cells).length);

    let cur = first;
    const { result } = renderHook(() => useCellClosure(() => cur));

    await act(async () => { await result.current.refresh(); });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // 同长度编辑：旧指纹（length 拼接）会命中缓存 → 只有 1 次请求（回归即在此暴露）
    cur = second;
    await act(async () => { await result.current.refresh(); });
    expect(fetchMock).toHaveBeenCalledTimes(2);

    // 且第二次请求真的带上了新内容
    const body = JSON.parse(String((fetchMock.mock.calls[1] as [string, RequestInit])[1].body));
    expect(body.cells[0].material).toBe("2");
  });

  it("surfaces 内容改变（同长度）同样重发", async () => {
    let surfaces = "1 pz 0\n";
    const { result } = renderHook(() =>
      useCellClosure(() => ({ surfaces, cells: [], tr_cards: "" })));
    await act(async () => { await result.current.refresh(); });
    surfaces = "1 pz 9\n"; // 等长
    await act(async () => { await result.current.refresh(); });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("后端 status !== 'ok' → 静默降级、不写 report、loading 复位、不抛错", async () => {
    fetchMock.mockResolvedValue({ json: async () => ({ status: "error", message: "FreeCAD 不可用" }) });
    const { result } = renderHook(() => useCellClosure(() => deck("1")));
    await act(async () => { await result.current.refresh(); });

    expect(result.current.loading).toBe(false);
    expect(result.current.report).toBeNull();
    expect(result.current.statusOf(1)).toBeUndefined();
  });

  it("网络异常 → 静默保留上次结果、loading 复位、不抛错", async () => {
    let surfaces = "1 pz 0\n";
    const { result } = renderHook(() =>
      useCellClosure(() => ({ surfaces, cells: [{ number: 1, material: "1" }], tr_cards: "" })));

    // 先成功一次 → report 有值
    await act(async () => { await result.current.refresh(); });
    expect(result.current.statusOf(1)?.status).toBe("closed");

    // 换一版 deck（触发新指纹）后让请求失败 → 必须保留上次 report 而非清空
    surfaces = "1 pz 9\n";
    fetchMock.mockRejectedValue(new Error("backend boom"));
    await act(async () => { await result.current.refresh(); });

    expect(result.current.loading).toBe(false);
    expect(result.current.report).not.toBeNull();
    expect(result.current.statusOf(1)?.status).toBe("closed"); // 旧结果仍在
  });
});
