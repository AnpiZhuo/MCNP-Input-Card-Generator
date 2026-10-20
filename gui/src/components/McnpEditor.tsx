/**
 * MCNP 卡片编辑器。
 *
 * Monaco 使用单一 TextModel 同时负责文本、光标、选区和复制。
 * 曲面/TR 提示通过 inline completion（ghost text）绘制，不再叠加第二份正文。
 * 语法与幽灵提示在 `mcnpCardSyntax.ts`（纯数据，可离线逐行断言）。
 *
 * ⚠️ `./monacoLocal` 是副作用导入，必须保留：它把**随包打包**的 monaco 交给 loader 并自带
 * worker，否则 monaco 会在运行时去 jsdelivr CDN 下载 —— 本程序不能联网，那样编辑器会直接不可用。
 */
import "./monacoLocal";

import React, { useEffect, useRef } from "react";
import Editor, { type Monaco, type BeforeMount, type OnMount } from "@monaco-editor/react";
import type { IDisposable, Position, editor } from "monaco-editor";
import {
  completionDetail,
  completionWords,
  deckTokenizer,
  ghostForLine,
  languageId,
  surfaceTokenizer,
  surfaceCompletionAllowed,
  trTokenizer,
} from "./mcnpCardSyntax";

let registered = false;

function configureMonaco(monaco: Monaco): void {
  if (registered) return;
  registered = true;
  monaco.languages.register({ id: languageId("surface") });
  monaco.languages.register({ id: languageId("tr") });
  monaco.languages.register({ id: languageId("deck") });
  // ⛔ 全局关掉 Monaco 的「颜色码」识别（2026-10-11 用户报「#加数字前面会显示色块」）：
  //    Monaco 自带一个**对所有语言生效**的默认颜色提供者，会把 `#232`、`rgb(...)` 这类文本
  //    当成 CSS 颜色 ⇒ 在字前画一个色块（点开还弹取色器）。而 MCNP 里 `#n` 是**栅元补集**
  //    （`#232` = 挖掉 232 号栅元），卡片里到处都是；`#RRGGBB` 形状的数字也不代表颜色。
  //    这里对本程序注册的三种语言各注册一个**空**颜色提供者（语言级优先于 `*`），
  //    配合 `McnpEditor` 的 `colorDecorators/defaultColorDecorators` 开关，双保险。
  const emptyColors = () => [];
  for (const id of [languageId("surface"), languageId("tr"), languageId("deck")]) {
    monaco.languages.registerColorProvider(id, {
      provideDocumentColors: emptyColors,
      provideColorPresentations: emptyColors,
    });
  }
  // 语法本身在 mcnpCardSyntax.ts（纯数据，可离线逐行断言 —— 见该文件顶部说明与
  // gui/test/mcnpCardSyntax.test.ts）。这里只负责接到 Monaco 上。
  monaco.languages.setMonarchTokensProvider(languageId("surface"), surfaceTokenizer());
  monaco.languages.setMonarchTokensProvider(languageId("tr"), trTokenizer());
  monaco.languages.setMonarchTokensProvider(languageId("deck"), deckTokenizer());
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
      "editorSuggestWidget.foreground": "#F1F1F9",
      "editorSuggestWidget.selectedForeground": "#FFFFFF",
      "editorSuggestWidget.selectedBackground": "#37306B",
      "editorSuggestWidget.highlightForeground": "#67E8F9",
      "editorSuggestWidget.border": "#6D5BD0",
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
      "editorSuggestWidget.foreground": "#1F2937",
      "editorSuggestWidget.selectedForeground": "#111827",
      "editorSuggestWidget.selectedBackground": "#DBEAFE",
      "editorSuggestWidget.highlightForeground": "#1D4ED8",
      "editorSuggestWidget.border": "#93C5FD",
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
  mode?: "surface" | "tr" | "deck";
  /** 只读（生成预览页用：文本由表单生成，不允许在这里改） */
  readOnly?: boolean;
  /**
   * 按**字符区间**高亮（不是整行）：参数扫描用它标出"这几个字符会被替换"。
   * 颜色只给 CSS 类名（Monaco 的 inlineClassName 不认颜色值）—— 见 utils/sweepHighlight。
   */
  highlights?: { start: number; end: number; className: string }[];
  /** 选区变化（字符偏移，0-based，[start, end)）：参数扫描据此记住"用户划了哪几个字符" */
  onSelect?: (start: number, end: number) => void;
}

export default function McnpEditor({
  id,
  value = "",
  onChange,
  placeholder = "",
  minHeight = 180,
  mode = "surface",
  readOnly = false,
  highlights,
  onSelect,
}: Props) {
  const currentLanguageId = languageId(mode);
  const modeRef = useRef(mode);
  modeRef.current = mode;
  const monacoRef = useRef<Monaco | null>(null);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const completionDisposable = useRef<IDisposable | null>(null);
  const inlineDisposable = useRef<IDisposable | null>(null);
  const selectionDisposable = useRef<IDisposable | null>(null);
  const decorationIds = useRef<string[]>([]);
  const highlightsRef = useRef(highlights);
  highlightsRef.current = highlights;

  /** 把「字符偏移」画成 Monaco 的区间高亮（局部高亮：只覆盖划中的那几个字符） */
  const paintHighlights = () => {
    const ed = editorRef.current;
    const m = monacoRef.current;
    const model = ed?.getModel();
    if (!ed || !m || !model) return;
    const len = model.getValueLength();
    const decorations = (highlightsRef.current || [])
      .filter((h) => h.end > h.start)
      .map((h) => {
        const start = Math.max(0, Math.min(h.start, len));
        const end = Math.max(start, Math.min(h.end, len));
        const p1 = model.getPositionAt(start);
        const p2 = model.getPositionAt(end);
        return {
          range: new m.Range(p1.lineNumber, p1.column, p2.lineNumber, p2.column),
          options: { inlineClassName: h.className, stickiness: m.editor.TrackedRangeStickiness.NeverGrowsWhenTypingAtEdges },
        };
      });
    decorationIds.current = ed.deltaDecorations(decorationIds.current, decorations);
  };

  const beforeMount: BeforeMount = (monaco) => {
    configureMonaco(monaco);
  };

  const handleMount: OnMount = (editor, monaco) => {
    monacoRef.current = monaco;
    editorRef.current = editor;
    monaco.editor.setModelLanguage(editor.getModel()!, currentLanguageId);
    monaco.editor.setTheme(currentMonacoTheme());

    // 选区 → 字符偏移（参数扫描要"我划了哪些字符"，不是"哪一行"）
    selectionDisposable.current?.dispose();
    selectionDisposable.current = editor.onDidChangeCursorSelection(() => {
      const model = editor.getModel();
      const sel = editor.getSelection();
      if (!model || !sel || !onSelect) return;
      onSelect(model.getOffsetAt(sel.getStartPosition()), model.getOffsetAt(sel.getEndPosition()));
    });

    // 整张卡模式不提供补全/幽灵提示（卡型太多，猜不准就不猜）
    completionDisposable.current?.dispose();
    inlineDisposable.current?.dispose();
    if (modeRef.current === "deck") { paintHighlights(); return; }

    completionDisposable.current = monaco.languages.registerCompletionItemProvider(currentLanguageId, {
      triggerCharacters: [" "],
      provideCompletionItems: (model: editor.ITextModel, position: Position) => {
        const line = model.getLineContent(position.lineNumber);
        const before = line.slice(0, position.column - 1);
        if (modeRef.current === "surface" && !surfaceCompletionAllowed(before)) {
          return { suggestions: [] };
        }
        const partial = before.match(/[A-Za-z/*]+$/)?.[0] || "";
        const words = completionWords(modeRef.current);
        const suggestions = words
          .filter((word) => word.toUpperCase().startsWith(partial.toUpperCase()))
          .map((word) => ({
            label: word,
            kind: monaco.languages.CompletionItemKind.Keyword,
            insertText: word,
            detail: completionDetail(word, modeRef.current),
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
    selectionDisposable.current?.dispose();
  }, []);

  // 高亮区间变了（加/删参数、框选别处）或有新文本 → 重画；内容变了要重新按偏移算位置
  useEffect(() => { paintHighlights(); }, [highlights, value]);

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
        beforeMount={beforeMount}
        onMount={handleMount}
        // 加载期文案（默认是英文 "Loading..."）。monaco 现在随包，正常只闪一下；但万一编辑器
        // 起不来，这行字至少让用户看出「卡在编辑器本身」，而不是一片空白。
        loading={<span style={{ color: "#9CA3AF", fontSize: 12 }}>编辑器加载中…</span>}
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
          inlineSuggest: { enabled: !readOnly && mode !== "deck" },
          // ⛔ 全局关掉颜色码装饰（`#232` 是 MCNP 的栅元补集，不是颜色）——对所有模式生效：
          //    colorDecorators 默认 true、defaultColorDecorators 默认 "auto"，两个都得关。
          //    见 configureMonaco 里注册的空颜色提供者。
          colorDecorators: false,
          defaultColorDecorators: "never",
          readOnly,
          domReadOnly: readOnly,
          // 只读时不要"未聚焦就灰掉选中"的观感（预览页整块都是只读的）
          renderLineHighlight: "none",
        }}
      />
    </div>
  );
}
