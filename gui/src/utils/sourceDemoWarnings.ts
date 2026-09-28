/**
 * sourceDemoWarning — 源演示的**非阻断告警**文案（契约 source-demo-visualization.md §1/§4）。
 *
 * 后端 `sample_source` 会在**成功**响应里带两类告警，前端必须都展示，否则等于静默：
 *
 * - `geometryWarnings`：几何解析类（曲面行/栅元没解析出来）⇒ 相关源形状可能不准；
 * - `warnings`：引擎侧语义告警。当前唯一来源是 **`ARA`**（面源面积）——C810 Table 3.3
 *   p.3-56 说明它只用于**点探测器直接贡献的归一化**（「required only for direct
 *   contributions to point detectors」），与粒子的起始位置/方向/能量/权重**无关**；
 *   本程序不算 tally，故**接受它但不使用**，只记一条说明。此前这条说明在
 *   `SourceTab` 里被丢掉（只读 `geometryWarnings`）⇒ 用户以为 ARA 生效了。
 */
export function sourceDemoWarning(
  geometryWarnings?: string[],
  warnings?: string[],
): string {
  const parts: string[] = [];
  if (geometryWarnings && geometryWarnings.length) {
    parts.push(
      "部分栅元几何未能解析（" + geometryWarnings.slice(0, 3).join("；")
      + (geometryWarnings.length > 3 ? " 等 " + geometryWarnings.length + " 项" : "")
      + "），相关源形状可能不准。",
    );
  }
  if (warnings && warnings.length) {
    parts.push(warnings.join("；"));
  }
  return parts.join(" ");
}
