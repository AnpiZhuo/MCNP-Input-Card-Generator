/**
 * alignWorld — 几何外壳与体积盒世界坐标对齐核心（契约 meshtal-visualization.md §7）
 *
 * 坐标事实（§7.1）：外壳 STL（preview-3d 产自 deck 曲面/栅元全局坐标）与
 * 体积盒（meshtal bin 边界，MCNP 结果即全局坐标）天然同坐标系，只需「统一归一化」。
 *
 * 机制（§7.2）：单一归一化偏移 offset = -unionBox.center，外壳与体积盒共用同一
 * offset → 世界坐标相对几何逐点保留，两者在场景坐标中与在世界坐标中重合关系一致。
 *
 * 验收（§7.3 四断言）：
 *  1. shared_offset_invariant：SminScene == Smin + offset、VminScene == Vmin + offset
 *  2. world_box_from_edges：每轴 min=edge[0]、max=edge[-1]
 *  3. volume_inside_shell：归一化后体积盒场景包围盒 ⊆ 外壳场景包围盒
 *  4. 尺寸保持 / 相对位移保持
 */
export type Vec3 = [number, number, number];

export interface AABB {
  min: Vec3;
  max: Vec3;
}

/** 体积盒：由 meshtal bin 边界边数组构建全局包围盒（每轴 min=edge[0]、max=edge[-1]） */
export function worldBoxFromEdges(edges: { x: number[]; y: number[]; z: number[] }): AABB {
  return {
    min: [edges.x[0], edges.y[0], edges.z[0]],
    max: [edges.x[edges.x.length - 1], edges.y[edges.y.length - 1], edges.z[edges.z.length - 1]],
  };
}

export function boxCenter(box: AABB): Vec3 {
  return [(box.min[0] + box.max[0]) / 2, (box.min[1] + box.max[1]) / 2, (box.min[2] + box.max[2]) / 2];
}

export function boxSize(box: AABB): Vec3 {
  return [box.max[0] - box.min[0], box.max[1] - box.min[1], box.max[2] - box.min[2]];
}

/** 多个包围盒的并集（体积盒 ⊆ 外壳时 union = 外壳） */
export function unionBoxes(boxes: AABB[]): AABB {
  const min: Vec3 = [Infinity, Infinity, Infinity];
  const max: Vec3 = [-Infinity, -Infinity, -Infinity];
  for (const b of boxes) {
    for (let i = 0; i < 3; i++) {
      if (b.min[i] < min[i]) min[i] = b.min[i];
      if (b.max[i] > max[i]) max[i] = b.max[i];
    }
  }
  return { min, max };
}

/** 平移接口：THREE.BufferGeometry.translate 满足（保持模块无 THREE 依赖，可测） */
export interface Translatable {
  translate(x: number, y: number, z: number): void;
}

/**
 * 单一归一化偏移：把给定几何逐个平移到 box 中心，返回 offset = -center。
 * 外壳 STL 与体积盒必须共用此 offset（§7.2 关键不变量）。
 */
export function translateToCenter(geometries: Translatable[], box: AABB): Vec3 {
  const c = boxCenter(box);
  const offset: Vec3 = [-c[0], -c[1], -c[2]];
  for (const g of geometries) g.translate(offset[0], offset[1], offset[2]);
  return offset;
}

/** 向量 + offset（用于把全局包围盒角点换算到场景坐标） */
export function applyOffset(vec: Vec3, offset: Vec3): Vec3 {
  return [vec[0] + offset[0], vec[1] + offset[1], vec[2] + offset[2]];
}

/**
 * AABB + offset → 场景盒（尺寸不变，min/max 同步平移）。
 * 对齐不变式（§7）：相机取景、体积盒、外壳几何必须共用同一 offset；
 * 相机若用未 offset 的 world 盒会盯着原中心而物体已被平移到原点（P0 相机错位根因）。
 */
export function applyOffsetToBox(box: AABB, offset: Vec3): AABB {
  return { min: applyOffset(box.min, offset), max: applyOffset(box.max, offset) };
}

/**
 * 开窗取景盒判定阈值：体积盒最大边 / 并集最大边 < 此值 → 外壳远大于体积盒，
 * 以体积盒为主取景（用户反馈「默认视距特别大、把栅元弄的特别小」）。
 */
export const VOLUME_FRAMING_RATIO = 0.25;

/** 两盒是否空间相交（任一轴 min≥max 或 max≤min 即分离） */
export function boxesOverlap(a: AABB, b: AABB): boolean {
  for (let i = 0; i < 3; i++) {
    if (a.min[i] >= b.max[i] || b.min[i] >= a.max[i]) return false;
  }
  return true;
}

/**
 * 开窗取景盒（A2.1 修正版，纯函数）：
 * - 无外壳 / 外壳 ⊆ 体积 / 外壳与体积可比（比例 ≥ 阈值）→ 返回并集（既有行为，中心重合不回归）
 * - 外壳 ≫ 体积盒（体积盒最大边 < 25% 并集最大边）→ 返回体积盒（体积层清晰可辨，避免视距过大）
 * - 外壳与体积盒**空间不相交**（网格与模型不在一起）→ 返回并集（两者都可见；
 *   否则体积盒取景会把模型挤出屏幕，观感=「体积层错位」，A1.2 横幅同步解释）
 * 仅影响相机取景；共享归一化 offset 仍按并集（§7.2 对齐不变量不变）。
 */
export function computeFramingBox(shellBox: AABB | null, volumeBox: AABB): AABB {
  if (shellBox == null) return volumeBox;
  if (!boxesOverlap(shellBox, volumeBox)) return unionBoxes([shellBox, volumeBox]);
  const union = unionBoxes([shellBox, volumeBox]);
  const unionMaxDim = Math.max(boxSize(union)[0], boxSize(union)[1], boxSize(union)[2]);
  const volMaxDim = Math.max(boxSize(volumeBox)[0], boxSize(volumeBox)[1], boxSize(volumeBox)[2]);
  const ratio = unionMaxDim > 0 ? volMaxDim / unionMaxDim : 1;
  return ratio < VOLUME_FRAMING_RATIO ? volumeBox : union;
}
