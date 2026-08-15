/**
 * FMeshForm — 网格计数（FMESH）结构化表单（契约 meshtal-visualization.md §4.7.1 / §5.3 / §12 F5.1）
 *
 * ⚠️ UI 现状（2026-08-14 用户决定）：TMESH 计数卡「创建/选择」入口已隐藏，kind 下拉只留 FMESH；
 *    导入的 TMESH 行显示只读徽标（数据原样保留，round-trip 保真），代码路径保留待后续启用。
 *
 * ✅ FMESH 表单改进（2026-08-14 PM 指令）：
 * - GEOM 改四选下拉（XYZ 默认/REC 直角、CYL/RZT 圆柱），value 存单 token（GEOM=XYZ 连写）；
 * - OUT 改九选下拉（COL 默认/CF/COLSC/CFSC/IJ/IK/JK/NONE/XDMF），附说明（CF 体积、NONE 不打印、XDMF 供 ParaView）；
 * - AXS/VEC 仅在圆柱系（CYL/RZT）显示，并校验两向量不平行；TR 可选变换编号；MAT 帮助文案（0=粒子所在格材料默认）；
 * - 每行提交/生成前友好提示校验（validateFmeshRow 纯函数）。
 *
 * 只做卡体结构化编辑：网格定义（每输入框幽灵文字注明关键字作用）+ 卡体预览 + 空态提示。
 * 「3D 体积可视化」启动入口已统一到「输出」标签页（开窗逻辑见 openVolume3DWindow.ts 共享模块）。
 */
import React, { useEffect, useMemo, useState } from "react";
import {
  emptyFmeshRow, fmeshToCardText, FMESH_PLACEHOLDERS,
  FMESH_GEOM_OPTIONS, FMESH_OUT_OPTIONS, isCylGeom, validateFmeshRow,
  fmeshTemplates, FMESH_ROW_LAYOUT,
  type FmeshKind, type FmeshRow, type FmeshTemplate, type FmeshValidationIssue,
} from "./fmeshState";
import { computeSurfacesAABB, aabbToFmeshValues } from "./surfacesAABB";
import { useDeck } from "../utils/DeckContext";

interface RowWithId extends FmeshRow {
  _uid: number;
}

const FMESH_FIELD_LABELS: { key: keyof FmeshRow; label: string; placeholder: string; width?: number; hint?: string }[] = [
  { key: "origin", label: "ORIGIN", placeholder: FMESH_PLACEHOLDERS.origin, width: 200 },
  { key: "imesh", label: "IMESH", placeholder: FMESH_PLACEHOLDERS.imesh, width: 200 },
  { key: "iints", label: "IINTS", placeholder: FMESH_PLACEHOLDERS.iints, width: 90 },
  { key: "jmesh", label: "JMESH", placeholder: FMESH_PLACEHOLDERS.jmesh, width: 200 },
  { key: "jints", label: "JINTS", placeholder: FMESH_PLACEHOLDERS.jints, width: 90 },
  { key: "kmesh", label: "KMESH", placeholder: FMESH_PLACEHOLDERS.kmesh, width: 200 },
  { key: "kints", label: "KINTS", placeholder: FMESH_PLACEHOLDERS.kints, width: 90 },
  { key: "emesh", label: "EMESH", placeholder: FMESH_PLACEHOLDERS.emesh, width: 200 },
  { key: "emints", label: "EMINTS", placeholder: FMESH_PLACEHOLDERS.emints, width: 90 },
  { key: "tmesh", label: "时间分箱（TMESH 关键字）", placeholder: FMESH_PLACEHOLDERS.tmesh, width: 200, hint: "这是 FMESH 卡的时间边界分箱关键字，不是 TMESH 计数卡" },
  { key: "tmints", label: "TMINTS（时间区间数）", placeholder: FMESH_PLACEHOLDERS.tmints, width: 90 },
  { key: "mat", label: "MAT", placeholder: FMESH_PLACEHOLDERS.mat, width: 140, hint: "0=粒子所在格材料（默认）；非 0=指定材料号" },
  { key: "axs", label: "AXS", placeholder: FMESH_PLACEHOLDERS.axs, width: 130 },
  { key: "vec", label: "VEC", placeholder: FMESH_PLACEHOLDERS.vec, width: 130 },
  { key: "tr", label: "TR", placeholder: FMESH_PLACEHOLDERS.tr, width: 60 },
  { key: "factor", label: "FACTOR", placeholder: FMESH_PLACEHOLDERS.factor, width: 70, hint: "每网格单元乘一个系数（正整数，默认 1）" },
];

/**
 * kind 控件降级（2026-08-14 用户决定：TMESH 计数卡入口 UI 隐藏）：
 * - FMESH → 可编辑下拉（select，唯一选项）；
 * - TMESH（仅来自 INP 导入/后端 parse）→ 只读徽标（badge），不可编辑不可切，
 *   数据原样保留（序列化路径未删，未来启用 UI 直接放开即可）。
 * geom=cyl 的 TMESH 行本就不进入体积可视化，note 一并说明。
 */
export function fmeshKindControl(
  kind: FmeshKind,
  geom?: string,
): { control: "select" | "badge"; note: string } {
  if (kind === "TMESH") {
    return {
      control: "badge",
      note: isCylGeom(geom || "")
        ? "TMESH 计数卡入口已隐藏（后续版本启用）；本行数据原样保留，cyl 网格不进入体积可视化"
        : "TMESH 计数卡入口已隐藏（后续版本启用）；本行数据原样保留",
    };
  }
  return { control: "select", note: "" };
}

export interface FMeshFormProps {
  /** FMESH/TMESH 行（受控自 deck.tally.fmesh） */
  value: FmeshRow[];
  /** 更新 rows（写回 deck.tally.fmesh） */
  onChange: (rows: FmeshRow[]) => void;
}

export default function FMeshForm({ value, onChange }: FMeshFormProps) {
  const [rows, setRows] = useState<RowWithId[]>(() =>
    (value || []).map((r, i) => ({ ...r, _uid: i + 1 })),
  );
  // 始终显示完整字段表单（2026-08-15 PM 指令：去掉简单/高级模式切换；布局按 FMESH_ROW_LAYOUT 9 行分组）
  const { deck } = useDeck();

  // 外部 value 变化（导入/文本模式回填）→ 同步本地 rows
  useEffect(() => {
    setRows((prev) => {
      const sig = JSON.stringify(value || []);
      const cur = JSON.stringify(prev.map((r) => {
        const { _uid, ...rest } = r;
        return rest;
      }));
      if (sig === cur) return prev;
      return (value || []).map((r, i) => ({ ...r, _uid: (prev[i]?._uid) ?? (Date.now() + i) }));
    });
  }, [value]);

  const pushRows = (next: RowWithId[]) => {
    setRows(next);
    onChange(next.map((r) => {
      const { _uid, ...rest } = r;
      return rest;
    }));
  };

  const updateRow = (uid: number, field: keyof FmeshRow, val: string) => {
    pushRows(rows.map((r) => (r._uid === uid ? { ...r, [field]: val } : r)));
  };
  const addRow = () => {
    pushRows([...rows, { ...emptyFmeshRow(), particle: "N", _uid: Date.now() }]);
  };
  const delRow = (uid: number) => {
    pushRows(rows.filter((r) => r._uid !== uid));
  };

  // 通用模板一键填充：把模板网格值并入当前行（走受控状态更新，其余字段保留）
  const applyTemplate = (uid: number, tpl: FmeshTemplate) => {
    pushRows(rows.map((r) => (r._uid === uid ? { ...tpl.apply(r), _uid: r._uid } : r)));
  };

  // ⚡ 按几何自动填充：解析曲面卡算模型 AABB → 一键填入 ORIGIN + IMESH/JMESH/KMESH（网格覆盖模型）
  const autoFillByGeometry = (uid: number) => {
    const aabb = computeSurfacesAABB(deck.surfaces || "", deck.tr_cards || "");
    if (!aabb) {
      alert("无法从曲面卡解析几何包围盒。请先在「几何」标签页填写曲面卡（平面/球/圆柱等可解类型，TR 变换需对应 TR 卡），或改用「通用模板一键填充」。");
      return;
    }
    const vals = aabbToFmeshValues(aabb);
    pushRows(rows.map((r) => (r._uid === uid ? { ...r, ...vals } : r)));
  };

  // 每行校验（TMESH 只读导入行数据原样保留，不做校验提示）
  const rowIssues = useMemo(() => {
    const m = new Map<number, FmeshValidationIssue[]>();
    for (const r of rows) {
      if (r.kind === "TMESH") continue;
      m.set(r._uid, validateFmeshRow(r));
    }
    return m;
  }, [rows]);

  // 导出卡体（供调试/生成；生成载荷由 buildFmeshPayload 由父层调用）
  const cardText = useMemo(() => fmeshToCardText(rows), [rows]);

  /* ── 渲染（传行对象，免重复 rows.find） ── */
  const input = (r: RowWithId, field: keyof FmeshRow) => {
    const spec = FMESH_FIELD_LABELS.find((f) => f.key === field);
    return (
      <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: 10 }}>
        <span style={{ color: "var(--text-tertiary)" }}>{spec?.label}</span>
        <input
          className="form-input"
          value={(r[field] as string) || ""}
          onChange={(e) => updateRow(r._uid, field, e.target.value)}
          placeholder={spec?.placeholder}
          title={spec?.placeholder}
          style={{ height: 26, fontSize: 11, width: spec?.width || 120 }}
        />
        {spec?.hint && (
          <span style={{ color: "var(--text-tertiary)", fontSize: 9, maxWidth: spec.width || 120, lineHeight: 1.35 }}>
            {spec.hint}
          </span>
        )}
      </label>
    );
  };

  const particleSelect = (r: RowWithId) => (
    <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: 10 }}>
      <span style={{ color: "var(--text-tertiary)" }}>粒子设计符</span>
      <select
        className="form-select"
        value={r.particle}
        onChange={(e) => updateRow(r._uid, "particle", e.target.value)}
        style={{ height: 26, fontSize: 11, width: 70 }}
        title="粒子设计符：N/P/E"
      >
        <option value="N">N（中子）</option>
        <option value="P">P（光子）</option>
        <option value="E">E（电子）</option>
      </select>
    </label>
  );

  const geomSelect = (r: RowWithId) => (
    <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: 10 }}>
      <span style={{ color: "var(--text-tertiary)" }}>GEOM</span>
      <select
        className="form-select"
        value={r.geom || "XYZ"}
        onChange={(e) => updateRow(r._uid, "geom", e.target.value)}
        style={{ height: 26, fontSize: 11, width: 130 }}
        title={FMESH_PLACEHOLDERS.geom}
      >
        {FMESH_GEOM_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <span style={{ color: "var(--text-tertiary)", fontSize: 9, maxWidth: 130, lineHeight: 1.35 }}>
        {isCylGeom(r.geom) ? "圆柱系：AXS/VEC 生效，KMESH 末值=1" : "直角系"}
      </span>
    </label>
  );

  const outSelect = (r: RowWithId) => {
    const cur = FMESH_OUT_OPTIONS.find((o) => o.value === (r.out || "COL"))?.hint;
    return (
      <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: 10 }}>
        <span style={{ color: "var(--text-tertiary)" }}>OUT</span>
        <select
          className="form-select"
          value={r.out || "COL"}
          onChange={(e) => updateRow(r._uid, "out", e.target.value)}
          style={{ height: 26, fontSize: 11, width: 100 }}
          title={FMESH_PLACEHOLDERS.out}
        >
          {FMESH_OUT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <span style={{ color: "var(--text-tertiary)", fontSize: 9, maxWidth: 170, lineHeight: 1.35 }}>
          {cur || "OUT 控制 meshtal 输出：NONE 不打印；XDMF 供 ParaView"}
        </span>
      </label>
    );
  };

  const issuesBlock = (uid: number) => {
    const issues = rowIssues.get(uid);
    if (!issues || issues.length === 0) return null;
    return (
      <div style={{ width: "100%", marginTop: 6, display: "flex", flexDirection: "column", gap: 3 }}>
        {issues.map((iss, idx) => (
          <div key={idx} style={{ fontSize: 10, lineHeight: 1.4, color: iss.level === "error" ? "#f87171" : "#fbbf24" }}>
            {iss.level === "error" ? "错误" : "警告"}·{iss.field}：{iss.message}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="glass-card" style={{ marginTop: 16 }}>
      <div className="card-header">
        <span className="card-title">网格计数（FMESH）</span>
        <button className="btn btn-success btn-sm" onClick={addRow}>+ 添加网格计数</button>
      </div>

      {/* FMESH 结构化表单（F5.1 幽灵文字；TMESH 计数卡入口 UI 隐藏，导入行只读徽标保留） */}
      {rows.length === 0 ? (
        <div style={{ padding: "8px 14px", fontSize: 11, color: "var(--text-tertiary)" }}>
          尚无网格计数卡。点「+ 添加网格计数」创建 FMESH 卡，或从 INP 导入自动识别。
        </div>
      ) : (
        rows.map((r) => {
          const kindCtrl = fmeshKindControl(r.kind, r.geom);
          const isSelectRow = kindCtrl.control === "select";
          return (
          <div key={r._uid} style={{ border: "1px solid rgba(255,255,255,0.06)", borderRadius: 6, padding: 8, margin: "8px 0" }}>
            {/* 头行：类型 + 编号 + 删除（始终可见） */}
            <div style={{ display: "flex", gap: 8, alignItems: "flex-end", marginBottom: 6, flexWrap: "wrap" }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: 10 }}>
                <span style={{ color: "var(--text-tertiary)" }}>类型</span>
                {kindCtrl.control === "badge" ? (
                  <span
                    title={kindCtrl.note}
                    style={{ height: 26, lineHeight: "26px", padding: "0 10px", borderRadius: 4, background: "rgba(255,200,0,0.10)", border: "1px solid rgba(255,200,0,0.28)", color: "var(--text-tertiary)", fontSize: 11, whiteSpace: "nowrap" }}
                  >TMESH</span>
                ) : (
                  <select
                    className="form-select"
                    value={r.kind}
                    onChange={(e) => updateRow(r._uid, "kind", e.target.value)}
                    style={{ height: 26, fontSize: 11, width: 90 }}
                  >
                    <option value="FMESH">FMESH</option>
                  </select>
                )}
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: 10 }}>
                <span style={{ color: "var(--text-tertiary)" }}>编号</span>
                <input className="form-input" value={r.number} onChange={(e) => updateRow(r._uid, "number", e.target.value)} placeholder="如 4" style={{ height: 26, fontSize: 11, width: 60 }} />
              </label>
              <button className="btn btn-danger btn-xs" onClick={() => delRow(r._uid)} style={{ marginLeft: "auto", alignSelf: "flex-end" }}>x</button>
            </div>

            {/* 三步上手引导（FMESH 可编辑行） */}
            {isSelectRow && (
              <div style={{ marginBottom: 6, fontSize: 11, color: "var(--accent)" }}>
                ① 选粒子　② 点自动填充　③ 解析看 3D 结果
              </div>
            )}

            {/* 字段区：按 MCNP 卡结构 9 行分组（FMESH_ROW_LAYOUT：卡头粒子/GEOM/OUT → ORIGIN → 各轴 IMESH/IINTS → 能量/时间 → MAT/FACTOR/TR → AXS/VEC 圆柱系才显示） */}
            {FMESH_ROW_LAYOUT.map((rowFields) => {
              const shown = rowFields.filter((f) => (f === "axs" || f === "vec") ? isCylGeom(r.geom) : true);
              if (shown.length === 0) return null;
              return (
                <div key={rowFields[0]} style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
                  {shown.map((f) => {
                    if (f === "particle") return particleSelect(r);
                    if (f === "geom") return geomSelect(r);
                    if (f === "out") return outSelect(r);
                    return input(r, f);
                  })}
                </div>
              );
            })}

            {/* 粒子说明（每个网格计数一个粒子） */}
            {isSelectRow && (
              <div style={{ marginTop: 6, fontSize: 9, color: "var(--text-tertiary)" }}>
                每个网格计数一个粒子（N/P/E）；要多种粒子就加多行
              </div>
            )}

            {/* 一键填充按钮（⚡ 按几何自动填充 + 通用模板） */}
            {isSelectRow && (
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginTop: 8, fontSize: 10 }}>
                <button
                  type="button"
                  className="btn btn-success btn-xs"
                  onClick={() => autoFillByGeometry(r._uid)}
                  title="解析曲面卡算模型 x/y/z 包围盒，自动填 ORIGIN + IMESH/JMESH/KMESH（网格覆盖模型）"
                >
                  ⚡ 按几何自动填充
                </button>
                <span style={{ color: "var(--text-tertiary)" }}>通用模板一键填充</span>
                <div className="btn-group">
                  {fmeshTemplates.map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      className="btn btn-ghost btn-xs"
                      title={`${t.label}：${t.hint}`}
                      onClick={() => applyTemplate(r._uid, t)}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
                <span style={{ color: "var(--text-tertiary)", fontSize: 9, lineHeight: 1.35 }}>
                  先粗网格看分布，再按需加密 · 只覆盖网格字段，其余已填内容保留
                </span>
              </div>
            )}

            {kindCtrl.control === "badge" && kindCtrl.note && (
              <div style={{ width: "100%", fontSize: 9, color: "var(--text-tertiary)", marginTop: 6 }}>
                {kindCtrl.note}
              </div>
            )}
            {issuesBlock(r._uid)}
          </div>
          );
        })
      )}

      {cardText && (
        <details style={{ fontSize: 10, color: "var(--text-tertiary)", padding: "4px 14px" }}>
          <summary style={{ cursor: "pointer" }}>当前卡体预览（点击展开）</summary>
          <pre style={{ background: "rgba(0,0,0,0.3)", padding: 8, borderRadius: 4, fontFamily: "Consolas,monospace", fontSize: 11, whiteSpace: "pre-wrap" }}>{cardText}</pre>
        </details>
      )}
    </div>
  );
}
