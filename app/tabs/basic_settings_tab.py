"""
📄 基本设置标签页：标题卡、MODE、NPS、CTME
Basic Settings Tab: Title card, MODE, NPS, CTME

This module provides the BasicSettingsTab widget, which allows users to configure
the essential MCNP input card parameters: the problem title card, particle mode selection,
number of particles (NPS), time cutoff (CTME), and neutron fission switch (NONU).

Module contents:
    - BasicSettingsTab: Main widget for basic parameter configuration
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QCheckBox,
    QFormLayout, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal

from app.models import BasicSettings


class BasicSettingsTab(QWidget):
    """基本设置标签页"""

    modeChanged = pyqtSignal(object)  # 发射 BasicSettings（MODE 勾选变化时）

    # Tooltip text for each particle mode option
    # Describes the particle type and its common use cases in MCNP simulations
    PAR_MODE_TOOLTIP = {
        "N": "N - 中子\n跟踪中子在介质中的输运过程。\n大部分 MCNP 问题都需要中子输运。",
        "P": "P - 光子/γ\n跟踪光子（伽马射线）的输运。\n中子反应常伴随产生光子。",
        "E": "E - 电子\n跟踪电子的输运。\n需要电子-光子耦合输运时勾选。",
        "H": "H - 质子\n跟踪质子的输运。\n用于质子治疗、空间辐射屏蔽等。",
        "HE": "HE - 重离子\n跟踪α粒子、氘核、氚核等重离子。\n需相应截面库支持。",
        "D": "D - 氘核\n跟踪氘核的输运。\n用于加速器、聚变中子学等。",
        "T": "T - 氚核\n跟踪氚核的输运。\n用于聚变中子学等。",
        "A": "A - α粒子\n跟踪α粒子的输运。\n用于α辐射源、聚变等。",
    }

    def __init__(self):
        """初始化基本设置标签页"""
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

        # ===== 标题卡
        grp_title = QGroupBox("标题卡（必填）")
        grp_title.setToolTip(
            "MCNP 输入卡的第一行，用于标识问题。\n"
            "⚠ 仅限英文、数字和标点，禁止中文！"
        )
        title_layout = QVBoxLayout(grp_title)

        title_label = QLabel("输入卡标题（纯英文，禁止中文）:")
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("例: Shielding calculation for Pb container")
        self.title_edit.setToolTip(
            "MCNP 文件第一行，标题卡仅支持 ASCII 字符。\n"
            "中文字符会导致 Fortran 解析错位。\n"
            "长度建议不超过 80 列。\n"
            "First line of MCNP file. ASCII characters only.\n"
            "Chinese characters will corrupt Fortran parsing.\n"
            "Recommended length: no more than 80 columns."
        )
        # Enforce max length to prevent Fortran column overflow issues
        # MCNP's Fortran parser reads fixed-format lines, so 80 columns is a hard limit.
        self.title_edit.setMaxLength(80)

        tip = QLabel(
            "<span style='color:gray; font-size:11px;'>"
            "⚠ 标题卡只能使用英文字母、数字和英文标点，不可包含中文"
        )

        title_layout.addWidget(title_label)
        title_layout.addWidget(self.title_edit)
        title_layout.addWidget(tip)
        layout.addWidget(grp_title)

        grp_mode = QGroupBox("MODE 卡（必选至少一种粒子）")
        grp_mode.setToolTip(
            "MODE 卡指定 MCNP 需要跟踪的粒子类型。\n"
            "至少选择一种粒子，最常用的是 N（中子）。"
        )
        mode_layout = QVBoxLayout(grp_mode)

        mode_label = QLabel("选择需要跟踪的粒子")
        self.chk_n = QCheckBox("N - 中子")
        self.chk_n.setToolTip(self.PAR_MODE_TOOLTIP["N"])
        self.chk_p = QCheckBox("P - 光子")
        self.chk_p.setToolTip(self.PAR_MODE_TOOLTIP["P"])
        self.chk_e = QCheckBox("E - 电子")
        self.chk_e.setToolTip(self.PAR_MODE_TOOLTIP["E"])
        self.chk_h = QCheckBox("H - 质子")
        self.chk_h.setToolTip(self.PAR_MODE_TOOLTIP["H"])
        self.chk_he = QCheckBox("HE - 重离子")
        self.chk_he.setToolTip(self.PAR_MODE_TOOLTIP["HE"])
        self.chk_d = QCheckBox("D - 氘核")
        self.chk_d.setToolTip(self.PAR_MODE_TOOLTIP["D"])
        self.chk_t = QCheckBox("T - 氚核")
        self.chk_t.setToolTip(self.PAR_MODE_TOOLTIP["T"])
        self.chk_a = QCheckBox("A - α粒子")
        self.chk_a.setToolTip(self.PAR_MODE_TOOLTIP["A"])

        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.chk_n)
        mode_layout.addWidget(self.chk_p)
        mode_layout.addWidget(self.chk_e)
        mode_layout.addWidget(self.chk_h)
        mode_layout.addWidget(self.chk_he)
        mode_layout.addWidget(self.chk_d)
        mode_layout.addWidget(self.chk_t)
        mode_layout.addWidget(self.chk_a)
        layout.addWidget(grp_mode)

        # 连接 MODE 复选框变化信号
        for chk in [self.chk_n, self.chk_p, self.chk_e, self.chk_h,
                     self.chk_he, self.chk_d, self.chk_t, self.chk_a]:
            chk.toggled.connect(lambda: self.modeChanged.emit(self.get_data()))

        grp_nps = QGroupBox("NPS 卡（必填）")
        grp_nps.setToolTip(
            "NPS 设定模拟的粒子总数，\n"
            "数值越大统计误差越小，但耗时越长。"
        )
        nps_layout = QFormLayout(grp_nps)

        self.nps_edit = QLineEdit()
        self.nps_edit.setPlaceholderText("例: 1000000 或 1.00E+05，留空不生成")
        self.nps_edit.setToolTip(
            "每个粒子代表一次独立的随机游走模拟。\n"
            "推荐：10,000（粗略） / 1,000,000（工程级） / 100,000,000+（高精度）\n"
            "支持科学计数法，如 1.00E+05"
        )

        nps_hint = QLabel(
            "<span style='color:gray; font-size:11px;'>"
            "留空 = 不生成 NPS 卡"
        )

        nps_layout.addRow("粒子数 NPS:", self.nps_edit)
        nps_layout.addRow("", nps_hint)
        layout.addWidget(grp_nps)

        grp_ctme = QGroupBox("CTME 卡（可选）")
        grp_ctme.setToolTip(
            "CTME 设定最大运行时间（分钟），\n"
            "到达时间后 MCNP 自动停止。\n"
            "留空表示不设时间限制。"
        )
        ctme_layout = QFormLayout(grp_ctme)

        self.ctme_edit = QLineEdit()
        self.ctme_edit.setPlaceholderText("例: 60 或 30.5，留空不生成")
        self.ctme_edit.setToolTip(
            "单位：分钟\n"
            "例如：60 = 1 小时后自动停止\n"
            "留空 = 不设时间限制"
        )

        ctme_hint = QLabel(
            "<span style='color:gray; font-size:11px;'>"
            "留空 = 不设时间截断，由 NPS 控制终止"
        )

        ctme_layout.addRow("时间截断 CTME (min):", self.ctme_edit)
        ctme_layout.addRow("", ctme_hint)
        layout.addWidget(grp_ctme)

        grp_phys = QGroupBox("NONU — 中子裂变开关")
        grp_phys.setToolTip(
            "关闭裂变后中子不会引发裂变，适合纯散射或屏蔽计算。\n"
            "注意：MCNP6.1 的 PHYS:N 卡已无独立的非弹性/相干散射开关。"
        )
        phys_layout = QVBoxLayout(grp_phys)

        self.phys_fis = QCheckBox("关闭裂变（NONU）— 中子不会引发裂变")
        self.phys_fis.setChecked(False)
        self.phys_fis.setToolTip(
            "勾选后输出 NONU 卡，中子不会引发裂变，适合纯散射或屏蔽计算"
        )
        phys_layout.addWidget(self.phys_fis)

        phys_hint = QLabel(
            "<span style='color:gray; font-size:11px;'>"
            "💡 默认不勾选（裂变开启）。仅屏蔽计算时才需要勾选</span>"
        )
        phys_layout.addWidget(phys_hint)
        layout.addWidget(grp_phys)

        # Add stretch to push all content to the top
        # Prevents widgets from being stretched across the full scroll area height.
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def get_data(self) -> BasicSettings:
        """获取当前标签页的数据"""
        return BasicSettings(
            title=self.title_edit.text().strip(),
            mode_n=self.chk_n.isChecked(),
            mode_p=self.chk_p.isChecked(),
            mode_e=self.chk_e.isChecked(),
            mode_h=self.chk_h.isChecked(),
            mode_he=self.chk_he.isChecked(),
            mode_d=self.chk_d.isChecked(),
            mode_t=self.chk_t.isChecked(),
            mode_a=self.chk_a.isChecked(),
            nps=self.nps_edit.text().strip(),
            ctme=self.ctme_edit.text().strip(),
            # 复选框文字="关闭裂变"：勾选=True → 关闭裂变 → phys_fis=False（输出 NONU）
            # 不勾选=False → 裂变开启 → phys_fis=True（不输出 NONU）
            # Checkbox text="Disable fission": checked=True → fission off → phys_fis=False (output NONU)
            # Unchecked=False → fission on → phys_fis=True (omit NONU)
            phys_fis=not self.phys_fis.isChecked(),
        )

    def set_data(self, basic: BasicSettings):
        """从 BasicSettings 回填 UI（用于 INP 导入） / Populate UI from BasicSettings (for INP import).

        Restores all widget states from a BasicSettings object, used when
        loading an existing MCNP input file. This is the inverse of get_data().

        Args:
            basic: The BasicSettings data object containing saved values.
        """
        self.title_edit.setText(basic.title)
        self.chk_n.setChecked(basic.mode_n)
        self.chk_p.setChecked(basic.mode_p)
        self.chk_e.setChecked(basic.mode_e)
        self.chk_h.setChecked(basic.mode_h)
        self.chk_he.setChecked(basic.mode_he)
        self.chk_d.setChecked(getattr(basic, 'mode_d', False))
        self.chk_t.setChecked(getattr(basic, 'mode_t', False))
        self.chk_a.setChecked(getattr(basic, 'mode_a', False))
        self.nps_edit.setText(basic.nps or "")
        self.ctme_edit.setText(basic.ctme or "")
        self.phys_fis.setChecked(not basic.phys_fis)
