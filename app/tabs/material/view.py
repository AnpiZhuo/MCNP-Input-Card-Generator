"""Material — 纯 UI 视图层"""

from collections.abc import Callable
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTableWidget, QHeaderView, QLabel, QPushButton, QScrollArea
)
from PyQt5.QtCore import Qt

from app.widgets.ui_helpers import make_add_button, make_delete_button
from app.widgets.text_mode_section import TextModeSection


class MaterialUI:
    def __init__(self):
        self.table: QTableWidget = None
        self.btn_add: QPushButton = None
        self.btn_del: QPushButton = None
        self.raw_mat: TextModeSection = None


def create_ui(parent, gen_fn: Callable[[], str]) -> MaterialUI:
    ui = MaterialUI()
    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)

    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setSpacing(16)

    grp = QGroupBox("材料定义")
    grp.setToolTip("定义模型中使用的材料组成（核素 + 份额）。\n密度在栅元卡中设置。")
    inner = QVBoxLayout(grp)
    inner.setSpacing(10)
    inner.setContentsMargins(20, 20, 20, 20)

    toolbar = QHBoxLayout()
    lbl = QLabel("材料号 — 注释")
    lbl.setStyleSheet("font-weight:600; font-size:12px;")
    toolbar.addWidget(lbl)
    toolbar.addStretch()

    ui.btn_add = make_add_button("+ 添加材料")
    ui.btn_del = make_delete_button("× 删除选中")
    toolbar.addWidget(ui.btn_add)
    toolbar.addWidget(ui.btn_del)

    inner.addLayout(toolbar)

    ui.table = QTableWidget(0, 3)
    ui.table.setHorizontalHeaderLabels(["材料号", "注释", "操作"])
    header = ui.table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.Interactive)
    header.setStretchLastSection(False)
    ui.table.setColumnWidth(0, 80)
    ui.table.setColumnWidth(1, 250)
    ui.table.setColumnWidth(2, 70)
    ui.table.setEditTriggers(QTableWidget.NoEditTriggers)
    ui.table.setSelectionBehavior(QTableWidget.SelectRows)
    ui.table.setToolTip("双击行或点击编辑按钮编辑材料核素组成。列宽可拖拽调整。")

    ui.raw_mat = TextModeSection(
        form_widget=ui.table,
        generate_fn=gen_fn,
        section_name="materials",
    )
    toolbar.insertWidget(toolbar.indexOf(ui.btn_del) + 1, ui.raw_mat.toggle_btn)
    inner.addWidget(ui.raw_mat.stack)

    tip = QLabel("💡 密度在栅元卡中设置。点击 [✎] 编辑核素组成")
    tip.setStyleSheet("font-size:12px;")
    inner.addWidget(tip)
    layout.addWidget(grp)
    layout.addStretch()
    scroll.setWidget(content)
    outer.addWidget(scroll, 1)

    return ui
