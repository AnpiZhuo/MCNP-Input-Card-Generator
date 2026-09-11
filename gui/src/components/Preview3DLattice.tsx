/**
 * Preview3DLattice —— 已废弃（DEPRECATED），此处保留占位，避免 479 行死代码继续滞留。
 *
 * 历史：阶段3 曾把「格阵按 FILL 装配」做成独立组件（本文件），由 Preview3D 按
 * fill/fill_grid 路由切换进去。**该接线后来被内联取代**：装配逻辑现由
 * `gui/src/components/Preview3D.tsx` 直接承担：
 *   - `Preview3D.tsx:15`  `import { buildLatticeInstances, DETAIL_MAX_INSTANCES } from "../three/latticeInstances"`
 *   - `Preview3D.tsx:721` POST `/api/preview-lattice`（后端 compose_lattice_tree → FLAT leafInstances + 每格阵 STL）
 *   - 其后在同一 effect 内**内联**消费 leafInstances 完成装配（InstancedMesh / 总览与详细模式 / 取景）
 *
 * 因此本组件在 `gui/src` 内**零 import**，行为与 Preview3D 的内联实现重复且无任何测试触达
 * → 按技术债 **TD-16** 清退（审计侧编号 FE-03 / M-22）。
 *
 * 保留占位文件（而非物理删除）只为让历史 diff 与审计记录仍能定位到该路径。
 * 如需恢复「格阵独立视图」，**请以 `Preview3D.tsx` 的内联装配为唯一权威实现，不要复活本文件**。
 *
 * 关联记录：`docs/audit/t3-frontend-debt.md`（FE-03）、`docs/audit/t1-memory-debt.md`（M-22：
 * 审计判定为「曾接线、后被内联取代」，文档侧清理归 M-22）。
 */

export {};
