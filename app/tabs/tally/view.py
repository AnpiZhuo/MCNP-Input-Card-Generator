"""Tally — 纯 UI 视图层"""

from collections.abc import Callable
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTableWidget, QHeaderView, QLabel, QCheckBox,
    QLineEdit, QSpinBox, QPlainTextEdit, QFormLayout,
    QScrollArea, QComboBox, QPushButton
)
from PyQt5.QtCore import Qt, QSettings

from app.widgets.text_mode_section import TextModeSection
from app.widgets.reference_viewer import make_help_button
from app.widgets.ui_helpers import (
    make_section_title, make_add_button, make_delete_button,
    make_centered_label, make_centered_edit, make_table_checkbox,
)


class TallyUI:
    def __init__(self):
        self.table: QTableWidget = None
        self.btn_add: QPushButton = None
        self.btn_del: QPushButton = None
        self.e_min: QLineEdit = None
        self.e_max: QLineEdit = None
        self.e_bins: QSpinBox = None
        self.e_log_cb: QCheckBox = None
        self.e_custom_cb: QCheckBox = None
        self.e_custom_edit: QPlainTextEdit = None
        self.t0_min: QLineEdit = None
        self.t0_max: QLineEdit = None
        self.t0_bins: QSpinBox = None
        self.t0_log_cb: QCheckBox = None
        self.t0_custom_cb: QCheckBox = None
        self.t0_custom_edit: QPlainTextEdit = None
        self.en_container: QVBoxLayout = None
        self.en_note: QLabel = None
        self.tn_container: QVBoxLayout = None
        self.tn_note: QLabel = None


def create_ui(parent,
              gen_tally_fn: Callable[[], str],
              gen_e0_fn: Callable[[], str],
              gen_t0_fn: Callable[[], str]) -> TallyUI:
    ui = TallyUI()
    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)

    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setSpacing(16)

    grp = QGroupBox("计数卡")
    grp.setToolTip("在此定义 MCNP 计数卡。每行包含：计数类型、编号、粒子、参数。\n⚠ F5 探测器（含 FIP/FIR/FIC）总数 ≤ 20。")
    inner = QVBoxLayout(grp)
    inner.setSpacing(10)
    inner.setContentsMargins(20, 20, 20, 20)

    # 工具栏
    toolbar = QHBoxLayout()
    lbl = QLabel("类型 — 编号 — 粒子 — 参数")
    lbl.setStyleSheet("font-weight:600; font-size:12px;")
    toolbar.addWidget(lbl)
    toolbar.addWidget(make_help_button(parent, "MCNP6_FN卡结构参考.md", "MCNP6 计数卡结构参考"))
    toolbar.addStretch()

    ui.btn_add = make_add_button("+ 添加计数")
    ui.btn_del = make_delete_button("× 删除选中")
    toolbar.addWidget(ui.btn_add)
    toolbar.addWidget(ui.btn_del)
    inner.addLayout(toolbar)

    # 表格
    ui.table = QTableWidget(0, 8)
    ui.table.setHorizontalHeaderLabels(["前缀", "类型", "编号", "粒子", "参数", "En", "Tn", "操作"])
    header = ui.table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.Interactive)
    header.setStretchLastSection(False)
    header.setSectionsMovable(False)
    ui.table.setColumnWidth(0, 50)
    ui.table.setColumnWidth(1, 100)
    ui.table.setColumnWidth(2, 80)
    ui.table.setColumnWidth(3, 80)
    ui.table.setColumnWidth(4, 200)
    ui.table.setColumnWidth(5, 35)
    ui.table.setColumnWidth(6, 35)
    ui.table.setColumnWidth(7, 70)
    ui.table.setEditTriggers(QTableWidget.NoEditTriggers)
    ui.table.setSelectionBehavior(QTableWidget.SelectRows)
    ui.table.setToolTip("双击编辑参数列。粒子可输如 n p e h he。列宽可拖拽调整。")
    inner.addLayout(toolbar)

    raw_tally = TextModeSection(form_widget=ui.table, generate_fn=gen_tally_fn, section_name="tally")
    toolbar.insertWidget(toolbar.indexOf(ui.btn_del) + 1, raw_tally.toggle_btn)
    inner.addWidget(raw_tally.stack)

    tip = QLabel("💡 每个粒子输出一张 Fn 卡。如编号=15 粒子=n p 生成 F15:N 和 F15:P 两张卡。")
    tip.setStyleSheet("font-size:12px;")
    inner.addWidget(tip)
    layout.addWidget(grp)

    # ═══ 能谱网格（E0）卡片 ═══
    e0_card = QGroupBox("能谱网格")
    e0_inner = QVBoxLayout(e0_card)
    e0_inner.setSpacing(8)
    e0_inner.setContentsMargins(20, 20, 20, 20)

    e_header = QHBoxLayout()
    lbl_e = QLabel("E0 卡 — 能量网格"); lbl_e.setStyleSheet("font-weight:600; font-size:12px;")
    e_header.addWidget(lbl_e)
    e_header.addStretch()
    e0_inner.addLayout(e_header)

    e_form_container = QWidget()
    e_form = QFormLayout(e_form_container)
    e_form.setSpacing(6)
    e_form.setContentsMargins(0, 0, 0, 0)

    e_range = QHBoxLayout()
    ui.e_min = QLineEdit(""); ui.e_min.setPlaceholderText("如 0.001"); ui.e_min.setToolTip("能量网格最低值（MeV），留空不生成 E0 卡")
    ui.e_max = QLineEdit(""); ui.e_max.setPlaceholderText("如 14"); ui.e_max.setToolTip("能量网格最高值（MeV），留空不生成 E0 卡")
    e_range.addWidget(QLabel("从")); e_range.addWidget(ui.e_min); e_range.addWidget(QLabel("到")); e_range.addWidget(ui.e_max); e_range.addWidget(QLabel("MeV"))
    e_form.addRow("能量范围:", e_range)
    ui.e_bins = QSpinBox(); ui.e_bins.setRange(0, 10000); ui.e_bins.setValue(0); ui.e_bins.setSpecialValueText("不设置"); ui.e_bins.setToolTip("能量间隔数，0=不生成 E0 卡")
    e_form.addRow("间隔数:", ui.e_bins)
    ui.e_log_cb = QCheckBox("对数网格（勾选=对数，不勾=线性）")
    e_form.addRow("", ui.e_log_cb)
    ui.e_custom_cb = QCheckBox("自定义网格（手动输入能量边界，勾选后忽略上面设置）")
    e_form.addRow("", ui.e_custom_cb)
    ui.e_custom_edit = QPlainTextEdit()
    ui.e_custom_edit.setPlaceholderText("示例:\n0.001\n0.01\n0.1\n1\n10\n14")
    ui.e_custom_edit.setToolTip("每行一个能量值（MeV），从小到大排列")
    ui.e_custom_edit.setMaximumHeight(100)
    ui.e_custom_edit.setVisible(False)
    e_form.addRow("", ui.e_custom_edit)
    tip_e = QLabel("对数网格推荐：0.001~14 MeV，200 间隔")
    tip_e.setStyleSheet("font-size:12px;")
    e_form.addRow("", tip_e)

    raw_e0 = TextModeSection(form_widget=e_form_container, generate_fn=gen_e0_fn, section_name="e0")
    e_header.addWidget(raw_e0.toggle_btn)
    e0_inner.addWidget(raw_e0.stack)
    ui.en_container = QVBoxLayout()
    ui.en_note = QLabel("（勾选计数卡的 En 后在此显示生成的能量卡）")
    ui.en_note.setStyleSheet("font-size:12px;")
    ui.en_container.addWidget(ui.en_note)
    e0_inner.addLayout(ui.en_container)
    layout.addWidget(e0_card)

    # ═══ 时间网格（T0）卡片 ═══
    t0_card = QGroupBox("时间网格")
    t0_inner = QVBoxLayout(t0_card)
    t0_inner.setSpacing(8)
    t0_inner.setContentsMargins(20, 20, 20, 20)

    t0_header = QHBoxLayout()
    lbl_t0 = QLabel("T0 卡 — 时间网格"); lbl_t0.setStyleSheet("font-weight:600; font-size:12px;")
    t0_header.addWidget(lbl_t0)
    t0_header.addStretch()
    t0_inner.addLayout(t0_header)

    t0_form_container = QWidget()
    t0_form = QFormLayout(t0_form_container)
    t0_form.setSpacing(6)
    t0_form.setContentsMargins(0, 0, 0, 0)

    t0_range = QHBoxLayout()
    ui.t0_min = QLineEdit(""); ui.t0_min.setPlaceholderText("如 0"); ui.t0_min.setToolTip("时间网格起始值（shake），留空不生成 T0 卡")
    ui.t0_max = QLineEdit(""); ui.t0_max.setPlaceholderText("如 1"); ui.t0_max.setToolTip("时间网格结束值（shake）")
    t0_range.addWidget(QLabel("从")); t0_range.addWidget(ui.t0_min); t0_range.addWidget(QLabel("到")); t0_range.addWidget(ui.t0_max); t0_range.addWidget(QLabel("shake"))
    t0_form.addRow("时间范围:", t0_range)
    ui.t0_bins = QSpinBox(); ui.t0_bins.setRange(0, 10000); ui.t0_bins.setValue(0); ui.t0_bins.setSpecialValueText("不设置"); ui.t0_bins.setToolTip("时间间隔数，0=不生成 T0 卡")
    t0_form.addRow("间隔数:", ui.t0_bins)
    ui.t0_log_cb = QCheckBox("对数网格（勾选=对数，不勾=线性）")
    t0_form.addRow("", ui.t0_log_cb)
    ui.t0_custom_cb = QCheckBox("自定义网格（手动输入时间边界，勾选后忽略上面设置）")
    t0_form.addRow("", ui.t0_custom_cb)
    ui.t0_custom_edit = QPlainTextEdit()
    ui.t0_custom_edit.setPlaceholderText("示例:\n0\n1e-8\n1e-6\n1e-4\n1e-2\n1")
    ui.t0_custom_edit.setToolTip("时间网格，单位为 shake（1 shake = 10⁻⁸ s）\n每行一个时间值，从小到大排列。")
    ui.t0_custom_edit.setMaximumHeight(100)
    ui.t0_custom_edit.setVisible(False)
    t0_form.addRow("", ui.t0_custom_edit)
    tip_t0 = QLabel("💡 空 = 不生成 T0 卡。勾选计数卡的 Tn 后自动据此生成对应 Tn 卡")
    tip_t0.setStyleSheet("font-size:12px;")
    t0_form.addRow("", tip_t0)

    raw_t0 = TextModeSection(form_widget=t0_form_container, generate_fn=gen_t0_fn, section_name="t0")
    t0_header.addWidget(raw_t0.toggle_btn)
    t0_inner.addWidget(raw_t0.stack)
    ui.tn_container = QVBoxLayout()
    ui.tn_note = QLabel("（勾选计数卡的 Tn 后在此显示生成的时间卡）")
    ui.tn_note.setStyleSheet("font-size:12px;")
    ui.tn_container.addWidget(ui.tn_note)
    t0_inner.addLayout(ui.tn_container)
    layout.addWidget(t0_card)

    layout.addStretch()
    scroll.setWidget(content)
    outer.addWidget(scroll, 1)

    return ui, raw_tally, raw_e0, raw_t0


# ── 模块级工具函数（供 controller 引用） ──────────────

_TYPE_CN_NAME = {
    "F1": "曲面粒子流", "F2": "曲面平均通量",
    "F4": "栅元平均通量",
    "F5": "点/环探测器", "FIP": "针孔成像", "FIR": "平板成像", "FIC": "柱面成像",
    "F6": "能量沉积", "F7": "裂变能沉积",
    "F8": "脉冲高度谱",
}

_TYPE_DEFAULT_NUMBER = {
    "F1": 1, "F2": 2, "F4": 4, "F5": 5,
    "F6": 6, "F7": 7, "F8": 8,
}


def _type_param_placeholder(tally_type: str) -> str:
    placeholders = {
        "F1": "曲面号，如: 1 2 3", "F2": "曲面号，如: 1 2 3",
        "F4": "栅元号，如: 1 2 3",
        "F5": "点: X Y Z R0  / 环: a0 r R0",
        "F6": "栅元号，如: 1 2 3", "F7": "栅元号，如: 1 2 3",
        "F8": "栅元号，如: 1 2 3",
    }
    return placeholders.get(tally_type, "")


def _type_param_tooltip(tally_type: str) -> str:
    tips = {
        "F1": "穿过指定曲面的粒子流。曲面号可输多个，空格分隔。",
        "F2": "曲面平均通量。曲面号可输多个，空格分隔。",
        "F4": "栅元平均通量。栅元号可输多个，空格分隔。",
        "F5": "F5 探测器（总探测器数 ≤ 20，含 FIP/FIR/FIC）。\n详见参数栏参考文档。",
        "F6": "能量沉积 (MeV/g)。栅元号可输多个，空格分隔。",
        "F7": "裂变能沉积 (MeV/g)。栅元号可输多个，空格分隔。",
        "F8": "脉冲高度谱。栅元号可输多个，空格分隔。",
    }
    return tips.get(tally_type, "")


def _number_to_type(n: int) -> str | None:
    digit = n % 10
    mapping = {1: "F1", 2: "F2", 4: "F4", 5: "F5",
               6: "F6", 7: "F7", 8: "F8"}
    return mapping.get(digit)
