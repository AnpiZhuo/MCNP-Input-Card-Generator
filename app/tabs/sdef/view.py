"""Sdef — 纯 UI 视图层"""

from collections.abc import Callable
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTableWidget, QHeaderView, QLabel, QPushButton,
    QLineEdit, QComboBox, QFormLayout, QScrollArea,
    QStackedWidget,
)
from PyQt5.QtCore import Qt, QSettings

from app.widgets.text_mode_section import TextModeSection
from app.widgets.ui_helpers import make_add_button, make_delete_button


class SdefUI:
    def __init__(self):
        self.stack: QStackedWidget = None
        self.source_table: QTableWidget = None
        self.btn_add: QPushButton = None
        self.btn_del: QPushButton = None
        self.mode_combo = None
        # KCODE
        self.kcode_nsrc: QLineEdit = None
        self.kcode_rkk: QLineEdit = None
        self.kcode_ikz: QLineEdit = None
        self.kcode_kct: QLineEdit = None
        self.kcode_knrm: QLineEdit = None
        self.ksrc_table: QTableWidget = None
        self.btn_ksrc_add: QPushButton = None
        self.btn_ksrc_del: QPushButton = None
        # SDEF 字段 (distribution mode)
        self.sdef_par: QLineEdit = None
        self.sdef_erg: QLineEdit = None
        self.sdef_pos_x: QLineEdit = None
        self.sdef_pos_y: QLineEdit = None
        self.sdef_pos_z: QLineEdit = None
        self.sdef_wgt: QLineEdit = None
        self.sdef_tme: QLineEdit = None
        self.sdef_dir: QLineEdit = None
        self.sdef_vec: QLineEdit = None
        self.sdef_axs: QLineEdit = None
        self.sdef_ext: QLineEdit = None
        self.sdef_rad: QLineEdit = None
        self.sdef_cel: QLineEdit = None
        self.sdef_sur: QLineEdit = None
        self.sdef_nrm: QLineEdit = None
        self.sdef_tr: QLineEdit = None
        self.sdef_ccc: QLineEdit = None
        self.sdef_ara: QLineEdit = None
        self.sdef_rate: QLineEdit = None
        self.sdef_extra: QLineEdit = None


def create_ui(parent,
              gen_fn: Callable[[], str],
              gen_dist_fn: Callable[[], str]) -> SdefUI:
    ui = SdefUI()
    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)

    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setSpacing(16)

    grp = QGroupBox("源定义")
    inner = QVBoxLayout(grp)
    inner.setSpacing(10)
    inner.setContentsMargins(20, 20, 20, 20)

    # ── 模式切换 ──
    mode_row = QHBoxLayout()
    mode_row.addWidget(QLabel("源模式："))
    ui.mode_combo = QComboBox()
    ui.mode_combo.addItems(["固定点源", "分布源", "KCODE 临界源"])
    ui.mode_combo.setToolTip("固定点源 — 离散多源列表\n分布源 — SDEF 字段 + SI/SP 分布卡\nKCODE 临界源 — 裂变链计算")
    mode_row.addWidget(ui.mode_combo)
    mode_row.addStretch()
    inner.addLayout(mode_row)

    # ── QStackedWidget ──
    ui.stack = QStackedWidget()

    # Page 0: 固定点源
    page0 = QWidget()
    p0 = QVBoxLayout(page0)
    p0.setContentsMargins(0, 0, 0, 0)

    toolbar = QHBoxLayout()
    lbl = QLabel("固定点源列表"); lbl.setStyleSheet("font-weight:600; font-size:12px;")
    toolbar.addWidget(lbl)
    toolbar.addStretch()
    ui.btn_add = make_add_button("+ 添加源")
    ui.btn_del = make_delete_button("× 删除选中")
    toolbar.addWidget(ui.btn_add)
    toolbar.addWidget(ui.btn_del)
    p0.addLayout(toolbar)

    ui.source_table = QTableWidget(0, 6)
    ui.source_table.setHorizontalHeaderLabels(["粒子", "能量", "位置", "权重", "方向", "操作"])
    hdr = ui.source_table.horizontalHeader()
    hdr.setSectionResizeMode(QHeaderView.Interactive)
    hdr.setStretchLastSection(False)
    ui.source_table.setColumnWidth(0, 60)
    ui.source_table.setColumnWidth(1, 80)
    ui.source_table.setColumnWidth(2, 180)
    ui.source_table.setColumnWidth(3, 60)
    ui.source_table.setColumnWidth(4, 80)
    ui.source_table.setColumnWidth(5, 60)
    ui.source_table.setEditTriggers(QTableWidget.NoEditTriggers)
    ui.source_table.setSelectionBehavior(QTableWidget.SelectRows)
    p0.addWidget(ui.source_table)

    raw_sdef = TextModeSection(form_widget=page0, generate_fn=gen_fn, section_name="sdef")
    toolbar.insertWidget(toolbar.indexOf(ui.btn_del) + 1, raw_sdef.toggle_btn)
    ui.stack.addWidget(raw_sdef.stack)
    # store refs
    ui._raw_sdef = raw_sdef

    # Page 1: 分布源
    page1 = QWidget()
    p1 = QVBoxLayout(page1)
    p1.setContentsMargins(0, 0, 0, 0)

    # SDEF 字段
    sdef_form = QFormLayout()
    sdef_form.setSpacing(6)
    ui.sdef_par = QLineEdit()
    ui.sdef_par.setPlaceholderText("例: 1 或 D1")
    ui.sdef_par.setToolTip("粒子类型：1=中子 n, 2=光子 p, 3=电子 e, H=质子, A=α\n或输入 D1/D2 引用分布")
    sdef_form.addRow("PAR:", ui.sdef_par)

    for attr, label in [("sdef_erg","ERG"),("sdef_wgt","WGT"),
                        ("sdef_tme","TME"),("sdef_dir","DIR"),("sdef_vec","VEC"),
                        ("sdef_axs","AXS"),("sdef_ext","EXT"),("sdef_rad","RAD"),
                        ("sdef_cel","CEL")]:
        le = QLineEdit(); le.setPlaceholderText(label)
        setattr(ui, attr, le)
        sdef_form.addRow(f"{label}:", le)

    # POS: 三个子字段 (x y z)
    pos_widget = QWidget()
    pos_row = QHBoxLayout(pos_widget)
    pos_row.setContentsMargins(0, 0, 0, 0)
    for lab, attr in [("x","sdef_pos_x"),("y","sdef_pos_y"),("z","sdef_pos_z")]:
        le = QLineEdit(); le.setPlaceholderText(lab); le.setMaximumWidth(80)
        setattr(ui, attr, le)
        pos_row.addWidget(QLabel(lab))
        pos_row.addWidget(le)
    pos_row.addStretch()
    sdef_form.addRow("POS:", pos_widget)

    # 折叠额外参数
    extra_container = QWidget()
    extra_layout = QVBoxLayout(extra_container)
    extra_layout.setContentsMargins(0, 0, 0, 0)
    btn_extra = QPushButton("▼ 额外参数")
    btn_extra.setCheckable(True)
    extra_layout.addWidget(btn_extra)
    extra_fields = QWidget()
    extra_fields.setVisible(False)
    ef = QFormLayout(extra_fields)
    ef.setSpacing(4)
    for attr, label in [("sdef_sur","SUR"),("sdef_nrm","NRM"),("sdef_tr","TR"),
                        ("sdef_ccc","CCC"),("sdef_ara","ARA"),("sdef_rate","RATE")]:
        le = QLineEdit(); le.setPlaceholderText(label)
        setattr(ui, attr, le)
        ef.addRow(f"{label}:", le)
    ui.sdef_extra = QLineEdit(); ui.sdef_extra.setPlaceholderText("其他 SDEF 参数")
    ef.addRow("其他:", ui.sdef_extra)
    extra_layout.addWidget(extra_fields)
    ui._btn_extra = btn_extra

    sdef_form.addRow(extra_container)
    p1.addLayout(sdef_form)

    # SI/SP 分布卡容器（由控制器动态填充）
    ui.sisp_container = QVBoxLayout()
    sisp_grp_hint = QLabel("SI 类型: L=离散列表  H=连续均匀  A=解析函数  S=分布号  Q=用户概率")
    sisp_grp_hint.setStyleSheet("font-size:11px;")
    p1.addWidget(sisp_grp_hint)
    p1.addLayout(ui.sisp_container)
    ui.btn_add_sisp = QPushButton("＋ 添加分布")
    ui.btn_add_sisp.setToolTip("手动添加一个 SI/SP 对（Dn 编号自动分配）")
    p1.addWidget(ui.btn_add_sisp)

    raw_dist = TextModeSection(form_widget=page1, generate_fn=gen_dist_fn, section_name="dist")
    ui.stack.addWidget(raw_dist.stack)
    ui._raw_dist = raw_dist

    # Page 2: KCODE 临界源
    page2 = QWidget()
    p2 = QVBoxLayout(page2)
    p2.setContentsMargins(0, 0, 0, 0)
    p2.setSpacing(8)

    kcode_grp = QGroupBox("KCODE 参数")
    kf = QFormLayout(kcode_grp)
    kf.setSpacing(6)
    ui.kcode_nsrc = QLineEdit(); ui.kcode_nsrc.setPlaceholderText("如: 50000"); ui.kcode_nsrc.setToolTip("每代粒子数"); kf.addRow("NSRC（每代粒子数）:", ui.kcode_nsrc)
    ui.kcode_rkk = QLineEdit(); ui.kcode_rkk.setPlaceholderText("如: 1.0"); ui.kcode_rkk.setToolTip("初始 keff 估计"); kf.addRow("RKK（初始 keff）:", ui.kcode_rkk)
    ui.kcode_ikz = QLineEdit(); ui.kcode_ikz.setPlaceholderText("如: 50"); ui.kcode_ikz.setToolTip("非活跃代数"); kf.addRow("IKZ（非活跃代数）:", ui.kcode_ikz)
    ui.kcode_kct = QLineEdit(); ui.kcode_kct.setPlaceholderText("如: 200"); ui.kcode_kct.setToolTip("活跃代数"); kf.addRow("KCT（总代数）:", ui.kcode_kct)
    ui.kcode_knrm = QLineEdit(); ui.kcode_knrm.setPlaceholderText("可选"); ui.kcode_knrm.setToolTip("归一化选项"); kf.addRow("KNRM（可选）:", ui.kcode_knrm)
    p2.addWidget(kcode_grp)

    ksrc_grp = QGroupBox("KSRC 初始裂变点")
    ksrc_layout = QVBoxLayout(ksrc_grp)
    ksrc_toolbar = QHBoxLayout()
    ksrc_toolbar.addWidget(QLabel("X  Y  Z 坐标"))
    ksrc_toolbar.addStretch()
    ui.btn_ksrc_add = QPushButton("+ 添加点"); ui.btn_ksrc_add.setToolTip("添加一个裂变起始点"); ksrc_toolbar.addWidget(ui.btn_ksrc_add)
    ui.btn_ksrc_del = QPushButton("× 删除选中"); ui.btn_ksrc_del.setToolTip("删除选中裂变点"); ksrc_toolbar.addWidget(ui.btn_ksrc_del)
    ksrc_layout.addLayout(ksrc_toolbar)
    ui.ksrc_table = QTableWidget(0, 3)
    ui.ksrc_table.setHorizontalHeaderLabels(["X", "Y", "Z"])
    hk = ui.ksrc_table.horizontalHeader()
    hk.setSectionResizeMode(QHeaderView.Interactive)
    hk.setStretchLastSection(False)
    ui.ksrc_table.setColumnWidth(0, 120); ui.ksrc_table.setColumnWidth(1, 120); ui.ksrc_table.setColumnWidth(2, 120)
    ui.ksrc_table.setEditTriggers(QTableWidget.DoubleClicked)
    ui.ksrc_table.setSelectionBehavior(QTableWidget.SelectRows)
    ksrc_layout.addWidget(ui.ksrc_table)
    p2.addWidget(ksrc_grp, 1)

    ui.stack.addWidget(page2)  # index 2

    inner.addWidget(ui.stack)

    # 上下文提示标签
    ui.hint = QLabel("")
    ui.hint.setStyleSheet("font-size:12px;")
    inner.addWidget(ui.hint)

    layout.addWidget(grp)
    layout.addStretch()
    scroll.setWidget(content)
    outer.addWidget(scroll)

    return ui, btn_extra, raw_sdef, raw_dist
