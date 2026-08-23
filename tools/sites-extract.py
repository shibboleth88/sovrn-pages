"""Pull a Google Sites page apart in document order.

Sites wraps everything in generated class names, so anchor on the tags that
actually carry meaning: headings, paragraphs, list items, images and links.
Order matters — the page is a narrative and the images sit inside it.
"""
import re, html, sys, json

def strip(s):
    s = re.sub(r'<[^>]+>', '', s)
    return re.sub(r'\s+', ' ', html.unescape(s)).strip()

BOILER = re.compile(
    r'^(Search this site|Embedded Files|Skip to (main content|navigation)|'
    r'Report abuse|Page details|Page updated|Google Sites|Copy heading link|'
    r'sovrn\.art|Home|Curated|Museums|Marketplaces|About|Contact)$', re.I)

def blocks(t):
    body = re.sub(r'<(script|style|noscript)[^>]*>.*?</\1>', '', t, flags=re.S | re.I)
    out = []
    pat = re.compile(
        r'<(h[1-4])\b[^>]*>(.*?)</\1>'
        r'|<(p|li)\b[^>]*>(.*?)</\3>'
        r'|<img\b([^>]*)>'
        r'|<a\b([^>]*)>(.*?)</a>', re.S | re.I)
    for m in pat.finditer(body):
        if m.group(1):
            v = strip(m.group(2))
            if v and not BOILER.match(v): out.append(('h', m.group(1).lower(), v))
        elif m.group(3):
            v = strip(m.group(4))
            if len(v) > 1 and not BOILER.match(v): out.append(('p', m.group(3).lower(), v))
        elif m.group(5) is not None:
            a = m.group(5)
            src = re.search(r'\bsrc="([^"]+)"', a)
            alt = re.search(r'\balt="([^"]*)"', a)
            if src and ('googleusercontent' in src.group(1) or 'blogger' in src.group(1)):
                out.append(('img', src.group(1), alt.group(1) if alt else ''))
        else:
            href = re.search(r'\bhref="([^"]+)"', m.group(6) or '')
            v = strip(m.group(7) or '')
            if href and v and not BOILER.match(v) and href.group(1).startswith('http'):
                out.append(('a', href.group(1), v))
    return out

if __name__ == '__main__':
    t = open(sys.argv[1], encoding='utf-8', errors='ignore').read()
    b = blocks(t)
    if len(sys.argv) > 2 and sys.argv[2] == '--json':
        print(json.dumps(b, ensure_ascii=False, indent=1))
    else:
        for kind, a, v in b:
            if kind == 'img':   print(f'  [IMG] {v[:40]:40s} {a[:70]}')
            elif kind == 'a':   print(f'  [LNK] {v[:56]:56s} -> {a[:60]}')
            elif kind == 'h':   print(f'  [{a.upper()}]  {v[:150]}')
            else:               print(f'  [txt] {v[:180]}')
