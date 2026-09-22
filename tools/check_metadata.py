#!/usr/bin/env python3
"""Titles, descriptions, canonicals, social tags, structured data, sitemap.

    python3 tools/check_metadata.py

Pure text and XML parsing, no browser, so it is fast enough to run on every
commit. Catches the things that quietly cost search traffic: a relative
canonical, a description that no longer matches the page, a page missing from
the sitemap, JSON-LD that does not parse.
"""
import collections
import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from audit_common import SITE, SKIP, pages, report  # noqa: E402

BASE = 'https://www.hwsbydanni.com/'
NS = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
TITLE_RANGE = (25, 65)      # what Google shows before truncating
DESC_RANGE = (110, 170)


def first(pattern, text, group=1):
    m = re.search(pattern, text, re.S | re.I)
    return m.group(group).strip() if m else None


def run():
    issues = []
    seen_titles, seen_descs = collections.defaultdict(list), collections.defaultdict(list)

    for f in pages():
        s = open(os.path.join(SITE, f), encoding='utf-8').read()
        expect = BASE + ('' if f == 'index.html' else f)

        title = first(r'<title>(.*?)</title>', s)
        desc = first(r'<meta name="description" content="(.*?)"', s)
        canon = first(r'<link rel="canonical" href="(.*?)"', s)
        og_url = first(r'<meta property="og:url" content="(.*?)"', s)
        robots = first(r'<meta name="robots" content="(.*?)"', s)

        if not title:
            issues.append(f'{f}: no <title>')
        elif not TITLE_RANGE[0] <= len(title) <= TITLE_RANGE[1]:
            issues.append(f'{f}: title is {len(title)} chars, want {TITLE_RANGE[0]}-{TITLE_RANGE[1]}')
        if not desc:
            issues.append(f'{f}: no meta description')
        elif not DESC_RANGE[0] <= len(desc) <= DESC_RANGE[1]:
            issues.append(f'{f}: description is {len(desc)} chars, want {DESC_RANGE[0]}-{DESC_RANGE[1]}')
        if canon != expect:
            issues.append(f'{f}: canonical is {canon!r}, expected {expect!r}')
        if og_url != expect:
            issues.append(f'{f}: og:url is {og_url!r}, expected {expect!r}')
        for tag, pat in [('og:title', r'og:title'), ('og:description', r'og:description'),
                         ('og:image', r'og:image"'), ('twitter:card', r'twitter:card')]:
            if not re.search(pat, s):
                issues.append(f'{f}: no {tag}')
        if robots and 'noindex' in robots:
            issues.append(f'{f}: NOINDEX is set')
        if first(r'<html lang="(.*?)"', s) != 'en':
            issues.append(f'{f}: missing or unexpected lang')
        if not re.search(r'name="viewport"', s):
            issues.append(f'{f}: no viewport meta')

        h1 = re.findall(r'<h1[^>]*>(.*?)</h1>', s, re.S)
        if len(h1) != 1:
            issues.append(f'{f}: {len(h1)} <h1> elements, want exactly 1')

        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S)
        if not blocks:
            issues.append(f'{f}: no structured data')
        for b in blocks:
            try:
                json.loads(b)
            except Exception as e:
                issues.append(f'{f}: JSON-LD does not parse: {e}')
        # JSON-LD inside a <script> is NOT entity-decoded, so "&amp;" and any
        # leftover tags end up in the published value verbatim.
        for bad in re.findall(r'"name":"([^"]*(?:<[a-z/]|&amp;)[^"]*)"', s):
            issues.append(f'{f}: markup or entity leaked into structured data: {bad!r}')

        for href in re.findall(r'href="([^"#?:/]+\.html)"', s):
            if not os.path.exists(os.path.join(SITE, href)):
                issues.append(f'{f}: link to missing page {href}')

        if title:
            seen_titles[title].append(f)
        if desc:
            seen_descs[desc].append(f)

    for t, fs in seen_titles.items():
        if len(fs) > 1:
            issues.append(f'duplicate title across {fs}: {t!r}')
    for d, fs in seen_descs.items():
        if len(fs) > 1:
            issues.append(f'duplicate description across {fs}')

    # --- sitemap -----------------------------------------------------------
    sm = os.path.join(SITE, 'sitemap.xml')
    if not os.path.exists(sm):
        issues.append('no sitemap.xml')
    else:
        try:
            root = ET.parse(sm).getroot()
        except ET.ParseError as e:
            issues.append(f'sitemap.xml does not parse: {e}')   # "--" inside an XML comment does this
        else:
            locs = [u.find(NS + 'loc').text for u in root]
            dupes = [l for l, n in collections.Counter(locs).items() if n > 1]
            if dupes:
                issues.append(f'sitemap has duplicate entries: {dupes}')
            for m in [u.find(NS + 'lastmod') for u in root]:
                if m is None or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', m.text or ''):
                    issues.append(f'sitemap lastmod is missing or malformed: {m is not None and m.text}')
            expected = {BASE + ('' if f == 'index.html' else f) for f in pages()}
            for missing in sorted(expected - set(locs)):
                issues.append(f'sitemap is missing {missing}')
            for stale in sorted(set(locs) - expected):
                issues.append(f'sitemap lists a page that does not exist: {stale}')

    return report(f'Metadata, links and sitemap ({len(pages())} pages'
                  f'{", " + ", ".join(sorted(SKIP)) + " skipped" if SKIP else ""})', issues)


if __name__ == '__main__':
    sys.exit(run())
