'use client';

import { Flame, Target, Trophy, TrendingUp, Zap } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { MePayload } from '../types';

interface Props {
    me: MePayload;
}

export default function MyRankCard({ me }: Props) {
    const rankLabel = me.rank
        ? `#${me.rank}`
        : me.out_of > 0
            ? 'Unranked'
            : 'New';

    const rankSubtitle = me.rank
        ? `of ${me.out_of} active learners`
        : me.out_of > 0
            ? `${me.out_of} learners ahead — start studying to enter the board`
            : 'Answer 1 question to enter the board';

    const goalPct = Math.min(
        100,
        Math.round((me.weekly_xp / Math.max(1, me.weekly_goal_xp)) * 100),
    );

    return (
        <Card className="border-primary/30 bg-gradient-to-br from-primary/10 via-card to-card">
            <CardContent className="p-5 space-y-4">
                <div className="flex items-center gap-4">
                    <div className="w-12 h-12 md:w-14 md:h-14 rounded-2xl bg-primary/20 flex items-center justify-center font-extrabold text-primary text-lg md:text-xl">
                        {rankLabel}
                    </div>
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                            <h2 className="font-bold text-foreground text-lg truncate">{me.username}</h2>
                            {me.college && (
                                <Badge variant="outline" className="text-[10px] truncate max-w-45">
                                    🎓 {me.college}
                                </Badge>
                            )}
                        </div>
                        <p className="text-xs md:text-sm text-muted-foreground truncate">{rankSubtitle}</p>
                    </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <Stat icon={<Zap className="w-4 h-4 text-yellow-500" />} label="Total XP" value={me.xp_points.toLocaleString()} />
                    <Stat icon={<Flame className="w-4 h-4 text-orange-500" />} label="Streak" value={`${me.current_streak}d`} />
                    <Stat icon={<Target className="w-4 h-4 text-emerald-500" />} label="Accuracy" value={`${me.accuracy.toFixed(1)}%`} />
                    <Stat icon={<TrendingUp className="w-4 h-4 text-blue-500" />} label="Tests" value={String(me.tests_completed)} />
                </div>

                <div className="space-y-1.5">
                    <div className="flex justify-between text-xs font-semibold">
                        <span className="text-muted-foreground flex items-center gap-1.5">
                            <Trophy className="w-3.5 h-3.5 text-amber-500" />
                            This week
                        </span>
                        <span className="text-foreground">
                            {me.weekly_xp.toLocaleString()} / {me.weekly_goal_xp.toLocaleString()} XP
                        </span>
                    </div>
                    <div
                        className="h-2 w-full rounded-full bg-muted overflow-hidden"
                        role="progressbar"
                        aria-valuenow={goalPct}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label="Weekly XP progress"
                    >
                        <div
                            className="h-full bg-gradient-to-r from-amber-500 via-orange-500 to-rose-500 transition-all"
                            style={{ width: `${goalPct}%` }}
                        />
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
    return (
        <div className="rounded-lg border border-border/60 bg-background/60 p-2.5">
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                {icon}
                {label}
            </div>
            <div className="text-base md:text-lg font-bold text-foreground mt-0.5">{value}</div>
        </div>
    );
}