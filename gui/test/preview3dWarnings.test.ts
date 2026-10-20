import { describe, expect, it } from "vitest";
import { preview3dWarnings } from "../src/utils/preview3dWarnings";

describe("3D 预览诊断", () => {
  it("说明无界栅元会按包围盒裁剪，而不是把它误报成球体", () => {
    const warnings = preview3dWarnings({
      closure_report: { "18": { status: "infinite" } },
    });
    expect(warnings[0]).toContain("栅元 18 无界");
    expect(warnings[0]).toContain("包围盒裁剪");
  });

  it("保留曲面解析和跳过栅元的原因", () => {
    expect(preview3dWarnings({
      parse_errors: ["曲面 18 解析失败"],
      skipped_cells: [{ number: 2, reason: "表达式无法解析" }],
    })).toEqual(["曲面 18 解析失败", "栅元 2：表达式无法解析"]);
  });
});
