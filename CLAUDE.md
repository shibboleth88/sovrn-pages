# sovrn-pages — operating notes

**This repo *is* sovrn.art.** Since 25 August 2026 it is served directly at
`https://www.sovrn.art` from GitHub Pages — Google Sites is gone. Editing a file
here and pushing to `main` changes the live site a minute later; there is no
staging step and no second system to keep in sync.

Read [`MIGRATION.md`](MIGRATION.md) before restructuring anything. It carries the
URL contract, why the flat share shells are shaped the way they are, and the
things the move cost real time to discover. [`NOTES.md`](NOTES.md) is still worth
having — its Google Sites sections are now history, but everything about the
artworks, the Reflection cascade and raster.art still applies.

**Two rules survive the move:**

1. **URLs do not change.** `tools/check-site.py --urls https://www.sovrn.art`
   asserts all 47 resolve. Outside sites link these paths, and one of them is
   iframed by vanarman.com. If you move a page, leave a stub — see the ones at
   the old flat paths for the shape.
2. **Run the checkers before pushing.** `main` is production.

   ```bash
   python3 tools/check-site.py --urls https://www.sovrn.art
   python3 tools/check-site.py --assets https://www.sovrn.art
   python3 tools/check-share-pages.py
   ```

This file covers what can break the live site from outside this repository.

## Images are served from this repo, deliberately

Every image the site renders is under `img/`. Until 25 August 2026 the homepage
tiles, museum photographs, KINDL and Vitra installation views and the Francisco
Carolinum plates were loaded from six repos under a **different account**
(`gorgonorgon`) over `raw.githubusercontent.com`. They were copied in — 71 files,
11MB — and every reference now points at `/img/...`.

This is the same argument as the artwork mirror, and it should not be undone: a
same-origin file has exactly the page's availability, while any outside host can
be blocked, rate-limited or deleted independently. That one also happened to be an
account nobody here can administer, and it sent `max-age=300` against the site's
own 600.

**Do not reintroduce an external image host.** New images go in `img/`.

One trap if you ever audit this: **the URLs are built by string concatenation in
JS**, so grepping the HTML finds base constants rather than filenames and badly
under-reports. Render the pages and read `document.images` instead — every page is
same-origin now, so an iframe over the sitemap does it. That is how the seventh
repo (`reflection-page`) was found after six had been listed.

## Responsive images: `img/derived/` is generated, `img/` is the source

Every raster the site serves has AVIF and WebP copies under `img/derived/`, and
the pages ask for those. The originals under `img/` never move and are still what
a `<picture>` falls back to, so nothing that points at them can break.

Measured on the homepage, which is the worst case: **3,142KB of raster down to
1,380KB.** Where that came from is worth knowing, because it was not where it
looked:

| | before | after |
|---|---|---|
| the logo | 521KB | 28KB |
| seven footer icons | 262KB | 11KB |
| twelve collection cards | 1,367KB | 608KB |
| the mosaic tiles | 896KB | 638KB |

The logo and the icons were nearly a quarter of the page on their own: 256–500px
files in a **26px** slot. The mosaic, which looks like the extravagance, was
already tiled at 160 and 320px and had the least to give. Measure before
optimising here; the eye is wrong about which of these is heavy.

### Three mechanisms, because one does not fit

`<picture>` is the good answer and it works for 118 of the tags. It cannot be
used everywhere, and the reason is specific: **inside a `<picture>`, the
`<source>` elements win a later assignment to `img.src`.** Anything the page
re-points — the mosaic as it turns over, the cards as they cycle, every lightbox
— would freeze on whatever the sources first resolved to. So:

1. **`<picture>` with `srcset`**, written by `tools/responsive-images.py` into
   the HTML. It skips any `<img>` carrying an `id`, because on this site that is
   exactly the set the scripts re-point, and the homepage crossfade pairs.
2. **One capability test and a path rewrite**, for the two families whose `src`
   does get reassigned. `index.html` tests once for WebP and `W()` maps
   `img/foo/bar.jpg` to `img/derived/foo/bar-x.webp`. The `-x` name exists so the
   page can build the path without knowing the source's dimensions.
3. **A `<picture>` built in script**, for the footer icons, which are assembled
   from data arrays and so are invisible to (1). They sit in the same 26px slot
   at every width, so three rungs and one `sizes` cover every screen.

### `sizes` is measured, not guessed

`tools/image-sizes.json` holds the CSS width each image occupies at a desktop and
a mobile viewport, read off the live pages. `sizes` is what decides which rung
the browser takes, and getting it wrong fails **silently** in both directions —
the largest file to a phone, or a soft one to a desktop. Neither logs anything.
Re-measure after a layout change: load the sitemap into an iframe and record
`getBoundingClientRect().width` per image at 1280 and at 390.

The rung widths come from those slots — desktop at 1x and 2x, mobile at 2x and
3x. **3x is a phone**, and a phone lays the page out at the mobile slot, so
pairing the desktop slot with 3x builds a 3000px copy of a picture that is never
wider than 1040. That mistake alone was 27MB.

### The order matters

```bash
python3 tools/build-images.py           # derivatives for everything measured
python3 tools/responsive-images.py      # wrap what can be wrapped
python3 tools/build-images.py --prune   # drop what no page can ask for
python3 tools/build-images.py --check   # referenced files present and current
```

The build has to run first because the rewriter can only offer a rung that
already exists, and `--prune` has to run last because until the rewriting is done
there is no way to tell a derivative nothing wants from one nothing has claimed
*yet*. Skipping the prune leaves ~25MB for galleries that build their `<img>` in
script: those are measured, so derivatives get written, and no page ever requests
one. `img/derived/` should sit around 42MB.

`check-site.py --files` verifies every srcset target and every `-x.webp`, and CI
runs it. It cannot see a *stale* derivative whose source was edited underneath
it — `build-images.py --check` does that, and it needs Pillow, which is why it is
not in CI.

Two things are deliberately left alone. **Animated GIFs**, because several of
these are the artwork and a still frame is not the artwork. And **alpha is
preserved** — flattening the logo and the icons to RGB gives a white box on a
white card, which looks fine in a thumbnail and wrong on the page.

That GIF rule is right about the artwork and was wrong about the banners, which
is the next section.

## The three moving banners are MP4, and one of them was the wrong collection

`build-images.py` skips animated GIFs on the principle that a still frame is not
the artwork. True of a byteGAN; **not** true of a banner, which is promotional
key art — a slideshow of stills with hard cuts and no movement inside a hold. So
the banners sat outside the responsive-images work entirely, and they were the
heaviest thing the site served: **18.3MB across three pages, now 1.0MB.**

`tools/build-banner.py` does the conversion and carries the reasoning. The short
version is that most of the win is not the codec. The GIF encoder wrote every
frame with its own palette and dither, so two frames of the same still differ by
a few levels everywhere — a GIF artefact, not anything the artist made, and it
denies H.264 the almost-free P-frames a static hold should give it. Collapsing
each hold to its median restores the still being quantised and roughly halves the
file again on top of the format change.

| | before | after |
|---|---|---|
| `sightseers/hero` | 6,229,097 | 430,802 |
| `perimeter-town/hero` | 6,229,097 | 335,704 |
| `painting-with-fire/hero` | 5,821,513 | 269,009 |

Each is now `<video autoplay muted loop playsinline>` inside the `header`, with
`.hero video{position:absolute;inset:0;object-fit:cover;z-index:0}`. The header
keeps a `background-image` pointing at the poster, so one file does three jobs:
first paint, the fallback if the video never arrives, and what
`prefers-reduced-motion` leaves on screen once the rule hides the video. The
poster is **the frame the loop opens on**, so playback starts without a jump.

### SIGHTSEERS had no banner of its own

Those first two rows were the same 6.2MB file, byte for byte — lettered
SIGHTSEERS / PERIMETER TOWN / A NORMAN HARMAN AI COLLABORATION, made 30 May 2023,
four days before the Perimeter Town release and eight months after SIGHTSEERS. It
is Perimeter Town's key art, on both pages. The original sovrn.art had the same
error, so it arrived here honestly: `sites-bg.mjs` read each page's computed
background off the live site, per slug, and both pages handed it that file. It is
the same failure as the Raster links two collections carried from a neighbour.

`--sightseers` composes the replacement, and two things about it are deliberate.

**The type is lifted, not re-set.** No font here matches the artist's exactly, so
rather than guess the face, take the pixels: the lettering is the only thing that
holds still across all 44 frames, which makes a min-projection an almost perfect
alpha matte. SIGHTSEERS and the credit line were already the strings this page
wants; only PERIMETER TOWN is dropped. That makes the two pages siblings rather
than approximately alike — and it is why `perimeter-town/hero.gif` stays in the
tree though no page points at it any more. **It is the source of the lettering.**

**Every frame has to be a work this collection can claim.** The banner exists
because a page was showing another collection's key art, so getting that wrong
inside it would be worse than leaving it alone. `sightseers tableau.jpg` is the
obvious source — four works, 3795x2493, named for the collection — and it is
excluded, because its bottom-left quadrant is Perimeter Town's own `02.jpg`.
Check any new source against `img/pages/perimeter-town/` before using it.

Four of the eight works sit outside this repo, under `~/Pictures`; `--sightseers`
names the missing ones and stops rather than quietly composing a shorter loop.

`check-site.py` now sees banners at all. `ATTR` matched `src` and `href`, and a
banner is a `url()` in a style attribute, so **no check on this site had ever
looked at a hero image** — which is how a page could show the wrong collection
through every green run. `CSSURL` covers them now, and `poster` joins `ATTR`.

## Every collection page hands across one of its own works

`transitions.css` names one element per page (`.vt-lead`) and the navigation
hands that element across. For that to look like anything, the named element has
to be **near the top and belong to the collection**. It was not: on most of these
pages the first artwork sat 700 to 1500px down, so the navigation worked and flew
the artwork off the bottom of the screen to reach it.

There are two arrangements, because these pages are not built alike.

**Eight pages open with a banner, and the banner is what travels.** The `header`
itself carries `vt-lead`, so the card opens out into it. Note *why* the header is
named rather than an image: five of the eight banners are a CSS
`background-image`, which can never carry a `view-transition-name` because it is
not an element — naming the box takes the background with it. The other three are
now a `<video>` and could carry the name themselves, and deliberately do not:
naming the header keeps all eight arranged the same way, and the poster the video
sits over is the header's background regardless. `::view-transition-old/new(art)` are set to
`object-fit: cover`, since a square work left to `fill` visibly squashes itself
into a wide banner for the length of the animation.

**Five have no banner to grow into and show a plate:** `figure.vt-plate`, one
work from the collection, under the title block, set in the reading column rather
than centred because those pages are set left. Two things about it are
deliberate:

- **The plate is the same file the homepage card shows** — a morph of one
  picture rather than a cross-fade between two, and already in cache on arrival.
  `curated-data.js` holds that mapping; if a card's image changes, change the
  plate with it.
- **It is not cropped to the card's square.** A centre crop on Latent Couture
  takes the headpieces off. The morph survives a change of aspect ratio; the
  artwork does not survive the crop.

byteGANs is the one banner page still using a plate rather than its banner.

A page must name **exactly one** element. Two under one name make the browser
drop the pairing silently rather than complain. Reflection and CENTS already
opened with a work of their own and were left alone.

## Writing for the site

The reference for prose voice is the **Concept text on `/curated/reflection`**. Read it
before writing anything substantial and match it. What it does, concretely:

- Third person, present tense, declarative. **No second person and no imperatives** — not in
  the body and not in headings. Headings are plain noun phrases: *Concept*, *On-chain*,
  *Resolution*, *Verification*.
- **Single quotes** for coined terms, with the stop inside: `'Reflective AI.'`
- **Spaced en dashes** for a parenthetical break, never em dashes.
- **No Oxford comma**: *splashes, drips and blending*.
- *Reflective AI* capitalised. Collection names set plain in this register, not italic.
- Figures spelled out in prose, left as numerals in tables and code.

### Strip the constructions that read as machine-written

Prose for this site gets a pass for these before it ships. They are not stylistic
preferences; they are the specific habits that make text read as generated, and they arrive
without being noticed:

- **The balanced antithesis**, above all `X rather than Y` and `not X, but Y`. One in a page
  is prose. Five is a signature. This is the single most reliable tell.
- Formulas that announce an insight: `This is where …`, `is the evidence that`,
  `is the signature of`, `what emerges is`, `serves as`, `stands as`.
- Ornamental qualifiers: `in consequence`, `in the strong sense of the word`,
  `which is a matter of record`, `while appearing to succeed`.
- The vocabulary: delve, tapestry, realm, testament, underscore, showcase, seamless, robust,
  pivotal, crucial, harness, unlock, multifaceted.
- Sentence-initial *Moreover*, *Furthermore*, *Indeed*, *Notably*.
- **Uniform rhythm.** Vary sentence length deliberately, and never leave two consecutive
  sentences opening on the same word. A short sentence after a long one does the work that
  an em dash is usually reached for.

Counting beats intuition here — grep the draft for `rather than` and for repeated sentence
openings, because both are invisible while writing and obvious when read.

## The share pages no longer depend on any service of ours

They used to. `share.js` reads `tokenURI` for the three on-chain collections, and
its endpoint list ended with **Sovrn's own read-only proxy**, on a Railway host,
because crypto RPC hostnames sit on the "NoCoin"/cryptomining filter lists that
uBlock Origin, AdGuard, Brave Shields and DNS filters ship or enable by default.
A visitor running any of those got "Failed to fetch" on every work while the page
itself loaded fine — the title index being same-origin — and that combination is
still the diagnosis if it ever recurs. It looks like a contract or chain problem
and is neither: "Failed to fetch" is a `TypeError` from the Fetch API, meaning
the request never left the browser. An RPC that is merely down *answers*.

**The proxy was retired in August 2026** along with the chatbot that housed it,
and what made that safe is the mirror below: `/onchain/` holds **all 2,218 works**
of the three collections, same-origin, so a filtered visitor never reaches the
RPC list at all. Verified before removing it — a search on the live share page
resolves entirely from `/onchain/` with zero RPC requests.

Two public RPCs remain in the list as a fallback for a mirror miss. They belong
to no one here and cost nothing. In practice they are unreachable: the mirror
holds exactly the 2,218 works the index lists.

**If artwork ever fails for ad-blocked visitors again**, that is the diagnosis,
and the service is preserved ready to redeploy at
[`shibboleth88/sovrn-eth`](https://github.com/shibboleth88/sovrn-eth) — four
files, Express only, with its reasoning written down. Redeploy it, add its URL
back to `RPCS` in `share.js`, and set `ETH_PROXY_ORIGINS` to the site's origin
before the change, not after.

## Reflection is ~144 contracts, not one

`share.js` reads `tokenURI` from `0x5137cfB4…`, and that is the right address to
call. It is not, however, "the Reflection contract" in any complete sense, so do
not write copy that says so.

Tracing real calls across 20 tokens: rendering one work touches **31** contracts —
13 shared by every work, plus 18 token-specific ones drawn from a pool estimated at
~131. Call it ~144 for the collection, as a floor.

Two consequences that matter here:

- **Responses are large by design.** One `tokenURI` returns ~163KB, assembled from
  ~170KB of bytecode across those 31 contracts. That is why an RPC that truncates
  or size-limits responses fails on this collection specifically — `cloudflare-eth`
  is already excluded from the harvester for exactly this reason.
- **The artwork is stored, not recomputed.** The generative process ran once at
  mint and was written to chain, which is why the works are immutable and why the
  mirrored SVGs in `sovrn-onchain` can never drift.

Full detail, including why static analysis of the bytecode gives a badly wrong
answer, is in `sovrn-onchain/CLAUDE.md`.

## Related repositories

| repo | what it holds |
|---|---|
| `sovrn-onchain` | every on-chain work as static SVG, plus `tools/` and `data/` — including `share.py`, which builds post-ready files |
| `sovrn-bot` | the retired chatbot, archived August 2026 |
| `sovrn-eth` | the `/api/eth` proxy, extracted from it and not currently deployed |
| `moca-submission` | the MOCA library documents and the vanarman.com archive |
