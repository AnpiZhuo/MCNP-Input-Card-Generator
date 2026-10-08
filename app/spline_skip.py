# -*- coding: utf-8 -*-
"""样条曲面：**跳过而不是终止**，并把"跳过了什么、为什么"如实报告。

问题（用户实机遇到的那条路）
============================
GEOUNED 遇到含样条（NURBS）面的实体，默认 `spline_surfaces="stop"` ——
`loadfile/load_step.py:69-71` 直接 `exit()`。worker 那层的 `SystemExit` 兜底只能吐
一句"GEOUNED 终止: None"：用户既不知道**哪个实体**有事、也不知道该怎么办，导入就
这么没了；而 GeoUNED 自己的 `remove` 档在 **enclosure 路径**上仍会强制退出
（`core.py:335-338` 不看档位地对"无形状实体"调 exit）。

本程序的约定（用户指定：遇到样条曲线就跳过，不要终止/暂停）
=========================================================
1. **默认档 = 跳过**（`remove`）：含样条面的实体不参与转换，其余照常转换，导入不中断；
2. **必须报告**：被跳过的实体序号（0 起，与界面「跳过实体编号」同一口径）、曲面类型、
   面数，全部进 `warnings` → 界面 alert；
3. 用户显式选了「停止转换」时才停 —— 而且要停得**具体**（哪个实体、换成哪一档能继续），
   不是一句"GEOUNED 终止: None"；
4. 全部实体都含样条面时（跳过之后就空了）**提前失败并说清原因**，不给一份空卡。

为什么判定不在这里（本模块是纯逻辑，不 import FreeCAD）
=====================================================
"哪些实体含样条面"的**唯一权威**是 GEOUNED 自己的 `load_functions.spline()`：

    isinstance(f.Surface, (Part.BSplineSurface, Part.SurfaceOfRevolution,
                           Part.SurfaceOfExtrusion))

在这里复制一份判据就是自找漂移（将来 GEOUNED 加一类曲面，两处必然不一致）。
所以**读**在 worker（那里才有 FreeCAD），本模块只吃"每个实体的样条面类型名"
这个已经判好的结果，负责其余全部可离线单测的部分：命名、报告文案、
能否继续（`blocking_reason`）、以及物理剔除之后的编号重映射。
"""
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

# 默认档：跳过含样条面的实体（GEOUNED 那三档 stop/remove/ignore 里最不伤人的一档）
DEFAULT_POLICY = "remove"

POLICIES = ("stop", "remove", "ignore")

_POLICY_CN = {
    "stop": "停止转换",
    "remove": "跳过该实体",
    "ignore": "强行翻译",
}

# FreeCAD 的曲面类名 → 中文（只用于文案；判据仍在 worker 的 isinstance 上）
_KIND_CN = {
    "BSplineSurface": "NURBS 曲面",
    "SurfaceOfRevolution": "旋转面",
    "SurfaceOfExtrusion": "拉伸面",
}


def normalize_policy(policy) -> str:
    """任何输入都收敛到三档之一；认不得的一律回默认档（界面/JSON 来的值不抛异常）。"""
    if isinstance(policy, str):
        low = policy.strip().lower()
        if low in POLICIES:
            return low
    return DEFAULT_POLICY


def kind_cn(kind: str) -> str:
    """曲面类名的中文名；没有对应文案就原样返回（不吞信息）。"""
    return _KIND_CN.get(kind, kind)


@dataclass(frozen=True)
class SplineSolid:
    """一个含样条面的实体。`index` 是 **0 起**的实体序号（与 GEOUNED 同一口径）。"""
    index: int
    kinds: tuple           # 该实体上被判为样条的**面**的类型名（可重复）

    @property
    def face_count(self) -> int:
        return len(self.kinds)

    def kinds_cn(self) -> str:
        """去重后的中文类型名，按首次出现顺序（如「NURBS 曲面 / 拉伸面」）。"""
        out = []
        for k in self.kinds:
            cn = kind_cn(k)
            if cn not in out:
                out.append(cn)
        return " / ".join(out)


@dataclass(frozen=True)
class SplineReport:
    """一次扫描的结果（空 `solids` = 没有样条实体，一切照旧）。"""
    solids: tuple
    total_solids: int

    @property
    def indices(self) -> tuple:
        return tuple(s.index for s in self.solids)

    @property
    def face_count(self) -> int:
        return sum(s.face_count for s in self.solids)

    @property
    def is_total_loss(self) -> bool:
        """**全部**实体都含样条面 ⇒ 跳过之后没有可转换的实体。"""
        return bool(self.solids) and len(self.solids) >= self.total_solids

    def indices_cn(self) -> str:
        return "、".join(str(i) for i in self.indices)

    def kinds_cn(self) -> str:
        out = []
        for s in self.solids:
            for k in s.kinds:
                cn = kind_cn(k)
                if cn not in out:
                    out.append(cn)
        return " / ".join(out)

    def headline(self) -> str:
        """所有文案共用的一句事实（不含任何处置建议）。"""
        return (f"样条曲面：实体 {self.indices_cn()} 共 {len(self.solids)} 个含样条类曲面"
                f"（{self.kinds_cn()}，{self.face_count} 个面）")


def scan(kinds_per_solid: Optional[Sequence[Sequence[str]]]) -> Optional[SplineReport]:
    """把"每个实体的样条面类型名"转成报告；`None`（读不出来）原样返回 `None`。

    输入形状：`[[第一实体的样条面类型名...], [第二实体...], ...]`，空列表 = 该实体干净。
    """
    if kinds_per_solid is None:
        return None
    rows = list(kinds_per_solid)
    solids = tuple(SplineSolid(i, tuple(row)) for i, row in enumerate(rows) if row)
    return SplineReport(solids=solids, total_solids=len(rows))


def blocking_reason(report: Optional[SplineReport], policy) -> Optional[str]:
    """不能继续的原因（可直接给用户看的中文）；能继续返回 `None`。

    两种"不能继续"：
      · 用户显式选了「停止转换」（GEOUNED 自己的默认档）—— 告诉他换哪一档就能继续；
      · 全部实体都含样条面 ⇒ 跳过之后一个实体都不剩 —— 跳过这条路本身走不通。
    """
    if report is None or not report.solids:
        return None
    pol = normalize_policy(policy)
    if pol == "stop":
        return (f"{report.headline()}。当前「样条曲面处理」设为「{_POLICY_CN['stop']}」，"
                f"导入已终止 —— 把它改成「{_POLICY_CN['remove']}」即可继续："
                f"这 {len(report.solids)} 个实体不参与转换，其余实体照常转换。")
    if pol == "remove" and report.is_total_loss:
        return (f"{report.headline()} —— STEP 里 {report.total_solids} 个实体**全部**含样条类曲面，"
                f"跳过它们之后没有可转换的实体。请在 CAD 里把这些面换成解析曲面"
                f"（平面 / 圆柱 / 球 / 圆锥 / 圆环）后重新导出 STEP；"
                f"或把「样条曲面处理」设为「{_POLICY_CN['ignore']}」试着强转一次"
                f"（结果可能有误，事后务必核对体积与重叠）。")
    return None


def describe(report: Optional[SplineReport], policy) -> list:
    """给界面的提示列表（中文）。没有样条实体（或读不出来）时返回空列表 —— 不刷屏。"""
    if report is None or not report.solids:
        return []
    pol = normalize_policy(policy)
    if pol == "remove":
        return [f"{report.headline()}，已跳过这 {len(report.solids)} 个实体、其余照常转换"
                f" —— GEOUNED 无法把样条面写成 MCNP 曲面。"]
    if pol == "ignore":
        return [f"{report.headline()}，已按「{_POLICY_CN['ignore']}」处理：GEOUNED 会把样条面"
                f"一并翻译，几何可能有误 —— 请核对栅元体积与重叠。"]
    # stop 档在 blocking_reason 里已经报告并终止，这里不该再走到
    return []


def remap_skip_solids(skip_solids: Iterable, removed: Iterable) -> tuple:
    """物理剔除实体之后，把用户的「跳过实体编号」重映射到**新**编号。

    返回 `(新编号列表, 因为已被剔除而不再需要的编号列表)`。
    两条纪律：
      · 用户给的编号是**原文件**口径（GEOUNED 的 `skip_solids` 本来就是这个口径）；
      · 被剔除的实体本身已经是"不转换"，用户若也把它列进跳过表，只是多余 —— 丢掉并上报，
        不能让序号错位（错位 = 默默跳过另一个实体）。
    """
    drop = sorted({int(i) for i in removed})
    drop_set = set(drop)
    mapped, redundant = set(), set()
    for raw in skip_solids or ():
        idx = int(raw)
        if idx in drop_set:
            redundant.add(idx)
            continue
        mapped.add(idx - sum(1 for d in drop if d < idx))
    return sorted(mapped), sorted(redundant)
