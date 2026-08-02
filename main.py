"""
MCNP 输入卡生成器
图形界面基于 PyQt5
"""

import sys
import os

# 确保项目根目录在模块搜索路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication, QStyleFactory
from app.main_window import MainWindow
from app.widgets.ui_helpers import app_icon
from app.style import STYLE
from app._version import __version__


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MCNP 输入卡生成器")
    app.setApplicationVersion(__version__)
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet(STYLE)

    icon = app_icon()
    app.setWindowIcon(icon)

    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
