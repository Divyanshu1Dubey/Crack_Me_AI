'use client';

import { useState } from 'react';

export default function EligibilityChecker() {
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
