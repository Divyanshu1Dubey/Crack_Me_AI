# UPSC CMS 2014–2017: the eight papers completed from the official papers (2026-11-08)

**Source.** "UPSC CMS 2009-2025 with Answer Key.pdf", the owner's copy of the official question papers with UPSC's
answer keys (sha256 in `backend/questions/data/cms_official_2014_2017.json`). For 2014–2017 the PDF has a text
layer (a retyped copy of the papers); the key tables were read from the same text layer and cross-checked against
the word positions of each table (identical). Key pages: 2014 P-I p.650, P-II p.673; 2015 P-I p.599, P-II p.624;
2016 P-I p.543, P-II p.568; 2017 P-I p.497, P-II p.518.

**Delivered by** migration `questions.0049_cms_official_2014_2017` (the guarded machinery of 0047/0048,
`questions/cms_official.py`) and the release step `python manage.py record_official_cms_keys --apply` (records
UPSC's key in the answer-key audit; it now covers 2014–2025). On an empty CMS bank (a fresh database, a test run)
0049 does nothing: `seed_question_bank` loads the fixture there.

## Before

The bank had no question tagged 2014–2017. 21 of the 960 official questions were in the bank without a year
(a Paediatrics block of 2016/2017 Paper I), most of them two or three times.

## What changed

| | count |
|---|---|
| official questions added (official text, numbered as in the paper, the key of the paper's key table, the paper's section as subject) | 939 |
| copies already in the bank tagged with year, paper, number (their key already the official one; 18 moved to the paper's section) | 21 |
| second live copies of those 21 hidden (`duplicate of #…`; the copy kept has the official key, the longer explanation, the figure) | 5 |
| broken copies hidden (#25375, #26233: another question's stem over the statements of 2017 Paper II Q96 and an explanation; the official Q96 is added) | 2 |

* **Sections.** Paper I of these years: General Medicine 1–70, Paediatrics 71–90, **General Ability 91–120**
  (the subject "General Ability", code `GENABIL`, is created if missing). Paper II: General Surgery 1–40,
  Obstetrics & Gynaecology 41–80, Community Medicine 81–120, except 2016 (Community Medicine 41–80, Obstetrics &
  Gynaecology 81–120). Checked on the questions at each boundary.
* **Layout.** 35 match-the-list questions are tables with the code written out ("A-2, B-3, C-4, D-1"; 2014 prints
  the code as "A/2 B/3 …"); statements on their own lines; the question line under a list of statements on its own
  line ("4. Femoral vein / What is the correct sequence …").
* **Text-layer artefacts removed.** The 2017 papers carry each page's number after the last option of the page's
  last question ("Fallot tetralogy 2", "1, 2 and 3 12"): removed from 37 options (pages 2–19 / 2–20, read off the
  pages, none missing). No header, footer or watermark text is in any question.
* **Spelling.** The transcription's misspellings were corrected on 68 questions, each correction listed on its
  `add` operation (`spelling`: printed → used), e.g. "Kwashiorkar" → "Kwashiorkor", "Gullain" → "Guillain",
  "arteriosuswith" → "arteriosus with", "Steptococcus" → "Streptococcus", "Wegner's" → "Wegener's". Only standard
  spellings; nothing else changed. Left as printed where the intent is not certain: "Pulsus alternates bisferens"
  (2017 P-I Q29) and "BMI 30" (2017 P-II Q14, the PDF prints no comparison sign).
* **Other exams.** Five official questions (2016 P-I Q85, 2017 P-I Q76, Q81, Q82, Q86) had their only live copy
  labelled NEET PG. They are added to the CMS bank; the NEET PG rows are left as they are (moving them would take
  them out of the NEET PG bank).
* **Hidden copies left hidden.** A test import (`Pediatrics_test4_boxes.docx`) left hidden, `is_dropped` copies of
  some of the Paediatrics questions; they stay hidden and untagged (the live copies are tagged).

## Keys

Every key is the paper's key table: all 960 are single letters (no question dropped, none with two answers in
2014–2017). **One key is held for review:** the table prints "Dc" for 2015 Paper II Q60; D is used, the question
has `needs_review`, and `record_official_cms_keys` does not record it as an official key until an editor confirms
it. The 21 tagged copies list their options in the official order (`letter_map` is empty).

## Reviewed and left

Nine added questions have a live CMS question on the same topic that scores 0.6–0.8 similar (e.g. a reworded
albinism / Chediak–Higashi question, an MDR-TB definition with other options): different questions, both kept.

## Checked

On a copy of the production database (crack_local) migrated 0045 → 0049 as a deploy would:

* all eight papers have 120 active questions numbered 1–120 once, each with the official key, the sections as above;
* a second run of each plan (2018–2025, 2026, 2014–2017) changes nothing;
* `record_official_cms_keys` (dry run): 2,859 questions found, 2,858 to record (1,899 for 2018–2025, 959 for
  2014–2017), 1 held for review;
* `questions.tests.test_cms_official` (28 tests): an added question with the same stem but other options
  ("Which one of the following pairs is not correctly matched?" is asked twice in 2014 Paper I) is added, General
  Ability created, a copy without a year tagged, data-file integrity, the held key not recorded.

## Verify after a deploy

```
python manage.py record_official_cms_keys          # dry run: "2859 found, 2858 already recorded, 0 to record, 1 held for review"
```
and, per paper, `Question.objects.filter(exam_type='cms', year=Y, paper=P, is_active=True).count() == 120` for
2014–2026.

## Not done

* **2009–2013** are scanned pages in the PDF (no text layer): imported by `questions.0051` from OCR checked on the
  page images (`CMS_OFFICIAL_2009_2013.md`).
* Explanations: the 939 added questions have none yet; they are generated on demand (AI, marked as such) or by the
  batch pipeline.
