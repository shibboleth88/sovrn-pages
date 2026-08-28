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
import argparse, glob, io, os, re, sys, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "sovrn-site-check/1.0"}

# The public URLs sovrn.art serves. Keep this in step with the site by hand: it is
# a statement of intent, not an observation, which is the point of it.
PUBLIC = """
/ /about /marketplaces /shareable /museums /collections /curated /exhibitions
/cents /cents/inquiries /cents/artist-obituary /cents/taschen /cents/block-839969
/contact /home /curated/cents
/curated/ai-spaceships /curated/latent-couture /curated/mementi
/curated/painting-with-fire /curated/painting-with-fire/gan-timeline
/curated/perimeter-town /curated/possibility-spaces /curated/reflection /curated/reflection/on-chain
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
ATTR = re.compile(r'(?:src|href|poster)="([^"]+)"')
# Banners are a url() in a style attribute, not a src, so a src/href sweep never
# saw them: eight collection pages could point their header at a missing file, or
# at another collection's, and every check here would still pass. It is not a
# hypothetical -- /curated/sightseers shipped Perimeter Town's banner.
CSSURL = re.compile(r'url\(\s*["\']?([^"\')]+)["\']?\s*\)')
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
        stub = b"This page has moved" in body
        target = None
        if stub:
            m = re.search(rb'url=([^"\']+)', body)
            if m:
                target = m.group(1).decode("utf-8", "replace").strip()
        return p, code, listing, stub, target
    with ThreadPoolExecutor(max_workers=8) as pool:
        for p, code, listing, stub, target in pool.map(one, PUBLIC):
            if code != 200:
                bad.append((p, code))
                print(f"    {code}  {p}")
            elif listing:
                bad.append((p, "listing"))
                print(f"    no index.html  {p}   (a directory listing, which Pages 404s)")
            elif stub and (target or "").rstrip("/") == p.rstrip("/"):
                # A stub at <name>.html shadows /<name>: Pages strips .html when
                # resolving an extensionless request and prefers the file to the
                # directory. The stub then points back at itself — a redirect loop,
                # and both it and the real page answer 200, so status alone is blind
                # to it. This is how /cents stopped opening.
                #
                # Pointing somewhere else is not that. Some URLs in the contract are
                # meant to be stubs — /home is the Sites homepage alias and /curated/
                # cents a second route onto /cents — so the test is whether the stub
                # names itself, not whether it is a stub.
                bad.append((p, "stub"))
                print(f"    a redirect stub  {p}   (points at itself — loop)")
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
        for raw in ATTR.findall(text) + CSSURL.findall(text):
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



def check_files():
    """Resolve the URL contract against the working tree, with no network.

    This is the pre-merge gate: it answers "would this tree serve the contract?"
    before anything is published, which the live checks cannot do by definition.

    It resolves the way GitHub Pages does, and the order is the whole point.
    For an extensionless request Pages strips/appends `.html` and **prefers the
    file to the directory** — so with both `cents.html` and `cents/index.html`
    present, `/cents` is served by the file. That is precisely how /cents once
    became an infinite redirect: the file was a stub pointing back at /cents.
    Resolving in any other order would agree with itself and miss it.
    """
    bad = []
    for path in PUBLIC:
        rel = path.strip("/")
        if not rel:
            cands = ["index.html"]
        else:
            cands = [rel + ".html", os.path.join(rel, "index.html")]

        found = [c for c in cands if os.path.isfile(os.path.join(ROOT, c))]
        if not found:
            bad.append((path, "missing"))
            print(f"    no file serves  {path}   (looked for {' then '.join(cands)})")
            continue

        served = found[0]                       # Pages takes the first match
        body = io.open(os.path.join(ROOT, served), encoding="utf-8", errors="replace").read()

        if "This page has moved" in body:
            m = re.search(r'url=([^"\']+)', body)
            target = (m.group(1).strip() if m else "")
            if target.rstrip("/") == path.rstrip("/"):
                bad.append((path, "loop"))
                print(f"    redirect loop   {path}   ({served} points at itself)")
                continue
            if len(found) > 1:
                bad.append((path, "shadow"))
                print(f"    {served} shadows {found[1]} and redirects away — "
                      f"{path} never reaches its page")
                continue

    print(f"  {len(PUBLIC) - len(bad)}/{len(PUBLIC)} resolve in the tree")
    return bad



def check_local_assets():
    """Every image a page builds from a base constant must exist on disk.

    The pages overwhelmingly write their image paths as `const R = "/img/fc/"`
    and then `R + "reflection_fc.jpg"`, which no HTML parse resolves and no
    crawl of the live site sees unless that particular image happens to be in
    the DOM at the moment it is crawled. That is not a hypothetical: the
    Francisco Carolinum page shows one work at a time, so a crawl found one
    image, reported no broken images, and ten missing files went unnoticed.

    Resolving the concatenation offline is the only honest check, and it is
    cheap because the idiom is consistent.
    """
    import glob
    bad = []
    files = []
    for pat in ("*.html", "*.js", "*/*.html", "*/*.js", "*/*/*.html", "*/*/*/*.html"):
        files += glob.glob(os.path.join(ROOT, pat))

    base_re = re.compile(r'(?:const|var|let)?\s*(\w+)\s*=\s*"(/?img/[^"]*/)"')
    use_re = re.compile(r'\b(\w+)\s*\+\s*"([^"]+\.(?:jpg|jpeg|png|gif|svg|webp|mp4))"', re.I)

    for f in sorted(set(files)):
        if os.sep + "onchain" + os.sep in f or os.sep + "img" + os.sep in f:
            continue
        text = io.open(f, encoding="utf-8", errors="replace").read()
        bases = dict(base_re.findall(text))
        if not bases:
            continue
        for name, tail in use_re.findall(text):
            base = bases.get(name)
            if not base:
                continue
            rel = (base + tail).lstrip("/")
            rel = urllib.parse.unquote(rel)
            if not os.path.isfile(os.path.join(ROOT, rel)):
                bad.append((os.path.relpath(f, ROOT), rel))
                print(f"    missing  {rel}   (built in {os.path.relpath(f, ROOT)})")

    print(f"  {len(bad)} missing of the images pages assemble from a base path")
    return bad


def check_banners():
    """Every url() a page names must be a file in the tree.

    This is the offline half of the CSSURL sweep, and it is the half that runs in
    CI. It exists because a banner is the one image on this site that nothing
    checked: not a `src`, not in a `<picture>`, not assembled from a base path.
    /curated/sightseers spent its whole life pointing at Perimeter Town's key art
    and every run here was green, because no check had ever resolved a hero.

    A wrong file is still beyond this -- only a person can see that a banner
    belongs to another collection -- but a missing one is not, and the two fail
    the same way to a visitor: a header with no artwork in it.
    """
    import glob
    bad = []
    files = []
    for pat in ("*.html", "*/*.html", "*/*/*.html", "*/*/*/*.html"):
        files += glob.glob(os.path.join(ROOT, pat))

    seen = 0
    for f in sorted(set(files)):
        if os.sep + "onchain" + os.sep in f:
            continue
        text = io.open(f, encoding="utf-8", errors="replace").read()
        based = bool(BASE.search(text))
        for raw in CSSURL.findall(text):
            if SKIP.match(raw) or "://" in raw or raw.startswith("//"):
                continue
            # <base href="/"> makes a bare path root-relative; without one it is
            # relative to the page. Getting this backwards is the whole risk in
            # a tree of directories, so resolve it the way the browser does.
            if raw.startswith("/") or based:
                rel = raw.lstrip("/")
            else:
                rel = os.path.relpath(
                    os.path.normpath(os.path.join(os.path.dirname(f), raw)), ROOT)
            seen += 1
            if not os.path.isfile(os.path.join(ROOT, urllib.parse.unquote(rel))):
                bad.append((os.path.relpath(f, ROOT), raw))
                print(f"    missing  {raw}   (named by {os.path.relpath(f, ROOT)})")

    print(f"  {seen - len(bad)}/{seen} url() targets resolve in the tree")
    return bad


def check_srcsets():
    """Every file a <picture> offers must be on disk, and so must every -x.webp
    the two JS families construct.

    A missing srcset entry is the quietest failure on the site: the browser
    simply picks another candidate, or falls through to the <img>, and the page
    looks correct while shipping the original file it was meant to replace. The
    JS families are worse — there is no fallback there, so a missing -x.webp is
    a broken image for every visitor whose browser takes WebP.
    """
    import glob
    bad = []
    files = []
    for pat in ("*.html", "*.js", "*/*.html", "*/*.js", "*/*/*.html", "*/*/*/*.html"):
        files += glob.glob(os.path.join(ROOT, pat))
    seen = set()
    for f in sorted(set(files)):
        if os.sep + "onchain" + os.sep in f or os.sep + "img" + os.sep in f:
            continue
        text = io.open(f, encoding="utf-8", errors="replace").read()
        for ss in re.findall(r'srcset="([^"]+)"', text):
            # index.html builds one srcset in script, so the literal text here is
            # a fragment of JS rather than a path. A candidate carrying a quote or
            # a + is being concatenated at runtime and cannot be resolved offline.
            if re.search(r"""["'+]""", ss): continue
            for cand in ss.split(","):
                u = cand.strip().split()[0]
                if u.startswith("/"): u = u[1:]
                if u in seen: continue
                seen.add(u)
                if not os.path.isfile(os.path.join(ROOT, u)):
                    bad.append("missing srcset target %s (%s)" % (u, os.path.relpath(f, ROOT)))
    # The footer icons: index.html builds their <picture> in script, so the
    # loop above deliberately skips that srcset and it would otherwise go
    # unchecked — a missing rung there is a broken image, not a quiet fallback.
    # The rung list is read from the page so the two cannot drift.
    sizes_path = os.path.join(ROOT, "tools", "image-sizes.json")
    idx = os.path.join(ROOT, "index.html")
    if os.path.isfile(sizes_path) and os.path.isfile(idx):
        import json
        table = json.load(io.open(sizes_path))
        m = re.search(r'\[([\d,\s]+)\]\.map\(w=>d\+"-"\+w', io.open(idx, encoding="utf-8").read())
        rungs = [int(x) for x in re.findall(r"\d+", m.group(1))] if m else []
        icons = [k for k, v in table.items()
                 if k.startswith("img/homepage/") and v.get("d") == 26]
        for k in icons:
            for w in rungs:
                for ext in ("avif", "webp"):
                    f = "img/derived/%s-%d.%s" % (os.path.splitext(k)[0][4:], w, ext)
                    seen.add(f)
                    if not os.path.isfile(os.path.join(ROOT, f)):
                        bad.append("missing icon rung %s" % f)
        if icons and not rungs:
            bad.append("could not read the icon rung list out of index.html")

    # the families the pages build a path into rather than writing one
    for fam in ("img/banner", "img/banner-lg", "img/collections"):
        for dp, _, fs in os.walk(os.path.join(ROOT, fam)):
            for fn in fs:
                if not fn.lower().endswith((".jpg", ".jpeg", ".png")): continue
                src = os.path.relpath(os.path.join(dp, fn), ROOT)
                stem = os.path.splitext(src)[0][4:]
                d = os.path.join(ROOT, "img", "derived", stem + "-x.webp")
                if not os.path.isfile(d):
                    bad.append("missing %s for %s" % (os.path.relpath(d, ROOT), src))
    print("  srcset targets checked: %d" % len(seen))
    for b in bad[:10]: print("  FAIL " + b)
    if len(bad) > 10: print("  ... and %d more" % (len(bad) - 10))
    if not bad: print("  all present")
    return bad



def check_furniture():
    """Every collection page keeps a way out and a way home.

    This exists because a rewrite of the byteGANs page silently dropped its
    links row and its footer. Nothing caught it — every asset resolved, the URL
    contract held, the page rendered and looked finished. What had gone was the
    only place on the page saying where to see the work and who made it, and it
    stayed gone through a deploy. A page can be well-formed in every checkable
    way and still be missing its point.

    It tests for the links themselves rather than for the classes around them,
    because the pages do not share one implementation: Reflection carries its
    own markup, and a check that insists on `class="links"` reports three false
    problems and teaches you to ignore it."""
    want = [("a link home",        re.compile(r'class="homemark"')),
            ("a link to the work", re.compile(r'raster\.art/artwork/')),
            ("a credit line",      re.compile(r'class="foot"'))]
    # Reflection is the only collection page with no credit line, and it is not
    # clear that is deliberate — it carries its own darker design and may simply
    # never have had one. Named here rather than matched around, so that the
    # test still bites for the other twelve and this stays visible as a thing to
    # settle rather than becoming a hole in the check.
    known = {"curated/reflection/index.html": {"a credit line"}}
    bad, n = [], 0
    for d in sorted(glob.glob(os.path.join(ROOT, "curated", "*"))):
        page = os.path.join(d, "index.html")
        if not os.path.isfile(page):
            continue
        html = io.open(page, encoding="utf-8").read()
        rel, n = os.path.relpath(page, ROOT), n + 1
        for label, rx in want:
            if not rx.search(html) and label not in known.get(rel, ()):
                bad.append("%s: %s is missing" % (rel, label))
    print("  collection pages checked: %d" % n)
    print("  all present" if not bad else "\n".join("  " + b for b in bad))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", nargs="?", const="https://www.sovrn.art",
                    help="check the public URL contract against this host")
    ap.add_argument("--assets", metavar="BASE_URL",
                    help="crawl a served tree and resolve every asset")
    ap.add_argument("--files", action="store_true",
                    help="resolve the URL contract against the working tree, no network")
    a = ap.parse_args()
    if not a.urls and not a.assets and not a.files:
        ap.error("give --files, --urls and/or --assets BASE_URL")

    bad = []
    if a.files:
        print("\nURL contract against the tree")
        bad += check_files()
        print("\nImages assembled from a base path")
        bad += check_local_assets()
        print("\nBanners and other url() targets")
        bad += check_banners()
        print("\nResponsive derivatives")
        bad += check_srcsets()
        print("\nPage furniture")
        bad += check_furniture()
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
