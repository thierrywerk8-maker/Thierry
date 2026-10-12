"""Finish the workbook written by build_planning_v2.py.

Usage: python3 -I finalize_xlsx.py <built.xlsx> <recalculated.xlsx> <original_upload.xlsx> <out.xlsx>

- built.xlsx:        openpyxl output (formulas, no cached values)
- recalculated.xlsx: the same file after scripts/recalc.py (LibreOffice), used only as the source of cached values
- original upload:   source of the threaded comment on 'Door2Door| Paylogic'!A1 (with @-mentions and the reply),
                     the persons list and the sensitivity-label part, which openpyxl and LibreOffice both drop

The output is built.xlsx with cached values filled in and those parts put back, so the styling stays exactly as
openpyxl wrote it and the comment thread survives.
"""
import sys, zipfile, posixpath
from lxml import etree

built, recalced, original, out = sys.argv[1:5]
PLAN = 'Door2Door| Paylogic'
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      'pr': 'http://schemas.openxmlformats.org/package/2006/relationships',
      'ct': 'http://schemas.openxmlformats.org/package/2006/content-types'}
M = '{%s}' % NS['m']
REL_T = {
    'comments': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments',
    'vml': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing',
    'threaded': 'http://schemas.microsoft.com/office/2017/10/relationships/threadedComment',
    'person': 'http://schemas.microsoft.com/office/2017/10/relationships/person',
    'label': 'http://schemas.microsoft.com/office/2020/02/relationships/classificationlabels',
}


def sheet_paths(z):
    """sheet name -> part path inside the zip"""
    wb = etree.fromstring(z.read('xl/workbook.xml'))
    rels = etree.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    target = {r.get('Id'): r.get('Target') for r in rels}
    paths = {}
    for s in wb.iterfind('m:sheets/m:sheet', NS):
        t = target[s.get('{%s}id' % NS['r'])]
        paths[s.get('name')] = t.lstrip('/') if t.startswith('/') else posixpath.normpath(posixpath.join('xl', t))
    return paths


def rels_path(part):
    d, f = posixpath.split(part)
    return posixpath.join(d, '_rels', f + '.rels')


def add_rel(rels_root, rtype, target):
    ids = {r.get('Id') for r in rels_root}
    n = 1
    while f'rIdX{n}' in ids:
        n += 1
    el = etree.SubElement(rels_root, '{%s}Relationship' % NS['pr'])
    el.set('Id', f'rIdX{n}'), el.set('Type', rtype), el.set('Target', target)
    return f'rIdX{n}'


zb, zr, zo = zipfile.ZipFile(built), zipfile.ZipFile(recalced), zipfile.ZipFile(original)
parts = {n: zb.read(n) for n in zb.namelist()}
bpaths, rpaths, opaths = sheet_paths(zb), sheet_paths(zr), sheet_paths(zo)

# ---- 1. cached values from the LibreOffice recalculation ----
filled = 0
for name, bpath in bpaths.items():
    rroot = etree.fromstring(zr.read(rpaths[name]))
    cached = {}
    for c in rroot.iter(M + 'c'):
        if c.find(M + 'f') is not None and c.find(M + 'v') is not None:
            cached[c.get('r')] = (c.get('t'), c.find(M + 'v').text)
    broot = etree.fromstring(parts[bpath])
    for c in broot.iter(M + 'c'):
        if c.find(M + 'f') is None or c.get('r') not in cached:
            continue
        t, v = cached[c.get('r')]
        vel = c.find(M + 'v')
        if vel is None:
            vel = etree.SubElement(c, M + 'v')
        vel.text = v
        if t in ('str', 'b', 'e'):
            c.set('t', t)
        elif 't' in c.attrib:
            del c.attrib['t']
        filled += 1
    parts[bpath] = etree.tostring(broot, xml_declaration=True, encoding='UTF-8', standalone=True)

# ---- 2. threaded comment thread on the planning tab (A1) ----
o_sheet = opaths[PLAN]
o_rels = etree.fromstring(zo.read(rels_path(o_sheet)))
o_targets = {r.get('Type'): posixpath.normpath(posixpath.join(posixpath.dirname(o_sheet), r.get('Target'))) for r in o_rels}
comment_parts = {k: o_targets[REL_T[k]] for k in ('comments', 'vml', 'threaded')}
for part in comment_parts.values():
    assert part not in parts, part
    parts[part] = zo.read(part)

b_sheet = bpaths[PLAN]
b_rels_path = rels_path(b_sheet)
b_rels = etree.fromstring(parts[b_rels_path]) if b_rels_path in parts else etree.Element('{%s}Relationships' % NS['pr'], nsmap={None: NS['pr']})
rid = {k: add_rel(b_rels, REL_T[k], posixpath.relpath(comment_parts[k], posixpath.dirname(b_sheet))) for k in comment_parts}
parts[b_rels_path] = etree.tostring(b_rels, xml_declaration=True, encoding='UTF-8', standalone=True)

sroot = etree.fromstring(parts[b_sheet])
assert sroot.find(M + 'legacyDrawing') is None
ld = etree.Element(M + 'legacyDrawing')
ld.set('{%s}id' % NS['r'], rid['vml'])
after = ['legacyDrawingHF', 'drawingHF', 'picture', 'oleObjects', 'controls', 'webPublishItems', 'tableParts', 'extLst']
nxt = next((ch for ch in sroot if etree.QName(ch).localname in after), None)
if nxt is not None:
    nxt.addprevious(ld)
else:
    sroot.append(ld)
parts[b_sheet] = etree.tostring(sroot, xml_declaration=True, encoding='UTF-8', standalone=True)

# persons list (who the @-mentions point to) hangs off the workbook
o_wbrels = etree.fromstring(zo.read('xl/_rels/workbook.xml.rels'))
person_part = next(posixpath.normpath(posixpath.join('xl', r.get('Target'))) for r in o_wbrels if r.get('Type') == REL_T['person'])
parts[person_part] = zo.read(person_part)
b_wbrels = etree.fromstring(parts['xl/_rels/workbook.xml.rels'])
add_rel(b_wbrels, REL_T['person'], posixpath.relpath(person_part, 'xl'))
parts['xl/_rels/workbook.xml.rels'] = etree.tostring(b_wbrels, xml_declaration=True, encoding='UTF-8', standalone=True)

# ---- 3. sensitivity-label metadata ----
o_pkgrels = etree.fromstring(zo.read('_rels/.rels'))
label = next((r.get('Target') for r in o_pkgrels if r.get('Type') == REL_T['label']), None)
if label:
    parts[label] = zo.read(label)
    b_pkgrels = etree.fromstring(parts['_rels/.rels'])
    add_rel(b_pkgrels, REL_T['label'], label)
    parts['_rels/.rels'] = etree.tostring(b_pkgrels, xml_declaration=True, encoding='UTF-8', standalone=True)

# ---- content types for everything added ----
o_ct = etree.fromstring(zo.read('[Content_Types].xml'))
b_ct = etree.fromstring(parts['[Content_Types].xml'])
have_default = {d.get('Extension') for d in b_ct.iterfind('ct:Default', NS)}
for d in o_ct.iterfind('ct:Default', NS):
    if d.get('Extension') == 'vml' and 'vml' not in have_default:
        b_ct.insert(0, d)
added = set(comment_parts.values()) | {person_part} | ({label} if label else set())
for o in o_ct.iterfind('ct:Override', NS):
    if o.get('PartName').lstrip('/') in added:
        b_ct.append(o)
parts['[Content_Types].xml'] = etree.tostring(b_ct, xml_declaration=True, encoding='UTF-8', standalone=True)

with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zout:
    zout.writestr('[Content_Types].xml', parts.pop('[Content_Types].xml'))
    for n, data in parts.items():
        zout.writestr(n, data)
print(f'saved {out} | cached values filled: {filled} | added parts: {sorted(added)}')
