#!/usr/bin/env python3
"""Generate responsive derivatives for every raster the pages reference.

    python3 tools/build-images.py            # build what is missing
    python3 tools/build-images.py --prune    # ...then drop what no page can ask for
    python3 tools/build-images.py --check    # non-zero exit if a referenced file is stale

The order matters. A build writes a derivative for every image with a measured
slot, because tools/responsive-images.py can only offer a rung that already
exists; the rewriter then takes up as many as it can; --prune clears the rest.
Galleries that build their <img> in script are the ones left behind, and there
are enough of them that skipping this leaves ~27MB nothing will ever request.

Originals stay where they are and remain the fallback inside every <picture>, so
nothing that already points at them can break. Derivatives mirror the source path
under img/derived/.

Two things here are deliberate and easy to undo by accident:

  * PNGs keep their alpha. The homepage logo and the marketplace icons sit on a
    light card; flattening them to RGB gives a white box on a white card, which
    looks fine in a thumbnail and wrong on the page.
  * The ladder starts at 64px. Most of the waste on this site is not a large
    photograph, it is a 256px icon in a 26px slot — a ladder that starts at 400
    would generate nothing for the files that account for most of the excess.

Animated GIFs are skipped: several of these are the artwork, and a still frame
is not the artwork. SVG is skipped as it is already resolution-independent.
"""
import io, json, os, re, sys
from PIL import Image
try:
    import pillow_avif          # noqa: F401  — registers the AVIF plugin
    HAVE_AVIF = True
except ImportError:
    HAVE_AVIF = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = "img/derived"
# How close two rungs may be before the smaller is dropped. A shared ladder was
# tried first and is worse on both counts: snapping a 1116px requirement up to
# the nearest rung of 1536 ships 37% more pixels than anything asks for, and the
# rungs it does not round away sit close enough to be indistinguishable. Widths
# derived from the slots themselves are exact, and there are fewer of them.
CLOSE = 1.25
SIZES = os.path.join(ROOT, "tools", "image-sizes.json")
# Families whose <img> src JS reassigns — the mosaic tiles, which turn over, and
# the collection cards, which cycle. Neither can sit in a <picture>: the sources
# win a later src assignment, so the element would freeze on its first pick.
# index.html tests for WebP once and rewrites the path instead, which means the
# derivative has to have a name the page can build without knowing the source's
# dimensions. So: one file per source, native size, WebP, called <stem>-x.webp.
# Native size because these are already authored near their display size — the
# tiles exactly so — which leaves format as the whole of the gain.
JS_FAMILIES = ("img/banner/", "img/banner-lg/", "img/collections/")
# The homepage cards are built in script as well, and they are the heaviest
# thing left on the page once the mosaic and the icons are dealt with. They
# share a directory with the footer icons and the logo, which are ordinary
# <picture> elements, so the two are told apart by the slot each was measured
# in rather than by a list of filenames that would rot the first time a card
# changed: a card fills 336px, nothing else there is close.
CARD_SLOT, CARD_WIDTH = 336, 672

def referenced():
    """Every raster a page names literally, plus the JS families by directory.

    The families have to be walked rather than grepped: their paths are built a
    piece at a time ("img/banner" + (lg ? "-lg" : "") + ...), so no literal path
    to a tile exists anywhere in the source to find."""
    found = set()
    # Directories a page names as a base constant. The pages write
    # const H = "/img/homepage/" and then H + m[1], where m[1] comes out of a
    # data array — so no literal path to the file exists to be found, the same
    # way the families' paths do not exist. Taking the whole directory costs
    # nothing: anything in it without a measured slot gets no derivative anyway.
    bases = set()
    for root, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "img", "onchain", "tools")]
        for f in names:
            if not f.endswith((".html", ".js")): continue
            s = io.open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
            for m in re.findall(r'=\s*"(/?img/[\w./-]*/)"', s):
                bases.add(m.lstrip("/"))
    for fam in tuple(JS_FAMILIES) + tuple(bases):
        for dp, _, fs in os.walk(os.path.join(ROOT, fam)):
            for f in fs:
                if f.lower().endswith((".jpg", ".jpeg", ".png")):
                    found.add(os.path.relpath(os.path.join(dp, f), ROOT))
    for root, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "img", "onchain", "tools")]
        for f in names:
            if not f.endswith((".html", ".js", ".css")): continue
            s = io.open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
            if 'http-equiv="refresh"' in s: continue
            for m in re.findall(r'["\'(]((?:/)?img/[\w./%-]+\.(?:jpg|jpeg|png))["\')]', s, re.I):
                found.add(m.lstrip("/"))
    return sorted(found)

def is_card(repo, table):
    return (repo.startswith("img/homepage/")
            and (table.get(repo) or {}).get("d") == CARD_SLOT)


def widths_for(repo, w0, table):
    """The rungs that correspond to a slot this image actually occupies.

    Every width here is some real slot at 1x, 2x or 3x, capped at the source.
    Building the whole ladder instead produced 68MB, most of it rungs no layout
    on the site ever asks for — a 2000px copy of a picture that is never wider
    than 336. An image on no measured page gets nothing and keeps its original."""
    if repo.startswith(JS_FAMILIES): return [w0]
    if is_card(repo, TABLE): return [min(w0, CARD_WIDTH)]
    slot = table.get(repo)
    if not slot: return []
    want = set()
    # 3x screens are phones, and a phone lays the page out at the mobile slot, so
    # the desktop slot never needs a 3x rung. Pairing every slot with every
    # density instead builds a 3000px copy of a picture that is 1040 at its
    # widest anywhere, which is where most of the first 52MB went.
    for s, densities in ((slot.get("d"), (1, 2)), (slot.get("m"), (2, 3))):
        if not s: continue
        for dpr in densities:
            want.add(min(w0, 16 * round(s * dpr / 16)))
    keep = []
    for w in sorted(want):                     # drop a rung the next one covers
        if keep and w < keep[-1] * CLOSE: keep[-1] = w
        else: keep.append(w)
    return keep

def derive(src, check):
    made, stale = 0, []
    full = os.path.join(ROOT, src)
    if not os.path.isfile(full): return 0, []
    try:
        with Image.open(full) as im:
            if getattr(im, "n_frames", 1) > 1: return 0, []      # animated
            w0, h0 = im.size
            alpha = im.mode in ("RGBA", "LA", "P") and "transparency" in im.info or im.mode in ("RGBA", "LA")
            base = im.convert("RGBA" if alpha else "RGB")
    except Exception as e:
        print("  ! skipped %s (%s)" % (src, e)); return 0, []
    stem = os.path.splitext(src)[0][4:]                          # drop "img/"
    for w in widths_for(src, w0, TABLE):
        h = max(1, round(h0 * w / w0))
        img = base if w == w0 else base.resize((w, h), Image.LANCZOS)
        js = src.startswith(JS_FAMILIES) or is_card(src, TABLE)
        for ext in ("webp",) if js else ("webp",) + (("avif",) if HAVE_AVIF else ()):
            tag = "x" if js else str(w)
            dst = os.path.join(ROOT, OUT, "%s-%s.%s" % (stem, tag, ext))
            if os.path.isfile(dst) and os.path.getmtime(dst) >= os.path.getmtime(full):
                continue
            if check:
                # only what a page can actually ask for: the rest are candidates
                # the rewriter has not taken up, and --prune clears those
                if dst in USED: stale.append(os.path.relpath(dst, ROOT))
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if ext == "webp":
                img.save(dst, "WEBP", quality=78, method=6)
            else:
                img.save(dst, "AVIF", quality=60)
            made += 1
    return made, stale

TABLE = {}
USED = set()

def usable():
    """Every derivative path some page can actually request."""
    import glob
    used = set()
    files = []
    for pat in ("*.html", "*.js", "*/*.html", "*/*.js", "*/*/*.html", "*/*/*/*.html"):
        files += glob.glob(os.path.join(ROOT, pat))
    for f in sorted(set(files)):
        if os.sep + "img" + os.sep in f or os.sep + "onchain" + os.sep in f: continue
        s = io.open(f, encoding="utf-8", errors="replace").read()
        for ss in re.findall(r'srcset="([^"]+)"', s):
            for c in ss.split(","):
                used.add(os.path.join(ROOT, c.strip().split()[0].lstrip("/")))
        for m in re.findall(r'\[([\d,\s]+)\]\.map\(w=>d\+"-"\+w', s):   # the icon rungs
            for w in re.findall(r"\d+", m):
                for d in glob.glob(os.path.join(ROOT, OUT, "homepage", "*-%s.*" % w)):
                    used.add(d)
    for fam in JS_FAMILIES:
        for dp, _, fs in os.walk(os.path.join(ROOT, OUT, fam[4:])):
            for fn in fs: used.add(os.path.join(dp, fn))
    for k in TABLE:
        if is_card(k, TABLE):
            used.add(os.path.join(ROOT, OUT, os.path.splitext(k)[0][4:] + "-x.webp"))
    return used


def prune():
    """Delete derivatives nothing on the site can ask for.

    A measured slot is not the same as a rewritten tag. Several galleries build
    their <img> in script from a base path, so tools/responsive-images.py never
    sees them and they keep their originals — but they are measured, so this
    would happily write a full set of derivatives for them and no page would
    ever request one. That was 27MB of the first 68MB.

    What can be asked for is: anything named in a srcset, the two JS families,
    and the fixed rungs index.html builds for the footer icons.
    """
    used = usable()
    gone = freed = 0
    for dp, _, fs in os.walk(os.path.join(ROOT, OUT)):
        for fn in fs:
            p = os.path.join(dp, fn)
            if p not in used:
                freed += os.path.getsize(p); os.remove(p); gone += 1
    for dp, ds, fs in os.walk(os.path.join(ROOT, OUT), topdown=False):
        if not ds and not fs:
            try: os.rmdir(dp)
            except OSError: pass
    print("  pruned unusable    : %d files, %.1f MB" % (gone, freed / 1048576))


def main():
    global TABLE, USED
    TABLE = json.load(io.open(SIZES)) if os.path.isfile(SIZES) else {}
    USED = usable()
    check = "--check" in sys.argv
    refs = referenced()
    made, stale = 0, []
    for r in refs:
        m, s = derive(r, check)
        made += m; stale += s
    print("  referenced rasters : %d" % len(refs))
    if check:
        print("  missing/stale      : %d" % len(stale))
        for m in stale[:10]: print("    " + m)
        return 1 if stale else 0
    print("  derivatives written: %d" % made)
    if "--prune" in sys.argv: prune()
    tot = sum(os.path.getsize(os.path.join(dp, f))
              for dp, _, fs in os.walk(os.path.join(ROOT, OUT)) for f in fs)
    print("  img/derived        : %.1f MB" % (tot / 1048576))
    return 0

if __name__ == "__main__":
    sys.exit(main())
