/* Pair one element across a navigation, so the artwork moves rather than blinks.
 *
 * The pairing has to be worked out per navigation rather than declared in CSS:
 * a view-transition-name must be unique in a document, and the element that
 * should travel depends on which card was clicked. The pages also do not share
 * a hero markup pattern — some build their images in script — so a single CSS
 * selector could not name the right thing on every page anyway.
 *
 * pageswap fires on the page being left, pagereveal on the page being entered.
 * If either side cannot find its element the navigation is simply a cross-fade,
 * which is why nothing here throws or guards beyond a null check.
 */
(function () {
  if (!document.startViewTransition) return;

  var NAME = "art";

  function pathOf(u) {
    try { return new URL(u, location.href).pathname.replace(/\/+$/, ""); }
    catch (e) { return ""; }
  }

  /* The image inside a card linking to `path`, if this page shows one. */
  function cardImageFor(path) {
    if (!path) return null;
    var a = document.querySelector('a.card[href="' + path + '"]') ||
            document.querySelector('a.card[href="' + path + '/"]');
    return a ? a.querySelector("img") : null;
  }

  /* Otherwise this page's own lead image: the largest one near the top, ignoring
     the logo and navigation so a 40px mark never wins. */
  function leadImage() {
    var best = null, bestArea = 12000;      /* below this it is furniture, not artwork */
    var imgs = document.querySelectorAll("img");
    for (var i = 0; i < imgs.length; i++) {
      var im = imgs[i];
      if (im.closest("nav, .nav, a.logo, .logo")) continue;
      var r = im.getBoundingClientRect();
      if (r.top > (window.innerHeight || 800)) continue;
      var area = r.width * r.height;
      if (area > bestArea) { bestArea = area; best = im; }
    }
    return best;
  }

  function give(el) { if (el) el.style.viewTransitionName = NAME; }

  function clear() {
    var named = document.querySelectorAll('[style*="view-transition-name"]');
    for (var i = 0; i < named.length; i++) named[i].style.viewTransitionName = "";
  }

  /* A page that declares .vt-lead has already named its element in CSS. Naming a
     second one here would put two elements under the same name, which makes the
     browser drop the pairing altogether — so leave those pages alone. */
  function declared() { return !!document.querySelector(".vt-lead"); }

  addEventListener("pageswap", function (e) {
    if (!e.viewTransition || declared()) return;
    var to = (e.activation && e.activation.entry) ? pathOf(e.activation.entry.url) : "";
    give(cardImageFor(to) || leadImage());
  });

  addEventListener("pagereveal", function (e) {
    if (!e.viewTransition) return;
    if (!declared()) {
      var from = (window.navigation && navigation.activation && navigation.activation.from)
        ? pathOf(navigation.activation.from.url) : "";
      give(cardImageFor(from) || leadImage());
    }
    e.viewTransition.finished.then(clear, clear);
  });
})();
