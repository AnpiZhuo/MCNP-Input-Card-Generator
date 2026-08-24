import { describe, it, expect } from "vitest";
import { localToDeckCells, deckToLocalCells, type LocalCellRow } from "../src/utils/cellBridge";
import type { CellData } from "../src/components/CellEditDialog";

const FILL_GRID_JSON = '{"lat":"1","kind":"lattice","range":["0:16","0:16","0:0"],"dims":[17,17,1],"cells":[{"u":"1","dx":"","dy":"","dz":""}],"raw":"1 1 1"}';

const baseCell = (over: Partial<CellData> = {}): CellData => ({
  num: "1",
  mat: "0",
  density: "",
  surfaces: "-1",
  impN: "",
  impP: "",
  impE: "",
  vol: "",
  pwt: "",
  ext: "",
  fcl: "",
  u: "",
  fill: "0:16 0:16 0:0",
  lat: "1",
  trcl: "",
  tmp: "",
  otherParams: "",
  render: true,
  fill_grid: "",
  comment: "a",
  ...over,
});

/** 后端 parse/text-to-section 返回的 deck cell（snake_case，无 fill_grid 时模拟旧数据） */
const deckCell = (over: Record<string, unknown> = {}): Record<string, unknown> => ({
  kind: "cell",
  cell: {
    number: 1,
    material: "0",
    density: "",
    surface_expr: "-1",
    imp_n: "",
    imp_p: "",
    imp_e: "",
    vol: "",
    pwt: "",
    ext: "",
    fcl: "",
    u: "",
    fill: "0:16 0:16 0:0",
    lat: "1",
    trcl: "",
    tmp: "",
    other_params: "",
    render: true,
    comment: "a",
    ...over,
  },
});

describe("cellBridge fill_grid 透传（阶段1 wire）", () => {
  it("local → deck：fill_grid 随 cell 进入后端请求 JSON", () => {
    const row: LocalCellRow = { kind: "cell", cell: baseCell({ fill_grid: FILL_GRID_JSON }) };
    const deck = localToDeckCells([row]);
    expect(deck[0]).toMatchObject({ kind: "cell" });
    expect((deck[0] as { cell: Record<string, unknown> }).cell.fill_grid).toBe(FILL_GRID_JSON);
    // 其余字段 snake_case 映射不受影响
    expect((deck[0] as { cell: Record<string, unknown> }).cell.surface_expr).toBe("-1");
    expect((deck[0] as { cell: Record<string, unknown> }).cell.other_params).toBe("");
  });

  it("deck → local：parse/text 回填含 fill_grid（非空透传）", () => {
    const local = deckToLocalCells([deckCell({ fill_grid: FILL_GRID_JSON })]);
    expect(local[0]).toMatchObject({ kind: "cell" });
    const cell = (local[0] as { cell: CellData }).cell;
    expect(cell.fill_grid).toBe(FILL_GRID_JSON);
    expect(cell.num).toBe("1");
    expect(cell.surfaces).toBe("-1");
  });

  it("旧数据缺 fill_grid：回填兜底为空串（round-trip 兼容）", () => {
    const local = deckToLocalCells([deckCell()]);
    expect((local[0] as { cell: CellData }).cell.fill_grid).toBe("");
  });

  it("local → deck → local 往返：fill_grid 不丢（parse→deck→generate 链路）", () => {
    const row: LocalCellRow = { kind: "cell", cell: baseCell({ fill_grid: FILL_GRID_JSON }) };
    const deck = localToDeckCells([row]);
    const back = deckToLocalCells(deck);
    expect((back[0] as { cell: CellData }).cell.fill_grid).toBe(FILL_GRID_JSON);
  });

  it("raw 行原样透传不受影响", () => {
    const deck = localToDeckCells([{ kind: "raw", text: "#ifdef X" }]);
    expect(deck[0]).toEqual({ kind: "raw", text: "#ifdef X" });
    const back = deckToLocalCells(deck);
    expect(back[0]).toEqual({ kind: "raw", text: "#ifdef X" });
  });
});
