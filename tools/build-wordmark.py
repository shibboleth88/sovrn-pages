#!/usr/bin/env python3
"""Build the wordmark: "sovrn art" cut out of the programme's own on-chain identifiers.

    pip3 install fonttools brotli
    python3 tools/build-wordmark.py            # writes img/wordmark.svg
    python3 tools/build-wordmark.py --preview  # ...and a page to look at it on

The technique is Van Arman's, taken from Reflection. Open any piece of that
collection and the drawn forms are not filled with colour — they are filled with
text. The `owner` group holds the collector's wallet address repeated across a
row; `hex48` and `bin48` hold forty-eight rows each of the work's hex and binary.
Those layers are then clipped through the shapes the robot painted: skullclip,
byteganclip, invasionclip. The data is the ink and the painted form is the
stencil, so the picture is made of its own provenance.

This does the same to the wordmark. The letters are a clip path; what shows
through them is every contract the programme has released. At arm's length it
reads sovrn art. Up close it is the work.

Two decisions worth keeping:

**The letters are outlines, not text.** An SVG loaded through <img> is an
isolated document: it cannot see the host page's fonts, so a <text> clip falls
back to a system serif and the mark silently becomes a different mark. Outlines
render identically inline, as <img>, as an og:image, at any size, with no
network. Reflection solves the same problem the same way — it is pure geometry
and embeds no raster.

**The field stays live text.** It could have been flattened too, but then the
addresses would stop being addresses. Left as text they are selectable,
searchable and readable by a screen reader: you can drag across the wordmark and
copy a contract out of it. That seemed worth more than absolute self-containment
for a layer whose whole claim is that every character is real.
"""
import io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = "/Users/ericandrewgreen/sovrn-onchain/data/collections.json"
# The faces live in the repo rather than in /tmp, which gets cleared: the marks
# have to be reproducible without a download, and a generator that silently
# depends on a temp file is a generator that stops working.
FONT = os.path.join(ROOT, "tools", "fonts", "fraunces-light-italic.woff2")
# The round mark needs a different face, and the reason is structural rather
# than stylistic. A stencil has to hold ink: Reflection fills a skull and an
# invasion, big solid forms that carry many rows of text. Fraunces Light Italic
# is the opposite — thin strokes catch two rows and the gold washes out to pale
# lavender against the violet. Black, soft and wonky is both a better stencil and
# far closer to the chunky lettering the existing logo actually uses.
DISC_FONT = os.path.join(ROOT, "tools", "fonts", "fraunces-black.woff2")
OUT = os.path.join(ROOT, "img", "wordmark.svg")

LINES = ("sovrn", "art")
INK = "#7830fc"                 # the violet of the existing mark
# Sampled off the logo itself rather than guessed: the disc and its lettering.
VIOLET, GOLD = "#7230fc", "#fcd284"
# A darker violet sits under the character field. Without it the disc is only as
# opaque as text is dense — around half — so on the homepage mosaic the tiles
# showed straight through and it stopped reading as a disc at all. The ground is
# darker than the field rather than equal to it, so the characters still read as
# characters against it: the disc is opaque, and visibly made of writing.
GROUND = "#4c18b8"
DISC = 1200                     # the round mark is drawn large — see the note in main()
LINE_PX = 460                   # em size for the letterforms
# The texture has to be dense relative to the stroke it fills. Fraunces Light
# Italic is a thin face, so at 13px on 16.5px rows a stroke caught only fragments
# of characters and the word fell apart into speckle. Small and tight enough that
# every stroke carries two or three rows of text is what makes it read.
FIELD_PX, ROW_PX = 8.5, 10.2
PAD = 26

def identifiers():
    """Every on-chain identifier the programme has.

    Emerging Faces is absent on purpose rather than by oversight: it is fully
    on-chain but carries no Sovrn release contract, so there is no address to
    set. Inventing a placeholder would put the one false mark on a wordmark whose
    entire claim is that every character is real."""
    rows = json.load(io.open(DATA, encoding="utf-8"))
    rows = rows if isinstance(rows, list) else rows.get("collections", rows)
    out = []
    for c in rows:
        if c.get("contract"):
            out.append((c["title"], c["contract"]))
        elif c.get("inscription"):
            out.append((c["title"], "inscription %s" % c["inscription"]))
        rel = c.get("related_contract")
        if rel and rel.get("contract"):
            out.append((rel.get("title", c["title"]), rel["contract"]))
    return out

def letterforms(font_path=None, line_px=None):
    """The two words as path data, plus the box they occupy."""
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.misc.transform import Transform

    font = instancer.instantiateVariableFont(TTFont(font_path or FONT), {"opsz": 144})
    gs, cmap = font.getGlyphSet(), font.getBestCmap()
    scale = (line_px or LINE_PX) / font["head"].unitsPerEm

    words = []
    for word in LINES:
        # lay the glyphs out on a baseline, flipping y — font space is y-up,
        # SVG is y-down
        pen = SVGPathPen(gs)
        bounds = BoundsPen(gs)
        x = 0.0
        for ch in word:
            g = gs[cmap[ord(ch)]]
            t = Transform().scale(scale, -scale).translate(x, 0)
            g.draw(TransformPen(pen, t))
            g.draw(TransformPen(bounds, t))
            x += g.width
        words.append({"d": pen.getCommands(), "bounds": bounds.bounds, "adv": x * scale})
    return words

def layout(words, line_px):
    """Stack the two lines centred on the widest, and report the block's box."""
    widest = max(w["adv"] for w in words)
    gap = line_px * 0.02
    tops, y = [], 0.0
    for w in words:
        x0, y0, x1, y1 = w["bounds"]
        tops.append({"dx": (widest - w["adv"]) / 2, "dy": y - y0, "d": w["d"]})
        y += (y1 - y0) + gap
    return tops, widest, y - gap


def field_rows(strip, width, height, size, row, y0):
    """One long ribbon of every identifier, each row starting at a different
    point in it so the field never lines up into columns — a grid would read as
    a table rather than as material."""
    per_row = int(width / (size * 0.60)) + 8
    rows, i, yy = [], 0, y0
    while yy < height:
        shift = (i * 137) % len(strip)          # 137 is prime: no visible cycle
        line = (strip[shift:] + strip) * (per_row // len(strip) + 2)
        rows.append('      <text y="%.1f">%s</text>' % (yy, line[:per_row]))
        yy += row; i += 1
    return rows


def build_disc():
    """The round mark: the existing logo, with its gold lettering made of the
    programme's own contracts.

    It has a property the flat version does not. Shrink it and the texture
    disappears before the letterforms do, so at masthead size it settles into
    very nearly the logo the site already uses — violet disc, gold wordmark —
    and only opens up into its material when it is given room."""
    ids = identifiers()
    # The block spans about 62% of the diameter, which is where the existing
    # logo sets it.
    probe = letterforms(DISC_FONT, 1000.0)          # measure, then fit
    line_px = 1000.0 * (DISC * 0.66) / max(w["adv"] for w in probe)
    words = letterforms(DISC_FONT, line_px)

    tops, widest, block_h = layout(words, line_px)
    cx = cy = DISC / 2
    ox, oy = cx - widest / 2, cy - block_h / 2
    r = DISC * 0.48

    paths = "\n".join(
        '      <path transform="translate(%.1f %.1f)" d="%s"/>' % (ox + t["dx"], oy + t["dy"], t["d"])
        for t in tops
    )
    # Density held to the same ratio the flat mark uses, so both read alike.
    size, row = line_px * 0.0155, line_px * 0.0186
    strip = "   ".join(v for _, v in ids) + "   "
    rows = field_rows(strip, DISC, DISC, size, row, size)

    names = ", ".join(t for t, _ in ids)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {DISC} {DISC}"
     width="{DISC}" height="{DISC}" role="img" aria-label="sovrn art">
  <title>sovrn art</title>
  <desc>The whole mark is one field of the programme's own on-chain identifiers —
  the {len(ids)} contracts and inscriptions behind {names}. The disc is that field
  clipped to a circle; the wordmark is the same field, the same characters in the
  same places, clipped again to the letterforms and coloured gold. Nothing is
  drawn but text. The technique is taken from Reflection, where the painted forms
  are filled with the owner's wallet address rather than with colour.</desc>
  <defs>
    <clipPath id="sovrn-disc">
      <circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r:.0f}"/>
    </clipPath>
    <clipPath id="sovrn-letters">
{paths}
    </clipPath>
    <!-- One field, written once and used twice. The two layers therefore share
         every character position exactly, so the wordmark is not a second thing
         laid on top of the disc: it is the same stream of addresses, coloured
         differently where the letters fall. -->
    <g id="sovrn-field"
       font-family="\'IBM Plex Mono\', ui-monospace, SFMono-Regular, Menlo, monospace"
       font-size="{size:.2f}" xml:space="preserve">
{chr(10).join(rows)}
    </g>
  </defs>
  <circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r:.0f}" fill="{GROUND}"/>
  <g clip-path="url(#sovrn-disc)">
    <use href="#sovrn-field" fill="{VIOLET}"/>
    <!-- The letters are the same field worked a second time, offset by half a
         row and half a character so the two passes interleave rather than
         overprint. That doubles the ink inside the letterforms and nowhere else,
         which is what makes the wordmark read: at equal density the gold and the
         violet differ only in hue and the word disappears. Reflection solves the
         same problem the same way — it carries lighten, darken and highlight
         passes over ground it has already laid. -->
    <g clip-path="url(#sovrn-letters)">
      <use href="#sovrn-field" fill="{GOLD}"/>
      <use href="#sovrn-field" fill="{GOLD}" transform="translate({size * 0.30:.2f} {row * 0.5:.2f})"/>
    </g>
  </g>
</svg>
'''


def build():
    ids = identifiers()
    words = letterforms()

    # Stack the two lines, each centred on the widest.
    widest = max(w["adv"] for w in words)
    gap = LINE_PX * 0.02
    tops, y = [], 0.0
    for w in words:
        x0, y0, x1, y1 = w["bounds"]
        tops.append({"dx": (widest - w["adv"]) / 2, "dy": y - y0, "d": w["d"]})
        y += (y1 - y0) + gap
    W = widest + PAD * 2
    H = y - gap + PAD * 2

    paths = "\n".join(
        '      <path transform="translate(%.1f %.1f)" d="%s"/>' % (PAD + t["dx"], PAD + t["dy"], t["d"])
        for t in tops
    )

    # The texture. One long ribbon of every identifier, each row starting at a
    # different point in it so the field never lines up into columns — a grid
    # would read as a table rather than as material.
    strip = "   ".join(v for _, v in ids) + "   "
    per_row = int(W / (FIELD_PX * 0.60)) + 8
    rows, i, yy = [], 0, PAD * 0.4
    while yy < H:
        shift = (i * 137) % len(strip)          # 137 is prime: no visible cycle
        line = (strip[shift:] + strip) * (per_row // len(strip) + 2)
        rows.append('      <text y="%.1f">%s</text>' % (yy, line[:per_row]))
        yy += ROW_PX; i += 1

    names = ", ".join(t for t, _ in ids)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}"
     width="{W:.0f}" height="{H:.0f}" role="img" aria-label="sovrn art">
  <title>sovrn art</title>
  <desc>The wordmark cut out of the programme's own on-chain identifiers: the
  {len(ids)} contracts and inscriptions behind {names}. The technique is taken
  from Reflection, where the painted forms are filled with the owner's wallet
  address rather than with colour.</desc>
  <defs>
    <clipPath id="sovrn-wordmark">
{paths}
    </clipPath>
  </defs>
  <g clip-path="url(#sovrn-wordmark)" fill="{INK}"
     font-family="'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
     font-size="{FIELD_PX}" xml:space="preserve">
{chr(10).join(rows)}
  </g>
</svg>
'''

def main():
    if not os.path.exists(FONT):
        sys.exit("  missing %s — see the note at the top of this file" % FONT)
    svg = build()
    io.open(OUT, "w", encoding="utf-8").write(svg)
    disc = build_disc()
    disc_path = os.path.join(ROOT, "img", "wordmark-disc.svg")
    io.open(disc_path, "w", encoding="utf-8").write(disc)
    ids = identifiers()
    print("  wrote %s (%.1f KB)" % (os.path.relpath(OUT, ROOT), len(svg) / 1024))
    print("  wrote %s (%.1f KB)" % (os.path.relpath(disc_path, ROOT), len(disc) / 1024))
    print("  identifiers set into each: %d" % len(ids))

    if "--preview" in sys.argv:
        p = os.path.join(ROOT, "wordmark-preview.html")
        io.open(p, "w", encoding="utf-8").write('''<!doctype html><meta charset="utf-8">
<title>wordmark</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  body{background:#e9e9e5;margin:0;padding:44px;font:400 11px/1.5 "IBM Plex Mono",monospace;color:#6b6f76}
  .row{max-width:1180px;margin:0 auto 52px}
  .lbl{text-transform:uppercase;letter-spacing:.11em;margin:0 0 12px}
  img{display:block;width:100%;height:auto}
  .w520{width:520px}.w300{width:300px}.w176{width:176px}
  .dark{background:#16181d;padding:34px}
</style>
<div class="row"><p class="lbl">full width — 1180px</p><img src="/img/wordmark.svg" alt="sovrn art"></div>
<div class="row"><p class="lbl">520px</p><img class="w520" src="/img/wordmark.svg" alt=""></div>
<div class="row"><p class="lbl">176px — the size the current logo runs at</p><img class="w176" src="/img/wordmark.svg" alt=""></div>
<div class="row dark"><p class="lbl" style="color:#8a8f98">on ink, 300px</p><img class="w300" src="/img/wordmark.svg" alt=""></div>
''')
        print("  preview: wordmark-preview.html")

if __name__ == "__main__":
    main()
