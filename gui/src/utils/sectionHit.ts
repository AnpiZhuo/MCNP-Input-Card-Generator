/**
 * sectionHit — 二维截面的**绘制次序**与**命中次序**（深模块，纯函数）。
 *
 * ## 这个模块存在的理由
 * 截面在屏幕上是一堆半透明多边形叠着画的，所以"鼠标下面到底是哪个栅元"只能有一个答案：
 * **最上面那个**。而"谁在最上面"由绘制次序决定 —— 两者必须来自同一个次序，
 * 否则就会出现"图看着是 A 盖住 B，悬停却报 B"这种不一致。
 *
 * 2026-09-19 的真 bug 正是这条：绘制按 `slices` 顺序（= 栅元卡的**声明顺序**），
 * 后声明的画在上面；而命中检测却从数组头开始找**第一个**包含点的多边形 ⇒ 报的是
 * 最先声明的那个栅元。实测 q1112 卡在 X=0 平面：栅元 2（水，r≤1）与栅元 3（钢，r≤4）
 * 在中心重叠，图上钢盘盖住水芯，悬停却报 `2 · M1`。
 *
 * ## 为什么不是"反过来改绘制次序"
 * 那样会改变**图形本身**（谁盖住谁），属于另一个更大的决定（要让 MCNP 的"先声明者
 * 占有重叠区"语义真正生效，得做多边形布尔裁剪）；本模块只保证**读数与图形一致**。
 * 将来若真做了裁剪，绘制次序会变，那时**只改 `paintOrder` 一处**，命中自动跟随。
 */

export interface SectionCellLike {
  number: number | string;
}

/** 命中判定的结果：命中的栅元（只带出宿主需要的字段） */
export interface SectionHit<T> {
  cell: T;
  /** 该点在**投影后 2D 坐标**里的位置，原样回带，便于宿主反投影成 3D */
  x: number;
  y: number;
}

/**
 * 绘制次序：**后声明的栅元画在上面**（后来的盖住先来的）。
 *
 * 返回新数组，不改入参。`cellOrder` 给的是 deck 里的声明顺序（栅元号数组）；
 * 没在其中的栅元排在末尾（各自保持相对次序）——它们不在卡里，无从谈声明先后。
 */
export function paintOrder<T extends SectionCellLike>(
  cells: readonly T[],
  cellOrder?: readonly (number | string)[] | null,
): T[] {
  const arr = [...cells];
  if (!cellOrder || cellOrder.length === 0) return arr;
  const rank = new Map<string, number>();
  cellOrder.forEach((n, i) => rank.set(String(n), i));
  const key = (c: T, i: number): number => {
    const r = rank.get(String(c.number));
    return r === undefined ? Number.MAX_SAFE_INTEGER + i : r;
  };
  const decorated = arr.map((c, i) => ({ c, i, k: key(c, i) }));
  // 稳定排序：k 相同（都缺声明次序）时保持原相对位置
  decorated.sort((a, b) => (a.k !== b.k ? a.k - b.k : a.i - b.i));
  return decorated.map((d) => d.c);
}

/** 射线法：点 (px,py) 是否在多边形内（多边形为 2D 点序列，闭合由实现隐含） */
export function pointInPolygon(poly: readonly { x: number; y: number }[], px: number, py: number): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i].x, yi = poly[i].y;
    const xj = poly[j].x, yj = poly[j].y;
    if ((yi > py) !== (yj > py) && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/**
 * 栅元区域判定：点是否属于该栅元 —— 环集合的**奇偶**规则。
 *
 * ## 为什么必须是奇偶，而不是"落在任意一个环里"
 * 后端返回的 `polygons` 是**一串闭合环**，没有"谁是外圈、谁是洞"的标记。环只是
 * **边界曲线**，所以区域内部 = 被**奇数条**环套住的点。于是：
 *   · 内孔：被外圈 + 孔圈套住 = 2 层（偶）⇒ **不属于**该栅元；
 *   · 孔里的孤岛（同一栅元的不连通并集）：外圈 + 孔圈 + 孤岛圈 = 3 层（奇）⇒ 属于。
 * 2026-10-07 用户实测的 bug 正是这条没做：栅元 6（水体）的截面是"一大片 + ρ<6 的孔"，
 * 旧判据"落在任意一环内即命中"把孔也算成水 ⇒ 孔里的石墨/聚乙烯被水色盖住，悬停报水。
 *
 * ## 为什么不用绕向（winding）
 * 环的方向**不可信**：实测同一张卡里，栅元 2 的孔环与外环反号（−63.5 / +78.4），
 * 而栅元 1 的三个环全为正号 ⇒ 只能按包含关系取奇偶。
 *
 * 与 `fill-rule="evenodd"` 严格同义 —— 渲染与命中因此可以共用这一条规则。
 */
export function pointInCell(
  loops: readonly (readonly { x: number; y: number }[])[],
  px: number,
  py: number,
): boolean {
  let inside = false;
  for (const lp of loops) {
    if (lp.length >= 3 && pointInPolygon(lp, px, py)) inside = !inside;
  }
  return inside;
}

/**
 * 命中检测：返回**最上面**那个包含该点的栅元（与绘制次序严格一致）。
 *
 * 从绘制次序的**末尾**往前找：末尾画得最晚 ⇒ 视觉最上层 ⇒ 优先报它。
 * "包含该点"用 `pointInCell`（奇偶）——与渲染的 even-odd 填充同源，
 * 否则会出现"图上这块是空的，悬停却报某个栅元"。
 * 没有任何栅元包含该点 → `null`（宿主据此隐藏悬停框）。
 */
export function topMostHit<T extends SectionCellLike>(
  cells: readonly T[],
  polygonsOf: (cell: T) => readonly (readonly { x: number; y: number }[])[],
  px: number,
  py: number,
): T | null {
  for (let i = cells.length - 1; i >= 0; i--) {
    if (pointInCell(polygonsOf(cells[i]), px, py)) return cells[i];
  }
  return null;
}
