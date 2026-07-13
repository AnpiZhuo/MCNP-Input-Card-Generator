"""
源编辑对话框（所有参数可见，CEL 从高级移出，新增额外参数下拉）
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QComboBox, QLineEdit, QLabel, QPushButton,
    QDialogButtonBox, QGroupBox, QWidget
)
from PyQt5.QtCore import Qt

from app.models import SourceData


class SourceEditDialog(QDialog):
    """编辑单个 SDEF 源参数"""

    PAR_OPTIONS = [
        ("1", "1 - 中子（neutron）"),
        ("2", "2 - 光子（photon）"),
        ("3", "3 - 电子（electron）"),
        ("H", "H - 质子（proton）"),
        ("A", "A - α粒子（alpha）"),
        ("S", "S - 裂片/重离子"),
    ]

    def __init__(self, source: SourceData, parent=None):
        super().__init__(parent)
        self.source = source
        self.setWindowTitle(f"编辑源 {source.number}")
        self.setMinimumWidth(620)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        # ── PAR ──
        self.par_combo = QComboBox()
        for val, label in self.PAR_OPTIONS:
            self.par_combo.addItem(label, val)
        for i in range(self.par_combo.count()):
            if self.par_combo.itemData(i) == self.source.par:
                self.par_combo.setCurrentIndex(i)
                break
        form.addRow("PAR (粒子类型):", self.par_combo)

        # ── ERG ──
        self.erg_edit = QLineEdit(self.source.erg)
        self.erg_edit.setPlaceholderText("⚠ 必填 — 请输入能量值 (MeV)")
        self.erg_edit.setStyleSheet(
            "QLineEdit { background-color: #FFF3E0; border: 1px solid #FF6D00; }"
            "QLineEdit:focus { border: 2px solid #E65100; }"
            "QLineEdit::placeholder { color: #E65100; font-weight: bold; }"
        )
        self.erg_edit.setToolTip("能量, MeV — 必填项")
        form.addRow("ERG (能量 MeV):", self.erg_edit)

        # ── POS ──
        pos_layout = QHBoxLayout()
        self.pos_x = QLineEdit(self.source.pos_x)
        self.pos_x.setPlaceholderText("X")
        self.pos_y = QLineEdit(self.source.pos_y)
        self.pos_y.setPlaceholderText("Y")
        self.pos_z = QLineEdit(self.source.pos_z)
        self.pos_z.setPlaceholderText("Z")
        pos_layout.addWidget(QLabel("X:")); pos_layout.addWidget(self.pos_x)
        pos_layout.addWidget(QLabel("Y:")); pos_layout.addWidget(self.pos_y)
        pos_layout.addWidget(QLabel("Z:")); pos_layout.addWidget(self.pos_z)
        form.addRow("POS (位置 cm):", pos_layout)

        # ── DIR ──
        self.dir_edit = QLineEdit(self.source.dir_)
        self.dir_edit.setPlaceholderText("留空=各向同性")
        self.dir_edit.setToolTip(
            "DIR = 粒子发射方向（方向余弦）\n"
            "  1   = 朝 +Z 方向发射（或 VEC 指定的方向）\n"
            "  -1  = 朝 -Z 方向发射\n"
            "  留空 = 各向同性（朝所有方向均匀发射）\n\n"
            "配合 VEC 使用可指定任意方向"
        )
        form.addRow("DIR (方向):", self.dir_edit)

        # ── WGT ──
        self.wgt_edit = QLineEdit(self.source.wgt)
        self.wgt_edit.setPlaceholderText("默认: 1")
        self.wgt_edit.setToolTip(
            "WGT = 粒子权重（Weight）\n"
            "每个模拟粒子代表的真实粒子数量。\n"
            "通常为 1（一个模拟粒子 = 一个真实粒子）。\n"
            "用于方差缩减时，权重高的区域采样更少。"
        )
        form.addRow("WGT (权重):", self.wgt_edit)

        # ── CEL（从高级参数移出，设为常用） ──
        self.cel_edit = QLineEdit(self.source.cel)
        self.cel_edit.setPlaceholderText("留空=不限栅元")
        self.cel_edit.setToolTip(
            "CEL = 源所在栅元（Cell）\n"
            "限制粒子只从指定栅元内部发射。\n"
            "留空 = 整个几何空间都可能发射（配合 POS 定位）。\n"
            "通常配合 POS 使用，不用特殊设置。"
        )
        form.addRow("CEL (栅元号):", self.cel_edit)

        # ── 概率 ──
        self.prob_edit = QLineEdit(self.source.probability)
        self.prob_edit.setPlaceholderText("⚠ 多源时必填 — 概率比例")
        self.prob_edit.setStyleSheet(
            "QLineEdit { background-color: #FFF3E0; border: 1px solid #FF6D00; }"
            "QLineEdit:focus { border: 2px solid #E65100; }"
            "QLineEdit::placeholder { color: #E65100; font-weight: bold; }"
        )
        self.prob_edit.setToolTip(
            "多个源时，该源被抽中的概率比例。\n"
            "例如 2 个源分别填 70 和 30，则各有 70% 和 30% 的粒子来自该源。\n"
            "只有一个源时填 1 或留空即可。\n\n⚠ 多源时概率之和不能为零！"
        )
        form.addRow("概率 %:", self.prob_edit)

        layout.addLayout(form)

        # ── 展开参数区（始终可见） ──
        expand_grp = QGroupBox("TME / VEC / AXS / RAD / EXT")
        expand_layout = QHBoxLayout(expand_grp)
        expand_layout.setSpacing(6)

        expand_layout.addWidget(QLabel("TME:"))
        self.tme_edit = QLineEdit(self.source.tme)
        self.tme_edit.setPlaceholderText("时间")
        self.tme_edit.setMaximumWidth(80)
        self.tme_edit.setToolTip(
            "TME = 发射时间（Time）\n"
            "单位: 10⁻⁸ 秒（shakes）\n"
            "用于瞬态问题，定义粒子在何时发射。\n"
            "一般静态问题留空或填 0。"
        )
        expand_layout.addWidget(self.tme_edit)

        expand_layout.addWidget(QLabel("VEC:"))
        self.vec_edit = QLineEdit(self.source.vec)
        self.vec_edit.setPlaceholderText("x y z")
        self.vec_edit.setMaximumWidth(140)
        self.vec_edit.setToolTip(
            "VEC = 方向向量（Vector）\n"
            "指定粒子的发射方向轴，格式: x y z\n"
            "例如 0 0 1 表示沿 Z 轴方向，配合 DIR=1 使用。\n"
            "DIR 决定朝正还是朝负，VEC 决定朝哪个轴。"
        )
        expand_layout.addWidget(self.vec_edit)

        expand_layout.addWidget(QLabel("AXS:"))
        self.axs_edit = QLineEdit(self.source.axs)
        self.axs_edit.setPlaceholderText("轴")
        self.axs_edit.setMaximumWidth(80)
        self.axs_edit.setToolTip(
            "AXS = 轴对称源的轴（Axis）\n"
            "定义体源或面源的对称轴方向。\n"
            "例如 0 0 1 表示以 Z 轴为对称轴。\n"
            "配合 RAD（径向范围）和 EXT（轴向范围）定义源的形状。"
        )
        expand_layout.addWidget(self.axs_edit)

        expand_layout.addWidget(QLabel("RAD:"))
        self.rad_edit = QLineEdit(self.source.rad)
        self.rad_edit.setPlaceholderText("径向")
        self.rad_edit.setMaximumWidth(70)
        self.rad_edit.setToolTip(
            "RAD = 径向范围（Radial）\n"
            "体源/面源从对称轴向外延伸的距离。\n"
            "例如 RAD=2 表示源在半径 2cm 的圆柱范围内均匀分布。\n"
            "需要配合 AXS 使用。"
        )
        expand_layout.addWidget(self.rad_edit)

        expand_layout.addWidget(QLabel("EXT:"))
        self.ext_edit = QLineEdit(self.source.ext)
        self.ext_edit.setPlaceholderText("轴向")
        self.ext_edit.setMaximumWidth(70)
        self.ext_edit.setToolTip(
            "EXT = 轴向范围（Extent）\n"
            "体源/面源沿对称轴方向的延伸距离。\n"
            "例如 EXT=5 表示源在轴向上延伸 5cm。\n"
            "需要配合 AXS 使用。"
        )
        expand_layout.addWidget(self.ext_edit)

        expand_layout.addStretch()
        layout.addWidget(expand_grp)

        # ── 额外参数折叠区（SUR / NRM / TR / CCC / ARA / RATE）──
        self.btn_extra = QPushButton("▼ 额外参数")
        self.btn_extra.setToolTip("点击展开/收起 SUR, NRM, TR, CCC, ARA, RATE")
        self.btn_extra.setCheckable(True)
        self.btn_extra.clicked.connect(self._toggle_extra)

        self.extra_widget = QWidget()
        self.extra_widget.setVisible(False)
        extra_inner = QHBoxLayout(self.extra_widget)
        extra_inner.setSpacing(6)

        extra_inner.addWidget(QLabel("SUR:"))
        self.sur_edit = QLineEdit(getattr(self.source, "sur", ""))
        self.sur_edit.setPlaceholderText("曲面源")
        self.sur_edit.setMaximumWidth(80)
        extra_inner.addWidget(self.sur_edit)

        extra_inner.addWidget(QLabel("NRM:"))
        self.nrm_edit = QLineEdit(getattr(self.source, "nrm", ""))
        self.nrm_edit.setPlaceholderText("曲面法线")
        self.nrm_edit.setMaximumWidth(80)
        extra_inner.addWidget(self.nrm_edit)

        extra_inner.addWidget(QLabel("TR:"))
        self.tr_edit = QLineEdit(getattr(self.source, "tr", ""))
        self.tr_edit.setPlaceholderText("变换")
        self.tr_edit.setMaximumWidth(80)
        extra_inner.addWidget(self.tr_edit)

        extra_inner.addWidget(QLabel("CCC:"))
        self.ccc_edit = QLineEdit(getattr(self.source, "ccc", ""))
        self.ccc_edit.setPlaceholderText("Cookie-cutter")
        self.ccc_edit.setMaximumWidth(80)
        extra_inner.addWidget(self.ccc_edit)

        extra_inner.addWidget(QLabel("ARA:"))
        self.ara_edit = QLineEdit(getattr(self.source, "ara", ""))
        self.ara_edit.setPlaceholderText("点探测器归一化")
        self.ara_edit.setMaximumWidth(80)
        extra_inner.addWidget(self.ara_edit)

        extra_inner.addWidget(QLabel("RATE:"))
        self.rate_edit = QLineEdit(getattr(self.source, "rate", ""))
        self.rate_edit.setPlaceholderText("源强度")
        self.rate_edit.setMaximumWidth(80)
        extra_inner.addWidget(self.rate_edit)

        extra_inner.addStretch()

        layout.addWidget(self.btn_extra)
        layout.addWidget(self.extra_widget)

        # ── 按钮 ──
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ---------- 额外参数折叠 ----------

    def _toggle_extra(self):
        visible = self.btn_extra.isChecked()
        self.extra_widget.setVisible(visible)
        self.btn_extra.setText("▲ 收起额外参数" if visible else "▼ 额外参数")

    # ---------- 校验 ----------

    def _on_accept(self):
        if not self.erg_edit.text().strip():
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "校验", "能量（ERG）不能为空！")
            return
        self.accept()

    def get_data(self) -> SourceData:
        return SourceData(
            number=self.source.number,
            par=self.par_combo.currentData(),
            erg=self.erg_edit.text().strip(),
            pos_x=self.pos_x.text().strip(),
            pos_y=self.pos_y.text().strip(),
            pos_z=self.pos_z.text().strip(),
            dir_=self.dir_edit.text().strip(),
            wgt=self.wgt_edit.text().strip(),
            probability=self.prob_edit.text().strip(),
            cel=self.cel_edit.text().strip(),
            tme=self.tme_edit.text().strip(),
            vec=self.vec_edit.text().strip(),
            axs=self.axs_edit.text().strip(),
            rad=self.rad_edit.text().strip(),
            ext=self.ext_edit.text().strip(),
            sur=self.sur_edit.text().strip(),
            nrm=self.nrm_edit.text().strip(),
            tr=self.tr_edit.text().strip(),
            ccc=self.ccc_edit.text().strip(),
            ara=self.ara_edit.text().strip(),
            rate=self.rate_edit.text().strip(),
        )
