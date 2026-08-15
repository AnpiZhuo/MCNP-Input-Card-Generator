import { describe, it, expect } from "vitest";
import { deriveOpacity, DEFAULT_VOLUME_OPACITY } from "../../src/volume/VolumeRenderer";
import { DEFAULT_SHELL_OPACITY } from "../../src/three/cellMaterial";

/**
 * 用户实测反馈「改透明度没有用 / 只有一个透明度滑杆语义不清」（PM 修复要求 2）：
 * 控制面板拆两个独立滑杆——「栅元透明度」（控外壳）与「体积透明度」（控体积数据层）。
 * deriveOpacity 纯函数派生两个渲染参数，两者独立、可叠加。
 */
describe("双透明度滑杆状态派生（deriveOpacity）", () => {
  it("默认状态：栅元 0.4 半透明 + 体积 1 不透明（两滑杆默认值）", () => {
    const d = deriveOpacity(DEFAULT_SHELL_OPACITY, DEFAULT_VOLUME_OPACITY);
    expect(d.shellSpec.transparent).toBe(true);
    expect(d.shellSpec.opacity).toBe(DEFAULT_SHELL_OPACITY);
    expect(d.volumeUniform).toBe(DEFAULT_VOLUME_OPACITY);
  });

  it("两滑杆独立：改栅元透明度只影响外壳，体积 uniform 不变", () => {
    const a = deriveOpacity(0.4, 1);
    const b = deriveOpacity(0.8, 1);
    expect(a.shellSpec.opacity).toBe(0.4);
    expect(b.shellSpec.opacity).toBe(0.8);
    expect(a.volumeUniform).toBe(1);
    expect(b.volumeUniform).toBe(1);
  });

  it("两滑杆独立：改体积透明度只影响体积 uniform，外壳 spec 不变", () => {
    const a = deriveOpacity(0.4, 1);
    const b = deriveOpacity(0.4, 0.5);
    expect(a.volumeUniform).toBe(1);
    expect(b.volumeUniform).toBe(0.5);
    expect(a.shellSpec.opacity).toBe(b.shellSpec.opacity);
    expect(a.shellSpec.transparent).toBe(b.shellSpec.transparent);
  });

  it("两滑杆可叠加：栅元 0.4 + 体积 0.5 同时生效", () => {
    const d = deriveOpacity(0.4, 0.5);
    expect(d.shellSpec.opacity).toBe(0.4);
    expect(d.volumeUniform).toBe(0.5);
  });

  it("栅元透明度滑杆拉满 1 → 外壳不透明（无 overdraw）", () => {
    const d = deriveOpacity(1, 1);
    expect(d.shellSpec.transparent).toBe(false);
    expect(d.shellSpec.depthWrite).toBe(true);
    expect(d.shellSpec.opacity).toBe(1);
  });

  it("栅元透明度滑杆拉到 0 → 外壳全透明（opacity 0）", () => {
    const d = deriveOpacity(0, 1);
    expect(d.shellSpec.transparent).toBe(true);
    expect(d.shellSpec.opacity).toBe(0);
  });

  it("越界输入钳制到 [0,1]", () => {
    const d = deriveOpacity(-1, 2);
    expect(d.shellSpec.opacity).toBe(0);
    expect(d.volumeUniform).toBe(1);
  });
});
