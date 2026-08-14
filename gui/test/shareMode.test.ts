import { describe, it, expect } from "vitest";
import {
  shareModeToIsWeight,
  shareModeLabel,
  SHARE_MODES,
  SIGN_CONVENTION_NOTE,
  SHARE_CONVERSION_NOTE,
} from "../src/components/MaterialEditDialog";

/*
 * 化学式份额模式（MaterialEditDialog.tsx）—— 纯函数/常量。
 *
 * 背景：MCNP 约定 负号=质量份额、正号=原子份额；/api/expand-formula 默认输出质量份额
 * （is_weight 缺省 true → 负号），is_weight:false 输出原子份额（正号）。
 * 以下用例 pin 模式→is_weight 映射与 UI 标注文案，确保对接参数名与正负号约定不漂移。
 */

describe("shareModeToIsWeight（份额模式 → 后端 is_weight）", () => {
  it("质量份额 = is_weight true（负号）", () => {
    expect(shareModeToIsWeight("weight")).toBe(true);
  });

  it("原子份额 = is_weight false（正号）", () => {
    expect(shareModeToIsWeight("atomic")).toBe(false);
  });
});

describe("shareModeLabel（份额模式显示名）", () => {
  it("weight → 质量份额 / atomic → 原子份额", () => {
    expect(shareModeLabel("weight")).toBe("质量份额");
    expect(shareModeLabel("atomic")).toBe("原子份额");
  });

  it("覆盖全部合法模式（穷举 SHARE_MODES），无遗漏", () => {
    expect(SHARE_MODES.map(shareModeLabel).join("/")).toBe("质量份额/原子份额");
  });
});

describe("SIGN_CONVENTION_NOTE（MCNP 正负号约定标注）", () => {
  it("同时说明 负号=质量份额 与 正号=原子份额", () => {
    expect(SIGN_CONVENTION_NOTE).toContain("负号=质量份额");
    expect(SIGN_CONVENTION_NOTE).toContain("正号=原子份额");
  });
});

describe("SHARE_CONVERSION_NOTE（份额含义转换说明）", () => {
  it("覆盖 质量占比 与 原子数占比 两种含义", () => {
    expect(SHARE_CONVERSION_NOTE).toContain("质量份额按各核素质量占比");
    expect(SHARE_CONVERSION_NOTE).toContain("原子份额按原子数占比");
  });
});
