// @vitest-environment jsdom
/**
 * 出图出口契约（2026-09-19 用户裁决：**所有导出的图片都是 PNG**，**一律白底**）。
 *
 * 这一批锁的是"产物形态"，不是像素：
 *  1. 二维图（原 PDF+SVG）与三维图**都只出 PNG** —— 不再有 pdf / svg 产物；
 *  2. 产物**白底**（用户当天先要透明、实机看过之后改口"png 都改为白底"）；
 *  3. 用户在「另存为」里取消 → `cancelled`，且**不残留半份文件**（旧实现先落 SVG 再落 PDF，
 *     在 PDF 那步取消会留下一个没人认领的 SVG）。
 *
 * ⚠️ 注意区分**产物底色**与**3D 中间帧**：产物白底，但 3D 取帧仍是透明的
 * （`renderTransparentNow`）——不这样，WebGL 的深色场景底会被一起贴上来。
 * 后者的回归在 `captureTransparent3D` 那组用例里。
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

const saveCalls: { fileName: string; mime: string; data: unknown }[] = [];
let rasterizeBg: (string | null | undefined)[] = [];

vi.mock("../src/export/saveFile", async (orig) => {
  const actual = await (orig as any)();
  return {
    ...actual,
    saveFile: vi.fn(async (req: any) => {
      saveCalls.push({ fileName: req.fileName, mime: req.mime, data: req.data });
      return { status: "saved", path: req.fileName };
    }),
  };
});

vi.mock("../src/export/captureFrame", async (orig) => {
  const actual = await (orig as any)();
  return {
    ...actual,
    // 真实现要等 <img> 解码，jsdom 里永远不 fire
    svgToRaster: vi.fn(async (_svg: string, opts: any) => {
      rasterizeBg.push(opts?.background);
      const c = document.createElement("canvas");
      c.width = 100; c.height = 80;
      return c;
    }),
    capturePngBytes: vi.fn(async () => new Uint8Array([1, 2, 3, 4])),
  };
});

import { exportFigure } from "../src/export/exportFigure";

describe("exportFigure 出口契约：一律 PNG", () => {
  beforeEach(() => {
    saveCalls.length = 0;
    rasterizeBg = [];
  });

  it("二维矢量图 → 只出 PNG（不再有 pdf/svg）", async () => {
    const r = await exportFigure({
      view: "截面",
      nameParts: ["1/0/0", 0],
      vector: { title: "二维截面", panels: [{ svg: `<svg width="200" height="150"><rect width="200" height="150"/></svg>` }] },
    });
    expect(r.status).toBe("exported");
    if (r.status !== "exported") return;
    expect(r.files.map((f) => f.format)).toEqual(["png"]);
    expect(saveCalls).toHaveLength(1);
    expect(saveCalls[0].mime).toBe("image/png");
    expect(saveCalls[0].fileName.endsWith(".png")).toBe(true);
  });

  it("二维矢量图一律白底（栅格化时 background=#ffffff）", async () => {
    await exportFigure({
      view: "截面",
      vector: { panels: [{ svg: `<svg width="100" height="100"><g/></svg>` }] },
    });
    expect(rasterizeBg).toEqual(["#ffffff"]);
  });

  it("调用方显式要透明底时仍能拿到（能力保留，门面默认不再用它）", async () => {
    // 注意：门面在**栅格化那一步**固定传白底（保证不透明），所以这里断言的是
    // "矢量合成层仍认调用方的 background" —— 合成出的 SVG 最底层有没有那块白矩形。
    const { buildVectorFigure } = await import("../src/export/vectorFigure");
    const svg = `<svg width="100" height="100"><g/></svg>`;
    const withWhite = buildVectorFigure({ background: "#ffffff", panels: [{ svg }] });
    const transparent = buildVectorFigure({ background: null, panels: [{ svg }] });
    expect(withWhite.svg).toContain('fill="#ffffff"');
    expect(transparent.svg).not.toContain('fill="#ffffff"');
  });

  it("三维（栅格）通路 → 也是 PNG", async () => {
    const canvas = document.createElement("canvas");
    canvas.width = 320; canvas.height = 240;
    const r = await exportFigure({
      view: "3D预览",
      raster: { panels: [{ kind: "image", canvas }] },
    });
    expect(r.status).toBe("exported");
    if (r.status !== "exported") return;
    expect(r.files.map((f) => f.format)).toEqual(["png"]);
  });

  it("没有可导出内容 → 明确报错，不静默成功", async () => {
    const r = await exportFigure({ view: "空" });
    expect(r.status).toBe("error");
  });
});

/**
 * 3D 透明底取帧：`scene.background` 只做到了"不画背景色"，
 * 场景本身那片实色（`new THREE.Color(0x0d0d22)`）必须**临时**关掉 + 按 alpha=0 清屏，
 * 取完立刻还原 —— 否则"透明 PNG"要么是深蓝底、要么是脏像素。
 */
describe("captureTransparent3D（3D 透明底取帧）", () => {
  /**
   * jsdom 没有真 canvas 实现（`getContext` 返回 null），而 `captureCanvas` 拿不到 ctx
   * 就**不会调用** `renderNow` —— 这里补一个最小 2D 上下文桩，让"取帧窗口内改了什么"
   * 真的能被观察到（否则这条用例只是在测一个从不执行的回调）。
   */
  const stubCtx = () => {
    const orig = HTMLCanvasElement.prototype.getContext;
    (HTMLCanvasElement.prototype as any).getContext = function (type: string) {
      if (type !== "2d") return null;
      return {
        canvas: this, fillStyle: "", imageSmoothingEnabled: false, imageSmoothingQuality: "",
        fillRect() {}, drawImage() {},
      };
    };
    return () => { (HTMLCanvasElement.prototype as any).getContext = orig; };
  };

  it("取帧期间场景背景置空、清屏 alpha=0，取完原样还原", async () => {
    const restore = stubCtx();
    try {
      const { captureTransparent3D } = await import("../src/export/captureFrame");
      const canvas = document.createElement("canvas");
      canvas.width = 40; canvas.height = 30;

      const calls: (number | undefined)[] = [];
      const renderer = {
        setClearColor: (color: number, alpha?: number) => { calls.push(alpha); void color; },
        getClearColor: () => ({ r: 13, g: 13, b: 34 }),
        getClearAlpha: () => 1,
      };
      const scene = { background: "SENTINEL" as unknown };
      let bgDuringRender: unknown = "unset";

      captureTransparent3D(canvas, renderer, scene, () => {
        bgDuringRender = scene.background;
      });

      expect(bgDuringRender).toBeNull();          // 取帧时背景确实被关掉
      expect(calls[0]).toBe(0);                   // 清屏 alpha=0（真透明）
      expect(scene.background).toBe("SENTINEL");  // 取完还原，屏幕观感不变
    } finally {
      restore();
    }
  });

  it("渲染函数抛错也还原背景（不把用户屏幕留在透明状态）", async () => {
    const restore = stubCtx();
    try {
      const { captureTransparent3D } = await import("../src/export/captureFrame");
      const canvas = document.createElement("canvas");
      canvas.width = 20; canvas.height = 20;
      const scene = { background: "SENTINEL" as unknown };
      // captureCanvas 内部 catch 掉渲染异常，这里断言"还原"一定发生
      captureTransparent3D(canvas, { setClearColor: () => {} }, scene, () => { throw new Error("boom"); });
      expect(scene.background).toBe("SENTINEL");
    } finally {
      restore();
    }
  });
});
