import { GuideLayout, buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';

const title = 'UPSC CMS Complete Guide 2026 — Eligibility, Syllabus, Pattern, Books, Salary';
const description = 'Everything about UPSC CMS 2026: eligibility (MBBS, age limit), exam pattern (240 MCQs, -0.33), subject-wise syllabus, topper-recommended books, salary, cutoff, and a 6-month study plan.';
const slug = 'upsc-cms-complete-guide';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const faqs = [
    { q: 'What is the full form of UPSC CMS?', a: 'UPSC CMS stands for Union Public Service Commission Combined Medical Services Examination. It is conducted annually to recruit medical officers for central government services.' },
    { q: 'How many papers are there in UPSC CMS?', a: 'UPSC CMS has two papers — Paper I (120 questions) and Paper II (120 questions). Both are offline pen-and-paper MCQ papers of 120 minutes each.' },
    { q: 'What is the negative marking in UPSC CMS?', a: 'UPSC CMS has -0.33 negative marking for every wrong answer. Each correct answer carries 4 marks.' },
    { q: 'Can final-year MBBS students apply for UPSC CMS?', a: 'Yes, candidates appearing in the final year of MBBS can apply provisionally, provided they pass the exam before the personality test / document verification.' },
    { q: 'What is the salary of a UPSC CMS Medical Officer?', a: 'Central government Medical Officers appointed through UPSC CMS are paid Pay Level 10 (₹56,100 - ₹1,77,500) plus 20% NPA, HRA, and rural allowance.' },
    { q: 'What is the UPSC CMS 2026 cutoff?', a: 'The UPSC CMS cutoff varies by category. In recent years the general-category cutoff has ranged between 340-400 out of 800. Check the official UPSC website for the latest cutoffs.' },
];

export default function UPSCCMSGuide() {
    return (
        <GuideLayout
            title={title}
            description={description}
            slug={slug}
            heading="UPSC CMS Complete Guide 2026"
            lede="Everything you need to crack the Combined Medical Services Examination — eligibility, syllabus, pattern, books, salary, cutoff, and a 6-month study plan. Updated for the 2026 cycle."
            author="Dr. CrackCMS Editorial Team"
            lastUpdated="July 21, 2026"
            readingTime="12 min"
            faqs={faqs}
        >
            <h2>What is UPSC CMS?</h2>
            <p>
                The <strong>Union Public Service Commission (UPSC) Combined Medical Services (CMS) Examination</strong>
                is one of India&apos;s most prestigious recruitment exams for MBBS graduates. Conducted annually by UPSC,
                CMS recruits Medical Officers (GDMOs), Specialists, and Assistant Divisional Medical Officers for central
                government services including the Central Health Service, Railways, Municipal Corporation of Delhi,
                and Defence.
            </p>

            <h3>Key facts</h3>
            <ul>
                <li>Conducting body: Union Public Service Commission (UPSC)</li>
                <li>Frequency: Once a year (notification typically April, exam July)</li>
                <li>Posts: Medical Officer (GDMO), Assistant Divisional Medical Officer, Junior Scale Posts in Railways, MO in MCD</li>
                <li>Approximate vacancies: 800-1,200 per cycle</li>
                <li>Service type: Central Government (Gazetted)</li>
            </ul>

            <h2>UPSC CMS Eligibility 2026</h2>
            <h3>Age limit</h3>
            <p>
                <strong>Upper age limit: 32 years</strong> as on the cut-off date. Relaxations:
            </p>
            <ul>
                <li>SC/ST: 5 years (max 37)</li>
                <li>OBC (non-creamy layer): 3 years (max 35)</li>
                <li>PwD (benchmark disability): 10 years</li>
                <li>Defence services personnel: 5 years</li>
                <li>Ex-servicemen: as per govt rules</li>
            </ul>

            <h3>Educational qualification</h3>
            <p>
                MBBS degree from an NMC-recognised institution. Final-year MBBS students can also apply, but they must
                pass the final exam before the personality test / document verification.
            </p>

            <h3>Nationality</h3>
            <ul>
                <li>Indian citizen, OR</li>
                <li>Subject of Nepal/Bhutan, OR</li>
                <li>Tibetan refugee who came to India before 1 January 1962 with intent to permanently settle, OR</li>
                <li>Person of Indian Origin migrated from Pakistan, Burma, Sri Lanka, East Africa, Vietnam, etc.</li>
            </ul>

            <h2>UPSC CMS Exam Pattern 2026</h2>
            <table>
                <thead>
                    <tr><th>Component</th><th>Detail</th></tr>
                </thead>
                <tbody>
                    <tr><td>Paper I</td><td>120 MCQs, 120 minutes, 480 marks</td></tr>
                    <tr><td>Paper II</td><td>120 MCQs, 120 minutes, 480 marks</td></tr>
                    <tr><td>Total marks</td><td>960</td></tr>
                    <tr><td>Negative marking</td><td>-0.33 per wrong answer</td></tr>
                    <tr><td>Mode</td><td>Offline (pen-and-paper OMR)</td></tr>
                    <tr><td>Subjects</td><td>Paper I — General Medicine &amp; Paediatrics; Paper II — Surgery, OBG, PSM, ENT, Ophthalmology, Anaesthesia, Orthopaedics</td></tr>
                </tbody>
            </table>

            <h3>Subject-wise distribution</h3>
            <ul>
                <li><strong>Paper I (96 questions on Medicine + 24 on Paediatrics):</strong> Cardiology, Respiratory, GI, Endocrinology, Neurology, Infectious diseases, Nephrology, Psychiatry, Dermatology</li>
                <li><strong>Paper II:</strong> General Surgery (40), OBG (40), PSM / Preventive &amp; Social Medicine (40)</li>
            </ul>

            <h2>UPSC CMS Syllabus 2026 — Subject-wise</h2>

            <h3>General Medicine</h3>
            <ul>
                <li>Cardiology: heart failure, MI, arrhythmias, valvular heart disease</li>
                <li>Respiratory: pneumonia, TB, COPD, asthma, PE</li>
                <li>Gastroenterology: peptic ulcer, IBD, hepatitis, cirrhosis</li>
                <li>Endocrinology: diabetes, thyroid, adrenal</li>
                <li>Neurology: stroke, epilepsy, Parkinson&apos;s, migraine</li>
                <li>Infectious diseases: malaria, dengue, typhoid, HIV, TB</li>
                <li>Nephrology: AKI, CKD, glomerulonephritis</li>
                <li>Haematology: anaemia, leukaemia, lymphoma</li>
            </ul>

            <h3>Paediatrics</h3>
            <ul>
                <li>Neonatology: newborn resuscitation, sepsis, jaundice, prematurity</li>
                <li>Growth &amp; development: milestones, failure to thrive</li>
                <li>Immunisation: NIS schedule, catch-up vaccination</li>
                <li>Common infections: pneumonia, diarrhoea, measles, pertussis</li>
                <li>Congenital heart disease, rheumatic fever</li>
            </ul>

            <h3>Surgery</h3>
            <ul>
                <li>GI surgery: appendicitis, intestinal obstruction, peptic perforation</li>
                <li>Trauma: ATLS principles, fracture management</li>
                <li>Oncology: breast cancer, colon cancer, oral cancer</li>
                <li>Hernia, gallbladder disease, thyroid surgery</li>
                <li>Burns, wounds, ulcers</li>
            </ul>

            <h3>OBG</h3>
            <ul>
                <li>Antenatal care, high-risk pregnancy</li>
                <li>Labour: stages, complications, operative delivery</li>
                <li>Gynaecological oncology: cervical, ovarian, breast cancer</li>
                <li>Contraception, MTP act</li>
            </ul>

            <h3>PSM (Preventive &amp; Social Medicine)</h3>
            <ul>
                <li>Epidemiology, biostatistics</li>
                <li>National Health Programmes: NVBDCP, RNTCP, NACP, RMNCH+A</li>
                <li>Nutrition, immunisation</li>
                <li>Demography, family planning</li>
                <li>Communicable &amp; non-communicable diseases</li>
            </ul>

            <h2>Best Books for UPSC CMS Preparation</h2>
            <ol>
                <li><strong>Harrison&apos;s Principles of Internal Medicine</strong> — gold standard for Medicine. Latest 21st edition.</li>
                <li><strong>Bailey &amp; Love&apos;s Short Practice of Surgery</strong> — definitive Surgery text. Pair with Manipal Manual.</li>
                <li><strong>OP Ghai Essential Pediatrics</strong> — single-volume Pediatrics for UPSC CMS.</li>
                <li><strong>Park&apos;s Textbook of Preventive &amp; Social Medicine</strong> — required for PSM.</li>
                <li><strong>Dutta&apos;s Gynecology and Obstetrics</strong> — most-cited OBG textbook.</li>
                <li><strong>Review of PSM (Vivek Jain)</strong> — high-yield MCQ book for last-mile revision.</li>
                <li><strong>Saxena&apos;s How to Prepare for UPSC CMS</strong> — past-solved papers.</li>
            </ol>

            <h2>UPSC CMS Cutoff &amp; Salary</h2>
            <h3>Recent cutoffs (out of 800)</h3>
            <table>
                <thead><tr><th>Year</th><th>General</th><th>OBC</th><th>SC</th><th>ST</th></tr></thead>
                <tbody>
                    <tr><td>2024</td><td>378</td><td>343</td><td>296</td><td>275</td></tr>
                    <tr><td>2023</td><td>385</td><td>355</td><td>295</td><td>282</td></tr>
                    <tr><td>2022</td><td>357</td><td>316</td><td>265</td><td>252</td></tr>
                </tbody>
            </table>

            <h3>Salary structure</h3>
            <ul>
                <li>Pay Band: Level 10 (7th CPC)</li>
                <li>Basic pay: ₹56,100 - ₹1,77,500</li>
                <li>Non-Practising Allowance (NPA): 20% of basic pay (if not running private practice)</li>
                <li>DA, HRA, rural allowance as applicable</li>
                <li>Approximate gross in-hand: ₹80,000 - ₹1,20,000 per month</li>
            </ul>

            <h2>6-month UPSC CMS study plan</h2>
            <h3>Months 1-2: Foundation</h3>
            <ul>
                <li>Read Harrison Medicine (paper I topics) — 2 chapters/day</li>
                <li>Read Bailey &amp; Love (paper II surgery topics) — 1 chapter/day</li>
                <li>Solve 50 PYQs/day from the topic you studied</li>
                <li>Make one-page revision notes for each topic</li>
            </ul>

            <h3>Months 3-4: PSM + OBG + Paediatrics</h3>
            <ul>
                <li>Read Park PSM cover-to-cover</li>
                <li>Read Ghai Pediatrics + Dutta OBG</li>
                <li>Solve 80 PYQs/day</li>
                <li>Take one full mock test every Sunday</li>
            </ul>

            <h3>Months 5-6: Revision + Mocks</h3>
            <ul>
                <li>Two full mock tests per week (Saturday &amp; Sunday)</li>
                <li>Analyse every mock — identify weak areas and revisit revision notes</li>
                <li>Solve PYQs at the rate of 100/day from a random topic</li>
                <li>Read the last 6 months&apos; UPSC CMS analysis online</li>
            </ul>

            <h2>Why CrackCMS for UPSC CMS?</h2>
            <ul>
                <li>1,920+ previous-year UPSC CMS questions with AI explanations</li>
                <li>Real-exam simulator with negative marking and 120-min timer</li>
                <li>AI tutor trained on Harrison, Bailey, Ghai, Park, Dutta</li>
                <li>Spaced-repetition flashcards for high-yield mnemonics</li>
                <li>Personalised analytics — see exactly which topics are dragging your rank</li>
            </ul>

            <h2>Frequently asked questions</h2>
            <p>
                See the FAQ section above for answers to the most common UPSC CMS questions. If you have additional
                queries, ask our <a href="/ai-tutor">AI tutor</a> or browse our <a href="/questions">question bank</a>.
            </p>
        </GuideLayout>
    );
}
