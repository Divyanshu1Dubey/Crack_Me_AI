# UPSC CMS 2018–2025: the bank made to match the official papers (2026-11-07)

**Source.** `UPSC CMS 2009-2025 with Answer Key.pdf`, the owner's copy of the official question papers and the
UPSC answer keys (Series A; sha256 in `backend/questions/data/cms_official_2018_2025.json`). It is treated as
authentic. 2014–2020 papers have a text layer; 2021–2025 papers and all 2019–2025 key pages are scans.

**Delivered by** migration `questions.0047_cms_official_2018_2025` (applies
`backend/questions/data/cms_official_2018_2025.json` through `questions/cms_official.py`) and the release step
`python manage.py record_official_cms_keys --apply` (records UPSC's key in the answer-key audit).

## Result

Every paper of 2018–2025 has exactly **120 active questions, numbered 1–120 as in the official paper**
(`display_number`), each with the **official key**, or flagged `is_dropped` where UPSC dropped the question.
Checked on a copy of the production database restored locally (crack_local), migrated exactly as a deploy
migrates (0045 → 0046 → 0047): 16 / 16 papers at 120, 0 keys differing from the official key, 0 questions left
with mojibake, and a second run of the plan changes nothing.

| Paper | Covered before | Key corrections | Added | Restored | Text repaired | Duplicates hidden | UPSC-dropped flagged | Statements numbered |
|---|---|---|---|---|---|---|---|---|
| 2025 P1 | 120 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025 P2 | 114 | 37 | 6 | 0 | 0 | 1 | 0 | 0 |
| 2024 P1 | 120 | 17 | 0 | 0 | 0 | 0 | 2 | 22 |
| 2024 P2 | 102 | 22 | 18 | 0 | 0 | 2 | 0 | 14 |
| 2023 P1 | 120 | 32 | 0 | 0 | 0 | 0 | 1 | 29 |
| 2023 P2 | 117 | 17 | 3 | 0 | 0 | 3 | 0 | 13 |
| 2022 P1 | 120 | 19 | 0 | 0 | 1 | 0 | 1 | 58 |
| 2022 P2 | 110 | 18 | 10 | 0 | 0 | 3 | 1 | 0 |
| 2021 P1 | 120 | 15 | 0 | 0 | 1 | 0 | 2 | 25 |
| 2021 P2 | 112 | 19 | 8 | 0 | 0 | 5 | 2 | 21 |
| 2020 P1 | 120 | 10 | 0 | 0 | 0 | 0 | 2 | 2 |
| 2020 P2 | 114 | 26 | 6 | 0 | 2 | 4 | 0 | 10 |
| 2019 P1 | 107 | 18 | 4 | 9 | 2 | 0 | 3 | 0 |
| 2019 P2 | 105 | 24 | 9 | 6 | 0 | 9 | 1 | 0 |
| 2018 P1 | 117 | 22 | 0 | 3 | 1 | 0 | 4 | 0 |
| 2018 P2 | 110 | 18 | 4 | 6 | 2 | 8 | 1 | 0 |
| **Total** | | **314** | **68** | **24** | **9** | **35** | **20** | **194** |

"Covered before": official questions that had an active copy in the bank. Besides the table: 14 active questions
tagged Paper I/II that are in no official paper were hidden (13 stand-in questions in 2024 Paper II at the slots of
the missing Q67–70, Q86–88, Q105–110, e.g. "protein with the highest biological value", and #6588, a garbled mix
of 2019 Paper I Q2–Q6); 1,114 questions got their official paper / number; the 70 swapped subject tags of
2018 Paper II were corrected (that paper runs PSM 1–40, O&G 41–80, Surgery 81–120); 313 questions had mojibake
decoded (`ΓåÆ` → `→`, `ΓëÑ` → `≥`, `┬░` → `°`, `╬▓` → `β`, …).

## How the keys were established

* 2019–2025 keys were read off the scanned Series-A key pages; 2018 from the text layer. Every cell where the
  bank disagreed (and every dropped / two-answer cell) was checked again on a crop of the key page; six tables
  (2020 P2, 2021 P1, 2021 P2, 2023 P2, 2024 P1, 2024 P2) were read twice in full and compared (one reading error
  found and corrected: 2024 Paper II Q57 is **B**).
* A key changes only when the option **text** behind the official letter is identified in the bank's options:
  the same text (numbers and Roman numerals folded), or the same order confirmed option by option. Two questions
  list their options in another order than the booklet (2024 Paper II Q46, Q111); their keys already pointed at the
  official answer and were left as they are (`letter_map`). 25 cases where the OCR made the options unreadable
  were settled on the scan.
* Each change is an `AnswerKeyChange` (`source='official_key'`) whose evidence names the PDF, its sha256, the key
  page and the cell; the old key stays in that record. An explanation written for the old key is marked
  `stale` (not shown to students; generated again for the new key), unless it was written for the official key.
* Medical sense was a sanity check only (e.g. hyperparathyroidism localisation → sestamibi scan, tamponade →
  muffled heart sounds and hypotension), never a reason to change a key.

## What was not changed

* **2009–2017** (in the PDF, 2014–2017 with a text layer, 2009–2013 scanned) were not imported here; 2014–2017
  followed in `questions.0049` (`CMS_OFFICIAL_2014_2017.md`); **2026** is not in this PDF
  (`CMS_OFFICIAL_2026.md`).
* Past attempts keep the score they were given (re-scoring after a key change is not implemented; the
  `AnswerKeyChange` rows are `rescore_status='pending'`).
* Questions UPSC dropped stay active (the bank keeps its key); students are not yet shown that UPSC dropped them.
* Untagged (paper 0) questions dated by a guideline year (e.g. "GAPPD goals for 2025") are left as they are.

## Verify after a deploy

```
python manage.py record_official_cms_keys          # dry run, with 0049: "2859 found, 2858 already recorded, 0 to record, 1 held for review"
```
and, per paper, `Question.objects.filter(exam_type='cms', year=Y, paper=P, is_active=True).count() == 120`.
