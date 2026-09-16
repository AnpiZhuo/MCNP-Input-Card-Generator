/**
 * materialLegend — 材料图例的注释来源（3D 预览 / 二维截面共用，单一实现）。
 *
 * 职责边界（2026-09-16 用户澄清）：
 *   - **材料显示接材料页**：图例（● M1 - 注释）的注释只能来自 `MaterialData.comment`；
 *   - **栅元信息接栅元定义**：栅元列表（`CellList` 行尾）显示 `cell.comment`。
 * 两者不可互串 —— 旧代码把 **栅元注释** 塞进图例注释槽（`cellViews.find(cv => cv.mat === e.mat)?.comment`），
 * 于是「材料」页里写的注释永远读不到（用户报的"3D 预览读不到材料注释"），
 * 而且同一材料有多个栅元时，图例会随机显示其中某个栅元的注释（语义错 + 不确定）。
 *
 * 因此本模块**只**做一件事：由材料表解析图例注释；栅元注释不参与、也不回退。
 */

export interface LegendMaterial {
  number: number | string;
  comment?: string;
}

/** 空白（undefined / null / 纯空格）视为"没写注释" */
function meaningful(s?: string | null): string | undefined {
  const t = (s ?? "").trim();
  return t.length > 0 ? t : undefined;
}

/** 材料页注释（唯一来源）；材料表缺该项 / 注释为空 → undefined（图例只显示 M{n}） */
export function materialComment(
  mat: string | number,
  materials?: LegendMaterial[],
): string | undefined {
  const hit = (materials || []).find((m) => String(m.number) === String(mat));
  return meaningful(hit?.comment);
}

/** 按「出现的材料号」生成图例项（注释来自材料页） */
export function materialLegendEntries(
  mats: (string | number)[],
  materials?: LegendMaterial[],
): { mat: string; comment?: string }[] {
  const seen = new Set<string>();
  const out: { mat: string; comment?: string }[] = [];
  for (const m of mats) {
    const key = String(m);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ mat: key, comment: materialComment(key, materials) });
  }
  return out;
}
