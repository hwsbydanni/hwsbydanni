# Site checks

Scripts that check the site the way a browser sees it, rather than the way the
source reads. Each one exists because it caught something that reading the CSS
had already missed.

```bash
pip install -r tools/requirements.txt
playwright install chromium

tools/check_all.sh              # the fast set, ~1 minute
tools/check_all.sh --states     # adds hover and open accordions, ~6 minutes
```

Every check exits non-zero on failure, so `check_all.sh` can gate a commit.

---

## What each one does

### `check_contrast.py` — WCAG AA colour contrast

Every text run on every page, in both themes, against 4.5:1 for body text,
3:1 for large text (≥24px, or ≥18.66px bold) and 3:1 for icon-only controls.

`--states` runs a second pass with every `<details>` open and hovering every
link, summary and button in turn. Worth the extra minutes before shipping a
colour change: the resting pass once reported a clean sheet while five hover
colours were still unreadable.

### `check_gutters.py` — nothing jammed against a phone's edge

Measures text at 320 / 360 / 390 / 414 / 480px and reports anything inside a
16px margin, plus any page wider than its own viewport.

### `check_metadata.py` — titles, descriptions, canonicals, sitemap

No browser, so it is fast enough to run on every commit. Title and description
lengths, canonical and `og:url` matching the page's own URL, the full og and
twitter set, exactly one `<h1>`, `lang`, viewport, no stray `noindex`, JSON-LD
that parses, internal links that resolve, and a sitemap that parses and covers
every page exactly once with well-formed dates.

### `check_css.py` — keep `home.css` an override layer

`index.html` loads `styles.css` and then `home.css`, which makes two mistakes
easy. A rule duplicated in `home.css` goes stale the moment someone fixes the
shared one. A rule in `home.css` with no media query outranks a `styles.css`
rule that has one, because it loads later. Both have happened here.

### `snapshot.py` — prove a change did only what you meant

```bash
git stash
python3 tools/snapshot.py /tmp/before.json
git stash pop
python3 tools/snapshot.py /tmp/after.json
python3 tools/snapshot.py --diff /tmp/before.json /tmp/after.json
```

Records ~25 computed properties and a bounding rect for every element on every
page, four widths, both themes. The diff separates what you changed from what
merely moved as a result, so a one-line token edit does not read as three
thousand regressions.

### `sitemap_dates.py` — what `lastmod` should say

Reports only; you edit `sitemap.xml` yourself so the judgement stays visible.
See the comment at the top of `sitemap.xml` for why raw git dates are wrong.

---

## Five things these scripts get right that are easy to get wrong

Each of these is a bug one of the checks let through before it was fixed.

**1. Strip `has-motion` before measuring anything.** `motion.css` holds
`.reveal` at `opacity: 0` until an IntersectionObserver adds `.is-visible`.
Without stripping it, everything below the fold measures as invisible and the
check silently passes. This is handled in `audit_common.prepare()`.

**2. Disable transitions before reading a colour.** CSS colour transitions are
still mid-flight right after a theme switch, so `getComputedStyle` returns
intermediate values. Two identical runs once disagreed on 384 findings. Also
in `prepare()`.

**3. Measure text, not boxes.** A full-width `<li>` whose `<a>` carries 40px
of padding is not text running to the edge. Measuring element boxes reported
561 gutter problems where there were 235. `check_gutters.py` uses Range rects
on the text nodes.

**4. Composite the background, and fold in opacity.** A translucent background
has to be flattened against what is behind it, and `opacity` fades text toward
its backdrop before it reaches the eye. Treating `rgba(198,154,84,0.08)` as
opaque gold reported a passing link at 1.6:1. Over a gradient no single colour
exists, so those elements are skipped rather than guessed at.

**5. A colour-only change still needs a render diff.** Removing an `opacity`
made one span measure 1px taller. Nothing moved, but it is the kind of thing
worth seeing rather than assuming.

---

## Notes

- `404.html` is skipped: it links its assets from `/`, so it renders unstyled
  over `file://`. Check it on the live site.
- The checks read the working tree over `file://`. They do not need a server.
- `check_css.py`'s parser is a lint, not a CSS engine. It handles these two
  stylesheets; it does not understand `@supports` nesting or CSS nesting
  syntax.
