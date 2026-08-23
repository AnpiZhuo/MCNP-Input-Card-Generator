import { describe, expect, it } from "vitest";
import { parseDiffLines } from "../src/utils/diffRender";

describe("parseDiffLines", () => {
  it("classifies header / add / del / context lines", () => {
    const diff = [
      "--- a",
      "+++ b",
      "@@ -1,2 +1,2 @@",
      " mode n",
      "-nps 1000",
      "+nps 5000",
    ].join("\n");
    const lines = parseDiffLines(diff);
    expect(lines.map((l) => l.type)).toEqual([
      "header", "header", "header", "ctx", "del", "add",
    ]);
    expect(lines[4].text).toBe("-nps 1000");
  });

  it("handles empty diff", () => {
    expect(parseDiffLines("")).toEqual([]);
    expect(parseDiffLines(undefined as unknown as string)).toEqual([]);
  });
});
