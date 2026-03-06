/**
 * dashboard/page.tsx — Main dashboard with study analytics overview.
 * Shows: daily stats (questions, accuracy, streak), performance charts,
 * subject-wise progress, recent test scores, study activity heatmap.
 * Data from analyticsAPI endpoints.
 */
'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import { analyticsAPI, questionsAPI } from '@/lib/api';
import {
    TrendingUp, Target, Clock, Award, BookOpen,
    Brain, FileText, ChevronRight, Flame
} from 'lucide-react';
import Link from 'next/link';

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
            <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg-primary)' }}>
                <div className="animate-pulse text-xl gradient-text">Loading Dashboard...</div>
            </div>
        );
    }

    const overall = dashData?.overall || {
        total_tests: 0, avg_score: 0, total_questions: 0, total_correct: 0,
        total_incorrect: 0, overall_accuracy: 0, total_time_hours: 0
    };

    const quickActions = [
        { label: 'Practice Questions', icon: BookOpen, href: '/questions', color: '#06b6d4' },
        { label: 'Take a Test', icon: FileText, href: '/tests', color: '#8b5cf6' },
        { label: 'AI Tutor', icon: Brain, href: '/ai-tutor', color: '#f59e0b' },
        { label: 'CMS Simulator', icon: Target, href: '/simulator', color: '#ec4899' },
    ];

    return (
        <div style={{ background: 'var(--bg-primary)' }} className="min-h-screen">
            <Sidebar />
            <div className="main-content">
                {/* Header */}
                <div className="mb-8">
                    <h1 className="text-3xl font-bold mb-1">
                        Welcome back, <span className="gradient-text">{user?.first_name || user?.username}</span> 👋
                    </h1>
                    <p style={{ color: 'var(--text-secondary)' }}>Here&apos;s your preparation overview</p>
                </div>

                {/* Overall Stats */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                    {[
                        { icon: <FileText className="w-6 h-6" />, value: overall.total_tests, label: 'Tests Taken', color: '#06b6d4' },
                        { icon: <Target className="w-6 h-6" />, value: `${overall.overall_accuracy}%`, label: 'Accuracy', color: '#10b981' },
                        { icon: <TrendingUp className="w-6 h-6" />, value: overall.total_questions, label: 'Questions Done', color: '#8b5cf6' },
                        { icon: <Clock className="w-6 h-6" />, value: `${overall.total_time_hours}h`, label: 'Time Spent', color: '#f59e0b' },
                    ].map((stat, i) => (
                        <div key={i} className="stat-card">
                            <div className="flex items-center gap-3 mb-2">
                                <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: `${stat.color}15`, color: stat.color }}>
                                    {stat.icon}
                                </div>
                            </div>
                            <div className="text-2xl font-bold">{stat.value}</div>
                            <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>{stat.label}</div>
                        </div>
                    ))}
                </div>

                {/* Quick Actions */}
                <div className="mb-8">
                    <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                        <Flame className="w-5 h-5" style={{ color: '#f59e0b' }} />
                        Quick Actions
                    </h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        {quickActions.map((action, i) => (
                            <Link key={i} href={action.href} className="glass-card p-5 flex flex-col items-center text-center gap-3 group cursor-pointer">
                                <div className="w-12 h-12 rounded-xl flex items-center justify-center transition-transform group-hover:scale-110"
                                    style={{ background: `${action.color}15`, color: action.color }}>
                                    <action.icon className="w-6 h-6" />
                                </div>
                                <span className="text-sm font-medium">{action.label}</span>
                                <ChevronRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" style={{ color: action.color }} />
                            </Link>
                        ))}
                    </div>
                </div>

                {/* Subject Performance & Question Bank Stats */}
                <div className="grid md:grid-cols-2 gap-6">
                    {/* Subject Performance */}
                    <div className="glass-card p-6">
                        <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                            <Award className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                            Subject Performance
                        </h3>
                        {dashData?.subject_performance && dashData.subject_performance.length > 0 ? (
                            <div className="space-y-4">
                                {dashData.subject_performance.map((sp, i) => (
                                    <div key={i}>
                                        <div className="flex justify-between text-sm mb-1">
                                            <span>{sp.subject}</span>
                                            <span style={{ color: sp.accuracy >= 60 ? '#10b981' : '#ef4444' }}>{sp.accuracy}%</span>
                                        </div>
                                        <div className="w-full h-2 rounded-full" style={{ background: 'rgba(139, 149, 168, 0.1)' }}>
                                            <div className="h-full rounded-full transition-all duration-500"
                                                style={{ width: `${sp.accuracy}%`, background: sp.color || 'var(--accent-primary)' }} />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                                Take some tests to see your subject performance here!
                            </p>
                        )}
                    </div>

                    {/* Question Bank Stats */}
                    <div className="glass-card p-6">
                        <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                            <BookOpen className="w-5 h-5" style={{ color: '#8b5cf6' }} />
                            Question Bank
                        </h3>
                        <div className="text-3xl font-bold gradient-text mb-4">{stats?.total || 0} Questions</div>
                        {stats?.by_subject && (
                            <div className="space-y-3">
                                {stats.by_subject.map((s, i) => (
                                    <div key={i} className="flex justify-between items-center">
                                        <span className="text-sm">{s.name}</span>
                                        <span className="badge" style={{ background: 'rgba(6, 182, 212, 0.1)', color: 'var(--accent-primary)' }}>
                                            {s.count} Qs
                                        </span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
