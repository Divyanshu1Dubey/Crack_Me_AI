# Display-Number Backfill — Prod Runbook (2026-07-25)

**Bug:** Bug #9 — NEET PG 2021 questions had `display_number = NULL` for
all 329 rows (the field was added to the schema but never populated).
The player UI shows the question ordinal, so NULL renders as "Q  / 367"
in the chrome.

**Status:** Script committed (`backend/backfill_display_number.py`,
commit `638be9a`). Local DB touched 4,489 rows. Prod DB still has 0
rows with `display_number` populated because the DigitalOcean
container never ran the script.

**Goal:** Populate `display_number = 1..N` per `(exam_type, year)`,
ordered by `id` ASC, on the prod DB.

---

## Approach Decision

There are two paths. Pick **option A** unless the answer to question 1
is "no" — option A is safer because it does not require a fixture
re-export.

### Option A — Run the script on the prod container (preferred)

The script is idempotent: it only writes rows where `display_number`
IS NULL. After it runs, the data is correct in-place and no other
deploy step is required.

Steps:

1. SSH / exec into the DigitalOcean App Platform container running
   the Django app. The container shell is reachable from the
   DigitalOcean dashboard (`Apps → crackcms → Console`).
2. Confirm `DJANGO_SETTINGS_MODULE=crack_cms.settings` is the prod
   config (it always is — `manage.py` and `build.sh` both set it).
3. Dry-run first so the log shows the planned write count without
   touching anything:

   ```bash
   cd backend
   python backfill_display_number.py
   ```

   Expected output (numbers approximate):

   ```
   [dry-run] would update 500 rows (sample: [(12345, 1), (12346, 2), (12347, 3)])
   [dry-run] would update 500 rows (sample: ...)
   ...
   [dry-run] would touch 4489 rows
   ```

   If the count is **0**, the prod DB is already populated — stop
   here, no apply needed. (This would happen if a previous run was
   successful or the fixture re-export happened in the meantime.)
4. If the dry-run count is plausible (4,000–6,000 for the current
   corpus), apply:

   ```bash
   cd backend
   python backfill_display_number.py --apply
   ```

   The script runs in 500-row batches. Expected wall time on the
   App Platform SFO tier: ~30 seconds for ~4,500 rows.
5. Verify on prod by curl'ing a NEET PG 2021 question id directly:

   ```bash
   curl -s https://crackcms-vsthc.ondigitalocean.app/api/questions/?exam=neet_pg&year=2021&page_size=5 \
     | python -m json.tool | head -40
   ```

   The `display_number` field should now read `1, 2, 3, 4, 5` for
   the first 5 questions returned.

### Option B — Re-export the fixture

Use this path if you ALSO want the local dev DB and any other
fresh-import sites to have `display_number` baked in from the start.

1. Apply the script on prod per Option A.
2. Run the export script locally (it pulls from the local SQLite DB):

   ```bash
   cd backend
   python _export_fixture.py
   ```

3. The export includes the new field automatically (Django serialises
   the model field). Commit the resulting `questions_fixture.json`
   diff and push.

> **Do NOT run option B without option A.** Re-exporting without
> the prod apply means the prod container's `loaddata` on next deploy
> would clobber the live values back to NULL.

---

## Re-running the Playwright Bug #9 Test

After the apply, verify on prod:

```bash
cd frontend
PLAYWRIGHT_SKIP_WEBSERVER=1 \
  BASE_URL=https://www.cracklabs.app \
  API_BASE_URL=https://crackcms-vsthc.ondigitalocean.app \
  npx playwright test tests/e2e/neet-pg-qa.spec.ts \
    --grep "Bug #9"
```

Expected: `1 passed`. The test asserts
`withNum.length > 0` for NEET PG 2021 questions.

If still failing, the script ran but `display_number` is still NULL —
check the prod DB directly via Django shell:

```bash
cd backend
python manage.py shell -c "
from questions.models import Question
qs = Question.objects.filter(exam_type='neet_pg', year=2021)
print('total:', qs.count())
print('with display_number:', qs.exclude(display_number__isnull=True).count())
print('sample:', list(qs.exclude(display_number__isnull=True).values('id', 'display_number')[:5]))
"
```

---

## Rollback

The script writes `display_number = <ordinal>` (a non-null integer)
and never touches other columns. To roll back, set the field back to
NULL for the rows that were touched (the script does not currently
emit an "undo" file, but a single Django ORM statement suffices):

```bash
cd backend
python manage.py shell -c "
from questions.models import Question
Question.objects.filter(display_number__isnull=False).update(display_number=None)
"
```

This reverses the apply without affecting any other data. The
fixture is unchanged.

---

## When to Run This

- **Bug #9 prod test failure** — the most common trigger.
- **Adding a new exam paper** — if you import a new exam with
  `display_number=NULL`, the script will backfill it on the next run
  (the `isnull=True` filter is what guards against re-overwriting
  populated values).
- **Mass-reimport of a year** — if you wipe and re-import a year
  without `display_number`, run this script afterwards.

The script is safe to run at any time. It only writes NULL rows.

---

## See Also

- `backend/backfill_display_number.py` — the script itself.
- `docs/qa/MASTER_QA_REPORT.md` → Outstanding Follow-Ups section.
- `frontend/tests/e2e/neet-pg-qa.spec.ts` → "Bug #9 — display_number
  must default to a per-paper ordinal" — the regression test that
  will go green after the apply.
