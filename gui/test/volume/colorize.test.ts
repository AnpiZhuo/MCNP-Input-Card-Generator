import { describe, it, expect } from "vitest";
import { createHash } from "node:crypto";
import {
  weatherLut, colorizeScalar, WEATHER_STOPS, roundHalfEven, defaultDisplayMin, minPositiveOfBytes,
} from "../../src/volume/colorize";

/**
 * 色阶映射（契约 meshtal-visualization.md §4.3 / §4.3.1 / §12 A2.2）
 *
 * golden sha256 跨语言防漂移：TS `weatherLut()` 256 项 RGBA 拼连的 sha256
 * **必须等于** `36770ae2b9cd2a2ac3b6e6a08de45d522261dfced960c0c1db49bc515358c038`
 * （与后端 `app/meshtal/colormap.py::weather_lut()` 逐字节一致）。
 */

describe("weatherLut golden（跨语言防漂移）", () => {
  it("sha256 == golden 36770ae2…（与后端 colormap 逐字节一致）", () => {
    const lut = weatherLut(256);
    expect(lut.length).toBe(256 * 4);
    const digest = createHash("sha256").update(lut).digest("hex");
    expect(digest).toBe("36770ae2b9cd2a2ac3b6e6a08de45d522261dfced960c0c1db49bc515358c038");
  });

  it("锚点：lut[0]=蓝 #3B4CC0、lut[-1]=红 #DC2626（§4.3.1）", () => {
    const lut = weatherLut(256);
    expect([lut[0], lut[1], lut[2], lut[3]]).toEqual([0x3b, 0x4c, 0xc0, 255]);
    const last = (lut.length / 4) - 1;
    expect([lut[last * 4], lut[last * 4 + 1], lut[last * 4 + 2]]).toEqual([0xdc, 0x26, 0x26]);
  });

  it("锚点区间插值：i=84 青 #00E5FF、i=191 橙 (249,116,22)（PM 仲裁 t-space）", () => {
    const lut = weatherLut(256);
    expect([lut[84 * 4], lut[84 * 4 + 1], lut[84 * 4 + 2]]).toEqual([0x00, 0xe5, 0xff]);
    expect([lut[191 * 4], lut[191 * 4 + 1], lut[191 * 4 + 2]]).toEqual([249, 116, 22]);
  });

  it("roundHalfEven：Python round 语义（half-to-even）", () => {
    expect(roundHalfEven(2.5)).toBe(2);
    expect(roundHalfEven(3.5)).toBe(4);
    expect(roundHalfEven(2.4)).toBe(2);
    expect(roundHalfEven(112.5)).toBe(112);
  });

  it("WEATHER_STOPS 锚点位置/颜色单一事实来源", () => {
    const positions = WEATHER_STOPS.map(([p]) => p);
    expect(positions).toEqual([0.0, 0.33, 0.55, 0.75, 1.0]);
    expect(WEATHER_STOPS[0][1][0]).toBe(0x3b); // 蓝
    expect(WEATHER_STOPS[WEATHER_STOPS.length - 1][1][0]).toBe(0xdc); // 红
  });
});

describe("defaultDisplayMin（自适应色阶下限）", () => {
  it("数据最小值恰为 0 且提供最小正值 → minPositive*0.5（只隐纯零背景，正结构全保留）", () => {
    // 用户实测：±2000 全域网格，u8 纹理最小非零值≈7.38e-8、max=1.88e-5；
    // sqrt 规则切太狠（200cm 粗光束只剩 1 体素宽的"一个面"观感），改为只隐零背景
    expect(defaultDisplayMin({ min: 0, max: 1.88115e-5 }, 7.376e-8)).toBeCloseTo(7.376e-8 * 0.5, 12);
  });

  it("数据最小值恰为 0 但无 minPositive → 保守兜底 max*1e-6", () => {
    expect(defaultDisplayMin({ min: 0, max: 1.88115e-5 })).toBeCloseTo(1.88115e-11, 20);
  });

  it("最小值 > 0（无零背景）→ 保持数据最小值（自适应色阶既有行为）", () => {
    expect(defaultDisplayMin({ min: 0.5, max: 5 })).toBe(0.5);
    expect(defaultDisplayMin({ min: 0.5, max: 5 }, 0.6)).toBe(0.5);
  });

  it("全零网格（退化）→ 0，不产生负/NaN 阈值", () => {
    expect(defaultDisplayMin({ min: 0, max: 0 })).toBe(0);
    expect(defaultDisplayMin({ min: 0, max: 0 }, undefined)).toBe(0);
  });

  it("负最小值（异常数据）→ 保持最小值（不回退到 0 规则）", () => {
    expect(defaultDisplayMin({ min: -1, max: 5 })).toBe(-1);
  });
});

describe("minPositiveOfBytes（纹理最小非零正值）", () => {
  it("线性归一化 u8 → 最小非零重建值", () => {
    const bytes = new Uint8Array([0, 0, 1, 5, 255]);
    const mp = minPositiveOfBytes(bytes, { min: 0, max: 1.88115e-5 });
    expect(mp).toBeCloseTo((1.88115e-5 / 255) * 1, 12);
  });

  it("带偏移的 scalarRange：f = u8*scale + offset", () => {
    const bytes = new Uint8Array([0, 100]);
    const mp = minPositiveOfBytes(bytes, { min: 10, max: 20 });
    expect(mp).toBeCloseTo(10 + (10 / 255) * 100, 12);
  });

  it("全零帧 → undefined", () => {
    expect(minPositiveOfBytes(new Uint8Array([0, 0, 0]), { min: 0, max: 1 })).toBeUndefined();
  });
});

describe("colorizeScalar", () => {
  const lut = weatherLut(256);

  it("threshold→alpha0：v 对应 float 值 < displayMin（显示阈值=色阶下限）→ alpha 0", () => {
    // scalar u8 [0,255]，scalarRange 缺省 = {0,255} → float = v
    const scalar = new Uint8Array([0, 50, 100, 150, 200, 255]);
    const out = colorizeScalar(scalar, lut, { min: 0, max: 255 }, /* displayMin */ 100);
    expect(out[0 * 4 + 3]).toBe(0); // v=0 < 100 → alpha 0
    expect(out[1 * 4 + 3]).toBe(0); // v=50 < 100 → alpha 0
    expect(out[2 * 4 + 3]).toBe(255); // v=100 == displayMin → alpha 255（后端 map_value: v<lo 才 0）
    expect(out[3 * 4 + 3]).toBe(255); // v=150 ≥ 100 → alpha 255
    expect(out[5 * 4 + 3]).toBe(255); // v=255
  });

  it("默认 range=scalarRange（A2.2）：全 [0,255] 归一化映射正确渐变", () => {
    // 默认自适应：scalarRange={0,255} 全量，v 直接映射 LUT
    const scalar = new Uint8Array([0, 127, 255]);
    const out = colorizeScalar(scalar, lut, { min: 0, max: 255 }, 0);
    expect([out[0], out[1], out[2], out[3]]).toEqual([lut[0], lut[1], lut[2], lut[3]]);
    expect([out[4], out[5], out[6]]).toEqual([lut[127 * 4], lut[127 * 4 + 1], lut[127 * 4 + 2]]);
    expect([out[8], out[9], out[10]]).toEqual([lut[255 * 4], lut[255 * 4 + 1], lut[255 * 4 + 2]]);
  });

  it("range 重映射：用户手改上下限 → 重新线性映射", () => {
    const scalar = new Uint8Array([64, 128, 192]);
    const out = colorizeScalar(scalar, lut, { min: 64, max: 192 }, 0);
    // v=64 → t=0 → lut[0]；v=128 → t=0.5 → lut[127]；v=192 → t=1 → lut[255]
    expect([out[0], out[1], out[2]]).toEqual([lut[0], lut[1], lut[2]]);
    expect([out[4], out[5], out[6]]).toEqual([lut[127 * 4], lut[127 * 4 + 1], lut[127 * 4 + 2]]);
    expect([out[8], out[9], out[10]]).toEqual([lut[255 * 4], lut[255 * 4 + 1], lut[255 * 4 + 2]]);
  });

  it("scalarRange 重建：u8 → float 再阈值/映射（真实 frame 语义）", () => {
    // 后端 frame.scalarRange 是 float（如 0~3.5e7），u8 是归一化值
    const scalarRange = { min: 0, max: 3.5e7 };
    const scalar = new Uint8Array([0, 128, 255]); // 0, 1.75e7, 3.5e7
    const out = colorizeScalar(scalar, lut, { min: 0, max: 3.5e7 }, 1e7, scalarRange);
    expect(out[3]).toBe(0); // float 0 < 1e7 → 不显示
    expect(out[7]).toBe(255); // float 1.75e7 ≥ 1e7
    expect(out[11]).toBe(255);
  });

  it("128³ 上色：结果正确 + 耗时中位数在宽松上限内（契约 §8 时间轴切帧 KPI 代理）", () => {
    const n = 128 * 128 * 128;
    // 标量构造（16.7M 次写）与 warmup 都放在计时区**之外**，避免把分配成本算进上色耗时
    const scalar = new Uint8Array(n);
    for (let i = 0; i < n; i++) scalar[i] = (i * 7919) % 256;

    // 正确性先在单次调用上锁死（不受计时影响）
    const out = colorizeScalar(scalar, lut, { min: 0, max: 255 }, 0);
    expect(out.length).toBe(n * 4);

    // 计时：先 warmup 一次（消除 JIT/首次分配偏差），再取 N 次**中位数**。
    // 单次墙钟阈值（原 <50ms）在负载/GC 下随机红（PROJECT_MEMORY 多次记载该 flaky），
    // 故改为「中位数 + 宽松上限」：KPI 目标仍是 50ms（开发机实测数量级），
    // 门禁上限取 3×=150ms 以吸收 CI 抖动 —— 真回归（如算法退化）仍会被抓住。
    const N = 5;
    const KPI_MS = 50;
    const GUARD_MS = KPI_MS * 3;
    colorizeScalar(scalar, lut, { min: 0, max: 255 }, 0); // warmup，不计入
    const samples: number[] = [];
    for (let k = 0; k < N; k++) {
      const t0 = performance.now();
      colorizeScalar(scalar, lut, { min: 0, max: 255 }, 0);
      samples.push(performance.now() - t0);
    }
    samples.sort((a, b) => a - b);
    const median = samples[Math.floor(N / 2)];
    // 期望消息里带真实量级，人工排查 flaky 时可直接读数
    expect(median, `128³ 上色中位数 ${median.toFixed(1)}ms（KPI ${KPI_MS}ms / 门禁 ${GUARD_MS}ms）`).toBeLessThan(GUARD_MS);
  });
});
