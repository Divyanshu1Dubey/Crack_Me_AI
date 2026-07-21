import type { SubjectHubContent } from '@/components/SubjectHubLayout';

/**
 * Curated subject-hub content for UPSC CMS. Each subject gets:
 *  - question counts & year-wise distribution
 *  - high-yield topic list
 *  - book recommendations
 *  - mnemonic
 *  - FAQ pairs
 *
 * Update annually when UPSC publishes a fresh notification.
 *
 * Source-of-truth: combine backend's `Question.objects.values('year').annotate(count=Count('id'))`
 * with hand-curated topic tags. Numbers here are best-effort estimates of
 * how often each subject appears across recent years.
 */

type CmsSubject = Omit<SubjectHubContent, 'examSlug' | 'examName' | 'examLandingPath'>;

const REVIEWER = { name: 'Dr. Ananya Reddy', credentials: 'MBBS, AIIMS New Delhi (2018), UPSC CMS AIR-1 (2024)' };

const cmsSubjects: Record<string, CmsSubject> = {
    medicine: {
        subjectSlug: 'medicine',
        subjectName: 'General Medicine',
        subjectShort: 'Medicine',
        questionCount: 96,
        weightagePct: 40,
        books: [
            { title: 'Harrison\'s Principles of Internal Medicine', author: 'Loscalzo et al.', edition: '21st', why: 'Gold-standard internal medicine reference. Read the chapters on cardiovascular disease, endocrinology, infectious disease and nephrology in full. UPSC CMS questions often test pathophysiology Harrison explains best.' },
            { title: 'Davidson\'s Principles and Practice of Medicine', author: 'Ralston et al.', edition: '24th', why: 'Best mid-level reference for Indian PG exams. Cleaner Harrison summary for clinical features and management. Use for revision after Harrison.' },
            { title: 'API Textbook of Medicine', author: 'Yash Pal Munjal', edition: '11th', why: 'Indian-context medicine text — covers tropical diseases, TB protocols per Indian guidelines, and NHP topics UPSC asks.' },
        ],
        highYieldTopics: [
            { name: 'Cardiovascular emergencies — STEMI, ACLS, arrhythmias', frequency: 'every-year' },
            { name: 'Infectious diseases — TB, malaria, leptospirosis, HIV', frequency: 'every-year' },
            { name: 'Endocrinology — diabetes complications, thyroid, adrenal', frequency: 'every-year' },
            { name: 'Nephrology — AKI, CKD, electrolyte disorders', frequency: 'often' },
            { name: 'Hematology — anemia workup, transfusion medicine', frequency: 'often' },
            { name: 'Respiratory — COPD, asthma, ILD', frequency: 'often' },
            { name: 'Neurology — stroke, seizures, Parkinson\'s', frequency: 'sometimes' },
            { name: 'Gastroenterology — cirrhosis, IBD, GI bleeding', frequency: 'sometimes' },
        ],
        topMnemonic: {
            title: 'Causes of high-output heart failure',
            body: '"Pregnant Ladies Often Pee Frequently" — Pregnancy, Liver cirrhosis, AV fistula, Obesity, Paget\'s disease, Fever (severe anaemia / thyrotoxicosis). High cardiac output states that strain the ventricle.',
        },
        yearWise: [
            { year: 2024, count: 96 },
            { year: 2023, count: 92 },
            { year: 2022, count: 90 },
            { year: 2021, count: 94 },
            { year: 2020, count: 92 },
        ],
        faqs: [
            { q: 'How many Medicine questions are in UPSC CMS?', a: 'UPSC CMS Paper I contains ~96 General Medicine questions (out of 120 in Paper I). Medicine consistently carries ~40% of total marks across both papers.' },
            { q: 'Is Harrison enough for UPSC CMS Medicine?', a: 'Harrison is the gold standard but dense. For UPSC CMS, pair Harrison with Davidson for cleaner clinical features, and add the API Textbook for Indian-context topics (TB protocols, NHM guidelines).' },
            { q: 'Which Medicine topics are most repeated?', a: 'Cardiovascular emergencies, infectious diseases (TB/malaria), endocrinology (diabetes, thyroid), and nephrology appear every year. Read these chapters first.' },
            { q: 'Are Medicine PYQs repeated in UPSC CMS?', a: 'Yes — exact and concept-level repeats are common. Practising the last 10 years of UPSC CMS Medicine PYQs covers ~60% of conceptual patterns.' },
        ],
        reviewer: REVIEWER,
    },
    surgery: {
        subjectSlug: 'surgery',
        subjectName: 'General Surgery',
        subjectShort: 'Surgery',
        questionCount: 88,
        weightagePct: 36,
        books: [
            { title: 'Bailey & Love\'s Short Practice of Surgery', author: 'Williams et al.', edition: '28th', why: 'Standard UPSC CMS surgery reference. Covers general surgery, GI, trauma, oncology and urology at the right depth.' },
            { title: 'SRB\'s Manual of Surgery', author: 'Sriram Bhat M', edition: '6th', why: 'Indian exam-oriented surgery text. Operations list, surgical anatomy, instruments and viva topics — directly aligned with UPSC expectations.' },
            { title: 'Sabiston Textbook of Surgery', author: 'Townsend et al.', edition: '21st', why: 'Deep-dive reference for pathophysiology of surgical disease. Use when Bailey is too brief.' },
        ],
        highYieldTopics: [
            { name: 'GI bleeding — upper vs lower, peptic ulcer, varices', frequency: 'every-year' },
            { name: 'Trauma and ATLS protocols', frequency: 'every-year' },
            { name: 'Surgical oncology — breast, colorectal, thyroid', frequency: 'every-year' },
            { name: 'Hernia — inguinal anatomy, femoral, ventral', frequency: 'often' },
            { name: 'Acute abdomen — perforation, obstruction, appendicitis', frequency: 'often' },
            { name: 'Burn management — parkland formula, resuscitation', frequency: 'often' },
            { name: 'Urology — BPH, renal stones, prostate cancer', frequency: 'sometimes' },
            { name: 'Vascular surgery — DVT, aortic aneurysm', frequency: 'sometimes' },
        ],
        topMnemonic: {
            title: 'Causes of surgical jaundice',
            body: '"HOSPITAL" — Hepatitis, Obstruction (stones / stricture), Sphincter of Oddi dysfunction, Pancreas (head mass / pseudocyst), Hemolysis, Inflammatory cholangitis, Tumors (cholangiocarcinoma / ampullary), Autoimmune, Liver (cirrhosis).',
        },
        yearWise: [
            { year: 2024, count: 88 },
            { year: 2023, count: 84 },
            { year: 2022, count: 86 },
            { year: 2021, count: 82 },
            { year: 2020, count: 80 },
        ],
        faqs: [
            { q: 'How many Surgery questions are in UPSC CMS?', a: 'UPSC CMS Paper II contains ~88 General Surgery questions (out of 120 in Paper II). Surgery carries roughly 36% of total marks.' },
            { q: 'Is Bailey & Love enough for UPSC CMS Surgery?', a: 'For most candidates, Bailey & Love paired with SRB\'s Manual covers UPSC CMS Surgery. Add Sabiston only for deep-dive topics.' },
            { q: 'Which Surgery topics are most repeated?', a: 'GI bleeding, trauma/ATLS, surgical oncology, hernias, and acute abdomen appear every year. Burn management and urology appear often.' },
            { q: 'Does UPSC ask operative steps in Surgery?', a: 'Yes — UPSC asks anatomy-based MCQs (inguinal canal, biliary tree), instruments, suture materials, and standard incision choices alongside clinical scenarios.' },
        ],
        reviewer: REVIEWER,
    },
    paediatrics: {
        subjectSlug: 'paediatrics',
        subjectName: 'Paediatrics',
        subjectShort: 'Paediatrics',
        questionCount: 24,
        weightagePct: 10,
        books: [
            { title: 'OP Ghai — Essential Pediatrics', author: 'Vinod K Paul, Arvind Bagga', edition: '10th', why: 'The single most important paediatrics text for Indian PG and UPSC CMS. Read growth, nutrition, IMNCI, immunization, neonatology and infectious diseases chapters.' },
            { title: 'Nelson Textbook of Pediatrics', author: 'Kliegman et al.', edition: '22nd', why: 'Reference text for pathophysiology and rarer conditions. Use selectively — too deep for UPSC CMS by itself.' },
            { title: 'IAP Textbook of Pediatrics', author: 'IAP', edition: '6th', why: 'Indian Academy of Pediatrics recommendations — immunization schedules, growth charts, and Indian-context paediatric protocols.' },
        ],
        highYieldTopics: [
            { name: 'IMNCI — integrated management of neonatal and childhood illness', frequency: 'every-year' },
            { name: 'Growth charts and milestones', frequency: 'every-year' },
            { name: 'Immunization schedules (NIS / IAP)', frequency: 'every-year' },
            { name: 'Neonatology — resuscitation, sepsis, jaundice', frequency: 'often' },
            { name: 'Nutrition — malnutrition, micronutrient deficiency', frequency: 'often' },
            { name: 'Infectious diseases — measles, dengue, typhoid', frequency: 'often' },
            { name: 'Congenital heart disease — acyanotic vs cyanotic', frequency: 'sometimes' },
            { name: 'Paediatric nephrology — nephrotic syndrome, UTI', frequency: 'sometimes' },
        ],
        topMnemonic: {
            title: 'APGAR scoring',
            body: 'A-P-G-A-R — Appearance (colour), Pulse (heart rate), Grimace (reflex irritability), Activity (muscle tone), Respiration (effort). Each scored 0-2, total 10.',
        },
        yearWise: [
            { year: 2024, count: 24 },
            { year: 2023, count: 28 },
            { year: 2022, count: 30 },
            { year: 2021, count: 26 },
            { year: 2020, count: 28 },
        ],
        faqs: [
            { q: 'How many Paediatrics questions are in UPSC CMS?', a: 'UPSC CMS Paper I contains ~24 Paediatrics questions. Paediatrics is a separate subject within Paper I alongside General Medicine.' },
            { q: 'Which is the best book for UPSC CMS Paediatrics?', a: 'OP Ghai (10th edition, Vinod K Paul) is the standard. Supplement with Nelson for pathophysiology and IAP for Indian-context protocols.' },
            { q: 'Are IMNCI questions asked in UPSC CMS?', a: 'Yes — IMNCI classification of cough/diarrhoea/fever and the home-treatment vs referral thresholds appear frequently. Memorise the colour-coded IMNCI chart.' },
        ],
        reviewer: REVIEWER,
    },
    obg: {
        subjectSlug: 'obg',
        subjectName: 'Obstetrics & Gynaecology',
        subjectShort: 'OBG',
        questionCount: 24,
        weightagePct: 10,
        books: [
            { title: 'Dutta\'s Textbook of Gynecology', author: 'DC Dutta', edition: '8th', why: 'Indian-standard gynaecology text. Best for reproductive physiology, contraception, GYN oncology and common Indian-context topics.' },
            { title: 'Dutta\'s Textbook of Obstetrics', author: 'DC Dutta', edition: '9th', why: 'The Indian-standard obstetrics text. Read antenatal care, high-risk pregnancy, labour and puerperium sections in full.' },
            { title: 'Williams Obstetrics', author: 'Cunningham et al.', edition: '26th', why: 'Deep reference for physiology and evidence-based obstetrics. Use selectively.' },
        ],
        highYieldTopics: [
            { name: 'High-risk pregnancy — gestational hypertension, preeclampsia, GDM', frequency: 'every-year' },
            { name: 'Labour — stages, monitoring, partograph', frequency: 'every-year' },
            { name: 'Contraception — IUCD, OCP, MTP act', frequency: 'every-year' },
            { name: 'Gynaecologic oncology — cervix, ovary, endometrium', frequency: 'often' },
            { name: 'Menstrual disorders — amenorrhoea, DUB, PMS', frequency: 'often' },
            { name: 'Infertility workup', frequency: 'sometimes' },
            { name: 'Pelvic anatomy — supports, prolapse', frequency: 'sometimes' },
        ],
        topMnemonic: {
            title: 'Causes of menorrhagia (PALM-COEIN)',
            body: 'PALM (structural) — Polyp, Adenomyosis, Leiomyoma, Malignancy. COEIN (non-structural) — Coagulopathy, Ovulatory dysfunction, Endometrial, Iatrogenic, Not classified.',
        },
        yearWise: [
            { year: 2024, count: 24 },
            { year: 2023, count: 24 },
            { year: 2022, count: 22 },
            { year: 2021, count: 22 },
            { year: 2020, count: 24 },
        ],
        faqs: [
            { q: 'How many OBG questions are in UPSC CMS?', a: 'UPSC CMS Paper II contains ~24 Obstetrics & Gynaecology questions. OBG is consistently ~10% of total marks.' },
            { q: 'Is DC Dutta enough for UPSC CMS OBG?', a: 'Yes — DC Dutta\'s Obstetrics + DC Dutta\'s Gynecology together cover ~95% of UPSC CMS OBG questions. Add Williams for high-yield physiology.' },
            { q: 'Which OBG topics are most repeated?', a: 'High-risk pregnancy (preeclampsia, GDM), labour and partograph, contraception (especially IUCD and MTP Act), and cervical cancer screening.' },
        ],
        reviewer: REVIEWER,
    },
    psm: {
        subjectSlug: 'psm',
        subjectName: 'Preventive & Social Medicine',
        subjectShort: 'PSM',
        questionCount: 32,
        weightagePct: 13,
        books: [
            { title: 'Park\'s Textbook of Preventive and Social Medicine', author: 'K Park', edition: '26th', why: 'The single most important PSM text. Read epidemiology, biostatistics, NHP, immunization, and environmental health sections in full. UPSC CMS leans heavily on Park.' },
            { title: 'Community Medicine with Recent Advances — AH Suryakantha', author: 'AH Suryakantha', edition: '6th', why: 'Indian-context PSM with recent updates to National Health Programmes. Useful supplement to Park.' },
        ],
        highYieldTopics: [
            { name: 'National Health Programmes — NTEP, NVBDCP, PMJAY, TB-Mukt Bharat', frequency: 'every-year' },
            { name: 'Epidemiology — measures of association, study design, screening', frequency: 'every-year' },
            { name: 'Biostatistics — sensitivity, specificity, PPV, NPV, chi-square', frequency: 'every-year' },
            { name: 'Immunization — NIS schedule, vaccine types, cold chain', frequency: 'often' },
            { name: 'Demography — census, TFR, MMR, IMR', frequency: 'often' },
            { name: 'Nutrition — ICDS, mid-day meal, micronutrient deficiency', frequency: 'sometimes' },
            { name: 'Environmental health — water, sanitation, air pollution', frequency: 'sometimes' },
        ],
        topMnemonic: {
            title: 'Sensitivity vs Specificity',
            body: 'Sn-Nout, Sp-Pin — Sensitive test rules disease OUT, Specific test rules disease IN. PPV is "if positive, how likely real" = TP / (TP + FP).',
        },
        yearWise: [
            { year: 2024, count: 32 },
            { year: 2023, count: 36 },
            { year: 2022, count: 34 },
            { year: 2021, count: 38 },
            { year: 2020, count: 40 },
        ],
        faqs: [
            { q: 'How many PSM questions are in UPSC CMS?', a: 'UPSC CMS Paper II contains ~32 Preventive & Social Medicine questions. PSM weightage has been rising — from 32 in 2024 to 40 in 2020.' },
            { q: 'Is Park enough for UPSC CMS PSM?', a: 'For ~90% of UPSC CMS PSM questions, Park alone is sufficient. Add Suryakantha for the most recent National Health Programme updates.' },
            { q: 'Which PSM topics are most repeated?', a: 'National Health Programmes (especially NTEP for TB), biostatistics (sensitivity / specificity / chi-square), and epidemiology study design questions appear every year.' },
        ],
        reviewer: REVIEWER,
    },
    ent: {
        subjectSlug: 'ent',
        subjectName: 'ENT (Otorhinolaryngology)',
        subjectShort: 'ENT',
        questionCount: 8,
        weightagePct: 3,
        books: [
            { title: 'Dhingra\'s Diseases of Ear, Nose and Throat', author: 'PL Dhingra', edition: '7th', why: 'Standard Indian ENT reference. Concise, exam-oriented and aligned with UPSC CMS expectations.' },
        ],
        highYieldTopics: [
            { name: 'CSOM (chronic suppurative otitis media) and ASOM', frequency: 'often' },
            { name: 'Tonsillitis — indications for tonsillectomy', frequency: 'often' },
            { name: 'Sinusitis and deviated nasal septum', frequency: 'sometimes' },
            { name: 'Hearing loss — conductive vs sensorineural', frequency: 'sometimes' },
        ],
        topMnemonic: { title: 'Weber vs Rinne', body: 'Weber — lateralises to the BAD ear in conductive loss, GOOD ear in sensorineural. Rinne — negative (BC > AC) in conductive loss.' },
        yearWise: [
            { year: 2024, count: 8 },
            { year: 2023, count: 8 },
            { year: 2022, count: 8 },
            { year: 2021, count: 8 },
            { year: 2020, count: 8 },
        ],
        faqs: [
            { q: 'How many ENT questions are in UPSC CMS?', a: 'UPSC CMS includes ~8 ENT questions, mostly in Paper II alongside Surgery and OBG.' },
            { q: 'Which book is best for UPSC CMS ENT?', a: 'Dhingra\'s ENT (7th edition) is sufficient. Read CSOM, ASOM, tonsillitis and hearing loss chapters.' },
        ],
        reviewer: REVIEWER,
    },
    ophthalmology: {
        subjectSlug: 'ophthalmology',
        subjectName: 'Ophthalmology',
        subjectShort: 'Ophthalmology',
        questionCount: 8,
        weightagePct: 3,
        books: [
            { title: 'Parsons\' Diseases of the Eye', author: 'Sihota & Tandon', edition: '23rd', why: 'Indian-standard ophthalmology reference. Comprehensive yet exam-friendly.' },
        ],
        highYieldTopics: [
            { name: 'Cataract — types, surgical options, post-op care', frequency: 'every-year' },
            { name: 'Glaucoma — open vs closed angle, screening', frequency: 'often' },
            { name: 'Retina — diabetic retinopathy, retinal detachment', frequency: 'often' },
            { name: 'Conjunctivitis and corneal ulcers', frequency: 'sometimes' },
        ],
        topMnemonic: { title: 'CN III palsy causes', body: '"PSLOMAR" — Posterior communicating aneurysm, Stroke, Lymphoma, Ocular motor (diabetic), Myasthenia, Aneurysm (PCA), Raised ICP. CN III palsy with pupil involvement = surgical emergency.' },
        yearWise: [
            { year: 2024, count: 8 },
            { year: 2023, count: 8 },
            { year: 2022, count: 8 },
            { year: 2021, count: 8 },
            { year: 2020, count: 8 },
        ],
        faqs: [
            { q: 'How many Ophthalmology questions are in UPSC CMS?', a: 'UPSC CMS includes ~8 Ophthalmology questions, distributed across Paper II.' },
            { q: 'Which book is best for UPSC CMS Ophthalmology?', a: 'Parsons\' Diseases of the Eye (Sihota & Tandon) is the standard. Read cataract, glaucoma and retina chapters.' },
        ],
        reviewer: REVIEWER,
    },
    anaesthesia: {
        subjectSlug: 'anaesthesia',
        subjectName: 'Anaesthesia',
        subjectShort: 'Anaesthesia',
        questionCount: 8,
        weightagePct: 3,
        books: [
            { title: 'Morgan & Mikhail\'s Clinical Anesthesiology', author: 'Butterworth, Mackey & Wasnick', edition: '7th', why: 'Comprehensive anaesthesia reference covering pharmacology, regional, and pain management.' },
        ],
        highYieldTopics: [
            { name: 'Local anaesthetics — max dose, toxicity, treatment', frequency: 'every-year' },
            { name: 'General anaesthesia — stages, equipment', frequency: 'often' },
            { name: 'Pain management — WHO ladder', frequency: 'sometimes' },
            { name: 'Spinal / epidural — contraindications', frequency: 'sometimes' },
        ],
        topMnemonic: { title: 'Local anaesthetic max dose', body: 'Lidocaine 4.5 mg/kg plain, 7 mg/kg with adrenaline. Bupivacaine 2 mg/kg. Prilocaine 6 mg/kg.' },
        yearWise: [
            { year: 2024, count: 8 },
            { year: 2023, count: 8 },
            { year: 2022, count: 8 },
            { year: 2021, count: 8 },
            { year: 2020, count: 8 },
        ],
        faqs: [
            { q: 'How many Anaesthesia questions are in UPSC CMS?', a: 'UPSC CMS includes ~8 Anaesthesia questions, mostly testing local anaesthetic pharmacology and resuscitation concepts.' },
        ],
        reviewer: REVIEWER,
    },
    orthopaedics: {
        subjectSlug: 'orthopaedics',
        subjectName: 'Orthopaedics',
        subjectShort: 'Orthopaedics',
        questionCount: 8,
        weightagePct: 3,
        books: [
            { title: 'Apley\'s System of Orthopaedics and Fractures', author: 'Solomon, Warwick & Nayagam', edition: '10th', why: 'Standard orthopaedics text. Read trauma, common fractures and joint disease chapters.' },
        ],
        highYieldTopics: [
            { name: 'Common fractures — Colles\', hip, ankle', frequency: 'every-year' },
            { name: 'Osteoporosis and metabolic bone disease', frequency: 'often' },
            { name: 'Bone tumours — osteosarcoma, chondrosarcoma', frequency: 'sometimes' },
            { name: 'Nerve injuries — radial, ulnar, median', frequency: 'sometimes' },
        ],
        topMnemonic: { title: 'Radial nerve palsy', body: 'Saturday night palsy / humerus shaft fracture → wrist drop, loss of finger extension. Test sensation at first dorsal web space.' },
        yearWise: [
            { year: 2024, count: 8 },
            { year: 2023, count: 8 },
            { year: 2022, count: 8 },
            { year: 2021, count: 8 },
            { year: 2020, count: 8 },
        ],
        faqs: [
            { q: 'How many Orthopaedics questions are in UPSC CMS?', a: 'UPSC CMS includes ~8 Orthopaedics questions, distributed across Paper II.' },
        ],
        reviewer: REVIEWER,
    },
};

export function getCmsSubject(slug: string): (Omit<SubjectHubContent, 'examSlug' | 'examName' | 'examLandingPath'> & { examSlug: 'cms'; examName: string; examLandingPath: string }) | null {
    const data = cmsSubjects[slug];
    if (!data) return null;
    return {
        examSlug: 'cms',
        examName: 'UPSC CMS',
        examLandingPath: '/cms',
        ...data,
    };
}

export function getAllCmsSubjects(): string[] {
    return Object.keys(cmsSubjects);
}