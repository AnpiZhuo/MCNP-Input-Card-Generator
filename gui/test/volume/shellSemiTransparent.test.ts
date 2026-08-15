import { describe, it, expect } from "vitest";
import { buildCellMaterial, DEFAULT_SHELL_OPACITY } from "../../src/three/cellMaterial";

/**
 * 用户实测反馈「栅元默认半透明」（PM 修复要求 1）：
 * 体积窗口外壳默认应【半透明】而非不透明——原 opaque depthWrite 挡住体积层
 * → 体积层永远被遮住（症状 1/5）。semi 档位 + 连续透明度覆盖。
 *
 * 共享模块契约保持：无 mode 调用仍默认 opaque（Preview3D 不回归）。
 */
describe("栅元外壳默认半透明（buildCellMaterial semi 档位）", () => {
  it("DEFAULT_SHELL_OPACITY = 0.4（半透明档位默认透明度）", () => {
    expect(DEFAULT_SHELL_OPACITY).toBe(0.4);
  });

  it("semi 档位：transparent + depthWrite off + opacity 0.4（外壳半透明、体积层可透出）", () => {
    const spec = buildCellMaterial({ color: "#3366ff", transparentMode: "semi" });
    expect(spec.transparent).toBe(true);
    expect(spec.depthWrite).toBe(false);
    expect(spec.opacity).toBe(DEFAULT_SHELL_OPACITY);
  });

  it("semi 档位可被连续透明度覆盖（栅元透明度滑杆逐级生效）", () => {
    const spec = buildCellMaterial({ color: "#3366ff", transparentMode: "semi", opacity: 0.8 });
    expect(spec.opacity).toBe(0.8);
    expect(spec.transparent).toBe(true);
    expect(spec.depthWrite).toBe(false);
  });

  it("真空栅元（M0）在 semi 档位仍 opacity 0（全透明语义保持）", () => {
    const spec = buildCellMaterial({ color: "transparent", transparentMode: "semi" });
    expect(spec.opacity).toBe(0);
    expect(spec.transparent).toBe(true);
  });

  it("透明度滑杆拉满 1 → 外壳不透明（depthWrite 恢复，无 overdraw）", () => {
    const spec = buildCellMaterial({ color: "#3366ff", transparentMode: "opaque", opacity: 1 });
    expect(spec.transparent).toBe(false);
    expect(spec.depthWrite).toBe(true);
    expect(spec.opacity).toBe(1);
  });

  it("无 mode 调用默认仍 opaque（共享模块默认契约不变，Preview3D 不回归）", () => {
    const spec = buildCellMaterial({ color: "#3366ff" });
    expect(spec.transparent).toBe(false);
    expect(spec.depthWrite).toBe(true);
    expect(spec.opacity).toBe(1);
  });
});
