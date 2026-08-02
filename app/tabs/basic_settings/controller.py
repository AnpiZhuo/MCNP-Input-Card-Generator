"""
BasicSettings — 控制器层

桥接视图和数据模型，处理信号路由和数据读写。
"""

import re
from PyQt5.QtWidgets import QWidget, QMessageBox
from PyQt5.QtCore import Qt, pyqtSignal

from app.models import BasicSettings
from .view import create_ui


class BasicSettingsTab(QWidget):
    """基本设置标签页 — 控制器"""

    modeChanged = pyqtSignal(object)  # 发射 BasicSettings

    def __init__(self):
        super().__init__()
        self.ui = create_ui(self)
        self._egg_triggered: set[str] = set()
        self._connect_signals()

    def _connect_signals(self):
        """信号路由"""
        # MODE 复选框 → 发射 modeChanged
        for chk in [self.ui.chk_n, self.ui.chk_p, self.ui.chk_e, self.ui.chk_h,
                    self.ui.chk_he, self.ui.chk_d, self.ui.chk_t, self.ui.chk_a]:
            chk.toggled.connect(lambda: self.modeChanged.emit(self.get_data()))
        # 标题彩蛋
        self.ui.title_edit.textChanged.connect(self._easter_egg)

    # ── 彩蛋（纯娱乐，不影响功能） ──

    def _easter_egg(self, text: str):
        t = text.lower().strip()
        eggs = [
            (r'\boutp\b', 'outp',
             "不是……大哥，你写的是输入卡。\nOUTP 是输出文件的名字，你标题写这个干嘛？"),
            (r'\binp\b', 'inp',
             "INP！INP！INP！\n你就不能想个比 INP 更有创意的名字吗？"),
            (r'\btitle\b', 'title',
             "Title? 你管这叫 title？\n行吧，你说是就是。"),
            (r'\btest\b', 'test',
             "又到了经典的「先跑个测试看看」环节。祝你一次过。"),
            (r'\b(simple|easy|just|quick)\b', 'simple',
             "「简单算一下」—— 全人类的 flag。建议预留半天调参数。"),
            (r'\b(final|last|ultimate)\b', 'final',
             "检测到标题含「最终版」。三天后你还会回来的。"),
            (r'\b(help|sos)\b', 'help',
             "你好，你已经在使用 MCNP 生成器了。剩下的帮不了你了，去看 C810 吧。"),
            (r'\bhello\b', 'hello',
             "Hello World! 来自一个没有感情的 AI。"),
            (r'\b(uranium|plutonium)\b', 'uranium',
             "检测到裂变材料。确保你持有相关许可证。"),
            (r'\bboring\b', 'boring',
             "MCNP 前处理确实不酷。但你把这件事做完了，这才是酷的。"),
            (r'\b(perfect|nice|good|done|awesome)\b', 'good',
             "看到成果了吧？奖励自己一杯奶茶。"),
            (r'\bweiyizhuo\b', 'weiyizhuo',
             "这你都认识？你跟作者很熟吗？\n别声张，他不知道自己是个名人。"),
            (r'1378963177', 'qq',
             "这个邮箱我记住了。"),
            (r'\b(bug|error|crash|fail)\b', 'bug',
             "\U0001f41b 没有 bug 的程序不是好程序。"),
            (r'\b(shit|crap|fuck|damn)\b', 'shit',
             "消消气。出去喝杯水，回来再战。"),
        ]
        for pattern, key, msg in eggs:
            if key not in self._egg_triggered and re.search(pattern, t):
                self._egg_triggered.add(key)
                QMessageBox.information(self, "\U0001f38a 彩蛋！", msg)
                break

    # ── 数据接口 ──

    def get_data(self) -> BasicSettings:
        """获取当前标签页的数据"""
        return BasicSettings(
            title=self.ui.title_edit.text().strip(),
            mode_n=self.ui.chk_n.isChecked(),
            mode_p=self.ui.chk_p.isChecked(),
            mode_e=self.ui.chk_e.isChecked(),
            mode_h=self.ui.chk_h.isChecked(),
            mode_he=self.ui.chk_he.isChecked(),
            mode_d=self.ui.chk_d.isChecked(),
            mode_t=self.ui.chk_t.isChecked(),
            mode_a=self.ui.chk_a.isChecked(),
            nps=self.ui.nps_edit.text().strip(),
            ctme=self.ui.ctme_edit.text().strip(),
            act=self.ui.act_edit.text().strip(),
            print_pr=self.ui.pr_edit.text().strip(),
            phys_fis=not self.ui.phys_fis.isChecked(),
        )

    def set_data(self, basic: BasicSettings):
        """从 BasicSettings 回填 UI"""
        self.ui.title_edit.setText(basic.title)
        self.ui.chk_n.setChecked(basic.mode_n)
        self.ui.chk_p.setChecked(basic.mode_p)
        self.ui.chk_e.setChecked(basic.mode_e)
        self.ui.chk_h.setChecked(basic.mode_h)
        self.ui.chk_he.setChecked(basic.mode_he)
        self.ui.chk_d.setChecked(getattr(basic, 'mode_d', False))
        self.ui.chk_t.setChecked(getattr(basic, 'mode_t', False))
        self.ui.chk_a.setChecked(getattr(basic, 'mode_a', False))
        self.ui.nps_edit.setText(basic.nps or "")
        self.ui.ctme_edit.setText(basic.ctme or "")
        self.ui.act_edit.setText(basic.act or "")
        self.ui.pr_edit.setText(basic.print_pr or "")
        self.ui.phys_fis.setChecked(not basic.phys_fis)
