/**
 * exportFigure — 出图的**唯一门面**：调用方只说"我这张图由哪些块组成"，其余全在这里决定。
 *
 * ## 用户怎么用（这就是全部交互）
 * 点窗口标题栏那个「导出」按钮。不弹格式框、不弹参数框、不问落盘位置（走系统「另存为」）。
 *
 * ## 我们替他决定的事（2026-09-19 用户裁决后**只有一种产物**）
 * | 情况 | 产物 | 依据 |
 * | :--- | :--- | :--- |
 * | 任何视图（3D / 截面 / 曲线 / 切面 / keff） | **PNG（2×、白底）** | 用户原话（2026-09-19）："png 都改为白底" |
 *
 * ## 为什么不再出 PDF/SVG（这是有代价的选择，写在这里免得后人再问）
 * 2D 图原先出矢量 PDF+SVG（放大不糊、可编辑），改成 PNG 后**丢掉矢量性**：
 * 放大到海报尺寸会糊，也不能再进 Illustrator 改线。换来的是一致性 ——
 * 用户拿到的永远是同一类文件、"另存为"只问一次、不用再纠结选哪个格式。
 * 若将来要恢复矢量出口，缺的不是渲染能力，而是**格式决策的口径**（问用户 / 加开关），
 * 代码路径本身（`buildVectorFigure` → `figureToPdf`）还原样保留着。
 */
import { capturePngBytes, svgToRaster, withPngDpi } from "./captureFrame";
import { preparePanels, renderFigure, type FigureSpec } from "./figureCanvas";
import { figureFileName, saveFile, type SaveOutcome } from "./saveFile";
import { buildVectorFigure, type VectorFigureSpec } from "./vectorFigure";

/** 位图出口的放大倍数（基准；实际倍率由目标 dpi 与成品宽度算出，见 `rasterScaleFor`） */
export const RASTER_SCALE = 2;

/**
 * 出图目标分辨率与成品宽度（**中文期刊口径**，2026-09-19 按国标/期刊要求重定）。
 *
 * | 图类型 | 分辨率要求 | 本程序取值 |
 * | :--- | :--- | :--- |
 * | 线条图 / 散点图 / 示意图（line art） | 通常 **≥600 dpi** | `PRINT_LINE_DPI = 600` |
 * | 照片 / 半色调 / 热图 | 通常 **≥300 dpi** | `PRINT_HALFTONE_DPI = 300` |
 *
 * 为什么必须把"成品宽度"一起定下来：**PNG 本身没有物理尺寸**，
 * 不说清"这张图印 80 mm 还是 170 mm"，"够不够 600 dpi"就是空话。
 * 这里取中文期刊常见**单栏 80 mm** 为基准，并把该物理尺寸写进 PNG 的 `pHYs` 块 ——
 * 排版软件读到的就是"按 80 mm 宽、600 dpi 使用"。
 */
export const PRINT_LINE_DPI = 600;
export const PRINT_HALFTONE_DPI = 300;
/** 成品宽度（mm）：中文期刊单栏约 80 mm；通栏/双栏约 170 mm */
export const PRINT_WIDTH_MM_SINGLE = 80;
export const PRINT_WIDTH_MM_FULL = 170;
const MM_PER_INCH = 25.4;

/**
 * 按"目标 dpi × 成品宽度"反算栅格倍率。
 *
 * 逻辑画布宽 `logicalW` px 要印成 `targetWmm` 毫米 ⇒ 需要 `targetDpi × targetWmm / 25.4` 像素，
 * 倍率 = 该像素数 / logicalW。**上限 6×**（逻辑画布很小时避免算出几十倍把内存炸掉）。
 */
export function rasterScaleFor(logicalW: number, targetWmm = PRINT_WIDTH_MM_SINGLE, targetDpi = PRINT_LINE_DPI): number {
  if (!logicalW || logicalW <= 0) return RASTER_SCALE;
  const targetPx = (targetDpi * targetWmm) / MM_PER_INCH;
  const k = targetPx / logicalW;
  return Math.max(1, Math.min(6, Math.round(k * 100) / 100));
}

export interface ExportFigureRequest {
  /** 视图名（进文件名与图标题），如 "3D几何" / "截面" / "Tally通量" */
  view: string;
  /** 文件名里的参数段（tally 号、能量区间、分辨率、层号……） */
  nameParts?: (string | number | undefined | null)[];
  /** 栅格出口的规格（3D 视图 / 含热图的合成图） */
  raster?: Omit<FigureSpec, "theme">;
  /** 二维图的规格（先组合成矢量，再栅格成 PNG —— 保住文字锐度） */
  vector?: Omit<VectorFigureSpec, "theme">;
  /** 保存位置（Tauri fs 降级时用）；不给则走系统对话框/浏览器下载 */
  dir?: string;
  /**
   * 成品宽度（mm）。缺省 `PRINT_WIDTH_MM_SINGLE`（80 mm，中文期刊单栏）；
   * 通栏/双栏传 `PRINT_WIDTH_MM_FULL`（170 mm）。
   * 只影响**栅格倍率与写进 PNG 的物理尺寸**，不改变版面。
   */
  printWidthMm?: number;
  /**
   * 目标分辨率；缺省按图类型自动取（含热图/位图 → 300 dpi，纯二维线图 → 600 dpi）。
   */
  targetDpi?: number;
}

export interface ExportedFile {
  /** 一律 "png" */
  format: string;
  path: string;
  bytes: number;
  /** true = 走了降级路径（如中文字形缺失改浏览器默认字体），便于界面提示与问题排查 */
  degraded?: boolean;
  degradeReason?: string;
}

export type ExportResult =
  | { status: "exported"; files: ExportedFile[] }
  | { status: "cancelled" }
  | { status: "error"; message: string };

/**
 * 出图底色：**白底**（2026-09-19 用户裁决，取代当天的"缺省透明底"）。
 *
 * ## 为什么改成白底
 * 用户先要"该用透明底的用透明底"，实机看过之后改口"png 都改为白底"。白底的现实好处：
 * 贴进 Word/LaTeX 不会因为页面底色不同而出现"文字看不清"（论文主题的轴与文字是深色，
 * 叠在深色幻灯片上时确实会糊）；也省掉"这张要不要透明"的判断负担。
 *
 * ## 那"透明取帧"还留着吗——留着，但不是给最终产物用的
 * 3D 的 `renderTransparentNow()`（`captureFrame.captureTransparent3D`）仍在用：
 * 取到**透明底**的一帧，才能把它干净地合成到这张白底版面上（否则会把 WebGL 的深色场景底
 * 一起贴上来）。**产物是白底，中间帧是透明**——两件事，别混。
 */
const FIGURE_BACKGROUND = "#ffffff";

/**
 * 出一张图。**只有 PNG 一种产物，一律白底**。
 *
 * 两条通路的差别只在于"先组合什么"：
 * - `vector` 给了 → 先做矢量合成（版面用真 `<text>`/`<path>`），再按目标 dpi 栅格化；
 * - 否则用 `raster`（3D 视图这类本来就是位图的）。
 *
 * **倍率不再写死 2×**：由「目标 dpi × 成品宽度」反算（`rasterScaleFor`），
 * 并按同一物理尺寸给 PNG 补 `pHYs` 元数据。纯二维线图按 600 dpi，含位图/热图按 300 dpi。
 */
export async function exportFigure(req: ExportFigureRequest): Promise<ExportResult> {
  const files: ExportedFile[] = [];
  const widthMm = req.printWidthMm ?? PRINT_WIDTH_MM_SINGLE;

  // ── 矢量通路：合成矢量（白底铺在最底层）→ 按目标 dpi 栅格 → PNG ──
  if (req.vector) {
    const built = buildVectorFigure({ theme: "paper", background: FIGURE_BACKGROUND, ...req.vector });
    // 纯二维线图：按线图分辨率（600 dpi）
    const dpi = req.targetDpi ?? PRINT_LINE_DPI;
    const scale = rasterScaleFor(built.width, widthMm, dpi);
    const canvas = await svgToRaster(built.svg, { scale, background: FIGURE_BACKGROUND });
    if (!canvas) return { status: "error", message: "图像生成失败（矢量栅格化失败）" };
    // 产物不透明：这里再按白底编码一次，保证 alpha 通道也干净（不依赖上游每一步都不漏底）
    const bytes = await capturePngBytes(canvas, { scale: 1, background: FIGURE_BACKGROUND });
    if (!bytes) return { status: "error", message: "图像生成失败（编码失败）" };
    return await savePng(bytes, req, widthMm, canvas.width, canvas.height);
  }

  // ── 栅格通路（3D 视图、含热图的合成图） ──
  if (req.raster) {
    // 含位图/热图 ⇒ 半色调分辨率（300 dpi）。版面尺寸要先算出来才能定倍率，
    // 所以这里先用基准倍率摆一次版面拿到逻辑宽，再按它算真实倍率重做一次。
    const probe = renderFigure({ theme: "paper", ...req.raster }, { background: FIGURE_BACKGROUND });
    const dpi = req.targetDpi ?? PRINT_HALFTONE_DPI;
    const scale = rasterScaleFor(probe.width, widthMm, dpi);
    const prepared = await preparePanels({ theme: "paper", ...req.raster }, scale);
    // 白底铺在合成图最底层；3D 面板本身是透明取帧，叠上来正好
    const { canvas } = renderFigure(prepared, { background: FIGURE_BACKGROUND });
    const bytes = await capturePngBytes(canvas, { scale: 1, background: FIGURE_BACKGROUND });
    if (!bytes) return { status: "error", message: "图像生成失败（画布为空）" };
    return await savePng(bytes, req, widthMm, canvas.width, canvas.height);
  }

  return { status: "error", message: "没有可导出的内容" };
}

/** PNG 落盘（名称、提示、取消语义都收在这里，两条通路共用；顺带写物理尺寸元数据） */
async function savePng(
  bytes: Uint8Array,
  req: ExportFigureRequest,
  widthMm: number,
  pxW: number,
  pxH: number,
): Promise<ExportResult> {
  // 把"这张图按 widthMm 宽使用"写进 PNG 的 pHYs（否则物理尺寸不明，dpi 无从谈起）
  const withDpi = withPngDpi(bytes, pxW / (widthMm / MM_PER_INCH));
  const name = figureFileName(req.view, req.nameParts ?? [], "png");
  const out = await saveFile({ data: withDpi, fileName: name, mime: "image/png", dir: req.dir });
  if (out.status === "cancelled") return { status: "cancelled" };
  if (out.status === "error") return { status: "error", message: out.message };
  return { status: "exported", files: [{ format: "png", path: out.path, bytes: withDpi.byteLength }] };
}

/** 把 `ExportResult` 变成一句给用户看的话（各窗口共用，避免提示文案分叉） */
export function exportMessage(r: ExportResult, viewLabel = "图"): string {
  if (r.status === "cancelled") return ""; // 用户主动取消：不打扰
  if (r.status === "error") return `❌ ${viewLabel}导出失败：${r.message}`;
  const lines = r.files.map((f) => {
    const size = f.bytes > 1024 * 1024 ? `${(f.bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(f.bytes / 1024))} KB`;
    const note = f.degraded ? `（${f.degradeReason}）` : "";
    return `  · ${f.format.toUpperCase()}  ${size}${note}`;
  });
  return `✅ 已导出${viewLabel}：\n${lines.join("\n")}\n\n位置：${r.files[0]?.path ?? ""}`;
}

/** 便捷：导出并提示（各窗口一行接线用；测试里不调它，避免绑死 UI） */
export async function exportFigureWithToast(req: ExportFigureRequest, viewLabel?: string): Promise<ExportResult> {
  const r = await exportFigure(req);
  const msg = exportMessage(r, viewLabel ?? req.view);
  if (msg) {
    // 用 alert 而不是 toast：导出是"用户主动等结果"的动作，需要明确回执
    try { alert(msg); } catch { /* 非浏览器环境 */ }
  }
  return r;
}

export type { SaveOutcome };

