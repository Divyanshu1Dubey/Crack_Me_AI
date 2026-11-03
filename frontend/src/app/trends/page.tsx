'use client';
import { useEffect, useState } from 'react';
import {
    Calendar,
    ArrowUpRight,
    ArrowDownRight,
    AlertCircle,
    Brain,
    Zap,
    Target,
    Activity,
    Star,
    Flame,
    BookOpen,
    ChevronDown, ChevronUp
} from 'lucide-react';
import api from '@/lib/api';
import { useRequireAuth } from '@/lib/hooks/useRequireAuth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';

interface TrendItem {
    year: number;
    subject__name: string;
    subject__code: string;
    count: number;
}

interface SubjectStat {
    name: string;
    code: string;
    count: number;
    color?: string;
}

// GET /api/analytics/pyq-trends/ — real year x subject counts of the PYQ bank.
interface StatsData {
    total: number;
    years: number[];
    trends: TrendItem[];
    subjects: SubjectStat[];
}

// High-yield PYQ topics with star ratings
const HIGH_YIELD_TOPICS = [
    {
        subject: 'Medicine (Paper I)',
        color: '#06b6d4',
        topics: [
            { name: 'Hypertension', stars: 3, ref: "Harrison's Ch.241", note: 'Increasing frequency, guaranteed questions', trend: 'up' },
            { name: 'Diabetes Mellitus', stars: 3, ref: "Harrison's Ch.344", note: 'Guaranteed questions, high-yield', trend: 'up' },
            { name: 'Acute Coronary Syndromes', stars: 2, ref: "Harrison's Ch.238", note: 'Increasing frequency, important', trend: 'up' },
            { name: 'Chronic Kidney Disease', stars: 2, ref: "Harrison's Ch.296", note: 'Guaranteed questions, high-yield', trend: 'up' },
            { name: 'Stroke', stars: 2, ref: "Harrison's Ch.243", note: 'Increasing frequency, important', trend: 'up' },
            { name: 'Pneumonia', stars: 2, ref: "Harrison's Ch.170", note: 'Guaranteed questions, high-yield', trend: 'stable' },
            { name: 'Hepatitis', stars: 2, ref: "Harrison's Ch.305", note: 'Increasing frequency, important', trend: 'up' },
            { name: 'Rheumatoid Arthritis', stars: 1, ref: "Harrison's Ch.344", note: 'Important, but less frequent', trend: 'stable' },
            { name: 'Mental Health Disorders', stars: 2, ref: "Harrison's Ch.419", note: 'Increasing frequency, important', trend: 'up' },
            { name: 'Antibiotic Resistance', stars: 2, ref: "Harrison's Ch.169", note: 'Increasing frequency, important', trend: 'up' },
        ],
    },
    {
        subject: 'Pediatrics (Paper I)',
        color: '#8b5cf6',
        topics: [
            { name: 'Growth and Development', stars: 3, ref: "Ghai Essential Pediatrics Ch.1", note: 'Guaranteed questions, high-yield', trend: 'up' },
            { name: 'Immunization Schedule', stars: 2, ref: "Ghai Essential Pediatrics Ch.15", note: 'Increasing frequency, important', trend: 'up' },
            { name: 'Neonatal Disorders', stars: 2, ref: "Ghai Essential Pediatrics Ch.10", note: 'Guaranteed questions, high-yield', trend: 'stable' },
            { name: 'Pediatric Infections', stars: 2, ref: "Ghai Essential Pediatrics Ch.13", note: 'Important, increasing', trend: 'up' },
        ],
    },
    {
        subject: 'Surgery (Paper II)',
        color: '#f59e0b',
        topics: [
            { name: 'GI Surgery (Colorectal)', stars: 3, ref: "Bailey & Love Ch.68", note: 'Most tested surgical topic', trend: 'up' },
            { name: 'Trauma & Emergency Surgery', stars: 2, ref: "Bailey & Love Ch.20", note: 'High-yield in exams', trend: 'up' },
            { name: 'Breast Surgery', stars: 2, ref: "Bailey & Love Ch.54", note: 'Important, consistent', trend: 'stable' },
            { name: 'Thyroid Disorders', stars: 2, ref: "Bailey & Love Ch.52", note: 'Guaranteed questions', trend: 'up' },
        ],
    },
    {
        subject: 'Obstetrics & Gynecology (Paper II)',
        color: '#ec4899',
        topics: [
            { name: 'Normal Labor & Delivery', stars: 3, ref: "DC Dutta Obstetrics Ch.12", note: 'Guaranteed questions, high-yield', trend: 'up' },
            { name: 'Preeclampsia/Eclampsia', stars: 3, ref: "DC Dutta Obstetrics Ch.17", note: 'Most tested OBG topic', trend: 'up' },
            { name: 'Cervical Cancer', stars: 2, ref: "Shaw\'s Gynecology Ch.28", note: 'Increasing, high-yield', trend: 'up' },
            { name: 'PCOS', stars: 2, ref: "Shaw\'s Gynecology Ch.20", note: 'Important, consistent', trend: 'stable' },
        ],
    },
    {
        subject: 'PSM / Community Medicine (Paper II)',
        color: '#10b981',
        topics: [
            { name: 'Epidemiology & Biostatistics', stars: 3, ref: "Park\'s PSM Ch.2", note: 'Always high-yield in Paper II', trend: 'up' },
            { name: 'National Health Programs', stars: 3, ref: "Park\'s PSM Ch.12", note: 'Guaranteed questions', trend: 'up' },
            { name: 'Environmental Health', stars: 2, ref: "Park\'s PSM Ch.7", note: 'Important, increasing', trend: 'up' },
            { name: 'Nutrition', stars: 2, ref: "Park\'s PSM Ch.11", note: 'Consistent, high-yield', trend: 'stable' },
        ],
    },
];

export default function TrendsPage() {
    // Member page (like the endpoint): wait for auth, then load. The request
    // used to fire before the session was ready and render only dashes.
    const { ready } = useRequireAuth();
    const [stats, setStats] = useState<StatsData | null>(null);
    const [loading, setLoading] = useState(true);
    const [expandedSubject, setExpandedSubject] = useState<number | null>(0);

    useEffect(() => {
        if (!ready) return;
        api.get('/analytics/pyq-trends/', { params: { exam_source: 'UPSC CMS' } }).then(res => {
            setStats(res.data);
            setLoading(false);
        }).catch(() => setLoading(false));
    }, [ready]);

    // Process trends data
    const trends: TrendItem[] = stats?.trends || [];
    const years = stats?.years?.length ? stats.years : Array.from(new Set(trends.map(t => t.year))).sort((a, b) => b - a);
    const subjects = stats?.subjects || [];
    const countFor = (year: number, code: string) =>
        trends.find(t => t.year === year && t.subject__code === code)?.count || 0;
    const yearRange = years.length ? `${years[years.length - 1]}–${years[0]}` : '';
    const maxCell = Math.max(1, ...trends.map(t => t.count));

    return (
        <div className="min-h-screen bg-background">
            <Sidebar />
            <div className="main-content">
                <Header />
                <div className="page-container">
                {loading ? (
                    <div className="flex flex-col items-center justify-center py-24 gap-4">
                        <div className="w-10 h-10 rounded-full border-4 border-primary border-t-transparent animate-spin"></div>
                        <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Analyzing Exam Patterns...</p>
                    </div>
                ) : (
                <div className="space-y-8 animate-fadeIn">

                {/* Page Description */}
                <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                        Track the evolution of UPSC CMS papers. Identify high-yield subjects and master the changing exam pattern.
                    </p>
                    <div className="flex items-center gap-3 p-2 glass-card rounded-2xl">
                        <div className="p-3 rounded-xl text-white" style={{ background: 'var(--accent-primary)' }}>
                            <Calendar className="w-5 h-5" />
                        </div>
                        <div className="pr-4">
                            <div className="text-xs font-bold uppercase" style={{ color: 'var(--text-secondary)' }}>Latest Data</div>
                            <div className="text-lg font-black">{years[0] ? `${years[0]} Examination` : '—'}</div>
                        </div>
                    </div>
                </div>

                {/* Top Insights Matrix */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="glass-card p-5 border-l-4 border-l-[var(--accent-primary)] group hover:scale-[1.02] transition-transform cursor-default">
                        <div className="flex justify-between items-start mb-3">
                            <div className="p-2 bg-cyan-500/10 rounded-xl text-cyan-400">
                                <Brain className="w-5 h-5" />
                            </div>
                            {years.length > 0 && (
                                <span className="text-xs font-bold text-cyan-400 bg-cyan-400/10 px-2 py-1 rounded-full">{years.length} exam years</span>
                            )}
                        </div>
                        <h3 className="font-bold mb-1">Total Questions</h3>
                        <p className="text-2xl font-black gradient-text mb-1">{stats ? stats.total.toLocaleString() : '—'}</p>
                        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>UPSC CMS questions in our question bank{yearRange ? ` (${yearRange})` : ''}.</p>
                    </div>

                    <div className="glass-card p-5 border-l-4 border-l-[var(--accent-secondary)] group hover:scale-[1.02] transition-transform cursor-default">
                        <div className="flex justify-between items-start mb-3">
                            <div className="p-2 bg-purple-500/10 rounded-xl text-purple-400">
                                <Target className="w-5 h-5" />
                            </div>
                            <span className="text-xs font-bold text-purple-400 bg-purple-400/10 px-2 py-1 rounded-full">High Influence</span>
                        </div>
                        <h3 className="font-bold mb-1">Core Subjects</h3>
                        <p className="text-2xl font-black gradient-text mb-1">{stats ? subjects.length : '—'}</p>
                        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Subjects with dated PYQs in our bank (the exam has 5 major clinical sections).</p>
                    </div>

                    <div className="glass-card p-5 border-l-4 border-l-pink-500 group hover:scale-[1.02] transition-transform cursor-default">
                        <div className="flex justify-between items-start mb-3">
                            <div className="p-2 bg-pink-500/10 rounded-xl text-pink-400">
                                <Zap className="w-5 h-5" />
                            </div>
                            <span className="text-xs font-bold text-pink-400 bg-pink-400/10 px-2 py-1 rounded-full">Most Frequent</span>
                        </div>
                        <h3 className="font-bold mb-1">Top Subject</h3>
                        <p className="text-2xl font-black gradient-text mb-1">{subjects[0]?.name || '—'}</p>
                        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                            {subjects[0] ? `${subjects[0].count.toLocaleString()} dated PYQs — the most of any subject in our bank.` : 'No dated PYQs yet.'}
                        </p>
                    </div>
                </div>

                {/* Trend Table / Matrix */}
                <div className="glass-card overflow-hidden">
                    <div className="p-5 border-b border-[var(--glass-border)] flex items-center justify-between" style={{ background: 'linear-gradient(to right, rgba(6,182,212,0.05), transparent)' }}>
                        <div className="flex items-center gap-3">
                            <Activity className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                            <h2 className="text-lg font-black">Year-wise Subject Weightage</h2>
                        </div>
                    </div>

                    {years.length === 0 ? (
                        <p className="p-6 text-sm" style={{ color: 'var(--text-secondary)' }}>
                            {stats ? 'No dated UPSC CMS questions in the bank yet.' : 'Could not load exam trends. Please refresh the page.'}
                        </p>
                    ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse">
                            <thead>
                                <tr className="bg-[var(--bg-secondary)]/50">
                                    <th className="p-6 font-bold text-[var(--text-secondary)] uppercase tracking-wider text-sm border-b border-[var(--glass-border)]">Subject</th>
                                    {years.map(year => (
                                        <th key={year} className="p-6 font-black text-center border-b border-[var(--glass-border)]">
                                            <div className="text-lg">{year}</div>
                                            <div className="text-[10px] text-[var(--text-secondary)] font-bold uppercase">Questions</div>
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-[var(--glass-border)]">
                                {subjects.map((sub: SubjectStat) => (
                                    <tr key={sub.code} className="hover:bg-[var(--accent-primary)]/5 transition-colors group">
                                        <td className="p-6">
                                            <div className="flex items-center gap-4">
                                                <div className="w-3 h-12 rounded-full" style={{ background: sub.color || 'var(--accent-primary)' }}></div>
                                                <div>
                                                    <div className="font-black text-lg group-hover:text-[var(--accent-primary)] transition-colors">{sub.name}</div>
                                                    {/* The "Imported" bucket is shown as "Expert Curated"; its code is internal. */}
                                                    {sub.code && sub.code.toUpperCase() !== 'IMPORTED' && (
                                                        <div className="text-xs text-[var(--text-secondary)] font-bold tracking-widest uppercase">{sub.code} Section</div>
                                                    )}
                                                </div>
                                            </div>
                                        </td>
                                        {years.map((year, yi) => {
                                            const count = countFor(year, sub.code);
                                            // Real change vs the previous exam year in the bank (columns are newest first).
                                            const previousYear = years[yi + 1];
                                            const previous = previousYear !== undefined ? countFor(previousYear, sub.code) : null;
                                            const trendDirection = previous === null || previous === count ? null : (count > previous ? 'up' : 'down');

                                            return (
                                                <td key={year} className="p-6 text-center">
                                                    <div className="relative inline-block">
                                                        <span className="text-2xl font-black">{count}</span>
                                                        {count > 0 && trendDirection && (
                                                            <div className="absolute -right-6 top-1" title={`${previous} in ${previousYear}`}>
                                                                {trendDirection === 'up' ? (
                                                                    <ArrowUpRight className="w-4 h-4 text-emerald-500" />
                                                                ) : (
                                                                    <ArrowDownRight className="w-4 h-4 text-rose-500 opacity-50" />
                                                                )}
                                                            </div>
                                                        )}
                                                    </div>
                                                    {count > 0 && (
                                                        <div className="w-24 mx-auto h-1.5 bg-[var(--bg-card)] rounded-full mt-2 overflow-hidden border border-[var(--glass-border)]">
                                                            <div
                                                                className="h-full rounded-full transition-all duration-1000"
                                                                style={{
                                                                    width: `${Math.min(100, (count / maxCell) * 100)}%`,
                                                                    background: sub.color || 'var(--accent-primary)'
                                                                }}
                                                            ></div>
                                                        </div>
                                                    )}
                                                </td>
                                            );
                                        })}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    )}
                </div>

                {/* Curated PYQ High-Yield Topics (editorial list, not computed) */}
                <div className="glass-card overflow-hidden">
                    <div className="p-5 border-b border-[var(--glass-border)] flex items-center gap-3" style={{ background: 'linear-gradient(to right, rgba(139,92,246,0.08), transparent)' }}>
                        <div className="p-2 rounded-xl text-white" style={{ background: 'var(--accent-primary)' }}>
                            <Star className="w-5 h-5" />
                        </div>
                        <div>
                            <h2 className="text-lg font-black">Curated High-Yield PYQ Topics</h2>
                            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Editorial picks from past papers · ★★★ = Must do · ★★ = Important · ★ = Watch</p>
                        </div>
                    </div>
                    <div className="divide-y divide-[var(--glass-border)]">
                        {HIGH_YIELD_TOPICS.map((section, si) => (
                            <div key={si}>
                                <button
                                    onClick={() => setExpandedSubject(expandedSubject === si ? null : si)}
                                    className="w-full flex items-center justify-between p-4 hover:bg-[var(--accent-primary)]/5 transition-colors">
                                    <div className="flex items-center gap-3">
                                        <div className="w-3 h-3 rounded-full" style={{ background: section.color }}></div>
                                        <span className="font-bold text-sm">{section.subject}</span>
                                        <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: `${section.color}15`, color: section.color }}>
                                            {section.topics.length} topics
                                        </span>
                                    </div>
                                    {expandedSubject === si ? <ChevronUp className="w-4 h-4" style={{ color: 'var(--text-secondary)' }} /> : <ChevronDown className="w-4 h-4" style={{ color: 'var(--text-secondary)' }} />}
                                </button>
                                {expandedSubject === si && (
                                    <div className="pb-3 px-3 space-y-2">
                                        {section.topics.map((topic, ti) => (
                                            <div key={ti} className="flex items-start gap-3 p-3 rounded-xl transition-all hover:scale-[1.01]"
                                                style={{ background: `${section.color}06`, border: `1px solid ${section.color}20` }}>
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2 flex-wrap">
                                                        <span className="font-bold text-sm">{topic.name}</span>
                                                        <span className="text-amber-500 text-xs tracking-widest">
                                                            {Array(topic.stars).fill('★').join('')}{Array(3 - topic.stars).fill('☆').join('')}
                                                        </span>
                                                        {topic.trend === 'up' && (
                                                            <span className="flex items-center gap-0.5 text-xs text-emerald-500 font-medium">
                                                                <ArrowUpRight className="w-3 h-3" /> Rising
                                                            </span>
                                                        )}
                                                    </div>
                                                    <div className="flex items-center gap-1 mt-1">
                                                        <BookOpen className="w-3 h-3 shrink-0" style={{ color: section.color }} />
                                                        <span className="text-xs" style={{ color: section.color }}>{topic.ref}</span>
                                                    </div>
                                                    <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>{topic.note}</p>
                                                </div>
                                                {topic.stars === 3 && (
                                                    <span className="flex items-center gap-1 text-xs px-2 py-1 rounded-full font-bold whitespace-nowrap shrink-0"
                                                        style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444' }}>
                                                        <Flame className="w-3 h-3" /> Must Do
                                                    </span>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                {/* How to read this page (replaces an invented "AI trend detection" claim) */}
                <div className="p-5 rounded-2xl border border-dashed border-cyan-500/30 bg-cyan-500/5 flex flex-col md:flex-row items-center gap-4">
                    <div className="p-3 rounded-xl text-white shrink-0" style={{ background: '#06b6d4' }}>
                        <AlertCircle className="w-6 h-6" />
                    </div>
                    <div className="flex-1 text-center md:text-left">
                        <h4 className="font-black text-cyan-400 mb-1">How to read these trends</h4>
                        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                            Counts are the dated UPSC CMS previous-year questions in our question bank, by exam year. Arrows compare a subject with the previous exam year in the bank. Pair the table with the curated topic list above to plan your revision.
                        </p>
                    </div>
                </div>

                </div>
                )}
                </div>
            </div>
        </div>
    );
}
