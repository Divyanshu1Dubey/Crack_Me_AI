'use client';

import { useState } from 'react';
import { UPSC_CMS_CYCLE } from '@/lib/examPatterns';

/**
 * Upper age limit as given in the UPSC CMS notice: a candidate must not have
 * attained 32 years on 1 August of the exam year, with relaxations of
 * 3 years (OBC), 5 years (SC/ST and eligible Ex-Servicemen) and 10 years
 * (PwBD). The limit is exclusive: turning 32 by 1 August makes a General
 * candidate ineligible.
 */
const AGE_LIMITS: Record<string, { limit: number; label: string }> = {
    general: { limit: 32, label: 'General' },
    obc: { limit: 35, label: 'OBC' },
    sc_st: { limit: 37, label: 'SC/ST' },
    pwbd: { limit: 42, label: 'PwBD' },
    exservicemen: { limit: 37, label: 'Ex-Servicemen' },
};

/** The next exam cycle: the current notice's year until its exam day has passed. */
function nextExamYear(now = new Date()): number {
    const examDay = new Date(`${UPSC_CMS_CYCLE.examDate}T23:59:59`);
    return now.getTime() > examDay.getTime() ? UPSC_CMS_CYCLE.year + 1 : UPSC_CMS_CYCLE.year;
}

export default function EligibilityChecker() {
    const examYear = nextExamYear();
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
            // Reference date used by the UPSC CMS notice: 1 August of the exam year.
            const refDate = new Date(examYear, 7, 1);
            let age = refDate.getFullYear() - birth.getFullYear();
            const monthDiff = refDate.getMonth() - birth.getMonth();
            if (monthDiff < 0 || (monthDiff === 0 && refDate.getDate() < birth.getDate())) {
                age--;
            }
            const { limit, label } = AGE_LIMITS[category] ?? AGE_LIMITS.general;
            if (age >= limit) {
                eligible = false;
                reasons.push(`✗ Age on 1 August ${examYear}: ${age} years. ${label} candidates must be under ${limit}.`);
            } else {
                reasons.push(`✓ Age on 1 August ${examYear}: ${age} years — within the limit (under ${limit} for ${label}).`);
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
            <h3 className="text-xl font-bold">UPSC CMS {examYear} Eligibility Checker</h3>
            <p className="mt-2 text-sm text-muted-foreground">Answer the questions below to check if you are eligible for UPSC CMS {examYear}. Age is worked out as on 1 August {examYear}, the reference date used in the UPSC CMS notice — confirm it in the {examYear} notification.</p>

            <div className="mt-6 space-y-5">
                <div>
                    <label htmlFor="elig-dob" className="block text-sm font-semibold mb-1">Date of Birth</label>
                    <input
                        id="elig-dob"
                        aria-describedby="elig-dob-help"
                        type="date"
                        value={birthDate}
                        onChange={(e) => setBirthDate(e.target.value)}
                        className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
                        max="2010-08-02"
                    />
                    <p id="elig-dob-help" className="mt-1 text-xs text-muted-foreground">Used to calculate your age as on 1 August {examYear}.</p>
                </div>

                <div>
                    <label htmlFor="elig-category" className="block text-sm font-semibold mb-1">Category</label>
                    <select id="elig-category" value={category} onChange={(e) => setCategory(e.target.value)} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm">
                        <option value="general">General</option>
                        <option value="obc">OBC (Non-Creamy Layer)</option>
                        <option value="sc_st">SC / ST</option>
                        <option value="pwbd">PwBD (Person with Benchmark Disability)</option>
                        <option value="exservicemen">Ex-Servicemen</option>
                    </select>
                </div>

                <div>
                    <label htmlFor="elig-qualification" className="block text-sm font-semibold mb-1">Educational Qualification</label>
                    <select id="elig-qualification" value={qualification} onChange={(e) => setQualification(e.target.value)} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm">
                        <option value="mbbs_passed">MBBS Degree (Passed)</option>
                        <option value="mbbs_final">Final-year MBBS Student (appearing)</option>
                        <option value="other">Other</option>
                    </select>
                </div>

                <div>
                    <label htmlFor="elig-nationality" className="block text-sm font-semibold mb-1">Nationality</label>
                    <select id="elig-nationality" value={citizenship} onChange={(e) => setCitizenship(e.target.value)} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm">
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
                            {result.eligible ? `✓ You appear to be eligible for UPSC CMS ${examYear}` : '✗ You may not meet the eligibility criteria'}
                        </p>
                        <ul className="mt-3 space-y-1.5 text-sm">
                            {result.reasons.map((r, i) => (
                                <li key={i} className={r.startsWith('✓') ? 'text-green-700 dark:text-green-300' : r.startsWith('✗') ? 'text-red-700 dark:text-red-300' : 'text-muted-foreground'}>
                                    {r}
                                </li>
                            ))}
                        </ul>
                        <p className="mt-3 text-xs text-muted-foreground">
                            * This is an indicative check based on the publicly available UPSC CMS criteria. Always verify against the official UPSC notification on upsc.gov.in.
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
