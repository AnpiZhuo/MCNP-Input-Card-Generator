/**
 * cjkFont — 给矢量 PDF 找一份能显示中文的字体（**找不到就明确说找不到**）。
 *
 * ## 为什么必须有这一层
 * PDF 的标准字体不含中文，而本程序每张图都带中文（"计数""能量""材料"）。
 * svg2pdf 只能内嵌**已注册**的字体 ⇒ 没有中文字体时，导出的 PDF 里所有中文都是空白。
 * 这是最恶劣的一类失败：文件打得开、看着"就差几个字"，用户以为是图没导全。
 * 所以本模块的接口把结果分成三态：拿到字体 / 这台机器没有 / 读取失败——
 * 由调用方决定降级（见 `exportFigure`：拿不到就改走**300dpi 白底位图 PDF**，内容一个字不丢）。
 *
 * ## 为什么读系统字体而不是随包带一份
 * 随包带一份 CJK 字体要 +15 MB 安装体积，而这个程序本来就只跑 Windows、
 * 系统必然自带中文字体。所以按候选表从 `C:/Windows/Fonts` 读**纯 TTF**
 * （刻意避开 `.ttc` 字体集合：jsPDF 的 TTF 解析对集合文件不可靠，
 * 而 Deng/simhei 这种单字体 TTF 正是为这种情况存在的）。
 *
 * ## 为什么读字节不依赖 Tauri fs
 * 目标平台只有 WebView2（Chromium 内核），`showSaveFilePicker`/`fetch` 之外还有
 * Tauri fs 可用；两条路都试，读到的字节同一份，调用方不用关心来源。
 */

export interface CjkFontCandidate {
  file: string;
  name: string;
}

/**
 * 候选字体（按优先序）。全部是**纯 TTF**：
 * - `Deng.ttf`（等线，Win10+ 自带，无衬线，与图注风格一致，首选）
 * - `simhei.ttf`（黑体，Win7 起自带，兜底最稳）
 * - `simkai.ttf` / `simfang.ttf`（楷体/仿宋，再兜一层）
 */
export const CJK_FONT_CANDIDATES: CjkFontCandidate[] = [
  { file: "Deng.ttf", name: "DengXian" },
  { file: "simhei.ttf", name: "SimHei" },
  { file: "simkai.ttf", name: "KaiTi" },
  { file: "simfang.ttf", name: "FangSong" },
];

export type FontLoadResult =
  | { ok: true; name: string; data: Uint8Array; path: string }
  | { ok: false; reason: "notFound" | "error"; message?: string };

/** 进程内缓存：一次导出多张图只读一次盘 */
let cached: FontLoadResult | null = null;
/** 测试注入点（读取器可替换，便于验证三态分支而不碰真磁盘） */
let reader: (path: string) => Promise<Uint8Array> = defaultReader;

/** 测试用：替换/还原字体读取器 */
export function setFontReader(fn: ((path: string) => Promise<Uint8Array>) | null): void {
  reader = fn ?? defaultReader;
  cached = null;
}

function fontPath(file: string): string {
  return `C:/Windows/Fonts/${file}`;
}

async function defaultReader(path: string): Promise<Uint8Array> {
  // ① Tauri fs（打包版最稳）
  try {
    const fs: any = await import("@tauri-apps/api/fs");
    if (fs?.readBinaryFile) return await fs.readBinaryFile(path);
  } catch { /* 浏览器模式 → 走 ② */ }
  // ② fetch（WebView2 下 file:// 通常被拦，但同源 http 场景可用）
  const r = await fetch(path);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return new Uint8Array(await r.arrayBuffer());
}

/**
 * 取一份中文字体字节。结果缓存；`notFound` 与 `error` 分开返回，
 * 便于调用方在日志/提示里说清是"这台机器没装"还是"读了但失败"。
 */
export async function loadCjkFont(force = false): Promise<FontLoadResult> {
  if (cached && !force) return cached;
  let lastError: string | undefined;
  for (const c of CJK_FONT_CANDIDATES) {
    const path = fontPath(c.file);
    try {
      const data = await reader(path);
      if (data && data.byteLength > 10_000) {
        const ok = looksLikeTtf(data);
        if (!ok) { lastError = `${c.file} 不是有效的 TTF`; continue; }
        cached = { ok: true, name: c.name, data, path };
        return cached;
      }
      lastError = `${c.file} 读到的内容过小`;
    } catch (e: any) {
      lastError = `${c.file}: ${e?.message || e}`;
    }
  }
  cached = lastError ? { ok: false, reason: "error", message: lastError } : { ok: false, reason: "notFound" };
  return cached;
}

/** TTF 魔数校验（0x00010000 / "true" / "OTTO"）；TTC 的 "ttcf" 明确判为不可用 */
export function looksLikeTtf(data: Uint8Array): boolean {
  if (data.byteLength < 12) return false;
  const tag = String.fromCharCode(data[0], data[1], data[2], data[3]);
  if (tag === "ttcf") return false;              // 字体集合：jsPDF 解析不可靠
  if (tag === "true" || tag === "OTTO") return true;
  return data[0] === 0 && data[1] === 1 && data[2] === 0 && data[3] === 0;
}
