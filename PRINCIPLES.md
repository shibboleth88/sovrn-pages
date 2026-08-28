# Principles

Everything here was learned by getting it wrong on this site. Each one is stated
as a rule, with the failure that produced it, because a rule with no incident
attached is advice and gets ignored — and because the incident is usually the
part that makes the rule stick.

`NOTES.md` holds the specifics: what a particular collection contains, how a
particular tool behaves. This file holds the things that generalise.

Add to it when something surprises you. A near miss belongs here as much as a
shipped bug; the shipped bug is only the near miss you did not notice.

---

## Verifying

### A check that regenerates its input is not a check

`build-bytegans.py --check` rebuilt the data files and then verified what it had
just written. It could only ever catch a bug in itself, never drift in what was
actually being served. It passed, cheerfully, with two artworks swapped by hand.

A check reads what is on disk. If it writes anything first, it is a build step
wearing a check's clothes.

### Prove a check fails before believing that it passes

The fix above was only believable once the corruption was reintroduced and the
check reported it and exited non-zero. Until then it was a function that printed
a reassuring sentence.

Every check added here should be run once against known-bad input. If you cannot
produce known-bad input, you do not yet know what the check is for.

### Absence of an error is not evidence of success

A CSP-blocked iframe still fires `onload`. The framing test looked like it
passed; only the console said the frame had been refused. The same shape recurs
everywhere: a 200 that is a bot wall, a request that resolves to a placeholder,
a screenshot of a page that has not painted.

Find the positive signal — the thing that can only be true if it worked — and
assert on that.

### When a measurement comes back suspiciously uniform, suspect the measurement

Reading agent positions out of the page returned *every one of them at y=0*. The
page was fine; the regex did not allow for the spaces a browser inserts when it
serialises `translate3d`, so every match failed and every value fell through to
a default of zero.

A result that is too clean is a result about your instrument. Print one raw
sample before believing an aggregate.

### Measure where the frames actually run

Motion could not be observed through the browser pane: a tab that is not being
looked at throttles `requestAnimationFrame` to about 2fps, and the frame delta is
clamped, so a wandering byteGAN advanced in slow motion and screenshots showed it
frozen. Three separate attempts to "see" it failed before this was understood.

Extract the page's own script and drive it under a controlled clock instead. Doing
that tests the shipped code — not a reimplementation of it — and gives numbers
that mean something: distance travelled, how many paused, whether any left the
box.

### A status code from outside a browser cannot tell a dead link from a bot wall

raster.art answers `429` for every path, valid or not. Medium answers `403`,
the WSJ `401`. `curl` cannot distinguish any of these from a genuine death, and
a 429 body looks exactly like a 404 body if you only read the body.

Load the page in a real browser, wait for the checkpoint, and always include a
deliberately bogus URL as a control so you can prove a 404 is real.

---

## Changing things

### A slice by marker must assert that it found something

A script that rebuilt a page cut the "links and footer" block by searching for a
marker. The marker had moved above the text being cut, so the slice returned an
empty string, and the page was rebuilt without its Raster link, its SuperRare
link, the artist's X, or its credit line. Every check passed. It was live for an
hour.

Assert the length. `assert block, "links block came back empty"` would have cost
nothing and stopped it.

### The checks you have are about the things you have already broken

Nothing caught the missing footer because every existing check was about assets
resolving. The page was well-formed in every checkable way and missing its point.

When something ships broken, the fix is two commits' worth of work: the repair,
and the check that would have caught it. `check-site.py --files` now asserts every
collection page keeps a way out and a way home.

### Test for the thing, not for the markup around it

The first version of that check looked for `class="links"`, and reported three
false problems on pages that carry their links in different markup. A check that
cries wolf teaches you to ignore it, which is worse than not having it.

It looks for the Raster URL and the credit line themselves now. Where a page
genuinely lacks one — Reflection has no credit line — that is recorded as a named
exception, so it stays visible as something to settle rather than becoming a hole.

### Check who reads a file before deleting it

`img/bytegans/` looked like twenty-four duplicates of files already in the
mirror, and it is. It is also what `share.js` reads for its sample strip.

Grep the whole repo for a filename before removing it, including from `.js`.

### Never retype what you can parse

Five URLs were transcribed by hand out of a display that silently truncated at
110 characters. All five 404'd. Since then, lists of URLs are generated from a
parse of the source and never read off a screen.

### Verify before destroying

A shell loop that word-split filenames on spaces reported a thousand photographs
as missing from the backup drive when they were all present. Had that been
believed, the originals would have been deleted.

Do file work in a language with real string handling, and confirm by content —
every one of those thousand was matched by MD5 before anything was removed.

---

## The browser's own rules

### A transform creates a stacking context, so z-index inside it is local

A translation panel on the CENTS page kept being painted over by the row below
it, and raising its z-index from 9 to 40 changed nothing — which was the clue,
and I read it as a fade instead. The link the panel sits in has
`transform: translateX(6px)` on hover, the row's slide-right. **A transform
creates a stacking context**, so the panel's z-index only ever ranked it inside
that link. Nothing it could be set to would lift it above a later sibling.

The fix is never a bigger number. Lift the thing that is a sibling of what is
covering you — here `li:hover { z-index: 41 }`, which raises the whole row,
transform and panel and all. `opacity` below 1, `filter`, `will-change`,
`contain` and `perspective` all do the same thing as `transform`, and none of
them look like they are about painting order.

**When raising a z-index does nothing, stop raising it.** That is not a weak
effect, it is the wrong axis, and it means something between you and the root
has closed a stacking context over your head.

### The UA sheet is the weakest sheet

`[hidden]` is only `display:none` in the user-agent stylesheet, so any class that
sets `display` beats it. A button with `hidden` stayed on screen because `.cta`
set `display:inline-flex`. It was visible in a screenshot and invisible to every
test.

### Presentational attributes are CSS, and they win where you are not looking

`width` and `height` on an `<img>` become real CSS declarations. A specified
height beats `aspect-ratio`, so tiles meant to be square came out 34×11 while the
rule intended to square them sat there looking correct.

Either set `height:auto` and let the ratio work, or size by the attributes alone
and add no CSS at all. Both are fine; the mixture is the trap.

### A `<source>` beats a later `src`

Wrapping an `<img>` in `<picture>` breaks any image whose `src` is later assigned
by JavaScript: the `<source>` continues to win. Every JS-driven image on the site
is therefore excluded from the responsive-images pass, by rule, in
`responsive-images.py`.

### An SVG loaded through `<img>` is a different document

It cannot see the host page's fonts. A `<text>` element used as a clip path fell
back to a system serif, and the wordmark silently became a different wordmark.
Outline the letters with fontTools instead. The same isolation means no scripts
run and no external resources load.

---

## Size, motion and layout

### Set what has to be read in the units the reader sees

The disc wordmark had its texture set as a fraction of the drawing, which is
1200 units wide and displayed at 340. Everything inside it was therefore divided
by three and a half on the way to the screen, and the addresses it is made of
arrived at 1.4px: not small text, but noise with no letters in it.

Copying a ratio from another mark looked like consistency and was the bug. If
something must be legible, compute its size from the size it is actually shown at.

### Ink is coverage times passes, and bigger characters cover less

Making those characters five times larger emptied the letterforms — the same
address written large leaves more paper between its strokes — so the stencil
needed three passes of gold instead of two. One pass at that size is not a
fainter word, it is no word.

A parameter that looks independent often is not. Change one and re-check the
other.

### When the input is a sample you choose, quality is a selection criterion

A third of the byteGANs cannot have their backgrounds removed, and no amount of
cleverness will change that: a midnight skullGAN is a field of four blues with no
figure in it to separate. Effort went into handling animating grounds and
dithered grounds, both of which were real and worth fixing — but the works with
no figure at all were never a processing problem.

The page shows a few hundred of the 1,111 and the sample was already being
chosen. Making "separates cleanly" one of the criteria cost nothing in size and
removed the whole class of bad results. Measured on the result rather than the
source: does the cut keep every frame, leave the creature in one piece, remove
something from every frame, and strand no more background inside the figure than
a pair of eyes.

The threshold came from a sweep, and the sweep is what stopped it going too far:
one notch tighter dropped the eligible works from 754 to 556 and took the only
kingGAN with it, which the page promises. Tune a filter until it starts removing
something you need, then step back one.

### Removing a background is not keying out a colour

Cutting the backgrounds off the byteGANs so the creature wanders instead of the
tile looks like a one-liner: find the commonest colour, make it transparent. It
is wrong on every single work in the collection. The ground colour also appears
*inside* the figure — the eyes, the mouth, the gaps between limbs are background
showing through — so keying the colour punches holes in every face. Measured: 3
to 7 pixels of trapped ground in each work checked, in all of them.

What is wanted is the *background*, meaning the pixels of that colour reachable
from the edge, which is a flood fill and not a filter. The difference does not
show up in a thumbnail and is glaring at 34px.

Two more things, found only by measuring the result rather than looking at it:

**A property of a work may not be a property of its frames.** The ground colour
was taken once, as the commonest across the whole animation, and filled in every
frame. Some of these grounds animate — one cycles its cyan through five shades,
another alternates bone with near-black — so those frames matched nothing and
came out entirely uncut. One frame in the cast was 0% transparent: a full opaque
square in the middle of an otherwise clean cutout, flickering once a cycle.
Each frame's own border says what its background is.

**And check the result, not the code.** None of this was visible in a montage of
first frames, because first frames were fine. It surfaced from a measurement —
transparency per frame, per work, sorted worst-first — which is the sort of thing
worth computing whenever a batch operation runs over hundreds of items. The
sorted list also cleared the survivors: the remaining low scorer is a *decohering*
skullGAN whose figure genuinely fills the tile, which the number alone would have
condemned.

### Text is about half transparent

A disc made only of characters let the homepage mosaic straight through and
stopped reading as a disc. It had held on a flat test page only because that
background was uniform.

Anything built out of type needs an opaque ground under it if it has to work over
arbitrary content — and it has to be tested over the actual content, not over
grey.

### A seamless loop is arithmetic

A marquee track written twice and translated `-50%` twitches on every wrap if the
spacing is a flex `gap`: the track measures `2n·w + (2n−1)·g`, and half of that
falls half a gap short of where the second copy begins.

Put the spacing in a margin on each tile and the track is exactly `2n·(w+g)`.
Check the number rather than the animation — 92 tiles at 44+3 gives 4324px, and
half of it is 46 tiles precisely.

### Lazy loading needs a box to defer

`loading="lazy"` on 1,111 tiles fetched all 1,111 immediately. Unloaded images
with no reserved height collapse to nothing, the document is then shorter than
the viewport, and every image is technically on screen.

Reserve the space — `aspect-ratio`, or width and height attributes — or lazy
loading is decoration.

### `1fr` fills the row, which is rarely what a lone item wants

A grid of `minmax(x, 1fr)` stretched a single kingGAN across a full-width panel
with an acre of empty ground beside it. Flex with `width: fit-content` sizes the
container to its contents — the full width for 289 works, one tile for one —
because `fit-content` is `min(max-content, available)`.

### One tab stop per crowd

1,111 focusable tiles put 1,111 tab stops between the top of the page and its
links. That is not navigation, it is a trap. Roving tabindex: the first item is
in the tab order, the arrow keys move within, and focus is restored when a dialog
closes.

Better still, ask whether the crowd should be focusable at all. The wandering
byteGANs are scenery: no pointer events, hidden from assistive tech, and nothing
is lost, because a moving 34px target was never a usable control.

### Motion that cannot be reduced should be removed

There is no gentler version of forty byteGANs wandering across a page. Under
`prefers-reduced-motion` the layer does not load at all, which is more honest
than parking them all over the text. The artwork itself keeps animating: eleven
frames of an eleven-pixel being is the work, not an effect.

### Something that works and cannot be seen is not working

Colliding byteGANs transformed correctly from the day it was written, and the
first report was that nothing was happening. It was true and it was invisible: a
given one changed every 29 seconds, the jolt announcing it lasted 0.28s and took
a 34px tile to 48px, and there was 0.44 of a jolt on screen at any instant. You
had to already be looking at the right tile at the right third of a second.

Tuning away from one failure — this must not strobe — walked straight past the
target into another. For anything meant to be noticed, compute the thing the
viewer actually experiences: how often does *this one* change, and how much of
the effect is on screen at any moment. Half of one is not enough.

### An optimisation that skips work can change behaviour, not just cost

Only the byteGANs inside the window are stepped, which is right and cheap. But
they were also choosing destinations anywhere on the page, so a visible one would
set off towards somewhere two screens down, walk out of the window — and freeze
there for good, because it was no longer being stepped. Every visible one
eventually does this. After three minutes the first screen was empty: y ranged
1130 to 2864 on a 2900px page, with nothing at all in the top third.

The optimisation was correct about cost and wrong about the world. It now works
because each one wanders only near where it lives, which keeps the density even
for as long as the page is open — and reads better anyway, since they mill about
instead of commuting.

Whenever you skip work for things that are out of view, ask what those things
were going to do, and whether not doing it is really the same as doing it
invisibly.

### A short run cannot find a slow leak

The first test of that landscape ran for twenty seconds and confirmed exactly
what it was asked to: the off-screen ones do not move. The drain needed three
minutes to become visible, and it was only noticed while measuring something
else entirely.

For anything that runs continuously, run it long enough to be boring, and check
the distribution rather than the instant — "still evenly spread over five bands
of the page after eight minutes" is a claim; "it looked fine" is not.

### Only animate what can be seen

A `requestAnimationFrame` loop for every section is battery spent on things
nobody is looking at. Sections start and stop with an `IntersectionObserver`;
agents outside the viewport are skipped in the loop, which makes the cost
proportional to the window rather than to the length of the page. Clamp the
frame delta, or a backgrounded tab returns to find everything teleported.

---

## Delivery

### A same-origin file has exactly the page's own availability

If it cannot be reached, there is no page either. Every other arrangement — a
public RPC, our own proxy, a custom domain — adds a host that can be blocked or
fail independently. Once you have said "this must work for everyone", that is the
only answer; nothing else removes the failure surface, it only shrinks it.

This is why 2,218 artworks are mirrored inside the site's own repository. It is
also why a custom domain forced the mirror to move: `www.sovrn.art` and
`shibboleth88.github.io` are different origins, and a cross-origin image taints
the canvas exactly like IPFS does.

### "Failed to fetch" plus a working same-origin file means a blocked hostname

That combination is the whole diagnosis, and it looks like a contract or chain
problem and is neither. `Failed to fetch` is a `TypeError` — the request never
completed at the network layer. Something merely down, erroring or rate-limiting
*answers*, and you see its message instead. Crypto RPC hostnames sit on filter
lists that uBlock, AdGuard, Brave and DNS filters enable by default.

### Requests, not bytes

On GitHub Pages the request count is the constraint long before the byte count
is. Pointing 1,111 `<img>` at 1,111 mirror files works and costs 1,111 requests
per visitor; the same artwork grouped into four files costs four. The bytes were
never the problem.

### Test a replacement with the real payload

`cloudflare-eth.com` answers `eth_blockNumber` perfectly and returns "Internal
error" on a real Reflection `tokenURI`, which is ~338,000 hex characters. A
smoke test with a small call qualifies providers that cannot serve the actual
request.

### Access is not a trigger

Granting a deploy service access to a repository does not create the webhook. The
service went green, served traffic, and ignored every push to `main` — a healthy
deployment is not evidence that push-to-deploy works. Confirm the trigger exists,
then confirm a push actually produces a build.

---

## Facts

### A number inside a heading is not the number

"Twelve works, three to a season" on the Seasons of Mobility page is a display
selection. The contract holds 365, one for each day. An earlier pass took the
heading as the collection size and published it.

Where a contract can answer, ask the contract.

### An identifier inside a title is a label, not an index

Every byteGAN is titled `<modifier> <kind>GAN #<n>`, and that `n` matches the
token id for exactly one of the 1,111. Reading `#950` off a title and fetching
token 950 returns a different work, with nothing to signal it.

Reflection has the same shape in gentler form: the artist's list is 1–999 and the
token ids are 0–998, so the id is always the list number minus one.

### Never rewrite a URL you are given

`/collections/fransisco-carolinum` is misspelled and is the live URL. Correcting
the spelling 404s. Fix it in prose only.

### A written record goes stale, including this one

Every checkable claim in this file was verified against the repository before it
was committed, and one was wrong: the misspelled museum URL was recorded as
`/museums/fransisco-carolinum` in an older set of notes, and those pages have
since moved under `/collections/`. Written from memory it would have sent the
next reader to a 404 while sounding authoritative — the worst combination a note
can have.

Check a claim before you repeat it, especially one you are confident about. The
confident ones are the ones nobody checks.

### Absent means unpublished, never zero

Where a source does not state a figure, the field is omitted rather than filled
with a plausible one, and the page says the source does not give it. A backfilled
guess is indistinguishable from a fact once it is written down.
