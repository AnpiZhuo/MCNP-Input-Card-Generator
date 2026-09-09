"""
校验器：检查所有必填项，返回错误列表
"""

import re
from app.models import BasicSettings, CellData, MaterialData, SourceData, DeckData, TallySettings, AdvancedSettings


# ===== 曲面类型关键字（不区分大小写）=====
_SURFACE_TYPES = {
    'P', 'PX', 'PY', 'PZ',
    'SO', 'S', 'SX', 'SY', 'SZ',
    'CX', 'CY', 'CZ', 'C/X', 'C/Y', 'C/Z',
    'KX', 'KY', 'KZ', 'K/X', 'K/Y', 'K/Z',
    'SQ', 'GQ',
    'TX', 'TY', 'TZ',
    'X', 'Y', 'Z',
    'BOX', 'RPP', 'SPH', 'RCC', 'RHP', 'HEX',
    'REC', 'TRC', 'ELL', 'WED', 'ARB',
}

# 宏体类型 → (最小参数个数, 别名说明)
# 对照 OWEN rules.ts `mcnp.macrobody` 参数范围检查；RHP/HEX 支持 9/12/15/18 四种长度。
_MACROBODY_PARAM_MIN = {
    "RPP": (6,             "xmin xmax ymin ymax zmin zmax"),
    "SPH": (4,             "x y z r"),
    "RCC": (7,             "x y z hx hy hz r"),
    "RHP": (9,             "vx vy vz hx hy hz r1 [r2 [r3]]（可选 r2/r3 使总数 9/12/15/18）"),
    "HEX": (9,             "vx vy vz hx hy hz r1 [r2 [r3]]（可选 r2/r3 使总数 9/12/15/18）"),
    "TRC": (8,             "x y z hx hy hz r1 r2"),
    "REC": (12,            "x y z hx hy hz v1x v1y v1z v2x v2y v2z"),
    "ELL": (7,             "v1x v1y v1z v2x v2y v2z rm"),
    "WED": (12,            "x y z v1x v1y v1z v2x v2y v2z v3x v3y v3z"),
    "BOX": (9,             "x y z a1x a1y a1z a2x a2y a2z [a3x a3y a3z]（9 或 12 参）"),
    "ARB": (30,            "A-H 顶点(24) + n1..n6(6)"),
}

# 行长度限制（OWEN mcnp.line-length）
_COL_WARN = 80            # 超过此值发出警告
_COL_ERROR = 128          # 超过此值报错


# ===== 材料级规则（交叉核对 OWEN src/language/rules.ts validateMCNP）=====
_ZAID_RE = re.compile(r"^\d{4,6}(?:\.\d{2,}[a-zA-Z])?$")

# S(α,β) 表前缀 → 必需的目标元素 Z（rules.ts SAB_TARGETS 映射的精简版）
_SAB_Z_REQUIRED = {
    "lwtr": 1, "hwtr": 1, "benz": 1, "poly": 1, "zrh": 1, "h": 1,      # 氢基
    "grph": 6,                                                          # 石墨
    "be": 4, "beo": 4,                                                  # 铍
    "o": 8, "o2": 8, "ou": 8,                                          # 氧
    "b": 5, "b4c": 5, "b4c2": 5,                                       # 硼
    "zr": 40,                                                           # 锆
    "al": 13,                                                           # 铝
    "fe": 26, "fe56": 26,                                               # 铁
    "u": 92, "uo2": 92,                                                 # 铀
}


def _zaid_z(zaid: str) -> int | None:
    """从 ZAID（ZZZAAA 或 ZZZAAA.NNx）提取 Z（原子序数）；非法返回 None。"""
    num = zaid.split(".")[0]
    if not num.isdigit():
        return None
    n = len(num)
    if n == 4:
        return int(num[0])
    if n == 5:
        return int(num[:2])
    if n == 6:
        return int(num[:3])
    return None


def _check_sab_target(mat: MaterialData) -> str | None:
    """S(α,β) 卡（mt_card）目标核素检查：表要求的元素必须在材料核素中。

    对齐 OWEN rules.ts `mcnp.sab-no-target`：表目标核素不在材料里时，
    该表会被 MCNP 忽略。
    """
    mt = (mat.mt_card or "").strip()
    if not mt:
        return None
    present_z = set()
    for row in mat.rows:
        if row.kind == "nuclide" and row.zaid.strip():
            z = _zaid_z(row.zaid.strip())
            if z is not None:
                present_z.add(z)
    for tok in mt.split():
        sab = tok.lower().split(".")[0]
        sab = re.sub(r"\d+$", "", sab)
        z_req = _SAB_Z_REQUIRED.get(sab)
        if z_req is not None and z_req not in present_z:
            return (
                f"材料 M{mat.number}：S(α,β) 表 {tok} 需要 Z={z_req} "
                "核素，但材料中不存在（MCNP 会忽略该表）"
            )
    return None


def _check_surfaces_text(surfaces: str) -> list[str]:
    """
    逐行校验曲面卡文本。允许中文出现在 C 注释行和 $ 注释部分。
    返回当前文本的错误列表（仅为「警告」性质，不影响生成）。
    """
    errors = []
    lines = surfaces.split('\n')
    for line_num, raw_line in enumerate(lines, 1):
        stripped = raw_line.strip()
        if not stripped:
            continue

        # C 注释行允许任何内容（包括中文）
        if stripped.startswith('C ') or stripped.startswith('c '):
            continue

        # 拆分 $ 注释（保留原始前导空格以正确统计 MCNP 列号）
        before_dollar_raw = raw_line.split('$')[0].rstrip()
        if not before_dollar_raw.strip():
            continue  # 整行只有注释/空白
        stripped = before_dollar_raw.strip()
        if not stripped:
            continue

        # C 注释行允许任何内容（包括中文）
        if stripped.startswith('C ') or stripped.startswith('c '):
            continue

        # 行长度限制（OWEN mcnp.line-length）：MCNP 数据区为 1–80 列（续行 81–128 列），
        # 超出 128 列的部分被截断丢弃。按原始行的 1–128 列计数。
        n_cols = len(before_dollar_raw)
        if n_cols > _COL_ERROR:
            errors.append(
                f"几何：曲面卡第 {line_num} 行 {n_cols} 列超过 {_COL_ERROR} 列"
                "（MCNP 读取到第 128 列即截断，后续参数会丢失）"
            )
        elif n_cols > _COL_WARN:
            errors.append(
                f"几何：曲面卡第 {line_num} 行 {n_cols} 列超过 {_COL_WARN} 列"
                "（建议拆到续行）"
            )

        # 数据部分不能有中文
        if re.search(r'[一-鿿]', stripped):
            errors.append(
                f"几何：曲面卡第 {line_num} 行的数据部分含有中文字符"
            )

        # 格式检查：曲面号 [TRn] 类型 参数…
        parts = stripped.split()
        if len(parts) < 2:
            errors.append(f"几何：曲面卡第 {line_num} 行格式不完整（至少需要曲面号和类型）")
            continue

        # 第一项应为曲面号
        if not parts[0].lstrip('-+').isdigit():
            errors.append(
                f"几何：曲面卡第 {line_num} 行应以数字开头（曲面号），"
                f"当前第一项为 '{parts[0]}'"
            )
            continue

        # 判断类型关键字在第2还是第3个位置（第2个可能是 TRn 号）
        if parts[1].upper() in _SURFACE_TYPES:
            type_idx = 1
        elif len(parts) >= 3 and parts[2].upper() in _SURFACE_TYPES:
            type_idx = 2
        else:
            # 非已知类型——可能是宏体或拼写错误
            if not parts[1].replace('-', '').replace('.', '').isdigit():
                errors.append(
                    f"几何：曲面卡第 {line_num} 行的类型 '{parts[1]}' 不是"
                    f"已知的曲面类型"
                )
            elif len(parts) < 3:
                errors.append(
                    f"几何：曲面卡第 {line_num} 行似乎缺少曲面类型关键字"
                )
            else:
                errors.append(
                    f"几何：曲面卡第 {line_num} 行的类型 '{parts[2]}' 不是"
                    f"已知的曲面类型"
                )
            continue

        # 宏体参数个数检查（OWEN mcnp.macrobody）：type_idx 之后的数值 token 计数
        kw = parts[type_idx].upper()
        spec = _MACROBODY_PARAM_MIN.get(kw)
        if spec is not None:
            min_params, expected_desc = spec
            rest = parts[type_idx + 1:]
            # 只统计数值 token（*TRn 等非数值属于行列外层信息，不计入曲面参数）
            n_params = sum(
                1 for tok in rest
                if tok.lstrip('-+').replace('.', '', 1).replace('e', '', 1).replace('E', '', 1).isdigit()
            )
            if kw in ("RHP", "HEX"):
                if n_params not in (9, 12, 15, 18):
                    errors.append(
                        f"几何：曲面卡第 {line_num} 行的 {kw} 宏体参数个数为 {n_params}，"
                        f"应为 9/12/15/18（{expected_desc}）"
                    )
            elif kw in ("BOX",) and n_params in (9, 12):
                pass  # BOX 允许 9 或 12 参（省略 a3 = 正交补全）
            elif n_params != min_params:
                errors.append(
                    f"几何：曲面卡第 {line_num} 行的 {kw} 宏体参数个数为 {n_params}，"
                    f"应为 {min_params}（{expected_desc}）"
                )

    return errors


def _collect_surface_numbers(surfaces_text: str) -> set[int]:
    """从曲面卡文本收集已定义的曲面号集合（用于未定义引用检查）。"""
    nums = set()
    for line in surfaces_text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("C ") or stripped.startswith("c "):
            continue
        if "$" in stripped:
            stripped = stripped.split("$")[0].strip()
            if not stripped:
                continue
        parts = stripped.split()
        if not parts:
            continue
        first = parts[0].lstrip("-+")
        if first.isdigit():
            nums.add(int(first))
    return nums


def validate_all(
    basic: BasicSettings,
    surfaces: str,
    cells: list[CellData],
    materials: list[MaterialData],
    sources: list[SourceData],
    tally: TallySettings | None = None,
    adv: AdvancedSettings | None = None,
) -> list[str]:
    """
    校验所有模块的必填项。
    返回错误信息列表，为空表示全部通过。
    """
    if tally is None:
        tally = TallySettings()
    errors = []

    # ----- 基本设置 -----
    if not basic.title:
        errors.append("基本设置：请填写标题卡")

    if not (basic.mode_n or basic.mode_p or basic.mode_e or
            basic.mode_h or basic.mode_he):
        errors.append("基本设置：请至少选择一种粒子类型（MODE）")

    if not basic.nps:
        errors.append("基本设置：请填写 NPS 粒子数")
    else:
        try:
            nps_val = int(float(basic.nps))
            if nps_val <= 0:
                errors.append("基本设置：NPS 必须大于 0")
        except ValueError:
            errors.append("基本设置：NPS 数字格式不正确")

    # ----- 曲面卡 -----
    if not surfaces:
        errors.append("几何：请至少定义一个曲面")
    else:
        errors.extend(_check_surfaces_text(surfaces))

    # ----- 栅元卡 -----
    if not cells:
        errors.append("几何：请至少定义一个栅元")
    else:
        # 先收集已定义曲面号（用于未定义引用检查）
        defined_surfaces = _collect_surface_numbers(surfaces) if surfaces else set()
        for cell in cells:
            if not cell.surface_expr.strip():
                errors.append(f"几何：栅元 {cell.number} 的曲面表达式不能为空")
                continue
            # 未定义曲面引用检查：提取表达式中的所有数字（曲面号）检查是否已定义
            if defined_surfaces:
                expr = cell.surface_expr.strip()
                for token in re.findall(r"\b\d+\b", expr):
                    ref_num = int(token)
                    if ref_num not in defined_surfaces:
                        errors.append(
                            f"几何：栅元 {cell.number} 引用了未定义的曲面 {ref_num}"
                        )
            # 非真空栅元必须有密度
            if cell.material.strip() != "0" and "void" not in cell.material.lower():
                if not cell.density.strip():
                    errors.append(f"几何：栅元 {cell.number} 引用了材料 {cell.material}，密度不能为空")
                else:
                    dens = cell.density.strip()
                    if not re.match(r'^[+-]?(?:\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$', dens):
                        errors.append(f"几何：栅元 {cell.number} 的密度格式不正确（应为数字）")

        # 检查栅元号重复
        numbers = [c.number for c in cells]
        if len(numbers) != len(set(numbers)):
            errors.append("几何：存在重复的栅元号")

    # ----- 材料 -----
    if not materials:
        errors.append("材料：请至少定义一个材料")
    else:
        for mat in materials:
            if not mat.rows:
                errors.append(f"材料 M{mat.number}：至少添加一行 ZAID + 份额")
            else:
                signs = set()
                for row in mat.rows:
                    if not row.zaid.strip() or not row.fraction.strip():
                        errors.append(f"材料 M{mat.number}：ZAID 和份额不能为空")
                        continue
                    zaid = row.zaid.strip()
                    frac = row.fraction.strip()
                    if not _ZAID_RE.match(zaid):
                        errors.append(
                            f"材料 M{mat.number}：ZAID '{zaid}' 格式不正确"
                            "（应为 ZZZAAA 或 ZZZAAA.NNx，如 92235.80c）"
                        )
                    try:
                        fv = float(frac)
                        if fv < 0:
                            signs.add("-")
                        elif fv > 0:
                            signs.add("+")
                    except ValueError:
                        errors.append(
                            f"材料 M{mat.number}：份额 '{frac}' 格式不正确（应为数字）"
                        )
                if len(signs) == 2:
                    errors.append(
                        f"材料 M{mat.number}：份额正负号混用"
                        "（正=原子份额，负=质量份额），请保持一致"
                    )
                sab_err = _check_sab_target(mat)
                if sab_err:
                    errors.append(sab_err)

    # ----- SDEF / KCODE -----
    if adv and adv.source_mode == "distribution":
        # 分布源模式：不校验 sources，而是校验分布源文本（v2 结构化 sdef_distributions
        # 为主；sdef_raw_text 为旧数据兜底）
        def _dist_json_has_entries(s: str) -> bool:
            if not s or not s.strip():
                return False
            try:
                import json as _json
                arr = _json.loads(s)
                return isinstance(arr, list) and len(arr) > 0
            except Exception:
                return False
        if not adv.sdef_raw_text.strip() and not _dist_json_has_entries(adv.sdef_distributions):
            errors.append("源项：分布源模式下 SI/SP 内容不能为空")
    elif adv and adv.source_mode == "kcode":
        # KCODE 临界源模式
        if not adv.kcode_nsrc.strip():
            errors.append("源项：KCODE 模式下 NSRC（每代粒子数）不能为空")
        if not adv.kcode_rkk.strip():
            errors.append("源项：KCODE 模式下 RKK（初始 keff）不能为空")
        if not adv.kcode_ikz.strip():
            errors.append("源项：KCODE 模式下 IKZ（非活跃代数）不能为空")
        if not adv.kcode_kct.strip():
            errors.append("源项：KCODE 模式下 KCT（总代数）不能为空")
    else:
        if not sources:
            errors.append("源项：请至少定义一个源")
        else:
            for src in sources:
                if not src.erg.strip():
                    errors.append(f"源 {src.number}：能量（ERG）不能为空")

            # 检查 probability 之和是否为 0
            total_prob = 0.0
            for src in sources:
                try:
                    total_prob += float(src.probability or "0")
                except ValueError:
                    errors.append(f"源 {src.number}：概率格式不正确")
            if total_prob <= 0 and len(sources) > 1:
                errors.append("源项：所有源的概率之和为零，无法抽样")

    # ----- 计数卡 (F1~F8 via TallyDefinition) -----
    for td in tally.tallies:
        if not td.params.strip():
            if td.type == "F5":
                errors.append(f"计数：F{td.number}（点探测器）的坐标参数不能为空")
            elif td.type in ("F1", "F2"):
                errors.append(f"计数：F{td.number}（{td.type}）的曲面号不能为空")
            else:
                errors.append(f"计数：F{td.number}（{td.type}）的栅元号不能为空")

    # 能谱参数检查（仅当填写了能量值时检查）
    if tally.e_min.strip() and tally.e_max.strip():
        try:
            e_min = float(tally.e_min)
            e_max = float(tally.e_max)
            if e_max <= e_min:
                errors.append("计数：能量最大值必须大于最小值")
            if tally.e_bins < 1:
                errors.append("计数：间隔数必须大于 0")
        except ValueError:
            errors.append("计数：能量值格式不正确")

    # ----- 交叉引用校验：栅元→材料、计数→栅元/曲面 -----
    if cells and materials:
        # 收集已定义的材料号（"M1" → 1）
        defined_mats = set()
        for m in materials:
            defined_mats.add(m.number)
        # 检查栅元引用的材料是否已定义
        for cell in cells:
            mat_str = cell.material
            if " " in mat_str:
                mat_str = mat_str.split()[0]
            if mat_str.startswith("M"):
                mat_str = mat_str[1:]
            if mat_str.isdigit() and int(mat_str) > 0:
                if int(mat_str) not in defined_mats:
                    errors.append(f"几何：栅元 {cell.number} 引用的材料 M{mat_str} 未在材料页中定义")

    # 计数卡引用的栅元号检查（遍历 TallyDefinition）
    if cells:
        cell_numbers = {c.number for c in cells}
        for td in tally.tallies:
            if td.type in ("F4", "F6", "F7", "F8") and td.params.strip():
                for cid in td.params.split():
                    if cid.isdigit() and int(cid) not in cell_numbers:
                        errors.append(f"计数：F{td.number} 引用的栅元 {cid} 未定义")

    return errors


def _unwrap_cells(cells):
    """CellRow 判别联合 → 仅保留 kind=='cell' 的 CellData；raw 条件行不参与校验。"""
    return [row.cell for row in cells if getattr(row, "kind", "cell") == "cell"]


def validate_deck(deck: DeckData) -> list[str]:
    """从 DeckData 聚合对象校验必填项。"""
    return validate_all(
        basic=deck.basic,
        surfaces=deck.surfaces,
        cells=_unwrap_cells(deck.cells),
        materials=deck.materials,
        sources=deck.sources,
        tally=deck.tally or TallySettings(),
        adv=deck.adv,
    )


def check_inp_format(inp_path: str) -> list[str]:
    """
    使用 pymcnp.Check 对已生成的 INP 文件做格式级校验。
    返回 diff 行列表（空列表 = 格式正确，无需修正）。
    """
    import pymcnp
    try:
        checker = pymcnp.Check(inp_path)
        diff = checker.check()
        # pymcnp.Check.check() 返回 generator (unified_diff)
        lines = list(diff) if hasattr(diff, '__iter__') else []
        return lines
    except Exception as e:
        return [f"pymcnp.Check 执行失败: {e}"]
