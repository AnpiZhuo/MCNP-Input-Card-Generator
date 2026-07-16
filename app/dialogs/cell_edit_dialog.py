"""
栅元编辑对话框（含 IMP:P、IMP:E、VOL 高级参数 + 折叠更多参数）
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QLineEdit, QPushButton, QLabel,
    QDialogButtonBox, QWidget
)
from PyQt5.QtCore import Qt

from app.models import CellData


class CellEditDialog(QDialog):
    """编辑栅元参数的弹出窗口"""

    def __init__(self, cell: CellData, available_materials: list[str], parent=None):
        super().__init__(parent)
        self.cell = cell
        self.available_materials = available_materials
        self.setWindowTitle(f"编辑栅元 {cell.number}")
        self.setMinimumWidth(550)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # 栅元号
        self.cell_number_combo = QComboBox()
        self.cell_number_combo.setEditable(True)
        self.cell_number_combo.setToolTip("栅元号，1-99999。下拉为推荐编号，也可手动输入。")
        for n in range(1, 21):
            self.cell_number_combo.addItem(str(n))
        self.cell_number_combo.setCurrentText(str(self.cell.number))
        form.addRow("栅元号:", self.cell_number_combo)

        # 材料号（下拉项含注释，如 "M1 (钢铁)"）
        self.material_combo = QComboBox()
        self.material_combo.setToolTip("选择此栅元使用的材料。0 (void) = 真空。")
        for m in self.available_materials:
            self.material_combo.addItem(m)
        # 用去除 M 前缀后的数字匹配（兼容 "4" 和 "M4" 两种写法）
        cell_mat_token = self.cell.material.split()[0] if " " in self.cell.material else self.cell.material
        cell_num = cell_mat_token.lstrip('M')  # "M4" → "4",  "4" → "4"
        matched = False
        for i in range(self.material_combo.count()):
            item_raw = self.material_combo.itemText(i)
            item_token = item_raw.split()[0] if " " in item_raw else item_raw
            if item_token.lstrip('M') == cell_num:  # 都去掉 M 再比
                self.material_combo.setCurrentIndex(i)
                matched = True
                break
        if not matched:
            self.material_combo.setCurrentIndex(self.material_combo.count() - 1)
        form.addRow("材料号:", self.material_combo)

        # 密度
        self.density_edit = QLineEdit(self.cell.density)
        self.density_edit.setPlaceholderText("例: -11.34（void 留空）")
        self.density_edit.setToolTip("负值 = g/cm³，正值 = atoms/b-cm。void 留空。")
        form.addRow("密度:", self.density_edit)

        # 曲面表达式
        self.surface_edit = QLineEdit(self.cell.surface_expr)
        self.surface_edit.setPlaceholderText("例: -10 20 -30 40 -50 60")
        self.surface_edit.setToolTip(
            "带符号曲面号，空格=交(AND)，:=并(OR)，#=补(NOT)\n"
            "负号 (-) = 曲面内侧（inside）  |  正号 (+) = 曲面外侧（outside）"
        )
        self.surface_edit.textChanged.connect(self._validate_surface)
        form.addRow("曲面表达式:", self.surface_edit)

        self.surface_hint = QLabel(
            "<span style='color:gray; font-size:11px;'>"
            "带符号曲面号，空格分隔。"
            "<b>负号=内侧</b>，<b>正号=外侧</b>。"
            "空格=AND，冒号:=OR，井号#=NOT</span>"
        )
        form.addRow("", self.surface_hint)

        # IMP:N
        self.imp_n_edit = QLineEdit(self.cell.imp_n)
        self.imp_n_edit.setPlaceholderText("留空则不生成 IMP:N")
        self.imp_n_edit.setToolTip(
            "IMP:N = 中子重要性（Importance）\n"
            "控制中子在这个栅元里的行为：\n"
            "  1  = 正常输运（最常用）\n"
            "  0  = 中子到此栅元即终止（外部世界用）\n"
            "  0~1 之间 = 降低权重，用于方差缩减"
        )
        form.addRow("IMP:N:", self.imp_n_edit)

        # IMP:P（不再折叠）
        self.imp_p_edit = QLineEdit(self.cell.imp_p)
        self.imp_p_edit.setPlaceholderText("留空则不生成（无光子输运）")
        self.imp_p_edit.setToolTip("光子重要性（IMP:P），留空表示不需要光子输运")
        form.addRow("IMP:P:", self.imp_p_edit)

        # IMP:E
        self.imp_e_edit = QLineEdit(self.cell.imp_e)
        self.imp_e_edit.setPlaceholderText("留空则不生成（无电子输运）")
        self.imp_e_edit.setToolTip("电子重要性（IMP:E），留空表示不需要电子输运")
        form.addRow("IMP:E:", self.imp_e_edit)

        # VOL
        self.vol_edit = QLineEdit(self.cell.vol)
        self.vol_edit.setPlaceholderText("留空让 MCNP 自动计算")
        self.vol_edit.setToolTip(
            "VOL = 栅元体积（cm³）\n"
            "MCNP 默认会根据几何自动计算体积，但复杂几何可能算不准。\n"
            "手动指定可以提高通量计数（F4）的精度。\n"
            "球体体积公式: (4/3)πR³"
        )
        form.addRow("VOL:", self.vol_edit)

        vol_hint = QLabel(
            "<span style='color:gray; font-size:11px;'>"
            "💡 复杂几何或计数需要高精度时建议指定 VOL</span>"
        )
        form.addRow("", vol_hint)

        # ── 折叠更多参数 ──
        self.btn_extra = QPushButton("▼ 更多参数（PWT·EXT·FCL·U·FILL·LAT·TRCL）")
        self.btn_extra.setToolTip("点击展开/收起不常用栅元参数")
        self.btn_extra.setStyleSheet("QPushButton { text-align: left; padding: 4px 8px; }")
        self.btn_extra.setCheckable(True)
        self.btn_extra.clicked.connect(self._toggle_extra)

        self.extra_widget = QWidget()
        self.extra_widget.setVisible(False)
        extra_form = QFormLayout(self.extra_widget)
        extra_form.setContentsMargins(0, 4, 0, 4)
        extra_form.setSpacing(6)

        self.pwt_edit = QLineEdit(self.cell.pwt)
        self.pwt_edit.setPlaceholderText("留空不生成")
        self.pwt_edit.setToolTip("PWT = 光子产生权重\n"
            "控制中子与物质相互作用时产生光子的权重。\n"
            "默认 = 1。设为 0 可关闭光子产生。")
        extra_form.addRow("PWT:", self.pwt_edit)

        self.ext_edit = QLineEdit(self.cell.ext)
        self.ext_edit.setPlaceholderText("留空不生成")
        self.ext_edit.setToolTip("EXT = 指数变换（Exponential Transform）\n"
            "方差缩减技术，引导粒子朝特定方向输运。\n"
            "正值=朝曲面方向，负值=远离曲面。")
        extra_form.addRow("EXT:", self.ext_edit)

        self.fcl_edit = QLineEdit(self.cell.fcl)
        self.fcl_edit.setPlaceholderText("留空不生成")
        self.fcl_edit.setToolTip("FCL = 强制碰撞（Forced Collision）\n"
            "在光学薄的栅元中强制粒子发生碰撞。\n"
            "0=关闭，1=对所有碰撞打开。")
        extra_form.addRow("FCL:", self.fcl_edit)

        self.u_edit = QLineEdit(self.cell.u)
        self.u_edit.setPlaceholderText("留空不生成")
        self.u_edit.setToolTip("U = 宇宙号（Universe Number）\n"
            "用于嵌套栅元结构（结合 FILL/LAT 使用）。\n"
            "相同 U 编号的栅元属于同一个宇宙。")
        extra_form.addRow("U:", self.u_edit)

        self.fill_edit = QLineEdit(self.cell.fill)
        self.fill_edit.setPlaceholderText("留空不生成")
        self.fill_edit.setToolTip("FILL = 填充的宇宙号\n"
            "指定此栅元内填充哪个宇宙（U 编号）的内容。\n"
            "用于重复结构和格阵填充。")
        extra_form.addRow("FILL:", self.fill_edit)

        self.lat_edit = QLineEdit(self.cell.lat)
        self.lat_edit.setPlaceholderText("留空不生成")
        self.lat_edit.setToolTip("LAT = 格阵类型\n"
            "1 = 六面体格阵（Hexahedral）\n"
            "2 = 六棱柱格阵（Hexagonal Prism）")
        extra_form.addRow("LAT:", self.lat_edit)

        self.trcl_edit = QLineEdit(self.cell.trcl)
        self.trcl_edit.setPlaceholderText("留空不生成")
        self.trcl_edit.setToolTip("TRCL = 坐标变换编号\n"
            "引用 TRn 卡定义的坐标变换。\n"
            "格式: TRCL=n 或 TRCL=n x y z")
        extra_form.addRow("TRCL:", self.trcl_edit)

        layout.addLayout(form)
        layout.addWidget(self.btn_extra)
        layout.addWidget(self.extra_widget)

        # 注释
        self.comment_edit = QLineEdit(self.cell.comment)
        self.comment_edit.setPlaceholderText("可选的注释文字，如「铁球壳、水反射层」")
        self.comment_edit.setToolTip("注释不影响计算，仅用于标识")
        layout.addWidget(QLabel("注释:"))
        layout.addWidget(self.comment_edit)

        # 按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _toggle_extra(self):
        visible = self.btn_extra.isChecked()
        self.extra_widget.setVisible(visible)
        self.btn_extra.setText(
            "▲ 收起更多参数" if visible
            else "▼ 更多参数（PWT·EXT·FCL·U·FILL·LAT·TRCL）"
        )

    def _validate_surface(self):
        text = self.surface_edit.text().strip()
        if text:
            self.surface_hint.setText(
                "<span style='color:green; font-size:11px;'>✓ 已填写</span>"
            )
        else:
            self.surface_hint.setText(
                "<span style='color:orange; font-size:11px;'>⚠ 必填</span>"
            )

    def _on_accept(self):
        if not self.surface_edit.text().strip():
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "校验", "曲面表达式不能为空！")
            return
        # 检查栅元号是否为有效整数
        try:
            val = int(self.cell_number_combo.currentText())
            if val < 1 or val > 99999:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, "校验", "栅元号必须在 1~99999 之间")
                return
        except ValueError:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "校验", "栅元号必须为数字")
            return
        self.accept()

    def get_data(self) -> CellData:
        """返回编辑后的栅元数据"""
        mat_text = self.material_combo.currentText()
        if " " in mat_text:
            mat_text = mat_text.split()[0]
        return CellData(
            number=int(self.cell_number_combo.currentText()),
            material=mat_text,
            density=self.density_edit.text().strip(),
            surface_expr=self.surface_edit.text().strip(),
            imp_n=self.imp_n_edit.text().strip(),
            imp_p=self.imp_p_edit.text().strip(),
            imp_e=self.imp_e_edit.text().strip(),
            vol=self.vol_edit.text().strip(),
            pwt=self.pwt_edit.text().strip(),
            ext=self.ext_edit.text().strip(),
            fcl=self.fcl_edit.text().strip(),
            u=self.u_edit.text().strip(),
            fill=self.fill_edit.text().strip(),
            lat=self.lat_edit.text().strip(),
            trcl=self.trcl_edit.text().strip(),
            comment=self.comment_edit.text().strip(),
        )
