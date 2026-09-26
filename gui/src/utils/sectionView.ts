/**
 * sectionView — 二维截面视图的视口 / 变换计算（纯函数，CrossSectionView 唯一实现）。
 *
 * 为什么抽出来：视图变换（viewBox 平移缩放 + `<g>` 旋转/翻转）原先散在组件里，
 * 于是"拖动"与"旋转"两个量互相渗透，产生了一个只有转过角度才看得见的 bug：
 *
 *   旧实现把旋转中心写成 `(viewBox.x - pan.x) + w/zoom/2` —— **跟着平移走**。
 *   `<g transform="scale(1,-1) rotate(θ cx cy)">` 里的 cx 一旦含 pan，
 *   平移量就被卷进旋转矩阵：拖动 Δ 时内容不是沿 Δ 走，而是沿 **Δ 旋转 θ 之后**的方向走
 *   （拖↑它往←走、拖→它往↘走）。用户报的"截面拖动时，如果截面有进行过旋转，
 *   拖动行为就会变得很怪异"就是它（θ=0 时旋转矩阵是单位矩阵，所以平时看不出来）。
 *
 * 不变量（`sectionView.test.ts` 锁死）：**任意旋转角、任意缩放、任意留白下，
 * 拖动 Δ 像素 ⇒ 内容在屏幕上正好移动 Δ 像素**（内容严格跟手）。
 * 由此推出的两条实现约束：
 *   ① 旋转中心**只由内容视口决定，与 pan 无关**（pan 必须留在旋转矩阵之外）；
 *   ② pan 的像素↔用户单位换算用**等比缩放**（preserveAspectRatio="xMidYMid meet" 的
 *      `min(rw/w, rh/h)`），而不是 X 用宽、Y 用高各算一套 —— 后者在长宽比不匹配时
 *      会让"拖 100px 只动 80px"。
 */
export interface SliceViewBox { x: number; y: number; w: number; h: number }
export interface SliceViewState {
  /** 挂载时按内容自动取景得到的视口（用户单位；不含平移与缩放） */
  viewBox: SliceViewBox;
  zoom: number;
  pan: { x: number; y: number };
  /** 视图旋转角（度） */
  rotation: number;
}
export interface SliceRect { width: number; height: number }

const DEG = Math.PI / 180;

/** 当前可见的 viewBox 矩形尺寸（用户单位） */
export function sliceViewportSize(s: SliceViewState): { w: number; h: number } {
  const z = s.zoom || 1;
  return { w: s.viewBox.w / z, h: s.viewBox.h / z };
}

/** `<svg viewBox="...">` 字符串（含平移） */
export function sliceViewBoxString(s: SliceViewState): string {
  const { w, h } = sliceViewportSize(s);
  return `${s.viewBox.x - s.pan.x} ${s.viewBox.y - s.pan.y} ${w} ${h}`;
}

/**
 * 旋转中心（用户坐标）——**不含 pan**。
 *
 * ⚠️ 这里是 bug 的原址：写成 `viewBox.x - pan.x + w/2` 就会让拖动方向随旋转角偏转
 * （见文件头说明与 `sectionView.test.ts` 的反向对照用例）。
 */
export function sliceRotationCenter(s: SliceViewState): { cx: number; cy: number } {
  const { w, h } = sliceViewportSize(s);
  return { cx: s.viewBox.x + w / 2, cy: s.viewBox.y + h / 2 };
}

/** `<g>` 的 transform：先按内容坐标旋转，再做 Y 翻转（SVG 的 Y 朝下） */
export function sliceGroupTransform(s: SliceViewState): string {
  const { cx, cy } = sliceRotationCenter(s);
  return `scale(1,-1) rotate(${s.rotation} ${cx} ${cy})`;
}

/**
 * 用户单位 → 屏幕像素的等比缩放。
 *
 * SVG 默认 `preserveAspectRatio="xMidYMid meet"`：视口长宽比与 viewBox 不一致时
 * 取较小的一边，另一边留白。取 `min()` 才与实际渲染一致。
 */
export function sliceScreenScale(s: SliceViewState, rect: SliceRect): number {
  const { w, h } = sliceViewportSize(s);
  if (!(rect.width > 0) || !(rect.height > 0) || !(w > 0) || !(h > 0)) return 0;
  return Math.min(rect.width / w, rect.height / h);
}

/**
 * 内容点（已投影的 2D 用户坐标，未旋转）→ 屏幕像素（相对 SVG 视口左上角）。
 *
 * 顺序与 DOM 一致：`<g transform="scale(1,-1) rotate(θ cx cy)">` 先旋转后翻转，
 * 再由 viewBox（含 pan/zoom）映射到视口，最后叠加留白偏移。
 * 只用于推导"内容是否跟手"这一不变量；不需要精确像素的地方（如测试之外）不必调用。
 */
export function sliceContentToScreen(
  p: { x: number; y: number }, s: SliceViewState, rect: SliceRect,
): { x: number; y: number } {
  const { w, h } = sliceViewportSize(s);
  const k = sliceScreenScale(s, rect);
  const offX = (rect.width - w * k) / 2;
  const offY = (rect.height - h * k) / 2;
  const { cx, cy } = sliceRotationCenter(s);
  const rad = s.rotation * DEG;
  const c = Math.cos(rad), sn = Math.sin(rad);
  const dx = p.x - cx, dy = p.y - cy;
  const rx = cx + dx * c - dy * sn;
  const ry = cy + dx * sn + dy * c;
  const fy = -ry;                                        // <g> 的 scale(1,-1)
  return {
    x: (rx - (s.viewBox.x - s.pan.x)) * k + offX,
    y: (fy - (s.viewBox.y - s.pan.y)) * k + offY,
  };
}

/**
 * 拖拽 Δ 屏幕像素 → 新 pan（**内容严格跟手**：1:1，与旋转角/缩放/留白无关）。
 *
 * 推导：可见 viewBox 原点 = `viewBox.x - pan.x`，故 pan.x 增加 δ ⇒ 内容在屏幕上右移 `δ·k`。
 * 要让内容右移 `dxPx` 就取 `δ = dxPx / k`（k = 等比缩放）。
 * 旧实现用的是 `dx * (w/zoom)/rect.width`：长宽比匹配时与 1/k 相等（所以平时看不出来），
 * 一旦留白就偏小 ⇒ 拖动跟不上鼠标。
 */
export function panAfterDrag(
  pan: { x: number; y: number }, dxPx: number, dyPx: number,
  s: SliceViewState, rect: SliceRect,
): { x: number; y: number } {
  const k = sliceScreenScale(s, rect);
  if (!(k > 0)) return pan;
  return { x: pan.x + dxPx / k, y: pan.y + dyPx / k };
}
