"""Output — 控制器层"""

import os, re
import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QFileDialog, QMessageBox, QHeaderView, QTableWidgetItem
)
from PyQt5.QtCore import Qt, QSettings

from app.widgets.ui_helpers import make_section_title
from .view import create_ui


class OutputTab(QWidget):

    def __init__(self):
        super().__init__()
        self._outp = None
        self._tally_numbers = []
        self._fallback_data: dict = {}
        self._out_settings = QSettings("MCNPGen", "MCNPGenerator")
        ui, btn_browse = create_ui(self)
        self.ui = ui
        self._connect_signals(btn_browse)
        self._restore_col_widths()

    def _connect_signals(self, btn_browse):
        btn_browse.clicked.connect(self._browse_file)
        self.ui.btn_parse.clicked.connect(self._parse)
        self.ui.btn_plot.clicked.connect(self._plot)
        self.ui.btn_csv.clicked.connect(self._export_csv)
        self.ui.btn_parquet.clicked.connect(self._export_parquet)
        self.ui.data_table.horizontalHeader().sectionResized.connect(self._save_out_col_widths)

    def _restore_col_widths(self):
        saved = self._out_settings.value("output_col_widths")
        if saved and len(saved) == 3:
            for col, w in enumerate(saved):
                self.ui.data_table.setColumnWidth(col, int(w))

    def _save_out_col_widths(self):
        widths = [self.ui.data_table.columnWidth(c) for c in range(self.ui.data_table.columnCount())]
        self._out_settings.setValue("output_col_widths", widths)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 MCNP 输出文件",
            os.path.dirname(self.ui.path_edit.text()) if self.ui.path_edit.text() else "D:\\",
            "输出文件 (*.outp *.o *.out);;所有文件 (*.*)"
        )
        if path:
            self.ui.path_edit.setText(path)

    def _parse(self):
        path = self.ui.path_edit.text().strip()
        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, "错误", "请先选择有效的输出文件")
            return
        try:
            import pymcnp
            self.ui.btn_parse.setEnabled(False)
            self.ui.btn_parse.setText("解析中…")
            self._outp = pymcnp.Outp.from_file(path)
            dfs = self._outp.to_dataframe()
            if not dfs:
                self.ui.file_status.setText("<span style='color:#c62828;'>⚠ 未找到 tally 数据</span>")
                return
            self._tally_numbers = sorted(dfs.keys(), key=lambda x: int(x) if x.isdigit() else x)
            self.ui.tally_combo.clear()
            for num in self._tally_numbers:
                df = dfs[num]
                self.ui.tally_combo.addItem(f"Tally {num} ({len(df)} rows)", num)
            self.ui.file_status.setText(
                f"<span style='color:#2e7d32;'>✓ 解析成功，共 {len(self._tally_numbers)} 个 tally</span>")
            self._update_preview()
            try:
                self.ui.tally_combo.currentIndexChanged.disconnect()
            except TypeError:
                pass
            self.ui.tally_combo.currentIndexChanged.connect(lambda: self._update_preview())
        except Exception as e:
            msg = str(e)
            if "OUTP table not recognized" in msg:
                if self._parse_fallback(path):
                    self.ui.file_status.setText(
                        "<span style='color:#e65100;'>⚠ pymcnp 解析失败，已使用文本 fallback 解析</span>")
                else:
                    self.ui.file_status.setText("<span style='color:#c62828;'>⚠ 解析失败: 无法识别的输出文件格式</span>")
            else:
                self.ui.file_status.setText(f"<span style='color:#c62828;'>⚠ 解析失败: {msg}</span>")
        finally:
            self.ui.btn_parse.setEnabled(True)
            self.ui.btn_parse.setText("📊 解析")

    def _parse_fallback(self, path: str) -> bool:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception:
            return False
        if not re.search(r'run terminated', text, re.I):
            self.ui.file_status.setText("<span style='color:#c62828;'>⚠ 输出文件未正常终止</span>")
            return False
        sections = re.split(r'\n1tally\s+(\d+)', text, flags=re.IGNORECASE)
        self._fallback_data = {}
        self._tally_numbers = []
        for i in range(1, len(sections), 2):
            if i + 1 >= len(sections):
                break
            tally_num = sections[i].strip()
            block = sections[i + 1]
            lines = block.split('\n')
            table_start = None
            for j, ln in enumerate(lines):
                if re.match(r'\s+energy\s+', ln, re.I):
                    table_start = j + 1
                    break
            if table_start is None:
                continue
            data_rows = []
            for ln in lines[table_start:]:
                if not ln.strip() or re.match(r'^\s*$', ln):
                    continue
                parts = re.findall(r'[\s\d.eE+-]+', ln)
                vals = re.findall(r'[\d.]+(?:[eE][+-]?\d+)?', ln)
                if len(vals) >= 3:
                    try:
                        data_rows.append([float(vals[0]), float(vals[1]), float(vals[2])])
                    except ValueError:
                        continue
            if data_rows:
                self._fallback_data[tally_num] = np.array(data_rows)
                self._tally_numbers.append(tally_num)
                self.ui.tally_combo.addItem(f"Tally {tally_num} ({len(data_rows)} rows)", tally_num)
        return len(self._fallback_data) > 0

    def _update_preview(self):
        num = self.ui.tally_combo.currentData()
        if num is None:
            return
        df = None
        if self._outp and hasattr(self._outp, 'to_dataframe'):
            try:
                dfs = self._outp.to_dataframe()
                df = dfs.get(num)
            except Exception:
                pass
        if df is not None:
            rows = min(len(df), 100)
            self.ui.data_table.setRowCount(rows)
            for i in range(rows):
                for j, col in enumerate(df.columns[:3]):
                    val = df.iloc[i][col]
                    item = QTableWidgetItem(f"{val:.6e}" if isinstance(val, float) else str(val))
                    item.setTextAlignment(Qt.AlignCenter)
                    self.ui.data_table.setItem(i, j, item)
            self.ui.tally_info.setText(f"✓ {len(df)} 行数据")
            return
        arr = self._fallback_data.get(num)
        if arr is not None:
            rows = min(len(arr), 100)
            self.ui.data_table.setRowCount(rows)
            for i in range(rows):
                for j in range(3):
                    item = QTableWidgetItem(f"{arr[i, j]:.6e}")
                    item.setTextAlignment(Qt.AlignCenter)
                    self.ui.data_table.setItem(i, j, item)
            self.ui.tally_info.setText(f"✓ {len(arr)} 行数据")
            return
        self.ui.data_table.setRowCount(0)
        self.ui.tally_info.setText("")

    def _plot_fallback(self, num):
        arr = self._fallback_data.get(num)
        if arr is None:
            return
        try:
            import matplotlib
            matplotlib.use('Qt5Agg')
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.errorbar(arr[:, 0], arr[:, 1], yerr=arr[:, 2], fmt='o-', capsize=3)
            ax.set_xlabel('Energy (MeV)')
            ax.set_ylabel('Counts')
            ax.set_title(f'Tally {num} (Fallback)')
            ax.set_xscale('log')
            ax.set_yscale('log')
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            fig.show()
        except Exception:
            pass

    def _plot(self):
        num = self.ui.tally_combo.currentData()
        if num is None:
            return
        if self._fallback_data:
            self._plot_fallback(num)
            return
        try:
            import matplotlib
            matplotlib.use('Qt5Agg')
            import matplotlib.pyplot as plt
            dfs = self._outp.to_dataframe()
            if num not in dfs:
                return
            df = dfs[num]
            cols = df.columns[:3]
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.errorbar(df[cols[0]], df[cols[1]], yerr=df[cols[2]], fmt='o-', capsize=3)
            ax.set_xlabel(cols[0])
            ax.set_ylabel(cols[1])
            ax.set_title(f'Tally {num}')
            ax.set_xscale('log')
            ax.set_yscale('log')
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            fig.show()
        except Exception as e:
            QMessageBox.warning(self, "绘图失败", str(e))

    def _export_csv(self):
        num = self.ui.tally_combo.currentData()
        if num is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出 CSV", f"tally_{num}.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            if self._fallback_data:
                arr = self._fallback_data[num]
                np.savetxt(path, arr, delimiter=",", header="Energy,Counts,Errors", comments="")
            else:
                dfs = self._outp.to_dataframe()
                dfs[num].to_csv(path, index=False)
            QMessageBox.information(self, "导出成功", f"已保存: {path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def _export_parquet(self):
        num = self.ui.tally_combo.currentData()
        if num is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出 Parquet", f"tally_{num}.parquet", "Parquet (*.parquet)")
        if not path:
            return
        try:
            import pandas as pd
            if self._fallback_data:
                arr = self._fallback_data[num]
                df = pd.DataFrame(arr, columns=["Energy", "Counts", "Errors"])
            else:
                dfs = self._outp.to_dataframe()
                df = dfs[num]
            df.to_parquet(path, index=False)
            QMessageBox.information(self, "导出成功", f"已保存: {path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))
