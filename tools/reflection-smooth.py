"""Rebuild the Francisco Carolinum 'smooth' cascade from a minted Reflection SVG.

The minted file carries its own schedule. Comments number every painting pass --
11 ganStrokes, 12 skull, 13 background, 14, 15 circles, 16 touchups, 17 lighten,
18 darken, 19 highlight, 20 skull flourish, 21 final -- and startanim/endanim
bracket the seven fades the artist minted.

Smoothing walks the groups from pass 11 and gives each drawn layer its own fade,
one every 0.4s, leaving the seven minted fades untouched. keyTimes follows from
begin: the layer dips out at 1/16 of the loop and is back begin/8 + 1/16 later,
which is 0.125 + 0.0625*begin.

Four things the artist's own renders do that the plain walk would not:
  - the grid beneath the strokes (a *rows class inside pass 11) never fades
  - the group that opens pass 13 holds a slot in the sequence but does not fade
  - passes 19 and 20 fade their unclassed wrappers too, unlike every other pass
  - pass 20 is empty in some pieces, marked by a childless group; then it fades
    nothing, and its closing wrapper -- which really belongs to pass 21 -- never
    fades in any piece
"""
import re, sys

ROWCLS = ('fortyeightrows', 'eightyrows', 'twentyfourrows')
STEP = 0.4

def scan(svg):
    """every <g> in document order: text offset, pass number, class, minted?, empty?"""
    gs, sec = [], -1
    for m in re.finditer(r'<!--\s*(.*?)\s*-->|<g\b([^>]*?)(/?)>', svg, re.S):
        if m.group(1) is not None:
            n = re.match(r'(\d+):', m.group(1))
            if n: sec = int(n.group(1))
            continue
        attrs, selfclose = m.group(2), m.group(3)
        cls = re.search(r'class="([^"]+)"', attrs)
        rest = svg[m.end():].lstrip()
        gs.append({'pos': m.end(), 'sec': sec,
                   'cls': cls.group(1) if cls else None,
                   'minted': rest.startswith('<animate'),
                   'empty': bool(selfclose) or rest.startswith('</g>')})
    return gs

def plan(svg):
    gs = scan(svg)
    p20 = [g for g in gs if g['sec'] == 20]
    p20_dead = any(g['empty'] for g in p20)          # the pass painted nothing
    p20_last = p20[-1] if p20 else None              # really pass 21's wrapper
    out, k, seen13 = [], 0, False
    for g in gs:
        if g['sec'] < 11 or g['minted']:
            continue
        if g['sec'] == 13 and not seen13:
            seen13 = True; k += 1                    # holds a slot, stays still
            continue
        if g['sec'] == 11 and g['cls'] in ROWCLS:
            continue
        if g['sec'] == 20 and (p20_dead or g is p20_last):
            continue
        if not (g['cls'] or g['sec'] in (19, 20)):
            continue
        out.append((g['pos'], round(k * STEP, 10))); k += 1
    return out

def fade(begin):
    k3 = 0.125 + 0.0625 * begin
    return ('<animate attributeType="XML" attributeName="opacity" values="1;0;0;1;1" '
            f'keyTimes="0;0.0625;{k3:g};{k3 + 0.0625:g};1" begin="{begin}s" dur="8s" '
            'repeatCount="indefinite" fill="freeze" />')

def smooth(svg):
    for pos, begin in sorted(plan(svg), reverse=True):
        svg = svg[:pos] + fade(begin) + svg[pos:]
    return svg

if __name__ == '__main__':
    open(sys.argv[2], 'w', encoding='utf-8').write(
        smooth(open(sys.argv[1], encoding='utf-8').read()))
