"""
MCNP 曲面卡 / TR 卡语法高亮 — QSyntaxHighlighter

高亮规则：
  - 注释卡 C/c → 整行灰斜
  - $ 行内注释 → 灰斜
  - 曲面号（行首整数）→ 蓝色
  - 曲面类型助记符 → 深蓝加粗
  - 数字参数 → 绿色
  - TRn/*TRn 前缀 → 紫红
"""

from PyQt5.QtCore import QRegExp, Qt
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont


# ── 完整曲面类型列表（MCNP6 C810） ────────────────────────
_SURFACE_TYPES = [
    # 平面
    "P", "PX", "PY", "PZ",
    # 球
    "SO", "S", "SX", "SY", "SZ",
    # 圆柱（轴对齐 / 平行轴）
    "CX", "CY", "CZ", "C/X", "C/Y", "C/Z",
    # 圆锥
    "KX", "KY", "KZ", "K/X", "K/Y", "K/Z",
    # 二次曲面
    "SQ", "GQ",
    # 环面
    "TX", "TY", "TZ",
    # 点定义截面
    "X", "Y", "Z",
    # Macrobody
    "RPP", "SPH", "RCC", "TRC", "REC", "ELL", "WED", "BOX", "ARB", "RHP", "HEX",
]

def _make_format(color, bold=False, italic=False):
    fmt = QTextCharFormat()
    fmt.setForeground(color)
    if bold:
        fmt.setFontWeight(QFont.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


# ── 默认颜色（被 style.py PALETTES.syn_* 覆盖） ──────────
_DEFAULT_COLORS = {
    "syn_comment": "#6b7280", "syn_keyword": "#2563eb",
    "syn_number": "#059669", "syn_surface": "#7c3aed",
    "syn_operator": "#dc2626", "syn_trcl": "#0891b2",
    "syn_tr_param": "#d97706", "syn_ref": "#0891b2",
    "syn_id": "#e65100",
}


def _colors_from_dict(d: dict) -> dict:
    """从 dict 取 9 个 syn_* 值，缺少的从 _DEFAULT_COLORS 补"""
    return {k: QColor(d.get(k, _DEFAULT_COLORS[k])) for k in _DEFAULT_COLORS}


class MCNPSurfaceHighlighter(QSyntaxHighlighter):
    """曲面卡 + TR 卡语法高亮"""

    def __init__(self, parent=None, colors: dict = None):
        super().__init__(parent)
        self.colors = _colors_from_dict(colors or {})
        self._build_rules()

    def set_colors(self, colors: dict):
        self.colors = _colors_from_dict(colors)
        self._build_rules()
        self.rehighlight()

    def _build_rules(self):
        c = self.colors
        # 1. 注释卡（C 或 c 开头）—— 整行
        self._comment_line_fmt = _make_format(c["syn_comment"], italic=True)
        self._comment_line_re = QRegExp(r"^[Cc]\s.*")

        # 2. $ 行内注释
        self._inline_comment_fmt = _make_format(c["syn_comment"], italic=True)
        self._inline_comment_re = QRegExp(r"\$.*")

        # 3. TRn / *TRn / TRCL= 引用
        self._tr_fmt = _make_format(c["syn_trcl"], bold=True)
        self._tr_re = QRegExp(r"\*?TR\d+")
        self._tr_re.setCaseSensitivity(Qt.CaseInsensitive)
        self._trcl_fmt = _make_format(c["syn_trcl"])
        self._trcl_re = QRegExp(r"TRCL=\d+")

        # 4. 曲面类型助记符（独立单词，大写）
        self._type_fmt = _make_format(c["syn_surface"], bold=True)
        self._type_re = QRegExp(r"\b(" + "|".join(_SURFACE_TYPES) + r")\b")
        self._type_re.setCaseSensitivity(Qt.CaseInsensitive)

        # 5. 曲面号（行首整数 → 橙红）
        self._id_fmt = _make_format(c["syn_id"])
        self._id_re = QRegExp(r"^\s*\d+")

        # 6. 曲面号后的数字引用（与 TRn 同色）：j n a… 中的 n
        self._tr_ref_fmt = _make_format(c["syn_trcl"])
        self._tr_ref_re = QRegExp(r"^\s*\d+\s+(\d+)\s+[A-Za-z/]")

        # 7. 数字参数（整数、浮点、科学计数 → 绿色）
        self._num_fmt = _make_format(c["syn_number"])
        self._num_re = QRegExp(r"\b[+-]?\d+\.?\d*(?:[eE][+-]?\d+)?\b")

    def highlightBlock(self, text):
        if not text:
            return

        # 注释卡 → 整行灰斜，跳过其余规则
        if self._comment_line_re.indexIn(text) == 0:
            self.setFormat(0, len(text), self._comment_line_fmt)
            return

        # 按优先级从低到高应用（后面的覆盖前面的）
        self._apply_rule(self._num_re, self._num_fmt, text)          # 数字参数（绿）
        self._apply_rule(self._id_re, self._id_fmt, text)            # 曲面号（红）覆盖行首数字
        self._apply_tr_ref(text)                                      # 曲面号后的数字引用（紫）
        self._apply_rule(self._type_re, self._type_fmt, text)        # 类型（深蓝）覆盖数字
        self._apply_rule(self._tr_re, self._tr_fmt, text)            # TRn（紫红）覆盖
        self._apply_rule(self._trcl_re, self._trcl_fmt, text)        # TRCL= 引用
        self._apply_rule(self._inline_comment_re, self._inline_comment_fmt, text)  # 注释最高

    def _apply_tr_ref(self, text):
        """匹配曲面号后的数字引用（j n a… 中的 n），只给第二个数字上色"""
        idx = self._tr_ref_re.indexIn(text)
        if idx >= 0:
            pos = self._tr_ref_re.pos(1)
            if pos >= 0:
                self.setFormat(pos, len(self._tr_ref_re.cap(1)), self._tr_ref_fmt)

    def _apply_rule(self, regex, fmt, text):
        idx = regex.indexIn(text)
        while idx >= 0:
            length = regex.matchedLength()
            self.setFormat(idx, length, fmt)
            idx = regex.indexIn(text, idx + length)


# ── TR 卡专用高亮（强调 TRn / *TRn） ────────────────────

class MCNPTRHighlighter(QSyntaxHighlighter):
    """TR 变换卡语法高亮：TRn 紫 + 前3个数(Tx,Ty,Tz)橙黄 + 后9个(B)绿 + 注释灰"""

    def __init__(self, parent=None, colors: dict = None):
        super().__init__(parent)
        self.colors = _colors_from_dict(colors or {})
        self._build_rules()

    def set_colors(self, colors: dict):
        self.colors = _colors_from_dict(colors)
        self._build_rules()
        self.rehighlight()

    def _build_rules(self):
        c = self.colors
        self._tr_fmt = _make_format(c["syn_trcl"], bold=True)
        self._t_fmt = _make_format(c["syn_tr_param"])   # Tx,Ty,Tz
        self._b_fmt = _make_format(c["syn_number"])       # B 矩阵
        self._comment_fmt = _make_format(c["syn_comment"], italic=True)
        self._tr_re = QRegExp(r"\*?TR\d+")
        self._tr_re.setCaseSensitivity(Qt.CaseInsensitive)
        self._comment_re = QRegExp(r"\$.*")

    def highlightBlock(self, text):
        if not text:
            return

        # $ 注释优先处理
        ci = self._comment_re.indexIn(text)
        comment_start = ci if ci >= 0 else len(text)

        # 取 $ 之前的部分做数字解析
        body = text[:comment_start]

        # 将 body 拆成 tokens
        tokens = body.split()
        # 跳过第一个 token（TRn/*TRn），对其单独上色
        token_start = 0
        token_idx = 0
        for i, tok in enumerate(tokens):
            # 找到 token 在 body 中的位置
            start = body.find(tok, token_start)
            if start < 0:
                break
            end = start + len(tok)

            if i == 0:
                # TRn 或 *TRn → 紫红
                if self._tr_re.indexIn(tok) >= 0:
                    self.setFormat(start, end - start, self._tr_fmt)
            elif i <= 3:
                # 第 1-3 个参数（Tx, Ty, Tz）→ 橙黄
                self.setFormat(start, end - start, self._t_fmt)
            else:
                # 第 4 个及以后（B1-B9, M）→ 绿
                self.setFormat(start, end - start, self._b_fmt)

            token_start = end

        # $ 注释 → 灰色斜体
        if ci >= 0:
            self.setFormat(ci, len(text) - ci, self._comment_fmt)
