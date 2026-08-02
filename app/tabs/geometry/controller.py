"""Geometry — 控制器层"""

import re, hashlib, os, webbrowser

from PyQt5.QtWidgets import (
    QWidget, QTableWidgetItem, QPushButton, QMessageBox,
    QHBoxLayout, QHeaderView, QLabel, QSplitter,
    QApplication, QProgressDialog, QFileDialog,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings
from PyQt5.QtGui import QColor

from app.models import CellData
from app.widgets.cross_section_window import CellSlice, _compute_plane_origin
from app.widgets.render_ctrl import RenderControlWindow
from app.widgets.mcnp_highlighter import _SURFACE_TYPES
from app.style import PALETTES
from app.step_importer import StepImporter
from app.dialogs.cell_edit_dialog import CellEditDialog
from app.freecad_preview import FreeCADEngine
from .view import create_ui


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


# ===== Surface Parser for 3D Preview =====
_SURFACE_PARSERS = {}


def _register(name, count, cls):
    for alias in (name.upper(), name.lower()):
        _SURFACE_PARSERS[alias] = (count, cls)


def _lazy_register():
    if _SURFACE_PARSERS:
        return
    import pymcnp.inp as pi
    _register("PX", 1, pi.Px); _register("PY", 1, pi.Py); _register("PZ", 1, pi.Pz)
    _register("SO", 1, pi.So)
    _register("S", 4, pi.S)
    _register("SX", 2, pi.Sx); _register("SY", 2, pi.Sy); _register("SZ", 2, pi.Sz)
    _register("CX", 1, pi.Cx); _register("CY", 1, pi.Cy); _register("CZ", 1, pi.Cz)
    _register("C/X", 3, pi.C_x); _register("C/Y", 3, pi.C_y); _register("C/Z", 3, pi.C_z)
    _register("KX", 3, pi.Kx); _register("KY", 3, pi.Ky); _register("KZ", 3, pi.Kz)
    _register("K/X", 5, pi.K_x); _register("K/Y", 5, pi.K_y); _register("K/Z", 5, pi.K_z)
    _register("SQ", 10, pi.Sq)
    _register("GQ", 10, pi.Gq)
    _register("TX", 6, pi.Tx); _register("TY", 6, pi.Ty); _register("TZ", 6, pi.Tz)
    _register("X", 6, pi.X); _register("Y", 6, pi.Y); _register("Z", 6, pi.Z)
    _register("RPP", 6, pi.Rpp)
    _register("SPH", 4, pi.Sph)
    _register("RCC", 7, pi.Rcc)
    _register("TRC", 8, pi.Trc)
    _register("REC", 12, pi.Rec)
    _register("ELL", 7, pi.Ell)
    _register("WED", 12, pi.Wed)
    _register("BOX", 12, pi.Box)
    _register("ARB", 30, pi.Arb)
    _register("RHP", 15, pi.Rhp)
    _register("HEX", 15, pi.Rhp)


def _parse_surface_line(line: str) -> tuple:
    _lazy_register()
    stripped = line.strip()
    if not stripped or stripped.startswith("C ") or stripped.startswith("c "):
        return (None, None)
    if "$" in stripped:
        stripped = stripped.split("$")[0].strip()
    if not stripped:
        return (None, None)
    parts = stripped.split()
    if len(parts) < 2:
        return (None, f"格式不完整: {line[:60]}")
    surf_num = parts[0]
    surf_prefix = ""
    if surf_num.startswith("*") or surf_num.startswith("+"):
        surf_prefix = surf_num[0]
        surf_num = surf_num[1:]
    try:
        surf_num = int(surf_num)
    except ValueError:
        return (None, f"曲面号非数字: {line[:60]}")
    tr_val = None
    type_idx = 1
    tr_candidate = parts[1].upper()
    if tr_candidate.startswith("TR") and len(parts) > 2 and tr_candidate[2:].isdigit():
        tr_val = parts[1]
        type_idx = 2
    elif len(parts) > 2:
        try:
            n_val = int(parts[1])
            surf_type_check = parts[2].upper()
            if n_val != 0 and (surf_type_check in _SURFACE_PARSERS or surf_type_check == "P"):
                tr_val = parts[1]
                type_idx = 2
        except ValueError:
            pass
    if type_idx >= len(parts):
        return (None, f"缺少曲面类型: {line[:60]}")
    surf_type = parts[type_idx].upper()
    params = parts[type_idx + 1:]
    if surf_type == "P":
        import pymcnp.inp as pi
        if len(params) == 4:
            min_params, cls = 4, pi.P_0
        elif len(params) == 9:
            min_params, cls = 9, pi.P_1
        else:
            return (None, f"P 曲面参数数必须为 4（方程系数 A B C D）或 9（三点定义），"
                          f"实际 {len(params)} 个")
    else:
        if surf_type not in _SURFACE_PARSERS:
            return (None, f"不支持的曲面类型: {surf_type}")
        min_params, cls = _SURFACE_PARSERS[surf_type]
    if len(params) < min_params:
        return (None, f"参数不足: 需要≥{min_params}个, 实际{len(params)}个 ({surf_type})")
    try:
        float_params = [float(p) for p in params[:min_params]]
    except ValueError:
        return (None, f"参数非数字: {line[:60]}")
    try:
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

    _preview_error = pyqtSignal(str)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.cells: list[CellData] = []
        self._render_ctrl_win: RenderControlWindow = None
        self._cross_section_window = None
        self._freecad_engine: FreeCADEngine = None
        self._3d_plotter = None
        self._3d_cell_actors: dict[int, object] = {}
        self._coord_aids = None
        self._preview_error.connect(self._on_preview_error)

        ui = create_ui(self, main_window, gen_cell_fn=lambda: self._gen_cell_raw())
        self.ui = ui
        self._surf_hl = ui._surf_hl
        self._tr_hl = ui._tr_hl
        self._raw_cell = getattr(ui, '_raw_cell', None)

        self._connect_signals()
        self._setup_completion()
        # 启动时检测 FreeCAD
        from app.step_importer import StepImporter
        _fc_path = StepImporter.detect_freecad()
        if _fc_path:
            try:
                self._freecad_engine = FreeCADEngine(_fc_path)
                self.ui.lbl_step_warn.setText("✅ FreeCAD 已就绪")
            except Exception:
                self.ui.lbl_step_warn.setText("⚠ FreeCAD 初始化失败")
        else:
            self.ui.lbl_step_warn.setText("⚠ 未检测到 FreeCAD（3D 预览/STEP 导入不可用）")

    def _connect_signals(self):
        self.ui.btn_add_cell.clicked.connect(self._add_cell)
        self.ui.btn_del_cell.clicked.connect(self._delete_cell)
        self.ui.cell_table.doubleClicked.connect(self._edit_cell)
        self.ui.cell_table.horizontalHeader().sectionResized.connect(self._save_cell_col_widths)
        self.ui.btn_import_step.clicked.connect(self._import_step)
        self.ui.btn_3d.clicked.connect(self._preview_3d)
        self.ui.btn_export_step.clicked.connect(self._export_step)
        self.ui.btn_render_ctrl.clicked.connect(self._open_render_ctrl)
        self.ui.btn_cross_section.clicked.connect(self._open_cross_section)

    def _setup_completion(self):
        self.ui.surface_text.set_completion_provider(self._surf_words)
        self.ui.surface_text.set_desc_provider(self._surf_desc)
        self.ui.surface_text.set_ghost_provider(self._surf_ghost)
        self.ui.tr_text.set_completion_provider(self._tr_words)
        self.ui.tr_text.set_ghost_provider(self._tr_ghost)
        # 补词列表由 _surf_words / _tr_words 提供器动态返回，无需额外刷新

    # ── 公开接口 ──

    def get_surfaces(self) -> str:
        return self.ui.surface_text.toPlainText().strip()

    def get_tr_cards(self) -> str:
        return self.ui.tr_text.toPlainText().strip()

    def get_cells(self) -> list[CellData]:
        return self.cells

    def set_data(self, surfaces: str, cells: list[CellData], tr_cards: str = ""):
        self.ui.surface_text.setPlainText(surfaces)
        self.ui.tr_text.setPlainText(tr_cards)
        self.cells = list(cells)
        self._refresh_table()

    def get_raw_overrides(self) -> dict:
        return {"cells": self._raw_cell.get_raw_text() if self._raw_cell else ""}

    def _gen_cell_raw(self) -> str:
        """生成栅元卡的 MCNP 文本（用于 TextModeSection）"""
        from app.generator.inp_generator import _generate_cells
        return "\n".join(_generate_cells(self.cells))

    def add_cell_for_material(self, material_number: int):
        new_number = self._next_cell_number()
        self.cells.append(CellData(
            number=new_number, material=f"M{material_number}",
            density="", surface_expr="", imp_n="", comment="",
        ))
        self._refresh_table()

    def remove_cells_for_material(self, material_number: int) -> int:
        removed = [c for c in self.cells if c.material == f"M{material_number}"]
        self.cells = [c for c in self.cells if c.material != f"M{material_number}"]
        self._refresh_table()
        return len(removed)

    # ── 曲面/TR 补全 ──

    def _surf_words(self) -> list[str]:
        surf_nums: set[str] = set()
        for line in self.ui.surface_text.toPlainText().split("\n"):
            line = line.strip()
            if line and line[0].isdigit():
                parts = line.split()
                if parts and parts[0].isdigit():
                    surf_nums.add(parts[0])
        tr_refs: set[str] = set()
        for m in re.finditer(r"\*?(TR\d+)", self.ui.tr_text.toPlainText(), re.I):
            tr_refs.add(m.group(0).upper())
        return list(_SURFACE_TYPES) + sorted(surf_nums) + sorted(tr_refs) + ["TRCL="]

    def _surf_desc(self, word: str) -> str | None:
        _SURFACE_CN = {
            "P": "一般平面", "PX": "X垂面", "PY": "Y垂面", "PZ": "Z垂面",
            "SO": "原点球", "S": "一般球", "SX": "X轴球", "SY": "Y轴球", "SZ": "Z轴球",
            "CX": "X轴柱", "CY": "Y轴柱", "CZ": "Z轴柱",
            "C/X": "X平柱", "C/Y": "Y平柱", "C/Z": "Z平柱",
            "KX": "X轴锥", "KY": "Y轴锥", "KZ": "Z轴锥",
            "K/X": "X平锥", "K/Y": "Y平锥", "K/Z": "Z平锥",
            "SQ": "轴平二次", "GQ": "一般二次",
            "TX": "X环", "TY": "Y环", "TZ": "Z环",
            "RPP": "长方体", "SPH": "球体", "RCC": "正圆柱", "TRC": "锥台",
            "REC": "椭圆柱", "ELL": "椭球", "WED": "楔形", "BOX": "正交盒",
            "ARB": "多面体", "RHP": "六棱柱", "HEX": "六棱柱",
        }
        return _SURFACE_CN.get(word.upper())

    def _surf_ghost(self, line: str) -> str | None:
        _LABELS = {
            "P": ["A","B","C","D"], "PX":["D"], "PY":["D"], "PZ":["D"],
            "SO":["R"], "S":["x̄","ȳ","z̄","R"],
            "SX":["x̄","R"], "SY":["ȳ","R"], "SZ":["z̄","R"],
            "CX":["R"], "CY":["R"], "CZ":["R"],
            "C/X":["ȳ","z̄","R"], "C/Y":["x̄","z̄","R"], "C/Z":["x̄","ȳ","R"],
            "KX":["x̄","t²","±1"], "KY":["ȳ","t²","±1"], "KZ":["z̄","t²","±1"],
            "K/X":["x̄","ȳ","z̄","t²","±1"], "K/Y":["x̄","ȳ","z̄","t²","±1"], "K/Z":["x̄","ȳ","z̄","t²","±1"],
            "SQ":["A","B","C","D","E","F","G","x̄","ȳ","z̄"], "GQ":["A","B","C","D","E","F","G","H","J","K"],
            "TX":["x̄","ȳ","z̄","A","B","C"], "TY":["x̄","ȳ","z̄","A","B","C"], "TZ":["x̄","ȳ","z̄","A","B","C"],
            "RPP":["Xmin","Xmax","Ymin","Ymax","Zmin","Zmax"], "SPH":["Vx","Vy","Vz","R"],
            "RCC":["Vx","Vy","Vz","Hx","Hy","Hz","R"],
            "TRC":["Vx","Vy","Vz","Hx","Hy","Hz","R1","R2"],
            "REC":["Vx","Vy","Vz","Hx","Hy","Hz","V1x","V1y","V1z","V2x","V2y","V2z"],
            "ELL":["V1x","V1y","V1z","V2x","V2y","V2z","Rm"],
            "WED":["Vx","Vy","Vz","V1x","V1y","V1z","V2x","V2y","V2z","V3x","V3y","V3z"],
            "BOX":["Vx","Vy","Vz","A1x","A1y","A1z","A2x","A2y","A2z","A3x","A3y","A3z"],
            "RHP":["v1","v2","v3","h1","h2","h3","r1","r2","r3","s1","s2","s3","t1","t2","t3"],
            "HEX":["v1","v2","v3","h1","h2","h3","r1","r2","r3","s1","s2","s3","t1","t2","t3"],
        }
        parts = line.strip().split()
        if len(parts) < 2 or not parts[0].isdigit():
            return None
        stype = None; type_idx = -1
        for i, p in enumerate(parts[1:], start=1):
            if p.isalpha():
                stype = p.upper(); type_idx = i; break
        if not stype or '$' in line:
            return None
        labels = _LABELS.get(stype)
        used = len(parts) - type_idx - 1
        ghost_parts = []
        if labels and used < len(labels):
            ghost_parts.append("  ".join(labels[used:]))
        cn = self._surf_desc(stype)
        if cn:
            ghost_parts.append(f"$ {cn}")
        return "  ".join(ghost_parts) if ghost_parts else None

    def _tr_words(self) -> list[str]:
        tr_refs = set()
        for m in re.finditer(r"\*?(TR\d+)", self.ui.tr_text.toPlainText(), re.I):
            tr_refs.add(m.group(0).upper())
        return list(tr_refs) if tr_refs else ["TR"]

    def _tr_ghost(self, line: str) -> str | None:
        parts = line.strip().split()
        if not parts or not re.match(r"\*?TR\d+", parts[0], re.I):
            return None
        labels = ["Tx","Ty","Tz","B1","B2","B3","B4","B5","B6","B7","B8","B9","M"]
        used = len(parts) - 1
        if used >= len(labels):
            return None
        return "  ".join(labels[used:])

    # ── 栅元管理 ──

    def _next_cell_number(self) -> int:
        if not self.cells:
            return 1
        return max(c.number for c in self.cells) + 1

    def _refresh_render_ctrl(self):
        if self._render_ctrl_win is not None and self._render_ctrl_win.isVisible():
            try:
                self._render_ctrl_win.refresh()
            except Exception:
                pass

    def _refresh_table(self):
        self.ui.cell_table.setRowCount(len(self.cells))
        self._refresh_render_ctrl()
        for i, cell in enumerate(self.cells):
            self.ui.cell_table.setItem(i, 0, QTableWidgetItem(str(cell.number)))
            self.ui.cell_table.setItem(i, 1, QTableWidgetItem(str(cell.material)))
            self.ui.cell_table.setItem(i, 2, QTableWidgetItem(cell.density))
            self.ui.cell_table.setItem(i, 3, QTableWidgetItem(cell.imp_n))
            self.ui.cell_table.setItem(i, 4, QTableWidgetItem(cell.comment))
            btn_edit = QPushButton("✎")
            btn_edit.setProperty("cssClass", "btnEdit")
            btn_edit.clicked.connect(lambda checked, idx=i: self._edit_cell_at(idx))
            self.ui.cell_table.setCellWidget(i, 5, btn_edit)
        self._auto_resize_table(self.ui.cell_table)

    @staticmethod
    def _auto_resize_table(table, min_rows=8):
        n = table.rowCount()
        rows = max(min_rows, n)
        hh = table.horizontalHeader().height() or 28
        rh = table.rowHeight(0) if n > 0 else 30
        fw = 2 * table.frameWidth()
        table.setMinimumHeight(hh + rh * rows + fw + 4)

    def _save_cell_col_widths(self):
        if not hasattr(self, '_cell_width_settings'):
            self._cell_width_settings = QSettings("MCNPGen", "MCNPGenerator")
        widths = [self.ui.cell_table.columnWidth(c) for c in range(self.ui.cell_table.columnCount())]
        self._cell_width_settings.setValue("geo_col_widths", widths)

    def _add_cell(self):
        new_num = self._next_cell_number()
        self.cells.append(CellData(number=new_num, material="0", density="",
                                    surface_expr="", imp_n="0", comment=""))
        self._refresh_table()

    def _delete_cell(self):
        rows = sorted(set(idx.row() for idx in self.ui.cell_table.selectedIndexes()), reverse=True)
        if not rows:
            QMessageBox.information(self, "提示", "请先选中要删除的栅元")
            return
        for r in rows:
            if 0 <= r < len(self.cells):
                self.cells.pop(r)
        self._refresh_table()

    def _edit_cell(self, index):
        self._edit_cell_at(index.row())

    def _edit_cell_at(self, idx: int):
        if idx < 0 or idx >= len(self.cells):
            return
        # 构造可用材料列表
        from app.models import MaterialData
        mats = self.main_window.tab_mat.get_materials() if hasattr(self.main_window, 'tab_mat') else []
        mat_list = ["0 (void)"] + [
            f"M{m.number} ({m.comment})" if m.comment else f"M{m.number}"
            for m in mats if isinstance(m, MaterialData)
        ]
        dialog = CellEditDialog(self.cells[idx], mat_list)
        if dialog.exec_() == CellEditDialog.Accepted:
            self.cells[idx] = dialog.get_data()
            self._refresh_table()

    # ── 3D 预览 ──

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

        surfaces_text = self.ui.surface_text.toPlainText().strip()
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
        from pymcnp.types.Geometry import Geometry
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
            self._coord_aids = coord

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

    def _on_preview_error(self, msg: str):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("3D 预览失败 / 3D Preview Failed")
        box.setText(msg)
        box.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        box.exec_()

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
        tr_text = self.ui.tr_text.toPlainText().strip()
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

    def _export_step(self):
        if not self._freecad_engine:
            QMessageBox.warning(self, "导出 STEP", "未检测到 FreeCAD，无法导出。")
            return
        path = QFileDialog.getSaveFileName(self, "导出 STEP 文件", "", "STEP (*.step *.stp)")[0]
        if not path:
            return
        try:
            from app.freecad_preview import FreeCADEngine
            surfs = []
            for line in self.ui.surface_text.toPlainText().strip().split('\n'):
                obj, _ = _parse_surface_line(line.strip())
                if obj is not None: surfs.append(obj)
            cells_data = []
            for c in self.cells:
                if not c.surface_expr.strip(): continue
                from pymcnp.types.Geometry import Geometry
                cells_data.append({"number": c.number, "ast": Geometry.from_mcnp(c.surface_expr), "material": c.material})
            import os
            out_dir = os.path.dirname(path)
            self._freecad_engine.build_geometry(surfs, cells_data, {}, fmt="step", single_file=True)
            QMessageBox.information(self, "导出成功", f"STEP 文件已保存:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _import_step(self):
        from app.step_importer import StepImporter
        path, _ = QFileDialog.getOpenFileName(self, "导入 STEP 文件", "", "STEP (*.step *.stp)")
        if path:
            self._import_step_path(path)

    def _open_cross_section(self):
        """打开截面生成窗口"""
        from app.widgets.cross_section_window import CellSlice
        w = CellSlice(self.cells, self)
        w.exec_()

    def _open_render_ctrl(self):
        """打开渲染控制窗口，联动 3D 预览栅元显隐"""
        from app.widgets.render_ctrl import RenderControlWindow
        from PyQt5.QtGui import QColor
        if self._render_ctrl_win is None or not self._render_ctrl_win.isVisible():
            def _get_cells():
                return self.cells
            def _format_fn(idx, cell):
                mat = cell.material.strip()
                if not mat or mat == "0":
                    return f"栅元 {cell.number} — void", "void"
                mats = self.main_window.tab_mat.get_materials() if hasattr(self.main_window, 'tab_mat') else []
                mat_num = mat.lstrip("M")
                comment = ""
                for m in mats:
                    if str(getattr(m, 'number', '')) == mat_num and getattr(m, 'comment', ''):
                        comment = m.comment
                        break
                if comment:
                    return f"栅元 {cell.number} — M{mat_num} ({comment})", f"M{mat_num} ({comment})"
                return f"栅元 {cell.number} — M{mat_num}", f"M{mat_num}"
            def _on_visibility_changed():
                """同步 3D 预览中的栅元显隐"""
                if not hasattr(self, '_render_ctrl_win') or self._render_ctrl_win is None:
                    return
                rows = getattr(self._render_ctrl_win, '_cell_rows', [])
                cbs = getattr(self._render_ctrl_win, '_checkboxes', [])
                for i, (_, cell_num, _) in enumerate(rows):
                    if i < len(cbs) and cell_num in self._3d_cell_actors:
                        actor = self._3d_cell_actors[cell_num]
                        try:
                            actor.SetVisibility(cbs[i].isChecked())
                        except Exception:
                            pass
            self._render_ctrl_win = RenderControlWindow(
                get_cells_fn=_get_cells,
                format_fn=_format_fn,
                on_changed=_on_visibility_changed,
                on_close_callback=lambda: setattr(self, '_render_ctrl_win', None),
            )
            # 参考点坐标联动
            def _ref_point_callback(pos):
                if self._coord_aids is not None:
                    try:
                        sphere = getattr(self._coord_aids, '_sphere', None)
                        if sphere:
                            sphere.SetCenter(pos[0], pos[1], pos[2])
                            self._coord_aids._coord_text.SetText(
                                2, f'  X: {pos[0]:.1f}   Y: {pos[1]:.1f}   Z: {pos[2]:.1f}  (cm)  ')
                            if self._3d_plotter:
                                self._3d_plotter.render()
                    except Exception:
                        pass
            self._render_ctrl_win.set_ref_point_callback(_ref_point_callback)

            # 设置截面生成回调（基于 3D 预览中的 pyvista 网格）
            def _slice_fn(a, b, c, d_val, selected):
                """返回截面数据用于 CrossSectionWindow"""
                import numpy as np
                plane_params = (a, b, c, d_val)
                cell_slices = []
                bg_color = "#f0f2f5"
                for cell_num_str, actor in self._3d_cell_actors.items():
                    try:
                        mesh = actor.GetMapper().GetInput()
                        if mesh is None:
                            continue
                        # pyvista 裁剪
                        import pyvista as pv
                        pd = pv.wrap(mesh)
                        clipped = pd.clip(origin=(0,0,d_val), normal=(a,b,c), invert=False)
                        if clipped and clipped.n_cells > 0:
                            # 提取截面轮廓
                            contour = clipped.slice(normal=(a,b,c), origin=(0,0,d_val))
                            if contour and contour.n_points > 0:
                                pts = contour.points
                                cell_num = int(cell_num_str)
                                mat = _get_mat_color(cell_num) or (0.7, 0.7, 0.7)
                                cs = type('CS', (), {})()
                                cs.cell_num = cell_num
                                cs.contours = [pts]
                                cs.color = mat
                                cs.material_label = f"Cell {cell_num}"
                                cell_slices.append(cs)
                    except Exception:
                        pass
                return plane_params, cell_slices, bg_color
            self._render_ctrl_win.set_gen_slice_callback(_slice_fn)
            self._render_ctrl_win.show()
            # 初次打开时同步状态
            _on_visibility_changed()
        else:
            self._render_ctrl_win.raise_()
            self._render_ctrl_win.activateWindow()

    def _import_step_path(self, path: str):
        pass
