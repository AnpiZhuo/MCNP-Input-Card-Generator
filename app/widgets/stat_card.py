"""
📊 数据统计卡片 — 甲方展示风仪表盘组件

用法:
    card = StatCard("栅元", "Cells", value="12", color="#58a6ff")
    card.set_value("42")       # 动态更新数字
    card.set_color("#3fb950")  # 动态换颜色
"""

from PyQt5.QtWidgets import QFrame, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt


class StatCard(QFrame):
    """科技感数据统计卡片，带颜色竖条装饰和自动数字更新"""

    def __init__(self, label_cn: str, label_en: str, value: str = "0",
                 color: str = "#58a6ff", parent=None):
        super().__init__(parent)
        self._color = color
        self._setup_ui(label_cn, label_en, value)
        self._apply_card_style()

    def _setup_ui(self, label_cn: str, label_en: str, value: str):
        self.setFixedHeight(86)
        self.setMinimumWidth(110)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(1)

        self._label_cn = QLabel(label_cn)
        self._label_cn.setObjectName("statLabelCN")

        self._value = QLabel(value)
        self._value.setObjectName("statValue")

        self._label_en = QLabel(label_en)
        self._label_en.setObjectName("statLabelEN")

        layout.addWidget(self._label_cn)
        layout.addSpacing(2)
        layout.addWidget(self._value)
        layout.addWidget(self._label_en)

    def _apply_card_style(self):
        """用 inline 样式直接设颜色，不依赖全局 QSS 的 palette(highlight)"""
        self.setStyleSheet(f"""
            StatCard {{
                background-color: #151923;
                border: 1px solid #30363d;
                border-radius: 10px;
                border-left: 3px solid {self._color};
            }}
            StatCard:hover {{
                border-color: #58a6ff;
            }}
            StatCard QLabel#statLabelCN {{
                color: #8b949e;
                font-size: 11px;
                background: transparent;
            }}
            StatCard QLabel#statValue {{
                color: {self._color};
                font-size: 24px;
                font-weight: 700;
                background: transparent;
            }}
            StatCard QLabel#statLabelEN {{
                color: #8b949e;
                font-size: 10px;
                background: transparent;
            }}
        """)

    def set_value(self, text: str):
        """更新数值显示"""
        self._value.setText(text)

    def set_color(self, color: str):
        """动态更换 accent 颜色并刷新样式"""
        self._color = color
        self._apply_card_style()

    def _update_theme(self, is_dark: bool):
        """供外部调用：切换白天/黑夜主题的卡片底色"""
        if is_dark:
            bg = "#151923"
            border = "#30363d"
            text_sec = "#8b949e"
        else:
            bg = "#ffffff"
            border = "#d0d7de"
            text_sec = "#656d76"
        self.setStyleSheet(f"""
            StatCard {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 10px;
                border-left: 3px solid {self._color};
            }}
            StatCard:hover {{
                border-color: #58a6ff;
            }}
            StatCard QLabel#statLabelCN {{
                color: {text_sec};
                font-size: 11px;
                background: transparent;
            }}
            StatCard QLabel#statValue {{
                color: {self._color};
                font-size: 24px;
                font-weight: 700;
                background: transparent;
            }}
            StatCard QLabel#statLabelEN {{
                color: {text_sec};
                font-size: 10px;
                background: transparent;
            }}
        """)
