import { describe, it, expect } from "vitest";
import { parseOutp } from "../src/utils/outputParser";

describe("parseOutp（本地兜底 OUTP 解析）", () => {
  it("MCNP6.1 紧凑布局：单栅元单能仓两列 flux/error，无 energy 列、无 total 行", () => {
    const text = [
      "1problem summary",
      "     run terminated when       10000  particle histories were done.",
      "1tally        4        nps =       10000",
      "           tally type 4    track length estimate of particle flux.      units   1/cm**2",
      "           particle(s): neutrons",
      "           volumes",
      "                   cell:       1",
      "                         4.18879E+03",
      " cell  1",
      "                 3.36115E-03 0.0071",
      " =======",
    ].join("\n");
    const r = parseOutp(text);
    expect(r.nps).toBe(10000);
    expect(Object.keys(r.tallies)).toEqual(["4"]);
    expect(r.tallies[4].rows).toEqual([{ energy: "", flux: "3.36115E-03", error: "0.0071" }]);
  });

  it("能量仓布局：energy/flux/error 三列 + total 行", () => {
    const text = [
      "1tally        4        nps =       50000",
      "           tally type 4    track length estimate of particle flux.",
      " cell  1",
      "      energy     flux     error",
      "   1.0000E-01   1.234E-03   0.0050",
      "   2.0000E-01   2.345E-03   0.0060",
      "      total       3.579E-03   0.0040",
      " =======",
    ].join("\n");
    const r = parseOutp(text);
    expect(r.tallies[4].rows).toEqual([
      { energy: "1.0000E-01", flux: "1.234E-03", error: "0.0050" },
      { energy: "2.0000E-01", flux: "2.345E-03", error: "0.0060" },
    ]);
    expect(r.tallies[4].total).toEqual({ energy: "total", flux: "3.579E-03", error: "0.0040" });
  });

  it("F1 面电流：surface 块 + 两列数值（MCNP6.1 紧凑布局）", () => {
    const text = [
      "1tally        1        nps =       10000",
      "           tally type 1    number of particles crossing a surface.",
      "           surfaces:                       2",
      " surface  2.1",
      "                 1.234E-03 0.0050",
      " =======",
    ].join("\n");
    const r = parseOutp(text);
    expect(r.tallies[1].rows).toEqual([{ energy: "", flux: "1.234E-03", error: "0.0050" }]);
  });

  it("F5 点探测器：detector 块 + 三列 + total", () => {
    const text = [
      "1tally        5        nps =       10000",
      "           tally type 5    point detector tally.",
      "           detector  1",
      "      energy     flux     error",
      "   1.0000E-01   1.234E-03   0.0050",
      "      total       3.579E-03   0.0040",
      " =======",
    ].join("\n");
    const r = parseOutp(text);
    expect(r.tallies[5].rows).toEqual([{ energy: "1.0000E-01", flux: "1.234E-03", error: "0.0050" }]);
    expect(r.tallies[5].total).toEqual({ energy: "total", flux: "3.579E-03", error: "0.0040" });
  });
});
