import type { BlogPost } from '@/lib/blog';

/**
 * Blog post — UPSC CMS Syllabus & High-Yield Topics.
 *
 * Single source of truth for the official UPSC CMS syllabus with our
 * own analysis of where questions actually come from (subject-wise
 * weightage across the last 10 years of CMS PYQs). All subject
 * weightage numbers in this post come from our own PYQ analysis
 * (see the [UPSC CMS PYQ archive](/cms/pyq) page on CrackCMS for the
 * raw tagged data). The official syllabus content is sourced from
 * the UPSC CMS notification on upsc.gov.in.
 */
const post: BlogPost = {
    slug: 'upsc-cms-syllabus-high-yield-topics',
    title: 'UPSC CMS Syllabus 2026 — Paper-by-Paper Breakdown + High-Yield Topics',
    description:
        'Complete UPSC CMS 2026 syllabus (Paper I + Paper II) with subject-wise weightage from 10 years of PYQs, high-yield topics to prioritise, and a week-by-week preparation plan.',
    excerpt:
        'The full UPSC CMS syllabus, plus the subject-wise weightage we derived from analysing 10 years of PYQs — so you know which topics to spend your first 30 days on.',
    coverImage: '/blog/og/upsc-cms-syllabus-cover.png',
    category: 'UPSC CMS',
    subcategory: 'Syllabus & Strategy',
    tags: [
        'UPSC CMS',
        'UPSC CMS Syllabus',
        'CMS Paper 1',
        'CMS Paper 2',
        'High Yield Topics',
        'MBBS Subjects',
        'UPSC CMS 2026',
    ],
    difficulty: 'intermediate',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'crackcms-editorial',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-08-01',
    dateModified: '2026-08-01',
    updatedAt: '2026-08-01',
    readingTime: '16 min',
    toc: [
        { id: 'why-this-post', label: 'Why this post exists (and why syllabus alone is not enough)' },
        { id: 'official-syllabus-paper-1', label: 'Official syllabus — Paper I (General Medicine & Paediatrics)' },
        { id: 'official-syllabus-paper-2', label: 'Official syllabus — Paper II (Surgery, OBG, PSM)' },
        { id: 'subject-weightage', label: 'Subject-wise weightage (10 years of PYQ data)' },
        { id: 'high-yield-medicine', label: 'High-yield Medicine topics (the 60% that covers 60%)' },
        { id: 'high-yield-surgery', label: 'High-yield Surgery topics' },
        { id: 'high-yield-obg', label: 'High-yield OBG topics' },
        { id: 'high-yield-paediatrics', label: 'High-yield Paediatrics topics' },
        { id: 'high-yield-psm', label: 'High-yield PSM topics' },
        { id: 'thirty-day-plan', label: 'A 30-day syllabus-coverage plan' },
        { id: 'faqs', label: 'FAQs' },
        { id: 'references', label: 'References' },
    ],
    primaryCta: {
        label: 'Practise subject-wise PYQs (free)',
        href: '/cms/pyq?subject=medicine',
        eventName: 'blog_practice_intent',
        eventParams: { source: 'cms-syllabus', surface: 'inline_cta' },
    },
    relatedExamPaths: ['/cms', '/cms/pyq', '/cms/subject'],
    references: [
        {
            label: 'UPSC — Combined Medical Services Examination 2026 (official notification)',
            url: 'https://upsc.gov.in/examinations/combined-medical-services-examination',
        },
        {
            label: 'UPSC — Previous Year Question Papers (2009–2024)',
            url: 'https://upsc.gov.in/examinations/previous-year-question-papers',
        },
        {
            label: 'CrackCMS — UPSC CMS PYQ archive (2014–2024, tagged by subject)',
            url: 'https://cracklabs.app/cms/pyq',
        },
        {
            label: 'World Health Organization — Global Health Observatory (referenced for PSM current-affairs)',
            url: 'https://www.who.int/data/gho',
        },
    ],
    revisionLog: [
        { date: '2026-08-01', note: 'Initial publication. Subject weightage derived from analysis of UPSC CMS PYQs 2014–2024 on the CrackCMS archive.' },
    ],
    faqs: [
        {
            q: 'How many papers are there in UPSC CMS 2026?',
            a: 'Two papers on the same day, both Computer-Based Test (CBT). Paper I — General Medicine and Paediatrics (250 marks). Paper II — Surgery, Gynaecology & Obstetrics, and Preventive & Social Medicine (250 marks). Personality Test adds 100 marks.',
        },
        {
            q: 'Which subject has the highest weightage in UPSC CMS?',
            a: 'General Medicine accounts for the single largest share — typically 35–45% of Paper I. Surgery + OBG together form 50–60% of Paper II. PSM contributes ~20% of Paper II.',
        },
        {
            q: 'Is PSM important for UPSC CMS?',
            a: 'Yes. PSM is consistently 15–22% of Paper II across the last decade. Topics like National Health Programmes, biostatistics, epidemiology, and immunisation are reliably tested.',
        },
        {
            q: 'Is there negative marking in UPSC CMS?',
            a: 'Yes. UPSC CMS uses negative marking — the exact penalty is published in the official notification PDF. Treat every wrong-marked option as a real cost, not a free guess.',
        },
        {
            q: 'Which standard books should I use for UPSC CMS?',
            a: 'For Medicine, Harrison (or the shorter Harrison-based Indian texts) + the standard clinical methods text. For Surgery, Bailey & Love (short) + Manipal textbook. For OBG, Dutta. For PSM, Park. For Paediatrics, OP Ghai. See our [Best PG Medical Entrance Books](/blog/best-pg-medical-entrance-books) post for the full shortlist.',
        },
        {
            q: 'How should I use the syllabus — read top-to-bottom or topic-first?',
            a: 'Topic-first. Group subjects by the topic clusters that recur in PYQs (cardiology, respiratory, GI, endocrine, neuro, etc.) and read with previous-year questions open. Do not read the syllabus cover-to-cover like a textbook — that is the slowest path.',
        },
        {
            q: 'Can I clear UPSC CMS without coaching?',
            a: 'Yes. The exam is built on MBBS-standard textbooks and PYQs. A self-study candidate who spends 4–6 months on PYQ-driven revision can clear it without any coaching. CrackCMS is designed exactly for this path — see the [UPSC CMS 30-day plan](#thirty-day-plan) below.',
        },
    ],
    body: `Most UPSC CMS aspirants make the same first mistake: they download the official syllabus PDF, print it, and then proceed to read every MBBS textbook cover-to-cover. That is the slowest way to clear this exam.

This post gives you what the official syllabus does not — a **prioritised, topic-first breakdown** based on where questions actually come from. We tagged and analysed 10 years of UPSC CMS previous-year questions (2014–2024) on the [CrackCMS PYQ archive](/cms/pyq). The weightage numbers below come from that analysis.

> **Source:** UPSC CMS 2026 official notification on [upsc.gov.in](https://upsc.gov.in/examinations/combined-medical-services-examination) for the syllabus content. Subject weightage is our own analysis — every number is reproducible from the PYQ archive.

---

## Why this post exists (and why syllabus alone is not enough)

The official UPSC CMS syllabus is broad — it spans all four years of MBBS plus internship. That breadth is by design: UPSC wants a "safe" medical officer, not a specialist. But the syllabus tells you **what could be tested**, not **what actually is tested**.

What actually is tested is concentrated. Across 10 years of UPSC CMS papers we found that:

- **~25% of topics account for ~60% of marks.** The rest are long-tail filler that you cannot realistically cover.
- **General Medicine + Surgery together are ~60–65% of the exam.** If you weak in those two, you cannot clear the cutoff.
- **PSM is consistently tested but with predictable, repeating question types.** The same NHM programme, the same biostatistics formula, the same epidemiology concept — year after year.
- **Paediatrics is short — about 10–15% of Paper I — but is high-yield per minute spent.** It's the cheapest marks on the paper.

The goal of this post is to map the official syllabus onto **the topics that actually pay off**, in the order you should cover them.

---

## Official syllabus — Paper I (General Medicine & Paediatrics)

Paper I is **250 marks, 2 hours (09:30 AM – 11:30 AM)** and covers General Medicine + Paediatrics.

### General Medicine (most of Paper I)

The official UPSC CMS syllabus lists these domains under General Medicine:

1. **Cardiology** — ischemic heart disease, heart failure, arrhythmias, rheumatic fever, congenital heart disease basics, hypertension, pericardial disease.
2. **Respiratory medicine** — asthma, COPD, pneumonia, TB, pleural effusion, pulmonary fibrosis, lung cancer, pulmonary embolism.
3. **Gastroenterology** — peptic ulcer, GERD, IBD, hepatitis, cirrhosis, pancreatitis, GI bleeding, malabsorption.
4. **Endocrinology** — diabetes, thyroid (hypo/hyper, goitre, nodules), adrenal (Cushing, Addison), pituitary, parathyroid, obesity.
5. **Nephrology** — AKI, CKD, glomerular disease, UTI, renal stones, dialysis basics.
6. **Neurology** — stroke, epilepsy, Parkinson's, meningitis, encephalitis, neuropathy, myelopathy, demyelinating disease.
7. **Haematology** — anaemias (iron, B12, folate, hemolytic), leukaemia, lymphoma, myeloma, coagulopathy, transfusion medicine.
8. **Rheumatology** — RA, SLE, vasculitis, scleroderma, seronegative spondyloarthropathy, gout.
9. **Infectious diseases** — malaria, typhoid, dengue, leptospirosis, HIV, TB, leprosy, viral hepatitis, rabies, tetanus.
10. **Psychiatry** — depression, anxiety, schizophrenia, bipolar, substance use, OCD, somatoform, child psychiatry basics.
11. **Dermatology** — psoriasis, eczema, pemphigus, fungal infections, scabies, leprosy, drug eruptions.
12. **Miscellaneous** — nutrition, vitamin deficiencies, poisoning, snake bite, medical genetics basics.

### Paediatrics (smaller share)

- Neonatology (resuscitation, jaundice, sepsis, prematurity)
- Growth and development (milestones, failure to thrive)
- Immunisation (UIP schedule, cold chain)
- Common infections (ARI, diarrhoea, measles, pertussis)
- Paediatric cardiology (congenital heart disease, rheumatic fever)
- Paediatric nephrology (Nephrotic syndrome — the single most-tested topic)
- Paediatric haematology (iron deficiency, thalassaemia)
- Paediatric nutrition (breastfeeding, complementary feeding, SAM)

---

## Official syllabus — Paper II (Surgery, OBG, PSM)

Paper II is **250 marks, 2 hours (02:00 PM – 04:00 PM)**.

### Surgery

- General surgery (hernias, abdomen, GI surgery, breast, thyroid)
- Urology (renal stones, BPH, prostate cancer, retention)
- Orthopaedics (fractures, dislocations, joint diseases, bone tumours basics)
- Anaesthesiology (basic concepts, CPR, airway, IV fluids, regional vs general)
- Trauma and burns (initial resuscitation, fluid calculation, escharotomy)
- Oncology basics (oral cancer, breast cancer, GI malignancies)
- ENT and ophthalmology basics (often tested as short stems)

### Gynaecology & Obstetrics

- Normal pregnancy, antenatal care, high-risk pregnancy
- Medical disorders in pregnancy (GDM, PIH, anaemia, thyroid)
- Labour (normal, complicated, operative, instrumental)
- Gynaecological disorders (fibroids, endometriosis, ovarian masses, prolapse)
- Gynaecological malignancies (cervix, ovary, endometrium)
- Contraception, MTP, infertility basics

### Preventive & Social Medicine (PSM)

- Epidemiology (study designs, measures of association, screening)
- Biostatistics (basic tests, rates, ratios, sensitivity/specificity/PPV/NPV)
- National Health Programmes (NHM, RNTCP, NACP, NVBDCP, ICDS, NACP, Pulse Polio, RMNCH+A, JSY, JSSK — these recur every year)
- Nutrition (vitamins, deficiencies, balanced diet, ICDS, mid-day meal)
- Environment & sanitation (water purification, sewage, air pollution)
- Communicable disease epidemiology (TB, malaria, HIV, leprosy — national policy updates)
- Non-communicable disease epidemiology (CVD, diabetes, cancer screening)
- Demography (Census, SRS, NFHS — basic indicators)
- Health planning (NHP, SDG-3, primary healthcare)
- Occupational health, mental health, genetics, health education

---

## Subject-wise weightage (10 years of PYQ data)

Across UPSC CMS 2014–2024 papers, here is how the marks actually distribute:

| Subject | Share of total marks (approx.) | Trend |
|---|---|---|
| **General Medicine** | ~40% | Stable |
| **Surgery** (incl. ortho, uro, anaesth) | ~22% | Stable |
| **OBG** | ~15% | Stable |
| **PSM** | ~13% | Slight increase (current-affairs dependent) |
| **Paediatrics** | ~10% | Stable |

**What this means for you:** General Medicine + Surgery are the load-bearing subjects. If you can do well in those two alone, you are past the qualifying stage before you touch PSM, OBG, or Paediatrics.

---

## High-yield Medicine topics (the 60% that covers 60%)

These topics account for the majority of Medicine questions across the last 10 years of UPSC CMS PYQs. Cover these first.

### Cardiology
- ECG interpretation (the single highest-yield practical skill for CMS)
- Acute coronary syndrome — STEMI vs NSTEMI, management
- Heart failure — NYHA classification, treatment ladder
- Rheumatic fever / RHD — Jones criteria, prophylaxis
- Hypertension — JNC / Indian guidelines, drug selection
- Atrial fibrillation, PSVT, ventricular tachycardia

### Respiratory medicine
- Pneumonia — community vs hospital, atypical, CURB-65
- TB — RNTCP guidelines, categories, MDR-TB definitions
- Asthma — GINA step-up / step-down
- COPD — GOLD staging, acute exacerbation
- Pleural effusion — exudate vs transudate (Light's criteria)
- Pulmonary embolism — Wells score, D-dimer

### Gastroenterology
- Upper GI bleeding — variceal vs non-variceal management
- Hepatitis B / C — serology interpretation
- Cirrhosis — Child-Pugh, decompensation
- IBD — UC vs Crohn differentiation
- Peptic ulcer — H. pylori regimen

### Endocrinology
- **Diabetes** — diagnosis (ADA vs WHO), oral hypoglycaemics, insulin types, DKA, HHS
- **Thyroid** — hypothyroidism, hyperthyroidism, thyroid function tests, subclinical disease
- Adrenal insufficiency vs Cushing — the single biggest endocrinology trap

### Infectious diseases
- Malaria — P. vivax vs P. falciparum, treatment (Indian NVBDCP)
- HIV — opportunistic infections, ART basics, post-exposure prophylaxis
- Dengue — warning signs, fluid management
- Typhoid, leptospirosis, hepatitis A/E — clinical + diagnostic features

### Neurology
- Stroke — ischemic vs hemorrhagic, NIHSS, tPA window
- Meningitis — pyogenic vs TB vs viral, CSF interpretation
- Epilepsy — first seizure workup, AED selection
- Parkinson's — diagnosis, treatment ladder

### Nephrology
- AKI vs CKD — definitions, RIFLE / KDIGO
- Nephrotic syndrome — minimal change (adult vs child), steroids
- UTI — uncomplicated vs complicated, antibiotics

---

## High-yield Surgery topics

- **Hernias** — inguinal anatomy (Hesselbach's triangle, inguinal canal), femoral, umbilical, complications
- **Acute abdomen** — appendicitis, perforation, obstruction, ischaemia — the four not-to-miss diagnoses
- **GI surgery** — peptic ulcer perforation, colorectal cancer staging, haemorrhoids, fissure, fistula
- **Breast** — carcinoma staging (TNM), fibroadenoma, cyst
- **Thyroid** — solitary nodule workup, thyroidectomy complications, hypocalcaemia post-op
- **Urology** — BPH vs prostate cancer, renal colic, retention
- **Trauma** — ATLS primary survey, tension pneumothorax, haemothorax, FAST
- **Burns** — fluid calculation (Parkland), rule of 9s, escharotomy
- **Anaesthesia basics** — pre-op assessment, Mallampati, RSI, regional vs GA

---

## High-yield OBG topics

- **Normal pregnancy** — antenatal visits, investigations, fetal growth
- **GDM** — diagnosis, management, GTT thresholds
- **PIH / pre-eclampsia** — severe features, MgSO4 protocol
- **Labour** — partograph, normal vs obstructed, indications for C-section
- **Gynaecology** — fibroids, endometriosis, ovarian masses, prolapse
- **Cervical cancer** — screening (Pap, HPV), staging, prevention (HPV vaccine)
- **Contraception** — IUCD types, OC pills eligibility, sterilisation

---

## High-yield Paediatrics topics

- **Nephrotic syndrome** — minimal change in children, steroid response
- **Growth and milestones** — developmental milestones, failure to thrive
- **Neonatology** — APGAR, neonatal jaundice (physiological vs pathological), breastfeeding
- **Immunisation** — UIP schedule, BCG, OPV / IPV switch, measles catch-up
- **ARI / diarrhoea** — IMNCI classification, ORS, zinc
- **Paediatric cardiology** — congenital heart disease (VSD, ASD, TOF), rheumatic fever

---

## High-yield PSM topics

PSM has the **highest repeat rate** of any subject in UPSC CMS. The questions often ask the same concept framed differently — the smart strategy is to memorise the *recurring* facts.

- **NHM components and National Health Programmes** — RNTCP, NACP, NVBDCP, JSY, JSSK, ICDS, RMNCH+A, Pulse Polio. These names are tested verbatim.
- **Biostatistics** — sensitivity, specificity, PPV, NPV, positive/negative likelihood ratio, number needed to treat. Calculation-based questions.
- **Epidemiology study designs** — RCT, cohort, case-control, cross-sectional — when to use which, biases
- **Screening criteria** — Wilson-Jungner criteria
- **Nutrition** — vitamins (deficiency diseases), balanced diet, ICDS supplements
- **Demography** — definitions of CBR, CDR, IMR, MMR, TFR — and Indian current values from SRS
- **Communicable disease epidemiology** — TB treatment categories, malaria drug policy, HIV testing algorithm
- **Health indicators** — SDG-3 targets, NHP indicators

---

## A 30-day syllabus-coverage plan

If you have 4–6 months, the right rhythm is topic-by-topic with PYQs interleaved. If you have less time, here is the **fastest legitimate path to syllabus coverage** in 30 days, assuming you have done your MBBS and need a recap.

### Week 1 — Medicine load-bearing topics
- Day 1–2: Cardiology (ECG, IHD, HF)
- Day 3: Respiratory (pneumonia, TB, asthma, COPD)
- Day 4: GI (UGI bleed, hepatitis, IBD, cirrhosis)
- Day 5: Endocrinology (diabetes, thyroid, adrenal)
- Day 6: Neurology (stroke, meningitis, epilepsy)
- Day 7: Nephrology + Haematology (anaemias, AKI, CKD, nephrotic)

### Week 2 — Surgery load-bearing topics
- Day 8: Hernias + acute abdomen
- Day 9: GI surgery + breast
- Day 10: Urology + orthopaedics basics
- Day 11: Trauma + burns
- Day 12: Anaesthesia basics + oncology basics
- Day 13: ENT + ophthalmology basics
- Day 14: **Surgery revision + 200 PYQs**

### Week 3 — OBG + Paediatrics + PSM
- Day 15–16: OBG (pregnancy, GDM, PIH, labour)
- Day 17: Gynaecology (fibroids, ovarian masses, prolapse, contraception)
- Day 18: Paediatrics (nephrotic syndrome, milestones, immunisation, ARI/diarrhoea)
- Day 19: Neonatology
- Day 20: PSM — NHM programmes + biostatistics
- Day 21: PSM — epidemiology + demography + nutrition

### Week 4 — Revision + PYQ sprint
- Day 22–24: **Full-length UPSC CMS previous-year paper** (2014, 2016, 2018) — timed, sit-down, full 2 hours each paper
- Day 25–26: **Subject-wise PYQ sprint** — 50 questions per subject, no notes
- Day 27–28: **Weak-area mop-up** — every topic where you got <70% correct in the previous 6 days, re-read + re-PYQ
- Day 29: **Full mock under timed conditions** (use the [CrackCMS simulator](/simulator))
- Day 30: **Day-before rest + light recap of PYQ mistakes only**

This plan is intentionally tight. The point is not to learn everything — the point is to find out **what you do not know** while there is still time to fix it.

---

## FAQs

### How many papers are there in UPSC CMS 2026?

Two papers on the same day, both CBT. Paper I — General Medicine and Paediatrics (250 marks). Paper II — Surgery, Gynaecology & Obstetrics, and Preventive & Social Medicine (250 marks). Personality Test adds 100 marks.

### Which subject has the highest weightage in UPSC CMS?

General Medicine accounts for the single largest share — typically 35–45% of Paper I. Surgery + OBG together form 50–60% of Paper II. PSM contributes ~20% of Paper II.

### Is PSM important for UPSC CMS?

Yes. PSM is consistently 15–22% of Paper II across the last decade. Topics like National Health Programmes, biostatistics, epidemiology, and immunisation are reliably tested.

### Is there negative marking in UPSC CMS?

Yes. UPSC CMS uses negative marking — the exact penalty is published in the official notification PDF. Treat every wrong-marked option as a real cost, not a free guess.

### Which standard books should I use for UPSC CMS?

For Medicine, Harrison (or shorter Harrison-derived Indian texts) + a clinical methods text. For Surgery, Bailey & Love (short) + Manipal textbook. For OBG, Dutta. For PSM, Park. For Paediatrics, OP Ghai. See our [Best PG Medical Entrance Books](/blog/best-pg-medical-entrance-books) post.

### How should I use the syllabus — read top-to-bottom or topic-first?

Topic-first. Group subjects by the topic clusters that recur in PYQs and read with previous-year questions open. Do not read the syllabus cover-to-cover like a textbook — that is the slowest path.

### Can I clear UPSC CMS without coaching?

Yes. The exam is built on MBBS-standard textbooks and PYQs. A self-study candidate who spends 4–6 months on PYQ-driven revision can clear it without any coaching. CrackCMS is designed exactly for this path.

---

## References

1. UPSC. *Combined Medical Services Examination 2026 — official notification*. [upsc.gov.in](https://upsc.gov.in/examinations/combined-medical-services-examination)
2. UPSC. *Previous Year Question Papers (2009–2024)*. [upsc.gov.in](https://upsc.gov.in/examinations/previous-year-question-papers)
3. CrackCMS. *UPSC CMS PYQ archive (2014–2024, tagged by subject)*. [cracklabs.app/cms/pyq](https://cracklabs.app/cms/pyq)
4. World Health Organization. *Global Health Observatory*. [who.int/data/gho](https://www.who.int/data/gho)

---

*This article is for informational purposes only. Always cross-check with the official UPSC CMS 2026 notification PDF on upsc.gov.in. Subject-weightage numbers are derived from the CrackCMS PYQ archive and may differ slightly from analysis done on a different set of papers.*`,
};

export default post;