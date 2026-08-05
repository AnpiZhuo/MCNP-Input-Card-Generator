"""Geometry — 纯 UI 视图层"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QTableWidget, QHeaderView,
    QSplitter, QCheckBox, QScrollArea
)
from PyQt5.QtCore import Qt

from app.widgets.autocomplete_edit import AutoCompleteEdit
from app.widgets.mcnp_highlighter import MCNPSurfaceHighlighter, MCNPTRHighlighter
from app.widgets.reference_viewer import make_help_button
from app.widgets.ui_helpers import make_section_title, make_add_button, make_delete_button
from app.widgets.text_mode_section import TextModeSection
from collections.abc import Callable
from app.style import PALETTES


class GeometryUI:
    def __init__(self):
        self.surface_text: AutoCompleteEdit = None
        self.tr_text: AutoCompleteEdit = None
        self.cell_table: QTableWidget = None
        self._surf_hl: MCNPSurfaceHighlighter = None
        self._tr_hl: MCNPTRHighlighter = None
        self.btn_add_cell: QPushButton = None
        self.btn_del_cell: QPushButton = None
        self.btn_import_step: QPushButton = None
        self.btn_3d: QPushButton = None
        self.btn_export_step: QPushButton = None
        self.btn_render_ctrl: QPushButton = None
        self.btn_cross_section: QPushButton = None
        self.lbl_step_warn: QLabel = None


def create_ui(parent, main_window,
              gen_cell_fn: Callable[[], str] = lambda: "") -> GeometryUI:
    ui = GeometryUI()

    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)

    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setSpacing(16)

    grp_surf = QGroupBox("曲面与 TR 卡")
    grp_surf.setToolTip("左：曲面定义（每行一个）\n右：TRn 坐标变换卡")
    surf_title_layout = QVBoxLayout(grp_surf)
    surf_title_layout.setSpacing(10)
    surf_title_layout.setContentsMargins(20, 20, 20, 20)

    # 标题栏
    surf_header = QHBoxLayout()
    lbl_surf = QLabel("曲面与 TR 卡"); lbl_surf.setStyleSheet("font-weight:600; font-size:12px;")
    surf_header.addWidget(lbl_surf)
    surf_header.addWidget(make_help_button(parent, "MCNP6_曲面卡格式参考.md", "MCNP6 曲面卡格式参考"))
    surf_header.addStretch()
    surf_title_layout.addLayout(surf_header)

    # 水平分割
    h_split = QSplitter(Qt.Horizontal)

    # 左：曲面卡
    left_widget = QWidget()
    left_layout = QVBoxLayout(left_widget)
    left_layout.setContentsMargins(0, 0, 0, 0)
    lbl_left = QLabel("曲面卡"); lbl_left.setStyleSheet("font-weight:600; font-size:12px;")
    left_layout.addWidget(lbl_left)
    hint_left = QLabel("曲面号  类型  参数 ...")
    hint_left.setStyleSheet("font-family:Consolas,monospace; font-size:11px;")
    left_layout.addWidget(hint_left)

    ui.surface_text = AutoCompleteEdit()
    ui.surface_text.setObjectName("surfaceEditor")
    ui.surface_text.setToolTip("每行一个曲面，支持所有 MCNP 曲面类型。键入时自动补全，灰字为参数提示")
    ui.surface_text.setMinimumHeight(400)
    _theme_colors = PALETTES.get(getattr(main_window, 'theme_mode', 'light'), PALETTES['light'])
    ui._surf_hl = MCNPSurfaceHighlighter(ui.surface_text.document(), colors=_theme_colors)
    left_layout.addWidget(ui.surface_text)
    tip_surf = QLabel("💡 建议曲面号大于 100，栅元号小于 100")
    tip_surf.setStyleSheet("font-size:12px;")
    left_layout.addWidget(tip_surf)
    h_split.addWidget(left_widget)

    # 右：TR 卡
    right_widget = QWidget()
    right_layout = QVBoxLayout(right_widget)
    right_layout.setContentsMargins(0, 0, 0, 0)
    lbl_tr = QLabel("TR 变换卡"); lbl_tr.setStyleSheet("font-weight:600; font-size:12px;")
    right_layout.addWidget(lbl_tr)
    hint_tr = QLabel("*TRn  Tx Ty Tz  B1..B9  [M]")
    hint_tr.setStyleSheet("font-family:Consolas,monospace; font-size:11px;")
    right_layout.addWidget(hint_tr)

    ui.tr_text = AutoCompleteEdit()
    ui.tr_text.setObjectName("trEditor")
    ui.tr_text.setToolTip("TRn 坐标变换卡。键入时自动补全")
    ui.tr_text.setMinimumHeight(400)
    ui._tr_hl = MCNPTRHighlighter(ui.tr_text.document(), colors=_theme_colors)
    right_layout.addWidget(ui.tr_text)
    h_split.addWidget(right_widget)

    h_split.setSizes([600, 400])
    surf_title_layout.addWidget(h_split, 1)

    # 按钮行
    btn_row = QHBoxLayout()
    ui.lbl_step_warn = QLabel("✅ GEOUNED 已就绪")
    ui.lbl_step_warn.setStyleSheet("font-size:12px;")
    btn_row.addWidget(ui.lbl_step_warn)
    ui.btn_import_step = QPushButton("📥 导入 STEP")
    ui.btn_import_step.setToolTip("使用 GEOUNED 转换 STEP → MCNP 输入卡")
    btn_row.addWidget(ui.btn_import_step)
    ui.btn_3d = QPushButton("🔍 3D 预览")
    ui.btn_3d.setToolTip("基于当前曲面和栅元定义打开 3D 几何预览窗口")
    ui.btn_3d.setProperty("cssClass", "btnPrimary")
    btn_row.addWidget(ui.btn_3d)
    ui.btn_export_step = QPushButton("📐 导出 STEP")
    ui.btn_export_step.setToolTip("将每个栅元导出为 STEP 实体模型")
    btn_row.addWidget(ui.btn_export_step)
    ui.btn_render_ctrl = QPushButton("🎨 渲染控制")
    ui.btn_render_ctrl.setToolTip("打开渲染控制窗口（批量设色、显隐控制）")
    btn_row.addWidget(ui.btn_render_ctrl)
    ui.btn_cross_section = QPushButton("✂ 生成截面")
    ui.btn_cross_section.setToolTip("打开截面窗口查看几何截面")
    btn_row.addWidget(ui.btn_cross_section)
    btn_row.addStretch()
    surf_title_layout.addLayout(btn_row)

    layout.addWidget(grp_surf)

    # ═══ 栅元卡 ═══
    grp_cell = QGroupBox("栅元卡")
    inner_cell = QVBoxLayout(grp_cell)
    inner_cell.setSpacing(8)
    inner_cell.setContentsMargins(20, 20, 20, 20)

    cell_toolbar = QHBoxLayout()
    cell_toolbar.addWidget(QLabel("栅元列表:"))
    cell_toolbar.addStretch()
    ui.btn_add_cell = make_add_button("+ 添加栅元")
    ui.btn_del_cell = make_delete_button("× 删除选中")
    cell_toolbar.addWidget(ui.btn_add_cell)
    cell_toolbar.addWidget(ui.btn_del_cell)
    inner_cell.addLayout(cell_toolbar)

    ui.cell_table = QTableWidget(0, 6)
    ui.cell_table.setHorizontalHeaderLabels(["栅元号", "材料号", "密度", "IMP:N", "注释", "操作"])
    hdr = ui.cell_table.horizontalHeader()
    hdr.setSectionResizeMode(QHeaderView.Interactive)
    hdr.setStretchLastSection(False)
    ui.cell_table.setColumnWidth(0, 80); ui.cell_table.setColumnWidth(1, 80)
    ui.cell_table.setColumnWidth(2, 80); ui.cell_table.setColumnWidth(3, 60)
    ui.cell_table.setColumnWidth(4, 200); ui.cell_table.setColumnWidth(5, 60)
    ui.cell_table.setEditTriggers(QTableWidget.NoEditTriggers)
    ui.cell_table.setSelectionBehavior(QTableWidget.SelectRows)

    raw_cell = TextModeSection(
        form_widget=ui.cell_table,
        generate_fn=gen_cell_fn,
        section_name="cells",
    )
    cell_toolbar.insertWidget(cell_toolbar.indexOf(ui.btn_del_cell) + 1, raw_cell.toggle_btn)
    inner_cell.addWidget(raw_cell.stack)
    layout.addWidget(grp_cell)
    ui._raw_cell = raw_cell

    layout.addStretch()
    scroll.setWidget(content)
    outer.addWidget(scroll, 1)

    return ui
