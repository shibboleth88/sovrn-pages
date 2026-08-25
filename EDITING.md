# Editing sovrn.art

Short version for anyone with write access. **This repository is the live site.**
Push to `main` and sovrn.art changes about a minute later. There is no staging
step and no separate deploy — the push *is* the deploy.

## Making a change

```bash
git clone https://github.com/shibboleth88/sovrn-pages.git
cd sovrn-pages
# edit
python3 tools/check-site.py --urls https://www.sovrn.art   # see "Before you push"
git commit -am "what changed"
git push
```

Give it a minute, then reload sovrn.art. If it looks unchanged, it's browser
cache — hard-reload before assuming the push failed.

## Where things are

| path | what it is |
|---|---|
| `index.html` | the homepage |
| `curated/<collection>/` | the fifteen collection pages |
| `cents/` | CENTS and its sub-pages |
| `exhibitions/`, `collections/`, `museums/` | shows and placements |
| `shareable/`, `share*.html` | the GIF export tool |
| `img/` | most of the site's images |
| `onchain/` | 2,218 on-chain artworks as SVG — the share tool reads these. Don't hand-edit |
| `tools/` | the checkers below |

Each page is a single self-contained HTML file — styles and data inline, no build
step, no framework. Edit it and it's done.

## Before you push

Three rules, in order of how much damage breaking them does.

**1. Don't change a URL.** Renaming or moving a file changes a live address.
Outside sites link these, X posts point at them, and museums cite them. If a page
genuinely must move, leave a redirect stub behind — copy the shape of one of the
`*.html` files at the repo root.

> This one has teeth for you specifically, Pindar: **vanarman.com/sharable iframes
> `share-reflection.html` from this repo.** Move or rename that file and your own
> page goes blank.

**2. Run the checkers.** They take seconds and they are the only gate:

```bash
python3 tools/check-site.py --urls https://www.sovrn.art     # all 47 URLs still resolve
python3 tools/check-site.py --assets https://www.sovrn.art   # no broken images or links
python3 tools/check-share-pages.py                           # the share tool's pages agree
```

Run the first one *before* pushing too — it checks the live site, so a clean run
before and after tells you whether you broke something or it was already broken.

**3. Keep images in this repo.** Everything the site shows lives under `img/` —
add new pictures there and reference them as `/img/...`. Don't link an image from
another GitHub repo, an S3 bucket or anywhere else: an outside host can be
blocked, rate-limited or deleted without warning, and the page is then broken
with nothing here to explain why. A file served from this repo has exactly the
site's own availability — if it can't be reached, there's no page either.

The site used to load its homepage tiles and museum photographs from repos under
another account; they were brought in on 25 August 2026 and the site no longer
depends on anything external for imagery.

## Two things that will look like bugs and aren't

- **`/museums/fransisco-carolinum` is misspelled on purpose.** It's the live URL.
  Correcting it 404s. Fix the spelling in prose only; a test pins the path.
- **Reflection token ids are the artist's list number minus one** — the list runs
  1–999, the ids run 0–998. Wunderkammer and byteGANs are 1-indexed, so for those
  the id *is* the number.

## If you're working with Claude

`CLAUDE.md` is written for that and gets picked up automatically. `NOTES.md` is
the long-form record of everything that cost real time to work out — worth
searching before concluding something is broken. `MIGRATION.md` covers the move
off Google Sites in August 2026, including why the share pages are shaped oddly.

Questions: Ezra (sovrnart@gmail.com).
