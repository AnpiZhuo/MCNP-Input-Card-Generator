/**
 * MCNP 卡片语法（Monaco Monarch）与幽灵提示的**唯一来源**。
 *
 * 为什么单独成模块：Monarch 的 tokenizer 状态是**跨行保持**的 —— 行尾停在哪个状态，下一行就从
 * 那个状态开始。语法写错只会表现为「某几行不着色」，而 Monaco 在无头环境下要跑起来需要一整套
 * standalone 服务，所以这种错**只能靠肉眼在界面上发现**。抽成纯数据 + 纯函数后，`monaco.editor
 * .tokenize()` 就能在测试里逐行断言（见 `gui/test/mcnpCardSyntax.test.ts`）。
 *
 * 组件（`McnpEditor.tsx`）只负责把这里的东西接到 Monaco 上，不再自己写语法。
 */
import type { languages } from "monaco-editor";

export type CardMode = "surface" | "tr";

export const languageId = (mode: CardMode): string => `mcnp-${mode}-card`;

export const SURFACE_DESCS: Record<string, string> = {
  P: "一般平面", PX: "X垂面", PY: "Y垂面", PZ: "Z垂面",
  SO: "球心在原点的球", S: "一般球", SX: "X轴球", SY: "Y轴球", SZ: "Z轴球",
  CX: "X轴圆柱", CY: "Y轴圆柱", CZ: "Z轴圆柱",
  "C/X": "平行X轴圆柱", "C/Y": "平行Y轴圆柱", "C/Z": "平行Z轴圆柱",
  KX: "X轴圆锥", KY: "Y轴圆锥", KZ: "Z轴圆锥",
  "K/X": "平行X轴锥", "K/Y": "平行Y轴锥", "K/Z": "平行Z轴锥",
  SQ: "轴平行二次曲面", GQ: "一般二次曲面",
  TX: "X轴环面", TY: "Y轴环面", TZ: "Z轴环面",
  X: "X轴旋转体", Y: "Y轴旋转体", Z: "Z轴旋转体",
  RPP: "长方体", SPH: "球体", RCC: "正圆柱", TRC: "截头圆锥",
  REC: "椭圆柱", ELL: "椭球", WED: "楔形", BOX: "盒子", ARB: "任意多面体",
  RHP: "正六棱柱", HEX: "正六棱柱",
};

const SURFACE_TYPES = Object.keys(SURFACE_DESCS);

const GHOST_HINTS: Record<string, string> = {
  P: "A B C D", PX: "D", PY: "D", PZ: "D",
  SO: "R", S: "x0 y0 z0 R", SX: "x0 R", SY: "y0 R", SZ: "z0 R",
  CX: "R", CY: "R", CZ: "R",
  "C/X": "y0 z0 R", "C/Y": "x0 z0 R", "C/Z": "x0 y0 R",
  KX: "x0 t2 ±1", KY: "y0 t2 ±1", KZ: "z0 t2 ±1",
  "K/X": "x0 y0 z0 t2 ±1", "K/Y": "x0 y0 z0 t2 ±1", "K/Z": "x0 y0 z0 t2 ±1",
  SQ: "x0 y0 z0 A B C D E F G", GQ: "A B C D E F G H J K",
  TX: "x0 y0 z0 A B C", TY: "x0 y0 z0 A B C", TZ: "x0 y0 z0 A B C",
  RPP: "Xmin Xmax Ymin Ymax Zmin Zmax",
  SPH: "Vx Vy Vz R", RCC: "Vx Vy Vz Hx Hy Hz R",
  TRC: "Vx Vy Vz Hx Hy Hz R1 R2",
  REC: "Vx Vy Vz Hx Hy Hz V1x V1y V1z V2x V2y V2z",
  ELL: "V1x V1y V1z V2x V2y V2z Rm",
  WED: "Vx Vy Vz V1 V2 V3", BOX: "Vx Vy Vz A1 A2 A3",
  ARB: "8顶点 6面定义",
  RHP: "Vx Vy Vz Hx Hy Hz R1 R2 R3 S1 S2 S3 T1 T2 T3",
  HEX: "Vx Vy Vz Hx Hy Hz R1 R2 R3 S1 S2 S3 T1 T2 T3",
};

const TR_PARAMS = "Tx Ty Tz B1 B2 B3 B4 B5 B6 B7 B8 B9".split(" ");

/** MCNP 数字的字面量正则**源**：语法着色与幽灵提示共用这一份，避免两处漂移。 */
const NUMBER_SRC = String.raw`[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?`;
const NUMBER_EXACT = new RegExp(`^(?:${NUMBER_SRC})$`);
const NUMBER = new RegExp(NUMBER_SRC);

const isNumberToken = (token: string): boolean => NUMBER_EXACT.test(token);

const surfaceTypePattern = new RegExp(
  `(?:${SURFACE_TYPES.map((t) => t.replace("/", "\\/")).join("|")})\\b`,
  "i",
);

/**
 * ⚠️ 这两个语法都必须**只有 root 一个状态**（回归测试守着这条不变量）。
 *
 * 反例是 2026-10-08 报的「曲面卡只有第一行着色」：当时是 root → surfaceAfterId → surfaceBody
 * 三层跳转，两个子状态都没有「行尾回 root」的规则，于是第 1 行读完就卡在 surfaceBody —— 从第 2 行起
 * 行首曲面号落到 `number`（绿）而不是 `surface-id`（黄），注释行也不再着色（那条规则只在 root 里）。
 * 单状态逐行独立，从根上没有这个坑。
 */
export const surfaceTokenizer = (): languages.IMonarchLanguage => ({
  tokenizer: {
    root: [
      [/^\s*[Cc].*$/, "comment"],
      // 曲面号 + 紧随其后的变换号（MCNP 语义：曲面号后面紧跟的整数就是 TR 引用）。两个捕获组都
      // 必然参与匹配，所以能用数组给它们分别指定 token。
      [new RegExp(`^(\\s*[+*]?\\d+)(\\s+[+-]?\\d+)(?=\\s|$)`), ["surface-id", "tr-reference"]],
      [/^\s*[+*]?\d+/, "surface-id"],
      [/\$.*/, "comment"],
      [surfaceTypePattern, "type"],
      [NUMBER, "number"],
    ],
  },
});

export const trTokenizer = (): languages.IMonarchLanguage => ({
  tokenizer: {
    root: [
      [/^\s*[Cc].*$/, "comment"],
      [/\$.*/, "comment"],
      [/^\s*\*?TR\d+\b/i, "tr-id"],
      [NUMBER, "number"],
    ],
  },
});

/** 当前行「还差哪些参数」的幽灵提示；不需要提示时返回 null。 */
export function ghostForLine(line: string, mode: CardMode): string | null {
  const trimmed = line.trim();
  if (!trimmed || /^[Cc]\s/.test(trimmed) || trimmed.startsWith("$")) return null;
  const body = trimmed.split("$", 1)[0].trim();
  if (mode === "tr") {
    if (!/^\*?TR\d+/i.test(body)) return null;
    const count = body.split(/\s+/).slice(1).filter(isNumberToken).length;
    return count >= TR_PARAMS.length ? null : TR_PARAMS.slice(count).join(" ");
  }

  const tokens = body.toUpperCase().split(/\s+/);
  let type = "";
  let start = -1;
  for (let i = 0; i < tokens.length; i++) {
    if (GHOST_HINTS[tokens[i]]) {
      type = tokens[i];
      start = i + 1;
      break;
    }
  }
  if (!type || start < 0) return null;
  const expected = GHOST_HINTS[type].split(/\s+/);
  const count = tokens.slice(start).filter((token) => isNumberToken(token) || token === "±1").length;
  if (count >= expected.length) return "$ " + SURFACE_DESCS[type];
  return expected.slice(count).join(" ");
}

/** 补全候选词（曲面卡 = 曲面类型；TR 卡 = 两条 TR 写法）。 */
export const completionWords = (mode: CardMode): string[] =>
  mode === "tr" ? ["TR", "*TR"] : SURFACE_TYPES;

/** 补全项的说明文字。 */
export const completionDetail = (word: string, mode: CardMode): string =>
  mode === "surface" ? SURFACE_DESCS[word] : "平移+旋转";
