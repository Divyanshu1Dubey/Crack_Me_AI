'use client';

/**
 * Admin analytics dashboard — internal BI for the CrackCMS team.
 *
 * Single-round-trip fetch from `/api/analytics/admin/dashboard-data/`
 * then renders KPI cards, top lists, geo / device split, daily-active
 * chart, and the conversion funnel. Refreshes every 60s while visible.
 *
 * Access: admin users only. Non-admin users get redirected.
 */

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { analyticsAPI } from '@/lib/api';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import {
    Activity,
    BarChart3,
    Globe2,
    Smartphone,
    TrendingUp,
    Users,
    Wallet,
    Zap,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

interface DashboardData {
    realtime: { active_visitors: number };
    today: { users: number; page_views: number; sign_ups: number; revenue_inr: number };
    weekly: { users: number; page_views: number; sign_ups: number; revenue_inr: number };
    monthly: { users: number; page_views: number; sign_ups: number; revenue_inr: number };
    top_pages: Array<{ path: string; views: number }>;
    top_blogs: Array<{ path: string; views: number }>;
    top_searches: Array<{ term: string; count: number }>;
    countries: Array<{ country: string; users: number }>;
    devices: Array<{ device_type: string; users: number }>;
    browsers: Array<{ browser: string; users: number }>;
    campaigns: Array<{
        utm_campaign: string;
        utm_source: string;
        users: number;
        page_views: number;
    }>;
    funnel: Array<{ stage: string; users: number }>;
    daily_active: Array<{ date: string; users: number; events: number }>;
}

const STAGE_LABEL: Record<string, string> = {
    landing: 'Landing',
    blog_view: 'Read blog',
    question_solve: 'Solved Q',
    ai_tutor: 'AI tutor',
    register_intent: 'Register intent',
    sign_up: 'Registered',
    checkout_start: 'Checkout',
    payment_success: 'Paid',
};

function KpiCard({
    label,
    value,
    icon: Icon,
    accent,
}: {
    label: string;
    value: string | number;
    icon: React.ElementType;
    accent: string;
}) {
    return (
        <Card className="border-border/70">
            <CardContent className="flex items-start justify-between gap-3 p-5">
                <div className="space-y-1">
                    <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                        {label}
                    </p>
                    <p className="text-2xl font-black text-foreground tabular-nums">
                        {value}
                    </p>
                </div>
                <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${accent}`}>
                    <Icon className="h-4 w-4" />
                </div>
            </CardContent>
        </Card>
    );
}

function Funnel({ stages }: { stages: DashboardData['funnel'] }) {
    if (!stages.length) return null;
    const top = stages[0]?.users ?? 1;
    return (
        <div className="space-y-1.5">
            {stages.map((s) => {
                const pct = top > 0 ? Math.max(2, (s.users / top) * 100) : 0;
                const stage = STAGE_LABEL[s.stage] ?? s.stage;
                return (
                    <div key={s.stage} className="flex items-center gap-3">
                        <div className="w-24 shrink-0 text-xs font-semibold text-muted-foreground">
                            {stage}
                        </div>
                        <div className="relative h-7 flex-1 overflow-hidden rounded-md bg-muted/40">
                            <div
                                className="absolute inset-y-0 left-0 bg-linear-to-r from-primary/80 to-primary"
                                style={{ width: `${pct}%` }}
                            />
                            <div className="absolute inset-0 flex items-center px-2 text-[10px] font-bold text-foreground/80">
                                {s.users.toLocaleString('en-IN')}
                            </div>
                        </div>
                        <div className="w-12 text-right text-[10px] tabular-nums text-muted-foreground">
                            {Math.round(pct)}%
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

function DailyChart({ rows }: { rows: DashboardData['daily_active'] }) {
    const max = Math.max(1, ...rows.map((r) => r.users));
    return (
        <div className="flex h-40 items-end gap-0.5">
            {rows.slice(-30).map((r) => {
                const h = (r.users / max) * 100;
                return (
                    <div
                        key={r.date}
                        className="flex-1 rounded-t bg-primary/80 hover:bg-primary"
                        title={`${r.date}: ${r.users.toLocaleString('en-IN')} users, ${r.events} events`}
                        style={{ height: `${Math.max(2, h)}%` }}
                    />
                );
            })}
        </div>
    );
}

export default function AdminAnalyticsDashboardPage() {
    const router = useRouter();
    const { user, isAuthenticated, loading: authLoading } = useAuth();
    const [data, setData] = useState<DashboardData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        try {
            const res = await analyticsAPI.getAdminDashboardData();
            setData(res.data as DashboardData);
            setError(null);
        } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : 'Failed to load dashboard';
            setError(msg);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (authLoading) return;
        if (!isAuthenticated) {
            router.push('/login');
            return;
        }
        if (!user?.is_admin) {
            router.push('/dashboard');
            return;
        }
        void load();
        const interval = setInterval(load, 60_000);
        return () => clearInterval(interval);
    }, [authLoading, isAuthenticated, user, router, load]);

    if (authLoading || loading) {
        return (
            <>
                <Sidebar />
                <div className="main-content">
                    <Header />
                    <div className="px-4 py-10 md:px-8">
                        <div className="rounded-2xl border border-border bg-card p-10 text-center text-sm text-muted-foreground">
                            Loading analytics…
                        </div>
                    </div>
                </div>
            </>
        );
    }
    if (error || !data) {
        return (
            <>
                <Sidebar />
                <div className="main-content">
                    <Header />
                    <div className="px-4 py-10 md:px-8">
                        <div className="rounded-2xl border border-destructive/40 bg-destructive/5 p-10 text-center text-sm text-destructive">
                            {error ?? 'No data'}
                        </div>
                    </div>
                </div>
            </>
        );
    }

    const inr = (n: number) => `₹${Math.round(n).toLocaleString('en-IN')}`;

    return (
        <>
            <Sidebar />
            <div className="main-content">
                <Header />
                <div className="space-y-6 px-4 py-6 md:px-8">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                        <div>
                            <h1 className="text-2xl font-black tracking-tight">
                                Analytics Dashboard
                            </h1>
                            <p className="text-xs text-muted-foreground">
                                Realtime + last 30 days · auto-refreshes every 60 s
                            </p>
                        </div>
                        <button
                            onClick={() => void load()}
                            className="rounded-xl border border-border bg-card px-3 py-1.5 text-xs font-bold hover:bg-muted"
                        >
                            Refresh
                        </button>
                    </div>

                    {/* KPI row */}
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        <KpiCard
                            label="Active now (5m)"
                            value={data.realtime.active_visitors.toLocaleString('en-IN')}
                            icon={Activity}
                            accent="bg-emerald-500/10 text-emerald-600"
                        />
                        <KpiCard
                            label="Today's users"
                            value={data.today.users.toLocaleString('en-IN')}
                            icon={Users}
                            accent="bg-blue-500/10 text-blue-600"
                        />
                        <KpiCard
                            label="Today's page views"
                            value={data.today.page_views.toLocaleString('en-IN')}
                            icon={BarChart3}
                            accent="bg-violet-500/10 text-violet-600"
                        />
                        <KpiCard
                            label="Today's revenue"
                            value={inr(data.today.revenue_inr)}
                            icon={Wallet}
                            accent="bg-amber-500/10 text-amber-600"
                        />
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        <KpiCard
                            label="Weekly users"
                            value={data.weekly.users.toLocaleString('en-IN')}
                            icon={TrendingUp}
                            accent="bg-indigo-500/10 text-indigo-600"
                        />
                        <KpiCard
                            label="Weekly sign-ups"
                            value={data.weekly.sign_ups.toLocaleString('en-IN')}
                            icon={Zap}
                            accent="bg-emerald-500/10 text-emerald-600"
                        />
                        <KpiCard
                            label="Monthly users"
                            value={data.monthly.users.toLocaleString('en-IN')}
                            icon={Users}
                            accent="bg-cyan-500/10 text-cyan-600"
                        />
                        <KpiCard
                            label="Monthly revenue"
                            value={inr(data.monthly.revenue_inr)}
                            icon={Wallet}
                            accent="bg-rose-500/10 text-rose-600"
                        />
                    </div>

                    {/* Daily active users chart */}
                    <Card>
                        <CardContent className="p-5">
                            <div className="flex items-center justify-between">
                                <h2 className="text-sm font-bold">Daily active users (last 30 days)</h2>
                                <span className="text-[10px] text-muted-foreground">
                                    Hover bars for details
                                </span>
                            </div>
                            <div className="mt-3">
                                <DailyChart rows={data.daily_active} />
                            </div>
                        </CardContent>
                    </Card>

                    <div className="grid gap-4 lg:grid-cols-3">
                        {/* Funnel */}
                        <Card className="lg:col-span-2">
                            <CardContent className="p-5">
                                <h2 className="text-sm font-bold">Conversion funnel (last 30 days)</h2>
                                <p className="text-xs text-muted-foreground">
                                    Unique visitors per stage
                                </p>
                                <div className="mt-4">
                                    <Funnel stages={data.funnel} />
                                </div>
                            </CardContent>
                        </Card>

                        {/* Geo */}
                        <Card>
                            <CardContent className="p-5">
                                <h2 className="flex items-center gap-2 text-sm font-bold">
                                    <Globe2 className="h-4 w-4 text-primary" />
                                    Top countries
                                </h2>
                                <ul className="mt-3 space-y-1.5 text-xs">
                                    {data.countries.length === 0 ? (
                                        <li className="text-muted-foreground">No geo data yet.</li>
                                    ) : (
                                        data.countries.map((c) => (
                                            <li
                                                key={c.country}
                                                className="flex items-center justify-between gap-2"
                                            >
                                                <span className="truncate font-semibold">
                                                    {c.country}
                                                </span>
                                                <span className="tabular-nums text-muted-foreground">
                                                    {c.users.toLocaleString('en-IN')}
                                                </span>
                                            </li>
                                        ))
                                    )}
                                </ul>
                            </CardContent>
                        </Card>
                    </div>

                    <div className="grid gap-4 lg:grid-cols-3">
                        {/* Top pages */}
                        <Card>
                            <CardContent className="p-5">
                                <h2 className="text-sm font-bold">Top pages</h2>
                                <ul className="mt-3 space-y-1 text-xs">
                                    {data.top_pages.length === 0 ? (
                                        <li className="text-muted-foreground">No data yet.</li>
                                    ) : (
                                        data.top_pages.map((p, i) => (
                                            <li
                                                key={p.path}
                                                className="flex items-center justify-between gap-2 truncate"
                                            >
                                                <span className="truncate text-foreground/80">
                                                    <span className="mr-2 font-bold text-muted-foreground">
                                                        {i + 1}.
                                                    </span>
                                                    {p.path}
                                                </span>
                                                <span className="tabular-nums text-muted-foreground">
                                                    {p.views.toLocaleString('en-IN')}
                                                </span>
                                            </li>
                                        ))
                                    )}
                                </ul>
                            </CardContent>
                        </Card>

                        {/* Top blogs */}
                        <Card>
                            <CardContent className="p-5">
                                <h2 className="text-sm font-bold">Top blog posts</h2>
                                <ul className="mt-3 space-y-1 text-xs">
                                    {data.top_blogs.length === 0 ? (
                                        <li className="text-muted-foreground">No data yet.</li>
                                    ) : (
                                        data.top_blogs.map((p, i) => (
                                            <li
                                                key={p.path}
                                                className="flex items-center justify-between gap-2 truncate"
                                            >
                                                <span className="truncate text-foreground/80">
                                                    <span className="mr-2 font-bold text-muted-foreground">
                                                        {i + 1}.
                                                    </span>
                                                    {p.path.replace('/blog/', '')}
                                                </span>
                                                <span className="tabular-nums text-muted-foreground">
                                                    {p.views.toLocaleString('en-IN')}
                                                </span>
                                            </li>
                                        ))
                                    )}
                                </ul>
                            </CardContent>
                        </Card>

                        {/* Top searches */}
                        <Card>
                            <CardContent className="p-5">
                                <h2 className="text-sm font-bold">Top searches</h2>
                                <ul className="mt-3 space-y-1 text-xs">
                                    {data.top_searches.length === 0 ? (
                                        <li className="text-muted-foreground">No data yet.</li>
                                    ) : (
                                        data.top_searches.map((s) => (
                                            <li
                                                key={s.term}
                                                className="flex items-center justify-between gap-2 truncate"
                                            >
                                                <span className="truncate font-semibold">
                                                    {s.term}
                                                </span>
                                                <span className="tabular-nums text-muted-foreground">
                                                    {s.count.toLocaleString('en-IN')}
                                                </span>
                                            </li>
                                        ))
                                    )}
                                </ul>
                            </CardContent>
                        </Card>
                    </div>

                    <div className="grid gap-4 lg:grid-cols-3">
                        {/* Devices */}
                        <Card>
                            <CardContent className="p-5">
                                <h2 className="flex items-center gap-2 text-sm font-bold">
                                    <Smartphone className="h-4 w-4 text-primary" />
                                    Devices
                                </h2>
                                <ul className="mt-3 space-y-1 text-xs">
                                    {data.devices.length === 0 ? (
                                        <li className="text-muted-foreground">No data yet.</li>
                                    ) : (
                                        data.devices.map((d) => (
                                            <li
                                                key={d.device_type}
                                                className="flex items-center justify-between"
                                            >
                                                <span className="font-semibold capitalize">
                                                    {d.device_type}
                                                </span>
                                                <span className="tabular-nums text-muted-foreground">
                                                    {d.users.toLocaleString('en-IN')}
                                                </span>
                                            </li>
                                        ))
                                    )}
                                </ul>
                            </CardContent>
                        </Card>

                        {/* Browsers */}
                        <Card>
                            <CardContent className="p-5">
                                <h2 className="text-sm font-bold">Browsers</h2>
                                <ul className="mt-3 space-y-1 text-xs">
                                    {data.browsers.length === 0 ? (
                                        <li className="text-muted-foreground">No data yet.</li>
                                    ) : (
                                        data.browsers.map((b) => (
                                            <li
                                                key={b.browser}
                                                className="flex items-center justify-between"
                                            >
                                                <span className="font-semibold">{b.browser}</span>
                                                <span className="tabular-nums text-muted-foreground">
                                                    {b.users.toLocaleString('en-IN')}
                                                </span>
                                            </li>
                                        ))
                                    )}
                                </ul>
                            </CardContent>
                        </Card>

                        {/* Campaigns */}
                        <Card>
                            <CardContent className="p-5">
                                <h2 className="text-sm font-bold">Top campaigns (UTM)</h2>
                                <ul className="mt-3 space-y-1 text-xs">
                                    {data.campaigns.length === 0 ? (
                                        <li className="text-muted-foreground">
                                            No tagged traffic yet. Share links with{' '}
                                            <code className="rounded bg-muted px-1 py-0.5">
                                                ?utm_source=...
                                            </code>{' '}
                                            to populate.
                                        </li>
                                    ) : (
                                        data.campaigns.map((c) => (
                                            <li
                                                key={`${c.utm_campaign}-${c.utm_source}`}
                                                className="flex items-center justify-between gap-2 truncate"
                                            >
                                                <span className="truncate">
                                                    <strong>{c.utm_campaign}</strong>{' '}
                                                    <span className="text-muted-foreground">
                                                        ({c.utm_source})
                                                    </span>
                                                </span>
                                                <span className="tabular-nums text-muted-foreground">
                                                    {c.users.toLocaleString('en-IN')} ·{' '}
                                                    {c.page_views.toLocaleString('en-IN')} pv
                                                </span>
                                            </li>
                                        ))
                                    )}
                                </ul>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </div>
        </>
    );
}