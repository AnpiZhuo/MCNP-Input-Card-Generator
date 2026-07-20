"""
FreeCAD OCC Python: 读取 STEP 文件 → 生成标准 MCNP 曲面卡（无 GQ）
由 step_importer.py 调用。
"""

import sys
import json
import math

# FreeCAD 路径
FREECAD_BIN = r"D:\FreeCAD\FreeCAD_1.1.1-Windows-x86_64-py311\bin"
sys.path.append(FREECAD_BIN)
sys.path.append(r"D:\FreeCAD\FreeCAD_1.1.1-Windows-x86_64-py311\lib")

import FreeCAD
import Part

import OCC.Core.STEPControl
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import (
    GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone,
    GeomAbs_Sphere, GeomAbs_Torus,
)
from OCC.Core.gp import gp_Pnt, gp_Vec
from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
from OCC.Core.GeomLProp import GeomLProp_SLProps
from OCC.Core.TopAbs import TopAbs_IN, TopAbs_OUT


def get_surface_info(adaptor, st):
    """Returns (mcnp_type, axis_info, params_tuple)."""
    if st == GeomAbs_Plane:
        pln = adaptor.Plane()
        loc = pln.Location()
        n = pln.Axis().Direction()
        D = -(n.X()*loc.X() + n.Y()*loc.Y() + n.Z()*loc.Z())
        ax = abs(n.X()); ay = abs(n.Y()); az = abs(n.Z())
        if ax > 0.9999: mt = "PX"
        elif ay > 0.9999: mt = "PY"
        elif az > 0.9999: mt = "PZ"
        else: mt = "P"
        return mt, n, (n.X(), n.Y(), n.Z(), D)

    elif st == GeomAbs_Cylinder:
        cyl = adaptor.Cylinder()
        loc = cyl.Location()
        axis = cyl.Axis().Direction()
        r = cyl.Radius()
        ax = abs(axis.X()); ay = abs(axis.Y()); az = abs(axis.Z())
        if ax > 0.9999: mt = "C/X"
        elif ay > 0.9999: mt = "C/Y"
        elif az > 0.9999: mt = "C/Z"
        else: mt = "C"
        return mt, axis, (loc, axis, r)

    elif st == GeomAbs_Cone:
        cn = adaptor.Cone()
        loc = cn.Location()
        axis = cn.Axis().Direction()
        sa = cn.SemiAngle()
        ax = abs(axis.X()); ay = abs(axis.Y()); az = abs(axis.Z())
        if ax > 0.9999: mt = "K/X"
        elif ay > 0.9999: mt = "K/Y"
        elif az > 0.9999: mt = "K/Z"
        else: mt = "K"
        return mt, axis, (loc, axis, sa)

    elif st == GeomAbs_Sphere:
        sp = adaptor.Sphere()
        loc = sp.Location()
        r = sp.Radius()
        mt = "SO" if (abs(loc.X())<1e-10 and abs(loc.Y())<1e-10 and abs(loc.Z())<1e-10) else "S"
        return mt, loc, (loc, r)

    elif st == GeomAbs_Torus:
        tr = adaptor.Torus()
        loc = tr.Location()
        axis = tr.Axis().Direction()
        maj = tr.MajorRadius()
        mini = tr.MinorRadius()
        ax = abs(axis.X()); ay = abs(axis.Y()); az = abs(axis.Z())
        if ax > 0.9999: mt = "TX"
        elif ay > 0.9999: mt = "TY"
        elif az > 0.9999: mt = "TZ"
        else: mt = "T"
        return mt, axis, (loc, axis, maj, mini)

    return "GQ", None, ()


def _orthogonal_basis(d):
    """给定方向 d，返回三个正交基向量 (v, w, u)，其中 u = d。"""
    dx, dy, dz = d.X(), d.Y(), d.Z()
    # 选参考向量（不与 d 平行）
    if abs(dx) < 0.9:
        ref = gp_Vec(1, 0, 0)
    elif abs(dy) < 0.9:
        ref = gp_Vec(0, 1, 0)
    else:
        ref = gp_Vec(0, 0, 1)
    v = ref.Crossed(gp_Vec(dx, dy, dz))
    v.Normalize()
    w = gp_Vec(dx, dy, dz).Crossed(v)
    w.Normalize()
    u = gp_Vec(dx, dy, dz)
    return v, w, u


def format_surf(num, mt, params, tr_num=0):
    """格式化成 MCNP 曲面卡。非轴对齐圆柱用 TRn + C/X/C/Y/C/Z。

    Returns:
        (card_text_or_None, tr_card_or_None)
    """
    s = f"{num:5d}"
    if tr_num:
        s += f" {tr_num}"

    if mt == "PX":   return (f"{s}    PX     {params[3]:.7f}", None)
    if mt == "PY":   return (f"{s}    PY     {params[3]:.7f}", None)
    if mt == "PZ":   return (f"{s}    PZ     {params[3]:.7f}", None)
    if mt == "P":    return (f"{s}    P      {params[0]:.7f} {params[1]:.7f} {params[2]:.7f} {params[3]:.7f}", None)
    if mt == "C/X":  return (f"{s}    C/X    {params[0].Y():.7f} {params[0].Z():.7f} {params[2]:.7f}", None)
    if mt == "C/Y":  return (f"{s}    C/Y    {params[0].X():.7f} {params[0].Z():.7f} {params[2]:.7f}", None)
    if mt == "C/Z":  return (f"{s}    C/Z    {params[0].X():.7f} {params[0].Y():.7f} {params[2]:.7f}", None)
    if mt == "S":
        loc, r = params
        return f"{s}    S      {loc.X():.7f} {loc.Y():.7f} {loc.Z():.7f} {r:.7f}"
    if mt == "SO":   return f"{s}    SO     {params[1]:.7f}"
    if mt == "K/X":
        loc, _, sa = params
        t2 = math.tan(sa)**2
        return f"{s}    K/X    {loc.X():.7f} {loc.Y():.7f} {loc.Z():.7f} {t2:.7f} 1"
    if mt == "K/Y":
        loc, _, sa = params
        t2 = math.tan(sa)**2
        return f"{s}    K/Y    {loc.X():.7f} {loc.Y():.7f} {loc.Z():.7f} {t2:.7f} 1"
    if mt == "K/Z":
        loc, _, sa = params
        t2 = math.tan(sa)**2
        return f"{s}    K/Z    {loc.X():.7f} {loc.Y():.7f} {loc.Z():.7f} {t2:.7f} 1"
    if mt in ("TX","TY","TZ"):
        loc, _, maj, mini = params
        return (f"{s}    {mt:5s} {loc.X():.7f} {loc.Y():.7f} {loc.Z():.7f} {maj:.7f} {mini:.7f} {mini:.7f}", None)
    return (None, None)


def gen_tr_for_cylinder(axis_dir, center, radius, next_tr_num, next_surf_num):
    """为非轴对齐圆柱生成 TR 卡 + 标准 C/X/C/Y/CZ 曲面。

    Returns:
        (surf_card, tr_card, surf_num) or (None, None, None) if axis-aligned.
    """
    dx = abs(axis_dir.X()); dy = abs(axis_dir.Y()); dz = abs(axis_dir.Z())
    if dx > 0.9999 or dy > 0.9999 or dz > 0.9999:
        return None, None, None

    # 选最接近的轴
    if dx >= dy and dx >= dz:
        base_type = "C/X"
    elif dy >= dx and dy >= dz:
        base_type = "C/Y"
    else:
        base_type = "C/Z"

    d = gp_Vec(axis_dir.X(), axis_dir.Y(), axis_dir.Z())
    d.Normalize()
    v, w, u = _orthogonal_basis(d)  # v=locX, w=locY, u=locZ

    # 按基础类型交换：让正确的 local 轴指向实际方向 d
    if base_type == "C/X":
        # local X → d; X=d, Y=perp1, Z=perp2
        v, w, u = d, v, w
    elif base_type == "C/Y":
        # local Y → d; X=perp, Y=d, Z=perp
        v, w, u = v, d, w
    else:  # C/Z — local Z → d
        v, w, u = v, w, d

    tr_num = next_tr_num
    surf_num = next_surf_num
    cx, cy, cz = center.X(), center.Y(), center.Z()
    tr_card = (f"TR{tr_num}   {cx:.7f} {cy:.7f} {cz:.7f}"
               f"  {v.X():.7f} {v.Y():.7f} {v.Z():.7f}"
               f"  {w.X():.7f} {w.Y():.7f} {w.Z():.7f}"
               f"  {u.X():.7f} {u.Y():.7f} {u.Z():.7f}")

    surf_card = f"{surf_num:5d} {tr_num}    {base_type}    0.0000000 0.0000000 {radius:.7f}"
    return surf_card, tr_card, surf_num


def dedup_key(mt, params, tr_info=None):
    """去重键。带 TR 时包含 TR 信息。"""
    if mt in ("PX","PY","PZ"):  return (mt, round(params[3], 5))
    if mt == "P": return ("P", round(params[0],5), round(params[1],5), round(params[2],5), round(params[3],5))
    if mt == "C/X": return (mt, round(params[0].Y(),5), round(params[0].Z(),5), round(params[2],5))
    if mt == "C/Y": return (mt, round(params[0].X(),5), round(params[0].Z(),5), round(params[2],5))
    if mt == "C/Z": return (mt, round(params[0].X(),5), round(params[0].Y(),5), round(params[2],5))
    if mt == "S":
        loc, r = params
        return ("S", round(loc.X(),5), round(loc.Y(),5), round(loc.Z(),5), round(r,5))
    if mt == "SO": return ("SO", round(params[1],5))
    if mt in ("K/X","K/Y","K/Z"):
        loc, _, sa = params
        return (mt, round(loc.X(),5), round(loc.Y(),5), round(loc.Z(),5), round(math.tan(sa)**2,5))
    if mt in ("TX","TY","TZ"):
        loc, _, maj, mini = params
        return (mt, round(loc.X(),5), round(loc.Y(),5), round(loc.Z(),5), round(maj,5), round(mini,5))
    return (mt, str(params))


def face_sense(face, solid):
    """判断面的法线方向。"""
    surf = BRepAdaptor_Surface(face)
    u1, u2 = surf.FirstUParameter(), surf.LastUParameter()
    v1, v2 = surf.FirstVParameter(), surf.LastVParameter()
    um, vm = (u1+u2)/2, (v1+v2)/2
    gs = surf.Surface().Surface()
    lp = GeomLProp_SLProps(gs, um, vm, 1, 1e-7)
    nd = lp.Normal()
    nv = gp_Vec(nd.X(), nd.Y(), nd.Z())
    p = gs.Value(um, vm)
    off = nv.Multiplied(0.001)
    tp = gp_Pnt(p.X()+off.X(), p.Y()+off.Y(), p.Z()+off.Z())
    cl = BRepClass3d_SolidClassifier(solid)
    cl.Perform(tp, 1e-6)
    st = cl.State()
    if st == TopAbs_IN: return "-"
    if st == TopAbs_OUT: return "+"
    off2 = nv.Multiplied(-0.001)
    tp2 = gp_Pnt(p.X()+off2.X(), p.Y()+off2.Y(), p.Z()+off2.Z())
    cl.Perform(tp2, 1e-6)
    return "+" if cl.State() == TopAbs_IN else "-"


def convert_decomposed_step(step_path, start_surf=1):
    """读取分解后的 STEP 文件，生成标准 MCNP 曲面卡（无 GQ）。

    Returns:
        dict: {surface_number: card_text}
        dict: {tr_number: tr_card_text}
        list: [{num, expr, nfaces}, ...]
    """
    reader = STEPControl_Reader()
    if reader.ReadFile(step_path) != 1:
        return None, None, None

    reader.TransferRoots()
    shape = reader.OneShape()

    solids = []
    exp = TopExp_Explorer(shape, TopAbs_SOLID)
    while exp.More():
        solids.append(exp.Current())
        exp.Next()
    if not solids:
        solids = [shape]

    surfaces = {}
    tr_cards = {}
    srf_map = {}
    nsurf = start_surf
    next_tr = 1
    cells = []

    for si, sol in enumerate(solids):
        fe = TopExp_Explorer(sol, TopAbs_FACE)
        cell_srfs = []

        while fe.More():
            face = fe.Current()
            adapt = BRepAdaptor_Surface(face)
            st = adapt.GetType()

            if st not in (GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone,
                          GeomAbs_Sphere, GeomAbs_Torus):
                fe.Next()
                continue

            mt0, axis, params = get_surface_info(adapt, st)
            sense = face_sense(face, sol)

            # 非轴对齐圆柱 → 用 TR
            if mt0 == "C" and axis is not None:
                loc = params[0]
                r = params[2]
                surf_card, tr_card, sn = gen_tr_for_cylinder(
                    axis, loc, r, next_tr, nsurf)
                if surf_card:
                    tr_cards[next_tr] = tr_card
                    next_tr += 1
                    key = ("TR_CYL", sn)
                    surfaces[nsurf] = surf_card
                    srf_map[key] = nsurf
                    cell_srfs.append((nsurf, sense))
                    nsurf += 1
                    fe.Next()
                    continue
                # 失败则回退到轴对齐
                mt = "C"  # fallback - shouldn't happen

            key = dedup_key(mt0, params) if mt0 != "C" else ("C", id(face))

            if key in srf_map:
                sn = srf_map[key]
                if (sn, sense) not in cell_srfs:
                    cell_srfs.append((sn, sense))
                fe.Next()
                continue

            # 轴对齐圆柱 & 标准表面
            card, tr_card = format_surf(nsurf, mt0, params)
            if card is None:
                fe.Next()
                continue
            surfaces[nsurf] = card
            srf_map[key] = nsurf
            cell_srfs.append((nsurf, sense))
            nsurf += 1
            fe.Next()

        if cell_srfs:
            parts = [f"{s}{n}" for n, s in cell_srfs]
            cells.append({"num": si + 1, "expr": " ".join(parts),
                          "nfaces": len(cell_srfs)})

    return surfaces, tr_cards, cells


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: <step_path> [start_surf]"}))
        sys.exit(1)

    step_path = sys.argv[1]
    start_surf = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    surfaces, tr_cards, cells = convert_decomposed_step(step_path, start_surf)
    if surfaces is None:
        print(json.dumps({"error": "Failed to read STEP file"}))
    else:
        result = {
            "surfaces": {str(k): v for k, v in sorted(surfaces.items())},
            "tr_cards": {str(k): v for k, v in sorted(tr_cards.items())},
            "cells": cells,
        }
        print(json.dumps(result))
