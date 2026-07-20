"""
Deep module: 3D 预览坐标辅助系统

封装三条贯穿轴线 + 动态刻度标签（密度随视角缩放自适应）+
可拖拽金色参考点 + 坐标文本 + 一键开关。

接口小而深：构造 + setup() 完成全部初始化，3 个事件回调驱动更新。

Usage:
    coord = CoordAids(plotter, extent=150, diag=200)
    coord.setup()
    # 在 RenderEvent 中:
    coord.on_render()
    # 在 EndInteractionEvent 中:
    coord.rebuild_ticks()
    # 其他:
    coord.toggle(False)   # 隐藏全部
"""
import math
import pyvista as pv


class CoordAids:
    """3D 坐标辅助系统 — 小而深的接口，隐藏 VTK 复杂度。

    Interface:
        CoordAids(plotter, extent, diag)
          .setup()              → None  创建所有元素
          .on_render()           → None  每帧更新球体大小
          .rebuild_ticks()       → None  重建动态刻度
          .toggle(value: bool)   → None  显隐切换

          .default_pos: list     [10, 10, 10] 参考点默认位置
          .actors: list[vtkProp] 给 toggle 用
          .widgets: list[vtkWidget] 给 toggle 用
    """

    def __init__(self, plotter: pv.Plotter, extent: float, diag: float):
        self._p = plotter
        self.extent = extent
        self.diag = diag

        self.default_pos = [10.0, 10.0, 10.0]
        self.actors: list = []    # vtkProp — SetVisibility(bool)
        self.widgets: list = []   # vtk3DWidget — SetEnabled(bool)

        self._tick_actors: list = []
        self._sphere = None
        self._coord_text = None

    # ── Public interface ──────────────────────────────────────────────

    def setup(self):
        """创建所有坐标辅助元素：轴线 → 刻度 → 参考点 → 开关"""
        self._add_axis_lines()
        self._rebuild_ticks()
        self._add_reference_point()
        self._add_toggle()

    def on_render(self):
        """每帧调用：拖拽球大小随视距自适应"""
        if self._sphere is None:
            return
        cam = self._p.camera_position[0]
        dx = cam[0] - self.default_pos[0]
        dy = cam[1] - self.default_pos[1]
        dz = cam[2] - self.default_pos[2]
        dist = (dx * dx + dy * dy + dz * dz) ** 0.5
        self._sphere.SetRadius(dist * 0.008)

    def rebuild_ticks(self):
        """交互结束时调用：按当前视角重建刻度（密度自动适配）"""
        self._rebuild_ticks()

    def toggle(self, value: bool):
        """一键显隐所有坐标辅助元素"""
        for a in self.actors:
            a.SetVisibility(value)
        for w in self.widgets:
            w.SetEnabled(value)
        self._p.render()

    # ── Internal builders ─────────────────────────────────────────────

    def _add_axis_lines(self):
        """贯穿原点的三轴参考线（红 X / 绿 Y / 蓝 Z）"""
        e = self.extent
        x = self._p.add_mesh(pv.Line((-e, 0, 0), (e, 0, 0)), color='red', line_width=2)
        y = self._p.add_mesh(pv.Line((0, -e, 0), (0, e, 0)), color='green', line_width=2)
        z = self._p.add_mesh(pv.Line((0, 0, -e), (0, 0, e)), color='blue', line_width=2)
        self.actors.extend([x, y, z])

    def _rebuild_ticks(self):
        """清除旧刻度 → 计算间距 → 在三条轴上添加新标注"""
        # 1. 清除
        for a in self._tick_actors:
            try:
                self._p.renderer.RemoveActor(a)
            except Exception:
                pass
            try:
                self.actors.remove(a)
            except ValueError:
                pass
        self._tick_actors.clear()

        # 2. 确定间距（自动适配视角，不强制最小 1 cm）
        try:
            cam = self._p.camera_position[0]
            dist = (cam[0] ** 2 + cam[1] ** 2 + cam[2] ** 2) ** 0.5
        except Exception:
            dist = self.extent * 2
        spacing = self._nice_spacing(dist)
        spacing = max(spacing, self.diag * 0.002)   # 最小为模型尺寸的 0.2%

        # 3. 刻度位置（上限 30 个/侧，避免标签太多导致性能问题）
        max_side = 30
        n = min(int(self.extent // spacing), max_side)
        ticks = sorted(
            [i * spacing for i in range(1, n + 1)]
            + [-i * spacing for i in range(1, n + 1)]
        )
        fmt = '.0f' if spacing >= 1 else '.1f' if spacing >= 0.1 else '.2f'

        # 4. 三条轴分别创建
        for (dx, dy, dz), color in (
            ((1, 0, 0), 'red'),
            ((0, 1, 0), 'green'),
            ((0, 0, 1), 'blue'),
        ):
            pts = [(float(dx * v), float(dy * v), float(dz * v)) for v in ticks]
            labels = [f'{v:{fmt}}' for v in ticks]
            if not pts:
                continue
            try:
                actor = self._p.add_point_labels(
                    pts, labels,
                    show_points=False, point_size=0,
                    font_size=10, text_color=color,
                    always_visible=True, shape=None,
                )
                self._tick_actors.append(actor)
                self.actors.append(actor)
            except Exception:
                pass
        self._p.render()

    @staticmethod
    def _nice_spacing(dist: float) -> float:
        """取 1/2/5 的整数倍作为刻度间距"""
        if dist <= 0:
            return 10
        raw = dist * 0.6 / 8
        magnitude = 10 ** int(math.log10(max(raw, 1e-3)))
        r = raw / magnitude
        if r < 1.5:
            return magnitude
        if r < 3.5:
            return magnitude * 2
        if r < 7.5:
            return magnitude * 5
        return magnitude * 10

    def _add_reference_point(self):
        """可拖拽金色线框球 + 左上角实时坐标文本"""
        pos = self.default_pos
        self._coord_text = self._p.add_text(
            f'  X: {pos[0]:.1f}   Y: {pos[1]:.1f}   Z: {pos[2]:.1f}  (cm)  ',
            position='upper_left', font_size=14, color=(0.1, 0.1, 0.1), font='courier',
        )
        self.actors.append(self._coord_text)

        def _drag(point):
            self._coord_text.SetText(
                2,
                f'  X: {point[0]:.1f}   Y: {point[1]:.1f}   Z: {point[2]:.1f}  (cm)  ',
            )
            self._p.render()

        self._sphere = self._p.add_sphere_widget(
            _drag, center=pos, radius=self.diag * 0.008,
            color=(1, 0.84, 0), style='wireframe',
            theta_resolution=20, phi_resolution=20, selected_color='orange',
        )
        self.widgets.append(self._sphere)

    def _add_toggle(self):
        """Checkbox 按钮 — 一键开关所有坐标辅助元素"""
        self._p.add_checkbox_button_widget(
            self.toggle, value=True,
            position=(10, 10), size=40,
            color_on='royalblue', color_off='grey', background_color='white',
        )
