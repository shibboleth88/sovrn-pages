#!/usr/bin/env python3
"""Prove the site is whole: every public URL answers, every asset resolves.

    python3 tools/check-site.py --urls                        # the live sovrn.art contract
    python3 tools/check-site.py --assets http://127.0.0.1:8000/   # a served tree

Written before the GitHub Pages migration and run against the site as it stands,
so that when it passes on the restructured tree that means something. A checker
first written to describe the new arrangement would only ever agree with itself.

--urls walks the public URLs sovrn.art is expected to serve. That list is the
contract: anything that stops answering is an inbound link broken somewhere we
cannot see, so it is written out here rather than discovered by crawling.

--assets crawls a served copy and resolves every src and href on every page,
honouring <base>, and reports anything that does not answer 200. Point it at a
local server for the tree you are about to publish. Relative paths are the whole
risk in moving flat files into directories, and this is what catches them.

**What it cannot see.** Paths assembled in script are skipped, because there is no
honest way to resolve `I + x[3]` without running the page. That covers real
families — home.html builds its collection cards and its 223 mosaic tiles that
way, and share.js builds the panel pools from BASE. The named ones are asserted
explicitly in RUNTIME below, and `<base href="/">` fixes the rest by construction,
but after any restructure the homepage still wants opening in a browser to watch
the mosaic and the cards actually arrive. A green run here is necessary and not
sufficient.
"""
import argparse, os, re, sys, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "sovrn-site-check/1.0"}

# The public URLs sovrn.art serves. Keep this in step with the site by hand: it is
# a statement of intent, not an observation, which is the point of it.
PUBLIC = """
/ /about /marketplaces /shareable /museums /collections /curated /exhibitions
/cents /cents/inquiries /cents/artist-obituary /cents/cents-in-tachens-on-nfts
/curated/ai-spaceships /curated/latent-couture /curated/mementi
/curated/painting-with-fire /curated/painting-with-fire/gan-timeline
/curated/perimeter-town /curated/possibility-spaces /curated/reflection
/curated/seasons-of-mobility /curated/sightseers /curated/wunderkammer
/collections/abs-collection /collections/fransisco-carolinum /collections/lacma
/collections/moca
/exhibitions/bankable /exhibitions/christies-augmented-intelligence
/exhibitions/fc-3-blockchains /exhibitions/kindl /exhibitions/marfa-popup
/exhibitions/screens-contextualized /exhibitions/ucca /exhibitions/vitra
/shareable/share-reflection /shareable/share-wunderkammer /shareable/share-bytegans
/curated/bytegans /curated/cope-vol-1 /curated/rabbit-takeover
/cents/project-description /cents/makes-cents /cents/trait-council
""".split()

# Those last six were missing from the first draft of this list, because it was
# derived by grepping the repo for sovrn.art URLs and nothing in the repo links to
# them — they are reached only from Sites pages, which are outside it. That is
# exactly the failure this list exists to prevent, so: the contract is what the
# site serves, not what the repo happens to mention.

# Paths share.js and shareables.js build at runtime, which no HTML parse will see.
RUNTIME = ["onchain-titles.json", "onchain-traits.json",
           "img/collections/reflection/reflection-02.svg",
           "img/wunderkammer-works/wunderkammer-08.svg",
           "img/bytegans/bytegan-15.svg",
           "share.css", "share.js", "shareables.js"]

SKIP = re.compile(r"^(#|mailto:|tel:|data:|javascript:)", re.I)
ATTR = re.compile(r'(?:src|href)="([^"]+)"')
BASE = re.compile(r'<base[^>]+href="([^"]+)"', re.I)


def fetch(url, method="GET"):
    req = urllib.request.Request(url, headers=UA, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read() if method == "GET" else b""
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:                                      # noqa: BLE001
        return 0, str(e).encode()


def check_urls(host):
    """Every public URL must answer with a real page.

    A directory with no index.html is the trap here. `python -m http.server`
    answers it with a generated listing and a cheerful 200, while GitHub Pages
    returns 404 — so a tree can pass locally and be broken in production. The
    listing is recognisable and is treated as the failure it is.
    """
    print(f"  {len(PUBLIC)} public URLs on {host}")
    bad = []
    def one(p):
        code, body = fetch(host.rstrip("/") + p + ("/" if "127.0.0.1" in host and p != "/" else ""), "GET")
        listing = b"Directory listing for" in body
        return p, code, listing
    with ThreadPoolExecutor(max_workers=8) as pool:
        for p, code, listing in pool.map(one, PUBLIC):
            if code != 200:
                bad.append((p, code))
                print(f"    {code}  {p}")
            elif listing:
                bad.append((p, "listing"))
                print(f"    no index.html  {p}   (a directory listing, which Pages 404s)")
            elif b"This page has moved" in body:
                # A stub at <name>.html shadows /<name>: Pages strips .html when
                # resolving an extensionless request and prefers the file to the
                # directory. The stub then points back at itself — a redirect loop,
                # and both it and the real page answer 200, so status alone is blind
                # to it. This is how /cents stopped opening.
                bad.append((p, "stub"))
                print(f"    a redirect stub  {p}   (shadowing its own page — loop)")
    # The misspelling is the live URL and correcting it 404s (NOTES.md).
    if not any(p == "/collections/fransisco-carolinum" for p in PUBLIC):
        bad.append(("fransisco-carolinum missing from the contract", 0))
        print("    the Francisco Carolinum URL must keep its misspelling")
    print(f"  {len(PUBLIC) - len(bad)}/{len(PUBLIC)} answered")
    return bad


def check_assets(base_url):
    pages, seen_assets, bad = [], {}, []
    entry = [base_url.rstrip("/") + "/" + n for n in
             sorted(f for f in os.listdir(ROOT) if f.endswith(".html"))]
    # A restructured tree has index.html inside directories; find those too.
    for dirpath, _dirs, files in os.walk(ROOT):
        if ".git" in dirpath or "/img" in dirpath:
            continue
        for f in files:
            if f == "index.html":
                rel = os.path.relpath(os.path.join(dirpath, f), ROOT)
                entry.append(base_url.rstrip("/") + "/" + rel.replace(os.sep, "/"))
    entry = sorted(set(entry))

    print(f"  crawling {len(entry)} pages at {base_url}")
    for page in entry:
        code, body = fetch(page)
        if code != 200:
            bad.append((page, code)); print(f"    {code}  {page}"); continue
        text = body.decode("utf-8", "replace")
        pages.append(page)
        m = BASE.search(text)
        base_for_page = urllib.parse.urljoin(page, m.group(1)) if m else page
        for raw in ATTR.findall(text):
            if SKIP.match(raw) or "://" in raw or raw.startswith("//"):
                continue
            if "'" in raw or "+" in raw:        # assembled in script; not resolvable here
                continue
            seen_assets.setdefault(urllib.parse.urljoin(base_for_page, raw), page)

    for rel in RUNTIME:
        seen_assets.setdefault(base_url.rstrip("/") + "/" + rel, "(runtime)")

    print(f"  resolving {len(seen_assets)} distinct assets")
    def one(u):
        code, _ = fetch(u, "HEAD")
        if code in (0, 405, 501):                  # some servers dislike HEAD
            code, _ = fetch(u, "GET")
        return u, code
    with ThreadPoolExecutor(max_workers=12) as pool:
        for u, code in pool.map(one, list(seen_assets)):
            if code != 200:
                bad.append((u, code))
                print(f"    {code}  {u}   <- from {seen_assets[u]}")
    print(f"  {len(seen_assets) - len([b for b in bad if b[0] in seen_assets])}"
          f"/{len(seen_assets)} assets resolved")
    return bad


def check_mirror():
    """share.js must reach the artwork by a path that survives being served at root."""
    js = open(os.path.join(ROOT, "share.js"), encoding="utf-8").read()
    m = re.search(r'var ART = ([^;]+);', js)
    if not m:
        print("    share.js: no ART definition found"); return [("ART", 0)]
    expr = m.group(1).strip()
    print(f"    share.js ART = {expr}")
    if '"../sovrn-onchain/"' in expr:
        print("      relative — correct only while pages sit under /sovrn-pages/.")
        print("      Must become absolute or root-relative before cutover.")
        return []          # a warning today, an error after the move
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", nargs="?", const="https://www.sovrn.art",
                    help="check the public URL contract against this host")
    ap.add_argument("--assets", metavar="BASE_URL",
                    help="crawl a served tree and resolve every asset")
    a = ap.parse_args()
    if not a.urls and not a.assets:
        ap.error("give --urls and/or --assets BASE_URL")

    bad = []
    if a.urls:
        print("\nPublic URLs")
        bad += check_urls(a.urls)
    if a.assets:
        print("\nAssets")
        bad += check_assets(a.assets)
        print("\nMirror")
        bad += check_mirror()

    print("\n" + ("site check: all good" if not bad else f"site check: {len(bad)} PROBLEM(S)"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
