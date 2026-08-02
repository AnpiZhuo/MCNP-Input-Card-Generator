"""Advanced — 纯 UI 视图层"""

from collections.abc import Callable
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPlainTextEdit, QLabel, QLineEdit, QPushButton,
    QScrollArea
)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QFont

from app.models import AdvancedSettings
from app.widgets.text_mode_section import TextModeSection
from app.widgets.ui_helpers import make_section_title


class AdvancedUI:
    def __init__(self):
        self.other_edit: QPlainTextEdit = None
        self.xsdir_edit: QLineEdit = None
        self.xsdir_status: QLabel = None
        self.phys_n_emax: QLineEdit = None
        self.phys_n_emcnf: QLineEdit = None
        self.phys_n_iunr: QLineEdit = None
        self.phys_n_dnb: QLineEdit = None
        self.phys_n_fisnu: QLineEdit = None
        self.phys_p_emcpf: QLineEdit = None
        self.phys_p_ides: QLineEdit = None
        self.phys_p_nocoh: QLineEdit = None
        self.phys_p_ispn: QLineEdit = None
        self.phys_p_nodop: QLineEdit = None
        self.phys_e_emax: QLineEdit = None
        self.phys_e_ides: QLineEdit = None
        self.phys_e_iphoto: QLineEdit = None
        self.phys_e_ibad: QLineEdit = None
        self.phys_e_istrg: QLineEdit = None
        self.phys_e_bnum: QLineEdit = None
        self.phys_e_xnum: QLineEdit = None
        self.phys_e_rnok: QLineEdit = None
        self.phys_e_enum: QLineEdit = None
        self.phys_e_numb: QLineEdit = None
        self.phys_h_emax: QLineEdit = None
        self.phys_h_ie: QLineEdit = None
        self.phys_h_ipr: QLineEdit = None
        self.phys_h_rgas: QLineEdit = None
        self.phys_h_emin: QLineEdit = None
        self.phys_h_ecut: QLineEdit = None
        self.phys_he_emax: QLineEdit = None
        self.phys_he_ie: QLineEdit = None
        self.phys_he_ipr: QLineEdit = None
        self.phys_he_rgas: QLineEdit = None
        self.phys_he_emin: QLineEdit = None
        self.phys_he_ecut: QLineEdit = None


def create_ui(parent,
              gen_phys_fn: Callable[[], str],
              gen_cut_fn: Callable[[], str]) -> AdvancedUI:
    ui = AdvancedUI()
    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)

    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setSpacing(16)

    # ═══ 其他 MCNP 卡片 ═══
    grp_other = QGroupBox("其他 MCNP 卡片")
    inner_other = QVBoxLayout(grp_other)
    inner_other.setSpacing(8)
    inner_other.setContentsMargins(20, 20, 20, 20)
    hint = QLabel(
        "常见可在此处添加的卡片：KCODE / KSRC / PRDMP / PTRAC / TOTNU / "
        "VOID / DBCN / PERT / SSW/SSR / ESPLT / WWE/WWN …\n"
        "格式：每行一张卡片，如 KCODE 5000 1.0 50 100"
    )
    hint.setWordWrap(True)
    hint.setStyleSheet("font-size:12px;")
    inner_other.addWidget(hint)
    ui.other_edit = QPlainTextEdit()
    ui.other_edit.setPlaceholderText("示例:\nKCODE  5000  1.0  50  100\nKSRC  0  0  0\nPRDMP  100  0  0  0  0")
    ui.other_edit.setToolTip("每行一个 MCNP 卡片，按格式直接写入 INP 数据段")
    ui.other_edit.setFont(QFont("Consolas", 10))
    ui.other_edit.setMinimumHeight(200)
    inner_other.addWidget(ui.other_edit)
    warn = QLabel("⚠ 输入的内容不会校验格式，请自行确认正确性")
    warn.setStyleSheet("color:#F59E0B; font-size:12px;")
    inner_other.addWidget(warn)
    layout.addWidget(grp_other)

    # ═══ PHYS 卡 ═══
    grp_phys = QGroupBox("PHYS 卡")
    inner_phys = QVBoxLayout(grp_phys)
    inner_phys.setSpacing(8)
    inner_phys.setContentsMargins(20, 20, 20, 20)
    phys_header = QHBoxLayout()
    lbl_phys = QLabel("留空 = 使用 MCNP 默认值"); lbl_phys.setStyleSheet("font-size:12px;")
    phys_header.addWidget(lbl_phys)
    phys_header.addStretch()

    phys_container = QWidget()
    phys_layout = QVBoxLayout(phys_container)
    phys_layout.setSpacing(8)
    phys_layout.setContentsMargins(0, 0, 0, 0)

    # PHYS:N
    phys_n = QHBoxLayout(); lbl_n = QLabel("PHYS:N"); lbl_n.setStyleSheet("font-weight:600;"); phys_n.addWidget(lbl_n)
    lines_phys_n = []
    for ph, pl, tip in [("phys_n_emax","EMAX","中子能量上限 (MeV)"),("phys_n_emcnf","EMCNF","俘获方式转变能 (MeV)"),
                         ("phys_n_iunr","IUNR","未分辨共振概率表"),("phys_n_dnb","DNB","缓发中子处理"),
                         ("phys_n_fisnu","FISNU","裂变中子谱")]:
        le = QLineEdit(); le.setPlaceholderText(pl); le.setToolTip(tip); le.setMaximumWidth(80)
        phys_n.addWidget(le); lines_phys_n.append(le)
    ui.phys_n_emax, ui.phys_n_emcnf, ui.phys_n_iunr, ui.phys_n_dnb, ui.phys_n_fisnu = lines_phys_n
    phys_n.addStretch(); phys_layout.addLayout(phys_n)

    # PHYS:P
    phys_p = QHBoxLayout(); lbl_p = QLabel("PHYS:P"); lbl_p.setStyleSheet("font-weight:600;"); phys_p.addWidget(lbl_p)
    for attr, pl, tip in [("phys_p_emcpf","EMCPF","详细/简单分界能量"),("phys_p_ides","IDES","0=光子产生电子"),
                          ("phys_p_nocoh","NOCOH","相干散射"),("phys_p_ispn","ISPN","光核作用"),
                          ("phys_p_nodop","NODOP","Doppler展宽")]:
        le = QLineEdit(); le.setPlaceholderText(pl); le.setToolTip(tip); le.setMaximumWidth(80)
        phys_p.addWidget(le); setattr(ui, attr, le)
    phys_p.addStretch(); phys_layout.addLayout(phys_p)

    # PHYS:E
    phys_e = QHBoxLayout(); lbl_e = QLabel("PHYS:E"); lbl_e.setStyleSheet("font-weight:600;"); phys_e.addWidget(lbl_e)
    for attr, pl, tip in [("phys_e_emax","EMAX","电子能量上限"),("phys_e_ides","IDES","光子产生电子"),
                          ("phys_e_iphoto","IPHOT","电子产生光子"),("phys_e_ibad","IBAD","角分布"),
                          ("phys_e_istrg","ISTRG","连续减慢"),("phys_e_bnum","BNUM","轫致辐射缩放"),
                          ("phys_e_xnum","XNUM","步长缩放"),("phys_e_rnok","RNOK","Knock-on"),
                          ("phys_e_enum","ENUM","离散化点数"),("phys_e_numb","NUMB","轫致辐射控制")]:
        le = QLineEdit(); le.setPlaceholderText(pl); le.setToolTip(tip); le.setMaximumWidth(70)
        phys_e.addWidget(le); setattr(ui, attr, le)
    phys_e.addStretch(); phys_layout.addLayout(phys_e)

    # PHYS:H
    phys_h = QHBoxLayout(); lbl_h = QLabel("PHYS:H"); lbl_h.setStyleSheet("font-weight:600;"); phys_h.addWidget(lbl_h)
    for attr, pl, tip in [("phys_h_emax","emax","最大能量"),("phys_h_ie","ie","非弹性散射模型"),
                          ("phys_h_ipr","ipr","核反冲"),("phys_h_rgas","rgas","气体截面"),
                          ("phys_h_emin","emin","最小能量"),("phys_h_ecut","ecut","能量截断")]:
        le = QLineEdit(); le.setPlaceholderText(pl); le.setToolTip(tip); le.setMaximumWidth(80)
        phys_h.addWidget(le); setattr(ui, attr, le)
    phys_h.addStretch(); phys_layout.addLayout(phys_h)

    # PHYS:HE
    phys_he = QHBoxLayout(); lbl_he = QLabel("PHYS:HE"); lbl_he.setStyleSheet("font-weight:600;"); phys_he.addWidget(lbl_he)
    for attr, pl in [("phys_he_emax","emax"),("phys_he_ie","ie"),("phys_he_ipr","ipr"),
                     ("phys_he_rgas","rgas"),("phys_he_emin","emin"),("phys_he_ecut","ecut")]:
        le = QLineEdit(); le.setPlaceholderText(pl); le.setMaximumWidth(80)
        phys_he.addWidget(le); setattr(ui, attr, le)
    phys_he.addStretch(); phys_layout.addLayout(phys_he)

    phys_raw = TextModeSection(form_widget=phys_container, generate_fn=gen_phys_fn, section_name="phys")
    phys_header.addWidget(phys_raw.toggle_btn)
    inner_phys.addLayout(phys_header)
    inner_phys.addWidget(phys_raw.stack)
    layout.addWidget(grp_phys)

    # ═══ CUT 卡 ═══
    grp_cut = QGroupBox("CUT 卡")
    inner_cut = QVBoxLayout(grp_cut)
    inner_cut.setSpacing(6)
    inner_cut.setContentsMargins(20, 20, 20, 20)
    cut_header = QHBoxLayout()
    lbl_cut = QLabel("粒子截断设置（CUT 卡）")
    lbl_cut.setStyleSheet("font-weight:600; font-size:12px;")
    cut_header.addWidget(lbl_cut)
    cut_header.addStretch()

    cut_container = QWidget()
    cut_vbox = QVBoxLayout(cut_container)
    cut_vbox.setSpacing(4)
    cut_vbox.setContentsMargins(0, 0, 0, 0)

    header_row = QWidget()
    hh = QHBoxLayout(header_row); hh.setContentsMargins(0,0,0,0)
    for text, w in [("粒子",80),("tme",100),("e",100),("wc1",100),("wc2",100),("swtm",100)]:
        l = QLabel(text); l.setStyleSheet("font-weight:600;"); l.setMinimumWidth(w); hh.addWidget(l)
    hh.addStretch(); cut_vbox.addWidget(header_row)

    field_names = ["t","e","wc1","wc2","swtm"]
    field_labels = {"t":"时间截断","e":"能量截断","wc1":"权重比1","wc2":"权重比2","swtm":"群标志"}
    pcn = {"n":"中子","p":"光子","e":"电子","h":"质子","he":"重离子","d":"氘核","t":"氚核","a":"α粒子"}
    for p, label, _visible in [("n","CUT:N 中子",True),("p","CUT:P 光子",True),("e","CUT:E 电子",True),
                                ("h","CUT:H 质子",True),("he","CUT:HE 重离子",True),
                                ("d","CUT:D 氘核",False),("t","CUT:T 氚核",False),("a","CUT:A α粒子",False)]:
        row = QWidget(); hbox = QHBoxLayout(row); hbox.setContentsMargins(0,0,0,0)
        hbox.addWidget(QLabel(label))
        for fn in field_names:
            le = QLineEdit(); le.setPlaceholderText("留空"); le.setMaximumWidth(100)
            le.setToolTip(f"{pcn.get(p,p)} {field_labels[fn]}")
            setattr(ui, f"cut_{p}_{fn}", le)
            hbox.addWidget(le)
        hbox.addStretch(); cut_vbox.addWidget(row)

    tip = QLabel("💡 留空 = 使用 MCNP 默认值")
    tip.setStyleSheet("font-size:12px;")
    cut_vbox.addWidget(tip)
    cut_raw = TextModeSection(form_widget=cut_container, generate_fn=gen_cut_fn, section_name="cut")
    cut_header.addWidget(cut_raw.toggle_btn)
    inner_cut.addLayout(cut_header)
    inner_cut.addWidget(cut_raw.stack)
    layout.addWidget(grp_cut)

    # ═══ xsdir ═══
    grp_xsdir = QGroupBox("截面库路径")
    inner_xsdir = QVBoxLayout(grp_xsdir)
    inner_xsdir.setSpacing(6)
    inner_xsdir.setContentsMargins(20, 20, 20, 20)
    xsdir_row = QHBoxLayout()
    ui.xsdir_edit = QLineEdit()
    ui.xsdir_edit.setPlaceholderText("例: D:\\MCNP\\MCNP6\\MCNP_DATA\\xsdir")
    ui.xsdir_edit.setToolTip("MCNP 截面库索引文件（xsdir）的完整路径")
    xsdir_row.addWidget(ui.xsdir_edit, 1)
    btn_browse = QPushButton("浏览…"); btn_browse.setToolTip("选择 xsdir 文件"); btn_browse.setProperty("cssClass", "btnBrowse")
    xsdir_row.addWidget(btn_browse)
    inner_xsdir.addLayout(xsdir_row)
    ui.xsdir_status = QLabel("")
    inner_xsdir.addWidget(ui.xsdir_status)
    tip_xsdir = QLabel("💡 设置 xsdir 后，材料编辑器中输入的 ZAID 会自动核对是否在库中")
    tip_xsdir.setStyleSheet("font-size:12px;")
    inner_xsdir.addWidget(tip_xsdir)
    layout.addWidget(grp_xsdir)

    layout.addStretch()
    scroll.setWidget(content)
    outer.addWidget(scroll)

    return ui, btn_browse, phys_raw, cut_raw
