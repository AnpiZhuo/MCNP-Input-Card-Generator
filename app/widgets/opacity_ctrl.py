"""
Deep module: 3D 预览透明度控制器

根据摄像机距离动态调整每个栅元的透明度，实现"外层半透明、内层实心"的
视觉效果。摄像机越靠近，外层越透明，便于观察内部结构。

Usage:
    ctrl = OpacityController()
    ctrl.set_actors(plotter_actors_with_base_opacity_and_center)
    # 在 RenderEvent 中:
    ctrl.update(camera_position)
"""
from typing import List, Tuple


class OpacityController:
    """距离驱动透明度控制器。

    Interface:
        OpacityController()
          .set_actors(actor_data)    → None  注册 (actor, base_op, center)
          .update(camera_position)   → None  更新透明度
    """

    def __init__(self):
        self._actors: List[Tuple] = []  # (vtkActor, base_opacity, (cx, cy, cz))

    def set_actors(self, actors):
        """注册所有要控制透明度的 actor。

        Args:
            actors: [(vtkActor, base_opacity, (cx,cy,cx)), ...]
        """
        self._actors = list(actors)

    def update(self, camera_position):
        """根据摄像机位置更新透明度。"""
        if not self._actors:
            return
        pos = camera_position
        # 最远距离
        max_d = 1.0
        for _, _, center in self._actors:
            d = ((pos[0] - center[0]) ** 2 +
                 (pos[1] - center[1]) ** 2 +
                 (pos[2] - center[2]) ** 2) ** 0.5
            max_d = max(max_d, d)
        # 逐 actor 更新
        for actor, base_op, center in self._actors:
            d = ((pos[0] - center[0]) ** 2 +
                 (pos[1] - center[1]) ** 2 +
                 (pos[2] - center[2]) ** 2) ** 0.5
            ratio = d / max_d if max_d > 0 else 0.5
            op = base_op * (0.7 + 0.3 * ratio)
            op = max(0.15, min(1.0, op))
            actor.GetProperty().SetOpacity(op)
