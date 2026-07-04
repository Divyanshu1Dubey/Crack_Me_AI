'use client';
import { useEffect, useMemo, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import useSWR from 'swr';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { analyticsAPI, questionsAPI } from '@/lib/api';
import {
    ArrowRight, Award, BookOpen,
    Calendar, CheckCircle, Clock, FileText, Flame,
    HeartPulse, Crown, Brain, Sparkles
} from 'lucide-react';
import Link from 'next/link';
import Image from 'next/image';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import CustomIcon from '@/components/CustomIcon';

interface HeatmapDay {
    date: string;
    questions_attempted: number;
    correct_answers: number;
    time_spent_minutes: number;
    tests_completed: number;
}

// SWR fetchers with caching
const dashboardFetcher = () => analyticsAPI.getDashboard().then(r => r.data).catch(() => null);
const heatmapFetcher = () => analyticsAPI.getHeatmap().then(r => r.data || []).catch(() => []);
const streakFetcher = () => analyticsAPI.getStreak().then(r => r.data).catch(() => null);

const CAMPUS_MOMENTUM = [
    { name: 'Riya S.', college: 'AIIMS Delhi', note: '412 Qs this month' },
    { name: 'Aarav M.', college: 'CMC Vellore', note: '7-day streak active' },
    { name: 'Nisha K.', college: 'JIPMER Puducherry', note: 'Top 9% mock rank' },
    { name: 'Harsh V.', college: 'KGMU Lucknow', note: '58 weak topics fixed' },
] as const;

export default function DashboardPage() {
    const { user, loading: authLoading, isAuthenticated } = useAuth();
    const router = useRouter();
    const isRedirecting = !authLoading && !isAuthenticated;

    const [selectedExam, setSelectedExam] = useState<'UPSC CMS' | 'NEET PG'>('UPSC CMS');

    // Heatmap tooltip state
    const [hoveredDay, setHoveredDay] = useState<{ date: string; questions: number; tests: number; minutes: number } | null>(null);
    const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

    // SWR config
    const swrConfig = {
        revalidateOnFocus: true,
        dedupingInterval: 2000,
        errorRetryCount: 2,
    };

    const { data: dashData, isLoading: loadingDash } = useSWR(
        isAuthenticated ? 'dashboard' : null,
        dashboardFetcher,
        swrConfig
    );

    // Dynamic SWR keys based on selected exam source
    const { data: stats } = useSWR(
        isAuthenticated ? ['question-stats', selectedExam] : null,
        () => questionsAPI.getStats({ exam_source: selectedExam }).then(r => r.data).catch(() => null),
        swrConfig
    );

    const { data: heatmap = [] } = useSWR(
        isAuthenticated ? 'heatmap' : null,
        heatmapFetcher,
        swrConfig
    );

    const { data: streak } = useSWR(
        isAuthenticated ? 'streak' : null,
        streakFetcher,
        swrConfig
    );

    const loading = loadingDash;

    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            router.replace('/login');
        }
    }, [authLoading, isAuthenticated, router]);

    const heatmapByDate = useMemo<Map<string, HeatmapDay>>(() => {
        return new Map(heatmap.map((day: HeatmapDay) => [day.date, day]));
    }, [heatmap]);

    const todayDateStr = useMemo(() => {
        const today = new Date();
        const yyyy = today.getFullYear();
        const mm = String(today.getMonth() + 1).padStart(2, '0');
        const dd = String(today.getDate()).padStart(2, '0');
        return `${yyyy}-${mm}-${dd}`;
    }, []);

    const todayActivity = useMemo<HeatmapDay>(() => {
        const found = heatmapByDate.get(todayDateStr);
        return found || {
            date: todayDateStr,
            questions_attempted: 0,
            correct_answers: 0,
            time_spent_minutes: 0,
            tests_completed: 0
        };
    }, [heatmapByDate, todayDateStr]);

    const dailyQuestionGoal = 30;
    const dailyQuestionGoalProgress = Math.min(100, Math.round((todayActivity.questions_attempted / dailyQuestionGoal) * 100));

    const todayAccuracy = useMemo(() => {
        if (todayActivity.questions_attempted === 0) return 0;
        return Math.round((todayActivity.correct_answers / todayActivity.questions_attempted) * 100);
    }, [todayActivity]);

    // Heatmap levels setup
    const heatmapLevelClasses = [
        'bg-slate-100 dark:bg-slate-800 border-slate-200/40 dark:border-slate-800/40',
        'bg-sky-200 dark:bg-sky-950/40',
        'bg-sky-300 dark:bg-sky-900/60',
        'bg-sky-400 dark:bg-sky-500/80',
        'bg-sky-600 dark:bg-sky-300',
    ];

    const overall = dashData?.overall || {
        total_tests: 0, avg_score: 0, total_questions: 0, total_correct: 0,
        total_incorrect: 0, overall_accuracy: 0, total_time_hours: 0
    };

    const topWeakSubjects = [...(dashData?.subject_performance || [])]
        .sort((a, b) => a.accuracy - b.accuracy)
        .slice(0, 3);

    // Grid details for the last 16 weeks contribution calendar
    const contributionGrid = useMemo(() => {
        const weeks: Array<Array<{ date: string; isInRange: boolean; questions: number; tests: number; minutes: number; level: number; isToday: boolean }>> = [];
        const today = new Date();
        const startDay = new Date(today);
        startDay.setDate(today.getDate() - (16 * 7) + 1);

        const current = new Date(startDay);
        while (current.getDay() !== 0) {
            current.setDate(current.getDate() - 1);
        }

        const monthMarkers: Array<{ month: string; weekIndex: number }> = [];
        let lastMonth = '';

        for (let w = 0; w < 16; w++) {
            const weekDays: Array<{ date: string; isInRange: boolean; questions: number; tests: number; minutes: number; level: number; isToday: boolean }> = [];
            for (let d = 0; d < 7; d++) {
                const dateStr = current.toISOString().split('T')[0];
                const dayActivityData = heatmapByDate.get(dateStr);
                const qs = dayActivityData?.questions_attempted || 0;
                const ts = dayActivityData?.tests_completed || 0;
                const mins = dayActivityData?.time_spent_minutes || 0;

                let level = 0;
                if (qs > 0) {
                    if (qs <= 10) level = 1;
                    else if (qs <= 25) level = 2;
                    else if (qs <= 50) level = 3;
                    else level = 4;
                }

                weekDays.push({
                    date: dateStr,
                    isInRange: current >= startDay && current <= today,
                    questions: qs,
                    tests: ts,
                    minutes: mins,
                    level,
                    isToday: dateStr === todayDateStr
                });

                if (d === 0 && w > 0) {
                    const currentMonth = current.toLocaleString('default', { month: 'short' });
                    if (currentMonth !== lastMonth) {
                        monthMarkers.push({ month: currentMonth, weekIndex: w });
                        lastMonth = currentMonth;
                    }
                }

                current.setDate(current.getDate() + 1);
            }
            weeks.push(weekDays);
        }
        return { weeks, monthMarkers };
    }, [heatmapByDate, todayDateStr]);

    if (authLoading || isRedirecting) {
        return (
            <div className="min-h-screen bg-background">
                <Sidebar />
                <div className="main-content">
                    <Header />
                    <div className="page-container space-y-5">
                        <Skeleton className="h-40 rounded-2xl" />
                        <div className="grid md:grid-cols-12 gap-4">
                            <Skeleton className="h-[520px] md:col-span-8 rounded-2xl" />
                            <Skeleton className="h-[520px] md:col-span-4 rounded-2xl" />
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    if (loading) {
        return (
            <div className="min-h-screen bg-background">
                <Sidebar />
                <div className="main-content">
                    <Header />
                    <div className="page-container space-y-5">
                        <Skeleton className="h-40 rounded-2xl" />
                        <div className="grid md:grid-cols-12 gap-4">
                            <Skeleton className="h-[520px] md:col-span-8 rounded-2xl" />
                            <Skeleton className="h-[520px] md:col-span-4 rounded-2xl" />
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50/60 dark:bg-slate-950">
            <Sidebar />
            <div className="main-content">
                <Header />
                <div className="page-container space-y-6 pb-8">
                    {/* Premium Upgrade Banner */}
                    {!user?.is_subscribed && (
                        <Card className="border-amber-500/30 bg-gradient-to-r from-amber-500/10 via-yellow-500/5 to-transparent shadow-sm relative overflow-hidden">
                            <div className="absolute top-0 right-0 h-32 w-32 rounded-full bg-amber-500/5 blur-3xl pointer-events-none" />
                            <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                                <div className="space-y-1">
                                    <h4 className="text-sm font-bold text-amber-500 flex items-center gap-1.5">
                                        <Crown className="w-4 h-4" /> Claim Premium Pass — ₹129/mo (Unlock ₹79 rate via Scholarship!)
                                    </h4>
                                    <p className="text-xs text-muted-foreground">
                                        Get complete access to NEET PG, UPSC CMS mock simulators, standard reference guides, and AI tutors.
                                    </p>
                                </div>
                                <Link href="/subscription" className="shrink-0">
                                    <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-black font-semibold">
                                        View Subscription Offers
                                    </Button>
                                </Link>
                            </CardContent>
                        </Card>
                    )}

                    {/* Hero Welcome Card */}
                    <Card className="overflow-hidden border-0 shadow-md bg-slate-900 border-border text-white relative">
                        <div className="absolute right-0 top-0 h-full w-1/3 opacity-40 mix-blend-screen overflow-hidden hidden md:block">
                            <Image src="/dashboard_hero.png" alt="Medical Hero" fill sizes="(min-width: 768px) 33vw, 0px" className="object-cover object-left" />
                            <div className="absolute inset-0 bg-gradient-to-r from-slate-900 to-transparent"></div>
                        </div>
                        <CardContent className="p-0 relative z-10">
                            <div className="grid md:grid-cols-3">
                                <div className="md:col-span-2 p-6 md:p-8">
                                    <div className="inline-flex items-center gap-2 rounded-full bg-blue-500/20 px-3 py-1 text-xs font-medium mb-4 text-blue-200">
                                        <CustomIcon name="medical-stethoscope" label="Medical" className="w-3.5 h-3.5" variant="active" />
                                        CrackLabs Medical Companion
                                    </div>
                                    <h1 className="text-2xl md:text-3xl font-bold mb-2">
                                        Welcome back, Dr. {user?.first_name || user?.username || 'Doctor'}
                                    </h1>
                                    <p className="text-sky-100 text-sm md:text-base mb-6 max-w-xl">
                                        Your comprehensive preparation dashboard. Solve clinical case drills, review textbooks, and ask the AI Tutor for diagnostics guides.
                                    </p>
                                    <div className="flex flex-wrap gap-3">
                                        <Button asChild variant="secondary" className="bg-white text-slate-900 hover:bg-slate-100">
                                            <Link href="/tests">
                                                Start Today&apos;s Test
                                                <ArrowRight className="w-4 h-4" />
                                            </Link>
                                        </Button>
                                        <Button asChild variant="outline" className="border-white/60 bg-transparent text-white hover:bg-white/10">
                                            <Link href="/questions">Practice Questions</Link>
                                        </Button>
                                    </div>
                                </div>
                                <div className="p-6 md:p-8 bg-black/10 backdrop-blur-sm space-y-4">
                                    <div className="rounded-xl bg-white/15 p-4">
                                        <p className="text-xs text-sky-100 mb-1">Current Streak</p>
                                        <p className="text-3xl font-bold">{streak?.current_streak || 0} <span className="text-sm font-medium text-sky-100">days</span></p>
                                    </div>
                                    <div className="rounded-xl bg-white/15 p-4">
                                        <p className="text-xs text-sky-100 mb-1">Today&apos;s Questions</p>
                                        <p className="text-3xl font-bold">{todayActivity.questions_attempted}</p>
                                    </div>
                                    <div className="rounded-xl bg-white/15 p-4">
                                        <p className="text-xs text-sky-100 mb-1">Overall Accuracy</p>
                                        <p className="text-3xl font-bold">{overall.overall_accuracy}%</p>
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* KPI Strip */}
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                        {[
                            { iconName: 'tests-check', value: overall.total_tests, label: 'Tests Completed', bg: 'bg-blue-100 dark:bg-blue-900/40' },
                            { iconName: 'question-bank-book', value: `${overall.total_questions}`, label: 'Questions Solved', bg: 'bg-blue-100 dark:bg-blue-900/40' },
                            { iconName: 'dashboard-layout', value: `${overall.total_time_hours}h`, label: 'Study Time', bg: 'bg-blue-100 dark:bg-blue-900/40' },
                            { iconName: 'ai-questions-creativity', value: `${streak?.xp_points || 0}`, label: 'XP Points', bg: 'bg-blue-100 dark:bg-blue-900/40' },
                        ].map((metric, i) => (
                            <Card key={i} className="shadow-sm">
                                <CardContent className="p-5">
                                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-3 ${metric.bg}`}>
                                        <CustomIcon name={metric.iconName} label={metric.label} className="w-5 h-5" variant="active" />
                                    </div>
                                    <p className="text-2xl font-bold text-foreground leading-none">{metric.value}</p>
                                    <p className="text-xs text-muted-foreground mt-2">{metric.label}</p>
                                </CardContent>
                            </Card>
                        ))}
                    </div>

                    {/* AI PREP TOOLKIT (Top section toolkit grid) */}
                    <div className="space-y-4 text-left">
                        <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
                            <Sparkles className="w-5 h-5 text-amber-500" />
                            AI Prep Toolkit & Features
                        </h2>
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                            {[
                                {
                                    title: 'AI Question Generator',
                                    desc: 'Generate tailored clinical scenarios & practice questions on any topic.',
                                    href: '/generate',
                                    icon: Brain,
                                    color: 'text-amber-500 bg-amber-500/10'
                                },
                                {
                                    title: 'AI Study Assistant',
                                    desc: 'Chat with medical AI trained on standard textbooks like Harrison & Ghai.',
                                    href: '/ai-tutor',
                                    icon: BookOpen,
                                    color: 'text-cyan-500 bg-cyan-500/10'
                                },
                                {
                                    title: 'Mock Simulator',
                                    desc: 'Practice real exam environments with positive/negative marking rules.',
                                    href: '/simulator',
                                    icon: FileText,
                                    color: 'text-emerald-500 bg-emerald-500/10'
                                },
                                {
                                    title: 'Study Roadmap Planner',
                                    desc: 'Get step-by-step checklists, timelines and textbook index lookups.',
                                    href: '/roadmap',
                                    icon: Award,
                                    color: 'text-indigo-500 bg-indigo-500/10'
                                }
                            ].map((tool, i) => (
                                <Link key={i} href={tool.href}>
                                    <Card className="hover:scale-[1.02] transition-all duration-300 cursor-pointer h-full border border-border/80 bg-card">
                                        <CardContent className="p-5 space-y-3">
                                            <div className={`w-10 h-10 rounded-2xl flex items-center justify-center ${tool.color}`}>
                                                <tool.icon className="w-5 h-5" />
                                            </div>
                                            <div className="space-y-1 text-left">
                                                <h3 className="font-bold text-sm text-foreground">{tool.title}</h3>
                                                <p className="text-xs text-muted-foreground leading-relaxed">{tool.desc}</p>
                                            </div>
                                        </CardContent>
                                    </Card>
                                </Link>
                            ))}
                        </div>
                    </div>

                    <div className="grid lg:grid-cols-12 gap-6">
                        {/* Left Main Column (Occupies most width, balanced layout) */}
                        <div className="lg:col-span-8 space-y-6">
                            
                            {/* Today Focus */}
                            <Card className="shadow-sm border-border">
                                <CardHeader className="pb-4 text-left">
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <HeartPulse className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                                        Today&apos;s Focus
                                    </CardTitle>
                                    <CardDescription>
                                        Your daily consistency and activity metrics.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-5">
                                    <div className="grid sm:grid-cols-3 gap-3 text-left">
                                        {[
                                            { label: 'Questions Today', value: todayActivity.questions_attempted, icon: BookOpen },
                                            { label: 'Tests Today', value: todayActivity.tests_completed, icon: FileText },
                                            { label: 'Study Minutes', value: todayActivity.time_spent_minutes, icon: Clock },
                                        ].map((item, i) => (
                                            <div key={i} className="rounded-xl bg-blue-600 dark:bg-blue-700 text-white p-4 shadow-xs relative overflow-hidden">
                                                <div className="absolute -right-4 -bottom-4 h-16 w-16 rounded-full bg-white/10 blur-xl" />
                                                <div className="flex items-center justify-between mb-3 relative z-10">
                                                    <p className="text-xs text-blue-100 font-semibold">{item.label}</p>
                                                    <item.icon className="w-4.5 h-4.5 text-blue-200" />
                                                </div>
                                                <p className="text-2xl font-extrabold text-white relative z-10">{item.value}</p>
                                            </div>
                                        ))}
                                    </div>

                                    <div className="grid sm:grid-cols-2 gap-4 text-left">
                                        <div className="rounded-xl border border-border p-4">
                                            <div className="flex items-center justify-between mb-2">
                                                <p className="text-sm font-medium text-foreground">Daily Question Goal</p>
                                                <p className="text-xs text-muted-foreground">{todayActivity.questions_attempted}/{dailyQuestionGoal}</p>
                                            </div>
                                            <Progress value={dailyQuestionGoalProgress} className="h-2.5" />
                                            <p className="text-xs text-muted-foreground mt-2 font-semibold">
                                                {dailyQuestionGoalProgress >= 100
                                                    ? 'Goal complete! Great work today.'
                                                    : `${dailyQuestionGoal - todayActivity.questions_attempted} more to reach your daily goal.`}
                                            </p>
                                        </div>
                                        <div className="rounded-xl border border-border p-4">
                                            <div className="flex items-center justify-between mb-2">
                                                <p className="text-sm font-medium text-foreground">Today&apos;s Accuracy</p>
                                                <p className="text-sm font-semibold text-sky-700 dark:text-sky-300">{todayAccuracy}%</p>
                                            </div>
                                            <Progress value={todayAccuracy} className="h-2.5" />
                                            <p className="text-xs text-muted-foreground mt-2 font-semibold">
                                                Correct: {todayActivity.correct_answers} / Attempted: {todayActivity.questions_attempted}
                                            </p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Heatmap Calendar */}
                            <Card className="shadow-sm border-border">
                                <CardHeader className="pb-4 text-left">
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <Calendar className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                                        Study Activity Calendar
                                    </CardTitle>
                                    <CardDescription>
                                        Your daily practice consistency over the last 16 weeks.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="rounded-xl border border-border bg-slate-50/50 dark:bg-slate-900/30 p-4 mb-4 text-left">
                                        <div className="flex items-center justify-between gap-4 flex-wrap">
                                            <div>
                                                <p className="text-xs uppercase tracking-wide text-blue-400 font-medium font-bold">Today&apos;s Activity</p>
                                                <p className="text-xl font-black text-foreground mt-1">{todayActivity.questions_attempted} questions, {todayActivity.tests_completed} tests</p>
                                                <p className="text-xs text-muted-foreground mt-1">{todayActivity.time_spent_minutes} minutes of study today</p>
                                            </div>
                                            <Badge className="bg-blue-600 hover:bg-blue-600 text-white font-bold">
                                                {streak?.current_streak || 0} day streak
                                            </Badge>
                                        </div>
                                    </div>

                                    <div className="overflow-x-auto pb-2 relative">
                                        {hoveredDay && (
                                            <div
                                                className="fixed z-50 bg-popover text-popover-foreground border border-border px-3 py-2 rounded-lg shadow-lg text-xs pointer-events-none"
                                                style={{ left: tooltipPos.x, top: tooltipPos.y }}
                                            >
                                                {hoveredDay.date} | Q: {hoveredDay.questions}, Tests: {hoveredDay.tests}, Time: {hoveredDay.minutes}m
                                            </div>
                                        )}
                                        <div className="min-w-[720px]">
                                            <div className="relative h-5 mb-2 text-[10px] text-muted-foreground">
                                                {contributionGrid.monthMarkers.map((marker) => (
                                                    <span
                                                        key={`${marker.month}-${marker.weekIndex}`}
                                                        className="absolute"
                                                        style={{ left: `${marker.weekIndex * 15}px` }}
                                                    >
                                                        {marker.month}
                                                    </span>
                                                ))}
                                            </div>
                                            <div className="grid grid-flow-col grid-rows-7 gap-1 w-max">
                                                {contributionGrid.weeks.flat().map((day) => (
                                                    <div
                                                        key={day.date}
                                                        onMouseEnter={(e) => {
                                                            const rect = e.currentTarget.getBoundingClientRect();
                                                            setTooltipPos({ x: rect.left, y: rect.bottom + 8 });
                                                            setHoveredDay({ date: day.date, questions: day.questions, tests: day.tests, minutes: day.minutes });
                                                        }}
                                                        onMouseLeave={() => setHoveredDay(null)}
                                                        className={`h-3.5 w-3.5 rounded-sm border cursor-pointer transition-transform hover:scale-110 ${day.isInRange ? `border-border/40 ${heatmapLevelClasses[day.level]}` : 'bg-transparent border-transparent'} ${day.isToday ? 'ring-2 ring-sky-500 ring-offset-1 ring-offset-background scale-110' : ''}`}
                                                    />
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2 mt-4 text-xs text-muted-foreground">
                                        <span>Less</span>
                                        {heatmapLevelClasses.map((cls, i) => (
                                            <div key={i} className={`h-3.5 w-3.5 rounded-sm border border-border/40 ${cls}`} />
                                        ))}
                                        <span>More</span>
                                        <span className="ml-4 inline-flex items-center gap-1">
                                            <span className="h-3.5 w-3.5 rounded-sm ring-2 ring-blue-500" />
                                            Today
                                        </span>
                                    </div>
                                </CardContent>
                            </Card>

                        </div>

                        {/* Right Rail Column */}
                        <div className="lg:col-span-4 space-y-6">
                            
                            {/* Weak Subjects */}
                            <Card className="shadow-sm text-left">
                                <CardHeader className="pb-3">
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <Award className="w-4 h-4 text-sky-600 dark:text-sky-300" />
                                        Subjects to Focus On
                                    </CardTitle>
                                    <CardDescription>
                                        These need more practice based on your recent scores.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    {topWeakSubjects.length === 0 ? (
                                        <p className="text-sm text-muted-foreground">Complete a few mock tests to calculate weak subjects details.</p>
                                    ) : (
                                        <div className="space-y-4">
                                            {topWeakSubjects.map((subject, i) => (
                                                <div key={i}>
                                                    <div className="flex items-center justify-between mb-1.5">
                                                        <p className="text-sm font-semibold text-foreground">{subject.subject}</p>
                                                        <p className="text-xs font-bold text-muted-foreground">{subject.accuracy}%</p>
                                                    </div>
                                                    <Progress value={subject.accuracy} className="h-2" />
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>

                            {/* Campus Momentum (Peer Leaderboard details) */}
                            <Card className="shadow-sm border-border text-left">
                                <CardHeader className="pb-3">
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <CustomIcon name="medical-stethoscope" label="Community" className="w-4 h-4" variant="active" />
                                        National Campus Momentum
                                    </CardTitle>
                                    <CardDescription>
                                        Live streaks and questions solved by peers.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-3">
                                    <Badge className="bg-sky-600 text-white hover:bg-sky-600 py-1 px-2.5 font-bold">2,900+ active aspirants this week</Badge>
                                    {CAMPUS_MOMENTUM.map((student) => (
                                        <div key={student.name} className="rounded-xl border border-border p-3">
                                            <p className="text-sm font-semibold text-foreground">{student.name}</p>
                                            <p className="text-xs text-muted-foreground mt-0.5">{student.college}</p>
                                            <p className="text-xs font-medium text-sky-700 dark:text-sky-300 mt-1">{student.note}</p>
                                        </div>
                                    ))}
                                </CardContent>
                            </Card>
                        </div>
                    </div>

                    {/* QUESTION BANK PROGRESS — Full-width section for balanced layout */}
                    <Card className="shadow-sm border-border text-left">
                        <CardHeader className="pb-4">
                            <div className="flex justify-between items-center gap-3 flex-wrap">
                                <div className="space-y-1">
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <CustomIcon name="trends-graph" label="Question Bank" className="w-4 h-4" variant="active" />
                                        Question Bank Mastery Progress
                                    </CardTitle>
                                    <CardDescription>
                                        Track solved question rates and completion by subjects.
                                    </CardDescription>
                                </div>
                                {/* Exam Stats Toggle */}
                                <div className="flex rounded-xl bg-slate-100 dark:bg-slate-900 p-1 border border-border shrink-0">
                                    <button
                                        onClick={() => setSelectedExam('UPSC CMS')}
                                        className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${selectedExam === 'UPSC CMS' ? 'bg-white dark:bg-slate-800 text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground'}`}
                                    >
                                        UPSC CMS
                                    </button>
                                    <button
                                        onClick={() => setSelectedExam('NEET PG')}
                                        className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${selectedExam === 'NEET PG' ? 'bg-white dark:bg-slate-800 text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground'}`}
                                    >
                                        NEET PG
                                    </button>
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-5">
                            {/* Overall + Difficulty — horizontal strip */}
                            <div className="grid md:grid-cols-4 gap-4">
                                <div className="p-4 rounded-2xl bg-cyan-50 dark:bg-cyan-900/10 border border-cyan-200/50 dark:border-cyan-800/30">
                                    <span className="text-[10px] uppercase font-bold text-cyan-700 dark:text-cyan-400 tracking-wider">Overall Solved</span>
                                    <p className="text-2xl font-black text-foreground mt-2">
                                        {stats?.total_solved || 0} <span className="text-xs font-bold text-muted-foreground">/ {stats?.total || 1440}</span>
                                    </p>
                                    {stats?.total > 0 && (
                                        <div className="mt-3">
                                            <Progress value={Math.round((stats.total_solved / stats.total) * 100)} className="h-1.5 bg-cyan-200/40" />
                                            <span className="text-[10px] font-bold text-cyan-700 dark:text-cyan-400 mt-1.5 block">
                                                {Math.round((stats.total_solved / stats.total) * 100)}% Completed
                                            </span>
                                        </div>
                                    )}
                                </div>

                                {(stats?.by_difficulty || []).map((d: { difficulty: string; count: number; solved: number }, idx: number) => {
                                    const pct = d.count > 0 ? Math.round((d.solved / d.count) * 100) : 0;
                                    const colorMap: Record<string, string> = {
                                        easy: 'text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/15',
                                        medium: 'text-sky-600 dark:text-sky-400 bg-sky-500/10 border-sky-500/15',
                                        hard: 'text-red-600 dark:text-red-400 bg-red-500/10 border-red-500/15'
                                    };
                                    const colorClass = colorMap[d.difficulty] || 'bg-muted';
                                    return (
                                        <div key={idx} className={`p-4 rounded-2xl border ${colorClass}`}>
                                            <span className="text-[10px] font-bold capitalize block">{d.difficulty}</span>
                                            <span className="text-xl font-extrabold block mt-1">{d.solved}/{d.count}</span>
                                            <span className="text-[9px] font-bold mt-1 opacity-80 block">{pct}% solved</span>
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Progress by Year + Subjects — horizontal */}
                            <div className="grid md:grid-cols-2 gap-6">
                                {/* Progress by Year */}
                                <div className="space-y-3">
                                    <p className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Progress by Year</p>
                                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                                        {(stats?.by_year || [])
                                            .slice(0, 4)
                                            .map((item: { year: number; count: number; solved: number }, idx: number) => {
                                                const pct = item.count > 0 ? Math.round((item.solved / item.count) * 100) : 0;
                                                const isCompleted = item.solved === item.count && item.count > 0;
                                                return (
                                                    <div key={idx} className="p-2.5 rounded-xl border border-border bg-slate-50/50 dark:bg-slate-900/30">
                                                        <div className="flex justify-between items-center mb-1">
                                                            <span className="text-xs font-extrabold text-foreground">{item.year}</span>
                                                            <span className="text-[10px] font-semibold text-muted-foreground">{item.solved}/{item.count}</span>
                                                        </div>
                                                        <Progress value={pct} className="h-1.5" />
                                                        <div className="flex justify-between items-center mt-1">
                                                            <span className="text-[9px] font-bold text-muted-foreground">{pct}%</span>
                                                            {isCompleted && (
                                                                <span className="text-[9px] text-emerald-500 font-extrabold">Done! 🎉</span>
                                                            )}
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                    </div>
                                </div>

                                {/* Progress by Subject */}
                                <div className="space-y-3">
                                    <p className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Progress by Subject</p>
                                    <div className="grid sm:grid-cols-2 gap-3">
                                        {(stats?.by_subject || []).slice(0, 4).map((item: { name: string; count: number; solved: number }, idx: number) => {
                                            const pct = item.count > 0 ? Math.round((item.solved / item.count) * 100) : 0;
                                            return (
                                                <div key={idx} className="space-y-1 bg-slate-50/30 dark:bg-slate-900/10 p-2.5 rounded-xl border border-border/40">
                                                    <div className="flex items-center justify-between text-xs">
                                                        <span className="text-foreground font-semibold truncate max-w-[140px]">{item.name}</span>
                                                        <span className="text-muted-foreground text-[10px] shrink-0 font-bold">{item.solved}/{item.count} ({pct}%)</span>
                                                    </div>
                                                    <Progress value={pct} className="h-1.5 bg-slate-200/50" />
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Streak Footer */}
                    <Card className="shadow-sm border-border text-left">
                        <CardContent className="p-4 flex flex-wrap items-center justify-between gap-3">
                            <div className="flex items-center gap-3">
                                <Flame className="w-5 h-5 text-amber-500 animate-bounce" />
                                <div>
                                    <p className="text-sm font-semibold text-foreground">Your Active Streak Stats</p>
                                    <p className="text-xs text-muted-foreground">
                                        Longest: {streak?.longest_streak || 0} days • Total study days: {streak?.total_study_days || 0}
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                                <CheckCircle className="w-4 h-4 text-emerald-500" />
                                <span>Practice at least 1 question daily to protect your study streak</span>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
}
