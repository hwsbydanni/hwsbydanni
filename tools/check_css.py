#!/usr/bin/env python3
"""Keep home.css an override layer, not a second copy of styles.css.

    python3 tools/check_css.py

index.html loads styles.css and then home.css. That ordering makes two
mistakes easy, and the site has made both:

  DUPLICATE   A rule in home.css identical to one in styles.css. Harmless
              until someone fixes the shared one and the homepage silently
              keeps the old value. That happened twice: the mobile nav
              panel's max-height, and .btn-text.on-light's colour.

  ORDERING    A rule in home.css with no media query, matching a selector
              that styles.css only sets inside one. Because home.css loads
              second, the unconditional value wins and the media query never
              applies. That is how .pain-row lost its mobile two-column
              layout.

Anything home.css genuinely needs to override is fine; it just has to differ
from styles.css, and it has to carry the same media query if there is one.
"""
import os
import re
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from audit_common import SITE, report  # noqa: E402

BASE_SHEET = 'styles.css'
OVERRIDE_SHEET = 'home.css'


def parse(path):
    """-> [(media, selector, {prop: value})], in source order.

    Small enough for these two files: no @supports nesting, no calc() with
    braces, no CSS nesting syntax. It is a lint, not a compiler.
    """
    text = re.sub(r'/\*.*?\*/', '', open(path, encoding='utf-8').read(), flags=re.S)
    rules, i, media, stack, buf = [], 0, '', [], ''
    while i < len(text):
        c = text[i]
        if c == '{':
            head, buf = buf.strip(), ''
            if head.startswith('@'):
                stack.append(media)
                media = (media + ' ' + head).strip()
            else:
                depth, j = 1, i + 1
                while j < len(text) and depth:
                    depth += (text[j] == '{') - (text[j] == '}')
                    j += 1
                decls = {}
                for d in text[i + 1:j - 1].split(';'):
                    if ':' in d:
                        k, v = d.split(':', 1)
                        decls[k.strip()] = ' '.join(v.split())
                for sel in head.split(','):
                    sel = ' '.join(sel.split())
                    if sel:
                        rules.append((media, sel, decls))
                i = j - 1
        elif c == '}':
            if stack:
                media = stack.pop()
            buf = ''
        else:
            buf += c
        i += 1
    return rules


def run():
    base_path = os.path.join(SITE, BASE_SHEET)
    over_path = os.path.join(SITE, OVERRIDE_SHEET)
    if not os.path.exists(over_path):
        print(f'{OVERRIDE_SHEET} not present; nothing to check')
        return 0

    base, over = parse(base_path), parse(over_path)
    shared, in_media = {}, {}
    for m, s, d in base:
        shared.setdefault((m, s), {}).update(d)
        if m:
            in_media.setdefault(s, []).append((m, d))

    duplicates, ordering = [], []
    for m, s, d in over:
        key = (m, s)
        if key in shared and all(shared[key].get(k) == v for k, v in d.items()):
            duplicates.append(f'{("@" + m + " ") if m else ""}{s}  is identical to {BASE_SHEET}; delete it')
        if not m:
            for mq, dd in in_media.get(s, []):
                for k in sorted(set(d) & set(dd)):
                    ordering.append(
                        f'{s} sets {k}: {d[k]!r} with no media query, so it beats '
                        f'{BASE_SHEET} {mq} which sets {dd[k]!r}')

    bad = report(f'{OVERRIDE_SHEET} rules duplicating {BASE_SHEET}', duplicates)
    bad |= report(f'{OVERRIDE_SHEET} rules outranking a {BASE_SHEET} media query', ordering)
    return bad


if __name__ == '__main__':
    sys.exit(run())
