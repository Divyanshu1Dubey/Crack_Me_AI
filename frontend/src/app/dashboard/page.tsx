'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { analyticsAPI, questionsAPI } from '@/lib/api';
import {
    TrendingUp, Target, Clock, Award, BookOpen,
    Brain, FileText, ChevronRight, Flame
} from 'lucide-react';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

interface DashboardData {
    overall: {
        total_tests: number;
        avg_score: number;
        total_questions: number;
        total_correct: number;
        total_incorrect: number;
        overall_accuracy: number;
        total_time_hours: number;
    };
    subject_performance: Array<{
        subject: string;
        code: string;
        color: string;
        total_attempts: number;
        correct: number;
        accuracy: number;
    }>;
}

interface QuestionStats {
    total: number;
    by_subject: Array<{ name: string; code: string; count: number }>;
    by_difficulty: Array<{ difficulty: string; count: number }>;
}

export default function DashboardPage() {
    const { user, loading: authLoading, isAuthenticated } = useAuth();
    const router = useRouter();
    const [dashData, setDashData] = useState<DashboardData | null>(null);
    const [stats, setStats] = useState<QuestionStats | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            router.push('/login');
            return;
        }
        if (isAuthenticated) {
            Promise.all([
                analyticsAPI.getDashboard().catch(() => ({ data: null })),
                questionsAPI.getStats().catch(() => ({ data: null })),
            ]).then(([dashRes, statsRes]) => {
                if (dashRes.data) setDashData(dashRes.data);
                if (statsRes.data) setStats(statsRes.data);
            }).finally(() => setLoading(false));
        }
    }, [authLoading, isAuthenticated, router]);

    if (authLoading || loading) {
        return (
            <div className="min-h-screen bg-background">
                <Sidebar />
                <div className="main-content">
                    <Header />
                    <div className="page-container space-y-6">
                        <Skeleton className="h-8 w-64" />
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    const overall = dashData?.overall || {
        total_tests: 0, avg_score: 0, total_questions: 0, total_correct: 0,
        total_incorrect: 0, overall_accuracy: 0, total_time_hours: 0
    };

    const quickActions = [
        { label: 'Practice Questions', icon: BookOpen, href: '/questions', color: 'text-indigo-600 dark:text-indigo-400', bg: 'bg-indigo-50 dark:bg-indigo-500/10' },
        { label: 'Take a Test', icon: FileText, href: '/tests', color: 'text-violet-600 dark:text-violet-400', bg: 'bg-violet-50 dark:bg-violet-500/10' },
        { label: 'AI Tutor', icon: Brain, href: '/ai-tutor', color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-500/10' },
        { label: 'CMS Simulator', icon: Target, href: '/simulator', color: 'text-pink-600 dark:text-pink-400', bg: 'bg-pink-50 dark:bg-pink-500/10' },
    ];

    return (
        <div className="min-h-screen bg-background">
            <Sidebar />
            <div className="main-content">
                <Header />
                <div className="page-container">
                    {/* Greeting */}
                    <div className="mb-8">
                        <h1 className="text-2xl font-bold text-foreground mb-1">
                            Welcome back, {user?.first_name || user?.username}
                        </h1>
                        <p className="text-muted-foreground text-sm">Here&apos;s your preparation overview</p>
                    </div>

                    {/* Overall Stats */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                        {[
                            { icon: FileText, value: overall.total_tests, label: 'Tests Taken', color: 'text-indigo-600 dark:text-indigo-400', bg: 'bg-indigo-50 dark:bg-indigo-500/10' },
                            { icon: Target, value: `${overall.overall_accuracy}%`, label: 'Accuracy', color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-500/10' },
                            { icon: TrendingUp, value: overall.total_questions, label: 'Questions Done', color: 'text-violet-600 dark:text-violet-400', bg: 'bg-violet-50 dark:bg-violet-500/10' },
                            { icon: Clock, value: `${overall.total_time_hours}h`, label: 'Time Spent', color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-500/10' },
                        ].map((stat, i) => (
                            <Card key={i}>
                                <CardContent className="p-5">
                                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-3 ${stat.bg}`}>
                                        <stat.icon className={`w-5 h-5 ${stat.color}`} />
                                    </div>
                                    <div className="text-2xl font-bold text-foreground">{stat.value}</div>
                                    <div className="text-xs text-muted-foreground mt-1">{stat.label}</div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>

                    {/* Quick Actions */}
                    <div className="mb-8">
                        <h2 className="section-title flex items-center gap-2 mb-4">
                            <Flame className="w-4 h-4 text-amber-500" />
                            Quick Actions
                        </h2>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            {quickActions.map((action, i) => (
                                <Link key={i} href={action.href}>
                                    <Card className="hover:shadow-md transition-shadow cursor-pointer group">
                                        <CardContent className="p-5 flex flex-col items-center text-center gap-3">
                                            <div className={`w-12 h-12 rounded-xl flex items-center justify-center transition-transform group-hover:scale-105 ${action.bg}`}>
                                                <action.icon className={`w-6 h-6 ${action.color}`} />
                                            </div>
                                            <span className="text-sm font-medium text-foreground">{action.label}</span>
                                            <ChevronRight className={`w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity ${action.color}`} />
                                        </CardContent>
                                    </Card>
                                </Link>
                            ))}
                        </div>
                    </div>

                    {/* Subject Performance & Question Bank Stats */}
                    <div className="grid md:grid-cols-2 gap-6">
                        {/* Subject Performance */}
                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-base flex items-center gap-2">
                                    <Award className="w-4 h-4 text-primary" />
                                    Subject Performance
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                {dashData?.subject_performance && dashData.subject_performance.length > 0 ? (
                                    <div className="space-y-4">
                                        {dashData.subject_performance.map((sp, i) => (
                                            <div key={i}>
                                                <div className="flex justify-between text-sm mb-1.5">
                                                    <span className="text-foreground font-medium">{sp.subject}</span>
                                                    <span className={sp.accuracy >= 60 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'}>{sp.accuracy}%</span>
                                                </div>
                                                <Progress value={sp.accuracy} className="h-2" />
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-muted-foreground">
                                        Take some tests to see your subject performance here!
                                    </p>
                                )}
                            </CardContent>
                        </Card>

                        {/* Question Bank Stats */}
                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-base flex items-center gap-2">
                                    <BookOpen className="w-4 h-4 text-violet-600 dark:text-violet-400" />
                                    Question Bank
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold text-foreground mb-4">{stats?.total || 0} <span className="text-base font-normal text-muted-foreground">Questions</span></div>
                                {stats?.by_subject && (
                                    <div className="space-y-3">
                                        {stats.by_subject.map((s, i) => (
                                            <div key={i} className="flex justify-between items-center">
                                                <span className="text-sm text-foreground">{s.name}</span>
                                                <Badge variant="secondary" className="text-xs">{s.count} Qs</Badge>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </div>
        </div>
    );
}
