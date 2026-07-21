import { LegalLayout, buildLegalMetadata } from '@/components/LegalLayout';
import type { Metadata } from 'next';

const title = 'Medical Review Policy — CrackLabs Editorial Board';
const description = 'How CrackLabs verifies medical accuracy: clinician reviewers, AI red-teaming, citation standards, and audit cadence.';
const canonical = '/medical-review-policy';

export const metadata: Metadata = buildLegalMetadata({ title, description, canonical });

export default function MedicalReviewPage() {
    return (
        <LegalLayout
            title={title}
            description={description}
            lastUpdated="July 21, 2026"
            canonical={canonical}
            schemaType="MedicalWebPage"
        >
            <h2>Why medical review matters</h2>
            <p>
                Medical education content directly affects how future doctors diagnose and treat patients.
                An incorrect mnemonic or outdated guideline recommendation can cost lives. At CrackCMS,
                every clinical statement is reviewed by qualified clinicians before publication and
                re-audited on a rolling cadence.
            </p>

            <h2>Reviewer Qualifications</h2>
            <ul>
                <li>All clinical reviewers hold an MBBS plus MD/MS in the relevant subject.</li>
                <li>Senior reviewers have a minimum of 5 years post-PG clinical or teaching experience.</li>
                <li>External subject-matter experts (e.g. pediatric cardiologists) review niche content.</li>
            </ul>

            <h2>Review Workflow</h2>
            <ol>
                <li><strong>Drafting</strong> — author (clinician or AI) writes the explanation.</li>
                <li><strong>Fact-check</strong> — clinical reviewer cross-references with at least one Tier-1 textbook.</li>
                <li><strong>Style review</strong> — editorial lead ensures learner-friendly phrasing.</li>
                <li><strong>Final sign-off</strong> — chief medical officer approves for publication.</li>
                <li><strong>Quarterly re-audit</strong> — random 10% sample re-reviewed for currency.</li>
            </ol>

            <h2>AI Output Audits</h2>
            <p>
                We sample 200+ AI tutor responses per week across all specialties. Each sample is scored
                on a 5-point rubric covering accuracy, citation, safety, and clarity. Any response scoring
                below 4.0 is escalated for human review.
            </p>

            <h2>Red-Team Testing</h2>
            <p>
                A dedicated prompt set simulates adversarial questions (drug dosages, contraindications,
                emergency protocols) to test whether the AI tutor produces unsafe recommendations. Failed
                prompts trigger immediate model-prompt adjustments.
            </p>

            <h2>Disclosure of AI Involvement</h2>
            <p>
                Every explanation card carries a small "AI-assisted" or "Clinician-authored" badge so
                learners know the source. The full review trail is available to administrators on the
                Admin → Question Review page.
            </p>

            <h2>Reporting Concerns</h2>
            <p>
                If you believe a clinical statement on CrackCMS is incorrect or unsafe, please flag it
                using the in-app report button or email
                <a href="mailto:medical-safety@cracklabs.app">medical-safety@cracklabs.app</a>. We respond
                within 24 hours for safety-critical issues.
            </p>
        </LegalLayout>
    );
}
