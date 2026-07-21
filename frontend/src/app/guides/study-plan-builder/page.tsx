import { GuideLayout, buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';

const title = 'Build a Personalised UPSC CMS / NEET PG Study Plan';
const description = 'Step-by-step framework to build a 6-month UPSC CMS or NEET PG study plan using PYQs, AI tutor, and spaced repetition.';
const slug = 'study-plan-builder';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const faqs = [
    { q: 'How many months do I need to prepare for UPSC CMS?', a: 'Most successful candidates prepare for 6-9 months with 6-8 hours/day of focused study. A baseline assessment helps you calibrate.' },
    { q: 'Should I start with PYQs or textbooks?', a: 'Take a diagnostic test first (50 mixed MCQs across all subjects). Identify your weakest topic, then read the corresponding textbook chapter, then solve topic-wise PYQs. This is the most efficient 3-step loop.' },
];

export default function StudyPlanBuilderGuide() {
    return (
        <GuideLayout
            title={title}
            description={description}
            slug={slug}
            heading="Build a Personalised Study Plan"
            lede="A step-by-step framework to build a 6-month UPSC CMS or NEET PG study plan using PYQs, AI tutor, and spaced repetition."
            author="Dr. CrackCMS Editorial Team"
            lastUpdated="July 21, 2026"
            readingTime="6 min"
            faqs={faqs}
        >
            <h2>Step 1: Take a diagnostic test</h2>
            <p>
                Before designing your study plan, take a 50-question mixed-subject diagnostic test on CrackCMS. This
                gives you a baseline score and identifies your weakest subjects and topics. Without this data point,
                you&apos;ll waste weeks on subjects you already know.
            </p>

            <h2>Step 2: Set your target score</h2>
            <p>
                Based on your baseline and the exam cutoff:
            </p>
            <ul>
                <li><strong>UPSC CMS:</strong> Aim 480+ out of 800 (well above the ~380 general cutoff).</li>
                <li><strong>NEET PG:</strong> Aim 600+ out of 800 for top clinical branches.</li>
                <li><strong>INI-CET:</strong> Aim 150+ out of 200.</li>
            </ul>

            <h2>Step 3: Define your weekly time budget</h2>
            <table>
                <thead><tr><th>Time available</th><th>Recommended plan</th></tr></thead>
                <tbody>
                    <tr><td>2 hours/day</td><td>6-month plan, focus on PYQs + AI tutor</td></tr>
                    <tr><td>4 hours/day</td><td>4-month plan, textbook + PYQs + mocks</td></tr>
                    <tr><td>6+ hours/day</td><td>2-3 month crash plan, intensive mock + revision</td></tr>
                </tbody>
            </table>

            <h2>Step 4: The 3-step topic loop</h2>
            <p>
                For every topic:
            </p>
            <ol>
                <li><strong>Read:</strong> Textbook chapter (Harrison / Bailey / Ghai / Park / Dutta).</li>
                <li><strong>Solve:</strong> 30-50 topic-wise PYQs.</li>
                <li><strong>Clarify:</strong> Ask the AI tutor for explanations on any wrong answers.</li>
            </ol>
            <p>
                Repeat this loop daily for the weakest subject. This is more effective than passive reading.
            </p>

            <h2>Step 5: Weekly schedule template</h2>
            <ul>
                <li><strong>Monday–Friday:</strong> 2 hours textbook + 2 hours PYQs + 30 min AI tutor</li>
                <li><strong>Saturday:</strong> Full mock test + 1-hour analysis</li>
                <li><strong>Sunday:</strong> Review + revision of weak topics + AI tutor deep-dive</li>
            </ul>

            <h2>Step 6: Spaced repetition</h2>
            <p>
                For high-yield mnemonics and clinical pearls, use CrackCMS flashcards with spaced repetition. Review
                cards on Day 1, Day 3, Day 7, Day 14, Day 30. This compounds retention.
            </p>

            <h2>Step 7: Track &amp; adjust</h2>
            <p>
                After every mock test:
            </p>
            <ul>
                <li>Review your analytics (subject-wise accuracy, time-per-question).</li>
                <li>Identify the 3 weakest topics from this mock.</li>
                <li>Add them to next week&apos;s study plan.</li>
                <li>Use the AI tutor to clarify every concept you got wrong.</li>
            </ul>

            <h2>Common mistakes to avoid</h2>
            <ul>
                <li>Reading without solving MCQs — passive reading has poor retention.</li>
                <li>Ignoring weak subjects — your weakest subject = your biggest score gainer.</li>
                <li>Skipping mocks — the only way to build exam temperament is timed practice.</li>
                <li>Not reviewing wrong answers — every wrong answer is a learning opportunity.</li>
            </ul>

            <h2>Start today</h2>
            <p>
                <a href="/register">Create a free CrackCMS account</a> to access the diagnostic test, AI tutor, and
                full question bank. Your personalised study plan awaits.
            </p>
        </GuideLayout>
    );
}
