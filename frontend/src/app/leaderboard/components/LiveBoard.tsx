'use client';

import { Flame, Sparkles, Target, Trophy, Zap } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import type { LiveBoardRow } from '../types';

interface Props {
    rows: LiveBoardRow[];
    myUserId?: number;
}

/**
 * Top-10 live leaderboard. Only rendered when the user-base crosses the
 * `LEADERBOARD_LIVE_THRESHOLD` env value (default 50 real weekly-active
 * users). Below threshold the envelope omits this so the small-user
 * count is never exposed on the page.
 */
export default function LiveBoard({ rows, myUserId }: Props) {
    if (!rows || rows.length === 0) return null;

    return (
        <Card className="border-emerald-500/25 bg-gradient-to-br from-emerald-500/8 via-card to-card">
            <CardContent className="p-5 space-y-3">
                <div className="flex items-center gap-2">
                    <Trophy className="w-5 h-5 text-emerald-500" />
                    <h3 className="font-bold text-foreground">Top 10 this week — live</h3>
                    <span className="ml-auto inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                        Live
                    </span>
                </div>

                <ul className="divide-y divide-border/60">
                    {rows.map((row) => {
                        const isMe = row.user_id === myUserId;
                        return (
                            <li
                                key={row.user_id}
                                className={`flex items-center gap-3 py-2.5 ${isMe ? 'bg-primary/5 -mx-2 px-2 rounded-lg' : ''}`}
                            >
                                <span className={`w-7 text-center text-sm font-bold ${row.rank <= 3 ? 'text-amber-500' : 'text-muted-foreground'}`}>
                                    {row.rank <= 3 ? <Sparkles className="w-4 h-4 inline" /> : `#${row.rank}`}
                                </span>
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-semibold truncate">
                                        @{row.username}
                                        {isMe && (
                                            <span className="ml-2 text-[10px] font-bold uppercase tracking-wider text-primary">
                                                You
                                            </span>
                                        )}
                                    </p>
                                    {row.college && (
                                        <p className="text-[10px] text-muted-foreground truncate">{row.college}</p>
                                    )}
                                </div>
                                <div className="flex items-center gap-3 text-xs text-muted-foreground shrink-0">
                                    <span className="hidden sm:inline-flex items-center gap-1">
                                        <Flame className="w-3 h-3 text-orange-500" />
                                        {row.current_streak}d
                                    </span>
                                    <span className="hidden sm:inline-flex items-center gap-1">
                                        <Target className="w-3 h-3 text-emerald-500" />
                                        {row.accuracy.toFixed(0)}%
                                    </span>
                                    <span className="inline-flex items-center gap-1 font-semibold text-foreground">
                                        <Zap className="w-3.5 h-3.5 text-yellow-500" />
                                        {row.xp_points.toLocaleString()}
                                    </span>
                                </div>
                            </li>
                        );
                    })}
                </ul>
            </CardContent>
        </Card>
    );
}