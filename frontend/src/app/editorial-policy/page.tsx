import { LegalLayout, buildLegalMetadata } from '@/components/LegalLayout';
import type { Metadata } from 'next';
import Link from 'next/link';

const title = 'Editorial Policy — CrackCMS Content Standards';
const description = 'How CrackCMS curates, reviews, and updates medical content. Our editorial standards, AI safety, source citation, and revision policy.';
const canonical = '/editorial-policy';

export const metadata: Metadata = buildLegalMetadata({ title, description, canonical });

// Only processes the product implements (see /medical-review-policy): no
// unconfirmed doctor authors, specialist sign-off, review board or unbuilt
// badges and e-mails.
export default function EditorialPolicyPage() {
    return (
        <LegalLayout
            title={title}
            description={description}
            lastUpdated="November 1, 2026"
            canonical={canonical}
            schemaType="MedicalWebPage"
        >
            <h2>Our Editorial Mission</h2>
            <p>
                CrackCMS exists to make high-yield, evidence-based medical knowledge accessible to every
                aspirant preparing for UPSC CMS, NEET PG, INI-CET, FMGE, USMLE and other medical
                examinations. This policy sets out how questions, explanations, mnemonics and study notes
                on CrackCMS are sourced, checked and corrected.
            </p>

            <h2>1. Sourcing &amp; Curation</h2>
            <ul>
                <li>UPSC CMS previous-year questions are transcribed from the question papers UPSC publishes. NEET PG and INI-CET questions are mostly memory-based recalls, as those papers are not publicly released.</li>
                <li>Practice questions from the AI question generator are created on demand by AI, are not reviewed before you see them, and are not added to the previous-year banks.</li>
                <li>Explanations cite standard textbooks (Harrison, Robbins, Bailey &amp; Love, Ghai, Park, Nelson, Goodman &amp; Gilman, Katzung).</li>
                <li>Articles and guides are cross-checked against current guidelines (NMC, WHO, ICMR, NICE, AAP) before publication.</li>
            </ul>

            <h2>2. Medical Review</h2>
            <p>
                Answers and explanations are checked by the CrackCMS Editorial Team against standard
                textbooks and official sources, starting with questions that learners report or that the
                automatic answer-key check flags. Reviews cover factual accuracy, currency, alignment with
                the source textbook, and absence of harmful clinical advice. Questions the team has checked
                show a &quot;Verified by Admin&quot; badge. The full process is in our{' '}
                <Link href="/medical-review-policy">medical review policy</Link>.
            </p>

            <h2>3. Sources &amp; Citations</h2>
            <p>
                CrackCMS uses a tiered source hierarchy:
            </p>
            <ol>
                <li><strong>Tier 1</strong> — official notifications (UPSC, NBE, AIIMS, NMC, USMLE).</li>
                <li><strong>Tier 2</strong> — standard medical textbooks (latest edition).</li>
                <li><strong>Tier 3</strong> — peer-reviewed journals (PubMed, Cochrane).</li>
                <li><strong>Tier 4</strong> — institutional guidelines (WHO, ICMR, NICE).</li>
                <li><strong>Tier 5</strong> — verified open-access medical references.</li>
            </ol>

            <h2>4. Updates &amp; Versioning</h2>
            <p>
                Each question bank is exported to a version-controlled snapshot. Every admin edit to a
                question also keeps a snapshot of the previous version, so a change can be traced and
                undone, and a verified question records when it was verified.
            </p>

            <h2>5. Conflict of Interest</h2>
            <p>
                Authors and reviewers disclose any financial relationship with pharmaceutical, medical
                device, or coaching-industry companies. We do not accept payment in exchange for positive
                content placement.
            </p>

            <h2>6. AI Output &amp; Safety</h2>
            <p>
                AI output is a study aid, not medical advice. AI tutor answers are generated live, shown in
                AI-labelled panels and not reviewed before you see them. When an AI-drafted explanation
                disagrees with the stored answer key, the question is flagged for the editorial team.
                Report wrong, unsafe or biased output with the in-app report buttons or by e-mail.
            </p>

            <h2>7. Corrections Policy</h2>
            <p>
                Verified corrections are published within 7 days. When a report is accepted, the learner
                who sent it receives bonus AI tokens and can be told by e-mail that it was resolved.
            </p>

            <h2>8. Community Contributions</h2>
            <p>
                Question discussion posts and feedback reports are moderated by the CrackCMS team, who can
                remove any discussion post. Off-topic or harmful content is removed within 24 hours.
            </p>

            <h2>9. Contact Editorial Team</h2>
            <p>
                Editorial team: CrackCMS Editorial Team<br />
                Email: <a href="mailto:crackwith.ai@gmail.com">crackwith.ai@gmail.com</a>
            </p>
        </LegalLayout>
    );
}
