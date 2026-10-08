/**
 * svgPaint — 在 jsdom 里求值"这块地方被哪个颜色涂了"（测试用工具，非生产代码）。
 *
 * ## 为什么需要它
 * jsdom 不做 SVG 渲染、也没有命中测试 API，所以"用户看到什么"只能按 **SVG 规范的填充规则**
 * 自己算：一个元素的着色区域 = 它的全部子路径在 `fill-rule`（缺省 nonzero）下的内部。
 * 几何直接取自 DOM（`polygon` 的 points、`path` 的 d），与浏览器看到的是同一份 ⇒
 * 断言的是**用户可见的结果**，而不是 DOM 结构。这样：
 *   · 修法换成"一条 path + evenodd"或"环定向 + nonzero"都照样成立；
 *   · "把图删空"这类假绿会被对照点抓住。
 */
export type P2 = { x: number; y: number };

/** 取一个 SVG 元素的全部子路径（polygon → 1 条；path → 按 M/L/Z 切分） */
export function subpathsOf(el: Element): P2[][] {
  const tag = el.tagName.toLowerCase();
  if (tag === "polygon") {
    const pts = (el.getAttribute("points") || "").trim().split(/\s+/).filter(Boolean)
      .map((s) => { const [x, y] = s.split(",").map(Number); return { x, y }; });
    return pts.length >= 3 ? [pts] : [];
  }
  if (tag === "path") {
    const d = el.getAttribute("d") || "";
    const out: P2[][] = [];
    let cur: P2[] = [];
    const tokens = d.match(/[MLZmlz][^MLZmlz]*/g) || [];
    for (const tk of tokens) {
      const cmd = tk[0];
      const nums = (tk.slice(1).match(/-?\d*\.?\d+(?:e[-+]?\d+)?/gi) || []).map(Number);
      if (cmd === "M" || cmd === "m") {
        if (cur.length >= 3) out.push(cur);
        cur = [];
        for (let i = 0; i + 1 < nums.length; i += 2) cur.push({ x: nums[i], y: nums[i + 1] });
      } else if (cmd === "L" || cmd === "l") {
        for (let i = 0; i + 1 < nums.length; i += 2) cur.push({ x: nums[i], y: nums[i + 1] });
      } else if (cmd === "Z" || cmd === "z") {
        if (cur.length >= 3) out.push(cur);
        cur = [];
      }
    }
    if (cur.length >= 3) out.push(cur);
    return out;
  }
  return [];
}

function isLeft(a: P2, b: P2, p: P2): number {
  return (b.x - a.x) * (p.y - a.y) - (p.x - a.x) * (b.y - a.y);
}

/** 射线法：点是否在环内 */
export function pointInLoop(loop: P2[], p: P2): boolean {
  let inside = false;
  for (let i = 0, j = loop.length - 1; i < loop.length; j = i++) {
    const a = loop[i], b = loop[j];
    if ((a.y > p.y) !== (b.y > p.y) && p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y) + a.x) inside = !inside;
  }
  return inside;
}

/** 环的有符号绕数（nonzero 规则用） */
export function windingNumber(loop: P2[], p: P2): number {
  let wn = 0;
  for (let i = 0; i < loop.length; i++) {
    const a = loop[i], b = loop[(i + 1) % loop.length];
    if (a.y <= p.y) {
      if (b.y > p.y && isLeft(a, b, p) > 0) wn++;
    } else if (b.y <= p.y && isLeft(a, b, p) < 0) wn--;
  }
  return wn;
}

/** 按 SVG 填充规则求值：该元素是否在 p 点着色 */
export function elementPaints(el: Element, p: P2): boolean {
  const loops = subpathsOf(el);
  if (loops.length === 0) return false;
  const rule = (el.getAttribute("fill-rule") || (el as any).style?.fillRule || "nonzero").toLowerCase();
  if (rule === "evenodd") {
    let inside = false;
    for (const lp of loops) if (pointInLoop(lp, p)) inside = !inside;
    return inside;
  }
  let wn = 0;
  for (const lp of loops) wn += windingNumber(lp, p);
  return wn !== 0;
}

/** 该颜色在 p 点是否被涂上（= 浏览器会画出来的东西） */
export function paintedAt(container: HTMLElement, color: string, p: P2): boolean {
  const els = Array.from(container.querySelectorAll("polygon, path")) as Element[];
  return els.some((el) => {
    const f = (el.getAttribute("fill") || "").trim();
    if (f.toUpperCase() !== color.toUpperCase()) return false;
    if (el.getAttribute("fill-opacity") === "0") return false;
    return elementPaints(el, p);
  });
}
