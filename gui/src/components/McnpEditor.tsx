/**
 * MCNP 卡片编辑器 — 语法高亮 + 幽灵提示 + 自动补全
 * 采用 textarea 叠加 <pre> 方案，光标位置由浏览器原生管理
 */

import React, { useRef, useState, useCallback, useEffect, useMemo } from "react";

const SURFACE_DESCS: Record<string, string> = {
  "P": "一般平面", "PX": "X垂面", "PY": "Y垂面", "PZ": "Z垂面",
  "SO": "球心在原点的球", "S": "一般球", "SX": "X轴球", "SY": "Y轴球", "SZ": "Z轴球",
  "CX": "X轴圆柱", "CY": "Y轴圆柱", "CZ": "Z轴圆柱",
  "C/X": "平行X轴圆柱", "C/Y": "平行Y轴圆柱", "C/Z": "平行Z轴圆柱",
  "KX": "X轴圆锥", "KY": "Y轴圆锥", "KZ": "Z轴圆锥",
  "K/X": "平行X轴锥", "K/Y": "平行Y轴锥", "K/Z": "平行Z轴锥",
  "SQ": "轴平行二次曲面", "GQ": "一般二次曲面",
  "TX": "X轴环面", "TY": "Y轴环面", "TZ": "Z轴环面",
  "X": "X轴旋转体", "Y": "Y轴旋转体", "Z": "Z轴旋转体",
  "RPP": "长方体", "SPH": "球体", "RCC": "正圆柱",
  "TRC": "截头圆锥", "REC": "椭圆柱", "ELL": "椭球",
  "WED": "楔形", "BOX": "盒子", "ARB": "任意多面体",
  "RHP": "正六棱柱", "HEX": "正六棱柱",
};

const SURFACE_TYPES = [
  "P", "PX", "PY", "PZ",
  "SO", "S", "SX", "SY", "SZ",
  "CX", "CY", "CZ", "C/X", "C/Y", "C/Z",
  "KX", "KY", "KZ", "K/X", "K/Y", "K/Z",
  "SQ", "GQ",
  "TX", "TY", "TZ",
  "X", "Y", "Z",
  "RPP", "SPH", "RCC", "TRC", "REC", "ELL", "WED", "BOX", "ARB", "RHP", "HEX",
];

const GHOST_HINTS: Record<string, string> = {
  "P": "A B C D", "PX": "D", "PY": "D", "PZ": "D",
  "SO": "R", "S": "x0 y0 z0 R", "SX": "x0 R", "SY": "y0 R", "SZ": "z0 R",
  "CX": "R", "CY": "R", "CZ": "R",
  "C/X": "y0 z0 R", "C/Y": "x0 z0 R", "C/Z": "x0 y0 R",
  "KX": "x0 t2 ±1", "KY": "y0 t2 ±1", "KZ": "z0 t2 ±1",
  "K/X": "x0 y0 z0 t2 ±1", "K/Y": "x0 y0 z0 t2 ±1", "K/Z": "x0 y0 z0 t2 ±1",
  "SQ": "x0 y0 z0 A B C D E F G", "GQ": "A B C D E F G H J K",
  "TX": "x0 y0 z0 A B C", "TY": "x0 y0 z0 A B C", "TZ": "x0 y0 z0 A B C",
  "RPP": "Xmin Xmax Ymin Ymax Zmin Zmax",
  "SPH": "Vx Vy Vz R", "RCC": "Vx Vy Vz Hx Hy Hz R",
  "TRC": "Vx Vy Vz Hx Hy Hz R1 R2",
  "REC": "Vx Vy Vz Hx Hy Hz V1x V1y V1z V2x V2y V2z",
  "ELL": "V1x V1y V1z V2x V2y V2z Rm",
  "WED": "Vx Vy Vz V1 V2 V3",
  "BOX": "Vx Vy Vz A1 A2 A3",
  "ARB": "8顶点 6面定义",
  "RHP": "Vx Vy Vz Hx Hy Hz R1 R2 R3 S1 S2 S3 T1 T2 T3",
  "HEX": "Vx Vy Vz Hx Hy Hz R1 R2 R3 S1 S2 S3 T1 T2 T3",
};

interface Props {
  id?: string;
  value?: string;
  onChange?: (val: string) => void;
  placeholder?: string;
  minHeight?: number;
  mode?: "surface" | "tr";
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function highlightLine(line: string, mode: "surface" | "tr"): string {
  if (!line) return "";
  const trimmed = line.trim();
  if (/^[Cc]\s/.test(trimmed) || /^\$/.test(trimmed))
    return '<span style="color:#6b7280;font-style:italic">' + escapeHtml(line) + '</span>';

  // Token-based coloring: split into words, assign per-role
  var tokens = trimmed.split(/\s+/);
  var ti = 0;
  var inComment = false;
  var out = [];
  for (var ci = 0; ci < tokens.length; ci++) {
    var tok = tokens[ci];
    if (!tok) continue;
    if (inComment) { out.push('<span style="color:#6b7280;font-style:italic">' + escapeHtml(tok) + '</span>'); continue; }
    if (tok.startsWith("$")) { inComment = true; out.push('<span style="color:#6b7280;font-style:italic">' + escapeHtml(tok) + '</span>'); continue; }

    if (mode === "tr") {
      // TR mode: TRn|*TRn purple, Tx Ty Tz amber, rest green
      if (/^\*?TR\d+$/i.test(tok)) { out.push('<span style="color:#0891b2;font-weight:bold">' + escapeHtml(tok) + '</span>'); ti++; continue; }
      if (/^[+-]?\d/.test(tok)) {
        if (ti < 4) out.push('<span style="color:#d97706">' + escapeHtml(tok) + '</span>');
        else out.push('<span style="color:#059669">' + escapeHtml(tok) + '</span>');
        ti++; continue;
      }
      out.push(escapeHtml(tok)); ti++; continue;
    }

    // Surface mode
    if (SURFACE_TYPES.includes(tok.toUpperCase())) { out.push('<span style="color:#7c3aed;font-weight:bold">' + escapeHtml(tok) + '</span>'); ti++; continue; }
    if (/^\*?TR\d+$/i.test(tok)) { out.push('<span style="color:#0891b2;font-weight:bold">' + escapeHtml(tok) + '</span>'); ti++; continue; }
    if (/^[+-]?\d+\.?\d*(?:[eE][+-]?\d+)?$/.test(tok) || tok === "±1") {
      if (ti === 0) out.push('<span style="color:#e65100">' + escapeHtml(tok) + '</span>');
      else if (ti === 1) out.push('<span style="color:#0891b2;font-weight:bold">' + escapeHtml(tok) + '</span>');
      else out.push('<span style="color:#059669">' + escapeHtml(tok) + '</span>');
      ti++; continue;
    }
    out.push(escapeHtml(tok)); ti++;
  }
  return out.join(" ");
}

function ghostForLine(line: string): string | null {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith("C") || trimmed.startsWith("c") || trimmed.startsWith("$")) return null;

  const upper = trimmed.toUpperCase();
  // TR 卡幽灵提示
  if (/^\*?TR\d+/i.test(upper)) {
    const trTokens = upper.split(/\s+/).filter(t => /^[+\-]?\d/.test(t) || t.startsWith("TR"));
    const trParamCount = trTokens.filter(t => /^[+\-]?\d/.test(t)).length;
    const trHint = "Tx Ty Tz B1 B2 B3 B4 B5 B6 B7 B8 B9".split(" ");
    if (trParamCount >= trHint.length) return "$ 变换矩阵";
    return trHint.slice(trParamCount).join(" ");
  }
  // 提取曲面类型：跳过行首曲面号（数字+可选 * 前缀），取第一个字母词
  const tokens = upper.split(/\s+/);
  let typeToken = "";
  let paramStart = 0;
  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i];
    if (t === "*TR" || t.startsWith("TR")) {
      typeToken = "TR";
      paramStart = i + 1;
      break;
    }
    if (/^[\d*]+\d*$/.test(t)) continue; // 曲面号，跳过
    if (GHOST_HINTS[t]) {
      typeToken = t;
      paramStart = i + 1;
      break;
    }
  }
  if (!typeToken) return null;

  const hint = GHOST_HINTS[typeToken];
  if (!hint) return null;

  // 已输入的参数数（跳过曲面号后的数字/符号 token）
  const paramTokens = tokens.slice(paramStart).filter(t => /^[+\-]?\d/.test(t) || t === "±1");
  const paramCount = paramTokens.length;

  // 预期参数数
  const expectedParts = hint.split(/\s+/).filter(Boolean);
  if (paramCount >= expectedParts.length) return null;

  // 全部参数都输入了 → 显示 $曲面描述
  if (paramCount >= expectedParts.length) {
    const desc = SURFACE_DESCS[typeToken];
    return desc ? ("$ " + desc) : null;
  }
  // 返回剩余参数提示
  return expectedParts.slice(paramCount).join(" ");
}

function getCompletions(mode: "surface" | "tr"): Array<{ word: string; desc: string }> {
  if (mode === "tr") return [
    { word: "TR", desc: "平移+旋转" },
    { word: "*TR", desc: "组合变换" },
  ];
  return SURFACE_TYPES.map((t) => ({ word: t, desc: SURFACE_DESCS[t] || GHOST_HINTS[t] || "" }));
}

export default function McnpEditor({ id, value = "", onChange, placeholder = "", minHeight = 180, mode = "surface" }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const highlightRef = useRef<HTMLPreElement>(null);
  const ghostRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const [showDropdown, setShowDropdown] = useState(false);
  const [dropdownItems, setDropdownItems] = useState<Array<{ word: string; desc: string }>>([]);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0 });
  const [selectedIdx, setSelectedIdx] = useState(0);

  const words = useMemo(() => getCompletions(mode), [mode]);

  // 幽灵提示渲染
  const renderGhost = useCallback(() => {
    if (!value) return null;
    const lines = value.split("\n");
    const last = lines[lines.length - 1];
    const g = ghostForLine(last);
    return g ? <span style={{ color: "var(--text-tertiary)", fontStyle: "italic" }}> {g}</span> : null;
  }, [value]);

  // 检测补全
  const checkCompletion = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    const pos = ta.selectionStart;
    const text = ta.value;
    const beforePos = text.substring(0, pos);
    const lastWord = beforePos.match(/[\w/*]+$/)?.[0] || "";

    if (lastWord.length >= 1 && !/^\d+$/.test(lastWord)) {
      const matched = words.filter((w) => w.word.toUpperCase().startsWith(lastWord.toUpperCase()));
      if (matched.length > 0) {
        // 计算 textarea 光标像素位置
        const val = ta.value;
        const before = val.substring(0, pos);
        const lines = before.split("\n");
        const lineNum = lines.length - 1;
        const colNum = lines[lineNum].length;
        const lineHeight = 19.2; // ~1.6em at 12px
        const charWidth = 7.2;  // ~monospace 7.2px
        setDropdownItems(matched.slice(0, 10));
        const scrollTop = ta.scrollTop || 0;
        setDropdownPos({ top: (lineNum) * lineHeight + 10 - scrollTop, left: colNum * charWidth + 14 });
        setSelectedIdx(0);
        setShowDropdown(true);
        return;
      }
    }
    setShowDropdown(false);
  }, [words]);

  const acceptCompletion = useCallback((word: string) => {
    const ta = textareaRef.current;
    if (!ta) return;
    const pos = ta.selectionStart;
    const text = ta.value;
    const beforePos = text.substring(0, pos);
    const lastWord = beforePos.match(/[\w/*]+$/)?.[0] || "";
    const newText = text.substring(0, pos - lastWord.length) + word + text.substring(pos);
    ta.focus();
    const newPos = pos - lastWord.length + word.length;
    ta.setSelectionRange(newPos, newPos);
    // 触发 React onChange
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value")?.set;
    nativeInputValueSetter?.call(ta, newText);
    ta.dispatchEvent(new Event("input", { bubbles: true }));
    setShowDropdown(false);
  }, []);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange?.(e.target.value);
    checkCompletion();
  }, [onChange, checkCompletion]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (showDropdown) {
      if (e.key === "ArrowDown") { e.preventDefault(); setSelectedIdx(p => Math.min(p + 1, dropdownItems.length - 1)); return; }
      if (e.key === "ArrowUp") { e.preventDefault(); setSelectedIdx(p => Math.max(p - 1, 0)); return; }
      if (e.key === "Tab" || e.key === "Enter") { e.preventDefault(); acceptCompletion(dropdownItems[selectedIdx]?.word); return; }
      if (e.key === "Escape") { setShowDropdown(false); return; }
    }
    // Tab → 插空格
    if (e.key === "Tab") {
      e.preventDefault();
      const ta = textareaRef.current;
      if (!ta) return;
      const pos = ta.selectionStart;
      const text = ta.value;
      const newText = text.substring(0, pos) + "  " + text.substring(ta.selectionEnd);
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value")?.set;
      nativeInputValueSetter?.call(ta, newText);
      ta.setSelectionRange(pos + 2, pos + 2);
      ta.dispatchEvent(new Event("input", { bubbles: true }));
    }
  }, [showDropdown, dropdownItems, selectedIdx, acceptCompletion]);

  // 点击外部关闭下拉
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    if (showDropdown) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showDropdown]);

  // 构建高亮 HTML
  const highlightedHtml = useMemo(() => {
    if (!value) return "";
    return value.split("\n").map((line, i) => {
      const g = ghostForLine(line);
      const hl = highlightLine(line, mode);
      return `<div style="min-height:1.6em">${hl}${g ? `<span style="color:var(--text-tertiary);font-style:italic"> ${escapeHtml(g)}</span>` : ""}</div>`;
    }).join("");
  }, [value, mode]);

  return (
    <div className="mcnp-editor-wrapper" style={{ position: "relative", minHeight, background: "var(--editor-bg)", borderRadius: 6, border: "1px solid var(--border-glass)" }}>
      {/* 高亮层 */}
      <pre
        ref={highlightRef}
        className="mcnp-highlight"
        style={{
          position: "absolute", inset: 0, margin: 0, padding: "10px 14px",
          fontFamily: "Consolas, monospace", fontSize: 12, lineHeight: 1.6,
          whiteSpace: "pre-wrap", wordBreak: "break-all", overflow: "hidden",
          color: "var(--text-primary)", pointerEvents: "none", zIndex: 1,
          border: "none", background: "transparent",
          minHeight,
        }}
        dangerouslySetInnerHTML={{ __html: highlightedHtml || `<span style="color:var(--text-tertiary);font-style:italic">${escapeHtml(placeholder)}</span>` }}
      />

      {/* 输入层 — textarea 透明文字 */}
      <textarea
        ref={textareaRef}
        id={id}
        className="mcnp-textarea"
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        onScroll={() => {
          if (highlightRef.current && textareaRef.current) {
            highlightRef.current.scrollTop = textareaRef.current.scrollTop;
            highlightRef.current.scrollLeft = textareaRef.current.scrollLeft;
          }
        }}
        style={{
          position: "relative", zIndex: 2,
          width: "100%", minHeight,
          padding: "10px 14px",
          fontFamily: "Consolas, monospace", fontSize: 12, lineHeight: 1.6,
          whiteSpace: "pre-wrap", wordBreak: "break-all",
          color: "transparent", caretColor: "var(--text-primary)",
          background: "transparent", border: "none", outline: "none",
          resize: "vertical", overflow: "auto",
        }}
      />

      {/* 自动补全下拉 */}
      {showDropdown && dropdownItems.length > 0 && (
        <div
          ref={dropdownRef}
          style={{
            position: "absolute", top: dropdownPos.top, left: dropdownPos.left,
            zIndex: 100, background: "var(--autocomplete-bg)",
            border: "1px solid var(--border-glass)", borderRadius: 6,
            boxShadow: "0 4px 16px rgba(0,0,0,0.3)",
            minWidth: 180, maxHeight: 220, overflow: "auto",
          }}
        >
          {dropdownItems.map((item, idx) => (
            <div
              key={item.word}
              style={{
                padding: "4px 10px", cursor: "pointer", fontSize: 12,
                background: idx === selectedIdx ? "rgba(255,0,128,0.2)" : "transparent",
                color: idx === selectedIdx ? "var(--text-primary)" : "var(--text-secondary)",
              }}
              onClick={() => acceptCompletion(item.word)}
              onMouseEnter={() => setSelectedIdx(idx)}
            >
              <span style={{ fontWeight: 600 }}>{item.word}</span>
              {item.desc && <span style={{ color: "var(--text-tertiary)", marginLeft: 8, fontSize: 11 }}>{item.desc}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
