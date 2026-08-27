#!/usr/bin/env python3
"""Wrap every static <img> on the site in a <picture> offering AVIF and WebP.

    python3 tools/responsive-images.py --dry     # report, change nothing
    python3 tools/responsive-images.py           # rewrite in place
    python3 tools/responsive-images.py --check   # non-zero exit if any img is unwrapped

Run tools/build-images.py first — this only offers a derivative that exists.

The original <img> survives untouched inside the <picture>, keeping its src, its
classes and its handlers. That matters more here than it usually does: .vt-lead
carries the view-transition name, several tags carry an onerror fallback, and
share cards read the img. A browser with no AVIF or WebP, or a request for a file
we did not derive, lands on exactly the file it fetches today.

sizes comes from tools/image-sizes.json, measured off the live pages rather than
guessed. sizes is the attribute that decides which rung the browser picks; a
wrong one silently either ships the largest file to a phone or a blurry one to a
desktop, and neither shows up as an error.
"""
import io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DERIVED = os.path.join(ROOT, "img", "derived")
SIZES = os.path.join(ROOT, "tools", "image-sizes.json")

# An <img> whose src JS reassigns must stay bare. Inside a <picture> the
# <source> elements win a later src assignment, so the element would freeze on
# whatever the sources first resolved to — the lightbox would open the same
# picture every time, and the homepage cards would stop turning over. Two shapes
# of that exist here:
#   * every JS-driven img on this site carries an id (hero, lbi, art, pf, bg,
#     f1..f3) and is reached as $("id").src = ...
#   * the homepage crossfade pairs are .card[data-p] .im img, which have no id
# Skipping an image only means it keeps the file it fetches today.
ID = re.compile(r'\bid\s*=\s*"[^"]+"', re.I)

IMG = re.compile(r'<img((?:\s+[\w:.-]+(?:\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+))?)*)\s*/?>', re.I)
SRC = re.compile(r'\bsrc\s*=\s*"([^"]+)"', re.I)

def rungs(repo_path):
    """Available derivative widths for a source image, per format."""
    stem, _ = os.path.splitext(repo_path)
    stem = stem[4:] if stem.startswith("img/") else stem
    d = os.path.join(DERIVED, os.path.dirname(stem))
    base = os.path.basename(stem)
    got = {"avif": [], "webp": []}
    if not os.path.isdir(d): return got
    for f in os.listdir(d):
        m = re.match(re.escape(base) + r"-(\d+)\.(avif|webp)$", f)
        if m: got[m.group(2)].append(int(m.group(1)))
    for k in got: got[k].sort()
    return got

def srcset(repo_path, ws, ext):
    stem = os.path.splitext(repo_path)[0]
    stem = stem[4:] if stem.startswith("img/") else stem
    return ", ".join("/img/derived/%s-%d.%s %dw" % (stem, w, ext, w) for w in ws)

def sizes_for(repo_path, table):
    m = table.get(repo_path)
    if not m: return None
    desk, mob = m.get("d"), m.get("m")
    if not desk: return None
    if mob and abs(mob - desk) > 8:
        return "(max-width: 700px) %dpx, %dpx" % (mob, desk)
    return "%dpx" % desk

def main():
    dry = "--dry" in sys.argv
    check = "--check" in sys.argv
    table = json.load(io.open(SIZES)) if os.path.isfile(SIZES) else {}
    wrapped = skipped = unwrapped = 0
    reasons = {}
    for root, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "img", "onchain", "tools")]
        for f in names:
            if not f.endswith(".html"): continue
            p = os.path.join(root, f)
            s = orig = io.open(p, encoding="utf-8").read()
            if 'http-equiv="refresh"' in s: continue
            out, last = [], 0
            for m in IMG.finditer(s):
                tag, attrs = m.group(0), m.group(1)
                before = s[max(0, m.start() - 200):m.start()]
                if "<picture" in before and "</picture" not in before:
                    skipped += 1; continue                      # already wrapped
                if ID.search(attrs):
                    unwrapped += 1; reasons.setdefault("has id (JS-driven)", []).append(f); continue
                if 'class="im"' in before[-120:]:
                    unwrapped += 1; reasons.setdefault("crossfade pair", []).append(f); continue
                sm = SRC.search(attrs)
                if not sm: continue
                src = sm.group(1)
                # a src the page assembles at runtime is not a path we can resolve
                if not re.search(r"\.(jpe?g|png)$", src, re.I) or re.search(r"[{}'+]", src):
                    continue
                repo = src.lstrip("/")
                got = rungs(repo)
                if not got["webp"]:
                    unwrapped += 1; reasons.setdefault("no derivative", []).append(src); continue
                sz = sizes_for(repo, table)
                if not sz:
                    unwrapped += 1; reasons.setdefault("unmeasured", []).append(src); continue
                srcs = ""
                for ext in ("avif", "webp"):
                    if got[ext]:
                        srcs += '<source type="image/%s" srcset="%s" sizes="%s">' % (
                            ext, srcset(repo, got[ext], ext), sz)
                out.append((m.start(), m.end(), "<picture>" + srcs + tag + "</picture>"))
                wrapped += 1
            if out and not (dry or check):
                buf, last = [], 0
                for a, b, rep in out:
                    buf.append(s[last:a]); buf.append(rep); last = b
                buf.append(s[last:])
                io.open(p, "w", encoding="utf-8").write("".join(buf))
    print("  wrapped   : %d" % wrapped)
    print("  already   : %d" % skipped)
    print("  left alone: %d" % unwrapped)
    for k, v in reasons.items():
        print("    %-14s %d  e.g. %s" % (k, len(v), ", ".join(sorted(set(v))[:3])))
    return 1 if (check and wrapped) else 0

if __name__ == "__main__":
    sys.exit(main())
