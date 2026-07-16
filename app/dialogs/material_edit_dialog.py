"""
材料编辑对话框：手动 ZAID 模式"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QPushButton,
    QHeaderView, QLabel, QLineEdit, QDialogButtonBox,
    QComboBox, QMessageBox, QPlainTextEdit, QStackedWidget, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from app.models import MaterialData, MaterialRow
from app.xsdir_db import DB as xsdir_db, Z_TO_SYMBOL, format_zzaaam, parse_zzaaam
from app.material_presets import get_all_presets, PRESET_CATEGORIES


class ElementCombo(QComboBox):
    """带元素列表的下拉框，可选择或输入元素"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setToolTip("输入元素符号（H、U、Fe）或原子序数（1、26、92），不区分大小写")

    def set_element_list(self, elements: list[tuple[int, str]]):
        self.clear()
        self.addItem("— 请选择元素 —", None)
        for z, sym in elements:
            self.addItem(f"{sym} (Z={z})", z)

    def selected_z(self) -> int | None:
        data = self.currentData()
        if data is not None and isinstance(data, int):
            return data
        text = self.currentText().strip()
        if not text:
            return None
        import re
        m = re.match(r'.*?(\d+)', text)
        if m:
            z = int(m.group(1))
            if 1 <= z <= 100:
                return z
        text_lower = text.lower()
        for z, sym in Z_TO_SYMBOL.items():
            if sym.lower() == text_lower:
                return z
        return None


class MaterialEditDialog(QDialog):
    """编辑材料的 ZAID 和份额 — 支持手动/化学式两种模式"""

    def __init__(self, material: MaterialData, parent=None):
        super().__init__(parent)
        self.material = material
        self.setWindowTitle(f"编辑材料 M{material.number}")
        self.setMinimumSize(700, 480)
        self.available_elements = xsdir_db.get_element_list()
        self._formula_rows: list[MaterialRow] = []  # 化学式解析结果缓存
        self._suppress_validate = False
        self.init_ui()

    # ---------- UI ----------

    def init_ui(self):
        layout = QVBoxLayout(self)

        # ===== 预设材料 =====
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("预设材料:"))
        self.preset_combo = QComboBox()
        self.preset_combo.setToolTip(
            "从预设库快速填充常用材料（水、空气、混凝土、金属、合金等）\n"
            "选择后自动填充化学式或手动输入区域"
        )
        self.preset_combo.addItem("— 从预设库选择 —", None)
        for cat_name, items in PRESET_CATEGORIES:
            # 类别标题（不可选）
            self.preset_combo.insertSeparator(self.preset_combo.count())
            for key, name, formula, desc in items:
                self.preset_combo.addItem(f"  {name}  — {desc}", key)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        self.preset_combo.setInsertPolicy(QComboBox.NoInsert)
        # 加宽下拉列表以显示完整描述
        self.preset_combo.view().setMinimumWidth(500)
        preset_layout.addWidget(self.preset_combo, 1)
        layout.addLayout(preset_layout)

        # 注释
        self.comment_edit = QLineEdit(self.material.comment)
        self.comment_edit.setPlaceholderText("材料名称/注释，如「铅」「水」「不锈钢」")
        self.comment_edit.setToolTip("材料的名称或描述")
        layout.addWidget(QLabel("注释:"))
        layout.addWidget(self.comment_edit)

        # 高级选项（nlib= / gas= / plib= 等）
        adv_row = QHBoxLayout()
        adv_row.addWidget(QLabel("高级选项:"))
        opts = getattr(self.material, 'options', '') or ''
        self.options_edit = QLineEdit(opts)
        self.options_edit.setPlaceholderText("例: nlib=.66c")
        self.options_edit.setToolTip(
            "MCNP 材料卡附加参数，空格分隔：\n"
            "  nlib=.66c — 指定中子截面库\n"
            "  gas=1 — 气体材料  |  plib=02p — 光子库\n"
            "留空则不生成任何附加参数"
        )
        adv_row.addWidget(self.options_edit, 1)
        layout.addLayout(adv_row)

        # 热中子 MT 卡
        mt_row = QHBoxLayout()
        mt_row.addWidget(QLabel("热中子 S(a,b) 处理 (MT 卡):"))
        self.mt_card_edit = QLineEdit(getattr(self.material, 'mt_card', ''))
        self.mt_card_edit.setPlaceholderText("例: lwtr.10t  hwtr.10t 石墨: grph.10t")
        self.mt_card_edit.setToolTip(
            "MCNP MT 卡，引用热中子 S(a,b) 散射截面库。\n"
            "常用: lwtr.10t (轻水), hwtr.10t (重水), grph.10t (石墨), be.10t (铍)\n"
            "多个用空格分隔。留空则不生成 MT 卡。"
        )
        mt_row.addWidget(self.mt_card_edit, 1)
        layout.addLayout(mt_row)

        # 密度提示
        layout.addWidget(QLabel(
            "<span style='color:#5f6368; font-size:12px;'>"
            "💡 密度在栅元卡中设置（MCNP 材料卡不含密度）</span>"
        ))

        # ===== 模式切换 =====
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("输入模式:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("🔢 手动输入 ZAID", "manual")
        self.mode_combo.addItem("🧪 化学式输入（自动查 NIST 同位素）", "formula")
        self.mode_combo.setToolTip(
            "手动模式：手动选择元素和质量数，逐行输入 ZAID 份额。\n"
            "化学式模式：直接输入化学式，程序自动查 NIST 同位素组成。"
        )
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # ===== 堆叠面板：手动/化学式 =====
        self.stack = QStackedWidget()

        # 页面 0：手动 ZAID 表格
        page_manual = QWidget()
        manual_layout = QVBoxLayout(page_manual)
        manual_layout.setContentsMargins(0, 0, 0, 0)

        label_manual = QLabel("核素组成（选择元素 → 填质量数 → 填份额）：")
        label_manual.setToolTip(
            "1. 在「元素」列选择或输入元素符号（如 H、Fe、26）\n"
            "2. 在「质量数」列直接输入整数（如 1、56、235）\n"
            "3. 在「份额」列填写质量分数（负值）或原子分数（正值）"
        )
        manual_layout.addWidget(label_manual)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["元素", "质量数", "份额"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.cellChanged.connect(self._on_cell_changed)
        manual_layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.btn_add_row = QPushButton("+ 添加行")
        self.btn_add_row.setToolTip("添加一行核素")
        self.btn_add_row.setProperty("cssClass", "btnAdd")
        self.btn_add_row.clicked.connect(self._add_row)
        self.btn_del_row = QPushButton("× 删除选中行")
        self.btn_del_row.setToolTip("删除选中的行")
        self.btn_del_row.setProperty("cssClass", "btnDelete")
        self.btn_del_row.clicked.connect(self._delete_row)
        btn_layout.addWidget(self.btn_add_row)
        btn_layout.addWidget(self.btn_del_row)
        btn_layout.addStretch()
        manual_layout.addLayout(btn_layout)

        manual_hint = QLabel(
            "<span style='color:gray; font-size:11px;'>"
            "💡 常用: H-1 (氢), O-16 (氧), Fe-56 (铁), Pb-208 (铅), U-235 (铀)。"
            "份额用负值表示质量分数，如 -0.05 = 5%</span>"
        )
        manual_layout.addWidget(manual_hint)

        self.stack.addWidget(page_manual)  # index 0

        # 页面 1：化学式输入
        page_formula = QWidget()
        formula_layout = QVBoxLayout(page_formula)
        formula_layout.setContentsMargins(0, 0, 0, 0)

        formula_label = QLabel("输入化学式（格式: 化学式: 比例；多个组分用逗号或换行分隔）：")
        formula_label.setToolTip(
            "支持常见化学式：\n"
            "  H2O: 1\n  Pb: 1\n  N2: 0.8, O2: 0.2\n  LiF: 1\n"
            "  H: 0.01, O: 0.529, Si: 0.337, Ca: 0.044\n\n"
            "⚠ 多个组分在同一行必须用逗号分隔，空格分隔无效"
        )
        formula_layout.addWidget(formula_label)

        self.formula_edit = QPlainTextEdit()
        self.formula_edit.setPlaceholderText(
            "每行一个或逗号分隔多个组分，例:\n"
            "H2O: 1\n"
            "N2: 0.8, O2: 0.2\n"
            "H: 0.01, O: 0.529, Si: 0.337"
        )
        self.formula_edit.setToolTip(
            "格式: 化学式: 比例\n"
            "⚠ 同一行多个组分必须用英文逗号 + 空格分隔（如 N2: 0.8, O2: 0.2），不能用空格分隔\n"
            "比例不需要归一化"
        )
        self.formula_edit.setMaximumHeight(120)
        formula_layout.addWidget(self.formula_edit)

        # 解析按钮
        parse_btn_layout = QHBoxLayout()
        self.btn_parse = QPushButton("🔬 解析化学式")
        self.btn_parse.setToolTip("使用 pymcnp M_0.from_formula 解析化学式并查 NIST 同位素组成")
        self.btn_parse.setProperty("cssClass", "btnPrimary")
        self.btn_parse.clicked.connect(self._parse_formula)
        parse_btn_layout.addWidget(self.btn_parse)
        parse_btn_layout.addStretch()
        formula_layout.addLayout(parse_btn_layout)

        # 解析结果预览表（只读）
        self.formula_table = QTableWidget(0, 3)
        self.formula_table.setHorizontalHeaderLabels(["ZAID", "元素", "质量分数"])
        self.formula_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.formula_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.formula_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.formula_table.setEditTriggers(QTableWidget.NoEditTriggers)
        formula_layout.addWidget(self.formula_table)

        self.formula_status = QLabel("")
        formula_layout.addWidget(self.formula_status)

        formula_hint = QLabel(
            "<span style='color:gray; font-size:11px;'>"
            "💡 化学式模式使用 pymcnp 内置 NIST 同位素数据库自动查找天然丰度。"
            "适合常见材料（水、空气、混凝土、金属等）。</span>"
        )
        formula_layout.addWidget(formula_hint)

        self.stack.addWidget(page_formula)  # index 1

        layout.addWidget(self.stack, 1)

        # 按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        # 初始化数据
        self._init_data()

    def _init_data(self):
        """加载现有材料数据"""
        # 填充手动表格
        row_count = max(len(self.material.rows), 1)
        self.table.setRowCount(row_count)
        for i, row in enumerate(self.material.rows):
            self._setup_row_widgets(i, row)
        if len(self.material.rows) == 0:
            self._setup_row_widgets(0, None)

        # 如有保存的化学式，回填
        if hasattr(self.material, 'formula') and self.material.formula:
            self.formula_edit.setPlainText(self.material.formula)
            self.mode_combo.setCurrentIndex(1)  # 化学式模式

    # ---------- 模式切换 ----------

    def _populate_manual_table(self, rows: list[MaterialRow]):
        """将 ZAID 列表填充到手动模式表格。"""
        self.table.setRowCount(max(len(rows), 1))
        for i, row in enumerate(rows):
            self._setup_row_widgets(i, row)
        if not rows:
            self._setup_row_widgets(0, None)

    def _on_mode_changed(self, idx: int):
        mode = self.mode_combo.currentData()
        if mode == "formula":
            self.stack.setCurrentIndex(1)
        else:
            # 切到手动模式时，把公式解析结果带到手动表格
            if self._formula_rows:
                self._populate_manual_table(self._formula_rows)
            self.stack.setCurrentIndex(0)

    # ---------- 预设材料 ----------

    def _on_preset_changed(self, idx: int):
        """预设材料选择 → 自动填充化学式并解析"""
        key = self.preset_combo.currentData()
        if not key:
            return

        from app.material_presets import get_preset_by_key
        preset = get_preset_by_key(key)
        if not preset:
            return

        # 填充注释（总是更新为当前预设的名称）
        self.comment_edit.setText(preset["name"])

        # 切换到化学式模式
        self.mode_combo.setCurrentIndex(1)

        # 填充化学式
        self.formula_edit.setPlainText(preset["formula"])

        # 自动解析
        self._parse_formula()

    # ---------- 化学式解析 ----------

    def _parse_formula(self):
        """使用 pymcnp M_0.from_formula 解析化学式"""
        text = self.formula_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请先输入化学式")
            return

        # 解析用户输入
        formulas = {}
        line_count = 0
        for line in text.split("\n"):
            line = line.strip()
            line_count += 1
            if not line or line.startswith("#"):
                continue
            # 逗号分隔多个组分
            parts = [p.strip() for p in line.split(",")]
            for part in parts:
                if not part:
                    continue
                # 检测：含多个冒号 → 格式错误
                colon_count = part.count(":")
                if colon_count > 1:
                    self.formula_status.setText(
                        f"<span style='color:#c62828;'>⚠ 第 {line_count} 行格式错误: "
                        f"'{part}' 含多个冒号</span>"
                    )
                    return
                if colon_count == 1:
                    formula, ratio = part.split(":", 1)
                else:
                    # 无冒号：空格分隔 — 但可能有歧义（如 "N2 0.8 O2 0.3"），提示用逗号
                    tokens = part.split()
                    if len(tokens) >= 3:
                        self.formula_status.setText(
                            f"<span style='color:#c62828;'>⚠ 第 {line_count} 行格式错误: "
                            f"多个组分必须用逗号分隔，不能用空格。\n"
                            f"当前输入: '{part}'</span>"
                        )
                        return
                    elif len(tokens) == 2:
                        formula, ratio = tokens[0], tokens[1]
                    else:
                        formula = tokens[0]
                        ratio = "1"

                formula = formula.strip()
                ratio = ratio.strip()

                # 合法性检测
                if not formula:
                    self.formula_status.setText(
                        f"<span style='color:#c62828;'>⚠ 第 {line_count} 行: 化学式为空</span>"
                    )
                    return
                if formula in formulas:
                    self.formula_status.setText(
                        f"<span style='color:#c62828;'>⚠ 化学式 '{formula}' 重复定义</span>"
                    )
                    return
                try:
                    formulas[formula] = float(ratio)
                except ValueError:
                    self.formula_status.setText(
                        f"<span style='color:#c62828;'>⚠ 第 {line_count} 行: "
                        f"'{ratio}' 不是有效的数字（化学式 '{formula}'）</span>"
                    )
                    return

        if not formulas:
            QMessageBox.warning(self, "提示", "未能解析出有效的化学式")
            return

        try:
            import pymcnp

            # 逐个组分独立展开，避免 pymcnp 丢弃低含量组分
            # from_formula 在混合多元素时会静默丢弃质量分数低(~1.2%)的元素，
            # 因此先对每个组分单独调用 from_formula，再按用户比例合并。
            all_rows: list[tuple[str, float]] = []
            for elem_symbol, user_ratio in formulas.items():
                # cutoff=1e-9 防止 pymcnp 丢弃低丰度同位素（默认 cutoff=0.01）
                sub = pymcnp.inp.M_0.from_formula({elem_symbol: 1}, cutoff=1e-9)
                sub_str = str(sub)
                # 提取 ZAID + 丰度（跳过 "m{n}" 和续行符）
                cleaned = sub_str.replace("&", " ").replace("\n", " ")
                sub_parts = cleaned.split()
                if len(sub_parts) < 3:
                    continue  # 空组分
                for k in range(1, len(sub_parts), 2):
                    zaid = sub_parts[k]
                    try:
                        # 该组分内同位素丰度（天然百分比）
                        iso_frac = float(sub_parts[k + 1])
                        # 按用户设定的质量比缩放
                        all_rows.append((zaid, iso_frac * user_ratio))
                    except (ValueError, IndexError):
                        continue

            if not all_rows:
                QMessageBox.warning(self, "解析失败", "pymcnp 返回空材料")
                return

            # 归一化到总和 = 1（pymcnp 用负数表示质量分数）
            total = sum(abs(f) for _, f in all_rows)
            if abs(total - 1.0) > 1e-9 and total > 0:
                normalized = [(zaid, f / total) for zaid, f in all_rows]
            else:
                normalized = all_rows

            # 填充预览表
            self.formula_table.setRowCount(len(normalized))
            for j, (zaid, frac) in enumerate(normalized):
                self.formula_table.setItem(j, 0, QTableWidgetItem(zaid))
                num = zaid
                parsed = parse_zzaaam(num) if num.isdigit() else None
                elem_name = f"{Z_TO_SYMBOL.get(parsed[0], '?')}-{parsed[1]}" if parsed else "?"
                self.formula_table.setItem(j, 1, QTableWidgetItem(elem_name))
                self.formula_table.setItem(j, 2, QTableWidgetItem(f"{frac:.6f}"))

            # 缓存结果用于保存
            self._formula_rows = [
                MaterialRow(zaid=zaid, fraction=f"{frac:.6f}")
                for zaid, frac in normalized
            ]

            self.formula_status.setText(
                f"<span style='color:#2e7d32;'>✓ 解析成功，共 {len(normalized)} 个核素</span>"
            )

        except Exception as e:
            self.formula_status.setText(
                f"<span style='color:#c62828;'>⚠ 解析失败: {e}</span>"
            )

    # ---------- 手动模式：表格操作 ----------

    def _setup_row_widgets(self, row: int, row_data: MaterialRow | None):
        elem_combo = ElementCombo()
        elem_combo.set_element_list(self.available_elements)
        elem_combo.currentTextChanged.connect(
            lambda text, r=row: self._validate_row(r)
        )
        self.table.setCellWidget(row, 0, elem_combo)

        mass_edit = QLineEdit()
        mass_edit.setPlaceholderText("例: 16、56、235、238.80c")
        mass_edit.setToolTip("质量数 A（整数），可选加库后缀如 238.80c、235.70u")
        mass_edit.textChanged.connect(lambda text, r=row: self._validate_row(r))
        self.table.setCellWidget(row, 1, mass_edit)

        if row_data and row_data.zaid:
            num = row_data.zaid.split(".")[0]
            parsed = parse_zzaaam(num)
            if parsed:
                z, a = parsed
                # 设置元素
                elem_combo.blockSignals(True)
                for i in range(elem_combo.count()):
                    if elem_combo.itemData(i) == z:
                        elem_combo.setCurrentIndex(i)
                        break
                sym = Z_TO_SYMBOL.get(z, "")
                if sym:
                    elem_combo.setCurrentText(f"{sym} (Z={z})")
                elem_combo.blockSignals(False)
                # 还原质量数 + 库后缀到输入框
                if "." in row_data.zaid:
                    _, lib = row_data.zaid.split(".", 1)
                    mass_edit.setText(f"{a}.{lib}")
                else:
                    mass_edit.setText(str(a))

        frac = row_data.fraction if row_data else ""
        item = QTableWidgetItem(frac)
        item.setToolTip("份额（小数）：负值=质量分数，正值=原子分数")
        self.table.setItem(row, 2, item)

    def _get_row_data(self, row: int) -> tuple[str, str]:
        elem_combo = self.table.cellWidget(row, 0)
        mass_edit = self.table.cellWidget(row, 1)
        z = elem_combo.selected_z() if elem_combo else None
        a_str = mass_edit.text().strip() if mass_edit else ""
        frac_item = self.table.item(row, 2)
        frac = frac_item.text().strip() if frac_item else ""
        if z is not None:
            # 解析质量数 + 可选库后缀: "238" → a=238, lib=""; "238.80c" → a=238, lib=".80c"
            import re
            m = re.match(r'^(\d{1,3})(\..*)?$', a_str)
            if m:
                a = int(m.group(1))
                lib = m.group(2) or ""
                if 1 <= a <= 999:
                    return (format_zzaaam(z, a) + lib, frac)
            # 未输入质量数 → 默认 000（天然元素）
            if not a_str:
                return (format_zzaaam(z, 0), frac)
        return ("", frac)

    def _set_row_color(self, row: int, bg: str, fg: str = "#ffffff"):
        elem_combo = self.table.cellWidget(row, 0)
        if elem_combo:
            elem_combo.setStyleSheet(f"""
                QComboBox {{ background-color: {bg}; color: {fg}; border-radius: 4px; padding: 2px 4px; }}
                QComboBox::drop-down {{ border: none; }}
                QComboBox::down-arrow {{ image: none; border-left: 4px solid transparent;
                    border-right: 4px solid transparent; border-top: 5px solid {fg}; }}
            """)
        mass_edit = self.table.cellWidget(row, 1)
        if mass_edit:
            mass_edit.setStyleSheet(
                f"QLineEdit {{ background-color: {bg}; color: {fg}; border-radius: 4px; padding: 2px 4px; }}"
            )
        frac_item = self.table.item(row, 2)
        if frac_item:
            frac_item.setBackground(QColor(bg))
            frac_item.setForeground(QColor("#000000"))

    def _validate_row(self, row: int):
        if self._suppress_validate:
            return
        elem_combo = self.table.cellWidget(row, 0)
        mass_edit = self.table.cellWidget(row, 1)
        z = elem_combo.selected_z() if elem_combo else None
        a_str = mass_edit.text().strip() if mass_edit else ""

        if z is not None:
            # 未输入质量数 → 默认 000（天然元素）
            if not a_str:
                zaid = format_zzaaam(z, 0)
                sym = Z_TO_SYMBOL.get(z, "?")
                self._set_row_color(row, "#2196F3")
                tip = f"{sym} → {zaid}（天然元素，质量数默认 000）"
                elem_combo.setToolTip(tip)
                mass_edit.setToolTip(tip)
                return

            # 支持纯数字 "238" 和带库后缀 "238.80c" 两种格式
            import re
            m = re.match(r'^(\d{1,3})(\..*)?$', a_str)
            if m:
                a = int(m.group(1))
                if 1 <= a <= 999:
                    zaid = format_zzaaam(z, a)
                    sym = Z_TO_SYMBOL.get(z, "?")
                    in_db = xsdir_db.loaded and a in xsdir_db.get_isotopes(z)
                    if in_db:
                        self._set_row_color(row, "#00E676")
                        tip = f"{sym}-{a} → {zaid}  ✓ 已在截面库中"
                        elem_combo.setToolTip(tip)
                        mass_edit.setToolTip(tip)
                    else:
                        hint = "数据库未加载" if not xsdir_db.loaded else "数据库中无此核素"
                        self._set_row_color(row, "#FF1744")
                        tip = f"{sym}-{a} → {zaid}  ⚠ {hint}"
                        elem_combo.setToolTip(tip)
                        mass_edit.setToolTip(tip)
                    return

        self._set_row_color(row, "#FF9100")

    def _on_cell_changed(self, row: int, col: int):
        if col == 2:
            self._validate_row(row)

    def _add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._setup_row_widgets(row, None)

    def _delete_row(self):
        rows = set()
        for idx in self.table.selectedIndexes():
            rows.add(idx.row())
        for row in sorted(rows, reverse=True):
            self.table.removeRow(row)
        self._reconnect_all_signals()

    def _reconnect_all_signals(self):
        for row in range(self.table.rowCount()):
            elem_combo = self.table.cellWidget(row, 0)
            mass_edit = self.table.cellWidget(row, 1)
            if elem_combo:
                try:
                    elem_combo.currentTextChanged.disconnect()
                except TypeError:
                    pass
                elem_combo.currentTextChanged.connect(
                    lambda text, r=row: self._validate_row(r)
                )
            if mass_edit:
                try:
                    mass_edit.textChanged.disconnect()
                except TypeError:
                    pass
                mass_edit.textChanged.connect(
                    lambda r=row: self._validate_row(r)
                )

    # ---------- 校验与保存 ----------

    def _auto_generate_comment(self) -> str:
        """未填写注释时，从核素自动生成，如 'U238+U235+H2'"""
        mode = self.mode_combo.currentData()
        parts = []

        if mode == "formula":
            text = self.formula_edit.toPlainText().strip()
            if text:
                formulas = []
                for line in text.split("\n"):
                    for seg in line.split(","):
                        seg = seg.strip()
                        if not seg:
                            continue
                        if ":" in seg:
                            formula = seg.split(":")[0].strip()
                        else:
                            tokens = seg.split()
                            formula = tokens[0] if tokens else seg
                        if formula:
                            formulas.append(formula)
                return "+".join(formulas) if formulas else ""

        # 手动模式：从 ZAID 提取元素符号+质量数
        import re
        for row in range(self.table.rowCount()):
            elem_combo = self.table.cellWidget(row, 0)
            mass_edit = self.table.cellWidget(row, 1)
            z = elem_combo.selected_z() if elem_combo else None
            if z is None:
                continue
            sym = Z_TO_SYMBOL.get(z, "")
            if not sym:
                continue
            # 提取质量数字（去掉 .80c 等库后缀）
            a_str = mass_edit.text().strip() if mass_edit else ""
            m = re.match(r'^(\d{1,3})', a_str)
            if m:
                parts.append(f"{sym}{m.group(1)}")
            else:
                parts.append(sym)

        return "+".join(parts)

    def _on_accept(self):
        mode = self.mode_combo.currentData()

        if mode == "formula":
            if not self._formula_rows:
                QMessageBox.warning(self, "校验", "请先点击「解析化学式」并确认结果")
                return
        else:
            has_data = False
            for row in range(self.table.rowCount()):
                zaid, frac = self._get_row_data(row)
                if zaid and frac:
                    has_data = True
                    break
            if not has_data:
                QMessageBox.warning(self, "校验", "至少添加一行完整数据（元素 + 质量数 + 份额）")
                return

        # 未填写注释时自动从核素生成
        if not self.comment_edit.text().strip():
            auto_comment = self._auto_generate_comment()
            if auto_comment:
                self.comment_edit.setText(auto_comment)

        self.accept()

    def get_data(self) -> MaterialData:
        mode = self.mode_combo.currentData()

        options = self.options_edit.text().strip() if hasattr(self, 'options_edit') else ""

        if mode == "formula":
            return MaterialData(
                number=self.material.number,
                rows=list(self._formula_rows),
                comment=self.comment_edit.text().strip(),
                formula=self.formula_edit.toPlainText().strip(),
                options=options,
                mt_card=self.mt_card_edit.text().strip(),
            )
        else:
            rows = []
            for row in range(self.table.rowCount()):
                zaid, frac = self._get_row_data(row)
                if zaid and frac:
                    rows.append(MaterialRow(zaid=zaid, fraction=frac))

            return MaterialData(
                number=self.material.number,
                rows=rows,
                comment=self.comment_edit.text().strip(),
                formula="",
                options=options,
                mt_card=self.mt_card_edit.text().strip(),
            )
