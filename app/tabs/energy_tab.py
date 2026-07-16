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
from app.generator.inp_generator import _generate_energy_mesh, _generate_cut, _generate_en_cards


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

        # ===== En 分计数能量箱 =====
        grp_en = QGroupBox("分计数能量箱（En 卡）")
        grp_en.setToolTip(
            "每个勾选了 En 的计数可独立设置能量网格，完全复制 E0 的 UI。\n"
            "在「计数卡」标签页中勾选 En 即可激活对应 En 卡。"
        )
        en_layout = QVBoxLayout(grp_en)
        self._en_container = QVBoxLayout()
        en_layout.addLayout(self._en_container)
        self._en_rows = {}  # tally_number -> dict of all widgets
        self._en_note = QLabel("（在「计数卡」标签页中为 Fn 勾选 En 即可在此编辑）")
        self._en_note.setStyleSheet("color: gray; font-size: 11px;")
        self._en_container.addWidget(self._en_note)
        layout.addWidget(grp_en)

        # ===== CUT 时间+能量截断 =====
        grp_cut = QGroupBox()
        grp_cut.setToolTip(
            "CUT:N tcut ecut — 时间截断 + 能量截断\n"
            "tcut = 时间截断 (shake, 1 shake = 10⁻⁸ s, 0 = 不限)\n"
            "ecut = 能量截断 (MeV)，低于此能量的粒子被杀死"
        )
        cut_container = QWidget()
        cut_vbox = QVBoxLayout(cut_container)
        cut_vbox.setSpacing(4)
        cut_vbox.setContentsMargins(0, 0, 0, 0)

        # 表头（宽度与行控件对齐）
        header_row = QWidget()
        header_hbox = QHBoxLayout(header_row)
        header_hbox.setContentsMargins(0, 0, 0, 0)
        head_info = [("粒子", 80), ("tme", 100), ("e", 100),
                     ("wc1", 100), ("wc2", 100), ("swtm", 100)]
        for text, w in head_info:
            lbl = QLabel(f"<b>{text}</b>")
            lbl.setMinimumWidth(w)
            header_hbox.addWidget(lbl)
        header_hbox.addStretch()
        cut_vbox.addWidget(header_row)

        # CUT 行定义: (粒子名, 显示标签, 默认可见)
        cut_defs = [
            ("n",  "CUT:N 中子",   True),
            ("p",  "CUT:P 光子",   True),
            ("e",  "CUT:E 电子",   True),
            ("h",  "CUT:H 质子",   True),
            ("he", "CUT:HE 重离子", True),
            ("d",  "CUT:D 氘核",   False),
            ("t",  "CUT:T 氚核",   False),
            ("a",  "CUT:A α粒子", False),
        ]
        field_names = ["t", "e", "wc1", "wc2", "swtm"]
        field_labels = {"t": "时间截断", "e": "能量截断",
                        "wc1": "权重比1", "wc2": "权重比2", "swtm": "群标志"}
        particle_cn = {"n":"中子","p":"光子","e":"电子","h":"质子",
                       "he":"重离子","d":"氘核","t":"氚核","a":"α粒子"}
        self._cut_rows = {}
        for p, label, _visible in cut_defs:
            row = QWidget()
            row.setVisible(True)
            hbox = QHBoxLayout(row)
            hbox.setContentsMargins(0, 0, 0, 0)
            hbox.addWidget(QLabel(label))
            for fn in field_names:
                le = QLineEdit()
                le.setPlaceholderText("留空")
                le.setMaximumWidth(100)
                le.setToolTip(f"{particle_cn.get(p,p)} {field_labels[fn]}")
                setattr(self, f"cut_{p}_{fn}", le)
                hbox.addWidget(le)
            hbox.addStretch()
            cut_vbox.addWidget(row)
            self._cut_rows[p] = row

        cut_hint = QLabel(
            "<span style='color:gray; font-size:11px;'>"
            "💡 留空 = 使用 MCNP 默认值（导入时 j-skip 语法会自动展开到各字段）</span>"
        )
        cut_vbox.addWidget(cut_hint)

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
            cut_n_wc1=self.cut_n_wc1.text().strip(),
            cut_n_wc2=self.cut_n_wc2.text().strip(),
            cut_n_swtm=self.cut_n_swtm.text().strip(),
            cut_p_t=self.cut_p_t.text().strip(),
            cut_p_e=self.cut_p_e.text().strip(),
            cut_p_wc1=self.cut_p_wc1.text().strip(),
            cut_p_wc2=self.cut_p_wc2.text().strip(),
            cut_p_swtm=self.cut_p_swtm.text().strip(),
            cut_e_t=self.cut_e_t.text().strip(),
            cut_e_e=self.cut_e_e.text().strip(),
            cut_e_wc1=self.cut_e_wc1.text().strip(),
            cut_e_wc2=self.cut_e_wc2.text().strip(),
            cut_e_swtm=self.cut_e_swtm.text().strip(),
            cut_h_t=self.cut_h_t.text().strip(),
            cut_h_e=self.cut_h_e.text().strip(),
            cut_h_wc1=self.cut_h_wc1.text().strip(),
            cut_h_wc2=self.cut_h_wc2.text().strip(),
            cut_h_swtm=self.cut_h_swtm.text().strip(),
            cut_he_t=self.cut_he_t.text().strip(),
            cut_he_e=self.cut_he_e.text().strip(),
            cut_he_wc1=self.cut_he_wc1.text().strip(),
            cut_he_wc2=self.cut_he_wc2.text().strip(),
            cut_he_swtm=self.cut_he_swtm.text().strip(),
            cut_d_t=self.cut_d_t.text().strip(),
            cut_d_e=self.cut_d_e.text().strip(),
            cut_d_wc1=self.cut_d_wc1.text().strip(),
            cut_d_wc2=self.cut_d_wc2.text().strip(),
            cut_d_swtm=self.cut_d_swtm.text().strip(),
            cut_t_t=self.cut_t_t.text().strip(),
            cut_t_e=self.cut_t_e.text().strip(),
            cut_t_wc1=self.cut_t_wc1.text().strip(),
            cut_t_wc2=self.cut_t_wc2.text().strip(),
            cut_t_swtm=self.cut_t_swtm.text().strip(),
            cut_a_t=self.cut_a_t.text().strip(),
            cut_a_e=self.cut_a_e.text().strip(),
            cut_a_wc1=self.cut_a_wc1.text().strip(),
            cut_a_wc2=self.cut_a_wc2.text().strip(),
            cut_a_swtm=self.cut_a_swtm.text().strip(),
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
            'e_cards_text': self._en_rows_to_text(),
            'cut_n_t': self.cut_n_t.text().strip(),
            'cut_n_e': self.cut_n_e.text().strip(),
            'cut_n_wc1': self.cut_n_wc1.text().strip(),
            'cut_n_wc2': self.cut_n_wc2.text().strip(),
            'cut_n_swtm': self.cut_n_swtm.text().strip(),
            'cut_p_t': self.cut_p_t.text().strip(),
            'cut_p_e': self.cut_p_e.text().strip(),
            'cut_p_wc1': self.cut_p_wc1.text().strip(),
            'cut_p_wc2': self.cut_p_wc2.text().strip(),
            'cut_p_swtm': self.cut_p_swtm.text().strip(),
            'cut_e_t': self.cut_e_t.text().strip(),
            'cut_e_e': self.cut_e_e.text().strip(),
            'cut_e_wc1': self.cut_e_wc1.text().strip(),
            'cut_e_wc2': self.cut_e_wc2.text().strip(),
            'cut_e_swtm': self.cut_e_swtm.text().strip(),
            'cut_h_t': self.cut_h_t.text().strip(),
            'cut_h_e': self.cut_h_e.text().strip(),
            'cut_h_wc1': self.cut_h_wc1.text().strip(),
            'cut_h_wc2': self.cut_h_wc2.text().strip(),
            'cut_h_swtm': self.cut_h_swtm.text().strip(),
            'cut_he_t': self.cut_he_t.text().strip(),
            'cut_he_e': self.cut_he_e.text().strip(),
            'cut_he_wc1': self.cut_he_wc1.text().strip(),
            'cut_he_wc2': self.cut_he_wc2.text().strip(),
            'cut_he_swtm': self.cut_he_swtm.text().strip(),
            'cut_d_t': self.cut_d_t.text().strip(),
            'cut_d_e': self.cut_d_e.text().strip(),
            'cut_d_wc1': self.cut_d_wc1.text().strip(),
            'cut_d_wc2': self.cut_d_wc2.text().strip(),
            'cut_d_swtm': self.cut_d_swtm.text().strip(),
            'cut_t_t': self.cut_t_t.text().strip(),
            'cut_t_e': self.cut_t_e.text().strip(),
            'cut_t_wc1': self.cut_t_wc1.text().strip(),
            'cut_t_wc2': self.cut_t_wc2.text().strip(),
            'cut_t_swtm': self.cut_t_swtm.text().strip(),
            'cut_a_t': self.cut_a_t.text().strip(),
            'cut_a_e': self.cut_a_e.text().strip(),
            'cut_a_wc1': self.cut_a_wc1.text().strip(),
            'cut_a_wc2': self.cut_a_wc2.text().strip(),
            'cut_a_swtm': self.cut_a_swtm.text().strip(),
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
        # 从 e_cards_text 恢复 En 行（如为空则自动从 E0 填充）
        self._en_rows_from_text(tally.e_cards_text or "")

        # CUT（留空则留空） — C810: T E WC1 WC2 SWTM
        self.cut_n_t.setText(tally.cut_n_t or "")
        self.cut_n_e.setText(tally.cut_n_e or "")
        self.cut_n_wc1.setText(tally.cut_n_wc1 or "")
        self.cut_n_wc2.setText(tally.cut_n_wc2 or "")
        self.cut_n_swtm.setText(tally.cut_n_swtm or "")
        self.cut_p_t.setText(tally.cut_p_t or "")
        self.cut_p_e.setText(tally.cut_p_e or "")
        self.cut_p_wc1.setText(tally.cut_p_wc1 or "")
        self.cut_p_wc2.setText(tally.cut_p_wc2 or "")
        self.cut_p_swtm.setText(tally.cut_p_swtm or "")
        self.cut_e_t.setText(tally.cut_e_t or "")
        self.cut_e_e.setText(tally.cut_e_e or "")
        self.cut_e_wc1.setText(tally.cut_e_wc1 or "")
        self.cut_e_wc2.setText(tally.cut_e_wc2 or "")
        self.cut_e_swtm.setText(tally.cut_e_swtm or "")
        self.cut_h_t.setText(tally.cut_h_t or "")
        self.cut_h_e.setText(tally.cut_h_e or "")
        self.cut_h_wc1.setText(tally.cut_h_wc1 or "")
        self.cut_h_wc2.setText(tally.cut_h_wc2 or "")
        self.cut_h_swtm.setText(tally.cut_h_swtm or "")
        self.cut_he_t.setText(tally.cut_he_t or "")
        self.cut_he_e.setText(tally.cut_he_e or "")
        self.cut_he_wc1.setText(tally.cut_he_wc1 or "")
        self.cut_he_wc2.setText(tally.cut_he_wc2 or "")
        self.cut_he_swtm.setText(tally.cut_he_swtm or "")
        self.cut_d_t.setText(getattr(tally, 'cut_d_t', '') or "")
        self.cut_d_e.setText(getattr(tally, 'cut_d_e', '') or "")
        self.cut_d_wc1.setText(getattr(tally, 'cut_d_wc1', '') or "")
        self.cut_d_wc2.setText(getattr(tally, 'cut_d_wc2', '') or "")
        self.cut_d_swtm.setText(getattr(tally, 'cut_d_swtm', '') or "")
        self.cut_t_t.setText(getattr(tally, 'cut_t_t', '') or "")
        self.cut_t_e.setText(getattr(tally, 'cut_t_e', '') or "")
        self.cut_t_wc1.setText(getattr(tally, 'cut_t_wc1', '') or "")
        self.cut_t_wc2.setText(getattr(tally, 'cut_t_wc2', '') or "")
        self.cut_t_swtm.setText(getattr(tally, 'cut_t_swtm', '') or "")
        self.cut_a_t.setText(getattr(tally, 'cut_a_t', '') or "")
        self.cut_a_e.setText(getattr(tally, 'cut_a_e', '') or "")
        self.cut_a_wc1.setText(getattr(tally, 'cut_a_wc1', '') or "")
        self.cut_a_wc2.setText(getattr(tally, 'cut_a_wc2', '') or "")
        self.cut_a_swtm.setText(getattr(tally, 'cut_a_swtm', '') or "")
    
    def _create_en_row(self, tally_num: int):
        """创建 En 编辑区块，完全复制 E0 的 UI 结构"""
        grp = QGroupBox(f"E{tally_num}  — 计数 F{tally_num} 专用能量网格")
        grp.setToolTip(
            f"为计数 F{tally_num} 单独设置能量分界。\n"
            "留空所有字段则计数使用全局 E0 网格。"
        )
        form = QFormLayout(grp)
        form.setSpacing(6)

        # 能量范围
        range_box = QHBoxLayout()
        le_min = QLineEdit("")
        le_min.setPlaceholderText("如 0.001")
        le_min.setToolTip(f"E{tally_num} 能量最低值（MeV），留空使用 E0")
        le_max = QLineEdit("")
        le_max.setPlaceholderText("如 14")
        le_max.setToolTip(f"E{tally_num} 能量最高值（MeV），留空使用 E0")
        range_box.addWidget(QLabel("从"))
        range_box.addWidget(le_min)
        range_box.addWidget(QLabel("到"))
        range_box.addWidget(le_max)
        range_box.addWidget(QLabel("MeV"))
        form.addRow("能量范围:", range_box)

        # 间隔数
        sb_bins = QSpinBox()
        sb_bins.setRange(0, 10000)
        sb_bins.setValue(0)
        sb_bins.setSpecialValueText("使用 E0")
        sb_bins.setToolTip(f"E{tally_num} 能量间隔数，0=使用 E0 网格")
        form.addRow("间隔数:", sb_bins)

        # 对数
        cb_log = QCheckBox("对数网格（勾选=对数，不勾=线性）")
        cb_log.setToolTip(
            "对数网格：低能区道宽小，高能区道宽大。\n"
            "线性网格：所有能道等宽。"
        )
        form.addRow("", cb_log)

        # 自定义网格
        cb_custom = QCheckBox("自定义网格（手动输入能量边界，勾选后忽略上面设置）")
        cb_custom.setToolTip(
            "勾选后自行输入能量边界值，每行一个能量（MeV），从小到大。"
        )
        form.addRow("", cb_custom)

        custom_edit = QPlainTextEdit()
        custom_edit.setPlaceholderText(
            "示例 (从低到高，每行一个):\n"
            "0.001\n0.01\n0.1\n1\n10\n14"
        )
        custom_edit.setMaximumHeight(80)
        custom_edit.setVisible(False)
        cb_custom.toggled.connect(custom_edit.setVisible)
        form.addRow("", custom_edit)

        # 插入到 note 之前
        self._en_container.insertWidget(self._en_container.count() - 1, grp)
        self._en_rows[tally_num] = {
            "widget": grp,
            "min": le_min, "max": le_max, "bins": sb_bins, "log": cb_log,
            "custom_cb": cb_custom, "custom_edit": custom_edit,
        }
        return grp

    def update_en_preview(self, tallies: list):
        """根据计数卡列表创建/删除/更新 En 行，Fn 编号变化时保留数据。
        未勾选 En 且无数据的行自动消失；有导入数据的行灰显保留。"""
        existing_nums = {td.number for td in tallies}
        en_map = {td.number: getattr(td, 'generate_en', False) for td in tallies}

        # 更新现有行的编号（Fn 编号变化时保留已填数据）
        old_keys = list(self._en_rows.keys())
        for i, num in enumerate(sorted(existing_nums)):
            if num in self._en_rows:
                continue
            if i < len(old_keys) and old_keys[i] in self._en_rows:
                old_num = old_keys[i]
                if old_num not in existing_nums:
                    row_data = self._en_rows.pop(old_num)
                    self._en_rows[num] = row_data
                    row_data["widget"].setTitle(
                        f"E{num}  — 计数 F{num} 专用能量网格")

        # 删除不存在的计数对应的行
        for num in list(self._en_rows.keys()):
            if num not in existing_nums:
                row_data = self._en_rows.pop(num)
                row_data["widget"].setParent(None)
                row_data["widget"].deleteLater()

        # 为勾选 En 的行创建（如该计数尚无行）
        for num in sorted(existing_nums):
            if num not in self._en_rows and en_map.get(num, False):
                self._create_en_row(num)

        # 处理未勾选的行：有数据则灰显保留，无数据则消失
        for num in list(self._en_rows.keys()):
            if en_map.get(num, False):
                self._en_rows[num]["widget"].setEnabled(True)
            else:
                rd = self._en_rows[num]
                has_data = bool(
                    rd["min"].text().strip()
                    or rd["max"].text().strip()
                    or rd["bins"].value() > 0
                    or (rd.get("custom_cb") and rd["custom_cb"].isChecked())
                    or (rd.get("custom_edit") and rd["custom_edit"].toPlainText().strip())
                )
                if has_data:
                    rd["widget"].setEnabled(False)
                else:
                    rd["widget"].setParent(None)
                    rd["widget"].deleteLater()
                    del self._en_rows[num]

        # 更新 note 显隐
        self._en_note.setVisible(not bool(self._en_rows))

    def _en_rows_to_text(self) -> str:
        """将 En 行数据序列化为 e_cards_text 格式"""
        if not self._en_rows:
            return ""
        lines = []
        for num in sorted(self._en_rows.keys()):
            r = self._en_rows[num]
            custom_text = r.get("custom_edit", None)
            if custom_text and r.get("custom_cb", None) and r["custom_cb"].isChecked():
                raw = custom_text.toPlainText().strip()
                if raw:
                    lines.append(f"E{num}  {raw.replace(chr(10), ' ')}")
                    continue

            e_min = r["min"].text().strip()
            e_max = r["max"].text().strip()
            e_bins = r["bins"].value()
            e_log = r["log"].isChecked()

            if e_min and e_bins > 0 and e_max:
                grid = "log" if e_log else "i"
                lines.append(f"E{num}  {e_min} {e_bins}{grid} {e_max}")
            elif e_min and e_max and not (e_bins > 0):
                # 只有 min 和 max，无 bins → 输出为 2 个显式值
                lines.append(f"E{num}  {e_min} {e_max}")
            elif e_min and e_max and e_bins > 0:
                # 三个都填了但上一条没匹配（理论上不会发生），兜底输出完整格式
                grid = "log" if e_log else "i"
                lines.append(f"E{num}  {e_min} {e_bins}{grid} {e_max}")
        return "\n".join(lines)

    def _en_rows_from_text(self, text: str):
        """从 e_cards_text 恢复 En 行"""
        # 先清理所有现有行
        for num in list(self._en_rows.keys()):
            row_data = self._en_rows.pop(num)
            row_data["widget"].setParent(None)
            row_data["widget"].deleteLater()

        if not text or not text.strip():
            self._en_note.setVisible(True)
            return

        import re
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            m = re.match(r'^E(\d+)(?:\s+(.*))?$', line, re.IGNORECASE)
            if not m:
                continue
            num = int(m.group(1))
            if num in self._en_rows:
                continue  # 跳过重复的 En 编号，避免 widget 泄漏
            self._create_en_row(num)
            row_data = self._en_rows.get(num)
            if not row_data:
                continue
            params = (m.group(2) or "").strip()
            if params:
                # 解析 min nlog max 或 min 或 值列表
                pts = params.split()
                if len(pts) >= 3 and re.match(r'\d+(log|lin|i)$', pts[1].lower()):
                    row_data["min"].setText(pts[0])
                    row_data["max"].setText(pts[2])
                    nl_m = re.match(r'^(\d+)(LOG|LIN|I)$', pts[1].upper())
                    if nl_m:
                        is_log = nl_m.group(2) == "LOG"
                        row_data["log"].setChecked(is_log)
                        try:
                            row_data["bins"].setValue(int(nl_m.group(1)))
                        except ValueError:
                            pass
                elif len(pts) >= 3:
                    # 显式值列表（如 E15  0.001 0.01 0.1 1 10）→ 放入自定义网格
                    row_data["custom_cb"].setChecked(True)
                    row_data["custom_edit"].setPlainText("\n".join(pts))
                elif len(pts) == 2:
                    row_data["min"].setText(pts[0])
                    row_data["max"].setText(pts[1])
                elif len(pts) == 1:
                    row_data["min"].setText(pts[0])
        self._en_note.setVisible(bool(self._en_rows))

    def sync_cut_with_mode(self, basic):
        """CUT 全部显示，不再依赖 MODE"""
        pass
