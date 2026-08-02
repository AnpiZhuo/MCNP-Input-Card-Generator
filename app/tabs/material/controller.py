"""Material — 控制器层"""

from PyQt5.QtWidgets import QWidget, QPushButton, QTableWidgetItem, QMessageBox
from PyQt5.QtCore import Qt, pyqtSignal, QSettings

from app.models import MaterialData, MaterialRow
from app.dialogs.material_edit_dialog import MaterialEditDialog
from app.generator.inp_generator import _generate_materials
from .view import create_ui


class MaterialTab(QWidget):

    material_added = pyqtSignal(int)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.materials: list[MaterialData] = []
        self._mt_settings = QSettings("MCNPGen", "MCNPGenerator")
        # 创建视图，传入 raw text 生成回调
        self.ui = create_ui(self, gen_fn=lambda: "\n".join(_generate_materials(self.materials)))
        self._connect_signals()
        self._restore_column_widths()

    def _connect_signals(self):
        self.ui.btn_add.clicked.connect(self._add_material)
        self.ui.btn_del.clicked.connect(self._delete_material)
        self.ui.table.horizontalHeader().sectionResized.connect(self._save_mat_col_widths)

    def _restore_column_widths(self):
        saved = self._mt_settings.value("mat_col_widths")
        if saved and len(saved) == 3:
            for col, w in enumerate(saved):
                self.ui.table.setColumnWidth(col, int(w))

    def _save_mat_col_widths(self):
        widths = [self.ui.table.columnWidth(c) for c in range(self.ui.table.columnCount())]
        self._mt_settings.setValue("mat_col_widths", widths)

    @staticmethod
    def _auto_resize_table(table, min_rows=5):
        n = table.rowCount()
        rows = max(min_rows, n)
        hh = table.horizontalHeader().height() or 28
        rh = table.rowHeight(0) if n > 0 else 30
        fw = 2 * table.frameWidth()
        table.setMinimumHeight(hh + rh * rows + fw + 4)

    # ── 公开接口 ──

    def get_materials(self) -> list[MaterialData]:
        return self.materials

    def set_data(self, materials: list[MaterialData]):
        self.materials = list(materials)
        self._refresh_table()

    def get_raw_overrides(self) -> dict:
        return {"materials": self.ui.raw_mat.get_raw_text()}

    # ── 内部 ──

    def _refresh_table(self):
        self.ui.table.setRowCount(len(self.materials))
        for i, mat in enumerate(self.materials):
            self.ui.table.setItem(i, 0, QTableWidgetItem(f"M{mat.number}"))
            self.ui.table.setItem(i, 1, QTableWidgetItem(mat.comment))
            btn_edit = QPushButton("✎ 编辑")
            btn_edit.setToolTip("编辑此材料的 ZAID 和份额")
            btn_edit.setProperty("cssClass", "btnEdit")
            btn_edit.clicked.connect(lambda checked, idx=i: self._edit_material(idx))
            self.ui.table.setCellWidget(i, 2, btn_edit)
        self._auto_resize_table(self.ui.table)

    def _next_material_number(self) -> int:
        if not self.materials:
            return 1
        return max(m.number for m in self.materials) + 1

    def _add_material(self):
        new_num = self._next_material_number()
        self.materials.append(MaterialData(number=new_num, rows=[], comment=""))
        self._refresh_table()
        self.material_added.emit(new_num)

    def _delete_material(self):
        rows = set(idx.row() for idx in self.ui.table.selectedIndexes())
        if not rows:
            QMessageBox.information(self, "提示", "请先选中要删除的材料")
            return
        deleted_numbers = []
        for row in sorted(rows, reverse=True):
            if 0 <= row < len(self.materials):
                deleted_numbers.append(self.materials[row].number)
        if not deleted_numbers:
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除 {len(deleted_numbers)} 个材料吗？\n对应的栅元也将自动删除。",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        deleted_set = set(deleted_numbers)
        self.materials = [m for m in self.materials if m.number not in deleted_set]
        geo = getattr(self.main_window, 'tab_geo', None)
        if geo:
            removed = sum(geo.remove_cells_for_material(num) for num in deleted_numbers)
            if removed:
                QMessageBox.information(self, "栅元已清理", f"已自动删除 {removed} 个引用被删材料的栅元行。")
        self._refresh_table()

    def _edit_material(self, idx: int):
        if idx < 0 or idx >= len(self.materials):
            return
        dialog = MaterialEditDialog(self.materials[idx], self)
        if dialog.exec_() == MaterialEditDialog.Accepted:
            self.materials[idx] = dialog.get_data()
            self._refresh_table()
