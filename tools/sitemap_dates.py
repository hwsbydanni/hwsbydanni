#!/usr/bin/env python3
"""Work out what each page's sitemap lastmod should be.

    python3 tools/sitemap_dates.py            # compare against sitemap.xml
    python3 tools/sitemap_dates.py --all      # show every page, not just drift

lastmod is meant to be the date a page's CONTENT last changed. The raw git
date is not that: a nav rebuild or an added analytics snippet touches all 22
files at once, and dating every page to the same day tells Google the whole
site was rewritten, after which it stops trusting lastmod on the domain.

So this walks each page's history newest-first and stops at the first commit
that still changes the page once <head>, <header>, <footer>, comments and
<script> blocks are stripped out. That is the first commit that changed what a
reader would see as this page rather than as the site.

It only reports. Edit sitemap.xml yourself, so the judgement stays visible.
"""
import argparse
import os
import re
import signal
import subprocess
import sys

try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):
    pass
import xml.etree.ElementTree as ET

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from audit_common import SITE, pages  # noqa: E402

BASE = 'https://www.hwsbydanni.com/'
NS = '{http://www.sitemaps.org/schemas/sitemap/0.9}'


def git(*args):
    return subprocess.run(['git', '-C', SITE, *args], capture_output=True, text=True).stdout


def content_only(html):
    """What a reader would see as THIS page, rather than as the site.

    Kept: the body, plus <title> and the meta description. Those two are the
    strings a search result shows, so changing them is worth a recrawl even
    though nothing on the page moved.

    Dropped: the rest of <head>, the shared header and footer, scripts,
    comments, and style="..." attributes. Recolouring a heading is a styling
    change like any other and no more worth a recrawl than editing styles.css.
    """
    keep = []
    m = re.search(r'<title>(.*?)</title>', html, re.S | re.I)
    if m:
        keep.append(m.group(1))
    m = re.search(r'<meta name="description" content="(.*?)"', html, re.S | re.I)
    if m:
        keep.append(m.group(1))
    for pattern in (r'<head>.*?</head>', r'<header>.*?</header>', r'<footer.*?</footer>',
                    r'<script.*?</script>', r'<!--.*?-->', r'\sstyle="[^"]*"'):
        html = re.sub(pattern, '', html, flags=re.S)
    return ' '.join((' '.join(keep) + ' ' + html).split())


def content_date(page):
    for line in git('log', '--format=%H %ad', '--date=short', '--', page).strip().splitlines():
        sha, date = line.split(' ', 1)
        now = git('show', f'{sha}:{page}')
        prev = git('show', f'{sha}^:{page}')
        if not prev:
            return date, 'page created'
        if content_only(now) != content_only(prev):
            return date, sha[:7]
    return None, 'no history'


def run(show_all):
    current = {}
    sm = os.path.join(SITE, 'sitemap.xml')
    if os.path.exists(sm):
        try:
            for u in ET.parse(sm).getroot():
                current[u.find(NS + 'loc').text] = u.find(NS + 'lastmod').text
        except ET.ParseError as e:
            print(f'sitemap.xml does not parse ({e}); showing computed dates only\n')

    drift = 0
    print(f'{"page":24} {"in sitemap":12} {"content date":12}  reason')
    for f in pages():
        loc = BASE + ('' if f == 'index.html' else f)
        have = current.get(loc, '(absent)')
        want, why = content_date(f)
        differs = want and have != want
        if differs:
            drift += 1
        if differs or show_all:
            print(f'{f:24} {have:12} {want or "?":12}  {why}'
                  f'{"   <-- update" if differs else ""}')
    print(f'\n{drift} page(s) to update' if drift else '\nsitemap dates match the content history')
    return 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true', help='list every page, not just the drift')
    sys.exit(run(ap.parse_args().all))
