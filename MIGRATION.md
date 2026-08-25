# Moving sovrn.art off Google Sites onto GitHub Pages

A plan, not a decision. Written 25 August 2026 from a full survey of the live site,
so the numbers in it are measured rather than estimated. Re-check them before
starting if much time has passed.

---

## Why this is smaller than it sounds

**34 of the 39 live URLs are already HTML in this repository.** Google Sites is a
frame around pages we author; it hosts almost none of the content. The survey:

| | count | |
|---|---|---|
| Full-page embeds of `sovrn-pages` HTML | **34** | nothing to migrate — they already exist |
| Native Sites pages | **4** | `/about`, `/curated`, `/cents/cents-in-tachens-on-nfts`, `/cents/artist-obituary` |
| Broken | **1** | ~~`/curated/reflection/further-details`~~ — resolved 25 Aug by dropping the link; the URL still 404s but nothing points at it |

The four native pages are 322, 159, 405 and 74 words. Their images are
Google-hosted signed URLs — those can be downloaded at their current size but
**never resized in the URL**, which 403s (`NOTES.md`).

## What we gain

- **Per-page cards.** Sites emits one site-wide `og:image` and gives no way to set
  it per page, so today *every* sovrn.art link unfurls on X with the same 1024×1024
  magenta logo. On Pages every meta tag is ours, and per-work cards become possible.
  This is currently impossible, not merely unfinished.
- **The sandbox constraint disappears.** Every `target="_blank"` in this repo exists
  because the Sites embed iframe omits `allow-top-navigation`. So does the `< >`
  full-page-embed dance and its mobile aspect-ratio trap.
- **No Google cookie banner.** The live site currently shows one; GitHub Pages sets
  no cookies and runs no analytics.
- Real `<title>` per page, a 404 page, and the whole site under one git history.

## What we lose

- The Sites WYSIWYG editor. Anyone who edits through it would need git.
- Sites' built-in search box.
- Whatever Sites analytics are in use — worth checking before committing.

---

## The approach

The awkward part is that files here are flat (`reflection.html`) while the URLs are
nested (`/curated/reflection`). Preserving URLs means real directories:

```
curated/reflection/index.html
collections/fransisco-carolinum/index.html      <- misspelling preserved exactly
shareable/share-reflection/index.html
```

Moving a file into a directory breaks every relative path in it, and there are
**216** of them across 38 files — some assembled in JavaScript, where a blind
find-and-replace would mangle them.

**`<base href="/">` fixes all 216 at a stroke**, one line per page. Its one real
hazard is that it also rewrites in-page anchors, sending `#concept` to the
homepage. There are **3 such anchors, in 2 files** (`cents.html`, `reflection.html`),
both built in script. That is the entire exposure, and it is a two-line fix.

### The work

| step | what | how |
|---|---|---|
| 1 | 42 files into URL-shaped directories | scripted |
| 2 | `<base href="/">` into each | scripted |
| 3 | Fix the 3 script-built anchors to `location.pathname + "#id"` | by hand |
| 4 | `share.js`: `BASE` becomes `"/"` — it is derived from `location.pathname` and would otherwise resolve to the page's own directory | one line |
| 5 | `share.js`: `ART` becomes an absolute `https://shibboleth88.github.io/sovrn-onchain/` | one line |
| 6 | Rebuild the 4 native pages, downloading their Google-hosted images | the only real authoring |
| 7 | Fix the `/curated/reflection/further-details` 404 — write the page or drop the link | small |
| 8 | `CNAME`, DNS, certificate | minutes |

**Step 5 matters and is easy to get wrong.** `../sovrn-onchain/` resolves correctly
today only because pages sit at `/sovrn-pages/`. Served at the domain root it would
point at `www.sovrn.art/sovrn-onchain/`, which does not exist, and every artwork
would silently fall back to the RPC chain. The absolute URL works because GitHub
Pages sends `access-control-allow-origin: *` (verified), and because the page
converts the fetched SVG to a `data:` URI rather than assigning it to `img.src` —
so the canvas still does not taint and the GIF export is unaffected.

`sovrn-onchain` keeps serving from `shibboleth88.github.io` throughout. A custom
domain on one repo does not disturb another.

---

## What happens to the live site while this is done

**Nothing, if the work stays off `main`.**

This is the single most important operational point. The live site is Google Sites
embedding **flat file URLs** — `shibboleth88.github.io/sovrn-pages/reflection.html`.
Step 1 moves that file to `curated/reflection/index.html`. **Doing that on `main`
would break every page on sovrn.art the moment Pages rebuilt**, and would stay
broken until DNS moved.

So:

- Do the whole restructure on a **branch**, or in a scratch repo with its own Pages
  URL for a true dry run.
- `main` keeps serving the flat files, and sovrn.art keeps working, untouched, for
  the entire duration.
- Verify locally by serving the restructured tree **at a root**, since `<base href="/">`
  only behaves correctly there. `python3 -m http.server` from the tree root does it.
- The site changes exactly once: at the cutover.

## Leave stubs at the old flat paths

The restructure moves `share.html` to `shareable/index.html` and so on, which
changes the **`shibboleth88.github.io/sovrn-pages/...`** URLs. Those are a
different namespace from sovrn.art's, and other people embed and link them —
vanarman.com embeds the share tool, and any link posted anywhere points at
whatever URL was current when it was posted.

So leave a thin redirect at every old flat path: a few lines of HTML that send the
browser to the new location, one per file. It costs nothing, it protects links we
do not know about, and it means **nobody outside this repo has to change anything
at cutover**. Without them, an embed goes blank the moment the file moves — and
the owner of that page would have no idea why.

**A known one:** `https://www.vanarman.com/sharable` embeds
`shibboleth88.github.io/sovrn-pages/share-reflection.html` in a plain, unsandboxed
iframe. That exact file moves in the restructure, so it needs a stub. Its iframe
carries no `sandbox` attribute, so any redirect technique works there and the tool
keeps its full capability, downloads included.

Keep the query string when redirecting: `share.html?c=reflection` has to land on
the scoped page, not the combined one.

### Write them as meta-refresh plus canonical, and keep them one hop

```html
<link rel="canonical" href="https://www.sovrn.art/shareable/share-reflection">
<meta http-equiv="refresh" content="0; url=/shareable/share-reflection">
```

GitHub Pages cannot emit a 301, and this is the convention it supports —
`jekyll-redirect-from` generates exactly this shape. Search engines treat a
meta-refresh as a redirect, and the canonical removes any duplicate-content
ambiguity.

This pattern is not the kind of thing that gets a site flagged. What does is an
**open redirect** — a `?url=` parameter forwarding anywhere, which phishing abuses
— or **cloaking**, serving crawlers something other than what people see. These
have a fixed destination compiled into the file and are identical for everyone.
Two rules keep it that way: never let a stub point at another stub, and never take
the destination from a query parameter.

## Cutover

1. Merge the branch. Pages rebuilds; `shibboleth88.github.io/sovrn-pages/` now
   serves the new structure. **sovrn.art breaks at this moment** — its embeds point
   at paths that have moved. This is the window, and it should be short.
2. Add `CNAME` containing `www.sovrn.art`; point the `www` record at
   `shibboleth88.github.io`. The apex already redirects to `www` via Squarespace and
   can stay as it is.
3. Provision the certificate — **it does not always start on its own.** On the
   `preview.sovrn.art` rehearsal every DNS precondition was already satisfied
   (`dns_resolves` true, `is_cname_to_github_user_domain` true, `is_served_by_pages`
   true, not proxied, no CAA error) and Pages still sat at `https_certificate: null`
   with `https_eligible: null` — no cert requested, HTTPS simply refusing connections.
   Clearing the custom domain and setting it again started it immediately: `authorized`
   at once, `approved` and serving HTTPS within about a minute.

   ```bash
   gh api -X PUT repos/shibboleth88/sovrn-pages/pages -f cname=""
   gh api -X PUT repos/shibboleth88/sovrn-pages/pages -f cname="www.sovrn.art"
   gh api repos/shibboleth88/sovrn-pages/pages --jq '.https_certificate.state'
   ```

   Then enforce it, and confirm the `CNAME` file survived the round-trip (the API
   rewrites it, and a later `rsync` that excludes `CNAME` will not restore it):

   ```bash
   gh api -X PUT repos/shibboleth88/sovrn-pages/pages -F https_enforced=true
   ```

   The point for timing: **sovrn.art is down for this whole step.** Don't budget the
   optimistic case — plan on doing the re-set, not on waiting to see whether you need to.
4. Walk the 39 URLs and confirm every one resolves.

**Rollback is a DNS record.** Point `www` back at `ghs.googlehosted.com` and revert
the merge; the flat files return and Sites serves them again. Minutes, not hours.

Prefer a quiet window, and do not start one without time to finish it.

---

## Risks

Ordered by how much damage each can do.

1. **Restructuring on `main`.** Breaks the live site immediately, before any DNS
   change can help. *Mitigation: branch or scratch repo, never `main`.*
2. **A URL changing.** Anything that 404s breaks inbound links — X posts, other
   sites, Van Arman's pages, anywhere the collection pages are cited. *Mitigation:
   the 39-URL inventory above is the contract; a checker asserts every one resolves
   before cutover.*
3. **The `fransisco-carolinum` misspelling.** It is the live URL and correcting it
   404s. It must survive the restructure exactly. *Pinned by the checker.*
4. **`<base href="/">` side effects beyond anchors.** Form actions and any URL built
   from a relative string also resolve differently. *Mitigation: the checker walks
   every page and asserts no asset 404s; `share.js` uses `BASE` explicitly, which
   step 4 handles.*
5. **Fidelity of the four rebuilt pages.** Their text is recoverable and their images
   downloadable, but they are hand-rebuilt and could lose detail. *Mitigation: they
   are small; compare against the live pages before cutover.*
6. **The certificate window.** Between the CNAME resolving and Pages issuing a
   certificate, HTTPS fails outright. Confirmed on the rehearsal, and worse than
   "can" suggests: Pages never requested the certificate at all until the custom
   domain was cleared and re-set, so waiting patiently would have waited forever.
   *Mitigation: cutover step 3 does the re-set as a matter of course; keep rollback
   to hand.*
7. **Colliding with the other Claude instance.** A 42-file move conflicts with
   anything in flight. *Mitigation: do not start until the repo is quiet.*
8. **Repo weight.** `img/` is 175MB and `.git` 201MB. Pages' soft ceiling is 1GB, so
   there is room, but it is worth watching rather than forgetting.

## Verification

Write the checker before the restructure, not after. It should:

- walk all 39 URLs from the inventory and assert each returns 200;
- parse every page and assert no `src`/`href` resolves to a 404;
- assert `fransisco-carolinum` is spelled exactly that way;
- assert `share.js` resolves the mirror to an absolute `sovrn-onchain` URL;
- run the share tool end to end — search, trait filter, open a work, render a GIF —
  with the RPC endpoints disabled, so it proves the mirror path.

## Settled

- **No Sites analytics are in use.** Nothing to replace.
- **Only git edits these pages** — no one is authoring through the Sites editor, so
  losing that editor costs nothing.
- **`/open` is retired and is meant to 404.** Sovrn Open was live on Sites and is
  deliberately not carried over — decided at cutover, 25 August 2026. It is absent
  from the URL contract on purpose, so a later pass that "finds a missing page"
  should leave it alone. Its images were on Google Sites signed URLs and are gone
  with the site; rebuilding it later means sourcing them again.

### The hand-written inventory was wrong three times

The 44 URLs were listed by hand rather than crawled, and diffing the contract
against the live site before cutover found four it did not have:

| URL | What it was | Resolution |
|---|---|---|
| `/cents/taschen` | live, and we had rebuilt it at an invented path | moved to the real URL |
| `/home` | Sites serves the homepage at `/` **and** `/home`, and its own nav links `/home` | stub to `/` |
| `/contact` | a native Sites page, so no file in this repo to notice it | rebuilt |
| `/curated/cents` | a second path onto the CENTS page | stub to `/cents` |
| `/open` | Sovrn Open | retired, see above |

Sites publishes no sitemap and renders its nav in JavaScript, so nothing can be
crawled out of it — the gap was only findable by probing candidate URLs against
the live site. Worth repeating if the site is ever moved again.

## What to do with `sovrn-onchain`

It is the artwork mirror the share tool reads: 2,218 works as static SVG, 93MB, of
which Reflection alone is 85MB. It also now carries the CLI tools and data.

Today both repos are served from `shibboleth88.github.io`, so they are the **same
origin**, and that is the whole point of the mirror — the artwork has exactly the
availability the page has. After migration `sovrn-pages` answers at
`www.sovrn.art` while `sovrn-onchain` stays on `shibboleth88.github.io`, and they
become different origins.

Cross-origin works: Pages sends `access-control-allow-origin: *`, and the page
builds a `data:` URI rather than assigning a remote `img.src`, so nothing taints
and the GIF export is unaffected. And both being Pages, they largely fail together
anyway.

**The exception is the reason to prefer folding it in.** Some corporate and school
networks block `github.io` specifically. Those visitors would load sovrn.art
perfectly and watch every artwork fail — the same "page fine, artwork broken"
signature this mirror was built to end, arriving by a different door.

So: **move the artwork into this repo**, at `/onchain/`. It restores true
same-origin, takes the tree from ~175MB to ~270MB against Pages' 1GB ceiling, and
simplifies `share.js` — a root path instead of an absolute cross-origin URL to
maintain. `sovrn-onchain` keeps its README, `tools/` and `data/` (176KB), so the
provenance and the reproduce-it-yourself tooling survive as a citable thing.

**This does not block the migration.** It is one line in `share.js` either way, and
reversible in both directions, so it can be done first, last, or not at all.
