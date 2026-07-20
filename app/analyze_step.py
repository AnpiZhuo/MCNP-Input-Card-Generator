import sys, os
sys.path.append('D:/FreeCAD/FreeCAD_1.1.1-Windows-x86_64-py311/bin')
sys.path.append('D:/FreeCAD/FreeCAD_1.1.1-Windows-x86_64-py311/lib')

import OCC.Core.STEPControl
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder

reader = STEPControl_Reader()
reader.ReadFile('P:/魏一卓塞进去的/mcnp/geometry.stp')
reader.TransferRoots()
shape = reader.OneShape()

solids = []
exp = TopExp_Explorer(shape, TopAbs_SOLID)
while exp.More():
    solids.append(exp.Current())
    exp.Next()

print('原始STEP: %d 个实体' % len(solids))

for si, sol in enumerate(solids):
    bb = sol.BoundingBox()
    xmin = bb.CornerMin().X(); ymin = bb.CornerMin().Y(); zmin = bb.CornerMin().Z()
    xmax = bb.CornerMax().X(); ymax = bb.CornerMax().Y(); zmax = bb.CornerMax().Z()
    print('\n实体 %d:' % (si+1))
    print('  包围盒: X[%.0f,%.0f] Y[%.0f,%.0f] Z[%.0f,%.0f]' % (xmin,xmax,ymin,ymax,zmin,zmax))

    planes = 0; cylinders = 0; angled = 0
    fe = TopExp_Explorer(sol, TopAbs_FACE)
    while fe.More():
        adapt = BRepAdaptor_Surface(fe.Current())
        st = adapt.GetType()
        if st == GeomAbs_Plane:
            planes += 1
        elif st == GeomAbs_Cylinder:
            cylinders += 1
            cyl = adapt.Cylinder()
            axis = cyl.Axis().Direction()
            loc = cyl.Location()
            r = cyl.Radius()
            ax = abs(axis.X()); ay = abs(axis.Y()); az = abs(axis.Z())
            if max(ax, ay, az) < 0.9999:
                angled += 1
                print('  斜柱 R=%.0f 方向(%.3f,%.3f,%.3f) 中心(%.0f,%.0f,%.0f)' % (r, axis.X(), axis.Y(), axis.Z(), loc.X(), loc.Y(), loc.Z()))
        fe.Next()

    print('  面: %d 平面, %d 圆柱(%d斜)' % (planes, cylinders, angled))
