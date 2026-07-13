"""
全局样式表 — MCNP 输入卡生成器
现代蓝色主题，统一配色
"""

# 全局样式（传统）—— 用作默认应用样式
STYLE = """
/* ===== 全局 ===== */
QMainWindow, QWidget {
    background-color: #f5f7fa;                    /* 浅灰背景 */
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #2c3e50;                               /* 深灰蓝文字 */
}

/* ===== 标签页 ===== */
QTabWidget::pane {
    border: 1px solid #dce1e8;                    /* 标签内容区边框 */
    border-top: none;                              /* 去掉上边框使标签相连 */
    background: #ffffff;
    border-radius: 0 0 8px 8px;
    padding: 8px;
}

QTabWidget::tab-bar {
    alignment: left;
}

QTabBar::tab {
    background: #e8ecf1;
    border: 1px solid #dce1e8;
    border-bottom: none;                           /* 去掉下边框使标签与面板融合 */
    padding: 10px 20px;
    margin-right: 2px;
    border-radius: 6px 6px 0 0;
    font-weight: bold;
    font-size: 12px;
    color: #5a6a7a;
}

QTabBar::tab:selected {
    background: #ffffff;
    color: #1a73e8;                               /* 选中标签蓝色 */
    border-bottom: 2px solid #1a73e8;
}

QTabBar::tab:hover:!selected {
    background: #dce1e8;
    color: #2c3e50;
}

/* ===== 分组框 ===== */
QGroupBox {
    background: #ffffff;
    border: 1px solid #dce1e8;
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px 12px 12px 12px;
    font-weight: bold;
    font-size: 13px;
    color: #1a73e8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 12px;
    background: #e8f0fe;                           /* 标题浅蓝徽章 */
    color: #1a73e8;
    border-radius: 4px;
    margin-left: 8px;
}

/* ===== 按钮 ===== */
QPushButton {
    background: #e8ecf1;
    border: 1px solid #dce1e8;
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
    color: #2c3e50;
    min-height: 20px;
}

QPushButton:hover {
    background: #d2d9e3;
    border-color: #b8c3d1;
}

QPushButton:pressed {
    background: #b8c3d1;
}

QPushButton:disabled {
    background: #f0f2f4;
    color: #aab2bc;
}


/* 主操作按钮 - 生成 INP */
QPushButton#btnGenerate {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1a73e8, stop:1 #1557b0);
    color: white;
    border: none;
    font-weight: bold;
    font-size: 14px;
    padding: 10px 30px;
    border-radius: 8px;
}

QPushButton#btnGenerate:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1557b0, stop:1 #0d47a1);
}



/* 添加按钮 - 绿色文字（用 text 开头匹配 "+ 添加"） */
/* 删除按钮 - 红色文字（用 text 开头匹配 "× 删除"） */

/* ===== 输入框 ===== */
QLineEdit, QSpinBox, QDoubleSpinBox {
    background: #ffffff;
    border: 1px solid #dce1e8;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    color: #2c3e50;
    min-height: 20px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #1a73e8;                        /* 聚焦时蓝色边框 */
    background: #f8fbff;
}

QLineEdit:disabled {
    background: #f0f2f4;
    color: #aab2bc;
}

/* ===== 下拉框 ===== */
QComboBox {
    background: #ffffff;
    border: 1px solid #dce1e8;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    color: #2c3e50;
    min-height: 20px;
}

QComboBox:focus {
    border-color: #1a73e8;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #5a6a7a;                /* 用CSS三角做箭头指示 */
    margin-right: 6px;
}

QComboBox:hover {
    border-color: #b8c3d1;
}

/* ===== 复选框 ===== */
QCheckBox {
    spacing: 8px;
    font-size: 13px;
    color: #2c3e50;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #b8c3d1;
    border-radius: 4px;
    background: #ffffff;
}

QCheckBox::indicator:checked {
    background: #1a73e8;                           /* 选中时蓝色填充 */
    border-color: #1a73e8;
}

QCheckBox::indicator:hover {
    border-color: #1a73e8;
}

/* ===== 表格 ===== */
QTableWidget {
    background: #ffffff;
    border: 1px solid #dce1e8;
    border-radius: 6px;
    gridline-color: #eef1f5;
    selection-background-color: #e8f0fe;
    selection-color: #1a73e8;
    font-size: 13px;
}

QHeaderView::section {
    background: #f0f4f8;
    border: none;
    border-bottom: 2px solid #dce1e8;
    padding: 8px 12px;
    font-weight: bold;
    font-size: 12px;
    color: #5a6a7a;
}

QTableWidget::item {
    padding: 4px 8px;
}

QTableWidget::item:selected {
    background: #e8f0fe;
    color: #1a73e8;
}

/* ===== 文本编辑区 ===== */
QPlainTextEdit {
    background: #ffffff;
    border: 1px solid #dce1e8;
    border-radius: 6px;
    padding: 8px;
    font-family: "Consolas", "Courier New", monospace;  /* 等宽字体用于INP编辑 */
    font-size: 12px;
    color: #2c3e50;
}

QPlainTextEdit:focus {
    border-color: #1a73e8;
    background: #f8fbff;
}

/* ===== 状态栏 ===== */
QStatusBar {
    background: #e8ecf1;
    border-top: 1px solid #dce1e8;
    color: #5a6a7a;
    font-size: 12px;
}

/* ===== 滚动条 ===== */
QScrollBar:vertical {
    background: #f0f2f4;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #c8cfd8;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #aab2bc;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;                                  /* 隐藏滚动条箭头按钮 */
}

/* ===== 提示标签 ===== */
QLabel {
    color: #5a6a7a;
}

/* ===== 底部工具栏 ===== */
QWidget#toolbar {
    background: #ffffff;
    border-top: 1px solid #dce1e8;
    border-radius: 0 0 8px 8px;
    padding: 8px;
}

/* ===== 对话框 ===== */
QDialog {
    background: #f5f7fa;
}

QDialog QPushButton {
    min-width: 80px;
}

/* ===== 分割器 ===== */
QSplitter::handle {
    background: #dce1e8;
    height: 2px;
}

QSplitter::handle:hover {
    background: #1a73e8;
}
"""

# ===== 白天主题（MainWindow 专用）=====
LIGHT_QSS = """
/* ===== 全局默认 ===== */
QWidget {
    background-color: #f0f2f5;                    /* 浅灰基调 */
    color: #1a1a2e;                               /* 近黑色文字 */
    font-family: "Microsoft YaHei", "Segoe UI", "PingFang SC", sans-serif;
    font-size: 13px;
}
QWidget:disabled {
    color: #9e9e9e;                               /* 禁用控件灰文字 */
}

QGroupBox {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
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
    background-color: #1565C0;                    /* 蓝色标题徽章 */
    color: white;
    border-radius: 4px;
    left: 10px;
    font-size: 12px;
    font-weight: bold;
}

QTabWidget::pane {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    background-color: #f0f2f5;
    padding: 4px;
}
QTabBar::tab {
    background-color: #e8eaf0;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    margin-right: 4px;
    font-size: 13px;
    font-weight: 500;
    color: #5f6368;
}
QTabBar::tab:hover {
    background-color: #d0d7e3;
    color: #1a1a2e;
}
QTabBar::tab:selected {
    background-color: #1565C0;                    /* 激活标签蓝色背景 */
    color: white;
    font-weight: bold;
}

QPushButton {
    background-color: #e8eaf0;
    border: 1px solid #d0d5dd;
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 13px;
    color: #1a1a2e;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #d0d7e3;
    border-color: #a0aab8;
}
QPushButton:pressed {
    background-color: #b0bccf;
}
/* 主操作 - 生成 INP */
QPushButton#btnGenerate {
    background-color: #1565C0;
    color: white;
    border: none;
    font-weight: bold;
    font-size: 14px;
    padding: 8px 28px;
    border-radius: 8px;
}
QPushButton#btnGenerate:hover {
    background-color: #1976D2;
}
QPushButton#btnGenerate:pressed {
    background-color: #0D47A1;
}
/* 添加按钮 — 绿色 */
QPushButton[cssClass="btnAdd"] {
    background-color: #2E7D32;
    color: white;
    border: none;
    font-weight: bold;
}
QPushButton[cssClass="btnAdd"]:hover {
    background-color: #388E3C;
}
QPushButton[cssClass="btnAdd"]:pressed {
    background-color: #1B5E20;
}
/* 删除按钮 — 红色 */
QPushButton[cssClass="btnDelete"] {
    background-color: #C62828;
    color: white;
    border: none;
    font-weight: bold;
}
QPushButton[cssClass="btnDelete"]:hover {
    background-color: #D32F2F;
}
QPushButton[cssClass="btnDelete"]:pressed {
    background-color: #B71C1C;
}
/* 编辑按钮 — 浅蓝描边 */
QPushButton[cssClass="btnEdit"] {
    background-color: #E3F2FD;
    color: #1565C0;
    border: 1px solid #BBDEFB;
    border-radius: 4px;
    padding: 4px 12px;
    font-weight: normal;
    min-height: 24px;
}
QPushButton[cssClass="btnEdit"]:hover {
    background-color: #BBDEFB;
}
QPushButton[cssClass="btnEdit"]:pressed {
    background-color: #90CAF9;
}
/* 主操作按钮（通用） */
QPushButton[cssClass="btnPrimary"] {
    background-color: #1565C0;
    color: white;
    border: none;
    font-weight: bold;
    padding: 8px 24px;
    font-size: 14px;
}
QPushButton[cssClass="btnPrimary"]:hover {
    background-color: #1976D2;
}
QPushButton[cssClass="btnPrimary"]:pressed {
    background-color: #0D47A1;
}
/* 导入按钮 — 绿色描边 */
QPushButton#btnImport {
    background-color: #E8F5E9;
    color: #2E7D32;
    border: 1px solid #A5D6A7;
    font-weight: bold;
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 6px;
}
QPushButton#btnImport:hover {
    background-color: #C8E6C9;
    border-color: #66BB6A;
}
/* 主题切换按钮 — 金色 */
QPushButton#btnTheme {
    background-color: #e8eaf0;
    color: #f5a623;
    border: 1px solid #d0d5dd;
    font-weight: bold;
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 6px;
}
QPushButton#btnTheme:hover {
    background-color: #d0d7e3;
    color: #e91e63;
    border-color: #a0aab8;
}
/* 浏览按钮 — 灰色 */
QPushButton[cssClass="btnBrowse"] {
    background-color: #6c757d;
    color: white;
    border: none;
    padding: 6px 14px;
}
QPushButton[cssClass="btnBrowse"]:hover {
    background-color: #5a6268;
}
QPushButton[cssClass="btnBrowse"]:pressed {
    background-color: #545b62;
}
/* 切换按钮 — 虚线边框 */
QPushButton[cssClass="btnToggle"] {
    background-color: transparent;
    border: 1px dashed #c0c7d0;
    text-align: left;
    color: #5f6368;
    padding: 4px 12px;
}
QPushButton[cssClass="btnToggle"]:hover {
    border-color: #1565C0;
    color: #1565C0;
    background-color: #f0f4ff;
}

QLineEdit {
    background-color: #ffffff;
    border: 1px solid #d0d5dd;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    color: #1a1a2e;
    selection-background-color: #BBDEFB;          /* 浅蓝文字选中 */
}
QLineEdit:focus {
    border-color: #1565C0;
    border-width: 2px;
    padding: 5px 9px;
}
QLineEdit:disabled {
    background-color: #f5f5f5;
    color: #9e9e9e;
}

QPlainTextEdit {
    background-color: #ffffff;
    border: 1px solid #d0d5dd;
    border-radius: 6px;
    padding: 6px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 13px;
    color: #1a1a2e;
    selection-background-color: #BBDEFB;
}
QPlainTextEdit:focus {
    border-color: #1565C0;
}


QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #d0d5dd;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 13px;
    color: #1a1a2e;
    min-height: 24px;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #1565C0;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #d0d5dd;
    border-bottom: 1px solid #d0d5dd;
    border-top-right-radius: 6px;
    background-color: #f5f7fa;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border-left: 1px solid #d0d5dd;
    border-bottom-right-radius: 6px;
    background-color: #f5f7fa;
}

QComboBox {
    background-color: #ffffff;
    border: 1px solid #d0d5dd;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    color: #1a1a2e;
    min-height: 24px;
}
QComboBox:hover {
    border-color: #1565C0;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid #d0d5dd;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #d0d5dd;
    border-radius: 4px;
    selection-background-color: #E3F2FD;
    selection-color: #1565C0;
    padding: 4px;
}

QCheckBox {
    spacing: 8px;
    font-size: 13px;
    color: #1a1a2e;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid #b0bccf;
    background-color: #ffffff;
}
QCheckBox::indicator:hover {
    border-color: #1565C0;
}
QCheckBox::indicator:checked {
    background-color: #1565C0;
    border-color: #1565C0;
}

QTableWidget {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    gridline-color: #f0f0f0;
    selection-background-color: #E3F2FD;
    selection-color: #1a1a2e;
}
QTableWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #f5f5f5;
}
QTableWidget::item:hover {
    background-color: #f5f8ff;
}
QTableWidget::item:selected {
    background-color: #E3F2FD;
    color: #1565C0;
    font-weight: 500;
}

QHeaderView::section {
    background-color: #f5f7fa;
    color: #5f6368;
    padding: 8px 10px;
    border: none;
    border-bottom: 2px solid #e0e0e0;
    font-weight: bold;
    font-size: 12px;
}
QHeaderView::section:hover {
    background-color: #eef1f6;
}

QScrollBar:vertical {
    background-color: #f0f2f5;
    width: 12px;
    border-radius: 6px;
}
QScrollBar::handle:vertical {
    background-color: #c0c7d0;
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background-color: #a0aab8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background-color: #f0f2f5;
    height: 12px;
    border-radius: 6px;
}
QScrollBar::handle:horizontal {
    background-color: #c0c7d0;
    border-radius: 6px;
    min-width: 30px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #a0aab8;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

QStatusBar {
    background-color: #ffffff;
    border-top: 1px solid #e0e0e0;
    font-size: 12px;
    color: #5f6368;
    padding: 2px 8px;
}

QSplitter::handle {
    background-color: #e0e0e0;
    height: 4px;
    margin: 2px 0;
    border-radius: 2px;
}
QSplitter::handle:hover {
    background-color: #1565C0;
}

QLabel {
    background: transparent;
    color: #1a1a2e;
}
"""

# ===== 黑夜主题（MainWindow 专用）=====
DARK_QSS = """
/* ===== 全局默认 ===== */
QWidget {
    background-color: #1e1e2e;                    /* 深色基调 */
    color: #cdd6f4;                               /* 浅色文字 */
    font-family: "Microsoft YaHei", "Segoe UI", "PingFang SC", sans-serif;
    font-size: 13px;
}
QWidget:disabled {
    color: #6c7086;                               /* 禁用控件暗灰文字 */
}

QGroupBox {
    background-color: #313244;                     /* 面板色 */
    border: 1px solid #45475a;                    /* 细微边框 */
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
    background-color: #89b4fa;                    /* 蓝色标题徽章 */
    color: #1e1e2e;                               /* 亮徽章上深色文字 */
    border-radius: 4px;
    left: 10px;
    font-size: 12px;
    font-weight: bold;
}

QTabWidget::pane {
    border: 1px solid #45475a;
    border-radius: 8px;
    background-color: #1e1e2e;
    padding: 4px;
}
QTabBar::tab {
    background-color: #313244;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    margin-right: 4px;
    font-size: 13px;
    font-weight: 500;
    color: #a6adc8;
}
QTabBar::tab:hover {
    background-color: #45475a;
    color: #cdd6f4;
}
QTabBar::tab:selected {
    background-color: #89b4fa;                    /* 选中标签蓝色 */
    color: #1e1e2e;
    font-weight: bold;
}

QPushButton {
    background-color: #45475a;
    border: 1px solid #585b70;
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 13px;
    color: #cdd6f4;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #585b70;
    border-color: #6c7086;
}
QPushButton:pressed {
    background-color: #313244;
}
/* 主操作 - 生成 INP */
QPushButton#btnGenerate {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    font-weight: bold;
    font-size: 14px;
    padding: 8px 28px;
    border-radius: 8px;
}
QPushButton#btnGenerate:hover {
    background-color: #b4d0fb;
}
QPushButton#btnGenerate:pressed {
    background-color: #74a8f7;
}
/* 导入按钮 */
QPushButton#btnImport {
    background-color: #313244;
    color: #a6e3a1;                               /* 绿色强调 */
    border: 1px solid #45475a;
    font-weight: bold;
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 6px;
}
QPushButton#btnImport:hover {
    background-color: #45475a;
    border-color: #a6e3a1;
}
/* 主题切换按钮 */
QPushButton#btnTheme {
    background-color: #45475a;
    color: #f9e2af;                               /* 黄色强调 */
    border: 1px solid #585b70;
    font-weight: bold;
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 6px;
}
QPushButton#btnTheme:hover {
    background-color: #585b70;
    color: #f5c2e7;
}
/* 添加按钮 — 绿色 */
QPushButton[cssClass="btnAdd"] {
    background-color: #a6e3a1;
    color: #1e1e2e;
    border: none;
    font-weight: bold;
}
QPushButton[cssClass="btnAdd"]:hover {
    background-color: #94e2d5;
}
QPushButton[cssClass="btnAdd"]:pressed {
    background-color: #7dc98c;
}
/* 删除按钮 — 红色 */
QPushButton[cssClass="btnDelete"] {
    background-color: #f38ba8;
    color: #1e1e2e;
    border: none;
    font-weight: bold;
}
QPushButton[cssClass="btnDelete"]:hover {
    background-color: #f5a0b8;
}
QPushButton[cssClass="btnDelete"]:pressed {
    background-color: #e07090;
}
/* 编辑按钮 */
QPushButton[cssClass="btnEdit"] {
    background-color: #313244;
    color: #89b4fa;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 12px;
    font-weight: normal;
    min-height: 24px;
}
QPushButton[cssClass="btnEdit"]:hover {
    background-color: #45475a;
}
QPushButton[cssClass="btnEdit"]:pressed {
    background-color: #585b70;
}
/* 主操作按钮（通用） */
QPushButton[cssClass="btnPrimary"] {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    font-weight: bold;
    padding: 8px 24px;
    font-size: 14px;
}
QPushButton[cssClass="btnPrimary"]:hover {
    background-color: #b4d0fb;
}
QPushButton[cssClass="btnPrimary"]:pressed {
    background-color: #74a8f7;
}
/* 浏览按钮 */
QPushButton[cssClass="btnBrowse"] {
    background-color: #585b70;
    color: #cdd6f4;
    border: none;
    padding: 6px 14px;
}
QPushButton[cssClass="btnBrowse"]:hover {
    background-color: #6c7086;
}
QPushButton[cssClass="btnBrowse"]:pressed {
    background-color: #45475a;
}
/* 切换按钮 — 虚线边框 */
QPushButton[cssClass="btnToggle"] {
    background-color: transparent;
    border: 1px dashed #585b70;
    text-align: left;
    color: #a6adc8;
    padding: 4px 12px;
}
QPushButton[cssClass="btnToggle"]:hover {
    border-color: #89b4fa;
    color: #89b4fa;
    background-color: #313244;
}

QLineEdit {
    background-color: #313244;
    border: 1px solid #585b70;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}
QLineEdit:focus {
    border-color: #89b4fa;
    border-width: 2px;
    padding: 5px 9px;
}
QLineEdit:disabled {
    background-color: #181825;
    color: #6c7086;
}

QPlainTextEdit {
    background-color: #313244;
    border: 1px solid #585b70;
    border-radius: 6px;
    padding: 6px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 13px;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}
QPlainTextEdit:focus {
    border-color: #89b4fa;
}


QSpinBox, QDoubleSpinBox {
    background-color: #313244;
    border: 1px solid #585b70;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 13px;
    color: #cdd6f4;
    min-height: 24px;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #89b4fa;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #585b70;
    border-bottom: 1px solid #585b70;
    border-top-right-radius: 6px;
    background-color: #45475a;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border-left: 1px solid #585b70;
    border-bottom-right-radius: 6px;
    background-color: #45475a;
}

QComboBox {
    background-color: #313244;
    border: 1px solid #585b70;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    color: #cdd6f4;
    min-height: 24px;
}
QComboBox:hover {
    border-color: #89b4fa;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid #585b70;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}
QComboBox QAbstractItemView {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
    padding: 4px;
    color: #cdd6f4;
}

QCheckBox {
    spacing: 8px;
    font-size: 13px;
    color: #cdd6f4;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid #6c7086;
    background-color: #313244;
}
QCheckBox::indicator:hover {
    border-color: #89b4fa;
}
QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}

QTableWidget {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    gridline-color: #45475a;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
}
QTableWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #45475a;
}
QTableWidget::item:hover {
    background-color: #45475a;
}
QTableWidget::item:selected {
    background-color: #45475a;
    color: #89b4fa;
    font-weight: 500;
}

QHeaderView::section {
    background-color: #45475a;
    color: #a6adc8;
    padding: 8px 10px;
    border: none;
    border-bottom: 2px solid #585b70;
    font-weight: bold;
    font-size: 12px;
}
QHeaderView::section:hover {
    background-color: #585b70;
}

QScrollBar:vertical {
    background-color: #1e1e2e;
    width: 12px;
    border-radius: 6px;
}
QScrollBar::handle:vertical {
    background-color: #585b70;
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background-color: #6c7086;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background-color: #1e1e2e;
    height: 12px;
    border-radius: 6px;
}
QScrollBar::handle:horizontal {
    background-color: #585b70;
    border-radius: 6px;
    min-width: 30px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #6c7086;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

QStatusBar {
    background-color: #313244;
    border-top: 1px solid #45475a;
    font-size: 12px;
    color: #a6adc8;
    padding: 2px 8px;
}

QSplitter::handle {
    background-color: #45475a;
    height: 4px;
    margin: 2px 0;
    border-radius: 2px;
}
QSplitter::handle:hover {
    background-color: #89b4fa;
}

QLabel {
    background: transparent;
    color: #cdd6f4;
}
"""
