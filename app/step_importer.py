"""
STEP → MCNP 转换：封装 McCAD（外置转换器）调用 + 输出解析

使用方法：
    from app.step_importer import StepImporter

    # FreeCAD 检测（用于 3D 预览和 STEP 导出）
    bin_path = StepImporter.detect_freecad()

    # McCAD STEP 导入
    deck = StepImporter.import_step("模型.stp", "SS", -7.93)
注：McCAD.exe 为独立子进程，适用 AGPL-3.0 许可证，不影响主程序。
"""

import os
import sys
import json
import re
import shutil
import subprocess
import tempfile
import winreg
import time as _time

from pathlib import Path

from PyQt5.QtCore import QSettings, Qt, QByteArray
from PyQt5.QtWidgets import (
    QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox, QLineEdit,
    QComboBox, QPushButton, QDialogButtonBox, QScrollArea, QWidget,
    QLabel
)


# ===================================================================
# McCAD 导入设置对话框
# ===================================================================

class McCADSettings:
    """McCAD 设置容器 — 默认值 + QSettings 持久化。"""

    KEYS = [
        # 常用
        "voidGeneration", "startCellNum", "startSurfNum", "tmp",
        # 分解
        "decompose", "recurrenceDepth", "minSolidVolume", "minFaceArea",
        "scalingFactor", "precision", "faceTolerance", "edgeTolerance",
        "parameterTolerance", "angularTolerance", "distanceTolerance",
        "simplifyTori", "simplifyAllTori", "torusSplitAngle",
        # 转换
        "compoundIsSingleCell", "minVoidVolume", "maxSolidsPerVoidCell",
        "BVHVoid", "maxLineWidth", "debugLevel", "units", "startMatNum",
    ]

    DEFAULTS = {
        "voidGeneration": True, "startCellNum": 1, "startSurfNum": 1,
        "tmp": "2.53e-8",
        "decompose": True, "recurrenceDepth": 20,
        "minSolidVolume": 1e-3, "minFaceArea": 1e-4,
        "scalingFactor": 100.0, "precision": 1e-6,
        "faceTolerance": 1e-8, "edgeTolerance": 1e-8,
        "parameterTolerance": 1e-8, "angularTolerance": 1e-4,
        "distanceTolerance": 1e-6,
        "simplifyTori": False, "simplifyAllTori": False,
        "torusSplitAngle": 30.0,
        "compoundIsSingleCell": False, "minVoidVolume": 1.0,
        "maxSolidsPerVoidCell": 20, "BVHVoid": False,
        "maxLineWidth": 80, "debugLevel": 0, "units": "cm",
        "startMatNum": 1,
    }

    def __init__(self):
        self._data = dict(self.DEFAULTS)
        self._load()

    def _load(self):
        s = QSettings("MCNPGen", "McCADImport")
        for k in self.KEYS:
            v = s.value(k)
            if v is not None:
                default = self.DEFAULTS[k]
                if isinstance(default, bool):
                    self._data[k] = str(v).lower() in ("true", "1", "yes")
                elif isinstance(default, int):
                    self._data[k] = int(str(v))
                elif isinstance(default, float):
                    self._data[k] = float(str(v))
                else:
                    self._data[k] = v

    def save(self):
        s = QSettings("MCNPGen", "McCADImport")
        for k, v in self._data.items():
            s.setValue(k, v)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        if key in self._data:
            self._data[key] = value

    def update(self, **kw):
        self._data.update(kw)


class _CollapsibleSection(QWidget):
    """可折叠区域：点击标题栏展开/收起内容。"""
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._open = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._btn = QPushButton(f"▶ {title}")
        self._btn.setStyleSheet(
            "QPushButton { text-align: left; padding: 4px 8px; "
            "border: 1px solid #ccc; border-radius: 3px; "
            "background: #f5f5f5; font-weight: bold; }"
            "QPushButton:hover { background: #e0e0e0; }"
        )
        self._btn.setCheckable(True)
        self._btn.setChecked(False)
        self._btn.clicked.connect(self._toggle)
        layout.addWidget(self._btn)

        self._content = QWidget()
        self._content.setVisible(False)
        self._form = QFormLayout(self._content)
        self._form.setContentsMargins(12, 4, 4, 4)
        layout.addWidget(self._content)

    def _toggle(self):
        self._open = not self._open
        self._content.setVisible(self._open)
        self._btn.setText(f"▼ {self._btn.text()[2:]}" if self._open
                          else f"▶ {self._btn.text()[2:]}")

    def add_row(self, label: str, widget):
        self._form.addRow(label, widget)

    def form_layout(self) -> QFormLayout:
        return self._form


class StepImportDialog(QDialog):
    """McCAD 导入设置对话框。常用可见，高级可折叠，设置自动保存。"""

    def __init__(self, parent=None, material="MAT", density=-1.0,
                 step_path=""):
        super().__init__(parent)
        self.setWindowTitle("McCAD 导入设置")
        self.setMinimumWidth(520)
        self._settings = McCADSettings()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)

        # ==================== 常用设置（不折叠） ====================
        common = QGroupBox("常用设置")
        cf = QFormLayout(common)
        self.material_edit = QLineEdit(material)
        cf.addRow("材料名:", self.material_edit)
        self.density_spin = QDoubleSpinBox()
        self.density_spin.setRange(0.001, 100000)
        self.density_spin.setDecimals(4)
        self.density_spin.setValue(abs(density))
        cf.addRow("密度 (g/cm³):", self.density_spin)
        self.tmp_edit = QLineEdit(self._settings["tmp"])
        cf.addRow("TMP 温度 (MeV):", self.tmp_edit)
        self.void_cb = QCheckBox("生成真空栅元")
        self.void_cb.setChecked(self._settings["voidGeneration"])
        cf.addRow("", self.void_cb)
        self.start_cell = QSpinBox()
        self.start_cell.setRange(1, 99999)
        self.start_cell.setValue(self._settings["startCellNum"])
        cf.addRow("起始栅元号:", self.start_cell)
        self.start_surf = QSpinBox()
        self.start_surf.setRange(1, 99999)
        self.start_surf.setValue(self._settings["startSurfNum"])
        cf.addRow("起始曲面号:", self.start_surf)
        self.units_combo = QComboBox()
        self.units_combo.addItems(["cm", "m", "mm"])
        self.units_combo.setCurrentText(self._settings["units"])
        cf.addRow("STEP 单位:", self.units_combo)
        layout.addWidget(common)

        # ==================== 分解设置（折叠） ====================
        decomp = _CollapsibleSection("分解设置")
        for key, label, typ, *args in [
            ("decompose", "启用分解", "bool"),
            ("recurrenceDepth", "递归深度", "int", 1, 100),
            ("minSolidVolume", "最小实体体积 (cm³)", "float", 1e-10, 1e6),
            ("minFaceArea", "最小面面积 (cm²)", "float", 1e-10, 1e6),
            ("scalingFactor", "缩放因子", "float", 0.1, 1e6),
            ("precision", "精度", "float", 1e-12, 1.0),
            ("faceTolerance", "面容差 (cm)", "float", 1e-12, 1.0),
            ("edgeTolerance", "边容差 (cm)", "float", 1e-12, 1.0),
            ("parameterTolerance", "参数容差 (cm)", "float", 1e-12, 1.0),
            ("angularTolerance", "角度容差 (rad/PI)", "float", 1e-12, 1.0),
            ("distanceTolerance", "距离容差 (cm)", "float", 1e-12, 1.0),
            ("simplifyTori", "简化环面", "bool"),
            ("simplifyAllTori", "简化全部环面", "bool"),
            ("torusSplitAngle", "环面分割角度 (°)", "float", 0, 360),
        ]:
            w = self._make_widget(key, typ, *args)
            decomp.add_row(label + ":", w)
        layout.addWidget(decomp)

        # ==================== 转换设置（折叠） ====================
        conv = _CollapsibleSection("转换设置")
        for key, label, typ, *args in [
            ("compoundIsSingleCell", "复合体合并为单栅元", "bool"),
            ("minVoidVolume", "最小真空体积 (cm³)", "float", 1e-10, 1e6),
            ("maxSolidsPerVoidCell", "每真空栅元最大实体数", "int", 1, 1000),
            ("BVHVoid", "BVH 真空", "bool"),
            ("maxLineWidth", "最大行宽", "int", 40, 200),
            ("debugLevel", "调试级别", "int", 0, 3),
            ("startMatNum", "起始材料号", "int", 1, 99999),
        ]:
            w = self._make_widget(key, typ, *args)
            conv.add_row(label + ":", w)
        layout.addWidget(conv)

        # ==================== 按钮 ====================
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.addWidget(scroll)

    def _make_widget(self, key, typ, *args):
        default = self._settings[key]
        if typ == "bool":
            w = QCheckBox()
            w.setChecked(bool(default))
        elif typ == "int":
            w = QSpinBox()
            lo = args[0] if len(args) > 0 else 0
            hi = args[1] if len(args) > 1 else 999999
            w.setRange(lo, hi)
            w.setValue(int(default))
        elif typ == "float":
            w = QDoubleSpinBox()
            lo = args[0] if len(args) > 0 else -1e12
            hi = args[1] if len(args) > 1 else 1e12
            w.setRange(lo, hi)
            w.setDecimals(6)
            w.setValue(float(default))
        else:
            w = QLineEdit(str(default))
        w._key = key
        return w

    def _collect_values(self, parent_widget) -> dict:
        result = {}
        for w in parent_widget.findChildren(QCheckBox):
            if hasattr(w, '_key'):
                result[w._key] = w.isChecked()
        for w in parent_widget.findChildren(QSpinBox):
            if hasattr(w, '_key'):
                result[w._key] = w.value()
        for w in parent_widget.findChildren(QDoubleSpinBox):
            if hasattr(w, '_key'):
                result[w._key] = w.value()
        for w in parent_widget.findChildren(QLineEdit):
            if hasattr(w, '_key'):
                try:
                    result[w._key] = float(w.text())
                except ValueError:
                    result[w._key] = w.text()
        return result

    def _on_accept(self):
        tmp_val = self.tmp_edit.text().strip()
        # TMP 留空 → 不记录，让生成器不输出 TMP=
        if tmp_val == "":
            tmp_val = ""

        data = {
            "voidGeneration": self.void_cb.isChecked(),
            "startCellNum": self.start_cell.value(),
            "startSurfNum": self.start_surf.value(),
            "units": self.units_combo.currentText(),
            "tmp": tmp_val,
        }
        # 折叠区收集的值（不覆盖已存在的显式 key）
        collected = self._collect_values(self)
        for k, v in collected.items():
            if k not in data:
                data[k] = v
        self._settings.update(**data)
        self._settings.save()
        self.accept()

    def get_settings(self) -> dict:
        return dict(self._settings._data)

    def get_material(self) -> str:
        return self.material_edit.text().strip()

    def get_density(self) -> float:
        return -abs(self.density_spin.value())


# ===================================================================
# StepImporter — 公共接口 (Seam)
# ===================================================================

class StepImporter:
    """STEP 导入器。封装 McCAD 外部转换器的调用和输出解析。

    用法：
        StepImporter.detect_freecad()  → FreeCAD bin 目录路径
        StepImporter.import_step(...)  → DeckData
    """

    # --- FreeCAD 检测（已有逻辑，包装为类方法）---

    @classmethod
    def detect_freecad(cls) -> str | None:
        """检测 FreeCAD 可执行文件路径。返回 bin 目录或 None。"""
        return _cached_detect()

    @classmethod
    def save_freecad_path(cls, exe_path: str) -> None:
        """保存 FreeCAD 路径到 QSettings。"""
        settings = QSettings("MCNPGen", "MCNPGenerator")
        settings.setValue("freecad_path", exe_path)

    # --- McCAD 导入 ---

    @classmethod
    def import_step(cls, step_path: str, material: str = "MAT",
                    density: float = -1.0,
                    settings: dict | None = None) -> "DeckData | None":
        """STEP → McCAD 完整转换 → 解析 MCFile.i → DeckData。"""
        if settings is None:
            settings = {}
        converter = McCADConverter()
        if not converter.is_available():
            raise RuntimeError("McCAD 不可用")

        try:
            mcnp_path = converter.run(step_path, material, density,
                                      settings=settings)
        except RuntimeError as e:
            raise RuntimeError(f"McCAD 转换失败: {e}")

        parser = MCNPOutputParser()
        return parser.parse(mcnp_path, post_settings=settings)


# ===================================================================
# McCADConverter — 封装 McCAD 子进程
# ===================================================================

class McCADConverter:
    """封装 McCAD 外部可执行文件的调用。

    使用方式：
        converter = McCADConverter()
        if converter.is_available():
            mcnp_file = converter.run("input.stp", "SS", -7.93)
    """

    # ── 路径：开发环境 vs 打包环境 ──
    # 打包后 McCAD.exe 在 _internal/mccad/，OCC DLL 在 _internal/occ/
    _BUNDLED = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

    @staticmethod
    def _mccad_path() -> str:
        """返回 McCAD.exe 路径（自动适配打包/开发环境）。"""
        if McCADConverter._BUNDLED:
            return os.path.join(sys._MEIPASS, "mccad", "McCAD.exe")
        return r"D:\McCAD_build\src\McCAD\Release\McCAD.exe"

    @staticmethod
    def _occ_bin_dir() -> str:
        """返回 OCC DLL 目录（自动适配打包/开发环境）。"""
        if McCADConverter._BUNDLED:
            return os.path.join(sys._MEIPASS, "occ")
        return r"D:\OCC\win64\vc14\bin"

    @staticmethod
    def is_available() -> bool:
        """检查 McCAD.exe 和 OCC DLL 是否可用。"""
        mccad = McCADConverter._mccad_path()
        occ = McCADConverter._occ_bin_dir()
        if not os.path.isfile(mccad):
            return False
        key_dll = os.path.join(occ, "TKernel.dll")
        return os.path.isfile(key_dll)

    @staticmethod
    def get_version() -> str:
        """返回 McCAD 版本号。"""
        try:
            result = subprocess.run(
                [McCADConverter._mccad_path(), "help"],
                capture_output=True, text=True, timeout=10,
                env=McCADConverter._build_env(),
            )
            match = re.search(r"v(\d+\.\d+)", result.stdout)
            return match.group(0) if match else "unknown"
        except Exception:
            return "unknown"

    @staticmethod
    def run(step_path: str, material: str, density: float,
            work_dir: str | None = None,
            settings: dict | None = None) -> str:
        if settings is None:
            settings = {}
        if work_dir is None:
            work_dir = os.path.dirname(os.path.abspath(step_path))
        os.makedirs(work_dir, exist_ok=True)

        mat_filename = f"{material}_{density}.stp"
        step_copy = os.path.join(work_dir, mat_filename)
        shutil.copy2(step_path, step_copy)

        # 写入 McCAD 配置文件，使用用户设置
        def s(key, default=""):
            return str(settings.get(key, default))

        config_path = os.path.join(work_dir, "McCADInputConfig.i")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(f"""debugLevel = {s("debugLevel", "0")}
units = {s("units", "cm")}
inputFileName = {mat_filename}
decompose = {s("decompose", "true")}
recurrenceDepth = {s("recurrenceDepth", "20")}
minSolidVolume = {s("minSolidVolume", "1.0e-3")} [cm3]
minFaceArea = {s("minFaceArea", "1.0e-4")} [cm2]
scalingFactor = {s("scalingFactor", "100.0")}
precision = {s("precision", "1.0e-6")}
faceTolerance = {s("faceTolerance", "1.0e-8")} [cm]
edgeTolerance = {s("edgeTolerance", "1.0e-8")} [cm]
parameterTolerance = {s("parameterTolerance", "1.0e-8")} [cm]
angularTolerance = {s("angularTolerance", "1.0e-4")} [radian/PI]
distanceTolerance = {s("distanceTolerance", "1.0e-6")} [cm]
simplifyTori = {s("simplifyTori", "false")}
simplifyAllTori = {s("simplifyAllTori", "false")}
torusSplitAngle = {s("torusSplitAngle", "30.0")} [degrees]
convert = true
voidGeneration = {s("voidGeneration", "true")}
compoundIsSingleCell = {s("compoundIsSingleCell", "false")}
minVoidVolume = {s("minVoidVolume", "1.0")} [cm3]
maxSolidsPerVoidCell = {s("maxSolidsPerVoidCell", "20")}
BVHVoid = {s("BVHVoid", "false")}
MCcode = mcnp
startCellNum = {s("startCellNum", "1")}
startSurfNum = {s("startSurfNum", "1")}
startMatNum = {s("startMatNum", "1")}
maxLineWidth = {s("maxLineWidth", "80")}
MCFileName = MCFile.i
""")

        # 构建环境（加入 OCC DLL 路径）
        env = McCADConverter._build_env()

        # 运行 McCAD
        try:
            result = subprocess.run(
                [McCADConverter._mccad_path(), "run"],
                cwd=work_dir, env=env,
                capture_output=True, text=True, timeout=600,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("McCAD 执行超时（>10分钟）")

        # McCAD 没有返回值错误码，检查输出文件是否存在
        mcnp_path = os.path.join(work_dir, "MCFile.i")
        if not os.path.isfile(mcnp_path) or os.path.getsize(mcnp_path) == 0:
            stderr = result.stderr.strip() if result.stderr else ""
            stdout = result.stdout.strip() if result.stdout else ""
            raise RuntimeError(
                f"McCAD 未生成输出文件。\nstdout:\n{stdout}\nstderr:\n{stderr}"
            )

        # 清理中间文件
        for fname in os.listdir(work_dir):
            if fname.startswith(material) and fname != mat_filename:
                if fname.endswith((".stp", ".i")):
                    try:
                        os.remove(os.path.join(work_dir, fname))
                    except OSError:
                        pass

        return mcnp_path

    @staticmethod
    def run_decompose(step_path: str, material: str, density: float,
                      work_dir: str | None = None,
                      settings: dict | None = None) -> str:
        """运行 McCAD 只做分解（convert=false），返回 *Decomposed.stp 路径。"""
        if work_dir is None:
            work_dir = os.path.dirname(os.path.abspath(step_path))
        os.makedirs(work_dir, exist_ok=True)

        mat_filename = f"{material}_{density}.stp"
        step_copy = os.path.join(work_dir, mat_filename)
        shutil.copy2(step_path, step_copy)

        def s(key, default=""):
            return str(settings.get(key, default)) if settings else default

        config_path = os.path.join(work_dir, "McCADInputConfig.i")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(f"""debugLevel = 0
units = cm
inputFileName = {mat_filename}
decompose = true
recurrenceDepth = 20
minSolidVolume = 1.0e-3 [cm3]
minFaceArea = 1.0e-4 [cm2]
precision = 1.0e-6
convert = false
""")

        env = McCADConverter._build_env()
        result = subprocess.run(
            [McCADConverter.MCCAD_PATH, "run"],
            cwd=work_dir, env=env,
            capture_output=True, text=True, timeout=600,
        )

        # McCAD 产出 *Decomposed.stp
        dec_files = [f for f in os.listdir(work_dir)
                     if f.endswith("Decomposed.stp")]
        if not dec_files:
            raise RuntimeError(
                f"McCAD 未生成分解 STEP 文件。\nstdout:{result.stdout[:200]}")
        dec_path = os.path.join(work_dir, dec_files[0])

        # 清理中间文件
        dec_basename = os.path.basename(dec_path)
        for fname in os.listdir(work_dir):
            if (fname.startswith(material) and fname != mat_filename
                    and fname != dec_basename):
                try:
                    os.remove(os.path.join(work_dir, fname))
                except OSError:
                    pass
        return dec_path

    @staticmethod
    def _build_env() -> dict:
        """构建子进程环境变量，加入 OCC DLL 路径。"""
        env = os.environ.copy()
        occ_bin = McCADConverter._occ_bin_dir()
        if "PATH" in env:
            env["PATH"] = occ_bin + os.pathsep + env["PATH"]
        else:
            env["PATH"] = occ_bin
        return env


# ===================================================================
# MCNPOutputParser — 解析 McCAD 生成的 MCNP 文件
# ===================================================================

class MCNPOutputParser:
    """解析 McCAD 生成的 MCFile.i，提取栅元、曲面和数据卡。

    使用方式：
        parser = MCNPOutputParser()
        deck = parser.parse("MCFile.i")
    """

    @staticmethod
    def parse(mcnp_path: str,
              post_settings: dict | None = None) -> "DeckData | None":
        from app.generator.parsers import parse_inp_text
        from app.models import DeckData

        if not os.path.isfile(mcnp_path):
            return None

        with open(mcnp_path, "r", encoding="utf-8-sig") as f:
            text = f.read()

        # 预处理：取消注释材料卡，跳过注释掉的栅元（如体积计算卡）
        lines = text.splitlines()
        processed = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.match(r"^\s*c\s+M(\d+)\s*$", line, re.IGNORECASE):
                mat_num = re.match(
                    r"^\s*c\s+M(\d+)\s*$", line, re.IGNORECASE).group(1)
                processed.append(f"c M{mat_num}  $ TODO: add ZAID + fraction")
            elif re.match(r"^\s*c\s+\d+", line, re.IGNORECASE):
                # 注释掉的栅元（如 McCAD 的体积计算卡 c 24 ...），跳过
                pass
            else:
                processed.append(line)
            i += 1

        modified_text = "\n".join(processed)

        # 分离 TR 卡（McCAD 改版后 TR 卡写在曲面段末尾）
        tr_lines = []
        surf_lines = []
        for line in modified_text.splitlines():
            if re.match(r"^\s*TR\d+\s", line, re.IGNORECASE):
                tr_lines.append(line)
            else:
                surf_lines.append(line)
        surf_text = "\n".join(surf_lines)
        tr_text = "\n".join(tr_lines)

        deck, warnings = parse_inp_text(surf_text)

        # TR 卡放到 deck.tr_cards
        if tr_text and deck:
            deck.tr_cards = tr_text

        # 应用后处理设置（如 TMP）
        if post_settings and deck and deck.cells:
            tmp_val = post_settings.get("tmp", "")
            if tmp_val:
                for cell in deck.cells:
                    cell.tmp = tmp_val
            else:
                for cell in deck.cells:
                    cell.tmp = ""

        return deck


# ===================================================================
# StandardSurfaceConverter — 用 FreeCAD OCC 将 STEP 转成标准 MCNP 曲面
# ===================================================================

class StandardSurfaceConverter:
    """读取（分解后的）STEP 文件，用 FreeCAD OCC 生成标准 MCNP 曲面卡（无 GQ）。"""

    CONVERTER_SCRIPT = os.path.join(
        os.path.dirname(__file__), "step_to_standard.py")

    @classmethod
    def convert(cls, step_path: str, start_surf: int = 1,
                freecad_bin: str | None = None) -> "tuple[dict, list] | None":
        if freecad_bin is None:
            freecad_bin = StepImporter.detect_freecad()
        if not freecad_bin:
            raise RuntimeError("FreeCAD 未找到")

        python_exe = os.path.join(freecad_bin, "python.exe")
        if not os.path.isfile(python_exe):
            raise RuntimeError(f"FreeCAD Python 未找到: {python_exe}")

        cmd = [python_exe, cls.CONVERTER_SCRIPT,
               step_path, str(start_surf)]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
            env=os.environ,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"FreeCAD 转换失败:\n{result.stderr[:500]}")

        try:
            data = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            raise RuntimeError(
                f"FreeCAD 输出解析失败:\n{result.stdout[:500]}")

        if "error" in data:
            raise RuntimeError(f"FreeCAD 错误: {data['error']}")

        surfaces = {int(k): v for k, v in data.get("surfaces", {}).items()}
        tr_cards = {int(k): v for k, v in data.get("tr_cards", {}).items()}
        cells = data.get("cells", [])
        return surfaces, tr_cards, cells


# ===================================================================
# FreeCAD 检测（已有代码，不做改动）
# ===================================================================

def _reg_query(key_path: str, value_name: str = "",
               wow64_flag: int = 0) -> str | None:
    """读取 Windows 注册表字符串值，返回 None 表示未找到。"""
    try:
        access = winreg.KEY_READ | wow64_flag if wow64_flag else winreg.KEY_READ
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, access) as k:
            return winreg.QueryValueEx(k, value_name)[0]
    except OSError:
        return None

def _find_freecad_from_registry() -> str | None:
    """尝试从注册表定位 FreeCAD.exe，同时检查 64/32 位视图。"""
    path = _reg_query(
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\FreeCAD.exe",
        wow64_flag=winreg.KEY_WOW64_64KEY,
    )
    if path and os.path.isfile(path):
        return path
    path = _reg_query(
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\FreeCAD.exe",
        wow64_flag=winreg.KEY_WOW64_32KEY,
    )
    if path and os.path.isfile(path):
        return path
    return None

def _find_freecad_from_common_dirs() -> str | None:
    """在常见安装目录下搜索 FreeCAD.exe。"""
    _SEARCH_BASES = [
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "D:\\",
        os.path.expanduser("~"),
    ]
    for base in _SEARCH_BASES:
        try:
            for name in os.listdir(base):
                if "FreeCAD" not in name:
                    continue
                freecad_dir = os.path.join(base, name)
                exe = os.path.join(freecad_dir, "bin", "FreeCAD.exe")
                if os.path.isfile(exe):
                    return exe
                try:
                    for subname in os.listdir(freecad_dir):
                        if "FreeCAD" in subname:
                            exe = os.path.join(freecad_dir, subname, "bin", "FreeCAD.exe")
                            if os.path.isfile(exe):
                                return exe
                except PermissionError:
                    continue
        except (FileNotFoundError, PermissionError, NotADirectoryError):
            continue
    return None

_freecad_cache_state: int = 0
_freecad_cache_path: str | None = None

def _cached_detect() -> str | None:
    """带缓存的 FreeCAD 检测。"""
    global _freecad_cache_state, _freecad_cache_path
    if _freecad_cache_state == 0:
        settings = QSettings("MCNPGen", "MCNPGenerator")
        saved = settings.value("freecad_path", "")
        if saved and os.path.isfile(saved):
            _freecad_cache_state = 1
            _freecad_cache_path = saved
            return os.path.dirname(saved)
        exe = _find_freecad_from_registry()
        if not exe:
            exe = _find_freecad_from_common_dirs()
        if exe and os.path.isfile(exe):
            settings.setValue("freecad_path", exe)
            _freecad_cache_state = 1
            _freecad_cache_path = exe
            return os.path.dirname(exe)
        _freecad_cache_state = -1
        _freecad_cache_path = None
    if _freecad_cache_state == 1 and _freecad_cache_path:
        return os.path.dirname(_freecad_cache_path)
    return None

