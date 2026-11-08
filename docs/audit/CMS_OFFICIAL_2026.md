# UPSC CMS 2026: the bank matched to the official question papers (2026-11-08)

**Source.** The official 2026 question papers, Test Booklet **Series A**:
`QP-CMSE-26-GnrlMdcnPediatrc-Paper-I-030826.pdf` (Paper I, T.B.C. NTDC-O-KPMS, 28 scanned pages) and
`QP-CMSE-26-SrgryGynaeObstPvntSclMdcnPaper-II-03082026.pdf` (Paper II, T.B.C. NTDC-T-GSPO, 32 scanned pages); their
sha256 are in `backend/questions/data/cms_official_2026.json`.

**Delivered by** migration `questions.0048_cms_official_2026` (same guarded machinery as 0047:
`questions/cms_official.py`).

## What changed

* **Numbering.** The 240 questions were imported from a publisher's solutions, which follow another booklet series:
  every question's number differed from the official paper. Each was matched to its Series-A question (221 by
  text; 19 read off the pages: questions the OCR merged with a neighbour, the case scenarios, match-the-list tables)
  and now carries the Series-A number (`display_number`), like every other year. The match is one to one: 120 + 120.
* **Figures.** 16 questions have a figure in the official papers; none had one in the bank. The figures were
  cropped from the scans (`backend/questions/data/figures_2026/`, checksums in its `manifest.json`), are staged in
  `ops_media_transfer` and attached as the question's image (the image endpoint writes a staged file to the media
  volume on first use). The **14 questions that were hidden only because their figure was missing are live**;
  2 others (Paper I Q44 letter-cancellation test, Q110 abdominal X-ray) had been shown without their figure.
* **Layout repaired, same words (43 questions).** "Select the correct answer…" on its own line; the first row of
  match-the-list tables joined (it rendered as a broken table); 11 statement lists that had lost their numbers
  numbered from the official text (the bank's own words, checked item by item); the case-scenario references
  renumbered ("Questions 3–4" → "Questions 113–114", "5–9" → "115–119"); a publisher note removed from an
  option ("Progesterone (Note: Standard physiological consensus question analysis)" → "Progesterone").
* The wording otherwise agrees with the official papers (230 of 240 stems ≥ 0.85 similar to the OCR text; the 10
  below are the case scenarios, a labelled diagram and two tables, checked on the page).

## Keys

**No official 2026 answer key is available** (UPSC publishes keys after the final result). The keys are left as they
are: they come from the publisher's solutions and the answer-key audit holds them as publisher signals
(`SourceKey`), never as official keys. When UPSC publishes the Series-A key it can be applied the way 0047 applied the
2018–2025 keys.

## Checked

On a copy of the production database (crack_local) migrated 0045 → 0048: both papers have 120 active questions
numbered 1–120 once, all 16 figure questions have their image, no 2026 question is hidden, a staged figure restores
to the media folder, and a second run changes nothing.
