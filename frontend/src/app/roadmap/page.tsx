'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { aiAPI, analyticsAPI } from '@/lib/api';
import { Map, Target, Brain, TrendingUp, Calendar, Sparkles, ChevronDown, ChevronUp } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

export default function RoadmapPage() {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const [studyPlan, setStudyPlan] = useState('');
    const [highYield, setHighYield] = useState('');
    const [loading, setLoading] = useState(false);
    const [activeTab, setActiveTab] = useState<'plan' | 'highyield'>('plan');
    const [daysRemaining, setDaysRemaining] = useState(60);
    const [weakTopics, setWeakTopics] = useState<string[]>([]);
    const [expandedPhase, setExpandedPhase] = useState<number | null>(0);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) router.push('/login');
    }, [authLoading, isAuthenticated, router]);

    // Fetch weak topics for study plan
    useEffect(() => {
        if (isAuthenticated) {
            analyticsAPI.getWeakTopics().then(res => {
                const topics = (res.data?.weak_topics || []).map((t: { topic_name?: string; name?: string; topic?: string } | string) => t && typeof t === 'object' ? (t.topic_name || t.name || t.topic || '') : t);
                setWeakTopics(topics.slice(0, 5));
            }).catch(() => { });
        }
    }, [isAuthenticated]);

    const generatePlan = async () => {
        setLoading(true);
        try {
            const res = await aiAPI.getStudyPlan({
                weak_topics: weakTopics,
                days_remaining: daysRemaining,
            });
            setStudyPlan(res.data.study_plan);
        } catch {
            setStudyPlan('Failed to generate study plan. Please configure AI API keys in backend/.env');
        }
        setLoading(false);
    };

    const fetchHighYield = async () => {
        setLoading(true);
        try {
            const res = await aiAPI.getHighYieldTopics();
            setHighYield(res.data.predictions);
        } catch {
            setHighYield('Failed to fetch predictions. Please configure AI API keys.');
        }
        setLoading(false);
    };

    const phases = [
        { title: 'Phase 1: Foundation', desc: 'Core subject revision — Harrison, Ghai, Park', weeks: '1-3', color: '#06b6d4' },
        { title: 'Phase 2: Deep Dive', desc: 'Weak area focused intensive study + PYQs', weeks: '4-6', color: '#8b5cf6' },
        { title: 'Phase 3: Practice', desc: 'Mock tests, PYQ solving, time management', weeks: '7-8', color: '#f59e0b' },
        { title: 'Phase 4: Revision', desc: 'Quick revision, mnemonics, high-yield review', weeks: '9-10', color: '#10b981' },
    ];

    return (
        <div className="min-h-screen bg-background">
            <Sidebar />
            <div className="main-content">
                <Header />
                <div className="page-container">
                <h1 className="text-2xl font-bold mb-1 flex items-center gap-2">
                    <Map className="w-6 h-6" style={{ color: 'var(--accent-primary)' }} />
                    AI-Powered Personalized Study Plan
                </h1>
                <p className="text-sm mb-6" style={{ color: 'var(--text-secondary)' }}>
                    Designed specifically for UPSC CMS — tailored to your weak areas and exam timeline
                </p>

                {/* Phase Timeline */}
                <div className="glass-card p-6 mb-6">
                    <h3 className="font-bold mb-4 flex items-center gap-2">
                        <Target className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                        Preparation Phases
                    </h3>
                    <div className="space-y-3">
                        {phases.map((phase, i) => (
                            <div key={i} className="p-4 rounded-xl cursor-pointer transition-all"
                                style={{
                                    background: expandedPhase === i ? `${phase.color}11` : 'rgba(139,149,168,0.05)',
                                    border: `1px solid ${expandedPhase === i ? phase.color + '44' : 'transparent'}`
                                }}
                                onClick={() => setExpandedPhase(expandedPhase === i ? null : i)}>
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-3">
                                        <div className="w-3 h-3 rounded-full" style={{ background: phase.color }} />
                                        <div>
                                            <div className="font-medium text-sm">{phase.title}</div>
                                            <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                                                Weeks {phase.weeks}
                                            </div>
                                        </div>
                                    </div>
                                    {expandedPhase === i ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                                </div>
                                {expandedPhase === i && (
                                    <p className="mt-3 text-sm pl-6" style={{ color: 'var(--text-secondary)' }}>
                                        {phase.desc}
                                    </p>
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                {/* Tab Buttons */}
                <div className="flex gap-3 mb-6">
                    <button onClick={() => setActiveTab('plan')}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${activeTab === 'plan' ? 'btn-primary' : 'btn-secondary'}`}>
                        <Brain className="w-4 h-4" /> Personalized Study Plan
                    </button>
                    <button onClick={() => setActiveTab('highyield')}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${activeTab === 'highyield' ? 'btn-primary' : 'btn-secondary'}`}>
                        <TrendingUp className="w-4 h-4" /> High Yield Topics
                    </button>
                </div>

                {activeTab === 'plan' && (
                    <div className="space-y-4">
                        {/* Config */}
                        <div className="glass-card p-4 flex flex-wrap items-center gap-4">
                            <div className="flex items-center gap-2">
                                <Calendar className="w-4 h-4" style={{ color: 'var(--accent-primary)' }} />
                                <span className="text-sm">Days Remaining:</span>
                                <input type="number" value={daysRemaining} onChange={e => setDaysRemaining(Number(e.target.value))}
                                    className="input-field w-20 text-center" min={1} max={365} />
                            </div>
                            <button onClick={generatePlan} disabled={loading} className="btn-primary text-sm">
                                <Sparkles className="w-4 h-4" />
                                {loading ? 'Generating...' : 'Generate AI Study Plan'}
                            </button>
                        </div>

                        {/* Weak topics */}
                        {weakTopics.length > 0 && (
                            <div className="glass-card p-4">
                                <div className="text-sm font-medium mb-2">Your Weak Areas (from analytics):</div>
                                <div className="flex flex-wrap gap-2">
                                    {weakTopics.map((t, i) => (
                                        <span key={i} className="badge" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>
                                            {t}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Plan Result */}
                        {studyPlan && (
                            <div className="glass-card p-6 animate-fadeInUp prose prose-invert max-w-none">
                                <ReactMarkdown>{studyPlan}</ReactMarkdown>
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'highyield' && (
                    <div className="space-y-4">
                        <div className="glass-card p-4 flex items-center justify-between">
                            <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                                AI-analyzed PYQ trends (2018-2024) to predict high-yield topics
                            </span>
                            <button onClick={fetchHighYield} disabled={loading} className="btn-primary text-sm">
                                <TrendingUp className="w-4 h-4" />
                                {loading ? 'Analyzing...' : 'Analyze PYQ Trends'}
                            </button>
                        </div>

                        {highYield && (
                            <div className="glass-card p-6 animate-fadeInUp prose prose-invert max-w-none">
                                <ReactMarkdown>{highYield}</ReactMarkdown>
                            </div>
                        )}
                    </div>
                )}
                </div>
            </div>
        </div>
    );
}
