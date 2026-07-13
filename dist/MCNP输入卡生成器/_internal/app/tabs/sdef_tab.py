"""
🎯 源项标签页：固定点源（多源列表）+ 分布源（SDEF 字段 + SI/SP 对）
通过 QStackedWidget 切换两种模式
Source Definition Tab: Fixed point sources (multi-source list) + Distribution source (SDEF fields + SI/SP pairs)
Switches between two modes via QStackedWidget

This module provides the SdefTab widget for configuring MCNP particle sources.
Two modes are available:
1. Fixed point source mode: table-based management of multiple discrete sources
2. Distribution source mode: SDEF parameter fields with auto-generated SI/SP distribution pairs

The tab supports automatic Dn reference detection: when users type D1/D2/... in SDEF fields,
corresponding SI/SP card pairs are automatically created.
"""

import json
import re

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTableWidget, QTableWidgetItem, QPushButton,
    QHeaderView, QLabel, QMessageBox, QScrollArea,
    QStackedWidget, QLineEdit, QComboBox, QFormLayout,
)
from PyQt5.QtCore import Qt, QSettings

from app.models import SourceData, AdvancedSettings
from app.dialogs.source_edit_dialog import SourceEditDialog
from app.widgets.text_mode_section import TextModeSection
from app.generator.inp_generator import _generate_sdef, _generate_distribution_sdef


class SdefTab(QWidget):
    """源项标签页 / Source Definition Tab

    Manages MCNP source definitions (SDEF card) in two modes:

    Fixed Point Source Mode:
    - Table listing multiple sources with particle type, energy, position, and weight
    - Dialog-based editing via SourceEditDialog
    - Supports sources with different probabilities for sampling ratios

    Distribution Source Mode:
    - SDEF parameter fields (PAR, ERG, POS, WGT, DIR, VEC, etc.)
    - Collapsible extra parameters (SUR, NRM, TR, CCC, ARA, RATE)
    - Auto-generated SI/SP distribution pairs based on Dn references
    - Manual SI/SP pair addition with type hints (L, H, A, S, Q, F, T)

    The two modes are switched via a QStackedWidget with a toggle button.
    """

    def __init__(self):
        """Initialize the source definition tab."""
        super().__init__()
        self.fixed_sources: list[SourceData] = []
        # Distribution source mode: list of SI/SP pair dictionaries
        # Each item: {"frame": QGroupBox, "si": QLineEdit, "sp": QLineEdit,
        #             "ref_index": int, "ref_param": str, "auto": bool}
        self.dist_pairs: list[dict] = []
        self.init_ui()

    def init_ui(self):
        """Build the complete source definition tab UI.

        Creates a scrollable layout containing:
        - Mode toggle toolbar (fixed source <-> distribution source)
        - QStackedWidget with two pages (fixed table, distribution form)
        - Hint text that updates based on current mode
        """
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)

        # ===== GroupBox =====
        grp = QGroupBox("源定义（SDEF）")
        grp.setToolTip(
            "定义粒子源。固定点源模式支持多源列表；"
            "分布源模式支持 SDEF 字段 + SI/SP 分布卡。"
        )
        inner = QVBoxLayout(grp)

        # ===== Toolbar with mode selector and actions =====
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("<span style='font-weight:bold;'>源模式：</span>"))

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["固定点源", "分布源", "KCODE 临界源"])
        self.mode_combo.setToolTip(
            "选择源定义模式：\n"
            "固定点源 — 离散多源列表\n"
            "分布源 — SDEF 字段 + SI/SP 分布卡\n"
            "KCODE 临界源 — 裂变链计算（KCODE + KSRC，不输出 SDEF）"
        )
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        toolbar.addWidget(self.mode_combo)

        # Text mode toggle button
        self._raw_sdef = TextModeSection(
            form_widget=QWidget(),
            generate_fn=self._gen_sdef_raw,
            section_name="sdef",
        )
        toolbar.addWidget(self._raw_sdef.toggle_btn)

        toolbar.addStretch()

        self.btn_add = QPushButton("+ 添加源")
        self.btn_add.setToolTip("新增一个源（固定点源模式）")
        self.btn_add.setProperty("cssClass", "btnAdd")
        self.btn_add.clicked.connect(self._add_source)

        self.btn_del = QPushButton("× 删除选中")
        self.btn_del.setToolTip("删除选中的源")
        self.btn_del.setProperty("cssClass", "btnDelete")
        self.btn_del.clicked.connect(self._delete_source)

        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_del)
        inner.addLayout(toolbar)

        # ===== QStackedWidget for mode switching =====
        self.stack = QStackedWidget()
        self.page_fixed = self._build_fixed_page()
        self.page_dist = self._build_distribution_page()
        self.page_kcode = self._build_kcode_page()
        self.stack.addWidget(self.page_fixed)     # index 0
        self.stack.addWidget(self.page_dist)      # index 1
        self.stack.addWidget(self.page_kcode)     # index 2
        self.stack.setCurrentIndex(0)             # fixed mode default

        # Wrap in TextModeSection for raw text editing support
        self._raw_sdef.stack.removeWidget(self._raw_sdef.stack.widget(0))
        self._raw_sdef.stack.insertWidget(0, self.stack)
        inner.addWidget(self._raw_sdef.stack, 1)
        self._raw_sdef.stack.setCurrentIndex(0)  # 强制表单模式
        layout.addWidget(grp)

        # ===== Context-sensitive hint label =====
        self.hint = QLabel("")
        self.hint.setTextFormat(Qt.RichText)
        self._update_hint_text(0)
        layout.addWidget(self.hint)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ---------- UI 构建 ----------

    def _build_fixed_page(self) -> QWidget:
        """固定点源模式：表格 / Build fixed point source mode page with table.

        Returns:
            QWidget: Page widget containing the source table.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["源#", "粒子(PAR)", "能量(MeV)", "位置", "权重", "操作"]
        )
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setStretchLastSection(False)
        self._src_settings = QSettings("MCNPGen", "MCNPGenerator")
        saved = self._src_settings.value("sdef_src_col_widths")
        if saved and len(saved) == 6:
            for col, w in enumerate(saved):
                self.table.setColumnWidth(col, int(w))
        else:
            self.table.setColumnWidth(0, 40)
            self.table.setColumnWidth(1, 120)
            self.table.setColumnWidth(2, 100)
            self.table.setColumnWidth(3, 160)
            self.table.setColumnWidth(4, 60)
            self.table.setColumnWidth(5, 70)
        hdr.sectionResized.connect(self._save_src_col_widths)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setToolTip("双击行或点击编辑按钮编辑源参数")
        layout.addWidget(self.table)
        return page

    def _build_distribution_page(self) -> QWidget:
        """分布源模式：SDEF 字段 + 可折叠额外参数 + SI/SP 对 / Build distribution source mode page.

        Creates a comprehensive distribution source form with:
        - Fixed SDEF parameter fields (always visible)
        - Collapsible extra parameter section
        - Dynamic SI/SP distribution card list

        Returns:
            QWidget: Page widget containing the distribution source form.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ── SDEF 字段（基础参数始终可见）/ SDEF Fields (always visible) ──
        fixed_grp = QGroupBox("SDEF 参数（键入 D1/D2/… 自动生成 SI/SP 分布卡）")
        fixed_grid = QVBoxLayout(fixed_grp)
        fixed_grid.setSpacing(4)

        # Row 1: PAR, ERG, POS(x,y,z), WGT, CEL
        row1 = QHBoxLayout()
        row1.setSpacing(4)

        row1.addWidget(QLabel("<b>PAR:</b>"))
        self.sdef_par = QLineEdit()
        self.sdef_par.setPlaceholderText("例: 1 或 D1")
        self.sdef_par.setMaximumWidth(100)
        self.sdef_par.textChanged.connect(self._on_sdef_field_changed)
        row1.addWidget(self.sdef_par)

        row1.addWidget(QLabel("<b>ERG:</b>"))
        self.sdef_erg = QLineEdit()
        self.sdef_erg.setPlaceholderText("例: 14 或 D2")
        self.sdef_erg.setMaximumWidth(100)
        self.sdef_erg.textChanged.connect(self._on_sdef_field_changed)
        row1.addWidget(self.sdef_erg)

        # Position coordinates (X, Y, Z)
        row1.addWidget(QLabel("<b>POS:</b>"))
        self.sdef_pos_x = QLineEdit()
        self.sdef_pos_x.setPlaceholderText("x")
        self.sdef_pos_x.setMaximumWidth(60)
        row1.addWidget(self.sdef_pos_x)
        self.sdef_pos_y = QLineEdit()
        self.sdef_pos_y.setPlaceholderText("y")
        self.sdef_pos_y.setMaximumWidth(60)
        row1.addWidget(self.sdef_pos_y)
        self.sdef_pos_z = QLineEdit()
        self.sdef_pos_z.setPlaceholderText("z")
        self.sdef_pos_z.setMaximumWidth(60)
        row1.addWidget(self.sdef_pos_z)

        row1.addWidget(QLabel("<b>WGT:</b>"))
        self.sdef_wgt = QLineEdit()
        self.sdef_wgt.setPlaceholderText("例: 1")
        self.sdef_wgt.setMaximumWidth(80)
        self.sdef_wgt.textChanged.connect(self._on_sdef_field_changed)
        row1.addWidget(self.sdef_wgt)

        row1.addWidget(QLabel("<b>CEL:</b>"))
        self.sdef_cel = QLineEdit()
        self.sdef_cel.setPlaceholderText("栅元")
        self.sdef_cel.setMaximumWidth(80)
        self.sdef_cel.textChanged.connect(self._on_sdef_field_changed)
        row1.addWidget(self.sdef_cel)

        row1.addStretch()
        fixed_grid.addLayout(row1)

        # Row 2: DIR, TME, VEC, AXS, RAD, EXT
        row2 = QHBoxLayout()
        row2.setSpacing(4)

        row2.addWidget(QLabel("DIR:"))
        self.sdef_dir = QLineEdit()
        self.sdef_dir.setPlaceholderText("方向")
        self.sdef_dir.setMaximumWidth(80)
        self.sdef_dir.textChanged.connect(self._on_sdef_field_changed)
        row2.addWidget(self.sdef_dir)

        row2.addWidget(QLabel("TME:"))
        self.sdef_tme = QLineEdit()
        self.sdef_tme.setPlaceholderText("时间")
        self.sdef_tme.setMaximumWidth(80)
        self.sdef_tme.textChanged.connect(self._on_sdef_field_changed)
        row2.addWidget(self.sdef_tme)

        row2.addWidget(QLabel("VEC:"))
        self.sdef_vec = QLineEdit()
        self.sdef_vec.setPlaceholderText("x y z")
        self.sdef_vec.setMaximumWidth(150)
        self.sdef_vec.textChanged.connect(self._on_sdef_field_changed)
        row2.addWidget(self.sdef_vec)

        row2.addWidget(QLabel("AXS:"))
        self.sdef_axs = QLineEdit()
        self.sdef_axs.setPlaceholderText("轴")
        self.sdef_axs.setMaximumWidth(80)
        row2.addWidget(self.sdef_axs)

        row2.addWidget(QLabel("RAD:"))
        self.sdef_rad = QLineEdit()
        self.sdef_rad.setPlaceholderText("径向")
        self.sdef_rad.setMaximumWidth(80)
        row2.addWidget(self.sdef_rad)

        row2.addWidget(QLabel("EXT:"))
        self.sdef_ext = QLineEdit()
        self.sdef_ext.setPlaceholderText("轴向")
        self.sdef_ext.setMaximumWidth(80)
        row2.addWidget(self.sdef_ext)

        row2.addStretch()
        fixed_grid.addLayout(row2)

        # ── 折叠额外参数（SUR / NRM / TR / CCC / ARA / RATE）/ Collapsible Extra Parameters ──
        self.btn_extra = QPushButton("▼ 额外参数")
        self.btn_extra.setToolTip("点击展开/收起 SUR、NRM、TR、CCC、ARA、RATE")
        self.btn_extra.setStyleSheet("QPushButton { text-align: left; padding: 2px 8px; }")
        self.btn_extra.setCheckable(True)
        self.btn_extra.clicked.connect(self._toggle_extra_params)

        self.extra_widget = QWidget()
        self.extra_widget.setVisible(False)
        extra_layout = QVBoxLayout(self.extra_widget)
        extra_layout.setContentsMargins(8, 4, 0, 4)
        extra_layout.setSpacing(4)

        # Row 3a: SUR, NRM, TR
        extra_row1 = QHBoxLayout()
        extra_row1.setSpacing(4)
        extra_row1.addWidget(QLabel("SUR:"))
        self.sdef_sur = QLineEdit()
        self.sdef_sur.setPlaceholderText("曲面源")
        self.sdef_sur.setMaximumWidth(100)
        self.sdef_sur.textChanged.connect(self._on_sdef_field_changed)
        extra_row1.addWidget(self.sdef_sur)

        extra_row1.addWidget(QLabel("NRM:"))
        self.sdef_nrm = QLineEdit()
        self.sdef_nrm.setPlaceholderText("曲面法线")
        self.sdef_nrm.setMaximumWidth(100)
        self.sdef_nrm.textChanged.connect(self._on_sdef_field_changed)
        extra_row1.addWidget(self.sdef_nrm)

        extra_row1.addWidget(QLabel("TR:"))
        self.sdef_tr = QLineEdit()
        self.sdef_tr.setPlaceholderText("变换")
        self.sdef_tr.setMaximumWidth(100)
        self.sdef_tr.textChanged.connect(self._on_sdef_field_changed)
        extra_row1.addWidget(self.sdef_tr)

        extra_row1.addStretch()
        extra_layout.addLayout(extra_row1)

        # Row 3b: CCC, ARA, RATE
        extra_row2 = QHBoxLayout()
        extra_row2.setSpacing(4)
        extra_row2.addWidget(QLabel("CCC:"))
        self.sdef_ccc = QLineEdit()
        self.sdef_ccc.setPlaceholderText("Cookie-cutter")
        self.sdef_ccc.setMaximumWidth(100)
        self.sdef_ccc.textChanged.connect(self._on_sdef_field_changed)
        extra_row2.addWidget(self.sdef_ccc)

        extra_row2.addWidget(QLabel("ARA:"))
        self.sdef_ara = QLineEdit()
        self.sdef_ara.setPlaceholderText("点探测器归一化")
        self.sdef_ara.setMaximumWidth(100)
        self.sdef_ara.textChanged.connect(self._on_sdef_field_changed)
        extra_row2.addWidget(self.sdef_ara)

        extra_row2.addWidget(QLabel("RATE:"))
        self.sdef_rate = QLineEdit()
        self.sdef_rate.setPlaceholderText("源强度")
        self.sdef_rate.setMaximumWidth(100)
        self.sdef_rate.textChanged.connect(self._on_sdef_field_changed)
        extra_row2.addWidget(self.sdef_rate)

        extra_row2.addStretch()
        extra_layout.addLayout(extra_row2)

        fixed_grid.addWidget(self.btn_extra)
        fixed_grid.addWidget(self.extra_widget)
        layout.addWidget(fixed_grp)

        # ── SI/SP 对列表 / SI/SP Pair List ──
        sisp_grp = QGroupBox("SI/SP 分布卡")
        sisp_layout = QVBoxLayout(sisp_grp)

        si_hint = QLabel(
            "<span style='color:#888; font-size:10px;'>"
            "SI 类型: L=离散列表  H=连续均匀  A=解析函数  S=分布号  "
            "Q=用户概率  F=内置函数  T=表格</span>"
        )
        sisp_layout.addWidget(si_hint)

        # Container for dynamically added SI/SP pair cards
        self.sisp_container = QVBoxLayout()
        sisp_layout.addLayout(self.sisp_container)

        btn_add_sisp = QPushButton("＋ 添加分布")
        btn_add_sisp.setToolTip("手动添加一个 SI/SP 对（Dn 编号自动分配）")
        btn_add_sisp.clicked.connect(self._add_sisp_pair)
        sisp_layout.addWidget(btn_add_sisp)

        layout.addWidget(sisp_grp, 1)
        return page

    def _build_kcode_page(self) -> QWidget:
        """KCODE 临界源模式页面 / Build KCODE/KSRC criticality source page.

        KCODE: NSRC RKK IKZ KCT [KNRM]
        KSRC:  x y z coordinates table

        Returns:
            QWidget: Page widget containing KCODE fields and KSRC table.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ── KCODE 参数 / KCODE Parameters ──
        kcode_grp = QGroupBox("KCODE 参数（临界源设置）")
        kcode_form = QFormLayout(kcode_grp)
        kcode_form.setSpacing(6)

        self.kcode_nsrc = QLineEdit()
        self.kcode_nsrc.setPlaceholderText("如: 50000")
        self.kcode_nsrc.setToolTip("每代粒子数（Number of source histories per generation）")
        kcode_form.addRow("NSRC（每代粒子数）:", self.kcode_nsrc)

        self.kcode_rkk = QLineEdit()
        self.kcode_rkk.setPlaceholderText("如: 1.0")
        self.kcode_rkk.setToolTip("初始 keff 估计（Initial keff guess）")
        kcode_form.addRow("RKK（初始 keff）:", self.kcode_rkk)

        self.kcode_ikz = QLineEdit()
        self.kcode_ikz.setPlaceholderText("如: 50")
        self.kcode_ikz.setToolTip("非活跃代数（Number of inactive generations）")
        kcode_form.addRow("IKZ（非活跃代数）:", self.kcode_ikz)

        self.kcode_kct = QLineEdit()
        self.kcode_kct.setPlaceholderText("如: 200")
        self.kcode_kct.setToolTip("活跃代数（Number of active generations）")
        kcode_form.addRow("KCT（总代数）:", self.kcode_kct)

        self.kcode_knrm = QLineEdit()
        self.kcode_knrm.setPlaceholderText("可选，如 0 或 1")
        self.kcode_knrm.setToolTip("归一化选项：0=归一化到 NSRC，1=按实际粒子数（可选）")
        kcode_form.addRow("KNRM（归一化，可选）:", self.kcode_knrm)

        layout.addWidget(kcode_grp)

        # ── KSRC 坐标点表格 / KSRC Coordinate Points ──
        ksrc_grp = QGroupBox("KSRC 初始裂变点（坐标表格）")
        ksrc_layout = QVBoxLayout(ksrc_grp)

        ksrc_toolbar = QHBoxLayout()
        ksrc_toolbar.addWidget(QLabel(
            "<span style='color:#5f6368;'>X Y Z 裂变起始点坐标</span>"
        ))
        ksrc_toolbar.addStretch()
        self.btn_ksrc_add = QPushButton("+ 添加点")
        self.btn_ksrc_add.setToolTip("添加一个裂变起始点坐标")
        self.btn_ksrc_add.clicked.connect(self._add_ksrc_point)
        ksrc_toolbar.addWidget(self.btn_ksrc_add)

        self.btn_ksrc_del = QPushButton("× 删除选中")
        self.btn_ksrc_del.setToolTip("删除选中的裂变起始点")
        self.btn_ksrc_del.clicked.connect(self._delete_ksrc_points)
        ksrc_toolbar.addWidget(self.btn_ksrc_del)
        ksrc_layout.addLayout(ksrc_toolbar)

        self.ksrc_table = QTableWidget(0, 3)
        self.ksrc_table.setHorizontalHeaderLabels(["X", "Y", "Z"])
        hdr = self.ksrc_table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setStretchLastSection(False)
        self._ksrc_settings = QSettings("MCNPGen", "MCNPGenerator")
        saved = self._ksrc_settings.value("ksrc_col_widths")
        if saved and len(saved) == 3:
            for col, w in enumerate(saved):
                self.ksrc_table.setColumnWidth(col, int(w))
        else:
            self.ksrc_table.setColumnWidth(0, 120)
            self.ksrc_table.setColumnWidth(1, 120)
            self.ksrc_table.setColumnWidth(2, 120)
        hdr.sectionResized.connect(self._save_ksrc_col_widths)
        self.ksrc_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ksrc_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ksrc_table.setToolTip("KSRC 裂变起始点坐标（多行 = 多点）。列宽可拖拽调整。")
        ksrc_layout.addWidget(self.ksrc_table)

        ksrc_hint = QLabel(
            "<span style='color:gray; font-size:11px;'>"
            "💡 KSRC 定义初始裂变点位置，需位于裂变材料栅元内。"
            "多行定义多个起始点。</span>"
        )
        ksrc_layout.addWidget(ksrc_hint)
        layout.addWidget(ksrc_grp, 1)
        return page

    def _save_src_col_widths(self):
        """固定源表列宽自动保存"""
        widths = [self.table.columnWidth(c) for c in range(self.table.columnCount())]
        self._src_settings.setValue("sdef_src_col_widths", widths)

    def _save_ksrc_col_widths(self):
        """KSRC 表列宽自动保存"""
        widths = [self.ksrc_table.columnWidth(c) for c in range(self.ksrc_table.columnCount())]
        self._ksrc_settings.setValue("ksrc_col_widths", widths)

    # ───────── KSRC 操作 ─────────

    def _add_ksrc_point(self, x: str = "", y: str = "", z: str = ""):
        """Add a KSRC coordinate point row to the table."""
        row = self.ksrc_table.rowCount()
        self.ksrc_table.insertRow(row)
        self.ksrc_table.setItem(row, 0, QTableWidgetItem(x))
        self.ksrc_table.setItem(row, 1, QTableWidgetItem(y))
        self.ksrc_table.setItem(row, 2, QTableWidgetItem(z))

    def _delete_ksrc_points(self):
        """Delete selected KSRC coordinate rows."""
        rows = sorted(set(idx.row() for idx in self.ksrc_table.selectedIndexes()),
                      reverse=True)
        if not rows:
            QMessageBox.information(self, "提示", "请先选中要删除的裂变点")
            return
        for r in rows:
            self.ksrc_table.removeRow(r)

    def _update_hint_text(self, mode_index: int):
        """Update the hint label text based on current mode.

        Args:
            mode_index: 0=fixed, 1=distribution, 2=kcode
        """
        hints = {
            0: "💡 多个源时，每个源的「概率」参数决定抽样比例。"
               "例如 2 个源各 50% 则各占一半。",
            1: "💡 分布源模式：上方设置 SDEF 固定参数，下方编辑 SI/SP 分布卡。"
               "键入 D1/D2/… 自动生成对应的 SI/SP 行。",
            2: "💡 KCODE 临界源模式：不输出 SDEF 卡，改为 KCODE + KSRC 卡。"
               "用于裂变链临界计算。NSRC = 每代粒子数，IKZ = 非活跃代数，KCT = 总代数。",
        }
        text = hints.get(mode_index, "")
        self.hint.setText(
            f"<span style='color:#5f6368; font-size:12px;'>{text}</span>"
        )

    # ---------- 内部操作：固定点源 ----------

    def _refresh_table(self):
        """Refresh the fixed source table display.

        Rebuilds all table rows from the current fixed_sources list.
        Shows source number, particle type label, energy, position, weight, and edit button.
        """
        par_labels = {"1": "1-中子", "2": "2-光子", "3": "3-电子",
                      "H": "H-质子", "A": "A-α粒子", "S": "S-裂片"}
        self.table.setRowCount(len(self.fixed_sources))
        for i, src in enumerate(self.fixed_sources):
            self.table.setItem(i, 0, QTableWidgetItem(str(src.number)))
            self.table.setItem(i, 1, QTableWidgetItem(
                par_labels.get(src.par, src.par)
            ))
            self.table.setItem(i, 2, QTableWidgetItem(src.erg))
            pos = f"{src.pos_x} {src.pos_y} {src.pos_z}"
            self.table.setItem(i, 3, QTableWidgetItem(pos))
            self.table.setItem(i, 4, QTableWidgetItem(src.wgt))

            btn_edit = QPushButton("✎ 编辑")
            btn_edit.setToolTip("编辑此源的详细参数")
            btn_edit.setProperty("cssClass", "btnEdit")
            btn_edit.clicked.connect(lambda checked, idx=i: self._edit_source(idx))
            self.table.setCellWidget(i, 5, btn_edit)

    def _next_source_number(self) -> int:
        """Get the next available source number.

        Returns:
            int: Highest existing source number + 1, or 1 if none exist.
        """
        if not self.fixed_sources:
            return 1
        return max(s.number for s in self.fixed_sources) + 1

    def _add_source(self):
        """Add a new fixed point source with auto-assigned number."""
        new_num = self._next_source_number()
        src = SourceData(number=new_num)
        self.fixed_sources.append(src)
        self._refresh_table()

    def _delete_source(self):
        """Delete selected fixed point sources from the table."""
        rows = set()
        for idx in self.table.selectedIndexes():
            rows.add(idx.row())
        if not rows:
            QMessageBox.information(self, "提示", "请先选中要删除的源")
            return
        for row in sorted(rows, reverse=True):
            if 0 <= row < len(self.fixed_sources):
                del self.fixed_sources[row]
        self._refresh_table()

    def _edit_source(self, idx: int):
        """Open the source edit dialog for a fixed point source.

        Args:
            idx: Index of the source in self.fixed_sources list.
        """
        if idx < 0 or idx >= len(self.fixed_sources):
            return
        dialog = SourceEditDialog(self.fixed_sources[idx], self)
        if dialog.exec_() == SourceEditDialog.Accepted:
            self.fixed_sources[idx] = dialog.get_data()
            self._refresh_table()

    # ---------- 分布源：Dn 检测 ----------

    def _toggle_extra_params(self):
        """Toggle visibility of the extra SDEF parameters section."""
        visible = self.btn_extra.isChecked()
        self.extra_widget.setVisible(visible)
        self.btn_extra.setText("▲ 收起额外参数" if visible else "▼ 额外参数")

    def _get_all_d_refs(self) -> list[tuple[int, str]]:
        """扫描所有 SDEF 字段，提取 Dn 引用 / Scan all SDEF fields and extract Dn references.

        Looks for patterns like D1, D2, etc. in all SDEF parameter values.
        Returns unique references sorted by index.

        Returns:
            list[tuple[int, str]]: List of (reference_number, parameter_name) pairs.
        """
        pos_val = f"{self.sdef_pos_x.text()} {self.sdef_pos_y.text()} {self.sdef_pos_z.text()}"
        fields = [
            ("PAR", self.sdef_par.text()),
            ("ERG", self.sdef_erg.text()),
            ("WGT", self.sdef_wgt.text()),
            ("DIR", self.sdef_dir.text()),
            ("CEL", self.sdef_cel.text()),
            ("TME", self.sdef_tme.text()),
            ("VEC", self.sdef_vec.text()),
            ("AXS", self.sdef_axs.text()),
            ("RAD", self.sdef_rad.text()),
            ("EXT", self.sdef_ext.text()),
            ("POS", pos_val),
            ("SUR", self.sdef_sur.text()),
            ("NRM", self.sdef_nrm.text()),
            ("TR", self.sdef_tr.text()),
            ("CCC", self.sdef_ccc.text()),
            ("ARA", self.sdef_ara.text()),
            ("RATE", self.sdef_rate.text()),
        ]
        seen = set()
        refs = []
        for name, val in fields:
            m = re.search(r'D(\d+)', val)
            if m:
                n = int(m.group(1))
                if n not in seen:
                    seen.add(n)
                    refs.append((n, name))
        refs.sort(key=lambda x: x[0])
        return refs

    def _on_sdef_field_changed(self):
        """SDEF 字段变化时自动同步 SI/SP 对 / Auto-sync SI/SP pairs when SDEF fields change.

        Connected to textChanged signals of all SDEF fields.
        Triggers ensure_sisp_pairs to add/remove SI/SP pairs as needed.
        """
        self._ensure_sisp_pairs()

    def _ensure_sisp_pairs(self):
        """根据 Dn 引用创建/移除 SI/SP 行 / Create or remove SI/SP rows based on Dn references.

        Scans all SDEF fields for Dn references, then:
        - Creates new SI/SP cards for new references
        - Removes auto-generated cards for deleted references
        - Updates labels for existing cards when parameter names change
        """
        refs = self._get_all_d_refs()
        ref_indices = {r[0] for r in refs}
        ref_map = dict(refs)

        # Collect currently existing ref_index values
        existing = {p["ref_index"]: p for p in self.dist_pairs}

        # Remove auto-generated pairs that are no longer referenced
        for p in list(self.dist_pairs):
            if p["auto"] and p["ref_index"] not in ref_indices:
                self.dist_pairs.remove(p)
                p["frame"].deleteLater()

        # Update labels for existing pairs, create new ones as needed
        for n, param in refs:
            if n in existing:
                if existing[n]["ref_param"] != param:
                    existing[n]["ref_param"] = param
                    existing[n]["frame"].setTitle(f"分布 D{n}（{param}）")
            else:
                self._create_sisp_card(n, param)

    def _create_sisp_card(self, index: int, param: str):
        """创建一个 SI/SP 卡片 / Create an SI/SP card widget.

        Creates a group box containing:
        - SI line edit (with placeholder showing the SI type hints)
        - SP line edit
        - Delete button

        Args:
            index: The Dn reference index (e.g., 1 for D1).
            param: The SDEF parameter name that references this distribution.
        """
        frame = QGroupBox(f"分布 D{index}（{param}）")
        h = QHBoxLayout(frame)
        h.setContentsMargins(8, 4, 8, 4)

        si_edit = QLineEdit()
        si_edit.setPlaceholderText(f"SI{index}  L  N  P")
        si_edit.setToolTip(
            "SI 类型说明:\n"
            "L = 离散列表      例: SI L 1 2 3\n"
            "H = 连续均匀       例: SI H 0 1\n"
            "A = 解析函数        例: SI -41 0 1\n"
            "S = 分布号         例: SI S 2\n"
            "Q = 用户概率\n"
            "F = 内置函数\n"
            "T = 表格"
        )
        h.addWidget(QLabel(f"SI{index}:"), 0)
        h.addWidget(si_edit, 1)

        sp_edit = QLineEdit()
        sp_edit.setPlaceholderText(f"SP{index}  …")
        h.addWidget(QLabel(f"SP{index}:"), 0)
        h.addWidget(sp_edit, 1)

        btn_del = QPushButton("×")
        btn_del.setMaximumWidth(24)
        btn_del.setToolTip("删除此分布")
        btn_del.clicked.connect(lambda: self._remove_sisp_card(frame))
        h.addWidget(btn_del)

        pair = {
            "frame": frame,
            "si": si_edit,
            "sp": sp_edit,
            "ref_index": index,
            "ref_param": param,
            "auto": True,  # Auto-generated vs. manually added
        }
        self.dist_pairs.append(pair)
        self.sisp_container.addWidget(frame)

    def _add_sisp_pair(self):
        """手动添加一个 SI/SP 对 / Manually add an SI/SP pair.

        Finds the lowest unused Dn index and creates a card.
        Marks it as manually added (non-auto) so it won't be removed
        automatically when Dn references change.
        """
        used = {p["ref_index"] for p in self.dist_pairs}
        next_n = 1
        while next_n in used:
            next_n += 1
        self._create_sisp_card(next_n, "手动")
        for p in self.dist_pairs:
            if p["ref_index"] == next_n:
                p["auto"] = False
                p["frame"].setTitle(f"分布 D{next_n}（手动）")
                break

    def _remove_sisp_card(self, frame):
        """删除一个 SI/SP 卡片 / Remove an SI/SP card.

        Args:
            frame: The QGroupBox frame of the card to remove.
        """
        for p in list(self.dist_pairs):
            if p["frame"] is frame:
                self.dist_pairs.remove(p)
                frame.deleteLater()
                break

    def _clear_sisp_pairs(self):
        """清除所有 SI/SP 卡片 / Clear all SI/SP cards.

        Removes every pair from the list and deletes their widgets.
        Used when loading new data to reset the distribution state.
        """
        for p in list(self.dist_pairs):
            self.dist_pairs.remove(p)
            p["frame"].deleteLater()

    # ---------- 模式切换 ----------

    def _on_mode_changed(self, index: int):
        """Handle mode selector change: switch the QStackedWidget page.

        Args:
            index: 0=fixed, 1=distribution, 2=kcode
        """
        self.stack.setCurrentIndex(index)
        self._update_hint_text(index)
        # Add/delete buttons only visible in fixed source mode
        self.btn_add.setVisible(index == 0)
        self.btn_del.setVisible(index == 0)
        if index == 1:
            self._ensure_sisp_pairs()
        if index == 0:
            self._refresh_table()

    # ---------- 公开接口 ----------

    def get_sources(self) -> list[SourceData]:
        """返回固定点源列表（分布源模式下返回空列表） / Get fixed point source list.

        Returns:
            list[SourceData]: Fixed point sources (empty list in distribution mode).
        """
        return self.fixed_sources

    def get_distribution_data(self) -> dict:
        """返回当前模式数据，用于合并到 AdvancedSettings / Get current mode data for AdvancedSettings.

        Fixed source mode returns {"source_mode": "fixed"}.
        Distribution source mode serializes SDEF fields and SI/SP pairs.
        KCODE mode returns KCODE/KSRC parameters.

        Returns:
            dict: Source configuration data for the current mode.
        """
        mode = self.stack.currentIndex()
        if mode == 0:  # fixed
            return {"source_mode": "fixed", "sdef_raw_text": ""}

        if mode == 2:  # KCODE
            return self._get_kcode_data()

        # mode == 1: distribution (existing logic)

        # Serialize SI/SP pairs as JSON
        pairs = []
        for p in sorted(self.dist_pairs, key=lambda x: x["ref_index"]):
            si_t = p["si"].text().strip()
            sp_t = p["sp"].text().strip()
            if si_t or sp_t:
                pairs.append({"si": si_t, "sp": sp_t})

        return {
            "source_mode": "distribution",
            "sdef_par": self.sdef_par.text().strip(),
            "sdef_erg": self.sdef_erg.text().strip(),
            "sdef_pos_x": self.sdef_pos_x.text().strip(),
            "sdef_pos_y": self.sdef_pos_y.text().strip(),
            "sdef_pos_z": self.sdef_pos_z.text().strip(),
            "sdef_wgt": self.sdef_wgt.text().strip(),
            "sdef_dir": self.sdef_dir.text().strip(),
            "sdef_cel": self.sdef_cel.text().strip(),
            "sdef_tme": self.sdef_tme.text().strip(),
            "sdef_vec": self.sdef_vec.text().strip(),
            "sdef_axs": self.sdef_axs.text().strip(),
            "sdef_rad": self.sdef_rad.text().strip(),
            "sdef_ext": self.sdef_ext.text().strip(),
            "sdef_sur": self.sdef_sur.text().strip(),
            "sdef_nrm": self.sdef_nrm.text().strip(),
            "sdef_tr": self.sdef_tr.text().strip(),
            "sdef_ccc": self.sdef_ccc.text().strip(),
            "sdef_ara": self.sdef_ara.text().strip(),
            "sdef_rate": self.sdef_rate.text().strip(),
            "sdef_raw_text": json.dumps(pairs, ensure_ascii=False),
        }

    def _get_kcode_data(self) -> dict:
        """收集 KCODE/KSRC 数据 / Collect KCODE/KSRC data.

        Returns:
            dict: KCODE fields + KSRC points JSON.
        """
        ksrc_points = []
        for row in range(self.ksrc_table.rowCount()):
            x = (self.ksrc_table.item(row, 0).text() if self.ksrc_table.item(row, 0) else "")
            y = (self.ksrc_table.item(row, 1).text() if self.ksrc_table.item(row, 1) else "")
            z = (self.ksrc_table.item(row, 2).text() if self.ksrc_table.item(row, 2) else "")
            if x or y or z:
                ksrc_points.append({"x": x, "y": y, "z": z})

        import json as _json
        return {
            "source_mode": "kcode",
            "kcode_nsrc": self.kcode_nsrc.text().strip(),
            "kcode_rkk": self.kcode_rkk.text().strip(),
            "kcode_ikz": self.kcode_ikz.text().strip(),
            "kcode_kct": self.kcode_kct.text().strip(),
            "kcode_knrm": self.kcode_knrm.text().strip(),
            "ksrc_points": _json.dumps(ksrc_points, ensure_ascii=False),
            "sdef_raw_text": "",
        }

    def _load_kcode_data(self, adv: AdvancedSettings):
        """从 AdvancedSettings 回填 KCODE/KSRC UI / Restore KCODE/KSRC UI from AdvancedSettings.

        Args:
            adv: AdvancedSettings with kcode_* fields.
        """
        self.kcode_nsrc.setText(adv.kcode_nsrc or "")
        self.kcode_rkk.setText(adv.kcode_rkk or "")
        self.kcode_ikz.setText(adv.kcode_ikz or "")
        self.kcode_kct.setText(adv.kcode_kct or "")
        self.kcode_knrm.setText(adv.kcode_knrm or "")

        # Restore KSRC points
        self.ksrc_table.setRowCount(0)
        if adv.ksrc_points:
            import json as _json
            try:
                points = _json.loads(adv.ksrc_points)
                for pt in points:
                    self._add_ksrc_point(pt.get("x", ""), pt.get("y", ""), pt.get("z", ""))
            except (_json.JSONDecodeError, TypeError):
                pass

    def set_data(self, sources: list[SourceData],
                 adv: AdvancedSettings | None = None):
        """从导入/加载数据回填 UI / Populate UI from imported/loaded data.

        Restores source definitions from fixed point source list,
        distribution source settings, or KCODE criticality settings.
        Used when loading an existing MCNP input file or a saved project.

        Args:
            sources: List of fixed point source data objects.
            adv: AdvancedSettings containing source mode and fields.
                If None, defaults to fixed point source mode (backward compatible).
        """
        self.fixed_sources = list(sources)

        if adv and adv.source_mode == "distribution":
            self.mode_combo.setCurrentIndex(1)
            self.stack.setCurrentIndex(1)
            self._update_hint_text(1)
            self._load_distribution_data(adv)
        elif adv and adv.source_mode == "kcode":
            self.mode_combo.setCurrentIndex(2)
            self.stack.setCurrentIndex(2)
            self._update_hint_text(2)
            self._load_kcode_data(adv)
        else:
            # Default to fixed point source mode
            self.mode_combo.setCurrentIndex(0)
            self.stack.setCurrentIndex(0)
            self._update_hint_text(0)
            self.btn_add.setVisible(True)
            self.btn_del.setVisible(True)

        self._refresh_table()

    def _load_distribution_data(self, adv: AdvancedSettings):
        """从 AdvancedSettings 回填分布源 UI / Restore distribution source UI from AdvancedSettings.

        Fills in all SDEF fields and reconstructs SI/SP pairs from the serialized data.

        Args:
            adv: AdvancedSettings object containing distribution source data.
        """
        # Restore primary SDEF fields
        self.sdef_par.setText(adv.sdef_par or "")
        self.sdef_erg.setText(adv.sdef_erg or "")
        self.sdef_pos_x.setText(adv.sdef_pos_x or "")
        self.sdef_pos_y.setText(adv.sdef_pos_y or "")
        self.sdef_pos_z.setText(adv.sdef_pos_z or "")
        self.sdef_wgt.setText(adv.sdef_wgt or "")
        self.sdef_dir.setText(adv.sdef_dir or "")
        self.sdef_cel.setText(adv.sdef_cel or "")
        self.sdef_tme.setText(adv.sdef_tme or "")
        self.sdef_vec.setText(adv.sdef_vec or "")
        self.sdef_axs.setText(adv.sdef_axs or "")
        self.sdef_rad.setText(adv.sdef_rad or "")
        self.sdef_ext.setText(adv.sdef_ext or "")

        # 额外参数（折叠区）/ Extra parameters (collapsible section)
        self.sdef_sur.setText(adv.sdef_sur or "")
        self.sdef_nrm.setText(adv.sdef_nrm or "")
        self.sdef_tr.setText(adv.sdef_tr or "")
        self.sdef_ccc.setText(adv.sdef_ccc or "")
        self.sdef_ara.setText(adv.sdef_ara or "")
        self.sdef_rate.setText(adv.sdef_rate or "")
        # Show extra section if any extra parameter has a value
        if any([adv.sdef_sur, adv.sdef_nrm, adv.sdef_tr,
                adv.sdef_ccc, adv.sdef_ara, adv.sdef_rate]):
            self.btn_extra.setChecked(True)
            self.extra_widget.setVisible(True)
            self.btn_extra.setText("▲ 收起额外参数")
        else:
            self.btn_extra.setChecked(False)
            self.extra_widget.setVisible(False)

        # 解析 SI/SP 对 / Parse and restore SI/SP pairs
        self._clear_sisp_pairs()
        if adv.sdef_raw_text:
            try:
                pairs = json.loads(adv.sdef_raw_text)
                for i, pair in enumerate(pairs):
                    idx = i + 1
                    self._create_sisp_card(idx, f"导入 D{idx}")
                    for p in self.dist_pairs:
                        if p["ref_index"] == idx:
                            p["auto"] = False
                            si_text = pair.get("si", "")
                            # Strip SI\d+ / SP\d+ prefix (UI label already shows the index number)
                            si_parts = si_text.split(None, 1)
                            if si_parts and re.match(r'^(SI|SP)\d+$', si_parts[0], re.IGNORECASE):
                                si_text = si_parts[1] if len(si_parts) > 1 else ""
                            p["si"].setText(si_text)
                            sp_text = pair.get("sp", "")
                            sp_parts = sp_text.split(None, 1)
                            if sp_parts and re.match(r'^SP\d+$', sp_parts[0], re.IGNORECASE):
                                sp_text = sp_parts[1] if len(sp_parts) > 1 else ""
                            p["sp"].setText(sp_text)
                            break
            except (json.JSONDecodeError, TypeError):
                pass

        # Re-create auto-generated pairs from Dn references in fields
        self._ensure_sisp_pairs()

    # ---------- 文本模式支持 ----------

    def _gen_sdef_raw(self) -> str:
        """生成当前模式的 MCNP SDEF 文本 / Generate MCNP source text for the current mode.

        Returns:
            str: The source card text appropriate for the current mode.
        """
        from app.generator.inp_generator import _generate_kcode
        mode = self.stack.currentIndex()
        if mode == 1:  # 分布源 / distribution source
            adv = AdvancedSettings()
            for k, v in self.get_distribution_data().items():
                setattr(adv, k, v)
            return "\n".join(_generate_distribution_sdef(adv))
        elif mode == 2:  # KCODE / criticality source
            adv = AdvancedSettings()
            for k, v in self._get_kcode_data().items():
                setattr(adv, k, v)
            return "\n".join(_generate_kcode(adv))
        else:  # 固定点源 / fixed point source
            return "\n".join(_generate_sdef(self.fixed_sources))

    def get_raw_overrides(self) -> dict:
        """Return raw text mode overrides for the generator.

        Returns:
            dict: Dictionary with "sdef" key containing raw text, if any.
        """
        return {"sdef": self._raw_sdef.get_raw_text()}
