import type { BookDeepDiveContent } from '@/components/BookDeepDiveLayout';

const REVIEWER = { name: 'Dr. Ananya Reddy', credentials: 'MBBS, AIIMS New Delhi (2018), UPSC CMS AIR-1 (2024)' };

export const CMS_BOOKS: Record<string, BookDeepDiveContent> = {
    harrison: {
        examSlug: 'cms', examName: 'UPSC CMS', examLandingPath: '/cms',
        bookSlug: 'harrison', bookTitle: "Harrison's Principles of Internal Medicine", bookAuthor: 'Loscalzo, Fauci, Kasper, Hauser, Longo, Jameson',
        bookEdition: '21st Edition',
        subjectName: 'General Medicine', subjectPath: '/cms/subject/medicine',
        verdict: "Harrison is the gold-standard internal medicine reference for UPSC CMS Paper I. Pick it for pathophysiology depth that no Indian text matches; pair with Davidson for clinical features.",
        shouldRead: [
            'You have ≥4 months until your CMS attempt',
            'You aim for AIR <500 (where Harrison-level depth shows)',
            'You want a single reference you can keep using through residency',
        ],
        canSkip: [
            'You are in the last 2 months before the exam',
            'You already cleared CMS once and only need revision',
            'You prefer Indian-context clinical texts (API / Davidson)',
        ],
        chapters: [
            { number: 1, title: 'Cardiovascular disease', weight: 'high', note: 'Highest yield — STEMI, ACLS, heart failure, arrhythmias. 18+ Qs per CMS paper.' },
            { number: 2, title: 'Endocrinology & metabolism', weight: 'high', note: 'Diabetes complications, thyroid disorders, adrenal axis. 12+ Qs.' },
            { number: 3, title: 'Infectious disease', weight: 'high', note: 'TB (India-specific regimens), HIV, malaria, leptospirosis, viral hepatitis. 14+ Qs.' },
            { number: 4, title: 'Nephrology', weight: 'high', note: 'AKI, CKD, glomerulonephritis, electrolyte disorders. 8-10 Qs.' },
            { number: 5, title: 'Hematology', weight: 'medium', note: 'Anemia workup, transfusion medicine, hematologic malignancies. 6-8 Qs.' },
            { number: 6, title: 'Respiratory', weight: 'medium', note: 'COPD, asthma, ILD, pulmonary embolism. 6 Qs.' },
            { number: 7, title: 'Neurology', weight: 'medium', note: 'Stroke, seizures, Parkinson\'s, MS. 5-6 Qs.' },
            { number: 8, title: 'Gastroenterology', weight: 'medium', note: 'Cirrhosis, IBD, GI bleeding. 5-6 Qs.' },
            { number: 9, title: 'Rheumatology & immunology', weight: 'low', note: 'SLE, RA, vasculitis. 2-3 Qs.' },
        ],
        schedule: [
            { week: 1, focus: 'Cardio + ECG interpretation', pages: 'pp. 1490-1760' },
            { week: 2, focus: 'Endo + nephro', pages: 'pp. 2200-2510' },
            { week: 3, focus: 'Infectious disease', pages: 'pp. 900-1280' },
            { week: 4, focus: 'Hematology + GI + revision', pages: 'pp. 700-900, 1880-2100' },
        ],
        pairWith: { title: "Davidson's Principles and Practice of Medicine (24th ed.)", why: 'Use Davidson as your first read for clinical features and management, then go back to Harrison for pathophysiology depth.' },
        faqs: [
            { q: 'Which Harrison edition for UPSC CMS?', a: 'The 21st edition is current (2025+) and aligned with NBE/UPSC expectations. 19th or 20th editions also work — Harrison changes slowly.' },
            { q: 'How many months to read Harrison?', a: 'A focused first read takes 6-8 weeks; revision pass takes 2-3 weeks. Budget 2.5-3 months total for Harrison before the exam.' },
            { q: 'Can I crack UPSC CMS with just Harrison?', a: 'Possible if you pair Harrison with a Park PSM text (Harrison doesn\'t cover PSM) and a Surgery text (Harrison is internal medicine only).' },
        ],
        reviewer: REVIEWER,
    },
    'bailey-love': {
        examSlug: 'cms', examName: 'UPSC CMS', examLandingPath: '/cms',
        bookSlug: 'bailey-love', bookTitle: "Bailey & Love's Short Practice of Surgery", bookAuthor: 'Williams, O\'Connell, McCaskie',
        bookEdition: '28th Edition',
        subjectName: 'General Surgery', subjectPath: '/cms/subject/surgery',
        verdict: "Bailey & Love is the standard UPSC CMS surgery reference — covers general surgery, GI, trauma and oncology at the right depth. Pair with SRB's Manual for instruments and viva topics.",
        shouldRead: [
            'You have ≥3 months until the exam',
            'You want a complete surgery reference in one volume',
            'You want to understand the "why" behind operative steps',
        ],
        canSkip: [
            'You only have 4-6 weeks (use SRB\'s Manual instead)',
            'You already own an older edition and only need updates',
        ],
        chapters: [
            { number: 1, title: 'GI surgery', weight: 'high', note: 'Upper GI bleed, peptic ulcer, colorectal cancer. 16+ Qs per CMS paper.' },
            { number: 2, title: 'Trauma & ATLS', weight: 'high', note: 'ATLS protocol, abdominal trauma, vascular injury. 12+ Qs.' },
            { number: 3, title: 'Hernia', weight: 'high', note: 'Inguinal anatomy, femoral hernia, ventral hernia repairs. 6-8 Qs.' },
            { number: 4, title: 'Surgical oncology', weight: 'high', note: 'Breast, thyroid, colorectal, gastric cancer staging. 10+ Qs.' },
            { number: 5, title: 'Acute abdomen', weight: 'high', note: 'Perforation, obstruction, appendicitis, pancreatitis. 10+ Qs.' },
            { number: 6, title: 'Burns', weight: 'medium', note: 'Parkland formula, resuscitation, escharotomy. 4-5 Qs.' },
            { number: 7, title: 'Urology', weight: 'medium', note: 'BPH, renal stones, prostate cancer. 4 Qs.' },
            { number: 8, title: 'Vascular surgery', weight: 'low', note: 'DVT, aortic aneurysm, varicose veins. 2-3 Qs.' },
        ],
        schedule: [
            { week: 1, focus: 'GI surgery + trauma', pages: 'pp. 1-260, 360-490' },
            { week: 2, focus: 'Hernia + oncology', pages: 'pp. 960-1080, 800-960' },
            { week: 3, focus: 'Acute abdomen + burns', pages: 'pp. 260-360, 490-560' },
            { week: 4, focus: 'Urology + vascular + revision', pages: 'pp. 1290-1450' },
        ],
        pairWith: { title: "SRB's Manual of Surgery (6th ed.)", why: 'SRB\'s is the Indian exam-oriented surgery text — operations list, instruments, suture materials, and viva questions. Use alongside Bailey.' },
        faqs: [
            { q: 'Which Bailey edition for UPSC CMS?', a: 'The 27th or 28th edition works. The book changes slowly; older editions are still exam-relevant.' },
            { q: 'Is Bailey enough for CMS Surgery?', a: 'For ~85% of CMS Surgery questions, Bailey alone is sufficient. Add SRB\'s Manual for instruments, operative steps and Indian-context viva topics.' },
        ],
        reviewer: REVIEWER,
    },
    park: {
        examSlug: 'cms', examName: 'UPSC CMS', examLandingPath: '/cms',
        bookSlug: 'park', bookTitle: "Park's Textbook of Preventive and Social Medicine", bookAuthor: 'K Park',
        bookEdition: '26th Edition',
        subjectName: 'Preventive & Social Medicine', subjectPath: '/cms/subject/psm',
        verdict: "Park is the single most important PSM text for UPSC CMS. Read epidemiology, biostatistics, NHP and immunization sections in full.",
        shouldRead: [
            'You want to cover PSM in one book',
            'You are 3-6 months from the exam',
            'You want both theory + Indian National Health Programme data',
        ],
        canSkip: [
            'You only have 2-3 weeks (read Suryakantha\'s shorter PSM text)',
        ],
        chapters: [
            { number: 1, title: 'Epidemiology', weight: 'high', note: 'Measures of association, study designs, screening. 8-10 Qs.' },
            { number: 2, title: 'Biostatistics', weight: 'high', note: 'Sensitivity, specificity, PPV, NPV, chi-square, sample size. 6-8 Qs.' },
            { number: 3, title: 'National Health Programmes', weight: 'high', note: 'NTEP, NVBDCP, PMJAY, RMNCH+A. 6+ Qs.' },
            { number: 4, title: 'Immunization', weight: 'high', note: 'NIS schedule, vaccine types, cold chain, AEFI. 4-5 Qs.' },
            { number: 5, title: 'Demography & family planning', weight: 'medium', note: 'Census, TFR, MMR, IMR, contraception methods. 4-5 Qs.' },
            { number: 6, title: 'Nutrition', weight: 'medium', note: 'ICDS, mid-day meal, micronutrient deficiency. 3-4 Qs.' },
            { number: 7, title: 'Environmental health', weight: 'medium', note: 'Water, sanitation, air pollution, waste. 3 Qs.' },
            { number: 8, title: 'Communicable diseases', weight: 'medium', note: 'TB, malaria, HIV, leprosy epidemiology. 4 Qs.' },
        ],
        schedule: [
            { week: 1, focus: 'Epidemiology + biostatistics', pages: 'pp. 60-160' },
            { week: 2, focus: 'NHPs + immunization', pages: 'pp. 430-510' },
            { week: 3, focus: 'Demography + nutrition', pages: 'pp. 540-620' },
            { week: 4, focus: 'Environment + communicable disease + revision', pages: 'pp. 670-790, 160-280' },
        ],
        pairWith: { title: "Community Medicine with Recent Advances (AH Suryakantha)", why: 'Suryakantha covers the most recent National Health Programme updates that Park editions sometimes lag on.' },
        faqs: [
            { q: 'Which Park edition for UPSC CMS?', a: 'The 25th or 26th edition is current. Park changes infrequently; older editions cover 90% of the syllabus.' },
            { q: 'Is Park enough for PSM?', a: 'Yes — for ~90% of UPSC CMS PSM questions, Park alone is sufficient. Add Suryakantha for the most recent programme updates.' },
        ],
        reviewer: REVIEWER,
    },
    ghai: {
        examSlug: 'cms', examName: 'UPSC CMS', examLandingPath: '/cms',
        bookSlug: 'ghai', bookTitle: 'OP Ghai — Essential Pediatrics', bookAuthor: 'Vinod K Paul, Arvind Bagga',
        bookEdition: '10th Edition',
        subjectName: 'Paediatrics', subjectPath: '/cms/subject/paediatrics',
        verdict: "Ghai (Vinod K Paul & Bagga) is THE Indian-standard paediatrics text for UPSC CMS, NEET PG and all INI-CET exams. Read growth, nutrition, IMNCI, immunization and neonatology in full.",
        shouldRead: [
            'You want the single best paediatrics reference for Indian PG exams',
            'You are 2-3 months from the exam',
        ],
        canSkip: [
            'You only have 1-2 weeks (use a paediatrics review book)',
        ],
        chapters: [
            { number: 1, title: 'Growth & development', weight: 'high', note: 'Growth charts, milestones, failure to thrive. 4-5 Qs.' },
            { number: 2, title: 'Nutrition', weight: 'high', note: 'Malnutrition classification, micronutrients, RDA. 3-4 Qs.' },
            { number: 3, title: 'IMNCI', weight: 'high', note: 'IMNCI classification and treatment. 3 Qs.' },
            { number: 4, title: 'Immunization', weight: 'high', note: 'NIS / IAP schedule, vaccines, cold chain. 3-4 Qs.' },
            { number: 5, title: 'Neonatology', weight: 'medium', note: 'Resuscitation, sepsis, jaundice, LBW. 3 Qs.' },
            { number: 6, title: 'Infectious diseases', weight: 'medium', note: 'Measles, dengue, typhoid, diphtheria. 2-3 Qs.' },
            { number: 7, title: 'Congenital heart disease', weight: 'low', note: 'Acyanotic vs cyanotic, VSD, TOF. 2 Qs.' },
        ],
        schedule: [
            { week: 1, focus: 'Growth + nutrition + IMNCI', pages: 'pp. 50-180, 280-340' },
            { week: 2, focus: 'Immunization + neonatology', pages: 'pp. 180-280' },
            { week: 3, focus: 'Infectious diseases + CHD', pages: 'pp. 340-480' },
            { week: 4, focus: 'Revision + PYQs', pages: 'all' },
        ],
        pairWith: { title: 'IAP Textbook of Pediatrics', why: 'IAP covers Indian-context immunization schedules and growth charts that UPSC CMS asks specifically.' },
        faqs: [
            { q: 'Which Ghai edition for UPSC CMS?', a: 'The 9th or 10th edition is current. Both are exam-aligned.' },
            { q: 'Is Ghai enough for UPSC CMS Paediatrics?', a: 'Yes — Ghai alone covers ~90% of UPSC CMS Paediatrics. Add IAP for the most recent Indian-context updates.' },
        ],
        reviewer: REVIEWER,
    },
    dutta: {
        examSlug: 'cms', examName: 'UPSC CMS', examLandingPath: '/cms',
        bookSlug: 'dutta', bookTitle: "Dutta's Textbook of Obstetrics & Gynecology", bookAuthor: 'DC Dutta',
        bookEdition: '9th (Obstetrics), 8th (Gynecology)',
        subjectName: 'Obstetrics & Gynaecology', subjectPath: '/cms/subject/obg',
        verdict: "DC Dutta's Obstetrics + Gynecology together cover ~95% of UPSC CMS OBG questions. Indian-standard, exam-aligned, comprehensive.",
        shouldRead: [
            'You want a complete OBG reference in Indian exam format',
            'You are 2-3 months from the exam',
        ],
        canSkip: [
            'You only have 2-3 weeks (use a smaller OBG review book)',
        ],
        chapters: [
            { number: 1, title: 'High-risk pregnancy', weight: 'high', note: 'Preeclampsia, GDM, APH, PPH. 4-5 Qs.' },
            { number: 2, title: 'Labour & partograph', weight: 'high', note: 'Stages of labour, monitoring, partograph interpretation. 3-4 Qs.' },
            { number: 3, title: 'Contraception & MTP', weight: 'high', note: 'IUCD, OCP, MTP Act. 3-4 Qs.' },
            { number: 4, title: 'Gynaecologic oncology', weight: 'high', note: 'Cervical, ovarian, endometrial cancer. 3 Qs.' },
            { number: 5, title: 'Menstrual disorders', weight: 'medium', note: 'Amenorrhoea, DUB, PMS. 2-3 Qs.' },
            { number: 6, title: 'Pelvic anatomy & prolapse', weight: 'medium', note: 'Supports of uterus, prolapse classification. 2 Qs.' },
        ],
        schedule: [
            { week: 1, focus: 'High-risk pregnancy + labour', pages: 'pp. 100-280 (Obstetrics)' },
            { week: 2, focus: 'Contraception + MTP', pages: 'pp. 540-620 (Obstetrics)' },
            { week: 3, focus: 'Gynaecologic oncology + menstrual disorders', pages: 'pp. 280-420 (Gynecology)' },
            { week: 4, focus: 'Pelvic anatomy + revision', pages: 'pp. 1-90 (Gynecology)' },
        ],
        pairWith: { title: 'Williams Obstetrics (26th ed.)', why: 'Williams is the deep reference for physiology and evidence-based obstetrics. Use Dutta for exam-aligned MCQ prep, Williams for understanding the "why".' },
        faqs: [
            { q: 'Is DC Dutta enough for UPSC CMS OBG?', a: 'Yes — DC Dutta\'s Obstetrics + Gynecology cover ~95% of UPSC CMS OBG questions. Williams is optional for physiology depth.' },
        ],
        reviewer: REVIEWER,
    },
};

export function getCmsBook(slug: string): BookDeepDiveContent | null {
    return CMS_BOOKS[slug] || null;
}
export function getAllCmsBookSlugs(): string[] {
    return Object.keys(CMS_BOOKS);
}