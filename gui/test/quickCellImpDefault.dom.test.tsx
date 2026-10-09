// @vitest-environment jsdom
/**
 * 快捷建栅元 IMP 默认值回归（2026-10-08 用户报「3D 预览里新加的栅元没被纳入重合检测」的根因）。
 *
 * 症状链：QuickCellForm 的 IMP:N/P/E 默认被写成 `"0"`（`659d5c6` 把 `f2e8c4f` 的复选框改成
 * 文本框时翻转了语义）⇒ 每个快捷新建栅元都带 `IMP:N=0` ⇒ 后端 `_is_graveyard` 判为墓地 ⇒
 * `build_cells_data` 直接丢掉它 ⇒ **不在 3D 渲染、也不进 /api/check-overlap**（实测：盒子+圆柱，
 * imp 留空检出 (1,2)，imp_n="0" 只剩栅元 1、overlaps 为空），且全程无任何提示。
 *
 * 这里从**真实组件**出发断言：默认不写 imp=0；留空 + 基础页启用 N → 填 1；显式填 0 才写 0。
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import QuickCellForm from "../src/components/QuickCellForm";
import type { QuickCellResult } from "../src/utils/quickCell";

afterEach(() => cleanup());

function renderForm(modeN: boolean, onGenerate: (r: QuickCellResult) => void) {
  return render(React.createElement(QuickCellForm, {
    surfacesText: "", trCardsText: "", cellNumbers: [1],
    materials: [{ number: 1, comment: "MAT", density: "-1.0" }],
    onGenerate, keepOpenAfterGenerate: true, modeN, modeP: false, modeE: false,
  } as any));
}

/** rcc 是默认形状：填满「底面中心 / 轴向量 / 半径」让它合法，再走「确认生成」。
 *  表单的字段标签是 `<label>` + 同级 `<input>`（未做 htmlFor 关联），按标签文字取同级输入框。 */
function fillRcc() {
  const byLabel = (text: string): HTMLInputElement => {
    const label = screen.getAllByText(text).find((el) => el.tagName === "LABEL");
    if (!label) throw new Error("找不到标签 " + text);
    return label.parentElement!.querySelector("input") as HTMLInputElement;
  };
  for (const [k, v] of [["X", "0"], ["Y", "0"], ["Z", "0"],
                        ["HX", "0"], ["HY", "0"], ["HZ", "10"], ["半径", "3"]] as const) {
    fireEvent.change(byLabel(k), { target: { value: v } });
  }
}

describe("快捷建栅元 IMP 默认（回归：默认不得是 0）", () => {
  it("IMP:N/P/E 初值为空（不是 \"0\"）", () => {
    renderForm(true, () => {});
    for (const k of ["N", "P", "E"]) {
      expect((screen.getByLabelText(`IMP:${k}`) as HTMLInputElement).value).toBe("");
    }
    // 旧 placeholder "0" 会被读成默认值 0；现在明确写「自动」
    expect((screen.getByLabelText("IMP:N") as HTMLInputElement).placeholder).toBe("自动");
  });

  it("默认生成（材料 0 走确认）→ 基础页启用 N 时填 1，不得填 0", () => {
    const onGenerate = vi.fn();
    renderForm(true, onGenerate);
    fillRcc();
    fireEvent.click(screen.getByText("生成并加入"));
    fireEvent.click(screen.getByText("确认生成"));
    expect(onGenerate).toHaveBeenCalledTimes(1);
    const cell = (onGenerate.mock.calls[0][0] as QuickCellResult).cells[0];
    expect(cell.impN).toBe("1");
    // 修复前这一条是红的：默认 impN === "0" ⇒ 后端当墓地丢弃
    expect(cell.impN).not.toBe("0");
  });

  it("基础页未启用任何粒子 → 留空即整条 imp 不写", () => {
    const onGenerate = vi.fn();
    renderForm(false, onGenerate);
    fillRcc();
    fireEvent.click(screen.getByText("生成并加入"));
    fireEvent.click(screen.getByText("确认生成"));
    expect((onGenerate.mock.calls[0][0] as QuickCellResult).cells[0].impN).toBe("");
  });

  it("用户显式填 0 仍然生效（合法用法，只是不该是默认）", () => {
    const onGenerate = vi.fn();
    renderForm(true, onGenerate);
    fireEvent.change(screen.getByLabelText("IMP:N"), { target: { value: "0" } });
    fillRcc();
    fireEvent.click(screen.getByText("生成并加入"));
    fireEvent.click(screen.getByText("确认生成"));
    expect((onGenerate.mock.calls[0][0] as QuickCellResult).cells[0].impN).toBe("0");
  });
});
