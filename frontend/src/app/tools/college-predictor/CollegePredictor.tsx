'use client';

import { useState } from 'react';

type HospitalEntry = {
    name: string;
    city: string;
    urClosingRank: number;
    department: string;
    preference: number;
};

type HospitalCategory = {
    label: string;
    entries: HospitalEntry[];
};

type CollegeResult = {
    safe: HospitalEntry[];
    moderate: HospitalEntry[];
    reach: HospitalEntry[];
    categoryLabel: string;
};

const HOSPITALS_BY_CATEGORY: Record<string, HospitalCategory> = {
    general: {
        label: 'General (UR)',
        entries: [
            { name: 'AIIMS New Delhi', city: 'Delhi', urClosingRank: 5, department: 'General Medicine / Surgery / Radiology', preference: 1 },
            { name: 'JIPMER Puducherry', city: 'Puducherry', urClosingRank: 28, department: 'General Medicine / Surgery / Paediatrics', preference: 2 },
            { name: 'PGIMER Chandigarh', city: 'Chandigarh', urClosingRank: 45, department: 'General Medicine / Surgery / Orthopaedics', preference: 3 },
            { name: 'NIMHANS Bangalore', city: 'Bangalore', urClosingRank: 68, department: 'Psychiatry / Neurology / Neurosurgery', preference: 4 },
            { name: 'Safdarjung Hospital', city: 'Delhi', urClosingRank: 110, department: 'General Medicine / Surgery / Orthopaedics', preference: 5 },
            { name: 'RML Hospital', city: 'Delhi', urClosingRank: 155, department: 'General Medicine / Surgery / Cardiology', preference: 6 },
            { name: 'Lady Hardinge Medical College', city: 'Delhi', urClosingRank: 190, department: 'Obstetrics & Gynaecology / Paediatrics', preference: 7 },
            { name: 'KGMU Lucknow', city: 'Lucknow', urClosingRank: 260, department: 'General Medicine / Surgery / Dermatology', preference: 8 },
            { name: 'Madras Medical College', city: 'Chennai', urClosingRank: 320, department: 'General Medicine / Surgery / Orthopaedics', preference: 9 },
            { name: 'CIMS Patna', city: 'Patna', urClosingRank: 450, department: 'General Medicine / Surgery / OBG', preference: 10 },
            { name: 'GGH Nizamabad', city: 'Nizamabad', urClosingRank: 550, department: 'General Medicine / Surgery', preference: 11 },
            { name: 'CNC Vizag', city: 'Visakhapatnam', urClosingRank: 680, department: 'General Medicine / Surgery / ENT', preference: 12 },
        ],
    },
    sc: {
        label: 'SC',
        entries: [
            { name: 'AIIMS New Delhi', city: 'Delhi', urClosingRank: 180, department: 'General Medicine / Surgery', preference: 1 },
            { name: 'JIPMER Puducherry', city: 'Puducherry', urClosingRank: 450, department: 'General Medicine / Surgery', preference: 2 },
            { name: 'PGIMER Chandigarh', city: 'Chandigarh', urClosingRank: 620, department: 'General Medicine / Surgery / Orthopaedics', preference: 3 },
            { name: 'Safdarjung Hospital', city: 'Delhi', urClosingRank: 800, department: 'General Medicine / Surgery', preference: 4 },
            { name: 'RML Hospital', city: 'Delhi', urClosingRank: 1100, department: 'General Medicine / Surgery / ENT', preference: 5 },
            { name: 'KGMU Lucknow', city: 'Lucknow', urClosingRank: 1400, department: 'General Medicine / Surgery', preference: 6 },
            { name: 'Madras Medical College', city: 'Chennai', urClosingRank: 1700, department: 'General Medicine / Surgery', preference: 7 },
            { name: 'CIMS Patna', city: 'Patna', urClosingRank: 2200, department: 'General Medicine / Surgery / OBG', preference: 8 },
        ],
    },
    st: {
        label: 'ST',
        entries: [
            { name: 'AIIMS New Delhi', city: 'Delhi', urClosingRank: 320, department: 'General Medicine / Surgery / Dermatology', preference: 1 },
            { name: 'JIPMER Puducherry', city: 'Puducherry', urClosingRank: 750, department: 'General Medicine / Surgery', preference: 2 },
            { name: 'PGIMER Chandigarh', city: 'Chandigarh', urClosingRank: 1050, department: 'General Medicine / Surgery / Orthopaedics', preference: 3 },
            { name: 'Safdarjung Hospital', city: 'Delhi', urClosingRank: 1400, department: 'General Medicine / Surgery', preference: 4 },
            { name: 'RML Hospital', city: 'Delhi', urClosingRank: 1900, department: 'General Medicine / Surgery / ENT', preference: 5 },
            { name: 'KGMU Lucknow', city: 'Lucknow', urClosingRank: 2500, department: 'General Medicine / Surgery', preference: 6 },
            { name: 'Madras Medical College', city: 'Chennai', urClosingRank: 3000, department: 'General Medicine / Surgery', preference: 7 },
        ],
    },
    obc: {
        label: 'OBC (NCL)',
        entries: [
            { name: 'AIIMS New Delhi', city: 'Delhi', urClosingRank: 50, department: 'General Medicine / Surgery / Radiology', preference: 1 },
            { name: 'JIPMER Puducherry', city: 'Puducherry', urClosingRank: 140, department: 'General Medicine / Surgery / Paediatrics', preference: 2 },
            { name: 'PGIMER Chandigarh', city: 'Chandigarh', urClosingRank: 220, department: 'General Medicine / Surgery / Orthopaedics', preference: 3 },
            { name: 'NIMHANS Bangalore', city: 'Bangalore', urClosingRank: 320, department: 'Psychiatry / Neurology', preference: 4 },
            { name: 'Safdarjung Hospital', city: 'Delhi', urClosingRank: 420, department: 'General Medicine / Surgery', preference: 5 },
            { name: 'RML Hospital', city: 'Delhi', urClosingRank: 550, department: 'General Medicine / Surgery / Cardiology', preference: 6 },
            { name: 'KGMU Lucknow', city: 'Lucknow', urClosingRank: 700, department: 'General Medicine / Surgery / Dermatology', preference: 7 },
            { name: 'Madras Medical College', city: 'Chennai', urClosingRank: 900, department: 'General Medicine / Surgery', preference: 8 },
        ],
    },
};

const CATEGORY_OPTIONS = [
    { value: 'general', label: 'General (UR)' },
    { value: 'obc', label: 'OBC (Non-Creamy Layer)' },
    { value: 'sc', label: 'SC' },
    { value: 'st', label: 'ST' },
];

const YEAR_OPTIONS = ['2026', '2025', '2024', '2023'];

export default function CollegePredictor() {
    const [rank, setRank] = useState('');
    const [category, setCategory] = useState('general');
    const [year, setYear] = useState('2026');
    const [result, setResult] = useState<CollegeResult | null>(null);
    const [error, setError] = useState<string | null>(null);

    const calculatePrediction = () => {
        setError(null);
        const numericRank = Number(rank);

        if (!rank || Number.isNaN(numericRank) || numericRank <= 0) {
            setError('Please enter a valid All India Rank (positive number).');
            setResult(null);
            return;
        }

        const categoryData = HOSPITALS_BY_CATEGORY[category] || HOSPITALS_BY_CATEGORY.general;
        const ranked = [...categoryData.entries].sort((a, b) => a.urClosingRank - b.urClosingRank);

        const safe: HospitalEntry[] = [];
        const moderate: HospitalEntry[] = [];
        const reach: HospitalEntry[] = [];

        for (const entry of ranked) {
            const ratio = numericRank / entry.urClosingRank;
            if (ratio <= 0.6) {
                safe.push(entry);
            } else if (ratio <= 1.0) {
                moderate.push(entry);
            } else {
                reach.push(entry);
            }
        }

        setResult({
            safe,
            moderate,
            reach,
            categoryLabel: categoryData.label,
        });
    };

    const RecommendationCard = ({ items, title, accent }: { items: HospitalEntry[]; title: string; accent: string }) => {
        if (items.length === 0) {
            return (
                <div className="rounded-xl border border-border bg-muted/50 p-5">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</p>
                    <p className="mt-2 text-sm text-muted-foreground">No hospitals in this band for your rank.</p>
                </div>
            );
        }
        return (
            <div className="rounded-xl border border-border bg-muted/50 overflow-hidden">
                <div className="px-5 py-3 border-b border-border" style={{ background: accent }}>
                    <p className="text-xs font-bold uppercase tracking-wider text-white">{title}</p>
                    <p className="text-[11px] text-white/80 mt-0.5">{items.length} hospital{items.length > 1 ? 's' : ''}</p>
                </div>
                <div className="divide-y divide-border">
                    {items.map((h) => (
                        <div key={h.name + h.department} className="px-5 py-3 flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-4">
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-bold text-foreground truncate">{h.name}</p>
                                <p className="text-xs text-muted-foreground">{h.city}</p>
                            </div>
                            <div className="sm:text-right">
                                <p className="text-xs font-semibold text-foreground">{h.department}</p>
                                <p className="text-[11px] text-muted-foreground">UR cutoff ~{h.urClosingRank}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        );
    };

    return (
        <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
            <h3 className="text-xl font-bold">UPSC CMS College Predictor 2026</h3>
            <p className="mt-2 text-sm text-muted-foreground">
                Estimate which government hospitals and departments are realistic options for you based on your
                UPSC CMS All India Rank, category, and previous year closing trends.
            </p>

            <div className="mt-6 grid gap-5 sm:grid-cols-2">
                <div>
                    <label className="block text-sm font-semibold mb-1">Your All India Rank</label>
                    <input
                        type="number"
                        value={rank}
                        onChange={(e) => setRank(e.target.value)}
                        placeholder="e.g. 250"
                        min="1"
                        className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
                    />
                    <p className="mt-1 text-xs text-muted-foreground">Enter the AIR you expect or have secured.</p>
                </div>
                <div>
                    <label className="block text-sm font-semibold mb-1">Category</label>
                    <select value={category} onChange={(e) => setCategory(e.target.value)} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm">
                        {CATEGORY_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                    </select>
                </div>
                <div>
                    <label className="block text-sm font-semibold mb-1">Exam Year</label>
                    <select value={year} onChange={(e) => setYear(e.target.value)} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm">
                        {YEAR_OPTIONS.map((yr) => (
                            <option key={yr} value={yr}>{yr}</option>
                        ))}
                    </select>
                </div>
            </div>

            {error && (
                <p className="mt-4 text-sm text-red-500 dark:text-red-400">{error}</p>
            )}

            <button onClick={calculatePrediction} className="mt-6 w-full rounded-xl bg-primary px-6 py-3 text-sm font-bold text-primary-foreground transition hover:opacity-90">
                Predict Colleges
            </button>

            {result && (
                <div className="mt-6 space-y-4">
                    <div className="rounded-xl bg-accent/10 border border-border p-4 flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-6">
                        <div>
                            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Your Rank</p>
                            <p className="text-2xl font-black text-foreground">{Number(rank).toLocaleString('en-IN')}</p>
                        </div>
                        <div>
                            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Category</p>
                            <p className="text-lg font-bold text-foreground">{result.categoryLabel}</p>
                        </div>
                        <div>
                            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Prediction Year</p>
                            <p className="text-lg font-bold text-foreground">{year}</p>
                        </div>
                        <div className="sm:ml-auto">
                            <p className="text-xs text-muted-foreground">Based on previous year category-wise closing ranks. Actual cutoffs may vary each year.</p>
                        </div>
                    </div>

                    <div className="grid gap-4 lg:grid-cols-3">
                        <RecommendationCard
                            items={result.safe}
                            title="High Confidence"
                            accent="#16a34a"
                        />
                        <RecommendationCard
                            items={result.moderate}
                            title="Moderate / On Border"
                            accent="#d97706"
                        />
                        <RecommendationCard
                            items={result.reach}
                            title="Reach (Low Probability)"
                            accent="#dc2626"
                        />
                    </div>

                    <p className="text-xs text-muted-foreground">
                        * Predictions are indicative only. Closing ranks change yearly based on vacancy counts, difficulty level, and candidate preferences. Always refer to the official UPSC CMS notification for the latest vacancies and cutoffs.
                    </p>
                </div>
            )}
        </div>
    );
}
