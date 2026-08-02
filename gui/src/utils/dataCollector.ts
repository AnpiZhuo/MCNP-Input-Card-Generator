/**
 * 生成 API 封装 — 把 deck 载荷 POST 到 Python 后端生成 INP
 * 表单数据采集已由受控组件直接写入 deck，本文件只保留 generateInp。
 */

export interface DeckData {
  basic: Record<string, any>;
  surfaces: string;
  tr_cards: string;
  cells: any[];
  materials: any[];
  sources: any[];
  tally: Record<string, any>;
  adv: Record<string, any>;
}

/** 调用 Python 后端生成 INP */
export async function generateInp(deck: DeckData): Promise<string> {
  const res = await fetch("http://localhost:5001/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(deck),
  });
  const json = await res.json();
  if (json.status === "error") throw new Error(json.message + "\n" + (json.traceback || ""));
  return json.inp;
}
