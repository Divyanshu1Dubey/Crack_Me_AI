import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import EligibilityChecker from './EligibilityChecker';

const title = 'UPSC CMS Eligibility Checker 2026 — MBBS, Age Limit, Attempts';
const description = 'Check if you are eligible for UPSC CMS 2026. Interactive eligibility checker for MBBS graduates: age limit, educational qualification, nationality, number of attempts, and medical fitness requirements.';
const slug = 'upsc-cms-eligibility-checker';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        { '@type': 'Question', name: 'What is the eligibility for UPSC CMS 2026?', acceptedAnswer: { '@type': 'Answer', text: 'UPSC CMS 2026 eligibility: MBBS degree from an NMC-recognised institution (final-year appearing allowed), age limit 32 years (relaxation for reserved categories), Indian citizenship or subject of Nepal/Bhutan, and medical fitness as prescribed by UPSC.' } },
        { '@type': 'Question', name: 'Can final-year MBBS students apply for UPSC CMS?', acceptedAnswer: { '@type': 'Answer', text: 'Yes — final-year MBBS students can apply provisionally, provided they pass the final exam before the personality test / document verification stage.' } },
        { '@type': 'Question', name: 'What is the age limit for UPSC CMS?', acceptedAnswer: { '@type': 'Answer', text: 'The upper age limit is 32 years for General category. Relaxations apply: OBC (3 years), SC/ST (5 years), PwBD (up to 10 years depending on category), Ex-servicemen (as per govt rules).' } },
    ],
};

export default function UPSCCMSEligibilityCheckerPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'Eligibility Checker', path: '/tools/upsc-cms-eligibility-checker' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        UPSC CMS Eligibility Checker 2026
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Use our interactive eligibility checker to find out if you meet the age, education, and nationality
                        requirements for <strong>UPSC CMS 2026</strong>. The exam is scheduled for <strong>02 August 2026</strong>.
                    </p>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <EligibilityChecker />

                    <h2 className="text-2xl font-bold mt-12 mb-4">UPSC CMS 2026 Eligibility Criteria</h2>
                    <div className="space-y-6 text-muted-foreground">
                        <div>
                            <h3 className="font-bold text-foreground">Educational Qualification</h3>
                            <ul className="mt-2 space-y-1 list-disc pl-5">
                                <li>MBBS degree from an NMC-recognised institution.</li>
                                <li>Final-year MBBS students can apply provisionally — must pass before document verification.</li>
                                <li>No minimum percentage requirement specified in the official notification.</li>
                            </ul>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Age Limit</h3>
                            <ul className="mt-2 space-y-1 list-disc pl-5">
                                <li>General category: 32 years (as on 01 January 2026).</li>
                                <li>OBC (Non-Creamy Layer): 35 years (3 years relaxation).</li>
                                <li>SC / ST: 37 years (5 years relaxation).</li>
                                <li>PwBD (General): 42 years (10 years relaxation).</li>
                                <li>Ex-servicemen: As per government rules.</li>
                            </ul>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Nationality</h3>
                            <ul className="mt-2 space-y-1 list-disc pl-5">
                                <li>Indian citizen, OR</li>
                                <li>Subject of Nepal/Bhutan, OR</li>
                                <li>Tibetan refugee who came to India before 1 January 1962 with intent to permanently settle, OR</li>
                                <li>Person of Indian Origin migrated from Pakistan, Burma, Sri Lanka, East Africa, Vietnam, etc.</li>
                            </ul>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Number of Attempts</h3>
                            <p>There is <strong>no fixed attempt limit</strong> for UPSC CMS, subject to the age ceiling. Candidates can attempt the exam as many times as they want until they exceed the age limit for their category.</p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Medical Fitness</h3>
                            <p>Candidates must meet the physical and medical standards prescribed for the post applied for. This includes vision standards, hearing, and general physical fitness as per UPSC guidelines.</p>
                        </div>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {[
                            { q: 'What is the eligibility for UPSC CMS 2026?', a: 'UPSC CMS 2026 eligibility: MBBS degree from an NMC-recognised institution (final-year appearing allowed), age limit 32 years (relaxation for reserved categories), Indian citizenship or subject of Nepal/Bhutan, and medical fitness as prescribed by UPSC. Use the eligibility checker above to verify your specific case.' },
                            { q: 'Can final-year MBBS students apply for UPSC CMS?', a: 'Yes — final-year MBBS students can apply provisionally, provided they pass the final exam before the personality test / document verification stage. This is explicitly mentioned in the UPSC CMS official notification.' },
                            { q: 'What is the age limit for UPSC CMS?', a: 'The upper age limit is 32 years for General category. Relaxations apply: OBC (3 years relaxation → 35 years), SC/ST (5 years relaxation → 37 years), PwBD (up to 10 years relaxation → 42 years), and Ex-servicemen (as per govt rules).' },
                            { q: 'Is there an attempt limit for UPSC CMS?', a: 'No — there is no fixed attempt limit for UPSC CMS. You can attempt the exam as many times as you want, subject to the age ceiling for your category.' },
                            { q: 'Can BDS graduates apply for UPSC CMS?', a: 'No — UPSC CMS is specifically for MBBS graduates. BDS graduates should look at state PSC Dental Surgeon posts or other dental recruitment exams.' },
                        ].map((faq) => (
                            <div key={faq.q} className="rounded-xl border border-border bg-card p-5">
                                <h3 className="font-bold text-sm">{faq.q}</h3>
                                <p className="mt-2 text-sm text-muted-foreground">{faq.a}</p>
                            </div>
                        ))}
                    </div>
                </section>
            </div>
        </>
    );
}
