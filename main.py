"""
MCNP Input Card Generator v1.3.2
==================================

Entry point for the PyQt5-based MCNP (Monte Carlo N-Particle) Input Card Generator
application. This module initializes the Qt application, configures global settings,
and launches the main window.

MCNP 输入卡生成器 v1.3.2
图形界面基于 PyQt5
"""

import sys
import os

# Ensure the project root directory is on the module search path
# 确保项目根目录在模块搜索路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from app.main_window import MainWindow
from app.style import STYLE


def main():
    """
    Application entry point.

    Creates the QApplication instance, sets the application name and version,
    applies the global stylesheet, creates and displays the main window,
    then enters the Qt event loop.

    应用程序入口点。
    创建 QApplication 实例，设置应用名称和版本，应用全局样式表，
    创建并显示主窗口，然后进入 Qt 事件循环。
    """
    app = QApplication(sys.argv)
    app.setApplicationName("MCNP Input Card Generator")   # Application display name / 应用显示名称
    app.setApplicationVersion("1.2.0")                     # Application version string / 应用版本号
    app.setStyleSheet(STYLE)                               # Apply the global QSS stylesheet / 应用全局 QSS 样式表

    window = MainWindow()
    window.show()                                          # Display the main window / 显示主窗口

    sys.exit(app.exec_())                                  # Enter the event loop; exit when closed / 进入事件循环，关闭时退出


if __name__ == "__main__":
    main()
