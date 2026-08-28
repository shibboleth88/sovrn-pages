#!/usr/bin/env python3
"""Make the still frame of a Reflection work, for readers who ask for no motion.

    python3 tools/build-reflection-still.py            # write the still
    python3 tools/build-reflection-still.py --check    # verify it against the source

The Reflection page stands on one of the paintings, and a minted Reflection is
not a still image: seven `<animate>` elements ramp the layer opacities on an
eight-second loop, so the picture perpetually unmakes and remakes itself. That is
the work, and it is the whole reason the background is worth having.

It is also motion, and `prefers-reduced-motion` has to be honoured. The artwork
is used as a CSS background, which means it is an *image* to the page — there is
no document to reach into and no way to call `pauseAnimations()` on it. The only
way to hold it still is to serve a version that does not move.

So this strips the `<animate>` elements and nothing else. Every one of them ends
at opacity 1 — `values="1;0;0;1;1"` — so removing them leaves each layer at rest
and the still is the painting fully assembled, which is the right thing for it to
settle on. Nothing is re-drawn, re-coloured or re-encoded; it is the same file
with seven elements deleted, so it stays byte-comparable to its source and
--check re-derives it rather than trusting it.
"""
import io, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = 52                      # 'human empathy'
SRC = os.path.join(ROOT, "onchain", "reflection", "%d.svg" % TOKEN)
OUT = os.path.join(ROOT, "img", "reflection-page", "human-empathy-still.svg")

def still(svg):
    out = re.sub(r'<animate\b[^>]*/>\s*', '', svg)
    out = re.sub(r'<animate\b[^>]*>.*?</animate>\s*', '', out, flags=re.S)
    return out

def main():
    src = io.open(SRC, encoding="utf-8").read()
    want = still(src)
    n = len(re.findall(r'<animate\b', src))
    if "--check" in sys.argv:
        if not os.path.exists(OUT):
            sys.exit("  missing %s" % os.path.relpath(OUT, ROOT))
        have = io.open(OUT, encoding="utf-8").read()
        if have != want:
            sys.exit("  %s is not the source with its %d fades removed" % (os.path.relpath(OUT, ROOT), n))
        if re.search(r'<animate\b', have):
            sys.exit("  the still still animates")
        print("  the still is token %d with its %d fades removed, and nothing else" % (TOKEN, n))
        return
    io.open(OUT, "w", encoding="utf-8").write(want)
    print("  wrote %s — token %d, %d fades removed, %.0f KB"
          % (os.path.relpath(OUT, ROOT), TOKEN, n, len(want) / 1024.0))

if __name__ == "__main__":
    main()
