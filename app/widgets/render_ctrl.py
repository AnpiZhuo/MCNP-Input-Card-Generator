"""
Render Control Window: 浮动窗口，控制3D预览中每个栅元的渲染状态

将栅元渲染勾选栏从主表格中摘出，放入独立的置顶窗口，避免主界面臃肿。

Usage:
    wnd = RenderControlWindow(get_cells_fn, format_fn, on_changed=None)
    wnd.show()
    # 当 cells 发生增删时调用 wnd.refresh() 重建列表
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QCheckBox, QLabel, QPushButton, QLineEdit, QToolTip,
)
from PyQt5.QtCore import Qt, QTimer, QEvent, QPoint
from PyQt5.QtGui import QColor, QCursor


class RenderControlWindow(QWidget):
    """浮动窗口：栅元渲染控制（默认置顶）

    独立于主界面的浮动面板，列出所有栅元及其材料信息，
    每个栅元带一个渲染开关勾选框，修改直接写入 cell.render。
    顶部有材料颜色对照区，替代3D预览图中的图例。

    Interface:
        RenderControlWindow(get_cells_fn, format_fn, on_changed, on_mat_changed)
            .refresh()            — 重建列表（增删栅元后调用）
            .set_legend(entries)  — 设置材料颜色对照（替代3D图例）
    """

    def __init__(self, get_cells_fn, format_fn, on_changed=None, on_mat_changed=None,
                 get_surface_info_fn=None):
        """
        Args:
            get_cells_fn: callable() -> list[CellData]
                返回当前栅元列表（每次访问都调 getter，确保拿到最新列表）
            format_fn: callable(idx, cell) -> (display_text: str, color: QColor|None)
                返回每个栅元的显示文本和材料颜色
            on_changed: callable() | None
                勾选变化时回调（可用于刷新 3D 预览等）
            on_mat_changed: callable(idx, new_material) | None
                材料号编辑时回调
            get_surface_info_fn: callable(surface_expr: str) -> list[tuple[int, str]] | None
                给定栅元的曲面表达式，返回 [(曲面号, 曲面卡原文), ...] 列表
                用于悬停 0.5s 显示曲面信息。None = 不启用该功能。
        """
        super().__init__()
        self._get_cells = get_cells_fn
        self._format_fn = format_fn
        self._on_changed = on_changed
        self._on_mat_callback = on_mat_changed
        self._get_surface_info_fn = get_surface_info_fn
        self._checkboxes: list[QCheckBox] = []
        self._legend_entries: list[tuple[str, QColor]] = []
        self._cell_rows: list[tuple[QWidget, int, str]] = []  # (row_widget, cell_num, surface_expr)

        # 悬停 0.5s 显示曲面信息的定时器
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(500)
        self._hover_timer.timeout.connect(self._show_surface_tooltip)
        self._hovered_row_idx: int | None = None

        self.setWindowTitle("3D 渲染控制")
        self.setWindowFlags(
            Qt.Window | Qt.WindowStaysOnTopHint
            | Qt.WindowCloseButtonHint | Qt.WindowMinMaxButtonsHint
        )
        self.setMinimumWidth(340)
        self.setMinimumHeight(260)
        self.resize(380, 420)

        self.setStyleSheet("""
            RenderControlWindow {
                background-color: #fafbfc;
            }
            QPushButton {
                padding: 4px 14px;
                border: 1px solid #c0c4cc;
                border-radius: 4px;
                background: #fff;
            }
            QPushButton:hover {
                background: #e8f0fe;
                border-color: #4a90d9;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ── 标题栏：标题 + 置顶开关 ──
        title_bar = QHBoxLayout()
        title_bar.setSpacing(8)
        title = QLabel("<b>🎨 栅元渲染控制</b>")
        title.setToolTip("勾选 = 在3D预览中显示该栅元")
        title_bar.addWidget(title)
        title_bar.addStretch()
        self._pin_cb = QCheckBox("置顶")
        self._pin_cb.setChecked(True)
        self._pin_cb.toggled.connect(self._toggle_pin)
        self._pin_cb.setStyleSheet("font-size: 11px; color: #555;")
        title_bar.addWidget(self._pin_cb)
        layout.addLayout(title_bar)

        hint = QLabel(
            "<span style='font-size:11px; color:#888;'>"
            "勾选状态实时生效，仅勾选的栅元会导出到 STEP 文件</span>"
        )
        layout.addWidget(hint)

        # ── 材料颜色对照区 ──
        self._legend_widget = QWidget()
        self._legend_layout = QVBoxLayout(self._legend_widget)
        self._legend_layout.setContentsMargins(4, 4, 4, 4)
        self._legend_layout.setSpacing(2)
        legend_title = QLabel("<b>材料颜色对照</b>")
        self._legend_layout.addWidget(legend_title)
        self._legend_body = QWidget()
        self._legend_body_layout = QVBoxLayout(self._legend_body)
        self._legend_body_layout.setContentsMargins(8, 0, 0, 0)
        self._legend_body_layout.setSpacing(1)
        self._legend_layout.addWidget(self._legend_body)
        sep = QLabel("<hr style='border: none; border-top: 1px solid #ddd;'>")
        self._legend_layout.addWidget(sep)
        self._legend_widget.setVisible(False)
        layout.addWidget(self._legend_widget)

        # ── 可滚动勾选列表 ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setSpacing(2)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self._content)
        layout.addWidget(scroll, 1)

        # ── 底部按钮 ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        self._lbl_count = QLabel()
        btn_layout.addWidget(self._lbl_count)
        btn_layout.addStretch()
        btn_all = QPushButton("全部选中")
        btn_none = QPushButton("全部取消")
        btn_all.clicked.connect(self._select_all)
        btn_none.clicked.connect(self._select_none)
        btn_layout.addWidget(btn_none)
        btn_layout.addWidget(btn_all)
        layout.addLayout(btn_layout)

        self._rebuild()

    # ── 公开接口 ──────────────────────────────────────────

    def refresh(self):
        """重建列表（栅元增删后调用）"""
        self._rebuild()

    def set_legend(self, entries: list[tuple[str, QColor]]):
        """设置材料颜色对照列表（替代3D图例）

        Args:
            entries: [(label_text, QColor), ...]
                如 [("Steel", QColor(31,119,180)), ("Copper", QColor(255,127,14))]
        """
        self._legend_entries = list(entries)
        self._rebuild_legend()

    def _toggle_pin(self, checked):
        """切换窗口置顶"""
        flags = self.windowFlags()
        if checked:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    # ── 悬停 0.5s 显示曲面信息 ────────────────────────────

    def eventFilter(self, obj, event):
        """监听行 widget 的 Enter/Leave 事件，控制悬停定时器"""
        if not self._get_surface_info_fn:
            return super().eventFilter(obj, event)

        if event.type() == QEvent.Enter:
            for idx, (row, num, expr) in enumerate(self._cell_rows):
                if row is obj:
                    self._hovered_row_idx = idx
                    self._hover_timer.start(500)
                    break
        elif event.type() == QEvent.Leave:
            # 检查是不是任意行被离开
            for row, num, expr in self._cell_rows:
                if row is obj:
                    self._hover_timer.stop()
                    self._hovered_row_idx = None
                    QToolTip.hideText()
                    break

        return super().eventFilter(obj, event)

    def _show_surface_tooltip(self):
        """悬停 0.5s 到期：获取曲面信息，显示 tooltip"""
        if self._hovered_row_idx is None:
            return
        if self._get_surface_info_fn is None:
            return

        row, cell_num, surface_expr = self._cell_rows[self._hovered_row_idx]
        items = self._get_surface_info_fn(surface_expr)
        if not items:
            return

        # 构建 HTML (QToolTip 支持基础 HTML)
        lines = [f"<b>栅元 {cell_num} 使用的曲面</b><hr>"]
        for surf_num, card_text in items:
            lines.append(
                f'<b style="color:#c76;">曲面 {surf_num}</b><br>'
                f'<tt>{card_text}</tt>'
            )

        html = "<br>".join(lines)

        cursor_pos = QCursor.pos()
        QToolTip.showText(cursor_pos + QPoint(12, 16), html, self)

    # ── 内部 ──────────────────────────────────────────────

    @property
    def _cells(self):
        return self._get_cells()

    def _rebuild_legend(self):
        """重建材料颜色对照区"""
        # 清除旧行
        while self._legend_body_layout.count():
            item = self._legend_body_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not self._legend_entries:
            self._legend_widget.setVisible(False)
            return

        self._legend_widget.setVisible(True)
        for label, color in self._legend_entries:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 1, 0, 1)
            row_layout.setSpacing(8)
            dot = QLabel("●")
            dot.setStyleSheet(
                f"color: {color.name()}; font-size: 24px; font-weight: bold;"
            )
            lbl = QLabel(label)
            row_layout.addWidget(dot)
            row_layout.addWidget(lbl)
            row_layout.addStretch()
            self._legend_body_layout.addWidget(row)

        # ── 操作说明 ──
        help_sep = QLabel(
            "<hr style='border: none; border-top: 1px solid #ddd; margin: 4px 0;'>"
        )
        self._legend_body_layout.addWidget(help_sep)
        help_text = QLabel(
            "<span style='font-size:11px; color:#666;'>"
            "← → 滚筒旋转 &nbsp;|&nbsp; A D 左右平移<br>"
            "🟡 金色球体 = 可拖拽参考点<br>"
            "<span style='color:#c0392b; font-weight:bold;'>"
            "⚠ W/S/Q/E 键暂有 BUG，请勿使用</span></span>"
        )
        self._legend_body_layout.addWidget(help_text)

    def _rebuild(self):
        """清除并重建所有勾选行"""
        self._checkboxes.clear()
        self._cell_rows.clear()
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        cells = self._cells
        if not cells:
            lbl = QLabel("<span style='color:#999;'>（无栅元定义）</span>")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setMinimumHeight(60)
            self._content_layout.addWidget(lbl)
            self._content_layout.addStretch()
            self._lbl_count.setText("0 个栅元")
            return

        for i, cell in enumerate(cells):
            row = QWidget()
            row.installEventFilter(self)
            self._cell_rows.append((row, cell.number, cell.surface_expr))
            row.setStyleSheet("""
                QWidget:hover {
                    background-color: #eef3f9;
                    border-radius: 4px;
                }
            """)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(6, 3, 6, 3)
            row_layout.setSpacing(10)

            # 勾选框
            cb = QCheckBox()
            cb.setChecked(getattr(cell, 'render', True))
            cb.setToolTip(f"栅元 {cell.number} 在 3D 预览中的显隐")
            cb.clicked.connect(lambda checked, idx=i: self._on_click(idx, checked))
            self._checkboxes.append(cb)
            row_layout.addWidget(cb)

            # 栅元号
            num_lbl = QLabel(f"<b>栅元 {cell.number}</b>")
            row_layout.addWidget(num_lbl)

            # 材料号编辑框（实时生效）
            mat_edit = QLineEdit()
            # 显示时去掉 M 前缀，如 "M1" → "1"
            display_mat = cell.material
            if display_mat.startswith("M") and len(display_mat) > 1:
                display_mat = display_mat[1:]
            mat_edit.setText(display_mat)
            mat_edit.setToolTip("输入数字修改材料号，实时更新 3D 预览颜色")
            mat_edit.setFixedWidth(70)
            mat_edit.setStyleSheet("QLineEdit { border: 1px solid #ccc; border-radius: 3px; padding: 1px 4px; }")
            mat_edit.textChanged.connect(
                lambda text, idx=i: self._on_mat_changed(idx, text)
            )
            row_layout.addWidget(mat_edit)

            # 材料显示名 + 注释
            mat_text, comment_text = self._format_fn(i, cell)
            # mat_text 格式: "—  M1 (Steel)" → 取 "(Steel)" 部分
            if "(" in mat_text and ")" in mat_text:
                display_name = mat_text.split("(")[-1].rstrip(")")
            else:
                display_name = ""
            if display_name:
                info_lbl = QLabel(f"<span style='color:#666; font-size:11px;'>({display_name})</span>")
                row_layout.addWidget(info_lbl)
            cmt_lbl = QLabel(comment_text) if comment_text else QLabel("")
            row_layout.addWidget(cmt_lbl, 1)

            self._content_layout.addWidget(row)

        self._content_layout.addStretch()

        # 统计
        n_on = sum(1 for c in cells if getattr(c, 'render', True))
        self._lbl_count.setText(
            f"<span style='color:#666;'>{n_on}/{len(cells)} 显示</span>"
        )

    def _on_click(self, idx, checked):
        """用户点击勾选框时同步 cell.render"""
        cells = self._cells
        if idx < len(cells):
            cells[idx].render = checked
            # 更新统计
            n_on = sum(1 for c in cells if getattr(c, 'render', True))
            self._lbl_count.setText(
                f"<span style='color:#666;'>{n_on}/{len(cells)} 显示</span>"
            )
        if self._on_changed:
            self._on_changed()

    def _on_mat_changed(self, idx, raw):
        """用户按下 Enter 时更新材料号"""
        raw = str(raw).strip()
        if not raw:
            return
        # 自动补 M 前缀：如果纯数字且非 "0"，加 M
        if raw.isdigit() and raw != "0":
            raw = "M" + raw
        cells = self._cells
        if idx < len(cells):
            cells[idx].material = raw
        if self._on_mat_callback:
            self._on_mat_callback(idx, raw)
        if self._on_changed:
            self._on_changed()

    def _select_all(self):
        cells = self._cells
        for i, cb in enumerate(self._checkboxes):
            cb.setChecked(True)
            if i < len(cells):
                cells[i].render = True
        n_on = len(cells)
        self._lbl_count.setText(
            f"<span style='color:#666;'>{n_on}/{len(cells)} 显示</span>"
        )
        if self._on_changed:
            self._on_changed()

    def _select_none(self):
        cells = self._cells
        for i, cb in enumerate(self._checkboxes):
            cb.setChecked(False)
            if i < len(cells):
                cells[i].render = False
        self._lbl_count.setText(
            f"<span style='color:#666;'>0/{len(cells)} 显示</span>"
        )
        if self._on_changed:
            self._on_changed()
