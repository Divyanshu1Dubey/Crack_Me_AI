import { GuideLayout, buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';

const title = 'INI-CET Complete Guide — AIIMS, PGIMER, JIPMER, NIMHANS, SCTIMST';
const description = 'Crack INI-CET for AIIMS, PGIMER, JIPMER, NIMHANS, SCTIMST. Pattern, eligibility, syllabus, books, image-based MCQs, and a 4-month study plan.';
const slug = 'ini-cet-complete-guide';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const faqs = [
    { q: 'What is INI-CET?', a: 'INI-CET is the common entrance test for PG medical courses at AIIMS, PGIMER Chandigarh, JIPMER Puducherry, NIMHANS Bangalore, and SCTIMST Trivandrum. Conducted twice a year by AIIMS.' },
    { q: 'How many questions in INI-CET?', a: '200 MCQs in 180 minutes. 1 mark per question, -1/3 negative marking. Total: 200 marks.' },
    { q: 'Is INI-CET harder than NEET PG?', a: 'INI-CET questions are more conceptual and image-heavy. Cutoffs are typically higher relative to the candidate pool. Most aspirants attempt both exams.' },
];

export default function INICETGuide() {
    return (
        <GuideLayout
            title={title}
            description={description}
            slug={slug}
            heading="INI-CET Complete Guide — AIIMS, PGIMER, JIPMER, NIMHANS, SCTIMST"
            lede="Crack INI-CET for India&apos;s top medical institutes. Pattern, eligibility, syllabus, books, image-based MCQs, and a 4-month study plan."
            author="Dr. CrackCMS Editorial Team"
            lastUpdated="July 21, 2026"
            readingTime="10 min"
            faqs={faqs}
        >
            <h2>What is INI-CET?</h2>
            <p>
                <strong>INI-CET (Institute of National Importance - Combined Entrance Test)</strong> is the common
                entrance examination for admission to PG medical courses (MD, MS, DM, MCh, MDS) at the
                Institutes of National Importance:
            </p>
            <ul>
                <li><strong>AIIMS</strong> — All India Institute of Medical Sciences (Delhi, Bhopal, Bhubaneswar, Jodhpur, Patna, Raipur, Rishikesh, Mangalagiri, Nagpur, Bathinda, Bibinagar, Kalyani, Gorakhpur, Guwahati, Raebareli, Deoghar, Rajkot, Bilaspur)</li>
                <li><strong>PGIMER</strong> — Post Graduate Institute of Medical Education &amp; Research, Chandigarh</li>
                <li><strong>JIPMER</strong> — Jawaharlal Institute of Postgraduate Medical Education &amp; Research, Puducherry</li>
                <li><strong>NIMHANS</strong> — National Institute of Mental Health and Neurosciences, Bangalore</li>
                <li><strong>SCTIMST</strong> — Sree Chitra Tirunal Institute for Medical Sciences and Technology, Trivandrum</li>
            </ul>

            <h2>INI-CET Exam Pattern</h2>
            <table>
                <thead><tr><th>Component</th><th>Detail</th></tr></thead>
                <tbody>
                    <tr><td>Mode</td><td>Computer-Based Test (CBT)</td></tr>
                    <tr><td>Total MCQs</td><td>200</td></tr>
                    <tr><td>Time</td><td>180 minutes (3 hours)</td></tr>
                    <tr><td>Marks per question</td><td>1 mark</td></tr>
                    <tr><td>Negative marking</td><td>-1/3 per wrong answer</td></tr>
                    <tr><td>Total marks</td><td>200</td></tr>
                    <tr><td>Frequency</td><td>Twice a year (January &amp; July sessions)</td></tr>
                </tbody>
            </table>

            <h2>INI-CET Eligibility</h2>
            <ul>
                <li>MBBS / BDS / equivalent from an NMC / DCI-recognised institution</li>
                <li>12-month compulsory rotating internship completed by the cutoff date</li>
                <li>Provisional or permanent NMC / State Medical Council registration</li>
                <li>Indian citizenship (OCI eligibility varies by institute)</li>
            </ul>

            <h2>INI-CET Syllabus</h2>
            <p>
                The syllabus mirrors the MBBS curriculum prescribed by NMC. Subject-wise distribution:
            </p>
            <ul>
                <li><strong>Pre-clinical</strong> (Anatomy, Physiology, Biochemistry) — ~15%</li>
                <li><strong>Para-clinical</strong> (Pathology, Microbiology, Pharmacology, Forensic, PSM) — ~25%</li>
                <li><strong>Clinical Medicine &amp; Allied</strong> — ~25%</li>
                <li><strong>Clinical Surgery &amp; Allied</strong> — ~20%</li>
                <li><strong>OBG &amp; Paediatrics</strong> — ~15%</li>
            </ul>

            <h2>Image-based questions</h2>
            <p>
                INI-CET papers feature a significant proportion of image-based questions (radiology, histopathology,
                dermatology, instruments, clinical photographs). Allocate at least 30-45 minutes daily to image-based
                practice for the last 8 weeks before the exam.
            </p>

            <h2>Best books for INI-CET</h2>
            <ul>
                <li><strong>Harrison&apos;s Principles of Internal Medicine</strong></li>
                <li><strong>Robbins Pathology + Robbins Review Questions</strong></li>
                <li><strong>Bailey &amp; Love + Manipal Manual of Surgery</strong></li>
                <li><strong>Solve last 10 years of AIIMS, PGI, JIPMER papers</strong> — these are the most relevant patterns</li>
                <li><strong>Review of AIIMS / PGI / JIPMER (Arora)</strong></li>
            </ul>

            <h2>4-month INI-CET study plan</h2>
            <h3>Month 1: Subject-wise foundation</h3>
            <ul>
                <li>Read Medicine (Harrison) — 1 chapter/day</li>
                <li>Solve 60 PYQs/day from the chapter</li>
            </ul>
            <h3>Month 2: Surgery + OBG + Paediatrics</h3>
            <ul>
                <li>Bailey + Manipal + Dutta + Ghai</li>
                <li>Solve 80 PYQs/day</li>
            </ul>
            <h3>Month 3: PSM + Para-clinical + Mocks</h3>
            <ul>
                <li>Read Park PSM cover-to-cover</li>
                <li>Take one full mock every Sunday</li>
                <li>30 minutes of image-based MCQs daily</li>
            </ul>
            <h3>Month 4: Revision + Intensive mocks</h3>
            <ul>
                <li>Two full mocks per week</li>
                <li>100 random PYQs per day</li>
                <li>Revise high-yield notes</li>
            </ul>

            <h2>Why CrackCMS for INI-CET?</h2>
            <ul>
                <li>12,000+ INI-CET MCQs spanning AIIMS, PGIMER, JIPMER, NIMHANS</li>
                <li>AI tutor that explains with mnemonics and clinical pearls</li>
                <li>Image-based MCQ drill with dedicated filter</li>
                <li>Mock tests with the exact AIIMS CBT interface</li>
            </ul>
        </GuideLayout>
    );
}
