"""
Cross-Section Viewer: 平面截面 2D 矢量图

用 QGraphicsView 渲染每个栅元在平面上的截面填充多边形。
可缩放平移，鼠标悬停显示栅元材料和坐标。

Interface:
    CellSlice(num, mesh_3d, color, material_label)
      mesh_3d: slice() 获得的截面 Polydata（3D 点集，在平面上）
    CrossSectionWindow(parent, plane_params, cell_slices)
"""

from dataclasses import dataclass
from typing import Optional

import math
import numpy as np
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QGraphicsView, QGraphicsScene, QGraphicsPolygonItem,
    QCheckBox,
)
from PyQt5.QtCore import Qt, QPointF, QRectF, QPoint, pyqtSignal, QEvent
from PyQt5.QtWidgets import QToolTip
from app.widgets.ui_helpers import app_icon
from PyQt5.QtGui import QColor, QPen, QBrush, QPolygonF, QFont, QPainter, QPainterPath
from PyQt5.QtWidgets import QGraphicsPathItem, QGraphicsItem
import pyvista as pv


@dataclass
class CellSlice:
    """一个栅元的截面数据"""
    cell_num: int
    contours: list    # list[np.ndarray] — 每条是 (N,3) 闭合轮廓点集
    color: tuple      # 填充色 (r,g,b) 0-1
    material_label: str       # 显示用材料名


def _compute_plane_origin(a: float, b: float, c: float, d: float) -> list:
    if abs(a) > 1e-12:
        return [d / a, 0.0, 0.0]
    if abs(b) > 1e-12:
        return [0.0, d / b, 0.0]
    if abs(c) > 1e-12:
        return [0.0, 0.0, d / c]
    return [0.0, 0.0, 0.0]


def _make_plane_basis(normal: np.ndarray, origin: np.ndarray):
    """构建平面上的正交基 (u, v)，用于 3D→2D 投影"""
    if abs(normal[0]) < 0.9:
        u = np.cross(normal, [1, 0, 0])
    else:
        u = np.cross(normal, [0, 1, 0])
    u_norm = np.linalg.norm(u)
    if u_norm < 1e-12:
        u = np.array([1.0, 0.0, 0.0])
    else:
        u /= u_norm
    v = np.cross(normal, u)
    v_norm = np.linalg.norm(v)
    if v_norm > 1e-12:
        v /= v_norm
    else:
        v = np.array([0.0, 1.0, 0.0])
    return u, v


def _to_2d(pt_3d: np.ndarray, origin: np.ndarray, u: np.ndarray, v: np.ndarray):
    """将平面上 3D 点投影为 2D 坐标"""
    d = pt_3d - origin
    return float(np.dot(d, u)), float(np.dot(d, v))


# ── 旋转控制器 ────────────────────────────────────────────

class _RotationControl(QWidget):
    """环形旋转控制器：拖拽圆上的手柄旋转视图"""

    angleChanged = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0.0
        self._dragging = False
        self._cx = self._cy = 40
        self._r = 28
        self.setFixedSize(80, 80)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy, r = self._cx, self._cy, self._r

        # 背景圆（半透明白）
        p.setPen(QPen(QColor(100, 100, 100), 1.2))
        p.setBrush(QBrush(QColor(255, 255, 255, 170)))
        p.drawEllipse(QPointF(cx, cy), r, r)

        # 十字线
        p.drawLine(cx - r, cy, cx + r, cy)
        p.drawLine(cx, cy - r, cx, cy + r)

        # 中心点
        p.setBrush(QBrush(QColor(80, 80, 80)))
        p.drawEllipse(QPointF(cx, cy), 2, 2)

        # 手柄（在圆周上）
        rad = math.radians(self._angle)
        hx = cx + r * math.cos(rad)
        hy = cy + r * math.sin(rad)
        p.setPen(QPen(QColor(40, 100, 200), 1.5))
        p.setBrush(QBrush(QColor(60, 140, 240)))
        p.drawEllipse(QPointF(hx, hy), 5, 5)
        p.end()

    def mousePressEvent(self, event):
        dx = event.pos().x() - self._cx
        dy = event.pos().y() - self._cy
        dist = math.hypot(dx, dy)
        if self._r - 8 < dist < self._r + 8:
            self._dragging = True
            self._update_angle(event.pos())

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._update_angle(event.pos())

    def mouseReleaseEvent(self, event):
        self._dragging = False

    def _update_angle(self, pos):
        dx = pos.x() - self._cx
        dy = pos.y() - self._cy
        self._angle = math.degrees(math.atan2(dy, dx))
        self.angleChanged.emit(self._angle)
        self.update()

    def set_angle(self, deg: float):
        self._angle = deg % 360
        self.update()


# ── 主模块 ─────────────────────────────────────────────────

class CrossSectionWindow(QMainWindow):
    """平面截面 2D 矢量图窗口

    接收 slice() 获得的截面 mesh，投影到 2D 后用 QGraphicsView 渲染。
    支持缩放（滚轮）、平移（拖拽）、悬停显示信息。
    """

    def __init__(
        self,
        parent: Optional[QWidget],
        plane_params: tuple[float, float, float, float],
        cell_slices: list[CellSlice],
        bg_color: str = "#f0f2f5",
    ):
        super().__init__(parent)
        self._slices = cell_slices
        self._plane_a, self._plane_b, self._plane_c, self._plane_d = plane_params
        self._normal = np.array([self._plane_a, self._plane_b, self._plane_c], dtype=float)
        nn = np.linalg.norm(self._normal)
        if nn > 0:
            self._normal /= nn
        self._origin = np.array(_compute_plane_origin(*plane_params))
        self._u, self._v = _make_plane_basis(self._normal, self._origin)

        self.setWindowTitle(f"截面: {self._plane_a}X + {self._plane_b}Y + {self._plane_c}Z = {self._plane_d}")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(600, 500)
        self.resize(800, 600)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        # ── UI ──
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self._scene = QGraphicsScene()
        self._view = _CrossSectionView(self._scene, self)
        self._view.setRenderHint(QPainter.Antialiasing)
        self._view.setBackgroundBrush(QBrush(QColor(bg_color)))
        self._view.setDragMode(QGraphicsView.ScrollHandDrag)
        self._view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        layout.addWidget(self._view)

        # 状态栏
        bar = QHBoxLayout()
        bar.setContentsMargins(10, 4, 10, 4)
        self._status_label = QLabel("滚轮缩放 | 拖拽平移 | ←→ 旋转")
        self._status_label.setStyleSheet("color: #666; font-size: 11px;")
        bar.addWidget(self._status_label)
        bar.addStretch()
        pin_cb = QCheckBox("置顶")
        pin_cb.setChecked(True)
        pin_cb.toggled.connect(self._toggle_pin)
        pin_cb.setStyleSheet("font-size: 11px; color: #555;")
        bar.addWidget(pin_cb)
        layout.addLayout(bar)

        self._build_scene()
        self._view.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

        # 旋转控制器（叠加在视图右下角）
        self._rot_ctrl = _RotationControl(self._view)
        self._rot_ctrl.angleChanged.connect(self._on_rotate)
        self._rot_ctrl.move(self._view.width() - 90, self._view.height() - 90)
        self._view.installEventFilter(self)
        self.show()

    def eventFilter(self, obj, event):
        if obj is self._view and event.type() == QEvent.Resize:
            self._rot_ctrl.move(self._view.width() - 90, self._view.height() - 90)
        return super().eventFilter(obj, event)

    def _on_rotate(self, angle: float):
        """旋转 QGraphicsView，保持当前缩放和视图中心"""
        t = self._view.transform()
        scale = (t.m11()**2 + t.m12()**2)**0.5  # 真实缩放（不受旋转影响）
        center = self._view.mapToScene(self._view.viewport().rect().center())
        self._view.resetTransform()
        self._view.scale(scale, scale)         # 恢复缩放
        self._view.rotate(angle)               # 旋转
        self._view.centerOn(center)            # 保持视图中心不变（内部处理 scrollbar）
        self._rot_ctrl.set_angle(angle)

    def _toggle_pin(self, checked: bool):
        flags = self.windowFlags()
        if checked:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    # ── 构建 2D 场景 ──────────────────────────────────

    _BATCH_SIZE = 500  # 每批最大三角形数，允许 BSP 树裁剪

    def _build_scene(self):
        """将每个栅元的闭合轮廓投影到 2D 并构建 QPainterPath。

        只渲染轮廓线，Qt 原生填充封闭区域——任意缩放不糊、顶点数极少。
        """
        self._path_items: list[tuple[QGraphicsPathItem, CellSlice]] = []
        bounds = [float('inf'), float('-inf'), float('inf'), float('-inf')]

        for s in self._slices:
            contours = s.contours
            if not contours:
                continue

            color_qt = QColor(
                int(s.color[0] * 255),
                int(s.color[1] * 255),
                int(s.color[2] * 255),
            )

            path = QPainterPath()
            for contour in contours:
                if len(contour) < 3:
                    continue
                pts_2d = [_to_2d(p, self._origin, self._u, self._v) for p in contour]
                path.moveTo(*pts_2d[0])
                for pt in pts_2d[1:]:
                    path.lineTo(*pt)
                path.closeSubpath()
                for x, y in pts_2d:
                    bounds[0] = min(bounds[0], x)
                    bounds[1] = max(bounds[1], x)
                    bounds[2] = min(bounds[2], y)
                    bounds[3] = max(bounds[3], y)

            if not path.isEmpty():
                self._add_path_item(path, color_qt, s)

        if bounds[0] < bounds[1] and bounds[2] < bounds[3]:
            margin_x = (bounds[1] - bounds[0]) * 0.1 or 10
            margin_y = (bounds[3] - bounds[2]) * 0.1 or 10
            self._scene.setSceneRect(
                bounds[0] - margin_x, bounds[2] - margin_y,
                bounds[1] - bounds[0] + 2 * margin_x,
                bounds[3] - bounds[2] + 2 * margin_y,
            )

    def _add_path_item(self, path, color_qt, cell_slice):
        if path.isEmpty():
            return
        item = QGraphicsPathItem(path)
        item.setPen(QPen(color_qt, 0.5))
        item.setBrush(QBrush(color_qt))
        item.setAcceptHoverEvents(True)
        # 矢量图不缓存 —— 任何缓存都会在放大时变糊
        self._scene.addItem(item)
        self._path_items.append((item, cell_slice))

    # ── 悬停信息来源（由 _CrossSectionView 调用） ──────

    def update_hover(self, screen_pos: QPoint, global_pos: QPoint):
        """鼠标悬停：在鼠标附近显示 tooltip，同时更新状态栏"""
        scene_pos = self._view.mapToScene(screen_pos)
        coord_2d = (scene_pos.x(), scene_pos.y())
        pt_3d = self._origin + self._u * coord_2d[0] + self._v * coord_2d[1]

        item = self._scene.itemAt(scene_pos, self._view.transform())
        if isinstance(item, QGraphicsPathItem):
            for path_item, s in self._path_items:
                if path_item is item:
                    tip = (
                        f"Cell {s.cell_num} ({s.material_label})\n"
                        f"X: {pt_3d[0]:.2f}  Y: {pt_3d[1]:.2f}  Z: {pt_3d[2]:.2f}"
                    )
                    QToolTip.showText(global_pos + QPoint(12, 16), tip, self)
                    self._status_label.setText(
                        f"Cell {s.cell_num} ({s.material_label})  |  "
                        f"X: {pt_3d[0]:.2f}  Y: {pt_3d[1]:.2f}  Z: {pt_3d[2]:.2f}"
                    )
                    return

        # 不在栅元上 → 隐藏 tooltip
        QToolTip.hideText()
        self._status_label.setText(
            f"X: {pt_3d[0]:.2f}  Y: {pt_3d[1]:.2f}  Z: {pt_3d[2]:.2f}  |  滚轮缩放 | 拖拽平移"
        )

    def _current_angle(self) -> float:
        """安全获取当前旋转角度"""
        return self._rot_ctrl._angle

    def update_content(self, plane_params: tuple, cell_slices: list[CellSlice], bg_color: str = "#f0f2f5"):
        """更新截面内容，复用同一窗口（不重新打开）"""
        # 清除旧场景
        self._scene.clear()
        self._path_items.clear()
        self._view.setBackgroundBrush(QBrush(QColor(bg_color)))

        # 更新平面参数
        self._slices = cell_slices
        self._plane_a, self._plane_b, self._plane_c, self._plane_d = plane_params
        self._normal = np.array([self._plane_a, self._plane_b, self._plane_c], dtype=float)
        nn = np.linalg.norm(self._normal)
        if nn > 0:
            self._normal /= nn
        self._origin = np.array(_compute_plane_origin(*plane_params))
        self._u, self._v = _make_plane_basis(self._normal, self._origin)

        # 重建场景
        self._build_scene()
        self._view.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        self._rot_ctrl.set_angle(0)

        # 更新标题
        self.setWindowTitle(
            f"截面: {self._plane_a}X + {self._plane_b}Y + {self._plane_c}Z = {self._plane_d}"
        )

    def closeEvent(self, event):
        super().closeEvent(event)


class _CrossSectionView(QGraphicsView):
    """支持滚轮缩放和鼠标追踪的 QGraphicsView"""

    def __init__(self, scene, win: CrossSectionWindow):
        super().__init__(scene)
        self._win = win
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        factor = 1.15 ** (event.angleDelta().y() / 120)
        self.scale(factor, factor)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self._win._on_rotate(self._win._current_angle() - 1)
        elif event.key() == Qt.Key_Right:
            self._win._on_rotate(self._win._current_angle() + 1)
        else:
            super().keyPressEvent(event)

    def mouseMoveEvent(self, event):
        # 拖拽中不更新悬停，避免 scene.itemAt() 拖慢帧率
        if not (event.buttons() & Qt.LeftButton and self.dragMode() == QGraphicsView.ScrollHandDrag):
            self._win.update_hover(event.pos(), event.globalPos())
        super().mouseMoveEvent(event)
