"""
BasicSettings — 纯 UI 视图层（次世代风格）
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QCheckBox, QGridLayout, QScrollArea
)
from PyQt5.QtCore import Qt

from app.widgets.reference_viewer import make_help_button


class BasicSettingsUI:
    def __init__(self):
        self.title_edit: QLineEdit = None
        self.nps_edit: QLineEdit = None
        self.ctme_edit: QLineEdit = None
        self.act_edit: QLineEdit = None
        self.pr_edit: QLineEdit = None
        self.chk_n: QCheckBox = None
        self.chk_p: QCheckBox = None
        self.chk_e: QCheckBox = None
        self.chk_h: QCheckBox = None
        self.chk_he: QCheckBox = None
        self.chk_d: QCheckBox = None
        self.chk_t: QCheckBox = None
        self.chk_a: QCheckBox = None
        self.phys_fis: QCheckBox = None


def create_ui(parent) -> BasicSettingsUI:
    ui = BasicSettingsUI()

    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)

    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setSpacing(0)

    # ═══ 卡片：问题定义 ═══
    grp = QGroupBox()
    grp.setToolTip("MCNP 输入卡基本参数设置：标题卡、粒子类型、运行控制")
    inner = QVBoxLayout(grp)
    inner.setSpacing(14)
    inner.setContentsMargins(20, 20, 20, 16)

    # 标题
    ui.title_edit = QLineEdit()
    ui.title_edit.setPlaceholderText("例: Shielding calculation for Pb container")
    ui.title_edit.setToolTip("MCNP 文件第一行。仅 ASCII 字符，最长 80 列。")
    ui.title_edit.setMaxLength(80)
    inner.addWidget(QLabel("标题 (Title)"))
    inner.addWidget(ui.title_edit)

    # 运行参数行：NPS | CTME | ACT | PRINT
    run_row = QHBoxLayout()
    run_row.setSpacing(12)

    field_config = [
        ("粒子数 NPS",       "例: 1000000",   "nps_edit"),
        ("时间截断 CTME",    "例: 60",         "ctme_edit"),
        ("活化分析 ACT",     "FISSION=N",      "act_edit"),
    ]
    for label, placeholder, attr in field_config:
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(QLabel(label))
        le = QLineEdit()
        le.setPlaceholderText(placeholder)
        col.addWidget(le)
        run_row.addLayout(col)
        setattr(ui, attr, le)

    inner.addLayout(run_row)

    # NONU — 中子裂变开关
    ui.phys_fis = QCheckBox("关闭裂变（NONU）— 中子不会引发裂变")
    ui.phys_fis.setChecked(False)
    ui.phys_fis.setToolTip("勾选后输出 NONU 卡，适合纯散射或屏蔽计算")
    inner.addWidget(ui.phys_fis)

    layout.addWidget(grp)

    # ═══ 卡片：粒子类型 ═══
    grp2 = QGroupBox()
    inner2 = QVBoxLayout(grp2)
    inner2.setSpacing(12)
    inner2.setContentsMargins(20, 20, 20, 16)

    inner2.addWidget(QLabel("粒子类型 (MODE)"))

    par_tip = {
        "N": "N - 中子\n跟踪中子在介质中的输运过程。",
        "P": "P - 光子/γ\n跟踪光子（伽马射线）的输运。",
        "E": "E - 电子\n跟踪电子的输运。",
        "H": "H - 质子\n跟踪质子的输运。",
        "HE": "HE - 重离子\n跟踪α粒子、氘核、氚核等重离子。",
        "D": "D - 氘核\n跟踪氘核的输运。",
        "T": "T - 氚核\n跟踪氚核的输运。",
        "A": "A - α粒子\n跟踪α粒子的输运。",
    }
    checks = []
    for k, label in [("N", "中子"), ("P", "光子"), ("E", "电子"), ("H", "质子"),
                     ("HE", "重离子"), ("D", "氘核"), ("T", "氚核"), ("A", "α粒子")]:
        cb = QCheckBox(f"N  {label}" if k == "N" else f"{k}  {label}")
        cb.setToolTip(par_tip[k])
        checks.append(cb)
    ui.chk_n, ui.chk_p, ui.chk_e, ui.chk_h, ui.chk_he, ui.chk_d, ui.chk_t, ui.chk_a = checks

    mode_grid = QGridLayout()
    mode_grid.setSpacing(8)
    for i, cb in enumerate(checks):
        mode_grid.addWidget(cb, i // 4, i % 4)
    inner2.addLayout(mode_grid)

    layout.addWidget(grp2)

    # ═══ 卡片：PRINT（单独卡片） ═══
    grp3 = QGroupBox()
    inner3 = QVBoxLayout(grp3)
    inner3.setSpacing(8)
    inner3.setContentsMargins(20, 20, 20, 16)

    pr_header = QHBoxLayout()
    pr_header.addWidget(QLabel("PRINT 输出控制"))
    pr_header.addStretch()
    pr_header.addWidget(make_help_button(parent, "PRINT卡说明.md", "MCNP6 PRINT 卡结构参考"))
    inner3.addLayout(pr_header)

    ui.pr_edit = QLineEdit()
    ui.pr_edit.setPlaceholderText("例: 110 40 150 或 -70 -110")
    ui.pr_edit.setToolTip("MCNP PRINT 卡。留空 = 不输出 PRINT 卡")
    inner3.addWidget(ui.pr_edit)

    layout.addWidget(grp3)

    layout.addStretch()
    scroll.setWidget(content)
    outer.addWidget(scroll)

    return ui
