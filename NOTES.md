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

Tile pool `img/banner/`: `b001`–`b186` are works, `b187`–`b223` are CENTS. The
band flows in **columns of three**, so placing a cent every sixth tile puts every
cent in the same row. The slot rotates `(k * 5) % 6` to spread them. One cent per
six tiles is the intended density.

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
