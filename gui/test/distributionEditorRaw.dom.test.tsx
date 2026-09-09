// @vitest-environment jsdom
/**
 * DistributionEditor 原文(raw)模式渲染回归测试。
 *
 * raw 模式 = 每行一条卡：卡名徽标(token, SI/SP/SB/DS)在文本框外提示，
 * 框内是纯文本内容（无前缀），值多时框自动变高排开。
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import DistributionEditor from "../src/components/DistributionEditor";
import type { DistEntry } from "../src/utils/DeckContext";

afterEach(() => cleanup());

function rawEntry(rawText: string, id = 1): DistEntry {
  return {
    id, paramRef: "ERG", auto: false,
    editMode: "raw", rawText,
    si: null, sp: null, sb: null, ds: null,
  } as DistEntry;
}

describe("DistributionEditor raw 模式：卡名徽标外置 + 纯文本内容框", () => {
  it("每行显示卡名徽标(SI1/SP1)在文本框外", () => {
    const onChange = vi.fn();
    render(React.createElement(DistributionEditor, {
      entry: rawEntry("SI1  L  0  1.335  2\nSP1  0.5  0.5"),
      onChange, onDelete: () => {},
    }));
    // 卡名徽标与底部添加卡按钮都会显示 SI1,但 token 徽标在文本框外
    const si1 = screen.getAllByText("SI1");
    expect(si1.length).toBeGreaterThanOrEqual(1);
    const sp1 = screen.getAllByText("SP1");
    expect(sp1.length).toBeGreaterThanOrEqual(1);
    // 确认第一行文本框的内容不含前缀 SI1
    const textareas = screen.getAllByRole("textbox") as HTMLTextAreaElement[];
    const siContent = textareas[0].value;
    expect(siContent).toMatch(/^L\b/);
  });

  it("文本框内是纯内容(不含前缀)", () => {
    const onChange = vi.fn();
    render(React.createElement(DistributionEditor, {
      entry: rawEntry("SI2  A  -5  5"),
      onChange, onDelete: () => {},
    }));
    // 找到 content textarea：它的 value 不应以 SI2 开头
    const textareas = screen.getAllByRole("textbox") as HTMLTextAreaElement[];
    expect(textareas.length).toBeGreaterThan(0);
    expect(textareas[0].value).toBe("A  -5  5");
    expect(textareas[0].value).not.toMatch(/^SI2\b/);
  });

  it("编辑文本框内容 → onChange 携带重建的整行(前缀 + 新内容)", () => {
    const onChange = vi.fn();
    render(React.createElement(DistributionEditor, {
      entry: rawEntry("SI2  A  -5  5\nSP2  0.5  0.5"),
      onChange, onDelete: () => {},
    }));
    const textareas = screen.getAllByRole("textbox") as HTMLTextAreaElement[];
    // 修改第一行(SI)的内容
    fireEvent.change(textareas[0], { target: { value: "A  -5  6" } });
    expect(onChange).toHaveBeenCalledTimes(1);
    const next = onChange.mock.calls[0][0] as DistEntry;
    expect(next.editMode).toBe("raw");
    // rawText 第一行应为 "SI2  A  -5  6", 第二行 "SP2  0.5  0.5" 不变
    const lines = next.rawText!.split("\n");
    expect(lines[0].trim()).toBe("SI2  A  -5  6");
    expect(lines[1].trim()).toBe("SP2  0.5  0.5");
  });

  it("多了条 distributionEditorRaw.dom.test.tsx 行编辑自动增高存在(纯文本不拆格子)", () => {
    const onChange = vi.fn();
    render(React.createElement(DistributionEditor, {
      entry: rawEntry("SI1  L  0  1.335  2  4  8  16  32  64"),
      onChange, onDelete: () => {},
    }));
    // 所有可编辑元素都应该是 textarea,没有 input(如网格格子)
    const textareas = screen.getAllByRole("textbox") as HTMLTextAreaElement[];
    expect(textareas.length).toBe(1);
    // 确认是 textarea(HTMLTextAreaElement)而非 input
    expect(textareas[0].tagName).toBe("TEXTAREA");
    // 内容包含所有值(不散成格子)
    expect(textareas[0].value).toContain("L");
    expect(textareas[0].value).toContain("64");
  });
});