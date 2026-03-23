/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { analyticsAPI } from '@/lib/api';
import { BarChart3, Target, TrendingDown, TrendingUp, Lightbulb, Activity, Brain, Calendar } from 'lucide-react';
import {
    LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
    XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Area, AreaChart,
    ComposedChart
} from 'recharts';

interface TopicPerf {
    topic_name: string;
    subject_name: string;
    accuracy: number;
    total_attempts: number;
    correct_answers: number;
    avg_time_per_question: number;
}

interface TrendPoint {
    date: string;
    test_title: string;
    accuracy: number;
    score: number;
    correct: number;
    incorrect: number;
    time_minutes: number;
}

interface SubjectPrediction {
    subject: string;
    code: string;
    accuracy: number;
    predicted_correct: number;
    strength: string;
}

interface HeatmapDay {
    date: string;
    questions_practiced: number;
    tests_taken: number;
    time_spent_minutes: number;
}

const CHART_COLORS = ['#06b6d4', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#ec4899'];

interface CustomTooltipProps {
    active?: boolean;
    payload?: Array<{ color: string; name: string; value: number | string }>;
    label?: string;
}

const CustomTooltip = ({ active, payload, label }: CustomTooltipProps) => {
    if (!active || !payload?.length) return null;
    return (
        <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--glass-border)', borderRadius: '8px', padding: '12px', fontSize: '13px' }}>
            <p style={{ color: 'var(--text-primary)', fontWeight: 600, marginBottom: 4 }}>{label}</p>
            {payload.map((p, i: number) => (
                <p key={i} style={{ color: p.color }}>{p.name}: {p.value}{typeof p.value === 'number' && p.name?.includes('ccuracy') ? '%' : ''}</p>
            ))}
        </div>
    );
};

export default function AnalyticsPage() {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const [weakTopics, setWeakTopics] = useState<TopicPerf[]>([]);
    const [strongTopics, setStrongTopics] = useState<TopicPerf[]>([]);
    const [suggestions, setSuggestions] = useState<string[]>([]);
    const [allPerf, setAllPerf] = useState<TopicPerf[]>([]);
    const [trend, setTrend] = useState<TrendPoint[]>([]);
    const [prediction, setPrediction] = useState<Record<string, unknown> | null>(null);
    const [heatmap, setHeatmap] = useState<HeatmapDay[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) { router.push('/login'); return; }
        if (isAuthenticated) {
            Promise.all([
                analyticsAPI.getWeakTopics().catch(() => ({ data: { weak_topics: [], strong_topics: [], suggestions: [] } })),
                analyticsAPI.getTopicPerformance().catch(() => ({ data: [] })),
                analyticsAPI.getPerformanceTrend().catch(() => ({ data: { trend: [] } })),
                analyticsAPI.getScorePrediction().catch(() => ({ data: null })),
                analyticsAPI.getHeatmap().catch(() => ({ data: [] })),
            ]).then(([weakRes, perfRes, trendRes, predRes, heatRes]) => {
                setWeakTopics(weakRes.data.weak_topics || []);
                setStrongTopics(weakRes.data.strong_topics || []);
                setSuggestions(weakRes.data.suggestions || []);
                setAllPerf(perfRes.data || []);
                setTrend(trendRes.data.trend || trendRes.data || []);
                setPrediction(predRes.data);
                setHeatmap(heatRes.data || []);
            }).finally(() => setLoading(false));
        }
    }, [authLoading, isAuthenticated, router]);

    // Aggregate subject data for pie chart
    const subjectData = allPerf.reduce((acc: Record<string, { subject: string; total: number; correct: number }>, p) => {
        if (!acc[p.subject_name]) acc[p.subject_name] = { subject: p.subject_name, total: 0, correct: 0 };
        acc[p.subject_name].total += p.total_attempts;
        acc[p.subject_name].correct += p.correct_answers;
        return acc;
    }, {});
    const pieData = Object.values(subjectData).map(s => ({
        name: s.subject,
        value: s.total,
        accuracy: s.total > 0 ? Math.round(s.correct / s.total * 100) : 0,
    })).filter(s => s.value > 0);

    return (
        <div className="min-h-screen bg-background">
            <Sidebar />
            <div className="main-content">
                <Header />
                <div className="page-container">
                <h1 className="text-2xl font-bold mb-1 flex items-center gap-2">
                    <BarChart3 className="w-6 h-6" style={{ color: 'var(--accent-primary)' }} />
                    Performance Analytics
                </h1>
                <p className="text-sm mb-6" style={{ color: 'var(--text-secondary)' }}>Detailed breakdown of your UPSC CMS preparation progress</p>

                {loading ? (
                    <div className="glass-card p-8 text-center"><div className="animate-pulse gradient-text">Loading analytics...</div></div>
                ) : (
                    <>
                        {/* Score Prediction Card */}
                        {prediction && prediction.predicted_score !== null && (
                            <div className="glass-card p-6 mb-6" style={{ borderColor: 'rgba(6, 182, 212, 0.3)' }}>
                                <div className="flex flex-wrap items-center justify-between gap-4">
                                    <div>
                                        <h3 className="font-bold mb-1 flex items-center gap-2">
                                            <Brain className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                                            AI Score Prediction
                                        </h3>
                                        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                                            Based on {prediction.tests_taken} tests • Confidence: {prediction.confidence} • Trend: {prediction.trend}
                                        </p>
                                    </div>
                                    <div className="text-right">
                                        <div className="text-3xl font-bold gradient-text">{prediction.predicted_score} / {prediction.max_score}</div>
                                        <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                                            P1: {prediction.predicted_score_paper1} | P2: {prediction.predicted_score_paper2}
                                        </div>
                                    </div>
                                </div>
                                {prediction.subject_predictions && prediction.subject_predictions.length > 0 && (
                                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
                                        {(prediction.subject_predictions as SubjectPrediction[]).map((sp, i) => (
                                            <div key={i} className="p-3 rounded-lg text-center" style={{ background: 'var(--bg-secondary)' }}>
                                                <div className="text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>{sp.subject}</div>
                                                <div className="text-lg font-bold" style={{ color: sp.strength === 'strong' ? '#10b981' : sp.strength === 'weak' ? '#ef4444' : '#f59e0b' }}>
                                                    {sp.accuracy}%
                                                </div>
                                                <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{sp.predicted_correct}/24 Qs</div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* AI Suggestions */}
                        {suggestions.length > 0 && (
                            <div className="glass-card p-6 mb-6" style={{ borderColor: 'rgba(245, 158, 11, 0.3)' }}>
                                <h3 className="font-bold mb-3 flex items-center gap-2">
                                    <Lightbulb className="w-5 h-5" style={{ color: '#f59e0b' }} />
                                    AI Recommendations
                                </h3>
                                <div className="space-y-2">
                                    {suggestions.map((s, i) => (
                                        <div key={i} className="flex items-start gap-2 p-3 rounded-lg text-sm"
                                            style={{ background: 'rgba(245, 158, 11, 0.05)' }}>
                                            <Target className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: '#f59e0b' }} />
                                            <span>{s}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Charts Row */}
                        <div className="grid md:grid-cols-2 gap-6 mb-6">
                            {/* Performance Trend Chart */}
                            <div className="glass-card p-6">
                                <h3 className="font-bold mb-4 flex items-center gap-2">
                                    <TrendingUp className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                                    Accuracy Trend
                                </h3>
                                {trend.length === 0 ? (
                                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Take some tests to see your accuracy trend!</p>
                                ) : (
                                    <ResponsiveContainer width="100%" height={250}>
                                        <AreaChart data={trend}>
                                            <defs>
                                                <linearGradient id="accGrad" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3} />
                                                    <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                                                </linearGradient>
                                            </defs>
                                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(139,149,168,0.1)" />
                                            <XAxis dataKey="date" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} tickFormatter={v => v.slice(5)} />
                                            <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                                            <Tooltip content={<CustomTooltip />} />
                                            <Area type="monotone" dataKey="accuracy" name="Accuracy" stroke="#06b6d4" fill="url(#accGrad)" strokeWidth={2} dot={{ fill: '#06b6d4', r: 4 }} />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                )}
                            </div>

                            {/* Subject Distribution Pie */}
                            <div className="glass-card p-6">
                                <h3 className="font-bold mb-4 flex items-center gap-2">
                                    <Activity className="w-5 h-5" style={{ color: 'var(--accent-secondary)' }} />
                                    Subject Distribution
                                </h3>
                                {pieData.length === 0 ? (
                                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Practice more to see subject-wise breakdown!</p>
                                ) : (
                                    <ResponsiveContainer width="100%" height={250}>
                                        <PieChart>
                                            <Pie data={pieData} cx="50%" cy="50%" innerRadius={55} outerRadius={90} paddingAngle={3} dataKey="value" nameKey="name" label={({ name, payload }: { name: string; payload: { accuracy: number } }) => `${name} (${payload?.accuracy ?? 0}%)`}>
                                                {pieData.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                                            </Pie>
                                            <Tooltip content={<CustomTooltip />} />
                                        </PieChart>
                                    </ResponsiveContainer>
                                )}
                            </div>
                        </div>

                        {/* Score Trend Bar Chart */}
                        {trend.length > 0 && (
                            <div className="glass-card p-6 mb-6">
                                <h3 className="font-bold mb-4 flex items-center gap-2">
                                    <BarChart3 className="w-5 h-5" style={{ color: '#10b981' }} />
                                    Score & Time Per Test
                                </h3>
                                <ResponsiveContainer width="100%" height={250}>
                                    <ComposedChart data={trend}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(139,149,168,0.1)" />
                                        <XAxis dataKey="date" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} tickFormatter={v => v.slice(5)} />
                                        <YAxis yAxisId="left" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                                        <YAxis yAxisId="right" orientation="right" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                                        <Tooltip content={<CustomTooltip />} />
                                        <Legend wrapperStyle={{ color: 'var(--text-secondary)', fontSize: 12 }} />
                                        <Bar yAxisId="left" dataKey="correct" name="Correct" fill="#10b981" radius={[4, 4, 0, 0]} />
                                        <Bar yAxisId="left" dataKey="incorrect" name="Incorrect" fill="#ef4444" radius={[4, 4, 0, 0]} />
                                        <Line yAxisId="right" type="monotone" dataKey="time_minutes" name="Time (min)" stroke="#f59e0b" strokeWidth={2} dot={{ fill: '#f59e0b' }} />
                                    </ComposedChart>
                                </ResponsiveContainer>
                            </div>
                        )}

                        {/* Study Heatmap */}
                        {heatmap.length > 0 && (
                            <div className="glass-card p-6 mb-6">
                                <h3 className="font-bold mb-4 flex items-center gap-2">
                                    <Calendar className="w-5 h-5" style={{ color: '#8b5cf6' }} />
                                    Study Activity Heatmap
                                </h3>
                                <div className="flex flex-wrap gap-1">
                                    {heatmap.slice(-90).map((d, i) => {
                                        const intensity = d.questions_practiced + (d.tests_taken * 10);
                                        let bg = 'var(--bg-card)';
                                        if (intensity > 50) bg = '#10b981';
                                        else if (intensity > 20) bg = 'rgba(16,185,129,0.6)';
                                        else if (intensity > 5) bg = 'rgba(16,185,129,0.3)';
                                        else if (intensity > 0) bg = 'rgba(16,185,129,0.15)';
                                        return (
                                            <div key={i} className="w-3 h-3 rounded-sm" style={{ background: bg }}
                                                title={`${d.date}: ${d.questions_practiced} Qs, ${d.tests_taken} tests`} />
                                        );
                                    })}
                                </div>
                                <div className="flex items-center gap-2 mt-3 text-xs" style={{ color: 'var(--text-secondary)' }}>
                                    <span>Less</span>
                                    {['var(--bg-card)', 'rgba(16,185,129,0.15)', 'rgba(16,185,129,0.3)', 'rgba(16,185,129,0.6)', '#10b981'].map((c, i) => (
                                        <div key={i} className="w-3 h-3 rounded-sm" style={{ background: c }} />
                                    ))}
                                    <span>More</span>
                                </div>
                            </div>
                        )}

                        <div className="grid md:grid-cols-2 gap-6 mb-6">
                            {/* Weak Topics */}
                            <div className="glass-card p-6">
                                <h3 className="font-bold mb-4 flex items-center gap-2">
                                    <TrendingDown className="w-5 h-5" style={{ color: '#ef4444' }} />
                                    Weak Topics
                                </h3>
                                {weakTopics.length === 0 ? (
                                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>No weak topics identified yet. Keep practicing!</p>
                                ) : (
                                    <div className="space-y-3">
                                        {weakTopics.map((t, i) => (
                                            <div key={i} className="flex justify-between items-center p-3 rounded-lg" style={{ background: 'var(--bg-secondary)' }}>
                                                <div>
                                                    <div className="text-sm font-medium">{t.topic_name}</div>
                                                    <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{t.subject_name} &bull; {t.total_attempts} attempts</div>
                                                </div>
                                                <div className="text-right">
                                                    <span className="text-sm font-bold" style={{ color: '#ef4444' }}>{t.accuracy}%</span>
                                                    <div className="w-16 h-1.5 rounded-full mt-1" style={{ background: 'var(--bg-card)' }}>
                                                        <div className="h-full rounded-full" style={{ width: `${t.accuracy}%`, background: '#ef4444' }} />
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>

                            {/* Strong Topics */}
                            <div className="glass-card p-6">
                                <h3 className="font-bold mb-4 flex items-center gap-2">
                                    <TrendingUp className="w-5 h-5" style={{ color: '#10b981' }} />
                                    Strong Topics
                                </h3>
                                {strongTopics.length === 0 ? (
                                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Keep practicing to build your strong areas!</p>
                                ) : (
                                    <div className="space-y-3">
                                        {strongTopics.map((t, i) => (
                                            <div key={i} className="flex justify-between items-center p-3 rounded-lg" style={{ background: 'var(--bg-secondary)' }}>
                                                <div>
                                                    <div className="text-sm font-medium">{t.topic_name}</div>
                                                    <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{t.subject_name} &bull; {t.total_attempts} attempts</div>
                                                </div>
                                                <div className="text-right">
                                                    <span className="text-sm font-bold" style={{ color: '#10b981' }}>{t.accuracy}%</span>
                                                    <div className="w-16 h-1.5 rounded-full mt-1" style={{ background: 'var(--bg-card)' }}>
                                                        <div className="h-full rounded-full" style={{ width: `${t.accuracy}%`, background: '#10b981' }} />
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* All Topic Performance Table */}
                        <div className="glass-card p-6">
                            <h3 className="font-bold mb-4 flex items-center gap-2">
                                <Activity className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                                All Topic Performance
                            </h3>
                            {allPerf.length === 0 ? (
                                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                                    Take some tests to see detailed topic-wise analytics here!
                                </p>
                            ) : (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr style={{ borderBottom: '1px solid var(--glass-border)' }}>
                                                <th className="text-left py-2 font-medium" style={{ color: 'var(--text-secondary)' }}>Topic</th>
                                                <th className="text-left py-2 font-medium" style={{ color: 'var(--text-secondary)' }}>Subject</th>
                                                <th className="text-center py-2 font-medium" style={{ color: 'var(--text-secondary)' }}>Attempts</th>
                                                <th className="text-center py-2 font-medium" style={{ color: 'var(--text-secondary)' }}>Accuracy</th>
                                                <th className="text-center py-2 font-medium" style={{ color: 'var(--text-secondary)' }}>Avg Time</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {allPerf.map((p, i) => (
                                                <tr key={i} style={{ borderBottom: '1px solid rgba(139, 149, 168, 0.05)' }}>
                                                    <td className="py-2">{p.topic_name}</td>
                                                    <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{p.subject_name}</td>
                                                    <td className="py-2 text-center">{p.total_attempts}</td>
                                                    <td className="py-2 text-center">
                                                        <span style={{ color: p.accuracy >= 70 ? '#10b981' : p.accuracy >= 40 ? '#f59e0b' : '#ef4444' }}>
                                                            {p.accuracy}%
                                                        </span>
                                                    </td>
                                                    <td className="py-2 text-center" style={{ color: 'var(--text-secondary)' }}>{p.avg_time_per_question}s</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    </>
                )}
                </div>
            </div>
        </div>
    );
}
