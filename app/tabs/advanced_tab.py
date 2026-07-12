"""
⚙ 高级设置标签页：说明书中提及但界面未单独列出的 MCNP 卡片
"""

import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QHBoxLayout,
    QPlainTextEdit, QLabel, QLineEdit, QPushButton,
    QFileDialog, QScrollArea
)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QFont

from app.models import AdvancedSettings
from app.xsdir_db import DB as xsdir_db
from app.widgets.text_mode_section import TextModeSection
from app.generator.inp_generator import _generate_advanced


class AdvancedTab(QWidget):
    """高级设置标签页"""

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
        layout.setSpacing(12)

        grp = QGroupBox("其他 MCNP 卡片（说明书中未在界面单独列出的选项）")
        grp.setToolTip(
            "在此输入界面其他标签页中未覆盖的任何 MCNP 卡片。\n"
            "每行一张卡，格式与 INP 文件一致。\n"
            "内容会被原样插入到数据卡段的末尾（计数卡之前）。"
        )
        inner = QVBoxLayout(grp)

        hint = QLabel(
            "<span style='font-size:11px;'>"
            "常见可在此处添加的卡片：<br>"
            "<b>KCODE</b> — 临界计算  |  <b>KSRC</b> — 裂变源点  |  "
            "<b>PRDMP</b> — 打印控制<br>"
            "<b>PTRAC</b> — 粒子径迹  |  <b>TOTNU</b> — 总裂变中子产额  |  "
            "<b>NONU</b> — 无裂变<br>"
            "<b>VOID</b> — 真空处理  |  <b>IDUM/RDUM</b> — 用户数组  |  "
            "<b>LOST</b> — 丢失粒子<br>"
            "<b>DBCN</b> — 调试控制  |  <b>PERT</b> — 微扰  |  "
            "<b>SSW/SSR</b> — 曲面源<br>"
            "<b>ESPLT</b> — 能量分裂  |  <b>WWE/WWN</b> — 权重窗  |  "
            "<b>CUT:P/E/H</b> — 其他粒子截断<br>"
            "<span style='color:gray;'>"
            "格式：每行一张卡片，如 KCODE 5000 1.0 50 100</span>"
        )
        hint.setWordWrap(True)
        inner.addWidget(hint)

        self.other_edit = QPlainTextEdit()
        self.other_edit.setPlaceholderText(
            "示例:\n"
            "KCODE  5000  1.0  50  100\n"
            "KSRC  0  0  0\n"
            "PRDMP  100  0  0  0  0\n"
            "PTRAC  MAX=10000  WRITE=ALL\n"
            "TOTNU\n"
        )
        self.other_edit.setToolTip("每行一个 MCNP 卡片，按格式直接写入 INP 数据段")
        self.other_edit.setFont(QFont("Consolas", 10))
        self.other_edit.setMinimumHeight(200)
        inner.addWidget(self.other_edit)

        inner.addWidget(QLabel(
            "<span style='color:orange; font-size:11px;'>"
            "⚠ 输入的内容不会校验格式，请自行确认正确性</span>"
        ))

        layout.addWidget(grp)

        # ===== PHYS:N / PHYS:P / PHYS:E 参数 =====
        grp_phys = QGroupBox()
        grp_phys.setToolTip(
            "PHYS:N/P/E 控制物理模型参数。\n"
            "所有字段留空则不生成 PHYS 卡。"
        )
        phys_container = QWidget()
        phys_layout = QVBoxLayout(phys_container)
        phys_layout.setSpacing(6)

        # PHYS:N
        phys_n_row = QHBoxLayout()
        phys_n_row.addWidget(QLabel("<b>PHYS:N</b>"))
        self.phys_n_emax = QLineEdit()
        self.phys_n_emax.setPlaceholderText("emax")
        self.phys_n_emax.setToolTip("最大能量 (MeV)，默认=100")
        self.phys_n_emax.setMaximumWidth(80)
        phys_n_row.addWidget(self.phys_n_emax)
        self.phys_n_ie = QLineEdit()
        self.phys_n_ie.setPlaceholderText("ie")
        self.phys_n_ie.setToolTip("非弹性散射模型 (0/1/2)")
        self.phys_n_ie.setMaximumWidth(60)
        phys_n_row.addWidget(self.phys_n_ie)
        self.phys_n_nubar = QLineEdit()
        self.phys_n_nubar.setPlaceholderText("nubar")
        self.phys_n_nubar.setToolTip("ν-bar 模型 (1=Keff, 2=能量相关)")
        self.phys_n_nubar.setMaximumWidth(60)
        phys_n_row.addWidget(self.phys_n_nubar)
        self.phys_n_rgas = QLineEdit()
        self.phys_n_rgas.setPlaceholderText("rgas")
        self.phys_n_rgas.setToolTip("气体产生截面")
        self.phys_n_rgas.setMaximumWidth(60)
        phys_n_row.addWidget(self.phys_n_rgas)
        self.phys_n_idm = QLineEdit()
        self.phys_n_idm.setPlaceholderText("idm")
        self.phys_n_idm.setToolTip("损伤能量截面")
        self.phys_n_idm.setMaximumWidth(60)
        phys_n_row.addWidget(self.phys_n_idm)
        phys_n_row.addStretch()
        phys_layout.addLayout(phys_n_row)

        # PHYS:P
        phys_p_row = QHBoxLayout()
        phys_p_row.addWidget(QLabel("<b>PHYS:P</b>"))
        self.phys_p_emin = QLineEdit()
        self.phys_p_emin.setPlaceholderText("emin")
        self.phys_p_emin.setToolTip("最小能量 (MeV)")
        self.phys_p_emin.setMaximumWidth(80)
        phys_p_row.addWidget(self.phys_p_emin)
        self.phys_p_isnp = QLineEdit()
        self.phys_p_isnp.setPlaceholderText("isnp")
        self.phys_p_isnp.setToolTip("相干散射 (0/1)")
        self.phys_p_isnp.setMaximumWidth(60)
        phys_p_row.addWidget(self.phys_p_isnp)
        self.phys_p_ff = QLineEdit()
        self.phys_p_ff.setPlaceholderText("ff")
        self.phys_p_ff.setToolTip("形式因子 (0/1)")
        self.phys_p_ff.setMaximumWidth(60)
        phys_p_row.addWidget(self.phys_p_ff)
        phys_p_row.addStretch()
        phys_layout.addLayout(phys_p_row)

        # PHYS:E
        phys_e_row = QHBoxLayout()
        phys_e_row.addWidget(QLabel("<b>PHYS:E</b>"))
        self.phys_e_emin = QLineEdit()
        self.phys_e_emin.setPlaceholderText("emin")
        self.phys_e_emin.setToolTip("最小能量 (MeV)")
        self.phys_e_emin.setMaximumWidth(80)
        phys_e_row.addWidget(self.phys_e_emin)
        self.phys_e_isne = QLineEdit()
        self.phys_e_isne.setPlaceholderText("isne")
        self.phys_e_isne.setToolTip("电子步长模型")
        self.phys_e_isne.setMaximumWidth(60)
        phys_e_row.addWidget(self.phys_e_isne)
        phys_e_row.addStretch()
        phys_layout.addLayout(phys_e_row)

        # PHYS:H
        phys_h_row = QHBoxLayout()
        phys_h_row.addWidget(QLabel("<b>PHYS:H</b>"))
        self.phys_h_emax = QLineEdit()
        self.phys_h_emax.setPlaceholderText("emax")
        self.phys_h_emax.setToolTip("最大能量 (MeV)")
        self.phys_h_emax.setMaximumWidth(80)
        phys_h_row.addWidget(self.phys_h_emax)
        self.phys_h_ie = QLineEdit()
        self.phys_h_ie.setPlaceholderText("ie")
        self.phys_h_ie.setToolTip("非弹性散射模型")
        self.phys_h_ie.setMaximumWidth(60)
        phys_h_row.addWidget(self.phys_h_ie)
        self.phys_h_ipr = QLineEdit()
        self.phys_h_ipr.setPlaceholderText("ipr")
        self.phys_h_ipr.setToolTip("质子产生核反冲")
        self.phys_h_ipr.setMaximumWidth(60)
        phys_h_row.addWidget(self.phys_h_ipr)
        self.phys_h_rgas = QLineEdit()
        self.phys_h_rgas.setPlaceholderText("rgas")
        self.phys_h_rgas.setToolTip("气体产生截面")
        self.phys_h_rgas.setMaximumWidth(60)
        phys_h_row.addWidget(self.phys_h_rgas)
        self.phys_h_emin = QLineEdit()
        self.phys_h_emin.setPlaceholderText("emin")
        self.phys_h_emin.setToolTip("最小能量 (MeV)")
        self.phys_h_emin.setMaximumWidth(80)
        phys_h_row.addWidget(self.phys_h_emin)
        self.phys_h_ecut = QLineEdit()
        self.phys_h_ecut.setPlaceholderText("ecut")
        self.phys_h_ecut.setToolTip("能量截断 (MeV)")
        self.phys_h_ecut.setMaximumWidth(80)
        phys_h_row.addWidget(self.phys_h_ecut)
        phys_h_row.addStretch()
        phys_layout.addLayout(phys_h_row)

        # PHYS:HE
        phys_he_row = QHBoxLayout()
        phys_he_row.addWidget(QLabel("<b>PHYS:HE</b>"))
        self.phys_he_emax = QLineEdit()
        self.phys_he_emax.setPlaceholderText("emax")
        self.phys_he_emax.setMaximumWidth(80)
        phys_he_row.addWidget(self.phys_he_emax)
        self.phys_he_ie = QLineEdit()
        self.phys_he_ie.setPlaceholderText("ie")
        self.phys_he_ie.setMaximumWidth(60)
        phys_he_row.addWidget(self.phys_he_ie)
        self.phys_he_ipr = QLineEdit()
        self.phys_he_ipr.setPlaceholderText("ipr")
        self.phys_he_ipr.setMaximumWidth(60)
        phys_he_row.addWidget(self.phys_he_ipr)
        self.phys_he_rgas = QLineEdit()
        self.phys_he_rgas.setPlaceholderText("rgas")
        self.phys_he_rgas.setMaximumWidth(60)
        phys_he_row.addWidget(self.phys_he_rgas)
        self.phys_he_emin = QLineEdit()
        self.phys_he_emin.setPlaceholderText("emin")
        self.phys_he_emin.setMaximumWidth(80)
        phys_he_row.addWidget(self.phys_he_emin)
        self.phys_he_ecut = QLineEdit()
        self.phys_he_ecut.setPlaceholderText("ecut")
        self.phys_he_ecut.setMaximumWidth(80)
        phys_he_row.addWidget(self.phys_he_ecut)
        phys_he_row.addStretch()
        phys_layout.addLayout(phys_he_row)

        self._raw_phys = TextModeSection(
            form_widget=phys_container,
            generate_fn=self._gen_phys_raw,
            section_name="phys",
        )
        gb_phys_layout = QVBoxLayout(grp_phys)
        phys_header = QHBoxLayout()
        phys_header.addWidget(QLabel("<b>PHYS 卡设置（留空=使用 MCNP 默认值）</b>"))
        phys_header.addStretch()
        phys_header.addWidget(self._raw_phys.toggle_btn)
        gb_phys_layout.addLayout(phys_header)
        gb_phys_layout.addWidget(self._raw_phys.stack)
        layout.addWidget(grp_phys)

        # ===== 截面库路径设置 =====
        grp_xsdir = QGroupBox("MCNP 截面库路径（xsdir）")
        grp_xsdir.setToolTip("设置 xsdir 文件路径后，材料卡的 ZAID 会自动校验是否存在")
        xsdir_layout = QVBoxLayout(grp_xsdir)

        xsdir_row = QHBoxLayout()
        self.xsdir_edit = QLineEdit()
        settings = QSettings("MCNPGen", "MCNPGenerator")
        saved = settings.value("xsdir_path", "")
        self.xsdir_edit.setText(saved)
        self.xsdir_edit.setPlaceholderText("例如: D:\\MCNP\\MCNP6\\MCNP_DATA\\xsdir")
        self.xsdir_edit.setToolTip("MCNP 截面库索引文件（xsdir）的完整路径")
        # textChanged 在 setText 之后连接，避免启动时 setText 触发重复加载
        self.xsdir_edit.textChanged.connect(self._on_xsdir_changed)

        btn_browse = QPushButton("浏览…")
        btn_browse.setToolTip("选择 xsdir 文件")
        btn_browse.setProperty("cssClass", "btnBrowse")
        btn_browse.clicked.connect(self._browse_xsdir)

        xsdir_row.addWidget(self.xsdir_edit, 1)
        xsdir_row.addWidget(btn_browse)
        xsdir_layout.addLayout(xsdir_row)

        self.xsdir_status = QLabel("")
        xsdir_layout.addWidget(self.xsdir_status)

        xsdir_hint = QLabel(
            "<span style='color:gray; font-size:11px;'>"
            "💡 设置 xsdir 后，材料编辑器中输入的 ZAID 会自动核对是否在库中，"
            "不在库中的会标红提示</span>"
        )
        xsdir_layout.addWidget(xsdir_hint)
        layout.addWidget(grp_xsdir)

        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

        self._refresh_xsdir_status()

    def _refresh_xsdir_status(self):
        """更新截面库状态显示"""
        if xsdir_db.loaded:
            self.xsdir_status.setText(
                f"<span style='color:#2e7d32;'>✓ 已加载，共 {xsdir_db.count()} 条 ZAID</span>"
            )
        elif xsdir_db.error:
            self.xsdir_status.setText(
                f"<span style='color:#c62828;'>⚠ {xsdir_db.error}</span>"
            )
        else:
            self.xsdir_status.setText(
                "<span style='color:#888;'>未加载</span>"
            )

    def _browse_xsdir(self):
        """选择 xsdir 文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 xsdir 截面库索引文件",
            os.path.dirname(self.xsdir_edit.text()) if self.xsdir_edit.text() else "D:\\",
            "xsdir (xsdir);;所有文件 (*.*)"
        )
        if path:
            self.xsdir_edit.setText(path)

    def _on_xsdir_changed(self, text: str):
        """路径改变时自动加载"""
        path = text.strip()
        if path and os.path.isfile(path):
            settings = QSettings("MCNPGen", "MCNPGenerator")
            settings.setValue("xsdir_path", path)
            xsdir_db.load(path)
        self._refresh_xsdir_status()

    def get_data(self) -> AdvancedSettings:
        return AdvancedSettings(
            other_cards=self.other_edit.toPlainText().strip(),
            phys_n_emax=self.phys_n_emax.text().strip(),
            phys_n_ie=self.phys_n_ie.text().strip(),
            phys_n_nubar=self.phys_n_nubar.text().strip(),
            phys_n_rgas=self.phys_n_rgas.text().strip(),
            phys_n_idm=self.phys_n_idm.text().strip(),
            phys_p_emin=self.phys_p_emin.text().strip(),
            phys_p_isnp=self.phys_p_isnp.text().strip(),
            phys_p_ff=self.phys_p_ff.text().strip(),
            phys_e_emin=self.phys_e_emin.text().strip(),
            phys_e_isne=self.phys_e_isne.text().strip(),
            phys_h_emax=self.phys_h_emax.text().strip(),
            phys_h_ie=self.phys_h_ie.text().strip(),
            phys_h_ipr=self.phys_h_ipr.text().strip(),
            phys_h_rgas=self.phys_h_rgas.text().strip(),
            phys_h_emin=self.phys_h_emin.text().strip(),
            phys_h_ecut=self.phys_h_ecut.text().strip(),
            phys_he_emax=self.phys_he_emax.text().strip(),
            phys_he_ie=self.phys_he_ie.text().strip(),
            phys_he_ipr=self.phys_he_ipr.text().strip(),
            phys_he_rgas=self.phys_he_rgas.text().strip(),
            phys_he_emin=self.phys_he_emin.text().strip(),
            phys_he_ecut=self.phys_he_ecut.text().strip(),
        )

    # ---------- 文本模式支持 ----------

    def _gen_phys_raw(self) -> str:
        return "\n".join(_generate_advanced(self.get_data()))

    def get_raw_overrides(self) -> dict:
        return {"phys": self._raw_phys.get_raw_text()}

    def set_data(self, adv: AdvancedSettings):
        """从导入数据回填 UI（用于 INP 导入）"""
        self.other_edit.setPlainText(adv.other_cards)
        self.phys_n_emax.setText(adv.phys_n_emax or "")
        self.phys_n_ie.setText(adv.phys_n_ie or "")
        self.phys_n_nubar.setText(adv.phys_n_nubar or "")
        self.phys_n_rgas.setText(adv.phys_n_rgas or "")
        self.phys_n_idm.setText(adv.phys_n_idm or "")
        self.phys_p_emin.setText(adv.phys_p_emin or "")
        self.phys_p_isnp.setText(adv.phys_p_isnp or "")
        self.phys_p_ff.setText(adv.phys_p_ff or "")
        self.phys_e_emin.setText(adv.phys_e_emin or "")
        self.phys_e_isne.setText(adv.phys_e_isne or "")
        self.phys_h_emax.setText(adv.phys_h_emax or "")
        self.phys_h_ie.setText(adv.phys_h_ie or "")
        self.phys_h_ipr.setText(adv.phys_h_ipr or "")
        self.phys_h_rgas.setText(adv.phys_h_rgas or "")
        self.phys_h_emin.setText(adv.phys_h_emin or "")
        self.phys_h_ecut.setText(adv.phys_h_ecut or "")
        self.phys_he_emax.setText(adv.phys_he_emax or "")
        self.phys_he_ie.setText(adv.phys_he_ie or "")
        self.phys_he_ipr.setText(adv.phys_he_ipr or "")
        self.phys_he_rgas.setText(adv.phys_he_rgas or "")
        self.phys_he_emin.setText(adv.phys_he_emin or "")
        self.phys_he_ecut.setText(adv.phys_he_ecut or "")
