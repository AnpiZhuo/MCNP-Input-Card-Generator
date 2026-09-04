import { describe, it, expect } from "vitest";
import { sliceFrame, frameToCsv, sliceToSvg, type SliceFrameInput } from "../../src/volume/sliceExport";

/** 构造 frame：字节值 = fill(i,j,k)，scalarRange=[0,255] → float 重建 = 字节值 */
function makeFrame(dims: [number, number, number], fill: (i: number, j: number, k: number) => number): SliceFrameInput {
  const [ni, nj, nk] = dims;
  const bytes = new Uint8Array(ni * nj * nk);
  for (let i = 0; i < ni; i++) {
    for (let j = 0; j < nj; j++) {
      for (let k = 0; k < nk; k++) {
        bytes[i * (nj * nk) + j * nk + k] = Math.max(0, Math.min(255, fill(i, j, k)));
      }
    }
  }
  let s = "";
  for (let idx = 0; idx < bytes.length; idx++) s += String.fromCharCode(bytes[idx]);
  return { resolution: dims, dataBase64: btoa(s), scalarRange: { min: 0, max: 255 } };
}

describe("sliceFrame — 切面 2D 热图", () => {
  const frame = makeFrame([2, 3, 4], (i, j, k) => i * 100 + j * 10 + k); // 2×3×4

  it("x 切固定 i，宽=nk、高=nj", () => {
    const s = sliceFrame(frame, "x", 0, 0);
    expect(s.width).toBe(4); // nk
    expect(s.height).toBe(3); // nj
    expect(s.rgba.length).toBe(s.width * s.height * 4); // RGBA
    expect(s.axis).toBe("x");
    expect(s.sliceIndex).toBe(0);
  });

  it("y 切固定 j，宽=nk、高=ni", () => {
    const s = sliceFrame(frame, "y", 1, 0);
    expect(s.width).toBe(4); // nk
    expect(s.height).toBe(2); // ni
    expect(s.sliceIndex).toBe(1);
  });

  it("z 切固定 k，宽=ni、高=nj", () => {
    const s = sliceFrame(frame, "z", 2, 0);
    expect(s.width).toBe(2); // ni
    expect(s.height).toBe(3); // nj
    expect(s.sliceIndex).toBe(2);
  });

  it("displayMin 阈值：低于阈值 alpha=0（不显示）", () => {
    // 构造全 10 的帧，displayMin=50 → 全部低于 → alpha 全 0
    const low = makeFrame([2, 2, 2], () => 10);
    const s = sliceFrame(low, "z", 0, 50);
    for (let p = 3; p < s.rgba.length; p += 4) {
      expect(s.rgba[p]).toBe(0);
    }
  });
});

describe("frameToCsv — 整帧体素导出", () => {
  it("表头 + 每体素一行 i,j,k,value", () => {
    const frame = makeFrame([2, 2, 2], (i, j, k) => i + j + k);
    const csv = frameToCsv(frame);
    const lines = csv.split("\n");
    expect(lines[0]).toBe("i,j,k,value");
    expect(lines.length).toBe(1 + 2 * 2 * 2); // 表头 + 8 体素
    expect(lines[1]).toBe("0,0,0,0");
    // float 重建 = 字节值（scalarRange=[0,255]）
    expect(lines[8] || lines[lines.length - 1]).toMatch(/^1,1,1,/)
  });
});

describe("sliceToSvg — 矢量 SVG", () => {
  it("含 <svg> 与每体素 <rect>（非空 alpha 体素才画）", () => {
    const frame = makeFrame([2, 2, 2], (i, j, k) => (i + j + k === 0 ? 0 : 200));
    const s = sliceFrame(frame, "z", 0, 0);
    const svg = sliceToSvg(s);
    expect(svg).toContain("<svg");
    expect(svg).toContain("</svg>");
    expect(svg).toContain("<rect "); // 有体素被绘制
  });
});
