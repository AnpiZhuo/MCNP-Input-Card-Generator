"""
MCNP 截面库索引：读取 xsdir 文件，提供 ZAID 校验、元素选择、质量数过滤
"""

import os
import re

# 常见 xsdir 位置
COMMON_PATHS = [
    r"D:\MCNP\MCNP6\MCNP_DATA\xsdir", r"D:\MCNP6\MCNP_DATA\xsdir",
    r"D:\MCNP\MCNP_DATA\xsdir", r"C:\Program Files\MCNP6\MCNP_DATA\xsdir",
    r"C:\Program Files (x86)\MCNP6\MCNP_DATA\xsdir", r"C:\MCNP6\MCNP_DATA\xsdir",
    r"C:\MCNP\MCNP_DATA\xsdir", r"C:\xdata\xsdir", r"D:\xdata\xsdir",
    r"C:\MCNP_DATA\xsdir", r"D:\MCNP_DATA\xsdir",
    "/d/MCNP/MCNP6/MCNP_DATA/xsdir", "/c/Program Files/MCNP6/MCNP_DATA/xsdir",
]

# 原子序数 → 元素符号
Z_TO_SYMBOL = {
    1: "H", 2: "He", 3: "Li", 4: "Be", 5: "B", 6: "C", 7: "N", 8: "O", 9: "F", 10: "Ne",
    11: "Na", 12: "Mg", 13: "Al", 14: "Si", 15: "P", 16: "S", 17: "Cl", 18: "Ar", 19: "K", 20: "Ca",
    21: "Sc", 22: "Ti", 23: "V", 24: "Cr", 25: "Mn", 26: "Fe", 27: "Co", 28: "Ni", 29: "Cu", 30: "Zn",
    31: "Ga", 32: "Ge", 33: "As", 34: "Se", 35: "Br", 36: "Kr", 37: "Rb", 38: "Sr", 39: "Y", 40: "Zr",
    41: "Nb", 42: "Mo", 43: "Tc", 44: "Ru", 45: "Rh", 46: "Pd", 47: "Ag", 48: "Cd", 49: "In", 50: "Sn",
    51: "Sb", 52: "Te", 53: "I", 54: "Xe", 55: "Cs", 56: "Ba", 57: "La", 58: "Ce", 59: "Pr", 60: "Nd",
    61: "Pm", 62: "Sm", 63: "Eu", 64: "Gd", 65: "Tb", 66: "Dy", 67: "Ho", 68: "Er", 69: "Tm", 70: "Yb",
    71: "Lu", 72: "Hf", 73: "Ta", 74: "W", 75: "Re", 76: "Os", 77: "Ir", 78: "Pt", 79: "Au", 80: "Hg",
    81: "Tl", 82: "Pb", 83: "Bi", 84: "Po", 85: "At", 86: "Rn", 87: "Fr", 88: "Ra", 89: "Ac", 90: "Th",
    91: "Pa", 92: "U", 93: "Np", 94: "Pu", 95: "Am", 96: "Cm", 97: "Bk", 98: "Cf", 99: "Es", 100: "Fm",
}

# 元素符号 → 原子序数（不区分大小写）
SYMBOL_TO_Z = {v.lower(): k for k, v in Z_TO_SYMBOL.items()}


def find_xsdir() -> str | None:
    for path in COMMON_PATHS:
        if os.path.isfile(path):
            return path
    return None


def parse_zzaaam(num_str: str) -> tuple[int, int] | None:
    """
    解析 ZZZAAA 数字部分，返回 (Z, A)。
    4位: Z=1位, A=3位 (1001 → 1, 1)
    5位: Z=2位, A=3位 (6012 → 6, 12)
    6位: Z=3位, A=3位 (92235 → 92, 235)
    """
    if not num_str.isdigit():
        return None
    n = len(num_str)
    if n == 4:
        z = int(num_str[0])
        a = int(num_str[1:])
    elif n == 5:
        z = int(num_str[:2])
        a = int(num_str[2:])
    elif n == 6:
        z = int(num_str[:3])
        a = int(num_str[3:])
    else:
        return None
    if z < 1 or z > 100:
        return None
    return (z, a)


def format_zzaaam(z: int, a: int) -> str:
    """将 (Z, A) 格式化为 ZZZAAA 数字字符串
    Z 变长（1~3位），A 固定 3 位:
       Z=1, A=1   → "1" + "001" = "1001"
       Z=6, A=12  → "6" + "012" = "6012"
       Z=92, A=235 → "92" + "235" = "92235"
    """
    return f"{z}{a:03d}"


class XsdirDB:
    """截面库索引，提供 ZAID 查询、元素选择、质量数过滤"""

    def __init__(self):
        self.path: str | None = None
        self.zaids: dict[str, list[str]] = {}  # "1001.80c" → [...]
        self.loaded = False
        self.error = ""
        # 按元素分组的同位素: { z: set([a1, a2, ...]) }
        self.isotopes: dict[int, set[int]] = {}

    def load(self, filepath: str | None = None, force: bool = False) -> bool:
        if filepath:
            if not force and filepath == self.path and self.loaded:
                return True
            self.path = filepath
        else:
            self.path = find_xsdir()
        if not self.path:
            self.error = "未找到 xsdir 文件，请手动指定截面库路径"
            self.loaded = False
            return False

        self.zaids = {}
        self.isotopes = {}
        try:
            with open(self.path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("dir"):
                        continue
                    parts = line.split()
                    if not parts:
                        continue
                    zaid = parts[0].lower()
                    if not re.match(r'^\d{4,7}\.\w+$', zaid):
                        continue
                    self.zaids[zaid] = parts
                    # 解析元素/同位素
                    num = zaid.split(".")[0]
                    parsed = parse_zzaaam(num)
                    if parsed:
                        z, a = parsed
                        if z not in self.isotopes:
                            self.isotopes[z] = set()
                        self.isotopes[z].add(a)
        except Exception as e:
            self.error = f"解析 xsdir 失败: {e}"
            self.loaded = False
            return False

        self.loaded = True
        self.error = ""
        return True

    def has_zaid(self, zaid: str) -> bool:
        if not self.loaded:
            return True
        return zaid.lower() in self.zaids

    def get_suggestions(self, prefix: str, max_count: int = 20) -> list[str]:
        if not self.loaded or not prefix:
            return []
        prefix = prefix.lower()
        matches = [z for z in self.zaids if z.startswith(prefix)]
        matches.sort()
        return matches[:max_count]

    def count(self) -> int:
        return len(self.zaids)

    def search_element(self, query: str) -> list[tuple[int, str]]:
        """
        搜索元素。query 可以是：
        - 元素符号 (H, He, U) 不区分大小写
        - 原子序数 (1, 92, 26)
        返回 [(Z, 符号), ...]，精确匹配优先
        """
        if not self.loaded:
            return []
        q = query.strip()
        if not q:
            return []
        exact = []
        prefix = []
        # 数字匹配
        if q.isdigit():
            z = int(q)
            if z in self.isotopes:
                exact.append((z, Z_TO_SYMBOL.get(z, "?")))
        # 符号匹配（不区分大小写）
        q_lower = q.lower()
        for z, sym in Z_TO_SYMBOL.items():
            if z not in self.isotopes:
                continue
            if sym.lower() == q_lower:
                exact.append((z, sym))
            elif sym.lower().startswith(q_lower):
                prefix.append((z, sym))
        # 精确匹配在前，前缀匹配在后
        seen = set()
        results = []
        for z, sym in exact + prefix:
            if z not in seen:
                seen.add(z)
                results.append((z, sym))
        return results

    def get_isotopes(self, z: int) -> list[int]:
        """获取某元素在数据库中的所有可用质量数"""
        if not self.loaded or z not in self.isotopes:
            return []
        return sorted(self.isotopes[z])

    def get_element_list(self) -> list[tuple[int, str]]:
        """获取数据库中有截面数据的元素列表"""
        if not self.loaded:
            return []
        return [(z, Z_TO_SYMBOL.get(z, "?")) for z in sorted(self.isotopes.keys())]

    def make_zaid(self, z: int, a: int) -> str:
        """生成 ZZZAAA 格式字符串"""
        return format_zzaaam(z, a)


# 全局单例
DB = XsdirDB()
