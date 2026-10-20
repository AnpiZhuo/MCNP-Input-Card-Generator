/**
 * dragImport — 「拖入文件即导入」覆盖层的判定（纯函数，App.tsx 唯一实现）。
 *
 * 症状（2026-09-26 用户实测）：在 3D 预览 / 二维截面里按住左键拖动时，**有时**会亮起
 * 全屏粉色「释放以导入 INP 文件」并**卡死** —— 覆盖层 `position:fixed; inset:0; zIndex:9999`
 * 把整个界面盖住，鼠标落在哪儿都打在它身上（浏览器实测：`document.elementFromPoint(400,300)`
 * 命中的就是这个覆盖层），而它**再也没有消失**。
 *
 * 根因（浏览器实测，不是推断）：
 *   · `dragenter` 是**任何** HTML5 拖拽都会触发的 —— 拖拽起点落在**已选中的文字/可拖元素**上时，
 *     浏览器会起一次原生拖拽，其 `dataTransfer.types` 只有 `text/plain`、**没有 `Files`**；
 *   · 旧 `handleDragEnter` 对**任何** dragenter 都 `setDragOver(true)`（不判是不是拖文件）；
 *   · 旧 `handleDragLeave`/`handleDragEnd` 只 `preventDefault()`，**从不清除** ——
 *     于是"没落到 drop"的拖拽（松手在窗口外、Esc 取消、纯内部拖拽）留下的粉色覆盖层永远不熄。
 *
 * 两条判据（缺一不可）：
 *   ① **只有真拖文件**（`types` 含 `"Files"`）才亮覆盖层 —— 内部拖拽一律不亮；
 *   ② `leave`/`drop`/`end` **一律熄灭** —— 任何"没落下"的拖拽都能自愈。
 */

export type DragPhase = "enter" | "over" | "leave" | "drop" | "end";

/** 这次拖拽是不是"从外面拖文件进来"？（内部拖拽：选中文字/图片/SVG 也是 drag，但不是文件） */
export function isFileDrag(types?: ArrayLike<string> | readonly string[] | null): boolean {
  if (!types) return false;
  try {
    return Array.from(types as ArrayLike<string>).includes("Files");
  } catch {
    return false;
  }
}

/**
 * 覆盖层在某个拖拽阶段之后应处于什么状态。
 *
 * `enter`/`over`：真拖文件才亮（非文件拖拽**同时清掉**可能残留的旧状态）；
 * `leave`/`drop`/`end`：一律熄灭 —— 覆盖层不保留任何"等一个 drop"的记忆。
 */
export function overlayAfterDrag(phase: DragPhase, types?: ArrayLike<string> | readonly string[] | null): boolean {
  if (phase === "enter" || phase === "over") return isFileDrag(types);
  return false;
}

/** 覆盖层文案（App 与测试共用一处，避免测试去硬编码字符串） */
export const DROP_OVERLAY_TEXT = "释放以导入 INP 文件";

/**
 * Tauri（打包后）的 `tauri://file-drop-hover` 事件：**要不要亮主窗口覆盖层**。
 *
 * 2026-10-21 用户实测（第二个坑，与上面的 HTML5 drag 坑不同源）：
 *   在 **3D 预览子窗口** 里框选文字后拖拽 ⇒ **主窗口**亮起粉色覆盖层且永不消失。
 *   根因：`App.tsx` 用 `@tauri-apps/api/event` 的 **全局** `listen()` 订阅
 *   `tauri://file-drop-hover`；Tauri v1 的全局监听会收到**所有窗口**的事件
 *   （事件对象带 `windowLabel` 正是为此），于是子窗口里"拖文字"触发的 hover
 *   被主窗口当成"拖文件进来"；而文字拖拽没有对应的 drop/cancelled 事件 ⇒ 卡住。
 *
 * 两条判据（与 `overlayAfterDrag` 同一个"假拖拽不许亮"的原则）：
 *   ① **只认本窗口**（`windowLabel` 缺省或等于 mainLabel）——子窗口的事件一律忽略；
 *   ② **payload 必须是非空的文件路径数组** —— 文字/图片拖拽没有文件路径 ⇒ 不亮。
 */
export function shouldShowDropOverlay(
  payload: unknown,
  windowLabel?: string | null,
  mainLabel = "main",
): boolean {
  if (windowLabel && windowLabel !== mainLabel) return false;
  if (!Array.isArray(payload) || payload.length === 0) return false;
  return payload.some((p) => typeof p === "string" && p.length > 0);
}
