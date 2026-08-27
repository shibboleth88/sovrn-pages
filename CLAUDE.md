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

## The share pages depend on a service in another repo — do not remove it

`share.js:247` lists three Ethereum endpoints, tried in order:

```
https://ethereum-rpc.publicnode.com
https://eth.drpc.org
https://sovrn-bot-production.up.railway.app/api/eth     <- the important one
```

Seven shells load it, in two families that differ only in which root they assume:

| where | why it exists |
|---|---|
| `/share.html`, `/share-<slug>.html` | addressed from outside this repo and cannot move — **vanarman.com iframes `share-reflection.html`** |
| `/shareable/share-<slug>/` | canonical for sovrn.art; the flat ones point `rel=canonical` here |

They read `tokenURI` straight from the three on-chain contracts, so without a
reachable RPC there is no artwork.

**The flat shells carry no `<base>` and set `SHARE_ROOT = "./"` instead.** That is
not stylistic. Van Arman's iframe still addresses
`shibboleth88.github.io/sovrn-pages/share-reflection.html`, which now 301s to
`www.sovrn.art/share-reflection.html` — but if it is ever loaded from a project
page directly, `<base href="/">` would resolve every asset against the wrong root.
`tools/check-share-pages.py` fails if a flat shell grows a `<base>` or loses
`SHARE_ROOT`.

**The third entry is not a redundant fallback. For a large group of visitors it is
the only one that works.** Crypto RPC hostnames sit on the NoCoin/cryptomining
filter lists shipped by uBlock Origin, AdGuard, Brave Shields and various DNS
filters. Those visitors never reach the first two — the request does not leave the
browser. The proxy host is not a crypto domain, so the lists do not touch it.

The failure this prevents is easy to misdiagnose. It looks like a chain or
contract problem and is neither:

- **"Failed to fetch" is a `TypeError` from the Fetch API** — the request never
  completed at the network layer. An RPC that is merely down or rate-limiting
  *answers*, and the page shows that message instead.
- **The page itself loads fine** for the same visitor, because the title index is
  same-origin. Page fine, every artwork broken, is the signature.

### Its repository is being retired, and that is fine

`sovrn-bot` is being sunset as a chatbot. The `/api/eth` route is not part of the
bot — it is one line in `server.js` over a self-contained `src/ethproxy.js` that
never touches the chat engine. Retiring the chat does not require taking the
service down, and it must not.

If the Railway service ever does go away, this repo needs the endpoint replaced
before that happens, not after. Removing the line from `share.js` is not a fix —
it is the breakage.

Verified working 2026-08-25, **after the migration and from the new origin**: an
`eth_call` for `tokenURI` on the Reflection contract returns the full 338KB work,
with the preflight answering `access-control-allow-origin: https://www.sovrn.art`.
The proxy's allowlist already contained the apex and `www`, so the origin change
needed nothing — but it is an allowlist, not `*`, so **a future origin change does
need `ETH_PROXY_ORIGINS` updated in Railway first.**

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
| `sovrn-bot` | the retiring chatbot; still hosts the `/api/eth` proxy above |
| `moca-submission` | the MOCA library documents and the vanarman.com archive |
