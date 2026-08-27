#!/usr/bin/env python3
"""Build the page banners: MP4 loops, not animated GIFs.

    python3 tools/build-banner.py --from-gif perimeter-town   # re-encode from the GIF
    python3 tools/build-banner.py --from-gif painting-with-fire
    python3 tools/build-banner.py --sightseers                # compose the new one
    python3 tools/build-banner.py --check                     # sizes and loop lengths

Three collection pages open on a moving banner. They were 44- and 50-frame GIFs
of 6.2MB and 5.8MB, by far the heaviest files the site served, and `--from-gif`
is the conversion: **20 to 25 times smaller with nothing removed.**

Most of that is not the codec. These banners are slideshows -- six to eight
stills, hard cuts, no movement inside a hold -- but the GIF encoder wrote every
frame with its own palette and dither, so two frames of the same still differ by
a few levels across the whole image. That shimmer is a GIF artefact rather than
anything the artist made, and it is what costs the bitrate: it denies H.264 the
almost-free P-frames a genuinely static hold would give it. Taking the per-hold
median restores the still the encoder was quantising and roughly halves the file
again, on top of what the codec change already wins.

So the holds are detected rather than assumed: a mean absolute frame delta above
CUT is a cut, and anything below it is dither. Print them with --check before
trusting a re-encode of some other GIF -- the two here come out at 8 holds/4.4s
and 6 holds/5.0s, which is what the eye sees.

`-t` on the encode is not caution. The concat demuxer needs the final file
repeated to honour its duration and then gives that repeat a hold of its own, so
without it the loop runs one work long and the last work sits twice as long as
the rest.

## --sightseers composes a banner that did not exist

/curated/sightseers had no banner of its own. It was showing Perimeter Town's --
the same file, byte for byte, lettered SIGHTSEERS / PERIMETER TOWN / A NORMAN
HARMAN AI COLLABORATION, made four days before the Perimeter Town release and
eight months after SIGHTSEERS. The original sovrn.art carried the same error, so
it arrived here honestly: `tools/sites-bg.mjs` read each page's computed
background off the live site, per slug, and both pages gave it that file.

Two things about how this one is built are deliberate.

**The type is lifted, not re-set.** The lettering is the artist's own and no font
on the machine matches it exactly, so rather than guess the face, take the
pixels: the lettering is the only thing that holds still across all 44 frames of
the Perimeter Town banner, which makes a min-projection an almost perfect alpha
matte. The word SIGHTSEERS and the credit line are already exactly the strings
this page wants; only PERIMETER TOWN is dropped, and the credit moves up to sit
under the title. That guarantees the two pages are siblings rather than
approximately alike. The matte comes from `img/pages/perimeter-town/hero.gif`,
which is why that file stays in the tree though no page now points at it.

**Every frame has to be a SIGHTSEERS work, and that is not as easy as it looks.**
This banner exists because a page was showing another collection's key art, so
repeating the mistake inside it would be worse than leaving it alone.
`sightseers tableau.jpg` is the obvious source -- four works, 3795x2493, named
for the collection -- and it is excluded, because its bottom-left quadrant is
Perimeter Town's own `02.jpg`. The eight below are each attributable: three are
named for the collection in the filename, four were harvested from the
SIGHTSEERS page itself, and one is its homepage card.

Four of the eight sit outside the repository, under ~/Pictures. They are the
artist's own files at full size and there is no reason to carry a second copy
here; --sightseers says which are missing and stops rather than quietly
composing a shorter loop.
"""
import argparse, os, subprocess, sys, tempfile

try:
    import numpy as np
    from PIL import Image, ImageFilter
except ImportError:
    sys.exit("needs Pillow and numpy: pip install pillow numpy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIX = os.path.expanduser("~/Pictures")
CUT = 25.0          # mean abs frame delta that means a cut rather than dither
W, H = 800, 450     # the banners' native size, and the Perimeter Town lockup's
HOLD = 0.55         # seconds per work, matching the banner this one is a sibling to

BANNERS = ["sightseers", "perimeter-town", "painting-with-fire"]

# The eight works the SIGHTSEERS banner cycles. #248 leads deliberately: the
# lockup is white with no scrim behind it -- .hero.plain removes the one the
# other pages have -- so the work under it carries the contrast on its own, and
# this is the darkest of the eight (mean luminance 14 behind the title, against
# 135 for the brightest). The first frame is also the poster, and the poster is
# what a visitor who asked for less motion keeps, so it is the one frame worth
# choosing rather than accepting.
WORKS = [
    PIX + "/sovrn screen/SIGHTSEERS by Norman Harman #248.jpeg",
    PIX + "/sovrn screen/SIGHTSEERS by Norman Harman #148.jpeg",
    ROOT + "/img/pages/sightseers/01.jpg",
    ROOT + "/img/pages/sightseers/03.jpg",
    PIX + "/sightseer mascot.jpeg",
    PIX + "/sovrn screen/SIGHTSEERS by Norman Harman #363.jpeg",
    ROOT + "/img/pages/sightseers/04.jpg",
    ROOT + "/img/homepage/sightseers_homepage.jpg",
]

# Measured off the matte: (top, bottom, left, right) of each line of the lockup.
TITLE  = (153, 189, 275, 541)   # SIGHTSEERS                     cap 37px
CREDIT = (236, 244, 304, 520)   # A NORMAN HARMAN AI COLLABORATION, cap 9px
CREDIT_TO = 222                 # where it goes once PERIMETER TOWN is dropped


def frames(path):
    im = Image.open(path)
    out, durs = [], []
    while True:
        out.append(np.asarray(im.convert("RGB"), dtype=np.float32))
        durs.append(im.info.get("duration", 100) / 1000.0)
        try:
            im.seek(im.tell() + 1)
        except EOFError:
            return out, durs


def holds(path):
    """One clean still per hold, with the hold's total duration."""
    fs, durs = frames(path)
    groups, cur = [], [0]
    for i in range(1, len(fs)):
        if np.abs(fs[i] - fs[i - 1]).mean() > CUT:
            groups.append(cur); cur = [i]
        else:
            cur.append(i)
    groups.append(cur)
    out = []
    for g in groups:
        med = np.median(np.stack([fs[i] for i in g]), axis=0)
        out.append((Image.fromarray(np.clip(med, 0, 255).astype("uint8")),
                    sum(durs[i] for i in g)))
    return out


def encode(stills, dst, crf=23):
    """Write stills-with-durations as a looping MP4, and a poster of the first."""
    with tempfile.TemporaryDirectory() as td:
        lines = []
        for i, (im, d) in enumerate(stills):
            im.save(f"{td}/h{i:03d}.png")
            lines.append(f"file 'h{i:03d}.png'\nduration {d:.3f}")
        lines.append(f"file 'h{len(stills)-1:03d}.png'")
        open(f"{td}/list.txt", "w").write("\n".join(lines) + "\n")
        total = sum(d for _, d in stills)
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
             "-i", f"{td}/list.txt", "-vf", "fps=25,format=yuv420p",
             "-t", f"{total:.3f}", "-c:v", "libx264", "-crf", str(crf),
             "-preset", "veryslow", "-movflags", "+faststart", "-an", dst],
            check=True, cwd=td)
    poster = os.path.splitext(dst)[0] + ".jpg"
    stills[0][0].save(poster, quality=82, optimize=True, progressive=True)
    return total, poster


def lockup():
    """The SIGHTSEERS lockup, lifted off the Perimeter Town banner.

    The lettering never moves; the artwork under it does. So the per-pixel
    minimum across every frame is the lettering over whatever the darkest work
    put behind it, and subtracting a local floor from that recovers the alpha --
    including the anti-aliased edges, which a plain threshold eats.
    """
    src = os.path.join(ROOT, "img/pages/perimeter-town/hero.gif")
    fs, _ = frames(src)
    mn = np.stack(fs).mean(3).min(0)
    bg = np.asarray(
        Image.fromarray(np.clip(mn, 0, 255).astype("uint8"))
        .filter(ImageFilter.MedianFilter(9)).filter(ImageFilter.GaussianBlur(9)),
        dtype=np.float32)
    a = np.clip((mn - bg) / np.maximum(255.0 - bg, 1.0), 0, 1)
    a[a < 0.06] = 0

    out = np.zeros((H, W), dtype=np.float32)
    t, b, l, r = TITLE
    out[t:b + 1, l:r + 1] = a[t:b + 1, l:r + 1]          # title keeps its place
    t, b, l, r = CREDIT
    dy = CREDIT_TO - t
    out[t + dy:b + 1 + dy, l:r + 1] = a[t:b + 1, l:r + 1]
    return out[..., None]


def cover(path):
    im = Image.open(path).convert("RGB"); w, h = im.size
    s = max(W / w, H / h)
    im = im.resize((round(w * s), round(h * s)), Image.LANCZOS)
    nw, nh = im.size
    return im.crop(((nw - W) // 2, (nh - H) // 2,
                    (nw - W) // 2 + W, (nh - H) // 2 + H))


def build_sightseers():
    missing = [p for p in WORKS if not os.path.isfile(p)]
    if missing:
        print("  cannot build — these works are not on this machine:")
        for p in missing:
            print("   ", p)
        return 1
    pl = lockup()
    stills = []
    for p in WORKS:
        a = np.asarray(cover(p), dtype=np.float32)
        stills.append((Image.fromarray((a * (1 - pl) + 255 * pl).astype("uint8")), HOLD))
    dst = os.path.join(ROOT, "img/pages/sightseers/hero.mp4")
    total, poster = encode(stills, dst)
    print(f"  sightseers   {len(stills)} works, {total:.1f}s, "
          f"{os.path.getsize(dst):,} bytes  (+ {os.path.getsize(poster):,} poster)")
    return 0


def build_from_gif(slug):
    src = os.path.join(ROOT, f"img/pages/{slug}/hero.gif")
    if not os.path.isfile(src):
        print(f"  no {src}"); return 1
    hs = holds(src)
    dst = os.path.join(ROOT, f"img/pages/{slug}/hero.mp4")
    total, poster = encode(hs, dst)
    print(f"  {slug:20} {len(hs)} holds, {total:.1f}s, "
          f"{os.path.getsize(src):,} -> {os.path.getsize(dst):,} bytes "
          f"({os.path.getsize(src)/os.path.getsize(dst):.1f}x)  "
          f"(+ {os.path.getsize(poster):,} poster)")
    return 0


def check():
    bad = 0
    for slug in BANNERS:
        mp4 = os.path.join(ROOT, f"img/pages/{slug}/hero.mp4")
        jpg = os.path.join(ROOT, f"img/pages/{slug}/hero.jpg")
        for f in (mp4, jpg):
            if not os.path.isfile(f):
                print(f"    missing  {os.path.relpath(f, ROOT)}"); bad += 1
        if not os.path.isfile(mp4):
            continue
        dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                              "format=duration", "-of", "csv=p=0", mp4],
                             capture_output=True, text=True).stdout.strip()
        print(f"  {slug:20} {os.path.getsize(mp4):>9,} bytes  {float(dur):.2f}s"
              f"  poster {os.path.getsize(jpg):>7,}")
    print(f"  {len(BANNERS) - bad}/{len(BANNERS)} banners present")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-gif", metavar="SLUG", choices=BANNERS)
    ap.add_argument("--sightseers", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if not any((a.from_gif, a.sightseers, a.check)):
        ap.error("nothing to do — pass --from-gif, --sightseers or --check")
    rc = 0
    if a.from_gif:
        rc |= build_from_gif(a.from_gif)
    if a.sightseers:
        rc |= build_sightseers()
    if a.check:
        rc |= check()
    return rc


if __name__ == "__main__":
    sys.exit(main())
