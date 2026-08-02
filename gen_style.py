"""
gen_style.py — 生成器：从调色板 + QSS 模板生成 app/style.py

消除 4× QSS 重复（原 1944 行 → ~300 行模板 × 4 注入）。
修改配色只需编辑 _PALETTES 字典，然后重新运行 python gen_style.py。

变量命名规则：按区域/语义分组，全称可读。
  bg_*       背景色     text_*     文字色
  accent_*   强调色     success_*  成功/添加
  danger_*   删除/危险   warning_*  警告
  border_*   边框       import_*   导入按钮
  theme_*    主题切换    toolbar_*  工具栏
  code_*     代码块
"""

import os
from string import Template


# ── 调色板 ─────────────────────────────────────────────────────────────────
# 每个主题约 40 个颜色变量。各按钮独立设色是因为它们在主题间的映射不一致
# （例如 pink 主题的导入按钮用粉色调而非绿色调）。
_PALETTES = {
    "light": {
        # 背景色 Background
        "bg_window":     "#f0f2f5",
        "bg_panel":      "#ffffff",
        "bg_input":      "#ffffff",
        "bg_hover":      "#d0d7e3",
        "bg_press":      "#b0bccf",
        "bg_disabled":   "#f5f5f5",
        "bg_tab":        "#e8eaf0",
        "bg_header":     "#f5f7fa",
        "bg_selected":   "#E3F2FD",
        "bg_table_alt":  "#f8f9fb",
        "bg_code":       "#f5f5f5",
        # 文字色 Text
        "text_primary":      "#1a1a2e",
        "text_secondary":    "#5f6368",
        "text_disabled":     "#9e9e9e",
        "text_on_accent":    "#ffffff",
        # 强调色 Accent (blue)
        "accent":        "#1565C0",
        "accent_hover":  "#1976D2",
        "accent_press":  "#0D47A1",
        # 成功/添加按钮 Success / Add (green)
        "success_bg":        "#2E7D32",
        "success_text":      "#ffffff",
        "success_hover":     "#388E3C",
        "success_press":     "#1B5E20",
        "success_light":     "#E8F5E9",
        # 删除按钮 Danger / Delete (red)
        "danger_bg":     "#C62828",
        "danger_text":   "#ffffff",
        "danger_hover":  "#D32F2F",
        "danger_press":  "#B71C1C",
        # 警告色 Warning (amber)
        "warning":       "#f5a623",
        # 边框 Border
        "border":        "#e0e0e0",
        "border_soft":   "#d0d5dd",
        "border_focus":  "#1565C0",
        # 导入按钮 Import (greenish)
        "import_bg":         "#E8F5E9",
        "import_text":       "#2E7D32",
        "import_border":     "#A5D6A7",
        "import_hover_bg":   "#C8E6C9",
        "import_hover_border":"#66BB6A",
        # 主题切换按钮 Theme toggle
        "theme_bg":        "#e8eaf0",
        "theme_text":      "#f5a623",
        "theme_border":    "#d0d5dd",
        "theme_hover_bg":  "#d0d7e3",
        "theme_hover_text":"#e91e63",
        "theme_hover_border":"#a0aab8",
        # 工具栏 Toolbar
        "toolbar_bg":      "#ffffff",
        "toolbar_border":  "#dce1e8",
        # 代码块 Code block
        "code_bg":         "#f5f5f5",
        "code_border":     "#1976d2",
    },
    "dark": {
        "bg_window":     "#1e1e2e",
        "bg_panel":      "#313244",
        "bg_input":      "#313244",
        "bg_hover":      "#3e4158",
        "bg_press":      "#313244",
        "bg_disabled":   "#181825",
        "bg_tab":        "#313244",
        "bg_header":     "#45475a",
        "bg_selected":   "#45475a",
        "bg_table_alt":  "#252839",
        "bg_code":       "#313244",
        "text_primary":      "#cdd6f4",
        "text_secondary":    "#a6adc8",
        "text_disabled":     "#6c7086",
        "text_on_accent":    "#1e1e2e",
        "accent":        "#89b4fa",
        "accent_hover":  "#b4d0fb",
        "accent_press":  "#74a8f7",
        "success_bg":        "#a6e3a1",
        "success_text":      "#1e1e2e",
        "success_hover":     "#94e2d5",
        "success_press":     "#7dc98c",
        "success_light":     "#313244",
        "danger_bg":     "#f38ba8",
        "danger_text":   "#1e1e2e",
        "danger_hover":  "#f5a0b8",
        "danger_press":  "#e07090",
        "warning":       "#f9e2af",
        "border":        "#45475a",
        "border_soft":   "#585b70",
        "border_focus":  "#89b4fa",
        "import_bg":         "#313244",
        "import_text":       "#a6e3a1",
        "import_border":     "#45475a",
        "import_hover_bg":   "#45475a",
        "import_hover_border":"#a6e3a1",
        "theme_bg":        "#45475a",
        "theme_text":      "#f9e2af",
        "theme_border":    "#585b70",
        "theme_hover_bg":  "#585b70",
        "theme_hover_text":"#f5c2e7",
        "theme_hover_border":"#6c7086",
        "toolbar_bg":      "#1e1e2e",
        "toolbar_border":  "#45475a",
        "code_bg":         "#313244",
        "code_border":     "#89b4fa",
    },
    "pink": {
        "bg_window":     "#fff5f7",
        "bg_panel":      "#ffffff",
        "bg_input":      "#ffffff",
        "bg_hover":      "#f8d7e0",
        "bg_press":      "#f0b8c8",
        "bg_disabled":   "#fff5f7",
        "bg_tab":        "#fce4ec",
        "bg_header":     "#fff0f3",
        "bg_selected":   "#fce4ec",
        "bg_table_alt":  "#fef6f8",
        "bg_code":       "#fffafb",
        "text_primary":      "#4a3034",
        "text_secondary":    "#884a54",
        "text_disabled":     "#dbb6be",
        "text_on_accent":    "#ffffff",
        "accent":        "#e91e63",
        "accent_hover":  "#f06292",
        "accent_press":  "#c2185b",
        # Pink theme: success 也用粉色系（不用绿色）
        "success_bg":        "#e91e63",
        "success_text":      "#ffffff",
        "success_hover":     "#f06292",
        "success_press":     "#c2185b",
        "success_light":     "#fce4ec",
        # Pink theme: danger 用暖粉色
        "danger_bg":     "#ffb3b3",
        "danger_text":   "#8a2a2a",
        "danger_hover":  "#ff8a8a",
        "danger_press":  "#ff6666",
        "warning":       "#e91e63",
        "border":        "#f8d7e0",
        "border_soft":   "#f8d7e0",
        "border_focus":  "#e91e63",
        # Pink theme: import 也用粉色系
        "import_bg":         "#fce4ec",
        "import_text":       "#e91e63",
        "import_border":     "#f8d7e0",
        "import_hover_bg":   "#f8d7e0",
        "import_hover_border":"#e91e63",
        "theme_bg":        "#fce4ec",
        "theme_text":      "#e91e63",
        "theme_border":    "#f8d7e0",
        "theme_hover_bg":  "#f8d7e0",
        "theme_hover_text":"#c2185b",
        "theme_hover_border":"#f0b8c8",
        "toolbar_bg":      "#ffffff",
        "toolbar_border":  "#f8d7e0",
        "code_bg":         "#fffafb",
        "code_border":     "#e91e63",
    },
    "traditional": {
        "bg_window":     "#FFF8E1",
        "bg_panel":      "#FFFDE7",
        "bg_input":      "#FFFDE7",
        "bg_hover":      "#EF9A9A",
        "bg_press":      "#E57373",
        "bg_disabled":   "#FFF8E1",
        "bg_tab":        "#FFCDD2",
        "bg_header":     "#D32F2F",
        "bg_selected":   "#FFCDD2",
        "bg_table_alt":  "#FFF3E0",
        "bg_code":       "#FFFDE7",
        "text_primary":      "#4E342E",
        "text_secondary":    "#795548",
        "text_disabled":     "#BCAAA4",
        "text_on_accent":    "#FFD700",
        "accent":        "#D32F2F",
        "accent_hover":  "#C62828",
        "accent_press":  "#B71C1C",
        # Traditional: 翡翠绿 = 传统中国色之一
        "success_bg":        "#2E7D32",
        "success_text":      "#ffffff",
        "success_hover":     "#388E3C",
        "success_press":     "#1B5E20",
        "success_light":     "#C8E6C9",
        # Traditional: 朱红
        "danger_bg":     "#D32F2F",
        "danger_text":   "#FFD700",
        "danger_hover":  "#C62828",
        "danger_press":  "#B71C1C",
        "warning":       "#FFD700",
        "border":        "#E57373",
        "border_soft":   "#EF9A9A",
        "border_focus":  "#D32F2F",
        # Traditional: import 用红金配色
        "import_bg":         "#FFCDD2",
        "import_text":       "#D32F2F",
        "import_border":     "#C62828",
        "import_hover_bg":   "#EF9A9A",
        "import_hover_border":"#B71C1C",
        "theme_bg":        "#FFCDD2",
        "theme_text":      "#D32F2F",
        "theme_border":    "#C62828",
        "theme_hover_bg":  "#EF9A9A",
        "theme_hover_text":"#B71C1C",
        "theme_hover_border":"#b71c1c",
        "toolbar_bg":      "#FFF8E1",
        "toolbar_border":  "#C62828",
        "code_bg":         "#FFFDE7",
        "code_border":     "#D32F2F",
    },
}


# ── QSS 模板 ───────────────────────────────────────────────────────────────
# 使用 string.Template 语法（${var}），避免与 CSS 花括号 {} 冲突
_QSS_TEMPLATE = Template("""\
/* ===== 全局默认 ===== */
QWidget {
    background-color: ${bg_window};
    color: ${text_primary};
    font-family: "Microsoft YaHei", "Segoe UI", "PingFang SC", sans-serif;
    font-size: 13px;
}
QWidget:disabled {
    color: ${text_disabled};
}

/* ===== 分组框 ===== */
QGroupBox {
    background-color: ${bg_panel};
    border: 1px solid ${border};
    border-radius: 8px;
    margin-top: 16px;
    padding: 16px 12px 12px 12px;
    font-weight: bold;
    font-size: 13px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    background-color: ${accent};
    color: ${text_on_accent};
    border-radius: 4px;
    left: 10px;
    font-size: 12px;
    font-weight: bold;
}

/* ===== 标签页 ===== */
QTabWidget::pane {
    border: 1px solid ${border};
    border-radius: 8px;
    background-color: ${bg_window};
    padding: 4px;
}
QTabBar::tab {
    background-color: ${bg_tab};
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    margin-right: 4px;
    font-size: 13px;
    font-weight: 500;
    color: ${text_secondary};
}
QTabBar::tab:hover {
    background-color: ${bg_hover};
    color: ${text_primary};
}
QTabBar::tab:selected {
    background-color: ${accent};
    color: ${text_on_accent};
    font-weight: bold;
}

/* ===== 通用按钮 ===== */
QPushButton {
    background-color: ${bg_tab};
    border: 1px solid ${border_soft};
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 13px;
    color: ${text_primary};
}
QPushButton:hover {
    background-color: ${bg_hover};
    border-color: ${border};
}
QPushButton:pressed {
    background-color: ${bg_press};
}
QPushButton:disabled {
    background-color: ${bg_disabled};
    color: ${text_disabled};
}

/* ===== 生成 INP 按钮 ===== */
QPushButton#btnGenerate {
    background-color: ${accent};
    color: ${text_on_accent};
    border: none;
    font-weight: bold;
    font-size: 14px;
    padding: 8px 28px;
    border-radius: 8px;
}
QPushButton#btnGenerate:hover {
    background-color: ${accent_hover};
}
QPushButton#btnGenerate:pressed {
    background-color: ${accent_press};
}

/* ===== 添加按钮 ===== */
QPushButton[cssClass="btnAdd"] {
    background-color: ${success_bg};
    color: ${success_text};
    border: none;
    font-weight: bold;
    border-radius: 6px;
}
QPushButton[cssClass="btnAdd"]:hover {
    background-color: ${success_hover};
}
QPushButton[cssClass="btnAdd"]:pressed {
    background-color: ${success_press};
}

/* ===== 删除按钮 ===== */
QPushButton[cssClass="btnDelete"] {
    background-color: ${danger_bg};
    color: ${danger_text};
    border: none;
    font-weight: bold;
    border-radius: 6px;
}
QPushButton[cssClass="btnDelete"]:hover {
    background-color: ${danger_hover};
}
QPushButton[cssClass="btnDelete"]:pressed {
    background-color: ${danger_press};
}

/* ===== 行内删除按钮（表格内小按钮）===== */
QPushButton[cssClass="btnDeleteRow"] {
    background-color: transparent;
    color: ${danger_bg};
    border: 1px solid ${danger_bg};
    font-weight: bold;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 12px;
}
QPushButton[cssClass="btnDeleteRow"]:hover {
    background-color: ${danger_bg};
    color: ${danger_text};
}

/* ===== 编辑按钮 ===== */
QPushButton[cssClass="btnEdit"] {
    background-color: ${bg_selected};
    color: ${accent};
    border: 1px solid ${border};
    border-radius: 4px;
    padding: 4px 12px;
    font-weight: normal;
}
QPushButton[cssClass="btnEdit"]:hover {
    background-color: ${bg_hover};
}
QPushButton[cssClass="btnEdit"]:pressed {
    background-color: ${bg_press};
}

/* ===== 主操作按钮（通用）===== */
QPushButton[cssClass="btnPrimary"] {
    background-color: ${accent};
    color: ${text_on_accent};
    border: none;
    font-weight: bold;
    padding: 8px 24px;
    font-size: 14px;
    border-radius: 6px;
}
QPushButton[cssClass="btnPrimary"]:hover {
    background-color: ${accent_hover};
}
QPushButton[cssClass="btnPrimary"]:pressed {
    background-color: ${accent_press};
}

/* ===== 导入 INP 按钮 ===== */
QPushButton#btnImport {
    background-color: ${import_bg};
    color: ${import_text};
    border: 1px solid ${import_border};
    font-weight: bold;
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 6px;
}
QPushButton#btnImport:hover {
    background-color: ${import_hover_bg};
    border-color: ${import_hover_border};
}

/* ===== 主题切换按钮 ===== */
QPushButton#btnTheme {
    background-color: ${theme_bg};
    color: ${theme_text};
    border: 1px solid ${theme_border};
    font-weight: bold;
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 6px;
}
QPushButton#btnTheme:hover {
    background-color: ${theme_hover_bg};
    color: ${theme_hover_text};
    border-color: ${theme_hover_border};
}

/* ===== 帮助按钮（问号圆圈）===== */
QPushButton#btnGlobalHelp {
    background-color: ${accent};
    color: ${text_on_accent};
    border: none;
    border-radius: 11px;
    font-weight: bold;
    font-size: 12px;
    min-width: 22px;
    max-width: 22px;
    min-height: 22px;
    max-height: 22px;
    padding: 0;
}
QPushButton#btnGlobalHelp:hover {
    background-color: ${accent_hover};
}

/* ===== 浏览按钮 ===== */
QPushButton[cssClass="btnBrowse"] {
    background-color: ${text_secondary};
    color: ${text_on_accent};
    border: none;
    padding: 6px 14px;
    border-radius: 6px;
}
QPushButton[cssClass="btnBrowse"]:hover {
    background-color: ${text_disabled};
}
QPushButton[cssClass="btnBrowse"]:pressed {
    background-color: ${text_disabled};
}

/* ===== 切换按钮（虚线边框）===== */
QPushButton[cssClass="btnToggle"] {
    background-color: transparent;
    border: 1px dashed ${border_soft};
    text-align: left;
    color: ${text_secondary};
    padding: 4px 12px;
    border-radius: 4px;
}
QPushButton[cssClass="btnToggle"]:hover {
    border-color: ${accent};
    color: ${accent};
    background-color: ${bg_selected};
}

/* ===== 输入框 ===== */
QLineEdit {
    background-color: ${bg_input};
    border: 1px solid ${border_soft};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    color: ${text_primary};
    selection-background-color: ${bg_selected};
    selection-color: ${text_primary};
}
QLineEdit:focus {
    border-color: ${border_focus};
    border-width: 2px;
    padding: 5px 9px;
}
QLineEdit:disabled {
    background-color: ${bg_disabled};
    color: ${text_disabled};
}

/* ===== 文本编辑区 ===== */
QPlainTextEdit {
    background-color: ${bg_input};
    border: 1px solid ${border_soft};
    border-radius: 6px;
    padding: 6px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 13px;
    color: ${text_primary};
    selection-background-color: ${bg_selected};
    selection-color: ${text_primary};
}
QPlainTextEdit:focus {
    border-color: ${border_focus};
}

/* ===== 数字输入框 ===== */
QSpinBox, QDoubleSpinBox {
    background-color: ${bg_input};
    border: 1px solid ${border_soft};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 13px;
    color: ${text_primary};
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: ${border_focus};
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid ${border_soft};
    border-bottom: 1px solid ${border_soft};
    border-top-right-radius: 6px;
    background-color: ${bg_header};
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border-left: 1px solid ${border_soft};
    border-bottom-right-radius: 6px;
    background-color: ${bg_header};
}

/* ===== 下拉框 ===== */
QComboBox {
    background-color: ${bg_input};
    border: 1px solid ${border_soft};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    color: ${text_primary};
}
QComboBox:hover {
    border-color: ${accent};
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid ${border_soft};
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}
QComboBox QAbstractItemView {
    background-color: ${bg_input};
    border: 1px solid ${border};
    border-radius: 4px;
    selection-background-color: ${bg_selected};
    selection-color: ${accent};
    padding: 4px;
}

/* ===== 复选框 ===== */
QCheckBox {
    spacing: 8px;
    font-size: 13px;
    color: ${text_primary};
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid ${bg_press};
    background-color: ${bg_input};
}
QCheckBox::indicator:hover {
    border-color: ${accent};
}
QCheckBox::indicator:checked {
    background-color: ${accent};
    border-color: ${accent};
}

/* ===== 表格 ===== */
QTableWidget {
    background-color: ${bg_panel};
    border: 1px solid ${border};
    border-radius: 6px;
    gridline-color: ${bg_header};
    selection-background-color: ${bg_selected};
    selection-color: ${text_primary};
}
QTableWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid ${bg_window};
}
QTableWidget::item:alternate {
    background-color: ${bg_table_alt};
}
QTableWidget::item:hover {
    background-color: ${bg_tab};
}
QTableWidget::item:selected {
    background-color: ${bg_selected};
    color: ${accent};
    font-weight: 500;
}
QHeaderView::section {
    background-color: ${bg_header};
    color: ${text_secondary};
    padding: 8px 10px;
    border: none;
    border-bottom: 2px solid ${border};
    font-weight: bold;
    font-size: 12px;
}
QHeaderView::section:hover {
    background-color: ${bg_hover};
}

/* ===== 滚动条 ===== */
QScrollBar:vertical {
    background-color: ${bg_window};
    width: 12px;
    border-radius: 6px;
}
QScrollBar::handle:vertical {
    background-color: ${bg_press};
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background-color: ${text_disabled};
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background-color: ${bg_window};
    height: 12px;
    border-radius: 6px;
}
QScrollBar::handle:horizontal {
    background-color: ${bg_press};
    border-radius: 6px;
    min-width: 30px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background-color: ${text_disabled};
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ===== 状态栏 ===== */
QStatusBar {
    background-color: ${bg_panel};
    border-top: 1px solid ${border};
    font-size: 12px;
    color: ${text_secondary};
    padding: 2px 8px;
}

/* ===== 分割器 ===== */
QSplitter::handle {
    background-color: ${border};
    height: 4px;
    margin: 2px 0;
    border-radius: 2px;
}
QSplitter::handle:hover {
    background-color: ${accent};
}

/* ===== 标签 ===== */
QLabel {
    background: transparent;
    color: ${text_primary};
}

/* ===== 工具栏容器 ===== */
QWidget#toolbar {
    background-color: ${toolbar_bg};
    border-top: 1px solid ${toolbar_border};
    border-radius: 0 0 8px 8px;
    padding: 8px;
}
""")


def generate_module() -> str:
    """生成 app/style.py 的完整源码字符串。

    生成的 style.py 在 import 时从 PALETTES + _TEMPLATE 运行时推导 QSS。
    PALETTES 就是配色唯一来源——改它 QSS 自动更新。
    """
    lines = []
    lines.append('"""')
    lines.append("全局样式表 — MCNP 输入卡生成器")
    lines.append("运行时从 PALETTES + 模板生成 QSS。")
    lines.append("修改配色请编辑下方的 PALETTES 字典，QSS 会自动更新。")
    lines.append('"""')
    lines.append("from string import Template")
    lines.append("")

    # ── 调色板（配色唯一来源）──
    lines.append("")
    lines.append("# ===== 调色板（配色唯一来源）=====")
    lines.append("PALETTES = {")
    for theme_name in ["light", "dark", "pink", "traditional"]:
        p = _PALETTES[theme_name]
        lines.append(f'    "{theme_name}": {{')
        for k, v in p.items():
            lines.append(f'        "{k}": "{v}",')
        lines.append("    },")
    lines.append("}")
    lines.append("")

    # ── QSS 模板 ──
    lines.append("# ===== QSS 模板 ===== ")
    lines.append("_TEMPLATE = \"\"\"\\")
    raw = _QSS_TEMPLATE.template
    # 去掉首行空行（模板以 \n 开头）
    if raw.startswith("\n"):
        raw = raw[1:]
    # 去掉末尾多余的空白
    raw = raw.rstrip("\n")
    lines.append(raw)
    lines.append("\"\"\"")
    lines.append("")

    # ── 运行时生成函数 ──
    lines.append("")
    lines.append("def _make_qss(name):")
    lines.append('    """从调色板生成 QSS 字符串。"""')
    lines.append("    t = Template(_TEMPLATE)")
    lines.append("    return t.safe_substitute(**PALETTES[name])")
    lines.append("")
    lines.append("")

    # ── 导出的 QSS 变量 ──
    lines.append("# ===== 导出的 QSS 变量 =====")
    for name in ["light", "dark", "pink", "traditional"]:
        var = f"{name.upper()}_QSS"
        lines.append(f'{var} = _make_qss("{name}")')
    lines.append("")
    lines.append("# ===== 向后兼容别名 =====")
    lines.append("STYLE = LIGHT_QSS")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    target = os.path.join(os.path.dirname(__file__), "app", "style.py")
    content = generate_module()
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)

    # 快速验证
    ns = {}
    exec(content, ns)
    expected = ["LIGHT_QSS", "DARK_QSS", "PINK_QSS", "TRADITIONAL_QSS", "STYLE"]
    for name in expected:
        assert name in ns, f"缺少变量: {name}"
        assert isinstance(ns[name], str), f"{name} 不是字符串"
        assert len(ns[name]) > 200, f"{name} 太短（{len(ns[name])} 字符）"

    size = len(content.encode("utf-8"))
    lines_count = content.count("\n") + 1
    qss_sizes = ", ".join(f"{len(ns[n])//1024} KB" for n in ["LIGHT_QSS","DARK_QSS","PINK_QSS","TRADITIONAL_QSS"])
    print("[OK] 已生成: %s" % target)
    print("   模块大小: %d bytes / %d 行" % (size, lines_count))
    print("   QSS 各主题: %s" % qss_sizes)
    print("[OK] 变量验证通过（5/5）")
    print("原始 style.py: 1944 行 -> 新 style.py: %d 行" % lines_count)
