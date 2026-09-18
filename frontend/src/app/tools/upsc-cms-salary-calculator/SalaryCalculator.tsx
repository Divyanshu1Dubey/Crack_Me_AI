'use client';

import { useState } from 'react';

export default function SalaryCalculator() {
    const [payLevel, setPayLevel] = useState('10');
    const [basicPay, setBasicPay] = useState('56100');
    const [cityClass, setCityClass] = useState('metro');
    const [allowNPA, setAllowNPA] = useState(true);
    const [years, setYears] = useState('0');
    const [result, setResult] = useState<{ monthly: number; annual: number; components: Record<string, number> } | null>(null);

    const calculate = () => {
        const basic = Number(basicPay);
        const yr = Number(years);
        const npa = allowNPA ? basic * 0.20 : 0;
        const da = basic * 0.46;
        const hraRates: Record<string, number> = { metro: 0.24, tier2: 0.16, tier3: 0.08 };
        const hra = basic * (hraRates[cityClass] || 0.24);
        const transport = 3600;
        const medical = 500;
        const monthly = basic + npa + da + hra + transport + medical;
        const annual = monthly * 12;
        setResult({
            monthly: Math.round(monthly),
            annual: Math.round(annual),
            components: { basic, npa: Math.round(npa), da: Math.round(da), hra: Math.round(hra), transport, medical },
        });
    };

    return (
        <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
            <h3 className="text-xl font-bold">UPSC CMS Salary Calculator 2026</h3>
            <p className="mt-2 text-sm text-muted-foreground">Estimate your in-hand salary as a UPSC CMS Medical Officer. Adjust the parameters below to see your approximate monthly and annual take-home pay.</p>

            <div className="mt-6 grid gap-5 sm:grid-cols-2">
                <div>
                    <label className="block text-sm font-semibold mb-1">Pay Level (7th CPC)</label>
                    <select value={payLevel} onChange={(e) => setPayLevel(e.target.value)} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm">
                        <option value="10">Level 10 (Medical Officer)</option>
                        <option value="11">Level 11 (Senior Medical Officer)</option>
                        <option value="12">Level 12 (Chief Medical Officer)</option>
                    </select>
                </div>
                <div>
                    <label className="block text-sm font-semibold mb-1">Basic Pay (₹)</label>
                    <input type="number" value={basicPay} onChange={(e) => setBasicPay(e.target.value)} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm" />
                </div>
                <div>
                    <label className="block text-sm font-semibold mb-1">City Type (HRA)</label>
                    <select value={cityClass} onChange={(e) => setCityClass(e.target.value)} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm">
                        <option value="metro">Metro (X cities) — 24% HRA</option>
                        <option value="tier2">Tier-2 (Y cities) — 16% HRA</option>
                        <option value="tier3">Tier-3 (Z cities) — 8% HRA</option>
                    </select>
                </div>
                <div>
                    <label className="block text-sm font-semibold mb-1">Years of Service</label>
                    <input type="number" value={years} onChange={(e) => setYears(e.target.value)} min="0" max="35" className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm" />
                </div>
                <div className="flex items-center gap-2">
                    <input type="checkbox" id="npa" checked={allowNPA} onChange={(e) => setAllowNPA(e.target.checked)} className="h-4 w-4 rounded" />
                    <label htmlFor="npa" className="text-sm font-semibold">Include NPA (20% of basic)</label>
                </div>
            </div>

            <button onClick={calculate} className="mt-6 w-full rounded-xl bg-primary px-6 py-3 text-sm font-bold text-primary-foreground transition hover:opacity-90">
                Calculate Salary
            </button>

            {result && (
                <div className="mt-6 rounded-xl border border-border bg-muted/50 p-6">
                    <div className="grid gap-4 sm:grid-cols-2">
                        <div>
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Monthly In-Hand (approx.)</p>
                            <p className="text-3xl font-black text-foreground">₹{result.monthly.toLocaleString('en-IN')}</p>
                        </div>
                        <div>
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Annual In-Hand (approx.)</p>
                            <p className="text-3xl font-black text-foreground">₹{result.annual.toLocaleString('en-IN')}</p>
                        </div>
                    </div>
                    <div className="mt-4 grid gap-2 sm:grid-cols-3">
                        {Object.entries(result.components).map(([key, val]) => (
                            <div key={key} className="rounded-lg bg-background p-3">
                                <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">{key}</p>
                                <p className="text-sm font-bold">₹{val.toLocaleString('en-IN')}</p>
                            </div>
                        ))}
                    </div>
                    <p className="mt-3 text-xs text-muted-foreground">* Approximate calculation based on 7th CPC. Actual in-hand may vary based on deductions (NPS, IT, etc.).</p>
                </div>
            )}
        </div>
    );
}
