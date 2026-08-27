# -*- coding: utf-8 -*-
"""Dump each lattice entry positions + leafInstances xyz bucketing to find z-over-stacking."""
import sys, os, json
ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ROOT)
sys.path.insert(0, os.path.join(ROOT, 'app'))
sys.path.insert(0, ROOT)
import lattice
from generator.parsers import parse_inp_text

inp = open('gui/public/examples/beavrs_fullcore_mcnp.i', encoding='utf-8').read()
deck, _w = parse_inp_text(inp)
import dataclasses
def to_dict(o):
    if dataclasses.is_dataclass(o):
        return {k: to_dict(v) for k, v in dataclasses.asdict(o).items()}
    if isinstance(o, list):
        return [to_dict(x) for x in o]
    return o
dd = to_dict(deck)
surf_text = dd.get('surfaces', '')
sub_by_u = {}
lattice_infos = []
for c in dd.get('cells', []):
    if c.get('kind') == 'raw':
        continue
    cell = c.get('cell') if c.get('kind') == 'cell' and isinstance(c.get('cell'), dict) else c
    u = str(cell.get('u', '') or '')
    fg = lattice.FillGrid.from_json(cell.get('fill_grid', '')) if cell.get('fill_grid', '') else None
    info = {'cellNum': cell.get('number'), 'u': u, 'material': str(cell.get('material', '') or '0'),
            'fill': str(cell.get('fill', '') or ''), 'fill_grid': fg,
            'surface_expr': str(cell.get('surface_expr', '') or ''), 'lat': str(cell.get('lat', '') or ''),
            'trcl': str(cell.get('trcl', '') or '')}
    if fg is not None and fg.kind == 'translated':
        e = fg.cells[0] if fg.cells else None
        if e is not None:
            info['fill'] = str(e.u or '')
    sub_by_u.setdefault(u, []).append(info)
    if fg is not None and fg.kind == 'lattice':
        lattice_infos.append(info)

ref = set()
for _i in lattice_infos:
    _fg = _i.get('fill_grid')
    if _fg is not None:
        for _e in _fg.cells:
            ref.add(str(_e.u or ''))
outer = next((i for i in lattice_infos if str(i.get('u', '')) not in ref), lattice_infos[0])
fge = outer['fill_grid']
ext = lattice.lattice_cell_extent(outer.get('surface_expr', ''), '1', surf_text)
print('outer u=%s extent=%s' % (outer.get('u'), ext))

for detail in ('disc',):
    r = lattice.compose_lattice_tree(fge, sub_by_u, ext, 0.0,
                                     lattice.MAX_LATTICE_DEPTH, lattice.MAX_TOTAL_INSTANCES,
                                     surf_text, axial=False, detail=detail)
    print('\n=== detail=%s count=%d leaves=%d ==' % (detail, r.get('count'), len(r.get('leafInstances', []))))
    # per lattice entry positions z-buckets
    for lt in r.get('lattices', []):
        pos = lt.get('positions', [])
        if not pos:
            continue
        zs = [p.get('z') for p in pos if p.get('z') is not None]
        ucnt = {}
        for p in pos:
            ucnt[str(p.get('u'))] = ucnt.get(str(p.get('u')), 0) + 1
        print('lat num=%s u=%s dims=%s pitch=%s npos=%d zrange=(%.1f,%.1f) distinct_z=%d ucnt=%s' % (
            lt.get('num'), lt.get('center'), lt.get('dims'), lt.get('pitch'), len(pos),
            min(zs) if zs else -1, max(zs) if zs else -1, len(set(round(z,2) for z in zs)),
            dict(list(ucnt.items())[:8])))
    # leafInstances z bucketing
    leaves = r.get('leafInstances', [])
    zb = {}
    xs = [l.get('x') for l in leaves if l.get('x') is not None]
    ys = [l.get('y') for l in leaves if l.get('y') is not None]
    zs2 = [l.get('z') for l in leaves if l.get('z') is not None]
    for l in leaves:
        zb[round(l.get('z', 0), 1)] = zb.get(round(l.get('z', 0), 1), 0) + 1
    print('LEAF xrange=(%.1f,%.1f) yrange=(%.1f,%.1f) zrange=(%.1f,%.1f)' % (
        min(xs), max(xs), min(ys), max(ys), min(zs2), max(zs2)))
    dist = sorted(zb.items(), key=lambda kv: -kv[1])[:12]
    print('LEAF z buckets (z:count):', dist)
    print('leaf depth histogram:', dict((str(d), sum(1 for l in leaves if l.get('depth')==d)) for d in sorted(set(l.get('depth') for l in leaves))))
