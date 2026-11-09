# UPSC CMS 2009–2013: the ten papers added from the official papers (2026-11-09)

**Source.** "UPSC CMS 2009-2025 with Answer Key.pdf" (sha256 in `backend/questions/data/cms_official_2009_2013.json`).
For 2009–2013 the question papers are **scans** (two-column UPSC booklets with a diagonal "www.EduMedWeb.com"
watermark); each paper's **answer key** is a page with a text layer (PDF pp. 698, 715, 740, 761, 782, 803, 828, 857,
874, 893). Paper page ranges: 2013 P-I 674–697, P-II 699–714; 2012 716–739, 741–760; 2011 762–781, 783–802; 2010
804–827, 829–856; 2009 858–873, 875–892.

**Delivered by** migration `questions.0051_cms_official_2009_2013` (the guarded machinery of
`questions/cms_official.py`; nothing on an empty bank) and the release step `record_official_cms_keys --apply`
(now 2009–2025).

## How the text was read

1. Each page's scan image was decoded on its own (the watermark is a separate overlay image), split into columns at the
   gutter and read by Windows OCR in **four renderings**; the parses were merged per question by voting word by word.
2. Words outside a medical / English word list, words the renderings disagreed on, letters mixed with digits,
   symbols, brackets, line-break hyphens, match lists, figure words and structural problems were **flagged**, and
   every flagged item was **read on the page image** and corrected (`ocr_fixes.json`) or typed from the page.
3. Page furniture (headers, footers, booklet codes, page numbers, watermark text) never reaches a question.
4. Every paper: questions 1–120, each with four options; no unreadable item; no figure question in these years.

Working files (job folder, copied to `C:\Users\DIVYANSHU\crack_local\cms_official\`): `cms0913/official.json`,
`qa.json` (per paper: gaps and how they were resolved, match lists, sections, uncertain words), `ocr_fixes.json`,
`keys.json`.

## Keys

Read from the key pages' text layer, numbered by **grid position** (four blocks of 30). The key template prints "47"
in place of 48 on eight of the ten pages; the position wins. UPSC **dropped two questions** (key "X"): 2013 Paper I
Q108 and Paper II Q69: added without a key and flagged dropped (`dropped_by_upsc`: shown with "Dropped by UPSC",
never scored).

## What changed

| | count |
|---|---|
| official questions added (numbered as in the paper, the paper's section as subject, the official key) | 1,198 |
| questions UPSC dropped, added without a key and flagged | 2 |
| match-the-list questions as tables (codes written out "A-2, B-3, …") | 55 |
| printed misspellings corrected (listed per question in the data file: "Latrogenic" → "Iatrogenic", "nectosis factor" → "necrosis factor", "Supra condyler humerous" → "Supracondylar humerus", "Tropin-T" → "Troponin-T", "Gullian-Barre" → "Guillain-Barré", "Rheumatic cordites" → "Rheumatic carditis", "Fluconozole" → "Fluconazole", "Brocca index" → "Broca index", …) | 16 questions |

* **Sections** (checked at each boundary, `qa.json`): Paper I of **2009** runs General Ability 1–30, General
  Medicine 31–100, Paediatrics 101–120; Paper I of 2010–2013 General Medicine 1–70, Paediatrics 71–90, General
  Ability 91–120; every Paper II General Surgery 1–40, Obstetrics & Gynaecology 41–80, Community Medicine 81–120.
* **Already in the bank:** none as untagged copies. 11 official questions also appear under other years (UPSC asked
  them again): those rows are left as they are.
* Kept as printed where only the scan's faint print is uncertain: "Terfenadine" (2010 P-I Q54), "C1q" (2010 P-I Q62),
  "Licks on intact skin by a dog" (2011 P-II Q113); and "Sand Flea" against kala-azar (2012 P-II Q106): changing it
  would change the question, not its spelling.

## Checked

On a copy of the production database migrated through 0051:

* all ten papers: 120 active questions numbered 1–120 once, every key the official one (2013: 119 + the dropped one),
  sections as above;
* a second run of the 2014–2017 and 2009–2013 plans changes nothing;
* `record_official_cms_keys` (dry run): 4,057 questions found, 4,056 to record (1,899 for 2018–2025, 959 for
  2014–2017, 1,198 for 2009–2013), 1 held for review;
* the bank now holds **4,320 dated UPSC CMS questions, 2009–2026** (18 years × 2 papers × 120);
* `generate_pyq_blog_drafts` (dry run): 130 drafts (36 papers, 94 topics);
* `questions.tests.test_cms_official` (30 tests: the 2009–2013 data file, a dropped question added without a key).

## Not done

* Explanations: the 1,198 new questions have none yet (the AI explanation batch, `docs/EXPLANATION_BATCH.md`).
* `frontend/src/lib/bankStats.ts`: raise the public figures only after production shows 4,320 (rule in the file).
