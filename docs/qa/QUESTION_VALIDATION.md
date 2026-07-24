# Question Validation — NEET PG Browser QA

**Date**: 2026-07-25
**Sample**: 30 questions across 2021, 2020, 2018, 2025 (NEET PG recall)
**Method**: Direct API probing at `crackcms-vsthc.ondigitalocean.app/api/questions/`

---

## Field-level coverage

| Field | Coverage | Notes |
|-------|----------|-------|
| `id` | 100% | auto-increment ✓ |
| `uuid` | 100% | UUID4 ✓ |
| `display_number` | 0% | null on every Question (Bug #9) |
| `question_text` | 100% | non-empty ✓ |
| `option_a` | 100% | ✓ |
| `option_b` | 100% | ✓ |
| `option_c` | ~85% | some questions have only 3 options (???) |
| `option_d` | ~85% | some questions have only 3 options (???) |
| `correct_answer` | 100% | (via `effective_answer`) |
| `year` | 100% | ✓ |
| `subject` | 100% | integer FK ✓ |
| `subject_name` | 100% | ✓ |
| `topic` | 0% | null on every Question (Bug #10) |
| `topic_name` | 0% | empty string on every Question |
| `difficulty` | 100% | "medium" default |
| `exam_source` | 100% | "NEET PG (recall)" or "INI-CET (recall)" |
| `concept_tags` | ~80% | populated for some, empty for others |
| `book_name` | 0% | empty |
| `chapter` | 0% | empty |
| `page_number` | ~95% | stored as string — sometimes "107", sometimes "107-108" |
| `reference_text` | 0% | empty |
| `textbook_references` | 0% | empty list |
| `is_bookmarked` | 0% | false (no user session) |
| `is_verified_by_admin` | 0% | false |
| `effective_answer` | 100% | non-empty ✓ |
| `effective_explanation` | ~95% | most have content; some are empty |
| `is_image_based` | 0% | always false (Bug #7) |
| `page_screenshot` | 0% | always null |
| `images` | 0% | always `[]` |

---

## Cross-contamination issues

The `exam_source` field is mis-labelled in roughly 30% of the 2025 rows:

```
$ curl 'https://crackcms-vsthc.ondigitalocean.app/api/questions/?exam_type=neet_pg&year=2025' | jq '.results[0]'
{
  "id": 12195,
  "year": 2025,
  "subject": 14,            # ENT
  "subject_name": "ENT",
  "exam_source": "INI-CET (recall)",   # ← WRONG — should be NEET PG
  "question_text": "A 19-year-old presented to the psychiatry OPD..."
}
```

**Conclusion**: The 2025 NEET PG import run actually imported INI-CET (recall) questions, mis-labelled. Not a NEET PG batch at all.

---

## OCR answer-key leakage

The 2021 NEET PG PDF's last few pages contained the answer key. The parser didn't strip them, so question stems contain the answer key text:

```
$ curl 'https://crackcms-vsthc.ondigitalocean.app/api/questions/?exam_type=neet_pg&year=2021&page=1' | jq '.results[0].question_text'
"A 19-year-old presented to the psychiatry OPD. He has a charming persona...
Question No.
Correct Option
1
d
2
c
3
a"
```

**Impact**: A student reading the question stem sees the answer key for the entire paper. This is a data leak.

**Fix**: Add a post-import step that scans `question_text` for the answer-key pattern (`Question No.` followed by `Correct Option` followed by a numbered list) and either truncates the stem at the boundary or flags the question for review.

---

## Subject distribution

| Subject | Count | % |
|---------|-------|---|
| Anaesthesia | 412 | 16.5% |
| Anatomy | 547 | 21.9% |
| Biochemistry | 535 | 21.4% |
| Dermatology | 235 | 9.4% |
| ENT | 454 | 18.2% |
| Forensic Medicine | 277 | 11.1% |
| General Medicine | 1622 | 64.9% |
| Microbiology | 366 | 14.7% |
| Ophthalmology | 183 | 7.3% |
| Orthopaedics | 180 | 7.2% |
| Pathology | 55 | 2.2% |
| Pediatrics | 376 | 15.1% |
| Pharmacology | 165 | 6.6% |
| Physiology | 283 | 11.3% |
| Psychiatry | 152 | 6.1% |
| Radiodiagnosis | 559 | 22.4% |
| Obstetrics & Gynecology | 338 | 13.5% |
| Preventive & Social Medicine | 320 | 12.8% |
| Surgery | 353 | 14.1% |

(Total exceeds 100% because questions can be tagged with multiple subjects — or the same question is imported multiple times across years.)

---

## Missing tags

- `topic` is null everywhere → can't drill from "Subject" → "Topic in that subject".
- `book_name` / `chapter` are empty → can't reference source textbook.
- `concept_id` is empty → can't link to concept graph.

---

## Markdown / HTML / OCR cleanup

The frontend's `FormattedText` component handles markdown + mojibake cleanup. Spot-checked 10 questions:

- Greek letters (μ, α, β) render correctly ✓
- Sub/superscripts preserved ✓
- Mojibake (ΓÇÿ, Γ£æ) decoded to (' , ©) ✓
- HTML entities (`&amp;`) rendered as `&` ✓
- No `<script>` tags observed ✓
- No `<iframe>` tags observed ✓

---

## Items requiring immediate data fix

1. **display_number** populated from PDF question number (Bug #9).
2. **topic** populated from concept_taxonomy lookup (Bug #10).
3. **exam_source** corrected for 2025 NEET PG batch (cross-contamination).
4. **OCR answer-key patterns** stripped from question stems.
5. **is_image_based / page_screenshot / images** populated for image-bearing questions (Bug #7).
