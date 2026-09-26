/**
 * STEP 导入设置的持久化 —— 用**独立键**，与工作区状态互不干扰。
 *
 * 为什么独立键就够了（用户要求：「保留用户设置的内容，开启和关闭都记忆，
 * 就算程序主页面那个清空点了也不要改」）：
 * 主界面「🧹 清空」走的是 `App.tsx` 的 `handleClear` → `localStorage.removeItem(SAVE_KEY)`，
 * 只删工作区那一个键（`mcnp_workspace_v1`），**不是** `localStorage.clear()`
 * —— 仓库里主题（`THEME_KEY`）与「按 U 分组」（`mcnp_groupbyu_v1`）都是这么做的。
 * 所以本模块不需要、也不应该去改 `handleClear`。
 *
 * 三态语义（这是全模块唯一的难点，必须有单一来源）：
 *   · 键**不存在**      = 用户没动过该项 → 不发送 → 用 GEOUNED 自己的默认值
 *   · `false` / `"0"`   = 用户点过"关" → 显式发送 false
 *   · `true` / `"数值"` = 用户动过 → 显式发送
 * `JSON.stringify` 会丢掉 `undefined`、保留 `false`，所以往返不退化 ⇒
 * **"开启和关闭都记得住"** 是这套语义的自然结果，不需要额外字段。
 *
 * 接口刻意只有两个函数：读、写。没有 `clear()` ——
 * 「全部恢复默认」把所有项变回"没动过"，落盘结果自然就是 `{}`，
 * 少一个入口就少一条要保持同步的路径。
 */
const KEY = "mcnp_step_import_v1";
const VERSION = 1;

/** 值的类型与 StepImportDialog 的 vals 一致（string = 填空/下拉；boolean = 点选） */
export type ImportVals = Record<string, string | boolean | undefined>;

/** 坏数据/异版本一律当作"没有"：宁可用默认值，也不要拿半截数据去填表单 */
function isUsable(raw: string | null): boolean {
  if (!raw) return false;
  try {
    const data = JSON.parse(raw);
    return !!data && typeof data === "object" && data.version === VERSION
      && !!data.vals && typeof data.vals === "object";
  } catch {
    return false;
  }
}

/** 只保留 string / boolean；其余（数字、数组、null…）丢弃 —— 防止被篡改的存储污染表单 */
function sanitize(vals: ImportVals): ImportVals {
  const out: ImportVals = {};
  for (const [k, v] of Object.entries(vals || {})) {
    if (typeof v === "boolean" || (typeof v === "string" && v !== "")) out[k] = v;
  }
  return out;
}

/** 读取已记住的设置；没有/坏了/版本不符 → 空对象（= 全部用默认值） */
export function loadPrefs(): ImportVals {
  try {
    const raw = typeof localStorage === "undefined" ? null : localStorage.getItem(KEY);
    if (!isUsable(raw)) return {};
    const data = JSON.parse(raw as string);
    return sanitize(data.vals);
  } catch {
    return {};   // 存储不可用（某些 webview 会抛）也不能影响导入
  }
}

/** 记住当前设置；空对象 = 清空（「全部恢复默认」后自然走到这里） */
export function savePrefs(vals: ImportVals): void {
  try {
    if (typeof localStorage === "undefined") return;
    localStorage.setItem(KEY, JSON.stringify({ version: VERSION, vals: sanitize(vals) }));
  } catch {
    /* 存储写不进去（隐私模式/配额）也不该让导入失败 */
  }
}
