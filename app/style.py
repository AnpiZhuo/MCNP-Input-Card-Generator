"""
全局样式表 — MCNP 输入卡生成器
PALETTES + QSS 模板生成四套主题
设计语言：玻璃态（Glassmorphism）+ 霓虹渐变
所有颜色使用实色（hex），避免 rgba 在 Qt5 QSS 中导致字体背景框
"""
from string import Template

PALETTES = {
    "light": {
        "bg_window": "#F5FBFB",       # 东方亮
        "bg_card": "#F8F7F0",         # 玉色
        "bg_input": "#EBEEF0",        # 鹄白
        "bg_hover": "rgba(60,118,153,0.06)",  # 品月
        "bg_press": "rgba(60,118,153,0.12)",
        "bg_disabled": "#EBEEF0",
        "bg_selected": "rgba(174,208,237,0.25)",  # 碧落
        "bg_table_alt": "#F5FBFB",
        "bg_code": "#EBEEF0",
        "card_accent": "rgba(216,230,153,0.7)",
        "text_primary": "#1A2D3A",
        "text_secondary": "#3C7699",   # 品月
        "text_disabled": "#AED0ED",    # 碧落
        "text_on_accent": "#FFFFFF",
        "accent": "#3C7699",           # 品月
        "accent_hover": "#4A8CB3",
        "accent_press": "#2E5F7A",
        "success_bg": "#91B821",       # 绿茶
        "success_text": "#FFFFFF",
        "success_hover": "#A8D427",
        "success_press": "#7A9E1C",
        "danger_bg": "#D81918",        # 丹枫
        "danger_hover": "#E83030",
        "danger_press": "#B51515",
        "warning": "#EE781F",          # 金红
        "border": "#D4E5EF",           # 月白
        "border_hover": "#AED0ED",     # 碧落
        "border_focus": "#3C7699",     # 品月
        "code_bg": "#EBEEF0",
        "code_border": "rgba(60,118,153,0.3)",
        "side_bg": "rgba(245,251,251,0.85)",
        "syn_comment": "#AED0ED",
        "syn_keyword": "#3C7699",
        "syn_number": "#6BB392",       # 四绿
        "syn_surface": "#75C1C4",      # 松石
        "syn_operator": "#D81918",
        "syn_trcl": "#3C7699",
        "syn_tr_param": "#EE781F",
        "syn_ref": "#6BB392",
        "syn_id": "#E97040",           # 凌霄
    },
    "dark": {
        "bg_window": "#0A0A12",
        "bg_card": "#1A1A2E",
        "bg_input": "#12121E",
        "bg_hover": "rgba(233,112,64,0.10)",    # 凌霄
        "bg_press": "rgba(233,112,64,0.18)",
        "bg_disabled": "#0F0F1A",
        "bg_selected": "rgba(117,193,196,0.15)", # 松石
        "bg_table_alt": "#12121E",
        "bg_code": "#0F0F1A",
        "card_accent": "rgba(73,33,74,0.7)",
        "text_primary": "#EBEEF0",     # 鹄白
        "text_secondary": "#75C1C4",    # 松石
        "text_disabled": "#4A5A6A",
        "text_on_accent": "#FFFFFF",
        "accent": "#E97040",            # 凌霄
        "accent_hover": "#F08050",
        "accent_press": "#CC6035",
        "success_bg": "#91B821",        # 绿茶
        "success_text": "#FFFFFF",
        "success_hover": "#A8D427",
        "success_press": "#7A9E1C",
        "danger_bg": "#D81918",         # 丹枫
        "danger_hover": "#E83030",
        "danger_press": "#B51515",
        "warning": "#F3993A",           # 雄黄
        "border": "rgba(117,193,196,0.15)",  # 松石
        "border_hover": "rgba(233,112,64,0.30)", # 凌霄
        "border_focus": "#E97040",       # 凌霄
        "code_bg": "#0F0F1A",
        "code_border": "rgba(233,112,64,0.3)",
        "side_bg": "rgba(10,10,18,0.90)",
        "syn_comment": "#4A5A6A",
        "syn_keyword": "#E97040",
        "syn_number": "#91B821",
        "syn_surface": "#75C1C4",
        "syn_operator": "#D81918",
        "syn_trcl": "#75C1C4",
        "syn_tr_param": "#F3993A",
        "syn_ref": "#75C1C4",
        "syn_id": "#F3993A",
    },
    "pink": {
        "bg_window": "#FFF5EE",       #  暖奶油 — 多巴胺暖底
        "bg_card": "#FFFFFF",
        "bg_input": "#FFF0FA",        #  浅粉紫
        "bg_hover": "rgba(255,0,128,0.10)",
        "bg_press": "rgba(255,0,128,0.20)",
        "bg_disabled": "#FFF0F5",
        "bg_selected": "rgba(255,183,77,0.20)",  #  金黄高亮
        "bg_table_alt": "#FFF0FA",
        "bg_code": "#FFF5F9",
        "card_accent": "rgba(255,215,64,0.7)",
        "text_primary": "#1A0D2E",    #  深紫黑
        "text_secondary": "#FF0080",   #  热辣多巴胺粉
        "text_disabled": "#FFB6D0",   #  浅粉
        "text_on_accent": "#FFFFFF",
        "accent": "#FF0080",           #  撞色粉红
        "accent_hover": "#FF3399",
        "accent_press": "#CC0066",
        "success_bg": "#00E676",       #  荧光绿
        "success_text": "#1A1A2E",
        "success_hover": "#33EE99",
        "success_press": "#00C853",
        "danger_bg": "#FF1744",        #  亮红
        "danger_hover": "#FF4569",
        "danger_press": "#D5002A",
        "warning": "#FF9100",          #  亮橙
        "border": "#FFB6D0",           #  淡粉
        "border_hover": "#FF80AB",     #  中粉
        "border_focus": "#FF0080",     #  撞色粉红
        "code_bg": "#FFF5F9",
        "code_border": "rgba(255,0,128,0.2)",
        "side_bg": "rgba(255,255,255,0.80)",
        "syn_comment": "#FFB6D0",
        "syn_keyword": "#FF0080",      #  热粉关键词
        "syn_number": "#00E676",       #  荧光绿数字
        "syn_surface": "#FF80AB",      #  粉面
        "syn_operator": "#FF9100",     #  亮橙运算符
        "syn_trcl": "#2979FF",         #  电光蓝（多巴胺撞色）
        "syn_tr_param": "#FF9100",     #  亮橙
        "syn_ref": "#2979FF",          #  电光蓝
        "syn_id": "#FF0080",           #  热粉标识符
    },
    "traditional": {
        "bg_window": "#F2E6CE",       # 宣纸/牙色（古画底）
        "bg_card": "#F8F0E0",         # 浅金粟笺
        "bg_input": "#F5EBD4",        # 老纸
        "bg_hover": "rgba(184,60,40,0.08)",  # 赭石
        "bg_press": "rgba(184,60,40,0.15)",
        "bg_disabled": "#EDE0C8",
        "bg_selected": "rgba(200,160,98,0.20)",  # 泥金
        "bg_table_alt": "#F5EBD4",
        "bg_code": "#EDE0C8",
        "card_accent": "rgba(117,193,196,0.7)",
        "text_primary": "#2C1810",    # 墨色
        "text_secondary": "#8B6914",   # 古铜
        "text_disabled": "#C8A062",   # 泥金
        "text_on_accent": "#F8F0E0",
        "accent": "#B83C28",           # 赭红（仿古印色）
        "accent_hover": "#CC4A35",
        "accent_press": "#A03020",
        "success_bg": "#6B8E5A",       # 青瓷绿
        "success_text": "#FFFFFF",
        "success_hover": "#7DA06C",
        "success_press": "#5A7A4A",
        "danger_bg": "#B83C28",
        "danger_hover": "#CC4A35",
        "danger_press": "#A03020",
        "warning": "#D4943A",          # 雄黄
        "border": "#C8A062",          # 泥金
        "border_hover": "#8B6914",    # 古铜
        "border_focus": "#B83C28",    # 赭红
        "code_bg": "#EDE0C8",
        "code_border": "rgba(184,60,40,0.25)",
        "side_bg": "rgba(242,230,206,0.85)",
        "syn_comment": "#C8A062",
        "syn_keyword": "#B83C28",
        "syn_number": "#6B8E5A",
        "syn_surface": "#5A8A8A",      # 青灰
        "syn_operator": "#B83C28",
        "syn_trcl": "#5A8A8A",
        "syn_tr_param": "#D4943A",
        "syn_ref": "#5A8A8A",
        "syn_id": "#CC6035",
    },
}

_QSS_TEMPLATE = """
/* ═══ 全局 ═══ */
QWidget { background-color: ${bg_window}; color: ${text_primary}; font-size:14px; font-family:'Microsoft YaHei','Segoe UI','PingFang SC',sans-serif; }
QWidget:disabled { color: ${text_disabled}; }

/* ═══ 窗口容器 ═══ */
#centralContainer { background: ${bg_window}; }

/* ═══ 侧边栏 ═══ */
#sideBar { background: ${side_bg}; border-right: 1px solid ${border}; }
#sideBar QPushButton[sideBtn="true"] { background:transparent; border:none; border-radius:8px; text-align:left; padding:0 8px 0 12px; font-size:14px; color:${text_disabled}; }
#sideBar QPushButton[sideBtn="true"]:hover { background:${bg_hover}; }
#sideBar QPushButton[sideBtn="true"]:checked { background:${bg_selected}; color:${text_primary}; }

/* ═══ 玻璃卡片 ═══ */
QGroupBox { background:${bg_card}; border:1px solid ${border}; border-left:5px solid ; border-radius:16px; margin-top:20px; padding:20px; }
QGroupBox:hover { border-color:; border-left-color:${border_hover}; }
QGroupBox::title { subcontrol-origin:margin; subcontrol-position:top left; padding:0 8px 0 0; background:transparent; color:${text_secondary}; font-size:12px; font-weight:600; letter-spacing:0.5px; left:16px; }

/* ═══ 标签页 ═══ */
QTabWidget::pane { border:1px solid ${border}; border-radius:8px; background:${bg_window}; }
QTabBar::tab { background:transparent; border:none; padding:8px 20px; margin-right:2px; border-radius:6px 6px 0 0; color:${text_disabled}; font-size:13px; font-weight:500; }
QTabBar::tab:selected { color:${accent}; border-bottom:2px solid ${accent}; }
QTabBar::tab:hover { color:${text_secondary}; background:${bg_hover}; }

/* ═══ 按钮 ═══ */
QPushButton { background:transparent; border:1px solid ${border}; border-radius:6px; padding:7px 18px; color:${text_secondary}; font-size:14px; font-weight:500; }
QPushButton:hover { background:${bg_hover}; border-color:${border_hover}; color:${text_primary}; }
QPushButton:pressed { background:${bg_press}; }
QPushButton:disabled { background:${bg_disabled}; color:${text_disabled}; border-color:transparent; }
QPushButton#btnGenerate { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #FF0080,stop:1 #7000FF); color:white; border:none; font-weight:600; font-size:14px; padding:8px 26px; border-radius:6px; }
QPushButton#btnGenerate:hover { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #FF3399,stop:1 #8833FF); }
QPushButton[cssClass="btnPrimary"] { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #FF0080,stop:1 #7000FF); color:white; border:none; }
QPushButton[cssClass="btnPrimary"]:hover { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #FF3399,stop:1 #8833FF); }
QPushButton[cssClass="btnAdd"] { background:rgba(16,185,129,0.12); color:${success_bg}; border:1px solid rgba(16,185,129,0.18); font-size:13px; }
QPushButton[cssClass="btnAdd"]:hover { background:rgba(16,185,129,0.20); }
QPushButton[cssClass="btnDelete"] { background:rgba(239,68,68,0.12); color:${danger_bg}; border:1px solid rgba(239,68,68,0.18); font-size:13px; }
QPushButton[cssClass="btnDelete"]:hover { background:rgba(239,68,68,0.20); }
QPushButton[cssClass="btnBrowse"] { background:transparent; color:${text_secondary}; border:1px solid ${border}; font-size:13px; }
QPushButton[cssClass="btnBrowse"]:hover { background:${bg_hover}; color:${text_primary}; border-color:${border_hover}; }

/* ═══ 输入框 ═══ */
QLineEdit, QSpinBox, QDoubleSpinBox { background:${bg_input}; border:1px solid ${border}; border-radius:6px; padding:7px 12px; min-height:26px; color:${text_primary}; font-size:14px; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color:${border_focus}; }
QPlainTextEdit { background:${bg_input}; border:1px solid ${border}; border-radius:6px; padding:8px; color:${text_primary}; font-size:13px; }
QPlainTextEdit:focus { border-color:${border_focus}; }
QComboBox { background:${bg_input}; border:1px solid ${border}; border-radius:6px; padding:7px 12px; min-height:26px; color:${text_primary}; font-size:14px; }
QComboBox:focus { border-color:${border_focus}; }

/* ═══ 复选框 ═══ */
QCheckBox { background:transparent; spacing:8px; color:${text_secondary}; font-size:14px; }
QCheckBox:hover { color:${text_primary}; }
QCheckBox::indicator { width:18px; height:18px; border:2px solid ${border}; border-radius:4px; background:transparent; }
QCheckBox::indicator:hover { border-color:${border_hover}; }
QCheckBox::indicator:checked { background:${accent}; border-color:${accent}; }

/* ═══ 表格 ═══ */
QTableWidget { background:${bg_card}; border:1px solid ${border}; border-radius:8px; gridline-color:transparent; selection-background-color:${bg_selected}; font-size:13px; }
QTableWidget::item { padding:8px 12px; border:none; }
QTableWidget::item:alternate { background:${bg_table_alt}; }
QTableWidget::item:hover { background:${bg_hover}; }
QTableWidget::item:selected { background:${bg_selected}; color:${accent}; font-weight:500; }
QHeaderView::section { background:transparent; color:${text_disabled}; padding:8px 12px; border:none; border-bottom:1px solid ${border}; font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:0.5px; }
QHeaderView::section:hover { background:${bg_hover}; }

/* ═══ 滚动条 ═══ */
QScrollBar:vertical { background:transparent; width:4px; border-radius:2px; }
QScrollBar::handle:vertical { background:${border}; border-radius:2px; min-height:30px; }
QScrollBar::handle:vertical:hover { background:${border_hover}; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QScrollBar:horizontal { background:transparent; height:4px; border-radius:2px; }
QScrollBar::handle:horizontal { background:${border}; border-radius:2px; min-width:30px; }
QScrollBar::handle:horizontal:hover { background:${border_hover}; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }

/* ═══ 状态栏 ═══ */
#customStatusBar { background:rgba(2,1,5,0.7); border-top:1px solid ${border}; font-size:12px; color:${text_disabled}; padding:0 12px; }

/* ═══ 其他 ═══ */
QSplitter::handle { background:${border}; height:4px; }
QSplitter::handle:hover { background:${accent}; }
QLabel { background:transparent; color:${text_secondary}; font-size:13px; }
QDialog { background:${bg_window}; }
"""


def _make_qss(name: str) -> str:
    return Template(_QSS_TEMPLATE).safe_substitute(**PALETTES[name])

LIGHT_QSS = _make_qss("light")
DARK_QSS = _make_qss("dark")
PINK_QSS = _make_qss("pink")
TRADITIONAL_QSS = _make_qss("traditional")
STYLE = LIGHT_QSS
