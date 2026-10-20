import { describe, it, expect } from "vitest";
import { DROP_OVERLAY_TEXT, isFileDrag, overlayAfterDrag, shouldShowDropOverlay } from "../src/utils/dragImport";

/*
 * dragImport —— 「拖入文件即导入」覆盖层的判定。
 *
 * 用户报告（2026-09-26）：「3D 预览中，截面拖动时，有时候会不知道框选到什么东西，
 * 导致前端误以为是在导入东西，而卡死在导入时的粉色页面」。
 *
 * 浏览器实测（修复前，真 Chrome + 已构建 bundle）：
 *   ① 内部拖拽（dataTransfer.types = ["text/plain"]，没有 Files）→ 粉色覆盖层亮起；
 *   ② 接着 dispatch dragend + dragleave → **覆盖层仍在**（body.innerText 仍含
 *      "释放以导入 INP 文件"），且 elementFromPoint(400,300) 命中的就是覆盖层
 *      ⇒ 整个界面点不动 = 用户说的"卡死"。
 * 根因：dragenter 不判是不是拖文件，dragleave/dragend 从不清除（只有 drop 会清）。
 */

describe("isFileDrag（这次拖拽是不是拖文件进来）", () => {
  it("外部拖文件：types 含 Files", () => {
    expect(isFileDrag(["Files"])).toBe(true);
    expect(isFileDrag(["text/plain", "Files"])).toBe(true);
  });

  it("内部拖拽（选中文字/图片/SVG）：没有 Files ⇒ 不是文件拖入", () => {
    expect(isFileDrag(["text/plain"])).toBe(false);
    expect(isFileDrag(["text/uri-list", "text/html"])).toBe(false);
    expect(isFileDrag([])).toBe(false);
    expect(isFileDrag(null)).toBe(false);
    expect(isFileDrag(undefined)).toBe(false);
  });
});

describe("overlayAfterDrag（覆盖层状态机）", () => {
  it("拖文件进来才亮；普通拖拽一律不亮（用户报的『误以为在导入』）", () => {
    expect(overlayAfterDrag("enter", ["Files"])).toBe(true);
    expect(overlayAfterDrag("over", ["Files"])).toBe(true);
    expect(overlayAfterDrag("enter", ["text/plain"])).toBe(false);   // ← 旧实现这里是 true
    expect(overlayAfterDrag("over", ["text/plain"])).toBe(false);
    expect(overlayAfterDrag("enter", null)).toBe(false);
  });

  it("leave / drop / end 一律熄灭 —— 松手在窗口外、Esc 取消、内部拖拽都能自愈", () => {
    for (const phase of ["leave", "drop", "end"] as const) {
      expect(overlayAfterDrag(phase, ["Files"])).toBe(false);
      expect(overlayAfterDrag(phase, ["text/plain"])).toBe(false);
      expect(overlayAfterDrag(phase, null)).toBe(false);
    }
  });

  it("回归：复刻旧实现的状态序列（enter 无条件亮 + leave/end 不清除）——必须能看出它会永久卡住", () => {
    // 旧实现等价于：enter ⇒ true；leave/end ⇒ 保持原值
    const legacy = (state: boolean, phase: string) => (phase === "enter" || phase === "over" ? true : state);
    let legacyState = legacy(false, "enter");          // 内部拖拽也点亮
    legacyState = legacy(legacyState, "dragend");      // 松手：不清除
    legacyState = legacy(legacyState, "dragleave");    // 拖出：不清除
    expect(legacyState).toBe(true);                    // ← 永久卡在粉色页面

    // 新实现同一序列：从不点亮、且任何结束事件都熄灭
    let now = overlayAfterDrag("enter", ["text/plain"]);
    now = overlayAfterDrag("end", ["text/plain"]);
    expect(now).toBe(false);
    let fileDrag = overlayAfterDrag("enter", ["Files"]);
    fileDrag = overlayAfterDrag("end", ["Files"]);
    expect(fileDrag).toBe(false);
  });
});

describe("覆盖层文案", () => {
  it("只有一处字面量（App 与测试共用常量，避免测试硬编码）", () => {
    expect(DROP_OVERLAY_TEXT).toBe("释放以导入 INP 文件");
  });
});

/*
 * 2026-10-21 用户实测（第二个坑）：在 3D 预览**子窗口**里框选文字后拖拽 ⇒ 主窗口亮粉色
 * 覆盖层且永不消失。根因是 App 用全局 listen 订阅 file-drop-hover，子窗口事件泄漏到主窗口；
 * 且文字拖拽没有 drop/cancelled 事件。修法 = 窗口作用域 + payload 必须是文件路径数组。
 */
describe("shouldShowDropOverlay（Tauri 跨窗口 hover 事件）", () => {
  it("主窗口 + 真文件路径 ⇒ 亮", () => {
    expect(shouldShowDropOverlay(["C:\\MCNP\\a.inp"], "main")).toBe(true);
    expect(shouldShowDropOverlay(["C:\\a.inp", "C:\\b.inp"], undefined)).toBe(true); // 老版本无 windowLabel
  });

  it("子窗口（3D 预览）的事件一律不亮 —— 用户报的『拖文字把主窗口点亮』", () => {
    expect(shouldShowDropOverlay(["C:\\a.inp"], "preview3d")).toBe(false);
    expect(shouldShowDropOverlay(["C:\\a.inp"], "cross_section")).toBe(false);
  });

  it("没有文件路径的拖拽（选中文字/图片）不亮", () => {
    expect(shouldShowDropOverlay([], "main")).toBe(false);
    expect(shouldShowDropOverlay(null, "main")).toBe(false);
    expect(shouldShowDropOverlay(undefined, "main")).toBe(false);
    expect(shouldShowDropOverlay("C:\\a.inp", "main")).toBe(false);   // 非数组
    expect(shouldShowDropOverlay([""], "main")).toBe(false);          // 空字符串路径
    expect(shouldShowDropOverlay([123], "main")).toBe(false);         // 非字符串
  });
});
