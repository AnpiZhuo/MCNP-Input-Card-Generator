"""
MCNP Input Card Generator — Main Window
主窗口：管理标签页、生成/保存操作、设置默认路径

This module defines the MainWindow class, the central orchestrator of the
MCNP input card generator application. It manages tab switching, data collection
across all tabs, INP file generation, project save/load, INP import via file
dialog or drag-and-drop, xsdir loading, MCNP detection, and theme toggling.
"""

import os
from PyQt5.QtWidgets import (
    QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QWidget, QFileDialog, QMessageBox,
    QLabel, QLineEdit, QStatusBar, QInputDialog,
    QAction, QMenuBar, QComboBox, QApplication
)
from PyQt5.QtCore import Qt, QSettings, QEvent, QTimer
from PyQt5.QtGui import QDragEnterEvent, QDropEvent

from app.xsdir_db import DB as xsdir_db
from app.style import LIGHT_QSS, DARK_QSS
from app.mcnp_detector import detect_mcnp
from app.xsdir_manager import find_xsdir_from_env, load_xsdir
from app.project_io import deck_to_dict, deck_from_dict, save_project_file, load_project_file
from app.inp_importer import import_inp_file
from app.tabs.basic_settings_tab import BasicSettingsTab
from app.tabs.geometry_tab import GeometryTab
from app.tabs.material_tab import MaterialTab
from app.tabs.sdef_tab import SdefTab
from app.tabs.tally_tab import TallyTab
from app.tabs.energy_tab import EnergyTab
from app.tabs.advanced_tab import AdvancedTab
from app.tabs.output_tab import OutputTab
from app.models import DeckData, TallySettings
from app.generator.inp_generator import generate_inp_from_deck
from app.generator.validator import validate_deck


class MainWindow(QMainWindow):
    """MCNP 输入卡生成器主窗口
    Main application window that orchestrates all tabs, generation, import, save/load,
    xsdir management, MCNP detection, and theme switching."""

    def __init__(self):
        """Initialize the main window: load persisted settings, detect MCNP, build UI."""
        super().__init__()
        # Persistent application settings stored via QSettings (registry on Windows)
        self.settings = QSettings("MCNPGen", "MCNPGenerator")
        self.mcnp_exe = "mcnp6.exe"  # 默认 default MCNP executable
        # Load dark mode preference from saved settings
        self.is_dark = self.settings.value("dark_mode", False, type=bool)
        self.init_ui()
        self._connect_signals()
        self._detect_mcnp()
        self._apply_theme()

    def init_ui(self):
        """初始化界面 Build the complete user interface: menus, tabs, toolbar, status bar."""
        self.setWindowTitle("MCNP 输入卡生成器 v1.3.2")
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)
        self.setAcceptDrops(True)  # Enable drag-and-drop for INP files

        # ===== 菜单栏 Menu Bar =====
        menubar = self.menuBar()
        # 文件菜单 File menu
        file_menu = menubar.addMenu("文件(&F)")

        # Import INP file action
        act_import = QAction("📥 导入 INP...", self)
        act_import.setShortcut("Ctrl+I")
        act_import.setToolTip("从现有 MCNP 输入卡文件导入，自动回填到各标签页 Import an existing MCNP input file and auto-fill all tabs")
        act_import.triggered.connect(self._import_inp)
        file_menu.addAction(act_import)

        file_menu.addSeparator()

        # Save project (JSON) action
        act_save_proj = QAction("💾 保存项目...", self)
        act_save_proj.setShortcut("Ctrl+S")
        act_save_proj.setToolTip("将当前所有标签页数据保存为 JSON 项目文件 Save all tab data to a JSON project file")
        act_save_proj.triggered.connect(self._save_project)
        file_menu.addAction(act_save_proj)

        # Load project (JSON) action
        act_load_proj = QAction("📂 加载项目...", self)
        act_load_proj.setShortcut("Ctrl+O")
        act_load_proj.setToolTip("从 JSON 项目文件恢复所有标签页数据 Restore all tab data from a JSON project file")
        act_load_proj.triggered.connect(self._load_project)
        file_menu.addAction(act_load_proj)

        file_menu.addSeparator()

        # Exit action
        act_exit = QAction("退出(&X)", self)
        act_exit.setShortcut("Alt+F4")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # Central widget holding everything below the menu bar
        # 中央部件
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Top bar: import button + theme toggle + spacer
        # 顶部栏：导入按钮 + 主题切换按钮 + 留白
        top_bar = QHBoxLayout()
        self.btn_import = QPushButton("📥 导入 INP")
        self.btn_import.setObjectName("btnImport")
        self.btn_import.setToolTip("从现有 MCNP 输入卡文件导入数据（Ctrl+I）Import data from an existing MCNP input file")
        self.btn_import.setFixedWidth(120)
        self.btn_import.clicked.connect(self._import_inp)
        top_bar.addWidget(self.btn_import)
        # Theme toggle button — label switches based on current mode
        self.btn_theme = QPushButton("🌙 黑夜模式" if not self.is_dark else "☀ 白天模式")
        self.btn_theme.setObjectName("btnTheme")
        self.btn_theme.setToolTip("切换黑夜/白天模式 Toggle dark/light theme")
        self.btn_theme.setFixedWidth(130)
        self.btn_theme.clicked.connect(self._toggle_theme)
        top_bar.addWidget(self.btn_theme)
        top_bar.addStretch()  # Push buttons to the left
        main_layout.addLayout(top_bar)

        # Tab widget: each tab is a separate settings category
        # 标签页
        self.tab_widget = QTabWidget()
        self.tab_basic = BasicSettingsTab()   # 基本设置 Basic settings (title, mode, etc.)
        self.tab_mat = MaterialTab(self)      # 材料 Materials (ZAID, density, composition)
        self.tab_geo = GeometryTab(self)      # 几何 Geometry (surfaces and cells)
        self.tab_sdef = SdefTab()             # 源项 Source definition (SDEF)
        self.tab_tally = TallyTab()           # 计数 Tallies (F2, F4, F5, etc.)
        self.tab_energy = EnergyTab()         # 能谱 Energy spectrum / DE/DF cards
        self.tab_advanced = AdvancedTab()     # 高级 Advanced settings (xsdir, PHYS cards)
        self.tab_output = OutputTab()         # 输出 Output display

        # Add tabs in order — index positions used elsewhere (e.g., xsdir warning jumps to tab 6)
        self.tab_widget.addTab(self.tab_basic, "📄 基本设置")
        self.tab_widget.addTab(self.tab_mat, "🧪 材料")
        self.tab_widget.addTab(self.tab_geo, "📐 几何")
        self.tab_widget.addTab(self.tab_sdef, "🎯 源项")
        self.tab_widget.addTab(self.tab_tally, "📊 计数")
        self.tab_widget.addTab(self.tab_energy, "⚡ 能谱")
        self.tab_widget.addTab(self.tab_advanced, "⚙ 高级")
        self.tab_widget.addTab(self.tab_output, "📈 输出")

        main_layout.addWidget(self.tab_widget)

        # Bottom toolbar: output path, suffix selector, generate button
        # 底部工具栏
        toolbar = QHBoxLayout()

        # Output directory path input
        # 输出路径
        self.path_edit = QLineEdit()
        default_path = self.settings.value("output_path", "D:\\MCNP\\new\\claude")
        self.path_edit.setText(default_path)
        self.path_edit.setPlaceholderText("输出路径...")
        self.path_edit.setToolTip("INP 文件和 run.bat 的保存目录 Directory where INP files and run.bat will be saved")
        btn_browse = QPushButton("浏览…")
        btn_browse.setToolTip("选择输出目录 Choose output directory")
        btn_browse.setProperty("cssClass", "btnBrowse")
        btn_browse.clicked.connect(self._browse_path)

        # Output file suffix selector (.o, .out, .txt, or none)
        self.suffix_combo = QComboBox()
        self.suffix_combo.addItems([".o", ".out", ".txt", ""])
        saved_suffix = self.settings.value("output_suffix", ".o")
        idx = self.suffix_combo.findText(saved_suffix)
        self.suffix_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.suffix_combo.setToolTip("输出文件后缀 Output file suffix")
        self.suffix_combo.setMaximumWidth(70)
        # Persist suffix preference immediately on change
        self.suffix_combo.currentTextChanged.connect(
            lambda t: self.settings.setValue("output_suffix", t))

        # Generate INP button — main action of the application
        self.btn_generate = QPushButton("⚡ 生成 INP")
        self.btn_generate.setObjectName("btnGenerate")
        self.btn_generate.setToolTip("校验所有必填项后生成 MCNP 输入卡 Validate and generate the MCNP input card")
        self.btn_generate.clicked.connect(self._on_generate)

        toolbar.addWidget(QLabel("输出目录:"))
        toolbar.addWidget(self.path_edit, 1)
        toolbar.addWidget(btn_browse)
        toolbar.addSpacing(16)
        toolbar.addWidget(QLabel("后缀:"))
        toolbar.addWidget(self.suffix_combo)
        toolbar.addWidget(self.btn_generate)

        # Contact / bug-report information label
        # 联系信息
        contact = QLabel(
            "<span style='color:#E65100; font-size:12px; font-weight:bold;'>"
            "🐛 BUG/建议请联系 QQ: 1378963177 或电话: 15939031365</span>"
        )
        contact.setToolTip("发现 BUG 或功能建议欢迎联系 Report bugs or suggest features — contact info")

        # Wrap toolbar + contact into a single container widget for clean layout
        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(2)
        c_layout.addLayout(toolbar)
        c_layout.addWidget(contact, 0, Qt.AlignRight)
        main_layout.addWidget(container)

        # Status bar: general status, MCNP version, xsdir status
        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_xsdir = QLabel("")
        self.status_xsdir.setStyleSheet("color: #888; font-size: 11px; padding: 0 8px;")
        self.status_mcnp = QLabel("")
        self.status_mcnp.setStyleSheet("color: #888; font-size: 11px; padding: 0 8px;")
        self.status_mcnp.setCursor(Qt.PointingHandCursor)  # Indicates it's clickable
        # 使用事件过滤器替代猴子补丁，保留 QLabel 原生事件处理链
        # Use event filter instead of monkey-patching to preserve QLabel's native event chain
        self.status_mcnp.installEventFilter(self)
        self.statusBar().addWidget(self.status_label, 1)
        self.statusBar().addPermanentWidget(self.status_mcnp)
        self.statusBar().addPermanentWidget(self.status_xsdir)

        # 先显示"正在加载"，延后加载截面库，让窗口优先渲染
        # Show "loading" first, defer xsdir loading so the window renders immediately
        self.status_label.setText("正在加载截面库...")
        QApplication.processEvents()
        QTimer.singleShot(0, self._load_xsdir)

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
        safe_name = "".join(c for c in title if c.isalnum() or c in " _-").strip()
        if not safe_name:
            safe_name = "MCNP_Input"
        # Append the user-selected suffix
        suffix = self.suffix_combo.currentText().strip()
        filename = safe_name + suffix if suffix else safe_name

        try:
            # 收集文本模式覆盖
            # Collect raw (text-mode) overrides from tabs that support them
            raw_overrides = {}
            for tab in [self.tab_mat, self.tab_geo, self.tab_sdef,
                        self.tab_energy, self.tab_advanced]:
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
        Merge tally data from the Tally tab and Energy tab into a single TallySettings object.
        When keys overlap, the Energy tab's values take precedence (printed as warning).

        Returns:
            TallySettings: Combined tally configuration from both tabs.
        """
        import sys
        tally_data = self.tab_tally.get_data()
        energy_data = self.tab_energy.get_data()
        # Detect and warn about overlapping keys between the two tabs
        overlap = set(tally_data) & set(energy_data)
        if overlap:
            print(f"[WARN] _merge_tally_settings: overlapping keys {overlap} — energy_tab wins", file=sys.stderr)
        return TallySettings(**tally_data, **energy_data)

    def _apply_theme(self):
        """应用当前主题（黑夜/白天）
        Apply the current theme (dark or light) by setting the application stylesheet.
        Also updates the theme toggle button text to reflect the opposite mode."""
        if self.is_dark:
            self.setStyleSheet(DARK_QSS)
            self.btn_theme.setText("☀ 白天模式")
        else:
            self.setStyleSheet(LIGHT_QSS)
            self.btn_theme.setText("🌙 黑夜模式")

    def _toggle_theme(self):
        """切换黑夜/白天模式
        Toggle between dark and light themes.
        Persists the preference to QSettings and applies the new theme immediately."""
        self.is_dark = not self.is_dark
        self.settings.setValue("dark_mode", self.is_dark)
        self._apply_theme()

    def eventFilter(self, obj, event):
        """事件过滤器：处理 status_mcnp 的点击事件
        Event filter to handle left-click on the MCNP status label,
        which opens the version selection dialog.

        Args:
            obj: The object being filtered (checked against self.status_mcnp).
            event: The incoming event.

        Returns:
            True if the event was handled, otherwise delegates to the parent filter.
        """
        if obj is self.status_mcnp and event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._change_mcnp()
            return True
        return super().eventFilter(obj, event)

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
        self.tab_energy.set_data(deck.tally)
        self.tab_advanced.set_data(deck.adv)

    # ---------- 序列化辅助 Serialization Helpers ----------

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
            self.status_label.setText("📥 拖放以导入 INP 文件… Drop to import INP file...")
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Handle file drop for INP file drag-and-drop import.

        Extracts the first file URL from the drop event and delegates to _do_import.

        Args:
            event: The drop event from Qt.
        """
        self.status_label.setText("就绪 Ready")
        urls = event.mimeData().urls()
        if urls:
            self._do_import(urls[0].toLocalFile())

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
            "tally": self.tab_tally, "energy": self.tab_energy,
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
