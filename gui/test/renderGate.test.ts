import { describe, it, expect, vi } from "vitest";
import { createRenderLoop } from "../src/three/renderGate";

describe("createRenderLoop", () => {
  it("idle does not render; markDirty renders exactly once", () => {
    const frames: (() => void)[] = [];
    const onRender = vi.fn();
    const loop = createRenderLoop({
      requestFrame: (cb) => { frames.push(cb); return frames.length; },
      cancelFrame: () => {},
      onRender,
    });

    // 不 markDirty 跑 5 帧 → onRender 调用 0 次
    for (let i = 0; i < 5; i++) {
      const frame = frames.shift();
      expect(frame).toBeDefined();
      frame!();
    }
    expect(onRender).toHaveBeenCalledTimes(0);

    // markDirty 后下一帧恰渲染 1 次
    loop.markDirty();
    const frame = frames.shift();
    expect(frame).toBeDefined();
    frame!();
    expect(onRender).toHaveBeenCalledTimes(1);

    // 后续不 markDirty → 不再渲染
    for (let i = 0; i < 5; i++) {
      const f = frames.shift();
      expect(f).toBeDefined();
      f!();
    }
    expect(onRender).toHaveBeenCalledTimes(1);

    loop.dispose();
  });

  it("dispose stops rendering even if a scheduled frame runs", () => {
    const frames: (() => void)[] = [];
    const onRender = vi.fn();
    const loop = createRenderLoop({
      requestFrame: (cb) => { frames.push(cb); return frames.length; },
      cancelFrame: () => {},
      onRender,
    });
    loop.markDirty();
    loop.dispose();
    const frame = frames.shift();
    if (frame) frame();
    expect(onRender).not.toHaveBeenCalled();
  });
});
