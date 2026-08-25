# sovrn-pages — operating notes

Hosted HTML embedded into the Google Sites site at sovrn.art. Served from GitHub
Pages at `https://shibboleth88.github.io/sovrn-pages/`.

Most of what you need is in [`NOTES.md`](NOTES.md) — how Sites embedding behaves,
how to get content back out of it, how to reconstruct a page faithfully. This file
covers the one thing that can break the live site from outside this repository.

## The share pages depend on a service in another repo — do not remove it

`share.js:244` lists three Ethereum endpoints, tried in order:

```
https://ethereum-rpc.publicnode.com
https://eth.drpc.org
https://sovrn-bot-production.up.railway.app/api/eth     <- the important one
```

Four pages load it: `share.html`, `share-reflection.html`, `share-bytegans.html`,
`share-wunderkammer.html`. They read `tokenURI` straight from the three on-chain
contracts, so without a reachable RPC there is no artwork.

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

Verified working 2026-08-25: an `eth_call` for `tokenURI(884)` on the Reflection
contract returns the full work with `access-control-allow-origin` correctly set to
the GitHub Pages origin.

## Related repositories

| repo | what it holds |
|---|---|
| `sovrn-onchain` | every on-chain work as static SVG, plus `tools/` and `data/` — including `share.py`, which builds post-ready files |
| `sovrn-bot` | the retiring chatbot; still hosts the `/api/eth` proxy above |
| `moca-submission` | the MOCA library documents and the vanarman.com archive |
