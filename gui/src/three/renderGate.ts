/**
 * renderGate — 按需渲染门（dirty flag）
 *
 * 交互卡根因之一：渲染循环无条件每 rAF render，场景零变化也白跑。
 * 本模块只在 dirty 被置位的那一帧调用 onRender（其余帧空转）。
 *
 * 接线方负责在所有状态变更点调 markDirty()：
 * controls change、WASD 移动、loadStlMeshes、setVisible/setColor/selectAll、
 * resizeRenderer。OrbitControls enableDamping 衰减期持续触发 change →
 * dirty 保持 true 直到停稳，视觉无损。
 *
 * requestFrame/cancelFrame 依赖注入（测试假 rAF），生产用 rAF。
 */
export interface RenderLoop {
  markDirty(): void;
  dispose(): void;
}

export interface RenderLoopOptions {
  requestFrame?: (cb: () => void) => number;
  cancelFrame?: (id: number) => void;
  onRender: () => void;
}

export function createRenderLoop(opts: RenderLoopOptions): RenderLoop {
  const requestFrame = opts.requestFrame ?? ((cb: () => void) => requestAnimationFrame(cb));
  const cancelFrame = opts.cancelFrame ?? ((id: number) => cancelAnimationFrame(id));
  let running = true;
  let dirty = false;
  let rafId: number | null = null;

  function loop() {
    if (!running) return;
    rafId = requestFrame(loop);
    if (dirty) {
      dirty = false;
      opts.onRender();
    }
  }

  rafId = requestFrame(loop);

  return {
    markDirty() {
      dirty = true;
    },
    dispose() {
      running = false;
      if (rafId != null) cancelFrame(rafId);
    },
  };
}
