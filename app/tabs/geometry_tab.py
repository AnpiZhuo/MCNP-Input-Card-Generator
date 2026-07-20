"""
📐 几何标签页：曲面卡（大文本框）+ 栅元卡（列表+弹窗编辑）+ 3D 预览
Geometry Tab: Surface cards (large text box) + Cell cards (list + dialog edit) + 3D preview

This module provides the GeometryTab widget and supporting utilities for parsing
MCNP surface definitions and building 3D geometry previews using pyvista.
Key features:
- Free-text surface card input supporting all MCNP surface types
- Table-based cell card management with dialog editing
- Automatic 3D geometry preview via pymcnp and pyvista
- Lazy registration of surface parsers to avoid circular imports
- Linked material-cell management (auto add/remove when materials change)

Module contents:
    - GeometryTab: Main widget for surface and cell definition
    - _register: Register surface type parser
    - _lazy_register: Lazily register all surface parsers
    - _parse_surface_line: Parse a single MCNP surface definition line
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPlainTextEdit, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QLabel, QMessageBox,
    QSplitter, QScrollArea, QCheckBox
)
import webbrowser
import hashlib

from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QSettings, QObject, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication, QFileDialog, QProgressDialog

from app.models import CellData
from app.widgets.render_ctrl import RenderControlWindow
from app.step_importer import StepImporter
from app.dialogs.cell_edit_dialog import CellEditDialog
from app.freecad_preview import FreeCADEngine
from pymcnp.types.Geometry import Geometry
from app.widgets.text_mode_section import TextModeSection
from app.generator.inp_generator import _generate_cells


# ===== Surface Parser for 3D Preview =====
# Maps surface type names to (parameter_count, pymcnp_class) tuples.
# Used to dynamically parse surface definitions for 3D visualization.
# The parser registry is populated lazily to avoid circular imports with pymcnp.

_SURFACE_PARSERS = {}  # {typename: (param_count, pymcnp_class)}

# ── 3D 预览颜色方案 ────────────────────────────────────
# Tableau 20 — 高区分度分类色板（index 0 = None for void）
_COLORS = [
    None,
    (0.1216, 0.4667, 0.7059),   # 1  蓝
    (1.0000, 0.4980, 0.0549),   # 2  橙
    (0.1725, 0.6275, 0.1725),   # 3  绿
    (0.8392, 0.1529, 0.1569),   # 4  红
    (0.5804, 0.4039, 0.7412),   # 5  紫
    (0.7373, 0.7412, 0.1333),   # 6  金
    (0.0902, 0.7451, 0.8118),   # 7  青
    (0.9686, 0.5059, 0.7490),   # 8  粉
    (0.4980, 0.4980, 0.4980),   # 9  灰
    (0.6941, 0.3490, 0.1569),   # 10 棕
    (0.4000, 0.7608, 0.6471),   # 11 薄荷
    (0.9882, 0.5529, 0.3843),   # 12 杏
    (0.5529, 0.6275, 0.7961),   # 13 淡蓝
    (0.9059, 0.5412, 0.7647),   # 14 淡紫
    (0.6510, 0.8471, 0.3294),   # 15 黄绿
    (1.0000, 0.8510, 0.1843),   # 16 黄
    (0.8980, 0.7686, 0.5804),   # 17 卡其
    (0.7020, 0.7020, 0.7020),   # 18 银
    (0.8000, 0.4000, 0.4000),   # 19 砖红
    (0.4000, 0.6000, 0.8000),   # 20 钢蓝
]


def _get_mat_color(m):
    """将材料号映射为 RGB 颜色 (0-1)，超出 20 则用 MD5 生成稳定色。"""
    m = int(m)
    if m < 0:
        m = 0
    if m < len(_COLORS):
        return _COLORS[m]
    h = hashlib.md5(str(m).encode()).digest()
    return (h[0] / 255, h[1] / 255, h[2] / 255)


def _get_mat_qcolor(mat_num: int) -> QColor:
    """材料号 → QColor（用于表格文字染色）"""
    c = _get_mat_color(mat_num)
    if c is None:
        return QColor(100, 100, 100)
    return QColor(int(c[0]*255), int(c[1]*255), int(c[2]*255))


def _register(name, count, cls):
    """Register a surface type with its parameter count and pymcnp class.

    Registers both uppercase and lowercase versions of the name for
    case-insensitive matching. This allows users to write surface types
    in any case (e.g., "px", "PX", "Px").

    Args:
        name: Surface type keyword (e.g. "PX", "RCC", "SO")
        count: Minimum number of parameters required
        cls: The corresponding pymcnp surface class
    """
    for alias in (name.upper(), name.lower()):
        _SURFACE_PARSERS[alias] = (count, cls)


def _lazy_register():
    """延时注册，避免循环导入 / Lazy registration to avoid circular imports.

    参考：MCNP6 曲面卡格式完全参考 (C810.pdf 第3-11至3-24页)

    Registers all supported MCNP surface types on first call.
    Must be called before any surface parsing occurs.
    This function is idempotent — subsequent calls are no-ops once registered.

    Registered surface types:
        - Planes: PX, PY, PZ (1 param); P (4或9 params, see _parse_surface_line)
        - Spheres: SO (1 param), S (4 params), SX/SY/SZ (2 params)
        - Cylinders: CX/CY/CZ (1 param), C/X/C/Y/C/Z (3 params)
        - Cones: KX/KY/KZ (3 params), K/X/K/Y/K/Z (5 params)
        - Quadratic: SQ (10 params), GQ (10 params)
        - Torii: TX, TY, TZ (6 params)
        - Point-defined: X, Y, Z (6 params, 3 coordinate pairs)
        - Macrobodies: RPP, SPH, RCC, TRC, REC, ELL, WED, BOX, ARB, RHP, HEX
    """
    if _SURFACE_PARSERS:
        return
    import pymcnp.inp as pi
    # Planes perpendicular to axes (1 param: D)
    _register("PX", 1, pi.Px); _register("PY", 1, pi.Py); _register("PZ", 1, pi.Pz)
    # General plane P is handled specially in _parse_surface_line():
    #   4 params → P_0 (Ax + By + Cz = D coefficients)
    #   9 params → P_1 (three-point definition)
    # Spheres
    _register("SO", 1, pi.So)     # origin-centered sphere (R)
    _register("S", 4, pi.S)       # general sphere (x̄ ȳ z̄ R)
    _register("SX", 2, pi.Sx)     # x̄ R
    _register("SY", 2, pi.Sy)     # ȳ R
    _register("SZ", 2, pi.Sz)     # z̄ R
    # Cylinders: axis-aligned (R)
    _register("CX", 1, pi.Cx); _register("CY", 1, pi.Cy); _register("CZ", 1, pi.Cz)
    # Cylinders: parallel to axes (ȳ z̄ R / x̄ z̄ R / x̄ ȳ R)
    _register("C/X", 3, pi.C_x); _register("C/Y", 3, pi.C_y); _register("C/Z", 3, pi.C_z)
    # Cones: on-axis (x̄ t² ±1)
    _register("KX", 3, pi.Kx); _register("KY", 3, pi.Ky); _register("KZ", 3, pi.Kz)
    # Cones: parallel to axes (x̄ ȳ z̄ t² ±1)
    _register("K/X", 5, pi.K_x); _register("K/Y", 5, pi.K_y); _register("K/Z", 5, pi.K_z)
    # Quadratic surfaces
    _register("SQ", 10, pi.Sq)    # A B C D E F G x̄ ȳ z̄
    _register("GQ", 10, pi.Gq)    # A B C D E F G H J K
    # Torii (x̄ ȳ z̄ A B C)
    _register("TX", 6, pi.Tx); _register("TY", 6, pi.Ty); _register("TZ", 6, pi.Tz)
    # Point-defined axisymmetric surfaces (x1 r1 [x2 r2] [x3 r3])
    _register("X", 2, pi.X); _register("Y", 2, pi.Y); _register("Z", 2, pi.Z)
    # Macrobodies (C810.pdf Section III.D)
    _register("RPP", 6, pi.Rpp)   # xmin xmax ymin ymax zmin zmax
    _register("SPH", 4, pi.Sph)   # vx vy vz r
    _register("RCC", 7, pi.Rcc)   # vx vy vz hx hy hz r
    _register("TRC", 8, pi.Trc)   # vx vy vz hx hy hz r1 r2
    _register("REC", 12, pi.Rec)  # vx vy vz hx hy hz v1x v1y v1z v2x v2y v2z
    _register("ELL", 7, pi.Ell)   # v1x v1y v1z v2x v2y v2z rm
    _register("WED", 12, pi.Wed)  # vx vy vz v1x v1y v1z v2x v2y v2z v3x v3y v3z
    _register("BOX", 12, pi.Box)  # vx vy vz a1x a1y a1z a2x a2y a2z a3x a3y a3z
    _register("ARB", 30, pi.Arb)  # 8 vertices (24 coords) + 6 facet definitions
    _register("RHP", 15, pi.Rhp)  # vx vy vz hx hy hz r1 r2 r3 s1 s2 s3 t1 t2 t3
    _register("HEX", 15, pi.Rhp)  # HEX = RHP alias


def _parse_surface_line(line: str) -> tuple:
    """
    将单行 MCNP 曲面文本解析为 pymcnp 对象。
    返回 (surface_object, warning_string_or_None)。
    无法解析返回 (None, warning)。
    Parse a single line of MCNP surface text into a pymcnp object.

    Supports all registered surface types, comment lines (C/c prefix),
    inline $ comments, and optional TRn transform prefixes.

    The parsing logic:
        1. Strip and skip empty/comment lines
        2. Strip inline $ comments
        3. Extract surface number (must be integer)
        4. Check for optional TRn transform prefix
        5. Look up surface type in registered parsers
        6. Parse parameters as floats
        7. Create pymcnp object

    Returns:
        tuple: (surface_object_or_None, warning_string_or_None)
    """
    _lazy_register()
    import pymcnp.inp as pi
    stripped = line.strip()
    # Skip empty lines and comment lines (C or c at start)
    if not stripped or stripped.startswith("C ") or stripped.startswith("c "):
        return (None, None)

    # Strip inline $ comments (MCNP comment syntax)
    # Everything after $ is treated as a comment by MCNP.
    if "$" in stripped:
        stripped = stripped.split("$")[0].strip()
    if not stripped:
        return (None, None)

    parts = stripped.split()
    if len(parts) < 2:
        return (None, f"格式不完整: {line[:60]}")

    # Extract surface number (must be an integer)
    # MCNP6 supports * (reflecting) and + (white boundary) prefixes on surface numbers
    # (C810.pdf §3-11). These are stripped for display; the pymcnp object stores only the number.
    surf_num = parts[0]
    surf_prefix = ""
    if surf_num.startswith("*") or surf_num.startswith("+"):
        surf_prefix = surf_num[0]
        surf_num = surf_num[1:]
    try:
        surf_num = int(surf_num)
    except ValueError:
        return (None, f"曲面号非数字: {line[:60]}")

    # Handle optional TRn transform prefix (e.g., "TR1", bare integer "1", or "-3")
    # MCNP6 format (C810.pdf §3-11): j [n] a list
    #   n > 0 = TRn card number (bare integer or "TR1" syntax)
    #   n < 0 = periodic with surface |n|
    #   n can be omitted entirely (surface type at parts[1])
    # Must distinguish from surface types (always alphabetic) vs TRC (starts with "TR").
    tr_val = None
    type_idx = 1
    tr_candidate = parts[1].upper()

    # Case A: Explicit "TRn" prefix — ensure the "n" part is numeric to avoid
    # matching surface types like "TRC" (truncated cone).
    if tr_candidate.startswith("TR") and len(parts) > 2 and tr_candidate[2:].isdigit():
        tr_val = parts[1]
        type_idx = 2

    # Case B: Bare integer (positive or negative) — the n-position is a TRn reference
    # or periodic-surface index, and the actual surface type follows at parts[2].
    # We verify by checking that parts[2] is a known surface type.
    # Note: "P" is not in _SURFACE_PARSERS (handled specially later), so check for it explicitly.
    elif len(parts) > 2:
        try:
            n_val = int(parts[1])
            surf_type_check = parts[2].upper()
            if n_val != 0 and (surf_type_check in _SURFACE_PARSERS or surf_type_check == "P"):
                tr_val = parts[1]
                type_idx = 2
        except ValueError:
            pass  # parts[1] is not numeric → treat as surface type (normal case)

    if type_idx >= len(parts):
        return (None, f"缺少曲面类型: {line[:60]}")

    surf_type = parts[type_idx].upper()
    params = parts[type_idx + 1:]

    # Special handling for P (一般平面):
    #   C810.pdf §2.1 / §IV: 4 params → equation coefficients (A B C D)
    #                         9 params → three-point definition (X1 Y1 Z1 X2 Y2 Z2 X3 Y3 Z3)
    if surf_type == "P":
        if len(params) == 4:
            min_params, cls = 4, pi.P_0
        elif len(params) == 9:
            min_params, cls = 9, pi.P_1
        else:
            return (None, f"P 曲面参数数必须为 4（方程系数 A B C D）或 9（三点定义），"
                          f"实际 {len(params)} 个")
    else:
        # Check if the surface type is supported
        if surf_type not in _SURFACE_PARSERS:
            return (None, f"不支持的曲面类型: {surf_type}")

        min_params, cls = _SURFACE_PARSERS[surf_type]

    if len(params) < min_params:
        return (None, f"参数不足: 需要≥{min_params}个, 实际{len(params)}个 ({surf_type}) "
                      f"/ Insufficient params: need ≥{min_params}, got {len(params)} ({surf_type})")

    # Convert parameter strings to floats
    try:
        float_params = [float(p) for p in params[:min_params]]
    except ValueError:
        return (None, f"参数非数字: {line[:60]}")

    # Create the pymcnp surface object
    try:
        # Pass transform if tr_val is a positive integer (TRn reference)
        # Negative values = periodic surfaces (not supported by pymcnp's transform param)
        transform_num = None
        if tr_val is not None:
            tr_str = str(tr_val).upper().replace("TR", "").lstrip("*")
            try:
                tn = int(tr_str)
                if tn > 0:
                    transform_num = tn
            except ValueError:
                pass

        if transform_num is not None:
            obj = cls(*float_params, number=surf_num, transform=transform_num)
        else:
            obj = cls(*float_params, number=surf_num)
        return (obj, None)
    except Exception as e:
        return (None, f"创建 {surf_type} 失败: {e}")


class GeometryTab(QWidget):
    """几何标签页 / Geometry Tab

    Provides a complete geometry definition interface for MCNP input files including:
    - Free-text surface card input with tooltips and placeholder examples
    - Interactive cell card table with add/edit/delete operations
    - Material-linked cell management (automatic add/remove when materials change)
    - 3D geometry preview using pymcnp and pyvista rendering
    - Dual-mode editing (form-based table and raw text mode)

    Cross-tab integration:
        - Receives material_added/material_removed signals from MaterialTab
        - Accesses MainWindow for material data lookup

    Signals:
        _preview_error: Internal signal for cross-thread error communication in 3D preview.
    """

    # Signal to pass 3D preview thread errors to the main thread
    # PyQt requires signals to be declared at class level for cross-thread communication
    _preview_error = pyqtSignal(str)

    def __init__(self, main_window):
        """Initialize the geometry tab.

        Args:
            main_window: Reference to the main application window, used for
                        cross-tab communication (e.g., material data access).
        """
        super().__init__()
        self.main_window = main_window
        self.cells: list[CellData] = []
        self._render_ctrl_win: RenderControlWindow | None = None
        self._3d_plotter = None
        self._3d_cell_actors: dict[int, object] = {}
        self._preview_error.connect(self._on_preview_error)
        self.init_ui()

    def init_ui(self):
        """Build the complete geometry tab UI layout.

        Follows the same QScrollArea + stacked QGroupBox pattern as the energy tab.
        """
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)

        # ===== 曲面与TR卡（左右分栏）/ Surfaces & TR Cards (Left/Right) =====
        grp_surf = QGroupBox("曲面与TR卡")
        grp_surf.setToolTip(
            "左：曲面定义（每行一个）\n"
            "   曲面号  类型  参数1  参数2 ...\n"
            "右：TRn 坐标变换卡（如 *TR1 ...）\n\n"
            "示例：\n"
            "  左: 1 PX -9\n"
            "  右: *TR1 0 0 0  30 60 90\n\n"
            "⚠ 曲面号不要重复，每行不超过 80 列"
        )
        surf_layout = QVBoxLayout(grp_surf)

        # 自定义标题栏：标签 + 蓝色问号帮助按钮
        surf_header = QHBoxLayout()
        surf_header.setContentsMargins(0, 0, 0, 0)
        surf_title = QLabel("<b>曲面与TR卡</b>")
        surf_header.addWidget(surf_title)
        surf_header.addSpacing(4)
        self.btn_surf_help = QPushButton("?")
        self.btn_surf_help.setFixedSize(20, 20)
        self.btn_surf_help.setToolTip("查看 MCNP6 曲面卡格式参考")
        self.btn_surf_help.setStyleSheet(
            "QPushButton { background-color: #1976d2; color: white; border-radius: 10px; "
            "font-weight: bold; font-size: 11px; border: none; }"
            "QPushButton:hover { background-color: #1565c0; }"
        )
        self.btn_surf_help.clicked.connect(self._show_surface_reference)
        surf_header.addWidget(self.btn_surf_help)
        surf_header.addStretch()
        surf_layout.addLayout(surf_header)

        # Horizontal splitter for left (surfaces) and right (TR)
        h_split = QSplitter(Qt.Horizontal)

        # ---- Left: Surface cards ----
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_label = QLabel(
            "<b>曲面卡</b>  "
            "<span style='font-family:monospace;'>曲面号  类型  参数 ...</span>"
        )
        self.surface_text = QPlainTextEdit()
        self.surface_text.setPlaceholderText(
            "1  PX  -9\n2  PY  -9\n3  PZ  -9\n"
            "4  PX   9\n5  PY   9\n6  PZ   9\n7  CZ   5"
        )
        self.surface_text.setToolTip(
            "每行一个曲面，支持所有 MCNP 曲面类型：\n"
            "P/PX/PY/PZ (平面), SO/S/SX/SY/SZ (球),\n"
            "CX/CY/CZ/C/X/C/Y/C/Z (圆柱), 等"
        )
        self.surface_text.setMinimumHeight(400)

        # 编号建议
        surf_tip = QLabel(
            "<span style='color:#e65100; font-size:11px;'>"
            "💡 建议曲面号大于 100，栅元号小于 100</span>"
        )
        left_layout.addWidget(surf_tip)
        left_layout.addWidget(left_label)
        left_layout.addWidget(self.surface_text)
        h_split.addWidget(left_widget)

        # ---- Right: TR cards ----
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_label = QLabel(
            "<b>TR 变换卡</b>  "
            "<span style='font-family:monospace;'>*TRn  Tx Ty Tz  B1..B9  [M]</span>"
        )
        self.tr_text = QPlainTextEdit()
        self.tr_text.setPlaceholderText(
            "TR1  0 0 0  1 0 0  0 1 0  0 0 1\n"
            "*TR2  10 0 0  0 1 0  -1 0 0  0 0 1"
        )
        self.tr_text.setToolTip(
            "TRn 坐标变换卡。格式：\n"
            "  TRn  Tx Ty Tz  B1 B2 B3  B4 B5 B6  B7 B8 B9  [M]\n"
            "  *TRn 表示平移+旋转的组合变换\n"
            "例如：*TR1  0 0 0  30 60 90\n"
            "（Tx Ty Tz = 平移向量，B1~B9 = 旋转矩阵）"
        )
        self.tr_text.setMinimumHeight(400)
        right_layout.addWidget(right_label)
        right_layout.addWidget(self.tr_text)
        h_split.addWidget(right_widget)

        # Set initial 60/40 split
        h_split.setSizes([600, 400])
        surf_layout.addWidget(h_split, 1)

        # 3D preview + import button row
        surf_btn_layout = QHBoxLayout()
        surf_btn_layout.addStretch()

        self.lbl_step_warn = QLabel("✅ McCAD 已就绪")
        self.lbl_step_warn.setToolTip(
            "使用 McCAD 外置转换器导入 STEP 文件，\n"
            "支持自动分解非凸体。"
        )
        self.lbl_step_warn.setStyleSheet("color: #2e7d32; font-size: 11px; padding: 2px 6px;")
        surf_btn_layout.addWidget(self.lbl_step_warn)

        self.btn_import_step = QPushButton("📥 导入 STEP")
        self.btn_import_step.setToolTip("使用 McCAD 转换 STEP → MCNP 输入卡")
        self.btn_import_step.clicked.connect(self._import_step)
        surf_btn_layout.addWidget(self.btn_import_step)

        self.btn_3d = QPushButton("🔍 3D 预览")
        self.btn_3d.setToolTip(
            "基于当前曲面和栅元定义打开 3D 几何预览窗口。\n"
            "使用 FreeCAD + PyVista 渲染，支持真 CSG 布尔运算。\n"
            "需要已安装 FreeCAD。"
        )
        self.btn_3d.setProperty("cssClass", "btnPrimary")
        self.btn_3d.clicked.connect(self._preview_3d)
        surf_btn_layout.addWidget(self.btn_3d)

        self.btn_export_step = QPushButton("📐 导出 STEP")
        self.btn_export_step.setToolTip("将每个栅元导出为 STEP 实体模型")
        self.btn_export_step.clicked.connect(self._export_step)
        surf_btn_layout.addWidget(self.btn_export_step)
        surf_layout.addLayout(surf_btn_layout)
        layout.addWidget(grp_surf)

        # ===== 栅元卡（列表 + 编辑弹窗）/ Cell Cards (Table + Dialog Editor) =====
        # Table-based cell card management with dialog editing.
        # Each cell has: number, material, density, importance, comment, and surface expression.
        grp_cell = QGroupBox("栅元卡")
        grp_cell.setToolTip(
            "定义模型各区域的材料和几何边界。\n"
            "每个栅元由曲面布尔表达式围成。\n\n"
            "符号规则：负号(-)=曲面内侧(inside)，正号(+)=曲面外侧(outside)\n"
            "布尔运算：空格=AND(交)，冒号=OR(并)，井号#=NOT(补)\n\n"
            "Define material regions and geometric boundaries.\n"
            "Each cell is bounded by a boolean expression of surfaces.\n"
            "Sign rules: (-)=inside, (+)=outside the surface.\n"
            "Boolean ops: space=AND, colon=OR, hash#=NOT"
        )
        cell_layout = QVBoxLayout(grp_cell)

        # Toolbar: label + add/delete buttons + text mode toggle
        cell_toolbar = QHBoxLayout()
        cell_toolbar.addWidget(QLabel("栅元列表:"))
        cell_toolbar.addStretch()

        self.btn_add_cell = QPushButton("+ 添加栅元")
        self.btn_add_cell.setToolTip("新增一个栅元，材料默认 void（0）")
        self.btn_add_cell.setProperty("cssClass", "btnAdd")
        self.btn_add_cell.clicked.connect(self._add_cell)

        self.btn_del_cell = QPushButton("× 删除选中")
        self.btn_del_cell.setToolTip("删除列表中选中的栅元")
        self.btn_del_cell.setProperty("cssClass", "btnDelete")
        self.btn_del_cell.clicked.connect(self._delete_cell)

        self.btn_rend_ctrl = QPushButton("🎨 渲染控制")
        self.btn_rend_ctrl.setToolTip("控制每个栅元在3D预览中的显隐（独立置顶窗口）")
        self.btn_rend_ctrl.clicked.connect(self._open_render_ctrl)

        cell_toolbar.addWidget(self.btn_add_cell)
        cell_toolbar.addWidget(self.btn_del_cell)
        cell_toolbar.addWidget(self.btn_rend_ctrl)

        # Text mode toggle button for switching between form and raw text editing
        # TextModeSection provides a toggle button and stacked widget for dual-mode editing.
        self._raw_cell = TextModeSection(
            form_widget=QWidget(),
            generate_fn=lambda: "\n".join(_generate_cells(self.cells)),
            section_name="cells",
        )
        cell_toolbar.addWidget(self._raw_cell.toggle_btn)
        cell_layout.addLayout(cell_toolbar)

        # Cell table: displays all cells with key properties (列宽可拖拽)
        self.cell_table = QTableWidget(0, 6)
        self.cell_table.setHorizontalHeaderLabels(
            ["栅元号", "材料号", "密度", "IMP:N", "注释", "操作"]
        )
        header = self.cell_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.Interactive)
        header.setSectionResizeMode(5, QHeaderView.Interactive)
        header.setStretchLastSection(False)
        self._geo_settings = QSettings("MCNPGen", "MCNPGenerator")
        saved = self._geo_settings.value("geo_col_widths")
        if saved and len(saved) == 6:
            for col, w in enumerate(saved):
                header.resizeSection(col, int(w))
        else:
            header.resizeSection(0, 60)
            header.resizeSection(1, 140)
            header.resizeSection(2, 100)
            header.resizeSection(3, 60)
            header.resizeSection(4, 120)
            header.resizeSection(5, 80)
        header.sectionResized.connect(self._save_geo_col_widths)
        self.cell_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cell_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cell_table.setToolTip("双击行或点击编辑按钮可编辑栅元参数。列宽可拖拽调整。")

        # Replace the stack widget's first page with the table
        self._raw_cell.stack.removeWidget(self._raw_cell.stack.widget(0))
        self._raw_cell.stack.insertWidget(0, self.cell_table)
        cell_layout.addWidget(self._raw_cell.stack)
        self._raw_cell.stack.setCurrentIndex(0)  # 强制表单模式
        grp_cell.setMinimumHeight(600)
        layout.addWidget(grp_cell)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

    # ---------- 曲面格式参考弹窗 ----------

    def _show_surface_reference(self):
        """打开 MCNP6 曲面卡格式参考文档"""
        import os
        ref_path = os.path.join(os.path.dirname(__file__), "..", "docs",
                                "MCNP6_曲面卡格式参考.md")
        ref_path = os.path.normpath(ref_path)
        if not os.path.isfile(ref_path):
            QMessageBox.warning(self, "未找到", f"参考文档不存在:\n{ref_path}")
            return
        try:
            with open(ref_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            QMessageBox.critical(self, "读取失败", f"无法读取参考文档:\n{e}")
            return

        from PyQt5.QtWidgets import QDialog, QTextBrowser, QVBoxLayout, QPushButton
        import markdown as _md
        dialog = QDialog(self)
        dialog.setWindowTitle("MCNP6 曲面卡格式参考")
        dialog.setMinimumSize(850, 700)
        dialog.resize(850, 700)
        dlg_layout = QVBoxLayout(dialog)

        html_body = _md.markdown(
            content,
            extensions=["extra", "toc"],
        )
        full_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:'Microsoft YaHei','Segoe UI',sans-serif;
      font-size:14px; line-height:1.8; color:#222; max-width:820px; margin:0 auto; padding:12px 20px;">
<style>
  h1 {{ font-size:22px; border-bottom:2px solid #1976d2; padding-bottom:6px; color:#1565c0; }}
  h2 {{ font-size:18px; color:#1565c0; margin-top:24px; border-bottom:1px solid #e0e0e0; padding-bottom:4px; }}
  h3 {{ font-size:15px; color:#333; margin-top:18px; }}
  table {{ border-collapse:collapse; width:100%; margin:10px 0; }}
  th {{ background-color:#e3f2fd; font-weight:bold; padding:7px 10px; border:1px solid #bbb; text-align:left; }}
  td {{ padding:5px 10px; border:1px solid #ddd; }}
  tr:nth-child(even) {{ background-color:#f8f8f8; }}
  tr:hover {{ background-color:#e8f0fe; }}
  code {{ background-color:#f0f0f0; padding:1px 5px; border-radius:3px;
         font-family:Consolas,monospace; font-size:13px; color:#d32f2f; }}
  pre {{ background-color:#f5f5f5; padding:12px 16px; border-left:3px solid #1976d2;
        border-radius:4px; font-family:Consolas,monospace; font-size:13px; overflow-x:auto; }}
  blockquote {{ border-left:4px solid #1976d2; margin:14px 0; padding:8px 16px;
               background:#f5f8ff; color:#555; border-radius:0 4px 4px 0; }}
  hr {{ border:none; border-top:1px solid #ddd; margin:24px 0; }}
  strong {{ color:#1565c0; }}
  ul, ol {{ padding-left:22px; }}
  li {{ margin:4px 0; }}
  a {{ color:#1976d2; }}
</style>
{html_body}
</body>
</html>"""
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(full_html)
        browser.setStyleSheet("QTextBrowser { background-color: #fff; border: none; }")
        dlg_layout.addWidget(browser)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(dialog.close)
        dlg_layout.addWidget(btn_close, alignment=Qt.AlignRight)

        # 非模态：不阻塞主界面，可边看参考边编辑曲面卡
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        dialog.show()

    # ---------- 公开接口
    # These methods are called by the MainWindow and INP generator.

    def get_surfaces(self) -> str:
        """获取曲面卡文本 / Get the surface card text.

        Returns:
            str: The raw surface definitions (left panel).
        """
        return self.surface_text.toPlainText().strip()

    def get_tr_cards(self) -> str:
        """获取 TR 变换卡文本 / Get the TR transformation card text.

        Returns:
            str: The raw TR card definitions (right panel).
        """
        return self.tr_text.toPlainText().strip()

    def get_cells(self) -> list[CellData]:
        """获取栅元卡数据列表 / Get the cell card data list.

        Returns:
            list[CellData]: The list of cell data objects.
        """
        return self.cells

    def set_data(self, surfaces: str, cells: list[CellData], tr_cards: str = ""):
        """从导入数据回填 UI（用于 INP 导入） / Populate UI from imported data (for INP import).

        Args:
            surfaces: Surface definition text to restore.
            cells: List of cell data objects to restore.
            tr_cards: TR transformation card text to restore.
        """
        self.surface_text.setPlainText(surfaces)
        self.tr_text.setPlainText(tr_cards)
        self.cells = list(cells)
        self._refresh_table()

    def get_raw_overrides(self) -> dict:
        """返回文本模式原始文本，供生成器使用 / Return raw text mode overrides for the generator.

        When in raw text mode, this returns the user's custom cell text
        instead of the form-generated output.

        Returns:
            dict: Dictionary with "cells" key containing raw text, if any.
        """
        return {"cells": self._raw_cell.get_raw_text()}

    def add_cell_for_material(self, material_number: int):
        """
        材料新增时的联动：
        自动添加一个栅元行，预填栅元号和材料号
        Linked action when a material is added:
        Automatically creates a cell row pre-filled with cell number and material number.

        Called by MaterialTab.material_added signal. Ensures that every
        material definition has a corresponding cell in the geometry.

        Args:
            material_number: The material number to link this cell to.
        """
        new_number = self._next_cell_number()
        cell = CellData(
            number=new_number,
            material=f"M{material_number}",
            density="",
            surface_expr="",
            imp_n="",
            comment="",
        )
        self.cells.append(cell)
        self._refresh_table()

    def remove_cells_for_material(self, material_number: int) -> int:
        """删除引用指定材料号的所有栅元，返回删除数 / Remove all cells referencing a given material.

        Called when a material is deleted from MaterialTab. Removes all
        cells that reference the specified material number.

        Args:
            material_number: The material number whose cells should be removed.

        Returns:
            int: Number of cells removed.
        """
        removed = 0
        remaining = []
        mat_ref = f"M{material_number}"
        for cell in self.cells:
            cell_mat = cell.material
            # Handle case where material field contains extra data after the reference
            # The material field may contain density or other data after the material ID.
            if " " in cell_mat:
                cell_mat = cell_mat.split()[0]
            if cell_mat == mat_ref:
                removed += 1
            else:
                remaining.append(cell)
        self.cells = remaining
        self._refresh_table()
        return removed

    def get_available_materials(self) -> list[str]:
        """从材料标签页获取当前已定义的材料号列表（含注释，用于下拉显示） / Get defined material list with comments for dropdown display.

        Queries the MaterialTab for currently defined materials and formats
        them as display strings with comments. Always includes void (0) as
        the last option.

        Returns:
            list[str]: Material labels like "M1 (Steel)" plus "0 (void/真空)".
        """
        if hasattr(self.main_window, 'tab_mat'):
            materials = self.main_window.tab_mat.get_materials()
            items = []
            for m in materials:
                label = f"M{m.number}"
                if m.comment:
                    label += f" ({m.comment})"
                items.append(label)
            return items + ["0 (void / 真空)"]
        return ["0 (void / 真空)"]

    def _save_geo_col_widths(self):
        """拖拽列宽时自动保存"""
        widths = [self.cell_table.columnWidth(c) for c in range(self.cell_table.columnCount())]
        self._geo_settings.setValue("geo_col_widths", widths)

    def _get_material_display(self, raw_material: str) -> str:
        """将栅元中保存的材料号转为表格显示的友好名称（含注释） / Convert material reference to display-friendly name with comment.

        Parses the material reference from cell data and looks up its comment
        from the MaterialTab for a more informative display.

        Args:
            raw_material: The raw material string from cell data (e.g., "M1" or "M1 ...").

        Returns:
            str: Display string like "M1 (Steel)" or "0 (void/真空)".
        """
        mat = raw_material
        # Strip any extra data after the material reference
        if " " in mat:
            mat = mat.split()[0]
        if mat == "0":
            return "0 (void / 真空)"
        if mat.startswith("M") and hasattr(self.main_window, 'tab_mat'):
            num_str = mat[1:]
            if num_str.isdigit():
                num = int(num_str)
                for m in self.main_window.tab_mat.get_materials():
                    if m.number == num:
                        if m.comment:
                            return f"M{num} ({m.comment})"
                        return f"M{num}"
        return raw_material

    def _next_cell_number(self) -> int:
        """自动获取下一个可用的栅元号 / Get the next available cell number.

        Finds the highest existing cell number and returns it + 1.
        Returns 1 if no cells exist yet.
        Cell numbers must be unique in MCNP input files.

        Returns:
            int: Next available cell number.
        """
        if not self.cells:
            return 1
        existing = sorted(c.number for c in self.cells)
        return existing[-1] + 1

    # ---------- 内部操作
    # These methods handle table management, cell CRUD, and UI refresh.

    def _refresh_table(self):
        print(f"[_refresh_table] rows={len(self.cells)}")
        """刷新栅元表格显示 / Refresh the cell table display.

        Rebuilds all table rows from the current cells list.
        Each row shows: cell number, material (with comment), density,
        neutron importance, comment, edit button, and render checkbox.
        Called after any cell data change (add, edit, delete, import).
        """
        self.cell_table.setRowCount(len(self.cells))
        for i, cell in enumerate(self.cells):
            # 0 — 栅元号
            self.cell_table.setItem(i, 0, QTableWidgetItem(str(cell.number)))

            # 1 — 材料号（带颜色）
            mat_text = self._get_material_display(cell.material)
            mat_item = QTableWidgetItem(mat_text)
            # 解析材料号取色
            raw = cell.material
            if " " in raw:
                raw = raw.split()[0]
            if raw.startswith("M"):
                ns = raw[1:]
                if ns.isdigit():
                    mat_item.setForeground(_get_mat_qcolor(int(ns)))
            elif raw == "0":
                mat_item.setForeground(QColor(120, 120, 120))
            self.cell_table.setItem(i, 1, mat_item)

            self.cell_table.setItem(i, 2, QTableWidgetItem(
                cell.density if cell.density else "(void)"
            ))
            self.cell_table.setItem(i, 3, QTableWidgetItem(cell.imp_n))
            # 4 — 注释（带材料颜色）
            cmt_item = QTableWidgetItem(cell.comment)
            raw = cell.material
            if " " in raw:
                raw = raw.split()[0]
            if raw.startswith("M") and raw[1:].isdigit():
                cmt_item.setForeground(_get_mat_qcolor(int(raw[1:])))
            elif raw == "0":
                cmt_item.setForeground(QColor(120, 120, 120))
            self.cell_table.setItem(i, 4, cmt_item)

            # 5 — 编辑按钮
            btn_edit = QPushButton("✎ 编辑")
            btn_edit.setToolTip("编辑此栅元的详细参数")
            btn_edit.setProperty("cssClass", "btnEdit")
            btn_edit.clicked.connect(lambda checked, idx=i: self._edit_cell(idx))
            self.cell_table.setCellWidget(i, 5, btn_edit)

        # 同步渲染控制窗口（如果打开）
        if self._render_ctrl_win and self._render_ctrl_win.isVisible():
            self._render_ctrl_win.refresh()

    def _add_cell(self):
        """添加新栅元（默认 void） / Add a new cell (default void material).

        Creates a cell with void material (0), zero importance for neutrons,
        and no surface expression. The cell number is auto-assigned.
        """
        new_number = self._next_cell_number()
        cell = CellData(
            number=new_number,
            material="0 (void / 真空)",
            density="",
            surface_expr="",
            imp_n="0",    # void 栅元重要性默认为 0 / void cell importance defaults to 0
            comment="",
        )
        self.cells.append(cell)
        self._refresh_table()

    def _delete_cell(self):
        """删除选中的栅元 / Delete selected cells.

        Removes all cells whose rows are currently selected in the table.
        Processes rows in reverse order to maintain index validity during deletion.
        """
        rows = set()
        for idx in self.cell_table.selectedIndexes():
            rows.add(idx.row())
        # Sort in reverse to avoid index shifting issues when deleting
        for row in sorted(rows, reverse=True):
            if 0 <= row < len(self.cells):
                del self.cells[row]
        self._refresh_table()

    def _edit_cell(self, idx: int):
        """弹出栅元编辑对话框 / Open cell edit dialog.

        Opens a CellEditDialog for the given cell index. If the user accepts
        the changes, the cell data is updated and the table is refreshed.

        Args:
            idx: Index of the cell in the self.cells list.
        """
        if idx < 0 or idx >= len(self.cells):
            return
        cell = self.cells[idx]
        available_mats = self.get_available_materials()

        dialog = CellEditDialog(cell, available_mats, self)
        if dialog.exec_() == CellEditDialog.Accepted:
            self.cells[idx] = dialog.get_data()
            self._refresh_table()

    # ---------- 渲染控制窗口 / Render Control Window ----------

    def _open_render_ctrl(self):
        """打开/激活浮动渲染控制窗口"""
        if self._render_ctrl_win and self._render_ctrl_win.isVisible():
            self._render_ctrl_win.raise_()
            self._render_ctrl_win.refresh()
            return
        self._render_ctrl_win = RenderControlWindow(
            get_cells_fn=lambda: self.cells,
            format_fn=self._render_ctrl_format,
            on_changed=self._sync_3d_visibility,
            on_mat_changed=self._on_render_ctrl_mat_changed,
            get_surface_info_fn=self._get_cell_surface_info,
        )
        self._render_ctrl_win.show()

    def _get_cell_surface_info(self, surface_expr: str) -> list[tuple[int, str]]:
        """从栅元曲面表达式提取曲面号及对应卡片文本

        Args:
            surface_expr: 栅元的曲面表达式（如 "118 -111 -126"）

        Returns:
            [(曲面号, 曲面卡原文), ...] 按曲面号排序
        """
        # 1. 提取所有曲面号（去掉 + - # : ( ) 等符号）
        surf_nums: set[int] = set()
        for token in surface_expr.replace(':', ' ').split():
            token = token.strip().lstrip('+#-()')
            if token.isdigit():
                surf_nums.add(int(token))

        if not surf_nums:
            return []

        # 2. 从 surface_text 逐行匹配曲面卡原文
        text = self.surface_text.toPlainText()
        lines = text.split('\n')

        result = []
        for num in sorted(surf_nums):
            card_text = None
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                # 跳过注释行（以 c 或 C 开头）
                if stripped[0] in ('c', 'C'):
                    continue
                parts = stripped.split()
                if parts and parts[0] == str(num):
                    card_text = stripped
                    break
            if card_text:
                result.append((num, card_text))
            else:
                result.append((num, f"; {num} — 未找到曲面卡"))

        return result

    def _sync_3d_visibility(self):
        """勾选变化时实时更新3D场景中对应栅元的显隐"""
        if not self._3d_cell_actors or self._3d_plotter is None:
            return
        try:
            for c in self.cells:
                actor = self._3d_cell_actors.get(c.number)
                if actor is not None:
                    actor.SetVisibility(getattr(c, 'render', True))
            self._3d_plotter.render()
        except Exception:
            pass

    def _on_render_ctrl_mat_changed(self, idx, mat_text):
        """渲染控制窗口中材料号变更后的实时反馈"""
        cells = self.cells
        if idx >= len(cells):
            return
        cell = cells[idx]
        # 解析材料号
        raw = mat_text
        if raw.startswith("M"):
            raw = raw[1:]
        try:
            mat_num = int(raw) if raw.lstrip("-").isdigit() else 0
        except ValueError:
            mat_num = 0
        # 更新 3D 场景中对应栅元的颜色
        if self._3d_cell_actors and self._3d_plotter is not None:
            actor = self._3d_cell_actors.get(cell.number)
            if actor:
                color = _get_mat_color(mat_num)
                if color:
                    actor.GetProperty().SetColor(color[0], color[1], color[2])
                    self._3d_plotter.render()
        # 刷新主表格中对应行的注释颜色
        self._refresh_table()

    def _render_ctrl_format(self, idx, cell):
        """为渲染控制窗口格式化栅元显示文本

        Returns:
            (mat_text: str, comment_text: str)
            mat_text — 如 "—  M1 (Steel)"
            comment_text — 如 "# 外边界" 或 ""
        """
        mat_text = f"—  {self._get_material_display(cell.material)}"
        cell_c = str(cell.comment or '').strip()
        comment_text = f"# {cell_c}" if cell_c else ""
        return mat_text, comment_text

    # ---------- STEP 导入 / STEP Import ----------
    # STEP → MCNP 转换集成。依赖 FreeCAD + GEOUNED。

    def _scan_max_surf(self) -> int:
        """扫描曲面文本框中的数字，返回最大曲面号。无内容则返回 0。"""
        import re
        text = self.surface_text.toPlainText()
        nums = [int(m) for m in re.findall(r"^\s*(\d+)", text, re.MULTILINE)]
        return max(nums) if nums else 0

    def _scan_max_cell(self) -> int:
        """扫描栅元列表，返回最大栅元号。无内容则返回 0。"""
        if not self.cells:
            return 0
        return max(c.number for c in self.cells)

    def _show_import_dialog(self, step_path: str, freecad_bin: str):
        """弹出 STEP 导入设置对话框，确认后启动后台转换。"""
        max_surf = self._scan_max_surf()
        max_cell = self._scan_max_cell()
        dialog = StepImportDialog(self, max_surf=max_surf, max_cell=max_cell)
        if dialog.exec_() != StepImportDialog.Accepted:
            return  # 用户取消

        user_settings = dialog.get_settings()

        self._step_thread = QThread()
        self._step_worker = _StepWorker(step_path, freecad_bin, user_settings)
        self._step_worker.moveToThread(self._step_thread)

        self._step_progress = QProgressDialog(
            "正在转换 STEP → MCNP...\n这可能需要几秒到几分钟。",
            "取消", 0, 0, self
        )
        self._step_progress.setWindowTitle("导入 STEP")
        self._step_progress.setModal(True)
        self._step_progress.show()
        QApplication.processEvents()

        self._step_worker.result_ready.connect(self._on_step_result)
        self._step_progress.canceled.connect(self._cancel_step_import)
        self._step_thread.started.connect(self._step_worker.run)
        self._step_worker.finished.connect(self._step_thread.quit)
        self._step_worker.finished.connect(self._step_progress.close)
        self._step_worker.finished.connect(self._step_worker.deleteLater)
        self._step_thread.finished.connect(self._step_thread.deleteLater)
        self._step_thread.start()

    def _cancel_step_import(self):
        """用户取消进度对话框时终止转换。"""
        if hasattr(self, '_step_worker') and self._step_worker:
            self._step_worker.abort()
        if hasattr(self, '_step_thread') and self._step_thread:
            self._step_thread.quit()
        self._step_progress.close()

    def _show_freecad_guide(self):
        """FreeCAD 未安装时弹窗引导。选择路径后自动重试。"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("需要 FreeCAD")
        msg.setText("导入 STEP 需要 FreeCAD 作为转换引擎。")
        msg.setInformativeText("未检测到 FreeCAD 安装。\n\n选择操作：")
        btn_download = msg.addButton("🌐 前往官网下载", QMessageBox.ActionRole)
        btn_manual = msg.addButton("📁 手动指定路径", QMessageBox.ActionRole)
        msg.addButton("取消", QMessageBox.RejectRole)
        msg.exec_()

        if msg.clickedButton() == btn_download:
            webbrowser.open("https://www.freecad.org/?lang=zh_CN")
        elif msg.clickedButton() == btn_manual:
            exe_path, _ = QFileDialog.getOpenFileName(
                self, "选择 FreeCAD.exe",
                "", "FreeCAD (FreeCAD.exe)"
            )
            if exe_path:
                StepImporter.save_freecad_path(exe_path)
                # 保存后自动重试
                pass

    def _parse_tr_cards(self) -> dict:
        """解析 TRn 变换卡 → {tr_num: {translate, rotate}}"""
        import re as _re
        tr_map = {}
        tr_text = self.tr_text.toPlainText().strip()
        if not tr_text:
            return tr_map

        for line in tr_text.split("\n"):
            line_s = line.strip()
            if not line_s:
                continue
            m = _re.match(r'^(\*)?TR(\d+)', line_s.upper())
            if not m:
                continue
            try:
                tr_num = int(m.group(2))
                if tr_num in tr_map:
                    continue
                parts = line_s.split()
                vals = parts[1:]
                if len(vals) < 3:
                    continue
                floats = [float(v) for v in vals]
                translate = floats[0:3]
                rotate = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
                prefix = m.group(1) or ""
                if len(floats) >= 9:
                    rotate = [
                        [floats[3], floats[4], floats[5]],
                        [floats[6], floats[7], floats[8]],
                    ]
                    if len(floats) >= 12:
                        rotate.append([floats[9], floats[10], floats[11]])
                    else:
                        from numpy import cross as _cross
                        rotate.append(_cross(rotate[0], rotate[1]).tolist())
                elif len(floats) >= 6:
                    from numpy import cross as _cross
                    x_row = [floats[3], floats[4], floats[5]]
                    y_d = [1, 0, 0] if abs(floats[3]) < 0.9 else [0, 1, 0]
                    y_row = [floats[6] if len(floats) > 6 else 0,
                             floats[7] if len(floats) > 7 else 0,
                             floats[8] if len(floats) > 8 else 0]
                    if all(v == 0 for v in y_row):
                        y_row = y_d
                    rotate = [x_row, y_row, _cross(x_row, y_row).tolist()]

                if prefix == "*":
                    from math import cos, radians
                    rotate = [[cos(radians(v)) for v in row] for row in rotate]

                m_val = 1
                if len(floats) in (10, 13):
                    m_val = int(floats[-1])
                if m_val == -1:
                    from numpy import array, transpose
                    R = array(rotate)
                    translate = (-transpose(R) @ array(translate)).tolist()

                tr_map[tr_num] = {
                    "translate": translate, "rotate": rotate,
                }
            except Exception:
                continue
        return tr_map

    def _preview_3d(self):
        """基于当前曲面和栅元生成 3D 几何预览 (FreeCAD CSG + PyVista)

        流程:
            1. 解析曲面文本为 pymcnp 对象 (_parse_surface_line)
            2. 解析 TRn 变换卡
            3. 从 self.cells 构建栅元数据 + Geometry AST
            4. 子进程调 FreeCAD Python 做 CSG 布尔运算
            5. PyVista 渲染输出文件
        """
        print("[_preview_3d] start")
        freecad_bin = StepImporter.detect_freecad()
        if not freecad_bin:
            self._show_freecad_guide()
            return

        surfaces_text = self.surface_text.toPlainText().strip()
        raw_cell_text = self._raw_cell.get_raw_text()
        if not surfaces_text and not self.cells and not raw_cell_text:
                box = QMessageBox(self)
                box.setIcon(QMessageBox.Information)
                box.setWindowTitle("提示")
                box.setText("请先定义曲面和栅元")
                box.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
                box.exec_()
                return

        # 1. 解析曲面 (复用 _parse_surface_line)
        surfs = []
        warn_list = []
        for line in surfaces_text.split("\n"):
            obj, warn = _parse_surface_line(line)
            if obj is not None:
                surfs.append(obj)
            if warn:
                warn_list.append(warn)

        if not surfs:
            msg = "未解析到有效的曲面对象。"
            if warn_list:
                msg += "\n\n警告 (前5条):\n" + "\n".join(warn_list[:5])
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("无法预览")
            box.setText(msg)
            box.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            box.exec_()
            return

        # 2. 解析 TRn
        tr_cards = self._parse_tr_cards()

        # 3. 构建栅元数据：文本模式时从 raw text 解析，否则用表单
        cells_data = []
        raw_cell_text = self._raw_cell.get_raw_text()
        if raw_cell_text:
            # 文本模式：解析 raw text 中的栅元卡
            from app.generator.parsers.sections import split_sections
            from app.generator.parsers.core import parse_cells
            all_lines = raw_cell_text.split("\n")
            title, cell_lines, _, _ = split_sections(all_lines)
            raw_cells = parse_cells(cell_lines) if cell_lines else []
            for cell in raw_cells:
                expr = cell.surface_expr.strip()
                if not expr:
                    continue
                # 跳过 void 栅元（材料号 0）
                raw_mat = (cell.material or "").strip().split()[0] if cell.material else ""
                if raw_mat == "0":
                    continue
                try:
                    geometry = Geometry.from_mcnp(expr)
                except Exception:
                    continue
                cells_data.append({
                    "number": cell.number,
                    "material": cell.material,
                    "ast": geometry,
                    "density": cell.density,
                })
        else:
            # 表单模式
            for cell in self.cells:
                expr = cell.surface_expr.strip()
                if not expr:
                    continue
                # 跳过 void 栅元（材料号 0）
                raw_mat = (cell.material or "").strip().split()[0] if cell.material else ""
                if raw_mat == "0":
                    continue
                try:
                    geometry = Geometry.from_mcnp(expr)
                except Exception:
                    continue
                cells_data.append({
                    "number": cell.number,
                    "material": cell.material,
                    "ast": geometry,
                    "density": cell.density,
                })

        if not cells_data:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("无法预览")
            box.setText("没有有效的栅元定义")
            box.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            box.exec_()
            return

        # 4. 进度条
        progress = QProgressDialog(
            "FreeCAD 正在构建 3D 几何...\n首次启动约需 5-10 秒",
            "取消", 0, 0, self
        )
        progress.setWindowTitle("3D 预览")
        progress.setModal(True)
        progress.show()
        QApplication.processEvents()

        # 5. 自动计算包围盒：扫描曲面文本中所有数字
        bound = 5000  # 默认足够大
        try:
            import re as _re
            vals = []
            for line in surfaces_text.split("\n"):
                for token in line.split():
                    try:
                        vals.append(abs(float(token)))
                    except ValueError:
                        pass
            if vals:
                bound = int(max(vals) * 1.5) + 500
        except Exception:
            pass

        # 6. 子进程调 FreeCAD
        engine = FreeCADEngine(freecad_bin)
        try:
            result = engine.build_geometry(surfs, cells_data, tr_cards, bound=bound)
        except Exception as e:
            progress.close()
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Critical)
            box.setWindowTitle("3D 预览失败")
            box.setText(str(e))
            box.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            box.exec_()
            engine.cleanup()
            return
        finally:
            progress.close()

        # 6. PyVista 展示（在 engine.cleanup 之前，因为文件是临时的）
        try:
            import pyvista as pv
            from pyvistaqt import BackgroundPlotter as _BgPlotter
            from app.widgets.coord_aids import CoordAids
            from app.widgets.opacity_ctrl import OpacityController

            def _material_of(cell_num):
                """通过栅元号查材料号（用于 STL → 材料映射）"""
                for c in self.cells:
                    if c.number == cell_num:
                        ms = c.material
                        if " " in ms:
                            ms = ms.split()[0]
                        if ms.startswith("M"):
                            ms = ms[1:]
                        try:
                            return int(ms) if ms.lstrip("-").isdigit() else 0
                        except ValueError:
                            return 0
                return 0

            # 收集全部材料号 → 颜色/标签（始终展示所有材料，不依渲染状态过滤）
            legend_entries = []
            mat_seen = {}
            # 1. 从栅元中收集被引用的材料
            for c in self.cells:
                mat_num = _material_of(c.number)
                if mat_num <= 0 or mat_num in mat_seen:
                    continue
                mat_seen[mat_num] = True
                color = _get_mat_color(mat_num)
                label = f"M{mat_num}"
                if hasattr(self, 'main_window') and hasattr(self.main_window, 'tab_mat'):
                    try:
                        for m in self.main_window.tab_mat.get_materials():
                            if m.number == mat_num:
                                c = str(m.comment or '').strip()
                                if c:
                                    label = c
                                    break
                    except Exception:
                        pass
                legend_entries.append((label, color))
            # 2. 补充材料卡中定义但未被栅元引用的材料
            if hasattr(self, 'main_window') and hasattr(self.main_window, 'tab_mat'):
                try:
                    for m in self.main_window.tab_mat.get_materials():
                        if m.number not in mat_seen:
                            mat_seen[m.number] = True
                            color = _get_mat_color(m.number)
                            label = str(m.comment or '').strip() or f"M{m.number}"
                            legend_entries.append((label, color))
                except Exception:
                    pass

            # 构建 QColor 版图例数据（用于渲染控制窗口）
            legend_qc: list[tuple[str, QColor]] = []
            for lbl, rgb in legend_entries:
                legend_qc.append((lbl, QColor(int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))))

            # 按体积排序：外层（大）半透明，内层（小）实心
            cell_meshes = []
            for cell_num, stl_path in result.items():
                mesh = pv.read(stl_path)
                if mesh.n_cells == 0:
                    continue
                mat = _material_of(cell_num)
                cell_meshes.append((cell_num, mesh, mat,
                                    abs(mesh.volume) if hasattr(mesh, 'volume') else 0))
            cell_meshes.sort(key=lambda x: x[3])

            plot = _BgPlotter()
            plot.add_axes()

            # 计算模型包围盒对角线
            all_meshes = [m for _, m, _, _ in cell_meshes]
            if all_meshes:
                bbox = [float('inf'), float('-inf')] * 3
                for m in all_meshes:
                    b = m.bounds
                    for i in range(3):
                        bbox[2*i] = min(bbox[2*i], b[2*i])
                        bbox[2*i+1] = max(bbox[2*i+1], b[2*i+1])
                diag = ((bbox[1]-bbox[0])**2 + (bbox[3]-bbox[2])**2 + (bbox[5]-bbox[4])**2)**0.5 or 100
            else:
                bbox = [-50, 50, -50, 50, -50, 50]
                diag = 100
            extent = max(abs(bbox[0]), abs(bbox[1]), abs(bbox[2]),
                         abs(bbox[3]), abs(bbox[4]), abs(bbox[5])) * 1.5

            # === Deep Module: CoordAids ===
            coord = CoordAids(plot, extent, diag)
            coord.setup()

            # === Deep Module: OpacityController ===
            op_ctrl = OpacityController()
            _actors = []
            self._3d_cell_actors.clear()
            for cell_num, mesh, mat, vol in cell_meshes:
                if mat == 0:
                    color = (0.75, 0.75, 0.75)  # 真空栅元用浅灰
                    base_op = 0.5
                else:
                    color = _get_mat_color(mat)
                    if color is None:
                        continue
                    if vol > 1e6:
                        base_op = 0.35
                    elif vol > 1e4:
                        base_op = 0.65
                    else:
                        base_op = 1.0
                actor = plot.add_mesh(mesh, color=color, opacity=base_op)
                _actors.append((actor, base_op, mesh.center))
                # 实时显隐：找到对应 cell，设置 actor 初始可见性
                cell_obj = next((c for c in self.cells if c.number == cell_num), None)
                if cell_obj is not None and not getattr(cell_obj, 'render', True):
                    actor.SetVisibility(False)
                self._3d_cell_actors[cell_num] = actor
            op_ctrl.set_actors(_actors)
            self._3d_plotter = plot

            # ── 摄像机事件回调 ──
            def _on_render(obj, event):
                op_ctrl.update(plot.camera_position[0])
                coord.on_render()

            def _on_interaction_end(obj, event):
                _on_render(None, None)
                coord.rebuild_ticks()
                print("[_on_interaction_end]")

            plot.iren.add_observer("RenderEvent", _on_render)
            plot.iren.add_observer("EndInteractionEvent", _on_interaction_end)

            # ── 键盘控制摄像头（直接观察 iren，绕过坏掉的 add_key_event）──
            def _cam_move(dz):
                cam = plot.camera; p = list(cam.GetPosition()); f = list(cam.GetFocalPoint())
                fw = (f[0]-p[0], f[1]-p[1], f[2]-p[2])
                d = (fw[0]**2 + fw[1]**2 + fw[2]**2)**0.5
                if d < 1e-10: return
                fx, fy, fz = fw[0]/d, fw[1]/d, fw[2]/d
                cam.SetPosition(p[0]+fx*d*0.15*dz, p[1]+fy*d*0.15*dz, p[2]+fz*d*0.15*dz)
                _on_render(None, None)
                plot.ren_win.Render()

            def _cam_strafe(dx):
                cam = plot.camera; p = list(cam.GetPosition()); f = list(cam.GetFocalPoint())
                u = list(cam.GetViewUp())
                fw = (f[0]-p[0], f[1]-p[1], f[2]-p[2])
                d = (fw[0]**2 + fw[1]**2 + fw[2]**2)**0.5
                if d < 1e-10: return
                fx, fy, fz = fw[0]/d, fw[1]/d, fw[2]/d
                rt = (fy*u[2]-fz*u[1], fz*u[0]-fx*u[2], fx*u[1]-fy*u[0])
                s = d * 0.15
                cam.SetPosition(p[0]+rt[0]*dx*s, p[1]+rt[1]*dx*s, p[2]+rt[2]*dx*s)
                cam.SetFocalPoint(f[0]+rt[0]*dx*s, f[1]+rt[1]*dx*s, f[2]+rt[2]*dx*s)
                _on_render(None, None)
                plot.ren_win.Render()

            def _cam_roll(angle):
                """绕视线方向旋转（滚筒），直接用 VTK 方法"""
                import math
                cam = plot.camera
                pos = cam.GetPosition(); fp = cam.GetFocalPoint()
                # forward 方向
                fx = fp[0]-pos[0]; fy = fp[1]-pos[1]; fz = fp[2]-pos[2]
                d = (fx*fx+fy*fy+fz*fz)**0.5
                fx, fy, fz = fx/d, fy/d, fz/d
                # 当前 ViewUp
                ux, uy, uz = cam.GetViewUp()
                # right = forward × up（叉积）
                rx = fy*uz - fz*uy
                ry = fz*ux - fx*uz
                rz = fx*uy - fy*ux
                r_len = (rx*rx+ry*ry+rz*rz)**0.5
                rx, ry, rz = rx/r_len, ry/r_len, rz/r_len
                # 在 (up, right) 平面旋转 angle 度
                rad = math.radians(angle); c, s = math.cos(rad), math.sin(rad)
                cam.SetViewUp((ux*c+rx*s, uy*c+ry*s, uz*c+rz*s))
                _on_render(None, None)
                plot.ren_win.Render()

            def _keyboard_cb(caller, event):
                ks = caller.GetKeySym().lower()
                if ks == 'w': _cam_move(1)
                elif ks == 's': _cam_move(-1)
                elif ks == 'a': _cam_strafe(-1)
                elif ks == 'd': _cam_strafe(1)
                elif ks == 'left': _cam_roll(-5)
                elif ks == 'right': _cam_roll(5)

            plot.iren.add_observer('KeyPressEvent', _keyboard_cb)

            # 自动弹出渲染控制窗口
            self._open_render_ctrl()
            # 把材料颜色对照传给渲染控制窗口（替代 3D 图例）
            if self._render_ctrl_win and legend_qc:
                self._render_ctrl_win.set_legend(legend_qc)
            plot.show()
        except Exception as e:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Critical)
            box.setWindowTitle("渲染失败")
            box.setText(str(e))
            box.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            box.exec_()
        finally:
            engine.cleanup()

    def _export_step(self):
        """导出每个栅元为 STEP 文件"""
        self._export_geometry("step")

    def _export_geometry(self, fmt: str):
        """通用导出方法"""
        freecad_bin = StepImporter.detect_freecad()
        if not freecad_bin:
            self._show_freecad_guide()
            return

        default_dir = getattr(self.main_window, 'path_edit', None)
        default_path = default_dir.text().strip() if default_dir else ""
        out_dir = QFileDialog.getExistingDirectory(self, "选择导出目录", default_path)
        if not out_dir:
            return

        surfaces_text = self.surface_text.toPlainText().strip()
        surfs = []
        for line in surfaces_text.split("\n"):
            obj, _ = _parse_surface_line(line)
            if obj is not None:
                surfs.append(obj)

        if not surfs:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("提示")
            box.setText("没有有效的曲面定义")
            box.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            box.exec_()
            return

        tr_cards = self._parse_tr_cards()

        cells_data = []
        raw_cell_text = self._raw_cell.get_raw_text()
        if raw_cell_text:
            from app.generator.parsers.sections import split_sections
            from app.generator.parsers.core import parse_cells
            all_lines = raw_cell_text.split("\n")
            title, cell_lines, _, _ = split_sections(all_lines)
            raw_cells = parse_cells(cell_lines) if cell_lines else []
            for cell in raw_cells:
                expr = cell.surface_expr.strip()
                if not expr:
                    continue
                try:
                    geometry = Geometry.from_mcnp(expr)
                    cells_data.append({
                        "number": cell.number,
                        "material": cell.material,
                        "ast": geometry,
                        "density": cell.density,
                    })
                except Exception:
                    continue
        else:
            for cell in self.cells:
                expr = cell.surface_expr.strip()
                if not expr:
                    continue
                try:
                    geometry = Geometry.from_mcnp(expr)
                    if not getattr(cell, 'render', True):
                        continue
                    cells_data.append({
                        "number": cell.number,
                        "material": cell.material,
                        "ast": geometry,
                        "density": cell.density,
                    })
                except Exception:
                    continue

        if not cells_data:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("提示")
            box.setText("没有有效的栅元定义")
            box.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            box.exec_()
            return

        progress = QProgressDialog(
            "正在导出 " + fmt.upper() + "...", "取消", 0, 0, self
        )
        progress.setModal(True)
        progress.show()
        QApplication.processEvents()

        engine = FreeCADEngine(freecad_bin)
        try:
            files = engine.export_step(surfs, cells_data, tr_cards, out_dir)
            msg = "已导出几何体为 geometry.step (已跳过真空/空气栅元) 到:\n" + out_dir
            QMessageBox.information(self, "导出成功", msg)
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
        finally:
            progress.close()
            engine.cleanup()


    def _import_step(self):
        """调用 McCAD 导入 STEP 文件（通过文件对话框）。"""
        step_path, _ = QFileDialog.getOpenFileName(
            self, "选择 STEP 文件", "",
            "STEP 文件 (*.step *.stp);;所有文件 (*)"
        )
        if not step_path:
            return
        self._run_step_import(step_path)

    def _import_step_path(self, step_path: str):
        """直接传入路径导入 STEP（供拖放调用）。"""
        self._run_step_import(step_path)

    def _run_step_import(self, step_path: str):
        import os
        import re
        material = "MAT"
        density = -1.0

        # 弹出设置对话框
        from app.step_importer import StepImportDialog
        dialog = StepImportDialog(self, material=material, density=abs(density),
                                  step_path=step_path)
        if dialog.exec_() != StepImportDialog.Accepted:
            return

        material = dialog.get_material()
        density = dialog.get_density()
        mccad_settings = dialog.get_settings()

        progress = QProgressDialog("正在转换 STEP → MCNP...", "取消", 0, 0, self)
        progress.setWindowTitle("导入 STEP")
        progress.setModal(True)
        progress.show()
        QApplication.processEvents()

        try:
            from app.step_importer import StepImporter
            deck = StepImporter.import_step(step_path, material, density,
                                            settings=mccad_settings)
            if deck is None:
                QMessageBox.critical(self, "导入失败", "McCAD 未能生成有效的 MCNP 文件。")
                return

            # 填入编辑器
            self.set_data(deck.surfaces if hasattr(deck, 'surfaces') else "",
                          deck.cells if hasattr(deck, 'cells') else [],
                          deck.tr_cards if hasattr(deck, 'tr_cards') else "")

            # 同步到其他标签页
            main_win = self.window()
            if hasattr(main_win, 'tab_basic'):
                if hasattr(deck, 'basic') and deck.basic:
                    main_win.tab_basic.set_data(deck.basic)
                if hasattr(deck, 'materials') and deck.materials:
                    main_win.tab_mat.set_data(deck.materials)
                if hasattr(deck, 'sources') and deck.sources:
                    main_win.tab_sdef.set_data(deck.sources)
                if hasattr(deck, 'tally') and deck.tally:
                    main_win.tab_tally.set_data(deck.tally)

            QMessageBox.information(self, "导入成功",
                f"STEP 文件已成功导入！\n"
                f"栅元: {len(deck.cells) if hasattr(deck, 'cells') else 0} 个\n"
                f"材料: {len(deck.materials) if hasattr(deck, 'materials') else 0} 种"
            )
        except Exception as e:
            QMessageBox.critical(self, "导入失败",
                f"STEP 导入失败:\n{e}")
        finally:
            progress.close()
    def _on_preview_error(self, msg: str):
        """接收后台线程的预览错误并弹窗（支持 Ctrl+C 复制） / Handle preview errors from background thread.

        Displays the error in a message box with selectable text for easy copying.
        This method is connected to _preview_error signal and runs on the main thread.

        Args:
            msg: The error message string from the preview thread.
        """
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("3D 预览失败 / 3D Preview Failed")
        box.setText(msg)
        # Enable text selection so users can copy the error (e.g., Ctrl+C)
        box.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        box.exec_()
