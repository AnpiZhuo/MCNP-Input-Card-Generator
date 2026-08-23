/** unified diff 文本 → 着色行列表（纯函数，可单测）。 */

export type DiffLineType = "header" | "add" | "del" | "ctx";

export interface DiffLine {
  type: DiffLineType;
  text: string;
}

export function parseDiffLines(diff: string): DiffLine[] {
  const out: DiffLine[] = [];
  if (!diff) return out;
  for (const raw of (diff || "").split("\n")) {
    if (raw.startsWith("@@") || raw.startsWith("+++") || raw.startsWith("---")) {
      out.push({ type: "header", text: raw });
    } else if (raw.startsWith("+")) {
      out.push({ type: "add", text: raw });
    } else if (raw.startsWith("-")) {
      out.push({ type: "del", text: raw });
    } else {
      out.push({ type: "ctx", text: raw });
    }
  }
  return out;
}
