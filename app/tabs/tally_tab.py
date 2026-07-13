"""
📊 计数卡标签页：动态 QTableWidget + TallyDefinition 数据模型

参照 material_tab.py 的 list[MaterialData] + _refresh_table() 模式，
使用 list[TallyDefinition] + QTableWidget + 添加/删除行按钮。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTableWidget, QTableWidgetItem, QPushButton,
    QSpinBox, QLineEdit, QHeaderView,
    QLabel, QMessageBox, QScrollArea, QCheckBox,
)
from PyQt5.QtCore import Qt, QSettings, pyqtSignal

from app.models import TallySettings, TallyDefinition
from app.widgets.text_mode_section import TextModeSection
from app.generator.inp_generator import _generate_tallies

# 默认编号映射：选择类型时自动填入的默认编号
_TYPE_CN_NAME = {
    "F1": "曲面粒子流", "F2": "曲面平均通量",
    "F4": "栅元平均通量", "F5": "点探测器",
    "F6": "能量沉积", "F7": "裂变能沉积",
    "F8": "脉冲高度谱",
}

_TYPE_DEFAULT_NUMBER = {
    "F1": 1, "F2": 2, "F4": 4, "F5": 5,
    "F6": 6, "F7": 7, "F8": 8,
}


def _type_param_placeholder(tally_type: str) -> str:
    """返回该计数类型的参数输入框提示文本"""
    placeholders = {
        "F1": "曲面号，如: 1 2 3",
        "F2": "曲面号，如: 1 2 3",
        "F4": "栅元号，如: 1 2 3",
        "F5": "x y z R0（支持多点）",
        "F6": "栅元号，如: 1 2 3",
        "F7": "栅元号，如: 1 2 3",
        "F8": "栅元号，如: 1 2 3",
    }
    return placeholders.get(tally_type, "")


def _type_param_tooltip(tally_type: str) -> str:
    """返回该计数类型的参数输入框工具提示"""
    tips = {
        "F1": "穿过指定曲面的粒子流。曲面号可输多个，空格分隔。",
        "F2": "曲面平均通量。曲面号可输多个，空格分隔。",
        "F4": "栅元平均通量。栅元号可输多个，空格分隔。",
        "F5": "点探测器坐标。每组 x y z R0，空格分隔，支持多点。",
        "F6": "能量沉积 (MeV/g)。栅元号可输多个，空格分隔。",
        "F7": "裂变能沉积 (MeV/g)。栅元号可输多个，空格分隔。",
        "F8": "脉冲高度谱。栅元号可输多个，空格分隔。",
    }
    return tips.get(tally_type, "")


def _number_to_type(n: int) -> str | None:
    """由编号末位数字推断计数类型。

    MCNP 根据编号末位决定计数类型：
    F1/F11/F21… → F1,  F5/F15/F25… → F5,  以此类推。
    末位为 3/9/0 时无标准对应，返回 None。
    """
    digit = n % 10
    mapping = {1: "F1", 2: "F2", 4: "F4", 5: "F5",
               6: "F6", 7: "F7", 8: "F8"}
    return mapping.get(digit)


class TallyTab(QWidget):
    """计数卡标签页 — 动态表格 + 添加/删除行"""

    talliesChanged = pyqtSignal()  # 计数卡列表变化时发射（用于同步 En 预览）

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)

        grp = QGroupBox("计数卡列表（每行定义一个 Fn 计数）")
        grp.setToolTip(
            "在此定义 MCNP 计数卡。每行包含：计数类型、编号、粒子、参数。\n"
            "粒子可多选（如 n p e），生成时每个粒子输出一张 Fn 卡。\n"
            "支持编号如 15/25/35（F15:n 等），类型由下拉菜单决定行为。"
        )
        inner = QVBoxLayout(grp)

        # ── 工具栏 ──
        toolbar = QHBoxLayout()
        label_info = QLabel(
            "<span style='font-weight:bold;'>类型</span> — 编号 — 粒子 — 参数"
        )
        toolbar.addWidget(label_info)
        toolbar.addStretch()

        self.btn_add = QPushButton("+ 添加计数")
        self.btn_add.setToolTip("新增一行 F4:n 计数卡")
        self.btn_add.setProperty("cssClass", "btnAdd")
        self.btn_add.clicked.connect(self._add_default_tally)

        self.btn_del = QPushButton("× 删除选中")
        self.btn_del.setToolTip("删除选中的计数行")
        self.btn_del.setProperty("cssClass", "btnDelete")
        self.btn_del.clicked.connect(self._delete_selected)

        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_del)
        inner.addLayout(toolbar)

        # ── 表格（列宽可拖拽调整，自动保存）──
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["类型", "编号", "粒子", "参数", "En", "操作"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)
        header.setSectionsMovable(False)
        # 恢复上次保存的列宽
        self._col_settings = QSettings("MCNPGen", "MCNPGenerator")
        self._column_widths_key = "tally_tab_column_widths"
        saved_widths = self._col_settings.value(self._column_widths_key)
        n_cols = 6
        if saved_widths and len(saved_widths) >= n_cols:
            for col in range(n_cols):
                self.table.setColumnWidth(col, int(saved_widths[col]))
        else:
            # 默认宽度
            self.table.setColumnWidth(0, 100)
            self.table.setColumnWidth(1, 80)
            self.table.setColumnWidth(2, 80)
            self.table.setColumnWidth(3, 200)
            self.table.setColumnWidth(4, 40)
            self.table.setColumnWidth(5, 70)
        # 拖拽列宽时自动保存
        header.sectionResized.connect(self._save_column_widths)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setToolTip(
            "双击编辑参数列。粒子可输如 n p e h he。列宽可拖拽调整。"
        )

        # TextModeSection
        self._raw_tally = TextModeSection(
            form_widget=self.table,
            generate_fn=self._gen_tally_raw,
            section_name="tally",
        )
        toolbar.insertWidget(toolbar.indexOf(self.btn_del) + 1, self._raw_tally.toggle_btn)
        inner.addWidget(self._raw_tally.stack)

        layout.addWidget(grp)

        # 使用说明 + 计数类型参照表
        hint = QLabel(
            "<span style='color:#5f6368; font-size:12px;'>"
            "💡 每个粒子输出一张 Fn 卡。如编号=15 粒子=n p "
            "生成 <code>F15:N</code> 和 <code>F15:P</code> 两张卡。</span>"
        )
        layout.addWidget(hint)

        # 计数类型参照表
        ref_html = (
            "<table style='font-size:11px; color:#5f6368; border-collapse:collapse;'>"
            "<tr style='border-bottom: 1px solid #ddd;'>"
            "<th style='padding:2px 8px;'>编号末位</th>"
            "<th style='padding:2px 8px;'>类型</th>"
            "<th style='padding:2px 8px;'>含义</th>"
            "<th style='padding:2px 8px;'>说明</th></tr>"
        )
        for digit, ftype, cn, desc in [
            ("1", "F1", "曲面粒子流", "穿过指定曲面的粒子总数，单位：粒子"),
            ("2", "F2", "曲面平均通量", "曲面上的平均粒子通量，单位：粒子/cm²"),
            ("4", "F4", "栅元平均通量", "栅元内平均通量，最常用，单位：粒子/cm²"),
            ("5", "F5", "点探测器", "空间点的通量，不需栅元，单位：粒子/cm²"),
            ("6", "F6", "能量沉积", "栅元内能量沉积/吸收剂量，单位：MeV/g"),
            ("7", "F7", "裂变能沉积", "裂变材料栅元的裂变能量沉积，单位：MeV/g"),
            ("8", "F8", "脉冲高度谱", "栅元内脉冲高度分布，模拟探测器响应"),
        ]:
            ref_html += (
                f"<tr><td style='padding:1px 8px;text-align:center;'>{digit}</td>"
                f"<td style='padding:1px 8px;font-weight:bold;'>{ftype}</td>"
                f"<td style='padding:1px 8px;'>{cn}</td>"
                f"<td style='padding:1px 8px;'>{desc}</td></tr>"
            )
        ref_html += "</table>"
        ref_label = QLabel(ref_html)
        ref_label.setTextFormat(Qt.RichText)
        layout.addWidget(ref_label)
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ───────── 公开接口 ─────────

    def get_data(self) -> dict:
        """返回计数卡数据（dict 含 tallies 键）"""
        return {"tallies": self._collect_tallies()}

    def set_data(self, tally: TallySettings):
        """从 TallySettings 回填 UI"""
        self.table.setRowCount(0)
        for td in tally.tallies:
            self._add_row(td.type, td.number,
                          " ".join(td.particles),
                          td.params, td.generate_en)

    def get_raw_overrides(self) -> dict:
        return {"tally": self._raw_tally.get_raw_text()}

    # ───────── 内部操作 ─────────

    def _collect_tallies(self) -> list[TallyDefinition]:
        """从表格各行收集 TallyDefinition 列表"""
        tallies = []
        for row in range(self.table.rowCount()):
            lbl_type = self.table.cellWidget(row, 0)
            sb_num = self.table.cellWidget(row, 1)
            le_part = self.table.cellWidget(row, 2)
            le_params = self.table.cellWidget(row, 3)
            cb_en = self.table.cellWidget(row, 4)

            if not lbl_type or not sb_num:
                continue

            tally_type = lbl_type.text().strip().split()[0]
            number = sb_num.value()

            raw_particles = le_part.text().strip() if le_part else ""
            particles = [p.strip().lower() for p in raw_particles.split()
                         if p.strip()]
            if not particles:
                particles = ["n"]

            params = le_params.text().strip() if le_params else ""
            generate_en = cb_en.isChecked() if cb_en else True

            tallies.append(TallyDefinition(
                type=tally_type, number=number,
                particles=particles, params=params,
                generate_en=generate_en,
            ))
        return tallies

    def _add_row(self, tally_type: str = "F4", number: int = 4,
                 particles: str = "n", params: str = "",
                 generate_en: bool = False):
        """在表格末尾添加一行"""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # 类型（由编号末位自动同步，只读显示）
        cn_name = _TYPE_CN_NAME.get(tally_type, "")
        lbl_type = QLabel(f"{tally_type} {cn_name}" if cn_name else tally_type)
        lbl_type.setAlignment(Qt.AlignCenter)
        lbl_type.setStyleSheet("font-weight: bold; padding: 4px;")
        lbl_type.setToolTip(f"计数类型（由编号末位自动决定，不可编辑）\n{tally_type} = {cn_name}")
        self.table.setCellWidget(row, 0, lbl_type)

        # 编号（末位自动同步类型）
        sb = QSpinBox()
        sb.setRange(1, 99999)
        sb.setValue(number)
        sb.setToolTip("计数编号（如 1, 2, 5, 15, 25…）\n末位数字决定 MCNP 计数类型。"
                      "修改编号时类型下拉自动同步。")
        sb.valueChanged.connect(
            lambda v, r=row: self._on_number_changed(r, v)
        )
        self.table.setCellWidget(row, 1, sb)

        # 粒子
        le_part = QLineEdit()
        le_part.setText(particles)
        le_part.setPlaceholderText("如: n  n p  n p e h he")
        le_part.setToolTip("粒子类型，空格分隔。可用: n p e h he")
        self.table.setCellWidget(row, 2, le_part)

        # 参数（提示文字随类型变）
        le_params = QLineEdit()
        le_params.setText(params)
        le_params.setPlaceholderText(_type_param_placeholder(tally_type))
        le_params.setToolTip(_type_param_tooltip(tally_type))
        self.table.setCellWidget(row, 3, le_params)

        # En 能量卡生成开关
        cb_en = QCheckBox()
        cb_en.setChecked(generate_en)
        cb_en.setToolTip("勾选=自动生成该计数的 En 能量卡（使用 E0 的能量网格参数）")
        cb_en.toggled.connect(self.talliesChanged.emit)
        self.table.setCellWidget(row, 4, cb_en)

        # 删除按钮（列 5）
        btn_del = QPushButton("× 删除")
        btn_del.setToolTip("删除此行")
        btn_del.setProperty("cssClass", "btnDeleteRow")
        btn_del.clicked.connect(lambda checked, w=btn_del: self._delete_row(w))
        self.table.setCellWidget(row, 5, btn_del)

    def _save_column_widths(self):
        """拖拽列宽时自动保存到 QSettings"""
        widths = [self.table.columnWidth(c) for c in range(self.table.columnCount())]
        self._col_settings.setValue(self._column_widths_key, widths)

    def _on_type_changed(self, row: int, new_type: str):
        """类型改变时更新参数列的提示文字"""
        le_params = self.table.cellWidget(row, 3)
        if le_params:
            le_params.setPlaceholderText(_type_param_placeholder(new_type))
            le_params.setToolTip(_type_param_tooltip(new_type))

    def _on_number_changed(self, row: int, value: int):
        """编号改变时自动同步类型标签（末位数字决定 MCNP 计数类型）"""
        new_type = _number_to_type(value)
        if new_type is None:
            return  # 末位 3/9/0 无标准映射，保留当前类型
        lbl = self.table.cellWidget(row, 0)
        # Compare by stripping the Chinese suffix to avoid redundant updates
        current_short = lbl.text().split()[0] if lbl else ""
        if lbl and current_short != new_type:
            cn_name = _TYPE_CN_NAME.get(new_type, "")
            lbl.setText(f"{new_type} {cn_name}" if cn_name else new_type)
            lbl.setToolTip(
                f"计数类型（由编号末位自动决定，不可编辑）\n{new_type} = {cn_name}"
            )
            # 同步更新参数列的提示文字
            self._on_type_changed(row, new_type)
        # 编号变化 → 通知 En 预览更新
        self.talliesChanged.emit()

    def _delete_row(self, btn_widget: QPushButton):
        """通过按钮控件引用删除所在行"""
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 5) is btn_widget:
                self.table.removeRow(row)
                self.talliesChanged.emit()
                return

    def _delete_selected(self):
        """删除所有选中的行"""
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()),
                      reverse=True)
        if not rows:
            QMessageBox.information(self, "提示", "请先选中要删除的计数行")
            return
        for r in rows:
            self.table.removeRow(r)
        self.talliesChanged.emit()

    def _add_default_tally(self):
        """添加一行默认 F4:n"""
        self._add_row("F4", 4, "n", "")
        self.talliesChanged.emit()

    # ───────── 文本模式支持 ─────────

    def _gen_tally_raw(self) -> str:
        """用当前表格数据生成计数卡文本"""
        tallies = self._collect_tallies()
        ts = TallySettings(tallies=tallies)
        return "\n".join(_generate_tallies(ts))
