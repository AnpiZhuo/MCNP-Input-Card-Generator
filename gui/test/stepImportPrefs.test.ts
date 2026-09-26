// @vitest-environment jsdom
/**
 * `gui/src/utils/stepImportPrefs.ts` 单测。
 *
 * 锁死的契约（用户要求：「保留用户设置的内容，开启和关闭都记忆，
 * 就算程序主页面那个清空点了也不要改」）：
 *   1. 落在**独立键** `mcnp_step_import_v1` 上 —— 主界面「清空」只删
 *      `mcnp_workspace_v1`，所以清空工作区**不影响**导入设置；
 *   2. `false` 必须存得住（"关"也是一个决定），而 `undefined`/`""` 不落盘
 *      （= 没动过，用 GEOUNED 默认）—— 这就是"开启和关闭都记忆"的根；
 *   3. 坏数据/异版本/存储异常一律**当作没有**，绝不让持久化影响导入。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { loadPrefs, savePrefs } from "../src/utils/stepImportPrefs";

const KEY = "mcnp_step_import_v1";
const WORKSPACE_KEY = "mcnp_workspace_v1";

beforeEach(() => localStorage.clear());
afterEach(() => { vi.restoreAllMocks(); localStorage.clear(); });

describe("stepImportPrefs 往返与三态语义", () => {
  it("存得住、读得回（字符串与布尔都保留类型）", () => {
    savePrefs({ simplify: "voidfull", maxSurf: "20", cutSolids: true, sortEnclosure: false });
    const got = loadPrefs();
    expect(got.simplify).toBe("voidfull");
    expect(got.maxSurf).toBe("20");
    expect(got.cutSolids).toBe(true);
    expect(got.sortEnclosure).toBe(false);
  });

  it("显式 false 必须落盘（「关」也是一个决定，重启后仍是关）", () => {
    savePrefs({ cutSolids: false });
    expect(JSON.parse(localStorage.getItem(KEY)!).vals.cutSolids).toBe(false);
    expect(loadPrefs().cutSolids).toBe(false);
  });

  it("没动过的项不落盘：undefined 与空串都被剥掉", () => {
    savePrefs({ maxSurf: "20", simplify: undefined, debug: "", distance: "" });
    expect(Object.keys(JSON.parse(localStorage.getItem(KEY)!).vals)).toEqual(["maxSurf"]);
  });

  it("空对象 = 清空（「全部恢复默认」的自然结果）", () => {
    savePrefs({ maxSurf: "20", cutSolids: true });
    savePrefs({});
    expect(loadPrefs()).toEqual({});
  });

  it("存的是带版本号的信封（便于将来改结构时识别）", () => {
    savePrefs({ maxSurf: "20" });
    const raw = JSON.parse(localStorage.getItem(KEY)!);
    expect(raw.version).toBe(1);
    expect(raw.vals).toEqual({ maxSurf: "20" });
  });
});

describe("stepImportPrefs 与「清空工作区」互不影响", () => {
  it("删掉工作区键后，导入设置还在", () => {
    localStorage.setItem(WORKSPACE_KEY, JSON.stringify({ version: 1, deck: {} }));
    savePrefs({ maxSurf: "20", cutSolids: true });

    // 复刻 App.tsx handleClear 的动作（只删工作区键，不是 localStorage.clear()）
    localStorage.removeItem(WORKSPACE_KEY);

    expect(loadPrefs()).toMatchObject({ maxSurf: "20", cutSolids: true });
  });

  it("两个键是分开的，互不覆盖", () => {
    localStorage.setItem(WORKSPACE_KEY, "工作区");
    savePrefs({ maxSurf: "20" });
    expect(localStorage.getItem(WORKSPACE_KEY)).toBe("工作区");
    expect(localStorage.getItem(KEY)).toContain("maxSurf");
  });
});

describe("stepImportPrefs 容错：坏数据当作没有", () => {
  it("JSON 坏了 → 空对象（不是抛异常）", () => {
    localStorage.setItem(KEY, "{不是 json");
    expect(loadPrefs()).toEqual({});
  });

  it("缺版本号 / 版本不符 → 空对象", () => {
    localStorage.setItem(KEY, JSON.stringify({ vals: { maxSurf: "20" } }));
    expect(loadPrefs()).toEqual({});
    localStorage.setItem(KEY, JSON.stringify({ version: 99, vals: { maxSurf: "20" } }));
    expect(loadPrefs()).toEqual({});
  });

  it("被塞了非字符串/非布尔的值 → 丢弃，不污染表单", () => {
    localStorage.setItem(KEY, JSON.stringify({
      version: 1,
      vals: { ok: "20", num: 20, arr: [1], nul: null, flag: true },
    }));
    expect(loadPrefs()).toEqual({ ok: "20", flag: true });
  });

  it("localStorage 读取抛异常（隐私模式等）→ 空对象，不影响导入", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("denied"); });
    expect(loadPrefs()).toEqual({});
  });

  it("localStorage 写入抛异常 → 静默吞掉，不影响导入", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("quota"); });
    expect(() => savePrefs({ maxSurf: "20" })).not.toThrow();
  });
});
