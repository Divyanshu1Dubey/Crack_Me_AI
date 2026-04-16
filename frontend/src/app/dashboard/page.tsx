'use client';
import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import useSWR from 'swr';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { analyticsAPI, questionsAPI } from '@/lib/api';
import {
    ArrowRight, Award, BookOpen,
    Calendar, CheckCircle2, Clock, FileText, Flame,
    HeartPulse
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
const statsFetcher = () => questionsAPI.getStats().then(r => r.data).catch(() => null);
const heatmapFetcher = () => analyticsAPI.getHeatmap().then(r => r.data || []).catch(() => []);
const streakFetcher = () => analyticsAPI.getStreak().then(r => r.data).catch(() => null);

// Static data moved outside component to prevent re-renders
const QUICK_ACTIONS = [
    { label: 'Practice Questions', iconName: 'question-bank-book', href: '/questions', bg: 'bg-sky-100 dark:bg-sky-500/15' },
    { label: 'Take Mock Test', iconName: 'tests-check', href: '/tests', bg: 'bg-cyan-100 dark:bg-cyan-500/15' },
    { label: 'AI Study Assistant', iconName: 'ai-tutor-brain', href: '/ai-tutor', bg: 'bg-indigo-100 dark:bg-indigo-500/15' },
    { label: 'CMS Simulator', iconName: 'simulator-target', href: '/simulator', bg: 'bg-violet-100 dark:bg-violet-500/15' },
] as const;

const CAMPUS_MOMENTUM = [
    { name: 'Riya S.', college: 'AIIMS Delhi', note: '412 Qs this month' },
    { name: 'Aarav M.', college: 'CMC Vellore', note: '7-day streak active' },
    { name: 'Nisha K.', college: 'JIPMER Puducherry', note: 'Top 9% mock rank' },
    { name: 'Harsh V.', college: 'KGMU Lucknow', note: '58 weak topics fixed' },
] as const;

export default function DashboardPage() {
    const { user, loading: authLoading, isAuthenticated } = useAuth();
    const router = useRouter();

    // Heatmap tooltip state (single tooltip instead of 112+ components)
    const [hoveredDay, setHoveredDay] = useState<{ date: string; questions: number; tests: number; minutes: number } | null>(null);
    const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

    // SWR hooks with deduplication and caching (5 min cache)
    const swrConfig = {
        revalidateOnFocus: false,
        dedupingInterval: 300000, // 5 minutes
        errorRetryCount: 2,
    };

    const { data: dashData, isLoading: loadingDash } = useSWR(
        isAuthenticated ? 'dashboard' : null,
        dashboardFetcher,
        swrConfig
    );
    const { data: stats } = useSWR(
        isAuthenticated ? 'question-stats' : null,
        statsFetcher,
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

    const todayKey = useMemo(() => {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        return today.toISOString().slice(0, 10);
    }, []);

    const todayActivity = useMemo<HeatmapDay>(() => {
        const fall: HeatmapDay = {
            date: todayKey,
            questions_attempted: 0,
            correct_answers: 0,
            time_spent_minutes: 0,
            tests_completed: 0,
        };
        const active = heatmapByDate.get(todayKey);
        return active ? active : fall;
    }, [heatmapByDate, todayKey]);

    const dailyQuestionGoal = 30;
    const dailyQuestionGoalProgress = Math.min(100, Math.round((todayActivity.questions_attempted / dailyQuestionGoal) * 100));
    const todayAccuracy = todayActivity.questions_attempted > 0
        ? Math.round((todayActivity.correct_answers / todayActivity.questions_attempted) * 100)
        : 0;

    const contributionGrid = useMemo(() => {
        const end = new Date();
        end.setHours(0, 0, 0, 0);

        const start = new Date(end);
        start.setDate(end.getDate() - 111);

        const gridStart = new Date(start);
        gridStart.setDate(start.getDate() - start.getDay());

        const days: Array<{
            date: string;
            isInRange: boolean;
            questions: number;
            tests: number;
            minutes: number;
            level: number;
            month: string;
            dayOfMonth: number;
            isToday: boolean;
        }> = [];

        for (const d = new Date(gridStart); d <= end; d.setDate(d.getDate() + 1)) {
            const dateKey = d.toISOString().slice(0, 10);
            const activity = heatmapByDate.get(dateKey);
            const isInRange = d >= start;
            const questions = activity?.questions_attempted || 0;
            const tests = activity?.tests_completed || 0;
            const minutes = activity?.time_spent_minutes || 0;
            const isToday = dateKey === todayKey;

            const weightedActivity = questions + (tests * 10);
            let level = 0;
            if (weightedActivity >= 50) level = 4;
            else if (weightedActivity >= 25) level = 3;
            else if (weightedActivity >= 10) level = 2;
            else if (weightedActivity > 0) level = 1;

            days.push({
                date: dateKey,
                isInRange,
                questions,
                tests,
                minutes,
                level,
                month: d.toLocaleString('en-US', { month: 'short' }),
                dayOfMonth: d.getDate(),
                isToday,
            });
        }

        const weeks: typeof days[] = [];
        for (let i = 0; i < days.length; i += 7) {
            weeks.push(days.slice(i, i + 7));
        }

        const monthMarkers = weeks
            .map((week, weekIndex) => {
                const labelDay = week.find((day) => day.isInRange && day.dayOfMonth <= 7);
                if (!labelDay) return null;
                return { weekIndex, month: labelDay.month };
            })
            .filter((marker, idx, arr) => {
                if (!marker) return false;
                const prev = arr[idx - 1];
                return !prev || prev.month !== marker.month;
            }) as Array<{ weekIndex: number; month: string }>;

        return { weeks, monthMarkers };
    }, [heatmapByDate, todayKey]);

    const heatmapLevelClasses = [
        'bg-muted/40',
        'bg-sky-100 dark:bg-sky-900/30',
        'bg-sky-300 dark:bg-sky-700/60',
        'bg-sky-500 dark:bg-sky-500/80',
        'bg-sky-700 dark:bg-sky-300',
    ];

    const overall = dashData?.overall || {
        total_tests: 0, avg_score: 0, total_questions: 0, total_correct: 0,
        total_incorrect: 0, overall_accuracy: 0, total_time_hours: 0
    };

    const topWeakSubjects = [...(dashData?.subject_performance || [])]
        .sort((a, b) => a.accuracy - b.accuracy)
        .slice(0, 3);

    if (authLoading || loading) {
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
                    {/* Hero */}
                    <Card className="overflow-hidden border-0 shadow-md bg-slate-900 border-border text-white relative">
                        <div className="absolute right-0 top-0 h-full w-1/3 opacity-40 mix-blend-screen overflow-hidden hidden md:block relative">
                            <Image src="/dashboard_hero.png" alt="Medical Hero" fill sizes="(min-width: 768px) 33vw, 0px" className="object-cover object-left" />
                            <div className="absolute inset-0 bg-gradient-to-r from-slate-900 to-transparent"></div>
                        </div>
                        <CardContent className="p-0 relative z-10">
                            <div className="grid md:grid-cols-3">
                                <div className="md:col-span-2 p-6 md:p-8">
                                    <div className="inline-flex items-center gap-2 rounded-full bg-blue-500/20 px-3 py-1 text-xs font-medium mb-4 text-blue-200">
                                        <CustomIcon name="medical-stethoscope" label="Medical" className="w-3.5 h-3.5" variant="active" />
                                        UPSC CMS Prep Dashboard
                                    </div>
                                    <h1 className="text-2xl md:text-3xl font-bold mb-2">
                                        Welcome back, Dr. {user?.first_name || user?.username || 'Doctor'}
                                    </h1>
                                    <p className="text-sky-100 text-sm md:text-base mb-6 max-w-xl">
                                        Your personal study companion. Track consistency, improve weak areas, and build exam confidence every day.
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

                    <div className="grid lg:grid-cols-12 gap-6">
                        {/* Left Main */}
                        <div className="lg:col-span-8 space-y-6">
                            {/* Today Focus */}
                            <Card className="shadow-sm border-border">
                                <CardHeader className="pb-4">
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <HeartPulse className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                                        Today&apos;s Progress
                                    </CardTitle>
                                    <CardDescription>
                                        Your daily study progress at a glance.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-5">
                                    <div className="grid sm:grid-cols-3 gap-3">
                                        {[
                                            { label: 'Questions Today', value: todayActivity.questions_attempted, icon: BookOpen },
                                            { label: 'Tests Today', value: todayActivity.tests_completed, icon: FileText },
                                            { label: 'Study Minutes', value: todayActivity.time_spent_minutes, icon: Clock },
                                        ].map((item, i) => (
                                            <div key={i} className="rounded-xl border border-border bg-slate-50/80 dark:bg-slate-900/70 p-4">
                                                <div className="flex items-center justify-between mb-3">
                                                    <p className="text-xs text-muted-foreground">{item.label}</p>
                                                    <item.icon className="w-4 h-4 text-sky-600 dark:text-sky-300" />
                                                </div>
                                                <p className="text-2xl font-bold text-foreground">{item.value}</p>
                                            </div>
                                        ))}
                                    </div>
                                    <div className="grid sm:grid-cols-2 gap-4">
                                        <div className="rounded-xl border border-border p-4">
                                            <div className="flex items-center justify-between mb-2">
                                                <p className="text-sm font-medium text-foreground">Daily Question Goal</p>
                                                <p className="text-xs text-muted-foreground">{todayActivity.questions_attempted}/{dailyQuestionGoal}</p>
                                            </div>
                                            <Progress value={dailyQuestionGoalProgress} className="h-2.5" />
                                            <p className="text-xs text-muted-foreground mt-2">
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
                                            <p className="text-xs text-muted-foreground mt-2">
                                                Correct: {todayActivity.correct_answers} / Attempted: {todayActivity.questions_attempted}
                                            </p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Heatmap */}
                            <Card className="shadow-sm border-border">
                                <CardHeader className="pb-4">
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <Calendar className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                                        Study Activity Calendar
                                    </CardTitle>
                                    <CardDescription>
                                        Your daily practice over the last 16 weeks.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="rounded-xl border border-border bg-slate-50/50 dark:bg-slate-900/30 p-4 mb-4">
                                        <div className="flex items-center justify-between gap-4 flex-wrap">
                                            <div>
                                                <p className="text-xs uppercase tracking-wide text-blue-400 font-medium">Today&apos;s Activity</p>
                                                <p className="text-xl font-bold text-foreground mt-1">{todayActivity.questions_attempted} questions, {todayActivity.tests_completed} tests</p>
                                                <p className="text-xs text-muted-foreground mt-1">{todayActivity.time_spent_minutes} minutes of study today</p>
                                            </div>
                                            <Badge className="bg-blue-600 hover:bg-blue-600 text-white">
                                                {streak?.current_streak || 0} day streak
                                            </Badge>
                                        </div>
                                    </div>

                                    <div className="overflow-x-auto pb-2 relative">
                                        {/* Single positioned tooltip for performance */}
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

                        {/* Right Rail */}
                        <div className="lg:col-span-4 space-y-6">
                            {/* Quick Actions */}
                            <Card className="shadow-sm">
                                <CardHeader className="pb-3">
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <CustomIcon name="ai-questions-creativity" label="Quick Actions" className="w-4 h-4" variant="active" />
                                        Quick Actions
                                    </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-3">
                                    {QUICK_ACTIONS.map((action, i) => (
                                        <Link key={i} href={action.href}>
                                            <div className="rounded-xl border border-border p-3 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors">
                                                <div className="flex items-center gap-3">
                                                    <div className={`h-10 w-10 rounded-lg flex items-center justify-center ${action.bg}`}>
                                                        <CustomIcon name={action.iconName} label={action.label} className="w-5 h-5" variant="active" />
                                                    </div>
                                                    <p className="text-sm font-medium text-foreground">{action.label}</p>
                                                </div>
                                                <ArrowRight className="w-4 h-4 text-muted-foreground" />
                                            </div>
                                        </Link>
                                    ))}
                                </CardContent>
                            </Card>

                            {/* Weak Subjects */}
                            <Card className="shadow-sm">
                                <CardHeader className="pb-3">
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <Award className="w-4 h-4 text-sky-600 dark:text-sky-300" />
                                        Subjects to Focus On
                                    </CardTitle>
                                    <CardDescription>
                                        These need more practice based on your scores.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    {topWeakSubjects.length === 0 ? (
                                        <p className="text-sm text-muted-foreground">Complete a few tests to see which subjects need work.</p>
                                    ) : (
                                        <div className="space-y-4">
                                            {topWeakSubjects.map((subject, i) => (
                                                <div key={i}>
                                                    <div className="flex items-center justify-between mb-1.5">
                                                        <p className="text-sm font-medium text-foreground">{subject.subject}</p>
                                                        <p className="text-xs text-muted-foreground">{subject.accuracy}%</p>
                                                    </div>
                                                    <Progress value={subject.accuracy} className="h-2" />
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>

                            {/* Question Bank */}
                            <Card className="shadow-sm">
                                <CardHeader className="pb-3">
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <CustomIcon name="trends-graph" label="Question Bank" className="w-4 h-4" variant="active" />
                                        Question Bank
                                    </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <div className="rounded-xl bg-cyan-50 dark:bg-cyan-900/15 border border-cyan-200/70 dark:border-cyan-500/30 p-3">
                                        <p className="text-xs text-cyan-700 dark:text-cyan-300">Total Questions Available</p>
                                        <p className="text-2xl font-bold text-foreground mt-1">1,920+ PYQs</p>
                                    </div>

                                    <div className="space-y-2">
                                        <p className="text-xs font-medium text-muted-foreground">By Subject</p>
                                        {(stats?.by_subject || []).slice(0, 5).map((item: { name: string; count: number }, idx: number) => (
                                            <div key={idx} className="flex items-center justify-between text-sm">
                                                <span className="text-foreground">{item.name}</span>
                                                <Badge variant="secondary">{item.count}</Badge>
                                            </div>
                                        ))}
                                    </div>

                                    <div className="space-y-2">
                                        <p className="text-xs font-medium text-muted-foreground">Difficulty Levels</p>
                                        <div className="flex flex-wrap gap-2">
                                            {(stats?.by_difficulty || []).map((d: { difficulty: string; count: number }, idx: number) => (
                                                <Badge key={idx} variant="outline" className="capitalize">{d.difficulty}: {d.count}</Badge>
                                            ))}
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            <Card className="shadow-sm border-border">
                                <CardHeader className="pb-3">
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <CustomIcon name="medical-stethoscope" label="Community" className="w-4 h-4" variant="active" />
                                        Community
                                    </CardTitle>
                                    <CardDescription>
                                        Join thousands preparing with CrackCMS.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-3">
                                    <Badge className="bg-sky-600 text-white hover:bg-sky-600">2,900+ active this week</Badge>
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

                    {/* Streak Footer */}
                    <Card className="shadow-sm border-border">
                        <CardContent className="p-4 flex flex-wrap items-center justify-between gap-3">
                            <div className="flex items-center gap-3">
                                <Flame className="w-5 h-5 text-amber-500" />
                                <div>
                                    <p className="text-sm font-semibold text-foreground">Your Streak Stats</p>
                                    <p className="text-xs text-muted-foreground">
                                        Best: {streak?.longest_streak || 0} days • Total study days: {streak?.total_study_days || 0}
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center gap-2 text-xs">
                                <CheckCircle2 className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                                <span className="text-muted-foreground">Practice daily to keep your streak alive</span>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
}
