/**
 * 标签页文本↔表单互转 API 封装。
 *
 * section: "materials" | "cells" | "tally"
 *  表单→文本: sectionToText(section, deck) → { text }
 *  文本→表单: textToSection(section, text) → { data: {materials|cells|tallies} }
 */

import { apiUrl } from "./api";

export type SectionKey = "materials" | "cells" | "tally";

/** 表单 → 文本：把某模块的表单数据生成该模块的 INP 文本 */
export async function sectionToText(section: SectionKey, deck: any): Promise<string> {
  const r = await fetch(apiUrl("/api/section-to-text"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ section, deck }),
  });
  const j = await r.json();
  if (j.status !== "ok") throw new Error(j.message || "生成文本失败");
  return j.text || "";
}

/** 文本 → 表单：把某模块的 INP 文本解析回结构化数据 */
export async function textToSection(section: SectionKey, text: string): Promise<any> {
  const r = await fetch(apiUrl("/api/text-to-section"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ section, text }),
  });
  const j = await r.json();
  if (j.status !== "ok") throw new Error(j.message || "解析失败");
  return j.data || {};
}
