// @vitest-environment jsdom
/**
 * TallyTab 前缀/后缀 DOM 回归 —— 用户报的两条症状在**界面层**锁死（2026-09-26）。
 *
 * 用户原话：
 *   ①「计数卡的前缀，`*` 号，解析时无法传入」—— 导入 `*F4:N` 后前缀列显示"无"；
 *   ②「自己点选后，点生成时也没有」—— 选了 `*` 点生成，INP 里还是 `F4:N`。
 *
 * 旧实现的实情：下拉框是**装饰品** ——
 *   `deckToLocalT` 硬编码 `prefix: ""`（导入必丢）、`localToDeckT` 根本不写 `prefix`
 *   （选择必丢），于是 deck.tallies 永远是 `F4` 无前缀，后端与引擎再对也没用。
 *
 * 本测试走真实组件 + 真实 DeckProvider：不是测桥接纯函数，而是测"下拉框真的落到 deck"。
 */
import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { DeckProvider, useDeck } from "../src/utils/DeckContext";
import TallyTab from "../src/components/TallyTab";

afterEach(() => cleanup());

/** 探针：把 deck.tallies 原样暴露给测试（不导出组件内部状态） */
function DeckProbe() {
  const { deck } = useDeck();
  return React.createElement("div", { "data-testid": "deck-tallies" },
    JSON.stringify(deck.tallies));
}

/** 复刻 App 的加载链路：loadDeck(后端回显 deck) */
function Seeder({ tallies }: { tallies: any[] }) {
  const { loadDeck } = useDeck();
  React.useEffect(() => {
    loadDeck({
      basic: {}, surfaces: "", tr_cards: "", cells: [], materials: [], sources: [],
      tallies, tally: {}, grids: {}, adv: {}, sourceTemplate: "free",
      rawOverrides: {}, textMode: {}, universeComments: {},
    } as any);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return null;
}

function renderTab(tallies: any[]) {
  return render(
    React.createElement(DeckProvider, null,
      React.createElement(Seeder, { tallies }),
      React.createElement(TallyTab),
      React.createElement(DeckProbe)),
  );
}

const deckTallies = (): any[] => JSON.parse(screen.getByTestId("deck-tallies").textContent || "[]");
const prefixSelect = () => screen.getByLabelText("计数卡前缀") as HTMLSelectElement;

describe("TallyTab 计数卡前缀（fn_prefix）", () => {
  it("导入回显带 `*` 时下拉框显示 `*`（症状①）", async () => {
    renderTab([{ type: "F4", number: 4, particle: "n", params: "1",
                 enableEn: false, enableTn: false, multiplier: "",
                 fn_prefix: "*", number_suffix: "" }]);
    await waitFor(() => expect(prefixSelect().value).toBe("*"));
  });

  it("在下拉框里选 `+` 之后，deck.tallies 立刻带上 fn_prefix（症状②）", async () => {
    renderTab([{ type: "F4", number: 4, particle: "n", params: "1",
                 enableEn: false, enableTn: false, multiplier: "",
                 fn_prefix: "", number_suffix: "" }]);
    await waitFor(() => expect(deckTallies()).toHaveLength(1));
    expect(deckTallies()[0].fn_prefix).toBe("");
    fireEvent.change(prefixSelect(), { target: { value: "+" } });
    await waitFor(() => expect(deckTallies()[0].fn_prefix).toBe("+"));
    // 其余字段不受影响（别把 A 改成 B 的同时把别的丢了）
    expect(deckTallies()[0]).toMatchObject({ type: "F4", number: 4, particle: "n", params: "1" });
  });

  it("回显里的成像前缀（FIC）在下拉框里有动态项、不被抹成空", async () => {
    renderTab([{ type: "F5", number: 5, particle: "n", params: "0 0 0 1",
                 enableEn: false, enableTn: false, multiplier: "",
                 fn_prefix: "FIC", number_suffix: "" }]);
    await waitFor(() => expect(prefixSelect().value).toBe("FIC"));
    expect(deckTallies()[0].fn_prefix).toBe("FIC");
  });
});

describe("TallyTab 环探测器后缀（number_suffix）", () => {
  it("导入 `F5X` 后轴字母显示在控件上、且留在 deck 上", async () => {
    renderTab([{ type: "F5", number: 5, particle: "n", params: "0 0 0 1",
                 enableEn: false, enableTn: false, multiplier: "",
                 fn_prefix: "", number_suffix: "X" }]);
    await waitFor(() => expect(deckTallies()).toHaveLength(1));
    expect((screen.getByLabelText("环探测器轴") as HTMLSelectElement).value).toBe("X");
    expect(deckTallies()[0].number_suffix).toBe("X");
  });

  it("改轴字母立刻落到 deck；改成空 = 退回点探测器", async () => {
    renderTab([{ type: "F5", number: 5, particle: "n", params: "0 0 0 1",
                 enableEn: false, enableTn: false, multiplier: "",
                 fn_prefix: "", number_suffix: "" }]);
    await waitFor(() => expect(deckTallies()).toHaveLength(1));
    expect(deckTallies()[0].number_suffix).toBe("");
    fireEvent.change(screen.getByLabelText("环探测器轴"), { target: { value: "Y" } });
    await waitFor(() => expect(deckTallies()[0].number_suffix).toBe("Y"));
    fireEvent.change(screen.getByLabelText("环探测器轴"), { target: { value: "" } });
    await waitFor(() => expect(deckTallies()[0].number_suffix).toBe(""));
  });

  it("编号框里粘 `25X`：数字进编号、X 进轴控件（旧行为：X 当场被吃掉）", async () => {
    renderTab([{ type: "F5", number: 5, particle: "n", params: "0 0 0 1",
                 enableEn: false, enableTn: false, multiplier: "",
                 fn_prefix: "", number_suffix: "" }]);
    await waitFor(() => expect(deckTallies()).toHaveLength(1));
    fireEvent.change(screen.getByLabelText("计数卡编号"), { target: { value: "25X" } });
    await waitFor(() => expect(deckTallies()[0]).toMatchObject({ number: 25, number_suffix: "X" }));
    expect((screen.getByLabelText("环探测器轴") as HTMLSelectElement).value).toBe("X");
  });

  it("非 F5 行不出现轴控件（F4 没有环探测器语义）", async () => {
    renderTab([{ type: "F4", number: 4, particle: "n", params: "1",
                 enableEn: false, enableTn: false, multiplier: "",
                 fn_prefix: "", number_suffix: "" }]);
    await waitFor(() => expect(deckTallies()).toHaveLength(1));
    expect(screen.queryByLabelText("环探测器轴")).toBeNull();
  });
});
