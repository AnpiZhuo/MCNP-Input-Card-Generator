# -*- coding: utf-8 -*-
"""`P A B C D`（四系数一般平面）的**感度必须在解析链路上活下来**。

## 这个 bug 长什么样（2026-09-24 实测，用户报"3D 预览体积爆炸、形状全变"）

C810 §3-17 给三点平面（`P x1 y1 z1 x2 y2 z2 x3 y3 z3`）定的规则是
**"原点具负感度"**；但四系数形式 `P A B C D` **没有这条规则** —— 平面就是
`Ax+By+Cz-D = 0`，**正侧由用户写下的 A B C D 的符号直接决定**。

GEOUNED 生成的曲面卡里，一般平面全是四系数形式，而且**大量 D < 0**
（实测 118/119/120/121/122 五个平面的 D 分别是 −197.99 / −32.509 / −19.799 /
−19.799 / −197.99）。而 `api_server._surf_classes()` 把 pymcnp 的
`P_0`（四系数）与 `P_1`（三点）**按 keyword 收成一个**，`P_1` 活了下来 ⇒
四系数卡解析失败 ⇒ 落进 `parse_surfaces` 的"系数转三点"兜底
（`_plane_coeff_to_points`）⇒ 交给下游的是**三个点**，而三点要走 C810 的
"原点负感度"规则 ⇒ **D < 0 的那些平面正负侧整体翻转**。

后果：含这些平面的栅元不再被那些面界定，会一直漏到包围盒边界 ——
FreeCAD 忠实渲染出来就是"体积爆炸 / 形状全变"。
实测块 002：实体栅元 21 个交项里有 2 项含包围盒角点，重建体积是块的
**71 倍**；块 000/001（不含斜置平面）偏差 +0.0004% / −0.0000% 完全正常。

## 为什么专门开一个文件

`plane_from_points`（C810 §3-17）**本身没错**，`test_surface_semantics.py`
第 2 组测的就是它，而且测的是**真三点**输入。漏掉的是"四系数卡被当成三点"这一环 ——
所以回归必须钉在**解析链路**上：原始卡文本 → `parse_surfaces` → `_pymcnp_surf_to_dict`
→ (type, params)。只有这一层能同时看见"被认成哪种形式"和"系数有没有留下来"。

## 纪律

按 `conftest.py` 铁律，本文件**不 import** `gui.backend.api_server`
（模块级 pyvista/FreeCAD 探测会污染纯引擎测试）⇒ 照 `test_build_cells_data.py`
范式在**子进程**里 import 并执行，测试只收 JSON。
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
API_DIR = PROJECT_DIR / "gui" / "backend"
APP_DIR = PROJECT_DIR / "app"

# 覆盖三种卡型：
#   · 四系数 + D<0（GEOUNED 的常态，bug 触发点）
#   · 四系数 + D>0（旧链路"碰巧对"，用来防止修完这一头坏那一头）
#   · 真三点（C810 §3-17 规则，必须继续走 P_1 + plane_from_points）
_DECK = """100 P 0 0 1 -3
101 P -0.707 -0.000 -0.707 -197.990
102 P 1 0 0 5
103 P 0.707 0 -0.707 -19.799
104 P 1 0 0 0 1 0 0 0 1
"""

_SNIPPET = '''
import sys, json
sys.path.insert(0, "@API_DIR@")
sys.path.insert(0, "@APP_DIR@")
import api_server
from freecad_preview import _pymcnp_surf_to_dict

deck = sys.stdin.read()
out = {}
for s in api_server.parse_surfaces(deck):
    d = _pymcnp_surf_to_dict(s)
    out[str(d["number"])] = {"type": d["type"], "params": [float(v) for v in d["params"]]}
print(json.dumps(out))
'''


@pytest.fixture(scope="module")
def parsed():
    """子进程里跑生产的解析链路，回收 {曲面号: {type, params}}。"""
    # 用 posix 分隔符：Windows 反斜杠塞进 `-c` 源码里会触发 invalid escape sequence
    snippet = (_SNIPPET.replace("@API_DIR@", API_DIR.as_posix())
                       .replace("@APP_DIR@", APP_DIR.as_posix()))
    proc = subprocess.run([sys.executable, "-c", snippet], input=_DECK,
                          capture_output=True, text=True, timeout=180,
                          cwd=str(PROJECT_DIR))
    if proc.returncode != 0:
        pytest.fail(f"解析子进程失败：{proc.stderr[-1500:]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


# ── 核心回归：四系数形式的**系数必须原样留下来**（= 感度没被重算） ──

@pytest.mark.parametrize("num,coeffs", [
    ("100", [0.0, 0.0, 1.0, -3.0]),                 # 平面 z=-3，正侧 z>-3
    ("101", [-0.707, -0.0, -0.707, -197.990]),      # GEOUNED 实测卡（D<0）
    ("102", [1.0, 0.0, 0.0, 5.0]),                  # 平面 x=5，正侧 x>5（D>0）
    ("103", [0.707, 0.0, -0.707, -19.799]),         # GEOUNED 实测卡（D<0）
])
def test_four_coefficient_plane_keeps_its_coefficients(parsed, num, coeffs):
    """四系数 `P` 卡必须序列化成 `P_0` + 原样系数。

    旧行为：变成 `P_1` + 九个合成点 ⇒ 下游按 C810 "原点负感度"重算法向 ⇒
    **D<0 的卡正负侧翻转**（用户症状：体积爆炸）。
    """
    got = parsed[num]
    assert got["type"] == "P_0", (
        f"曲面 {num} 是四系数 P 卡，却被认成 {got['type']} —— "
        f"系数在解析链路里丢了，下游只能靠三点重算感度（D<0 会翻转）")
    assert got["params"] == pytest.approx(coeffs, abs=1e-9)


# ── 语义判据：正侧必须仍然是卡上写的那个方向 ──

@pytest.mark.parametrize("num,inside,outside", [
    ("100", (0, 0, 0), (0, 0, -10)),      # z=-3：+z 侧为正
    ("102", (9, 0, 0), (1, 0, 0)),        # x=5 ：+x 侧为正
])
def test_four_coefficient_plane_sense_is_preserved(parsed, num, inside, outside):
    """把 (type, params) 丢给体素/解析场函数，正侧必须与卡面一致。

    这条不看"序列化成什么"，只看**几何结论**——就算将来换一种表示，
    只要感度是对的它就绿。
    """
    from app.voxel_csg import surface_fn
    f = surface_fn(parsed[num]["type"], parsed[num]["params"])
    v_in = float(f(*inside))
    v_out = float(f(*outside))
    assert v_in > 0, f"曲面 {num}：卡上 {inside} 应在**正**侧，实得 f={v_in}"
    assert v_out < 0, f"曲面 {num}：卡上 {outside} 应在**负**侧，实得 f={v_out}"


# ── 反向保护：真三点卡必须继续走 P_1 + C810 三点感度规则 ──

def test_genuine_three_point_card_still_parses_as_p1(parsed):
    """三点形式不能被"修四系数"顺手改坏（C810 §3-17 的规则只对它适用）。"""
    got = parsed["104"]
    assert got["type"] == "P_1"
    assert len(got["params"]) == 9


def test_genuine_three_point_card_keeps_origin_negative_rule(parsed):
    """卡 `P 1 0 0 0 1 0 0 0 1` = 平面 x+y+z=1。

    过原点那条规则管的是**过原点的平面**；这张卡不过原点，但同一条规则同样要求
    **原点具负感度** ⇒ f(0,0,0) < 0、f 指向 (1,1,1) 一侧为正 ⇒ (0,0,2) 为正。
    """
    from app.voxel_csg import surface_fn
    f = surface_fn(parsed["104"]["type"], parsed["104"]["params"])
    assert float(f(0, 0, 0)) < 0, "原点必须具负感度（C810 §3-17）"
    assert float(f(0, 0, 2)) > 0, "平面 x+y+z=1 的 (0,0,2) 侧应为正"


# ── 所有四系数卡都不能退化成三点 ──

def test_no_four_coefficient_card_degrades_to_three_points(parsed):
    """一眼扫全部：任何 `P_0` 都不该长出 9 个参数（那是三点形式的形状）。"""
    bad = {n: v for n, v in parsed.items()
           if v["type"] == "P_1" and len(v["params"]) != 9}
    assert not bad, f"形状与类型不匹配：{bad}"
    p0 = [n for n, v in parsed.items() if v["type"] == "P_0"]
    assert sorted(p0) == ["100", "101", "102", "103"], (
        f"四系数卡应全部落到 P_0，实得 {sorted(p0)}")
