/**
 * saveFile — 把一份产物交到用户手上（**一个口子**，三种环境自动降级）。
 *
 * 优先级（与仓库既有范式一致，见 `GeometryTab` 的 STEP 导出）：
 *   ① 系统「另存为」对话框（`showSaveFilePicker`，本程序跑在 WebView2/Chromium 内核，
 *      实测可用）——用户自己选位置，最符合"导出文件"的直觉；
 *   ② 用户取消对话框 → 明确返回 `cancelled`，**不当成失败**（不能弹错误）；
 *   ③ 无该能力（浏览器模式/老内核）→ 退化成 `<a download>` 放到浏览器默认下载目录；
 *   ④ Tauri 环境且前两者都不可用 → 退到 Tauri fs 写盘（写进给定目录）。
 *
 * ## 接口为什么长这样
 * 只吃 `{ data, fileName, mime, dir? }`：调用方（出图链路）不该知道文件对话框、
 * Blob、Tauri fs 的存在；它只回答"叫什么名字、装什么字节"。
 * 返回 `SaveOutcome` 而不是抛异常，是因为"用户点了取消"是正常路径不是错误，
 * 调用方需要把两者分开处理（取消→静默，失败→提示）。
 */

export interface SaveRequest {
  /** 文本（SVG/CSV）或二进制（PNG/PDF） */
  data: string | Uint8Array | Blob;
  /** 带扩展名的文件名，如 `3D预览_xyz.png` */
  fileName: string;
  /** MIME，用于对话框过滤与 `<a download>` */
  mime: string;
  /** ③④ 降级时的目标目录（Tauri fs / 无对话框环境）；缺省走浏览器下载目录 */
  dir?: string;
}

export type SaveOutcome =
  | { status: "saved"; path: string }
  /** 用户在「另存为」里点了取消 */
  | { status: "cancelled" }
  | { status: "error"; message: string };

/** 扩展名 → 对话框用的文件类型描述 */
function pickerTypes(fileName: string, mime: string): { description: string; accept: Record<string, string[]> }[] {
  const ext = "." + (fileName.split(".").pop() || "");
  const label: Record<string, string> = {
    ".png": "PNG 图片", ".svg": "SVG 矢量图", ".pdf": "PDF 文档",
    ".csv": "CSV 数据", ".zip": "压缩包",
  };
  return [{ description: label[ext] || "文件", accept: { [mime]: [ext] } }];
}

function toBlob(data: SaveRequest["data"], mime: string): Blob {
  if (typeof Blob !== "undefined" && data instanceof Blob) return data;
  if (typeof data === "string") return new Blob([data], { type: mime });
  // Uint8Array：拷进新缓冲，避免 Blob 持有外部可变视图
  const u8 = data as Uint8Array;
  return new Blob([u8.slice().buffer as ArrayBuffer], { type: mime });
}

/**
 * 存一份产物。**Textual/二进制都走这里**；不抛异常，失败以 `SaveOutcome` 返回。
 */
export async function saveFile(req: SaveRequest): Promise<SaveOutcome> {
  const { fileName, mime, dir } = req;
  let blob: Blob;
  try {
    blob = toBlob(req.data, mime);
  } catch (e: any) {
    return { status: "error", message: String(e?.message || e) };
  }

  // ① 系统「另存为」对话框
  const picker = (globalThis as any)?.showSaveFilePicker;
  if (typeof picker === "function") {
    try {
      const handle = await picker({ suggestedName: fileName, types: pickerTypes(fileName, mime) });
      const w = await handle.createWritable();
      await w.write(blob);
      await w.close();
      return { status: "saved", path: handle?.name || fileName };
    } catch (e: any) {
      // 用户取消：AbortError（不是失败）
      if (e?.name === "AbortError") return { status: "cancelled" };
      // 其它错误（权限/内核不支持）→ 继续降级，不在这里报死
    }
  }

  // ④ Tauri fs（有目录时）
  if (dir) {
    const r = await saveViaTauriFs(blob, dir, fileName);
    if (r) return r;
  }

  // ③ <a download>
  try {
    if (typeof document === "undefined") return { status: "error", message: "当前环境无法保存文件" };
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fileName;
    a.click();
    // 立刻 revoke 会让部分内核来不及开始下载；下一帧回收
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
    return { status: "saved", path: fileName };
  } catch (e: any) {
    return { status: "error", message: String(e?.message || e) };
  }
}

/** ④ Tauri fs 兜底：写 `dir/fileName`；不可用（浏览器模式）返回 null 让调用方继续降级 */
async function saveViaTauriFs(blob: Blob, dir: string, fileName: string): Promise<SaveOutcome | null> {
  try {
    const fs = await import("@tauri-apps/api/fs");
    const sep = dir.includes("\\") ? "\\" : "/";
    const path = dir.replace(/[\\/]+$/, "") + sep + fileName;
    const bytes = new Uint8Array(await blob.arrayBuffer());
    await (fs as any).writeBinaryFile(path, bytes);
    return { status: "saved", path };
  } catch {
    return null;
  }
}

/** 出图文件名：`<视图>_<参数…>_<时间戳>.<ext>`（参数清洗成文件名安全字符） */
export function figureFileName(view: string, parts: (string | number | undefined | null)[], ext: string): string {
  const safe = (s: string) => s.replace(/[\\/:*?"<>|\s]+/g, "_").replace(/_+/g, "_").replace(/^_|_$/g, "");
  const tail = parts.filter((p) => p !== undefined && p !== null && String(p) !== "").map((p) => safe(String(p)));
  const stamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, "").replace(/(\d{8})(\d{6})/, "$1_$2");
  return [safe(view), ...tail, stamp].filter(Boolean).join("_") + "." + ext.replace(/^\./, "");
}
