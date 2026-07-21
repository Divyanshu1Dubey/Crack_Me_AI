import { LegalLayout, buildLegalMetadata } from '@/components/LegalLayout';
import type { Metadata } from 'next';

const title = 'Privacy Policy — CrackCMS by CrackLabs AI';
const description = 'How CrackCMS (CrackLabs AI) collects, uses, protects, and shares your personal data. GDPR & DPDP Act aligned privacy practices for medical students.';
const canonical = '/privacy-policy';

export const metadata: Metadata = buildLegalMetadata({ title, description, canonical });

export default function PrivacyPolicyPage() {
    return (
        <LegalLayout
            title={title}
            description={description}
            lastUpdated="July 21, 2026"
            effectiveDate="January 1, 2025"
            canonical={canonical}
            schemaType="PrivacyPolicy"
        >
            <h2>1. Introduction</h2>
            <p>
                CrackCMS ("we", "our", "us") is operated by <strong>CrackLabs AI</strong>. This Privacy
                Policy explains how we collect, use, disclose, and safeguard your information when you
                visit our website, use the CrackCMS mobile or web app, or purchase a premium subscription.
                CrackCMS is an AI-powered medical exam preparation platform designed for UPSC CMS, NEET PG,
                INI-CET, FMGE, USMLE and other medical entrance exams.
            </p>
            <p>
                By accessing CrackCMS you agree to the practices described in this policy. If you do not
                agree, please discontinue use of the service.
            </p>

            <h2>2. Information We Collect</h2>
            <h3>2.1 Account information</h3>
            <p>
                When you register, we collect your name, email address, mobile number (optional), profile
                picture (optional), and password (stored as a one-way hash). If you sign in via Google or
                other OAuth providers, we receive a verified email and profile identifier.
            </p>
            <h3>2.2 Usage & learning data</h3>
            <p>
                To power AI tutoring, spaced-repetition flashcards, and personalised analytics, we record:
            </p>
            <ul>
                <li>Questions attempted, answered, flagged, and bookmarked.</li>
                <li>Time spent per question, per subject, and per mock test.</li>
                <li>Mock-test scores, streaks, XP, and badges.</li>
                <li>AI tutor conversations (used to improve model quality, with content moderation).</li>
            </ul>
            <h3>2.3 Device & technical data</h3>
            <p>
                We automatically receive IP address, browser type, device model, operating system, locale,
                referring URL, and aggregate usage analytics via privacy-respecting tooling (Datadog RUM,
                Google Analytics 4 with IP-anonymisation enabled).
            </p>
            <h3>2.4 Payment data</h3>
            <p>
                Payments are processed by PCI-DSS compliant third-party gateways (Razorpay / Stripe). We do
                not store full card numbers, CVV, or expiry dates on CrackCMS servers.
            </p>

            <h2>3. How We Use Your Information</h2>
            <ul>
                <li>Provide AI tutoring, mock-test scoring, and personalised study plans.</li>
                <li>Maintain your account, process subscriptions, and send transactional notifications.</li>
                <li>Detect cheating, fraud, and abuse; protect the integrity of leaderboards.</li>
                <li>Improve our models and content; conduct aggregate research on learning patterns.</li>
                <li>Comply with Indian and international legal obligations.</li>
            </ul>

            <h2>4. Sharing of Information</h2>
            <p>
                We <strong>do not sell</strong> your personal data. We share data only with vetted vendors:
                cloud hosting (Render, AWS, Supabase), analytics (Datadog, GA4), AI providers (Groq,
                Cerebras, Gemini, OpenRouter, Cohere, HuggingFace, Mistral, DeepSeek, Together, AI/ML API),
                and payment gateways. Each vendor is bound by confidentiality and data-processing
                agreements.
            </p>

            <h2>5. Cookies & Local Storage</h2>
            <p>
                CrackCMS uses essential cookies for authentication and preference storage (theme, sidebar
                state, exam track). We do not use advertising cookies. You can disable cookies in your
                browser settings; some features (login, dark-mode toggle) may stop working.
            </p>

            <h2>6. Data Retention</h2>
            <p>
                We retain your account information for as long as your account is active. AI tutor
                transcripts are retained for 12 months for quality and safety review, then anonymised for
                research. You can request immediate deletion of all personal data — see Section 8.
            </p>

            <h2>7. Your Rights</h2>
            <p>Under GDPR, the India DPDP Act 2023, and analogous frameworks, you have the right to:</p>
            <ul>
                <li>Access the personal data we hold about you.</li>
                <li>Correct inaccurate or incomplete data.</li>
                <li>Request deletion ("right to be forgotten").</li>
                <li>Object to or restrict processing.</li>
                <li>Data portability in a machine-readable format.</li>
            </ul>

            <h2>8. How to Exercise Your Rights</h2>
            <p>
                Email <a href="mailto:privacy@cracklabs.app">privacy@cracklabs.app</a> from the address
                registered with your account. We respond within 30 days. For deletion, we will anonymise
                your account and remove personal identifiers within 7 days.
            </p>

            <h2>9. Children&apos;s Privacy</h2>
            <p>
                CrackCMS is intended for medical graduates and senior medical students (typically aged 18+).
                We do not knowingly collect data from anyone under 16. If you believe a minor has created
                an account, contact us for immediate deletion.
            </p>

            <h2>10. International Data Transfers</h2>
            <p>
                Some AI providers process prompts outside India (United States, European Union). Where
                required, we rely on Standard Contractual Clauses or equivalent safeguards. Aggregated
                diagnostic data is processed in India.
            </p>

            <h2>11. Security</h2>
            <p>
                We use TLS 1.3 encryption in transit, AES-256 at rest, hardware-backed key storage, JWT
                authentication with short-lived tokens, brute-force protection via django-axes, single-
                device session enforcement, and routine penetration testing.
            </p>

            <h2>12. Changes to This Policy</h2>
            <p>
                We may update this policy to reflect product, legal, or operational changes. Material
                changes will be communicated via in-app notification and email at least 14 days before
                taking effect.
            </p>

            <h2>13. Contact</h2>
            <p>
                <strong>Data Protection Officer</strong><br />
                CrackLabs AI<br />
                Email: <a href="mailto:privacy@cracklabs.app">privacy@cracklabs.app</a><br />
                Postal: B-12, Sector 62, Noida, Uttar Pradesh 201301, India
            </p>
        </LegalLayout>
    );
}
