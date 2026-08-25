#!/usr/bin/env python3
"""Verify the four share pages differ only where they are supposed to.

    python3 tools/check-share-pages.py

share.html and shareable/share-<slug>/index.html are thin shells over share.css and
share.js. All four carry the same body markup, so the one way this arrangement can rot is
someone editing the markup in one shell and not the others. That is exactly the
drift a reader would never notice: three pages keep working and the fourth
quietly loses a button.

Checked here: identical markup across all four, each scoped page declaring the
scope its filename claims, share.html declaring none, no page carrying an inline
<style> or a second inline <script> that has escaped the shared files, and the
preload hints naming the frame each panel actually opens on — share.js decides
that, and a preload pointing at the wrong frame warms an image nobody shows
while leaving the real one cold.
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUGS = ["reflection", "wunderkammer", "bytegans"]

# share.html stays at the root: the Sites embeds address it as share.html?c=<slug>,
# and the flat share-<slug>.html paths are now redirect stubs pointing here.
def scoped(slug):
    return f"shareable/share-{slug}/index.html"

PAGES = ["share.html"] + [scoped(s) for s in SLUGS]
HUB = "shareable/index.html"

# The old flat paths, and where each must send a visitor. vanarman.com iframes
# share-reflection.html, so these are load-bearing for someone else's page.
STUBS = {f"share-{s}.html": f"/shareable/share-{s}" for s in SLUGS}
STUBS["shareables.html"] = "/shareable"


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def markup_of(text):
    """The body, minus the scope declaration and the shared-script tag."""
    body = text.split("<body>", 1)[1].split("</body>", 1)[0]
    body = re.sub(r"<script>var SHARE_SCOPE[^<]*</script>", "", body)
    body = body.replace('<script src="share.js"></script>', "")
    return body.strip()


def scope_of(text):
    m = re.search(r'var SHARE_SCOPE\s*=\s*"([a-z-]+)"', text)
    return m.group(1) if m else None


def main():
    problems = []

    for name in PAGES + ["share.css", "share.js"]:
        if not os.path.exists(os.path.join(ROOT, name)):
            problems.append(f"{name} is missing")
    if problems:
        for p in problems:
            print("  " + p)
        return 1

    baseline = markup_of(read("share.html"))
    for name in PAGES[1:]:
        if markup_of(read(name)) != baseline:
            problems.append(f"{name}: body markup has drifted from share.html")

    if scope_of(read("share.html")) is not None:
        problems.append("share.html declares a SHARE_SCOPE; it should serve all three")
    for slug in SLUGS:
        name = scoped(slug)
        found = scope_of(read(name))
        if found != slug:
            problems.append(f"{name}: declares scope {found!r}, expected {slug!r}")

    for name in PAGES:
        text = read(name)
        if "<style>" in text:
            problems.append(f"{name}: has an inline <style>; it belongs in share.css")
        if len(re.findall(r"<script(?![^>]*\bsrc=)", text)) > (0 if name == "share.html" else 1):
            problems.append(f"{name}: has an unexpected inline <script>")
        if 'href="share.css"' not in text:
            problems.append(f"{name}: does not link share.css")
        if 'src="share.js"' not in text:
            problems.append(f"{name}: does not load share.js")

    # The preload must name the frame share.js actually opens the panel on.
    js = read("share.js")
    starts = dict(re.findall(r"(\w+)\s*:\s*(\d+)", 
                             (re.search(r"var PANEL_START\s*=\s*\{([^}]*)\}", js) or
                              type("m", (), {"group": lambda *_: ""})()).group(1)))
    pools = dict(re.findall(r"(\w+):\s*\{\s*dir:\s*\"([^\"]+)\",\s*stem:\s*\"([^\"]+)\"",
                            js) and [(m[0], (m[1], m[2])) for m in
                 re.findall(r"(\w+):\s*\{\s*dir:\s*\"([^\"]+)\",\s*stem:\s*\"([^\"]+)\"", js)])
    for slug, (d, stem) in pools.items():
        n = int(starts.get(slug, 0))
        if not n:
            continue                      # uses the default stagger; nothing pinned
        want = f"{d}{stem}{n:02d}.svg"
        # shareables.html shows the same frame on its card, so a click lands on an
        # image already fetched. That claim is only true while they agree.
        for name in ("share.html", scoped(slug), HUB):
            if os.path.exists(os.path.join(ROOT, name)) and want not in read(name):
                problems.append(
                    f"{name}: preloads a frame other than {want}, which share.js opens on")

    # The stubs are what keep old inbound links and outside embeds working.
    for name, target in STUBS.items():
        if not os.path.exists(os.path.join(ROOT, name)):
            problems.append(f"{name}: stub is missing; old links and embeds break")
            continue
        text = read(name)
        if 'http-equiv="refresh"' not in text or target not in text:
            problems.append(f"{name}: stub no longer redirects to {target}")

    for p in problems:
        print("  " + p)
    print(f"\n{len(PAGES)} share pages: " +
          ("all consistent" if not problems else f"{len(problems)} PROBLEM(S)"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
