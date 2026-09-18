/**
 * PlaneControls — 「平面方程 + 步长 + 步进」共享控件（3D 预览 / 截面窗口 / 切面面板共用）。
 *
 * ## 为什么抽出来
 * 这套交互原先**两处各写一份**：`Preview3D.tsx` 的方程输入框 + 折半/加倍步长，
 * `CrossSectionView.tsx` 里另一份 `D ± step` 步进。三处（现在加上 fmesh 切面）各写一份，
 * 最先分叉的一定是"步长"的语义——用户会发现两个窗口里同样的步长走得不一样。
 * 抽成一个受控组件后：**方程解析、步长折半/加倍、步进方向只在这里定义一次**。
 *
 * 受控：平面由宿主持有（`plane` + `onPlaneChange`），本组件不存任何状态，
 * 除了输入框里"还没提交的文本"这一瞬态（否则用户打字时会被外部同步打断）。
 */
import React, { useEffect, useState } from "react";
import { parsePlane, planeToStr, halveStep, doubleStep, type PlaneEq } from "../three/planeEquation";

export interface PlaneControlsProps {
  plane: PlaneEq;
  onPlaneChange: (plane: PlaneEq) => void;
  /** 步长（D 的增量） */
  step: number;
  onStepChange: (step: number) => void;
  /** 是否显示 ◀ ▶ 步进按钮（只在能重新求值的地方显示，如截面窗口） */
  showStepButtons?: boolean;
  /** 步进后触发的重新求值（缺省只改 plane） */
  onStepMove?: (plane: PlaneEq) => void;
  /** 平面方程提交时的回调（缺省只改 plane）；用于"改完就重新切" */
  onSubmitPlane?: (plane: PlaneEq) => void;
  /** 紧凑模式（体积窗口右栏窄，用更小字号） */
  compact?: boolean;
  /** 步进按钮的提示（不同窗口语义不同） */
  stepTitle?: string;
  /** 注入到方程行下方的附加控件（如体积窗口的「轴 + 层号」滑块） */
  extra?: React.ReactNode;
}

export function PlaneControls({
  plane, onPlaneChange, step, onStepChange,
  showStepButtons = false, onStepMove, onSubmitPlane, compact = false, stepTitle, extra,
}: PlaneControlsProps) {
  const [text, setText] = useState(() => planeToStr(plane));
  const fs = compact ? 10 : 11;

  // 外部改平面（如步进、换轴）→ 同步输入框；用户正在打字时不会触发（受控来自 props 变化）
  useEffect(() => { setText(planeToStr(plane)); }, [plane.A, plane.B, plane.C, plane.D]);

  const submit = () => {
    const p = parsePlane(text);
    if (!p) {
      // 解析不了就退回显示原平面：不静默改成"0 = 0"的假平面（那会切不出任何东西）
      setText(planeToStr(plane));
      return;
    }
    onPlaneChange(p);
    onSubmitPlane?.(p);
  };

  const move = (dir: 1 | -1) => {
    const next = { ...plane, D: plane.D + dir * step };
    onPlaneChange(next);
    onStepMove?.(next);
  };

  const inputStyle: React.CSSProperties = {
    flex: 1, minWidth: 0, padding: "2px 4px", fontSize: fs,
    background: "var(--bg-input)", border: "1px solid var(--border-glass)",
    color: "var(--text-primary)", borderRadius: 4, fontFamily: "Consolas,monospace",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
        <span style={{ fontSize: fs, color: "var(--text-secondary)", flexShrink: 0 }}>平面</span>
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={submit}
          onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
          placeholder="X + Y + Z = 0"
          title="切割平面方程 AX + BY + CZ = D，例如 Z = 12.5 或 X + Y = 0"
          style={inputStyle}
        />
      </div>
      {extra}

      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
        <span style={{ fontSize: fs, color: "var(--text-secondary)", flexShrink: 0 }}>步长</span>
        <button
          className="btn btn-ghost btn-xs"
          onClick={() => onStepChange(halveStep(step))}
          style={{ fontSize: fs }}
          title="步长减半"
        >◀</button>
        <input
          type="text"
          value={String(step)}
          onChange={(e) => { const v = parseFloat(e.target.value); if (isFinite(v) && v > 0) onStepChange(v); }}
          title="沿法向每次移动的 D 增量"
          style={{ width: 56, padding: "2px 4px", fontSize: fs, textAlign: "center", background: "var(--bg-input)", border: "1px solid var(--border-glass)", color: "var(--text-primary)", borderRadius: 4 }}
        />
        <button
          className="btn btn-ghost btn-xs"
          onClick={() => onStepChange(doubleStep(step))}
          style={{ fontSize: fs }}
          title="步长加倍"
        >▶</button>
        {showStepButtons && (
          <>
            <button className="btn btn-ghost btn-xs" onClick={() => move(-1)} style={{ fontSize: fs }} title={stepTitle ?? "沿法向后退一个步长"}>◀ 退</button>
            <button className="btn btn-ghost btn-xs" onClick={() => move(1)} style={{ fontSize: fs }} title={stepTitle ?? "沿法向前进一个步长"}>进 ▶</button>
          </>
        )}
      </div>
    </div>
  );
}
