'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { testsAPI, questionsAPI } from '@/lib/api';
import { FileText, Play, Clock, Target, Sparkles, Plus, Award, ChevronRight } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

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
        { type: 'daily', label: 'Daily Quick Test', desc: '20 questions, mixed subjects', icon: Sparkles, color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-500/10' },
        { type: 'mixed', label: 'Mixed Practice', desc: 'Questions from all subjects', icon: Target, color: 'text-violet-600 dark:text-violet-400', bg: 'bg-violet-50 dark:bg-violet-500/10' },
        { type: 'paper1', label: 'Paper 1 Mock', desc: 'Medicine + Pediatrics (120 Qs)', icon: FileText, color: 'text-indigo-600 dark:text-indigo-400', bg: 'bg-indigo-50 dark:bg-indigo-500/10' },
        { type: 'paper2', label: 'Paper 2 Mock', desc: 'Surgery + OBG + PSM (120 Qs)', icon: FileText, color: 'text-pink-600 dark:text-pink-400', bg: 'bg-pink-50 dark:bg-pink-500/10' },
    ];

    return (
        <div className="min-h-screen bg-background">
            <Sidebar />
            <div className="main-content">
                <Header />
                <div className="page-container">
                <h1 className="text-2xl font-bold mb-1 flex items-center gap-2 text-foreground">
                    <FileText className="w-6 h-6 text-primary" />
                    Test Center
                </h1>
                <p className="text-sm mb-6 text-muted-foreground">Generate & take practice tests</p>

                {/* Quick Generate */}
                <div className="mb-8">
                    <h2 className="section-title flex items-center gap-2 mb-4">
                        <Plus className="w-4 h-4 text-emerald-500" />
                        Generate New Test
                    </h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                        {testTypes.map((tt) => (
                            <button key={tt.type} onClick={() => generateTest(tt.type)}
                                disabled={generating}>
                                <Card className="p-5 text-left group cursor-pointer hover:shadow-md transition-shadow h-full">
                                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-3 ${tt.bg}`}>
                                        <tt.icon className={`w-5 h-5 ${tt.color}`} />
                                    </div>
                                    <div className="font-medium text-sm mb-1 text-foreground">{tt.label}</div>
                                    <div className="text-xs text-muted-foreground">{tt.desc}</div>
                                </Card>
                            </button>
                        ))}
                    </div>

                    {/* Subject-wise tests */}
                    <h3 className="text-sm font-semibold mb-3 text-muted-foreground">Subject-wise Test</h3>
                    <div className="flex flex-wrap gap-2">
                        {subjects.map(s => (
                            <Button key={s.id} variant="outline" size="sm" onClick={() => generateTest('subject', s.id)}
                                disabled={generating}>
                                {s.name}
                            </Button>
                        ))}
                    </div>
                </div>

                {/* Test List */}
                <div>
                    <h2 className="section-title flex items-center gap-2 mb-4">
                        <Award className="w-4 h-4 text-amber-500" />
                        Available Tests
                    </h2>
                    {loading ? (
                        <div className="grid md:grid-cols-2 gap-4">
                            {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-40 rounded-xl" />)}
                        </div>
                    ) : tests.length === 0 ? (
                        <Card className="p-8 text-center text-muted-foreground">
                            No tests yet. Generate one above to get started!
                        </Card>
                    ) : (
                        <div className="grid md:grid-cols-2 gap-4">
                            {tests.map(test => (
                                <Card key={test.id}>
                                    <CardContent className="p-5">
                                        <div className="flex justify-between items-start mb-3">
                                            <h3 className="font-semibold text-sm text-foreground">{test.title}</h3>
                                            <Badge variant="secondary">{test.test_type}</Badge>
                                        </div>
                                        <div className="flex items-center gap-4 text-xs mb-4 text-muted-foreground">
                                            <span className="flex items-center gap-1"><Target className="w-3 h-3" /> {test.num_questions} Qs</span>
                                            <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {test.time_limit_minutes} min</span>
                                            <span className="flex items-center gap-1"><Play className="w-3 h-3" /> {test.attempt_count} attempts</span>
                                        </div>
                                        <Button onClick={() => startTest(test.id)} className="w-full" size="sm">
                                            Start Test <ChevronRight className="w-4 h-4" />
                                        </Button>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </div>
                </div>
            </div>
        </div>
    );
}
