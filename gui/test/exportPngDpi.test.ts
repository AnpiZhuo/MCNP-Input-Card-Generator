// @vitest-environment jsdom
/**
 * 出图的**物理尺寸元数据**与**目标分辨率**（2026-09-19 按中文期刊要求新增）。
 *
 * 依据：期刊对线条图通常要求 **≥600 dpi**、半色调图 **≥300 dpi**。
 * 而 **PNG 本身没有物理尺寸**——不说清"印 80 mm 还是 170 mm"，"够不够 dpi"就是空话。
 * 所以这里锁两件事：
 *  1. `rasterScaleFor` 按「目标 dpi × 成品宽度」算倍率（含 1× 下限与 6× 上限）；
 *  2. `withPngDpi` 真把 `pHYs` 写进 PNG 且**不破坏文件**（能被解析回 dpi）。
 */
import { describe, it, expect } from "vitest";
import { rasterScaleFor, PRINT_LINE_DPI, PRINT_HALFTONE_DPI, PRINT_WIDTH_MM_SINGLE } from "../src/export/exportFigure";
import { withPngDpi } from "../src/export/captureFrame";

/**
 * 造一张最小合法 PNG（**手写字节**，1×1 灰度、无 IDAT）。
 * 为什么不用 canvas：本仓库**没装 `canvas` npm 包**，jsdom 里 `toDataURL` 拿不到数据；
 * 而这里要测的正是"改字节结构"，手写反而更可控。
 */
function crc32(buf: Uint8Array): number {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c >>> 0;
  }
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = table[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type: string, data: number[]): number[] {
  const body = [...type].map((ch) => ch.charCodeAt(0)).concat(data);
  const len = data.length;
  const out = [(len >>> 24) & 255, (len >>> 16) & 255, (len >>> 8) & 255, len & 255, ...body];
  const crc = crc32(new Uint8Array(body));
  return out.concat([(crc >>> 24) & 255, (crc >>> 16) & 255, (crc >>> 8) & 255, crc & 255]);
}

function tinyPng(): Uint8Array {
  const sig = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  const ihdr = chunk("IHDR", [0, 0, 0, 1, 0, 0, 0, 1, 8, 0, 0, 0, 0]); // 1×1, 8bit 灰度
  const iend = chunk("IEND", []);
  return new Uint8Array([...sig, ...ihdr, ...iend]);
}

/** 从 PNG 字节里读 dpi（解析 pHYs；没有则返回 null） */
function readDpi(bytes: Uint8Array): number | null {
  let off = 8;
  while (off + 8 <= bytes.length) {
    const len = new DataView(bytes.buffer, bytes.byteOffset + off, 4).getUint32(0, false);
    const type = String.fromCharCode(bytes[off + 4], bytes[off + 5], bytes[off + 6], bytes[off + 7]);
    if (type === "pHYs") {
      const dv = new DataView(bytes.buffer, bytes.byteOffset + off + 8, 9);
      const ppx = dv.getUint32(0, false);
      const unit = bytes[off + 16];
      return unit === 1 ? ppx * 0.0254 : null; // px/m → dpi
    }
    if (type === "IEND") return null;
    off += 12 + len;
  }
  return null;
}

describe("rasterScaleFor（目标 dpi × 成品宽度 → 倍率）", () => {
  it("600 dpi、80 mm、逻辑宽 800 px ⇒ 约 2.36×", () => {
    // 600 dpi × 80 mm = 1890 px；1890 / 800 = 2.36
    expect(rasterScaleFor(800, PRINT_WIDTH_MM_SINGLE, PRINT_LINE_DPI)).toBeCloseTo(2.36, 2);
  });

  it("300 dpi 半色调比 600 dpi 线图矮一半", () => {
    const line = rasterScaleFor(800, PRINT_WIDTH_MM_SINGLE, PRINT_LINE_DPI);
    const half = rasterScaleFor(800, PRINT_WIDTH_MM_SINGLE, PRINT_HALFTONE_DPI);
    expect(half).toBeCloseTo(line / 2, 1);
  });

  it("逻辑画布已经很大时不缩（下限 1×）", () => {
    expect(rasterScaleFor(4000, PRINT_WIDTH_MM_SINGLE, PRINT_LINE_DPI)).toBe(1);
  });

  it("逻辑画布极小时不炸（上限 6×）", () => {
    expect(rasterScaleFor(10, PRINT_WIDTH_MM_SINGLE, PRINT_LINE_DPI)).toBe(6);
  });

  it("非法宽度回落到基准倍率，不抛错", () => {
    expect(rasterScaleFor(0)).toBe(2);
    expect(rasterScaleFor(-5)).toBe(2);
  });
});

describe("withPngDpi（把物理尺寸写进 PNG）", () => {
  it("写入的 dpi 能被解析回来（≈ 目标值）", async () => {
    const src = tinyPng();
    const out = withPngDpi(src, 600);
    const dpi = readDpi(out);
    expect(dpi).not.toBeNull();
    // pHYs 是整像素/米，600 dpi 会落到 599.99…~600.01
    expect(dpi!).toBeGreaterThan(599);
    expect(dpi!).toBeLessThan(601);
  });

  it("pHYs 紧跟 IHDR（规范建议位置）", async () => {
    const out = withPngDpi(tinyPng(), 300);
    expect(String.fromCharCode(out[12], out[13], out[14], out[15])).toBe("IHDR");
    // IHDR 块长 13 + 12 = 25 字节，从 8 开始 ⇒ 下一个块在 33
    expect(String.fromCharCode(out[37], out[38], out[39], out[40])).toBe("pHYs");
  });

  it("文件仍以 IEND 结束（没把图写坏）", async () => {
    const out = withPngDpi(tinyPng(), 300);
    const t = String.fromCharCode(...out.subarray(out.length - 8, out.length - 4));
    expect(t).toBe("IEND");
  });

  it("重复写入不会堆出两个 pHYs", async () => {
    let out = withPngDpi(tinyPng(), 300);
    out = withPngDpi(out, 600);
    let count = 0;
    let off = 8;
    while (off + 8 <= out.length) {
      const len = new DataView(out.buffer, out.byteOffset + off, 4).getUint32(0, false);
      const type = String.fromCharCode(out[off + 4], out[off + 5], out[off + 6], out[off + 7]);
      if (type === "pHYs") count++;
      off += 12 + len;
    }
    expect(count).toBe(1);
    expect(readDpi(out)!).toBeGreaterThan(599);
  });

  it("不是 PNG / dpi 非法 ⇒ 原样返回（宁可没元数据，也不弄坏图）", () => {
    const junk = new Uint8Array([1, 2, 3, 4]);
    expect(withPngDpi(junk, 600)).toBe(junk);
    const bytes = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0, 0x49, 0x48, 0x44, 0x52]);
    expect(withPngDpi(bytes, 0)).toBe(bytes);
  });
});
