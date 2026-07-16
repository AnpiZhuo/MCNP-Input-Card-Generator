"""
🧪 材料标签页：概览列表 + [✎] 弹窗编辑
材料新增时自动向栅元发出联动信号
Material Tab: Overview list + [Edit] dialog
Automatically signals the geometry tab when materials are added/removed

This module provides the MaterialTab widget for managing MCNP material definitions.
Materials consist of nuclide compositions (ZAID + fraction pairs) with optional comments.
Density is set in the cell cards per MCNP convention (density is written on cell cards,
not material cards).
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTableWidget, QTableWidgetItem, QPushButton,
    QHeaderView, QLabel, QMessageBox, QWidget,
    QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QSettings

from app.models import MaterialData, MaterialRow
from app.dialogs.material_edit_dialog import MaterialEditDialog
from app.widgets.text_mode_section import TextModeSection
from app.generator.inp_generator import _generate_materials


class MaterialTab(QWidget):
    """材料标签页 / Material Tab

    Provides a table-based interface for defining MCNP materials with:
    - Material list with auto-numbering and comment annotations
    - Dialog-based editing for ZAID (nuclide identifier) and fraction pairs
    - Automatic cell creation/deletion linkage with the geometry tab
    - Dual-mode editing (form-based table and raw text mode)

    Signals:
        material_added: Emitted with the new material number when a material is added.
    """

    material_added = pyqtSignal(int)  # 发出新材料号 / Emits new material number

    def __init__(self, main_window):
        """Initialize the material tab.

        Args:
            main_window: Reference to the main application window for cross-tab
                        communication (geometry tab cell linkage).
        """
        super().__init__()
        self.main_window = main_window
        self.materials: list[MaterialData] = []
        self.init_ui()

    def init_ui(self):
        """Build the material tab UI layout.

        Follows the same QScrollArea + stacked QGroupBox pattern as the energy tab.
        """
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)

        # ===== 材料概览列表 / Material Overview List =====
        grp = QGroupBox("材料列表（至少定义一个材料）")
        grp.setToolTip(
            "定义模型中使用的材料组成（核素 + 份额）。\n"
            "每个材料包含 ZAID（核素标识）和份额。\n"
            "密度在栅元卡中设置（MCNP 的密度写在栅元卡上）。"
        )
        inner = QVBoxLayout(grp)

        # Toolbar with label and action buttons
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel(
            "<span style='font-weight:bold;'>材料号</span> — 注释"
        ))
        toolbar.addStretch()

        self.btn_add = QPushButton("+ 添加材料")
        self.btn_add.setToolTip("新增一个材料，同时自动在栅元卡中添加对应的栅元行")
        self.btn_add.setProperty("cssClass", "btnAdd")
        self.btn_add.clicked.connect(self._add_material)

        self.btn_del = QPushButton("× 删除选中")
        self.btn_del.setToolTip("删除选中的材料及其对应的栅元行（需手动确认）")
        self.btn_del.setProperty("cssClass", "btnDelete")
        self.btn_del.clicked.connect(self._delete_material)

        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_del)
        inner.addLayout(toolbar)

        # Material table: number, comment, edit action (列宽可拖拽)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["材料号", "注释", "操作"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)
        self._mt_settings = QSettings("MCNPGen", "MCNPGenerator")
        saved = self._mt_settings.value("mat_col_widths")
        if saved and len(saved) == 3:
            for col, w in enumerate(saved):
                self.table.setColumnWidth(col, int(w))
        else:
            self.table.setColumnWidth(0, 80)
            self.table.setColumnWidth(1, 250)
            self.table.setColumnWidth(2, 70)
        header.sectionResized.connect(self._save_mat_col_widths)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setToolTip("双击行或点击编辑按钮编辑材料核素组成。列宽可拖拽调整。")

        # Text mode toggle button (added to toolbar after delete button)
        self._raw_mat = TextModeSection(
            form_widget=self.table,
            generate_fn=lambda: "\n".join(_generate_materials(self.materials)),
            section_name="materials",
        )
        # Insert toggle button into toolbar after the delete button
        toolbar.insertWidget(toolbar.indexOf(self.btn_del) + 1, self._raw_mat.toggle_btn)
        # table is already on stack page 0, add stack directly to layout
        inner.addWidget(self._raw_mat.stack)
        grp.setMinimumHeight(600)
        layout.addWidget(grp)

        # ===== Format hint =====
        hint = QLabel(
            "<span style='color:#5f6368; font-size:12px;'>"
            "💡 密度在栅元卡中设置。点击 [✎] 编辑核素组成，格式如 92235.06c -0.05</span>"
        )
        layout.addWidget(hint)
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

    # ---------- 公开接口 ----------

    def get_materials(self) -> list[MaterialData]:
        """Get the list of defined materials.

        Returns:
            list[MaterialData]: All material definitions currently in the tab.
        """
        return self.materials

    def set_data(self, materials: list[MaterialData]):
        """从导入数据回填 UI（用于 INP 导入） / Populate UI from imported data (for INP import).

        Args:
            materials: List of material data objects to restore.
        """
        self.materials = list(materials)
        self._refresh_table()

    def get_raw_overrides(self) -> dict:
        """返回文本模式原始文本，供生成器使用 / Return raw text mode overrides for the generator.

        Returns:
            dict: Dictionary with "materials" key containing raw text, if any.
        """
        return {"materials": self._raw_mat.get_raw_text()}

    # ---------- 内部操作 ----------

    def _refresh_table(self):
        """Refresh the material table display.

        Rebuilds all table rows from the current materials list.
        Each row shows: material number (with M prefix), comment, and an edit button.
        """
        self.table.setRowCount(len(self.materials))
        for i, mat in enumerate(self.materials):
            self.table.setItem(i, 0, QTableWidgetItem(f"M{mat.number}"))
            self.table.setItem(i, 1, QTableWidgetItem(mat.comment))

            btn_edit = QPushButton("✎ 编辑")
            btn_edit.setToolTip("编辑此材料的 ZAID 和份额")
            btn_edit.setProperty("cssClass", "btnEdit")
            btn_edit.clicked.connect(lambda checked, idx=i: self._edit_material(idx))
            self.table.setCellWidget(i, 2, btn_edit)

    def _next_material_number(self) -> int:
        """Get the next available material number.

        Returns the highest existing material number + 1, or 1 if none exist.

        Returns:
            int: Next available material number.
        """
        if not self.materials:
            return 1
        return max(m.number for m in self.materials) + 1

    def _add_material(self):
        """添加新材料 + 联动栅元 / Add a new material and link with geometry tab.

        Creates a new empty material and appends it to the list.
        Then emits material_added signal so the geometry tab can create
        a corresponding cell row.
        """
        new_num = self._next_material_number()
        mat = MaterialData(
            number=new_num,
            rows=[],
            comment="",
        )
        self.materials.append(mat)
        self._refresh_table()

        # 发出联动信号 → 几何标签页新增对应栅元行
        # Emit linkage signal -> geometry tab creates corresponding cell row
        self.material_added.emit(new_num)

    def _delete_material(self):
        """删除选中材料 / Delete selected materials.

        Prompts for confirmation, then removes the selected materials and
        their linked cells from the geometry tab.
        """
        rows = set()
        for idx in self.table.selectedIndexes():
            rows.add(idx.row())
        if not rows:
            QMessageBox.information(self, "提示", "请先选中要删除的材料")
            return

        # Collect material numbers to be deleted
        deleted_numbers = []
        for row in sorted(rows, reverse=True):
            if 0 <= row < len(self.materials):
                deleted_numbers.append(self.materials[row].number)

        if not deleted_numbers:
            return

        # Confirmation dialog before deletion
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除 {len(deleted_numbers)} 个材料吗？\n"
            f"对应的栅元也将自动删除。",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # Remove materials (use set membership for efficient filtering)
        deleted_set = set(deleted_numbers)
        self.materials = [m for m in self.materials if m.number not in deleted_set]

        # Linked deletion of corresponding cells in geometry tab
        geo = getattr(self.main_window, 'tab_geo', None)
        if geo:
            total_removed = 0
            for num in deleted_numbers:
                total_removed += geo.remove_cells_for_material(num)
            if total_removed > 0:
                QMessageBox.information(
                    self, "栅元已清理",
                    f"已自动删除 {total_removed} 个引用被删材料的栅元行。"
                )

        self._refresh_table()

    def _save_mat_col_widths(self):
        """拖拽列宽时自动保存"""
        widths = [self.table.columnWidth(c) for c in range(self.table.columnCount())]
        self._mt_settings.setValue("mat_col_widths", widths)

    def _edit_material(self, idx: int):
        """弹出材料编辑对话框 / Open material edit dialog.

        Opens a MaterialEditDialog for the material at the given index.
        If accepted, updates the material data and refreshes the table.

        Args:
            idx: Index of the material in self.materials list.
        """
        if idx < 0 or idx >= len(self.materials):
            return
        dialog = MaterialEditDialog(self.materials[idx], self)
        if dialog.exec_() == MaterialEditDialog.Accepted:
            updated = dialog.get_data()
            self.materials[idx] = updated
            self._refresh_table()
