/**
 * frameBox — 3D 预览**取景盒口径**（纯函数，无 THREE 依赖）。
 *
 * 两条，缺一条就会重现"模型缩成一点"：
 *   ① 不可见栅元不参与取景；
 *   ② 真空（material 0）即使勾选可见也不参与取景（用户口径：「不影响实体查看」）。
 * 取景主导 = 可见实体并集；一个实体都没有（纯真空 deck）时回退为全部可见并集。
 *
 * 背景一句话：`frameCamera` 原来对所有 mesh 求并集而不看 `visible`，画不出来的巨型外围壳
 * （实测直径 500 cm）照样把相机撑开；当年误判成"墓地照画"，去后端加 imp/注释判据，
 * 最终把用户 s.i 的 35 个栅元全吞掉、预览全空。**取景的缺陷只在取景侧修。**
 * 回归：`gui/test/frameBox.test.ts`（两条口径各有变异红证）。
 */
export type Vec3 = [number, number, number];

export interface BoxLike {
  min: Vec3;
  max: Vec3;
}

export interface FrameCandidate {
  /** 栅元包围盒；无（几何未算 boundingBox）→ null，跳过 */
  box: BoxLike | null;
  /** 不可见的栅元**不得**参与取景 */
  visible: boolean;
  /** 是否实体（material ≠ 0）；真空只作装饰，不参与取景 */
  solid: boolean;
}

export interface FrameBoxResult {
  /** 取景主导盒 = 可见实体并集（无实体时回退为全部可见）—— 相机 target 的来源 */
  model: BoxLike;
  /** 算相机距离用的盒 = model ∪ extra ∪ 原点 */
  frame: BoxLike;
  center: Vec3;
  size: Vec3;
}

const EMPTY: BoxLike = { min: [Infinity, Infinity, Infinity], max: [-Infinity, -Infinity, -Infinity] };

function isEmpty(b: BoxLike): boolean {
  return b.min[0] > b.max[0];
}

function union(a: BoxLike, b: BoxLike): BoxLike {
  if (isEmpty(a)) return { min: [...b.min] as Vec3, max: [...b.max] as Vec3 };
  if (isEmpty(b)) return { min: [...a.min] as Vec3, max: [...a.max] as Vec3 };
  return {
    min: [Math.min(a.min[0], b.min[0]), Math.min(a.min[1], b.min[1]), Math.min(a.min[2], b.min[2])],
    max: [Math.max(a.max[0], b.max[0]), Math.max(a.max[1], b.max[1]), Math.max(a.max[2], b.max[2])],
  };
}

/**
 * @param opts.extra 额外取景目标（线框 / 格阵装配），只撑 frame 尺寸，不改 center
 * @param opts.includeOrigin 是否把原点（坐标轴所在）纳入 frame；默认 true
 * @returns null = 不取景（无可见栅元且无 extra），与旧 `modelBox.isEmpty() && !extra` 一致；
 *          center 口径也不回退：并集为空时取 (0,0,0)（旧 `Box3.getCenter` 对空盒即此）。
 */
export function computeFrameBox(
  candidates: FrameCandidate[],
  opts: { extra?: BoxLike | null; includeOrigin?: boolean } = {},
): FrameBoxResult | null {
  let solids = EMPTY;
  let visibles = EMPTY;
  for (const c of candidates) {
    if (!c || !c.box || c.visible === false) continue;
    visibles = union(visibles, c.box);
    if (c.solid) solids = union(solids, c.box);
  }
  const model = !isEmpty(solids) ? solids : visibles;   // 无实体可看 → 回退全部可见
  const hasModel = !isEmpty(model);

  let frame = hasModel ? model : EMPTY;
  if (opts.extra) frame = union(frame, opts.extra);
  if (!hasModel && isEmpty(frame)) return null;
  if (opts.includeOrigin !== false) frame = union(frame, point());

  const center: Vec3 = hasModel
    ? [(model.min[0] + model.max[0]) / 2, (model.min[1] + model.max[1]) / 2, (model.min[2] + model.max[2]) / 2]
    : [0, 0, 0];
  return { model, frame, center, size: sub(frame.max, frame.min) };
}

function point(): BoxLike {
  return { min: [0, 0, 0], max: [0, 0, 0] };
}

function sub(a: Vec3, b: Vec3): Vec3 {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}
