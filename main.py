"""
MCNP 输入卡生成器 v1.3.2
图形界面基于 PyQt5
"""

import sys
import os

# 确保项目根目录在模块搜索路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from app.main_window import MainWindow
from app.style import STYLE


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MCNP 输入卡生成器")
    app.setApplicationVersion("1.2.0")
    app.setStyleSheet(STYLE)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
