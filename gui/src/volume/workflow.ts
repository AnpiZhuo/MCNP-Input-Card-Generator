/**
 * workflow — 引导式工作流空态纯逻辑（契约 meshtal-visualization.md §12 F1）
 *
 * F1.1 空态清晰指引：无 meshtal 数据时显示三步引导
 *      「① 先运行 MCNP（或选择 meshtal 文件）→ ② 点解析 → ③ 看结果」
 * F1.2 没找到文件给可操作提示：meshtal-detect 返回空列表 → 显示
 *      「未在输出目录找到 MESHTAL 文件，请点这里选择 meshtal 文件」，
 *      「点这里」触发 choose-file（可操作，非报错）。
 *
 * 纯逻辑（状态 → 文案/动作），vitest 可测。
 */
export type MeshWorkflowState = "idle" | "noFiles" | "parsed" | "error";

export interface WorkflowStep {
  no: string;
  text: string;
}

export interface WorkflowView {
  title: string;
  steps: WorkflowStep[];
}

const THREE_STEPS: WorkflowStep[] = [
  { no: "①", text: "先运行 MCNP（或选择 meshtal 文件）" },
  { no: "②", text: "点解析" },
  { no: "③", text: "看结果" },
];

/** 状态 → 空态指引视图（F1.1） */
export function workflowStep(state: MeshWorkflowState): WorkflowView {
  if (state === "noFiles") {
    return {
      title: "没有找到 MESHTAL 文件",
      steps: THREE_STEPS,
    };
  }
  if (state === "parsed") {
    return {
      title: "网格计数数据已就绪",
      steps: [
        { no: "✓", text: "MESHTAL 文件已解析" },
        { no: "→", text: "打开 3D 结果窗口查看体积渲染" },
      ],
    };
  }
  if (state === "error") {
    return {
      title: "解析没有成功",
      steps: THREE_STEPS,
    };
  }
  return {
    title: "还没有网格计数数据",
    steps: THREE_STEPS,
  };
}

/**
 * 没找到文件 → 可操作提示（F1.2）。
 * hasFiles=false 时返回提示文案 + 「点这里」动作文案（触发 choose-file）。
 */
export function noFileMessage(hasFiles: boolean): { text: string; action: string } {
  if (hasFiles) return { text: "", action: "" };
  return {
    text: "未在输出目录找到 MESHTAL 文件",
    action: "请点这里选择 meshtal 文件",
  };
}
