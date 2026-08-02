"""
Deep module: 参考文档弹窗

小接口：一个函数创建 ? 按钮，一个函数展示弹窗。
统一处理 app/docs/ 下的 .md（markdown 渲染）和 .txt（纯文本渲染）两种格式。
"""

import os
from PyQt5.QtWidgets import (
    QPushButton, QDialog, QTextBrowser, QVBoxLayout,
    QMessageBox,
)
from PyQt5.QtCore import Qt


def show_reference_doc(parent, filename: str, title: str):
    """读取 app/docs/ 下的参考文档，以非模态弹窗展示

    Args:
        parent: 父窗口 QWidget
        filename: 文件名（如 "MCNP6_曲面卡格式参考.md"）
        title: 窗口标题
    """
    ref_path = os.path.join(os.path.dirname(__file__), "..", "docs", filename)
    ref_path = os.path.normpath(ref_path)

    if not os.path.isfile(ref_path):
        QMessageBox.warning(parent, "未找到", f"参考文档不存在:\n{ref_path}")
        return

    try:
        with open(ref_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        QMessageBox.critical(parent, "读取失败", f"无法读取参考文档:\n{e}")
        return

    # 检测深色主题
    from PyQt5.QtGui import QColor
    bg = parent.palette().window().color()
    dark = bg.lightness() < 128

    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumSize(850, 700)
    dialog.resize(850, 700)
    layout = QVBoxLayout(dialog)

    # 根据扩展名选择渲染方式
    if filename.endswith(".md"):
        full_html = _render_markdown(content, dark)
    else:
        full_html = _render_plain_text(content, dark)

    browser = QTextBrowser()
    browser.setHtml(full_html)
    browser.setOpenExternalLinks(True)
    layout.addWidget(browser)

    btn_close = QPushButton("关闭")
    btn_close.clicked.connect(dialog.close)
    layout.addWidget(btn_close, alignment=Qt.AlignRight)

    dialog.setAttribute(Qt.WA_DeleteOnClose, True)
    dialog.setWindowFlags(
        dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint
    )
    dialog.show()


def make_help_button(parent, filename: str, title: str) -> QPushButton:
    """创建标准的蓝色 ? 帮助按钮，点击弹出参考文档

    Args:
        parent: 父窗口（按钮的 parent，也传给弹窗）
        filename: docs 目录下的文件名
        title: 弹窗标题

    Returns:
        QPushButton — 已连接好信号，addWidget 即可使用
    """
    btn = QPushButton("?")
    btn.setFixedSize(20, 20)
    btn.setStyleSheet(
        "QPushButton { background-color: #1976d2; color: white; "
        "border-radius: 10px; font-weight: bold; font-size: 11px; border: none; }"
        "QPushButton:hover { background-color: #1565c0; }"
    )
    btn.setToolTip(f"查看 {title}")
    btn.clicked.connect(lambda: show_reference_doc(parent, filename, title))
    return btn


# ── 内部渲染函数 ──────────────────────────────────────────

def _md_wrap(dark: bool) -> str:
    """返回 Markdown HTML 包装模板（明/暗两套色）。"""
    if dark:
        return """\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:'Microsoft YaHei','Segoe UI',sans-serif;
      font-size:14px; line-height:1.8; color:#e0e0e0; background:#1e1e1e;
      max-width:820px; margin:0 auto; padding:12px 20px;">
<style>
  body {{ background:#1e1e1e; }}
  h1 {{ font-size:22px; border-bottom:2px solid #42a5f5; padding-bottom:6px; color:#64b5f6; }}
  h2 {{ font-size:18px; color:#64b5f6; margin-top:24px; border-bottom:1px solid #333; padding-bottom:4px; }}
  h3 {{ font-size:15px; color:#b0bec5; margin-top:18px; }}
  table {{ border-collapse:collapse; width:100%; margin:10px 0; }}
  th {{ background-color:#333; font-weight:bold; padding:7px 10px; border:1px solid #555; text-align:left; color:#e0e0e0; }}
  td {{ padding:5px 10px; border:1px solid #444; color:#ccc; }}
  code {{ background:#2d2d2d; padding:1px 5px; border-radius:3px; font-size:13px; color:#ce93d8; }}
  pre {{ background:#2d2d2d; padding:10px; border-radius:4px; overflow-x:auto; color:#ccc; }}
  blockquote {{ border-left:3px solid #42a5f5; margin:10px 0; padding:4px 14px; color:#aaa; background:#252525; }}
</style>
{body}
</body>
</html>"""
    return """\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:'Microsoft YaHei','Segoe UI',sans-serif;
      font-size:14px; line-height:1.8; color:#222; max-width:820px; margin:0 auto; padding:12px 20px;">
<style>
  h1 {{ font-size:22px; border-bottom:2px solid #1976d2; padding-bottom:6px; color:#1565c0; }}
  h2 {{ font-size:18px; color:#1565c0; margin-top:24px; border-bottom:1px solid #e0e0e0; padding-bottom:4px; }}
  h3 {{ font-size:15px; color:#333; margin-top:18px; }}
  table {{ border-collapse:collapse; width:100%; margin:10px 0; }}
  th {{ background-color:#e3f2fd; font-weight:bold; padding:7px 10px; border:1px solid #bbb; text-align:left; }}
  td {{ padding:5px 10px; border:1px solid #ddd; }}
  code {{ background:#f5f5f5; padding:1px 5px; border-radius:3px; font-size:13px; }}
  pre {{ background:#f5f5f5; padding:10px; border-radius:4px; overflow-x:auto; }}
  blockquote {{ border-left:3px solid #1976d2; margin:10px 0; padding:4px 14px; color:#555; background:#f8f9fa; }}
</style>
{body}
</body>
</html>"""


def _render_markdown(content: str, dark: bool = False) -> str:
    """Markdown → 带样式的完整 HTML"""
    import markdown as _md
    html_body = _md.markdown(content, extensions=["extra", "toc"])
    return _md_wrap(dark).format(body=html_body)


def _render_plain_text(content: str, dark: bool = False) -> str:
    """纯文本 → 带样式的 HTML"""
    text_col = "#e0e0e0" if dark else "#222"
    bg_col = "#1e1e1e" if dark else "#ffffff"
    hdr_col = "#64b5f6" if dark else "#1565c0"
    code_bg = "#2d2d2d" if dark else "#f5f5f5"
    code_col = "#ce93d8" if dark else "#222"
    html = [
        f'<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
        f'<body style="font-family:Microsoft YaHei,sans-serif;font-size:14px;'
        f'line-height:1.8;color:{text_col};background:{bg_col};'
        f'max-width:820px;margin:0 auto;padding:12px 20px;">'
    ]
    in_code = False

    for line in content.split("\n"):
        s = line.strip()
        # 纯装饰线
        if s and all(c in "=#" for c in s) and len(s) > 3:
            if len(html) == 1:
                continue
            html.append("<hr>")
            continue
        # 【xxx】标题
        if s.startswith("【") and s.endswith("】"):
            html.append(f'<h3 style="color:{hdr_col};margin:18px 0 8px 0;">{s}</h3>')
            continue
        # # N. 标题
        if s.startswith("#") and s[1:2].isdigit():
            html.append(
                f'<h2 style="color:{hdr_col};border-bottom:1px solid #e0e0e0;'
                f'padding-bottom:4px;margin-top:24px;">{s.lstrip("# ").strip()}</h2>'
            )
            continue
        # 空行
        if not s:
            if in_code:
                html.append("</pre>")
                in_code = False
            html.append("<br>")
            continue
        # 短行 → 段落
        if any(c in s for c in "()【】:：") and len(s) < 80:
            html.append(f"<p style='margin:4px 0;'>{s}</p>" if not in_code else f"{s}<br>")
            continue
        # 长行 → 代码块
        if not in_code:
            html.append(
                f'<pre style="background:{code_bg};padding:6px 10px;'
                f'border-radius:4px;margin:4px 0;font-size:13px;">'
            )
            in_code = True
        html.append(f"{s}<br>")

    if in_code:
        html.append("</pre>")
    html.append("</body></html>")
    return "\n".join(html)
