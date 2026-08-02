"""Tally — 控制器层"""

import re
from PyQt5.QtWidgets import (
    QWidget, QLabel, QComboBox, QLineEdit, QCheckBox, QPushButton,
    QMessageBox, QHBoxLayout, QVBoxLayout, QSpinBox, QPlainTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, pyqtSignal, QSettings

from app.models import TallySettings, TallyDefinition
from app.widgets.ui_helpers import (
    make_centered_label, make_centered_edit, make_table_checkbox,
)
from .view import create_ui, _type_param_placeholder, _type_param_tooltip, _TYPE_CN_NAME


class TallyTab(QWidget):

    talliesChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._en_rows: dict[int, dict] = {}
        self._tn_rows: dict[int, dict] = {}
        self._col_settings = QSettings("MCNPGen", "MCNPGenerator")
        self._column_widths_key = "tally_tab_column_widths"

        ui, raw_tally, raw_e0, raw_t0 = create_ui(
            self,
            gen_tally_fn=lambda: self._gen_tally_raw(),
            gen_e0_fn=lambda: self._gen_e0_raw(),
            gen_t0_fn=lambda: self._gen_t0_raw(),
        )
        self.ui = ui
        self._raw_tally = raw_tally
        self._raw_e0 = raw_e0
        self._raw_t0 = raw_t0

        self._connect_signals()
        self._restore_column_widths()
        self.talliesChanged.connect(self._on_tallies_changed)

    def _connect_signals(self):
        self.ui.btn_add.clicked.connect(self._add_default_tally)
        self.ui.btn_del.clicked.connect(self._delete_selected)
        self.ui.table.horizontalHeader().sectionResized.connect(self._save_column_widths)
        self.ui.e_custom_cb.toggled.connect(self._toggle_custom_grid)
        self.ui.t0_custom_cb.toggled.connect(self._toggle_t0_custom)

    def _restore_column_widths(self):
        saved = self._col_settings.value(self._column_widths_key)
        if saved and len(saved) >= 6:
            for col, w in enumerate(saved[:6]):
                self.ui.table.setColumnWidth(col, int(w))

    def _save_column_widths(self):
        widths = [self.ui.table.columnWidth(c) for c in range(self.ui.table.columnCount())]
        self._col_settings.setValue(self._column_widths_key, widths)

    @staticmethod
    def _auto_resize_table(table, min_rows=8):
        n = table.rowCount()
        rows = max(min_rows, n)
        hh = table.horizontalHeader().height() or 28
        rh = table.rowHeight(0) if n > 0 else 30
        fw = 2 * table.frameWidth()
        table.setMinimumHeight(hh + rh * rows + fw + 4)

    # ── E0 / T0 ──

    def _toggle_custom_grid(self, checked):
        self.ui.e_custom_edit.setVisible(checked)

    def _toggle_t0_custom(self, checked):
        self.ui.t0_custom_edit.setVisible(checked)

    def _gen_e0_raw(self) -> str:
        from app.models import TallySettings as _TS
        from app.generator.inp_generator import _generate_energy_mesh as _gem
        ts = _TS(e_min=self.ui.e_min.text().strip(), e_max=self.ui.e_max.text().strip(),
                  e_bins=self.ui.e_bins.value(), e_log=self.ui.e_log_cb.isChecked(),
                  e_custom_enabled=self.ui.e_custom_cb.isChecked(),
                  e_custom_text=self.ui.e_custom_edit.toPlainText().strip())
        return "\n".join(_gem(ts))

    def _gen_t0_raw(self) -> str:
        parts = []
        if self.ui.t0_custom_cb.isChecked():
            raw = self.ui.t0_custom_edit.toPlainText().strip()
            if raw:
                parts.append("T0  " + raw.replace("\n", " "))
        else:
            tmin = self.ui.t0_min.text().strip()
            tmax = self.ui.t0_max.text().strip()
            nbins = self.ui.t0_bins.value()
            if tmin and tmax and nbins > 0:
                grid = "log" if self.ui.t0_log_cb.isChecked() else "i"
                parts.append(f"T0  {tmin} {nbins}{grid} {tmax}")
        return "\n".join(parts)

    # ── 公开接口 ──

    def get_data(self) -> dict:
        return {
            "tallies": self._collect_tallies(),
            'e_min': self.ui.e_min.text().strip(),
            'e_max': self.ui.e_max.text().strip(),
            'e_bins': self.ui.e_bins.value(),
            'e_log': self.ui.e_log_cb.isChecked(),
            'e_custom_enabled': self.ui.e_custom_cb.isChecked(),
            'e_custom_text': self.ui.e_custom_edit.toPlainText().strip(),
            'e_cards_text': self._en_rows_to_text(),
            't0_min': self.ui.t0_min.text().strip(),
            't0_max': self.ui.t0_max.text().strip(),
            't0_bins': self.ui.t0_bins.value(),
            't0_log': self.ui.t0_log_cb.isChecked(),
            't0_custom_enabled': self.ui.t0_custom_cb.isChecked(),
            't0_custom_text': self.ui.t0_custom_edit.toPlainText().strip(),
            't0_text': self._tn_rows_to_text(),
        }

    def set_data(self, tally: TallySettings):
        self.ui.e_min.setText(tally.e_min or "")
        self.ui.e_max.setText(tally.e_max or "")
        self.ui.e_bins.setValue(tally.e_bins or 0)
        self.ui.e_log_cb.setChecked(tally.e_log or False)
        self.ui.e_custom_cb.setChecked(tally.e_custom_enabled or False)
        self.ui.e_custom_edit.setPlainText(tally.e_custom_text or "")
        self.ui.t0_min.setText(getattr(tally, 't0_min', '') or "")
        self.ui.t0_max.setText(getattr(tally, 't0_max', '') or "")
        self.ui.t0_bins.setValue(getattr(tally, 't0_bins', 0) or 0)
        self.ui.t0_log_cb.setChecked(getattr(tally, 't0_log', False) or False)
        self.ui.t0_custom_cb.setChecked(getattr(tally, 't0_custom_enabled', False) or False)
        self.ui.t0_custom_edit.setPlainText(getattr(tally, 't0_custom_text', '') or "")
        self._clear_table()
        for td in tally.tallies:
            self._add_row(
                tally_type=td.type, number=td.number,
                particles=td.particles[0] if td.particles else "n",
                params=td.params, generate_en=td.generate_en,
                generate_tn=td.generate_tn,
                fn_prefix=td.fn_prefix,
                number_suffix=getattr(td, 'number_suffix', ''),
            )
        self.talliesChanged.emit()

    def get_raw_overrides(self) -> dict:
        return {
            "tally": self._raw_tally.get_raw_text(),
            "e0": self._raw_e0.get_raw_text(),
            "t0": self._raw_t0.get_raw_text(),
        }

    # ── En/Tn 预览 ──

    def _on_tallies_changed(self):
        d = self.get_data()
        tl = d.get("tallies", [])
        self.update_en_preview(tl)
        self.update_tn_preview(tl, d)

    def update_en_preview(self, tallies: list):
        self._update_preview(self.ui.en_container, tallies, "E", "e_cards_text",
                             self.ui.e_min.text(), self.ui.e_max.text(), self.ui.e_bins.value(), self.ui.e_log_cb.isChecked())

    def update_tn_preview(self, tallies: list, tally_data: dict = None):
        self._update_preview(self.ui.tn_container, tallies, "T", "t0_text",
                             self.ui.t0_min.text(), self.ui.t0_max.text(), self.ui.t0_bins.value(), self.ui.t0_log_cb.isChecked())

    def _update_preview(self, container, tallies, prefix, _unused, _a, _b, _c, _d):
        from PyQt5.QtWidgets import QLabel as _QL, QHBoxLayout as _HL, QLineEdit as _LE, QSpinBox as _SB, QCheckBox as _CB, QWidget as _W
        # 完全清空容器（保留索引 0 的 note）
        while container.count() > 1:
            it = container.takeAt(container.count() - 1)
            if it.widget(): it.widget().deleteLater()
        attr = "generate_en" if prefix == "E" else "generate_tn"
        sel = [td for td in tallies if getattr(td, attr, False)]
        nums = sorted(set(td.number for td in sel))
        rows_dict = self._en_rows if prefix == "E" else self._tn_rows
        rows_dict.clear()
        if not nums:
            return
        for n in nums:
            row = _W()
            h = _HL(row)
            h.setContentsMargins(0, 2, 0, 2)
            h.addWidget(_QL(f"{prefix}{n}:"))
            le_min = _LE(); le_min.setPlaceholderText("最低"); le_min.setMaximumWidth(70)
            le_max = _LE(); le_max.setPlaceholderText("最高"); le_max.setMaximumWidth(70)
            sb = _SB(); sb.setRange(0, 10000); sb.setSpecialValueText("—"); sb.setMaximumWidth(60)
            cb = _CB("对数")
            h.addWidget(le_min); h.addWidget(le_max); h.addWidget(sb); h.addWidget(cb)
            h.addStretch()
            container.addWidget(row)
            rows_dict[n] = {"min": le_min, "max": le_max, "bins": sb, "log": cb}

    # ── 内部 ──

    def _clear_table(self):
        self.ui.table.setRowCount(0)

    def _collect_tallies(self) -> list[TallyDefinition]:
        tallies = []
        for row in range(self.ui.table.rowCount()):
            cb_prefix = self.ui.table.cellWidget(row, 0)
            lbl_type = self.ui.table.cellWidget(row, 1)
            sb_num = self.ui.table.cellWidget(row, 2)
            le_part = self.ui.table.cellWidget(row, 3)
            le_params = self.ui.table.cellWidget(row, 4)
            cb_en = self.ui.table.cellWidget(row, 5)
            cb_tn = self.ui.table.cellWidget(row, 6)

            if not lbl_type or not sb_num:
                continue

            tally_type = lbl_type.text().strip().split()[0]
            num_text = sb_num.text().strip()
            num_m = re.match(r'^(\d+)([XYZ]?)$', num_text, re.I)
            if not num_m or int(num_m.group(1)) == 0:
                continue
            number = int(num_m.group(1))
            num_suffix = (num_m.group(2) or "").upper()

            raw_particles = le_part.text().strip() if le_part else ""
            particles = [p.strip().lower() for p in raw_particles.split() if p.strip()]
            if not particles:
                particles = ["n"]

            params = le_params.text().strip() if le_params else ""
            generate_en = cb_en.isChecked() if cb_en else True
            generate_tn = cb_tn.isChecked() if cb_tn else False
            prefix = cb_prefix.currentText().strip() if cb_prefix else ""

            tallies.append(TallyDefinition(
                type=tally_type, number=number,
                particles=particles, params=params,
                generate_en=generate_en, generate_tn=generate_tn,
                fn_prefix=prefix, number_suffix=num_suffix,
            ))
        return tallies

    def _add_row(self, tally_type="F4", number=4, particles="n", params="",
                 generate_en=False, generate_tn=False,
                 fn_prefix="", number_suffix=""):
        row = self.ui.table.rowCount()
        self.ui.table.insertRow(row)

        # 0 前缀
        cb_pre = QComboBox()
        tt = tally_type.upper()
        if tt in ("F5", "FIP", "FIR", "FIC"):
            cb_pre.addItems(["", "FIP", "FIR", "FIC"])
            cb_pre.setToolTip("F5 点/环探测器留空；通量成像选 FIP/FIR/FIC")
        else:
            is_f8 = tt.startswith('F8')
            cb_pre.addItems(["", "*"] + (["+"] if is_f8 else []))
            cb_pre.setToolTip("* = 能量/MeV" + ("  + = 电荷(F8)" if is_f8 else ""))
        pre = fn_prefix.strip()
        cb_pre.setCurrentIndex(cb_pre.findText(pre) if pre else 0)
        self.ui.table.setCellWidget(row, 0, cb_pre)

        # 1 类型
        cn_name = _TYPE_CN_NAME.get(tally_type, "")
        type_text = f"{tally_type} {cn_name}" if cn_name else tally_type
        lbl_type = make_centered_label(type_text, bold=True,
            tooltip=f"计数类型（由编号末位自动决定）\n{tally_type} = {cn_name}")
        self.ui.table.setCellWidget(row, 1, lbl_type)

        # 2 编号
        le_num = make_centered_edit(text=f"{number}{number_suffix}", max_length=6,
            tooltip="计数编号（如 1, 2, 5, 15, 25…）\nF5 环探测器可在数字后加轴字母，如 5X / 5Y / 5Z")
        le_num.editingFinished.connect(lambda r=row, le=le_num: self._on_number_changed(r, le.text()))
        self.ui.table.setCellWidget(row, 2, le_num)

        # 3 粒子
        le_part = make_centered_edit(text=particles, placeholder="如: n  n p  n p e h he",
            tooltip="粒子类型，空格分隔。可用: n p e h he")
        self.ui.table.setCellWidget(row, 3, le_part)

        # 4 参数
        le_params = make_centered_edit(text=params,
            placeholder=_type_param_placeholder(tally_type),
            tooltip=_type_param_tooltip(tally_type))
        self.ui.table.setCellWidget(row, 4, le_params)

        # 5 En
        cb_en = make_table_checkbox(checked=generate_en,
            tooltip="勾选=自动生成该计数的 En 能量卡（使用 E0 的能量网格参数）")
        cb_en.toggled.connect(self.talliesChanged.emit)
        self.ui.table.setCellWidget(row, 5, cb_en)

        # 6 Tn
        cb_tn = make_table_checkbox(checked=generate_tn,
            tooltip="勾选=自动生成该计数的 Tn 时间卡（使用 T0 的时间网格参数）")
        cb_tn.toggled.connect(self.talliesChanged.emit)
        self.ui.table.setCellWidget(row, 6, cb_tn)

        # 7 删除
        btn_del = QPushButton("× 删除")
        btn_del.setToolTip("删除此行")
        btn_del.setProperty("cssClass", "btnDeleteRow")
        btn_del.clicked.connect(lambda checked, w=btn_del: self._delete_row(w))
        self.ui.table.setCellWidget(row, 7, btn_del)

        self.ui.table.setRowHeight(row, 50)
        self._auto_resize_table(self.ui.table)

    def _on_number_changed(self, row: int, text: str):
        m = re.match(r'^(\d+)([XYZ]?)$', text.strip(), re.I)
        if not m:
            return
        value = int(m.group(1))
        from .view import _number_to_type
        new_type = _number_to_type(value)
        if new_type is None:
            return
        lbl = self.ui.table.cellWidget(row, 1)
        current_short = lbl.text().split()[0] if lbl else ""
        if lbl and current_short != new_type:
            cn_name = _TYPE_CN_NAME.get(new_type, "")
            lbl.setText(f"{new_type} {cn_name}" if cn_name else new_type)
            lbl.setToolTip(f"计数类型（由编号末位自动决定）\n{new_type} = {cn_name}")
            # 更新参数提示
            le_params = self.ui.table.cellWidget(row, 4)
            if le_params:
                le_params.setPlaceholderText(_type_param_placeholder(new_type))
                le_params.setToolTip(_type_param_tooltip(new_type))
            # 更新前缀
            cb_pre = self.ui.table.cellWidget(row, 0)
            if cb_pre:
                old_pre = cb_pre.currentText()
                is_f5 = new_type in ("F5", "FIP", "FIR", "FIC")
                cb_pre.blockSignals(True); cb_pre.clear()
                if is_f5:
                    cb_pre.addItems(["", "FIP", "FIR", "FIC"])
                else:
                    is_f8 = new_type.startswith('F8')
                    cb_pre.addItems(["", "*"] + (["+"] if is_f8 else []))
                    cb_pre.setToolTip("* = 能量/MeV" + ("  + = 电荷(F8)" if is_f8 else ""))
                idx = cb_pre.findText(old_pre) if old_pre else 0
                if idx < 0: idx = 0
                cb_pre.setCurrentIndex(idx)
                cb_pre.blockSignals(False)
        self.talliesChanged.emit()

    def _delete_row(self, btn_widget):
        for row in range(self.ui.table.rowCount()):
            if self.ui.table.cellWidget(row, 7) is btn_widget:
                self.ui.table.removeRow(row)
                self._auto_resize_table(self.ui.table)
                self.talliesChanged.emit()
                return

    def _delete_selected(self):
        rows = sorted(set(idx.row() for idx in self.ui.table.selectedIndexes()), reverse=True)
        if not rows:
            QMessageBox.information(self, "提示", "请先选中要删除的计数行")
            return
        for r in rows:
            self.ui.table.removeRow(r)
        self._auto_resize_table(self.ui.table)
        self.talliesChanged.emit()

    def _add_default_tally(self):
        self._add_row("F4", 4, "n", "")
        self.talliesChanged.emit()

    def _gen_tally_raw(self) -> str:
        from app.generator.inp_generator import _generate_tallies
        from app.models import TallySettings
        ts = TallySettings(tallies=self._collect_tallies())
        return "\n".join(_generate_tallies(ts))

    def _en_rows_to_text(self) -> str:
        lines = []
        for num in sorted(self._en_rows):
            r = self._en_rows[num]
            le_min = r.get('min')
            le_max = r.get('max')
            sb_bins = r.get('bins')
            cb_log = r.get('log')
            if le_min and le_max and sb_bins and sb_bins.value() > 0:
                lo = "LOG" if cb_log and cb_log.isChecked() else "I"
                lines.append(f"E{num}  {le_min.text().strip()} {sb_bins.value():d}{lo} {le_max.text().strip()}")
        return "\n".join(lines)

    def _tn_rows_to_text(self) -> str:
        lines = []
        for num in sorted(self._tn_rows):
            r = self._tn_rows[num]
            le_min = r.get('min')
            le_max = r.get('max')
            sb_bins = r.get('bins')
            cb_log = r.get('log')
            if le_min and le_max and sb_bins and sb_bins.value() > 0:
                lo = "LOG" if cb_log and cb_log.isChecked() else "I"
                lines.append(f"T{num}  {le_min.text().strip()} {sb_bins.value():d}{lo} {le_max.text().strip()}")
        return "\n".join(lines)
