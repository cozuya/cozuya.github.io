#!/usr/bin/env python3
"""Build the static site into _site/ from content/. Python standard library only.

    python3 build.py            # build and validate
    python3 build.py --out DIR  # build somewhere else

Each mathematical result is one JSON file in content/proofs/ or
content/refutations/. Adding a result means adding one file; the index pages,
sitemap, and structured data are generated from it. Fields whose names end in
"Html" hold trusted HTML; every other string is plain text and is escaped.
"""
import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / 'content'
STATIC = ROOT / 'static'

SLUG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
DATE = re.compile(r'\d{4}-\d{2}-\d{2}')
HYPE = re.compile(r'\b(first[- ]ever|breakthrough|world[- ]first|groundbreaking|'
                  r'revolutionary|historic)\b', re.I)
# Wording that reports no earlier result was found. Forbidden when one is known.
NONE_FOUND = re.compile(r'did not (?:find|locate)|(?:found|located) no |no earlier', re.I)

TRUST_LABELS = {
    'lean-kernel': 'Lean, kernel-checked; standard axioms only',
    'lean-native-decide': 'Lean with native_decide; also trusts Lean’s compiler and runtime',
    'computation': 'Exact computation; not formally verified in Lean',
}
SECTIONS = {
    'proof': [
        ('statement', 'Statement', 'statementHtml'),
        ('scope', 'What is proved', 'scopeHtml'),
        ('proof', 'Proof outline', 'proofOutlineHtml'),
        ('verification', 'Verification and trust model', 'verificationHtml'),
        ('prior-art', 'Prior-art search', 'priorArtHtml'),
        ('provenance', 'Provenance', 'provenanceHtml'),
    ],
    'refutation': [
        ('claim', 'The claim', 'claimHtml'),
        ('counterexample', 'Counterexample', 'counterexampleHtml'),
        ('explanation', 'Why this falsifies the claim', 'explanationHtml'),
        ('verification', 'Verification', 'verificationHtml'),
        ('prior-art', 'Prior art and earlier refutations', 'priorArtHtml'),
        ('provenance', 'Provenance', 'provenanceHtml'),
    ],
}
REQUIRED = ['slug', 'publicationStatus', 'title', 'shortTitle', 'description', 'summary',
            'dateModified', 'problem', 'verification', 'priority', 'repository', 'links']


def fail(message):
    raise SystemExit('FAIL: ' + message)


def esc(text):
    return html.escape(str(text), quote=True)


def load_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as error:
        fail(f'{path.relative_to(ROOT)}: {error}')


def validate(record, kind, path):
    where = path.relative_to(ROOT).as_posix()
    for key in REQUIRED + [field for _, _, field in SECTIONS[kind]]:
        if not record.get(key):
            fail(f'{where}: missing {key}')
    if record['slug'] != path.stem or not SLUG.fullmatch(record['slug']):
        fail(f'{where}: slug must match the file name and be lowercase-hyphenated')
    if record['publicationStatus'] not in ('published', 'draft'):
        fail(f'{where}: publicationStatus must be "published" or "draft"')
    if not DATE.fullmatch(record['dateModified']):
        fail(f'{where}: dateModified must be YYYY-MM-DD')
    if record['verification'].get('trustModel') not in TRUST_LABELS:
        fail(f'{where}: verification.trustModel must be one of {sorted(TRUST_LABELS)}')
    for key in ('name', 'identifiers', 'sourceHtml'):
        if not record['problem'].get(key):
            fail(f'{where}: missing problem.{key}')
    priority = record['priority']
    if not isinstance(priority.get('priorResolutionKnown'), bool) or not priority.get('statement'):
        fail(f'{where}: priority needs priorResolutionKnown (true/false) and statement')
    text = json.dumps(record, ensure_ascii=False)
    if HYPE.search(text):
        fail(f'{where}: promotional wording "{HYPE.search(text).group(0)}"')
    if priority['priorResolutionKnown']:
        if not priority.get('earlier'):
            fail(f'{where}: priorResolutionKnown is true, so list the earlier results')
        if NONE_FOUND.search(text):
            fail(f'{where}: says no earlier result was found, but one is known')
    for group in record['links']:
        for item in group['items']:
            if not item.get('label') or not item.get('url', '').startswith('https://'):
                fail(f'{where}: links need a label and an https URL')


def load_collection(name, kind):
    records = []
    for path in sorted((CONTENT / name).glob('*.json')):
        record = load_json(path)
        validate(record, kind, path)
        if record['publicationStatus'] == 'published':
            records.append(record)
    return sorted(records, key=lambda r: (r.get('order', 1000), r['shortTitle']))


def json_ld(data):
    return json.dumps(data, ensure_ascii=False, indent=1).replace('</', '<\\/')


def page(site, path, title, description, body, data, section=None, og_type='website'):
    url = site['url'] + path
    canonical = '' if path == '/404.html' else f'<link rel="canonical" href="{esc(url)}">'
    current = ' aria-current="page"'
    nav = ''.join(
        f'<li><a href="/{key}/"{current if key == section else ""}>'
        f'{esc(value["navLabel"])}</a></li>' for key, value in site['collections'].items())
    footer_links = ' · '.join(f'<a href="{esc(link["url"])}">{esc(link["label"])}</a>'
                              for link in site['footerLinks'])
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
{canonical}
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="{esc(site['name'])}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(url)}">
<link rel="stylesheet" href="/style.css">
<script type="application/ld+json">
{json_ld(data)}
</script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site">
<nav aria-label="Site"><a class="home" href="/">{esc(site['name'])}</a><ul>{nav}</ul></nav>
</header>
<main id="main">
{body}
</main>
<footer class="site"><p>{esc(site['name'])} · {footer_links}</p></footer>
</body>
</html>
'''


def person(site):
    return {'@type': 'Person', '@id': site['url'] + '/#person', 'name': site['name'],
            'jobTitle': site['jobTitle'], 'url': site['url'] + '/', 'sameAs': site['sameAs']}


def breadcrumbs(site, trail):
    return {'@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': i, 'name': name, 'item': site['url'] + path}
        for i, (name, path) in enumerate(trail, 1)]}


def breadcrumb_nav(trail):
    items = ''.join(f'<li><a href="{esc(path)}">{esc(name)}</a></li>' for name, path in trail[:-1])
    return (f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{items}'
            f'<li aria-current="page">{esc(trail[-1][0])}</li></ol></nav>')


def render_home(site, collections):
    cards = ''.join(f'''
<section class="collection">
<h3><a href="/{key}/">{esc(value['navLabel'])}</a></h3>
<p>{esc(value['blurb'])}</p>
<p><a href="/{key}/">View {esc(value['navLabel'].lower())}</a></p>
</section>''' for key, value in site['collections'].items())
    body = f'''<h1>{esc(site['name'])}</h1>
<p class="lede">{esc(site['jobTitle'])}.</p>
{site['homeIntroHtml']}
<h2>Recent mathematical work</h2>
{cards}'''
    data = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'WebSite', '@id': site['url'] + '/#website', 'url': site['url'] + '/',
         'name': site['name'], 'inLanguage': 'en'},
        {'@type': 'ProfilePage', 'url': site['url'] + '/', 'name': site['name'],
         'description': site['description'], 'mainEntity': {'@id': site['url'] + '/#person'}},
        person(site)]}
    return page(site, '/', site['name'], site['description'], body, data)


def render_index(site, key, records):
    meta = site['collections'][key]
    path = f'/{key}/'
    trail = [('Home', '/'), (meta['navLabel'], path)]
    entries = ''.join(f'''
<article class="entry">
<h2><a href="{path}{esc(r['slug'])}/">{esc(r['shortTitle'])}</a></h2>
<p class="ident">{esc(' · '.join(r['problem']['identifiers']))}</p>
<p>{esc(r['summary'])}</p>
<p class="trust"><strong>Verification:</strong> {esc(TRUST_LABELS[r['verification']['trustModel']])}.
{esc(r['verification'].get('summary', ''))}</p>
<p class="entry-links"><a href="{path}{esc(r['slug'])}/">Details and verification</a> ·
<a href="{esc(r['repository']['url'])}">GitHub repository</a></p>
</article>''' for r in records)
    if not records:
        entries = f'<p class="empty">{esc(meta["empty"])}</p>'
    body = f'''{breadcrumb_nav(trail)}
<h1>{esc(meta['heading'])}</h1>
{meta['introHtml']}
{entries}'''
    data = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'CollectionPage', 'url': site['url'] + path, 'name': meta['title'],
         'description': meta['description'], 'inLanguage': 'en',
         'isPartOf': {'@id': site['url'] + '/#website'}, 'author': {'@id': site['url'] + '/#person'},
         'mainEntity': {'@type': 'ItemList', 'numberOfItems': len(records), 'itemListElement': [
             {'@type': 'ListItem', 'position': i, 'url': f'{site["url"]}{path}{r["slug"]}/',
              'name': r['shortTitle']} for i, r in enumerate(records, 1)]}},
        breadcrumbs(site, trail), person(site)]}
    return page(site, path, meta['title'], meta['description'], body, data, section=key)


def render_detail(site, key, kind, r):
    meta = site['collections'][key]
    path = f'/{key}/{r["slug"]}/'
    trail = [('Home', '/'), (meta['navLabel'], f'/{key}/'), (r['shortTitle'], path)]
    problem, priority = r['problem'], r['priority']
    earlier = ''
    if priority.get('earlier'):
        earlier = '<ul>' + ''.join(f'<li><a href="{esc(e["url"])}">{esc(e["label"])}</a></li>'
                                   for e in priority['earlier']) + '</ul>'
    warning = f'<div class="warning" role="note">{r["scopeWarningHtml"]}</div>' \
        if r.get('scopeWarningHtml') else ''
    facts = [
        ('Original problem', esc(problem['name'])),
        ('Identifiers', esc(' · '.join(problem['identifiers']))),
        ('Source', problem['sourceHtml']),
        ('Result', esc(r['summary'])),
        ('Verification', esc(TRUST_LABELS[r['verification']['trustModel']]) + '. '
         + esc(r['verification'].get('summary', ''))),
        ('Repository', f'<a href="{esc(r["repository"]["url"])}">{esc(r["repository"]["url"])}</a>'),
    ]
    if problem.get('alternateNames'):
        facts.insert(1, ('Also known as', esc('; '.join(problem['alternateNames']))))
    fact_list = ''.join(f'<dt>{name}</dt><dd>{value}</dd>' for name, value in facts)
    sections = ''.join(f'<section id="{sid}"><h2>{esc(heading)}</h2>\n{r[field]}\n</section>\n'
                       for sid, heading, field in SECTIONS[kind])
    links = ''.join(
        f'<h3>{esc(group["group"])}</h3><ul>'
        + ''.join(f'<li><a href="{esc(i["url"])}">{esc(i["label"])}</a></li>' for i in group['items'])
        + '</ul>' for group in r['links'])
    body = f'''{breadcrumb_nav(trail)}
<article>
<h1>{esc(r['title'])}</h1>
<p class="lede">{esc(r['summary'])}</p>
{warning}
<div class="notice" role="note"><p><strong>Priority:</strong> {esc(priority['statement'])}</p>{earlier}</div>
<dl class="facts">{fact_list}</dl>
{sections}
<section id="links"><h2>Sources, verification, and records</h2>
{links}
</section>
</article>'''
    article = {
        '@type': 'TechArticle', '@id': site['url'] + path + '#article', 'url': site['url'] + path,
        'headline': r['title'], 'name': r['title'], 'description': r['description'],
        'abstract': r['summary'], 'inLanguage': 'en', 'dateModified': r['dateModified'],
        'author': {'@id': site['url'] + '/#person'},
        'isPartOf': {'@type': 'CollectionPage', 'url': f'{site["url"]}/{key}/'},
        'about': {'@type': 'Thing', 'name': problem['name'],
                  'alternateName': problem.get('alternateNames', []),
                  'identifier': problem['identifiers']},
        'keywords': ', '.join(r.get('keywords', [])),
        'isBasedOn': {'@type': 'SoftwareSourceCode', 'name': r['repository'].get('name', r['shortTitle']),
                      'codeRepository': r['repository']['url'],
                      'programmingLanguage': r['repository'].get('programmingLanguage')},
    }
    if problem.get('citations'):
        article['citation'] = problem['citations']
    data = {'@context': 'https://schema.org', '@graph': [article, breadcrumbs(site, trail), person(site)]}
    return page(site, path, r['title'], r['description'], body, data, section=key, og_type='article')


def render_404(site):
    body = '<h1>Page not found</h1>\n<p>Try the <a href="/">home page</a>.</p>'
    text = page(site, '/404.html', 'Page not found', 'Page not found.', body,
                {'@context': 'https://schema.org', '@type': 'WebPage', 'name': 'Page not found'})
    return text.replace('<meta name="viewport"', '<meta name="robots" content="noindex">\n<meta name="viewport"', 1)


def check_links(out):
    """Every root-relative link must resolve to a generated file."""
    for page_path in out.rglob('*.html'):
        for target in re.findall(r'(?:href|src)="(/[^"#?]*)', page_path.read_text(encoding='utf-8')):
            file = out / target.lstrip('/')
            if file.is_dir():
                file = file / 'index.html'
            if not file.is_file():
                fail(f'broken internal link {target} in {page_path.relative_to(out)}')


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', type=Path, default=ROOT / '_site')
    out = parser.parse_args().out.resolve()
    site = load_json(CONTENT / 'site.json')
    kinds = {key: value['kind'] for key, value in site['collections'].items()}
    collections = {key: load_collection(key, kind) for key, kind in kinds.items()}

    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(STATIC, out)
    pages = {'/': (render_home(site, collections), site['dateModified'])}
    for key, records in collections.items():
        updated = max([site['dateModified']] + [r['dateModified'] for r in records])
        pages[f'/{key}/'] = (render_index(site, key, records), updated)
        for r in records:
            pages[f'/{key}/{r["slug"]}/'] = (render_detail(site, key, kinds[key], r), r['dateModified'])
    for path, (text, _) in pages.items():
        target = out / path.lstrip('/') / 'index.html'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')
    (out / '404.html').write_text(render_404(site), encoding='utf-8')

    urls = ''.join(f'  <url><loc>{esc(site["url"] + path)}</loc><lastmod>{date}</lastmod></url>\n'
                   for path, (_, date) in pages.items())
    (out / 'sitemap.xml').write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + '</urlset>\n',
        encoding='utf-8')
    (out / 'robots.txt').write_text(
        f'User-agent: *\nAllow: /\n\nSitemap: {site["url"]}/sitemap.xml\n', encoding='utf-8')
    if site.get('indexNowKey'):
        (out / f'{site["indexNowKey"]}.txt').write_text(site['indexNowKey'], encoding='utf-8')
    (out / '.nojekyll').write_text('', encoding='utf-8')

    check_links(out)
    counts = ', '.join(f'{len(v)} {k}' for k, v in collections.items())
    print(f'PASS: built {len(pages)} pages ({counts}) into {out}')


if __name__ == '__main__':
    sys.exit(main())
