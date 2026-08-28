#!/usr/bin/env python3
"""Pack the whole byteGANs collection into per-kind chunks the page can draw.

    python3 tools/build-bytegans.py           # writes data/bytegans/*.json
    python3 tools/build-bytegans.py --check   # verify the page agrees with the chain

The collection is 1,111 works of eleven pixels square, and the entire thing —
every frame of every one — is about 1.2MB. That is the fact the page is built
on: this is a collection you can show completely rather than sample, and a
sample would misrepresent it, because what byteGANs *is* is the distribution.
You cannot see that twelve kinds exist, or that two of them have exactly one
member, from twenty-four tiles.

**Why chunks rather than the mirror files.** /onchain/bytegans/ already holds all
1,111 as separate SVGs, and pointing 1,111 <img> tags at them works — it is how
this was first tried. It costs 1,111 requests per visitor, and on GitHub Pages
requests are the constraint long before bytes are. Grouping the payloads by kind
brings that to twelve, one per section, each fetched only when its section comes
into view. A reader who stops after the opening downloads none of them.

Two smaller reasons fall out of it. The mirror files wrap each GIF in an SVG
element, about 150 bytes of boilerplate apiece that no longer has to be sent or
parsed. And the chunk can carry the titles alongside the artwork, so a tile can
name itself on hover without a second index.

The GIF bytes themselves are copied out of the mirror untouched — the mirror
holds the exact bytes tokenURI returns, and this reads them rather than
re-encoding, so what the page draws is what the contract stores.
"""
import base64, collections, io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIRROR = os.path.join(ROOT, "onchain", "bytegans")
TITLES = "/Users/ericandrewgreen/sovrn-onchain/data/onchain-titles.json"
OUT = os.path.join(ROOT, "data", "bytegans")
PAGE = os.path.join(ROOT, "curated", "bytegans", "index.html")

# The three the artist describes. Everything else is shown and counted but not
# explained, because the source says nothing about it and a plausible sentence
# per kind is exactly the invention this site is built to avoid.
NAMED = {
    "skullGAN": "Evolutionary Intelligence",
    "cyberGAN": "Artificial Intelligence",
    "octoGAN":  "Decentralized Intelligence",
}

def tile_px(count):
    """How large to draw one work of a kind, given how many there are.

    The rule is that rarity buys size. Nine hundred skulls at 128px would be a
    scroll with no shape to it, and a single kingGAN at 34px would be a speck
    you would never notice was alone. Sized this way each kind occupies a
    comparable, readable block, and the fact that a kind is rare arrives as a
    change in scale rather than as a number you have to read."""
    return 34 if count >= 200 else 42 if count >= 50 else 58 if count >= 15 else 92 if count >= 5 else 150

def load():
    t = json.load(io.open(TITLES, encoding="utf-8"))["collections"]["bytegans"]
    assert t["first_token"] == 1 and t["count"] == len(t["titles"])
    works = []
    for i, title in enumerate(t["titles"]):
        m = re.match(r"^(.*?)\s+(\w+GAN)\s+#(\d+)$", title)
        if not m:
            sys.exit("  title does not parse: %r" % title)
        works.append({"id": i + 1, "title": title, "mod": m.group(1),
                      "kind": m.group(2), "n": int(m.group(3))})
    return works

def gif_of(token):
    """The GIF as the contract stores it, lifted out of the mirror unchanged."""
    s = io.open(os.path.join(MIRROR, "%d.svg" % token), encoding="utf-8").read()
    m = re.search(r"base64,([^\"']+)", s)
    if not m:
        sys.exit("  no image payload in mirror file %d.svg" % token)
    return m.group(1)

def build():
    works = load()
    by = collections.OrderedDict()
    for w in works:
        by.setdefault(w["kind"], []).append(w)
    kinds = sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    os.makedirs(OUT, exist_ok=True)
    index, total_bytes = [], 0
    for kind, ws in kinds:
        # Within a kind, group by modifier — most common first, then by the
        # artist's own number. The modifiers are largely colour words, so this
        # bands each block into families instead of scattering them, and the
        # variety inside one kind becomes visible rather than looking like noise.
        freq = collections.Counter(w["mod"] for w in ws)
        ws = sorted(ws, key=lambda w: (-freq[w["mod"]], w["mod"], w["n"]))
        chunk = {"kind": kind, "count": len(ws),
                 "ids":    [w["id"] for w in ws],
                 "titles": [w["title"] for w in ws],
                 "gifs":   [gif_of(w["id"]) for w in ws]}
        name = kind.lower() + ".json"
        p = os.path.join(OUT, name)
        io.open(p, "w", encoding="utf-8").write(json.dumps(chunk, separators=(",", ":")))
        total_bytes += os.path.getsize(p)
        index.append({"kind": kind, "count": len(ws),
                      "share": round(100.0 * len(ws) / len(works), 1),
                      "tile": tile_px(len(ws)), "file": name,
                      "modifiers": len(freq),
                      "intelligence": NAMED.get(kind)})
    io.open(os.path.join(OUT, "index.json"), "w", encoding="utf-8").write(
        json.dumps({"total": len(works), "kinds": index}, indent=1))
    return works, index, total_bytes

def verify(works, index):
    """Re-read the chunks and prove each work still carries its own picture.

    Regrouping 1,111 things by kind and sorting them inside each group is
    exactly the operation that silently pairs the wrong image with the wrong
    name, and nothing about the result would look wrong: every tile would still
    be a real byteGAN and every title a real title. So the mapping is checked
    rather than assumed — for every one of the 1,111, not a sample."""
    by_id = {w["id"]: w for w in works}
    seen, bad = set(), []
    for e in index:
        d = json.load(io.open(os.path.join(OUT, e["file"]), encoding="utf-8"))
        if len(d["ids"]) != e["count"] or len(d["gifs"]) != e["count"]:
            bad.append("%s: chunk holds %d entries, expected %d" % (e["kind"], len(d["ids"]), e["count"]))
            continue
        for i, tok in enumerate(d["ids"]):
            w = by_id.get(tok)
            if w is None:            bad.append("token %s is not in the collection" % tok)
            elif w["kind"] != e["kind"]: bad.append("token %d is a %s, filed under %s" % (tok, w["kind"], e["kind"]))
            elif d["titles"][i] != w["title"]: bad.append("token %d: chunk says %r, chain says %r" % (tok, d["titles"][i], w["title"]))
            elif d["gifs"][i] != gif_of(tok): bad.append("token %d carries another work's image" % tok)
            seen.add(tok)
    missing = set(by_id) - seen
    if missing:
        bad.append("%d works are in no chunk, e.g. %s" % (len(missing), sorted(missing)[:5]))
    return bad

def check(works, index):
    """The page states each kind's count in its own markup, so that the sections
    exist before any script runs. That is a second copy of a fact, so it is
    checked rather than trusted."""
    html = io.open(PAGE, encoding="utf-8").read()
    bad = []
    for e in index:
        m = re.search(r'data-kind="%s"\s+data-count="(\d+)"' % e["kind"], html)
        if not m:
            bad.append("%s: no section in the page" % e["kind"])
        elif int(m.group(1)) != e["count"]:
            bad.append("%s: page says %s, chain says %d" % (e["kind"], m.group(1), e["count"]))
    for k in re.findall(r'data-kind="(\w+)"', html):
        if k not in {e["kind"] for e in index}:
            bad.append("%s: section in the page for a kind that does not exist" % k)
    n = re.search(r'data-total="(\d+)"', html)
    if not n or int(n.group(1)) != len(works):
        bad.append("total: page says %s, chain says %d" % (n and n.group(1), len(works)))
    return bad

def main():
    if not os.path.isdir(MIRROR):
        sys.exit("  missing the mirror at %s" % MIRROR)

    # --check must NOT rebuild first. Writing the files and then verifying what
    # was just written can only catch a bug in this script, never drift in what
    # is actually shipped — and it reports success while a corrupted chunk sits
    # in the repo, which is worse than having no check at all. Found by swapping
    # two images by hand and watching it pass.
    checking = "--check" in sys.argv
    if checking:
        works = load()
        index = json.load(io.open(os.path.join(OUT, "index.json"), encoding="utf-8"))["kinds"]
        print("  checking the %d chunks already in %s" % (len(index), os.path.relpath(OUT, ROOT)))
    else:
        works, index, nbytes = build()
        print("  %d works, %d kinds -> %s" % (len(works), len(index), os.path.relpath(OUT, ROOT)))
        for e in index:
            print("    %-10s %4d  %4.1f%%  %3dpx  %2d modifiers%s"
                  % (e["kind"], e["count"], e["share"], e["tile"], e["modifiers"],
                     "  " + e["intelligence"] if e["intelligence"] else ""))
        print("  %.2f MB across %d chunks" % (nbytes / 1048576.0, len(index)))

    if checking:
        bad = verify(works, index)
        if bad:
            print("\n  the chunks do not match the chain:")
            for b in bad[:12]: print("    " + b)
            sys.exit(1)
        print("  every one of the %d works carries its own title and its own image" % len(works))
        bad = check(works, index)
        if bad:
            print("\n  the page disagrees with the chain:")
            for b in bad: print("    " + b)
            sys.exit(1)
        print("  page agrees with the chain: every kind, every count, the total")

if __name__ == "__main__":
    main()
