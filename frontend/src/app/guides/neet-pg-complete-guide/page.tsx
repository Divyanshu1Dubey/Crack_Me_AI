import { GuideLayout, buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';

const title = 'NEET PG Complete Guide 2026 — Pattern, Syllabus, Books, AIR Prediction, Strategy';
const description = 'Complete NEET PG 2026 guide — exam pattern (200 MCQs, -1 negative marking), subject-wise syllabus, topper-recommended books, AIR prediction, image-based questions, and a 6-month study plan.';
const slug = 'neet-pg-complete-guide';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const faqs = [
    { q: 'What is NEET PG?', a: 'NEET PG (National Eligibility cum Entrance Test - Postgraduate) is the single-window entrance exam for MD/MS/PG Diploma courses in India, conducted by the National Board of Examinations (NBE).' },
    { q: 'How many questions are in NEET PG 2026?', a: 'NEET PG has 200 MCQs covering pre-clinical, para-clinical, and clinical subjects. Total marks: 800. Time: 210 minutes. Negative marking: -1 per wrong answer.' },
    { q: 'What is the NEET PG cutoff for MD/MS?', a: 'NEET PG cutoff varies by specialty and category. Top clinical branches (MD Medicine, MD Paediatrics, MD Radio) typically require 600-700+ out of 800. Cutoffs are published by MCC after each counselling round.' },
    { q: 'Can I prepare for NEET PG in 6 months?', a: 'Yes — a disciplined 6-month plan with 6-8 hours/day of study, weekly mocks, and AI-tutor-supported revision is sufficient for most candidates to clear NEET PG cutoff.' },
    { q: 'Does NEET PG have image-based questions?', a: 'Yes — since 2019, NEET PG includes image-based questions in radiology, histopathology, dermatology, and clinical photographs. Allocate at least 30 minutes daily to image-based practice.' },
];

export default function NEETPGGuide() {
    return (
        <GuideLayout
            title={title}
            description={description}
            slug={slug}
            heading="NEET PG Complete Guide 2026"
            lede="Crack NEET PG in 6 months — exam pattern, subject-wise syllabus, topper books, AIR prediction, image-based MCQs, and a week-by-week study plan."
            author="Dr. CrackCMS Editorial Team"
            lastUpdated="July 21, 2026"
            readingTime="11 min"
            faqs={faqs}
        >
            <h2>What is NEET PG?</h2>
            <p>
                <strong>NEET PG (National Eligibility cum Entrance Test - Postgraduate)</strong> is the single-window
                entrance examination for admission to MD, MS, and PG Diploma courses across India. Conducted by the
                <strong> National Board of Examinations (NBE)</strong>, NEET PG replaced the multiple state-level and
                institute-level PG entrance exams in 2017.
            </p>

            <h3>Why NEET PG matters</h3>
            <ul>
                <li>Single entrance for ~60,000 MD/MS/PG Diploma seats across India</li>
                <li>Required for central institutions (AIIMS, PGIMER, JIPMER, NIMHANS, SCTIMST) — note: these institutes also accept INI-CET</li>
                <li>Determines eligibility for state quota seats and private medical college seats</li>
                <li>Mandatory for foreign medical graduates (after FMGE)</li>
            </ul>

            <h2>NEET PG Exam Pattern 2026</h2>
            <table>
                <thead><tr><th>Component</th><th>Detail</th></tr></thead>
                <tbody>
                    <tr><td>Mode</td><td>Computer-Based Test (CBT) at designated centres</td></tr>
                    <tr><td>Total MCQs</td><td>200</td></tr>
                    <tr><td>Time</td><td>210 minutes (3.5 hours)</td></tr>
                    <tr><td>Marks per question</td><td>4 marks</td></tr>
                    <tr><td>Negative marking</td><td>-1 per wrong answer</td></tr>
                    <tr><td>Total marks</td><td>800</td></tr>
                    <tr><td>Image-based MCQs</td><td>~20-30 per paper (varies yearly)</td></tr>
                </tbody>
            </table>

            <h2>NEET PG Eligibility 2026</h2>
            <h3>Educational qualification</h3>
            <ul>
                <li>MBBS degree from an NMC-recognised medical college</li>
                <li>Provisional MBBS pass certificate acceptable at application stage</li>
                <li>12-month compulsory rotating internship completed or completing by the NBE cutoff date</li>
            </ul>
            <h3>Registration</h3>
            <ul>
                <li>Provisional or permanent registration certificate from NMC / State Medical Council</li>
            </ul>
            <h3>Nationality</h3>
            <ul>
                <li>Indian citizen</li>
                <li>Overseas Citizen of India (OCI)</li>
                <li>Foreign nationals (separate quota, subject to MCI/NMC rules)</li>
            </ul>
            <h3>Age limit</h3>
            <ul>
                <li>No upper age limit (per Supreme Court 2023 ruling)</li>
                <li>Must meet internship completion date</li>
            </ul>

            <h2>NEET PG Syllabus — Subject-wise Weightage</h2>
            <p>
                The NEET PG syllabus is derived from the MBBS curriculum as prescribed by the NMC. The 200 MCQs are
                distributed across:
            </p>
            <table>
                <thead><tr><th>Section</th><th>Subjects</th><th>Approx. weightage</th></tr></thead>
                <tbody>
                    <tr><td>Pre-clinical</td><td>Anatomy, Physiology, Biochemistry</td><td>~15%</td></tr>
                    <tr><td>Para-clinical</td><td>Pathology, Microbiology, Pharmacology, Forensic Medicine, PSM</td><td>~30%</td></tr>
                    <tr><td>Clinical — Medicine &amp; Allied</td><td>General Medicine, Psychiatry, Dermatology, TB &amp; Chest</td><td>~25%</td></tr>
                    <tr><td>Clinical — Surgery &amp; Allied</td><td>General Surgery, Orthopaedics, Anaesthesia, Radio, Ophthalmology, ENT</td><td>~20%</td></tr>
                    <tr><td>OBG &amp; Paediatrics</td><td>Obstetrics &amp; Gynaecology, Paediatrics</td><td>~10%</td></tr>
                </tbody>
            </table>

            <h3>High-yield topics by subject</h3>
            <ul>
                <li><strong>Anatomy:</strong> Neuroanatomy, embryology, histology</li>
                <li><strong>Physiology:</strong> Endocrine, CVS, Renal</li>
                <li><strong>Biochemistry:</strong> Enzymes, metabolism, genetics</li>
                <li><strong>Pathology:</strong> Neoplasia, inflammation, haematology</li>
                <li><strong>Pharmacology:</strong> Autonomic, CNS, antimicrobials</li>
                <li><strong>Medicine:</strong> Cardiology, endocrinology, neurology</li>
                <li><strong>Surgery:</strong> GI surgery, trauma, oncology</li>
                <li><strong>OBG:</strong> High-risk pregnancy, gynae oncology</li>
                <li><strong>Paediatrics:</strong> Neonatology, immunisation</li>
            </ul>

            <h2>Best Books for NEET PG</h2>
            <ol>
                <li><strong>Harrison&apos;s Principles of Internal Medicine</strong> — Medicine gold standard</li>
                <li><strong>Robbins Pathologic Basis of Disease</strong> — Pathology standard</li>
                <li><strong>Bailey &amp; Love + Manipal Manual of Surgery</strong> — Surgery combo</li>
                <li><strong>KD Tripathi Pharmacology</strong> — concise Indian-context pharmacology</li>
                <li><strong>Dutta OBG + Shaw Gynaecology</strong> — OBG combo</li>
                <li><strong>OP Ghai + IAP Pediatrics</strong> — Pediatrics combo</li>
                <li><strong>Review of AIIMS/NEET PG (Arora)</strong> — single-volume MCQ book</li>
                <li><strong>Mudit Khanna MCQ book</strong> — clinical MCQs</li>
            </ol>

            <h2>NEET PG Cutoff 2026 (expected)</h2>
            <table>
                <thead><tr><th>Category</th><th>Qualifying percentile</th><th>Expected score (out of 800)</th></tr></thead>
                <tbody>
                    <tr><td>General / EWS</td><td>50th percentile</td><td>275-300</td></tr>
                    <tr><td>General-PwD</td><td>45th percentile</td><td>250-275</td></tr>
                    <tr><td>OBC / SC / ST</td><td>40th percentile</td><td>230-260</td></tr>
                </tbody>
            </table>
            <p>
                <strong>For top clinical branches:</strong> MD Medicine / Radio / Paediatrics require 600-700+ in
                recent years. Cutoffs change with the difficulty of the paper and the candidate pool.
            </p>

            <h2>6-month NEET PG study plan</h2>
            <h3>Months 1-2: Pre &amp; Para-clinical foundation</h3>
            <ul>
                <li>Subject-wise reading: Robbins Pathology, KD Tripathi Pharmacology, Park PSM</li>
                <li>Solve 80 PYQs/day from the topic you read</li>
                <li>Maintain a notebook of high-yield facts</li>
            </ul>

            <h3>Months 3-4: Clinical subjects</h3>
            <ul>
                <li>Harrison Medicine — 1 chapter/day + 60 PYQs from that chapter</li>
                <li>Surgery: Bailey &amp; Love + Manipal Manual</li>
                <li>OBG + Paediatrics: Dutta + Ghai</li>
                <li>Take one full mock every Sunday</li>
            </ul>

            <h3>Months 5-6: Revision + Mocks</h3>
            <ul>
                <li>Two full mocks per week</li>
                <li>Daily 100 random PYQs</li>
                <li>Image-based MCQ drill (30 min/day)</li>
                <li>Revise high-yield notes from previous 5 months</li>
            </ul>

            <h2>Image-based questions on NEET PG</h2>
            <p>
                Since 2019, NBE has included 20-30 image-based MCQs covering radiology, histopathology slides,
                dermatology images, clinical photographs, and instruments. Allocate dedicated daily practice — at
                least 30 minutes — to image-based questions. CrackCMS has a dedicated image-based filter in the
                question bank for this purpose.
            </p>

            <h2>NEET PG vs INI-CET — Which is harder?</h2>
            <p>
                <strong>INI-CET</strong> (for AIIMS, PGIMER, JIPMER, NIMHANS, SCTIMST) is considered more
                conceptual and image-heavy, with a faster pace (200 questions in 180 minutes vs 210 for NEET PG).
                NEET PG has a slightly higher negative marking penalty (-1 vs -1/3). Most toppers attempt both.
            </p>

            <h2>Why CrackCMS for NEET PG?</h2>
            <ul>
                <li>18,000+ NEET PG MCQs across all 19 subjects</li>
                <li>AI tutor trained on Harrison, Robbins, Bailey, Ghai, Park, Dutta</li>
                <li>All-India rank prediction after every mock test</li>
                <li>Spaced-repetition flashcards adapted to your weak areas</li>
                <li>Image-based MCQ drill with 1,000+ curated images</li>
            </ul>
        </GuideLayout>
    );
}
