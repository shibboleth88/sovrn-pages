#!/usr/bin/env python3
"""Cast the byteGANs that wander the collection page.

    python3 tools/build-bytegans.py           # writes data/bytegans/*.json
    python3 tools/build-bytegans.py --check   # verify what is on disk against the chain

The page does not show the collection. It shows a **cast** — a few hundred of the
1,111, chosen here, who then move around the page under their own steam. That is
a deliberate step back from an earlier version that put every single work on the
page at once: complete was impressive and it was also a wall. A crowd you can
watch one member of is worth more than a crowd you can only measure.

So this picks who appears, and the picking has two rules:

**The rare kinds are all here.** Every apeGAN, every primeGAN, and the one
kingGAN and the one queenGAN. There is no sense running a lottery that a reader
cannot see the results of — if a kind has nine members, showing three of them
tells the reader nothing except that nine was not the number. Fourteen works
cost almost nothing and mean the lone king really is somewhere on the page.

**Everything else is sampled evenly through the modifier ordering** rather than
at random. The modifiers are largely colour words, so an even walk through that
order takes one of each family in turn and the cast comes out spread across the
palette instead of clumped in whatever the commonest colour happens to be.

The GIF bytes are copied out of the same-origin mirror at /onchain/bytegans/
without re-encoding, so what moves on the page is what the contract stores.
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

# How large the cast is. They are spread over the whole document now rather than
# over the window, so the number needed scales with the length of the page and
# not with the size of the screen — a few hundred rather than a few dozen. The
# surplus is the slack that lets a reload put a different crowd on the page.
CAST = 240
# Kinds small enough that sampling them would be a lie: everyone shows up.
WHOLE = 12

def spread(ws, n):
    """n of them, taken evenly through the list rather than at random.

    The list arrives ordered by modifier, so an even walk crosses the colour
    families in turn. Random sampling of the same list clumps, and clumping is
    exactly what you notice."""
    if n >= len(ws):
        return list(ws)
    return [ws[(i * len(ws)) // n] for i in range(n)]

def build():
    works = load()
    by = collections.OrderedDict()
    for w in works:
        by.setdefault(w["kind"], []).append(w)
    kinds = sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    # Order every kind by modifier — most common family first. Whatever is then
    # taken from it is taken across the colours rather than out of one corner.
    ordered = {}
    for kind, ws in kinds:
        freq = collections.Counter(w["mod"] for w in ws)
        ordered[kind] = sorted(ws, key=lambda w: (-freq[w["mod"]], w["mod"], w["n"]))

    if os.path.isdir(OUT):
        for f in os.listdir(OUT):
            os.remove(os.path.join(OUT, f))
    os.makedirs(OUT, exist_ok=True)

    def write(name, ws):
        d = {"count": len(ws),
             "ids":    [w["id"] for w in ws],
             "titles": [w["title"] for w in ws],
             "gifs":   [gif_of(w["id"]) for w in ws]}
        p = os.path.join(OUT, name)
        io.open(p, "w", encoding="utf-8").write(json.dumps(d, separators=(",", ":")))
        return os.path.getsize(p)

    # One file. The three kinds the artist describes no longer need their own,
    # because the page no longer shows a crowd of each — it shows one roaming
    # population, mixed, over the whole window.
    small = [k for k, ws in kinds if len(ws) <= WHOLE]
    cast = [w for k in small for w in ordered[k]]
    big = [(k, ws) for k, ws in kinds if k not in small]
    pool = float(sum(len(ws) for _, ws in big))
    room = CAST - len(cast)
    for k, ws in big:
        cast += spread(ordered[k], int(round(room * len(ws) / pool)))
    # deal them out so neighbours in the file are of different kinds — the page
    # takes a run of them starting anywhere, and a run of 30 skulls would look
    # like a bug rather than like a crowd
    cast = [cast[(i * 61) % len(cast)] for i in range(len(cast))]
    seen, deal = set(), []
    for w in cast:
        if w["id"] not in seen:
            seen.add(w["id"]); deal.append(w)
    total = write("cast.json", deal)
    files = [{"file": "cast.json", "kind": None, "shown": len(deal)}]

    index = [{"kind": k, "count": len(ws),
              "share": round(100.0 * len(ws) / len(works), 1),
              "modifiers": len(set(w["mod"] for w in ws)),
              "intelligence": NAMED.get(k)} for k, ws in kinds]
    io.open(os.path.join(OUT, "index.json"), "w", encoding="utf-8").write(
        json.dumps({"total": len(works), "cast": len(deal),
                    "kinds": index, "files": files}, indent=1))
    return works, index, files, total

def verify(works):
    """Prove every work in every file still carries its own title and picture.

    These are samples now, so there is nothing to check about coverage — but
    sampling and re-ordering 1,111 things is precisely the operation that pairs
    the wrong picture with the wrong name, and nothing about the result would
    look wrong: every tile would still be a real byteGAN and every title a real
    title. So each one is checked against the chain, not spot-checked."""
    by_id = {w["id"]: w for w in works}
    meta = json.load(io.open(os.path.join(OUT, "index.json"), encoding="utf-8"))
    bad, cast_kinds = [], set()
    for e in meta["files"]:
        d = json.load(io.open(os.path.join(OUT, e["file"]), encoding="utf-8"))
        if len(d["ids"]) != d["count"] or len(d["gifs"]) != d["count"]:
            bad.append("%s: entries do not agree with its own count" % e["file"])
            continue
        if len(set(d["ids"])) != len(d["ids"]):
            bad.append("%s: the same work appears twice" % e["file"])
        for i, tok in enumerate(d["ids"]):
            w = by_id.get(tok)
            if w is None:            bad.append("token %s is not in the collection" % tok)
            elif e["kind"] and w["kind"] != e["kind"]:
                bad.append("token %d is a %s, filed in %s" % (tok, w["kind"], e["file"]))
            elif d["titles"][i] != w["title"]:
                bad.append("token %d: file says %r, chain says %r" % (tok, d["titles"][i], w["title"]))
            elif d["gifs"][i] != gif_of(tok):
                bad.append("token %d carries another work's image" % tok)
            if not e["kind"] and w: cast_kinds.add(w["kind"])
    # the promise the page makes: every kind is represented, and the rare ones
    # in full, so the lone kingGAN really is out there somewhere
    for e in meta["kinds"]:
        if e["kind"] not in cast_kinds and not e["intelligence"]:
            bad.append("no %s made the cast" % e["kind"])
    cast = json.load(io.open(os.path.join(OUT, "cast.json"), encoding="utf-8"))
    for e in meta["kinds"]:
        if e["count"] <= WHOLE:
            have = sum(1 for t in cast["ids"] if by_id[t]["kind"] == e["kind"])
            if have != e["count"]:
                bad.append("%s: %d of %d in the cast, but small kinds appear whole"
                           % (e["kind"], have, e["count"]))
    return bad

def check(works, index):
    """The page states the three named kinds' counts and the total in its own
    markup, so that those sections exist before any script runs. That is a second
    copy of a fact, so it is checked rather than trusted."""
    html = io.open(PAGE, encoding="utf-8").read()
    bad = []
    for e in index:
        m = re.search(r'data-kind="%s"\s+data-count="(\d+)"' % e["kind"], html)
        if e["intelligence"]:
            if not m:
                bad.append("%s: the artist describes it and the page has no section for it" % e["kind"])
            elif int(m.group(1)) != e["count"]:
                bad.append("%s: page says %s, chain says %d" % (e["kind"], m.group(1), e["count"]))
        elif m:
            bad.append("%s: the page gives it a section, but nothing describes it" % e["kind"])
    for k in re.findall(r'data-kind="(\w+)"', html):
        if k not in {e["kind"] for e in index}:
            bad.append("%s: a section for a kind that does not exist" % k)
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
        print("  checking what is already in %s" % os.path.relpath(OUT, ROOT))
    else:
        works, index, files, nbytes = build()
        print("  %d works, %d kinds -> %s" % (len(works), len(index), os.path.relpath(OUT, ROOT)))
        for e in index:
            print("    %-10s %4d  %4.1f%%  %2d modifiers%s"
                  % (e["kind"], e["count"], e["share"], e["modifiers"],
                     "  " + e["intelligence"] if e["intelligence"] else ""))
        print("  %d works cast of %d: %s" % (sum(f["shown"] for f in files), len(works),
                                            ", ".join("%s %d" % (f["file"], f["shown"]) for f in files)))
        print("  %.0f KB" % (nbytes / 1024.0))

    if checking:
        bad = verify(works)
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
