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
from app.generator.inp_generator import _generate_phys, _generate_other_cards


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

        # PHYS:N — C810: EMAX EMCNF IUNR DNB FISNU
        phys_n_row = QHBoxLayout()
        phys_n_row.addWidget(QLabel("<b>PHYS:N</b>"))
        self.phys_n_emax = QLineEdit()
        self.phys_n_emax.setPlaceholderText("EMAX")
        self.phys_n_emax.setToolTip("中子能量上限 (MeV)，默认=极大")
        self.phys_n_emax.setMaximumWidth(80)
        phys_n_row.addWidget(self.phys_n_emax)
        self.phys_n_emcnf = QLineEdit()
        self.phys_n_emcnf.setPlaceholderText("EMCNF")
        self.phys_n_emcnf.setToolTip("俘获方式转变能 (MeV)，默认=0.0")
        self.phys_n_emcnf.setMaximumWidth(80)
        phys_n_row.addWidget(self.phys_n_emcnf)
        self.phys_n_iunr = QLineEdit()
        self.phys_n_iunr.setPlaceholderText("IUNR")
        self.phys_n_iunr.setToolTip("未分辨共振概率表：0=打开(默认)，1=关闭")
        self.phys_n_iunr.setMaximumWidth(60)
        phys_n_row.addWidget(self.phys_n_iunr)
        self.phys_n_dnb = QLineEdit()
        self.phys_n_dnb.setPlaceholderText("DNB")
        self.phys_n_dnb.setToolTip("缓发中子处理：0=常态(默认)，-n=选代，>n=每个中子")
        self.phys_n_dnb.setMaximumWidth(60)
        phys_n_row.addWidget(self.phys_n_dnb)
        self.phys_n_fisnu = QLineEdit()
        self.phys_n_fisnu.setPlaceholderText("FISNU")
        self.phys_n_fisnu.setToolTip("裂变中子谱：<0=高斯宽度，0=整数采样(默认)，1=推荐高斯，2=原始Terrell")
        self.phys_n_fisnu.setMaximumWidth(60)
        phys_n_row.addWidget(self.phys_n_fisnu)
        phys_n_row.addStretch()
        phys_layout.addLayout(phys_n_row)

        # PHYS:P — C810: EMCPF IDES NOCOH ISPN NODOP
        phys_p_row = QHBoxLayout()
        phys_p_row.addWidget(QLabel("<b>PHYS:P</b>"))
        self.phys_p_emcpf = QLineEdit()
        self.phys_p_emcpf.setPlaceholderText("EMCPF")
        self.phys_p_emcpf.setToolTip("详细/简单分界能量 (MeV)，默认=100")
        self.phys_p_emcpf.setMaximumWidth(80)
        phys_p_row.addWidget(self.phys_p_emcpf)
        self.phys_p_ides = QLineEdit()
        self.phys_p_ides.setPlaceholderText("IDES")
        self.phys_p_ides.setToolTip("0=光子产生电子(默认)，1=不产生")
        self.phys_p_ides.setMaximumWidth(60)
        phys_p_row.addWidget(self.phys_p_ides)
        self.phys_p_nocoh = QLineEdit()
        self.phys_p_nocoh.setPlaceholderText("NOCOH")
        self.phys_p_nocoh.setToolTip("0=含相干散射(默认)，1=关闭")
        self.phys_p_nocoh.setMaximumWidth(80)
        phys_p_row.addWidget(self.phys_p_nocoh)
        self.phys_p_ispn = QLineEdit()
        self.phys_p_ispn.setPlaceholderText("ISPN")
        self.phys_p_ispn.setToolTip("0=光核作用打开，-1=关闭(默认)")
        self.phys_p_ispn.setMaximumWidth(60)
        phys_p_row.addWidget(self.phys_p_ispn)
        self.phys_p_nodop = QLineEdit()
        self.phys_p_nodop.setPlaceholderText("NODOP")
        self.phys_p_nodop.setToolTip("0=含Doppler展宽(默认)，1=关闭")
        self.phys_p_nodop.setMaximumWidth(80)
        phys_p_row.addWidget(self.phys_p_nodop)
        phys_p_row.addStretch()
        phys_layout.addLayout(phys_p_row)

        # PHYS:E — C810: EMAX IDES IPHOT IBAD ISTRG BNUM XNUM RNOK ENUM NUMB
        phys_e_row = QHBoxLayout()
        phys_e_row.addWidget(QLabel("<b>PHYS:E</b>"))
        self.phys_e_emax = QLineEdit()
        self.phys_e_emax.setPlaceholderText("EMAX")
        self.phys_e_emax.setToolTip("电子能量上限 (MeV)，默认=100")
        self.phys_e_emax.setMaximumWidth(80)
        phys_e_row.addWidget(self.phys_e_emax)
        self.phys_e_ides = QLineEdit()
        self.phys_e_ides.setPlaceholderText("IDES")
        self.phys_e_ides.setToolTip("0=光子产生电子(默认)，1=不产生")
        self.phys_e_ides.setMaximumWidth(60)
        phys_e_row.addWidget(self.phys_e_ides)
        self.phys_e_iphoto = QLineEdit()
        self.phys_e_iphoto.setPlaceholderText("IPHOT")
        self.phys_e_iphoto.setToolTip("0=电子产生光子(默认)，1=不产生")
        self.phys_e_iphoto.setMaximumWidth(70)
        phys_e_row.addWidget(self.phys_e_iphoto)
        self.phys_e_ibad = QLineEdit()
        self.phys_e_ibad.setPlaceholderText("IBAD")
        self.phys_e_ibad.setToolTip("0=Koch-Motz角分布(默认)，1=简单近似")
        self.phys_e_ibad.setMaximumWidth(60)
        phys_e_row.addWidget(self.phys_e_ibad)
        self.phys_e_istrg = QLineEdit()
        self.phys_e_istrg.setPlaceholderText("ISTRG")
        self.phys_e_istrg.setToolTip("0=连续减慢(默认)，1=大步长")
        self.phys_e_istrg.setMaximumWidth(60)
        phys_e_row.addWidget(self.phys_e_istrg)
        self.phys_e_bnum = QLineEdit()
        self.phys_e_bnum.setPlaceholderText("BNUM")
        self.phys_e_bnum.setToolTip("轫致辐射光子数缩放因子，默认=1")
        self.phys_e_bnum.setMaximumWidth(60)
        phys_e_row.addWidget(self.phys_e_bnum)
        self.phys_e_xnum = QLineEdit()
        self.phys_e_xnum.setPlaceholderText("XNUM")
        self.phys_e_xnum.setToolTip("电子步长缩放因子")
        self.phys_e_xnum.setMaximumWidth(60)
        phys_e_row.addWidget(self.phys_e_xnum)
        self.phys_e_rnok = QLineEdit()
        self.phys_e_rnok.setPlaceholderText("RNOK")
        self.phys_e_rnok.setToolTip("0=Knock-on电子产生光子(默认)，1=关闭")
        self.phys_e_rnok.setMaximumWidth(60)
        phys_e_row.addWidget(self.phys_e_rnok)
        self.phys_e_enum = QLineEdit()
        self.phys_e_enum.setPlaceholderText("ENUM")
        self.phys_e_enum.setToolTip("电子能量离散化点数")
        self.phys_e_enum.setMaximumWidth(60)
        phys_e_row.addWidget(self.phys_e_enum)
        self.phys_e_numb = QLineEdit()
        self.phys_e_numb.setPlaceholderText("NUMB")
        self.phys_e_numb.setToolTip("轫致辐射每子步控制：>0=每子步产生，0=常态默认")
        self.phys_e_numb.setMaximumWidth(60)
        phys_e_row.addWidget(self.phys_e_numb)
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
            # PHYS:N — C810
            phys_n_emax=self.phys_n_emax.text().strip(),
            phys_n_emcnf=self.phys_n_emcnf.text().strip(),
            phys_n_iunr=self.phys_n_iunr.text().strip(),
            phys_n_dnb=self.phys_n_dnb.text().strip(),
            phys_n_fisnu=self.phys_n_fisnu.text().strip(),
            # PHYS:P — C810
            phys_p_emcpf=self.phys_p_emcpf.text().strip(),
            phys_p_ides=self.phys_p_ides.text().strip(),
            phys_p_nocoh=self.phys_p_nocoh.text().strip(),
            phys_p_ispn=self.phys_p_ispn.text().strip(),
            phys_p_nodop=self.phys_p_nodop.text().strip(),
            # PHYS:E — C810
            phys_e_emax=self.phys_e_emax.text().strip(),
            phys_e_ides=self.phys_e_ides.text().strip(),
            phys_e_iphoto=self.phys_e_iphoto.text().strip(),
            phys_e_ibad=self.phys_e_ibad.text().strip(),
            phys_e_istrg=self.phys_e_istrg.text().strip(),
            phys_e_bnum=self.phys_e_bnum.text().strip(),
            phys_e_xnum=self.phys_e_xnum.text().strip(),
            phys_e_rnok=self.phys_e_rnok.text().strip(),
            phys_e_enum=self.phys_e_enum.text().strip(),
            phys_e_numb=self.phys_e_numb.text().strip(),
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
        adv = self.get_data()
        lines = []
        lines.extend(_generate_phys(adv))
        lines.extend(_generate_other_cards(adv))
        return "\n".join(lines)

    def get_raw_overrides(self) -> dict:
        return {"phys": self._raw_phys.get_raw_text()}

    def set_data(self, adv: AdvancedSettings):
        """从导入数据回填 UI（用于 INP 导入）"""
        self.other_edit.setPlainText(adv.other_cards)
        # PHYS:N — C810
        self.phys_n_emax.setText(adv.phys_n_emax or "")
        self.phys_n_emcnf.setText(adv.phys_n_emcnf or "")
        self.phys_n_iunr.setText(adv.phys_n_iunr or "")
        self.phys_n_dnb.setText(adv.phys_n_dnb or "")
        self.phys_n_fisnu.setText(adv.phys_n_fisnu or "")
        # PHYS:P — C810
        self.phys_p_emcpf.setText(adv.phys_p_emcpf or "")
        self.phys_p_ides.setText(adv.phys_p_ides or "")
        self.phys_p_nocoh.setText(adv.phys_p_nocoh or "")
        self.phys_p_ispn.setText(adv.phys_p_ispn or "")
        self.phys_p_nodop.setText(adv.phys_p_nodop or "")
        # PHYS:E — C810
        self.phys_e_emax.setText(adv.phys_e_emax or "")
        self.phys_e_ides.setText(adv.phys_e_ides or "")
        self.phys_e_iphoto.setText(adv.phys_e_iphoto or "")
        self.phys_e_ibad.setText(adv.phys_e_ibad or "")
        self.phys_e_istrg.setText(adv.phys_e_istrg or "")
        self.phys_e_bnum.setText(adv.phys_e_bnum or "")
        self.phys_e_xnum.setText(adv.phys_e_xnum or "")
        self.phys_e_rnok.setText(adv.phys_e_rnok or "")
        self.phys_e_enum.setText(adv.phys_e_enum or "")
        self.phys_e_numb.setText(adv.phys_e_numb or "")
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
