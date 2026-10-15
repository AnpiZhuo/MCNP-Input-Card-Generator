/**
 * selectionSpan — 把文本框里的鼠标选区换算成「要删掉哪几个字符」。
 *
 * ## 为什么要有这个模块（2026-10-11 用户口径，逐字确认过）
 *
 * 用户原话：「我划了这些文字，你就把这些文字删掉，用我另外给出的文字替换」
 *          「不是整段删掉，是只把我划中的部分删掉」
 * ⇒ 替换是**文本级**的：删掉选中区间的那几个字符、把新内容原样插进去，**长度不限**
 *   （更长/更短/等于删除都行，像在 Word 里删掉再键入）。
 *
 * 之前的实现**没把选区位置传给后端**，只发了「选中的文字 + 所在整行」，后端于是自己猜
 * 「含这行的首个匹配」⇒ 同一个字出现两次就改错地方（实测：`SO 1 2323255 6` 划第二个 5，
 * 改的是第一个；文件里两行相同，划第二行改的是第一行）。
 *
 * 这里把「起点/终点」算准，并**保证 `content.slice(start, end) === anchor`** ——
 * 后端据此只认这一区间，对不上就报「位置失效，请重新框选」，绝不改到别处。
 */
export interface SelectionSpan {
  /** 选中（去掉两端空白后）的原文，供显示与参数命名 */
  anchor: string;
  /** 要删掉的区间起点（含） */
  start: number;
  /** 要删掉的区间终点（不含） */
  end: number;
}

/**
 * @returns 合法选区 → 区间；空选区 / 跨行 / 越界 → null（调用方给提示，不做替换）
 */
export function selectionSpan(content: string, rawStart: number, rawEnd: number): SelectionSpan | null {
  const start = Math.min(rawStart, rawEnd);
  const end = Math.max(rawStart, rawEnd);
  if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
  if (start < 0 || end > content.length || start >= end) return null;
  const seg = content.slice(start, end);
  const anchor = seg.trim();
  if (!anchor) return null;
  if (anchor.includes("\n")) return null;   // 只能框选同一行里的内容
  // 收窄到去掉两端空白后的真实内容 ⇒ slice(start,end) 恒等于 anchor
  const lead = seg.length - seg.replace(/^\s+/, "").length;
  return { anchor, start: start + lead, end: start + lead + anchor.length };
}
