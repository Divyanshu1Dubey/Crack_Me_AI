import { LegalLayout, buildLegalMetadata } from '@/components/LegalLayout';
import type { Metadata } from 'next';

const title = 'Terms & Conditions — CrackCMS by CrackLabs AI';
const description = 'Terms governing your use of CrackCMS — the AI medical exam preparation platform. Covers acceptable use, subscriptions, refunds, and intellectual property.';
const canonical = '/terms';

export const metadata: Metadata = buildLegalMetadata({ title, description, canonical });

export default function TermsPage() {
    return (
        <LegalLayout
            title={title}
            description={description}
            lastUpdated="July 21, 2026"
            effectiveDate="January 1, 2025"
            canonical={canonical}
            schemaType="TermsOfService"
        >
            <h2>1. Acceptance of Terms</h2>
            <p>
                By creating an account, accessing the CrackCMS website or mobile app, or using any of our
                services (collectively, the "Service"), you agree to be bound by these Terms &amp;
                Conditions. If you do not agree, do not use the Service.
            </p>

            <h2>2. Eligibility</h2>
            <p>
                You must be at least 16 years old and a medical graduate or currently enrolled in a
                medical degree (MBBS, BDS, BHMS, BAMS, BUMS, MD, MS, MDS) to use CrackCMS. By registering,
                you represent that you meet these requirements.
            </p>

            <h2>3. Account &amp; Security</h2>
            <ul>
                <li>You are responsible for safeguarding your password and OTP codes.</li>
                <li>CrackCMS enforces single-device active sessions; logging in elsewhere will sign you out.</li>
                <li>Notify us immediately of any unauthorised account access.</li>
                <li>Five failed login attempts within 30 minutes will lock the account for 30 minutes.</li>
            </ul>

            <h2>4. Acceptable Use</h2>
            <p>You agree <strong>not</strong> to:</p>
            <ul>
                <li>Scrape, crawl, or mass-download question banks or AI tutor responses.</li>
                <li>Share your account or premium subscription with non-subscribers.</li>
                <li>Upload copyrighted question banks you do not own without permission.</li>
                <li>Use AI tutor responses to train competing models.</li>
                <li>Reverse-engineer, decompile, or attempt to extract source code.</li>
                <li>Post hate speech, harassment, or medical advice that could harm patients.</li>
            </ul>

            <h2>5. Subscriptions, Pricing &amp; Refunds</h2>
            <h3>5.1 Free tier</h3>
            <p>
                Free accounts receive 10 daily AI tokens, 50 weekly AI tokens, and access to the question
                bank, mock tests, and analytics. Tokens reset on a rolling schedule.
            </p>
            <h3>5.2 Premium plans</h3>
            <p>
                Premium subscriptions unlock unlimited AI tutor sessions, advanced analytics, exam
                simulations, and full textbook access. Pricing is displayed on the
                <a href="/subscription">/subscription</a> page.
            </p>
            <h3>5.3 Refunds</h3>
            <p>
                Within 7 days of purchase, if you have used fewer than 10 AI tokens, you are eligible for a
                full refund. After 7 days or once you have consumed 10+ AI tokens, the purchase is
                non-refundable except where required by law. See our full
                <a href="/refund-policy">Refund Policy</a>.
            </p>

            <h2>6. Content &amp; Intellectual Property</h2>
            <p>
                CrackCMS content, including question banks curated by our medical team, UI designs, AI
                prompts, and brand assets, is owned by CrackLabs AI and protected under the Copyright
                Act, 1957. You may use content for personal study only.
            </p>
            <p>
                User-generated content (forum posts, discussion comments, AI-flagged feedback) is licensed
                to CrackLabs AI under a non-exclusive, royalty-free, perpetual licence to operate the
                Service.
            </p>

            <h2>7. AI-Generated Content Disclaimer</h2>
            <p>
                The AI tutor is a study aid, not a substitute for medical judgement. AI explanations may
                occasionally contain errors. Always verify clinical information against authoritative
                textbooks (Harrison&apos;s, Robbins, Bailey &amp; Love, Ghai, Park&apos;s) and your
                university curriculum. See <a href="/disclaimer">Disclaimer</a>.
            </p>

            <h2>8. Limitation of Liability</h2>
            <p>
                To the maximum extent permitted by law, CrackLabs AI&apos;s liability is limited to the
                amount you paid for the Service in the 12 months preceding the claim. We are not liable
                for indirect, incidental, special, or consequential damages.
            </p>

            <h2>9. Termination</h2>
            <p>
                We may suspend or terminate your account for violations of these terms. You may terminate
                at any time via Settings → Delete Account. Termination forfeits unused paid tokens.
            </p>

            <h2>10. Governing Law</h2>
            <p>
                These Terms are governed by the laws of India. Disputes are subject to the exclusive
                jurisdiction of courts in New Delhi, India.
            </p>

            <h2>11. Contact</h2>
            <p>
                <strong>CrackLabs AI</strong><br />
                Email: <a href="mailto:crackwith.ai@gmail.com">crackwith.ai@gmail.com</a><br />
                Phone: 9601981524
            </p>
        </LegalLayout>
    );
}
