import { describe, expect, it } from "vitest";
import { normalizeImportedCardText } from "../src/utils/mcnpText";

describe("normalizeImportedCardText", () => {
  it("压缩 GEOUNED 的空白并去掉数字尾随零", () => {
    expect(normalizeImportedCardText("  1    PX   1.000000   2.5000E+00   $ 说明  \r\n"))
      .toBe("1 PX 1 2.5E+00 $ 说明");
  });

  it("保留注释内容和负号", () => {
    expect(normalizeImportedCardText("2   PZ   -0.000   $ keep  spaces"))
      .toBe("2 PZ -0 $ keep  spaces");
  });
});
