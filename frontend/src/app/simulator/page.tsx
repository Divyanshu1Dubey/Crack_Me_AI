'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import { testsAPI, questionsAPI } from '@/lib/api';
import { GraduationCap, Play, Clock, FileText, Target, AlertTriangle, Calendar } from 'lucide-react';

interface Subject { id: number; name: string; code: string; }

export default function SimulatorPage() {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const [, setSubjects] = useState<Subject[]>([]);
    const [years, setYears] = useState<number[]>([]);
    const [, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [pyqYear, setPyqYear] = useState<number | null>(null);
    const [activeTab, setActiveTab] = useState<'mock' | 'pyq'>('mock');

    useEffect(() => {
        if (!authLoading && !isAuthenticated) { router.push('/login'); return; }
        if (isAuthenticated) {
            Promise.all([
                questionsAPI.getSubjects(),
                questionsAPI.getYears(),
            ]).then(([sRes, yRes]) => {
                setSubjects(sRes.data.results || sRes.data || []);
                setYears(yRes.data.results || yRes.data || []);
            }).catch(() => { }).finally(() => setLoading(false));
        }
    }, [authLoading, isAuthenticated, router]);

    const startSimulation = async (paper: 'paper1' | 'paper2') => {
        setGenerating(true);
        setError(null);
        try {
            const res = await testsAPI.generate({ test_type: paper, num_questions: 120 });
            router.push(`/tests/${res.data.id}`);
        } catch (err: unknown) {
            const msg = err && typeof err === 'object' && 'response' in err ? (err as { response?: { data?: { error?: string } } }).response?.data?.error : undefined;
            setError(msg || 'Failed to generate simulation. Make sure there are enough questions in the database.');
        } finally {
            setGenerating(false);
        }
    };

    const startPyqSimulation = async () => {
        if (!pyqYear) return;
        setGenerating(true);
        setError(null);
        try {
            const res = await testsAPI.pyqSimulation({ year: pyqYear });
            router.push(`/tests/${res.data.id}`);
        } catch (err: unknown) {
            const msg = err && typeof err === 'object' && 'response' in err ? (err as { response?: { data?: { error?: string } } }).response?.data?.error : undefined;
            setError(msg || `Failed to start PYQ simulation for ${pyqYear}. No questions may exist for that year.`);
        } finally {
            setGenerating(false);
        }
    };

    const papers = [
        { key: 'paper1' as const, title: 'Paper 1 — Full Mock', subjects: ['General Medicine', 'Pediatrics'], questions: 120, time: 120, color: '#06b6d4', desc: 'Complete Paper 1 simulation with Medicine and Pediatrics questions' },
        { key: 'paper2' as const, title: 'Paper 2 — Full Mock', subjects: ['Surgery', 'OBG', 'PSM'], questions: 120, time: 120, color: '#8b5cf6', desc: 'Complete Paper 2 simulation with Surgery, OBG, and PSM questions' },
    ];

    return (
        <div style={{ background: 'var(--bg-primary)' }} className="min-h-screen">
            <Sidebar />
            <div className="main-content">
                <div className="mb-8">
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <GraduationCap className="w-6 h-6" style={{ color: 'var(--accent-primary)' }} />
                        CMS Exam Simulator
                    </h1>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                        Experience the real UPSC CMS exam environment
                    </p>
                </div>

                {/* Error Display */}
                {error && (
                    <div className="glass-card p-4 mb-6 flex items-center gap-3" style={{
                        borderColor: 'rgba(239,68,68,0.3)',
                        background: 'rgba(239,68,68,0.08)',
                    }}>
                        <AlertTriangle className="w-5 h-5 flex-shrink-0" style={{ color: '#ef4444' }} />
                        <span className="text-sm" style={{ color: '#ef4444' }}>{error}</span>
                        <button onClick={() => setError(null)} className="ml-auto text-xs px-2 py-1 rounded" style={{ color: '#ef4444' }}>&times;</button>
                    </div>
                )}

                {/* Exam Info */}
                <div className="glass-card p-6 mb-8">
                    <h2 className="font-bold mb-3 flex items-center gap-2">
                        <AlertTriangle className="w-5 h-5" style={{ color: '#f59e0b' }} />
                        About UPSC CMS Exam
                    </h2>
                    <div className="grid md:grid-cols-3 gap-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
                        <div><strong style={{ color: 'var(--text-primary)' }}>Format:</strong> Objective MCQs</div>
                        <div><strong style={{ color: 'var(--text-primary)' }}>Papers:</strong> Paper 1 + Paper 2</div>
                        <div><strong style={{ color: 'var(--text-primary)' }}>Questions:</strong> 120 per paper</div>
                    </div>
                </div>

                {/* Tabs */}
                <div className="flex gap-2 mb-6">
                    <button onClick={() => setActiveTab('mock')}
                        className={`px-5 py-2 rounded-lg font-semibold text-sm transition-all flex items-center gap-2 ${activeTab === 'mock' ? 'btn-primary' : 'btn-secondary'}`}>
                        <FileText className="w-4 h-4" /> Full Mock Exams
                    </button>
                    <button onClick={() => setActiveTab('pyq')}
                        className={`px-5 py-2 rounded-lg font-semibold text-sm transition-all flex items-center gap-2 ${activeTab === 'pyq' ? 'btn-primary' : 'btn-secondary'}`}>
                        <Calendar className="w-4 h-4" /> PYQ Year Simulation
                    </button>
                </div>

                {activeTab === 'mock' ? (
                    <div className="grid md:grid-cols-2 gap-6">
                        {papers.map(paper => (
                            <div key={paper.key} className="glass-card p-8 animate-pulse-glow">
                                <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4"
                                    style={{ background: `${paper.color}15`, color: paper.color }}>
                                    <FileText className="w-7 h-7" />
                                </div>
                                <h3 className="text-xl font-bold mb-2">{paper.title}</h3>
                                <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>{paper.desc}</p>
                                <div className="flex items-center gap-4 mb-6 text-sm" style={{ color: 'var(--text-secondary)' }}>
                                    <span className="flex items-center gap-1"><Target className="w-4 h-4" /> {paper.questions} Qs</span>
                                    <span className="flex items-center gap-1"><Clock className="w-4 h-4" /> {paper.time} min</span>
                                </div>
                                <div className="mb-6">
                                    <div className="text-xs font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>Subjects:</div>
                                    <div className="flex flex-wrap gap-2">
                                        {paper.subjects.map(s => (
                                            <span key={s} className="badge" style={{ background: `${paper.color}10`, color: paper.color }}>{s}</span>
                                        ))}
                                    </div>
                                </div>
                                <button onClick={() => startSimulation(paper.key)} disabled={generating}
                                    className="btn-primary w-full justify-center py-3 text-base">
                                    <Play className="w-5 h-5" /> {generating ? 'Generating...' : 'Start Simulation'}
                                </button>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="glass-card p-8 max-w-lg">
                        <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4"
                            style={{ background: 'rgba(245,158,11,0.1)', color: '#f59e0b' }}>
                            <Calendar className="w-7 h-7" />
                        </div>
                        <h3 className="text-xl font-bold mb-2">PYQ Year Simulation</h3>
                        <p className="text-sm mb-6" style={{ color: 'var(--text-secondary)' }}>
                            Attempt actual UPSC CMS questions from a specific year under timed conditions.
                        </p>
                        <div className="mb-6">
                            <label className="text-xs font-medium mb-2 block" style={{ color: 'var(--text-secondary)' }}>Select Year</label>
                            <div className="flex flex-wrap gap-2">
                                {years.sort((a, b) => b - a).map(y => (
                                    <button key={y} onClick={() => setPyqYear(y)}
                                        className="px-4 py-2 rounded-lg text-sm font-bold transition-all"
                                        style={{
                                            background: pyqYear === y ? 'var(--accent-primary)' : 'var(--bg-secondary)',
                                            color: pyqYear === y ? 'white' : 'var(--text-secondary)',
                                            border: pyqYear === y ? '2px solid var(--accent-primary)' : '2px solid var(--glass-border)',
                                        }}>
                                        {y}
                                    </button>
                                ))}
                            </div>
                        </div>
                        <button onClick={startPyqSimulation} disabled={!pyqYear || generating}
                            className="btn-primary w-full justify-center py-3 text-base">
                            <Play className="w-5 h-5" /> {generating ? 'Starting...' : `Start ${pyqYear || ''} PYQ Exam`}
                        </button>
                    </div>
                )}

                {/* Tips */}
                <div className="glass-card p-6 mt-8">
                    <h3 className="font-bold mb-3">📋 Simulation Tips</h3>
                    <ul className="space-y-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                        <li>• Simulate real exam conditions — sit in a quiet place for 2 hours</li>
                        <li>• Use the mark feature for questions you want to revisit</li>
                        <li>• Negative marking is enabled ({'\u2013'}0.33 for wrong answers)</li>
                        <li>• Don&apos;t guess blindly — skip questions you&apos;re unsure about</li>
                        <li>• Review your results and focus on weak areas after each mock</li>
                    </ul>
                </div>
            </div>
        </div>
    );
}
