/**
 * keff 结果窗口：最终 k-eff（combined 优先）+ 逐周期收敛曲线（Recharts）+ 出图。
 *
 * 入口是「keff 解析」玻璃卡（`KeffParseCard`）的两个子按钮 —— 卡片选好文件后把
 * 路径作为 `initialPath` 传进来，本窗口挂载即解析。路径框仍可编辑：**运行目录**
 * （让后端自动找 mctal* / *.o）只能靠手输/粘贴，卡片按钮选不了目录。
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import FloatingDialog from "./FloatingDialog";
import { apiUrl, errorHint } from "../utils/api";
import { convergencePoints } from "../utils/sweepDashboard";
import { ExportButton } from "../export/useFigureExport";
import { build2dSpec, subtitleOf } from "../export/figureSpecs";
import { snapshotSvg } from "../export/captureFrame";

interface KeffResult {
  cycles: number[];
  mean: number[];
  std: number[];
  combined: { mean: number; std: number } | null;
}

export default function KeffDialog({ initialPath = "", onClose }:
  { initialPath?: string; onClose: () => void }) {
  const [path, setPath] = useState(initialPath);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [keff, setKeff] = useState<KeffResult | null>(null);

  const doParse = async (target?: string) => {
    const p = (target ?? path).trim();
    setErr("");
    if (!p) { setErr("请先在「keff 解析」卡里选文件，或粘贴 mctal / outp 路径、运行目录"); return; }
    setBusy(true);
    setKeff(null);
    try {
      const r = await fetch(apiUrl("/api/parse-keff"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: p }),
        signal: AbortSignal.timeout(30000),
      });
      const j = await r.json();
      if (j.status === "error") throw new Error(j.message);
      setKeff(j.keff);
    } catch (e: any) {
      setErr(errorHint(e, "keff 解析失败"));
    } finally {
      setBusy(false);
    }
  };

  // 卡片选好文件后直接出图（仅挂载时一次；之后由「解析」按钮/路径框驱动）
  useEffect(() => {
    if (initialPath.trim()) doParse(initialPath);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const points = useMemo(
    () => (keff ? convergencePoints({ cycles: keff.cycles, mean: keff.mean, std: keff.std }) : []),
    [keff],
  );

  const finalKeff = keff?.combined?.mean ?? (keff && keff.mean.length ? keff.mean[keff.mean.length - 1] : null);
  const finalStd = keff?.combined?.std ?? (keff && keff.std.length ? keff.std[keff.std.length - 1] : null);

  /**
   * 出图：Recharts 本身就渲染成 **SVG** ⇒ 直接抓下来就是真矢量，
   * 不用像 3D 那样做帧捕获（这也是"能用矢量就用矢量"里最便宜的一块）。
   *
   * ⚠️ 抓取必须发生在**点击那一刻**（`build()` 内），不能放渲染体里算：
   * Recharts 的 `<svg>` 由它自己的 effect 绘制，渲染期 `querySelector("svg")` 可能
   * 取到上一帧的空壳甚至 null。`snapshotSvg` 会把 CSS 变量解析成实际颜色，
   * 否则脱离文档后整片变黑。
   */
  const chartRef = useRef<HTMLDivElement>(null);
  // 出图走透明底：原先这里硬铺白矩形，与"该透明的透明"口径冲突
  const grabChartSvg = () => snapshotSvg(chartRef.current?.querySelector("svg") as SVGSVGElement | null);

  return (
    <FloatingDialog
      title="keff 收敛（mctal / outp）"
      onClose={onClose}
      width={680}
      footer={
        <>
          {keff && (
            <ExportButton
              label="keff 收敛曲线"
              build={() => {
                const svg = grabChartSvg();
                return {
                  view: "keff收敛",
                  nameParts: ["keff", finalKeff === null ? "" : finalKeff.toFixed(5)],
                  vector: build2dSpec({
                    title: "k-eff 逐周期收敛",
                    subtitle: subtitleOf([
                      finalKeff === null ? undefined : `最终 k-eff ${finalKeff.toFixed(5)}${finalStd !== null ? ` ± ${finalStd.toFixed(5)}` : ""}`,
                      `周期数 ${keff.cycles.length}（${keff.combined ? "combined keff" : "末周期均值"}）`,
                      path.trim() ? `来源 ${path.trim()}` : undefined,
                    ]),
                    panels: svg ? [{ svg }] : [],
                    caption: "红色虚线为 k = 1；图为屏幕图的直接导出（坐标系与配色沿用屏幕）",
                  }),
                };
              }}
            />
          )}
          <button className="btn btn-ghost btn-sm" onClick={onClose}>关闭</button>
          <button className="btn btn-primary btn-sm" onClick={() => doParse()} disabled={busy}>
            {busy ? "解析中…" : "解析 keff"}
          </button>
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 12 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            className="form-input"
            style={{ flex: 1, fontFamily: "Consolas,monospace", fontSize: 11 }}
            value={path}
            onChange={(e) => { setPath(e.target.value); setKeff(null); }}
            placeholder="mctal / outp(.o) 文件路径，或运行目录（自动找 mctal* / *.o）"
          />
        </div>
        <div style={{ fontSize: 11, color: "var(--text-tertiary)", lineHeight: 1.5 }}>
          选文件用输出页的「keff 解析」卡（<b>解析 mctal</b> / <b>解析 .o</b> 两个按钮）；
          这里也可以直接粘贴路径或<b>运行目录</b>（目录会自动找 mctal* / *.o）。
          mctal 通常无扩展名；<code>.o</code>（outp）的逐周期 keff 取 print table 175 的周期表。
        </div>
        {err && <div style={{ color: "#e53935", fontSize: 12 }}>{err}</div>}

        {keff && (
          <>
            <div style={{ display: "flex", gap: 16, alignItems: "baseline" }}>
              <div>
                <div style={{ fontSize: 10, color: "var(--text-tertiary)" }}>最终 k-eff</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: "var(--accent-glow, #38bdf8)" }}>
                  {finalKeff === null ? "n/a" : finalKeff.toFixed(5)}
                  {finalStd !== null && (
                    <span style={{ fontSize: 12, fontWeight: 400, color: "var(--text-tertiary)", marginLeft: 6 }}>
                      ± {finalStd.toFixed(5)}
                    </span>
                  )}
                </div>
              </div>
              <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>
                周期数：{keff.cycles.length}（{keff.combined ? "combined keff" : "末周期均值"}）
              </div>
            </div>
            <div ref={chartRef}>
            <LineChart width={640} height={240} data={points} margin={{ top: 8, right: 20, bottom: 4, left: 4 }}>
              <CartesianGrid stroke="rgba(255,255,255,0.08)" strokeDasharray="3 3" />
              <XAxis dataKey="cycle" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11, fill: "var(--text-tertiary, #94a3b8)" }} label={{ value: "cycle", position: "insideBottomRight", offset: -2, style: { fontSize: 10, fill: "var(--text-tertiary, #94a3b8)" } }} />
              <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11, fill: "var(--text-tertiary, #94a3b8)" }} width={56} />
              <Tooltip
                contentStyle={{ background: "var(--bg-input, #121a2e)", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 6, fontSize: 12, color: "var(--text-primary, #e2e8f0)" }}
              />
              <ReferenceLine y={1} stroke="#f87171" strokeDasharray="4 4" />
              <Line type="monotone" dataKey="mean" stroke="#38bdf8" strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
            </div>
          </>
        )}
      </div>
    </FloatingDialog>
  );
}
