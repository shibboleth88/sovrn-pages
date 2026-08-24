/* Rotation for the hub cards.

   Each card holds one work, then cross-fades to another from the same
   collection. A handful each, not the whole pool — this is a way in, not the
   tool, and every change pulls another file.

   The page works without this: the markup already carries the first frame, and
   these SVGs animate by themselves inside an <img>, so with JavaScript off the
   cards are still alive, just not turning. Nothing here is load-bearing.

   FRAMES[slug][0] must match the <img src> and the <link rel="preload"> in
   shareables.html, which are in turn pinned to the frame each scoped share page
   opens on. tools/check-share-pages.py holds all of that together. */
(function () {
  var FRAMES = {
    reflection:   { dir: "img/collections/reflection/", stem: "reflection-", at: [2, 10, 18, 26] },
    wunderkammer: { dir: "img/wunderkammer-works/", stem: "wunderkammer-", at: [8, 17, 26, 35] },
    bytegans:     { dir: "img/bytegans/", stem: "bytegan-", at: [15, 21, 3, 9] }
  };
  // Matches the tool's own panels, so the two pages feel like one thing.
  var HOLD_MS = 7000, FADE_MS = 1000;

  var cards = [], timers = [];

  function pathOf(slug, i) {
    var f = FRAMES[slug];
    return f.dir + f.stem + (i < 10 ? "0" + i : i) + ".svg";
  }

  [].forEach.call(document.querySelectorAll("a.panelcard[data-c]"), function (el) {
    var slug = el.getAttribute("data-c");
    if (!FRAMES[slug]) return;
    var front = el.querySelector("img");
    if (!front) return;
    // The second layer is made here rather than in the markup: without script
    // there is nothing to fade to, and an empty <img> would only be a stray
    // request and a broken-image icon.
    var back = document.createElement("img");
    back.alt = "";
    back.className = "out";
    back.decoding = "async";
    front.parentNode.insertBefore(back, front.nextSibling);
    cards.push({ slug: slug, front: front, back: back, at: 0, busy: false });
  });

  function turn(card) {
    if (document.hidden || card.busy) return;
    card.busy = true;
    var list = FRAMES[card.slug].at;
    card.at = (card.at + 1) % list.length;
    var src = pathOf(card.slug, list[card.at]);
    var probe = new Image();
    var release = function () { card.busy = false; };
    probe.onload = function () {
      // Decode before the fade, or the card fades up onto a blank.
      var ready = probe.decode ? probe.decode() : Promise.resolve();
      ready.catch(function () {}).then(function () {
        card.back.src = src;
        card.back.classList.remove("out");
        card.front.classList.add("out");
        var tmp = card.front; card.front = card.back; card.back = tmp;
        setTimeout(release, FADE_MS + 80);
      });
    };
    // Clear the flag on error too, or one failed fetch strands the card for good.
    probe.onerror = release;
    probe.src = src;
  }

  function start() {
    stop();
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    // Every change pulls another file, so stay off under Data Saver.
    if (navigator.connection && navigator.connection.saveData) return;
    cards.forEach(function (card, n) {
      timers.push(setTimeout(function tick() {        // staggered, so the three
        turn(card);                                   // never change together
        timers.push(setTimeout(tick, HOLD_MS));
      }, HOLD_MS / 2 + n * (HOLD_MS / 3)));
    });
  }

  function stop() {
    timers.forEach(clearTimeout);
    timers = [];
  }

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) stop(); else start();
  });

  start();
})();
