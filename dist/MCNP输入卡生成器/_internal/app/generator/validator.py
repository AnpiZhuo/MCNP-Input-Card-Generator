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

        # 拆分 $ 注释
        before_dollar = stripped
        if '$' in stripped:
            before_dollar = stripped.split('$')[0].strip()
            if not before_dollar:
                continue  # 整行只有注释

        # 数据部分不能有中文
        if re.search(r'[一-鿿]', before_dollar):
            errors.append(
                f"几何：曲面卡第 {line_num} 行的数据部分含有中文字符"
            )

        # 格式检查：曲面号 [TRn] 类型 参数…
        parts = before_dollar.split()
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
            pass  # parts[1] 就是类型
        elif len(parts) >= 3 and parts[2].upper() in _SURFACE_TYPES:
            pass  # parts[1] 是 TRn，parts[2] 是类型
        elif len(parts) >= 2:
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

    return errors


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
        for cell in cells:
            if not cell.surface_expr.strip():
                errors.append(f"几何：栅元 {cell.number} 的曲面表达式不能为空")
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
                for row in mat.rows:
                    if not row.zaid.strip() or not row.fraction.strip():
                        errors.append(f"材料 M{mat.number}：ZAID 和份额不能为空")

    # ----- SDEF / KCODE -----
    if adv and adv.source_mode == "distribution":
        # 分布源模式：不校验 sources，而是校验分布源文本
        if not adv.sdef_raw_text.strip():
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


def validate_deck(deck: DeckData) -> list[str]:
    """从 DeckData 聚合对象校验必填项。"""
    return validate_all(
        basic=deck.basic,
        surfaces=deck.surfaces,
        cells=deck.cells,
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
