"""
AutoCompleteEdit — 公用自动补全 + 幽灵提示文本编辑器

不绑定任何业务逻辑，任何需要文本自动补全 + 幽灵提示的地方都能直接 import 使用。

调用方只需提供两个回调：
  set_completion_provider(fn)   ← fn() → list[str]
  set_ghost_provider(fn)        ← fn(当前行文本) → str | None

100% 兼容 QPlainTextEdit，替换后 toPlainText/setPlainText 等全部可用。
"""

from PyQt5.QtWidgets import (
    QPlainTextEdit, QFrame, QListWidget, QListWidgetItem, QVBoxLayout
)
from PyQt5.QtCore import Qt, QTimer, QRect
from PyQt5.QtGui import QPainter, QFont, QTextCursor


# ── 补全弹窗 ─────────────────────────────────────────────

class _CompletionPopup(QFrame):
    """自动补全下拉弹窗。"""

    def __init__(self, editor: QPlainTextEdit):
        super().__init__(editor, Qt.Popup | Qt.FramelessWindowHint)
        self._editor = editor
        self._desc_provider = None  # fn(word) → str | None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.list = QListWidget(self)
        self.list.setFocusPolicy(Qt.NoFocus)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.itemClicked.connect(self._accept)
        self.list.setStyleSheet(
            "QListWidget { border: 1px solid #c0c0c0; background: #ffffff; }"
            "QListWidget::item { padding: 2px 6px; }"
            "QListWidget::item:selected { background: #0078d7; color: #ffffff; }"
        )
        layout.addWidget(self.list)

    def set_desc_provider(self, fn):
        """设置描述提供器：fn(补词) → 说明文字"""
        self._desc_provider = fn

    def show_for(self, prefix: str, words: list[str]):
        """按 prefix 过滤词表并定位于光标下方。"""
        upper = prefix.upper()
        matched = [w for w in words if upper in w.upper()]
        if not matched:
            self.hide()
            return

        self.list.clear()
        fm = self.list.fontMetrics()
        display_texts = []
        for w in matched:
            desc = self._desc_provider(w) if self._desc_provider else ""
            display = f"{w}  —  {desc}" if desc else w
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, w)
            self.list.addItem(item)
            display_texts.append(display)

        self.list.setCurrentRow(0)

        # 弹窗宽度 = 最宽显示文字 + 边距
        max_w = max(fm.horizontalAdvance(t) for t in display_texts) + 24
        h = min(len(matched), 10) * fm.height() + 4
        self.list.setFixedWidth(int(max_w))
        self.resize(int(max_w), h)

        # 定位到光标下方
        cr = self._editor.cursorRect()
        top_left = self._editor.viewport().mapToGlobal(cr.bottomLeft())
        self.move(top_left.x(), top_left.y() + 2)
        self.show()

    def _accept(self):
        item = self.list.currentItem()
        if item:
            word = item.data(Qt.UserRole) or item.text()
            self._editor._insert_completion(word)
        self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Down:
            r = self.list.currentRow()
            if r < self.list.count() - 1:
                self.list.setCurrentRow(r + 1)
        elif event.key() == Qt.Key_Up:
            r = self.list.currentRow()
            if r > 0:
                self.list.setCurrentRow(r - 1)
        elif event.key() in (Qt.Key_Tab, Qt.Key_Return, Qt.Key_Enter):
            self._accept()
        elif event.key() == Qt.Key_Escape:
            self.hide()
        else:
            # 其余按键 → 转发回编辑器，弹窗暂关
            self.hide()
            self._editor.keyPressEvent(event)


# ── 公用编辑器 ───────────────────────────────────────────

class AutoCompleteEdit(QPlainTextEdit):
    """带自动补全 + 幽灵提示的文本框。

    用法:
        editor = AutoCompleteEdit()
        editor.set_completion_provider(lambda: ["PX", "PY", "RCC", ...])
        editor.set_ghost_provider(lambda line: "Vx Vy Vz ..." if "RCC" in line else None)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._completion_provider = None
        self._ghost_provider = None

        self._popup = _CompletionPopup(self)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._trigger_completion)

        self.cursorPositionChanged.connect(self._on_cursor_moved)

    # ── 公用接口 ─────────────────────────────────────────

    def set_completion_provider(self, fn):
        """设置补词提供器：fn() → list[str]"""
        self._completion_provider = fn

    def set_desc_provider(self, fn):
        """设置补词描述提供器：fn(补词) → 说明文字（用于下拉菜单）"""
        self._popup.set_desc_provider(fn)

    def set_ghost_provider(self, fn):
        """设置幽灵提示提供器：fn(光标所在行文本) → str | None"""
        self._ghost_provider = fn

    # ── 补全触发 ─────────────────────────────────────────

    def _trigger_completion(self):
        if not self._completion_provider:
            return
        prefix = self._current_word()
        if len(prefix) < 1 or prefix.isdigit():
            self._popup.hide()
            return
        words = self._completion_provider()
        if not words:
            return
        self._popup.show_for(prefix, words)

    def _current_word(self) -> str:
        """光标左侧当前词（含 * / 作为词内字符）。"""
        text = self.toPlainText()
        pos = self.textCursor().position()
        start = pos
        while start > 0:
            ch = text[start - 1]
            if ch.isalnum() or ch in '*/':
                start -= 1
            else:
                break
        return text[start:pos]

    def _insert_completion(self, completion: str):
        """用补全文本替换当前词。"""
        tc = self.textCursor()
        pos = tc.position()
        text = self.toPlainText()
        start = pos
        while start > 0:
            ch = text[start - 1]
            if ch.isalnum() or ch in '*/':
                start -= 1
            else:
                break
        tc.setPosition(start, tc.KeepAnchor)
        tc.insertText(completion)
        self.setTextCursor(tc)

    def _on_cursor_moved(self):
        """光标移动 → 隐藏弹窗。"""
        self._popup.hide()

    # ── 幽灵提示绘制 ─────────────────────────────────────

    def paintEvent(self, event):
        super().paintEvent(event)

        if not self._ghost_provider:
            return

        p = QPainter(self.viewport())
        p.setClipRect(self.viewport().rect())
        col = self.palette().text().color()
        col.setAlpha(100)
        p.setPen(col)
        f = self.font()
        f.setItalic(True)
        p.setFont(f)

        # 遍历文档所有行，每行末尾渲染幽灵提示
        doc = self.document()
        block = doc.begin()
        while block.isValid():
            line_text = block.text()
            ghost = self._ghost_provider(line_text)
            if ghost:
                eoc = QTextCursor(block)
                eoc.movePosition(QTextCursor.EndOfBlock)
                vr = self.cursorRect(eoc)
                remain_w = self.viewport().width() - vr.right() - 2
                if remain_w > 20:
                    p.drawText(vr.right() + 2, vr.y(), remain_w, vr.height(),
                               Qt.AlignLeft | Qt.AlignVCenter, ghost)
            block = block.next()
        p.end()

    # ── 键盘事件 ─────────────────────────────────────────

    def keyPressEvent(self, event):
        # 补全弹窗可见时 Tab → 接受选中
        if event.key() == Qt.Key_Tab and self._popup.isVisible():
            self._popup._accept()
            return

        super().keyPressEvent(event)

        # 方向键、修饰键等不触发补全
        if event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right,
                           Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return

        # 文字输入 / 退格 → 防抖触发补全
        if event.text() or event.key() in (Qt.Key_Backspace, Qt.Key_Delete):
            self._debounce.start(80)
