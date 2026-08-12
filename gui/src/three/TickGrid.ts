/**
 * TickGrid — 动态刻度线/标签生命周期管理（深模块）
 *
 * 交互卡根因：rebuildTicks 相机 change 每帧重建 ~160 对象 / 81 张 CanvasTexture，
 * 且只 dispose sprite material，Line geometry 与 CanvasTexture 从未 dispose → GPU 泄漏。
 *
 * 本模块隐藏 台账/步长/格式化/定位/生命周期：
 * - rebuild 先完整 dispose 旧的（line.geometry/material + sprite.material + sprite.material.map）
 *   再建新的；台账 createdGeoms/createdTexs/disposedGeoms/disposedTexs 记账。
 * - planTickStep 纯函数：STEPS 表扩到 1e6（原表止于 500），dist/5 档位 → 每轴 ≤ ~10 刻度，
 *   避免大 dist 下 step 饱和 500 导致刻度爆炸。
 * - createTexture 依赖注入（默认 CanvasTexture），测试注入假纹理记账 dispose。
 */
import * as THREE from "three";

/** 步长档位表：1e-3 … 1e6（原实现止于 500，大 dist 下饱和导致刻度爆炸） */
const TICK_STEPS = [
  0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 10, 20, 50, 100, 200, 500,
  1000, 2000, 5000, 1e4, 2e4, 5e4, 1e5, 2e5, 5e5, 1e6,
];

/** 按镜头距离取严格步长档位（目标每轴 ≤ 10 刻度） */
export function planTickStep(dist: number): number {
  const rawStep = dist / 5;
  for (const s of TICK_STEPS) {
    if (s >= rawStep) return s;
  }
  return TICK_STEPS[TICK_STEPS.length - 1];
}

export interface TextureFactory {
  (label: string, color: number): THREE.Texture;
}

export interface TickGridAxis {
  dir: [number, number, number];
  color: number;
}

export interface RebuildResult {
  /** 本次新建对象数（line + sprite 计数） */
  created: number;
  /** 本次释放对象数（上一批的 line + sprite 计数） */
  disposed: number;
  /** 本次新建纹理数 */
  textures: number;
}

export interface TickGrid {
  rebuild(opts: { dist: number; axes: TickGridAxis[] }): RebuildResult;
  dispose(): void;
}

/** 默认纹理工厂：canvas 画黑底标签（依赖注入的兜底实现） */
function defaultTextureFactory(label: string, color: number): THREE.Texture {
  const c = document.createElement("canvas");
  c.width = 128;
  c.height = 48;
  const ctx = c.getContext("2d");
  if (ctx) {
    ctx.fillStyle = "rgba(0,0,0,0.4)";
    ctx.fillRect(0, 4, 128, 40);
    ctx.fillStyle = "#" + color.toString(16).padStart(6, "0");
    ctx.font = "Bold 28px Arial";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label, 64, 26);
  }
  return new THREE.CanvasTexture(c);
}

/** 轴的垂直基向量（与既有轴顺序 X/Z/Y 的 perp 选择一致） */
function perpBasis(dir: [number, number, number]): {
  perp1: THREE.Vector3;
  perp2: THREE.Vector3;
} {
  const ax = Math.abs(dir[0]);
  const ay = Math.abs(dir[1]);
  const az = Math.abs(dir[2]);
  if (ax > 0.9) return { perp1: new THREE.Vector3(0, 0, 1), perp2: new THREE.Vector3(0, 1, 0) };
  if (ay > 0.9) return { perp1: new THREE.Vector3(1, 0, 0), perp2: new THREE.Vector3(0, 0, 1) };
  if (az > 0.9) return { perp1: new THREE.Vector3(1, 0, 0), perp2: new THREE.Vector3(0, 1, 0) };
  return { perp1: new THREE.Vector3(0, 0, 1), perp2: new THREE.Vector3(0, 1, 0) };
}

export function createTickGrid(
  group: THREE.Group,
  createTexture?: TextureFactory,
): TickGrid {
  const texFactory = createTexture ?? defaultTextureFactory;

  // 台账：累计新建/释放（几何 + 纹理）
  let createdGeoms = 0;
  let createdTexs = 0;
  let disposedGeoms = 0;
  let disposedTexs = 0;

  // 当前存活对象
  const lines: THREE.Line[] = [];
  const sprites: THREE.Sprite[] = [];

  /** 完整释放当前全部对象，返回释放的对象数（line+sprite） */
  function clearAll(): number {
    for (const line of lines) {
      line.geometry.dispose();
      (line.material as THREE.Material).dispose();
      disposedGeoms += 1;
    }
    for (const sprite of sprites) {
      const mat = sprite.material as THREE.SpriteMaterial;
      mat.dispose();
      mat.map?.dispose();
      disposedTexs += 1;
    }
    const removed = lines.length + sprites.length;
    for (const child of [...group.children]) group.remove(child);
    lines.length = 0;
    sprites.length = 0;
    return removed;
  }

  function makeSprite(text: string, color: number, scale: number): THREE.Sprite | null {
    try {
      const tex = texFactory(text, color);
      const mat = new THREE.SpriteMaterial({ map: tex, depthTest: false, sizeAttenuation: true });
      const sprite = new THREE.Sprite(mat);
      sprite.scale.set(scale, scale * 0.35, 1);
      return sprite;
    } catch (e) {
      console.warn("[3D] makeNumberSprite error:", e);
      return null;
    }
  }

  function rebuild(opts: { dist: number; axes: TickGridAxis[] }): RebuildResult {
    const disposed = clearAll();
    const dist = opts.dist;
    const step = planTickStep(dist);
    const tickDecimals = Math.max(0, Math.ceil(-Math.log10(step)));
    const extent = dist;
    const tickLen = 0.15 * (dist / 8);

    let created = 0;
    let textures = 0;

    for (const ax of opts.axes) {
      const dir = new THREE.Vector3(ax.dir[0], ax.dir[1], ax.dir[2]);
      const color = ax.color;
      const perp = perpBasis(ax.dir);
      const perp1 = perp.perp1;
      const perp2 = perp.perp2;

      const start = Math.ceil(-extent / step) * step;
      for (let s = start; s <= extent; s += step) {
        if (Math.abs(s) < step * 0.01) continue;
        const pos = dir.clone().multiplyScalar(s);
        const tA = pos.clone().add(perp1.clone().multiplyScalar(-tickLen));
        const tB = pos.clone().add(perp1.clone().multiplyScalar(tickLen));
        const tickGeo = new THREE.BufferGeometry().setFromPoints([tA, tB]);
        const tickLine = new THREE.Line(tickGeo, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.5 }));
        group.add(tickLine);
        lines.push(tickLine);
        createdGeoms += 1;
        created += 1;

        const label = s.toFixed(tickDecimals);
        const sprite = makeSprite(label, color, dist / 12);
        if (sprite) {
          sprite.position.copy(
            pos
              .clone()
              .add(perp1.clone().multiplyScalar(-tickLen * 2.5))
              .add(perp2.clone().multiplyScalar(-tickLen * 1.5)),
          );
          group.add(sprite);
          sprites.push(sprite);
          createdTexs += 1;
          textures += 1;
          created += 1;
        }
      }
    }
    return { created, disposed, textures };
  }

  function dispose() {
    clearAll();
  }

  return { rebuild, dispose };
}
