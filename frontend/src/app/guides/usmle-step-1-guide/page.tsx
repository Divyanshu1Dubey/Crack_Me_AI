import { GuideLayout, buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';

const title = 'USMLE Step 1 Guide for Indian MBBS Students — First Aid, Pathoma, UWorld';
const description = 'Crack USMLE Step 1 as an Indian medical graduate — eligibility, registration, study materials (First Aid, Pathoma, UWorld), 6-9 month study plan, and IMG-specific advice.';
const slug = 'usmle-step-1-guide';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const faqs = [
    { q: 'What is USMLE Step 1?', a: 'USMLE Step 1 is the first of three exams required for medical licensure in the United States. It tests understanding of basic medical sciences with emphasis on principles and mechanisms. Pass/fail since January 2022.' },
    { q: 'How many questions in USMLE Step 1?', a: '280 MCQs across 7 blocks of 40 questions each. Each block is 60 minutes, total 8 hours including breaks.' },
    { q: 'Can Indian MBBS students take USMLE?', a: 'Yes — Indian medical graduates (IMGs) are eligible provided their school is listed in WDOMS and they obtain ECFMG certification. About 1 in 4 US residents is an IMG.' },
];

export default function USMLEGuide() {
    return (
        <GuideLayout
            title={title}
            description={description}
            slug={slug}
            heading="USMLE Step 1 Guide for Indian MBBS Students"
            lede="A comprehensive Step 1 roadmap — eligibility, ECFMG registration, study materials (First Aid, Pathoma, UWorld, Sketchy), 6-9 month study plan, and IMG-specific advice."
            author="Dr. CrackCMS Editorial Team"
            lastUpdated="July 21, 2026"
            readingTime="10 min"
            faqs={faqs}
        >
            <h2>What is USMLE Step 1?</h2>
            <p>
                The <strong>United States Medical Licensing Examination (USMLE) Step 1</strong> is the first of three
                exams required for medical licensure in the United States. It assesses understanding of basic
                medical sciences with an emphasis on principles and mechanisms underlying health, disease, and
                modes of therapy.
            </p>
            <p>
                Step 1 became a <strong>pass/fail exam</strong> in January 2022. Numeric scores are still reported to
                the examinee on request but are no longer visible to residency programs. This shift has elevated
                the importance of Step 2 CK (Clinical Knowledge) for IMG residency applications.
            </p>

            <h2>USMLE Step 1 eligibility for Indian MBBS students</h2>
            <ul>
                <li>Enrolled in or graduated from a medical school listed in the World Directory of Medical Schools (WDOMS)</li>
                <li>All Indian medical colleges recognized by NMC are WDOMS-listed</li>
                <li>Apply for ECFMG certification before residency match</li>
                <li>No age limit; maximum 4 attempts per Step (effective 2024)</li>
            </ul>

            <h2>Step 1 exam pattern</h2>
            <table>
                <thead><tr><th>Component</th><th>Detail</th></tr></thead>
                <tbody>
                    <tr><td>Total MCQs</td><td>280</td></tr>
                    <tr><td>Blocks</td><td>7 blocks of 40 questions</td></tr>
                    <tr><td>Time per block</td><td>60 minutes (≈ 90 sec/question)</td></tr>
                    <tr><td>Total testing time</td><td>7 hours</td></tr>
                    <tr><td>Breaks</td><td>45 minutes total</td></tr>
                    <tr><td>Question formats</td><td>Single best answer, multi-step, abstract, video, audio, image-based</td></tr>
                    <tr><td>Scoring</td><td>Pass / Fail (numeric score reported on request)</td></tr>
                    <tr><td>Test centres</td><td>Prometric centres worldwide — available in Delhi, Mumbai, Bangalore, Hyderabad, Chennai</td></tr>
                </tbody>
            </table>

            <h2>Best USMLE Step 1 resources</h2>
            <ol>
                <li><strong>First Aid for the USMLE Step 1</strong> — Bible. Use as your central checklist. Every CrackCMS USMLE question maps to a First Aid page.</li>
                <li><strong>Pathoma (Hussain Sattar)</strong> — Best Pathology video + textbook resource.</li>
                <li><strong>Sketchy Medical</strong> — Visual mnemonics for Microbiology, Pharmacology, Pathology.</li>
                <li><strong>UWorld QBank</strong> — Gold standard question bank. Use after subject-wise MCQs.</li>
                <li><strong>Boards &amp; Beyond (Ryan)</strong> — Video lectures aligned with First Aid.</li>
                <li><strong>Rx Bricks (Lecturio)</strong> — Conceptual building blocks for weak topics.</li>
                <li><strong>NBME practice exams</strong> — Take 4-6 NBME forms in the final month.</li>
            </ol>

            <h2>6-9 month study plan for Indian IMGs</h2>
            <h3>Phase 1 (Months 1-3): Foundation</h3>
            <ul>
                <li>Watch Boards &amp; Beyond videos topic-by-topic</li>
                <li>Read the corresponding First Aid chapter</li>
                <li>Solve CrackCMS USMLE MCQs topic-wise (100/day)</li>
                <li>Sketchy videos for Microbiology, Pharmacology, Pathology</li>
            </ul>
            <h3>Phase 2 (Months 4-6): UWorld + Pathoma</h3>
            <ul>
                <li>UWorld QBank — 1 block (40 questions) per day with detailed review</li>
                <li>Watch Pathoma for every Pathology topic</li>
                <li>Maintain an error log — review every week</li>
                <li>Take 1 NBME form every 3 weeks</li>
            </ul>
            <h3>Phase 3 (Months 7-9): Intensive review + NBME forms</h3>
            <ul>
                <li>Re-read First Aid cover-to-cover (2nd pass)</li>
                <li>Take 4-6 NBME practice forms in the final 6 weeks</li>
                <li>Review every wrong answer + every guess</li>
                <li>Take the Free 120 (NBME&apos;s official free practice exam) in the final week</li>
            </ul>

            <h2>USMLE Step 1 vs Step 2 CK — what matters now?</h2>
            <p>
                Since Step 1 is pass/fail, <strong>Step 2 CK score has become the de-facto differentiator</strong> for
                residency applications. A 240+ on Step 2 CK opens doors to most specialties; 250+ is competitive for
                radiology, dermatology, orthopaedic surgery, and other top-tier specialties.
            </p>

            <h2>IMG-specific advice</h2>
            <ul>
                <li><strong>Step 1 attempt limit:</strong> 4 attempts (down from 6) since 2024. Take it once, take it right.</li>
                <li><strong>Clinical rotations (USCE):</strong> Recommended 3-6 months of US clinical experience before applying to residency.</li>
                <li><strong>Letters of Recommendation:</strong> Aim for 3 USCE LORs from US physicians.</li>
                <li><strong>Visa:</strong> Most IMGs match on J-1 or H-1B visas. Plan finances accordingly.</li>
            </ul>

            <h2>Why CrackCMS for USMLE?</h2>
            <ul>
                <li>10,000+ USMLE Step 1 MCQs aligned with First Aid 2025</li>
                <li>AI tutor that explains with First Aid + Pathoma + UWorld style rationales</li>
                <li>NBME-style practice blocks (40 questions, 60-min timed)</li>
                <li>High-yield flashcards auto-generated from your weak areas</li>
            </ul>
        </GuideLayout>
    );
}
