#!/usr/bin/env python3
"""Pull the service photos from Acuity into images/services/.

    python3 tools/fetch_service_photos.py            # download what is missing
    python3 tools/fetch_service_photos.py --force    # re-download everything
    python3 tools/fetch_service_photos.py --check    # report, download nothing

Every service row on a category page can show the photo Danni already
uploaded to that appointment type in Acuity. The pages reference
images/services/<appointment type id>.jpg; this fetches those files.

Run it whenever the photos change in Acuity. The site does not hotlink
Acuity's CDN: those URLs carry a cache-busting timestamp that changes on
every edit, Acuity can move them, and they would stop working the day the
studio moves off Acuity. Local files also let us resize and recompress.

If an image is missing at page load the row simply shows no photo (motion.js
drops the figure), so the site is never broken by a file that has not been
fetched yet.

WHICH PHOTOS
------------
tools/service-photos.json lists them, keyed by appointment type id. It is
committed, so this script needs no credentials to do its job.

To rebuild that list after adding photos in Acuity, set credentials from
Acuity's "Integrations -> API" page and pass --refresh-manifest:

    export ACUITY_USER_ID=...  ACUITY_API_KEY=...
    python3 tools/fetch_service_photos.py --refresh-manifest
"""
import argparse
import base64
import io
import json
import os
import re
import signal
import sys
import urllib.request

try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):
    pass

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from audit_common import SITE  # noqa: E402

MANIFEST = os.path.join(SITE, 'tools', 'service-photos.json')
OUT_DIR = os.path.join(SITE, 'images', 'services')
API = 'https://acuityscheduling.com/api/v1/appointment-types'
CATEGORY_PAGES = ['bridal.html', 'extensions.html', 'lace-installs.html', 'maintenance.html',
                  'natural-hair.html', 'quick-weave.html', 'traveling.html', 'wigs.html']

# Stored at 2x the widest the layout ever shows them, so they stay sharp on a
# phone without carrying a full-resolution upload around.
MAX_WIDTH = 800
QUALITY = 82


def load_manifest():
    if not os.path.exists(MANIFEST):
        sys.exit(f'{MANIFEST} not found. Run with --refresh-manifest and Acuity credentials.')
    return json.load(open(MANIFEST, encoding='utf-8'))['photos']


def refresh_manifest():
    user, key = os.environ.get('ACUITY_USER_ID'), os.environ.get('ACUITY_API_KEY')
    if not (user and key):
        sys.exit('set ACUITY_USER_ID and ACUITY_API_KEY (Acuity: Integrations -> API)')
    auth = base64.b64encode(f'{user}:{key}'.encode()).decode()
    req = urllib.request.Request(API, headers={'Authorization': f'Basic {auth}'})
    types = json.load(urllib.request.urlopen(req, timeout=60))
    by_id = {str(t['id']): t for t in types}

    # Only the services actually linked from a category page.
    linked = {}
    for page in CATEGORY_PAGES:
        path = os.path.join(SITE, page)
        if not os.path.exists(path):
            continue
        for i in re.findall(r'appointmentType=(\d+)', open(path, encoding='utf-8').read()):
            t = by_id.get(i)
            if t and t.get('image'):
                e = linked.setdefault(i, {'name': t['name'].strip(),
                                          'category': (t.get('category') or '').strip(),
                                          'image': t['image'], 'pages': []})
                if page not in e['pages']:
                    e['pages'].append(page)
    for e in linked.values():
        e['pages'].sort()
    json.dump({'_note': json.load(open(MANIFEST, encoding='utf-8'))['_note'],
               'photos': dict(sorted(linked.items(), key=lambda kv: int(kv[0])))},
              open(MANIFEST, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print(f'{MANIFEST}: {len(linked)} services with a photo')
    return linked


def save(raw, dest):
    """Normalise to a reasonably sized JPEG. Falls back to the bytes as sent."""
    try:
        from PIL import Image
    except ImportError:
        open(dest, 'wb').write(raw)
        return 'saved unchanged (install Pillow to resize)'
    im = Image.open(io.BytesIO(raw))
    im = im.convert('RGB') if im.mode in ('RGBA', 'LA', 'P') else im.convert('RGB')
    before = im.size
    if im.width > MAX_WIDTH:
        im = im.resize((MAX_WIDTH, round(im.height * MAX_WIDTH / im.width)), Image.LANCZOS)
    im.save(dest, 'JPEG', quality=QUALITY, optimize=True, progressive=True)
    return f'{before[0]}x{before[1]} -> {im.width}x{im.height}, {os.path.getsize(dest) // 1024} KB'


def run(force, check_only, refresh):
    photos = refresh_manifest() if refresh else load_manifest()
    os.makedirs(OUT_DIR, exist_ok=True)

    have = [i for i in photos if os.path.exists(os.path.join(OUT_DIR, f'{i}.jpg'))]
    todo = [i for i in photos if force or i not in have]
    print(f'{len(photos)} services with a photo; {len(have)} already in images/services/')
    if check_only:
        for i in sorted(set(photos) - set(have), key=int):
            print(f'  missing  {i}.jpg  {photos[i]["name"]}')
        return 0 if len(have) == len(photos) else 1
    if not todo:
        print('nothing to fetch')
        return 0

    failed = []
    for n, i in enumerate(sorted(todo, key=int), 1):
        meta, dest = photos[i], os.path.join(OUT_DIR, f'{i}.jpg')
        try:
            with urllib.request.urlopen(meta['image'], timeout=60) as r:
                raw = r.read()
            note = save(raw, dest)
            print(f'  [{n}/{len(todo)}] {i}.jpg  {meta["name"][:34]:34} {note}')
        except Exception as e:
            failed.append((i, meta['name'], e))
            print(f'  [{n}/{len(todo)}] {i}.jpg  FAILED: {e}')

    if failed:
        print(f'\n{len(failed)} failed. The pages skip a missing photo, so the site '
              f'still renders; re-run to retry.')
    else:
        print(f'\nfetched {len(todo)}. Commit images/services/.')
    return 1 if failed else 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true', help='re-download files already present')
    ap.add_argument('--check', action='store_true', help='report what is missing, download nothing')
    ap.add_argument('--refresh-manifest', action='store_true',
                    help='rebuild service-photos.json from Acuity (needs credentials)')
    a = ap.parse_args()
    sys.exit(run(a.force, a.check, a.refresh_manifest))
