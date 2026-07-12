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
    QStackedWidget, QLineEdit
)
from PyQt5.QtCore import Qt

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
        grp = QGroupBox("源定义（SDEF） / Source Definition (SDEF)")
        grp.setToolTip(
            "定义粒子源。固定点源模式支持多源列表；"
            "分布源模式支持 SDEF 字段 + SI/SP 分布卡。\n"
            "Define particle source. Fixed mode: multi-source list; "
            "Distribution mode: SDEF fields + SI/SP distribution cards."
        )
        inner = QVBoxLayout(grp)

        # ===== Toolbar with mode toggle and actions =====
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("<span style='font-weight:bold;'>源列表 / Source List:</span>"))

        self.btn_mode = QPushButton("切换为分布源 / Switch to Distribution Source")
        self.btn_mode.setToolTip("切换到分布源模式：SDEF 字段 + SI/SP 分布卡 / Switch to distribution source mode with SDEF fields and SI/SP cards")
        self._style_mode_btn(False)
        self.btn_mode.clicked.connect(self._toggle_mode)
        toolbar.addWidget(self.btn_mode)

        # Text mode toggle button
        self._raw_sdef = TextModeSection(
            form_widget=QWidget(),
            generate_fn=self._gen_sdef_raw,
            section_name="sdef",
        )
        toolbar.addWidget(self._raw_sdef.toggle_btn)

        toolbar.addStretch()

        self.btn_add = QPushButton("+ 添加源 / Add Source")
        self.btn_add.setToolTip("新增一个源（固定点源模式） / Add a new source (fixed point source mode)")
        self.btn_add.setProperty("cssClass", "btnAdd")
        self.btn_add.clicked.connect(self._add_source)

        self.btn_del = QPushButton("× 删除选中 / Delete Selected")
        self.btn_del.setToolTip("删除选中的源 / Delete selected sources")
        self.btn_del.setProperty("cssClass", "btnDelete")
        self.btn_del.clicked.connect(self._delete_source)

        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_del)
        inner.addLayout(toolbar)

        # ===== QStackedWidget for mode switching =====
        self.stack = QStackedWidget()
        self.page_fixed = self._build_fixed_page()
        self.page_dist = self._build_distribution_page()
        self.stack.addWidget(self.page_fixed)
        self.stack.addWidget(self.page_dist)
        self.stack.setCurrentIndex(0)

        # Wrap in TextModeSection for raw text editing support
        self._raw_sdef.stack.removeWidget(self._raw_sdef.stack.widget(0))
        self._raw_sdef.stack.insertWidget(0, self.stack)
        inner.addWidget(self._raw_sdef.stack, 1)
        layout.addWidget(grp)

        # ===== Context-sensitive hint label =====
        self.hint = QLabel("")
        self.hint.setTextFormat(Qt.RichText)
        self._update_hint_text(False)
        layout.addWidget(self.hint)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ---------- UI 构建 / UI Construction ----------

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
            ["源# / Source#", "粒子(PAR)", "能量(MeV) / Energy", "位置 / Position", "权重 / Weight", "操作 / Action"]
        )
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setToolTip("双击行或点击编辑按钮编辑源参数 / Double-click or click Edit to modify source parameters")
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
        fixed_grp = QGroupBox("SDEF 参数（键入 D1/D2/… 自动生成 SI/SP 分布卡） / SDEF Parameters (type D1/D2/... to auto-generate SI/SP cards)")
        fixed_grid = QVBoxLayout(fixed_grp)
        fixed_grid.setSpacing(4)

        # Row 1: PAR, ERG, POS(x,y,z), WGT, CEL
        row1 = QHBoxLayout()
        row1.setSpacing(4)

        row1.addWidget(QLabel("<b>PAR:</b>"))
        self.sdef_par = QLineEdit()
        self.sdef_par.setPlaceholderText("例: 1 或 D1 / e.g. 1 or D1")
        self.sdef_par.setMaximumWidth(100)
        self.sdef_par.textChanged.connect(self._on_sdef_field_changed)
        row1.addWidget(self.sdef_par)

        row1.addWidget(QLabel("<b>ERG:</b>"))
        self.sdef_erg = QLineEdit()
        self.sdef_erg.setPlaceholderText("例: 14 或 D2 / e.g. 14 or D2")
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
        self.sdef_wgt.setPlaceholderText("例: 1 / e.g. 1")
        self.sdef_wgt.setMaximumWidth(80)
        self.sdef_wgt.textChanged.connect(self._on_sdef_field_changed)
        row1.addWidget(self.sdef_wgt)

        row1.addWidget(QLabel("<b>CEL:</b>"))
        self.sdef_cel = QLineEdit()
        self.sdef_cel.setPlaceholderText("栅元 / cell")
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
        self.sdef_dir.setPlaceholderText("方向 / direction")
        self.sdef_dir.setMaximumWidth(80)
        self.sdef_dir.textChanged.connect(self._on_sdef_field_changed)
        row2.addWidget(self.sdef_dir)

        row2.addWidget(QLabel("TME:"))
        self.sdef_tme = QLineEdit()
        self.sdef_tme.setPlaceholderText("时间 / time")
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
        self.sdef_axs.setPlaceholderText("轴 / axis")
        self.sdef_axs.setMaximumWidth(80)
        row2.addWidget(self.sdef_axs)

        row2.addWidget(QLabel("RAD:"))
        self.sdef_rad = QLineEdit()
        self.sdef_rad.setPlaceholderText("径向 / radial")
        self.sdef_rad.setMaximumWidth(80)
        row2.addWidget(self.sdef_rad)

        row2.addWidget(QLabel("EXT:"))
        self.sdef_ext = QLineEdit()
        self.sdef_ext.setPlaceholderText("轴向 / axial")
        self.sdef_ext.setMaximumWidth(80)
        row2.addWidget(self.sdef_ext)

        row2.addStretch()
        fixed_grid.addLayout(row2)

        # ── 折叠额外参数（SUR / NRM / TR / CCC / ARA / RATE）/ Collapsible Extra Parameters ──
        self.btn_extra = QPushButton("▼ 额外参数 / Extra Parameters")
        self.btn_extra.setToolTip("点击展开/收起 SUR、NRM、TR、CCC、ARA、RATE / Click to toggle extra SDEF parameters")
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
        self.sdef_sur.setPlaceholderText("曲面源 / surface source")
        self.sdef_sur.setMaximumWidth(100)
        self.sdef_sur.textChanged.connect(self._on_sdef_field_changed)
        extra_row1.addWidget(self.sdef_sur)

        extra_row1.addWidget(QLabel("NRM:"))
        self.sdef_nrm = QLineEdit()
        self.sdef_nrm.setPlaceholderText("曲面法线 / surface normal")
        self.sdef_nrm.setMaximumWidth(100)
        self.sdef_nrm.textChanged.connect(self._on_sdef_field_changed)
        extra_row1.addWidget(self.sdef_nrm)

        extra_row1.addWidget(QLabel("TR:"))
        self.sdef_tr = QLineEdit()
        self.sdef_tr.setPlaceholderText("变换 / transform")
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
        self.sdef_ara.setPlaceholderText("点探测器归一化 / detector normalization")
        self.sdef_ara.setMaximumWidth(100)
        self.sdef_ara.textChanged.connect(self._on_sdef_field_changed)
        extra_row2.addWidget(self.sdef_ara)

        extra_row2.addWidget(QLabel("RATE:"))
        self.sdef_rate = QLineEdit()
        self.sdef_rate.setPlaceholderText("源强度 / source strength")
        self.sdef_rate.setMaximumWidth(100)
        self.sdef_rate.textChanged.connect(self._on_sdef_field_changed)
        extra_row2.addWidget(self.sdef_rate)

        extra_row2.addStretch()
        extra_layout.addLayout(extra_row2)

        fixed_grid.addWidget(self.btn_extra)
        fixed_grid.addWidget(self.extra_widget)
        layout.addWidget(fixed_grp)

        # ── SI/SP 对列表 / SI/SP Pair List ──
        sisp_grp = QGroupBox("SI/SP 分布卡 / SI/SP Distribution Cards")
        sisp_layout = QVBoxLayout(sisp_grp)

        si_hint = QLabel(
            "<span style='color:#888; font-size:10px;'>"
            "SI 类型: L=离散列表  H=连续均匀  A=解析函数  S=分布号  "
            "Q=用户概率  F=内置函数  T=表格 / "
            "SI types: L=Discrete List, H=Continuous Uniform, A=Analytic Function, "
            "S=Distribution Number, Q=User Probability, F=Built-in Function, T=Table</span>"
        )
        sisp_layout.addWidget(si_hint)

        # Container for dynamically added SI/SP pair cards
        self.sisp_container = QVBoxLayout()
        sisp_layout.addLayout(self.sisp_container)

        btn_add_sisp = QPushButton("＋ 添加分布 / Add Distribution")
        btn_add_sisp.setToolTip("手动添加一个 SI/SP 对（Dn 编号自动分配） / Manually add an SI/SP pair (Dn number auto-assigned)")
        btn_add_sisp.clicked.connect(self._add_sisp_pair)
        sisp_layout.addWidget(btn_add_sisp)

        layout.addWidget(sisp_grp, 1)
        return page

    def _style_mode_btn(self, is_dist: bool):
        """切换模式按钮样式 / Style the mode toggle button based on current mode.

        Args:
            is_dist: True if currently in distribution source mode.
        """
        if is_dist:
            self.btn_mode.setText("切换为固定点源 / Switch to Fixed Point Source")
            self.btn_mode.setStyleSheet(
                "QPushButton { background-color: #1976d2; color: white; font-weight: bold; "
                "padding: 4px 12px; border-radius: 4px; }"
                "QPushButton:hover { background-color: #1565c0; }"
            )
        else:
            self.btn_mode.setText("切换为分布源 / Switch to Distribution Source")
            self.btn_mode.setStyleSheet(
                "QPushButton { background-color: #ff9800; color: white; font-weight: bold; "
                "padding: 4px 12px; border-radius: 4px; }"
                "QPushButton:hover { background-color: #f57c00; }"
            )

    def _update_hint_text(self, is_dist: bool):
        """Update the hint label text based on current mode.

        Args:
            is_dist: True if currently in distribution source mode.
        """
        if is_dist:
            self.hint.setText(
                "<span style='color:#5f6368; font-size:12px;'>"
                "💡 分布源模式：上方设置 SDEF 固定参数，下方编辑 SI/SP 分布卡。"
                "键入 D1/D2/… 自动生成对应的 SI/SP 行。 / "
                "Distribution mode: set SDEF parameters above, edit SI/SP cards below. "
                "Type D1/D2/... to auto-generate SI/SP rows.</span>"
            )
        else:
            self.hint.setText(
                "<span style='color:#5f6368; font-size:12px;'>"
                "💡 多个源时，每个源的「概率」参数决定抽样比例。"
                "例如 2 个源各 50% 则各占一半。 / "
                "For multiple sources, the 'probability' parameter controls sampling ratio. "
                "E.g., 2 sources at 50% each will be sampled equally.</span>"
            )

    # ---------- 内部操作：固定点源 / Internal Operations: Fixed Point Source ----------

    def _refresh_table(self):
        """Refresh the fixed source table display.

        Rebuilds all table rows from the current fixed_sources list.
        Shows source number, particle type label, energy, position, weight, and edit button.
        """
        par_labels = {"1": "1-中子 / neutron", "2": "2-光子 / photon", "3": "3-电子 / electron",
                      "H": "H-质子 / proton", "A": "A-α粒子 / alpha", "S": "S-裂片 / fission fragment"}
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

            btn_edit = QPushButton("✎ 编辑 / Edit")
            btn_edit.setToolTip("编辑此源的详细参数 / Edit detailed parameters of this source")
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
            QMessageBox.information(self, "提示 / Info", "请先选中要删除的源 / Please select sources to delete first")
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

    # ---------- 分布源：Dn 检测 / Distribution Source: Dn Detection ----------

    def _toggle_extra_params(self):
        """Toggle visibility of the extra SDEF parameters section."""
        visible = self.btn_extra.isChecked()
        self.extra_widget.setVisible(visible)
        self.btn_extra.setText("▲ 收起额外参数 / Collapse Extra" if visible else "▼ 额外参数 / Extra Parameters")

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
                    existing[n]["frame"].setTitle(f"分布 D{n}（{param}） / Distribution D{n} ({param})")
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
        frame = QGroupBox(f"分布 D{index}（{param}） / Distribution D{index} ({param})")
        h = QHBoxLayout(frame)
        h.setContentsMargins(8, 4, 8, 4)

        si_edit = QLineEdit()
        si_edit.setPlaceholderText(f"SI{index}  L  N  P")
        si_edit.setToolTip(
            "SI 类型说明:\n"
            "L = 离散列表 (Discrete List)     例: SI L 1 2 3\n"
            "H = 连续均匀 (Continuous Uniform)  例: SI H 0 1\n"
            "A = 解析函数 (Analytic Function)   例: SI -41 0 1\n"
            "S = 分布号 (Distribution Number)   例: SI S 2\n"
            "Q = 用户概率 (User Probability)\n"
            "F = 内置函数 (Built-in Function)\n"
            "T = 表格 (Table)"
        )
        h.addWidget(QLabel(f"SI{index}:"), 0)
        h.addWidget(si_edit, 1)

        sp_edit = QLineEdit()
        sp_edit.setPlaceholderText(f"SP{index}  …")
        h.addWidget(QLabel(f"SP{index}:"), 0)
        h.addWidget(sp_edit, 1)

        btn_del = QPushButton("×")
        btn_del.setMaximumWidth(24)
        btn_del.setToolTip("删除此分布 / Delete this distribution")
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
        self._create_sisp_card(next_n, "手动 / manual")
        for p in self.dist_pairs:
            if p["ref_index"] == next_n:
                p["auto"] = False
                p["frame"].setTitle(f"分布 D{next_n}（手动） / Distribution D{next_n} (manual)")
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

    # ---------- 分布源：切换 / Distribution Source: Mode Switching ----------

    def _toggle_mode(self):
        """Toggle between fixed point source and distribution source modes.

        Switches the QStackedWidget page, updates button styles and hints,
        and adjusts the visibility of add/delete buttons.
        """
        is_dist = self.stack.currentIndex() == 0
        self.stack.setCurrentIndex(1 if is_dist else 0)
        self._style_mode_btn(is_dist)
        self._update_hint_text(is_dist)
        # Show/hide add/delete buttons: only visible in fixed point source mode
        self.btn_add.setVisible(not is_dist)
        self.btn_del.setVisible(not is_dist)
        if is_dist:
            self._ensure_sisp_pairs()
        self._refresh_table()

    # ---------- 公开接口 / Public Interface ----------

    def get_sources(self) -> list[SourceData]:
        """返回固定点源列表（分布源模式下返回空列表） / Get fixed point source list.

        Returns:
            list[SourceData]: Fixed point sources (empty list in distribution mode).
        """
        return self.fixed_sources

    def get_distribution_data(self) -> dict:
        """返回分布源模式数据，用于合并到 AdvancedSettings / Get distribution source data for AdvancedSettings.

        Fixed point source mode returns {"source_mode": "fixed"}.
        Distribution source mode serializes all SDEF fields and SI/SP pairs.

        Returns:
            dict: Distribution source configuration data.
        """
        if self.stack.currentIndex() == 0:
            return {"source_mode": "fixed", "sdef_raw_text": ""}

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

    def set_data(self, sources: list[SourceData],
                 adv: AdvancedSettings | None = None):
        """从导入/加载数据回填 UI / Populate UI from imported/loaded data.

        Restores source definitions from both fixed source list and
        distribution source settings. Used when loading an existing MCNP
        input file or a saved project.

        Args:
            sources: List of fixed point source data objects.
            adv: AdvancedSettings containing distribution source fields.
                If None, defaults to fixed point source mode (backward compatible).
        """
        self.fixed_sources = list(sources)

        if adv and adv.source_mode == "distribution":
            # Switch to distribution source mode
            self.stack.setCurrentIndex(1)
            self._style_mode_btn(True)
            self._update_hint_text(True)
            self._load_distribution_data(adv)
        else:
            # Default to fixed point source mode
            self.stack.setCurrentIndex(0)
            self._style_mode_btn(False)
            self._update_hint_text(False)

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
            self.btn_extra.setText("▲ 收起额外参数 / Collapse Extra")
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
                    self._create_sisp_card(idx, f"导入 D{idx} / imported D{idx}")
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

    # ---------- 文本模式支持 / Text Mode Support ----------

    def _gen_sdef_raw(self) -> str:
        """生成当前模式的 MCNP SDEF 文本 / Generate MCNP SDEF text for the current mode.

        Returns:
            str: The SDEF card text appropriate for the current mode.
        """
        if self.stack.currentIndex() == 1:  # 分布源 / distribution source
            adv = AdvancedSettings()
            for k, v in self.get_distribution_data().items():
                setattr(adv, k, v)
            return "\n".join(_generate_distribution_sdef(adv))
        else:  # 固定点源 / fixed point source
            return "\n".join(_generate_sdef(self.fixed_sources))

    def get_raw_overrides(self) -> dict:
        """Return raw text mode overrides for the generator.

        Returns:
            dict: Dictionary with "sdef" key containing raw text, if any.
        """
        return {"sdef": self._raw_sdef.get_raw_text()}
