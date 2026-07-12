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
    QSplitter, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSlot

from app.models import CellData
from app.dialogs.cell_edit_dialog import CellEditDialog
from app.widgets.text_mode_section import TextModeSection
from app.generator.inp_generator import _generate_cells


# ===== Surface Parser for 3D Preview =====
# Maps surface type names to (parameter_count, pymcnp_class) tuples.
# Used to dynamically parse surface definitions for 3D visualization.
# The parser registry is populated lazily to avoid circular imports with pymcnp.

_SURFACE_PARSERS = {}  # {typename: (param_count, pymcnp_class)}


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

    Registers all supported MCNP surface types on first call.
    Must be called before any surface parsing occurs.
    This function is idempotent — subsequent calls are no-ops once registered.

    Registered surface types:
        - Planes: P, PX, PY, PZ, X, Y, Z (1 param)
        - Spheres: SO, S, SX, SY, SZ (1 param)
        - Cylinders: CX, CY, CZ, C/X, C/Y, C/Z (1 param)
        - Cones: KX, KY, KZ, K/X, K/Y, K/Z (3 params)
        - Quadratic: SQ (10 params), GQ (10+ params)
        - Torii: TX, TY, TZ (6 params)
        - Macrobodies: RPP, SPH, RCC, TRC
    """
    if _SURFACE_PARSERS:
        return
    import pymcnp.inp as pi
    # Single-parameter planes (planes perpendicular to axes)
    _register("PX", 1, pi.Px); _register("PY", 1, pi.Py); _register("PZ", 1, pi.Pz)
    # Spheres: general (SO) and centered on axes (Sx, Sy, Sz)
    _register("SO", 1, pi.So); _register("S", 1, pi.So)
    _register("SX", 1, pi.Sx); _register("SY", 1, pi.Sy); _register("SZ", 1, pi.Sz)
    # Cylinders: axis-aligned (Cx, Cy, Cz) and angled (C/X, C/Y, C/Z)
    _register("CX", 1, pi.Cx); _register("CY", 1, pi.Cy); _register("CZ", 1, pi.Cz)
    _register("C/X", 1, pi.C_x); _register("C/Y", 1, pi.C_y); _register("C/Z", 1, pi.C_z)
    # Cones (3 parameters: vertex x, t-squared, +/-1 sign)
    _register("KX", 3, pi.Kx); _register("KY", 3, pi.Ky); _register("KZ", 3, pi.Kz)
    _register("K/X", 3, pi.K_x); _register("K/Y", 3, pi.K_y); _register("K/Z", 3, pi.K_z)
    # Quadratic surfaces: SQ (10 params) and GQ (10+ params)
    _register("SQ", 10, pi.Sq); _register("GQ", 10, pi.Gq)
    # Torii (6 parameters)
    _register("TX", 6, pi.Tx); _register("TY", 6, pi.Ty); _register("TZ", 6, pi.Tz)
    # Macrobodies: rectangular parallelepiped, sphere, right circular cylinder, truncated cone
    _register("RPP", 6, pi.Rpp)   # xmin xmax ymin ymax zmin zmax
    _register("SPH", 4, pi.Sph)   # vx vy vz r
    _register("RCC", 7, pi.Rcc)   # vx vy vz hx hy hz r
    _register("TRC", 8, pi.Trc)   # vx vy vz hx hy hz r1 r2
    # Plane aliases (single-letter forms)
    _register("X", 1, pi.X); _register("Y", 1, pi.Y); _register("Z", 1, pi.Z)


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
        return (None, f"格式不完整: {line[:60]} / Incomplete format: {line[:60]}")

    # Extract surface number (must be an integer)
    surf_num = parts[0]
    try:
        surf_num = int(surf_num)
    except ValueError:
        return (None, f"曲面号非数字: {line[:60]} / Surface number is not numeric: {line[:60]}")

    # Handle optional TRn transform prefix (e.g., "TR1" before surface type)
    # TRn prefixes reference a transformation defined elsewhere in the input.
    tr_val = None
    type_idx = 1
    if parts[1].upper().startswith("TR") and len(parts) > 2:
        tr_val = parts[1]
        type_idx = 2

    if type_idx >= len(parts):
        return (None, f"缺少曲面类型: {line[:60]} / Missing surface type: {line[:60]}")

    surf_type = parts[type_idx].upper()
    params = parts[type_idx + 1:]

    # Check if the surface type is supported
    if surf_type not in _SURFACE_PARSERS:
        return (None, f"不支持的曲面类型: {surf_type} / Unsupported surface type: {surf_type}")

    min_params, cls = _SURFACE_PARSERS[surf_type]
    if len(params) < min_params:
        return (None, f"参数不足: 需要≥{min_params}个, 实际{len(params)}个 ({surf_type}) "
                      f"/ Insufficient params: need ≥{min_params}, got {len(params)} ({surf_type})")

    # Convert parameter strings to floats
    try:
        float_params = [float(p) for p in params[:min_params]]
    except ValueError:
        return (None, f"参数非数字: {line[:60]} / Non-numeric parameters: {line[:60]}")

    # Create the pymcnp surface object
    try:
        obj = cls(*float_params, number=surf_num)
        if tr_val:
            # pymcnp surface may support transform parameter
            # Currently not applied; left for future implementation
            import pymcnp.inp as pi
            pass
        return (obj, None)
    except Exception as e:
        return (None, f"创建 {surf_type} 失败: {e} / Failed to create {surf_type}: {e}")


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
        self._preview_error.connect(self._on_preview_error)
        self.init_ui()

    def init_ui(self):
        """Build the complete geometry tab UI layout.

        Creates a scrollable layout with a vertical splitter containing:
        1. Surface card group: free-text editor for surface definitions + 3D preview button
        2. Cell card group: table of cells with add/delete/edit toolbar + text mode toggle

        The splitter allows users to resize the relative height of the surface
        and cell card sections.
        """
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)

        # Use a vertical splitter to allow resizing between surface and cell areas
        splitter = QSplitter(Qt.Vertical)
        splitter.setMinimumHeight(400)

        # ===== 曲面卡（大文本框）/ Surface Cards (Large Text Box) =====
        # Free-text area for MCNP surface definitions.
        # Each line defines one surface: number, type, and parameters.
        grp_surf = QGroupBox("曲面卡 - 请在此输入曲面定义 / Surface Cards - Enter surface definitions here")
        grp_surf.setToolTip(
            "每行定义一个曲面，格式：\n"
            "曲面号  类型  参数1  参数2 ...\n\n"
            "示例：\n"
            "1  PX  -9\n"
            "2  PY  -9\n"
            "3  PZ  -9\n"
            "10  RCC  0 0 0  0 0 5  2\n\n"
            "⚠ 注意：曲面号不要重复，每行不超过 80 列\n"
            "One surface per line. Format:\n"
            "surf_number  type  param1  param2 ...\n"
            "Surface numbers must be unique. Keep lines under 80 columns."
        )
        surf_layout = QVBoxLayout(grp_surf)

        surf_label = QLabel(
            "格式：<span style='font-family:monospace;'>"
            "曲面号  类型  参数1  参数2 ... / Format: surf#  type  param1  param2 ...</span>"
        )

        self.surface_text = QPlainTextEdit()
        self.surface_text.setPlaceholderText(
            "示例 / Example:\n"
            "1  PX  -9\n"
            "2  PY  -9\n"
            "3  PZ  -9\n"
            "4  PX   9\n"
            "5  PY   9\n"
            "6  PZ   9\n"
            "7  CZ   5\n"
        )
        self.surface_text.setToolTip(
            "每行一个曲面，支持所有 MCNP 曲面类型：\n"
            "P/PX/PY/PZ (平面), SO/S/SX/SY/SZ (球),\n"
            "CX/CY/CZ/C/X/C/Y/C/Z (圆柱),\n"
            "KX/KY/KZ/K/X/K/Y/K/Z (锥),\n"
            "SQ/GQ (二次曲面), TX/TY/TZ (环),\n"
            "Macrobody: RPP/RCC/SPH/BOX/REC/TRC/ELL/WED/ARB 等\n\n"
            "One surface per line. Supports all MCNP surface types."
        )
        self.surface_text.setMinimumHeight(80)

        surf_layout.addWidget(surf_label)
        surf_layout.addWidget(self.surface_text)

        # 3D preview button row
        surf_btn_layout = QHBoxLayout()
        surf_btn_layout.addStretch()
        self.btn_3d = QPushButton("🔍 3D 预览 / 3D Preview")
        self.btn_3d.setToolTip(
            "基于当前曲面和栅元定义打开 3D 几何预览窗口。\n"
            "使用 pyvista 渲染，支持鼠标旋转/缩放。\n"
            "不支持的曲面类型将被跳过。\n"
            "Open 3D geometry preview based on current surfaces and cells.\n"
            "Uses pyvista rendering with mouse rotate/zoom support.\n"
            "Unsupported surface types will be skipped."
        )
        self.btn_3d.setProperty("cssClass", "btnPrimary")
        self.btn_3d.clicked.connect(self._preview_3d)
        surf_btn_layout.addWidget(self.btn_3d)
        surf_layout.addLayout(surf_btn_layout)
        splitter.addWidget(grp_surf)

        # ===== 栅元卡（列表 + 编辑弹窗）/ Cell Cards (Table + Dialog Editor) =====
        # Table-based cell card management with dialog editing.
        # Each cell has: number, material, density, importance, comment, and surface expression.
        grp_cell = QGroupBox("栅元卡 / Cell Cards")
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
        cell_toolbar.addWidget(QLabel("栅元列表 / Cell List:"))
        cell_toolbar.addStretch()

        self.btn_add_cell = QPushButton("+ 添加栅元 / Add Cell")
        self.btn_add_cell.setToolTip("新增一个栅元，材料默认 void（0） / Add a new cell with default void material (0)")
        self.btn_add_cell.setProperty("cssClass", "btnAdd")
        self.btn_add_cell.clicked.connect(self._add_cell)

        self.btn_del_cell = QPushButton("× 删除选中 / Delete Selected")
        self.btn_del_cell.setToolTip("删除列表中选中的栅元 / Delete the selected cells from the list")
        self.btn_del_cell.setProperty("cssClass", "btnDelete")
        self.btn_del_cell.clicked.connect(self._delete_cell)

        cell_toolbar.addWidget(self.btn_add_cell)
        cell_toolbar.addWidget(self.btn_del_cell)

        # Text mode toggle button for switching between form and raw text editing
        # TextModeSection provides a toggle button and stacked widget for dual-mode editing.
        self._raw_cell = TextModeSection(
            form_widget=QWidget(),
            generate_fn=lambda: "\n".join(_generate_cells(self.cells)),
            section_name="cells",
        )
        cell_toolbar.addWidget(self._raw_cell.toggle_btn)
        cell_layout.addLayout(cell_toolbar)

        # Cell table: displays all cells with key properties
        # Columns: cell number, material (with comment), density, neutron importance, comment, action
        self.cell_table = QTableWidget(0, 6)
        self.cell_table.setHorizontalHeaderLabels(
            ["栅元号 / Cell#", "材料号 / Material", "密度 / Density", "IMP:N / Importance", "注释 / Comment", "操作 / Action"]
        )
        header = self.cell_table.horizontalHeader()
        # Configure column resize modes for a clean layout
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.Interactive)
        header.setSectionResizeMode(5, QHeaderView.Interactive)
        # Set initial column widths
        header.resizeSection(0, 60)
        header.resizeSection(1, 140)
        header.resizeSection(2, 100)
        header.resizeSection(3, 60)
        header.resizeSection(4, 120)
        header.resizeSection(5, 80)
        header.setStretchLastSection(False)
        # Make table read-only; editing is done via dialog to ensure data integrity
        self.cell_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cell_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cell_table.setToolTip("双击行或点击编辑按钮可编辑栅元参数 / Double-click a row or click Edit to modify cell parameters")

        # Replace the stack widget's first page with the table
        self._raw_cell.stack.removeWidget(self._raw_cell.stack.widget(0))
        self._raw_cell.stack.insertWidget(0, self.cell_table)
        cell_layout.addWidget(self._raw_cell.stack)
        splitter.addWidget(grp_cell)

        layout.addWidget(splitter, 1)

        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ---------- 公开接口 / Public Interface ----------
    # These methods are called by the MainWindow and INP generator.

    def get_surfaces(self) -> str:
        """获取曲面卡文本 / Get the surface card text.

        Returns:
            str: The raw surface definitions as entered by the user.
        """
        return self.surface_text.toPlainText().strip()

    def get_cells(self) -> list[CellData]:
        """获取栅元卡数据列表 / Get the cell card data list.

        Returns:
            list[CellData]: The list of cell data objects.
        """
        return self.cells

    def set_data(self, surfaces: str, cells: list[CellData]):
        """从导入数据回填 UI（用于 INP 导入） / Populate UI from imported data (for INP import).

        Args:
            surfaces: Surface definition text to restore.
            cells: List of cell data objects to restore.
        """
        self.surface_text.setPlainText(surfaces)
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
            return items + ["0 (void / 真空 / vacuum)"]
        return ["0 (void / 真空 / vacuum)"]

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
            return "0 (void / 真空 / vacuum)"
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

    # ---------- 内部操作 / Internal Operations ----------
    # These methods handle table management, cell CRUD, and UI refresh.

    def _refresh_table(self):
        """刷新栅元表格显示 / Refresh the cell table display.

        Rebuilds all table rows from the current cells list.
        Each row shows: cell number, material (with comment), density,
        neutron importance, comment, and an edit button.
        Called after any cell data change (add, edit, delete, import).
        """
        self.cell_table.setRowCount(len(self.cells))
        for i, cell in enumerate(self.cells):
            self.cell_table.setItem(i, 0, QTableWidgetItem(str(cell.number)))
            self.cell_table.setItem(i, 1, QTableWidgetItem(
                self._get_material_display(cell.material)
            ))
            self.cell_table.setItem(i, 2, QTableWidgetItem(
                cell.density if cell.density else "(void)"
            ))
            self.cell_table.setItem(i, 3, QTableWidgetItem(cell.imp_n))
            self.cell_table.setItem(i, 4, QTableWidgetItem(cell.comment))

            # Edit button for each row
            # Opens the CellEditDialog when clicked.
            btn_edit = QPushButton("✎ 编辑 / Edit")
            btn_edit.setToolTip("编辑此栅元的详细参数 / Edit detailed parameters of this cell")
            btn_edit.setProperty("cssClass", "btnEdit")
            btn_edit.clicked.connect(lambda checked, idx=i: self._edit_cell(idx))
            self.cell_table.setCellWidget(i, 5, btn_edit)

    def _add_cell(self):
        """添加新栅元（默认 void） / Add a new cell (default void material).

        Creates a cell with void material (0), zero importance for neutrons,
        and no surface expression. The cell number is auto-assigned.
        """
        new_number = self._next_cell_number()
        cell = CellData(
            number=new_number,
            material="0 (void / 真空 / vacuum)",
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

    # ---------- 3D 预览 / 3D Preview ----------
    # Generates a pyvista-based 3D visualization of the geometry.
    # Runs in a separate thread to keep the UI responsive.

    def _preview_3d(self):
        """基于当前曲面和栅元定义生成 3D 几何预览 / Generate 3D geometry preview from current surfaces and cells.

        Parses surface definitions, builds pymcnp cell objects, and launches
        a pyvista-based 3D visualization window. Each material gets a different
        color for visual distinction. Runs the visualizer in a separate thread
        to avoid blocking the UI.

        The process:
            1. Parse surface definitions from text using _parse_surface_line
            2. Build pymcnp Cell objects from cell data with geometry expressions
            3. Create pymcnp Inp object and launch pyvista Plotter in a daemon thread

        Errors and warnings are collected and displayed to the user.
        """
        import pymcnp

        surfaces_text = self.surface_text.toPlainText().strip()
        if not surfaces_text and not self.cells:
            QMessageBox.information(self, "提示 / Info", "请先定义曲面和栅元 / Please define surfaces and cells first")
            return

        # 1. Parse surface definitions from text
        surfs = []
        warnings = []
        for line in surfaces_text.split("\n"):
            obj, warn = _parse_surface_line(line)
            if obj is not None:
                surfs.append(obj)
            if warn:
                warnings.append(warn)

        if not surfs:
            msg = "未解析到有效的曲面对象。 / No valid surface objects parsed."
            if warnings:
                msg += f"\n\n警告（前5条） / Warnings (first 5):\n" + "\n".join(warnings[:5])
            QMessageBox.warning(self, "无法预览 / Cannot Preview", msg)
            return

        # 2. Build pymcnp cell objects from cell data
        # Use Geometry.from_mcnp() for string parsing to avoid pymcnp
        # Geometry.py _Unary.to_show calling surface to_show with incorrect arguments
        from pymcnp.inp.cell import Imp
        from pymcnp.inp import Cell as PymcnpCell
        from pymcnp.types.Geometry import Geometry

        cells_pymcnp = []
        build_errors = []
        for cell in self.cells:
            expr = cell.surface_expr.strip()
            if not expr:
                continue

            # Parse the boolean surface expression
            # Geometry.from_mcnp() parses MCNP boolean surface notation.
            try:
                geometry = Geometry.from_mcnp(expr)
            except Exception as e:
                build_errors.append(f"栅元 {cell.number}: 表达式 '{expr}' 解析失败 — {e} / Cell {cell.number}: expression parse failed — {e}")
                continue

            # Extract material number (strip "M" prefix if present)
            mat_str = cell.material
            if " " in mat_str:
                mat_str = mat_str.split()[0]
            if mat_str.startswith("M"):
                mat_str = mat_str[1:]
            mat_num = int(mat_str) if mat_str.lstrip('-').isdigit() else 0

            # Set neutron importance (default to 1 if not specified)
            options = [
                Imp(designator='n', importance=int(cell.imp_n) if cell.imp_n.isdigit() else 1)
            ]

            # Set density for non-void materials
            density = None
            if mat_num != 0:
                dens_str = cell.density.strip()
                density = float(dens_str) if dens_str else -1.0

            try:
                cells_pymcnp.append(PymcnpCell(
                    material=mat_num, geometry=geometry, density=density,
                    options=options
                ))
            except Exception as e:
                build_errors.append(f"栅元 {cell.number}: 创建失败 — {e} / Cell {cell.number}: creation failed — {e}")

        if not cells_pymcnp:
            msg = "未能从栅元定义构建 3D 几何。 / Could not build 3D geometry from cell definitions."
            if build_errors:
                msg += "\n\n错误详情 / Error Details:\n" + "\n".join(build_errors[:5])
            QMessageBox.warning(self, "无法预览 / Cannot Preview", msg)
            return

        # 3. Build pymcnp Inp object and launch 3D visualization
        try:
            inp = pymcnp.Inp(
                title="3D Geometry Preview",
                cells=cells_pymcnp,
                surfaces=surfs,
                data=[],
            )

            # Inner function running in a separate thread to avoid blocking UI
            def _show():
                try:
                    import pyvista
                    # Build surface dictionary (consistent with to_show_cells internal logic)
                    # Maps surface numbers to their pyvista-compatible mesh objects.
                    surf_map = {}
                    for surf in inp.surfaces:
                        surf_map[str(surf.number)] = surf.to_show()

                    # Material-to-color mapping
                    # High-distinction color cycle indexed by material number
                    # 0 = void (transparent), 1+ = distinct colors
                    _COLORS = [
                        None,                  # 0: void 透明 / transparent
                        (0.12, 0.47, 0.71),    # 1: 蓝 / blue
                        (0.85, 0.37, 0.01),    # 2: 橙 / orange
                        (0.20, 0.63, 0.17),    # 3: 绿 / green
                        (0.74, 0.13, 0.13),    # 4: 红 / red
                        (0.44, 0.18, 0.66),    # 5: 紫 / purple
                        (0.00, 0.58, 0.58),    # 6: 青 / cyan
                        (0.77, 0.55, 0.00),    # 7: 金 / gold
                        (0.18, 0.31, 0.31),    # 8: 深青 / dark cyan
                        (0.58, 0.00, 0.33),    # 9: 洋红 / magenta
                        (0.30, 0.75, 0.93),    # 10: 天蓝 / sky blue
                        (1.00, 0.65, 0.00),    # 11: 琥珀 / amber
                        (0.50, 0.80, 0.20),    # 12: 草绿 / grass green
                        (0.95, 0.50, 0.55),    # 13: 粉红 / pink
                        (0.55, 0.35, 0.75),    # 14: 淡紫 / lavender
                        (0.00, 0.75, 0.75),    # 15: 湖蓝 / lake blue
                        (0.85, 0.70, 0.20),    # 16: 芥末 / mustard
                        (0.80, 0.35, 0.25),    # 17: 砖红 / brick red
                        (0.40, 0.40, 0.60),    # 18: 灰蓝 / gray blue
                        (0.40, 0.70, 0.40),    # 19: 翠绿 / emerald green
                    ]
                    def _mat_color(mat):
                        mat = int(mat)  # Convert pymcnp Integer type to native int
                        if mat < len(_COLORS):
                            return _COLORS[mat]
                        # For materials beyond the predefined list, generate color via hash
                        # Provides a deterministic color for any material number.
                        import hashlib
                        h = hashlib.md5(str(mat).encode()).digest()
                        return (h[0]/255, h[1]/255, h[2]/255)

                    # Create pyvista plotter and render all cells
                    plot = pyvista.Plotter()
                    plot.add_axes()

                    cell_shapes = {}
                    for cell in inp.cells:
                        if isinstance(cell, pymcnp.inp.Cell):
                            shape = cell.to_show(surf_map, cell_shapes)
                        elif isinstance(cell, pymcnp.inp.Like):
                            # Like cells reference another cell's shape
                            # Uses the previously computed shape from the referenced cell.
                            shape = cell_shapes.get(str(cell.cell))
                            if shape is None:
                                continue
                        else:
                            continue
                        cell_shapes[str(cell.number)] = shape

                        mat = cell.material if hasattr(cell, 'material') else 0
                        color = _mat_color(mat)
                        if color is not None:
                            plot.add_mesh(shape.surface, color=color, opacity=0.85)

                    plot.show()
                except Exception as e:
                    import traceback
                    # Emit error signal back to main thread for display
                    # PyQt signals are thread-safe for cross-thread communication.
                    self._preview_error.emit(
                        f"可视化启动失败: / Failed to start visualization:\n"
                        f"{type(e).__name__}: {e}\n\n"
                        f"{traceback.format_exc()[-500:]}"
                    )

            # Launch visualization in a daemon thread to keep UI responsive
            # Daemon thread exits automatically when the main application exits.
            import threading
            t = threading.Thread(target=_show, daemon=True)
            t.start()

            # Show any warnings/errors that occurred during preparation
            if warnings or build_errors:
                parts = []
                if warnings:
                    parts.append(f"曲面警告 ({len(warnings)} 条) / Surface warnings:\n" + "\n".join(warnings[:5]))
                if build_errors:
                    parts.append(f"栅元警告 ({len(build_errors)} 条) / Cell warnings:\n" + "\n".join(build_errors[:5]))
                if parts:
                    QMessageBox.information(self, "3D 预览 / 3D Preview",
                        f"预览已启动（独立窗口）。\n\n"
                        f"Preview started (separate window).\n\n" + "\n\n".join(parts)
                    )

        except Exception as e:
            QMessageBox.critical(self, "3D 预览失败 / 3D Preview Failed", str(e))

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
