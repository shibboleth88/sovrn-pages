/* ------------------------------------------------------------------------- *
 * A minimal GIF89a encoder. Inline because a CDN script is blocked here and
 * producing GIFs is the whole point of the page. One palette is built across
 * every frame so colours cannot shimmer frame to frame.
 * ------------------------------------------------------------------------- */
var GIF = (function () {
  function palette(frames, maxColours) {
    var px = [];
    // A fixed sample budget across ALL frames, not per frame. Sampling per frame
    // meant 72 frames fed ~1.8M points into median cut, and the repeated sorting
    // there — not the encoding — was the bulk of the time.
    var BUDGET = 24000;
    var perFrame = Math.max(1, Math.floor(BUDGET / frames.length));
    for (var f = 0; f < frames.length; f++) {
      var d = frames[f].data, count = d.length / 4;
      var stride = Math.max(1, Math.floor(count / perFrame));
      for (var i = 0; i < count; i += stride) {
        var o = i * 4;
        px.push([d[o], d[o + 1], d[o + 2]]);
      }
    }
    var boxes = [px];
    while (boxes.length < maxColours) {
      var bi = -1, bestRange = -1, bestCh = 0;
      for (var b = 0; b < boxes.length; b++) {
        if (boxes[b].length < 2) continue;
        for (var c = 0; c < 3; c++) {
          var lo = 255, hi = 0;
          for (var j = 0; j < boxes[b].length; j++) {
            var v = boxes[b][j][c];
            if (v < lo) lo = v;
            if (v > hi) hi = v;
          }
          if (hi - lo > bestRange) { bestRange = hi - lo; bi = b; bestCh = c; }
        }
      }
      if (bi < 0 || bestRange <= 0) break;
      var box = boxes[bi];
      box.sort(function (p, q) { return p[bestCh] - q[bestCh]; });
      var mid = box.length >> 1;
      boxes.splice(bi, 1, box.slice(0, mid), box.slice(mid));
    }
    return boxes.filter(function (b) { return b.length; }).map(function (b) {
      var r = 0, g = 0, bl = 0;
      for (var i = 0; i < b.length; i++) { r += b[i][0]; g += b[i][1]; bl += b[i][2]; }
      return [Math.round(r / b.length), Math.round(g / b.length), Math.round(bl / b.length)];
    });
  }

  // 6 bits per channel -> 262,144 slots. A plain object here cost ~55s on a
  // 72-frame Reflection; a typed array does the same work in a couple of seconds.
  function newMemo() {
    var m = new Int16Array(1 << 18);
    m.fill(-1);
    return m;
  }

  function nearest(palFlat, n, r, g, b, memo) {
    var key = ((r >> 2) << 12) | ((g >> 2) << 6) | (b >> 2);
    var hit = memo[key];
    if (hit >= 0) return hit;
    var best = 0, bd = Infinity;
    for (var i = 0, j = 0; i < n; i++, j += 3) {
      var dr = r - palFlat[j], dg = g - palFlat[j + 1], db = b - palFlat[j + 2];
      var d = dr * dr * 0.3 + dg * dg * 0.59 + db * db * 0.11;
      if (d < bd) { bd = d; best = i; }
    }
    memo[key] = best;
    return best;
  }

  // The dictionary is keyed (prefix << 8) | nextByte, so it fits an Int32Array of
  // 2^20 — the same object-versus-typed-array difference as the colour cache.
  var LZW_DICT = new Int32Array(1 << 20);

  function lzw(indices, minCodeSize) {
    var out = [], cur = 0, curBits = 0;
    function emit(code, size) {
      cur |= code << curBits;
      curBits += size;
      while (curBits >= 8) { out.push(cur & 255); cur >>= 8; curBits -= 8; }
    }
    var clear = 1 << minCodeSize, eoi = clear + 1;
    var size = minCodeSize + 1, next = eoi + 1;
    LZW_DICT.fill(-1);
    emit(clear, size);
    var prefix = indices[0];
    for (var i = 1; i < indices.length; i++) {
      var k = indices[i], key = (prefix << 8) | k;
      var hit = LZW_DICT[key];
      if (hit >= 0) { prefix = hit; continue; }
      emit(prefix, size);
      LZW_DICT[key] = next++;
      if (next > (1 << size)) {
        if (size < 12) size++;
        else {
          emit(clear, size);
          LZW_DICT.fill(-1);
          next = eoi + 1;
          size = minCodeSize + 1;
        }
      }
      prefix = k;
    }
    emit(prefix, size);
    emit(eoi, size);
    if (curBits > 0) out.push(cur & 255);
    return out;
  }

  /**
   * frames: [ImageData] all the same size. Returns a Blob.
   *
   * Frames after the first are encoded as **only the rectangle that changed**,
   * with unchanged pixels left transparent so the previous frame shows through
   * (disposal "do not dispose"). Writing every frame in full is what made the
   * Reflection cascade too heavy to give enough frames to look smooth.
   */
  function encode(frames, delaysMs, maxColours) {
    var w = frames[0].width, h = frames[0].height;
    // One palette entry is spent on transparency.
    var pal = palette(frames, (maxColours || 256) - 1);
    var transparent = pal.length;
    var bits = Math.max(2, Math.ceil(Math.log2(Math.max(2, pal.length + 1))));
    var palSize = 1 << bits, memo = newMemo();
    // Growable byte buffer: pushing one byte at a time into a JS array over a few
    // megabytes is itself a measurable cost.
    var buf = new Uint8Array(1 << 20), len = 0;
    function need(n) {
      if (len + n <= buf.length) return;
      var b2 = new Uint8Array(Math.max(buf.length * 2, len + n));
      b2.set(buf.subarray(0, len));
      buf = b2;
    }
    var out = {
      push: function () {
        need(arguments.length);
        for (var ai = 0; ai < arguments.length; ai++) buf[len++] = arguments[ai];
      }
    };
    // Flat Uint8Array beats an array of triples inside the hot loop.
    var palFlat = new Uint8Array(pal.length * 3);
    for (var pi = 0; pi < pal.length; pi++) {
      palFlat[pi * 3] = pal[pi][0];
      palFlat[pi * 3 + 1] = pal[pi][1];
      palFlat[pi * 3 + 2] = pal[pi][2];
    }
    function short_(v) { out.push(v & 255, (v >> 8) & 255); }

    "GIF89a".split("").forEach(function (c) { out.push(c.charCodeAt(0)); });
    short_(w); short_(h);
    out.push(0x80 | ((bits - 1) & 7), 0, 0);
    for (var i = 0; i < palSize; i++) {
      var c = pal[i] || [0, 0, 0];
      out.push(c[0], c[1], c[2]);
    }
    out.push(0x21, 0xFF, 11);
    "NETSCAPE2.0".split("").forEach(function (c) { out.push(c.charCodeAt(0)); });
    out.push(3, 1, 0, 0, 0);

    var prev = null, prev32 = null;
    for (var f = 0; f < frames.length; f++) {
      var cur = frames[f].data;
      // Compare whole pixels as 32-bit words rather than three byte tests.
      var cur32 = new Uint32Array(cur.buffer, cur.byteOffset, w * h);
      var x0 = 0, y0 = 0, fw = w, fh = h;

      if (prev) {
        // bounding box of what actually moved
        var minX = w, minY = h, maxX = -1, maxY = -1;
        for (var y = 0; y < h; y++) {
          var row = y * w;
          for (var x = 0; x < w; x++) {
            if (cur32[row + x] !== prev32[row + x]) {
              if (x < minX) minX = x;
              if (x > maxX) maxX = x;
              if (y < minY) minY = y;
              if (y > maxY) maxY = y;
            }
          }
        }
        if (maxX < 0) { minX = minY = 0; maxX = maxY = 0; }   // nothing moved
        x0 = minX; y0 = minY; fw = maxX - minX + 1; fh = maxY - minY + 1;
      }

      var delay = Math.max(2, Math.round((delaysMs[f] || 100) / 10));  // centiseconds
      // packed: disposal 1 (leave in place) | transparent colour present
      out.push(0x21, 0xF9, 4, prev ? 0x05 : 0x04,
               delay & 255, (delay >> 8) & 255, prev ? transparent : 0, 0);
      out.push(0x2C);
      short_(x0); short_(y0); short_(fw); short_(fh);
      out.push(0);

      var idx = new Uint8Array(fw * fh), q = 0;
      for (var yy = y0; yy < y0 + fh; yy++) {
        var base = yy * w;
        for (var xx = x0; xx < x0 + fw; xx++) {
          var pxi = base + xx;
          if (prev32 && cur32[pxi] === prev32[pxi]) {
            idx[q++] = transparent;
          } else {
            var oo = pxi * 4;
            idx[q++] = nearest(palFlat, pal.length, cur[oo], cur[oo + 1], cur[oo + 2], memo);
          }
        }
      }
      out.push(bits);
      var comp = lzw(idx, bits);
      for (var sIdx = 0; sIdx < comp.length; sIdx += 255) {
        var n = Math.min(255, comp.length - sIdx);
        need(n + 1);
        buf[len++] = n;
        for (var z = 0; z < n; z++) buf[len++] = comp[sIdx + z];
      }
      out.push(0);
      prev = cur; prev32 = cur32;
    }
    out.push(0x3B);
    return new Blob([buf.subarray(0, len)], { type: "image/gif" });
  }

  return { encode: encode };
})();

/* ------------------------------------------------------------------------- */

// These three collections keep their artwork in the contract: tokenURI returns
// base64 JSON whose image is a base64 SVG. Nothing comes from a gateway, and a
// data: URI does not taint the canvas, so every work here can be rasterised and
// re-encoded. Sovrn's other collections keep their images on IPFS, which taints
// the canvas and makes the export throw.
var BASE = location.pathname.replace(/[^/]*$/, "");
// Ethereum endpoints, tried in order. The first two are public RPCs. The third is
// Sovrn's own read-only proxy, and it is why this list exists at all: crypto RPC
// hostnames sit on the "NoCoin"/cryptomining filter lists that uBlock Origin,
// AdGuard, Brave Shields and DNS filters ship, so a visitor running any of those
// got "Failed to fetch" on every single work — the request never left the browser
// — while the page itself loaded fine, because the title index is same-origin.
// The proxy host is not a crypto domain, so those lists do not touch it. It serves
// only tokenURI on these three contracts, and caches (tokenURI is immutable).
var RPCS = [
  "https://ethereum-rpc.publicnode.com",
  "https://eth.drpc.org",
  "https://sovrn-bot-production.up.railway.app/api/eth"
];
// Sticky: a results list can fire forty lookups, and once one endpoint has
// answered there is no sense making all forty rediscover the dead ones.
var rpcAt = 0;
var MAX_HITS = 40;
var LABELS = { reflection: "Reflection", wunderkammer: "Wunderkammer", bytegans: "byteGANs" };
var ARTISTS = { reflection: "Pindar Van Arman", wunderkammer: "Isa Kost",
                bytegans: "Pindar Van Arman" };
var ORDER = ["reflection", "wunderkammer", "bytegans"];
// The cascade runs 8s. At 20 frames that is 2.5fps and reads as a slideshow, so
// it gets many more — affordable because frames after the first only carry the
// rectangle that changed, and because Reflection renders at 480 only.
var REFLECTION_FRAMES = 72;


// ?c=<slug> locks the page to one collection: the chips go away, the panels show
// only that collection, and the copy names it. Three Sites pages can then embed
// the same implementation rather than three copies of it drifting apart.
var LOCK = (function () {
  // The scoped pages (share-<slug>.html) set SHARE_SCOPE before loading this.
  // ?c=<slug> does the same for share.html, and is kept so an existing embed of
  // share.html?c=reflection keeps working.
  var want = (typeof SHARE_SCOPE === "string" && SHARE_SCOPE) || null;
  if (!want) {
    var m = /[?&]c=([a-z-]+)/.exec(location.search);
    want = m ? m[1] : null;
  }
  return want && ORDER.indexOf(want) >= 0 ? want : null;
})();
var VIEW = LOCK ? [LOCK] : ORDER;

var data = null, scope = null, sel = null, cache = {}, token = 0;
var lastRows = [];   // what the current search turned up, for the Enter shortcut
var $ = function (id) { return document.getElementById(id); };

fetch(BASE + "onchain-titles.json")
  .then(function (r) { return r.json(); })
  .then(function (d) { data = d.collections; boot(); })
  .catch(function () { $("note").textContent = "Couldn't load the title index."; });

function boot() {
  if (LOCK) lockTo(LOCK);
  var strip = $("sets");
  (LOCK ? [] : ORDER).forEach(function (slug) {
    var b = document.createElement("button");
    b.type = "button";
    b.textContent = LABELS[slug];
    b.setAttribute("aria-pressed", "false");
    b.onclick = function () {
      scope = (scope === slug) ? null : slug;      // click again to clear
      mark();
      search($("q").value.trim());
    };
    b._slug = slug;
    strip.appendChild(b);
  });
  scope = LOCK || "reflection";
  mark();
  syncTitleBoxes();
  buildPanels();
  buildShapes();
  renderComposer();
}

// Naming the collection in the heading matters more than it looks: the page is
// embedded, so the heading is the only thing telling a visitor what they are
// looking at.
// A short piece of prose at the foot of a scoped page. Keyed by collection, so
// Wunderkammer and byteGANs can have their own the moment there is text for them
// — nothing else has to change. The combined page shows none of it, having no
// single collection to speak for.
var ABOUT = {
  reflection: [
    "Reflection encodes and executes Pindar Van Arman\u2019s reflective AI process fully on-chain.",
    "The resulting artworks live inside a set of Ethereum contracts as encoded vector drawings.",
    "This tool pulls the SVG data from the contracts and converts it to gifs that play with the parameters specified in the encoding."
  ]
};

function renderAbout(slug) {
  var host = $("pageabout");
  if (!host) return;
  var lines = ABOUT[slug];
  host.textContent = "";
  host.hidden = !lines;
  if (!lines) return;
  lines.forEach(function (line) {
    var p = document.createElement("p");
    p.textContent = line;
    host.appendChild(p);
  });
}

function lockTo(slug) {
  $("sets").hidden = true;
  document.title = "Shareable GIFs of " + LABELS[slug] + " \u2014 sovrn.art";
  var h = document.querySelector("header h1");
  var p = document.querySelector("header p");
  if (h) h.textContent = "Shareable GIFs of " + LABELS[slug];
  if (p) p.textContent = "get animated versions of " + ARTISTS[slug] + "'s "
    + LABELS[slug] + " in a format that can be shared on socials";
  // The label above the panel goes entirely. "From the collections" is a plural
  // promise a scoped page doesn't keep, and naming the collection there just
  // says a third time what the heading and the caption already say.
  // [hidden] is !important globally and .gtitle sets no display, so this holds.
  var g = $("gtitle");
  if (g) g.hidden = true;
  renderAbout(slug);
}

/* ------------------------------------------------------- the opening panels */

// Local SVGs — the same files the homepage collection cards use. They paint
// instantly, cost no contract calls, and animate by themselves inside an <img>
// (sovrn-pages/NOTES.md: SMIL runs, and nested GIFs run, in an <img>).
//
// Three panels rather than a grid of tiles, because the cost is per animating
// SVG and Reflection is by far the heaviest: 89KB, 868 paths and 24 SMIL
// animations each, against a byteGAN's 1KB and zero paths. A grid holding a
// dozen Reflections ran ~10,000 animated vector paths behind a search box, which
// is what made it lag. One at a time is nothing — and it gets seen properly.
var POOLS = {
  reflection: { dir: "img/collections/reflection/", stem: "reflection-", n: 30 },
  wunderkammer: { dir: "img/wunderkammer-works/", stem: "wunderkammer-", n: 36 },
  bytegans: { dir: "img/bytegans/", stem: "bytegan-", n: 24 }
};

function poolPath(slug, i) {
  var pool = POOLS[slug];
  return BASE + pool.dir + pool.stem + (i < 10 ? "0" + i : i) + ".svg";
}

// Where a collection's opening panel starts in its pool, when the default
// stagger is not the frame we want to open on. Keep in step with the preload
// links in the share*.html shells.
var PANEL_START = { reflection: 2 };

var panels = [], rotators = [];
var HOLD_MS = 7000, FADE_MS = 1000;

function buildPanels() {
  var host = $("three");
  host.textContent = "";
  panels = [];
  $("gallery").hidden = false;

  host.classList.toggle("one", VIEW.length === 1);
  VIEW.forEach(function (slug, n) {
    var card = document.createElement("button");
    card.type = "button";
    card.className = "panelcard";
    card.setAttribute("aria-label", "Search " + LABELS[slug]);

    var a = document.createElement("img"), b = document.createElement("img");
    a.alt = ""; b.alt = ""; b.className = "out";
    a.decoding = "async"; b.decoding = "async";
    // Start each panel at a different point in its pool so the three do not
    // move in step. No loading="lazy": these are the first thing on the page,
    // and a lazy image never scrolled to is never loaded at all.
    //
    // Reflection opens on the second of its pool rather than the first. The
    // stagger below is only there to keep the panels out of lockstep, so
    // overriding one collection costs nothing — but the <link rel="preload"> in
    // every share*.html shell names this file, so the two have to move together.
    // tools/check-share-pages.py holds them to it.
    var startAt = PANEL_START[slug] || 1 + (n * 7) % POOLS[slug].n;
    a.src = poolPath(slug, startAt);

    var cap = document.createElement("figcaption");
    cap.textContent = LABELS[slug];
    var who = document.createElement("span");
    who.className = "who";
    who.textContent = ARTISTS[slug];
    cap.appendChild(who);

    card.appendChild(a); card.appendChild(b); card.appendChild(cap);
    // A panel is a sample of its collection, not a specific token — the local
    // files are not token-numbered — so it scopes the search rather than
    // pretending to be one work.
    card.onclick = function () {
      scope = slug; mark();
      $("q").focus();
      search($("q").value.trim());
    };
    host.appendChild(card);
    panels.push({ el: card, slug: slug, front: a, back: b, i: startAt, busy: false });
  });

  startRotating();
}

function startRotating() {
  stopRotating();
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  // Every change pulls another file, so stay off under Data Saver.
  if (navigator.connection && navigator.connection.saveData) return;
  panels.forEach(function (pnl, n) {
    rotators.push(setTimeout(function tick() {          // staggered, so the
      rotate(pnl);                                      // three never change
      rotators.push(setTimeout(tick, HOLD_MS));         // together
    }, HOLD_MS / 2 + n * (HOLD_MS / 3)));
  });
}

function stopRotating() {
  rotators.forEach(clearTimeout);
  rotators = [];
}

function rotate(pnl) {
  if (document.hidden || $("gallery").hidden || pnl.busy) return;
  pnl.busy = true;
  pnl.i = pnl.i % POOLS[pnl.slug].n + 1;
  var src = poolPath(pnl.slug, pnl.i);
  var probe = new Image();
  var release = function () { pnl.busy = false; };
  probe.onload = function () {
    // Decode before the fade, or the panel fades up onto a blank.
    var ready = probe.decode ? probe.decode() : Promise.resolve();
    ready.catch(function () {}).then(function () {
      pnl.back.src = src;
      pnl.back.classList.remove("out");
      pnl.front.classList.add("out");
      var tmp = pnl.front; pnl.front = pnl.back; pnl.back = tmp;
      setTimeout(release, FADE_MS + 80);
    });
  };
  // Clear the flag on error too, or one failed fetch strands the panel for good.
  probe.onerror = release;
  probe.src = src;
}

document.addEventListener("visibilitychange", function () {
  if (document.hidden) stopRotating(); else startRotating();
});

var EXAMPLES = {
  reflection:   "\u201ccogito\u201d, \u201cmachine\u201d, or 883",
  wunderkammer: "\u201cbeetle\u201d, \u201cseahorse\u201d, or 12",
  bytegans:     "\u201coctoGAN\u201d, \u201cskull\u201d, or 469"
};

function mark() {
  [].forEach.call($("sets").children, function (b) {
    b.setAttribute("aria-pressed", String(b._slug === scope));
  });
  $("note").textContent = scope
    ? "Search " + LABELS[scope] + " by title or token ID \u2014 " + EXAMPLES[scope] + "."
    : "Search every collection by title or token ID \u2014 "
      + "\u201cskull\u201d, \u201ccogito\u201d, \u201coctoGAN\u201d, or 883.";
}

$("q").addEventListener("input", function () { search(this.value.trim()); });

// Enter opens the work when the search has narrowed to exactly one. With more
// than one it would be a guess, so leave the list for the visitor to choose from.
$("q").addEventListener("keydown", function (e) {
  if (e.key !== "Enter") return;
  e.preventDefault();
  if (lastRows.length === 1) chooseResult(lastRows[0]);
});

// Thumbnails load only when a row is actually on screen. Forty rows would mean
// forty contract calls otherwise, and a Reflection token is ~115KB.
var thumbWatcher = null;

function watchThumb(row, img, r, eager) {
  row._thumb = { img: img, r: r };
  if (eager || !("IntersectionObserver" in window)) { fillThumb(row); return; }
  if (!thumbWatcher) {
    thumbWatcher = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        thumbWatcher.unobserve(e.target);
        fillThumb(e.target);
      });
    }, { root: document.getElementById("hits"), rootMargin: "150px" });
  }
  thumbWatcher.observe(row);
}

// Only Reflection thumbnails are flattened to stills. It is the expensive one —
// ~700 paths, ~115KB — and its eight-second cascade reads as nothing at 42px, so
// forty of them animating at once is all cost and no signal. A byteGAN is 1.1KB
// and lively even that small, and Wunderkammer's glint is nine cheap frames, so
// both keep moving. Drawing an SVG to a canvas captures one frame anyway, which
// is what makes the still free.
var THUMB_PX = 84;          // 2x the 42px list row, so it stays sharp on retina
// Composer slots are a few hundred px wide and there are at most four of them,
// so they get a real raster. Still a raster rather than the live SVG: four
// animating Reflections behind the composer is what made this lag before.
var SLOT_PX = 640;
var thumbStills = {};

function stillFrom(uri, slug, px) {
  // px matters: the same helper feeds the 42px list rows and the composer slots,
  // which are several hundred px wide. Baking everything at THUMB_PX meant the
  // slots were showing an 84px raster blown up five times over — a vector work
  // rendered as mush. The size is part of the cache key, or the two callers
  // hand each other the wrong one.
  px = px || THUMB_PX;
  var key = slug + ":" + px + ":" + uri.length + ":" + uri.slice(-24);
  if (thumbStills[key]) return Promise.resolve(thumbStills[key]);
  return loadImage(uri).then(function (img) {
    var c = document.createElement("canvas");
    c.width = c.height = px;
    var ctx = c.getContext("2d");
    // byteGANs are 11x11 pixel art; smoothing turns them to mush at any size.
    ctx.imageSmoothingEnabled = slug !== "bytegans";
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, px, px);
    var sw = img.naturalWidth || px, sh = img.naturalHeight || px;
    var k = px / Math.max(sw, sh);
    var dw = Math.round(sw * k), dh = Math.round(sh * k);
    ctx.drawImage(img, (px - dw) / 2, (px - dh) / 2, dw, dh);
    var out = c.toDataURL("image/png");
    thumbStills[key] = out;
    return out;
  });
}

var STILL_THUMBS = { reflection: true };

function fillThumb(row) {
  var t = row._thumb;
  if (!t || t.done) return;
  t.done = true;
  queuedWork(t.r.slug, t.r.id)
    .then(function (uri) {
      return STILL_THUMBS[t.r.slug] ? stillFrom(uri, t.r.slug) : uri;
    })
    .then(function (src) { t.img.src = src; })
    .catch(function () {});
}

function search(q) {
  var box = $("hits");
  box.textContent = "";
  // A new search means the previous work is no longer what is on screen.
  closePanel();
  if (!q) {
    lastRows = [];
    $("note").hidden = false;
    $("gallery").hidden = false;
    startRotating();
    return;
  }
  $("note").hidden = true;
  $("gallery").hidden = true;
  stopRotating();

  var lower = q.toLowerCase();
  var slugs = scope ? [scope] : ORDER;
  var rows = [], total = 0;
  lastRows = rows;

  // A bare number is a token id. Each collection has its own range, and they do
  // not agree — Reflection is 0-indexed, the other two are 1-indexed — so offer
  // whichever collections actually hold that id.
  if (/^\d+$/.test(q)) {
    var n = parseInt(q, 10);
    slugs.forEach(function (slug) {
      var rec = data[slug], i = n - rec.first_token;
      if (i >= 0 && i < rec.titles.length) {
        rows.push({ slug: slug, id: n, title: rec.titles[i], why: "token " + n });
        total++;
      }
    });
  }

  slugs.forEach(function (slug) {
    var rec = data[slug];
    for (var i = 0; i < rec.titles.length; i++) {
      if (rec.titles[i].toLowerCase().indexOf(lower) < 0) continue;
      total++;
      if (rows.length < MAX_HITS) {
        rows.push({ slug: slug, id: rec.first_token + i, title: rec.titles[i] });
      }
    }
  });

  lastRows = rows;
  if (!rows.length) {
    var none = document.createElement("button");
    none.type = "button";
    none.disabled = true;
    none.textContent = "Nothing matched that.";
    box.appendChild(none);
    return;
  }

  rows.forEach(function (r, rowIndex) {
    var b = document.createElement("button");
    b.type = "button";

    var th = document.createElement("span");
    th.className = "thumb";
    var im = document.createElement("img");
    im.alt = "";
    th.appendChild(im);

    var mid = document.createElement("span");
    mid.className = "rowtext";
    var t = document.createElement("span");
    t.className = "rowtitle";
    t.textContent = r.title;
    mid.appendChild(t);

    var tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = LABELS[r.slug] + " · " + (r.why || r.id);

    b.appendChild(th); b.appendChild(mid); b.appendChild(tag);
    b.onclick = function () { chooseResult(r); };
    box.appendChild(b);
    // The first rows are on screen by definition, so load them outright; the
    // rest wait for the observer.
    if (rowIndex < 8) { watchThumb(b, im, r, true); }
    else { watchThumb(b, im, r, false); }
  });

  if (total > rows.length) {
    var more = document.createElement("p");
    more.className = "more";
    more.textContent = total.toLocaleString() + " works match — showing the first "
      + rows.length + ". Keep typing to narrow it.";
    box.appendChild(more);
  }
}

var RENDER_SHARE = 0.92;          // encoding gets the last 8% of the bar

function showProgress(text, done, total) {
  $("prog").hidden = false;
  $("ptext").textContent = text;
  $("bar").style.width = (total ? Math.round(done / total * 100) : 0) + "%";
}

function hideProgress() {
  $("prog").hidden = true;
  $("bar").style.width = "0";
}

// Hand control back between frames so the bar can update.
//
// Deliberately NOT requestAnimationFrame: rAF is tied to painting, and a hidden
// or backgrounded tab throttles it to a crawl or stops it altogether — which
// would stall the render itself, not just the bar. (sovrn-pages/NOTES.md records
// the in-app preview pane firing one rAF in three seconds.) setTimeout keeps
// running regardless, so the work always finishes and the bar catches up
// whenever the browser does paint.
function yieldToPaint() {
  return new Promise(function (r) { setTimeout(r, 0); });
}

// Picking a result closes the list: it has done its job, and leaving forty rows
// open pushes the work you just chose off the screen. The query text stays, so
// it is obvious what was searched and easy to pick something else.
function chooseResult(r) {
  // In a tych, a click fills the next empty box and the list stays open so the
  // next work is one more click. In Single it opens the work, as before.
  if (shape > 1) {
    if (theSet.length >= shape || inSet(r)) return;
    queuedWork(r.slug, r.id).then(function (uri) {
      addToSet({ slug: r.slug, id: r.id, title: r.title, uri: uri });
    }).catch(function () {});
    return;
  }
  $("hits").textContent = "";
  lastRows = [];
  $("q").blur();                 // on a phone, let the keyboard get out of the way
  openWork(r);
}

// A composite has no token, no SVG, and no per-work size — it was encoded at
// the size the composer chose. Leaving these on screen offered choices that did
// nothing, and touching the size box cleared the built GIF out from under the
// download button.
function singleOnly(on) {
  $("ssize").hidden = !on;
  $("stitlebox").hidden = !on;
  $("add").hidden = !on;
  $("src").hidden = !on;
}

function closePanel() {
  sel = null;
  built = null;
  token++;                       // invalidates any fetch still in flight
  $("panel").hidden = true;
  $("shrunk").hidden = true;
  hideProgress();
  $("prev").removeAttribute("src");
  $("prev").style.width = "";
}

// The GIF is encoded at the chosen size; the frame may still be narrower than
// that, so say when what is on screen is not actual size.
function reportScale() {
  var img = $("prev");
  var actual = built ? built.size : 0;
  var shown = img.clientWidth;
  var note = $("shrunk");
  if (actual && shown && shown < actual - 2) {
    note.textContent = "shown at " + shown + "px to fit — the file is "
      + actual + "px";
    note.hidden = false;
  } else {
    note.hidden = true;
  }
}

addEventListener("resize", function () { if (built) reportScale(); });

/* ---------------------------------------------------- one work, from chain */

function openWork(r) {
  var mine = ++token;
  sel = { slug: r.slug, id: r.id, title: r.title };
  singleOnly(true);
  $("panel").hidden = false;
  $("pt").textContent = r.title;
  $("pm").innerHTML = meta(r);
  showProgress("Reading the contract", 0, 1);
  $("warn").textContent = "";
  $("prev").removeAttribute("src");
  $("dl").disabled = true;
  $("src").disabled = true;
  syncSizes(r.slug);

  fetchWork(r.slug, r.id).then(function (uri) {
    if (mine !== token) return;                       // superseded by a newer pick
    sel.uri = uri;
    $("src").disabled = false;
    $("dl").disabled = false;
    $("pm").innerHTML = meta(r) + " · on-chain";
    hideProgress();
    // The artwork itself, animating, at once — no encoder involved. Rendering a
    // GIF here meant every pick cost a full render, and composing a triptych
    // threw three of them away before you pressed Make.
    var img = $("prev");
    img.style.width = parseInt($("size").value, 10) + "px";
    img.src = uri;
    img.onload = reportScale;
    built = null;
    syncPreviewCap();
    $("warn").textContent = "";
    syncAddButton();
  }).catch(function (e) {
    if (mine !== token) return;
    $("pm").innerHTML = meta(r);
    $("warn").textContent = chainTrouble(e, "Couldn't read that work from the contract");
  });
}

// Reflection is pure vector, ~700 paths, natively 1200px — at 480 the fine work
// is simply gone, so it gets the same choice as the others and defaults high.
function sizesFor(slug) {
  // Reflection renders 72 frames against the others' handful, so it is the one
  // that grows: 3.9MB at 720, roughly 8.8MB at 1080, and past X's 14MB by 1440.
  // Composites are a separate control and go larger, because they use 30 frames.
  return slug === "reflection" ? [480, 720, 1080] : [480, 720, 1080];
}

function syncSizes(slug) {
  var el = $("size"), allowed = sizesFor(slug);
  var want = allowed.indexOf(parseInt(el.value, 10)) >= 0
    ? parseInt(el.value, 10) : allowed[allowed.length - 1];
  el.textContent = "";
  allowed.forEach(function (n) {
    var o = document.createElement("option");
    o.value = String(n); o.textContent = n + "px";
    if (n === want) o.selected = true;
    el.appendChild(o);
  });
  el.disabled = allowed.length < 2;
}

function meta(r) {
  var s = "<b>" + LABELS[r.slug] + "</b> · " + ARTISTS[r.slug] + " · token " + r.id;
  // Reflection is 0-indexed while the other two are 1-indexed; say so rather
  // than leaving it as a trap for anyone reading a number off a title card.
  if (r.slug === "reflection") s += " (no. " + (r.id + 1) + " of 999)";
  return s;
}

// Try each endpoint in turn, starting from whichever last worked. A fetch that
// rejects with a TypeError never completed — blocked, offline or DNS-filtered —
// which is a different thing from an RPC that answered with an error, and the
// two deserve different words to the visitor.
function rpcHost(u) {
  try { return new URL(u).host; } catch (e) { return u; }
}

// What to actually tell someone. A blocked request is not the contract's fault
// and not the chain's, and saying "couldn't read it from the contract" sends
// people looking in exactly the wrong place.
function chainTrouble(e, doing) {
  if (e && e.blocked) {
    return "Couldn't reach Ethereum — the request was blocked before it left your "
      + "browser. An ad blocker, privacy extension (uBlock Origin, Brave Shields, "
      + "AdGuard) or a network filter is the usual cause; allow this page and retry.";
  }
  return doing + " — " + ((e && e.message) ? e.message : "try again in a moment") + ".";
}

function rpcCall(to, callData) {
  var body = JSON.stringify({ jsonrpc: "2.0", id: 1, method: "eth_call",
                              params: [{ to: to, data: callData }, "latest"] });
  var problems = [];

  function attempt(i) {
    if (i >= RPCS.length) {
      rpcAt = 0;                       // next action starts from the top again
      var allBlocked = problems.length > 0 && problems.every(function (p) { return p.blocked; });
      var e = new Error(allBlocked
        ? "the request was blocked before it left your browser"
        : problems.map(function (p) { return p.msg; }).join("; "));
      e.blocked = allBlocked;
      throw e;
    }
    return fetch(RPCS[i], {
      method: "POST", headers: { "Content-Type": "application/json" }, body: body
    }).then(function (r) {
      if (!r.ok) { var e = new Error("HTTP " + r.status); e.reached = true; throw e; }
      return r.json();
    }).then(function (j) {
      if (j.error) { var e = new Error(j.error.message || "call failed"); e.reached = true; throw e; }
      if (typeof j.result !== "string") { var e2 = new Error("no result"); e2.reached = true; throw e2; }
      rpcAt = i;                       // stick to whatever answered
      return j;
    }).catch(function (e) {
      // A TypeError out of fetch() means the request never completed at all.
      var blocked = !e.reached && (e instanceof TypeError);
      problems.push({ blocked: blocked, msg: rpcHost(RPCS[i]) + ": " + e.message });
      return attempt(i + 1);
    });
  }
  return attempt(rpcAt);
}

// Same-origin copies of the artwork, harvested from the contracts and byte-identical
// to what they return (shibboleth88/sovrn-onchain, verified by re-reading a spread of
// them and comparing). Tried FIRST, for two reasons. A same-origin file has exactly
// the page's own availability — if it cannot be reached there is no page either, so
// nothing is added that can be blocked or go down independently. And it is far
// smaller: a Reflection work is ~21KB gzipped here against ~338KB of hex over an RPC
// call, because hex doubles every byte and the ABI pads it.
//
// The chain stays as the fallback, so a work missing from the mirror still resolves,
// and nothing here is load-bearing on the harvest being complete.
var ART = new URL("../sovrn-onchain/", location.href).href;

function svgToDataUri(text) {
  // The rest of the page expects a data: URI — same as tokenURI hands back — so the
  // static path produces one too and everything downstream is untouched.
  return "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(text)));
}

function fetchStatic(slug, id) {
  return fetch(ART + slug + "/" + id + ".svg").then(function (r) {
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.text();
  }).then(function (t) {
    if (t.indexOf("<svg") < 0) throw new Error("not an SVG");
    return svgToDataUri(t);
  });
}

function fetchWork(slug, id) {
  var key = slug + ":" + id;
  if (cache[key]) return Promise.resolve(cache[key]);
  return fetchStatic(slug, id).catch(function () {
    return fetchFromChain(slug, id);
  }).then(function (image) {
    cache[key] = image;
    return image;
  });
}

function fetchFromChain(slug, id) {
  var call = "0xc87b56dd" + id.toString(16).padStart(64, "0");   // tokenURI(uint256)
  return rpcCall(data[slug].contract, call).then(function (j) {
    var raw = j.result.slice(2);
    var len = parseInt(raw.slice(64, 128), 16);
    var bytes = new Uint8Array(len);
    for (var i = 0; i < len; i++) bytes[i] = parseInt(raw.substr(128 + i * 2, 2), 16);
    var uri = new TextDecoder().decode(bytes);
    var payload = uri.indexOf("base64,") >= 0 ? b64utf8(uri.split("base64,")[1])
                                              : uri.slice(uri.indexOf(",") + 1);
    var image;
    try {
      image = JSON.parse(payload).image;
    } catch (e) {
      // byteGAN #469's metadata is malformed on-chain — an attributes entry has
      // an unquoted key — and the contract is immutable, so read the field directly.
      var m = payload.match(/"image"\s*:\s*"([^"]+)"/);
      if (!m) throw new Error("its metadata could not be read");
      image = m[1];
    }
    if (!image) throw new Error("no image in the token");
    return image;
  });
}

// Artwork requests are capped: a results list can hold forty rows, and firing
// forty contract calls at once is both rude and slower than a small queue.
var artQueue = [], artActive = 0, ART_MAX = 3;

function queuedWork(slug, id) {
  var key = slug + ":" + id;
  if (cache[key]) return Promise.resolve(cache[key]);
  return new Promise(function (resolve, reject) {
    artQueue.push({ slug: slug, id: id, resolve: resolve, reject: reject });
    pumpArt();
  });
}

function pumpArt() {
  while (artActive < ART_MAX && artQueue.length) {
    var job = artQueue.shift();
    artActive++;
    fetchWork(job.slug, job.id).then(job.resolve, job.reject).then(function () {
      artActive--;
      pumpArt();
    }, function () { artActive--; pumpArt(); });
  }
}

// atob gives one byte per char; decode as UTF-8 so accented titles survive.
function b64utf8(b64) {
  return new TextDecoder().decode(
    Uint8Array.from(atob(b64), function (c) { return c.charCodeAt(0); }));
}

function svgOf(w) { return b64utf8(w.uri.split("base64,")[1]); }

function loadImage(src) {
  return new Promise(function (res, rej) {
    var i = new Image();
    i.onload = function () { res(i); };
    i.onerror = function () { rej(new Error("could not rasterise")); };
    i.src = src;
  });
}

function svgToUri(text) {
  return "data:image/svg+xml;base64," + btoa(
    String.fromCharCode.apply(null, new TextEncoder().encode(text)));
}

/* ------------------------------------------------------- frames, per source */

// A byteGAN is not a vector at heart: the artwork is an 11x11 animated GIF
// base64'd inside the SVG, and the wrapper only carries image-rendering:
// pixelated. Decode that GIF and scale by a whole-number factor with smoothing
// off, or the hard pixel edges smear.
function bytegansFrames(w, size, onStep) {
  var svg = svgOf(w);
  var m = svg.match(/data:image\/gif;base64,([A-Za-z0-9+/=\s]+)/);
  if (!m) throw new Error("no GIF inside the wrapper");
  return decodeGif(m[1]).then(function (g) {
    var f = Math.max(1, Math.round(size / g.width));
    var out = [], c = document.createElement("canvas");
    c.width = g.width * f; c.height = g.height * f;
    var ctx = c.getContext("2d", { willReadFrequently: true });
    ctx.imageSmoothingEnabled = false;
    var step = Promise.resolve();
    g.frames.forEach(function (bmp, i) {
      step = step.then(function () {
        ctx.clearRect(0, 0, c.width, c.height);
        ctx.drawImage(bmp, 0, 0, c.width, c.height);
        out.push(ctx.getImageData(0, 0, c.width, c.height));
        if (onStep) onStep(i + 1, g.frames.length);
        return i % 4 === 3 ? yieldToPaint() : null;
      });
    });
    return step.then(function () {
      return { frames: out, delays: g.delays, colours: 256 };
    });
  });
}

// Wunderkammer stacks four layers — a tiled pattern, a static base, the animated
// overlay, and the artist's seal. Rather than reproduce that layout by hand, swap
// the animated layer's data URI for one still frame at a time and let the SVG do
// its own compositing.
function wunderkammerFrames(w, size, onStep) {
  var svg = svgOf(w);
  var gifs = svg.match(/data:image\/gif;base64,[A-Za-z0-9+/=\s]+/g) || [];
  var animated = null;
  var chain = Promise.resolve();
  gifs.forEach(function (g) {
    chain = chain.then(function () {
      if (animated) return;
      return decodeGif(g.split("base64,")[1]).then(function (d) {
        if (d.frames.length > 1) animated = { raw: g, data: d };
      });
    });
  });
  return chain.then(function () {
    if (!animated) return staticFrames(w, size);       // one of the 36 is a single frame
    var c = document.createElement("canvas");
    c.width = animated.data.width; c.height = animated.data.height;
    var ctx = c.getContext("2d");
    var out = [], step = Promise.resolve();
    animated.data.frames.forEach(function (bmp) {
      step = step.then(function () {
        ctx.clearRect(0, 0, c.width, c.height);
        ctx.drawImage(bmp, 0, 0);
        var swapped = svg.replace(animated.raw, c.toDataURL("image/png"));
        return rasterise(svgToUri(swapped), size).then(function (im) {
          out.push(im);
          if (onStep) onStep(out.length, animated.data.frames.length);
          return yieldToPaint();
        });
      });
    });
    return step.then(function () {
      return { frames: out, delays: animated.data.delays, colours: 256 };
    });
  });
}

/* --------------------------------------------------------------------------
 * Reflection: rebuild the artist's smooth cascade from the minted file.
 *
 * A minted Reflection carries only SEVEN fades. The artist's Francisco
 * Carolinum renders have 20-26, and the minted file contains everything needed
 * to reconstruct them: HTML comments number each painting pass, and
 * startanim/endanim bracket the seven he minted. Walk the groups from pass 11,
 * give each drawn layer its own fade one every 0.4s, and leave the minted seven
 * alone.
 *
 * This is a direct port of sovrn-pages/tools/reflection-smooth.py, which proves
 * itself by reproducing six of the artist's own renders exactly. The port was
 * checked the same way: byte-identical output to that script on tokens 0, 515,
 * 700, 884, 883 and 998. If you change anything here, re-check it that way.
 * -------------------------------------------------------------------------- */
var ROWCLS = ["fortyeightrows", "eightyrows", "twentyfourrows"];
var FADE_STEP = 0.4;

// Python's str() on a float keeps a trailing ".0"; "%g" strips trailing zeros.
// Both appear in the output, and matching them is what makes it byte-identical.
function pyFloat(v) { return Number.isInteger(v) ? v.toFixed(1) : String(v); }
function pyG(v) { return String(Number(v.toPrecision(6))); }

function nextNonSpace(svg, pos) {
  var i = pos;
  while (i < svg.length && /\s/.test(svg.charAt(i))) i++;
  return svg.substr(i, 12);
}

function scanGroups(svg) {
  var gs = [], sec = -1;
  var re = /<!--([\s\S]*?)-->|<g\b([^>]*?)(\/?)>/g, m;
  while ((m = re.exec(svg)) !== null) {
    if (m[1] !== undefined) {
      var n = /^\s*(\d+):/.exec(m[1]);
      if (n) sec = parseInt(n[1], 10);
      continue;
    }
    var cls = /class="([^"]+)"/.exec(m[2]);
    var rest = nextNonSpace(svg, re.lastIndex);
    gs.push({ pos: re.lastIndex, sec: sec, cls: cls ? cls[1] : null,
              minted: rest.indexOf("<animate") === 0,
              empty: !!m[3] || rest.indexOf("</g>") === 0 });
  }
  return gs;
}

function fadePlan(svg) {
  var gs = scanGroups(svg);
  var p20 = gs.filter(function (g) { return g.sec === 20; });
  var p20dead = p20.some(function (g) { return g.empty; });
  var p20last = p20.length ? p20[p20.length - 1] : null;
  var out = [], k = 0, seen13 = false;
  for (var i = 0; i < gs.length; i++) {
    var g = gs[i];
    if (g.sec < 11 || g.minted) continue;
    // pass 13's opening group holds a slot in the sequence but does not fade
    if (g.sec === 13 && !seen13) { seen13 = true; k++; continue; }
    // the grid beneath the strokes never fades
    if (g.sec === 11 && ROWCLS.indexOf(g.cls) >= 0) continue;
    // pass 20 fades nothing when it painted nothing, and its closing wrapper
    // really belongs to pass 21
    if (g.sec === 20 && (p20dead || g === p20last)) continue;
    // passes 19 and 20 fade their unclassed wrappers too; everything else needs a class
    if (!(g.cls || g.sec === 19 || g.sec === 20)) continue;
    out.push([g.pos, Number((k * FADE_STEP).toFixed(10))]);
    k++;
  }
  return out;
}

function fadeTag(begin) {
  var k3 = 0.125 + 0.0625 * begin;
  return '<animate attributeType="XML" attributeName="opacity" values="1;0;0;1;1" '
       + 'keyTimes="0;0.0625;' + pyG(k3) + ';' + pyG(k3 + 0.0625) + ';1" '
       + 'begin="' + pyFloat(begin) + 's" dur="8s" '
       + 'repeatCount="indefinite" fill="freeze" />';
}

function smoothReflection(svg) {
  var ins = fadePlan(svg).sort(function (a, b) { return b[0] - a[0]; });
  for (var i = 0; i < ins.length; i++) {
    svg = svg.slice(0, ins[i][0]) + fadeTag(ins[i][1]) + svg.slice(ins[i][0]);
  }
  return svg;
}

// Reflection animates with SMIL. Serialising a seeked SVG would just give back
// the original markup, so instead each <animate> is evaluated at time t and
// written onto its parent as a static opacity, then removed.
function reflectionFrames(w, size, onStep, frameCount) {
  var svg = smoothReflection(svgOf(w));
  var doc = new DOMParser().parseFromString(svg, "image/svg+xml");
  var anims = [].slice.call(doc.querySelectorAll("animate"));
  var dur = 8;
  anims.forEach(function (a) {
    var d = parseFloat(a.getAttribute("dur") || "8");
    if (!isNaN(d)) dur = Math.max(dur, d);
  });
  var plan = anims.map(function (a) {
    return {
      parent: a.parentNode,
      attr: a.getAttribute("attributeName") || "opacity",
      values: (a.getAttribute("values") || "").split(";").map(parseFloat),
      keys: (a.getAttribute("keyTimes") || "").split(";").map(parseFloat),
      // Every added fade is staggered purely by `begin`; ignoring it would put
      // all of them in lockstep and undo the whole cascade.
      begin: parseFloat(a.getAttribute("begin") || "0") || 0,
      dur: parseFloat(a.getAttribute("dur") || "8") || 8,
      node: a
    };
  });
  plan.forEach(function (p) { if (p.node.parentNode) p.node.parentNode.removeChild(p.node); });

  // Every fade starts at its own `begin`, the last of them around 6s in, and only
  // then repeats every 8s. So the first eight seconds are a STARTUP, with layers
  // sitting at their base opacity waiting to begin — sampling there gave a GIF
  // that did not loop and barely moved early on. Sample a window that starts
  // after the last begin, where the cascade is in its steady repeating state.
  var maxBegin = 0;
  plan.forEach(function (p) { if (p.begin > maxBegin) maxBegin = p.begin; });
  var t0 = maxBegin;

  var out = [], delays = [], step = Promise.resolve();
  var nFrames = frameCount || REFLECTION_FRAMES;
  var ms = Math.round(dur * 1000 / nFrames);
  for (var i = 0; i < nFrames; i++) {
    (function (frac) {
      step = step.then(function () {
        var t = t0 + frac * dur;
        plan.forEach(function (p) {
          if (p.values.length < 2 || p.values.length !== p.keys.length) return;
          // Before `begin` an animation has not started and the element sits at
          // its base value; after, it repeats every dur. Wrapping backwards past
          // begin — which is what this used to do — reports a mid-fade opacity
          // for a layer the browser still shows untouched.
          var v = t < p.begin ? p.values[0]
                : valueAt(p.values, p.keys, ((t - p.begin) % p.dur) / p.dur);
          p.parent.setAttribute(p.attr, String(v));
        });
        var text = new XMLSerializer().serializeToString(doc);
        return rasterise(svgToUri(text), size).then(function (im) {
          out.push(im); delays.push(ms);
          if (onStep) onStep(out.length, nFrames);
          return yieldToPaint();
        });
      });
    })(i / nFrames);
  }
  return step.then(function () { return { frames: out, delays: delays, colours: 256 }; });
}

function valueAt(values, keys, f) {
  for (var i = 1; i < keys.length; i++) {
    if (f <= keys[i]) {
      var span = keys[i] - keys[i - 1];
      var t = span > 0 ? (f - keys[i - 1]) / span : 0;
      return values[i - 1] + (values[i] - values[i - 1]) * t;
    }
  }
  return values[values.length - 1];
}

function staticFrames(w, size) {
  return rasterise(w.uri, size).then(function (im) {
    return { frames: [im], delays: [1000], colours: 256 };
  });
}

function decodeGif(b64) {
  var bytes = Uint8Array.from(atob(b64.replace(/\s/g, "")),
                              function (c) { return c.charCodeAt(0); });
  var dec = new ImageDecoder({ data: bytes, type: "image/gif" });
  // tracks.ready and completed settle separately; frameCount is null before the
  // first of those resolves.
  return dec.tracks.ready.then(function () {
    return dec.completed;
  }).then(function () {
    var n = dec.tracks.selectedTrack.frameCount, frames = [], delays = [];
    var step = Promise.resolve();
    for (var i = 0; i < n; i++) {
      (function (k) {
        step = step.then(function () {
          return dec.decode({ frameIndex: k }).then(function (r) {
            frames.push(r.image);
            delays.push(Math.max(20, Math.round((r.image.duration || 100000) / 1000)));
          });
        });
      })(i);
    }
    return step.then(function () {
      return { frames: frames, delays: delays,
               width: frames[0].displayWidth, height: frames[0].displayHeight };
    });
  });
}

function rasterise(uri, size) {
  return loadImage(uri).then(function (img) {
    var sw = img.naturalWidth || size, sh = img.naturalHeight || size;
    var k = size / Math.max(sw, sh);
    var c = document.createElement("canvas");
    c.width = Math.max(1, Math.round(sw * k));
    c.height = Math.max(1, Math.round(sh * k));
    var ctx = c.getContext("2d", { willReadFrequently: true });
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, c.width, c.height);
    ctx.drawImage(img, 0, 0, c.width, c.height);
    return ctx.getImageData(0, 0, c.width, c.height);
  });
}

/* ------------------------------------------------------------------ build */

var built = null;

function build() {
  var mine = token, w = sel;
  var size = parseInt($("size").value, 10), caps = withTitles;
  $("dl").disabled = true;
  $("warn").textContent = "";
  showProgress("Rendering frames", 0, 1);
  var maker = w.slug === "bytegans" ? bytegansFrames
            : w.slug === "wunderkammer" ? wunderkammerFrames
            : reflectionFrames;
  return maker(w, size, function (done, total) {
    if (mine !== token) return;
    showProgress("Rendering frame " + done + " of " + total,
                 done / total * RENDER_SHARE, 1);
  }).then(function (r) {
    if (mine !== token) return;
    // Encoding is one synchronous stretch, so paint the label before starting it
    // or it never appears.
    showProgress("Encoding the GIF", RENDER_SHARE, 1);
    return Promise.all([yieldToPaint(), capFontReady]).then(function () {
      return caps ? captioned(r, w.title) : r;
    });
  }).then(function (r) {
    if (!r || mine !== token) return;
    var blob = GIF.encode(r.frames, r.delays, r.colours);
    built = { blob: blob, size: size, key: w.slug + ":" + w.id + (caps ? ":t" : "") };
    var img = $("prev");
    img.style.width = r.frames[0].width + "px";
    img.src = URL.createObjectURL(blob);
    // The GIF now carries the caption itself; leaving the band up would show it twice.
    // Guarded like every other reach for this element: assets are cached for ten
    // minutes, so a visitor can briefly hold this script alongside an older shell
    // that has no such element, and an unguarded throw here would land inside the
    // render and break the download rather than skip a cosmetic line.
    var band = $("prevcap");
    if (band) band.hidden = true;
    img.onload = reportScale;
    $("dl").disabled = false;
    var kb = blob.size / 1024;
    var line = r.frames.length + " frames · " + r.frames[0].width + "×"
      + r.frames[0].height + " · " + (kb > 1024 ? (kb / 1024).toFixed(1) + "MB"
                                                : Math.round(kb) + "KB");
    if (blob.size > 15 * 1024 * 1024) {
      line += " — over X's 15MB ceiling; choose a smaller size";
    } else if (w.slug === "reflection") {
      // A Reflection measured 3,326 distinct colours; GIF allows 256, so this is
      // an honest limit of the format rather than something to hide.
      line += " — GIF holds 256 colours, so this one bands a little";
    }
    line += " · " + (1000 / r.delays[0]).toFixed(1) + " fps";
    hideProgress();
    $("warn").textContent = line;
  }).catch(function (e) {
    if (mine !== token) return;
    hideProgress();
    $("warn").textContent = chainTrouble(e, "Couldn't build that GIF");
  });
}

// The preview is meant to be the live artwork; build() swaps in the encoded GIF
// so you can see what you are about to get. Anything that invalidates that GIF
// has to put the artwork back, or the screen keeps showing a render that no
// longer matches the settings — which is how un-ticking the title appeared to do
// nothing: the captioned GIF was still sitting there.
function showLiveArtwork() {
  // The stats line describes the render we are about to discard, so it goes too —
  // but only when there was one. On the error path built is already null and that
  // line is holding the error message, which must survive.
  if (built) $("warn").textContent = "";
  built = null;
  if (!sel || !sel.uri) return;
  var img = $("prev");
  if ((img.getAttribute("src") || "").slice(0, 5) === "blob:") img.src = sel.uri;
  img.style.width = parseInt($("size").value, 10) + "px";
  syncPreviewCap();
  reportScale();
}

// The band under the preview stands in for the one captioned() burns into the
// GIF, so ticking the box shows the effect at once rather than after a render.
function syncPreviewCap() {
  var cap = $("prevcap");
  if (!cap) return;
  var on = withTitles && sel && sel.title && sel.slug !== "compose";
  cap.hidden = !on;
  if (on) {
    // Same numbers the encoder uses, so what is on screen is the band you get
    // rather than an approximation of it.
    var size = parseInt($("size").value, 10);
    var bandH = capHeight(size);
    cap.textContent = sel.title;
    cap.style.width = size + "px";
    cap.style.height = bandH + "px";
    cap.style.lineHeight = bandH + "px";
    cap.style.fontSize = capType(bandH) + "px";
  }
}

$("size").onchange = function () {
  // Nothing is re-encoded here — the preview is the live artwork, and the GIF is
  // built when it is asked for.
  showLiveArtwork();
};

/* --------------------------------------------------------------- composing */

// Works are laid on a ground with a margin and gutters, like pictures matted on
// a wall. That is what makes these ratios possible without cropping anything:
// two squares side by side are naturally 2:1 and three are 3:1, both wider than
// X shows whole, but on a 16:9 ground they simply sit with space around them.
var GROUND = "#000000";            // black, so the ground reads as nothing at all
// On by default: the title is what makes a shared GIF legible to someone who did
// not already know the work, and it is one click to turn off. The markup leaves
// both boxes unchecked, so boot() calls syncTitleBoxes() to bring the controls and
// the pill state to meet this — one source of truth rather than two that can drift.
var withTitles = true;
var theSet = [], shape = 1;     // 1 = single; 2/3/4 = a tych
var COMPOSE_FRAMES = 30;           // one full loop of every work, together

var LAYOUTS = {
  1: { name: "single",   cols: 1, rows: 1, ratio: 1, label: "one work" },
  2: { name: "diptych",  cols: 2, rows: 1, ratio: 16 / 9, label: "16:9" },
  3: { name: "triptych", cols: 3, rows: 1, ratio: 16 / 9, label: "16:9" },
  4: { name: "quadtych", cols: 2, rows: 2, ratio: 1,      label: "1:1" }
};

// A title sits in its own band directly under its work, like a wall label, so
// there is never a question which title belongs to which picture.
// The site sets every work title in Fraunces italic 300 — the h1 on each page and
// the cards on the hub — so the caption burned into the GIF speaks in the same
// voice rather than a terminal's. Georgia is the fallback if the webfont is
// blocked; both are serifs, so the band keeps its proportions either way.
var CAP_FONT = 'Fraunces, Georgia, "Times New Roman", serif';
var CAP_FACE = 'italic 300';
var CAP_MIN_PX = 16;               // a serif gives up sooner than mono does
var CAP_RATIO = 0.60;              // type height as a share of the band

// Canvas silently falls back when a face is not loaded yet, so the first export
// would come out Georgia and later ones Fraunces — inconsistent in a way nobody
// would think to check. Every render waits on this.
var capFontReady = (document.fonts && document.fonts.load)
  ? document.fonts.load(CAP_FACE + ' 32px Fraunces').catch(function () {})
  : Promise.resolve();

// The band and the type in it. Sized for where these are actually read: a
// timeline scales a 1080px image down to roughly half, so the type has to survive
// that and still be legible. At 480 the type is 19px, at 1080 it is 42px.
function capHeight(width) { return Math.max(28, Math.round(width * 0.065)); }
function capType(bandH) { return Math.max(CAP_MIN_PX, Math.round(bandH * CAP_RATIO)); }

// Shrink to fit, and ellipsize only when even the smallest size will not do —
// a Reflection title can run to fifty characters and must not overrun its work.
function drawCap(ctx, text, x, y, w, h, align) {
  var t = String(text || ""), px = capType(h);
  while (px > CAP_MIN_PX) {
    ctx.font = CAP_FACE + " " + px + "px " + CAP_FONT;
    if (ctx.measureText(t).width <= w) break;
    px--;
  }
  ctx.font = CAP_FACE + " " + px + "px " + CAP_FONT;
  if (ctx.measureText(t).width > w) {
    while (t.length > 1 && ctx.measureText(t + "\u2026").width > w) t = t.slice(0, -1);
    t = t.replace(/\s+$/, "") + "\u2026";
  }
  ctx.fillStyle = "#9aa1ad";
  // A single work is centred under its own artwork. In a tych each caption
  // belongs to the cell above it, and centring those reads as one long row of
  // text rather than a label per work, so those stay left.
  ctx.textAlign = align === "center" ? "center" : "left";
  ctx.textBaseline = "middle";
  ctx.fillText(t, align === "center" ? Math.round(x + w / 2) : x,
               Math.round(y + h * 0.52));
}

// Geometry for a layout at a given output width: the largest square that lets
// every work fit with its margin and gutters, and the block centred on the ground.
function geometry(lay, width, caps) {
  var W = width, H = Math.round(width / lay.ratio);
  var m = Math.round(width * 0.035), g = Math.round(width * 0.028);
  var capH = caps ? capHeight(width) : 0;   // each row is a band taller
  var cell = Math.floor(Math.min(
    (W - 2 * m - (lay.cols - 1) * g) / lay.cols,
    (H - 2 * m - (lay.rows - 1) * g - lay.rows * capH) / lay.rows));
  var blockW = cell * lay.cols + g * (lay.cols - 1);
  var blockH = (cell + capH) * lay.rows + g * (lay.rows - 1);
  return { W: W, H: H, cell: cell, gutter: g, capH: capH,
           left: Math.round((W - blockW) / 2), top: Math.round((H - blockH) / 2) };
}

function cellBox(lay, geo, k) {
  return { x: geo.left + (k % lay.cols) * (geo.cell + geo.gutter),
           y: geo.top + Math.floor(k / lay.cols) * (geo.cell + geo.capH + geo.gutter) };
}

// One work, with its title under it, on the same ground the tychs use.
function captioned(r, title) {
  var w = r.frames[0].width, h = r.frames[0].height, capH = capHeight(w);
  var c = document.createElement("canvas");
  c.width = w; c.height = h + capH;
  var ctx = c.getContext("2d", { willReadFrequently: true });
  var scratch = document.createElement("canvas");
  scratch.width = w; scratch.height = h;
  var sctx = scratch.getContext("2d");
  var out = [];
  for (var i = 0; i < r.frames.length; i++) {
    ctx.fillStyle = GROUND;
    ctx.fillRect(0, 0, c.width, c.height);
    sctx.putImageData(r.frames[i], 0, 0);
    ctx.drawImage(scratch, 0, 0);
    drawCap(ctx, title, 0, h, w, capH, "center");
    out.push(ctx.getImageData(0, 0, c.width, c.height));
  }
  return { frames: out, delays: r.delays, colours: r.colours };
}

function inSet(w) {
  return theSet.some(function (x) { return x.slug === w.slug && x.id === w.id; });
}

function addToSet(w) {
  if (theSet.length >= shape || inSet(w)) return;
  theSet.push({ slug: w.slug, id: w.id, title: w.title, uri: w.uri });
  renderComposer();
}

function buildShapes() {
  var host = $("shapes");
  host.textContent = "";
  [1, 2, 3, 4].forEach(function (n) {
    var lay = LAYOUTS[n];
    var b = document.createElement("button");
    b.type = "button";
    b.setAttribute("aria-pressed", String(n === shape));
    b.textContent = lay.name.charAt(0).toUpperCase() + lay.name.slice(1);
    b.onclick = function () {
      shape = n;
      if (shape > 1 && theSet.length > shape) theSet.length = shape;  // keep the first few
      renderComposer();
    };
    host.appendChild(b);
  });
}

function renderComposer() {
  var lay = LAYOUTS[shape];
  [].forEach.call($("shapes").children, function (b, i) {
    b.setAttribute("aria-pressed", String([1, 2, 3, 4][i] === shape));
  });

  // Single is the plain mode: no slots, clicking a result just opens the work.
  if (shape === 1) {
    $("slots").hidden = true;
    $("crow").hidden = true;
    $("chint").textContent = "Search and click a work to see it and download it.";
    syncAddButton();
    return;
  }
  $("slots").hidden = false;
  $("crow").hidden = false;

  // The slots mirror the composition, so the shape is legible before building.
  var slots = $("slots");
  slots.textContent = "";
  slots.style.gridTemplateColumns = "repeat(" + lay.cols + ", 1fr)";
  slots.style.gridTemplateRows = "repeat(" + lay.rows + ", 1fr)";
  slots.style.aspectRatio = lay.cols + " / " + lay.rows;

  for (var i = 0; i < shape; i++) {
    var w = theSet[i];
    var cell = document.createElement("div");
    cell.className = w ? "slot filled" : "slot";
    cell.dataset.i = String(i);
    if (w) {
      cell.draggable = true;
      var img = document.createElement("img");
      img.alt = w.title;
      img.draggable = false;
      stillFrom(w.uri, w.slug, SLOT_PX).then(function (target) {
        return function (png) { target.src = png; };
      }(img)).catch(function () {});
      var cap = document.createElement("span");
      cap.className = "cap";
      cap.textContent = w.title;
      var rm = document.createElement("button");
      rm.type = "button";
      rm.className = "rm";
      rm.textContent = "×";
      rm.setAttribute("aria-label", "Remove " + w.title);
      rm.onclick = (function (k) {
        return function (e) { e.stopPropagation(); theSet.splice(k, 1); renderComposer(); };
      })(i);
      cell.appendChild(img); cell.appendChild(cap); cell.appendChild(rm);
    } else {
      var n = document.createElement("span");
      n.className = "n";
      n.textContent = String(i + 1);
      cell.appendChild(n);
    }
    wireDrag(cell);
    slots.appendChild(cell);
  }

  var ready = theSet.length === shape;
  // The button says what it does and is simply unavailable until it can do it.
  // Labelling it "Add 3 more" made a disabled control read like an instruction —
  // it looked clickable and did nothing. How many are still needed belongs in
  // the hint, which was already saying it.
  $("mkgrid").disabled = !ready;
  $("mkgrid").textContent = "Make " + lay.name;
  var g = geometry(lay, parseInt(($("csize") || {}).value || 1440, 10), withTitles);
  $("chint").textContent = ready
    ? lay.label + " on a black ground · " + g.W + "×" + g.H + " · " + g.cell
      + "px per work — whole, nothing cropped. Drag the boxes to rearrange."
    : theSet.length + " of " + shape + " chosen — search and click works, each one"
      + " drops into the next box.";
  syncAddButton();
}

// Rearranging is a swap between two slots, which keeps it predictable: the work
// you drag onto moves to where you dragged from, rather than everything shuffling.
var dragFrom = null;

function wireDrag(cell) {
  cell.addEventListener("dragstart", function (e) {
    dragFrom = Number(cell.dataset.i);
    cell.classList.add("dragging");
    if (e.dataTransfer) { e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", ""); }
  });
  cell.addEventListener("dragend", function () {
    dragFrom = null;
    [].forEach.call($("slots").children, function (c) {
      c.classList.remove("dragging"); c.classList.remove("over");
    });
  });
  cell.addEventListener("dragover", function (e) {
    if (dragFrom === null) return;
    e.preventDefault();
    cell.classList.add("over");
  });
  cell.addEventListener("dragleave", function () { cell.classList.remove("over"); });
  cell.addEventListener("drop", function (e) {
    e.preventDefault();
    var to = Number(cell.dataset.i);
    if (dragFrom === null || to === dragFrom) return;
    var moving = theSet[dragFrom];
    if (!moving) return;
    if (theSet[to]) {
      var tmp = theSet[to]; theSet[to] = moving; theSet[dragFrom] = tmp;
    } else {
      theSet.splice(dragFrom, 1);
      theSet.splice(Math.min(to, theSet.length), 0, moving);
    }
    dragFrom = null;
    renderComposer();
  });
}

function syncAddButton() {
  var b = $("add");
  if (!b) return;
  if (!sel || !sel.uri || sel.slug === "compose") {
    b.disabled = true; b.textContent = "Add to set"; return;
  }
  if (inSet(sel)) { b.disabled = true; b.textContent = "In the set"; return; }
  b.disabled = theSet.length >= shape;
  b.textContent = theSet.length >= shape ? "Set is full" : "Add to set";
}

$("add").onclick = function () { if (sel && sel.uri) addToSet(sel); };
$("clearset").onclick = function () { theSet = []; renderComposer(); };
$("csize").onchange = function () { renderComposer(); };

// The same preference either way, so the box is always to hand — beside Make
// when composing, beside Download when it is a single work.
function syncTitleBoxes() {
  $("ctitles").checked = withTitles;
  $("stitles").checked = withTitles;
  // The pill carries the state, the way the shape and collection chips do.
  // Done in script rather than with :has() so older mobile browsers get it too.
  ["ctitles", "stitles"].forEach(function (id) {
    var pill = $(id).closest(".titlepill");
    if (pill) pill.classList.toggle("on", withTitles);
  });
}
$("ctitles").onchange = function () {
  withTitles = this.checked;
  syncTitleBoxes();
  // A composite already on screen was rendered with the old choice, and unlike a
  // single work there is no live artwork to fall back to — the composite only
  // exists as the encoded GIF. Keeping it meant un-ticking left the titles both
  // on screen and in the download. So it is discarded, and Make is the way back.
  var stale = sel && sel.slug === "compose";
  if (stale) closePanel();
  renderComposer();
  if (stale) {
    $("chint").textContent = withTitles
      ? "Titles on — press Make it again to add them."
      : "Titles off — press Make it again to remove them.";
  }
  showLiveArtwork();
};
$("stitles").onchange = function () {
  withTitles = this.checked;
  syncTitleBoxes();
  // Drop the render and put the live artwork back. Without this, un-ticking left
  // the captioned GIF on screen and the title looked permanent — the download
  // was already correct, the picture was not.
  showLiveArtwork();
};

// Frames for one work at whatever size its cell needs.
function framesFor(w, size, frameCount, onStep) {
  if (w.slug === "bytegans") return bytegansFrames(w, size, onStep);
  if (w.slug === "wunderkammer") return wunderkammerFrames(w, size, onStep);
  return reflectionFrames(w, size, onStep, frameCount);
}

$("mkgrid").onclick = function () {
  var lay = LAYOUTS[shape];
  if (theSet.length !== shape) return;
  var mine = ++token;
  // Composites carry their own size, and it runs large on purpose: the cell is
  // what governs sharpness, and at 480 a triptych cell is only 140px — a 1200px
  // Reflection crushed to nothing. Measured worst case, four Reflections in a
  // quadtych at 1440: 650px cells and 6.69MB, against X's 14MB ceiling.
  var geo = geometry(lay, parseInt($("csize").value, 10), withTitles);

  $("mkgrid").disabled = true;
  $("panel").hidden = false;
  $("pt").textContent = lay.name.charAt(0).toUpperCase() + lay.name.slice(1);
  $("pm").innerHTML = "<b>" + lay.label + "</b> · "
    + theSet.map(function (w) { return w.title; }).join(" · ");
  $("warn").textContent = "";
  $("dl").disabled = true;
  $("prev").removeAttribute("src");

  var total = theSet.length, done = 0, results = [];
  showProgress("Rendering work 1 of " + total, 0, 1);

  // Sequential: several works rendering at once would contend for the main
  // thread and make the progress meaningless.
  theSet.reduce(function (chain, w, k) {
    return chain.then(function () {
      // Report per FRAME, not per work. Reporting only "2 of 3" left the bar
      // frozen for the twenty-odd seconds a Reflection takes, which reads as a
      // hang. Progress runs continuously across the whole build: each work owns
      // a slice of the bar and fills it as its frames come in.
      return framesFor(w, geo.cell, COMPOSE_FRAMES, function (i, m) {
        var within = m ? i / m : 0;
        showProgress("Rendering work " + (k + 1) + " of " + total
                     + " — frame " + i + " of " + m,
                     (k + within) / total * RENDER_SHARE, 1);
      }).then(function (r) {
        results[k] = r;
        done++;
      });
    });
  }, Promise.resolve()).then(function () {
    if (mine !== token) return;
    showProgress("Composing and encoding", RENDER_SHARE, 1);
    return Promise.all([yieldToPaint(), capFontReady]).then(function () {
      var frames = [], delays = [];
      var c = document.createElement("canvas");
      c.width = geo.W; c.height = geo.H;
      var ctx = c.getContext("2d", { willReadFrequently: true });
      var scratch = document.createElement("canvas");
      var sctx = scratch.getContext("2d");

      for (var i = 0; i < COMPOSE_FRAMES; i++) {
        ctx.fillStyle = GROUND;
        ctx.fillRect(0, 0, geo.W, geo.H);
        for (var k = 0; k < results.length; k++) {
          var src = results[k].frames, box = cellBox(lay, geo, k);
          // Every work completes exactly one loop across the composite's loop,
          // so it repeats seamlessly however long each piece natively runs.
          var f = src[Math.floor(i * src.length / COMPOSE_FRAMES) % src.length];
          if (scratch.width !== f.width || scratch.height !== f.height) {
            scratch.width = f.width; scratch.height = f.height;
          }
          sctx.putImageData(f, 0, 0);
          ctx.drawImage(scratch, box.x, box.y, geo.cell, geo.cell);
          if (geo.capH) {
            drawCap(ctx, theSet[k].title, box.x, box.y + geo.cell, geo.cell, geo.capH);
          }
        }
        frames.push(ctx.getImageData(0, 0, geo.W, geo.H));
        delays.push(150);
      }

      var blob = GIF.encode(frames, delays, 256);
      built = { blob: blob, size: geo.W, key: lay.name };
      sel = { slug: "compose", id: 0, title: lay.name,
              names: theSet.map(function (w) { return w.title; }),
              sets: theSet.map(function (w) { return w.slug; }) };
      singleOnly(false);
      // The composite carries a caption under every work already. Whatever single
      // work was open before Make was pressed had left its own band up, and
      // nothing here took it down — so a finished tych sat under a stray title
      // belonging to one of its parts.
      syncPreviewCap();
      var img = $("prev");
      img.style.width = geo.W + "px";
      img.src = URL.createObjectURL(blob);
      img.onload = reportScale;
      hideProgress();
      $("dl").disabled = false;
      var kb = blob.size / 1024;
      $("warn").textContent = COMPOSE_FRAMES + " frames · " + geo.W + "×" + geo.H
        + " (" + lay.label + ") · " + geo.cell + "px cells · "
        + (kb > 1024 ? (kb / 1024).toFixed(1) + "MB" : Math.round(kb) + "KB")
        + " · " + (1000 / 150).toFixed(1) + " fps"
        + (blob.size > 15 * 1024 * 1024
            ? " — over X's 15MB ceiling, try a smaller size" : "");
      renderComposer();
    });
  }).catch(function (e) {
    if (mine !== token) return;
    hideProgress();
    renderComposer();
    $("warn").textContent = chainTrouble(e, "Couldn't build that");
  });
};

/* ----------------------------------------------------------------- export */

function grab(href, filename) {
  var a = document.createElement("a");
  a.href = href; a.download = filename; a.rel = "noopener";
  document.body.appendChild(a); a.click(); a.remove();
}

function slugify(str) {
  return String(str)
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")   // clé -> cle
    .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

// Cut on a word boundary. Slicing mid-slug left filenames ending in half a
// title, or in a bare hyphen.
function clip(str, max) {
  if (str.length <= max) return str;
  var cut = str.slice(0, max);
  var lastGap = cut.lastIndexOf("-");
  return (lastGap > max / 2 ? cut.slice(0, lastGap) : cut).replace(/-+$/, "");
}

// Collection first, then the shape if it is a composite, then the titles:
//   wunderkammer-golden-beetle
//   reflection-triptych-language-is-a-skin-the-hive-mind-acute-innocence
// A composite drawn from more than one collection has no single collection to
// name, so it keeps the studio's own.
function fileName(w) {
  if (w.slug !== "compose") return slugify(LABELS[w.slug]) + "-" + slugify(w.title);
  var kinds = [];
  (w.sets || []).forEach(function (k) { if (kinds.indexOf(k) < 0) kinds.push(k); });
  var lead = kinds.length === 1 ? slugify(LABELS[kinds[0]]) : "sovrn";
  return lead + "-" + slugify(w.title) + "-"
    + clip((w.names || []).map(slugify).join("-"), 80);
}

$("src").onclick = function () {
  if (sel && sel.uri) grab(sel.uri, fileName(sel) + ".svg");
};

function deliver() {
  var url = URL.createObjectURL(built.blob);
  grab(url, fileName(sel) + ".gif");
  setTimeout(function () { URL.revokeObjectURL(url); }, 30000);
}

$("dl").onclick = function () {
  // A composite is already encoded by the time it reaches the screen — Make did
  // that work. This used to fall through to build(), which reads sel.slug to
  // choose a frame maker; "compose" matched none of them, so it landed on
  // reflectionFrames and handed it a work with no SVG. Nothing resolved and
  // nothing threw, so the bar sat at "Rendering frames" for good.
  if (sel && sel.slug === "compose") {
    if (built) deliver();
    return;
  }
  if (!sel || !sel.uri) return;
  var want = parseInt($("size").value, 10);
  // Reuse the last render only if it is this work at this size.
  if (built && built.key === sel.slug + ":" + sel.id + (withTitles ? ":t" : "")
      && built.size === want) {
    deliver();
    return;
  }
  build().then(function () { if (built) deliver(); });
};
