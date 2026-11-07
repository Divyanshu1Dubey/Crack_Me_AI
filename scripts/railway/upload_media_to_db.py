"""Stage media files in the production database so the server can write them onto its volume.

Railway volumes cannot be uploaded to from outside. Run this on the machine that has the files; the
next deploy's release step (``manage.py restore_media_transfer``) writes them onto the volume.

    python scripts/railway/upload_media_to_db.py --database-url "$DATABASE_URL" \
        --media backend/media --mirror C:/path/to/storage-mirror --only-referenced --workers 6

--only-referenced stages exactly the files the database points at (QuestionImage.file, /media/...
addresses in QuestionImage.url, Question.page_screenshot, /media/... paths inside question text, and
Supabase Storage URLs of QuestionImage.url mapped onto the mirror), instead of whole folders.
--rel-prefix imported/ (repeatable) keeps only paths under that prefix; --dry-run counts and writes
nothing. Resumable: a file already staged with the same SHA-256 is skipped. Prints counts only (never
the URL). The image endpoint writes a staged file to disk on its first request
(questions/media_restore.py); container start writes all of them (start_web.sh).
After images work in production: ``python manage.py restore_media_transfer --drop``.

2026-11-07: /media/ addresses in QuestionImage.url were not staged, so the 126 figures of the July 2026
material imports (/media/imported/...) never reached the production volume.
"""
import argparse
import hashlib
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg

DDL = """
CREATE TABLE IF NOT EXISTS ops_media_transfer (
    id bigserial PRIMARY KEY,
    target text NOT NULL CHECK (target IN ('media', 'mirror')),
    rel_path text NOT NULL,
    sha256 char(64) NOT NULL,
    size bigint NOT NULL,
    data bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (target, rel_path)
)
"""
SUPABASE_PUBLIC = re.compile(r'^https://[^/]+\.supabase\.co/storage/v1/object/public/(.+)$')
MEDIA_IN_TEXT = re.compile(r'/media/([A-Za-z0-9_./-]+\.(?:png|jpe?g|gif|webp|svg|mp4|webm))', re.I)


def media_rel(url: str) -> str:
    """``/media/a/b.png?v=2`` -> ``a/b.png`` (the key the image endpoint restores, questions/views.py)."""
    return url.split('?', 1)[0][len('/media/'):]


def keep(rel: str, prefixes) -> bool:
    return not prefixes or any(rel.startswith(p) for p in prefixes)


def files_under(root: Path, subdirs):
    for sub in subdirs:
        base = root / sub
        if not base.is_dir():
            print(f'  (missing: {base})', file=sys.stderr)
            continue
        for path in sorted(base.rglob('*')):
            if path.is_file() and not path.name.endswith(('.part', '.tmp')):
                yield path.relative_to(root).as_posix(), path


def referenced(conn, media_root, mirror_root, prefixes=()):
    """(target, rel_path, local path) for every file the database points at and that exists locally
    (only paths under ``prefixes`` when given)."""
    out, missing = {}, 0
    rels = set()
    for (name,) in conn.execute("SELECT file FROM questions_questionimage WHERE file <> ''"):
        rels.add(name)
    for (url,) in conn.execute("SELECT url FROM questions_questionimage WHERE url LIKE '/media/%%'"):
        rels.add(media_rel(url))
    for (name,) in conn.execute("SELECT page_screenshot FROM questions_question WHERE page_screenshot <> ''"):
        rels.add(name)
    for row in conn.execute("SELECT question_text, option_a, option_b, option_c, option_d, explanation "
                            "FROM questions_question WHERE concat(question_text, option_a, option_b, option_c, option_d, explanation) LIKE '%%/media/%%'"):
        for text in row:
            rels.update(MEDIA_IN_TEXT.findall(text or ''))
    if media_root:
        for rel in sorted(r for r in rels if r and keep(r, prefixes)):
            p = media_root / rel
            if p.is_file():
                out[('media', rel)] = p
            else:
                missing += 1
    if mirror_root:
        for (url,) in conn.execute("SELECT url FROM questions_questionimage WHERE url LIKE 'https://%%supabase.co/storage/v1/object/public/%%'"):
            m = SUPABASE_PUBLIC.match(url.split('?', 1)[0])
            if not m:
                continue
            rel = m.group(1)
            if not keep(rel, prefixes):
                continue
            p = mirror_root / rel
            if p.is_file():
                out[('mirror', rel)] = p
            else:
                missing += 1
    return [(t, r, p) for (t, r), p in sorted(out.items())], missing


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--database-url', required=True)
    ap.add_argument('--media', type=Path)
    ap.add_argument('--media-subdirs', nargs='*', default=['recall_images', 'mocktest_assets'])
    ap.add_argument('--mirror', type=Path)
    ap.add_argument('--mirror-subdirs', nargs='*', default=['crack-cms-question-images'])
    ap.add_argument('--only-referenced', action='store_true')
    ap.add_argument('--rel-prefix', action='append', default=[],
                    help='stage only paths starting with this prefix, e.g. imported/ (repeatable)')
    ap.add_argument('--dry-run', action='store_true', help='count what would be staged; write nothing')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--max-file-mb', type=float, default=200)
    a = ap.parse_args(argv)
    with psycopg.connect(a.database_url, connect_timeout=30, autocommit=True) as conn:
        if a.dry_run:
            exists = conn.execute("SELECT to_regclass('public.ops_media_transfer')").fetchone()[0] is not None
        else:
            conn.execute(DDL)
            exists = True
        have = ({(t, r): s for t, r, s in conn.execute('SELECT target, rel_path, sha256 FROM ops_media_transfer')}
                if exists else {})
        if a.only_referenced:
            plan, missing = referenced(conn, a.media, a.mirror, a.rel_prefix)
            print(f'referenced files found locally: {len(plan)}; referenced but missing locally: {missing}')
        else:
            plan = []
            if a.media:
                plan += [('media', rel, p) for rel, p in files_under(a.media, a.media_subdirs)]
            if a.mirror:
                plan += [('mirror', rel, p) for rel, p in files_under(a.mirror, a.mirror_subdirs)]
            plan = [item for item in plan if keep(item[1], a.rel_prefix)]
    todo = []
    for target, rel, path in plan:
        size = path.stat().st_size
        if size > a.max_file_mb * 1e6:
            continue
        todo.append((target, rel, path, size))
    print(f'{len(todo)} files, {sum(t[3] for t in todo) / 1e6:.0f} MB to check; {len(have)} already staged', flush=True)
    if a.dry_run:
        new = sum(1 for target, rel, _, _ in todo if (target, rel) not in have)
        print(f'dry run: {new} not staged yet, {len(todo) - new} staged before (re-sent only if changed); nothing written')
        return

    local = threading.local()
    lock = threading.Lock()
    stats = {'sent': 0, 'skipped': 0, 'bytes': 0, 'failed': 0}

    def conn_for_thread():
        if getattr(local, 'conn', None) is None:
            local.conn = psycopg.connect(a.database_url, connect_timeout=30, autocommit=True)
        return local.conn

    def send(item):
        target, rel, path, size = item
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if have.get((target, rel)) == sha:
            with lock:
                stats['skipped'] += 1
            return
        for attempt in range(3):
            try:
                conn_for_thread().execute(
                    'INSERT INTO ops_media_transfer (target, rel_path, sha256, size, data) VALUES (%s, %s, %s, %s, %s) '
                    'ON CONFLICT (target, rel_path) DO UPDATE SET sha256 = EXCLUDED.sha256, size = EXCLUDED.size, '
                    'data = EXCLUDED.data, created_at = now()', (target, rel, sha, size, data))
                break
            except psycopg.OperationalError:
                local.conn = None
                if attempt == 2:
                    with lock:
                        stats['failed'] += 1
                    return
        with lock:
            stats['sent'] += 1
            stats['bytes'] += size
            if stats['sent'] % 250 == 0:
                print(f"  {stats['sent']} uploaded ({stats['bytes'] / 1e6:.0f} MB)", flush=True)

    with ThreadPoolExecutor(max_workers=max(1, a.workers)) as pool:
        list(pool.map(send, todo))
    with psycopg.connect(a.database_url, connect_timeout=30) as conn:
        n, mb = conn.execute('SELECT count(*), coalesce(sum(size), 0) / 1e6 FROM ops_media_transfer').fetchone()
    print(f"uploaded {stats['sent']} ({stats['bytes'] / 1e6:.0f} MB), unchanged {stats['skipped']}, failed {stats['failed']}; "
          f'staged in total: {n} files, {mb:.0f} MB')


if __name__ == '__main__':
    main()
