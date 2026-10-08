/**
 * MCNP 卡片编辑器。
 *
 * Monaco 使用单一 TextModel 同时负责文本、光标、选区和复制。
 * 曲面/TR 提示通过 inline completion（ghost text）绘制，不再叠加第二份正文。
 */
import React, { useEffect, useRef } from "react";
import Editor, { type Monaco, type OnMount } from "@monaco-editor/react";
import type { IDisposable, Position, editor } from "monaco-editor";

const languageId = (mode: "surface" | "tr") => `mcnp-${mode}-card`;

const SURFACE_DESCS: Record<string, string> = {
  P: "一般平面", PX: "X垂面", PY: "Y垂面", PZ: "Z垂面",
  SO: "球心在原点的球", S: "一般球", SX: "X轴球", SY: "Y轴球", SZ: "Z轴球",
  CX: "X轴圆柱", CY: "Y轴圆柱", CZ: "Z轴圆柱",
  "C/X": "平行X轴圆柱", "C/Y": "平行Y轴圆柱", "C/Z": "平行Z轴圆柱",
  KX: "X轴圆锥", KY: "Y轴圆锥", KZ: "Z轴圆锥",
  "K/X": "平行X轴锥", "K/Y": "平行Y轴锥", "K/Z": "平行Z轴锥",
  SQ: "轴平行二次曲面", GQ: "一般二次曲面",
  TX: "X轴环面", TY: "Y轴环面", TZ: "Z轴环面",
  X: "X轴旋转体", Y: "Y轴旋转体", Z: "Z轴旋转体",
  RPP: "长方体", SPH: "球体", RCC: "正圆柱", TRC: "截头圆锥",
  REC: "椭圆柱", ELL: "椭球", WED: "楔形", BOX: "盒子", ARB: "任意多面体",
  RHP: "正六棱柱", HEX: "正六棱柱",
};

const SURFACE_TYPES = Object.keys(SURFACE_DESCS);

const GHOST_HINTS: Record<string, string> = {
  P: "A B C D", PX: "D", PY: "D", PZ: "D",
  SO: "R", S: "x0 y0 z0 R", SX: "x0 R", SY: "y0 R", SZ: "z0 R",
  CX: "R", CY: "R", CZ: "R",
  "C/X": "y0 z0 R", "C/Y": "x0 z0 R", "C/Z": "x0 y0 R",
  KX: "x0 t2 ±1", KY: "y0 t2 ±1", KZ: "z0 t2 ±1",
  "K/X": "x0 y0 z0 t2 ±1", "K/Y": "x0 y0 z0 t2 ±1", "K/Z": "x0 y0 z0 t2 ±1",
  SQ: "x0 y0 z0 A B C D E F G", GQ: "A B C D E F G H J K",
  TX: "x0 y0 z0 A B C", TY: "x0 y0 z0 A B C", TZ: "x0 y0 z0 A B C",
  RPP: "Xmin Xmax Ymin Ymax Zmin Zmax",
  SPH: "Vx Vy Vz R", RCC: "Vx Vy Vz Hx Hy Hz R",
  TRC: "Vx Vy Vz Hx Hy Hz R1 R2",
  REC: "Vx Vy Vz Hx Hy Hz V1x V1y V1z V2x V2y V2z",
  ELL: "V1x V1y V1z V2x V2y V2z Rm",
  WED: "Vx Vy Vz V1 V2 V3", BOX: "Vx Vy Vz A1 A2 A3",
  ARB: "8顶点 6面定义",
  RHP: "Vx Vy Vz Hx Hy Hz R1 R2 R3 S1 S2 S3 T1 T2 T3",
  HEX: "Vx Vy Vz Hx Hy Hz R1 R2 R3 S1 S2 S3 T1 T2 T3",
};

let registered = false;

function isNumberToken(token: string): boolean {
  return /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(token);
}

function ghostForLine(line: string, mode: "surface" | "tr"): string | null {
  const trimmed = line.trim();
  if (!trimmed || /^[Cc]\s/.test(trimmed) || trimmed.startsWith("$")) return null;
  const body = trimmed.split("$", 1)[0].trim();
  if (mode === "tr") {
    if (!/^\*?TR\d+/i.test(body)) return null;
    const count = body.split(/\s+/).slice(1).filter(isNumberToken).length;
    const expected = "Tx Ty Tz B1 B2 B3 B4 B5 B6 B7 B8 B9".split(" ");
    return count >= expected.length ? null : expected.slice(count).join(" ");
  }

  const tokens = body.toUpperCase().split(/\s+/);
  let type = "";
  let start = -1;
  for (let i = 0; i < tokens.length; i++) {
    if (GHOST_HINTS[tokens[i]]) {
      type = tokens[i];
      start = i + 1;
      break;
    }
  }
  if (!type || start < 0) return null;
  const expected = GHOST_HINTS[type].split(/\s+/);
  const count = tokens.slice(start).filter((token) => isNumberToken(token) || token === "±1").length;
  if (count >= expected.length) return "$ " + SURFACE_DESCS[type];
  return expected.slice(count).join(" ");
}

function configureMonaco(monaco: Monaco): void {
  if (registered) return;
  registered = true;
  monaco.languages.register({ id: languageId("surface") });
  monaco.languages.register({ id: languageId("tr") });
  const surfaceType = new RegExp(`(?:${SURFACE_TYPES.map((t) => t.replace("/", "\\/")).join("|")})\\b`, "i");
  monaco.languages.setMonarchTokensProvider(languageId("surface"), {
    tokenizer: {
      root: [
        [/^\s*[Cc].*$/, "comment"],
        [/\$.*/, "comment"],
        [/^\s*[+*]?\d+\b/, "surface-id", "@surfaceAfterId"],
        [/[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?/, "number"],
      ],
      surfaceAfterId: [
        [/\s+/, ""],
        [/[+-]?\d+\b/, "tr-reference", "@surfaceBody"],
        [surfaceType, "type", "@surfaceBody"],
        [/./, "number", "@surfaceBody"],
      ],
      surfaceBody: [
        [/\$.*/, "comment"],
        [surfaceType, "type"],
        [/[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?/, "number"],
      ],
    },
  });
  monaco.languages.setMonarchTokensProvider(languageId("tr"), {
    tokenizer: {
      root: [
        [/^\s*[Cc].*$/, "comment"],
        [/\$.*/, "comment"],
        [/^\s*\*?TR\d+\b/i, "tr-id"],
        [/[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?/, "number"],
      ],
    },
  });
  monaco.editor.defineTheme("mcnp-card-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "", foreground: "F1F1F9" },
      { token: "comment", foreground: "9CA3AF", fontStyle: "italic" },
      { token: "keyword", foreground: "67E8F9", fontStyle: "bold" },
      { token: "surface-id", foreground: "FBBF24", fontStyle: "bold" },
      { token: "tr-id", foreground: "67E8F9", fontStyle: "bold" },
      { token: "tr-reference", foreground: "67E8F9", fontStyle: "bold" },
      { token: "type", foreground: "C4B5FD", fontStyle: "bold" },
      { token: "number", foreground: "6EE7B7" },
    ],
    colors: {
      "editor.background": "#FFFFFF00",
      "editor.foreground": "#F1F1F9",
      "editorLineNumber.foreground": "#9CA3AF",
      "editor.selectionBackground": "#2563EB55",
      "editor.inactiveSelectionBackground": "#2563EB33",
      "editorSuggestWidget.background": "#1A1A3E",
    },
  });
  monaco.editor.defineTheme("mcnp-card-light", {
    base: "vs",
    inherit: true,
    rules: [
      { token: "", foreground: "1F2937" },
      { token: "comment", foreground: "6B7280", fontStyle: "italic" },
      { token: "surface-id", foreground: "B45309", fontStyle: "bold" },
      { token: "tr-id", foreground: "0369A1", fontStyle: "bold" },
      { token: "tr-reference", foreground: "0369A1", fontStyle: "bold" },
      { token: "type", foreground: "6D28D9", fontStyle: "bold" },
      { token: "number", foreground: "047857" },
    ],
    colors: {
      "editor.background": "#FFFFFF00",
      "editor.foreground": "#1F2937",
      "editor.selectionBackground": "#2563EB55",
      "editor.inactiveSelectionBackground": "#2563EB33",
      "editorSuggestWidget.background": "#FFFFFF",
    },
  });
}

function currentMonacoTheme(): string {
  const theme = document.documentElement.getAttribute("data-theme");
  return theme === "dark" ? "mcnp-card-dark" : "mcnp-card-light";
}

interface Props {
  id?: string;
  value?: string;
  onChange?: (val: string) => void;
  placeholder?: string;
  minHeight?: number;
  mode?: "surface" | "tr";
}

export default function McnpEditor({
  id,
  value = "",
  onChange,
  placeholder = "",
  minHeight = 180,
  mode = "surface",
}: Props) {
  const currentLanguageId = languageId(mode);
  const modeRef = useRef(mode);
  modeRef.current = mode;
  const monacoRef = useRef<Monaco | null>(null);
  const completionDisposable = useRef<IDisposable | null>(null);
  const inlineDisposable = useRef<IDisposable | null>(null);

  const handleMount: OnMount = (editor, monaco) => {
    monacoRef.current = monaco;
    configureMonaco(monaco);
    monaco.editor.setModelLanguage(editor.getModel()!, currentLanguageId);
    monaco.editor.setTheme(currentMonacoTheme());

    completionDisposable.current?.dispose();
    completionDisposable.current = monaco.languages.registerCompletionItemProvider(currentLanguageId, {
      provideCompletionItems: (model: editor.ITextModel, position: Position) => {
        const line = model.getLineContent(position.lineNumber);
        const before = line.slice(0, position.column - 1);
        const partial = before.match(/[A-Za-z/*]+$/)?.[0] || "";
        const words = modeRef.current === "tr" ? ["TR", "*TR"] : SURFACE_TYPES;
        const suggestions = words
          .filter((word) => word.toUpperCase().startsWith(partial.toUpperCase()))
          .map((word) => ({
            label: word,
            kind: monaco.languages.CompletionItemKind.Keyword,
            insertText: word,
            detail: modeRef.current === "surface" ? SURFACE_DESCS[word] : "平移+旋转",
            range: new monaco.Range(position.lineNumber, position.column - partial.length, position.lineNumber, position.column),
          }));
        return { suggestions };
      },
    });

    inlineDisposable.current?.dispose();
    inlineDisposable.current = monaco.languages.registerInlineCompletionsProvider(currentLanguageId, {
      provideInlineCompletions: (model: editor.ITextModel, position: Position) => {
        const line = model.getLineContent(position.lineNumber);
        if (position.column - 1 !== line.length) return { items: [] };
        const text = ghostForLine(line, modeRef.current);
        if (!text) return { items: [] };
        return {
          items: [{
            insertText: text,
            range: new monaco.Range(position.lineNumber, position.column, position.lineNumber, position.column),
          }],
        };
      },
      freeInlineCompletions: () => undefined,
    });
  };

  useEffect(() => () => {
    completionDisposable.current?.dispose();
    inlineDisposable.current?.dispose();
  }, []);

  useEffect(() => {
    const observer = new MutationObserver(() => {
      if (monacoRef.current) monacoRef.current.editor.setTheme(currentMonacoTheme());
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  return (
    <div
      id={id}
      className="mcnp-editor-wrapper"
      style={{ minHeight, background: "var(--editor-bg)", borderRadius: 6, border: "1px solid var(--border-glass)", overflow: "hidden" }}
    >
      <Editor
        height={minHeight}
        language={currentLanguageId}
        theme={currentMonacoTheme()}
        value={value}
        onChange={(next) => onChange?.(next ?? "")}
        onMount={handleMount}
        wrapperProps={{ "data-placeholder": placeholder }}
        options={{
          minimap: { enabled: false },
          lineNumbers: "off",
          folding: false,
          glyphMargin: false,
          overviewRulerLanes: 0,
          scrollBeyondLastLine: false,
          wordWrap: "on",
          wrappingIndent: "same",
          fontFamily: "Consolas, monospace",
          fontSize: 12,
          lineHeight: 19,
          padding: { top: 10, bottom: 10 },
          automaticLayout: true,
          suggest: { showMethods: false, showFunctions: false },
          inlineSuggest: { enabled: true },
        }}
      />
    </div>
  );
}
