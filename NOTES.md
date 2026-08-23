# Working notes

Things about this repo, the artworks and Google Sites that cost real time to
find out. Written so the next person — or the next session — does not have to
rediscover them.

---

## Google Sites

These pages are hosted here and embedded into Google Sites. Sites imposes three
constraints that are not obvious from inside the editor.

**Use the `< >` "Full page embed" page type.** In the Sites *Pages* panel a page
is either a normal page or a full page embed, marked with a `< >` icon. An
embed placed on a normal page is boxed into a container with `max-width: 1280`
and a locked aspect ratio, which on a phone leaves the bottom half of the screen
blank. A full page embed is full-bleed and behaves. Every page here needs the
`< >` type. This is a property of the page, not of how large you drag the frame.

**Every link needs `target="_blank"`.** The Sites embed iframe is sandboxed with
`allow-scripts allow-popups allow-forms allow-same-origin
allow-popups-to-escape-sandbox allow-downloads
allow-storage-access-by-user-activation`. `allow-top-navigation` is *absent*, so
`target="_top"` silently does nothing — links become completely dead. No target
at all gives "refused to connect". `_blank` is the only thing that works.

**There is no Sites editing API.** The Sites API is deprecated and Classic-only;
its changelog stops in June 2011. Every Sites-side step is manual.

**Recovering an embed's HTML.** The live page carries the embed markup in a
`data-code` attribute on the parent element. No need to paste anything by hand —
fetch the page and read the attribute.

---

## Never rewrite a URL someone gives you

Google-hosted image URLs end in something like `=w1280`. That size is baked into
the signed token; editing it returns a 403. The same goes for the misspelling in
`/museums/fransisco-carolinum` — that is the live URL and it is correct as-is.
Fix the spelling in prose only.

---

## Reflection: the two renditions, and how to smooth the minted one

This one is worth reading in full, because the obvious conclusion is wrong twice
over.

*Reflection* by Pindar Van Arman is **fully on-chain** at
`0x5137cfb461d24040f5ce6b85d860c47a24f85412` on Ethereum. `tokenURI(id)` returns
base64 JSON whose `image` field is a base64 SVG — the artwork itself, no gateway
involved.

```bash
curl -s -X POST https://ethereum-rpc.publicnode.com \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_call","params":[{
       "to":"0x5137cfb461d24040f5ce6b85d860c47a24f85412",
       "data":"0xc87b56dd0000000000000000000000000000000000000000000000000000000000000374"
      },"latest"]}'
```

`0xc87b56dd` is `tokenURI(uint256)`; the rest is the token id padded to 32 bytes
(`0x374` = 884). Two gotchas: **send a `User-Agent`** — publicnode 403s urllib's
default — and skip `cloudflare-eth.com`, which returns an internal error on
responses this large (a token is ~160 KB).

### Two renditions exist

| | fades | where |
|---|---|---|
| **As minted** | exactly **7**, on wrapper `<g>`s | the contract; raster.art serves this |
| **`reflection_<token>_layers_smooth.svg`** | **20–26** | `gorgonorgon/sovrn-FC-images`, six files only |

The `_layers_smooth` files are exhibition renders the artist derived for
Francisco Carolinum: the same file, the seven minted fades untouched, plus 13–19
more on the content layers. Only six exist — 515, 884, 885, 886, 888, 889.
`moca.html` shows five of them, which is why that page looks richer than
anything built from minted files.

**A minted file with 7 fades is not broken.** I deleted those seven once,
believing raster.art had stripped them. They are the artwork.

### The smoothing is reconstructible

The minted SVG carries its own schedule in HTML comments. Each painting pass is
numbered:

```
9:0 background · 10:1 bytegan 40x40 · 11:8 ganStrokes · 12:0 skull
13:0 background binary · 14:5 · 15:0 circles · 16:0 touchups · 17:5 lighten
18:0 darken · 19:2 highlight · 20:2 skull flourish · 21:23:0 final bytegans
```

with `startanim` / `endanim` bracketing the minted fades. That numbering is
exactly the "which pass does this layer belong to" information that makes the
cascade derivable.

The rule: walk the `<g>`s from pass 11, give each drawn layer its own fade one
every 0.4 s, leave the minted seven alone. `keyTimes` follows from `begin`:

```
keyTimes = 0 ; 0.0625 ; k ; k + 0.0625 ; 1      where k = 0.125 + 0.0625 × begin
values   = 1;0;0;1;1     dur = 8s     repeatCount = indefinite     fill = freeze
```

Four wrinkles the artist's renders show and a naive walk would miss:

- a `*rows` class inside pass 11 (the grid under the strokes) never fades
- the group opening pass 13 holds a slot in the sequence but does not fade
- passes 19 and 20 fade their unclassed wrappers too, unlike every other pass
- pass 20 fades nothing when it contains a childless group, and its closing
  wrapper — which really belongs to pass 21 — never fades in any piece

[`tools/reflection-smooth.py`](tools/reflection-smooth.py) implements this:

```bash
python3 tools/reflection-smooth.py minted.svg smoothed.svg
```

### How to know it is the artist's rule and not an invention

The tool proves itself. It fetches the six minted originals from the contract,
smooths them, and compares against the artist's own FC renders:

```bash
python3 tools/reflection-smooth.py --verify
```

It reproduces **all six exactly** — same groups, same `begin`, same `keyTimes`,
`values`, `dur`, `repeatCount`, `fill` — and exits non-zero if it ever stops
doing so. Run it after any change to the rule. Two further checks
worth keeping: stripping the fades from a smoothed file must leave it
byte-identical to the minted one, and all seven minted fades must survive
verbatim.

> **`ElementTree` discards comments** unless you pass
> `ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))`. Reading a
> comment-free parse is what led me to declare the schedule unrecoverable. If a
> generated SVG seems to be missing its logic, check you are not the one
> dropping it.

---

## Harvesting artwork from raster.art

raster.art lazy-loads its grid behind an `IntersectionObserver`, and **the
observer ignores synthetic events**. `dispatchEvent`, setting `scrollTop`,
`window.scrollTo` — none of them fire it. Only a real trusted scroll works.

What works:

1. Navigate to the artwork page.
2. Take a screenshot first — this establishes the coordinate frame that the
   scroll action needs.
3. Issue a **real** mouse scroll through the browser tool, repeatedly, letting
   the grid fill in.
4. Collect the `bits.raster.art` URLs the page has now loaded.
5. `curl` each one **with a `Referer` header**.

Repeated failures here look exactly like CDN rate-limiting. They are not — the
CDN returns 200 to `curl` throughout. Do not conclude you have been throttled.

raster.art serves `700.avif` / `1200.avif`. **PIL cannot read AVIF**; convert
with macOS `sips` first:

```bash
sips -s format jpeg in.avif --out out.jpg
```

Note that raster.art serves the **minted** rendition of Reflection, not the
smooth one. Rate-limits with a 429 if you hit the site directly too often.

---

## Rasterising and resizing

| need | tool |
|---|---|
| SVG → PNG | `qlmanage -t -s 700 -o <outdir> file.svg` — the only SVG rasteriser on this Mac |
| AVIF → JPEG | `sips -s format jpeg` |
| everything else | PIL |

`qlmanage` emits blank frames for some inputs; check the output directory rather
than trusting the exit code, and drop images whose channel extrema are all equal.

---

## SVG behaviour inside `<img>`

Worth knowing before choosing a format, and all of it verified here rather than
assumed:

- **SMIL animates.** Declarative `<animate>` runs normally. This is how every
  Reflection card works.
- **Nested animated GIFs animate too**, identically to the same GIF served
  directly — confirmed with a side-by-side control. The
  `<animate attributeName="opacity" from="1" to="0.999">` you see in the byteGAN
  and Wunderkammer files is a keep-playing hack, not the animation itself.
- **Scripts do not run.** An SVG that animates via JavaScript needs `<object>`
  or inline SVG.
- The SVG wrapper costs nothing, so prefer it over extracting the inner GIF —
  the wrapper carries the artist's `image-rendering: pixelated` and layering.

### What the collections actually contain

- **byteGANs** — an **11 × 11 pixel** animated GIF, 11 frames, 2.2 s, wrapped in
  SVG at 500 px with `image-rendering: pixelated`. 25–57 % of pixels change per
  frame. About 1.1 KB each, far lighter than any raster of them.
- **Wunderkammer** — four stacked layers: a 48 × 48 tiled pattern, a static
  base, an animated overlay, and Isa Kost's signature at bottom right. The
  overlay is almost entirely transparent and carries a single travelling glint;
  only 0.05–0.2 % of pixels change. That is the artwork, not a fault. One of the
  36 (`wunderkammer-03.svg`) is a single frame.
- **Reflection** — pure vector, ~700 paths, no embedded rasters.

---

## Verifying animation

**The in-app browser pane does not paint.** Measured: one `requestAnimationFrame`
in three seconds, `IntersectionObserver` never fires, `loading="lazy"` images
never load, and `document.visibilityState` stays `hidden`. Anything that depends
on rendering — rotation, lazy loading, scroll-driven animation — will look
broken there when it is fine.

Use headless Chrome instead:

```bash
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# drive a page's timers forward and read the resulting DOM
"$CH" --headless=new --disable-gpu --allow-file-access-from-files \
  --window-size=1280,900 --virtual-time-budget=120000 --dump-dom page.html
# sample a moment in an animation
"$CH" --headless=new --disable-gpu --allow-file-access-from-files \
  --virtual-time-budget=3800 --window-size=300,300 --screenshot=t.png page.html
```

`--virtual-time-budget` fast-forwards timers, so 120 s of a `setInterval` takes
seconds. Two cautions:

- It **quantises animation clocks**, so a 24-frame sample can collapse to three
  distinct states. Use it to prove that something changes, not to judge how
  smooth it looks.
- Always render a **control** — the same file twice, or a known-good file beside
  the one under test. Two `<img>`s on one page differ by a few hundred pixels
  from renderer noise alone; the same file rendered alone twice differs by zero.

To exercise scroll-dependent code, write a temp copy of the page with a
`setTimeout(() => scrollTo(0, grid.offsetTop - 120), 50)` appended, point Chrome
at that, and delete it afterwards.

---

## The homepage card rotation

`home.html` renders 15 collection cards from the `C` array. **`C`'s order is
chronological and must not change.**

Each card cycles works from its own collection. The folder is derived from the
last path segment of the card's own link — `/curated/reflection` →
`img/collections/reflection/` — so the pool and the card cannot drift apart. The
`PL` map takes either a count, meaning
`img/collections/<slug>/<slug>-NN.jpg`, or `[count, folder, prefix, extension]`
for sets that live elsewhere.

**Emerging Faces is deliberately absent from `PL`.** It links off-site to
vanarman.com and keeps its single portrait.

Mechanics: two stacked `<img>`s cross-fade over 0.85 s; an `IntersectionObserver`
means only on-screen cards rotate; one swap per 1.4 s tick caps the page at
roughly one image a second however wide the window; a card holds 14–22 s, except
Reflection at 19–27 s because its cascade needs a full 14–15.6 s pass. The whole
thing is off under `prefers-reduced-motion` and Data Saver, and pauses when the
tab is hidden.

Latent Couture is shot tall (0.69 ratio), so those cards use
`object-position: top` — a centre crop takes the headpieces off.

### Mosaic bands

Tile pool `img/banner/` at 160 px: `b001`–`b186` are works, `b187`–`b223` are
CENTS. `img/banner-lg/` is the same tile at 320 px, used only by blocks larger
than one cell. **Eleven tiles have no high-resolution source** — `b007 b039 b059
b082 b090 b102 b108 b125 b143 b145 b149` — and the `SMALLONLY` set in
`home.html` keeps them one cell wide. If you add tiles, regenerate both tiers
and update that set, or a big block will request a file that is not there.

The band is packed generatively: a walk over an occupancy grid drops blocks of
one, two or three cells wherever they still fit. The upper band runs finer, the
lower coarser, so the pair does not read as a repeat. The seed comes from the
clock — **`?mosaic=<n>` pins it**, which is the only way to compare two runs or
to reproduce something you saw.

**The composition is colour-led.** Each tile carries two base36 digits in the
`CL` string in `home.html` — lightness, then warmth, where warmth is how far the
tile leans toward copper scaled by how colourful it is, so greys land mid-scale
and go anywhere. Two slow waves drift across the band, one per axis, and each
tile is chosen from the last seven in the bag by whichever sits closest to the
field there. A small window keeps it a lean rather than a sort. Hue on its own
is no good for this: 84 of the 223 tiles fall in one warm bin, mostly the
copper cents. Lightness spans 0.10 to 0.94 evenly and is the axis worth
composing on, so it is weighted three to one.

Blocks come in five shapes — 1×1, 2×1, 1×2, 2×2 and 3×3, plus a 2×3 — and every
band gets one full-height anchor somewhere across the middle so the composition
does not depend on the dice. Large blocks end up covering half the upper band
and about sixty per cent of the lower one.

Five rules that took a couple of passes to get right:

- **Draw from a bag keyed by size class.** One shared bag lets a large block
  draw a tile that only exists at 160 px, and you get a broken image.
- **Count cents by area, not by tile.** A cent every sixth *tile* is far more
  than a sixth of the *band* once blocks vary in size. Cents also stay one cell:
  a penny is small, bright and round, and enlarged it pulls the eye off the
  works around it.
- **Keep bare cells apart.** Two touching rests merge into what looks like a
  hole rather than a pause.
- **Let the two rectangle orientations take turns going first.** Sharing one
  roll means wide always wins it and the band never gets a tall block.
- **The anchor must not set the spacing clock.** It is placed before the walk
  starts, so if it updates the `last` column that the `c - last` spacing check
  reads, every column to its left fails the check and the whole half comes out
  flat. This one is invisible in the code and obvious in a render.
- **Place cents on rising odds, not on a threshold.** Firing the moment the
  running share dips below a sixth drops a penny straight after every large
  block, at a cadence you can read across the band. Letting the probability
  rise with the shortfall still averages a sixth but lands irregularly.

### Animating the band

The bands hold still. The only movement is turnover: one cell somewhere on
screen dissolves into another work every 2.2s. The replacement matches that
cell's kind and size and is chosen against the colour field at its column, so a
passage keeps its character — each cell carries `data-c`, `data-k` and `data-b`
for that. The image is decoded before the fade, so a cell never fades up onto a
blank. It runs only for a band that is on screen, only for cells actually in the
window, and never while the tab is hidden. It stops for
`prefers-reduced-motion`, and under Data Saver, since every turn pulls another
tile.

**The band is sized to the frame.** Columns are computed from
`parentElement.clientWidth`, so the whole mosaic is on screen — about 22 columns
at a 1240px window, against the 58 it used to run. The count rounds up, so a
little sits past the frame; that surplus is split between the two edges with a
negative `margin-left`, because a slight bleed on both sides reads as full-bleed
while one clipped tile on the right reads as a mistake. A resize that changes
the column count rebuilds the band. There is no edge mask any more: the band now
ends where the frame does, so fading its own last tiles would be wrong.

Nothing is lost by the smaller band — the rest of the pool is what turnover
draws from, and with roughly 69 cells instead of 213 a given cell now comes
round about every two and a half minutes rather than every seven.

**What turnover costs.** Measured over four minutes at one swap per 2.2s: 69
tiles on screen at the start, 176 distinct tiles requested by the end, so about
27 new tiles a minute — early on, essentially every swap is a fresh fetch.
Tiles average 13.6KB, so roughly 370KB a minute. The important part is that this
is bounded: the whole library is 435 files and 5.9MB, and once a visitor has
seen enough of it every further swap is a cache hit and costs nothing. Running
turnover faster does not raise the total, it just reaches the ceiling sooner —
at one swap every 300ms it would saturate in two or three minutes. CPU is not
the constraint at any rate: a swap is one opacity transition on one element.

Two dead ends, in case either looks tempting again:

- **A slow horizontal travel** was built and then dropped — it read as motion
  rather than as change. If it is ever wanted back, size it as
  `gridWidth - frameWidth` and refit on resize, or widening the window walks the
  grid past its own end and shows the frame behind it.
- **Scroll-linked drift cannot work on this band at all.** `.banner` has
  `overflow: hidden`, which makes it a scroll container, so `animation-timeline:
  view()` on the grid resolves against that box rather than the page and the
  progress sits at 50% for ever.

If any animation does come back here, note that `#ban` sets the `animation`
shorthand, so a class-only rule like `.banner.off .mg` loses on specificity and
silently never applies.

Verifying motion is awkward. Headless `--screenshot` does not capture CSS
animation state under `--virtual-time-budget` — an animated band photographs
unmoved however long the budget, and that is not compositor promotion; removing
`will-change` changes nothing. `getComputedStyle` cannot see a scroll-driven
animation at all. What works is injecting a probe that reads
`getComputedStyle(el).transform` after `setTimeout` waits, or `getAnimations()`.
Note also that an early screenshot catches lazy images mid-load, which reads as
enormous frame-to-frame change and as the odd broken tile; neither is real.

Latent Couture is shot tall, so its fourteen banner tiles — `b017 b022 b025
b040 b046 b063 b091 b099 b117 b122 b151 b164 b178 b185` — are cropped from the
top in both tiers, or the square crop takes the headpieces off. The same applies
to its cards, which use `object-position: top`.

The old uniform-grid version flowed in columns of three, which meant a cent
every sixth tile landed every cent in the same row; it rotated the slot by
`(k * 5) % 6` to spread them. The packed version has no such problem.

---

## Odds and ends still open

- `museums-overview.html` says "Twelve works" for the Francisco Carolinum set;
  the FC page lists eleven.
- The KINDL photo credit (Jens Ziehe) is unconfirmed for the image in use.
- `AtlasVertabra` / `GinkoLeaf` are left spelled as the artist spells them.
- The Wunderkammer GIF download page needs either a re-save with all 108 loaded
  or the original named GIF files.
- The 24 smoothed Reflection renders are generated, not published by the artist.
  The recipe is provably his, but if only released renders should appear, the
  six are `reflection-01` … `-06` and the pool size is a one-line change.
