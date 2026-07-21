import { GuideLayout, buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';

const title = 'FMGE Complete Guide 2026 — MCI Screening Test for Foreign MBBS';
const description = 'Pass FMGE 2026 on your first attempt. Eligibility, syllabus, books, Indian-context preparation, and a 3-month study plan.';
const slug = 'fmge-complete-guide';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const faqs = [
    { q: 'What is FMGE?', a: 'FMGE (Foreign Medical Graduate Examination) is the screening test by NBEMS for Indian citizens with primary medical qualifications from foreign institutions, required to practise medicine in India or to appear for NEET PG.' },
    { q: 'How many questions in FMGE?', a: '300 MCQs across 19 subjects. 5 hours total. No negative marking. 50% aggregate (150/300) required to pass.' },
    { q: 'Is FMGE easier than NEET PG?', a: 'FMGE has more questions and no negative marking, but the syllabus emphasises Indian-context epidemiology and pharmacology. Foreign MBBS graduates typically need 3-6 months of focused study to pass.' },
];

export default function FMGEGuide() {
    return (
        <GuideLayout
            title={title}
            description={description}
            slug={slug}
            heading="FMGE Complete Guide 2026"
            lede="Pass the MCI Screening Test on your first attempt. Eligibility, syllabus, Indian-context preparation strategy, and a 3-month study plan."
            author="Dr. CrackCMS Editorial Team"
            lastUpdated="July 21, 2026"
            readingTime="9 min"
            faqs={faqs}
        >
            <h2>What is FMGE?</h2>
            <p>
                <strong>FMGE (Foreign Medical Graduate Examination)</strong>, also known as the <strong>MCI Screening
                Test</strong>, is conducted by the National Board of Examinations in Medical Sciences (NBEMS) for
                Indian citizens and OCIs who obtained their primary medical qualification (MBBS or equivalent)
                from a foreign institution. Passing FMGE is mandatory before you can:
            </p>
            <ul>
                <li>Practise medicine in India</li>
                <li>Apply for permanent NMC registration</li>
                <li>Appear for NEET PG (for MD/MS admission)</li>
                <li>Apply for state government Medical Officer posts</li>
            </ul>

            <h2>FMGE Eligibility 2026</h2>
            <ul>
                <li>Indian citizen or Overseas Citizen of India (OCI)</li>
                <li>Primary medical qualification (MBBS or equivalent) from an institution listed in the WHO World Directory of Medical Schools</li>
                <li>Eligibility Certificate from NMC at the time of admission to the foreign medical school</li>
                <li>Documentary proof of internship (if completed)</li>
                <li>No upper age limit, but the qualification must be within the NMC-prescribed window</li>
            </ul>

            <h2>FMGE Exam Pattern</h2>
            <table>
                <thead><tr><th>Component</th><th>Detail</th></tr></thead>
                <tbody>
                    <tr><td>Mode</td><td>Computer-Based Test (CBT)</td></tr>
                    <tr><td>Total MCQs</td><td>300</td></tr>
                    <tr><td>Total time</td><td>300 minutes (5 hours), two parts of 2.5 hours each</td></tr>
                    <tr><td>Marks per question</td><td>1 mark</td></tr>
                    <tr><td>Negative marking</td><td>None</td></tr>
                    <tr><td>Total marks</td><td>300</td></tr>
                    <tr><td>Passing criteria</td><td>150/300 (50% aggregate)</td></tr>
                    <tr><td>Frequency</td><td>Twice a year (June &amp; December)</td></tr>
                </tbody>
            </table>

            <h2>FMGE Syllabus — Subject-wise</h2>
            <p>
                The FMGE syllabus is drawn from the GMER 2019 (Graduate Medical Education Regulations) prescribed by NMC.
                All 19 MBBS subjects are tested. The most heavily tested are:
            </p>
            <ul>
                <li><strong>General Medicine</strong> — ~30%</li>
                <li><strong>General Surgery</strong> — ~15%</li>
                <li><strong>OBG</strong> — ~12%</li>
                <li><strong>Paediatrics</strong> — ~10%</li>
                <li><strong>PSM / Community Medicine</strong> — ~15%</li>
                <li><strong>Pathology, Microbiology, Pharmacology</strong> — ~10%</li>
                <li><strong>Anatomy, Physiology, Biochemistry</strong> — ~8%</li>
            </ul>

            <h2>Best books for FMGE</h2>
            <ul>
                <li><strong>Harrison&apos;s Principles of Internal Medicine</strong> — Medicine</li>
                <li><strong>Bailey &amp; Love + Manipal Manual</strong> — Surgery</li>
                <li><strong>OP Ghai</strong> — Paediatrics</li>
                <li><strong>Park&apos;s PSM</strong> — Indian-context epidemiology (CRITICAL)</li>
                <li><strong>Dutta OBG</strong> — Obstetrics &amp; Gynaecology</li>
                <li><strong>Self Assessment &amp; Review of FMGE (Arora)</strong> — MCQ book</li>
                <li><strong>Mudit Khanna MCQ book</strong> — last-mile revision</li>
            </ul>

            <h2>3-month FMGE study plan</h2>
            <h3>Month 1: Foundation</h3>
            <ul>
                <li>Read Harrison Medicine — 1 chapter/day + 80 PYQs</li>
                <li>Read Park PSM cover-to-cover</li>
            </ul>
            <h3>Month 2: Other clinical subjects</h3>
            <ul>
                <li>Bailey + Manipal (Surgery)</li>
                <li>Dutta (OBG) + Ghai (Paediatrics)</li>
                <li>100 PYQs/day from random topics</li>
                <li>One full mock test every Sunday</li>
            </ul>
            <h3>Month 3: Revision + Intensive mocks</h3>
            <ul>
                <li>Two full mocks per week</li>
                <li>150 random PYQs/day</li>
                <li>Revise high-yield mnemonics</li>
            </ul>

            <h2>Common FMGE mistakes to avoid</h2>
            <ul>
                <li>Using foreign textbooks (e.g. Davidson) — they underemphasise Indian epidemiology</li>
                <li>Ignoring PSM — 15% of the paper, very high-yield</li>
                <li>Not practising time-management — 5 hours is a long paper, stamina matters</li>
                <li>Leaving revision for the last week — start from month 1</li>
            </ul>

            <h2>Why CrackCMS for FMGE?</h2>
            <ul>
                <li>8,000+ FMGE-aligned MCQs covering all 19 subjects</li>
                <li>AI tutor trained on Indian medical textbooks</li>
                <li>Mock tests with the exact NBEMS CBT interface</li>
                <li>Personalised analytics to identify weak topics</li>
            </ul>
        </GuideLayout>
    );
}
