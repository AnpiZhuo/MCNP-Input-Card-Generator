import { describe, it, expect } from "vitest";
import {
  RAY_MARCH_VERTEX,
  RAY_MARCH_FRAGMENT,
  buildRayMarchMaterial,
  isWebGL2,
  WEBGL2_UNAVAILABLE,
} from "../../src/volume/volumeShader";

/**
 * 真实渲染回归守卫（2026-08-15 用户实测「体积层完全没渲染」根因）：
 * three r160 对 RawShaderMaterial 会先前置 `#define SHADER_TYPE …` 块再拼用户源码；
 * 旧实现 shader 字符串以 `#version 300 es` 开头 → 编译报
 * 「#version directive must occur before anything else」→ 程序无效 → 体积层从不显示。
 * 本组断言锁定正确契约：shader 字符串不含 #version、材质设 glslVersion=GLSL3。
 */
describe("RawShaderMaterial #version 指令契约（真实渲染回归）", () => {
  it("shader 字符串不得含 #version（three 前置 #define 块，用户源码首行 #version 会编译失败）", () => {
    expect(RAY_MARCH_VERTEX).not.toContain("#version");
    expect(RAY_MARCH_FRAGMENT).not.toContain("#version");
  });

  it("shader 首行为 precision 声明（#version 300 es 由 three 经 glslVersion 生成在最顶端）", () => {
    expect(RAY_MARCH_VERTEX.split("\n")[0]).toContain("precision");
    expect(RAY_MARCH_FRAGMENT.split("\n")[0]).toContain("precision");
  });

  it("buildRayMarchMaterial 设 glslVersion=GLSL3（three 在最顶端生成 #version 300 es）", () => {
    const mat = buildRayMarchMaterial({ texture: {} as any });
    expect(mat.glslVersion).toBe("300 es");
  });
});

/**
 * 光线步进 shader 字符串快照 + WebGL2 判定（契约 meshtal-visualization.md §4.7 / §13）
 * 快照锁防无意识改动（数值逻辑镜像纯 TS 模块 colorize/alignWorld/downsampleRequest vitest）。
 */
describe("RAY_MARCH_FRAGMENT", () => {
  it("前向光线步进 front-to-back 累积（acc 合成）", () => {
    expect(RAY_MARCH_FRAGMENT).toContain("acc.rgb += (1.0 - acc.a) * col.rgb * a");
    expect(RAY_MARCH_FRAGMENT).toContain("acc.a += (1.0 - acc.a) * a");
  });

  it("sampler3D 采样 + alpha 合成（CPU 已上色）", () => {
    expect(RAY_MARCH_FRAGMENT).toContain("sampler3D");
    expect(RAY_MARCH_FRAGMENT).toContain("texture(uTex");
    expect(RAY_MARCH_FRAGMENT).toContain("uOpacity");
    expect(RAY_MARCH_FRAGMENT).toContain("uBoxMin");
    expect(RAY_MARCH_FRAGMENT).toContain("uBoxMax");
  });

  it("数据布局 swizzle：numpy (x,y,z) 扁平 → 纹理 uv=(z,y,x)", () => {
    // DataTexture3D dims=(nk,nj,ni)，采样坐标 = (n.z, n.y, n.x)
    expect(RAY_MARCH_FRAGMENT).toContain("vec3(n.z, n.y, n.x)");
  });

  it("ray-box 求交 + 提前终止（>0.98 不透明即断）", () => {
    expect(RAY_MARCH_FRAGMENT).toContain("rayBox");
    expect(RAY_MARCH_FRAGMENT).toContain("t.y < t.x");
    expect(RAY_MARCH_FRAGMENT).toContain("acc.a > 0.98");
  });

  it("体积透明度为图层级：uOpacity 只乘最终 alpha，不乘每采样步（防 256 步累积饱和）", () => {
    // 用户实测回归：uOpacity 若按每采样步乘（col.a * uOpacity），大网格（±2000 全域）
    // 256 个采样步累积后 acc.a ≈ 1-(1-a)^256，滑杆再低也近乎不透明 →「调低透明度没用」。
    expect(RAY_MARCH_FRAGMENT).toContain("fragColor = vec4(acc.rgb, acc.a * uOpacity)");
    expect(RAY_MARCH_FRAGMENT).not.toContain("col.a * uOpacity");
  });

  it("深度剥除：拉低透明度时外层先淡出（peel 段二次曲线），内层保持完整采样", () => {
    // 用户需求「外层先透明、内层慢慢跟」：滑杆越低，每条光线靠近视线的外侧
    // peel 段按二次曲线淡出（m=k²），内层完整采样；u=1 → peel=0 零回归。
    expect(RAY_MARCH_FRAGMENT).toContain("float peel = (1.0 - uOpacity) * 0.5;");
    expect(RAY_MARCH_FRAGMENT).toContain("m = k * k");
    expect(RAY_MARCH_FRAGMENT).toContain("float a = col.a * m");
  });

  it("快照：片段着色器字符串稳定", () => {
    expect(RAY_MARCH_FRAGMENT).toMatchSnapshot();
  });
});

describe("RAY_MARCH_VERTEX", () => {
  it("透传世界坐标（vWorldPos 供片段射线方向）", () => {
    expect(RAY_MARCH_VERTEX).toContain("vWorldPos");
    expect(RAY_MARCH_VERTEX).toContain("modelMatrix");
    expect(RAY_MARCH_VERTEX).toMatchSnapshot();
  });
});

describe("isWebGL2", () => {
  it("node 环境无 canvas → false（返回布尔，不抛）", () => {
    const r = isWebGL2();
    expect(typeof r).toBe("boolean");
  });

  it("降级提示文案固定", () => {
    expect(WEBGL2_UNAVAILABLE).toContain("不支持 WebGL2");
  });
});
