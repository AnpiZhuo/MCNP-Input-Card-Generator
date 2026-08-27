# -*- coding: utf-8 -*-
"""Time compose_lattice_tree alone (no STL/HTTP) to isolate the 97s bottleneck."""
import sys, time, json, os
ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ROOT)  # tools/ -> project root
sys.path.insert(0, os.path.join(ROOT, 'app'))
sys.path.insert(0, ROOT)
import lattice
from generator.parsers import parse_inp_text

inp = open('gui/public/examples/beavrs_fullcore_mcnp.i', encoding='utf-8').read()
deck, _w = parse_inp_text(inp)
surf_text = deck.surfaces if hasattr(deck, 'surfaces') else ''
print('type deck', type(deck).__name__)

# Build sub_by_u like api_server _handle_preview_lattice
import dataclasses
def to_dict(obj):
    if dataclasses.is_dataclass(obj):
        return {k: to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
dd = to_dict(deck)

# top-level surfaces text
surf_text = dd.get('surfaces', '')
tr_text = dd.get('tr_cards', '')
# cells: filter kind != raw, build info like handler
sub_by_u = {}
lattice_infos = []
for c in dd.get('cells', []):
    if c.get('kind') == 'raw':
        continue
    cell = c.get('cell') if c.get('kind') == 'cell' and isinstance(c.get('cell'), dict) else c
    u = str(cell.get('u', '') or '')
    fg = lattice.FillGrid.from_json(cell.get('fill_grid', '')) if cell.get('fill_grid', '') else None
    info = {
        'cellNum': cell.get('number'),
        'u': u,
        'material': str(cell.get('material', '') or '0'),
        'fill': str(cell.get('fill', '') or ''),
        'fill_grid': fg,
        'surface_expr': str(cell.get('surface_expr', '') or ''),
        'lat': str(cell.get('lat', '') or ''),
        'trcl': str(cell.get('trcl', '') or ''),
    }
    if fg is not None and fg.kind == 'translated':
        e = fg.cells[0] if fg.cells else None
        if e is not None:
            info['fill'] = str(e.u or '')
    sub_by_u.setdefault(u, []).append(info)
    if fg is not None and fg.kind == 'lattice':
        lattice_infos.append(info)

# outer = 未被引用的格阵
referenced = set()
for _i in lattice_infos:
    _fg = _i.get('fill_grid')
    if _fg is not None:
        for _e in _fg.cells:
            referenced.add(str(_e.u or ''))
outer = next((i for i in lattice_infos if str(i.get('u', '')) not in referenced), lattice_infos[0])

# extent for outer
fge = outer['fill_grid']
ext = lattice.lattice_cell_extent(outer.get('surface_expr', ''), '1', surf_text)
print('outer u', outer.get('u'), 'extent', ext)

for detail in ('layers', 'disc'):
    t0 = time.time()
    r = lattice.compose_lattice_tree(fge, sub_by_u, ext, 0.0,
                                     lattice.MAX_LATTICE_DEPTH, lattice.MAX_TOTAL_INSTANCES,
                                     surf_text, axial=False, detail=detail)
    dt = time.time() - t0
    print('detail=%s  count=%d  status=%s  t=%.2fs  leaves=%d' % (
        detail, r.get('count'), r.get('status'), dt, len(r.get('leafInstances', []))))
