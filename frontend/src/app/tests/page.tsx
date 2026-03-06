'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import { testsAPI, questionsAPI } from '@/lib/api';
import { FileText, Play, Clock, Target, Sparkles, Plus, Award, ChevronRight } from 'lucide-react';

interface TestItem {
    id: number;
    title: string;
    test_type: string;
    subject_name: string;
    num_questions: number;
    time_limit_minutes: number;
    attempt_count: number;
}

interface Subject {
    id: number;
    name: string;
    code: string;
}

export default function TestsPage() {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const [tests, setTests] = useState<TestItem[]>([]);
    const [subjects, setSubjects] = useState<Subject[]>([]);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) { router.push('/login'); return; }
        if (isAuthenticated) {
            Promise.all([
                testsAPI.list(),
                questionsAPI.getSubjects(),
            ]).then(([tRes, sRes]) => {
                setTests(tRes.data.results || tRes.data || []);
                setSubjects(sRes.data.results || sRes.data || []);
            }).catch(() => { }).finally(() => setLoading(false));
        }
    }, [authLoading, isAuthenticated, router]);

    const generateTest = async (type: string, subjectId?: number) => {
        setGenerating(true);
        try {
            const data: Record<string, string | number> = { test_type: type, num_questions: 20 };
            if (subjectId) data.subject_id = subjectId;
            if (type === 'paper1' || type === 'paper2') data.num_questions = 120;
            if (type === 'daily') data.num_questions = 20;
            const res = await testsAPI.generate(data);
            setTests(prev => [res.data, ...prev]);
        } catch (err) {
            console.error('Failed to generate test:', err);
        } finally {
            setGenerating(false);
        }
    };

    const startTest = async (testId: number) => {
        router.push(`/tests/${testId}`);
    };

    const testTypes = [
        { type: 'daily', label: 'Daily Quick Test', desc: '20 questions, mixed subjects', icon: Sparkles, color: '#f59e0b' },
        { type: 'mixed', label: 'Mixed Practice', desc: 'Questions from all subjects', icon: Target, color: '#8b5cf6' },
        { type: 'paper1', label: 'Paper 1 Mock', desc: 'Medicine + Pediatrics (120 Qs)', icon: FileText, color: '#06b6d4' },
        { type: 'paper2', label: 'Paper 2 Mock', desc: 'Surgery + OBG + PSM (120 Qs)', icon: FileText, color: '#ec4899' },
    ];

    return (
        <div style={{ background: 'var(--bg-primary)' }} className="min-h-screen">
            <Sidebar />
            <div className="main-content">
                <h1 className="text-2xl font-bold mb-1 flex items-center gap-2">
                    <FileText className="w-6 h-6" style={{ color: 'var(--accent-primary)' }} />
                    Test Center
                </h1>
                <p className="text-sm mb-6" style={{ color: 'var(--text-secondary)' }}>Generate & take practice tests</p>

                {/* Quick Generate */}
                <div className="mb-8">
                    <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                        <Plus className="w-5 h-5" style={{ color: '#10b981' }} />
                        Generate New Test
                    </h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                        {testTypes.map((tt) => (
                            <button key={tt.type} onClick={() => generateTest(tt.type)}
                                disabled={generating}
                                className="glass-card p-5 text-left group cursor-pointer hover:scale-105 transition-transform">
                                <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-3"
                                    style={{ background: `${tt.color}15`, color: tt.color }}>
                                    <tt.icon className="w-5 h-5" />
                                </div>
                                <div className="font-medium text-sm mb-1">{tt.label}</div>
                                <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{tt.desc}</div>
                            </button>
                        ))}
                    </div>

                    {/* Subject-wise tests */}
                    <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--text-secondary)' }}>Subject-wise Test</h3>
                    <div className="flex flex-wrap gap-2">
                        {subjects.map(s => (
                            <button key={s.id} onClick={() => generateTest('subject', s.id)}
                                disabled={generating}
                                className="btn-secondary text-xs py-2 px-4">
                                {s.name}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Test List */}
                <div>
                    <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                        <Award className="w-5 h-5" style={{ color: '#f59e0b' }} />
                        Available Tests
                    </h2>
                    {loading ? (
                        <div className="glass-card p-8 text-center"><div className="animate-pulse gradient-text">Loading tests...</div></div>
                    ) : tests.length === 0 ? (
                        <div className="glass-card p-8 text-center" style={{ color: 'var(--text-secondary)' }}>
                            No tests yet. Generate one above to get started!
                        </div>
                    ) : (
                        <div className="grid md:grid-cols-2 gap-4">
                            {tests.map(test => (
                                <div key={test.id} className="glass-card p-5">
                                    <div className="flex justify-between items-start mb-3">
                                        <h3 className="font-bold text-sm">{test.title}</h3>
                                        <span className="badge" style={{ background: 'rgba(6, 182, 212, 0.1)', color: 'var(--accent-primary)' }}>
                                            {test.test_type}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-4 text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
                                        <span className="flex items-center gap-1"><Target className="w-3 h-3" /> {test.num_questions} Qs</span>
                                        <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {test.time_limit_minutes} min</span>
                                        <span className="flex items-center gap-1"><Play className="w-3 h-3" /> {test.attempt_count} attempts</span>
                                    </div>
                                    <button onClick={() => startTest(test.id)} className="btn-primary w-full justify-center text-sm py-2">
                                        Start Test <ChevronRight className="w-4 h-4" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
