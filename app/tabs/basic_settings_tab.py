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
from PyQt5.QtCore import Qt

from app.models import BasicSettings


class BasicSettingsTab(QWidget):
    """基本设置标签页 / Basic Settings Tab

    Provides UI controls for configuring the core MCNP simulation parameters:
    title card, MODE card (particle types), NPS (number of histories),
    CTME (time cutoff), and the NONU (fission disable) switch.

    Data flows:
        - get_data() -> BasicSettings (used by the INP generator)
        - set_data(BasicSettings) <- INP import (populate UI from parsed file)
    """

    # Tooltip text for each particle mode option
    # Describes the particle type and its common use cases in MCNP simulations
    PAR_MODE_TOOLTIP = {
        "N": "N - 中子（Neutron）\n跟踪中子在介质中的输运过程。\n大部分 MCNP 问题都需要中子输运。\n"
             "N - Neutron\nTracks neutron transport through media.\nRequired for most MCNP problems.",
        "P": "P - 光子/γ（Photon）\n跟踪光子（伽马射线）的输运。\n中子反应常伴随产生光子。\n"
             "P - Photon/Gamma\nTracks photon transport.\nNeutron reactions often produce photons.",
        "E": "E - 电子（Electron）\n跟踪电子的输运。\n需要电子-光子耦合输运时勾选。\n"
             "E - Electron\nTracks electron transport.\nEnable for coupled electron-photon transport.",
        "H": "H - 质子（Proton）\n跟踪质子的输运。\n用于质子治疗、空间辐射屏蔽等。\n"
             "H - Proton\nTracks proton transport.\nUsed for proton therapy, space shielding, etc.",
        "HE": "HE - 重离子（Heavy Ion）\n跟踪α粒子、氘核、氚核等重离子。\n需相应截面库支持。\n"
              "HE - Heavy Ion\nTracks alpha particles, deuterons, tritons, etc.\nRequires appropriate cross-section libraries.",
    }

    def __init__(self):
        """Initialize the basic settings tab and build the UI."""
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """Build the complete UI layout for the basic settings tab.

        Creates scrollable content containing:
        - Title card input (required, ASCII-only)
        - MODE card checkboxes (particle type selection)
        - NPS input (number of histories)
        - CTME input (time cutoff, optional)
        - NONU checkbox (fission disable for shielding calculations)

        Each section is wrapped in a QGroupBox with bilingual labels and tooltips.
        """
        # Outer layout with zero margins for seamless scroll area integration
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Wrap content in a scroll area to support small screen sizes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(16)

        # ===== 标题卡 / Title Card =====
        # The title card is the first line of any MCNP input file.
        # It must be ASCII-only — Chinese characters will cause Fortran parsing errors.
        grp_title = QGroupBox("标题卡（必填） / Title Card (Required)")
        grp_title.setToolTip(
            "MCNP 输入卡的第一行，用于标识问题。\n"
            "⚠ 仅限英文、数字和标点，禁止中文！\n"
            "First line of the MCNP input file, used to identify the problem.\n"
            "ASCII characters only — Chinese characters will cause Fortran parsing errors."
        )
        title_layout = QVBoxLayout(grp_title)

        title_label = QLabel("输入卡标题（纯英文，禁止中文） / Title (ASCII only, no Chinese):")
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText(
            "Example: Shielding calculation for Pb container"
        )
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
            "⚠ 标题卡只能使用英文字母、数字和英文标点，不可包含中文 / "
            "Title card allows only ASCII letters, digits, and punctuation"
        )

        title_layout.addWidget(title_label)
        title_layout.addWidget(self.title_edit)
        title_layout.addWidget(tip)
        layout.addWidget(grp_title)

        # ===== MODE 卡 / MODE Card =====
        # MODE card tells MCNP which particle types to track.
        # At least one particle type must be selected; N (neutron) is the most common.
        grp_mode = QGroupBox("MODE 卡（必选至少一种粒子） / MODE Card (Select at least one particle type)")
        grp_mode.setToolTip(
            "MODE 卡指定 MCNP 需要跟踪的粒子类型。\n"
            "至少选择一种粒子，最常用的是 N（中子）。\n"
            "MODE card specifies which particle types MCNP should track.\n"
            "Select at least one. N (neutron) is the most common."
        )
        mode_layout = QVBoxLayout(grp_mode)

        mode_label = QLabel("选择需要跟踪的粒子 / Select particles to track:")
        # Neutron checkbox
        self.chk_n = QCheckBox("N - 中子（Neutron）")
        self.chk_n.setToolTip(self.PAR_MODE_TOOLTIP["N"])
        # Photon/gamma checkbox
        self.chk_p = QCheckBox("P - 光子 / γ（Photon）")
        self.chk_p.setToolTip(self.PAR_MODE_TOOLTIP["P"])
        # Electron checkbox
        self.chk_e = QCheckBox("E - 电子（Electron）")
        self.chk_e.setToolTip(self.PAR_MODE_TOOLTIP["E"])
        # Proton checkbox
        self.chk_h = QCheckBox("H - 质子（Proton）")
        self.chk_h.setToolTip(self.PAR_MODE_TOOLTIP["H"])
        # Heavy ion checkbox
        self.chk_he = QCheckBox("HE - 重离子（Heavy Ion）")
        self.chk_he.setToolTip(self.PAR_MODE_TOOLTIP["HE"])

        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.chk_n)
        mode_layout.addWidget(self.chk_p)
        mode_layout.addWidget(self.chk_e)
        mode_layout.addWidget(self.chk_h)
        mode_layout.addWidget(self.chk_he)
        layout.addWidget(grp_mode)

        # ===== NPS / Number of Particles =====
        # NPS controls the total number of particle histories to simulate.
        # Higher values give better statistics but increase runtime.
        grp_nps = QGroupBox("NPS 卡（必填） / NPS Card (Required)")
        grp_nps.setToolTip(
            "NPS 设定模拟的粒子总数，\n"
            "数值越大统计误差越小，但耗时越长。\n"
            "NPS sets the total number of particle histories to simulate.\n"
            "Higher values reduce statistical uncertainty but increase runtime."
        )
        nps_layout = QFormLayout(grp_nps)

        self.nps_edit = QLineEdit()
        self.nps_edit.setPlaceholderText("例: 1000000 或 1.00E+05，留空不生成 / e.g. 1000000 or 1.00E+05 (leave empty to skip)")
        self.nps_edit.setToolTip(
            "每个粒子代表一次独立的随机游走模拟。\n"
            "推荐：10,000（粗略） / 1,000,000（工程级） / 100,000,000+（高精度）\n"
            "支持科学计数法，如 1.00E+05\n"
            "Each history = one independent random walk simulation.\n"
            "Recommended: 10K (rough) / 1M (engineering) / 100M+ (high precision)\n"
            "Supports scientific notation, e.g. 1.00E+05"
        )

        nps_hint = QLabel(
            "<span style='color:gray; font-size:11px;'>"
            "留空 = 不生成 NPS 卡 / Leave empty to omit NPS card</span>"
        )

        nps_layout.addRow("粒子数 NPS / Number of Particles:", self.nps_edit)
        nps_layout.addRow("", nps_hint)
        layout.addWidget(grp_nps)

        # ===== CTME（可选）/ Time Cutoff (Optional) =====
        # CTME sets a wall-clock time limit for the simulation.
        # When the time is reached, MCNP stops gracefully.
        grp_ctme = QGroupBox("CTME 卡（可选） / CTME Card (Optional)")
        grp_ctme.setToolTip(
            "CTME 设定最大运行时间（分钟），\n"
            "到达时间后 MCNP 自动停止。\n"
            "留空表示不设时间限制。\n"
            "CTME sets the maximum runtime in minutes.\n"
            "MCNP will stop automatically when this time is reached.\n"
            "Leave empty for no time limit."
        )
        ctme_layout = QFormLayout(grp_ctme)

        self.ctme_edit = QLineEdit()
        self.ctme_edit.setPlaceholderText("例: 60 或 30.5，留空不生成 / e.g. 60 or 30.5 (leave empty to skip)")
        self.ctme_edit.setToolTip(
            "单位：分钟\n"
            "例如：60 = 1 小时后自动停止\n"
            "留空 = 不设时间限制\n"
            "Unit: minutes\n"
            "Example: 60 = stop after 1 hour\n"
            "Leave empty = no time limit"
        )

        ctme_hint = QLabel(
            "<span style='color:gray; font-size:11px;'>"
            "留空 = 不设时间截断，由 NPS 控制终止 / Leave empty = termination controlled by NPS only</span>"
        )

        ctme_layout.addRow("时间截断 CTME (min) / Time Cutoff:", self.ctme_edit)
        ctme_layout.addRow("", ctme_hint)
        layout.addWidget(grp_ctme)

        # ===== 中子物理模型开关 / Neutron Physics Switches =====
        # NONU switch disables neutron-induced fission.
        # Useful for pure scattering or deep-penetration shielding problems.
        grp_phys = QGroupBox("NONU — 中子裂变开关 / Neutron Fission Switch")
        grp_phys.setToolTip(
            "关闭裂变后中子不会引发裂变，适合纯散射或屏蔽计算。\n"
            "注意：MCNP6.1 的 PHYS:N 卡已无独立的非弹性/相干散射开关。\n"
            "When enabled (checked), neutrons will not cause fission.\n"
            "Useful for pure scattering or shielding calculations.\n"
            "Note: MCNP6.1 PHYS:N no longer has separate inelastic/coherent scattering switches."
        )
        phys_layout = QVBoxLayout(grp_phys)

        self.phys_fis = QCheckBox("关闭裂变（NONU）— 中子不会引发裂变 / Disable fission (NONU)")
        self.phys_fis.setChecked(False)
        self.phys_fis.setToolTip(
            "勾选后输出 NONU 卡，中子不会引发裂变，适合纯散射或屏蔽计算\n"
            "When checked, outputs NONU card — neutrons won't cause fission.\n"
            "For pure scattering or shielding calculations."
        )
        phys_layout.addWidget(self.phys_fis)

        phys_hint = QLabel(
            "<span style='color:gray; font-size:11px;'>"
            "💡 默认不勾选（裂变开启）。仅屏蔽计算时才需要勾选 / "
            "Default: unchecked (fission enabled). Only check for shielding calculations</span>"
        )
        phys_layout.addWidget(phys_hint)
        layout.addWidget(grp_phys)

        # Add stretch to push all content to the top
        # Prevents widgets from being stretched across the full scroll area height.
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def get_data(self) -> BasicSettings:
        """获取当前标签页的数据 / Collect the current form data.

        Reads all widget values and returns them as a BasicSettings model instance.
        This is the primary data output method called by the INP generator.

        Returns:
            BasicSettings: A data object containing all basic settings from the UI.
        """
        return BasicSettings(
            title=self.title_edit.text().strip(),
            mode_n=self.chk_n.isChecked(),
            mode_p=self.chk_p.isChecked(),
            mode_e=self.chk_e.isChecked(),
            mode_h=self.chk_h.isChecked(),
            mode_he=self.chk_he.isChecked(),
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
        self.nps_edit.setText(basic.nps or "")
        self.ctme_edit.setText(basic.ctme or "")
        self.phys_fis.setChecked(not basic.phys_fis)
