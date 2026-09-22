#!/usr/bin/env python3
"""No text should run into the edge of a phone screen.

    python3 tools/check_gutters.py            # 320/360/390/414/480, 16px gutter
    python3 tools/check_gutters.py --gutter 20 --widths 320,390

Also reports horizontal overflow, which is the other way a narrow screen goes
wrong: the page itself becomes wider than the viewport.

It measures the TEXT, via Range rects, not the element box. Measuring boxes
reports a full-width <li> as touching the edge even when the <a> inside it
carries 40px of padding; that mistake turned 235 real findings into 561.
"""
import argparse
import collections
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from audit_common import launch, pages, prepare, report, url  # noqa: E402

JS = r"""([W, GUT]) => {
  const out=[], walker=document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {
    if (!n.textContent.trim()) continue;
    const p = n.parentElement;
    if (!p || !p.offsetParent) continue;
    const cs = getComputedStyle(p);
    if (cs.visibility === 'hidden' || +cs.opacity === 0) continue;
    // A deliberately swipeable rail scrolls past the edge by design.
    if (p.closest('.jump-inner, [style*="overflow-x"]')) continue;
    const rng = document.createRange(); rng.selectNodeContents(n);
    for (const r of rng.getClientRects()) {
      if (!r.width || !r.height) continue;
      if (r.left >= GUT && r.right <= W - GUT) continue;
      let a = p, sel = p.tagName.toLowerCase();
      while (a && !(typeof a.className === 'string' && a.className.trim())) a = a.parentElement;
      if (a) sel = a.tagName.toLowerCase() + '.' + a.className.trim().split(/\s+/)
                    .filter(c => !/^(reveal|reveal-item|is-visible)$/.test(c)).join('.');
      out.push({sel, left: Math.round(r.left), right: Math.round(r.right),
                txt: n.textContent.trim().slice(0, 30)});
      break;
    }
  }
  return out;}"""
OVERFLOW = "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"


def run(widths, gutter):
    tight = collections.defaultdict(list)
    overflow = []
    with sync_playwright() as pw:
        browser = launch(pw)
        page = browser.new_page(viewport={'width': widths[0], 'height': 844})
        for w in widths:
            page.set_viewport_size({'width': w, 'height': 844})
            for f in pages():
                page.goto(url(f), wait_until='load')
                prepare(page)
                for r in page.evaluate(JS, [w, gutter]):
                    tight[r['sel']].append((f, w, r))
                o = page.evaluate(OVERFLOW)
                if o > 1:
                    overflow.append((f, w, o))
        browser.close()

    bad = report(f'Text inside the {gutter}px gutter',
                 sorted(tight.items(), key=lambda kv: -len(kv[1])),
                 lambda kv: (f'{kv[0][:40]:40} n={len(kv[1]):<3} '
                             f'e.g. {kv[1][0][0]} @{kv[1][0][1]}px '
                             f'L={kv[1][0][2]["left"]} R={kv[1][0][2]["right"]} '
                             f'"{kv[1][0][2]["txt"]}"'))
    bad |= report('Horizontal overflow', overflow,
                  lambda x: f'{x[0]} @{x[1]}px overflows by {x[2]}px')
    return bad


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--widths', default='320,360,390,414,480')
    ap.add_argument('--gutter', type=int, default=16)
    a = ap.parse_args()
    widths = [int(w) for w in a.widths.split(',')]
    print(f'Gutters: {len(pages())} pages x widths {widths}, minimum {a.gutter}px')
    sys.exit(run(widths, a.gutter))
