#!/usr/bin/env python3
"""Notify IndexNow search engines (Bing and others) of new or changed pages.

    python3 indexnow.py https://cozuya.github.io/proofs/example/ ...
    python3 indexnow.py --all     # every URL in the live sitemap

Run after the deployment is live: the engine fetches the key file from the site.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

ENDPOINT = 'https://api.indexnow.org/indexnow'
SITE = json.loads((Path(__file__).resolve().parent / 'content/site.json').read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('urls', nargs='*')
    parser.add_argument('--all', action='store_true', help='submit every URL in the live sitemap')
    args = parser.parse_args()
    base, key = SITE['url'], SITE['indexNowKey']
    urls = list(args.urls)
    if args.all:
        with urllib.request.urlopen(base + '/sitemap.xml', timeout=30) as response:
            urls += re.findall(r'<loc>([^<]+)</loc>', response.read().decode())
    if not urls or any(not u.startswith(base + '/') for u in urls):
        raise SystemExit(f'Give one or more URLs under {base}/, or --all')
    with urllib.request.urlopen(f'{base}/{key}.txt', timeout=30) as response:
        if response.read().decode().strip() != key:
            raise SystemExit('The live key file does not match content/site.json')
    body = json.dumps({'host': base.split('://', 1)[1], 'key': key,
                       'keyLocation': f'{base}/{key}.txt', 'urlList': urls}).encode()
    request = urllib.request.Request(ENDPOINT, data=body, method='POST',
                                     headers={'Content-Type': 'application/json; charset=utf-8'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            print(f'IndexNow HTTP {response.status} for {len(urls)} URL(s)')
    except urllib.error.HTTPError as error:
        print(f'IndexNow HTTP {error.code}: {error.read().decode(errors="replace")}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
