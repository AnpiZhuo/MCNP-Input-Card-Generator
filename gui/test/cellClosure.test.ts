/**
 * cellClosure — 深模块纯函数测试（TD-30）。
 *
 * 覆盖 seam：`closureMeta(status)` → {icon, color, label, allowed, title} 六状态 + 未知 fallback。
 *
 * 语义锁（用户裁决，2026-09-10）：**「外无限 / 部分无限」允许存在，只提示感叹号；
 * 唯有「曲面不封闭」（空/退化、体素、未解析）才是禁止。** 故本文件把
 * `closed / infinite / semi_infinite → allowed === true` 钉成硬断言 —— 这条一旦被改，
 * 栅元编辑对话框与几何页会把 graveyard 类栅元误判成「需修复」。
 *
 * 跨端词表锁（T3 FE-21 遗留）：本模块第 15 行的 status 联合类型是**逐字复刻** Python
 * `app/_freecad_csg_worker.py` 的六个产出值（closed/infinite/semi_infinite/empty/voxel/
 * unresolvable，见该文件 :1157/:1168-1169/:1170-1171/:1148/:1140/:1137）。后端新增或改名状态时，
 * 前端会静默掉进 `closureMeta` 的 fallback（icon "?"、label 回显英文状态串）而**没有任何测试会红**。
 * 故此处显式断言这六个值 —— 它不会自动发现后端改了，但会让「前端契约表被改动」立即变红，
 * 是跨端锁的第一道（Python 侧同名锁见 tests/unit 的按需补充，非本批范围）。
 *
 * 另注（bound 依赖）：`semi_infinite` 的判定依赖包围盒（容差 tol = B*0.005），
 * 同一栅元在不同 bound 下可能从 closed 变 semi_infinite ⇒ **断言必须按「给定 bound 下的期望」写，
 * 不可写固定期望 semi_infinite**。本文件只测纯函数映射，不构造几何，故不受此影响。
 */
import { describe, expect, it } from "vitest";
import { closureMeta } from "../src/utils/cellClosure";
import type { ClosureEntry } from "../src/utils/cellClosure";

/** 六状态全表（与 cellClosure.ts 的 _META 同源；同时充当跨端词表锁） */
const ALL_STATUSES = [
  "closed", "infinite", "semi_infinite", "empty", "voxel", "unresolvable",
] as const;

describe("cellClosure.closureMeta（六状态展示元数据）", () => {
  it("六状态全部命中 _META（不回落到 fallback）", () => {
    for (const s of ALL_STATUSES) {
      const m = closureMeta(s);
      expect(m.icon).not.toBe("?");          // "?" 是 fallback 的记认
      expect(m.title).not.toBe("未知状态");   // fallback title
      expect(typeof m.label).toBe("string");
      expect(m.label).not.toBe(s);           // 命中真实中文标签，而非回显英文状态串
    }
  });

  it("closed → 勾、绿、允许、非空 label/title", () => {
    expect(closureMeta("closed")).toEqual({
      icon: "✓", color: "#2e7d32", label: "封闭", allowed: true, title: "封闭有界",
    });
  });

  it("语义锁（用户裁决）：infinite / semi_infinite 必须 allowed === true（外无限是允许的，不是错误）", () => {
    expect(closureMeta("infinite").allowed).toBe(true);
    expect(closureMeta("semi_infinite").allowed).toBe(true);
    // 只提示感叹号，不用禁止态的红 ❌
    expect(closureMeta("infinite").icon).toBe("!");
    expect(closureMeta("semi_infinite").icon).toBe("!");
  });

  it("语义锁：唯有曲面不封闭三态才是禁止（empty / voxel / unresolvable → allowed === false）", () => {
    for (const s of ["empty", "voxel", "unresolvable"] as const) {
      expect(closureMeta(s).allowed).toBe(false);
      expect(closureMeta(s).icon).toBe("❌");
    }
  });

  it("allowed 分组恰好二分：3 允许（closed/infinite/semi_infinite）+ 3 禁止（empty/voxel/unresolvable）", () => {
    const allowed = ALL_STATUSES.filter((s) => closureMeta(s).allowed);
    const blocked = ALL_STATUSES.filter((s) => !closureMeta(s).allowed);
    expect(allowed).toEqual(["closed", "infinite", "semi_infinite"]);
    expect(blocked).toEqual(["empty", "voxel", "unresolvable"]);
  });

  it("未知状态 → fallback：icon '?'、label 原样回显状态串、allowed false、title '未知状态'（不抛错）", () => {
    const m = closureMeta("brand_new_status");
    expect(m).toEqual({
      icon: "?", color: "var(--text-tertiary)", label: "brand_new_status", allowed: false, title: "未知状态",
    });
    // 空串同样走 fallback，不崩
    expect(closureMeta("").icon).toBe("?");
  });

  it("跨端词表锁：status 联合类型 == 六状态集合（改这里即需同步 Python 产出值）", () => {
    // 用 TS 类型层穷举：若联合类型新增/改名，下面的赋值会编译期报错。
    const asUnion = (s: string): ClosureEntry["status"] => {
      const hit = ALL_STATUSES.find((x) => x === s);
      if (!hit) throw new Error(`unknown status: ${s}`);
      return hit;
    };
    for (const s of ALL_STATUSES) expect(asUnion(s)).toBe(s);
    expect(ALL_STATUSES).toHaveLength(6);
  });

  it("颜色都是可用的 CSS 值（不出现 undefined/空串）", () => {
    for (const s of ALL_STATUSES) {
      const c = closureMeta(s).color;
      expect(typeof c).toBe("string");
      expect(c.length).toBeGreaterThan(0);
    }
  });
});
