# NEET PG & INI-CET Fixtures — Author Guide

This directory holds **three** independent Django fixtures + the image folders
they reference. Use them whenever you want to edit questions, fix wrong
explanations, add NEET PG / INI-CET content, or fix an image that didn't
render.

## File layout

```
backend/
  fixtures/
    cms_fixture.json          # renamed from questions_fixture.json (CMS exam)
    neet_pg_fixture.json      # NEET PG questions (subjects ANA, PHY, BCH, …)
    inicet_fixture.json       # INI-CET questions (subjects ANAI, PHYI, …)
    images/
      cms/                    # screenshots referenced from cms_fixture.json
      neet_pg/                # screenshots referenced from neet_pg_fixture.json
      inicet/                 # screenshots referenced from inicet_fixture.json
    README.md                 # ← you are here
```

## Editing workflow — drop a screenshot → commit-ready change

1. **Drop the image file** into `backend/fixtures/images/<exam>/` where `<exam>`
   is `cms`, `neet_pg`, or `inicet`. Use any sensible filename:
   `ecg_287.png`, `ct_thorax_412.jpg`, `my_diagram_v3.png`. Keep names short
   (avoid spaces; use underscore or dash).
2. **Edit the JSON** at `backend/fixtures/<exam>_fixture.json`. Reference the
   image *anywhere* in any text field using the `[[img:filename.png]]` token:

   ```json
   "question_text": "Identify the sign shown:\n[[img:ecg_287.png]]\nSelect:",
   "explanation":   "Note the deep sulcus sign. See [[img:radiograph_sign_287.png]].",
   "option_a":      "Anterior STEMI ([[img:ecg_anterior_stemi.png]]) — ST elevation V1-V4."
   ```

3. **Verify locally** (does NOT touch production):

   ```bash
   cd backend
   python manage.py load_exam_fixture neet_pg --dry-run
   python manage.py load_exam_fixture inicet --dry-run
   ```

   The command prints how many questions / subjects / topics it found, and
   warns you if any `[[img:…]]` tokens point at missing PNGs.

4. **Apply locally** to your DB:

   ```bash
   python manage.py load_exam_fixture neet_pg
   python manage.py load_exam_fixture inicet
   ```

   To wipe + recreate NEET PG Subjects first (when you've added new subject
   codes), add `--replace`:

   ```bash
   python manage.py load_exam_fixture neet_pg --replace
   ```

5. **Commit and push** the JSON + the PNGs. Render auto-detects the new
   file at `/media/fixtures/images/<exam>/` and serves them on the next
   deploy.

## What the loader does, mechanically

The `load_exam_fixture` management command:

- Reads the matching JSON fixture (e.g. `fixtures/neet_pg_fixture.json`).
- Walks every `[[img:foo.png]]` token and rewrites it to
  `/media/fixtures/images/<exam>/foo.png` so the frontend
  `<FormattedText />` renderer can show the image.
- Creates an `ExamTrack` row if missing (so the exam appears in the
  homepage selector).
- `update_or_create` on every Subject/Topic using its `(code, name)` key
  — re-running the loader is idempotent and won't duplicate.
- `update_or_create` on every Question using its `pk` if present, else
  `Question.objects.create()`. New pks are auto-assigned.

If a referenced image is missing, the loader keeps the literal token so
you can spot it during QA:

```
Some referenced images are missing — those [[img:…]] tokens were left as-is…
Add the PNGs into C:\…\fixtures\images\neet_pg and re-run.
```

## Editing the fixtures safely — JSON rules

- The file must be a **JSON array** of Django-fixture rows. Each row has
  `model`, optional `pk`, and a `fields` dict.
- Any object key starting with `_` is silently ignored — they're for
  section comments (`_doc`, `_note`, `_example`). Use them freely.
- `subject` / `topic` on each Question accept **either** the subject code
  (`"PHM"`) or the integer PK. Using the code keeps the file readable.
- Image tokens accept letters, digits, dash, underscore, dot — that's
  it. Nested subfolders are allowed (`subfolder/foo.png`) but not
  recommended.

## CMS (UPSC) backward compatibility

`questions_fixture.json` (the 5.3 MB original) was renamed to
`fixtures/cms_fixture.json`. The lazy-bootstrap path in
`questions/views.py` and the `fix_mojibake` command both auto-detect the
new path; the old path still works as a fallback. No CMS data was lost.

## Production deploy

The fixture re-load is **not** part of `build.sh` (NEET PG and CMS use
the `import_neet_pg` + `_seed_data` commands instead). The loader is
the editor-side tool: you run it locally, verify the UI in dev, then
push the JSON + image files for the next deploy to render them via
`MEDIA_URL=/media/`.

If you eventually need a server-side image upload step (because PNGs are
too large for git), see `docs/INGESTION_REPORT.md` for the
`crack-cms-question-images` Supabase bucket — but for editorial changes
this image-token workflow is intentionally low-friction.

## A new year's paper: `pyq/<exam>_<year>.json` (2026-11)

`fixtures/pyq/cms_2026.json` holds UPSC CMS 2026 Paper 1 and Paper 2
(question booklet Series C, 240 questions): stem, options, the printed
key, number, subject section and topic of every question, in the
`pyq-paper/1` format. Its `note` and `sources` say where it came from: the
Salaah Shots solution PDFs, an **unofficial** key (UPSC had not published
its key). Their explanations were not copied (their own writing); the
questions are imported without an explanation.

```
python manage.py import_pyq_paper fixtures/pyq/cms_2026.json            # dry run: the plan
python manage.py import_pyq_paper fixtures/pyq/cms_2026.json --apply    # write
```

The command (dry run unless `--apply`) skips what is already imported
(same exam, year, paper and `display_number`, so a second run changes
nothing) and stems an admin removed; it lists questions the bank already
has under another label but still creates them, so the paper stays whole
for the year simulator. Each printed key is recorded as a
`key_audit.SourceKey` (`inline_answer`: a secondary-source signal, never a
verified key) and the key audit runs for the new questions
(`insufficient_evidence` until other evidence or an admin review).

Figures: the solution PDFs have none; where the paper had one they write a
bracketed description that often names the answer, so it was removed. The
14 questions whose stem says a figure is shown (`needs_figure`) are created
**hidden** (`is_active=False`, `needs_review`, `is_image_based`): add the
figure from the official UPSC question paper in the questions editor
(`[[img:N]]`), then activate the question. They are 2026 Paper 1 Q17,
Q109, Q110 and Paper 2 Q84, Q88, Q92, Q94, Q95, Q97, Q101, Q106, Q108,
Q109, Q118 (Series C numbers).

Production gets it at deploy: migration `questions.0043_import_cms_2026_papers`
runs this import once on a live bank (1,000+ active CMS questions; a test or
fresh database is skipped), in the same release as the copy that quotes the
bigger bank (`frontend/src/lib/bankStats.ts`). It never fails the deploy: on
an error it prints the command to run by hand. Rehearsed on the local copy
of production: 240 created (226 visible, 14 hidden), 240 source keys and
audits, 2 s.

## The scholarship pool: `scholarship_pool.json` (2026-11-07)

The questions the scholarship challenge draws from (id, stored key and the
stem/options `stem_hash` of the reviewed version; see the file's
`selection` and `caveat`). Migration `questions.0044_scholarship_pool`
applies it once at deploy; `python manage.py apply_scholarship_pool` (dry
run unless `--apply`, `--revoke` to take them out) does the same by hand.
A question whose key or text changed since the review, or that the
challenge cannot show fairly (a figure, free showcase, no key ...), is
skipped and named. Admins add or remove single questions in the questions
editor (toggle and "Scholarship pool" filter). No key is changed.
