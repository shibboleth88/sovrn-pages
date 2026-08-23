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

# --- proof -------------------------------------------------------------------
# The reason to trust any of this: run the rule against the six minted originals
# and it reproduces the artist's own Francisco Carolinum renders exactly. Run
# `python3 reflection-smooth.py --verify` after touching anything above.

TOKENS = ('515', '884', '885', '886', '888', '889')
CONTRACT = '0x5137cfb461d24040f5ce6b85d860c47a24f85412'
FC = ('https://raw.githubusercontent.com/gorgonorgon/sovrn-FC-images/main/'
      'reflection_%s_layers_smooth.svg')
RPC = 'https://ethereum-rpc.publicnode.com'

def minted(token):
    """the artwork as minted, straight from the contract"""
    import json, base64, urllib.request
    data = '0xc87b56dd' + format(int(token), 'x').rjust(64, '0')
    body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'eth_call',
                       'params': [{'to': CONTRACT, 'data': data}, 'latest']}).encode()
    # publicnode 403s urllib's default User-Agent
    req = urllib.request.Request(RPC, body, {'Content-Type': 'application/json',
                                             'User-Agent': 'curl/8.4.0'})
    h = json.load(urllib.request.urlopen(req, timeout=120))['result'][2:]
    off = int(h[:64], 16) * 2
    ln = int(h[off:off + 64], 16) * 2
    uri = bytes.fromhex(h[off + 64:off + 64 + ln]).decode()
    meta = json.loads(base64.b64decode(uri.split(',', 1)[1]))
    return base64.b64decode(meta['image'].split(',', 1)[1]).decode()

def fades(svg):
    """every group's fade, normalised so formatting differences do not count"""
    import xml.etree.ElementTree as ET
    NS = '{http://www.w3.org/2000/svg}'
    out = []
    for g in ET.fromstring(svg).iter(NS + 'g'):
        a = next((c for c in g if c.tag == NS + 'animate'), None)
        if a is None:
            out.append(None); continue
        out.append((round(float(a.get('begin').rstrip('s')), 6),
                    tuple(round(float(x), 6) for x in a.get('keyTimes').split(';')),
                    a.get('values'), a.get('dur'),
                    a.get('repeatCount'), a.get('fill')))
    return out

def verify():
    import urllib.request
    ok = 0
    for t in TOKENS:
        got = fades(smooth(minted(t)))
        req = urllib.request.Request(FC % t, headers={'User-Agent': 'curl/8.4.0'})
        want = fades(urllib.request.urlopen(req, timeout=60).read().decode())
        if got == want:
            print(f'  token {t}: exact — {sum(x is not None for x in got)} fades'); ok += 1
        else:
            print(f'  token {t}: {sum(a != b for a, b in zip(got, want))} differ')
    print(f'\n  {ok}/{len(TOKENS)} exact')
    return ok == len(TOKENS)

if __name__ == '__main__':
    if '--verify' in sys.argv:
        sys.exit(0 if verify() else 1)
    open(sys.argv[2], 'w', encoding='utf-8').write(
        smooth(open(sys.argv[1], encoding='utf-8').read()))
