import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { quickAddCheckFailedMessage } from "../src/utils/quickCell";

/**
 * T2 回归：快捷建栅元的重合检测 catch 曾静默跳过（`catch (e) { /* 检测失败 → 直接追加 *​/ }`）。
 * 修法：失败时仍追加栅元，但弹出非阻塞警告（"重合检测失败，未校验与已有栅元重叠"）
 * + console.warn 记录原因。
 */
const HERE = dirname(fileURLToPath(import.meta.url));
const GEO_TSX = readFileSync(join(HERE, "../src/components/GeometryTab.tsx"), "utf-8");

describe("T2：快捷建栅元重合检测失败不再静默（非阻塞警告）", () => {
  it("quickAddCheckFailedMessage 生成含原因的中文警告", () => {
    expect(quickAddCheckFailedMessage(new Error("backend boom")))
      .toBe("重合检测失败，未校验与已有栅元重叠（backend boom）");
    expect(quickAddCheckFailedMessage("raw")).toBe("重合检测失败，未校验与已有栅元重叠");
    expect(quickAddCheckFailedMessage(undefined)).toBe("重合检测失败，未校验与已有栅元重叠");
    expect(quickAddCheckFailedMessage(null)).toBe("重合检测失败，未校验与已有栅元重叠");
  });

  it("GeometryTab 快捷添加 catch 不再静默：console.warn 记录 + 弹非阻塞警告", () => {
    expect(GEO_TSX).toContain("quickAddCheckFailedMessage");
    expect(GEO_TSX).toContain("setQuickCheckWarn");
    expect(GEO_TSX).toContain("console.warn(\"[quick-add-check]");
    // 旧静默注释（检测失败 → 直接追加）已移除
    expect(GEO_TSX).not.toContain("检测失败 → 直接追加");
  });
});
