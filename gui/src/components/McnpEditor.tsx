/**
 * MCNP 卡片编辑器。
 *
 * Monaco 使用单一 TextModel 同时负责文本、光标、选区和复制。
 * 曲面/TR 提示通过 inline completion（ghost text）绘制，不再叠加第二份正文。
 */
import React, { useEffect, useRef } from "react";
import Editor, { type Monaco, type OnMount } from "@monaco-editor/react";
import type { IDisposable, Position, editor } from "monaco-editor";
import {
  completionDetail,
  completionWords,
  ghostForLine,
  languageId,
  surfaceTokenizer,
  trTokenizer,
} from "./mcnpCardSyntax";

let registered = false;

function configureMonaco(monaco: Monaco): void {
  if (registered) return;
  registered = true;
  monaco.languages.register({ id: languageId("surface") });
  monaco.languages.register({ id: languageId("tr") });
  // 语法本身在 mcnpCardSyntax.ts（纯数据，可离线逐行断言 —— 见该文件顶部说明与
  // gui/test/mcnpCardSyntax.test.ts）。这里只负责接到 Monaco 上。
  monaco.languages.setMonarchTokensProvider(languageId("surface"), surfaceTokenizer());
  monaco.languages.setMonarchTokensProvider(languageId("tr"), trTokenizer());
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
