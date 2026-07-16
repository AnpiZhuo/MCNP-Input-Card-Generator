"""
📈 输出标签页：解析 MCNP 输出文件 + 绘图 + 导出
"""

import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox, QTextEdit, QSplitter
)
from PyQt5.QtCore import Qt, QSettings


class OutputTab(QWidget):
    """输出文件解析与绘图标签页"""

    def __init__(self):
        super().__init__()
        self._outp = None          # pymcnp.Outp 实例
        self._tally_numbers = []   # 可用的 tally 编号列表
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ===== 功能未完成提示 =====
        warn = QLabel(
            "<span style='color:#c62828; font-weight:bold;'>"
            "⚠ 注意：输出板块功能尚未完成，部分功能可能无法正常工作。</span>"
        )
        warn.setWordWrap(True)
        layout.addWidget(warn)

        # ===== 文件选择 =====
        grp_file = QGroupBox("选择 MCNP 输出文件")
        grp_file.setToolTip("加载 MCNP 输出文件（outp），解析并提取 tally 数据")
        file_layout = QVBoxLayout(grp_file)

        path_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("例: D:\\MCNP\\test_run\\output.outp")
        self.path_edit.setToolTip("MCNP 输出文件路径（.outp / .o / .out）")
        path_row.addWidget(self.path_edit, 1)

        btn_browse = QPushButton("浏览…")
        btn_browse.setToolTip("选择 MCNP 输出文件")
        btn_browse.setProperty("cssClass", "btnBrowse")
        btn_browse.clicked.connect(self._browse_file)
        path_row.addWidget(btn_browse)

        self.btn_parse = QPushButton("📊 解析")
        self.btn_parse.setToolTip("解析输出文件，提取所有 tally 数据")
        self.btn_parse.setProperty("cssClass", "btnPrimary")
        self.btn_parse.clicked.connect(self._parse)
        path_row.addWidget(self.btn_parse)

        file_layout.addLayout(path_row)
        self.file_status = QLabel("")
        file_layout.addWidget(self.file_status)
        layout.addWidget(grp_file)

        # ===== Tally 选择 & 操作 =====
        grp_tally = QGroupBox("Tally 数据")
        grp_tally.setToolTip("选择要查看/绘图的 tally 编号")
        tally_layout = QVBoxLayout(grp_tally)

        tally_row = QHBoxLayout()
        tally_row.addWidget(QLabel("Tally 编号:"))
        self.tally_combo = QComboBox()
        self.tally_combo.setToolTip("选择要操作的 tally 编号")
        self.tally_combo.setMinimumWidth(120)
        tally_row.addWidget(self.tally_combo)

        tally_row.addSpacing(16)

        self.btn_plot = QPushButton("📈 绘图")
        self.btn_plot.setToolTip("使用 matplotlib 绘制选中 tally 的能谱")
        self.btn_plot.setProperty("cssClass", "btnPrimary")
        self.btn_plot.clicked.connect(self._plot)
        tally_row.addWidget(self.btn_plot)

        self.btn_csv = QPushButton("📋 导出 CSV")
        self.btn_csv.setToolTip("将选中 tally 导出为 CSV 文件")
        self.btn_csv.clicked.connect(self._export_csv)
        tally_row.addWidget(self.btn_csv)

        self.btn_parquet = QPushButton("📦 导出 Parquet")
        self.btn_parquet.setToolTip("将选中 tally 导出为 Parquet 文件")
        self.btn_parquet.clicked.connect(self._export_parquet)
        tally_row.addWidget(self.btn_parquet)

        tally_row.addStretch()
        tally_layout.addLayout(tally_row)

        self.tally_info = QLabel("")
        tally_layout.addWidget(self.tally_info)

        layout.addWidget(grp_tally)

        # ===== 数据预览 =====
        grp_data = QGroupBox("数据预览（前 100 行）")
        data_layout = QVBoxLayout(grp_data)

        self.data_table = QTableWidget(0, 3)
        self.data_table.setHorizontalHeaderLabels(["Bins / Energy", "Counts", "Errors"])
        hdr = self.data_table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setStretchLastSection(False)
        self._out_settings = QSettings("MCNPGen", "MCNPGenerator")
        saved = self._out_settings.value("output_col_widths")
        if saved and len(saved) == 3:
            for col, w in enumerate(saved):
                self.data_table.setColumnWidth(col, int(w))
        else:
            self.data_table.setColumnWidth(0, 200)
            self.data_table.setColumnWidth(1, 150)
            self.data_table.setColumnWidth(2, 150)
        hdr.sectionResized.connect(self._save_out_col_widths)
        self.data_table.setEditTriggers(QTableWidget.NoEditTriggers)
        data_layout.addWidget(self.data_table)

        layout.addWidget(grp_data, 1)

        # 底部提示
        hint = QLabel(
            "<span style='color:gray; font-size:11px;'>"
            "💡 支持标准 MCNP 输出文件。解析后可查看 tally 数据、绘图或导出为 CSV/Parquet。</span>"
        )
        layout.addWidget(hint)

    # ---------- 操作 ----------

    def _save_out_col_widths(self):
        """数据预览表列宽自动保存"""
        widths = [self.data_table.columnWidth(c) for c in range(self.data_table.columnCount())]
        self._out_settings.setValue("output_col_widths", widths)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 MCNP 输出文件",
            os.path.dirname(self.path_edit.text()) if self.path_edit.text() else "D:\\",
            "输出文件 (*.outp *.o *.out);;所有文件 (*.*)"
        )
        if path:
            self.path_edit.setText(path)

    def _parse(self):
        path = self.path_edit.text().strip()
        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, "错误", "请先选择有效的输出文件")
            return

        try:
            import pymcnp
            self.btn_parse.setEnabled(False)
            self.btn_parse.setText("解析中…")

            self._outp = pymcnp.Outp.from_file(path)
            dfs = self._outp.to_dataframe()

            if not dfs:
                self.file_status.setText(
                    "<span style='color:#c62828;'>⚠ 未找到 tally 数据</span>"
                )
                return

            self._tally_numbers = sorted(dfs.keys(), key=lambda x: int(x) if x.isdigit() else x)
            self.tally_combo.clear()
            for num in self._tally_numbers:
                df = dfs[num]
                rows = len(df)
                cols = ", ".join(df.columns[:3])
                self.tally_combo.addItem(f"Tally {num} ({rows} rows)", num)

            self.file_status.setText(
                f"<span style='color:#2e7d32;'>✓ 解析成功，"
                f"共 {len(self._tally_numbers)} 个 tally</span>"
            )
            self._update_preview()

        except Exception as e:
            self.file_status.setText(
                f"<span style='color:#c62828;'>⚠ 解析失败: {e}</span>"
            )
        finally:
            self.btn_parse.setEnabled(True)
            self.btn_parse.setText("📊 解析")

    def _current_tally(self) -> str | None:
        """获取当前选中的 tally 编号"""
        idx = self.tally_combo.currentIndex()
        if idx < 0:
            return None
        return self.tally_combo.currentData()

    def _update_preview(self):
        """更新数据预览表"""
        if self._outp is None:
            return
        num = self._current_tally()
        if num is None:
            return

        try:
            dfs = self._outp.to_dataframe()
            df = dfs[num]
            self.tally_info.setText(
                f"<span style='color:#5f6368;'>列: {', '.join(df.columns[:6])}  |  "
                f"共 {len(df)} 行</span>"
            )

            # 显示前 100 行
            preview = df.head(100)
            self.data_table.setRowCount(len(preview))

            # 前 3 列
            cols = df.columns[:3]
            for row_idx in range(len(preview)):
                for col_idx, col in enumerate(cols):
                    if col_idx < 3:
                        val = preview.iloc[row_idx, col_idx]
                        item = QTableWidgetItem(f"{val:.6g}" if isinstance(val, float) else str(val))
                        self.data_table.setItem(row_idx, col_idx, item)

            # 更新表头
            headers = list(cols) + ([""] * (3 - len(cols)))
            self.data_table.setHorizontalHeaderLabels(headers[:3])

        except Exception as e:
            self.tally_info.setText(
                f"<span style='color:#c62828;'>⚠ 预览失败: {e}</span>"
            )

        self.tally_combo.currentIndexChanged.connect(
            lambda: self._update_preview()
        )

    def _plot(self):
        if self._outp is None:
            QMessageBox.warning(self, "提示", "请先解析输出文件")
            return
        num = self._current_tally()
        if num is None:
            QMessageBox.warning(self, "提示", "请选择要绘图的 tally")
            return

        try:
            import pymcnp
            import matplotlib.pyplot as plt
            pymcnp.Plot(self._outp).to_show(num)
            plt.show()
        except Exception as e:
            QMessageBox.critical(self, "绘图失败", str(e))

    def _export_csv(self):
        if self._outp is None:
            QMessageBox.warning(self, "提示", "请先解析输出文件")
            return
        num = self._current_tally()
        if num is None:
            QMessageBox.warning(self, "提示", "请选择要导出的 tally")
            return

        default_name = f"tally_{num}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 CSV", default_name,
            "CSV 文件 (*.csv);;所有文件 (*.*)"
        )
        if not path:
            return

        try:
            import pymcnp
            pymcnp.Convert(self._outp).to_csv(num, path)
            QMessageBox.information(self, "导出成功", f"已保存到:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _export_parquet(self):
        if self._outp is None:
            QMessageBox.warning(self, "提示", "请先解析输出文件")
            return
        num = self._current_tally()
        if num is None:
            QMessageBox.warning(self, "提示", "请选择要导出的 tally")
            return

        default_name = f"tally_{num}.parquet"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 Parquet", default_name,
            "Parquet 文件 (*.parquet);;所有文件 (*.*)"
        )
        if not path:
            return

        try:
            import pymcnp
            pymcnp.Convert(self._outp).to_parquet(num, path)
            QMessageBox.information(self, "导出成功", f"已保存到:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
