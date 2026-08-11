/**
 * useSectionTextMode — 标签页「文本模式」切换的深模块。
 *
 * 把「进/出文本模式」的全部复杂行为收在一个小接口后面：
 *   - 进（表单→文本）：调 /api/section-to-text 把当前表单生成文本填入 textarea
 *   - 出（文本→表单）：调 /api/text-to-section 把文本解析，回填表单（差异点由调用方传 onBackToForm）
 *   - busy 状态、错误提示、deck.textMode 同步
 *
 * 三个标签页（MaterialTab / GeometryTab / TallyTab）共用此模块，
 * 各自只需提供「解析结果 → 写回本地表单」的回调。互转逻辑只在此一处。
 */
import { useState } from "react";
import { SectionKey, sectionToText, textToSection } from "./sectionConvert";

interface Opts {
  /** 当前 deck（表单数据源，切文本模式时用它生成文本） */
  deck: any;
  /** 更新 deck（textMode / rawOverrides 同步） */
  patch: (p: Record<string, any>) => void;
  /** 文本模式下保存在 deck.rawOverrides 的 key（materials/cells/tally） */
  overrideKey: string;
  /** 文本 → 表单 解析成功后，把结果写回本地表单（各标签页差异点） */
  onBackToForm: (data: any) => void;
  /** 已有 rawOverrides 初值（供工作区恢复后回显） */
  initialText?: string;
  /** 当前是否文本模式（供外部恢复 textMode 状态） */
  initialMode?: boolean;
}

export function useSectionTextMode(section: SectionKey, opts: Opts) {
  const [rawMode, setRawMode] = useState(opts.initialMode ?? false);
  const [rawText, setRawText] = useState(opts.initialText ?? "");
  const [busy, setBusy] = useState(false);

  const toggleRawMode = async () => {
    if (busy) return;
    setBusy(true);
    try {
      if (!rawMode) {
        // 表单 → 文本
        const t = await sectionToText(section, opts.deck);
        setRawText(t);
        opts.patch({
          rawOverrides: { ...(opts.deck.rawOverrides || {}), [opts.overrideKey]: t },
          textMode: { ...(opts.deck.textMode || {}), [section]: true },
        });
        setRawMode(true);
      } else {
        // 文本 → 表单
        const txt = rawText || opts.deck.rawOverrides?.[opts.overrideKey] || "";
        if (txt.trim()) {
          const data = await textToSection(section, txt);
          opts.onBackToForm(data);
        }
        opts.patch({ textMode: { ...(opts.deck.textMode || {}), [section]: false } });
        setRawMode(false);
      }
    } catch (e: any) {
      alert(`${section} 文本/表单切换失败: ${e?.message || e}`);
    } finally {
      setBusy(false);
    }
  };

  const onDiscard = () => {
    setRawMode(false);
    setRawText("");
    opts.patch({
      rawOverrides: { ...(opts.deck.rawOverrides || {}), [opts.overrideKey]: "" },
      textMode: { ...(opts.deck.textMode || {}), [section]: false },
    });
  };

  return { rawMode, rawText, busy, setRawText, toggleRawMode, onDiscard };
}
