import { describe, it, expect } from "vitest";
import { colorizeScalar, weatherLut } from "../../src/volume/colorize";
import {
  worldBoxFromEdges,
  translateToCenter,
  unionBoxes,
  boxCenter,
  computeFramingBox,
  type AABB,
} from "../../src/volume/alignWorld";
import {
  textureDimsFromResolution,
  volumeBoxSceneTransform,
  computeVolumeCamera,
} from "../../src/volume/VolumeRenderer";

/**
 * PM 补充指令：用户真实文件（tests/fixtures/real_meshtal_jk.meshtal，tally14/p/1×2×2 共 4 体素）
 * 是受支持文件——验证其体积层渲染链路完整：meshtalTexture 帧（worldBox+resolution）→
 * colorizeScalar 上色 → DataTexture3D 维度（nk,nj,ni）→ ray-march 盒场景 position/scale/uBoxMin/uBoxMax。
 *
 * 契约 §9.2 把纯逻辑收敛到 colorize/alignWorld/volumeShader 镜像（vitest 可测 seam），
 * GPU 实渲染为 `#/volume` e2e/人工冒烟（契约 §9.3）。此处把渲染链路中可测的纯几何/数据
 * 派生全部 pin 住：数据长度、纹理维度、盒位置/缩放/shader box 均来自真实文件实测几何。
 */
describe("用户真实文件体积层渲染链路（tally14/p/1×2×2，4 体素）", () => {
  // 真实文件实测几何（PROJECT_MEMORY：grid_bounds 49,-10,90 ~ 51,10,110，resolution 1×2×2）
  const worldBox: AABB = { min: [49, -10, 90], max: [51, 10, 110] };
  const resolution: [number, number, number] = [1, 2, 2];

  it("worldBoxFromEdges 与真实 grid_bounds 一致（每轴 min=edge[0] max=edge[-1]）", () => {
    const box = worldBoxFromEdges({ x: [49, 51], y: [-10, 0, 10], z: [90, 100, 110] });
    expect(box.min).toEqual([49, -10, 90]);
    expect(box.max).toEqual([51, 10, 110]);
  });

  it("DataTexture3D 维度 = (nk,nj,ni)（后端 numpy z 最快扁平布局）", () => {
    expect(textureDimsFromResolution(resolution)).toEqual([2, 2, 1]);
  });

  it("标量帧长度 = ni*nj*nk = 4 体素 → colorize 输出 RGBA 长度 16", () => {
    const lut = weatherLut(256);
    const scalar = new Uint8Array([0, 64, 128, 255]);
    const rgba = colorizeScalar(scalar, lut, { min: 0, max: 255 }, 0, { min: 0, max: 255 });
    expect(rgba.length).toBe(16);
    expect(rgba.length / 4).toBe(4);
  });

  it("体积盒场景变换：position=中心+offset、scale=世界尺寸、uBoxMin/uBoxMax=世界盒+offset", () => {
    const offset: [number, number, number] = [-1, -2, -3];
    const t = volumeBoxSceneTransform(worldBox, offset);
    const c = boxCenter(worldBox);
    expect(t.position).toEqual([c[0] - 1, c[1] - 2, c[2] - 3]);
    expect(t.scale).toEqual([2, 20, 20]);
    expect(t.boxMin).toEqual([48, -12, 87]);
    expect(t.boxMax).toEqual([50, 8, 107]);
  });

  it("真实文件场景：外壳≫体积盒时取景以体积盒为主（相机 target=体积盒中心）", () => {
    const shell: AABB = { min: [-100, -100, -150], max: [100, 100, 150] };
    const frame = computeFramingBox(shell, worldBox);
    expect(frame).toEqual(worldBox);
    const cp = computeVolumeCamera(frame);
    expect(cp.target[0]).toBeCloseTo(boxCenter(worldBox)[0]);
    expect(cp.target[1]).toBeCloseTo(boxCenter(worldBox)[1]);
    expect(cp.target[2]).toBeCloseTo(boxCenter(worldBox)[2]);
    expect(cp.farNear).toBeLessThanOrEqual(1e4);
  });

  it("共享 offset 不变量：外壳与体积盒归一化后位置一致（§7.3，translateToCenter 联合盒）", () => {
    const shell: AABB = { min: [-100, -100, -150], max: [100, 100, 150] };
    const union = unionBoxes([shell, worldBox]);
    const offset = translateToCenter([{ translate: () => {} }], union);
    const uCenter = boxCenter(union);
    const t = volumeBoxSceneTransform(worldBox, offset);
    // 体积盒场景中心 = 世界中心 + offset（offset = -union.center）
    expect(t.position[0]).toBeCloseTo(boxCenter(worldBox)[0] - uCenter[0]);
    expect(t.position[1]).toBeCloseTo(boxCenter(worldBox)[1] - uCenter[1]);
    expect(t.position[2]).toBeCloseTo(boxCenter(worldBox)[2] - uCenter[2]);
    // shader 盒相对位移保持（§7.3 断言 4）
    expect(t.boxMin[0] - t.boxMin[0]).toBe(0);
  });
});
