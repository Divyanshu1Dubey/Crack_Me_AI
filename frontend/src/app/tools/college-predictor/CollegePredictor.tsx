'use client';

import { useState } from 'react';
import { CATEGORIES, type Category } from '../category-rank-filter/rankModel';
import { predictServices, type Band, type CmsService, type ServicePrediction } from './servicePredictor';

const BANDS: { band: Band; title: string; accent: string }[] = [
    { band: 'safe', title: 'High Confidence', accent: '#16a34a' },
    { band: 'moderate', title: 'Moderate / On Border', accent: '#d97706' },
    { band: 'reach', title: 'Reach (Low Probability)', accent: '#dc2626' },
];

const RecommendationCard = ({ items, title, accent, limit, categoryLabel }: { items: CmsService[]; title: string; accent: string; limit: number; categoryLabel: string }) => {
    if (items.length === 0) {
        return (
            <div className="rounded-xl border border-border bg-muted/50 p-5">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</p>
                <p className="mt-2 text-sm text-muted-foreground">No services in this band for your rank.</p>
            </div>
        );
    }
    return (
        <div className="rounded-xl border border-border bg-muted/50 overflow-hidden">
            <div className="px-5 py-3 border-b border-border" style={{ background: accent }}>
                <p className="text-xs font-bold uppercase tracking-wider text-white">{title}</p>
                <p className="text-[11px] text-white/80 mt-0.5">{items.length} service{items.length > 1 ? 's' : ''}</p>
            </div>
            <div className="divide-y divide-border">
                {items.map((s) => (
                    <div key={s.id} className="px-5 py-3 flex flex-col gap-1">
                        <p className="text-sm font-bold text-foreground">{s.name}</p>
                        <p className="text-xs font-semibold text-foreground">{s.group}</p>
                        <p className="text-[11px] text-muted-foreground">{categoryLabel}: approx. last rank ~{limit.toLocaleString('en-IN')}</p>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default function CollegePredictor() {
    const [rank, setRank] = useState('');
    const [category, setCategory] = useState<Category>('general');
    const [result, setResult] = useState<ServicePrediction | null>(null);
    const [error, setError] = useState<string | null>(null);

    const calculatePrediction = () => {
        setError(null);
        const prediction = predictServices(Number(rank), category);
        if (!rank || !prediction) {
            setError('Please enter a valid rank (positive number).');
            setResult(null);
            return;
        }
        setResult(prediction);
    };

    return (
        <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
            <div className="grid gap-5 sm:grid-cols-2">
                <div>
                    <label htmlFor="college-your-all-india-rank" className="block text-sm font-semibold mb-1">Your rank in your category</label>
                    <input id="college-your-all-india-rank"
                        type="number"
                        value={rank}
                        onChange={(e) => setRank(e.target.value)}
                        placeholder="e.g. 250"
                        min="1"
                        className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
                    />
                    <p className="mt-1 text-xs text-muted-foreground">General (UR): your All India Rank. Other categories: your rank within your category&apos;s list.</p>
                </div>
                <div>
                    <label htmlFor="college-category" className="block text-sm font-semibold mb-1">Category</label>
                    <select id="college-category" value={category} onChange={(e) => setCategory(e.target.value as Category)} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm">
                        {CATEGORIES.map((opt) => (
                            <option key={opt.id} value={opt.id}>{opt.label}</option>
                        ))}
                    </select>
                </div>
            </div>

            {error && (
                <p className="mt-4 text-sm text-red-500 dark:text-red-400">{error}</p>
            )}

            <button onClick={calculatePrediction} className="mt-6 w-full rounded-xl bg-primary px-6 py-3 text-sm font-bold text-primary-foreground transition hover:opacity-90">
                Predict My Service
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
                        <div className="sm:ml-auto">
                            <p className="text-xs text-muted-foreground">Illustrative thresholds — not official UPSC closing ranks. Actual cutoffs vary each year.</p>
                        </div>
                    </div>

                    <div className="grid gap-4 lg:grid-cols-3">
                        {BANDS.map((b) => (
                            <RecommendationCard
                                key={b.band}
                                items={result.band === b.band ? result.services : []}
                                title={b.title}
                                accent={b.accent}
                                limit={result.illustrativeLimit}
                                categoryLabel={result.categoryLabel}
                            />
                        ))}
                    </div>

                    <p className="text-xs text-muted-foreground">
                        * The threshold is your category&apos;s share of the advertised vacancies. Which of these services you get depends on your rank and your preference order (and that of candidates ranked above you); each service has its own category-wise vacancies. Always refer to the official UPSC CMS notification for the latest vacancies and cutoffs.
                    </p>
                </div>
            )}
        </div>
    );
}
