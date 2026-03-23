'use client';
import { useEffect, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { aiAPI, analyticsAPI } from '@/lib/api';
import {
    Map, Target, Brain, TrendingUp, Calendar, Sparkles,
    ChevronDown, BookOpen, AlertCircle, CheckCircle2,
    Star, Zap, Clock, GraduationCap, Flame, BookMarked,
    Stethoscope, Syringe, Baby, Heart, Activity
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';

// Parse AI response into structured topics
interface ParsedTopic {
    name: string;
    priority: number;
    subtopics?: string;
    textbook?: string;
    tag?: string;
}

interface ParsedSection {
    title: string;
    icon: string;
    priority: number;
    topics: ParsedTopic[];
}

function parseHighYieldContent(content: string): ParsedSection[] {
    const sections: ParsedSection[] = [];
    const lines = content.split('\n').filter(l => l.trim());

    let currentSection: ParsedSection | null = null;

    for (const line of lines) {
        const trimmed = line.trim();

        // Section headers: "**Medicine:**" or "**Medicine (Paper I)**" or "## Medicine" or "Medicine (★★★)"
        const sectionMatch = trimmed.match(/^\*\*([^*]+?)(?:\s*\(Paper\s*[IV]+\))?\*\*:?$/i) ||
                            trimmed.match(/^#{1,3}\s+([^(★]+)\s*\(?(★+)?\)?$/i) ||
                            trimmed.match(/^([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)\s*\(?(★+)?\)?:?$/);

        if (sectionMatch && !trimmed.match(/^\d+\./)) {
            if (currentSection && currentSection.topics.length > 0) {
                sections.push(currentSection);
            }
            const title = sectionMatch[1].replace(/:/g, '').trim();
            const stars = sectionMatch[2] ? sectionMatch[2].length : 3;
            currentSection = {
                title: title,
                icon: getIconForSection(title),
                priority: stars,
                topics: []
            };
            continue;
        }

        // Topic lines: "1. **[High Yield] Hypertension** (★★★) - Textbook Reference: ..."
        // Or: "- **Cardiovascular Diseases** (★★★★)"
        // Or: "[High Yield] Diabetes Mellitus (★★★)"
        if (currentSection && (trimmed.includes('★') || trimmed.includes('[High Yield]') || trimmed.includes('[PYQ'))) {
            // Extract topic name - handle various formats
            let name = '';
            let priority = 2;
            let tag: string | undefined;
            let textbook: string | undefined;

            // Extract stars for priority
            const starsMatch = trimmed.match(/\(?(★+)\)?/);
            if (starsMatch) {
                priority = starsMatch[1].length;
            }

            // Extract tag [High Yield] or [PYQ 2024]
            if (trimmed.includes('[High Yield]')) {
                tag = 'High Yield';
            }
            const pyqMatch = trimmed.match(/\[PYQ\s*(\d{4})\]/i);
            if (pyqMatch) {
                tag = `PYQ ${pyqMatch[1]}`;
            }

            // Extract topic name - remove numbering, asterisks, tags, stars
            name = trimmed
                .replace(/^\d+\.\s*/, '')           // Remove "1. "
                .replace(/^[-*•]\s*/, '')           // Remove "- " or "* "
                .replace(/\*\*/g, '')               // Remove **
                .replace(/\[High Yield\]/gi, '')    // Remove [High Yield]
                .replace(/\[PYQ\s*\d{4}\]/gi, '')   // Remove [PYQ 2024]
                .replace(/\(★+\)/g, '')             // Remove (★★★)
                .replace(/★+/g, '')                 // Remove loose stars
                .replace(/-\s*Textbook.*/i, '')     // Remove textbook reference
                .trim();

            // Extract textbook reference
            const textbookMatch = trimmed.match(/Textbook\s*Reference:\s*(.+)/i);
            if (textbookMatch) {
                textbook = textbookMatch[1].trim();
            }

            if (name && name.length > 2) {
                currentSection.topics.push({
                    name,
                    priority,
                    tag,
                    textbook
                });
            }
        }
    }

    if (currentSection && currentSection.topics.length > 0) {
        sections.push(currentSection);
    }

    return sections;
}

function getIconForSection(title: string): string {
    const lower = title.toLowerCase();
    if (lower.includes('medicine') || lower.includes('general')) return 'medicine';
    if (lower.includes('surgery')) return 'surgery';
    if (lower.includes('pediatric') || lower.includes('paediatric')) return 'pediatrics';
    if (lower.includes('obg') || lower.includes('obstetric') || lower.includes('gynec')) return 'obg';
    if (lower.includes('psm') || lower.includes('preventive') || lower.includes('community')) return 'psm';
    if (lower.includes('cardio') || lower.includes('heart')) return 'cardio';
    return 'default';
}

function SectionIcon({ type, className }: { type: string; className?: string }) {
    const icons: Record<string, React.ReactNode> = {
        medicine: <Stethoscope className={className} />,
        surgery: <Syringe className={className} />,
        pediatrics: <Baby className={className} />,
        obg: <Heart className={className} />,
        psm: <Activity className={className} />,
        cardio: <Heart className={className} />,
        default: <BookOpen className={className} />
    };
    return <>{icons[type] || icons.default}</>;
}

function PriorityStars({ count, max = 4 }: { count: number; max?: number }) {
    return (
        <div className="flex gap-0.5">
            {[...Array(max)].map((_, i) => (
                <Star
                    key={i}
                    className={`w-3.5 h-3.5 ${i < count ? 'text-amber-500 fill-amber-500' : 'text-muted-foreground/30'}`}
                />
            ))}
        </div>
    );
}

const sectionColors: Record<string, { bg: string; border: string; text: string; light: string }> = {
    medicine: { bg: 'bg-blue-500', border: 'border-blue-200 dark:border-blue-500/30', text: 'text-blue-600 dark:text-blue-400', light: 'bg-blue-50 dark:bg-blue-500/10' },
    surgery: { bg: 'bg-rose-500', border: 'border-rose-200 dark:border-rose-500/30', text: 'text-rose-600 dark:text-rose-400', light: 'bg-rose-50 dark:bg-rose-500/10' },
    pediatrics: { bg: 'bg-cyan-500', border: 'border-cyan-200 dark:border-cyan-500/30', text: 'text-cyan-600 dark:text-cyan-400', light: 'bg-cyan-50 dark:bg-cyan-500/10' },
    obg: { bg: 'bg-pink-500', border: 'border-pink-200 dark:border-pink-500/30', text: 'text-pink-600 dark:text-pink-400', light: 'bg-pink-50 dark:bg-pink-500/10' },
    psm: { bg: 'bg-emerald-500', border: 'border-emerald-200 dark:border-emerald-500/30', text: 'text-emerald-600 dark:text-emerald-400', light: 'bg-emerald-50 dark:bg-emerald-500/10' },
    default: { bg: 'bg-violet-500', border: 'border-violet-200 dark:border-violet-500/30', text: 'text-violet-600 dark:text-violet-400', light: 'bg-violet-50 dark:bg-violet-500/10' }
};

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
    const [expandedSections, setExpandedSections] = useState<Set<number>>(new Set([0]));

    useEffect(() => {
        if (!authLoading && !isAuthenticated) router.push('/login');
    }, [authLoading, isAuthenticated, router]);

    useEffect(() => {
        if (isAuthenticated) {
            analyticsAPI.getWeakTopics().then(res => {
                const topics = (res.data?.weak_topics || []).map((t: { topic_name?: string; name?: string; topic?: string } | string) => t && typeof t === 'object' ? (t.topic_name || t.name || t.topic || '') : t);
                setWeakTopics(topics.slice(0, 5));
            }).catch(() => { });
        }
    }, [isAuthenticated]);

    const parsedHighYield = useMemo(() => parseHighYieldContent(highYield), [highYield]);

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

    const toggleSection = (idx: number) => {
        setExpandedSections(prev => {
            const next = new Set(prev);
            if (next.has(idx)) next.delete(idx);
            else next.add(idx);
            return next;
        });
    };

    const phases = [
        {
            title: 'Phase 1: Foundation',
            desc: 'Core subject revision — Harrison, Ghai, Park. Build strong fundamentals across all major subjects.',
            weeks: '1-3',
            icon: BookOpen,
            color: 'text-cyan-600 dark:text-cyan-400',
            bg: 'bg-cyan-50 dark:bg-cyan-500/10',
            border: 'border-cyan-200 dark:border-cyan-500/30',
            tasks: ['Complete Harrison key chapters', 'Revise Ghai Pediatrics', 'Cover Park PSM basics']
        },
        {
            title: 'Phase 2: Deep Dive',
            desc: 'Weak area focused intensive study + PYQs. Target your problem areas identified by analytics.',
            weeks: '4-6',
            icon: Target,
            color: 'text-violet-600 dark:text-violet-400',
            bg: 'bg-violet-50 dark:bg-violet-500/10',
            border: 'border-violet-200 dark:border-violet-500/30',
            tasks: ['Focus on weak topics', 'Solve subject-wise PYQs', 'Create flashcards for difficult concepts']
        },
        {
            title: 'Phase 3: Practice',
            desc: 'Mock tests, PYQ solving, time management. Simulate real exam conditions.',
            weeks: '7-8',
            icon: Zap,
            color: 'text-amber-600 dark:text-amber-400',
            bg: 'bg-amber-50 dark:bg-amber-500/10',
            border: 'border-amber-200 dark:border-amber-500/30',
            tasks: ['Take full-length mock tests', 'Practice time management', 'Analyze mistakes thoroughly']
        },
        {
            title: 'Phase 4: Revision',
            desc: 'Quick revision, mnemonics, high-yield review. Final polish before the exam.',
            weeks: '9-10',
            icon: GraduationCap,
            color: 'text-emerald-600 dark:text-emerald-400',
            bg: 'bg-emerald-50 dark:bg-emerald-500/10',
            border: 'border-emerald-200 dark:border-emerald-500/30',
            tasks: ['Review all flashcards', 'Focus on high-yield topics', 'Light reading and rest']
        },
    ];

    // Parse study plan into sections
    const parsedStudyPlan = useMemo(() => {
        if (!studyPlan) return [];
        const sections: { title: string; items: string[]; priority?: number }[] = [];
        const lines = studyPlan.split('\n');
        let currentSection: { title: string; items: string[]; priority?: number } | null = null;

        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;

            // Headers: ## Title or **Title** or Week X:
            if (trimmed.match(/^#{1,3}\s+/) || trimmed.match(/^\*\*[^*]+\*\*$/) || trimmed.match(/^Week\s+\d+/i)) {
                if (currentSection) sections.push(currentSection);
                currentSection = {
                    title: trimmed.replace(/^#+\s*/, '').replace(/\*+/g, '').trim(),
                    items: [],
                    priority: trimmed.includes('High') || trimmed.includes('Priority') ? 4 : 3
                };
            } else if (trimmed.match(/^[-*•]\s+/) && currentSection) {
                currentSection.items.push(trimmed.replace(/^[-*•]\s+/, ''));
            } else if (currentSection && trimmed.length > 10) {
                currentSection.items.push(trimmed);
            }
        }
        if (currentSection) sections.push(currentSection);
        return sections;
    }, [studyPlan]);

    if (authLoading) {
        return (
            <div className="min-h-screen bg-background flex">
                <Sidebar />
                <div className="flex-1 flex flex-col">
                    <Header />
                    <main className="flex-1 p-6 page-container space-y-6">
                        <Skeleton className="h-8 w-64" />
                        <div className="grid gap-4">
                            {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
                        </div>
                    </main>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background flex">
            <Sidebar />
            <div className="flex-1 flex flex-col">
                <Header />
                <main className="flex-1 p-6 page-container space-y-6">
                    {/* Page Header */}
                    <div className="flex items-center gap-3 mb-2">
                        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg">
                            <Map className="w-6 h-6 text-white" />
                        </div>
                        <div>
                            <h1 className="text-2xl font-bold text-foreground">Study Roadmap</h1>
                            <p className="text-sm text-muted-foreground">
                                AI-powered personalized study plan for UPSC CMS
                            </p>
                        </div>
                    </div>

                    {/* Phase Timeline */}
                    <Card>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-base flex items-center gap-2">
                                <Target className="w-4 h-4 text-primary" />
                                Preparation Phases
                            </CardTitle>
                            <CardDescription>
                                Your structured preparation timeline — click to expand each phase
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            {phases.map((phase, i) => {
                                const isExpanded = expandedPhase === i;
                                return (
                                    <div
                                        key={i}
                                        className={`rounded-xl cursor-pointer transition-all border ${isExpanded ? phase.border : 'border-transparent'} ${isExpanded ? phase.bg : 'bg-muted/30 hover:bg-muted/50'}`}
                                        onClick={() => setExpandedPhase(isExpanded ? null : i)}
                                    >
                                        <div className="p-4 flex items-center justify-between">
                                            <div className="flex items-center gap-3">
                                                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${phase.bg}`}>
                                                    <phase.icon className={`w-5 h-5 ${phase.color}`} />
                                                </div>
                                                <div>
                                                    <div className="font-semibold text-foreground text-sm">{phase.title}</div>
                                                    <div className="text-xs text-muted-foreground flex items-center gap-2">
                                                        <Clock className="w-3 h-3" />
                                                        Weeks {phase.weeks}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className={`transition-transform ${isExpanded ? 'rotate-180' : ''}`}>
                                                <ChevronDown className="w-5 h-5 text-muted-foreground" />
                                            </div>
                                        </div>
                                        {isExpanded && (
                                            <div className="px-4 pb-4 space-y-3 animate-in slide-in-from-top-2 duration-200">
                                                <p className="text-sm text-muted-foreground pl-13">
                                                    {phase.desc}
                                                </p>
                                                <div className="pl-13 space-y-2">
                                                    {phase.tasks.map((task, j) => (
                                                        <div key={j} className="flex items-center gap-2 text-sm">
                                                            <CheckCircle2 className={`w-4 h-4 ${phase.color}`} />
                                                            <span className="text-foreground">{task}</span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </CardContent>
                    </Card>

                    {/* Tab Buttons */}
                    <div className="flex gap-3">
                        <Button
                            variant={activeTab === 'plan' ? 'default' : 'outline'}
                            onClick={() => setActiveTab('plan')}
                            className="gap-2"
                        >
                            <Brain className="w-4 h-4" />
                            Personalized Study Plan
                        </Button>
                        <Button
                            variant={activeTab === 'highyield' ? 'default' : 'outline'}
                            onClick={() => setActiveTab('highyield')}
                            className="gap-2"
                        >
                            <TrendingUp className="w-4 h-4" />
                            High Yield Topics
                        </Button>
                    </div>

                    {activeTab === 'plan' && (
                        <div className="space-y-4">
                            {/* Configuration Card */}
                            <Card>
                                <CardHeader className="pb-3">
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <Sparkles className="w-4 h-4 text-amber-500" />
                                        Generate Your AI Study Plan
                                    </CardTitle>
                                    <CardDescription>
                                        Set your exam timeline and let AI create a personalized study schedule
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="flex flex-wrap items-center gap-4">
                                        <div className="flex items-center gap-3">
                                            <div className="w-10 h-10 rounded-lg bg-indigo-50 dark:bg-indigo-500/10 flex items-center justify-center">
                                                <Calendar className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                                            </div>
                                            <div>
                                                <label className="text-xs text-muted-foreground">Days Until Exam</label>
                                                <Input
                                                    type="number"
                                                    value={daysRemaining}
                                                    onChange={e => setDaysRemaining(Number(e.target.value))}
                                                    className="w-24 h-9 text-center font-semibold"
                                                    min={1}
                                                    max={365}
                                                />
                                            </div>
                                        </div>
                                        <Button onClick={generatePlan} disabled={loading} className="gap-2">
                                            <Sparkles className="w-4 h-4" />
                                            {loading ? 'Generating...' : 'Generate AI Study Plan'}
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Weak Topics */}
                            {weakTopics.length > 0 && (
                                <Card className="border-amber-200 dark:border-amber-500/30">
                                    <CardHeader className="pb-2">
                                        <CardTitle className="text-sm flex items-center gap-2 text-amber-600 dark:text-amber-400">
                                            <AlertCircle className="w-4 h-4" />
                                            Your Weak Areas (from Analytics)
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="flex flex-wrap gap-2">
                                            {weakTopics.map((t, i) => (
                                                <Badge key={i} variant="outline" className="bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 border-red-200 dark:border-red-500/30">
                                                    {t}
                                                </Badge>
                                            ))}
                                        </div>
                                        <p className="text-xs text-muted-foreground mt-3">
                                            These topics will be prioritized in your AI-generated study plan
                                        </p>
                                    </CardContent>
                                </Card>
                            )}

                            {/* Study Plan Result - Parsed */}
                            {parsedStudyPlan.length > 0 && (
                                <div className="space-y-4">
                                    <div className="flex items-center gap-2">
                                        <Brain className="w-5 h-5 text-primary" />
                                        <h2 className="text-lg font-semibold text-foreground">Your Personalized Study Plan</h2>
                                    </div>
                                    <div className="grid gap-4 md:grid-cols-2">
                                        {parsedStudyPlan.map((section, idx) => (
                                            <Card key={idx} className="border-l-4 border-l-primary">
                                                <CardHeader className="pb-2">
                                                    <CardTitle className="text-sm flex items-center gap-2">
                                                        <BookMarked className="w-4 h-4 text-primary" />
                                                        {section.title}
                                                    </CardTitle>
                                                </CardHeader>
                                                <CardContent className="space-y-2">
                                                    {section.items.map((item, i) => (
                                                        <div key={i} className="flex items-start gap-2 text-sm">
                                                            <CheckCircle2 className="w-4 h-4 text-emerald-500 mt-0.5 shrink-0" />
                                                            <span className="text-muted-foreground">{item}</span>
                                                        </div>
                                                    ))}
                                                </CardContent>
                                            </Card>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Fallback raw display */}
                            {studyPlan && parsedStudyPlan.length === 0 && (
                                <Card>
                                    <CardContent className="pt-6">
                                        <pre className="whitespace-pre-wrap text-sm text-muted-foreground">{studyPlan}</pre>
                                    </CardContent>
                                </Card>
                            )}
                        </div>
                    )}

                    {activeTab === 'highyield' && (
                        <div className="space-y-4">
                            {/* High Yield Header Card */}
                            <Card>
                                <CardHeader className="pb-3">
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <Flame className="w-4 h-4 text-orange-500" />
                                        High Yield Topic Analysis
                                    </CardTitle>
                                    <CardDescription>
                                        AI-analyzed PYQ trends (2018-2024) to predict important topics for upcoming exams
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <Button onClick={fetchHighYield} disabled={loading} className="gap-2">
                                        <TrendingUp className="w-4 h-4" />
                                        {loading ? 'Analyzing...' : 'Analyze PYQ Trends'}
                                    </Button>
                                </CardContent>
                            </Card>

                            {/* Parsed High Yield Results */}
                            {parsedHighYield.length > 0 && (
                                <div className="space-y-4">
                                    <div className="flex items-center gap-2">
                                        <TrendingUp className="w-5 h-5 text-amber-500" />
                                        <h2 className="text-lg font-semibold text-foreground">High Yield Topics for UPSC CMS</h2>
                                        <Badge variant="outline" className="ml-auto bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400">
                                            {parsedHighYield.reduce((acc, s) => acc + s.topics.length, 0)} Topics Identified
                                        </Badge>
                                    </div>

                                    {parsedHighYield.map((section, sIdx) => {
                                        const colors = sectionColors[section.icon] || sectionColors.default;
                                        const isExpanded = expandedSections.has(sIdx);

                                        return (
                                            <Card key={sIdx} className={`overflow-hidden ${colors.border}`}>
                                                <div
                                                    className={`cursor-pointer ${colors.light} border-b ${colors.border}`}
                                                    onClick={() => toggleSection(sIdx)}
                                                >
                                                    <div className="p-4 flex items-center justify-between">
                                                        <div className="flex items-center gap-3">
                                                            <div className={`w-10 h-10 rounded-lg ${colors.bg} flex items-center justify-center`}>
                                                                <SectionIcon type={section.icon} className="w-5 h-5 text-white" />
                                                            </div>
                                                            <div>
                                                                <div className={`font-semibold ${colors.text}`}>{section.title}</div>
                                                                <div className="flex items-center gap-2 mt-0.5">
                                                                    <PriorityStars count={section.priority} />
                                                                    <span className="text-xs text-muted-foreground">
                                                                        {section.topics.length} high-yield topics
                                                                    </span>
                                                                </div>
                                                            </div>
                                                        </div>
                                                        <ChevronDown className={`w-5 h-5 text-muted-foreground transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                                                    </div>
                                                </div>

                                                {isExpanded && (
                                                    <CardContent className="p-4 space-y-3 animate-in slide-in-from-top-2 duration-200">
                                                        {section.topics.map((topic, tIdx) => (
                                                            <div
                                                                key={tIdx}
                                                                className="p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors"
                                                            >
                                                                <div className="flex items-start justify-between gap-2">
                                                                    <div className="flex items-center gap-2">
                                                                        <Flame className={`w-4 h-4 shrink-0 ${topic.priority >= 4 ? 'text-orange-500' : topic.priority >= 3 ? 'text-amber-500' : 'text-yellow-500'}`} />
                                                                        <span className="font-medium text-foreground">{topic.name}</span>
                                                                    </div>
                                                                    <div className="flex items-center gap-2 shrink-0">
                                                                        {topic.tag && (
                                                                            <Badge
                                                                                variant="outline"
                                                                                className={topic.tag.includes('High')
                                                                                    ? 'bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 border-red-200 dark:border-red-500/30 text-xs'
                                                                                    : 'bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-200 dark:border-blue-500/30 text-xs'
                                                                                }
                                                                            >
                                                                                {topic.tag}
                                                                            </Badge>
                                                                        )}
                                                                        <PriorityStars count={topic.priority} max={4} />
                                                                    </div>
                                                                </div>
                                                                {topic.subtopics && (
                                                                    <p className="text-sm text-muted-foreground mt-1 pl-6">
                                                                        {topic.subtopics}
                                                                    </p>
                                                                )}
                                                                {topic.textbook && (
                                                                    <div className="flex items-center gap-1.5 mt-2 pl-6">
                                                                        <BookOpen className="w-3.5 h-3.5 text-muted-foreground" />
                                                                        <span className="text-xs text-muted-foreground">{topic.textbook}</span>
                                                                    </div>
                                                                )}
                                                            </div>
                                                        ))}
                                                    </CardContent>
                                                )}
                                            </Card>
                                        );
                                    })}
                                </div>
                            )}

                            {/* Fallback for raw content if parsing fails */}
                            {highYield && parsedHighYield.length === 0 && (
                                <Card>
                                    <CardContent className="pt-6">
                                        <pre className="whitespace-pre-wrap text-sm text-muted-foreground">{highYield}</pre>
                                    </CardContent>
                                </Card>
                            )}
                        </div>
                    )}
                </main>
            </div>
        </div>
    );
}
