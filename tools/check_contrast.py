#!/usr/bin/env python3
"""WCAG AA contrast, every page, both themes, resting and interactive.

    python3 tools/check_contrast.py              # resting state only (fast)
    python3 tools/check_contrast.py --states     # also hover + open accordions

The --states pass is slower (it hovers every link on every page) but it is
where five unreadable hover colours were found after the resting pass had
already reported a clean sheet. Run it before shipping a colour change.

Exit code is non-zero if anything fails, so it can gate a commit.
"""
import argparse
import collections
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from audit_common import COLOUR_JS, launch, pages, prepare, report, url  # noqa: E402

THEMES = ('light', 'dark')

RESTING = "() => {" + COLOUR_JS + r"""
  const out=[];
  document.querySelectorAll('*').forEach(e => {
    if (!e.offsetParent) return;
    const txt=[...e.childNodes].filter(n=>n.nodeType===3)
                .map(n=>n.textContent.trim()).join(' ').trim();
    if (!txt) return;                       // only elements holding real text
    const bg=bgStack(e); if(!bg) return;    // over a gradient: unmeasurable
    const cs=getComputedStyle(e);
    if (cs.visibility==='hidden' || +cs.opacity===0) return;
    const need=threshold(cs), r=ratio(foreground(e,bg), bg);
    if (r>=need) return;
    out.push({sel:label(e), r, need, fg:hex(foreground(e,bg)), bg:hex(bg), txt:txt.slice(0,30)});
  });
  return out;}"""

# For hover we walk interactive elements one at a time, so this takes an index.
# It measures the hovered element AND everything inside it: a :hover that
# changes a row's background can push a price or a label inside that row under
# AA without touching the row's own colour.
ONE = "(i) => {" + COLOUR_JS + r"""
  const host=document.querySelectorAll('a,summary,button')[i];
  if(!host || !host.offsetParent) return [];
  const out=[];
  for (const e of [host, ...host.querySelectorAll('*')]) {
    if (!e.offsetParent) continue;
    const own=[...e.childNodes].filter(n=>n.nodeType===3)
                .map(n=>n.textContent.trim()).join(' ').trim();
    const isHost = e===host;
    // The host counts even with no text of its own: an icon-only control is
    // non-text, which WCAG 1.4.11 puts at 3:1 rather than 4.5:1.
    if (!own && !(isHost && !host.textContent.trim())) continue;
    const bg=bgStack(e); if(!bg) continue;
    const cs=getComputedStyle(e);
    if (cs.visibility==='hidden' || +cs.opacity===0) continue;
    const need = own ? threshold(cs) : 3;
    const r=ratio(foreground(e,bg), bg);
    if (r<need) out.push({sel:label(e), r, need, fg:hex(foreground(e,bg)), bg:hex(bg),
                          txt:(own || '(icon)').slice(0,30)});
  }
  return out;}"""
# Unfiltered, to stay in step with Playwright's nth(i); ONE skips the hidden ones.
COUNT = "() => document.querySelectorAll('a,summary,button').length"


def worst_by_selector(rows):
    g = collections.defaultdict(lambda: {'n': 0, 'worst': 99, 'ex': None})
    for page, theme, r in rows:
        k = (r['sel'], theme)
        g[k]['n'] += 1
        if r['r'] < g[k]['worst']:
            g[k].update(worst=r['r'], ex=(page, r))
    return g


def run(states):
    resting, interactive = [], []
    with sync_playwright() as pw:
        browser = launch(pw)
        for theme in THEMES:
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            for f in pages():
                page.goto(url(f), wait_until='load')
                prepare(page, theme, open_details=states)
                # The pointer survives navigation, so park it off the page or
                # the "resting" pass measures whatever is under it in :hover.
                page.mouse.move(0, 0)
                page.wait_for_timeout(30)
                for r in page.evaluate(RESTING):
                    resting.append((f, theme, r))
                if not states:
                    continue
                els = page.locator('a,summary,button')
                for i in range(page.evaluate(COUNT)):
                    try:
                        els.nth(i).hover(timeout=1500)
                    except Exception:
                        continue          # off-screen or covered; nothing to measure
                    page.wait_for_timeout(25)
                    for r in page.evaluate(ONE, i):
                        interactive.append((f, theme, r))
            page.close()
        browser.close()

    def line(item):
        (sel, theme), g = item
        pg, ex = g['ex']
        return (f'{sel[:38]:38} {theme:5} n={g["n"]:<3} worst {g["worst"]:>5} '
                f'(need {ex["need"]})  {ex["fg"]} on {ex["bg"]}  {pg} "{ex["txt"]}"')

    bad = report('Resting state', sorted(worst_by_selector(resting).items()), line)
    if states:
        bad |= report('Hover + open accordions', sorted(worst_by_selector(interactive).items()), line)
    return bad


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--states', action='store_true',
                    help='also hover every link and open every <details>')
    print(f'Contrast: {len(pages())} pages x {len(THEMES)} themes, '
          f'4.5:1 body / 3:1 large / 3:1 icon-only')
    sys.exit(run(ap.parse_args().states))
