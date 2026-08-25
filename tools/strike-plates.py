#!/usr/bin/env python3
"""Blank planchets for cents-striker.html.

Lifts Lincoln off a photographed cent and leaves the coin otherwise untouched:
same rim, same legends, same date, same patina. The striker then presses a
dropped avatar into what's left.

    python3 tools/strike-plates.py

Writes img/cents/plate-*.jpg (1024, the plate itself) and plate-*-sw.jpg (96,
the picker swatch). Sources are the cent photographs already in img/cents.

How it works
------------
Every photograph in img/cents was shot the same way, so once each coin is
resampled to a common centre and radius, Lincoln lands in the same place on all
of them - sharp enough that the average of 65 coins still reads as a portrait.
That makes one hand-traced silhouette (BUST below, traced off that average)
enough for the whole corpus.

The hole it leaves is filled in three steps. A push-pull estimate seeds it from
the surrounding field alone, so nothing of the bust survives to be smeared
around later. Diffusion then settles the low frequencies against the real
boundary. Finally the coin's own patina is patched back in - mid- and
high-frequency detail lifted from quiet parts of its own field, never from the
legends, whose letters would otherwise turn up scattered across the blank.
"""

import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(os.path.dirname(HERE), "img", "cents")

N = 1024
CX = CY = 511.0
RAD = 416.4                      # the plate geometry cents-striker.html assumes

# The coins to blank, in the order the picker shows them: a walk from mint red
# through to heavy verdigris.
PLATES = [
    ("1971-shiny.jpg",                    "1971-red",      1971, "red"),
    ("1944-alternative-orange-8526.jpg",  "1944-gold",     1944, "gold"),
    ("1971-wild-orange.jpg",              "1971-orange",   1971, "orange"),
    ("1912.jpg",                          "1912-chestnut", 1912, "chestnut"),
    ("1970-1.jpg",                        "1970-dark",     1970, "dark"),
    ("1434.jpg",                          "1976-silver",   1976, "silver"),
    ("1969-cent-2.jpg",                   "1969-sage",     1969, "sage"),
    ("1970-2.jpg",                        "1970-verdigris",1970, "verdigris"),
]

# Lincoln's silhouette on the normalised plate, traced off the 65-coin mean.
BUST = [(500,168),(556,176),(596,196),(628,228),(646,262),(652,300),(646,330),
        (664,352),(676,382),(668,406),(650,424),(654,452),(640,478),(628,500),
        (616,530),(612,560),(628,590),(648,626),(664,668),(678,714),(688,772),
        (708,836),(704,900),(640,910),(520,914),(400,910),(300,900),(258,884),
        (256,830),(262,772),(276,716),(294,668),(318,628),(340,596),(348,556),
        (344,500),(342,440),(344,380),(352,320),(372,262),(404,212),(450,180)]

rng = np.random.default_rng(11)


# ----------------------------------------------------------------- filtering

def boxf(a, r):
    """Mean over a (2r+1) square, via an integral image. Stays in float."""
    pad = ((r + 1, r + 1), (r + 1, r + 1)) + ((0, 0),) * (a.ndim - 2)
    c = np.pad(a, pad, mode="edge").cumsum(0).cumsum(1)
    c = np.pad(c, ((1, 0), (1, 0)) + ((0, 0),) * (a.ndim - 2))
    k = 2 * r + 1
    s = c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    return (s / (k * k))[:a.shape[0], :a.shape[1]]


def blurf(a, r):
    for _ in range(3):
        a = boxf(a, max(1, r // 2))
    return a


def blur(a, r):
    return np.asarray(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(r))).astype(np.float32)


# ------------------------------------------------------------------ geometry

def coin(im):
    """Centre and radius of the coin against its white seamless."""
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    ys, xs = np.nonzero(a.mean(2) < 242)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    return (x0 + x1) / 2, (y0 + y1) / 2, min(x1 - x0, y1 - y0) / 2


def normalize(path):
    """Resample so the coin lands centred at (CX,CY) with radius RAD on white."""
    im = Image.open(path).convert("RGB")
    cx, cy, r = coin(im)
    s = RAD / r
    im2 = im.resize((int(round(im.width * s)), int(round(im.height * s))), Image.LANCZOS)
    out = Image.new("RGB", (N, N), (255, 255, 255))
    out.paste(im2, (int(round(CX - cx * s)), int(round(CY - cy * s))))
    return out


def bust_mask(feather=6, grow=17):
    """The traced silhouette, grown a little: individual coins sit a few pixels
    off the mean, and an uncovered jawline is the one thing that reads."""
    m = Image.new("L", (N, N), 0)
    ImageDraw.Draw(m).polygon(BUST, fill=255)
    for _ in range(grow // 3):
        m = m.filter(ImageFilter.MaxFilter(7))
    a = np.asarray(m).astype(np.float32) / 255.0

    yy, xx = np.mgrid[0:N, 0:N]
    rr = np.sqrt((xx - CX) ** 2 + (yy - CY) ** 2) / RAD
    a *= np.clip((0.935 - rr) / 0.02, 0, 1)          # never touch the rim

    # The legends are the coin's own and must survive; the bust barely reaches them.
    keep = np.zeros((N, N), np.float32)
    keep[np.logical_and(rr > 0.845, yy < 420)] = 1   # IN GOD WE TRUST
    keep[508:600, 118:374] = 1                       # LIBERTY
    keep[604:718, 676:912] = 1                       # the date
    keep = np.asarray(Image.fromarray((keep * 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(3))).astype(np.float32) / 255.0
    a *= 1 - keep

    return np.asarray(Image.fromarray((a * 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(feather))).astype(np.float32) / 255.0


# ------------------------------------------------------------------- filling

def prefill(img, m):
    """Estimate the hole from the surrounding field alone, so no trace of the
    bust survives to be smoothed around later."""
    w = (1 - m)[..., None]
    return blurf(img * w, 90) / np.maximum(blurf(w, 90), 1e-6)


def diffuse(img, m, schedule=((3,20),(8,30),(18,40),(34,45),(60,35),(24,25),(9,18),(3,12))):
    m3 = m[..., None]
    out = img * (1 - m3) + prefill(img, m) * m3
    for r, n in schedule:
        for _ in range(n):
            out = out * (1 - m3) + blur(out, r) * m3
    return out


def transplant(base, src, m, block=112, r=26):
    """Borrow this coin's own patina. Sources are drawn only from quiet field."""
    res = src - blur(src, r)
    busy = blur(np.abs(res).mean(2), 10)

    yy, xx = np.mgrid[0:N, 0:N]
    rr = np.sqrt((xx - CX) ** 2 + (yy - CY) ** 2) / RAD
    legend = np.zeros((N, N), bool)
    legend |= (rr > 0.68) & (yy < 392)
    legend[505:605, 100:380] = True
    legend[600:720, 650:900] = True

    inner = (m < 0.02) & (rr < 0.88) & (~legend)
    valid = inner & (busy < np.percentile(busy[inner], 45))
    ys, xs = np.nonzero(valid)
    if len(ys) == 0:
        return base

    h = block // 2
    win = np.hanning(block)[:, None] * np.hanning(block)[None, :]
    acc = np.zeros_like(base)
    wsum = np.zeros(base.shape[:2], np.float32)
    for y in range(0, N - block, h):
        for x in range(0, N - block, h):
            if m[y:y+block, x:x+block].max() < 0.02:
                continue
            for _ in range(24):
                k = rng.integers(len(ys))
                sy, sx = int(ys[k]) - h, int(xs[k]) - h
                if sy < 0 or sx < 0 or sy + block > N or sx + block > N:
                    continue
                if m[sy:sy+block, sx:sx+block].max() < 0.02:
                    break
            else:
                continue
            acc[y:y+block, x:x+block] += res[sy:sy+block, sx:sx+block] * win[..., None]
            wsum[y:y+block, x:x+block] += win
    w = np.where(wsum > 1e-6, wsum, 1)[..., None]
    return base + (acc / w) * m[..., None]


def make_plate(path, mask):
    src = np.asarray(normalize(path)).astype(np.float32)
    out = transplant(diffuse(src, mask), src, mask)
    out += rng.normal(0, 1.1, out.shape[:2])[..., None] * mask[..., None]
    m3 = mask[..., None]
    out = src * (1 - m3) + out * m3          # outside the bust, exactly as photographed
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def main():
    mask = bust_mask()
    for name, slug, year, patina in PLATES:
        src = os.path.join(IMG, name)
        if not os.path.exists(src):
            print("missing", src, file=sys.stderr)
            continue
        plate = make_plate(src, mask)
        plate.save(os.path.join(IMG, "plate-%s.jpg" % slug), quality=86, optimize=True)
        plate.resize((96, 96), Image.LANCZOS).save(
            os.path.join(IMG, "plate-%s-sw.jpg" % slug), quality=88, optimize=True)
        print("plate-%s.jpg  (%d %s)" % (slug, year, patina))


if __name__ == "__main__":
    main()
