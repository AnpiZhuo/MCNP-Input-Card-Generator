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

/** three.js 场景底色开关（结构化类型，避免本模块 import three） */
export interface SceneBackgroundLike {
  background: unknown;
}

/** 渲染器上我们要用的两件事（结构化类型，避免本模块 import three） */
export interface ClearColorRenderer {
  setClearColor(color: number, alpha?: number): void;
  getClearColor?(target: { r: number; g: number; b: number }): { r: number; g: number; b: number };
  getClearAlpha?(): number;
}

/**
 * 出一张**透明底**的 3D 帧。
 *
 * ## 为什么必须走这个函数，不能只把 `opts.background` 传 null
 * `opts.background: null` 只做到"**不铺**底色"，可 3D 视图的场景本身带着
 * `scene.background = new THREE.Color(0x0d0d22)` —— 那层深蓝会被原样取进图里。
 * 想拿到真透明，必须在这一帧里三件事同时成立：
 *   1. `scene.background = null`（不画背景色）
 *   2. 渲染器按 `alpha = 0` 清屏（未清屏的像素在 `preserveDrawingBuffer:false` 下是垃圾值）
 *   3. 取完像素立刻把前两者还原（用户屏幕上的观感不能被出图改掉）
 *
 * 副作用被限制在**一次同步 render 的窗口内**，还原写在 `finally` 里，抛错也不漏。
 *
 * @param renderer 渲染器（three 的 `WebGLRenderer` 满足本接口）
 * @param scene 场景（只要带 `background` 字段）
 * @param renderNow 同步重画函数（一般是 `() => renderer.render(scene, camera)`）
 */
export function captureTransparent3D(
  canvas: HTMLCanvasElement | null | undefined,
  renderer: ClearColorRenderer,
  scene: SceneBackgroundLike,
  renderNow: () => void,
  opts: { scale?: number; clearColor?: [number, number, number, number] } = {},
): HTMLCanvasElement | null {
  const prevSceneBg = scene.background;
  // 保存渲染器原清屏色（尽力而为：拿不到就只还原场景背景，绝不因为取不到而失败）
  let prevHex: number | null = null;
  let prevAlpha: number | null = null;
  try {
    if (typeof renderer.getClearAlpha === "function") prevAlpha = renderer.getClearAlpha();
    if (typeof renderer.getClearColor === "function") {
      const c = renderer.getClearColor({ r: 0, g: 0, b: 0 });
      prevHex = channelToHex(c.r, c.g, c.b);
    }
  } catch { /* 忽略：无法读取原色不是致命问题 */ }

  try {
    scene.background = null;
    const [r, g, b, a] = opts.clearColor ?? [0, 0, 0, 0];
    renderer.setClearColor(channelToHex(r * 255, g * 255, b * 255), a);
    return captureCanvas(canvas, { scale: opts.scale ?? 1, background: null, renderNow });
  } finally {
    scene.background = prevSceneBg;
    try {
      if (prevHex !== null) renderer.setClearColor(prevHex, prevAlpha ?? 1);
      else if (prevAlpha !== null) renderer.setClearColor(0x000000, prevAlpha);
    } catch { /* 还原失败不影响已取到的像素 */ }
  }
}

/** 0–255 分量 → 0xRRGGBB（three 的 `setClearColor` 要的是这个整数） */
function channelToHex(r: number, g: number, b: number): number {
  const q = (v: number) => Math.max(0, Math.min(255, Math.round(v)));
  return (q(r) << 16) | (q(g) << 8) | q(b);
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

/* ───────────────────────── PNG 物理尺寸元数据 ───────────────────────── */

/**
 * 给 PNG 补 `pHYs` 块（物理像素尺寸），单位：像素/米。
 *
 * ## 为什么必须做这一步
 * **PNG 没有分辨率概念**——它只有像素。一张 1890 px 宽的图是"600 dpi 的 80 mm"还是
 * "300 dpi 的 160 mm"，完全取决于排版软件怎么缩放它。期刊要求"线条图 ≥600 dpi"，
 * 如果图里不写物理尺寸，这条要求**在文件层面无从判定**，作者与编辑只能靠猜。
 * 写上 `pHYs` 之后，Word/LaTeX 插进来时能显示"这张图 1890 px @ 600 dpi = 80 mm 宽"。
 *
 * ## 实现要点
 * - PNG 结构是 `签名(8B)` + 若干块；`pHYs` 必须**紧跟 `IHDR`**（规范建议，兼容性最好）；
 * - 每块 = `长度(4, BE)` + `类型(4)` + `数据` + `CRC32(4)`，CRC 覆盖"类型+数据"；
 * - 已有的 `pHYs` 先删掉再插（避免出现两个）；
 * - 任何一步不成立（不是 PNG / 结构异常）就**原样返回**，绝不因为"想写元数据"把图弄坏。
 *
 * @param dpi 目标分辨率（px/inch）
 */
export function withPngDpi(bytes: Uint8Array, dpi: number): Uint8Array {
  try {
    if (!Number.isFinite(dpi) || dpi <= 0) return bytes;
    if (bytes.length < 33) return bytes;
    // PNG 签名
    const SIG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
    for (let i = 0; i < 8; i++) if (bytes[i] !== SIG[i]) return bytes;
    if (String.fromCharCode(bytes[12], bytes[13], bytes[14], bytes[15]) !== "IHDR") return bytes;

    const ppx = Math.round(dpi / 0.0254); // px / m
    const phys = new Uint8Array(9);
    const dv = new DataView(phys.buffer);
    dv.setUint32(0, ppx, false);
    dv.setUint32(4, ppx, false);
    phys[8] = 1; // 单位 = 米

    const chunks: Uint8Array[] = [bytes.subarray(0, 8), bytes.subarray(8, 33)]; // 签名 + IHDR
    chunks.push(makeChunk("pHYs", phys));
    // 其余块原样搬（跳过可能已存在的 pHYs）
    let off = 33;
    while (off + 8 <= bytes.length) {
      const len = new DataView(bytes.buffer, bytes.byteOffset + off, 4).getUint32(0, false);
      const end = off + 12 + len;
      if (end > bytes.length) break;
      const type = String.fromCharCode(bytes[off + 4], bytes[off + 5], bytes[off + 6], bytes[off + 7]);
      if (type !== "pHYs") chunks.push(bytes.subarray(off, end));
      off = end;
    }
    const total = chunks.reduce((s, c) => s + c.length, 0);
    const out = new Uint8Array(total);
    let p = 0;
    for (const c of chunks) { out.set(c, p); p += c.length; }
    // 结构自检：结尾必须是 IEND，否则不冒险替换
    if (String.fromCharCode(out[out.length - 8], out[out.length - 7], out[out.length - 6], out[out.length - 5]) !== "IEND") {
      return bytes;
    }
    return out;
  } catch {
    return bytes;
  }
}

/** 组装一个 PNG 块（含 CRC32） */
function makeChunk(type: string, data: Uint8Array): Uint8Array {
  const body = new Uint8Array(4 + data.length);
  for (let i = 0; i < 4; i++) body[i] = type.charCodeAt(i);
  body.set(data, 4);
  const out = new Uint8Array(12 + data.length);
  const dv = new DataView(out.buffer);
  dv.setUint32(0, data.length, false);
  out.set(body, 4);
  dv.setUint32(8 + data.length, crc32(body), false);
  return out;
}

let crcTable: Uint32Array | null = null;
function crc32(buf: Uint8Array): number {
  if (!crcTable) {
    crcTable = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      crcTable[n] = c >>> 0;
    }
  }
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = crcTable[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
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
export function snapshotSvg(el: SVGSVGElement | null | undefined, opts: { stripSelector?: string; background?: string | null; strokeScale?: number } = {}): string | null {
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

    /**
     * ── `vector-effect="non-scaling-stroke"` 的导出换算（2026-09-19）──
     *
     * 屏幕上用该属性把描边锚在**屏幕像素**上是对的（缩放时线宽不漂移，见 `CrossSectionView`
     * 的描边注释）。但**它出了文档就没意义**：等值线/截面多边形被合成进版面时会再缩放一次，
     * 而 `non-scaling-stroke` 在部分渲染路径（含 svg→canvas 的光栅化）根本不生效
     * ⇒ 描边被当成**用户单位**直接乘以缩放比，导出图里边界比屏幕上重得多（用户实测到过）。
     *
     * 所以导出时**摘掉该属性，并把线宽换算成用户坐标**：`新宽度 = 原宽度 / strokeScale`，
     * 其中 `strokeScale` = 面板在版面里的显示尺寸 / 屏幕像素尺寸。换算后，
     * 无论面板被缩放到多大，边界线**始终是 1.2px 的细线**。
     *
     * 不传 `strokeScale`（默认）＝保持原样：本函数对"没有该属性"的 SVG 完全无影响。
     */
    if (opts.strokeScale && opts.strokeScale > 0) {
      const targets: Element[] = [clone, ...Array.from(clone.querySelectorAll("*"))];
      for (const t of targets) {
        const effect = t.getAttribute("vector-effect");
        if (!effect || !/non-scaling-stroke/i.test(effect)) continue;
        t.removeAttribute("vector-effect");
        const w = parseFloat(t.getAttribute("stroke-width") ?? "");
        if (Number.isFinite(w) && w > 0) {
          t.setAttribute("stroke-width", String(Math.round((w / opts.strokeScale) * 1000) / 1000));
        }
      }
    }

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
