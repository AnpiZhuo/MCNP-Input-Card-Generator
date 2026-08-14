import { describe, it, expect } from "vitest";
import { RAY_MARCH_VERTEX, RAY_MARCH_FRAGMENT, isWebGL2, WEBGL2_UNAVAILABLE } from "../../src/volume/volumeShader";

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
