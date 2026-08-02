"""Advanced — 控制器层"""

import os
from PyQt5.QtWidgets import QWidget, QFileDialog
from PyQt5.QtCore import QSettings

from app.models import AdvancedSettings
from app.xsdir_db import DB as xsdir_db
from app.generator.inp_generator import _generate_phys, _generate_other_cards, _generate_cut
from .view import create_ui


class AdvancedTab(QWidget):

    def __init__(self):
        super().__init__()
        self._phys_raw = None
        self._cut_raw = None
        ui, btn_browse, phys_raw, cut_raw = create_ui(
            self,
            gen_phys_fn=lambda: self._gen_phys_raw(),
            gen_cut_fn=lambda: self._gen_cut_raw())
        self.ui = ui
        self._phys_raw = phys_raw
        self._cut_raw = cut_raw
        self._connect_signals(btn_browse)
        self._restore_xsdir()
        self._refresh_xsdir_status()

    def _connect_signals(self, btn_browse):
        btn_browse.clicked.connect(self._browse_xsdir)
        self.ui.xsdir_edit.textChanged.connect(self._on_xsdir_changed)

    def _restore_xsdir(self):
        saved = QSettings("MCNPGen", "MCNPGenerator").value("xsdir_path", "")
        self.ui.xsdir_edit.setText(saved)

    def _refresh_xsdir_status(self):
        if xsdir_db.loaded:
            self.ui.xsdir_status.setText(
                f"<span style='color:#2e7d32;'>✓ 已加载，共 {xsdir_db.count()} 条 ZAID</span>")
        elif xsdir_db.error:
            self.ui.xsdir_status.setText(f"<span style='color:#c62828;'>⚠ {xsdir_db.error}</span>")
        else:
            self.ui.xsdir_status.setText("<span style='color:#888;'>未加载</span>")

    def _browse_xsdir(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 xsdir 截面库索引文件",
            os.path.dirname(self.ui.xsdir_edit.text()) if self.ui.xsdir_edit.text() else "D:\\",
            "xsdir (xsdir);;所有文件 (*.*)")
        if path:
            self.ui.xsdir_edit.setText(path)

    def _on_xsdir_changed(self, text: str):
        path = text.strip()
        if path and os.path.isfile(path):
            QSettings("MCNPGen", "MCNPGenerator").setValue("xsdir_path", path)
            xsdir_db.load(path)
        self._refresh_xsdir_status()

    # ── 数据接口 ──

    def get_data(self) -> AdvancedSettings:
        u = self.ui
        return AdvancedSettings(
            other_cards=u.other_edit.toPlainText().strip(),
            phys_n_emax=u.phys_n_emax.text().strip(),
            phys_n_emcnf=u.phys_n_emcnf.text().strip(),
            phys_n_iunr=u.phys_n_iunr.text().strip(),
            phys_n_dnb=u.phys_n_dnb.text().strip(),
            phys_n_fisnu=u.phys_n_fisnu.text().strip(),
            phys_p_emcpf=u.phys_p_emcpf.text().strip(),
            phys_p_ides=u.phys_p_ides.text().strip(),
            phys_p_nocoh=u.phys_p_nocoh.text().strip(),
            phys_p_ispn=u.phys_p_ispn.text().strip(),
            phys_p_nodop=u.phys_p_nodop.text().strip(),
            phys_e_emax=u.phys_e_emax.text().strip(),
            phys_e_ides=u.phys_e_ides.text().strip(),
            phys_e_iphoto=u.phys_e_iphoto.text().strip(),
            phys_e_ibad=u.phys_e_ibad.text().strip(),
            phys_e_istrg=u.phys_e_istrg.text().strip(),
            phys_e_bnum=u.phys_e_bnum.text().strip(),
            phys_e_xnum=u.phys_e_xnum.text().strip(),
            phys_e_rnok=u.phys_e_rnok.text().strip(),
            phys_e_enum=u.phys_e_enum.text().strip(),
            phys_e_numb=u.phys_e_numb.text().strip(),
            phys_h_emax=u.phys_h_emax.text().strip(),
            phys_h_ie=u.phys_h_ie.text().strip(),
            phys_h_ipr=u.phys_h_ipr.text().strip(),
            phys_h_rgas=u.phys_h_rgas.text().strip(),
            phys_h_emin=u.phys_h_emin.text().strip(),
            phys_h_ecut=u.phys_h_ecut.text().strip(),
            phys_he_emax=u.phys_he_emax.text().strip(),
            phys_he_ie=u.phys_he_ie.text().strip(),
            phys_he_ipr=u.phys_he_ipr.text().strip(),
            phys_he_rgas=u.phys_he_rgas.text().strip(),
            phys_he_emin=u.phys_he_emin.text().strip(),
            phys_he_ecut=u.phys_he_ecut.text().strip(),
        )

    def set_data(self, adv: AdvancedSettings):
        u = self.ui
        u.other_edit.setPlainText(adv.other_cards)
        for f in ['phys_n_emax','phys_n_emcnf','phys_n_iunr','phys_n_dnb','phys_n_fisnu',
                  'phys_p_emcpf','phys_p_ides','phys_p_nocoh','phys_p_ispn','phys_p_nodop',
                  'phys_e_emax','phys_e_ides','phys_e_iphoto','phys_e_ibad','phys_e_istrg',
                  'phys_e_bnum','phys_e_xnum','phys_e_rnok','phys_e_enum','phys_e_numb',
                  'phys_h_emax','phys_h_ie','phys_h_ipr','phys_h_rgas','phys_h_emin','phys_h_ecut',
                  'phys_he_emax','phys_he_ie','phys_he_ipr','phys_he_rgas','phys_he_emin','phys_he_ecut']:
            getattr(u, f).setText(getattr(adv, f, "") or "")

    def set_cut_data(self, tally):
        for p in ["n","p","e","h","he","d","t","a"]:
            for fn in ["t","e","wc1","wc2","swtm"]:
                key = f"cut_{p}_{fn}"
                try:
                    getattr(self.ui, key).setText(getattr(tally, key, "") or "")
                except AttributeError:
                    pass

    def get_cut_data(self):
        from app.models import TallySettings as _TS
        kw = {}
        for p in ["n","p","e","h","he","d","t","a"]:
            for fn in ["t","e","wc1","wc2","swtm"]:
                kw[f"cut_{p}_{fn}"] = getattr(self.ui, f"cut_{p}_{fn}").text().strip()
        return _TS(**kw)

    def get_raw_overrides(self) -> dict:
        return {
            "phys": self._phys_raw.get_raw_text() if self._phys_raw else "",
            "cut": self._cut_raw.get_raw_text() if self._cut_raw else "",
        }

    def _gen_phys_raw(self) -> str:
        adv = self.get_data()
        lines = []
        lines.extend(_generate_phys(adv))
        lines.extend(_generate_other_cards(adv))
        return "\n".join(lines)

    def _gen_cut_raw(self) -> str:
        return "\n".join(_generate_cut(self.get_cut_data()))
