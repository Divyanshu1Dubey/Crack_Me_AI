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
