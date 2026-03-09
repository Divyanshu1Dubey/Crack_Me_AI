# Question Bank Management Guide

This guide explains all practical ways to manage questions in CrackCMS, with a fixture-first workflow for reliable production deploys.

## Current Source of Truth

- `backend/questions_fixture.json` is the production source for question bank data.
- `backend/build.sh` loads this fixture during deploy.
- If you add or edit questions in local DB, re-export the fixture and commit it.

## Quick Decision Table

- Use `Django Admin` when adding/editing a few questions manually.
- Use `Upload API` when importing many questions at once.
- Use `questions_fixture.json` when syncing data to production.

## Method 1: Add or Edit Questions in Django Admin (Recommended)

1. Start backend server.
2. Open `http://localhost:8000/admin/`.
3. Login as admin/superuser.
4. Go to `Questions`.
5. To add: click `Add Question`.
6. To edit: open existing question, update fields.
7. Save.

Required fields for each MCQ:

- `question_text`
- `option_a`
- `option_b`
- `option_c`
- `option_d`
- `correct_answer` (`A`/`B`/`C`/`D`)
- `year`
- `subject`

Recommended fields:

- `difficulty`
- `explanation`
- `topic`
- `mnemonic`
- `concept_tags`

After admin edits, run fixture export (see Method 4) so production gets the same data.

## Method 2: Add Questions via API (Single or Bulk)

Base endpoint:

- `POST /api/questions/` (single object)
- `POST /api/questions/upload/` (array of objects)

Authentication:

- Admin JWT required.

Example bulk payload for `/api/questions/upload/`:

```json
[
  {
    "question_text": "Most common cause of acute myocardial infarction is:",
    "option_a": "Coronary artery thrombosis",
    "option_b": "Coronary artery spasm",
    "option_c": "Aortic dissection",
    "option_d": "Coronary embolism",
    "correct_answer": "A",
    "year": 2025,
    "subject": 1,
    "topic": null,
    "difficulty": "medium",
    "concept_tags": ["cardiology", "ischemic heart disease"],
    "explanation": "Plaque rupture with thrombus formation is the most common mechanism.",
    "concept_explanation": "ACS pathophysiology basics...",
    "mnemonic": "Rupture -> clot -> MI",
    "book_name": "Harrison",
    "chapter": "Cardiology",
    "page_number": 1021,
    "reference_text": "Relevant short reference",
    "exam_source": "UPSC CMS"
  }
]
```

## Method 3: Add Questions Directly in `questions_fixture.json`

You can manually edit `backend/questions_fixture.json`, but do it carefully.

Rules:

1. Keep valid JSON (no trailing commas, matching braces/brackets).
2. Keep model names unchanged (`questions.question`, `questions.subject`, `questions.topic`).
3. Each item must include:
   - `model`
   - `pk`
   - `fields`
4. New question `pk` should be unique (use next available integer).
5. `fields.subject` must point to a valid subject PK.
6. `fields.topic` must be valid or `null`.

Recommended validation after manual edit:

```powershell
cd backend
python -m json.tool questions_fixture.json > $null
python manage.py loaddata questions_fixture.json
python manage.py shell -c "from questions.models import Question; print(Question.objects.count())"
```

If `loaddata` succeeds and count is expected, commit the fixture.

## Method 4: Fixture Export Workflow (Best Practice)

After any local DB changes (admin/API/shell), export fixture:

```powershell
cd backend
python _export_fixture.py
```

Then:

1. Verify file changed as expected.
2. Commit `backend/questions_fixture.json`.
3. Push to deploy.

## Production Deploy Flow

`backend/build.sh` does:

1. Install requirements
2. Collect static
3. Run migrations
4. Create superuser if env vars exist
5. Load `questions_fixture.json`
6. Hard-check that question count is greater than 0

If fixture is broken or empty, build fails early (prevents silent bad deploy).

## FAQ

### If I edit only `questions_fixture.json`, do I need anything else?

Yes, two things:

1. Ensure JSON is valid and loadable.
2. Commit and redeploy so Render reloads DB from fixture.

### Do I need old import scripts now?

Not for production question loading if fixture-first workflow is used.

- Optional to keep for one-time parsing from raw text/markdown.
- Not required for normal day-to-day operations.

### Can we remove PYQ PDFs and raw import files?

Depends on use:

- Remove if you only care about question bank fixture workflow.
- Keep if you still use them for RAG training, OCR, or future re-parsing.

Safe-to-remove candidates (if not needed anymore):

- `backend/_import_pyq_txt.py`
- `backend/_import_pyq_md.py`
- `backend/Medura_Train/PYQ/*.txt`
- `backend/Medura_Train/PYQ/*.pdf`
- `backend/Medura_Train/PYQ/cms_pyq_database_2018_2024.md`

Before deleting, confirm no active command/script/process depends on these files.

## Admin Operational Checklist

For every question update cycle:

1. Add/edit questions (Admin/API/manual fixture).
2. Validate data.
3. Export fixture (`python _export_fixture.py`) unless you edited fixture directly.
4. Commit code + fixture.
5. Push and verify production counts (`/api/questions/stats/`, `/api/questions/years/`).

## Useful Endpoints for Verification

- `GET /api/questions/years/`
- `GET /api/questions/stats/`
- `GET /api/questions/?year=2018`
- `GET /api/questions/?year=2019`
- `GET /api/questions/?year=2020`
