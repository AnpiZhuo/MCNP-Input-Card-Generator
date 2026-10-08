"""CAD ↔ MCNP 的「上轴 / 方位」约定 —— 显式、可逆、可测（纯 stdlib，无 FreeCAD 依赖）。

## 为什么要这个东西（2026-10-08 用户实测）
用户报「STEP 文件坐标和我们用的数学坐标不一样 → 数字对得上，但模型躺倒、轴跟预览不一致」。
实测（对正在跑的后端导出一个已知盒子）：
  · 导出 MCNP→STEP：`(x,y,z)` **原样**（只 ×10 换成 mm），没有换轴；
  · 导入 STEP→MCNP：`geouned_worker` 把 STEP **原样**交给 GEOUNED，设置表里也没有换轴项。
于是整条链是 1:1 直传，而本程序（与 MCNP）是 **Z 朝上**、SolidWorks/Inventor 类 CAD 是
**Y 朝上** ⇒ 在他们那边看就是躺倒 90°。

## 关键事实（决定了做法）
**STEP 文件本身没有"上轴"字段**（ISO 10303 只有坐标值 + 单位 + 放置坐标系），差别来自
**源软件自己的默认全局坐标系**：Z 朝上 —— FreeCAD / AutoCAD / UG(NX) / CATIA / Creo /
Solid Edge / 3ds Max；Y 朝上 —— SolidWorks / Inventor / Maya / Unity。
（Blender 自身是 Z 朝上，但它的 glTF/FBX 导出默认转成 Y 朝上。）
所以**无法自动判断**来件是哪种，只能由使用者显式指定；而 glTF/OBJ 那种"导出时选上轴"的
开关，STEP 通常不提供 ⇒ 由本程序在导入/导出两侧自己做，且**必须互为逆**。

## 约定（单一来源，导入导出共用本模块）
    cad_orientation = {"up": "Z" | "Y", "azimuthDeg": 0 | 90 | 180 | 270}

* **导入 CAD→MCNP**：先把 CAD 的上轴搬到 `+Z`，再绕 `+Z` 转 `+azimuthDeg`；
* **导出 MCNP→CAD**：逆变换 —— 先绕 `+Z` 转 `-azimuthDeg`，再把 `+Z` 搬回 CAD 的上轴。
两者互为逆 ⇒ 导出再导入回到原坐标（`matrix_mcnp_to_cad @ matrix_cad_to_mcnp == I`）。

`up="Y"` 的那一步就是绕 X 转 +90°：`(x, y, z) → (x, −z, y)`（CAD 的 +Y 变成 MCNP 的 +Z，
CAD 的 +Z 变成 MCNP 的 −Y）。
"""

from __future__ import annotations

_UPS = ("Z", "Y")
_AZIMUTHS = (0, 90, 180, 270)

#: 默认 = 现状（不旋转），保证既有行为逐字节不变
DEFAULT = {"up": "Z", "azimuthDeg": 0}

#: 原点口径（用户 2026-10-08 指定：体心 / 坐在底面 / 按原本建模）
#:   keep   —— 按原本建模（不平移；CAD 坐标 = MCNP 坐标，逐字对应）
#:   center —— 包围盒**体心**落到原点
#:   bottom —— 包围盒**底心**落到原点（即"坐在底面上"：水平居中、上轴方向从 0 起）
ORIGINS = ("keep", "center", "bottom")
DEFAULT_ORIGIN = "keep"


def parse(spec) -> dict:
    """容忍一切输入的规范化：None / 字符串 "Y" / 缺键 / 非法值 → 永远返回合法 dict。

    非法值一律退回默认（不抛），理由：这是**几何方向**开关，宁可保守不转，
    也不要因为一个手写值把整个导入/导出搞崩。
    """
    up, az = DEFAULT["up"], DEFAULT["azimuthDeg"]
    if isinstance(spec, str):
        s = spec.strip().upper()
        if s in _UPS:
            up = s
    elif isinstance(spec, dict):
        raw_up = str(spec.get("up", "") or "").strip().upper()
        if raw_up in _UPS:
            up = raw_up
        raw_az = spec.get("azimuthDeg", spec.get("azimuth", None))
        if raw_az is not None and raw_az != "":
            try:
                az_i = int(round(float(raw_az))) % 360
            except (TypeError, ValueError):
                az_i = DEFAULT["azimuthDeg"]
            if az_i in _AZIMUTHS:
                az = az_i
    return {"up": up, "azimuthDeg": az, "origin": parse_origin(spec)}


def parse_origin(spec) -> str:
    """规范化「原点口径」：keep（按原本建模）/ center（体心）/ bottom（坐在底面）。"""
    raw = None
    if isinstance(spec, dict):
        raw = spec.get("origin", spec.get("originRule", None))
    elif isinstance(spec, str) and spec.strip().lower() in ORIGINS:
        raw = spec
    s = str(raw or "").strip().lower()
    return s if s in ORIGINS else DEFAULT_ORIGIN


def translation_for(bbox, origin: str, up_axis: str = "Z") -> tuple:
    """由包围盒算平移量：``bbox = (min3, max3)``，返回 ``(dx, dy, dz)`` 交给几何做平移。

    * ``keep``   → ``(0,0,0)``（不平移）
    * ``center`` → 体心搬到原点
    * ``bottom`` → **底心**搬到原点：水平两轴居中，**上轴方向从 0 起**。
      "上轴"取**目标坐标系**的（导入 = MCNP 的 Z；导出 = 目标 CAD 的上轴，
      所以 Y 朝上的 CAD 是"坐在 Y=0 平面"上）—— 这才是"放在底面上"的直觉。
    """
    lo, hi = bbox
    cx = (float(lo[0]) + float(hi[0])) / 2.0
    cy = (float(lo[1]) + float(hi[1])) / 2.0
    cz = (float(lo[2]) + float(hi[2])) / 2.0
    o = str(origin or DEFAULT_ORIGIN).strip().lower()
    if o == "center":
        return (-cx, -cy, -cz)
    if o == "bottom":
        if str(up_axis).upper() == "Y":       # 目标 CAD 上轴 = Y ⇒ 坐在 Y=0 上
            return (-cx, -float(lo[1]), -cz)
        return (-cx, -cy, -float(lo[2]))      # 默认 Z 朝上 ⇒ 坐在 Z=0 上
    return (0.0, 0.0, 0.0)


def is_identity(spec) -> bool:
    """是否等价于"不旋转"（= 与旧行为一致）。"""
    p = parse(spec)
    return p["up"] == "Z" and p["azimuthDeg"] == 0


def _matmul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
                 for i in range(3))


def _rot_x(deg: int):
    c = int(round(cos_deg(deg))); s = int(round(sin_deg(deg)))
    return ((1, 0, 0), (0, c, -s), (0, s, c))


def _rot_z(deg: int):
    c = int(round(cos_deg(deg))); s = int(round(sin_deg(deg)))
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))


def cos_deg(deg: float) -> float:
    import math
    return math.cos(math.radians(deg))


def sin_deg(deg: float) -> float:
    import math
    return math.sin(math.radians(deg))


def matrix_cad_to_mcnp(spec) -> tuple:
    """`p_mcnp = M @ p_cad` 的 3×3 整数矩阵（旋转，行列式为 +1，不改手性）。"""
    p = parse(spec)
    m = _rot_x(90) if p["up"] == "Y" else ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    if p["azimuthDeg"]:
        m = _matmul(_rot_z(p["azimuthDeg"]), m)
    return m


def matrix_mcnp_to_cad(spec) -> tuple:
    """逆变换：正交矩阵的逆 = 转置。"""
    m = matrix_cad_to_mcnp(spec)
    return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))


def freecad_steps(spec, direction: str) -> list:
    """FreeCAD 里依次施加的旋转：``[(axis3, degrees), ...]``（就地 `shape.rotate`）。

    direction：``"cad2mcnp"``（导入时用）/ ``"mcnp2cad"``（导出时用）。
    不合并成单次轴角：两步顺序明确、与上面的矩阵推导一一对应，便于核对。
    """
    p = parse(spec)
    up, az = p["up"], p["azimuthDeg"]
    x_deg = 90 if up == "Y" else 0
    if direction == "cad2mcnp":
        steps = []
        if x_deg:
            steps.append(((1.0, 0.0, 0.0), float(x_deg)))
        if az:
            steps.append(((0.0, 0.0, 1.0), float(az)))
        return steps
    if direction == "mcnp2cad":
        steps = []
        if az:
            steps.append(((0.0, 0.0, 1.0), float(-az)))
        if x_deg:
            steps.append(((1.0, 0.0, 0.0), float(-x_deg)))
        return steps
    raise ValueError(f"direction 只能是 cad2mcnp / mcnp2cad，收到 {direction!r}")


def translation_for_spec(bbox, spec) -> tuple:
    """按约定里的「原点口径」算平移量 —— 上轴取**目标坐标系**的（导出即目标 CAD 的上轴）。

    导入侧要的是 MCNP 系（Z），所以那里直接用 ``translation_for(bbox, origin, "Z")``：
    ``up="Y"`` 时 CAD 的 Y=0 平面经旋转后正好是 MCNP 的 Z=0 平面，两种说法一致。
    """
    p = parse(spec)
    return translation_for(bbox, p["origin"], p["up"])


def describe(spec, direction: str) -> str:
    """给界面/结果提示用的中文说明（要让用户看得出"这份几何按哪种约定转过/平移过"）。"""
    p = parse(spec)
    up_txt = {"Z": "Z 朝上（FreeCAD/UG/CATIA 类）",
              "Y": "Y 朝上（SolidWorks/Inventor 类）"}[p["up"]]
    org_txt = {"keep": "", "center": "、体心归零", "bottom": "、坐在底面上"}[p["origin"]]
    if is_identity(p) and p["origin"] == DEFAULT_ORIGIN:
        return f"上轴 {up_txt}、方位角 0°、原点 {p['origin']}（按原本建模）：与 MCNP 坐标一致，未旋转未平移"
    who = "导入" if direction == "cad2mcnp" else "导出"
    return (f"已按 {who}约定处理：上轴 {up_txt}"
            + (f"、绕上轴 {p['azimuthDeg']}°" if p["azimuthDeg"] else "")
            + (org_txt or "、不平移"))


__all__ = ["DEFAULT", "DEFAULT_ORIGIN", "ORIGINS", "parse", "parse_origin", "is_identity",
           "translation_for", "matrix_cad_to_mcnp", "matrix_mcnp_to_cad",
           "freecad_steps", "describe"]
