# sovrn-onchain

The artwork of Sovrn's three fully on-chain collections, as static SVG files.

| collection | works | token ids | size |
|---|---|---|---|
| [Reflection](https://www.sovrn.art/curated/reflection) — Pindar Van Arman | 999 | 0–998 | 85 MB |
| [Wunderkammer](https://www.sovrn.art/curated/wunderkammer) — Isa Kost | 108 | 1–108 | 4.0 MB |
| [byteGANs](https://www.sovrn.art/curated/bytegans) — Pindar Van Arman | 1,111 | 1–1111 | 4.3 MB |

`<collection>/<token>.svg` — so Reflection token 0 is `reflection/0.svg`. **Reflection is
0-indexed and the other two are 1-indexed**, which is the mistake everyone makes: a
Reflection token id is the artist's list number minus one.

## Where these came from

Each file is the **exact bytes the contract returns** — `tokenURI(id)` gives base64 JSON
whose `image` is a base64 SVG, and that SVG is what is stored here, decoded and otherwise
untouched. Nothing was re-rendered, re-compressed or cleaned up. All 2,218 were written by
[`tools/harvest-onchain.py`](tools/harvest-onchain.py) in this repo, which can also
re-read a spread of them from chain and byte-compare:

```bash
python3 tools/harvest-onchain.py --verify
```

Because these works are fully on-chain and immutable, the files cannot go stale. Anyone
can reproduce them from the contracts:

- Reflection `0x5137cfb461d24040f5ce6b85d860c47a24f85412`
- Wunderkammer `0x976A8Abe425dc8d7cE7736C54834DbB720695b76`
- byteGANs `0x45c67b2b81067911de611e11fc5c7a4605ca4162`

## Why it exists

[The share tool](https://shibboleth88.github.io/sovrn-pages/share.html) read the contracts
live from the browser. Crypto RPC hostnames sit on the cryptomining filter lists that
uBlock Origin, AdGuard, Brave Shields and DNS filters ship by default, so for a good share
of visitors every work failed with "Failed to fetch" — the request never left the browser.

Served from GitHub Pages, these files sit on the **same origin as the share page**
(`shibboleth88.github.io`), which is the only arrangement with exactly the same
availability as the page itself: if they are unreachable, there is no page either. Every
other option adds a host that can be blocked or go down. They are also *smaller* — one
Reflection work is ~21 KB gzipped here against ~338 KB of hex over an RPC call.

## Note on byteGAN #469

Its on-chain metadata is malformed — an `attributes` entry has an unquoted key, so
`JSON.parse` fails. The contract is immutable, so the harvester reads the `image` field
with a regex instead. Without that, one work in 2,218 would be silently absent.

---

Artwork © the artists. Reflection and byteGANs © Pindar Van Arman; Wunderkammer © Isa Kost.
Published by [Sovrn Art](https://www.sovrn.art/) as a reading copy of work the artists put
on-chain.
