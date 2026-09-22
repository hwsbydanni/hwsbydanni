#!/usr/bin/env python3
"""Prove a CSS change did only what you meant it to.

    git stash                                     # or check out the old state
    python3 tools/snapshot.py before.json
    git stash pop
    python3 tools/snapshot.py after.json
    python3 tools/snapshot.py --diff before.json after.json

It records ~25 computed properties plus a bounding rect for every element on
every page, at four widths in both themes, then diffs them. The diff separates
what you changed (colours, fonts, padding) from what merely moved as a result
(rects, heights, grid tracks), so a one-line token edit does not read as three
thousand regressions.

This is the check that caught .pain-row losing its mobile layout, and that
confirmed a token change touched index.html and left the other 21 pages alone.
"""
import argparse
import collections
import json
import signal
import sys

# So that piping the diff into `head` ends quietly instead of tracebacking.
try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):
    pass

from playwright.sync_api import sync_playwright

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from audit_common import launch, pages, prepare, url  # noqa: E402

WIDTHS = (1440, 900, 820, 390)
THEMES = ('light', 'dark')
PROPS = """display position width height maxWidth padding margin border color backgroundColor
fontSize fontWeight lineHeight letterSpacing textTransform textAlign gridTemplateColumns
flexDirection alignItems justifyContent gap aspectRatio overflow opacity boxShadow""".split()

# Changes to these are usually a consequence of a change to something else.
CONSEQUENCE = {'@rect', 'height', 'width', 'margin', 'gridTemplateColumns', 'lineHeight',
               'letterSpacing'}

JS = """(props) => {
  const out=[];
  document.querySelectorAll('*').forEach(e => {
    const cs=getComputedStyle(e), r={};
    for (const p of props) r[p]=cs[p];
    const b=e.getBoundingClientRect();
    r['@rect']=[Math.round(b.x*10)/10, Math.round(b.y*10)/10,
                Math.round(b.width*10)/10, Math.round(b.height*10)/10];
    out.push(r);
  });
  return {h: document.documentElement.scrollHeight,
          w: document.documentElement.scrollWidth, els: out};}"""


def capture(out_path):
    snap = {}
    with sync_playwright() as pw:
        browser = launch(pw)
        page = browser.new_page(viewport={'width': WIDTHS[0], 'height': 900})
        for f in pages():
            for w in WIDTHS:
                for theme in THEMES:
                    page.set_viewport_size({'width': w, 'height': 900})
                    page.goto(url(f), wait_until='load')
                    prepare(page, theme)
                    snap[f'{f}|{w}|{theme}'] = page.evaluate(JS, PROPS)
        browser.close()
    json.dump(snap, open(out_path, 'w'))
    print(f'{out_path}: {len(snap)} page/viewport/theme combinations, '
          f'{len(next(iter(snap.values()))["els"])} elements each')


def diff(before_path, after_path):
    a, b = json.load(open(before_path)), json.load(open(after_path))
    if a.keys() != b.keys():
        print('the two snapshots cover different pages; recapture both')
        return 1
    changed_pages = collections.Counter()
    roots = collections.defaultdict(set)
    geometry = collections.Counter()
    for k in a:
        page = k.split('|')[0]
        A, B = a[k], b[k]
        if len(A['els']) != len(B['els']):
            print(f'{k}: element count changed {len(A["els"])} -> {len(B["els"])}; '
                  f'the markup differs, not just the CSS')
            changed_pages[page] += 1
            continue
        if A['h'] != B['h']:
            geometry[f'{page} @{k.split("|")[1]}px: page height {A["h"]} -> {B["h"]}'] += 1
        for ra, rb in zip(A['els'], B['els']):
            for p in set(ra) | set(rb):
                if ra.get(p) == rb.get(p):
                    continue
                changed_pages[page] += 1
                if p in CONSEQUENCE:
                    geometry[f'{page} | {p}'] += 1
                else:
                    roots[(p, str(ra.get(p)), str(rb.get(p)))].add(page)

    print('\nPages touched:')
    for pg, n in sorted(changed_pages.items()):
        print(f'  {pg}: {n} property differences')
    if not changed_pages:
        print('  none - the two states render identically')

    print(f'\nWhat you changed ({len(roots)} distinct):')
    for (p, va, vb), pgs in sorted(roots.items(), key=lambda kv: -len(kv[1])):
        print(f'  {p}: {va} -> {vb}')
        print(f'      {len(pgs)} pages: {sorted(pgs)[:5]}{" ..." if len(pgs) > 5 else ""}')
    if not roots:
        print('  nothing - colours, fonts and spacing are unchanged')

    print(f'\nWhat moved as a result ({sum(geometry.values())} differences):')
    for k, n in list(geometry.most_common(12)):
        print(f'  {k}  x{n}')
    if not geometry:
        print('  nothing - no reflow')
    return 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='+', help='output file, or two files with --diff')
    ap.add_argument('--diff', action='store_true')
    a = ap.parse_args()
    if a.diff:
        if len(a.paths) != 2:
            sys.exit('--diff needs exactly two snapshot files')
        sys.exit(diff(*a.paths))
    capture(a.paths[0])
