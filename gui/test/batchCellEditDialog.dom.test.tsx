// @vitest-environment jsdom
/**
 * BatchCellEditDialog DOM 交互测试。
 *
 * 覆盖：锁死的曲面表达式提示（不可编辑）+ 后缀输入；确认回调携带正确的批量值；
 * 初始为空时「确认」禁用；填写后可用。
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import BatchCellEditDialog from "../src/components/BatchCellEditDialog";

afterEach(() => cleanup());

const cells = [
  { num: "1", mat: "1", density: "-1.0" },
  { num: "2", mat: "0", density: "" },
];
const mats = [{ number: 1, comment: "水", density: "1.0", nuclides: [], options: "", mt_card: "" }];

describe("BatchCellEditDialog DOM 交互", () => {
  it("显示可添加栅元数量与锁死的曲面提示", () => {
    render(React.createElement(BatchCellEditDialog, {
      cells, availableMats: mats, onApply: () => {}, onClose: () => {},
    }));
    expect(screen.getByText(/批量编辑栅元（已勾选 2 个）/)).toBeTruthy();
    expect(screen.getByText("无法批量更改曲面表达式，只可添加")).toBeTruthy();
    // 确认默认禁用（无写操作）
    expect((screen.getByRole("button", { name: "确认" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("选择材料自动带出密度 + 追加曲面 → 确认回调", () => {
    const onApply = vi.fn();
    render(React.createElement(BatchCellEditDialog, {
      cells, availableMats: mats, onApply, onClose: () => {},
    }));
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "1" } });
    fireEvent.change(screen.getByPlaceholderText("追加到勾选栅元曲面表达式之后，如: 3 -4"), { target: { value: "3 -4" } });
    fireEvent.click(screen.getByRole("button", { name: "确认" }));
    expect(onApply).toHaveBeenCalledTimes(1);
    expect(onApply.mock.calls[0][0]).toEqual(expect.objectContaining({ mat: "1", density: "1.0", surfaceAppend: "3 -4" }));
  });

  it("取消触发 onClose", () => {
    const onClose = vi.fn();
    render(React.createElement(BatchCellEditDialog, {
      cells, availableMats: mats, onApply: () => {}, onClose,
    }));
    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
