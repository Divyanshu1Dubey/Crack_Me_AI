import { LegalLayout, buildLegalMetadata } from '@/components/LegalLayout';
import type { Metadata } from 'next';
import Link from 'next/link';

const title = 'Medical Review Policy — How We Check Accuracy';
const description = 'How CrackCMS checks medical accuracy: AI-drafted explanations, automatic answer-key checks, editorial cross-checks against standard textbooks, and learner error reports.';
const canonical = '/medical-review-policy';

export const metadata: Metadata = buildLegalMetadata({ title, description, canonical });

// Describe only the process the product implements (owner review, PUB-06):
// AI drafts, the answer-key mismatch flag, the editorial team's cross-check
// and "Verified by Admin" badge, revision snapshots, learner reports. No named
// specialist reviewers, sign-offs or audit quotas until the owner confirms them.
export default function MedicalReviewPage() {
    return (
        <LegalLayout
            title={title}
            description={description}
            lastUpdated="November 1, 2026"
            canonical={canonical}
            schemaType="MedicalWebPage"
        >
            <h2>Why medical review matters</h2>
            <p>
                Medical education content directly affects how future doctors diagnose and treat patients.
                An incorrect mnemonic or outdated guideline recommendation can cost lives. This page
                describes how CrackCMS content is drafted and checked, and which parts are not checked
                before you see them.
            </p>

            <h2>Who reviews content</h2>
            <p>
                Content is checked by the CrackCMS Editorial Team, which cross-checks answers and
                explanations against standard textbooks and official sources. CrackCMS does not list named
                specialist reviewers, and no page on the site carries a specialist&apos;s sign-off.
            </p>

            <h2>Review Workflow</h2>
            <ol>
                <li><strong>Drafting</strong> — AI drafts explanations, mnemonics and clinical pearls, grounded in indexed textbook excerpts where available.</li>
                <li><strong>Automatic answer check</strong> — when the AI&apos;s answer disagrees with the stored answer key, the question is flagged as disputed for the editorial team.</li>
                <li><strong>Editorial cross-check</strong> — the editorial team checks flagged and reported questions against standard textbooks and official sources, corrects the answer key or explanation where needed, and can lock a corrected explanation so it is not regenerated.</li>
                <li><strong>Verified badge</strong> — questions the team has checked show a &quot;Verified by Admin&quot; badge in the question bank.</li>
                <li><strong>Revision history</strong> — every admin edit to a question keeps a snapshot of the previous version, so a change can be traced and undone.</li>
            </ol>

            <h2>Disclosure of AI Involvement</h2>
            <p>
                Output from the AI tutor is shown in AI-labelled panels (for example the AI explanation
                and AI tutor views), so learners know when they are reading AI-generated text. AI tutor
                answers and questions from the AI question generator are created live and are not
                reviewed before you see them.
            </p>
            <p>
                Per-question source badges are not shown yet; until they are, treat any explanation
                without a &quot;Verified by Admin&quot; badge as AI-assisted and cross-check it against a
                standard textbook.
            </p>

            <h2>Reporting Concerns</h2>
            <p>
                If you believe a clinical statement on CrackCMS is incorrect or unsafe, please flag it
                using the in-app report button or email{' '}
                <a href="mailto:crackwith.ai@gmail.com">crackwith.ai@gmail.com</a>. We respond
                within 24 hours for safety-critical issues. Verified corrections are applied to the
                question, and a learner whose report is accepted receives bonus AI tokens. How
                corrections are published is set out in our <Link href="/editorial-policy">editorial policy</Link>.
            </p>
        </LegalLayout>
    );
}
