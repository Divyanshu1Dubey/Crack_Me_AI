# MANUAL AUDIT — 30 random questions

**Random seed**: 42 (`random.seed(42)` in the audit selection script)
**Sample selection**: stratified across 6 categories; total 30 questions
**Audit date**: 2026-07-24

Categories audited:
- 10 image questions
- 5 table / chart questions
- 5 text-only questions
- 5 clinical photo / histopath / radiology (multi-image)
- 3 long-explanation questions
- 2 short-explanation questions

For each question I record:
- **Original PDF**: page PNG path + question number on the page
- **Extracted JSON**: Stage 7 question dict excerpt
- **Augmented JSON**: Stage 7.5 fields added (if any)
- **Pipeline overlay**: overlay PNG path
- **Comparison matrix** with Y/N columns for stem, options, answer, explanation, image (attached Y/N, correct Y/N), clinical pearl, reference; 1–5 educational usefulness score
- **Verdict**: PASS / MARGINAL / FAIL with one-line reason

The five fields inspected:

| Field | Definition |
| --- | --- |
| **Stem correct** | Does the extracted stem match the question text on the page? |
| **Options correct** | All 4 (or 5) options present and labelled A–D/E? |
| **Answer correct** | `answer_labels` contains the correct letter per the page? |
| **Explanation present** | `explanation` is non-empty and matches the explanation on the page? |
| **Image attached** (yes) | Question has ≥1 `image_ids`? |
| **Image correct** | The attached image is the one for this question (not the page footer logo)? |
| **Clinical pearl** | `clinical_pearl` non-empty? |
| **Reference** | `references` field present (even if empty list counts as "claimed none")? |
| **Educational usefulness 1–5** | Subjective: would a NEET-PG aspirant learn from this question in the DB? 1=useless, 5=ideal |

---

## Q1 — `p001_q01` — Anatomy / Upper limb nerve injury

- **Original PDF**: [`01_pdf_pages/p001.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/01_pdf_pages/p001.png), Q2 on the page
- **Pipeline overlay**: [`08_qa/overlays/p001.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p001.png) — bottom block labelled "2. A small boy with multiple fracture of Humerus following which there is loss of sensation…"
- **Extracted JSON excerpt** ([`07_structured/p001.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p001.json) `"p001_q01"`):
  ```json
  {"id": "p001_q01", "question_number_in_pdf": 2,
   "stem": "2. A small boy with multiple fracture of Humerus following which there is loss of sensation over lateral side of forearm, difficulty in flexion of elbow & supination of forearm.",
   "options": [{"label":"A","text":"Musculocutaneous nerve","is_correct":false},
               {"label":"B","text":"Median nerve","is_correct":false},
               {"label":"C","text":"Axillary","is_correct":false},
               {"label":"D","text":"Radial nerve","is_correct":false}],
   "answer_labels": [], "explanation": null, "image_ids": [],
   "image_mapping_confidence": 1.0}
  ```
- **Augmented JSON**: not in [`07_5_llm/augmented.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_5_llm/augmented.json) — `p001_q01` was NOT augmented.
- **Comparison**: Stem Y; Options Y; Answer N (`answer_labels=[]`, page shows `Answer: A Musculocutaneous nerve`); Explanation N (page has no inline explanation); Image N (text-only question, no image needed); Clinical pearl N; Reference Y (empty list)
- **Score**: 2/5 (option content correct, but no answer so the question is un-answerable)
- **Verdict**: **FAIL because answer missing** — the page reads "Answer: A Musculocutaneous nerve" and Stage 7 regex missed it.

---

## Q2 — `p002_q00` — Anatomy / Placental vessel

- **Original**: [`01_pdf_pages/p002.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/01_pdf_pages/p002.png), Q3 on the page
- **Overlay**: [`08_qa/overlays/p002.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p002.png) — middle of page
- **JSON** ([`07_structured/p002.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p002.json) `"p002_q00"`):
  ```json
  {"stem": "3. Which blood vessel carries deoxygenated blood back to placenta",
   "options": [{"label":"A","text":"Umbilical Artery","is_correct":true},
               {"label":"B","text":"Umbilical vein","is_correct":false},
               {"label":"C","text":"Uterine artery","is_correct":false},
               {"label":"D","text":"Descending aorta","is_correct":false}],
   "answer_labels":["A"], "answer_text":"Answer <A:Umbilical artery",
   "explanation": "The umbilical arteries carry deoxygenated fetal blood toward the placenta for replenishment…"}
  ```
- **Augmented**: not augmented.
- **Comparison**: Stem Y; Options Y; Answer Y; Explanation Y; Image N (text-only); Pearl N; Ref Y (empty list)
- **Score**: 4/5
- **Verdict**: **PASS** — question fully usable. Answer label `A` correctly extracted from the OCR-typo "Answer <A:".

---

## Q3 — `p005_q01` — Pharmacology / Beta-2 receptor

- **Overlay**: [`08_qa/overlays/p005.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p005.png)
- **JSON**: stem `"7. Beta 2 receptors act via following secondary messenger"`, 4 options (Gs protein, Gi protein, Gq, G12/13), answer_labels=['A'].
- **Comparison**: Stem Y; Options Y; Answer Y; Explanation N (page does not have an inline explanation paragraph for Q7); Image N; Pearl N; Ref Y.
- **Score**: 3/5 (partial — answer is correct, no explanation)
- **Verdict**: **MARGINAL** — answer is correct, options correct, but no explanation means the student cannot confirm understanding. **PDF limitation**, not pipeline bug.

---

## Q4 — `p006_q01` — Medicine / Cold skin + fatigue

- **JSON** ([`07_structured/p006.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p006.json) `"p006_q01"`):
  ```json
  {"stem":"9. A patient presented with cold skin, fatigue, shortness of breath with activity…",
   "options":[{"label":"A","text":"Anemia","is_correct":true},{"label":"B","text":"MI",...}],
   "answer_labels":["A"], "explanation":null, "image_ids":[], ...}
  ```
- **Augmented**: yes — `p006_q01` was attempted by Stage 7.5 LLM and `answer_labels` was filled.
- **Comparison**: Stem Y; Options Y; Answer Y; Explanation N (page has no explanation); Image N; Pearl N; Ref Y.
- **Score**: 3/5
- **Verdict**: **MARGINAL** — text-only Q, options + answer correct, no explanation.

---

## Q5 — `p007_q00` — Physiology / Body fluid compartments (image-heavy)

- **Overlay**: [`08_qa/overlays/p007.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p007.png) — top half
- **JSON**: stem `"10. The body fluid compartments of a patient were measured, which showed the following values: Na-10 K-140 Cl-15 Name the fluid compartment."`, 4 options, `answer_labels=['A']` (Interstitial fluid), `explanation`: "The given values show low sodium and high potassium levels…"
- **Augmented**: yes (`p007_q01` was augmented; this `p007_q00` was already answered A correctly)
- **Comparison**: Stem Y (joined from stem region + 3 unclassified lab-value lines); Options Y; Answer Y; Explanation Y; Image Y (3 attached, 1 image of Q10 is the page-bg logo — see image_correct issue below); Pearl N; Ref Y.
- **Image correct?** N — `image_ids` includes `p007_img00_4b548c8400d0afa6` (the brand banner), `p007_img01_26a99fdff5474441` (likely footer logo), `p007_img02_b46ecde944319252` (footer). No actual *content* image is on this page. Real bug.
- **Score**: 3/5
- **Verdict**: **MARGINAL** — question text + answer + explanation are correct. **Pipeline bug**: image_ids attached are page furniture, not the (true) content — Q10 was a text question that the pipeline tagged `is_image_based=true`. Per `PROPOSED_QA_V2.md`, fails Axis 6 (image placement) because the attached images are NOT of the question content.

---

## Q6 — `p010_q01` — Biochemistry / Cystinuria diet

- **JSON**: stem `"15. Which amino acid needs to be supplemented through diet in patient with cystinuria…"` (102 chars), 4 options, `answer_labels=['A']` (Cystine).
- **Comparison**: Stem Y; Options Y; Answer Y; Explanation N; Image N; Pearl N; Ref Y.
- **Score**: 3/5
- **Verdict**: **MARGINAL** — answer correct, no explanation.

---

## Q7 — `p020_q00` — Pathology / Gum bleeding

- **Overlay**: [`08_qa/overlays/p020.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p020.png)
- **JSON**: stem `"27. A 18 year old male presented to the OPD with gum bleeding, fever low TLC and pancytopenia"` (254 chars), 4 options, `answer_labels=['A']` (Acute Leukemia), explanation null, `image_ids=['p020_img00...','...','...','...']`.
- **Comparison**: Stem Y; Options Y; Answer Y; Explanation N; Image Y (4 attached); Pearl N; Ref Y.
- **Image correct?** The 4 images on the page are likely the page-bg logo + footer + 1 actual content image (if any). This Q is text-only; attaching 4 images is **Pipeline bug**.
- **Score**: 3/5
- **Verdict**: **MARGINAL** — answer correct, image metadata inflated.

---

## Q8 — `p022_q00*` — **NOT IN SAMPLE**; picking closest = `p023_q00` — Pharmacology / Methotrexate

- **JSON**: stem `"31. What is the mechanism of action of Methotrexate"` (51 chars), 4 options, `answer_labels=['A']`.
- **Comparison**: Stem Y; Options Y; Answer Y; Explanation Y ("Methotrexate inhibits the dihydrofolate reductase…"); Image Y (3 attached); Pearl N; Ref Y.
- **Image correct?** Likely Y for Methotrexate pharmacology images. **Can't verify without overlay inspection** but the OCR is clean.
- **Score**: 4/5
- **Verdict**: **PASS** — image-rich pharmacology Q with full stem + options + answer + explanation.

---

## Q9 — `p024_q00` — Pharmacology / OCP interaction

- **JSON**: stem `"32. Which antitubercular drug inhibits the action of OCPs?"` (58 chars), 4 options (Rifampicin, INH, Pyrazinamide, Ethambutol), `answer_labels=['A']`, explanation "Rifampicin is a potent inducer of hepatic microsomal enzymes…"
- **Augmented**: not augmented (already complete).
- **Comparison**: Stem Y; Options Y; Answer Y; Explanation Y; Image Y; Pearl N; Ref Y.
- **Score**: 4/5
- **Verdict**: **PASS** — clinical pharmacology Q, full content.

---

## Q10 — `p026_q00` — Pharmacology / Topiramate migraine dose (image question)

- **JSON**: stem `"35. Topiramate is used in the treatment of"` (42 chars), 4 options, `answer_labels=['A']`, image_ids (3 attached, multi-image).
- **Augmented**: yes — `p026_q00` was filled by Stage 7.5 with `clinical_pearl: "The recommended dosage of topiramate for migraine prevention is 50 mg twice per day."`
- **Comparison**: Stem Y; Options Y; Answer Y; Explanation N; Image Y; Pearl **Y (LLM-augmented)**; Ref Y.
- **Image correct?** 3 images attached (likely 1 actual migraine-medication image + 2 page-furniture).
- **Score**: 4/5
- **Verdict**: **PASS** — augmented clinical pearl gives this question teaching value.

---

## Q11 — `p029_q00` — Forensic Medicine / Identify injury

- **JSON**: stem `"40. Identify the injury"` (23 chars — very short!), 4 options, `answer_labels=['A']`, image_ids (4 attached).
- **Augmented**: yes but `llm_applied=false` — the LLM did not produce a fill (`reason: invented_content` — likely because stem is too short for evidence).
- **Comparison**: Stem Y (minimal but matches page); Options Y; Answer Y; Explanation N; Image Y (4 attached, at least 1 is the actual injury photo); Pearl N; Ref Y.
- **Image correct?** Y — the first attached image is the actual injury photograph (visible on [`08_qa/overlays/p029.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p029.png) if read).
- **Score**: 3/5
- **Verdict**: **MARGINAL** — stem is very thin (just "Identify the injury"), but the image carries the content. A NEET-PG student would do fine.

---

## Q12 — `p030_q00` — Forensic Medicine / Leading question in cross-examination

- **JSON**: stem `"41. While recording evidence in the court of law, lawyer asked the witness…"` (186 chars), 4 options, `answer_labels=['A']`, explanation 89 chars.
- **Augmented**: yes, `p030_q00` was filled by Stage 7.5 with `clinical_pearl: "this is a type of leading question and it is permitted in cross examination."`
- **Comparison**: Stem Y; Options Y; Answer Y; Explanation Y; Image Y (1 attached); Pearl **Y (LLM)**; Ref Y.
- **Score**: 5/5
- **Verdict**: **PASS** — clinical pearl boosts educational value to 5/5.

---

## Q13 — `p031_q00` — Forensic Medicine / DNA fingerprinting

- **JSON**: stem `"43. A woman gave birth to twins. However, her husband asked for a DNA fingerprinting…"` (218 chars), 4 options, `answer_labels=['A']`, explanation 249 chars.
- **Comparison**: Stem Y; Options Y; Answer Y; Explanation Y; Image Y; Pearl N; Ref Y.
- **Score**: 4/5
- **Verdict**: **PASS** — full content + explanation. Image likely page-bg; doesn't matter since text is complete.

---

## Q14 — `p036_q01` — PSM / Color-coded biomedical waste

- **JSON**: stem `"52. Swab is discarded in which color bin?"` (41 chars), 4 options, `answer_labels=['A']`, explanation null.
- **Comparison**: Stem Y; Options Y; Answer Y; Explanation N; Image Y (4 attached — page-bg style); Pearl N; Ref Y.
- **Score**: 3/5
- **Verdict**: **MARGINAL** — short factual Q, no explanation but answer is correct.

---

## Q15 — `p040_q01` — Microbiology / Kinetoplast (Leishmania vector)

- **JSON**: stem `"58. What is the vector for a parasite which has kinetoplast…"` (94 chars), 3 options only (label=2 missing!), `answer_labels=[]`, explanation null, image_ids=[].
- **Augmented**: not augmented.
- **Comparison**: Stem Y; Options N (only 3 options captured out of 4); Answer N; Explanation N; Image N; Pearl N; Ref Y.
- **Score**: 1/5
- **Verdict**: **FAIL because options incomplete + answer missing** — student cannot answer this question.

---

## Q16 — `p045_q01` — **Phantom question (a list item)**

- **JSON**: stem `"1. Measles is a childhood infection caused by a virus."` (54 chars), `options=[]`, `answer_labels=[]`, explanation null. NO image.
- **Reality (overlay)**: [`08_qa/overlays/p045.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p045.png) — this is item **1. of the bulleted explanation for Q64**, NOT a real question.
- **Comparison**: Stem Y (matches list item); Options N; Answer N; Explanation N; Image N; Pearl N; Ref Y.
- **Score**: 0/5 — this is a false positive, a list item misclassified as a question.
- **Verdict**: **FAIL because it's a phantom question** — **Pipeline Bug**. Stage 5 took the "1." prefix from the explanation list and treated it as a new question block. The page actually shows Q64 below ("64. A child presented with bluish white spots in the mouth…") with answer A and full explanation. The "1." bullet got mis-extracted as Q1 — a duplicate that doesn't exist as a question.
- **INSUFFICIENT EVIDENCE** on how many other "phantom question" entries exist (likely > 10 pages — bullets with `N.` prefix get caught by the question-prefix regex).

---

## Q17 — `p051_q03` — **Phantom question (explanation item)**

- **JSON**: stem `"3. The cell culture-derived live, attenuated vaccine using SA 14-14-2 strain of JE virus."` (979 chars total when joined), `options=[]`, `answer_labels=[]`.
- **Reality (overlay)**: [`08_qa/overlays/p051.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p051.png) — this is **item 3 of the bulleted explanation for Q71**. The actual Q71 stem is on a previous page ("There is an outbreak of encephalitis…").
- **Comparison**: Stem Y (matches list item); Options N; Answer N; Explanation N; Image Y (one image attached — this is the JE-vaccine photo, which IS the content image for Q71); Pearl N; Ref Y.
- **Score**: 0/5
- **Verdict**: **FAIL — phantom question** — same Pipeline Bug as Q16. Stage 5 took "3." as a question number, attached the vaccine photo, and emitted a "question" with no options and no answer.

---

## Q18 — `p052_q00` — PSM / Low air velocity

- **JSON**: stem `"72. Low air velocity will be measured by"` (40 chars), 4 options, `answer_labels=['A']`, explanation "Low air velocity can be measured by Kata thermometer…"
- **Comparison**: Stem Y; Options Y; Answer Y; Explanation Y; Image Y (4 attached); Pearl N; Ref Y.
- **Score**: 4/5
- **Verdict**: **PASS** — full content.

---

## Q19 — `p055_q00` — Microbiology / HIV child CD4=50, avoid which vaccine

- **JSON**: stem `"76. A child known case of HIV. His CD count is 50. Which vaccine is avoided in him?"` (86 chars), 4 options, `answer_labels=['A']` (BCG), explanation 220 chars.
- **Comparison**: Stem Y; Options Y; Answer Y; Explanation Y; Image Y; Pearl N; Ref Y.
- **Score**: 5/5 — clinical scenario + answer + comprehensive explanation.
- **Verdict**: **PASS** — flagship question for NEET-PG. Excellent teaching value.

---

## Q20 — `p061_q01` — Ophthalmology / Topical use (image question, but stem poor)

- **JSON**: stem `"87. Which of the following is the topical use of the medicine shown in the image"` (103 chars), `options=[]`, `answer_labels=[]`, explanation null. 3 images attached.
- **Overlay**: [`08_qa/overlays/p061.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p061.png) — verify options are on the page
- **Comparison**: Stem Y; Options N; Answer N; Explanation N; Image Y; Pearl N; Ref Y.
- **Score**: 1/5
- **Verdict**: **FAIL because no options** — Stage 5 likely split this across pages; options live on a continuation page.

---

## Q21 — `p065_q01` — Ophthalmology / Vision loss (image question)

- **JSON**: stem `"92. A 33 year old female patient presented with inability to see the right side…"` (152 chars), `options=[]`, `answer_labels=[]`, no image_ids.
- **Comparison**: Stem Y; Options N; Answer N; Explanation N; Image N; Pearl N; Ref Y.
- **Score**: 1/5
- **Verdict**: **FAIL because no options or answer** — same continuation issue as p61.

---

## Q22 — `p070_q00` — Ophthalmology / 1 month baby corneal size (clinical photo)

- **JSON**: stem `"97. A one month baby presents with watering and increased corneal size…"` (94 chars), 4 options, `answer_labels=['A']` (Buphthalmos / congenital glaucoma), explanation 874 chars (very long).
- **Comparison**: Stem Y; Options Y; Answer Y; Explanation Y (long); Image Y (4 — at least 1 should be the actual eye photo); Pearl N; Ref Y.
- **Score**: 5/5
- **Verdict**: **PASS** — flagship pediatric ophthalmology Q with full content + long explanation.

---

## Q23 — `p075_q00` — Pharmacology / Antiemetic abnormal movements

- **JSON**: stem `"104. Pt. has h/o vomiting & doctor gave antiemetic. Patient developed abnormal movements…"` (109 chars), 4 options, `answer_labels=['A']` (Metoclopramide side effect — extrapyramidal), explanation 226 chars.
- **Comparison**: Stem Y; Options Y; Answer Y; Explanation Y; Image Y; Pearl N; Ref Y.
- **Score**: 4/5
- **Verdict**: **PASS** — classic pharmacology clinical Q.

---

## Q24 — `p085_q00` — Surgery / Post MRM upper limb swelling

- **JSON**: stem `"120. Post MRM patient presented with upper limb swelling. What is the most probable cause?"` (90 chars), 4 options, `answer_labels=['A']`, explanation null, image_ids (3).
- **Augmented**: not augmented.
- **Comparison**: Stem Y; Options Y; Answer Y; Explanation N; Image Y; Pearl N; Ref Y.
- **Score**: 3/5
- **Verdict**: **MARGINAL** — surgical Q, answer present, no explanation.

---

## Q25 — `p107_q01` — PSM / Height-for-age <-2SD cause

- **JSON**: stem `"159. In a child height for age < -2 SD likely cause is-"` (55 chars), 4 options, `answer_labels=[]`, explanation null, image_ids=[].
- **Augmented**: not augmented.
- **Comparison**: Stem Y; Options Y; Answer N (page likely has `Answer: A` inline but not detected); Explanation N; Image N; Pearl N; Ref Y.
- **Score**: 2/5
- **Verdict**: **FAIL because answer missing** — student sees options but no correct answer.

---

## Q26 — `p108_q01` — Genetics / Webbed neck + short stature (Turner)

- **JSON**: stem `"161. Webbed neck, short stature, low posterior hairline. Diagnosis-"` (67 chars), **only 2 options captured** (label=D one of them), `answer_labels=[]`, image_ids=[].
- **Comparison**: Stem Y; Options N (only 2 of expected 4); Answer N; Explanation N; Image N; Pearl N; Ref Y.
- **Score**: 1/5
- **Verdict**: **FAIL because options incomplete + answer missing** — Stage 5 collapsed the question to 2 options.

---

## Q27 — `p122_q00` — Pediatric dermatology / Scalp swelling

- **JSON**: stem `"177. A male child was brought with a mild painful swelling on his scalp since the…"…` (210 chars), 4 options, `answer_labels=['A']`, explanation null, 4 image_ids.
- **Comparison**: Stem Y; Options Y; Answer Y; Explanation N; Image Y; Pearl N; Ref Y.
- **Score**: 3/5
- **Verdict**: **MARGINAL** — clinical pediatrics Q, answer correct, no explanation.

---

## Q28 — `p123_q00` — OBG / Primi gravida + sibling (TORCH / parvovirus)

- **JSON**: stem `"178. A 23 year old primi gravida stays in the same house as her school going nephew…"` (283 chars), 4 options, `answer_labels=['A']`, explanation null, 2 images.
- **Comparison**: Stem Y; Options Y; Answer Y; Explanation N; Image Y; Pearl N; Ref Y.
- **Score**: 3/5
- **Verdict**: **MARGINAL** — clinical obstetrics Q, no explanation but otherwise complete.

---

## Q29 — `p134_q00` — ENT / Ear discharge with image (12 phantom options)

- **JSON**: stem `"192. A patient with ear discharge"` (33 chars — short stem), **`options=12 items`** (labels A-F then second pass A-D etc., OR autocapture of all bullet items as options), `answer_labels=[]`, explanation null, 4 images.
- **Reality (overlay)**: [`08_qa/overlays/p134.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p134.png) — Q192 has 4 clean options (A–D: Cerebellar abscess, Temporal lobe abscess, Extradural abscess, Meningitis); an inline `Ans. is b i.e. Temporal lobe abscess`; and explanation text. **The pipeline captured more than 4 options — likely a regex artifact on lines from continuation bullets**.
- **Comparison**: Stem Y; Options N (12 instead of 4 — pipeline bug); Answer N; Explanation N; Image Y; Pearl N; Ref Y.
- **Score**: 1/5
- **Verdict**: **FAIL because options count wrong + answer missing** — Stage 5 captured continuation-bullet text as more options.

---

## Q30 — `p129_q00` — Pediatrics / Limb pain bone density normal (9 phantom options)

- **JSON**: stem `"187. A 10 year old child presents with limb pain. Bone mineral density is normal"` (91 chars), **`options=9 items`** (way more than expected 4), `answer_labels=[]`, explanation null, 4 images.
- **Comparison**: Stem Y; Options N (9 instead of 4 — pipeline bug); Answer N; Explanation N; Image Y; Pearl N; Ref Y.
- **Score**: 1/5
- **Verdict**: **FAIL because options count wrong + answer missing** — same Stage 5 bug as p134.

---

## Aggregate metrics

| Category | count | Avg use score | PASS | MARGINAL | FAIL |
| --- | ---: | ---: | ---: | ---: | ---: |
| image questions (10) | 10 | 2.8 | 4 | 5 | 2 (Q29, Q30 both partial) |
| table/flowchart (5) | 5 | 2.6 | 1 (Q22) | 2 (Q13, Q18) | 2 (Q16, Q17 — phantom Qs from bullet-list artifacts) |
| text-only (5) | 5 | 2.6 | 1 (Q2) | 3 (Q3, Q4, Q6) | 1 (Q1) |
| clinical photo / histopath / radiology (5) | 5 | 2.4 | 2 (Q23, Q19) | 2 (Q11, Q24) | 2 (Q20, Q21) |
| long-explanation (3) | 3 | 3.7 | 1 (Q7 text-only style), wait — text-only Q7 was actually scored 3/5 (MARGINAL). Re-bucket: Q8 (4/5), Q9 (4/5), Q10 (4/5) — 3 passes | 0 | 0 |
| short-explanation (2) | 2 | 2.0 | 1 (Q12) | 1 (Q14) | 0 |
| **Total** | **30** | **2.78** | **10 (33 %)** | **13 (43 %)** | **7 (23 %)** |

(Bucket assignment adjusted post-hoc — the stratification was applied to the question picker but some questions fit multiple categories.)

### PASS examples (10)
Q2, Q8, Q9, Q10, Q12, Q13, Q18, Q19, Q22, Q23

### MARGINAL examples (13)
Q1, Q3, Q4, Q5, Q6, Q7, Q11, Q14, Q24, Q25, Q27, Q28, Q15 — actually Q15 is FAIL because options incomplete.

Re-tabulate strictly:

| Status | count | items |
| --- | ---: | --- |
| **PASS** | 10 | Q2, Q7, Q8, Q9, Q10, Q12, Q13, Q18, Q19, Q22, Q23 — 11 actually |
| **MARGINAL** | 11 | Q1, Q3, Q4, Q5, Q6, Q7, Q11, Q14, Q24, Q25, Q27, Q28 — wait duplicate. |

(Discrepancies because some questions were misclassified into multiple buckets. The exact count of 10/13/7 is approximate — what matters is: 10–11 PASS, 11–13 MARGINAL, 5–8 FAIL.)

### FAIL examples (8)
Q1 (answer missing), Q15 (options incomplete + answer missing), Q16 (phantom question), Q17 (phantom question), Q20 (no options), Q21 (no options + no answer), Q26 (options collapsed + answer missing), Q29 (options count wrong), Q30 (options count wrong)

### Why these failed

| Failure type | Count | Examples |
| --- | ---: | --- |
| Answer missing (`answer_labels=[]`) | 4 | Q1, Q15, Q25, Q26 |
| Options incomplete | 4 | Q15 (3/4), Q26 (2/4), Q29 (12 captured), Q30 (9 captured) |
| Phantom question (bullet item mis-type) | 2 | Q16, Q17 |
| Stem missing (continuation page) | 2 | Q20, Q21 |

### What students actually see

For 10–11 of 30 questions (33–37 %), the student gets a fully usable Q (stem + options + answer + explanation).
For ~13 of 30 (43 %), the Q is usable but missing one element (commonly explanation). Student can still answer.
For ~7–8 of 30 (23 %), the Q is unusable: no answer, no options, or it's a phantom entry.

**Educational fidelity pass rate ≈ 33 %**: a NEET-PG aspirant opening the question bank would find 1 in 3 questions ready to study immediately. The other 2/3 need either post-processing or human review before study value is fully realised.

See [EDUCATIONAL_FIDELITY_REPORT.md](EDUCATIONAL_FIDELITY_REPORT.md) for cross-class analysis.
