#!/usr/bin/env python3
"""qa_image_audit.py — image rendering evidence collector.

Queries the production API for image-bearing questions, then HEAD-checks
every file_url. Reports HTTP status + content-type + file size so we
can tell apart: missing files (404), wrong content-type (text/html on
an image URL), and actual broken images (200 but 0 bytes).
"""
import json
import sys
import urllib.request
import urllib.error

API_BASE = 'https://crackcms-vsthc.ondigitalocean.app'

def fetch_json(path):
    with urllib.request.urlopen(API_BASE + path, timeout=30) as resp:
        return json.loads(resp.read())

def head(url):
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.headers.get('Content-Type', ''), resp.headers.get('Content-Length', '?')
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get('Content-Type', '') if e.headers else '', '?'
    except Exception as e:
        return 0, repr(e)[:60], '?'

def main():
    # 1) Sample image-bearing questions
    qdata = fetch_json('/api/questions/?is_image_based=true&page_size=20')
    questions = qdata.get('results', [])
    print(f'Total image-bearing questions: {qdata.get("count", "?")}')
    print(f'Sampled: {len(questions)}')
    print()

    rows = []
    for q in questions[:10]:
        qid = q['id']
        imgs = fetch_json(f'/api/questions/{qid}/images/')
        if not imgs:
            rows.append((qid, 0, 'no images'))
            continue
        for img in imgs[:2]:
            status, ctype, clen = head(img['file_url'])
            label = 'OK' if status == 200 and 'image' in ctype else (
                '404' if status == 404 else f'STATUS{status}')
            rows.append((qid, img['id'], label, img['file_url'].split('/')[-1], status, ctype, clen))

    print(f'{"qid":>6}  {"imgid":>6}  {"verdict":<10}  {"status":>6}  {"ctype":<22}  {"size":>6}  filename')
    for r in rows:
        if len(r) == 3:
            print(f'{r[0]:>6}  {"-":>6}  {r[2]:<10}')
            continue
        qid, imgid, verdict, fname, status, ctype, clen = r
        print(f'{qid:>6}  {imgid:>6}  {verdict:<10}  {status:>6}  {ctype:<22}  {clen:>6}  {fname}')

if __name__ == '__main__':
    main()