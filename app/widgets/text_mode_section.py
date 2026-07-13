"""
表单⇄文本切换组件。

用法：
    section = TextModeSection(form_widget, generate_fn)
    # 将 section.toggle_btn 插入标题栏
    # 将 section.stack 插入布局（替换原来的 form_widget 位置）
    # 用于生成：
    if section.is_raw_mode():
        text = section.get_raw_text()
"""

from PyQt5.QtWidgets import (
    QWidget, QStackedWidget, QPlainTextEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QLabel
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class TextModeSection:
    """
    为模块添加「表单⇄文本」切换功能。

    参数:
      form_widget: QWidget       — 表单控件容器（成为 stack page 0）
      generate_fn: () -> str     — 用当前表单数据生成 MCNP 文本
      section_name: str          — 标识名称，用于提示

    公开属性:
      toggle_btn: QPushButton    — 外部插入到标题布局
      stack: QStackedWidget      — page 0=form, page 1=editor

    公开方法:
      is_raw_mode() -> bool
      get_raw_text() -> str      — 文本模式下的内容（空串=未激活）
    """

    def __init__(self, form_widget: QWidget, generate_fn, section_name: str = ""):
        self._form = form_widget
        self._generate = generate_fn
        self._name = section_name
        self._active = False          # 文本模式是否激活
        self._saved_raw = ""          # 用户上次存的原始文本

        # ── 切换按钮 ──
        self.toggle_btn = QPushButton("✎ 文本模式")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setFixedWidth(110)
        self.toggle_btn.setToolTip(
            "切换到此模块的文本模式——直接键入 MCNP 卡，"
            "替代表单生成。"
        )
        self.toggle_btn.clicked.connect(self._toggle)

        # ── QStackedWidget ──
        # page 0: 表单
        # page 1: 文本编辑器
        self.stack = QStackedWidget()
        self.stack.addWidget(form_widget)   # page 0

        # page 1: 编辑器 + 顶部提示栏
        editor_page = QWidget()
        editor_layout = QVBoxLayout(editor_page)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(4)

        # 顶部提示栏
        hint_bar = QHBoxLayout()
        hint_label = QLabel(
            "✏️ <b>文本模式</b> — 此内容将替代表单生成"
        )
        hint_label.setStyleSheet("color: #1976D2; font-size: 12px;")
        hint_bar.addWidget(hint_label)
        hint_bar.addStretch()

        self._discard_btn = QPushButton("放弃文本，回到表单")
        self._discard_btn.setFixedWidth(140)
        self._discard_btn.setStyleSheet(
            "QPushButton { color: #c62828; font-size: 11px; "
            "border: 1px solid #c62828; border-radius: 3px; padding: 2px 6px; }"
            "QPushButton:hover { background: #ffebee; }"
        )
        self._discard_btn.clicked.connect(self._discard)
        hint_bar.addWidget(self._discard_btn)

        editor_layout.addLayout(hint_bar)

        self._editor = QPlainTextEdit()
        self._editor.setFont(QFont("Consolas", 10))
        self._editor.setToolTip(
            "在此直接键入 MCNP 卡文本。\n"
            "切换回表单时内容不会丢失，再次切回文本可见。"
        )
        self._editor.setPlaceholderText(
            "在此直接键入 MCNP 卡文本...\n"
            "切换回表单再切回来时，内容保留。"
        )
        editor_layout.addWidget(self._editor)

        editor_page.setLayout(editor_layout)
        self.stack.addWidget(editor_page)   # page 1

        self.stack.setCurrentIndex(0)

        # 按钮样式
        self._refresh_btn_style()

    def is_raw_mode(self) -> bool:
        return self._active

    def get_raw_text(self) -> str:
        """返回文本模式下的内容。如果未激活或为空则返回空串。"""
        if not self._active:
            return ""
        text = self._editor.toPlainText().strip()
        return text if text else ""

    def _toggle(self):
        checked = self.toggle_btn.isChecked()
        if checked:
            # 切到文本模式
            if not self._saved_raw:
                # 第一次：从表单生成
                self._saved_raw = self._generate()
            self._editor.setPlainText(self._saved_raw)
            self.stack.setCurrentIndex(1)
            self._active = True
        else:
            # 切回表单模式：保存编辑器内容
            self._saved_raw = self._editor.toPlainText()
            self.stack.setCurrentIndex(0)
            self._active = False
        self._refresh_btn_style()

    def _discard(self):
        """放弃已存的文本，回到表单模式"""
        self._saved_raw = ""
        self._active = False
        self.toggle_btn.setChecked(False)
        self.stack.setCurrentIndex(0)
        self._refresh_btn_style()

    def _refresh_btn_style(self):
        if self._active:
            self.toggle_btn.setText("← 回到表单")
            self.toggle_btn.setStyleSheet(
                "QPushButton { background: #1976D2; color: white; "
                "border: 1px solid #1976D2; border-radius: 3px; "
                "padding: 4px 8px; font-weight: bold; }"
                "QPushButton:hover { background: #1565C0; }"
            )
        else:
            self.toggle_btn.setText("✎ 文本模式")
            self.toggle_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #555; "
                "border: 1px solid #ccc; border-radius: 3px; "
                "padding: 4px 8px; }"
                "QPushButton:hover { border-color: #1976D2; color: #1976D2; }"
            )
