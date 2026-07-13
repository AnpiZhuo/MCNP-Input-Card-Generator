"""
预览对话框：确认 INP 内容后保存到指定目录
"""

import os
import subprocess
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QLabel, QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


# INP 后缀 → outp 后缀映射（空后缀也输出 .o）
_OUTPUT_SUFFIX_MAP = {".i": ".o", ".inp": ".out", ".txt": ".txt", "": ".o"}


class PreviewDialog(QDialog):
    """生成 INP 后的预览和保存对话框"""

    def __init__(self, inp_content: str, output_dir: str,
                 filename: str, parent=None, mcnp_exe: str = "mcnp6.exe"):
        super().__init__(parent)
        self.inp_content = inp_content
        self.output_dir = output_dir
        self.filename = filename
        self.mcnp_exe = mcnp_exe
        self.setWindowTitle("预览 INP 文件")
        self.resize(800, 600)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 提示
        label = QLabel(
            f"📄 以下是要生成的 INP 文件内容\n"
            f"保存到: <span style='font-weight:bold;'>{self.output_dir}</span>"
        )
        layout.addWidget(label)

        # 预览文本框
        self.preview = QPlainTextEdit()
        self.preview.setPlainText(self.inp_content)
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("Consolas", 10))
        self.preview.setToolTip("生成的 INP 文件内容，只读预览")
        layout.addWidget(self.preview)

        # 按钮
        btn_layout = QHBoxLayout()

        self.btn_save = QPushButton("💾 保存并打开目录")
        self.btn_save.setToolTip("保存 INP 和 run.bat 到输出目录，然后自动打开该目录")
        self.btn_save.setProperty("cssClass", "btnPrimary")
        self.btn_save.clicked.connect(self._save)

        self.btn_save_as = QPushButton("另存为…")
        self.btn_save_as.setToolTip("选择其他位置保存")
        self.btn_save_as.clicked.connect(self._save_as)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save_as)
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def _has_non_ascii(self, text: str) -> list[str]:
        """检测并返回含有非 ASCII 字符的行"""
        bad_lines = []
        for i, line in enumerate(text.split("\n"), 1):
            non_ascii = [c for c in line if ord(c) > 127]
            if non_ascii:
                bad_lines.append(f"第 {i} 行: {line.strip()[:60]}")
        return bad_lines

    def _save(self):
        """保存到默认输出目录"""
        try:
            os.makedirs(self.output_dir, exist_ok=True)

            # 检测非 ASCII 字符（仅标题卡建议使用 ASCII，注释中的中文可正常保存）
            bad_lines = self._has_non_ascii(self.inp_content)
            if bad_lines:
                detail = "\n".join(bad_lines[:5])
                if len(bad_lines) > 5:
                    detail += f"\n... 及另外 {len(bad_lines) - 5} 行"
                QMessageBox.information(
                    self, "包含非 ASCII 字符",
                    f"INP 内容中 {len(bad_lines)} 行含有非 ASCII 字符：\n\n"
                    f"{detail}\n\n"
                    "⚠ 标题卡（第 1 行）建议只使用 ASCII 字符，\n"
                    "否则 MCNP 可能解析错位。\n"
                    "注释（$ 之后）中的中文可正常保存。"
                )

            # 写 INP（UTF-8 编码，注释中的中文可正常保存）
            inp_path = os.path.join(self.output_dir, self.filename)
            with open(inp_path, "w", encoding="utf-8") as f:
                f.write(self.inp_content)

            # 写 run.bat（去掉多余的 call）
            bat_name = os.path.splitext(self.filename)[0] + ".bat"
            ext = os.path.splitext(self.filename)[1]
            out_ext = _OUTPUT_SUFFIX_MAP.get(ext, ".o")
            out_name = os.path.splitext(self.filename)[0] + out_ext
            bat_content = (
                "@echo off\n"
                f"{self.mcnp_exe} inp={self.filename} outp={out_name}\n"
                "pause\n"
            )
            bat_path = os.path.join(self.output_dir, bat_name)
            with open(bat_path, "w", encoding="ascii") as f:
                f.write(bat_content)

            QMessageBox.information(
                self, "保存成功",
                f"✓ INP 文件: {inp_path}\n"
                f"✓ 运行脚本: {bat_path}\n\n"
                f"双击 {bat_name} 即可运行 MCNP 计算。"
            )
            # 自动打开输出目录
            os.startfile(self.output_dir)
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存文件时出错:\n{str(e)}")

    def _save_as(self):
        """选择其他位置保存"""
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 INP 文件",
            os.path.join(self.output_dir, self.filename),
            "INP 文件 (*.i);;所有文件 (*.*)"
        )
        if not path:
            return

        try:
            # 检测非 ASCII 字符
            bad_lines = self._has_non_ascii(self.inp_content)
            if bad_lines:
                detail = "\n".join(bad_lines[:5])
                if len(bad_lines) > 5:
                    detail += f"\n... 及另外 {len(bad_lines) - 5} 行"
                QMessageBox.information(
                    self, "包含非 ASCII 字符",
                    f"INP 内容中 {len(bad_lines)} 行含有非 ASCII 字符：\n\n"
                    f"{detail}\n\n"
                    "⚠ 标题卡（第 1 行）建议只使用 ASCII 字符，\n"
                    "否则 MCNP 可能解析错位。\n"
                    "注释（$ 之后）中的中文可正常保存。"
                )

            with open(path, "w", encoding="utf-8") as f:
                f.write(self.inp_content)

            # run.bat 存放在同一目录
            save_dir = os.path.dirname(path)
            base = os.path.basename(path)
            bat_name = os.path.splitext(base)[0] + ".bat"
            ext = os.path.splitext(base)[1]
            out_ext = _OUTPUT_SUFFIX_MAP.get(ext, ".o")
            out_name = os.path.splitext(base)[0] + out_ext
            bat_content = (
                "@echo off\n"
                f"{self.mcnp_exe} inp={base} outp={out_name}\n"
                "pause\n"
            )
            bat_path = os.path.join(save_dir, bat_name)
            with open(bat_path, "w", encoding="ascii") as f:
                f.write(bat_content)

            QMessageBox.information(
                self, "保存成功",
                f"✓ INP 文件: {path}\n"
                f"✓ 运行脚本: {bat_path}"
            )
            # 自动打开目录
            os.startfile(save_dir)
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存文件时出错:\n{str(e)}")
