/**
 * captureFrame — 把一块 WebGL 画布**可靠地**变成一张图。
 *
 * ## 为什么不能直接 canvas.toDataURL()
 * 本程序所有 3D 视图都用 `THREE.WebGLRenderer`，且**没开 `preserveDrawingBuffer`**
 * （`useThreeCanvas` / `Preview3D` / `VolumeRenderer` / `PtracRenderer` / `SourceDemoRenderer`
 * 五处都是），再叠加按需渲染（`renderGate` 只在 dirty 时画一帧）。
 * 浏览器在合成后会清掉那块 drawing buffer ⇒ 直接取图**大概率全黑/全空**。
 *
 * 可靠做法（three.js 官方认可）：**在同一个任务里先同步 `renderer.render()` 再取图**。
 * 所以本模块要求调用方给一个 `renderNow()` —— 它必须**同步画完**，异步（等 rAF）就白搭。
 * 这个约束是这个模块接口里最重要的一条，写在这里而不是藏在实现里。
 *
 * ## 为什么 2× 不走"改 renderer.setSize"
 * 改真实 renderer 的尺寸会重建 drawing buffer、跑 resize 分支，交互中可能闪一下甚至触发
 * 重算（体积纹理）。这里改为：原图 → 放大到目标尺寸的离屏画布（`imageSmoothingQuality: high`）。
 * 效果是"高分辨率、平滑、绝不动渲染器状态"，代价是细节不是真采样 2×（对本用途够）。
 * 将来若要真采样，只需在这里补一条"临时放大 renderer 重画一帧再还原"的内部路径——
 * 调用方接口不变。
 */

export interface CaptureOptions {
  /** 目标放大倍数（1 = 原尺寸）。默认 1。 */
  scale?: number;
  /** 底色：`"#ffffff"` 白底 / `null` 透明底；缺省取 canvas 自身的黑底（不处理）。 */
  background?: string | null;
  /**
   * 同步重画当前帧（**必须同步**）。
   * 3D 视图传 `() => renderer.render(scene, camera)`；2D 画布不需要传。
   */
  renderNow?: () => void;
  /** 目标 `type`（默认 PNG） */
  mime?: "image/png" | "image/jpeg";
  /** JPEG 质量（仅 jpeg） */
  quality?: number;
}

/** 取当前帧 → 一张（可放大/可加底色的）离屏画布。失败返回 null（如画布尺寸为 0）。 */
export function captureCanvas(canvas: HTMLCanvasElement | null | undefined, opts: CaptureOptions = {}): HTMLCanvasElement | null {
  if (!canvas) return null;
  const scale = Math.max(1, opts.scale ?? 1);
  const sw = canvas.width;
  const sh = canvas.height;
  if (!sw || !sh) return null;

  const out = document.createElement("canvas");
  out.width = Math.round(sw * scale);
  out.height = Math.round(sh * scale);
  const ctx = out.getContext("2d");
  if (!ctx) return null;

  if (opts.background !== null && opts.background !== undefined) {
    ctx.fillStyle = opts.background;
    ctx.fillRect(0, 0, out.width, out.height);
  }
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  try {
    // ⚠️ 顺序不可交换：先同步重画，再立刻取像素
    opts.renderNow?.();
    ctx.drawImage(canvas, 0, 0, out.width, out.height);
  } catch (e) {
    console.warn("[captureFrame] 取帧失败", e);
    return null;
  }
  return out;
}

/** 取当前帧 → `data:` URL。 */
export function captureDataUrl(canvas: HTMLCanvasElement | null | undefined, opts: CaptureOptions = {}): string | null {
  const c = captureCanvas(canvas, opts);
  if (!c) return null;
  try {
    return c.toDataURL(opts.mime ?? "image/png", opts.quality);
  } catch (e) {
    console.warn("[captureFrame] 编码失败", e);
    return null;
  }
}

/** 取当前帧 → PNG 字节（给"直接落盘"用，避免 data URL 的 base64 膨胀）。 */
export async function capturePngBytes(canvas: HTMLCanvasElement | null | undefined, opts: CaptureOptions = {}): Promise<Uint8Array | null> {
  const c = captureCanvas(canvas, opts);
  if (!c) return null;
  const url = c.toDataURL("image/png");
  const comma = url.indexOf(",");
  if (comma < 0) return null;
  return base64ToBytes(url.slice(comma + 1));
}

/** base64 → 字节（浏览器原生 atob；不引依赖） */
export function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/**
 * RGBA 像素 → PNG `data:` URL（给"矢量图上叠一层位图热图"用）。
 *
 * 热图只有位图形式，而等值线是真矢量 —— 论文图里常见的就是"位图底 + 矢量线"。
 * 无 canvas 的环境（jsdom 单测）返回 null，调用方只画矢量部分，**不整体失败**。
 */
export function rgbaToPngDataUrl(rgba: Uint8ClampedArray, width: number, height: number): string | null {
  if (typeof document === "undefined" || !width || !height) return null;
  try {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    const img = ctx.createImageData(width, height);
    img.data.set(rgba);
    ctx.putImageData(img, 0, 0);
    return canvas.toDataURL("image/png");
  } catch (e) {
    console.warn("[captureFrame] RGBA→PNG 失败", e);
    return null;
  }
}

/** SVG 文本 → PNG 字节（把 DOM/SVG 图放进位图合成链路，或给 PDF 当底图）。 */
export async function svgToRaster(svg: string, opts: CaptureOptions = {}): Promise<HTMLCanvasElement | null> {
  const scale = Math.max(1, opts.scale ?? 1);
  const { width, height } = svgSize(svg);
  if (!width || !height) return null;
  const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  try {
    const img = await loadImage(url);
    const out = document.createElement("canvas");
    out.width = Math.round(width * scale);
    out.height = Math.round(height * scale);
    const ctx = out.getContext("2d");
    if (!ctx) return null;
    if (opts.background !== null && opts.background !== undefined) {
      ctx.fillStyle = opts.background;
      ctx.fillRect(0, 0, out.width, out.height);
    }
    ctx.drawImage(img, 0, 0, out.width, out.height);
    return out;
  } catch (e) {
    console.warn("[captureFrame] SVG 栅格化失败", e);
    return null;
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** 从 SVG 文本读尺寸（优先 width/height 属性，退回 viewBox） */export function svgSize(svg: string): { width: number; height: number } {
  const wAttr = /\bwidth\s*=\s*"([\d.]+)(px)?"/.exec(svg);
  const hAttr = /\bheight\s*=\s*"([\d.]+)(px)?"/.exec(svg);
  if (wAttr && hAttr) return { width: parseFloat(wAttr[1]), height: parseFloat(hAttr[1]) };
  const vb = /\bviewBox\s*=\s*"([-\d.]+)[\s,]+([-\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)"/.exec(svg);
  if (vb) return { width: parseFloat(vb[3]), height: parseFloat(vb[4]) };
  return { width: 0, height: 0 };
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("图片解码失败"));
    img.src = url;
  });
}

/**
 * 需要在导出时"钉死"成内联样式的属性（SVG 出图后没有 CSS 环境，全靠内联）。
 * ⚠️ 只对**子节点**内联：根节点的 style 稍后会被整体清掉（去掉屏幕定位样式），
 * 内联到根上等于白做 —— 见下方循环里的说明。
 */
const SVG_STYLE_PROPS = [
  "fill", "fill-opacity", "fill-rule",
  "stroke", "stroke-width", "stroke-opacity", "stroke-dasharray", "stroke-linecap", "stroke-linejoin",
  "opacity", "visibility", "display",
  "font-family", "font-size", "font-weight", "font-style", "text-anchor", "dominant-baseline",
  "paint-order", "shape-rendering", "vector-effect",
];

/**
 * 从活着的 DOM 里"抓"一张自洽的矢量 SVG 字符串。
 *
 * 为什么必须内联样式：屏幕上的样式来自 CSS（类选择器 / CSS 变量 / 主题），而导出后的 SVG
 * 脱离文档就没有 CSS 环境了 —— 不内联的话，导出的图会变成**默认黑填充**（轮廓糊成一片）。
 * 同时剥掉交互态元素（悬停提示、选中框）——它们不属于"图"。
 *
 * @param el 目标 `<svg>`（一般是 `svgRef.current`）
 * @param stripSelector 额外要剔除的元素选择器（如悬停提示层）
 */
export function snapshotSvg(el: SVGSVGElement | null | undefined, opts: { stripSelector?: string; background?: string | null } = {}): string | null {
  if (!el || typeof window === "undefined") return null;
  try {
    const clone = el.cloneNode(true) as SVGSVGElement;
    if (opts.stripSelector) {
      clone.querySelectorAll(opts.stripSelector).forEach((n) => n.remove());
    }
    const src = el;
    const dst = clone;
    /**
     * ⚠️ 两棵树必须**同构配对**：`stripSelector` 已从 clone 里删过元素，
     * 若还按下标配对，删除点之后的所有节点都会错位一格 —— 样式会贴到错误的元素上
     * （表现为导出图里颜色/线宽串味，且极难定位）。这里先过滤掉 clone 里不存在的源节点，
     * 再做逐位配对。
     */
    const srcAll: Element[] = [src, ...Array.from(src.querySelectorAll("*"))];
    const dstAll: Element[] = [dst, ...Array.from(dst.querySelectorAll("*"))];
    const srcNodes = opts.stripSelector
      ? srcAll.filter((n) => n === src || !n.matches(opts.stripSelector!))
      : srcAll;
    const srcNodes2 = srcNodes;
    const dstNodes = dstAll;
    for (let i = 0; i < srcNodes2.length && i < dstNodes.length; i++) {
      const from = srcNodes2[i] as Element;
      const to = dstNodes[i] as HTMLElement;
      if (!to.style || typeof window.getComputedStyle !== "function") continue;
      // 根节点不内联屏幕样式：克隆根上可能带着 position/inset 这类**布局**样式，
      // 后面要靠 removeAttribute("style") 清掉它们 —— 若先把视觉样式也内联到根上，
      // 那一步会把它们一起删掉（fill/font-family 变成默认黑，导出图整片发黑）。
      if (from === src) continue;
      const cs = window.getComputedStyle(from);
      for (const prop of SVG_STYLE_PROPS) {
        const v = cs.getPropertyValue(prop);
        // 空值与默认值不写：写了反而把继承来的正确颜色盖掉
        if (!v || v === "normal" || v === "auto") continue;
        to.style.setProperty(prop, v.trim());
      }
      /**
       * ⚠️ 只摘掉**值里含 `var()` 的表现属性**（如 `stroke="var(--text-tertiary)"`）。
       * 这类属性脱离文档后没有 CSS 环境，`var()` 必然失效；内联样式已给出解析后的实际值，
       * 留着它只是留一个坏掉的备份。
       *
       * **不能无差别全摘**：`getComputedStyle` 在少数环境（如 jsdom）不解析 SVG 表现属性，
       * 会把 `fill="rgb(255,0,0)"` 算成黑色——此时属性才是唯一正确的数据源，
       * 摘掉就等于把颜色丢了（实测踩过）。所以"解不出来的才摘，能用的保留"。
       */
      for (const prop of SVG_STYLE_PROPS) {
        const raw = to.getAttribute(prop);
        if (raw && raw.includes("var(") && to.style.getPropertyValue(prop)) to.removeAttribute(prop);
      }
    }
    // 尺寸显式化（导出后没有 CSS 布局）
    const rect = el.getBoundingClientRect();
    const vb = el.getAttribute("viewBox");
    if (!clone.getAttribute("width") && rect.width) clone.setAttribute("width", String(Math.round(rect.width)));
    if (!clone.getAttribute("height") && rect.height) clone.setAttribute("height", String(Math.round(rect.height)));
    if (!vb && rect.width && rect.height) clone.setAttribute("viewBox", `0 0 ${Math.round(rect.width)} ${Math.round(rect.height)}`);
    clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    clone.removeAttribute("style"); // 去掉屏幕定位样式（position/inset 等对导出无意义）
    const inner = new XMLSerializer().serializeToString(clone);
    // 可选底色：剖面图本身透明，铺白底更像论文图（也便于叠在深色底上）
    if (opts.background) {
      const w = clone.getAttribute("width") ?? "100%";
      const h = clone.getAttribute("height") ?? "100%";
      const bgRect = `<rect x="0" y="0" width="${w}" height="${h}" fill="${opts.background}"/>`;
      return inner.replace(/(<svg\b[^>]*>)/, `$1${bgRect}`);
    }
    return inner;
  } catch (e) {
    console.warn("[captureFrame] SVG 快照失败", e);
    return null;
  }
}
