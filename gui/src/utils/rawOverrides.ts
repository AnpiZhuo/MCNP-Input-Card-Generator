/**
 * raw_overrides 载荷构造（生成时发往后端 /api/generate）。
 *
 * 文本模式下（deck.textMode[sec] 为 true），对应 section 的原始文本
 * （deck.rawOverrides[sec]）原样覆盖生成器输出；表单模式不发送。
 * 单一事实来源：App.tsx handleGenerate 不再内联此逻辑。
 */
export const RAW_OVERRIDE_SECTIONS = ["materials", "cells", "tally", "sdef"] as const;

export function buildRawOverrides(deck: {
  textMode?: Record<string, boolean>;
  rawOverrides?: Record<string, string>;
}): Record<string, string> {
  const ro: Record<string, string> = {};
  const tm = deck.textMode || {};
  const raw = deck.rawOverrides || {};
  for (const sec of RAW_OVERRIDE_SECTIONS) {
    if (tm[sec] && raw[sec]) ro[sec] = raw[sec];
  }
  return ro;
}
