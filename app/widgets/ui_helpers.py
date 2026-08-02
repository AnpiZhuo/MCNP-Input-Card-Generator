"""
Deep module: 常用 UI 部件工厂函数

消除各处重复的 QLabel 标题 / QPushButton 添加删除 / QFrame 分隔线 /
表格单元格（居中 QLabel / QLineEdit / QCheckBox）创建代码。
"""

import os
from PyQt5.QtWidgets import QLabel, QPushButton, QFrame, QLineEdit, QCheckBox, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

# ── 应用图标（惰性加载，一次读盘） ──
_APP_ICON: QIcon | None = None


def app_icon() -> QIcon:
    """返回应用图标（缓存，只读一次文件）"""
    global _APP_ICON
    if _APP_ICON is None:
        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app_icon.ico"
        )
        if os.path.isfile(icon_path):
            _APP_ICON = QIcon(icon_path)
        else:
            _APP_ICON = QIcon()
    return _APP_ICON


def make_section_title(text: str, padding_top: int = 12) -> QLabel:
    """创建统一的段标题

    Args:
        text: 标题 HTML，如 "<b>曲面与 TR 卡</b>"
        padding_top: 顶部留白（默认 12px，与上方内容隔开）

    Returns:
        已设置好样式的 QLabel
    """
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"font-weight: bold; font-size: 13px; padding: {padding_top}px 0 4px 0;"
    )
    return lbl


def make_add_button(text: str, tooltip: str = "") -> QPushButton:
    """创建统一的「+ 添加」按钮

    Args:
        text: 按钮文字，如 "+ 添加计数"
        tooltip: 鼠标悬停提示

    Returns:
        已设好 cssClass 的 QPushButton
    """
    btn = QPushButton(text)
    btn.setProperty("cssClass", "btnAdd")
    if tooltip:
        btn.setToolTip(tooltip)
    return btn


def make_delete_button(text: str, tooltip: str = "") -> QPushButton:
    """创建统一的「× 删除」按钮

    Args:
        text: 按钮文字，如 "× 删除选中"
        tooltip: 鼠标悬停提示

    Returns:
        已设好 cssClass 的 QPushButton
    """
    btn = QPushButton(text)
    btn.setProperty("cssClass", "btnDelete")
    if tooltip:
        btn.setToolTip(tooltip)
    return btn


def make_hseparator(margin: int = 4) -> QFrame:
    """创建水平分隔线

    Args:
        margin: 上下外边距（通过 stylesheet margin 实现）

    Returns:
        设好样式的 QFrame(HLine)
    """
    sep = QFrame()
    sep.setFrameShape(QFrame.HLine)
    sep.setStyleSheet(f"margin: {margin}px 0;")
    return sep


# ── 表格单元格工厂 ──────────────────────────────────────

def make_logo(size: int = 36) -> QWidget:
    """创建渐变色 Logo 组件（山形图标 + 光泽覆盖层）

    Args:
        size: Logo 尺寸（正方形边长）

    Returns:
        已设好样式的 QWidget
    """
    w = QWidget()
    w.setFixedSize(size, size)
    w.setStyleSheet(
        "background: qlineargradient(x1:0,y1:0,x2:1,y2:1, "
        "stop:0 #FF0080, stop:1 #7000FF); "
        "border-radius: 10px;"
    )
    return w


def make_avatar(initials: str = "W", size: int = 32, image_path: str = "") -> QWidget:
    """创建圆形用户头像

    Args:
        initials: 缩写字母（无图片时显示）
        size: 头像直径
        image_path: 用户头像图片路径（可选）

    Returns:
        已设好样式的 QWidget
    """
    import os
    from PyQt5.QtGui import QPixmap
    if image_path and os.path.isfile(image_path):
        lbl = QLabel()
        pm = QPixmap(image_path)
        lbl.setPixmap(pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lbl.setFixedSize(size, size)
        lbl.setStyleSheet("border-radius: {}px;".format(size // 2))
        return lbl
    lbl = QLabel(initials)
    lbl.setFixedSize(size, size)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(
        "background: qlineargradient(x1:0,y1:0,x2:1,y2:1, "
        "stop:0 #FF0080, stop:1 #7000FF); "
        "color: white; font-weight: 600; font-size: 12px; "
        "border-radius: {}px;".format(size // 2)
    )
    return lbl


def make_stat_card(label: str, value: str, sub: str = "") -> QWidget:
    """创建统计卡片（栅元数/曲面数等）

    Args:
        label: 标签名（如 "栅元 (Cells)"）
        value: 数值（如 "47"）
        sub: 副标题（如 "+3 今次会话"）

    Returns:
        玻璃效果统计卡片 QWidget
    """
    card = QWidget()
    card.setStyleSheet(
        "background: rgba(18,18,42,0.45); border: 1px solid rgba(255,255,255,0.06); "
        "border-radius: 10px; padding: 16px 18px;"
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(4)
    lbl = QLabel(label)
    lbl.setStyleSheet("font-size: 11px; font-weight: 500; color: rgba(241,241,249,0.35); "
                      "text-transform: uppercase; letter-spacing: 0.4px; border: none; background: transparent;")
    val = QLabel(value)
    val.setStyleSheet("font-size: 26px; font-weight: 700; border: none; background: transparent;")
    val.setText(f'<span style="background:linear-gradient(135deg,#FF0080,#7000FF);'
                f'-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
                f'font-weight:700;">{value}</span>')
    layout.addWidget(lbl)
    layout.addWidget(val)
    if sub:
        s = QLabel(sub)
        s.setStyleSheet("font-size: 12px; color: rgba(241,241,249,0.3); border: none; background: transparent;")
        layout.addWidget(s)
    return card


def make_centered_label(text: str, tooltip: str = "", bold: bool = False) -> QLabel:
    """创建表格内居中只读标签

    Args:
        text: 文字内容
        tooltip: 悬停提示
        bold: 是否加粗

    Returns:
        已设好对齐和样式的 QLabel
    """
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    if bold:
        lbl.setStyleSheet("font-weight: bold; padding: 4px;")
    if tooltip:
        lbl.setToolTip(tooltip)
    return lbl


def make_centered_edit(text: str = "", placeholder: str = "",
                       tooltip: str = "", max_length: int = 0) -> QLineEdit:
    """创建表格内居中可编辑文本

    Args:
        text: 初始文本
        placeholder: 占位提示
        tooltip: 悬停提示
        max_length: 最大字符数（0=不限）

    Returns:
        设好居中和样式的 QLineEdit
    """
    le = QLineEdit(text)
    le.setAlignment(Qt.AlignCenter)
    if placeholder:
        le.setPlaceholderText(placeholder)
    if tooltip:
        le.setToolTip(tooltip)
    if max_length:
        le.setMaxLength(max_length)
    return le


def make_table_checkbox(checked: bool = False, tooltip: str = "") -> QCheckBox:
    """创建表格内居中勾选框

    Args:
        checked: 是否勾选
        tooltip: 悬停提示

    Returns:
        设好状态的 QCheckBox
    """
    cb = QCheckBox()
    cb.setChecked(checked)
    if tooltip:
        cb.setToolTip(tooltip)
    return cb
