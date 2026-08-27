/**
 * gpuInfo — GPU 分类/文案纯函数测试（项4 辅助）。
 * detectWebGLGpu 依赖浏览器 WebGL，jsdom 不测（返回 null 即可）。
 */
import { describe, expect, it } from "vitest";
import { classifyGpu, gpuStatusText } from "../src/utils/gpuInfo";

describe("classifyGpu", () => {
  it("NVIDIA GeForce / RTX → 独显", () => {
    expect(classifyGpu("NVIDIA", "NVIDIA GeForce RTX 4060")).toEqual({
      vendor: "nvidia", discrete: true, name: "NVIDIA GeForce RTX 4060",
    });
    expect(classifyGpu("NVIDIA Corporation", "NVIDIA GeForce GTX 1650")).toMatchObject({ vendor: "nvidia", discrete: true });
  });

  it("AMD Radeon RX / Vega 独显 → 独显", () => {
    expect(classifyGpu("Advanced Micro Devices", "AMD Radeon RX 6700 XT")).toMatchObject({ vendor: "amd", discrete: true });
    expect(classifyGpu("Advanced Micro Devices", "AMD Radeon(TM) Graphics")).toMatchObject({ vendor: "amd", discrete: false });
  });

  it("Intel UHD / Iris → 核显；Arc → 独显", () => {
    expect(classifyGpu("Intel", "Intel(R) UHD Graphics 770")).toMatchObject({ vendor: "intel", discrete: false });
    expect(classifyGpu("Intel", "Intel(R) Iris(R) Xe Graphics")).toMatchObject({ vendor: "intel", discrete: false });
    expect(classifyGpu("Intel", "Intel(R) Arc(TM) A770")).toMatchObject({ vendor: "intel", discrete: true });
  });

  it("空 → null；未命中 → unknown 核显", () => {
    expect(classifyGpu("", "")).toBeNull();
    expect(classifyGpu("Foo", "Bar")).toMatchObject({ vendor: "unknown", discrete: false });
  });
});

describe("gpuStatusText", () => {
  it("独显 / 核显 / null 文案", () => {
    expect(gpuStatusText({ vendor: "nvidia", discrete: true, name: "NVIDIA GeForce RTX 4060" })).toContain("独显");
    expect(gpuStatusText({ vendor: "intel", discrete: false, name: "Intel UHD 770" })).toContain("核显");
    expect(gpuStatusText(null)).toContain("不可用");
  });
});
