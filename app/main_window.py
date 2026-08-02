"""
MCNP Input Card Generator — Main Window
主窗口：管理标签页、生成/保存操作、设置默认路径

This module defines the MainWindow class, the central orchestrator of the
MCNP input card generator application. It manages tab switching, data collection
across all tabs, INP file generation, project save/load, INP import via file
dialog or drag-and-drop, xsdir loading, MCNP detection, and theme toggling.
"""

import os
from PyQt5.QtCore import Qt, QSettings, QEvent, QTimer, QVariantAnimation, QObject, QPropertyAnimation, pyqtProperty, QEasingCurve
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QPixmap, QPainter, QColor, QPen, QIcon, QFont, QKeySequence
from PyQt5.QtWidgets import (
    QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QWidget, QFileDialog, QMessageBox,
    QLabel, QLineEdit, QStatusBar, QInputDialog,
    QAction, QMenuBar, QComboBox, QApplication,
    QSpinBox, QDoubleSpinBox, QShortcut, QGraphicsOpacityEffect,
)

from app._version import APP_TITLE
from app.xsdir_db import DB as xsdir_db
from app.style import LIGHT_QSS, DARK_QSS, PINK_QSS, TRADITIONAL_QSS, PALETTES
from app.mcnp_detector import detect_mcnp
from app.xsdir_manager import find_xsdir_from_env, load_xsdir
from app.project_io import deck_to_dict, deck_from_dict, save_project_file, load_project_file
from app.inp_importer import import_inp_file
from app.tabs.basic_settings import BasicSettingsTab
from app.tabs.geometry import GeometryTab
from app.tabs.material import MaterialTab
from app.tabs.sdef import SdefTab
from app.tabs.tally import TallyTab
from app.tabs.advanced import AdvancedTab
from app.tabs.output import OutputTab
from app.widgets.reference_viewer import make_help_button
from app.widgets.ui_helpers import make_avatar
from app.models import DeckData, TallySettings
from app.generator.inp_generator import generate_inp_from_deck
from app.generator.validator import validate_deck


def _make_icon(draw_fn, size=20, color="#888888"):
    pm = QPixmap(size, size); pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(color), 1.5, Qt.SolidLine, Qt.RoundCap))
    draw_fn(p, size); p.end()
    return QIcon(pm)


class _WheelBlocker(QObject):
    """全局拦截 QComboBox/QSpinBox/QDoubleSpinBox 的滚轮事件，防止悬停误改值"""
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and isinstance(
            obj, (QComboBox, QSpinBox, QDoubleSpinBox)
        ):
            event.ignore()
            return True
        return super().eventFilter(obj, event)


class _SidebarButton(QPushButton):
    """侧边栏按钮：hover 时字体亮度渐变，checked 时白色"""
    def __init__(self, icon_fn, text, parent=None):
        super().__init__(parent)
        self._icon_fn = icon_fn
        self._brightness = 0
        self._icon_color = "#888888"
        self._hover_color = "#FFFFFF"
        self.setText(text)
        self.setCheckable(True)
        self.setProperty("sideBtn", "true")
        self.setFixedHeight(40)
        # hover 动画
        self._anim = QPropertyAnimation(self, b"brightness")
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        # 缓存 QIcon
        self._pix = None

    def set_hover_color(self, color):
        self._hover_color = color

    def enterEvent(self, event):
        self._anim.stop()
        self._anim.setStartValue(self._brightness)
        self._anim.setEndValue(100)
        self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.isChecked():
            self._anim.stop()
            self._anim.setStartValue(self._brightness)
            self._anim.setEndValue(0)
            self._anim.start()
        super().leaveEvent(event)

    def _on_checked(self, checked):
        if checked:
            self._anim.stop()
            self._brightness = 100
        else:
            self._anim.stop()
            self._brightness = 0

    def nextCheckState(self):
        super().nextCheckState()
        self._on_checked(self.isChecked())

    @pyqtProperty(int)
    def brightness(self):
        return self._brightness

    @brightness.setter
    def brightness(self, val):
        self._brightness = val
        alpha = int(val * 0.7 / 100 * 255)
        if val > 0 and not self.isChecked():
            self.setStyleSheet(f"color: rgba({','.join(str(int(self._hover_color[i:i+2],16)) for i in (1,3,5))},{alpha}) !important;")
        elif self.isChecked():
            self.setStyleSheet("color: white !important;")
        else:
            self.setStyleSheet("")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = 18; ix = 10; iy = (self.height() - side) // 2
        if self._pix is None:
            self._pix = QPixmap(side, side); self._pix.fill(Qt.transparent)
            ip = QPainter(self._pix)
            ip.setRenderHint(QPainter.Antialiasing)
            ip.setPen(QPen(QColor(self._icon_color), 1.5)); ip.setBrush(Qt.NoBrush)
            self._icon_fn(ip, side)
            ip.end()
        p.drawPixmap(ix, iy, self._pix)
        # 文字在图标右边
        text_rect = self.rect().adjusted(34, 0, 0, 0)
        p.setPen(QColor(self._icon_color))
        p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())
        p.end()


    def update_icon_colors(self, color):
        self._icon_color = color
        for btn in self.buttons:
            btn._icon_color = color
            btn._pix = None
            btn.update()
        for w in [self.btn_import, self.btn_theme]:
            if hasattr(w, '_SidebarButton__icon_color'):
                pass

class _Sidebar(QWidget):
    """侧边栏：7 个导航按钮 + 底部导入/主题按钮"""
    def __init__(self, parent=None, icon_color="#888888"):
        super().__init__(parent)
        self._icon_color = icon_color
        self.setObjectName("sideBar")
        self.setFixedWidth(56)
        self.setMouseTracking(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(4)

        nav_icons = [
            (lambda p,s: (p.drawRect(2,2,s-4,s-4) or p.drawText(s//2,s//2+2,"P")), "基本设置"),
            (lambda p,s: (p.drawRect(2,2,s-4,s-4) or p.drawText(s//2,s//2+2,"M")), "材料"),
            (lambda p,s: (p.drawRect(2,2,s-4,s-4) or p.drawText(s//2,s//2+2,"S")), "几何"),
            (lambda p,s: (p.drawRect(2,2,s-4,s-4) or p.drawText(s//2,s//2+2,"Src")), "源项"),
            (lambda p,s: (p.drawRect(2,2,s-4,s-4) or p.drawText(s//2,s//2+2,"T")), "计数"),
            (lambda p,s: (p.drawEllipse(3,3,s-6,s-6) or p.drawText(s//2,s//2+2,"A")), "高级"),
            (lambda p,s: (p.drawRect(2,2,s-4,s-4) or p.drawText(s//2,s//2+2,"O")), "输出"),
        ]

        self.buttons = []
        for i, (fn, text) in enumerate(nav_icons):
            btn = _SidebarButton(fn, text)
            btn._icon_color = self._icon_color
            btn.setToolTip(text)
            btn.clicked.connect(lambda checked, idx=i: self._on_click(idx))
            if i == 0: btn.setChecked(True)
            layout.addWidget(btn)
            self.buttons.append(btn)

        layout.addStretch()

        self.btn_import = QPushButton("📥")
        self.btn_import.setToolTip("导入 INP 输入卡")
        self.btn_import.setProperty("sideBtn", "true")
        self.btn_import.setFixedHeight(40)
        layout.addWidget(self.btn_import)

        self.btn_theme = QPushButton("🎨")
        self.btn_theme.setToolTip("切换主题")
        self.btn_theme.setProperty("sideBtn", "true")
        self.btn_theme.setFixedHeight(40)
        layout.addWidget(self.btn_theme)

        self._click_handler = None
        self._orig_width = 56

    def _on_click(self, idx):
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == idx)
        # 点击后缩回
        self._animate_width(56)
        if self._click_handler:
            self._click_handler(idx)

    def on_click(self, handler):
        self._click_handler = handler

    def enterEvent(self, event):
        self._animate_width(160)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_width(56)
        super().leaveEvent(event)

    def _animate_width(self, target):
        if hasattr(self, '_width_anim') and self._width_anim:
            self._width_anim.stop()
        self._width_anim = QVariantAnimation(self)
        self._width_anim.setDuration(200)
        self._width_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._width_anim.setStartValue(self.width())
        self._width_anim.setEndValue(target)
        self._width_anim.valueChanged.connect(lambda v: self.setFixedWidth(v))
        self._width_anim.start()

    def set_theme_label(self, text):
        if hasattr(self, 'btn_theme') and self.btn_theme:
            self.btn_theme.setText(f"🎨 {text}")


class _BreathingDot(QWidget):
    """呼吸灯 — 就绪状态指示"""
    def __init__(self, color="#10B981", size=7, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._opacity = 0.4  # 必须在动画启动前初始化
        self._anim = QPropertyAnimation(self, b"opacity_val")
        self._anim.setDuration(2000)
        self._anim.setStartValue(0.4)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.InOutSine)
        self._anim.setLoopCount(-1)
        self._anim.start()

    @pyqtProperty(float)
    def opacity_val(self):
        return self._opacity

    @opacity_val.setter
    def opacity_val(self, val):
        self._opacity = val
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(self._color)
        c.setAlphaF(self._opacity)
        p.setBrush(c); p.setPen(Qt.NoPen)
        size = min(self.width(), self.height()) - 4
        p.drawEllipse(2, 2, size, size)
        p.end()


class MainWindow(QMainWindow):
    """MCNP 输入卡生成器主窗口
    Main application window that orchestrates all tabs, generation, import, save/load,
    xsdir management, MCNP detection, and theme switching."""

    def __init__(self):
        """Initialize the main window: load persisted settings, detect MCNP, build UI."""
        super().__init__()
        # 全局拦截滚轮误改 QComboBox/QSpinBox 值
        _app = QApplication.instance()
        if _app:
            _app.installEventFilter(_WheelBlocker(_app))
        # Persistent application settings stored via QSettings (registry on Windows)
        self.settings = QSettings("MCNPGen", "MCNPGenerator")
        self.mcnp_exe = "mcnp6.exe"  # 默认 default MCNP executable
        # Load theme preference from saved settings ("light" | "dark" | "pink" | "traditional")
        self.theme_mode = self.settings.value("theme_mode", "light")
        self.init_ui()
        self._connect_signals()
        self._detect_mcnp()
        self._apply_theme()

    def init_ui(self):
        """初始化界面 Build the complete user interface: menus, tabs, toolbar, status bar."""
        self.setWindowTitle(APP_TITLE)
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)
        self.setAcceptDrops(True)  # Enable drag-and-drop for INP files
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # DWM 阴影
        try:
            import ctypes
            ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(
                int(self.winId()), ctypes.byref(ctypes.c_int(-1)))
            # Windows 11 原生圆角
            hwnd = ctypes.wintypes.HWND(int(self.winId()))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(ctypes.c_int(2)),
                ctypes.sizeof(ctypes.c_int))
        except:
            pass
        # 全局字体抗锯齿
        _fnt = QFont("Microsoft YaHei", 9)
        _fnt.setStyleStrategy(QFont.PreferAntialias)
        app = QApplication.instance()
        if app: app.setFont(_fnt)

        # 快捷键
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._save_project)
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self._load_project)
        QShortcut(QKeySequence("Ctrl+I"), self).activated.connect(self._import_inp)
        self.menuBar().setVisible(False)

        # 中央部件
        central = QWidget()
        central.setObjectName("centralContainer")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== 顶栏：用户头像 + 标题 + 状态信息 + 窗口控制按钮 =====
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(12, 6, 12, 4)

        _display_name = ""
        try:
            import ctypes
            _buf = ctypes.create_unicode_buffer(256)
            _sz = ctypes.c_ulong(256)
            if ctypes.windll.secur32.GetUserNameExW(3, _buf, ctypes.byref(_sz)):
                _display_name = _buf.value.strip()
        except: pass
        if not _display_name:
            _display_name = os.environ.get("USERNAME", "")
        if not _display_name:
            _display_name = "U"

        avatar = make_avatar(_display_name[0], 26)
        avatar.setToolTip("查看 C810 参考文档")
        avatar.mousePressEvent = lambda e: self._show_c810_reference()
        top_bar.addWidget(avatar)
        top_bar.addSpacing(8)

        title_lbl = QLabel(APP_TITLE)
        title_lbl.setStyleSheet("font-weight:600; font-size:13px; border:none; background:transparent;")
        top_bar.addWidget(title_lbl)
        top_bar.addSpacing(20)

        # 呼吸灯 + 状态
        self._ready_dot = _BreathingDot()
        top_bar.addWidget(self._ready_dot)
        top_bar.addSpacing(4)
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("border:none; background:transparent; font-size:11px; color:#4169E1;")
        top_bar.addWidget(self.status_label)
        top_bar.addSpacing(12)

        self.status_mcnp = QLabel("")
        self.status_mcnp.setStyleSheet("border:none; background:transparent; font-size:11px;")
        self.status_mcnp.setCursor(Qt.PointingHandCursor)
        self.status_mcnp.installEventFilter(self)
        top_bar.addWidget(self.status_mcnp)
        top_bar.addSpacing(12)

        self.status_xsdir = QLabel("")
        self.status_xsdir.setStyleSheet("border:none; background:transparent; font-size:11px;")
        top_bar.addWidget(self.status_xsdir)
        top_bar.addStretch()

        # 窗口控制按钮（最右）
        win_btn_style = (
            "QPushButton{background:transparent;border:none;font-size:14px;"
            "border-radius:4px;color:#888;}"
            "QPushButton:hover{background:rgba(128,128,128,0.25);color:#fff;}"
        )
        self._btn_max = None
        for sym, tip, slot in [
            ("─", "最小化", self.showMinimized),
            ("□", "最大化", lambda: self.showNormal() if self.isMaximized() else self.showMaximized()),
            ("✕", "关闭", self.close),
        ]:
            btn = QPushButton(sym)
            btn.setFixedSize(42, 26)
            btn.setToolTip(tip)
            if sym == "✕":
                btn.setStyleSheet(
                    "QPushButton{background:transparent;border:none;font-size:14px;"
                    "border-radius:4px;color:#888;}"
                    "QPushButton:hover{background:#E81123;color:white;}"
                )
            else:
                btn.setStyleSheet(win_btn_style)
            btn.clicked.connect(slot)
            top_bar.addWidget(btn)
            if sym in ("□", "❐"):
                self._btn_max = btn

        main_layout.addLayout(top_bar)

        # ===== 主体：侧边栏（左）+ 右列（标签页 + 工具栏） =====
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self._sidebar = _Sidebar()
        self._sidebar.on_click(self._switch_tab)
        self._sidebar.btn_import.clicked.connect(self._import_inp)
        self._sidebar.btn_theme.clicked.connect(self._toggle_theme)
        body_layout.addWidget(self._sidebar)

        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 工具栏：输出目录 / 浏览 / 后缀 / 生成 INP
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(16, 8, 16, 8)

        self.path_edit = QLineEdit()
        saved_path = self.settings.value("output_path", "")
        if saved_path and os.path.isdir(saved_path):
            self.path_edit.setText(saved_path)
        self.path_edit.setPlaceholderText("选择输出目录…")
        self.path_edit.setToolTip("INP 文件和 run.bat 的保存目录")
        btn_browse = QPushButton("浏览…")
        btn_browse.setToolTip("选择输出目录")
        btn_browse.setProperty("cssClass", "btnBrowse")
        btn_browse.clicked.connect(self._browse_path)

        self.suffix_combo = QComboBox()
        self.suffix_combo.addItems([".i", ".inp", ".txt", ""])
        saved_suffix = self.settings.value("inp_suffix", ".i")
        idx = self.suffix_combo.findText(saved_suffix)
        self.suffix_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.suffix_combo.setToolTip("INP 输入卡文件后缀")
        self.suffix_combo.setMaximumWidth(70)
        self.suffix_combo.currentTextChanged.connect(
            lambda t: self.settings.setValue("inp_suffix", t))

        self.btn_generate = QPushButton("⚡ 生成 INP")
        self.btn_generate.setObjectName("btnGenerate")
        self.btn_generate.setToolTip("校验后生成 MCNP 输入卡")
        self.btn_generate.clicked.connect(self._on_generate)

        toolbar.addWidget(QLabel("输出目录:"))
        toolbar.addWidget(self.path_edit, 1)
        toolbar.addWidget(btn_browse)
        toolbar.addSpacing(16)
        toolbar.addWidget(QLabel("后缀:"))
        toolbar.addWidget(self.suffix_combo)
        toolbar.addWidget(self.btn_generate)
        right_layout.addLayout(toolbar)

        # 标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.tabBar().hide()  # 用侧边栏切换

        self.tab_basic = BasicSettingsTab()
        self.tab_mat = MaterialTab(self)
        self.tab_geo = GeometryTab(self)
        self.tab_sdef = SdefTab()
        self.tab_tally = TallyTab()
        self.tab_advanced = AdvancedTab()
        self.tab_output = OutputTab()

        self.tab_tally.talliesChanged.connect(self._update_en_preview)

        self.tab_widget.addTab(self.tab_basic, "📄 基本设置")
        self.tab_widget.addTab(self.tab_mat, "🧪 材料")
        self.tab_widget.addTab(self.tab_geo, "📐 几何")
        self.tab_widget.addTab(self.tab_sdef, "🎯 源项")
        self.tab_widget.addTab(self.tab_tally, "📊 计数")
        self.tab_widget.addTab(self.tab_advanced, "⚙ 高级")
        self.tab_widget.addTab(self.tab_output, "📈 输出")

        right_layout.addWidget(self.tab_widget, 1)
        body_layout.addWidget(right_col, 1)
        main_layout.addWidget(body, 1)

        # 状态栏（半透明叠加在底部）
        sb = QStatusBar()
        sb.setObjectName("customStatusBar")
        contact = QLabel("🐛 联系")
        contact.setToolTip("发现 BUG 或功能建议请联系: 1378963177@qq.com")
        contact.setCursor(Qt.PointingHandCursor)
        sb.addPermanentWidget(contact)
        main_layout.addWidget(sb)

        QTimer.singleShot(200, self._load_xsdir)

    # ---------- 原生消息 ----------

    def nativeEvent(self, eventType, message):
        try:
            import ctypes
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == 0x84:  # WM_NCHITTEST
                lx = self.cursor().pos().x() - self.x()
                ly = self.cursor().pos().y() - self.y()
                if not self.isMaximized():
                    r = 6; w, h = self.width(), self.height()
                    top = ly < r; bot = ly > h - r; left = lx < r; right = lx > w - r
                    if top and left:   return True, 13
                    if top and right:  return True, 14
                    if bot and left:   return True, 16
                    if bot and right:  return True, 17
                    if top:            return True, 12
                    if bot:            return True, 15
                    if left:           return True, 10
                    if right:          return True, 11
                if ly < 40:
                    cw = self.centralWidget()
                    if cw:
                        child = cw.childAt(lx, ly)
                        if child is not None and isinstance(child, QPushButton):
                            return True, 1
                    return True, 2
        except:
            pass
        return super().nativeEvent(eventType, message)

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange and hasattr(self, '_btn_max') and self._btn_max:
            self._btn_max.setText("❐" if self.isMaximized() else "□")
        super().changeEvent(event)

    # ---------- 侧边栏切换 ----------

    def _switch_tab(self, idx: int):
        self.tab_widget.setCurrentIndex(idx)

    # ---------- 主题 ----------

    def _apply_theme(self):
        """应用当前主题"""
        from app.style import PALETTES
        theme_qss = {"light": LIGHT_QSS, "dark": DARK_QSS, "pink": PINK_QSS, "traditional": TRADITIONAL_QSS}
        self.setStyleSheet(theme_qss.get(self.theme_mode, LIGHT_QSS))
        cw = self.findChild(QWidget, "centralContainer")
        pal = PALETTES.get(self.theme_mode, PALETTES["light"])
        if cw:
            cw.setStyleSheet(
                f"#centralContainer {{ background: {pal['bg_window']}; border-radius: 10px; }}"
            )
        if hasattr(self, '_sidebar'):
            for btn in self._sidebar.buttons[:7]:
                if hasattr(btn, 'set_hover_color'):
                    btn.set_hover_color(pal['text_primary'])
        # 更新曲面/TR 高亮色
        if hasattr(self, 'tab_geo'):
            if hasattr(self.tab_geo, '_surf_hl'):
                self.tab_geo._surf_hl.set_colors(pal)
            if hasattr(self.tab_geo, '_tr_hl'):
                self.tab_geo._tr_hl.set_colors(pal)

    def _toggle_theme(self):
        """四档循环切换主题（截图覆盖淡出）"""
        cycle = {"light": "dark", "dark": "pink", "pink": "traditional", "traditional": "light"}
        self.theme_mode = cycle.get(self.theme_mode, "light")
        self.settings.setValue("theme_mode", self.theme_mode)
        if hasattr(self, '_theme_fade') and self._theme_fade:
            self._theme_fade.stop()
        cw = self.centralWidget()
        if not cw:
            self._apply_theme(); return
        snapshot = cw.grab()
        QTimer.singleShot(0, lambda: self._do_theme_transition(snapshot))

    def _do_theme_transition(self, snapshot):
        cw = self.centralWidget()
        if not cw: return
        overlay = QLabel(cw)
        overlay.setPixmap(snapshot)
        overlay.setGeometry(cw.rect())
        overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        overlay.show(); overlay.raise_()
        self._apply_theme()
        cn_map = {"light": "白天模式", "dark": "黑夜模式", "pink": "多巴胺模式", "traditional": "护眼模式"}
        if hasattr(self, '_sidebar'):
            self._sidebar.set_theme_label(cn_map.get(self.theme_mode, "白天模式"))
        effect = QGraphicsOpacityEffect(overlay)
        overlay.setGraphicsEffect(effect)
        self._theme_fade = QPropertyAnimation(effect, b"opacity")
        self._theme_fade.setDuration(200)
        self._theme_fade.setStartValue(1.0)
        self._theme_fade.setEndValue(0.0)
        self._theme_fade.finished.connect(overlay.deleteLater)
        self._theme_fade.start()

    # ---------- 事件过滤器 ----------

    def eventFilter(self, obj, event):
        """事件过滤器：双击最大化 + status_mcnp 点击"""
        if event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
            pos = self.mapFromGlobal(event.globalPos())
            if pos.y() < 40:
                cw = self.centralWidget()
                if cw:
                    child = cw.childAt(cw.mapFromGlobal(event.globalPos()))
                    if child is None or not isinstance(child, QPushButton):
                        if self.isMaximized(): self.showNormal()
                        else: self.showMaximized()
                        return True
        if obj is self.status_mcnp and event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._change_mcnp()
            return True
        return super().eventFilter(obj, event)

    # ---------- 截面库 ----------

    def _load_xsdir(self):
        """加载截面库索引（优先级：QSettings → 环境变量 → 弹窗提醒）
        Load the xsdir cross-section library index with fallback priority:
        1. Previously saved path in QSettings
        2. Auto-detect from environment variable DATAPATH or similar
        3. Show a warning dialog prompting manual selection"""
        saved_path = self.settings.value("xsdir_path", "")
        ok, count = False, 0
        # Priority 1: try the path previously saved in QSettings
        if saved_path:
            ok, count = load_xsdir(saved_path)
        if ok:
            self._update_xsdir_status(count, "✓ 截面库 {n} 条")
            self.tab_advanced._refresh_xsdir_status()
            return

        # QSettings 未指定 → 尝试从环境变量自动发现
        # Priority 2: QSettings empty — try auto-discovery from environment variables
        env_path = find_xsdir_from_env()
        if env_path:
            self.settings.setValue("xsdir_path", env_path)
            ok, count = load_xsdir(env_path)
            if ok:
                self._update_xsdir_status(count, "✓ 截面库 {n} 条（来自环境变量）")
                self.tab_advanced.xsdir_edit.setText(env_path)
                self.tab_advanced._refresh_xsdir_status()
                return

        # 环境变量也没有 → 弹窗提醒
        # Priority 3: no xsdir found anywhere — warn the user and redirect to advanced tab
        self.status_xsdir.setText("⚠ 未加载截面库")
        self.status_xsdir.setStyleSheet("color: #c62828; font-size: 11px; padding: 0 8px;")
        QTimer.singleShot(150, self._warn_xsdir_missing)

    def _update_xsdir_status(self, count: int, template: str):
        """Update the xsdir status label in the status bar.

        Args:
            count: Number of nuclides loaded from the xsdir file.
            template: Message template with {n} placeholder for the count.
        """
        msg = template.replace("{n}", str(count))
        self.status_xsdir.setText(msg)
        self.status_xsdir.setStyleSheet("color: #2e7d32; font-size: 11px; padding: 0 8px;")

    def _load_xsdir_path(self, path: str) -> tuple[bool, int]:
        """加载指定路径的 xsdir，返回 (ok, count)
        Load xsdir from a given file path.

        Args:
            path: Full path to the xsdir file.

        Returns:
            A tuple of (ok: bool, count: int) indicating success and number of entries loaded.
        """
        ok, count = load_xsdir(path)
        return ok, count

    def _warn_xsdir_missing(self):
        """弹窗提醒 xsdir 未加载，并跳转到高级标签页
        Show a warning dialog when no xsdir file is loaded,
        then switch to the Advanced tab so the user can set it manually."""
        self.tab_widget.setCurrentIndex(6)  # 0基本设置 1材料 2几何 3源项 4计数 5能谱 6高级
        QMessageBox.warning(
            self, "截面库未加载",
            "未找到 MCNP 截面库索引文件 (xsdir)。\n\n"
            "请在「高级」标签页中指定 xsdir 文件路径，\n"
            "以确保材料卡 ZAID 能够正确校验。\n\n"
            "常见路径：D:\\MCNP\\MCNP6\\MCNP_DATA\\xsdir"
        )

    def _detect_mcnp(self):
        """自动检测用户安装的 MCNP 版本
        Auto-detect the user's installed MCNP version.
        Checks common installation paths and the saved executable path.
        Updates the status bar with the detected version."""
        saved = self.settings.value("mcnp_exe", "")
        exe, label, found = detect_mcnp(saved)
        self.mcnp_exe = exe
        if found:
            # Persist the detected executable path
            self.settings.setValue("mcnp_exe", exe)
            self._update_mcnp_status(label)
        else:
            # MCNP not found — show warning state in status bar
            self._update_mcnp_status("MCNP?")
            self.status_mcnp.setToolTip("未检测到 MCNP，点击手动设置 MCNP not detected, click to set manually")
            self.status_mcnp.setStyleSheet("color: #c62828; font-size: 11px; padding: 0 8px;")

    def _update_mcnp_status(self, label: str):
        """Update the MCNP status label in the status bar.

        Args:
            label: Display label for the detected MCNP version (e.g., "MCNP6").
        """
        self.status_mcnp.setText(f"⚡ {label}")
        self.status_mcnp.setStyleSheet("color: #2e7d32; font-size: 11px; padding: 0 8px;")
        self.status_mcnp.setToolTip(f"当前: {self.mcnp_exe}  |  点击切换版本 Current: {self.mcnp_exe} | Click to switch version")

    def _change_mcnp(self):
        """弹出版本选择对话框
        Show a dialog to let the user select between MCNP versions (MCNP5 / MCNP6).
        Updates the persisted setting and status bar on selection."""
        choices = ["MCNP6 (mcnp6.exe)", "MCNP5 (mcnp5.exe)"]
        current = 0 if "6" in self.mcnp_exe else 1
        choice, ok = QInputDialog.getItem(
            self, "选择 MCNP 版本",
            "选择安装的 MCNP 版本：", choices, current, False
        )
        if ok and choice:
            label, exe = choice.split(" (")
            exe = exe.rstrip(")")
            self.mcnp_exe = exe
            self.settings.setValue("mcnp_exe", exe)
            self._update_mcnp_status(label)
            self.status_mcnp.setToolTip(f"当前: {self.mcnp_exe}  |  点击切换版本 Current: {self.mcnp_exe} | Click to switch version")

    def _browse_xsdir(self):
        """手动选择 xsdir 文件
        Open a file dialog for the user to manually select an xsdir file.
        Persists the chosen path and reloads the library index."""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 xsdir 截面库索引文件",
            "D:\\", "xsdir (xsdir);;所有文件 (*.*)"
        )
        if path:
            self.settings.setValue("xsdir_path", path)
            self._load_xsdir()

    def _connect_signals(self):
        """连接材料→栅元的联动信号
        Connect cross-tab signals:
        When a material is added, notify the Geometry tab to optionally create a cell for it."""
        # 材料新增时通知几何标签页
        # Notify the geometry tab when a new material is added
        self.tab_mat.material_added.connect(
            lambda mat_num: self.tab_geo.add_cell_for_material(mat_num)
        )

    def _browse_path(self):
        """选择输出目录
        Open a directory chooser for the output path.
        Updates the path text field and persists the selection."""
        path = QFileDialog.getExistingDirectory(
            self, "选择输出目录", self.path_edit.text()
        )
        if path:
            self.path_edit.setText(path)
            self.settings.setValue("output_path", path)

    def _on_generate(self):
        """生成 INP 前的校验 + 预览
        Main INP generation entry point:
        1. Collect data from all tabs into a DeckData object
        2. Validate the deck for completeness and correctness
        3. If validation passes, generate the INP text
        4. Show a preview dialog (PreviewDialog) with options to save and run"""
        # 收集数据 → 构建 DeckData（复用 _collect_deck）
        # Collect all tab data into a unified DeckData structure
        deck = self._collect_deck()

        # 校验 Validate the deck
        errors = validate_deck(deck)

        if errors:
            # Show all validation errors at once
            msg = "\n\n".join(f"❌ {e}" for e in errors)
            QMessageBox.critical(self, "校验未通过 Validation Failed", msg)
            return

        # 生成 INP Proceed to generation
        output_dir = self.path_edit.text().strip()
        if not output_dir or not os.path.isdir(output_dir):
            QMessageBox.critical(self, "错误 Error", "输出目录不存在，请先设置有效的输出路径 Output directory does not exist, please set a valid output path")
            return

        # Derive a safe file name from the deck title
        title = deck.basic.title.strip() or "MCNP_Input"
        safe_name = "".join(c for c in title if c.isalnum() or c in " _-").strip().replace(" ", "_")
        if not safe_name:
            safe_name = "MCNP_Input"
        # Append the user-selected suffix
        suffix = self.suffix_combo.currentText().strip()
        filename = safe_name + suffix

        try:
            # 收集文本模式覆盖
            # Collect raw (text-mode) overrides from tabs that support them
            raw_overrides = {}
            for tab in [self.tab_mat, self.tab_geo, self.tab_sdef,
                        self.tab_tally, self.tab_advanced]:
                raw_overrides.update(tab.get_raw_overrides())

            # Generate the INP file content as a string
            inp_content = generate_inp_from_deck(deck, raw_overrides=raw_overrides)

            # 预览对话框 Show the preview dialog with save/run options
            from app.dialogs.preview_dialog import PreviewDialog
            dialog = PreviewDialog(inp_content, output_dir, filename, self, mcnp_exe=self.mcnp_exe)
            dialog.exec_()

        except Exception as e:
            QMessageBox.critical(self, "生成失败 Generation Failed", f"生成 INP 文件时出错:\n{str(e)}")

    def _merge_tally_settings(self):
        """合并计数标签页和能谱标签页的数据 → TallySettings

        tally_tab 返回 {"tallies": list[TallyDefinition], "e_min":..., "e_cards_text":...}，
        CUT 参数来自 advanced_tab。
        若 En 文本区为空则自动从 tallies × E0 生成 En 卡。
        """
        import sys
        tally_data = self.tab_tally.get_data()
        # CUT 数据现在在 advanced_tab
        energy_data = self.tab_advanced.get_cut_data().__dict__ if hasattr(self.tab_advanced, 'get_cut_data') else {}
        energy_data.pop('tallies', None)  # __dict__ 含默认 tallies=[], 与下面关键字冲突
        tallies = tally_data.get("tallies", [])

        # E0/En 从 tally_tab 获取
        e_cards_text = tally_data.get("e_cards_text", "").strip()
        if not e_cards_text:
            en_tallies = [td for td in tallies if td.generate_en]
            if en_tallies:
                tally_nums = sorted(set(td.number for td in en_tallies))
                e0_min = tally_data.get("e_min", "")
                e0_max = tally_data.get("e_max", "")
                e0_bins = tally_data.get("e_bins", 0)
                e0_log = tally_data.get("e_log", False)
                if e0_min and e0_max and e0_bins:
                    grid_syntax = "log" if e0_log else "i"
                    e_lines = [f"E{n}  {e0_min} {e0_bins}{grid_syntax} {e0_max}"
                              for n in tally_nums]
                    tally_data["e_cards_text"] = "\n".join(e_lines)

        # E0 字段合并到 energy_data（来自 tally_tab）
        for k in ("e_min","e_max","e_bins","e_log","e_custom_enabled","e_custom_text","e_cards_text",
                   "t0_min","t0_max","t0_bins","t0_log","t0_custom_enabled","t0_custom_text","t0_text",
                   ):
            if k in tally_data:
                energy_data[k] = tally_data[k]
        return TallySettings(tallies=tallies, **energy_data)

    # ---------- INP 导入 INP Import ----------

    def _import_inp(self):
        """菜单/按钮触发：弹出文件对话框选择 INP 文件导入
        Triggered by menu action or import button.
        Opens a file dialog for selecting an INP file, then delegates to _do_import."""
        path, _ = QFileDialog.getOpenFileName(
            self, "导入 MCNP 输入卡 Import MCNP Input Card",
            self.path_edit.text() or "D:\\",
            "MCNP 输入卡 (*.i *.inp *.txt);;所有文件 (*.*)"
        )
        if path:
            self._do_import(path)

    # ---------- 项目保存/加载 Project Save/Load ----------

    def _save_project(self):
        """将当前所有标签页数据保存为 JSON 项目文件
        Save all current tab data to a JSON project file.
        Collects data from all tabs via _collect_deck, then serializes to disk."""
        path, _ = QFileDialog.getSaveFileName(
            self, "保存项目 Save Project", "D:\\MCNP\\project.json",
            "JSON 文件 (*.json);;所有文件 (*.*)"
        )
        if not path:
            return
        try:
            deck = self._collect_deck()
            save_project_file(deck, path)
            QMessageBox.information(self, "保存成功 Save Succeeded", f"项目已保存到:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败 Save Failed", str(e))

    def _load_project(self):
        """从 JSON 项目文件恢复所有标签页数据
        Load a JSON project file and restore all tab data from it.
        Reads the file, parses it into a DeckData object, then backfills all tabs."""
        path, _ = QFileDialog.getOpenFileName(
            self, "加载项目 Load Project", "D:\\MCNP\\",
            "JSON 文件 (*.json);;所有文件 (*.*)"
        )
        if not path:
            return
        # Step 1: read raw JSON data from file
        try:
            data = load_project_file(path)
        except Exception as e:
            QMessageBox.critical(self, "读取失败 Read Failed", f"无法读取文件:\n{e}")
            return
        # Step 2: parse raw dict into DeckData model
        try:
            deck = deck_from_dict(data)
        except Exception as e:
            QMessageBox.critical(self, "解析失败 Parse Failed", f"项目文件格式错误:\n{e}")
            return
        # Step 3: populate all tabs from the deserialized deck
        self._backfill_tabs(deck)
        QMessageBox.information(self, "加载成功 Load Succeeded",
            f"项目已加载，共 {len(deck.cells)} 个栅元、"
            f"{len(deck.materials)} 个材料、{len(deck.sources)} 个源"
            f"Project loaded: {len(deck.cells)} cells, {len(deck.materials)} materials, {len(deck.sources)} sources")

    def _backfill_tabs(self, deck: DeckData):
        """将 DeckData 回填到所有标签页（导入/加载共用）
        Populate all tab widgets from a DeckData object.
        Used by both INP import and project load operations.

        Args:
            deck: The DeckData object containing all problem settings.
        """
        self.tab_basic.set_data(deck.basic)
        self.tab_geo.set_data(deck.surfaces, deck.cells)
        self.tab_mat.set_data(deck.materials)
        self.tab_sdef.set_data(deck.sources, deck.adv)
        self.tab_tally.set_data(deck.tally)
        self.tab_advanced.set_data(deck.adv)
        self.tab_advanced.set_cut_data(deck.tally)
        # MODE 同步 CUT 显隐
        self._update_en_preview()

    # ---------- 序列化辅助 Serialization Helpers ----------


    def _update_en_preview(self):
        """计数卡 En/Tn 勾选变化时更新预览"""
        import json
        tally_data = self.tab_tally.get_data()
        tallies = tally_data.get("tallies", [])
        self.tab_tally.update_en_preview(tallies)
        self.tab_tally.update_tn_preview(tallies, tally_data)

    def _sync_cut_visibility(self, basic):
        """MODE 变化时同步 CUT 行显隐"""
        # CUT 全部显示，不再依赖 MODE
        pass

    def _collect_deck(self) -> DeckData:
        """收集当前所有标签页数据构建 DeckData
        Collect data from all tabs and assemble a unified DeckData object.

        Merges SDEF distribution data into the Advanced settings and combines
        tally and energy tab settings via _merge_tally_settings.

        Returns:
            DeckData: Complete data structure representing the current problem.
        """
        adv = self.tab_advanced.get_data()
        # 合并分布源模式的 SDEF 字段到 AdvancedSettings
        # Merge SDEF distribution fields into AdvancedSettings
        sdef_dist = self.tab_sdef.get_distribution_data()
        for k, v in sdef_dist.items():
            setattr(adv, k, v)

        return DeckData(
            basic=self.tab_basic.get_data(),         # Problem title, mode, etc.
            surfaces=self.tab_geo.get_surfaces(),     # Surface definitions
            tr_cards=self.tab_geo.get_tr_cards(),     # TR transformation cards
            cells=self.tab_geo.get_cells(),           # Cell definitions
            materials=self.tab_mat.get_materials(),   # Material compositions
            sources=self.tab_sdef.get_sources(),      # Source (SDEF) definitions
            tally=self._merge_tally_settings(),       # Tally + energy settings
            adv=adv,                                  # Advanced settings (with SDEF dist merged)
        )

    # ---------- 拖放导入 Drag-and-Drop Import ----------

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter for INP file drag-and-drop import.

        Accepts the drag action if the dragged content contains URLs (files).
        Updates the status label to provide visual feedback.

        Args:
            event: The drag enter event from Qt.
        """
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.status_label.setText("📥 拖放以导入文件…")
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Handle file drop for INP / STEP file drag-and-drop import.
        - .inp/.i/.txt/no ext -> INP import
        - .stp/.step -> STEP import (delegates to geometry tab)
        """
        import os
        self.status_label.setText("就绪 Ready")
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if not os.path.isfile(path):
            return
        ext = os.path.splitext(path)[1].lower()
        if ext in (".stp", ".step"):
            if hasattr(self.tab_geo, '_import_step_path'):
                self.tab_geo._import_step_path(path)
            else:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, "导入失败", "geometry tab 未就绪")
        elif ext in (".inp", ".i", ".txt", ""):
            self._do_import(path)
        else:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "不支持的格式",
                f"不支持的文件: {os.path.basename(path)}\n仅支持: .inp/.i/.txt 或 .stp/.step"
            )

    def _do_import(self, path: str):
        """导入 INP 文件（委托到 inp_importer）
        Import an INP file by delegating to the inp_importer module.
        Maps tab names to actual tab widget instances and passes them for backfilling.

        Args:
            path: Full file path to the INP file to import.
        """
        tabs = {
            "basic": self.tab_basic, "geo": self.tab_geo,
            "mat": self.tab_mat, "sdef": self.tab_sdef,
            "tally": self.tab_tally, "advanced": self.tab_advanced,
            "adv": self.tab_advanced,
        }
        ok, msg = import_inp_file(path, tabs)
        if ok:
            QMessageBox.information(self, "导入成功 Import Succeeded", msg)
            self.status_label.setText(f"✓ 已导入: {os.path.basename(path)}")
        else:
            QMessageBox.warning(self, "导入失败 Import Failed", msg)

    def closeEvent(self, event):
        """关闭时保存设置
        Persist the current output path setting when the window closes.

        Args:
            event: The close event from Qt.
        """
        self.settings.setValue("output_path", self.path_edit.text())
        super().closeEvent(event)

        theme_label = {"light": "白天模式", "dark": "黑夜模式", "pink": "多巴胺模式", "traditional": "护眼模式"}
        if hasattr(self, '_sidebar'):
            self._sidebar.btn_theme.setText(theme_label.get(self.theme_mode, "白天模式"))
            self._sidebar.update_icon_colors(pal.get("text_disabled", "#888888"))

