'use client';

import { Calendar, Flame, Target, Trophy } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import type { MePayload } from '../types';

interface Props {
    me: MePayload;
}

/**
 * Three small stat tiles — weekly XP, current streak, accuracy.
 * All derived from `me`; no extra server calls.
 */
export default function WeeklyStatsRow({ me }: Props) {
    const tiles = [
        {
            icon: <Trophy className="w-4 h-4 text-amber-500" />,
            label: 'XP this week',
            value: me.weekly_xp.toLocaleString(),
            sub: `Goal: ${me.weekly_goal_xp.toLocaleString()}`,
        },
        {
            icon: <Flame className="w-4 h-4 text-orange-500" />,
            label: 'Current streak',
            value: `${me.current_streak}d`,
            sub: `Longest: ${me.longest_streak}d`,
        },
        {
            icon: <Target className="w-4 h-4 text-emerald-500" />,
            label: 'Accuracy',
            value: `${me.accuracy.toFixed(1)}%`,
            sub: `${me.tests_completed} tests completed`,
        },
    ];

    return (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {tiles.map((t) => (
                <Card key={t.label} className="border-border/60 bg-card/80">
                    <CardContent className="p-4 flex items-start gap-3">
                        <div className="shrink-0 w-10 h-10 rounded-xl bg-muted flex items-center justify-center">
                            {t.icon}
                        </div>
                        <div className="min-w-0">
                            <p className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">
                                {t.label}
                            </p>
                            <p className="text-xl font-bold text-foreground mt-0.5">{t.value}</p>
                            <p className="text-[10px] text-muted-foreground mt-0.5 flex items-center gap-1">
                                <Calendar className="w-2.5 h-2.5" />
                                {t.sub}
                            </p>
                        </div>
                    </CardContent>
                </Card>
            ))}
        </div>
    );
}