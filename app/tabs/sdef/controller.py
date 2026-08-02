"""Sdef — 控制器层"""

import json, re
from PyQt5.QtWidgets import QWidget, QTableWidgetItem, QPushButton, QMessageBox, QHeaderView
from PyQt5.QtCore import Qt, QSettings

from app.models import SourceData, AdvancedSettings
from app.dialogs.source_edit_dialog import SourceEditDialog
from app.generator.inp_generator import _generate_sdef, _generate_distribution_sdef
from .view import create_ui


class SdefTab(QWidget):

    def __init__(self):
        super().__init__()
        self.sources: list[SourceData] = []
        self._saved_raw = ""
        self._mt_settings = QSettings("MCNPGen", "MCNPGenerator")
        self._current_mode = 0  # 0=fixed, 1=dist, 2=kcode
        self.dist_pairs: list[dict] = []

        ui, btn_extra, raw_sdef, raw_dist = create_ui(
            self,
            gen_fn=lambda: self._gen_sdef_raw(),
            gen_dist_fn=lambda: self._gen_dist_raw(),
        )
        self.ui = ui
        self._raw_sdef = raw_sdef
        self._raw_dist = raw_dist

        self._connect_signals(btn_extra)
        self._restore_col_widths()
        self._update_mode()

    def _connect_signals(self, btn_extra):
        self.ui.btn_add.clicked.connect(self._add_source)
        self.ui.btn_del.clicked.connect(self._delete_source)
        self.ui.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.ui.source_table.doubleClicked.connect(self._edit_source_selected)
        self.ui.source_table.horizontalHeader().sectionResized.connect(self._save_mat_col_widths)
        btn_extra.clicked.connect(self._toggle_extra_params)
        if hasattr(self.ui, 'btn_add_sisp'):
            self.ui.btn_add_sisp.clicked.connect(self._add_sisp_pair)
        if hasattr(self.ui, 'btn_ksrc_add'):
            self.ui.btn_ksrc_add.clicked.connect(self._add_ksrc_point)
            self.ui.btn_ksrc_del.clicked.connect(self._delete_ksrc_points)

    def _restore_col_widths(self):
        saved = self._mt_settings.value("sdef_col_widths")
        if saved and len(saved) == 6:
            for col, w in enumerate(saved):
                self.ui.source_table.setColumnWidth(col, int(w))

    def _save_mat_col_widths(self):
        widths = [self.ui.source_table.columnWidth(c) for c in range(self.ui.source_table.columnCount())]
        self._mt_settings.setValue("sdef_col_widths", widths)

    @staticmethod
    def _auto_resize_table(table, min_rows=5):
        n = table.rowCount()
        rows = max(min_rows, n)
        hh = table.horizontalHeader().height() or 28
        rh = table.rowHeight(0) if n > 0 else 30
        fw = 2 * table.frameWidth()
        table.setMinimumHeight(hh + rh * rows + fw + 4)

    def _on_mode_changed(self, index: int):
        self._current_mode = index
        self._update_mode()

    def _update_mode(self):
        m = self._current_mode
        self.ui.stack.setCurrentIndex(m)
        self.ui.btn_add.setVisible(m == 0)
        self.ui.btn_del.setVisible(m == 0)
        if hasattr(self.ui, 'hint') and self.ui.hint:
            hints = [
                "固定点源模式：多个源时，每个源的「概率」参数决定抽样比例。",
                "分布源模式：上方设置 SDEF 参数，下方编辑 SI/SP 分布卡。键入 D1/D2/… 自动生成对应行。",
                "KCODE 临界源模式：不输出 SDEF 卡，改为 KCODE + KSRC 卡。用于裂变链临界计算。",
            ]
            self.ui.hint.setText(hints[m] if m < len(hints) else "")

    def _add_source(self):
        new_num = max((s.number for s in self.sources), default=0) + 1
        dialog = SourceEditDialog(SourceData(number=new_num), self)
        if dialog.exec_() == SourceEditDialog.Accepted:
            self.sources.append(dialog.get_data())
            self._refresh_table()

    def _delete_source(self):
        rows = sorted(set(idx.row() for idx in self.ui.source_table.selectedIndexes()), reverse=True)
        if not rows:
            QMessageBox.information(self, "提示", "请先选中要删除的源")
            return
        for r in rows:
            if 0 <= r < len(self.sources):
                self.sources.pop(r)
        self._refresh_table()

    def _edit_source_selected(self, index):
        row = index.row()
        if 0 <= row < len(self.sources):
            self._edit_source(row)

    def _edit_source(self, idx: int):
        if idx < 0 or idx >= len(self.sources):
            return
        dialog = SourceEditDialog(self.sources[idx], self)
        if dialog.exec_() == SourceEditDialog.Accepted:
            self.sources[idx] = dialog.get_data()
            self._refresh_table()

    def _refresh_table(self):
        par_labels = {"1": "1-中子", "2": "2-光子", "3": "3-电子", "H": "H-质子", "A": "A-α粒子"}
        self.ui.source_table.setRowCount(len(self.sources))
        for i, src in enumerate(self.sources):
            self.ui.source_table.setItem(i, 0, QTableWidgetItem(par_labels.get(src.par, src.par)))
            self.ui.source_table.setItem(i, 1, QTableWidgetItem(src.erg))
            pos = f"{src.pos_x} {src.pos_y} {src.pos_z}".strip()
            self.ui.source_table.setItem(i, 2, QTableWidgetItem(pos))
            self.ui.source_table.setItem(i, 3, QTableWidgetItem(src.wgt))
            self.ui.source_table.setItem(i, 4, QTableWidgetItem(src.dir_))
            btn_edit = QPushButton("✎")
            btn_edit.setProperty("cssClass", "btnEdit")
            btn_edit.clicked.connect(lambda checked, idx=i: self._edit_source(idx))
            self.ui.source_table.setCellWidget(i, 5, btn_edit)
        self._auto_resize_table(self.ui.source_table)

    # ── KSRC 操作 ──

    def _add_ksrc_point(self):
        row = self.ui.ksrc_table.rowCount()
        self.ui.ksrc_table.insertRow(row)
        self.ui.ksrc_table.setItem(row, 0, QTableWidgetItem(""))
        self.ui.ksrc_table.setItem(row, 1, QTableWidgetItem(""))
        self.ui.ksrc_table.setItem(row, 2, QTableWidgetItem(""))

    def _delete_ksrc_points(self):
        rows = sorted(set(idx.row() for idx in self.ui.ksrc_table.selectedIndexes()), reverse=True)
        if not rows:
            QMessageBox.information(self, "提示", "请先选中要删除的裂变点")
            return
        for r in rows:
            self.ui.ksrc_table.removeRow(r)

    # ── 数据接口 ──

    def set_data(self, sources_or_data, adv=None):
        """兼容新旧调用方式：
        - inp_importer 传 (sources, adv)
        - 内部直接传 data dict
        """
        if adv is not None:
            # 旧风格：(sources_list, AdvancedSettings)
            self._set_fixed_data({"sources": list(sources_or_data)})
            sm = getattr(adv, 'source_mode', 'fixed')
            if sm == 'distribution':
                self.ui.mode_combo.setCurrentIndex(1)
                self._current_mode = 1
                self._load_distribution_data(adv)
            elif sm == 'kcode':
                self.ui.mode_combo.setCurrentIndex(2)
                self._current_mode = 2
                self._load_kcode_data(adv)
            self._update_mode()
        else:
            # 新风格：直接传 data dict
            data = sources_or_data or {}
            mode = data.get("mode", "fixed")
            if mode == "distribution":
                self._set_dist_data(data)
            elif mode == "kcode":
                self._load_kcode_data(AdvancedSettings())
            else:
                self._set_fixed_data(data)
        m = self._current_mode
        if m == 1:
            return self._get_dist_data()
        elif m == 2:
            return self._get_kcode_data()
        return self._get_fixed_data()

    def _get_fixed_data(self) -> dict:
        return {"sources": self.sources, "mode": "fixed"}

    def _get_dist_data(self) -> dict:
        u = self.ui
        # 序列化 SI/SP 对
        pairs = []
        for p in sorted(self.dist_pairs, key=lambda x: x["ref_index"]):
            si_t = p["si"].text().strip()
            sp_t = p["sp"].text().strip()
            if si_t or sp_t:
                pairs.append({"si": si_t, "sp": sp_t})
        return {
            "mode": "distribution",
            "par": u.sdef_par.text().strip(),
            "erg": u.sdef_erg.text().strip(),
            "pos": f"{u.sdef_pos_x.text().strip()} {u.sdef_pos_y.text().strip()} {u.sdef_pos_z.text().strip()}".strip(),
            "wgt": u.sdef_wgt.text().strip(),
            "tme": u.sdef_tme.text().strip(),
            "dir": u.sdef_dir.text().strip(),
            "vec": u.sdef_vec.text().strip(),
            "axs": u.sdef_axs.text().strip(),
            "ext": u.sdef_ext.text().strip(),
            "rad": u.sdef_rad.text().strip(),
            "cel": u.sdef_cel.text().strip(),
            "sur": u.sdef_sur.text().strip(),
            "nrm": u.sdef_nrm.text().strip(),
            "tr": u.sdef_tr.text().strip(),
            "ccc": u.sdef_ccc.text().strip(),
            "ara": u.sdef_ara.text().strip(),
            "rate": u.sdef_rate.text().strip(),
            "extra": u.sdef_extra.text().strip(),
        }

    def _set_fixed_data(self, data: dict):
        self.sources = list(data.get("sources", []))
        self._refresh_table()
        if self._current_mode != 0:
            self.ui.mode_combo.setCurrentIndex(0)
            self._on_mode_changed(0)

    def _set_dist_data(self, data: dict):
        u = self.ui
        u.sdef_par.setText(data.get("par", ""))
        for attr in ["erg","wgt","tme","dir","vec","axs","ext","rad",
                      "cel","sur","nrm","tr","ccc","ara","rate","extra"]:
            le = getattr(u, f"sdef_{attr}", None)
            if le:
                le.setText(data.get(attr, ""))
        # POS 三个子字段
        pos_val = data.get("pos", "").strip()
        parts = pos_val.split(None, 2)
        if hasattr(u, 'sdef_pos_x'): u.sdef_pos_x.setText(parts[0] if len(parts) > 0 else "")
        if hasattr(u, 'sdef_pos_y'): u.sdef_pos_y.setText(parts[1] if len(parts) > 1 else "")
        if hasattr(u, 'sdef_pos_z'): u.sdef_pos_z.setText(parts[2] if len(parts) > 2 else "")
        if self._current_mode != 1:
            le = getattr(u, f"sdef_{attr}", None)
            if le:
                le.setText(data.get(attr, ""))
        if self._current_mode != 1:
            self.ui.mode_combo.setCurrentIndex(1)
            self._on_mode_changed(1)

    def _load_distribution_data(self, adv):
        """从 AdvancedSettings 回填分布源 UI"""
        u = self.ui
        u.sdef_par.setText(getattr(adv, 'sdef_par', '') or '')
        u.sdef_pos_x.setText(getattr(adv, 'sdef_pos_x', '') or '')
        u.sdef_pos_y.setText(getattr(adv, 'sdef_pos_y', '') or '')
        u.sdef_pos_z.setText(getattr(adv, 'sdef_pos_z', '') or '')
        for attr in ['sdef_erg','sdef_wgt','sdef_tme','sdef_dir','sdef_vec',
                      'sdef_axs','sdef_ext','sdef_rad','sdef_cel',
                      'sdef_sur','sdef_nrm','sdef_tr','sdef_ccc','sdef_ara','sdef_rate','sdef_extra']:
            le = getattr(u, attr, None)
            val = getattr(adv, attr, '')
            if le and val:
                le.setText(str(val))
        # 恢复额外参数折叠状态
        if hasattr(u, '_btn_extra') and any(getattr(adv, a, '') for a in
            ['sdef_sur','sdef_nrm','sdef_tr','sdef_ccc','sdef_ara','sdef_rate']):
            u._btn_extra.setChecked(True)
            u._btn_extra.setText("▲ 收起额外参数")
        # 解析 SI/SP 对
        self._clear_sisp_pairs()
        raw = getattr(adv, 'sdef_raw_text', '')
        if raw:
            try:
                pairs = json.loads(raw) if isinstance(raw, str) else raw
                for i, pair in enumerate(pairs):
                    idx = i + 1
                    self._create_sisp_card(idx, f"导入 D{idx}")
                    for p in self.dist_pairs:
                        if p["ref_index"] == idx:
                            p["auto"] = False
                            si_text = pair.get("si", "")
                            sp_text = pair.get("sp", "")
                            p["si"].setText(si_text)
                            p["sp"].setText(sp_text)
                            break
            except Exception:
                pass

    def _load_kcode_data(self, adv):
        """从 AdvancedSettings 回填 KCODE/KSRC"""
        u = self.ui
        u.kcode_nsrc.setText(getattr(adv, 'kcode_nsrc', '') or '')
        u.kcode_rkk.setText(getattr(adv, 'kcode_rkk', '') or '')
        u.kcode_ikz.setText(getattr(adv, 'kcode_ikz', '') or '')
        u.kcode_kct.setText(getattr(adv, 'kcode_kct', '') or '')
        u.kcode_knrm.setText(getattr(adv, 'kcode_knrm', '') or '')
        u.ksrc_table.setRowCount(0)
        ksrc = getattr(adv, 'ksrc_points', '')
        if ksrc:
            try:
                pts = json.loads(ksrc) if isinstance(ksrc, str) else ksrc
                for pt in pts:
                    r = u.ksrc_table.rowCount()
                    u.ksrc_table.insertRow(r)
                    u.ksrc_table.setItem(r, 0, QTableWidgetItem(str(pt.get('x',''))))
                    u.ksrc_table.setItem(r, 1, QTableWidgetItem(str(pt.get('y',''))))
                    u.ksrc_table.setItem(r, 2, QTableWidgetItem(str(pt.get('z',''))))
            except Exception:
                pass

    def get_raw_overrides(self) -> dict:
        return {"sdef": self._raw_sdef.get_raw_text(),
                "dist": self._raw_dist.get_raw_text()}

    def _gen_sdef_raw(self) -> str:
        return "\n".join(_generate_sdef(self.sources))

    def _gen_dist_raw(self) -> str:
        adv = AdvancedSettings()
        for k, v in self._get_dist_data().items():
            setattr(adv, k, v)
        return "\n".join(_generate_distribution_sdef(adv))

    # ── 额外参数折叠 ──

    def _toggle_extra_params(self):
        btn = self.ui._btn_extra if hasattr(self.ui, '_btn_extra') else None
        if not btn:
            return
        visible = btn.isChecked()
        # 找到 extra_fields widget (btn 的下一个兄弟)
        parent = btn.parentWidget() if btn.parentWidget() else None
        if parent:
            for i in range(parent.layout().count()):
                w = parent.layout().itemAt(i).widget()
                if w and w is not btn:
                    w.setVisible(visible)
                    break
        btn.setText("▲ 收起额外参数" if visible else "▼ 额外参数")

    # ── SI/SP 分布卡管理 ──

    def _add_sisp_pair(self):
        """手动添加一个 SI/SP 对"""
        used = {p["ref_index"] for p in self.dist_pairs}
        next_n = 1
        while next_n in used:
            next_n += 1
        self._create_sisp_card(next_n, "手动")
        for p in self.dist_pairs:
            if p["ref_index"] == next_n:
                p["auto"] = False
                break

    def _create_sisp_card(self, index: int, param: str):
        """创建一个 SI/SP 卡片"""
        from PyQt5.QtWidgets import QGroupBox, QHBoxLayout, QLineEdit, QLabel, QPushButton
        frame = QGroupBox(f"分布 D{index}（{param}）")
        h = QHBoxLayout(frame)
        h.setContentsMargins(8, 4, 8, 4)

        si_edit = QLineEdit()
        si_edit.setPlaceholderText(f"SI{index}  L  N  P")
        si_edit.setToolTip("SI 类型: L=离散列表  H=连续均匀  A=解析函数  S=分布号")
        h.addWidget(QLabel(f"SI{index}:"))
        h.addWidget(si_edit, 1)

        sp_edit = QLineEdit()
        sp_edit.setPlaceholderText(f"SP{index}  …")
        h.addWidget(QLabel(f"SP{index}:"))
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
            "auto": True,
        }
        self.dist_pairs.append(pair)
        if hasattr(self.ui, 'sisp_container'):
            self.ui.sisp_container.addWidget(frame)

    def _remove_sisp_card(self, frame):
        """删除一个 SI/SP 卡片"""
        for p in list(self.dist_pairs):
            if p["frame"] is frame:
                self.dist_pairs.remove(p)
                frame.deleteLater()
                break

    def _clear_sisp_pairs(self):
        """清除所有 SI/SP 卡片"""
        for p in list(self.dist_pairs):
            self.dist_pairs.remove(p)
            p["frame"].deleteLater()

    def _ensure_sisp_pairs(self):
        """扫描 Dn 引用，自动创建/移除 SI/SP 卡片"""
        refs = self._get_all_d_refs()
        ref_indices = {r[0] for r in refs}
        ref_map = dict(refs)
        existing = {p["ref_index"]: p for p in self.dist_pairs}
        # 移除不再引用的自动卡片
        for p in list(self.dist_pairs):
            if p["auto"] and p["ref_index"] not in ref_indices:
                self.dist_pairs.remove(p)
                p["frame"].deleteLater()
        # 更新/创建新卡片
        for n, param in refs:
            if n in existing:
                if existing[n]["ref_param"] != param:
                    existing[n]["ref_param"] = param
                    existing[n]["frame"].setTitle(f"分布 D{n}（{param}）")
            else:
                self._create_sisp_card(n, param)

    def _get_all_d_refs(self) -> list[tuple[int, str]]:
        """扫描所有 SDEF 字段提取 Dn 引用"""
        u = self.ui
        pos_val = f"{u.sdef_pos_x.text()} {u.sdef_pos_y.text()} {u.sdef_pos_z.text()}"
        fields = [
            ("PAR", u.sdef_par.text()), ("ERG", u.sdef_erg.text()),
            ("WGT", u.sdef_wgt.text()), ("DIR", u.sdef_dir.text()),
            ("CEL", u.sdef_cel.text()), ("TME", u.sdef_tme.text()),
            ("VEC", u.sdef_vec.text()), ("AXS", u.sdef_axs.text()),
            ("RAD", u.sdef_rad.text()), ("EXT", u.sdef_ext.text()),
            ("POS", pos_val),
            ("SUR", u.sdef_sur.text()), ("NRM", u.sdef_nrm.text()),
            ("TR", u.sdef_tr.text()), ("CCC", u.sdef_ccc.text()),
            ("ARA", u.sdef_ara.text()), ("RATE", u.sdef_rate.text()),
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
