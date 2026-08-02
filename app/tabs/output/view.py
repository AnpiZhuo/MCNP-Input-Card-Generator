"""Output — 纯 UI 视图层"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QTableWidget, QHeaderView, QScrollArea,
)
from PyQt5.QtCore import Qt, QSettings

from app.widgets.ui_helpers import make_section_title
from app.widgets.reference_viewer import make_help_button


class OutputUI:
    def __init__(self):
        self.path_edit: QLineEdit = None
        self.btn_parse: QPushButton = None
        self.file_status: QLabel = None
        self.tally_combo: QComboBox = None
        self.btn_plot: QPushButton = None
        self.btn_csv: QPushButton = None
        self.btn_parquet: QPushButton = None
        self.tally_info: QLabel = None
        self.data_table: QTableWidget = None


def create_ui(parent) -> OutputUI:
    ui = OutputUI()
    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)

    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setSpacing(16)

    # ═══ 文件选择 ═══
    grp_file = QGroupBox("输出文件")
    inner_file = QVBoxLayout(grp_file)
    inner_file.setSpacing(8)
    inner_file.setContentsMargins(20, 20, 20, 20)
    file_row = QHBoxLayout()
    lbl = QLabel("选择 MCNP 输出文件")
    lbl.setStyleSheet("font-weight:600; font-size:12px;")
    file_row.addWidget(lbl)
    file_row.addStretch()
    file_row.addWidget(make_help_button(parent, "MCNP6_输出卡结构参考.md", "MCNP6 输出卡结构参考"))
    inner_file.addLayout(file_row)

    path_row = QHBoxLayout()
    ui.path_edit = QLineEdit()
    ui.path_edit.setPlaceholderText("例: D:\\MCNP\\test_run\\output.outp")
    ui.path_edit.setToolTip("MCNP 输出文件路径（.outp / .o / .out）")
    path_row.addWidget(ui.path_edit, 1)
    btn_browse = QPushButton("浏览…"); btn_browse.setToolTip("选择 MCNP 输出文件"); btn_browse.setProperty("cssClass", "btnBrowse")
    path_row.addWidget(btn_browse)
    ui.btn_parse = QPushButton("📊 解析"); ui.btn_parse.setToolTip("解析输出文件，提取所有 tally 数据"); ui.btn_parse.setProperty("cssClass", "btnPrimary")
    path_row.addWidget(ui.btn_parse)
    inner_file.addLayout(path_row)
    ui.file_status = QLabel("")
    inner_file.addWidget(ui.file_status)
    layout.addWidget(grp_file)

    # ═══ Tally 数据 ═══
    grp_tally = QGroupBox("Tally 数据")
    inner_tally = QVBoxLayout(grp_tally)
    inner_tally.setSpacing(8)
    inner_tally.setContentsMargins(20, 20, 20, 20)
    tally_row = QHBoxLayout()
    tally_row.addWidget(QLabel("Tally 编号:"))
    ui.tally_combo = QComboBox(); ui.tally_combo.setToolTip("选择要操作的 tally 编号"); ui.tally_combo.setMinimumWidth(120)
    tally_row.addWidget(ui.tally_combo)
    tally_row.addSpacing(16)
    ui.btn_plot = QPushButton("📈 绘图"); ui.btn_plot.setToolTip("使用 matplotlib 绘制选中 tally 的能谱"); ui.btn_plot.setProperty("cssClass", "btnPrimary")
    tally_row.addWidget(ui.btn_plot)
    ui.btn_csv = QPushButton("📋 导出 CSV"); ui.btn_csv.setToolTip("将选中 tally 导出为 CSV 文件")
    tally_row.addWidget(ui.btn_csv)
    ui.btn_parquet = QPushButton("📦 导出 Parquet"); ui.btn_parquet.setToolTip("将选中 tally 导出为 Parquet 文件")
    tally_row.addWidget(ui.btn_parquet)
    tally_row.addStretch()
    inner_tally.addLayout(tally_row)
    ui.tally_info = QLabel("")
    inner_tally.addWidget(ui.tally_info)
    layout.addWidget(grp_tally)

    # ═══ 数据预览 ═══
    grp_preview = QGroupBox("数据预览")
    inner_preview = QVBoxLayout(grp_preview)
    inner_preview.setSpacing(6)
    inner_preview.setContentsMargins(20, 20, 20, 20)
    ui.data_table = QTableWidget(0, 3)
    ui.data_table.setHorizontalHeaderLabels(["Bins / Energy", "Counts", "Errors"])
    hdr = ui.data_table.horizontalHeader()
    hdr.setSectionResizeMode(QHeaderView.Interactive)
    hdr.setStretchLastSection(False)
    ui.data_table.setColumnWidth(0, 200); ui.data_table.setColumnWidth(1, 150); ui.data_table.setColumnWidth(2, 150)
    ui.data_table.setEditTriggers(QTableWidget.NoEditTriggers)
    inner_preview.addWidget(ui.data_table)
    tip = QLabel("💡 支持标准 MCNP 输出文件。解析后可查看 tally 数据、绘图或导出为 CSV/Parquet。")
    tip.setStyleSheet("font-size:12px;")
    inner_preview.addWidget(tip)
    layout.addWidget(grp_preview)
    scroll.setWidget(content)
    outer.addWidget(scroll)

    return ui, btn_browse
