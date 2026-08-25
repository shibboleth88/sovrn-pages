# sovrn-pages

**This repository is sovrn.art.** It is served directly at
[www.sovrn.art](https://www.sovrn.art) from GitHub Pages. A push to `main` is a
deploy; there is no staging step.

Before it moved, on 25 August 2026, these files were embedded into a Google Sites
site. [`MIGRATION.md`](MIGRATION.md) records how the move was done, the 47-URL
contract it had to preserve, and what it cost to find out.

Start with [`CLAUDE.md`](CLAUDE.md) — the short version of what can break the live
site. [`NOTES.md`](NOTES.md) is the long-form record: how the Reflection cascade is
rebuilt from the minted files, how artwork is harvested from raster.art, how to
verify any of it, and — now as history — how Google Sites behaved.

```bash
python3 tools/check-site.py --urls https://www.sovrn.art     # all 47 URLs resolve
python3 tools/check-site.py --assets https://www.sovrn.art   # no asset 404s
python3 tools/check-share-pages.py                           # the share shells agree
```
