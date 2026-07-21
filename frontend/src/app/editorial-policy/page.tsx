import { LegalLayout, buildLegalMetadata } from '@/components/LegalLayout';
import type { Metadata } from 'next';

const title = 'Editorial Policy — CrackCMS Content Standards';
const description = 'How CrackCMS curates, reviews, and updates medical content. Our editorial standards, AI safety, source citation, and revision policy.';
const canonical = '/editorial-policy';

export const metadata: Metadata = buildLegalMetadata({ title, description, canonical });

export default function EditorialPolicyPage() {
    return (
        <LegalLayout
            title={title}
            description={description}
            lastUpdated="July 21, 2026"
            canonical={canonical}
            schemaType="MedicalWebPage"
        >
            <h2>Our Editorial Mission</h2>
            <p>
                CrackCMS exists to make high-yield, evidence-based medical knowledge accessible to every
                aspirant preparing for UPSC CMS, NEET PG, INI-CET, FMGE, USMLE and other medical
                examinations. Every question, explanation, mnemonic, and study note on CrackCMS follows a
                strict editorial workflow before it reaches a learner.
            </p>

            <h2>1. Sourcing &amp; Curation</h2>
            <ul>
                <li>Previous-year questions are transcribed from official conducting-body publications.</li>
                <li>AI-generated questions are written by clinicians and verified by our medical-review team.</li>
                <li>Explanations cite standard textbooks (Harrison, Robbins, Bailey &amp; Love, Ghai, Park, Nelson, Goodman &amp; Gilman, Katzung).</li>
                <li>Current guidelines (NMC, WHO, ICMR, NICE, AAP) are cross-checked before publication.</li>
            </ul>

            <h2>2. Medical Review</h2>
            <p>
                Every AI-generated or user-flagged explanation passes through a two-stage medical review:
                first by an MD/MS-qualified subject specialist, then by our editorial lead. Reviews cover
                factual accuracy, currency, alignment with the source textbook, and absence of harmful
                clinical advice.
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
                Question banks are versioned in <code>questions_fixture.json</code> and republished each
                release. Each question carries a <code>last_reviewed</code> timestamp visible to admins.
                Outdated explanations are tagged &amp; scheduled for re-review every 12 months.
            </p>

            <h2>5. Conflict of Interest</h2>
            <p>
                Authors and reviewers disclose any financial relationship with pharmaceutical, medical
                device, or coaching-industry companies. We do not accept payment in exchange for positive
                content placement.
            </p>

            <h2>6. AI Safety &amp; Bias Review</h2>
            <p>
                AI-tutor outputs are sampled weekly for toxicity, hallucination, and demographic bias. A
                dedicated red-team prompt set tests for unsafe clinical recommendations. Findings are
                reviewed by our medical board.
            </p>

            <h2>7. Corrections Policy</h2>
            <p>
                Verified corrections are published within 7 days. The question&apos;s explanation card
                shows a "Recently corrected" badge for 30 days, and the original contributor is notified.
                Substantive corrections trigger an email to all users who attempted the question in the
                prior 30 days.
            </p>

            <h2>8. Community Contributions</h2>
            <p>
                Forum posts, discussion comments, and feedback reports are moderated by a trained team of
                medical graduates. Off-topic or harmful content is removed within 24 hours.
            </p>

            <h2>9. Contact Editorial Team</h2>
            <p>
                Editorial lead: Dr. (editorial lead name)<br />
                Email: <a href="mailto:editorial@cracklabs.app">editorial@cracklabs.app</a>
            </p>
        </LegalLayout>
    );
}
