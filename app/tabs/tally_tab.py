"""
📊 计数卡标签页：F1~F8 全类型
Tally Card Tab: All F1~F8 tally types

This module provides the TallyTab widget for configuring MCNP tally cards.
Supports the standard F1 through F8 tally types with appropriate parameter inputs:
- F1 (surface current), F2 (surface flux), F4 (cell flux) — surface/cell number input
- F5 (point detector) — X, Y, Z coordinate input
- F6 (energy deposition), F7 (fission energy deposition), F8 (pulse height) — cell number input
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QCheckBox, QLabel, QLineEdit, QGridLayout, QScrollArea
)
from PyQt5.QtCore import Qt

from app.models import TallySettings


class TallyTab(QWidget):
    """计数卡标签页 / Tally Card Tab

    Provides a grid-based UI for enabling and configuring MCNP tally cards F1 through F8.
    Each tally type has a checkbox, description, and parameter input field(s).
    Supports multiple parameter values separated by spaces for tallying multiple
    surfaces or cells simultaneously.

    Tally types supported:
    - F1: Surface current (particles crossing a surface)
    - F2: Surface-averaged flux
    - F4: Cell-averaged flux (most commonly used)
    - F5: Point detector (requires X, Y, Z coordinates)
    - F6: Energy deposition (MeV/g)
    - F7: Fission energy deposition (MeV/g)
    - F8: Pulse height distribution (detector response simulation)
    """

    # Comprehensive tally information dictionary
    # Each entry contains: display name, detailed description, and parameter type
    TALLY_INFO = {
        "F1": ("F1:N — 曲面粒子流 / Surface Current",
               "穿过指定曲面的中子总数。\n单位：粒子\n"
               "Total number of neutrons crossing a specified surface.\nUnit: particles",
               "曲面 / Surface"),
        "F2": ("F2:N — 曲面平均通量 / Surface-Averaged Flux",
               "指定曲面上的平均中子通量。\n单位：粒子/cm²\n"
               "Average neutron flux over a specified surface.\nUnit: particles/cm²",
               "曲面 / Surface"),
        "F4": ("F4:N — 栅元平均通量 / Cell-Averaged Flux",
               "指定栅元内的平均中子通量。\n最常用的通量计数。\n单位：粒子/cm²\n"
               "Average neutron flux in a specified cell.\nMost commonly used flux tally.\nUnit: particles/cm²",
               "栅元 / Cell"),
        "F5": ("F5:N — 点探测器 / Point Detector",
               "空间某一点的中子通量。\n不需要定义栅元，只需坐标。\n单位：粒子/cm²\n"
               "Neutron flux at a point in space.\nNo cell definition needed, only coordinates.\nUnit: particles/cm²",
               "坐标 / Coordinates"),
        "F6": ("F6:N — 能量沉积 / Energy Deposition",
               "指定栅元内的能量沉积（吸收剂量）。\n单位：MeV/g\n"
               "Energy deposition (absorbed dose) in a specified cell.\nUnit: MeV/g",
               "栅元 / Cell"),
        "F7": ("F7:N — 裂变能沉积 / Fission Energy Deposition",
               "指定栅元内的裂变能量沉积。\n仅含裂变材料的栅元才有意义。\n单位：MeV/g\n"
               "Fission energy deposition in a specified cell.\nOnly meaningful for cells containing fissile materials.\nUnit: MeV/g",
               "栅元 / Cell"),
        "F8": ("F8:N — 脉冲高度谱 / Pulse Height Spectrum",
               "指定栅元内的能量脉冲高度分布。\n用于模拟探测器响应。\n单位：脉冲\n"
               "Energy pulse height distribution in a specified cell.\nUsed for simulating detector response.\nUnit: pulses",
               "栅元 / Cell"),
    }

    def __init__(self):
        """Initialize the tally tab and build the UI."""
        super().__init__()
        self._widgets = {}
        self.init_ui()

    def init_ui(self):
        """Build the complete tally configuration UI.

        Creates a scrollable grid layout containing:
        - Informational tip about multi-value support
        - Checkbox + parameter row for each tally type (F1-F8)
        - Special F5 row with X, Y, Z coordinate inputs
        - Hint about additional tally types available in the Advanced tab
        """
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)

        grp_tally = QGroupBox("计数类型（勾选需要的计数卡） / Tally Types (Check the tallies you need)")
        grp_tally.setToolTip(
            "选择 MCNP 需要计算的计数类型，勾选后自动生成对应的 Fn 卡。\n"
            "能谱网格（E0）和能量截断（CUT）请在「⚡ 能谱」标签页设置。\n"
            "Select the MCNP tally types to calculate. Checked tallies will be auto-generated.\n"
            "Energy mesh (E0) and energy cutoff (CUT) are configured in the Energy tab."
        )
        grid = QGridLayout(grp_tally)
        grid.setSpacing(8)

        tip = QLabel(
            "提示：栅元号/曲面号支持多个值，用空格隔开即可，例如输入"
            "<code>1 2 3</code>"
            " 表示同时统计 1、2、3 号栅元 / "
            "Tip: support multiple cell/surface numbers separated by spaces, "
            "e.g. <code>1 2 3</code> tallies cells 1, 2, and 3 simultaneously"
        )
        tip.setStyleSheet("font-size: 11px; color: #666;")
        grid.addWidget(tip, 0, 0, 1, 3)

        # Create tally rows for each standard tally type
        self._create_tally_row(grid, 1, "F1", ["曲面号 / Surface#"], ["f1_surface"])
        self._create_tally_row(grid, 2, "F2", ["曲面号 / Surface#"], ["f2_surface"])
        self._create_tally_row(grid, 3, "F4", ["栅元号 / Cell#"], ["f4_cell"])
        self._create_f5_row(grid, 4)  # Special row for F5 with X/Y/Z coordinates
        self._create_tally_row(grid, 5, "F6", ["栅元号 / Cell#"], ["f6_cell"])
        self._create_tally_row(grid, 6, "F7", ["栅元号 / Cell#"], ["f7_cell"])
        self._create_tally_row(grid, 7, "F8", ["栅元号 / Cell#"], ["f8_cell"])

        layout.addWidget(grp_tally)

        hint = QLabel(
            "💡 更多计数类型（如 F35、FMESH 等）请前往「高级」标签页自行键入 / "
            "For additional tally types (F35, FMESH, etc.), enter them manually in the Advanced tab"
        )
        hint.setStyleSheet("color: #888; font-size: 11px; padding: 4px 0;")
        layout.addWidget(hint)

        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _create_tally_row(self, grid, row, name, param_names, attr_names):
        """创建一行计数卡：复选框 + 中文描述 + 参数输入框（支持多值） / Create a tally row.

        Builds a horizontal row with:
        - Checkbox for enabling/disabling the tally
        - Short description label
        - Parameter input field(s) (supports space-separated multi-values)

        Args:
            grid: The QGridLayout to add the row to.
            row: The grid row index.
            name: Tally name (e.g., "F1", "F4").
            param_names: List of display names for parameter fields.
            attr_names: List of widget attribute names for internal storage.
        """
        full_label, desc, ptype = self.TALLY_INFO[name]
        chk = QCheckBox(full_label)
        desc_short = desc.split('\n')[0]
        chk.setToolTip(desc)
        chk.setChecked(False)
        if name == "F1":
            chk.setChecked(False)

        desc_label = QLabel(f"—— {desc_short}")
        desc_label.setStyleSheet("color: #666; font-size: 11px;")

        # Build parameter input row
        w_params = QHBoxLayout()
        w_params.setSpacing(4)
        params = []
        for pn, an in zip(param_names, attr_names):
            label_w = QLabel(f"{pn}:")
            label_w.setStyleSheet("font-weight: bold;")
            w_params.addWidget(label_w)
            le = QLineEdit("")
            le.setPlaceholderText("如: 1 2 3 / e.g. 1 2 3")
            le.setToolTip(f"{full_label}\n{desc}\n支持多个值，空格分隔，如: 1 2 3 / "
                          f"Supports multiple values separated by spaces, e.g. 1 2 3")
            le.setMaximumWidth(160)
            w_params.addWidget(le)
            params.append(le)

        w_params.addStretch()

        # Store widgets for data retrieval
        self._widgets[f"chk_{name.lower()}"] = chk
        for an, le in zip(attr_names, params):
            self._widgets[an] = le

        row_layout = QHBoxLayout()
        row_layout.setSpacing(6)
        row_layout.addWidget(chk)
        row_layout.addWidget(desc_label)
        row_layout.addLayout(w_params)
        row_layout.addStretch()

        container = QWidget()
        container.setLayout(row_layout)
        grid.addWidget(container, row, 0, 1, 3)

    def _create_f5_row(self, grid, row):
        """F5 点探测器特殊处理（需要 X Y Z 坐标） / Create F5 point detector row with X, Y, Z coordinates.

        F5 is handled separately because it needs three coordinate inputs
        rather than a single cell/surface number.

        Args:
            grid: The QGridLayout to add the row to.
            row: The grid row index.
        """
        chk = QCheckBox("F5:N — 点探测器 / Point Detector")
        chk.setToolTip(
            "空间某一点的中子通量。\n不需要定义栅元，只需坐标。\n单位：粒子/cm²\n"
            "Neutron flux at a point in space.\nNo cell definition needed.\nUnit: particles/cm²"
        )
        chk.setChecked(False)
        self._widgets["chk_f5"] = chk

        desc_label = QLabel("—— 空间某一点的中子通量（粒子/cm²） / Neutron flux at a point (particles/cm²)")
        desc_label.setStyleSheet("color: #666; font-size: 11px;")

        # X, Y, Z coordinate input fields
        w_params = QHBoxLayout()
        w_params.setSpacing(4)
        labels = ["X:", "Y:", "Z:"]
        attrs = ["f5_x", "f5_y", "f5_z"]
        for lb, attr in zip(labels, attrs):
            label_w = QLabel(lb)
            label_w.setStyleSheet("font-weight: bold;")
            w_params.addWidget(label_w)
            le = QLineEdit("")
            le.setToolTip(f"点探测器的 {lb} 坐标（cm） / Point detector {lb} coordinate (cm)")
            le.setMaximumWidth(80)
            w_params.addWidget(le)
            self._widgets[attr] = le

        w_params.addStretch()

        row_layout = QHBoxLayout()
        row_layout.setSpacing(6)
        row_layout.addWidget(chk)
        row_layout.addWidget(desc_label)
        row_layout.addLayout(w_params)
        row_layout.addStretch()

        container = QWidget()
        container.setLayout(row_layout)
        grid.addWidget(container, row, 0, 1, 3)

    def get_data(self) -> dict:
        """返回计数卡设置（不包含能谱/CUT） / Get tally card settings (excluding energy spectrum/CUT).

        Collects all checkbox states and parameter field values.

        Returns:
            dict: Dictionary with tally settings (enabled flags and parameter values).
        """
        def g(key):
            w = self._widgets.get(key)
            return w.text().strip() if w else ""

        return {
            'f1_enabled': self._widgets["chk_f1"].isChecked(),
            'f1_surface': g("f1_surface"),
            'f2_enabled': self._widgets["chk_f2"].isChecked(),
            'f2_surface': g("f2_surface"),
            'f4_enabled': self._widgets["chk_f4"].isChecked(),
            'f4_cell': g("f4_cell"),
            'f5_enabled': self._widgets["chk_f5"].isChecked(),
            'f5_x': self._widgets["f5_x"].text().strip() or "0",
            'f5_y': self._widgets["f5_y"].text().strip() or "0",
            'f5_z': self._widgets["f5_z"].text().strip() or "0",
            'f6_enabled': self._widgets["chk_f6"].isChecked(),
            'f6_cell': g("f6_cell"),
            'f7_enabled': self._widgets["chk_f7"].isChecked(),
            'f7_cell': g("f7_cell"),
            'f8_enabled': self._widgets["chk_f8"].isChecked(),
            'f8_cell': g("f8_cell"),
        }

    def set_data(self, tally):
        """从 TallySettings 回填 UI（用于 INP 导入） / Populate UI from TallySettings (for INP import).

        Restores all tally checkbox states and parameter values from a
        TallySettings object.

        Args:
            tally: TallySettings object containing saved tally configuration.
        """
        def set_chk(key, enabled):
            w = self._widgets.get(key)
            if w: w.setChecked(enabled)
        def set_txt(key, val):
            w = self._widgets.get(key)
            if w: w.setText(val if val else "")

        set_chk("chk_f1", tally.f1_enabled)
        set_txt("f1_surface", tally.f1_surface)
        set_chk("chk_f2", tally.f2_enabled)
        set_txt("f2_surface", tally.f2_surface)
        set_chk("chk_f4", tally.f4_enabled)
        set_txt("f4_cell", tally.f4_cell)
        set_chk("chk_f5", tally.f5_enabled)
        set_txt("f5_x", tally.f5_x)
        set_txt("f5_y", tally.f5_y)
        set_txt("f5_z", tally.f5_z)
        set_chk("chk_f6", tally.f6_enabled)
        set_txt("f6_cell", tally.f6_cell)
        set_chk("chk_f7", tally.f7_enabled)
        set_txt("f7_cell", tally.f7_cell)
        set_chk("chk_f8", tally.f8_enabled)
        set_txt("f8_cell", tally.f8_cell)
