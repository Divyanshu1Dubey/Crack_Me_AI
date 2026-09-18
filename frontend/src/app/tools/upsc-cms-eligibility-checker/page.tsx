'use client';

import { GuideLayout, buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import { useState } from 'react';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import Script from 'next/script';

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

function EligibilityChecker() {
    const [birthDate, setBirthDate] = useState('');
    const [category, setCategory] = useState('general');
    const [qualification, setQualification] = useState('mbbs_passed');
    const [citizenship, setCitizenship] = useState('indian');
    const [result, setResult] = useState<{ eligible: boolean; reasons: string[] } | null>(null);

    const checkEligibility = () => {
        const reasons: string[] = [];
        let eligible = true;

        // Check age
        if (birthDate) {
            const birth = new Date(birthDate);
            const refDate = new Date('2026-08-02'); // Exam date
            let age = refDate.getFullYear() - birth.getFullYear();
            const monthDiff = refDate.getMonth() - birth.getMonth();
            if (monthDiff < 0 || (monthDiff === 0 && refDate.getDate() < birth.getDate())) {
                age--;
            }
            const maxAge = category === 'general' ? 32 : category === 'obc' ? 35 : category === 'sc_st' ? 37 : 42;
            if (age > maxAge) {
                eligible = false;
                reasons.push(`Age on exam date: ${age} years. Maximum allowed: ${maxAge} years for ${category === 'general' ? 'General' : category === 'obc' ? 'OBC' : category === 'sc_st' ? 'SC/ST' : 'PwBD'} category.`);
            } else {
                reasons.push(`Age on exam date: ${age} years. ✓ Within limit (${maxAge} years for your category).`);
            }
        } else {
            reasons.push('Please enter your date of birth to check age eligibility.');
        }

        // Check qualification
        if (qualification === 'mbbs_passed') {
            reasons.push('✓ MBBS degree (passed) — meets educational qualification.');
        } else if (qualification === 'mbbs_final') {
            reasons.push('✓ Final-year MBBS student — provisionally eligible (must pass before document verification).');
        } else {
            eligible = false;
            reasons.push('✗ MBBS degree from an NMC-recognised institution is mandatory.');
        }

        // Check citizenship
        if (citizenship === 'indian') {
            reasons.push('✓ Indian citizen — meets nationality requirement.');
        } else if (citizenship === 'nepal_bhutan') {
            reasons.push('✓ Subject of Nepal/Bhutan — meets nationality requirement.');
        } else if (citizenship === 'tibetan') {
            reasons.push('✓ Tibetan refugee (came before 1 Jan 1962) — meets nationality requirement.');
        } else {
            reasons.push('✓ Person of Indian Origin — meets nationality requirement (check specific migration criteria).');
        }

        setResult({ eligible, reasons });
    };

    return (
        <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
            <h3 className="text-xl font-bold">UPSC CMS 2026 Eligibility Checker</h3>
            <p className="mt-2 text-sm text-muted-foreground">Answer the questions below to check if you are eligible for UPSC CMS 2026. The exam is scheduled for 02 August 2026.</p>

            <div className="mt-6 space-y-5">
                <div>
                    <label className="block text-sm font-semibold mb-1">Date of Birth</label>
                    <input
                        type="date"
                        value={birthDate}
                        onChange={(e) => setBirthDate(e.target.value)}
                        className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
                        max="2010-08-02"
                    />
                    <p className="mt-1 text-xs text-muted-foreground">Used to calculate age as on 02 August 2026 (exam date).</p>
                </div>

                <div>
                    <label className="block text-sm font-semibold mb-1">Category</label>
                    <select value={category} onChange={(e) => setCategory(e.target.value)} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm">
                        <option value="general">General</option>
                        <option value="obc">OBC (Non-Creamy Layer)</option>
                        <option value="sc_st">SC / ST</option>
                        <option value="pwbd">PwBD (Person with Benchmark Disability)</option>
                        <option value="exservicemen">Ex-Servicemen</option>
                    </select>
                </div>

                <div>
                    <label className="block text-sm font-semibold mb-1">Educational Qualification</label>
                    <select value={qualification} onChange={(e) => setQualification(e.target.value)} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm">
                        <option value="mbbs_passed">MBBS Degree (Passed)</option>
                        <option value="mbbs_final">Final-year MBBS Student (appearing)</option>
                        <option value="other">Other</option>
                    </select>
                </div>

                <div>
                    <label className="block text-sm font-semibold mb-1">Nationality</label>
                    <select value={citizenship} onChange={(e) => setCitizenship(e.target.value)} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm">
                        <option value="indian">Indian Citizen</option>
                        <option value="nepal_bhutan">Subject of Nepal / Bhutan</option>
                        <option value="tibetan">Tibetan Refugee (came before 1 Jan 1962)</option>
                        <option value="pio">Person of Indian Origin (migrated from Pakistan/Burma/Sri Lanka/East Africa)</option>
                    </select>
                </div>

                <button
                    onClick={checkEligibility}
                    className="w-full rounded-xl bg-primary px-6 py-3 text-sm font-bold text-primary-foreground transition hover:opacity-90"
                >
                    Check Eligibility
                </button>

                {result && (
                    <div className={`rounded-xl border p-5 ${result.eligible ? 'border-green-500/40 bg-green-50 dark:bg-green-950/30' : 'border-red-500/40 bg-red-50 dark:bg-red-950/30'}`}>
                        <p className={`text-lg font-bold ${result.eligible ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}`}>
                            {result.eligible ? '✓ You appear to be eligible for UPSC CMS 2026' : '✗ You may not meet the eligibility criteria'}
                        </p>
                        <ul className="mt-3 space-y-1.5 text-sm">
                            {result.reasons.map((r, i) => (
                                <li key={i} className={r.startsWith('✓') ? 'text-green-700 dark:text-green-300' : r.startsWith('✗') ? 'text-red-700 dark:text-red-300' : 'text-muted-foreground'}>
                                    {r}
                                </li>
                            ))}
                        </ul>
                        <p className="mt-3 text-xs text-muted-foreground">
                            * This is an indicative check based on publicly available UPSC CMS 2026 criteria. Always verify against the official UPSC notification on upsc.gov.in.
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}

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
