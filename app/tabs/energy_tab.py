"""
⚡ 能谱标签页：E0 能谱网格 + CUT 能量截断设置
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QCheckBox, QLabel, QSpinBox,
    QFormLayout, QLineEdit, QPlainTextEdit, QGridLayout, QScrollArea
)
from PyQt5.QtCore import Qt

from app.models import TallySettings
from app.widgets.text_mode_section import TextModeSection
from app.generator.inp_generator import _generate_energy_mesh, _generate_cut


class EnergyTab(QWidget):
    """能谱网格 & 能量截断标签页"""

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
        layout.setSpacing(16)

        # ===== E0 能谱网格 =====
        grp_e = QGroupBox()
        grp_e.setToolTip(
            "所有计数共享同一套能量分界。\n"
            "MCNP 将每个计数按能量分道记录。"
        )
        e_form_container = QWidget()
        e_form = QFormLayout(e_form_container)
        e_form.setSpacing(10)

        e_range = QHBoxLayout()
        self.e_min = QLineEdit("")
        self.e_min.setPlaceholderText("如 0.001")
        self.e_min.setToolTip("能量网格最低值（MeV），留空不生成 E0 卡")
        self.e_max = QLineEdit("")
        self.e_max.setPlaceholderText("如 14")
        self.e_max.setToolTip("能量网格最高值（MeV），留空不生成 E0 卡")
        e_range.addWidget(QLabel("从"))
        e_range.addWidget(self.e_min)
        e_range.addWidget(QLabel("到"))
        e_range.addWidget(self.e_max)
        e_range.addWidget(QLabel("MeV"))
        e_form.addRow("能量范围:", e_range)

        self.e_bins = QSpinBox()
        self.e_bins.setRange(0, 10000)
        self.e_bins.setValue(0)
        self.e_bins.setSpecialValueText("不设置")
        self.e_bins.setToolTip("能量间隔数，0=不生成 E0 卡")
        e_form.addRow("间隔数:", self.e_bins)

        self.e_log_cb = QCheckBox("对数网格（勾选=对数，不勾=线性）")
        self.e_log_cb.setChecked(False)
        self.e_log_cb.setToolTip(
            "对数网格：低能区道宽小，高能区道宽大，适合中子能谱。\n"
            "线性网格：所有能道等宽。"
        )
        e_form.addRow("", self.e_log_cb)

        self.e_custom_cb = QCheckBox("自定义网格（手动输入能量边界，勾选后忽略上面设置）")
        self.e_custom_cb.setToolTip(
            "勾选后自行输入能量边界值，每行一个能量（MeV），从小到大。\n"
            "适合需要特定能道划分的高级用户。"
        )
        self.e_custom_cb.toggled.connect(self._toggle_custom_grid)
        e_form.addRow("", self.e_custom_cb)

        self.e_custom_edit = QPlainTextEdit()
        self.e_custom_edit.setPlaceholderText(
            "示例 (从低到高，每行一个):\n"
            "0.001\n0.01\n0.1\n1\n10\n14"
        )
        self.e_custom_edit.setToolTip("每行一个能量值（MeV），从小到大排列")
        self.e_custom_edit.setMaximumHeight(120)
        self.e_custom_edit.setVisible(False)
        e_form.addRow("", self.e_custom_edit)

        e_hint = QLabel(
            "<span style='color:gray; font-size:11px;'>"
            "💡 对数网格推荐：0.001~14 MeV，200 间隔。"
            "自定义网格适合特殊能道需求。</span>"
        )
        e_form.addRow("", e_hint)

        self._raw_e0 = TextModeSection(
            form_widget=e_form_container,
            generate_fn=self._gen_e0_raw,
            section_name="e0",
        )
        gb_e_layout = QVBoxLayout(grp_e)
        e_header = QHBoxLayout()
        e_header.addWidget(QLabel("<b>能谱网格设置（E0 卡）</b>"))
        e_header.addStretch()
        e_header.addWidget(self._raw_e0.toggle_btn)
        gb_e_layout.addLayout(e_header)
        gb_e_layout.addWidget(self._raw_e0.stack)
        layout.addWidget(grp_e)

        # ===== CUT 时间+能量截断 =====
        grp_cut = QGroupBox()
        grp_cut.setToolTip(
            "CUT:N tcut ecut — 时间截断 + 能量截断\n"
            "tcut = 时间截断 (shake, 1 shake = 10⁻⁸ s, 0 = 不限)\n"
            "ecut = 能量截断 (MeV)，低于此能量的粒子被杀死"
        )
        cut_container = QWidget()
        cut_grid = QGridLayout(cut_container)
        cut_grid.setSpacing(8)

        # 表头
        headers = ["<b>粒子</b>", "<b>tme</b>", "<b>e</b>",
                   "<b>wgt</b>", "<b>tmc</b>", "<b>wc1</b>", "<b>wc2</b>"]
        for ci, h in enumerate(headers):
            cut_grid.addWidget(QLabel(h), 0, ci)

        # CUT:N
        cut_grid.addWidget(QLabel("CUT:N 中子"), 1, 0)
        self.cut_n_t = QLineEdit("")
        self.cut_n_t.setPlaceholderText("留空")
        self.cut_n_t.setToolTip("中子时间截断 (shake, 1e-8 s)")
        self.cut_n_t.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_n_t, 1, 1)
        self.cut_n_e = QLineEdit()
        self.cut_n_e.setPlaceholderText("留空")
        self.cut_n_e.setToolTip("中子能量截断 (MeV)")
        self.cut_n_e.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_n_e, 1, 2)
        self.cut_n_wgt = QLineEdit()
        self.cut_n_wgt.setPlaceholderText("留空")
        self.cut_n_wgt.setToolTip("中子权重截断")
        self.cut_n_wgt.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_n_wgt, 1, 3)
        self.cut_n_tmc = QLineEdit()
        self.cut_n_tmc.setPlaceholderText("留空")
        self.cut_n_tmc.setToolTip("中子碰撞时间截断")
        self.cut_n_tmc.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_n_tmc, 1, 4)
        self.cut_n_wc1 = QLineEdit()
        self.cut_n_wc1.setPlaceholderText("留空")
        self.cut_n_wc1.setToolTip("中子权重比 1")
        self.cut_n_wc1.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_n_wc1, 1, 5)
        self.cut_n_wc2 = QLineEdit()
        self.cut_n_wc2.setPlaceholderText("留空")
        self.cut_n_wc2.setToolTip("中子权重比 2")
        self.cut_n_wc2.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_n_wc2, 1, 6)

        # CUT:P
        cut_grid.addWidget(QLabel("CUT:P 光子"), 2, 0)
        self.cut_p_t = QLineEdit("")
        self.cut_p_t.setPlaceholderText("留空")
        self.cut_p_t.setToolTip("光子时间截断 (shake)")
        self.cut_p_t.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_p_t, 2, 1)
        self.cut_p_e = QLineEdit()
        self.cut_p_e.setPlaceholderText("留空")
        self.cut_p_e.setToolTip("光子能量截断 (MeV)")
        self.cut_p_e.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_p_e, 2, 2)
        self.cut_p_wgt = QLineEdit()
        self.cut_p_wgt.setPlaceholderText("留空")
        self.cut_p_wgt.setToolTip("光子权重截断")
        self.cut_p_wgt.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_p_wgt, 2, 3)
        self.cut_p_tmc = QLineEdit()
        self.cut_p_tmc.setPlaceholderText("留空")
        self.cut_p_tmc.setToolTip("光子碰撞时间截断")
        self.cut_p_tmc.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_p_tmc, 2, 4)
        self.cut_p_wc1 = QLineEdit()
        self.cut_p_wc1.setPlaceholderText("留空")
        self.cut_p_wc1.setToolTip("光子权重比 1")
        self.cut_p_wc1.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_p_wc1, 2, 5)
        self.cut_p_wc2 = QLineEdit()
        self.cut_p_wc2.setPlaceholderText("留空")
        self.cut_p_wc2.setToolTip("光子权重比 2")
        self.cut_p_wc2.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_p_wc2, 2, 6)

        # CUT:E
        cut_grid.addWidget(QLabel("CUT:E 电子"), 3, 0)
        self.cut_e_t = QLineEdit("")
        self.cut_e_t.setPlaceholderText("留空")
        self.cut_e_t.setToolTip("电子时间截断 (shake)")
        self.cut_e_t.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_e_t, 3, 1)
        self.cut_e_e = QLineEdit()
        self.cut_e_e.setPlaceholderText("留空")
        self.cut_e_e.setToolTip("电子能量截断 (MeV)")
        self.cut_e_e.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_e_e, 3, 2)
        self.cut_e_wgt = QLineEdit()
        self.cut_e_wgt.setPlaceholderText("留空")
        self.cut_e_wgt.setToolTip("电子权重截断")
        self.cut_e_wgt.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_e_wgt, 3, 3)
        self.cut_e_tmc = QLineEdit()
        self.cut_e_tmc.setPlaceholderText("留空")
        self.cut_e_tmc.setToolTip("电子碰撞时间截断")
        self.cut_e_tmc.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_e_tmc, 3, 4)
        self.cut_e_wc1 = QLineEdit()
        self.cut_e_wc1.setPlaceholderText("留空")
        self.cut_e_wc1.setToolTip("电子权重比 1")
        self.cut_e_wc1.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_e_wc1, 3, 5)
        self.cut_e_wc2 = QLineEdit()
        self.cut_e_wc2.setPlaceholderText("留空")
        self.cut_e_wc2.setToolTip("电子权重比 2")
        self.cut_e_wc2.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_e_wc2, 3, 6)

        # CUT:H
        cut_grid.addWidget(QLabel("CUT:H 质子"), 4, 0)
        self.cut_h_t = QLineEdit("")
        self.cut_h_t.setPlaceholderText("留空")
        self.cut_h_t.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_h_t, 4, 1)
        self.cut_h_e = QLineEdit()
        self.cut_h_e.setPlaceholderText("留空")
        self.cut_h_e.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_h_e, 4, 2)
        self.cut_h_wgt = QLineEdit()
        self.cut_h_wgt.setPlaceholderText("留空")
        self.cut_h_wgt.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_h_wgt, 4, 3)
        self.cut_h_tmc = QLineEdit()
        self.cut_h_tmc.setPlaceholderText("留空")
        self.cut_h_tmc.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_h_tmc, 4, 4)
        self.cut_h_wc1 = QLineEdit()
        self.cut_h_wc1.setPlaceholderText("留空")
        self.cut_h_wc1.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_h_wc1, 4, 5)
        self.cut_h_wc2 = QLineEdit()
        self.cut_h_wc2.setPlaceholderText("留空")
        self.cut_h_wc2.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_h_wc2, 4, 6)

        # CUT:HE
        cut_grid.addWidget(QLabel("CUT:HE 重离子"), 5, 0)
        self.cut_he_t = QLineEdit("")
        self.cut_he_t.setPlaceholderText("留空")
        self.cut_he_t.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_he_t, 5, 1)
        self.cut_he_e = QLineEdit()
        self.cut_he_e.setPlaceholderText("留空")
        self.cut_he_e.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_he_e, 5, 2)
        self.cut_he_wgt = QLineEdit()
        self.cut_he_wgt.setPlaceholderText("留空")
        self.cut_he_wgt.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_he_wgt, 5, 3)
        self.cut_he_tmc = QLineEdit()
        self.cut_he_tmc.setPlaceholderText("留空")
        self.cut_he_tmc.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_he_tmc, 5, 4)
        self.cut_he_wc1 = QLineEdit()
        self.cut_he_wc1.setPlaceholderText("留空")
        self.cut_he_wc1.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_he_wc1, 5, 5)
        self.cut_he_wc2 = QLineEdit()
        self.cut_he_wc2.setPlaceholderText("留空")
        self.cut_he_wc2.setMaximumWidth(100)
        cut_grid.addWidget(self.cut_he_wc2, 5, 6)

        cut_grid.setColumnStretch(7, 1)

        cut_hint = QLabel(
            "<span style='color:gray; font-size:11px;'>"
            "💡 留空 = 使用 MCNP 默认值（导入时 j-skip 语法会自动展开到各字段）</span>"
        )
        cut_grid.addWidget(cut_hint, 6, 0, 1, 7)

        self._raw_cut = TextModeSection(
            form_widget=cut_container,
            generate_fn=self._gen_cut_raw,
            section_name="cut",
        )
        gb_cut_layout = QVBoxLayout(grp_cut)
        cut_header = QHBoxLayout()
        cut_header.addWidget(QLabel("<b>粒子截断设置（CUT 卡）</b>"))
        cut_header.addStretch()
        cut_header.addWidget(self._raw_cut.toggle_btn)
        gb_cut_layout.addLayout(cut_header)
        gb_cut_layout.addWidget(self._raw_cut.stack)
        layout.addWidget(grp_cut)
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _toggle_custom_grid(self, checked):
        self.e_custom_edit.setVisible(checked)

    # ---------- 文本模式支持 ----------

    def _gen_e0_raw(self) -> str:
        tally = TallySettings(
            e_min=self.e_min.text().strip(),
            e_max=self.e_max.text().strip(),
            e_bins=self.e_bins.value(),
            e_log=self.e_log_cb.isChecked(),
            e_custom_enabled=self.e_custom_cb.isChecked(),
            e_custom_text=self.e_custom_edit.toPlainText().strip(),
        )
        return "\n".join(_generate_energy_mesh(tally))

    def _gen_cut_raw(self) -> str:
        tally = TallySettings(
            cut_n_t=self.cut_n_t.text().strip(),
            cut_n_e=self.cut_n_e.text().strip(),
            cut_n_wgt=self.cut_n_wgt.text().strip(),
            cut_n_tmc=self.cut_n_tmc.text().strip(),
            cut_n_wc1=self.cut_n_wc1.text().strip(),
            cut_n_wc2=self.cut_n_wc2.text().strip(),
            cut_p_t=self.cut_p_t.text().strip(),
            cut_p_e=self.cut_p_e.text().strip(),
            cut_p_wgt=self.cut_p_wgt.text().strip(),
            cut_p_tmc=self.cut_p_tmc.text().strip(),
            cut_p_wc1=self.cut_p_wc1.text().strip(),
            cut_p_wc2=self.cut_p_wc2.text().strip(),
            cut_e_t=self.cut_e_t.text().strip(),
            cut_e_e=self.cut_e_e.text().strip(),
            cut_e_wgt=self.cut_e_wgt.text().strip(),
            cut_e_tmc=self.cut_e_tmc.text().strip(),
            cut_e_wc1=self.cut_e_wc1.text().strip(),
            cut_e_wc2=self.cut_e_wc2.text().strip(),
            cut_h_t=self.cut_h_t.text().strip(),
            cut_h_e=self.cut_h_e.text().strip(),
            cut_h_wgt=self.cut_h_wgt.text().strip(),
            cut_h_tmc=self.cut_h_tmc.text().strip(),
            cut_h_wc1=self.cut_h_wc1.text().strip(),
            cut_h_wc2=self.cut_h_wc2.text().strip(),
            cut_he_t=self.cut_he_t.text().strip(),
            cut_he_e=self.cut_he_e.text().strip(),
            cut_he_wgt=self.cut_he_wgt.text().strip(),
            cut_he_tmc=self.cut_he_tmc.text().strip(),
            cut_he_wc1=self.cut_he_wc1.text().strip(),
            cut_he_wc2=self.cut_he_wc2.text().strip(),
        )
        return "\n".join(_generate_cut(tally))

    def get_raw_overrides(self) -> dict:
        return {
            "e0": self._raw_e0.get_raw_text(),
            "cut": self._raw_cut.get_raw_text(),
        }

    def get_data(self) -> dict:
        """返回能谱 & CUT 设置（供主窗口合并到 TallySettings）"""
        return {
            'e_min': self.e_min.text().strip(),
            'e_max': self.e_max.text().strip(),
            'e_bins': self.e_bins.value(),
            'e_log': self.e_log_cb.isChecked(),
            'e_custom_enabled': self.e_custom_cb.isChecked(),
            'e_custom_text': self.e_custom_edit.toPlainText().strip(),
            'cut_n_t': self.cut_n_t.text().strip(),
            'cut_n_e': self.cut_n_e.text().strip(),
            'cut_n_wgt': self.cut_n_wgt.text().strip(),
            'cut_n_tmc': self.cut_n_tmc.text().strip(),
            'cut_n_wc1': self.cut_n_wc1.text().strip(),
            'cut_n_wc2': self.cut_n_wc2.text().strip(),
            'cut_p_t': self.cut_p_t.text().strip(),
            'cut_p_e': self.cut_p_e.text().strip(),
            'cut_p_wgt': self.cut_p_wgt.text().strip(),
            'cut_p_tmc': self.cut_p_tmc.text().strip(),
            'cut_p_wc1': self.cut_p_wc1.text().strip(),
            'cut_p_wc2': self.cut_p_wc2.text().strip(),
            'cut_e_t': self.cut_e_t.text().strip(),
            'cut_e_e': self.cut_e_e.text().strip(),
            'cut_e_wgt': self.cut_e_wgt.text().strip(),
            'cut_e_tmc': self.cut_e_tmc.text().strip(),
            'cut_e_wc1': self.cut_e_wc1.text().strip(),
            'cut_e_wc2': self.cut_e_wc2.text().strip(),
            'cut_h_t': self.cut_h_t.text().strip(),
            'cut_h_e': self.cut_h_e.text().strip(),
            'cut_h_wgt': self.cut_h_wgt.text().strip(),
            'cut_h_tmc': self.cut_h_tmc.text().strip(),
            'cut_h_wc1': self.cut_h_wc1.text().strip(),
            'cut_h_wc2': self.cut_h_wc2.text().strip(),
            'cut_he_t': self.cut_he_t.text().strip(),
            'cut_he_e': self.cut_he_e.text().strip(),
            'cut_he_wgt': self.cut_he_wgt.text().strip(),
            'cut_he_tmc': self.cut_he_tmc.text().strip(),
            'cut_he_wc1': self.cut_he_wc1.text().strip(),
            'cut_he_wc2': self.cut_he_wc2.text().strip(),
        }

    def set_data(self, tally):
        """从 TallySettings 回填 UI（用于 INP 导入）"""
        self.e_min.setText(tally.e_min or "")
        self.e_max.setText(tally.e_max or "")
        try:
            self.e_bins.setValue(int(tally.e_bins) if tally.e_bins else 0)
        except (ValueError, TypeError):
            pass
        self.e_log_cb.setChecked(bool(tally.e_log))
        self.e_custom_cb.setChecked(tally.e_custom_enabled)
        self.e_custom_edit.setPlainText(tally.e_custom_text or "")
        self.e_custom_edit.setVisible(tally.e_custom_enabled)

        # CUT（留空则留空）
        self.cut_n_t.setText(tally.cut_n_t or "")
        self.cut_n_e.setText(tally.cut_n_e or "")
        self.cut_n_wgt.setText(tally.cut_n_wgt or "")
        self.cut_n_tmc.setText(tally.cut_n_tmc or "")
        self.cut_n_wc1.setText(tally.cut_n_wc1 or "")
        self.cut_n_wc2.setText(tally.cut_n_wc2 or "")
        self.cut_p_t.setText(tally.cut_p_t or "")
        self.cut_p_e.setText(tally.cut_p_e or "")
        self.cut_p_wgt.setText(tally.cut_p_wgt or "")
        self.cut_p_tmc.setText(tally.cut_p_tmc or "")
        self.cut_p_wc1.setText(tally.cut_p_wc1 or "")
        self.cut_p_wc2.setText(tally.cut_p_wc2 or "")
        self.cut_e_t.setText(tally.cut_e_t or "")
        self.cut_e_e.setText(tally.cut_e_e or "")
        self.cut_e_wgt.setText(tally.cut_e_wgt or "")
        self.cut_e_tmc.setText(tally.cut_e_tmc or "")
        self.cut_e_wc1.setText(tally.cut_e_wc1 or "")
        self.cut_e_wc2.setText(tally.cut_e_wc2 or "")
        self.cut_h_t.setText(tally.cut_h_t or "")
        self.cut_h_e.setText(tally.cut_h_e or "")
        self.cut_h_wgt.setText(tally.cut_h_wgt or "")
        self.cut_h_tmc.setText(tally.cut_h_tmc or "")
        self.cut_h_wc1.setText(tally.cut_h_wc1 or "")
        self.cut_h_wc2.setText(tally.cut_h_wc2 or "")
        self.cut_he_t.setText(tally.cut_he_t or "")
        self.cut_he_e.setText(tally.cut_he_e or "")
        self.cut_he_wgt.setText(tally.cut_he_wgt or "")
        self.cut_he_tmc.setText(tally.cut_he_tmc or "")
        self.cut_he_wc1.setText(tally.cut_he_wc1 or "")
        self.cut_he_wc2.setText(tally.cut_he_wc2 or "")
